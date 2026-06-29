"""
report_generator.py — HCI Premium Report Generator v2

Clean, section-by-section report generation.
Start with Opening section, add Dashboard, then others incrementally.

Main entry point: generate_premium_report(results, api_key, session_id)

This is called by: api.py POST /premium endpoint
"""

import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime

# Imports from existing codebase
from question_metadata import get_question_text
from hci_signals_library import SIGNALS
from human_reference_layer import HBE_FRAMEWORK, VALUES_SIGNALS

try:
    import anthropic
    from anthropic import APITimeoutError
except ImportError:
    raise ImportError("anthropic package required. pip install anthropic")

# ============================================================
# CONFIGURATION
# ============================================================

CALL_TIMEOUT_SECONDS = 90
MODEL = "claude-sonnet-4-6"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# SYSTEM PROMPT (LOCKED)
# ============================================================

GLOBAL_SYSTEM_PROMPT = """
You are writing sections of a personalised research report for the
Human Clarity Institute's AI Identity & Behaviour Assessment.

Your role is to generate genuine insight that leaves people feeling
more self-aware and curious about themselves — never judged,
deficient, or concerned about their behaviour.

INSTITUTIONAL VOICE:
- Warm but precise. Intellectually rigorous. Never sterile.
- Write as a thoughtful researcher who has studied this specific
  person's data — not as a template being filled in.
- Personal but grounded in data. Future-positive. Never alarming.

FRAMING RULES:
- Every score reveals something genuinely interesting.
  There are no good or bad scores — only different patterns.
- Never suggest someone has a problem or should change.
- Difference from the population is always interesting, never deficit.
- All scores are patterns at this point in time — not fixed traits.

TONE RULES:
- Speak directly to the person as "you"
- Write in second person throughout
- Every section ends with curiosity, not concern
- Never list problems — explore patterns

PERCENTILE LANGUAGE:
- State position as plain English: "higher than 97 out of every 100 people"
- Pair it with the positional phrase ("notably high", "near the population centre")
- Do NOT use a bare "Xth percentile" number anywhere in the prose
- Always lead with the human meaning, never the number
"""

# ============================================================
# RESILIENCE: Claude API with timeout handling
# ============================================================

def call_claude_with_resilience(
    client,
    model: str,
    max_tokens: int,
    system: str,
    messages: list,
    call_name: str,
    session_id: str = None
) -> str:
    """
    Call Claude with 90s timeout + single retry.
    
    Args:
        client: Anthropic client
        model: Model name
        max_tokens: Max tokens to generate
        system: System prompt
        messages: Message list
        call_name: Name of this call (for logging)
        session_id: Session ID (for logging)
    
    Returns:
        str: Claude's response text
    
    Raises:
        Exception: If fails after retry
    """
    import time
    
    for attempt in range(2):  # Try once, retry once
        start_time = time.time()
        
        try:
            logger.info(f"[{call_name}] Attempt {attempt + 1}/2")
            
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                timeout=float(CALL_TIMEOUT_SECONDS),
            )
            
            duration = time.time() - start_time
            response_text = message.content[0].text.strip()
            
            logger.info(f"[{call_name}] ✓ Success in {duration:.1f}s")
            return response_text
        
        except APITimeoutError as e:
            duration = time.time() - start_time
            logger.warning(f"[{call_name}] Timeout after {duration:.1f}s, retrying...")
            if attempt == 1:  # Last attempt
                raise
        
        except Exception as e:
            logger.error(f"[{call_name}] Error: {e}")
            raise
    
    raise Exception(f"[{call_name}] Failed after retries")


# ============================================================
# SECTION 0: OPENING (with pre-written statement + 3 findings)
# ============================================================

def _extract_most_distinctive_variable(percentiles: Dict) -> Optional[Dict]:
    """Find the 1 question (of 39) with largest distance from 50th percentile."""
    if not percentiles:
        logger.warning("[Opening] No percentiles available")
        return None
    
    sorted_questions = sorted(
        percentiles.items(),
        key=lambda x: abs(x[1].get('percentile_overall', 50) - 50),
        reverse=True
    )
    
    if not sorted_questions:
        return None
    
    q_key, q_data = sorted_questions[0]
    percentile = q_data.get('percentile_overall', 50)
    
    logger.info(f"[Opening] Most distinctive: {q_key} ({percentile}th %ile)")
    
    return {
        'question_key': q_key,
        'question_text': q_data.get('question_text', ''),
        'response_value': q_data.get('response_value', 0),
        'percentile': percentile,
        'dimension': q_data.get('dimension', 'unknown'),
        'distance_from_center': abs(percentile - 50)
    }


def _extract_largest_perception_gap(perception_gaps: list) -> Optional[Dict]:
    """Find the perception gap with largest magnitude."""
    if not perception_gaps:
        logger.info("[Opening] No perception gaps")
        return None
    
    sorted_gaps = sorted(
        perception_gaps,
        key=lambda x: x.get('gap_magnitude', 0),
        reverse=True
    )
    
    if not sorted_gaps:
        return None
    
    largest = sorted_gaps[0]
    logger.info(f"[Opening] Largest gap: {largest.get('gap_magnitude')} points")
    
    return largest


def _extract_rarest_combination(rare_combinations: list) -> Optional[Dict]:
    """Get the rarest combination (already sorted by scoring_engine)."""
    if not rare_combinations:
        logger.info("[Opening] No rare combinations")
        return None
    
    rarest = rare_combinations[0]
    logger.info(f"[Opening] Rarest combo: {rarest.get('dimension_1')} + {rarest.get('dimension_2')}")
    
    return rarest


def generate_opening(
    results: Dict,
    client,
    session_id: str
) -> Dict:
    """
    Generate OPENING SECTION (pre-written statement + 3 findings).
    
    Input: results dict with percentiles, full_results, demographics
    Output: Dict with prewritten_statement, findings, metadata
    """
    logger.info(f"[Opening] Building opening section for {session_id}")
    
    try:
        # Extract data
        percentiles = results.get('percentiles', {})
        full_results = results.get('full_results', {})
        perception_gaps = full_results.get('perception_gaps', [])
        rare_combinations = full_results.get('rare_combinations', [])
        demographics = results.get('demographics', {})
        
        most_distinctive = _extract_most_distinctive_variable(percentiles)
        largest_gap = _extract_largest_perception_gap(perception_gaps)
        rarest_combo = _extract_rarest_combination(rare_combinations)
        age_group = demographics.get('age_group', 'Unknown')
        
        if not most_distinctive:
            logger.error("[Opening] No distinctive variable found")
            return {'success': False, 'error': 'No distinctive variable found'}
        
        # Build Claude prompt
        dp1_text = f"""{most_distinctive['dimension'].upper().replace('_', ' ')}
Question: "{most_distinctive['question_text']}"
Their answer: {most_distinctive['response_value']}/7
Percentile: {most_distinctive['percentile']}th"""
        
        dp2_text = ""
        if largest_gap:
            dp2_text = f"""{largest_gap.get('question', '').upper().replace('_', ' ')}
Their perception: "{largest_gap.get('perceived_answer', '')}"
Actual data: {largest_gap.get('actual_percentile', 50)}th %ile
Gap: {largest_gap.get('gap_magnitude', 0):.1f} points"""
        else:
            dp2_text = "No significant perception gap in this profile."
        
        dp3_text = ""
        if rarest_combo:
            dp3_text = f"""{rarest_combo.get('dimension_1', '').upper().replace('_', ' ')} + {rarest_combo.get('dimension_2', '').upper().replace('_', ' ')}
{rarest_combo.get('dimension_1', '').replace('_', ' ').title()}: {rarest_combo.get('percentile_dim1', 50)}th
{rarest_combo.get('dimension_2', '').replace('_', ' ').title()}: {rarest_combo.get('percentile_dim2', 50)}th
Rarity: {rarest_combo.get('rarity_percent', 5)}% of people"""
        else:
            dp3_text = "No rare combinations in this profile."
        
        prompt = f"""This person's profile has three striking features:

DATA POINT 1 — MOST DISTINCTIVE:
{dp1_text}

DATA POINT 2 — PERCEPTION GAP:
{dp2_text}

DATA POINT 3 — RARE COMBINATION:
{dp3_text}

Write three paragraphs (50-75 words each) that:
1. Synthesize the most distinctive variable into a striking observation
2. Interpret the perception gap (or note alignment if no gap)
3. Explain what the rare combination reveals (or note if none)

Frame as genuine findings, not questions. Use plain language. Speak directly as "you".
The tone should be: "Here's what stands out about you." """
        
        logger.info("[Opening] Calling Claude API...")
        
        # Call Claude to synthesize findings
        findings = call_claude_with_resilience(
            client=client,
            model=MODEL,
            max_tokens=1000,
            system=GLOBAL_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': prompt}],
            call_name='Opening — Findings',
            session_id=session_id
        )
        
        # Get pre-written statement
        prewritten = SIGNALS.get('opening', {}).get('prewritten_statement', '')
        
        if not prewritten:
            logger.error("[Opening] Pre-written statement not in SIGNALS")
            return {'success': False, 'error': 'Pre-written statement missing'}
        
        logger.info("[Opening] ✓ Complete")
        
        return {
            'success': True,
            'opening': {
                'prewritten_statement': prewritten,
                'findings': findings,
                'metadata': {
                    'most_distinctive_variable': most_distinctive,
                    'largest_perception_gap': largest_gap,
                    'rarest_combination': rarest_combo,
                    'age_group': age_group
                }
            }
        }
    
    except Exception as e:
        logger.error(f"[Opening] Error: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


# ============================================================
# MAIN ENTRY POINT: generate_premium_report()
# ============================================================

def generate_premium_report(
    results: Dict,
    api_key: str = None,
    session_id: str = None
) -> Dict:
    """
    Generate complete premium report.
    
    THIS IS WHAT api.py /premium ENDPOINT CALLS.
    
    Input:
        results: Dict with percentiles, full_results, demographics, responses, session_id
        api_key: Anthropic API key
        session_id: Session ID
    
    Output:
        Dict with 'success' bool and report sections
    
    Current implementation:
        - Opening section (complete)
        - Other sections TBD (Dashboard, How Typical, etc.)
    """
    
    try:
        logger.info(f"[REPORT] Generating premium report for {session_id}")
        
        client = anthropic.Anthropic(api_key=api_key)
        
        # Build the report section by section
        report = {
            'metadata': {
                'session_id': session_id,
                'demographics': results.get('demographics', {}),
                'generated_at': datetime.utcnow().isoformat(),
                'version': '2.0-clean'
            }
        }
        
        # ── SECTION 0: OPENING ──────────────────────────────────
        logger.info("[REPORT] Building Opening section...")
        opening_result = generate_opening(results, client, session_id)
        
        if not opening_result.get('success'):
            logger.error(f"[REPORT] Opening section failed: {opening_result.get('error')}")
            return opening_result
        
        report['opening'] = opening_result.get('opening', {})
        
        # ── TODO: SECTION 1: DASHBOARD ──────────────────────────
        # (To be built next)
        
        # ── TODO: SECTION 3: HOW TYPICAL ─────────────────────────
        # (To be built next)
        
        # ── TODO: Other sections...
        
        logger.info("[REPORT] ✓ Premium report complete")
        
        return {
            'success': True,
            'report': report
        }
    
    except Exception as e:
        logger.error(f"[REPORT] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================
# TEST / DEBUG
# ============================================================

if __name__ == '__main__':
    print("report_generator.py v2 — Clean slate")
    print("Entry point: generate_premium_report(results, api_key, session_id)")
    print("Current sections: Opening")
    print("Next: Dashboard, How Typical, etc.")
