"""
report_builder.py

Clean, section-by-section report builder.
Each function builds ONE report section and returns clean output.
No dependencies between sections. Easy to test.

Purpose:
- Build sections independently
- Test each section before moving to next
- Clear data flow, no silent failures
- Debug individual sections without touching others

Sections built:
1. Opening (this file)
2. Dashboard (next)
3. How Typical (next)
... etc
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
# HELPER: Claude API with resilience
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
    Call Claude with timeout handling and single retry.
    
    Args:
        client: Anthropic client
        model: Model name
        max_tokens: Max tokens to generate
        system: System prompt
        messages: Message history
        call_name: Name of this call (for logging)
        session_id: Session ID (for logging)
    
    Returns:
        str: Claude's response text
    
    Raises:
        Exception: If call fails after retry
    """
    import time
    
    for attempt in range(2):  # Try once, then retry
        start_time = time.time()
        
        try:
            logger.info(f"[{call_name}] Attempt {attempt + 1}/2...")
            
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                timeout=float(CALL_TIMEOUT_SECONDS),
            )
            
            duration = time.time() - start_time
            
            if duration > 10:
                logger.info(f"[{call_name}] Completed in {duration:.1f}s")
            
            response_text = message.content[0].text.strip()
            logger.info(f"[{call_name}] ✓ Success ({len(response_text)} chars)")
            
            return response_text
        
        except APITimeoutError as e:
            duration = time.time() - start_time
            logger.warning(f"[{call_name}] Timeout after {duration:.1f}s, retrying...")
            
            if attempt == 1:  # Last attempt
                logger.error(f"[{call_name}] Failed after retry")
                raise
        
        except Exception as e:
            logger.error(f"[{call_name}] Error: {e}")
            raise
    
    raise Exception(f"[{call_name}] Failed to get response")


# ============================================================
# OPENING SECTION BUILDER
# ============================================================

def _extract_most_distinctive_variable(percentiles: Dict) -> Optional[Dict]:
    """
    Find the single question (of 39) with largest distance from 50th percentile.
    
    Args:
        percentiles: Dict of all question percentile data
    
    Returns:
        Dict with: question_key, question_text, response_value, percentile, dimension
        or None if no percentiles
    """
    if not percentiles:
        logger.warning("[Opening] No percentiles data available")
        return None
    
    # Sort all questions by distance from 50th
    sorted_questions = sorted(
        percentiles.items(),
        key=lambda x: abs(x[1].get('percentile_overall', 50) - 50),
        reverse=True
    )
    
    if not sorted_questions:
        logger.warning("[Opening] No questions in percentiles")
        return None
    
    q_key, q_data = sorted_questions[0]
    percentile = q_data.get('percentile_overall', 50)
    distance = abs(percentile - 50)
    
    logger.info(f"[Opening] Most distinctive variable: {q_key} ({percentile}th %ile, distance: {distance})")
    
    return {
        'question_key': q_key,
        'question_text': q_data.get('question_text', 'Question text not available'),
        'response_value': q_data.get('response_value', 0),
        'percentile': percentile,
        'dimension': q_data.get('dimension', 'unknown'),
        'distance_from_center': distance
    }


def _extract_largest_perception_gap(perception_gaps: list) -> Optional[Dict]:
    """
    Find the perception gap with largest magnitude (self-estimate vs actual).
    
    Args:
        perception_gaps: List of perception gap dicts from full_results
    
    Returns:
        Dict with: gap_magnitude, perceived_answer, actual_percentile, dimension
        or None if no gaps
    """
    if not perception_gaps:
        logger.info("[Opening] No perception gaps found")
        return None
    
    # Sort by gap_magnitude descending
    sorted_gaps = sorted(
        perception_gaps,
        key=lambda x: x.get('gap_magnitude', 0),
        reverse=True
    )
    
    if not sorted_gaps:
        logger.warning("[Opening] Perception gaps list is empty after sort")
        return None
    
    largest_gap = sorted_gaps[0]
    logger.info(f"[Opening] Largest perception gap: {largest_gap.get('gap_magnitude')} points "
                f"({largest_gap.get('question', 'unknown')})")
    
    return {
        'question': largest_gap.get('question', 'unknown'),
        'perceived_answer': largest_gap.get('perceived_answer', 'Unknown'),
        'actual_percentile': largest_gap.get('actual_percentile', 50),
        'perceived_percentile': largest_gap.get('perceived_percentile', 50),
        'gap_magnitude': largest_gap.get('gap_magnitude', 0)
    }


def _extract_rarest_combination(rare_combinations: list) -> Optional[Dict]:
    """
    Find the rarest (lowest rarity %) dimensional combination.
    Already sorted by scoring_engine, so just take [0].
    
    Args:
        rare_combinations: List of rare combo dicts from full_results
    
    Returns:
        Dict with: dimension_1, dimension_2, percentile_dim1, percentile_dim2, rarity_percent
        or None if no combos
    """
    if not rare_combinations:
        logger.info("[Opening] No rare combinations found")
        return None
    
    rarest = rare_combinations[0]
    logger.info(f"[Opening] Rarest combination: {rarest.get('dimension_1')} + "
                f"{rarest.get('dimension_2')} ({rarest.get('rarity_percent')}% rarity)")
    
    return {
        'dimension_1': rarest.get('dimension_1', 'unknown'),
        'dimension_2': rarest.get('dimension_2', 'unknown'),
        'percentile_dim1': rarest.get('percentile_dim1', 50),
        'percentile_dim2': rarest.get('percentile_dim2', 50),
        'rarity_percent': rarest.get('rarity_percent', 5),
        'description': rarest.get('description', '')
    }


def build_opening_section(
    results: Dict,
    api_key: str,
    session_id: str = None
) -> Dict:
    """
    Build the OPENING SECTION (pre-written statement + 3 findings).
    
    Input: results dict containing:
    - results['percentiles']: All 39 question percentile data
    - results['full_results']['perception_gaps']: List of perception gaps
    - results['full_results']['rare_combinations']: List of rare combos
    - results['demographics']['age_group']: Age group for context
    
    Output: Dict with:
    {
        'success': bool,
        'prewritten_statement': str,
        'findings': str (3 paragraphs),
        'metadata': {
            'most_distinctive_variable': dict,
            'largest_perception_gap': dict or None,
            'rarest_combination': dict or None,
            'age_group': str
        }
    }
    
    Raises: Exception if API call fails
    """
    
    logger.info(f"[Opening] Building opening section for session {session_id}")
    
    try:
        # Initialize client
        client = anthropic.Anthropic(api_key=api_key)
        
        # Extract the 3 key findings
        logger.info("[Opening] Extracting data...")
        
        percentiles = results.get('percentiles', {})
        full_results = results.get('full_results', {})
        perception_gaps = full_results.get('perception_gaps', [])
        rare_combinations = full_results.get('rare_combinations', [])
        demographics = results.get('demographics', {})
        
        most_distinctive_var = _extract_most_distinctive_variable(percentiles)
        largest_gap = _extract_largest_perception_gap(perception_gaps)
        rarest_combo = _extract_rarest_combination(rare_combinations)
        age_group = demographics.get('age_group', 'Unknown')
        
        # Validate we have at least some data
        if not most_distinctive_var:
            logger.error("[Opening] Failed to extract most distinctive variable")
            return {
                'success': False,
                'error': 'No distinctive variable found'
            }
        
        logger.info("[Opening] Data extraction complete")
        
        # Build prompt for Claude to synthesize 3 findings
        logger.info("[Opening] Building API prompt...")
        
        # Format data point 1: Most distinctive variable
        dp1_text = f"""{most_distinctive_var['dimension'].upper().replace('_', ' ')}
Question: "{most_distinctive_var['question_text']}"
Their answer: {most_distinctive_var['response_value']}/7
Percentile: {most_distinctive_var['percentile']}th (higher than {most_distinctive_var['distance_from_center']:.0f}% of people)"""
        
        # Format data point 2: Perception gap (if exists)
        dp2_text = ""
        if largest_gap and largest_gap['gap_magnitude'] > 0:
            dp2_text = f"""{largest_gap['question'].upper().replace('_', ' ')}
Their perception: "{largest_gap['perceived_answer']}" (approximately {largest_gap['perceived_percentile']}th %ile)
Actual data: {largest_gap['actual_percentile']}th %ile
Gap: {largest_gap['gap_magnitude']:.1f} percentile points"""
        else:
            dp2_text = "No significant perception gap detected in this profile."
        
        # Format data point 3: Rare combination (if exists)
        dp3_text = ""
        if rarest_combo:
            dp3_text = f"""{rarest_combo['dimension_1'].upper().replace('_', ' ')} + {rarest_combo['dimension_2'].upper().replace('_', ' ')}
{rarest_combo['dimension_1'].replace('_', ' ').title()}: {rarest_combo['percentile_dim1']}th percentile
{rarest_combo['dimension_2'].replace('_', ' ').title()}: {rarest_combo['percentile_dim2']}th percentile
Rarity: Only {rarest_combo['rarity_percent']}% of people show this combination"""
        else:
            dp3_text = "No rare combinations detected in this profile."
        
        # Build the prompt
        prompt = f"""This person's profile has three striking features:

DATA POINT 1 — MOST DISTINCTIVE:
{dp1_text}

DATA POINT 2 — PERCEPTION GAP:
{dp2_text}

DATA POINT 3 — RARE COMBINATION:
{dp3_text}

Write three paragraphs (50-75 words each) that:
1. Synthesize the most distinctive variable into a striking observation
2. Interpret the perception gap (or note alignment if no gap exists)
3. Explain what the rare combination (or absence of rare combos) reveals

Frame each as a genuine finding, not a question. Use plain language, no jargon.
Speak directly as "you". The tone should be: "Here's what stands out about you."
Ensure each paragraph flows naturally and makes intuitive sense."""
        
        logger.info("[Opening] Calling Claude API...")
        
        # Call Claude
        findings = call_claude_with_resilience(
            client=client,
            model=MODEL,
            max_tokens=1000,
            system=GLOBAL_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': prompt}],
            call_name='Opening — Findings Synthesis',
            session_id=session_id
        )
        
        # Get pre-written statement
        prewritten_statement = SIGNALS.get('opening', {}).get('prewritten_statement', '')
        
        if not prewritten_statement:
            logger.error("[Opening] Pre-written statement not found in SIGNALS")
            return {
                'success': False,
                'error': 'Pre-written statement not configured'
            }
        
        logger.info("[Opening] ✓ Opening section complete")
        
        # Return structured output
        return {
            'success': True,
            'prewritten_statement': prewritten_statement,
            'findings': findings,
            'metadata': {
                'most_distinctive_variable': most_distinctive_var,
                'largest_perception_gap': largest_gap,
                'rarest_combination': rarest_combo,
                'age_group': age_group
            },
            'generated_at': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"[Opening] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================
# FOR TESTING
# ============================================================

if __name__ == '__main__':
    print("report_builder.py loaded successfully")
    print("Functions available:")
    print("  - build_opening_section(results, api_key, session_id)")
