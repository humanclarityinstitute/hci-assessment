"""
HCI AI Identity & Behaviour Assessment — Report Generator v9.0

Generates premium reports with 9 focused API calls:
- 6 core calls (Opening, Rare Combos, Behaviour, Distinctive, Perception Gap, Trajectory)
- 3 deep dive calls (Research Lenses, Rare Combo Deep, Cross-Dimensional)

Plus 4 data-only sections (Dashboard, How Typical, Question Profile, Cohort Context)

All calls wrapped with resilience (90s timeout + single retry).
NO PARTIAL REPORTS — if any call fails, entire report fails.
PDF generated and stored in Supabase Storage.
Failure alerts sent to info@humanclarityinstitute.com
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from question_metadata import (
    QUESTION_MAP,
    get_question_text,
    PERCEPTION_QUESTIONS,
    get_perception_text,
    DEMOGRAPHIC_QUESTIONS,
    get_demographic_text,
    is_perception_question,
    is_demographic_question,
    is_assessment_question
)

# ============================================================
# MANDATORY IMPORTS — FAIL HARD IF MISSING
# ============================================================

try:
    import anthropic
    from anthropic import APITimeoutError
except ImportError as e:
    raise ImportError("anthropic package required. pip install anthropic") from e

try:
    from signal_selection import (
        prepare_complete_signal_context,
        format_signal_context_for_api_prompt
    )
except ImportError as e:
    raise ImportError("signal_selection.py required. Check repo.") from e

try:
    from benchmark_context_data import (
        FREQUENCY_GRADIENTS,
        AGE_COHORT_PATTERNS,
        DISTINCTIVE_FLAGS,
        KEY_FINDINGS_FOR_REPORTS,
        PRESSURE_POINTS,
        RESEARCH_NUMBERS
    )
except ImportError as e:
    raise ImportError("benchmark_context_data.py required. Check repo.") from e

try:
    from hci_signals_library import SIGNALS
except ImportError as e:
    raise ImportError("hci_signals_library.py required. Check repo.") from e

try:
    from human_reference_layer import (
        HBE_FRAMEWORK,
        VALUES_SIGNALS,
        get_values_reframe,
        apply_research_insight
    )
except ImportError as e:
    raise ImportError("human_reference_layer.py required. Check repo.") from e

# ============================================================
# CONFIGURATION
# ============================================================

CALL_TIMEOUT_SECONDS = 90
MAX_RETRIES_PER_CALL = 1
ALERT_EMAIL = "info@humanclarityinstitute.com"
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

LANGUAGE TO NEVER USE:
- concerning, worrying, problematic, at risk
- you should, you need to, you must
- loss of agency, cognitive decline, addiction, dependency
- alarming, dangerous, red flag

LANGUAGE TO USE:
- interesting, revealing, distinctive, worth exploring
- your pattern, your positioning, your profile
- people with similar profiles tend to...
- what appears worth protecting
- raises an interesting question
"""

# ============================================================
# RESILIENCE & FAILURE HANDLING
# ============================================================

def notify_failure(call_name: str, error: Exception, session_id: str, user_email: str):
    """
    Alert admins when API call fails.
    In production: sends email to info@humanclarityinstitute.com
    """
    timestamp = datetime.utcnow().isoformat()
    error_type = type(error).__name__
    error_msg = str(error)[:200]
    
    alert = f"""
REPORT GENERATION FAILURE ALERT

Session ID: {session_id}
User Email: {user_email}
Failed Call: {call_name}
Error Type: {error_type}
Error Message: {error_msg}
Timestamp: {timestamp}

ADMIN ACTION REQUIRED:
Go to: https://web-production-381d3.up.railway.app/recover-report
Paste session ID above and click "Rebuild Report"

The system will regenerate all 9 API calls and send a new report to the user.
    """
    
    logger.error(alert)
    # TODO: In production, send email to ALERT_EMAIL
    # For now, log it
    print(alert)


def call_claude_with_resilience(
    client,
    model: str,
    max_tokens: int,
    system: str,
    messages: List[Dict],
    call_name: str,
    session_id: str = None
) -> str:
    """
    Call Claude with 90s timeout + single retry on timeout.
    NO PARTIAL REPORTS — if this fails, the whole report fails.
    """
    
    for attempt in range(MAX_RETRIES_PER_CALL + 1):
        start_time = time.time()
        
        try:
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                timeout=float(CALL_TIMEOUT_SECONDS),
            )
            
            duration = time.time() - start_time
            
            if duration > 30:
                logger.info(
                    f"[SLOW] {call_name} completed in {duration:.1f}s "
                    f"(session: {session_id})"
                )
            
            return message.content[0].text.strip()
        
        except APITimeoutError as e:
            duration = time.time() - start_time
            logger.warning(
                f"[TIMEOUT] {call_name} timed out after {duration:.1f}s "
                f"(attempt {attempt + 1}/{MAX_RETRIES_PER_CALL + 1})"
            )
            
            if attempt < MAX_RETRIES_PER_CALL:
                time.sleep(1)
                continue
            else:
                logger.error(
                    f"[FATAL] {call_name} failed on final attempt. "
                    f"NO PARTIAL REPORTS — entire report generation aborted."
                )
                raise
        
        except Exception as e:
            logger.error(
                f"[ERROR] {call_name} failed: {type(e).__name__}: {str(e)[:100]}"
            )
            raise

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def plain_english_percentile(p: Optional[int]) -> str:
    """Convert percentile to plain English."""
    if not p:
        return "at the population centre"
    if p >= 75:
        return f"higher than {p} out of every 100 people"
    elif p >= 50:
        return f"higher than {p} out of every 100 people"
    else:
        return f"lower than {100-p} out of every 100 people"


def get_most_distinctive_variable(responses: Dict, percentiles: Dict) -> tuple:
    """
    Find the question with the largest deviation from 50th percentile.
    Returns: (question_key, percentile, raw_score)
    """
    max_divergence = 0
    most_distinctive = None
    
    for q_key, percentile in percentiles.items():
        if isinstance(percentile, dict):
            p = percentile.get('percentile_overall', 50)
        else:
            p = percentile
        
        divergence = abs(p - 50)
        if divergence > max_divergence:
            max_divergence = divergence
            most_distinctive = (q_key, p)
    
    return most_distinctive if most_distinctive else ('unknown', 50)


def get_perception_gaps(results: Dict) -> List[Dict]:
    """Extract perception gaps from results."""
    gaps = results.get('full_results', {}).get('perception_gaps', [])
    return gaps if isinstance(gaps, list) else []


def get_rare_combinations(results: Dict) -> List[Dict]:
    """Extract rare combinations from results."""
    combos = results.get('full_results', {}).get('rare_combinations', [])
    return combos if isinstance(combos, list) else []

# ============================================================
# API CALL GENERATORS — 9 TOTAL
# ============================================================

def generate_opening(results: Dict, client, session_id: str) -> str:
    """API CALL #1: Opening — Top 3 Findings"""
    
    logger.info("[1/9] Opening — Top 3 Findings")
    
    dimensions = results.get('full_results', {}).get('dimension_scores', {})
    demographics = results.get('demographics', {})
    perception_gaps = get_perception_gaps(results)
    rare_combos = get_rare_combinations(results)
    percentiles = results.get('percentiles', {})
    
    # Get signal context for most distinctive dimension
    top_dim_name = max(
        dimensions.keys(),
        key=lambda x: abs(dimensions[x].get('percentile_overall', 50) - 50)
    ) if dimensions else 'trust'
    
    top_dim_percentile = dimensions.get(top_dim_name, {}).get('percentile_overall', 50)
    
    signal_context = prepare_complete_signal_context(
        dimension=top_dim_name,
        actual_score=dimensions.get(top_dim_name, {}).get('raw_score', 3.5),
        frequency=demographics.get('ai_tool_use_frequency', 'sometimes'),
        age_group=demographics.get('age_group', '25-34'),
        actual_percentile=top_dim_percentile
    )
    
    signal_text = format_signal_context_for_api_prompt(signal_context, 'Opening')
    
    # Find largest perception gap
    largest_gap = max(perception_gaps, key=lambda x: abs(x.get('gap_magnitude', 0))) if perception_gaps else None
    
    # Get rare combo context
    combo_text = ""
    if rare_combos:
        combo = rare_combos[0]
        combo_key = f"{combo.get('dimension_1')}_{combo.get('dimension_2')}"
        if combo_key in SIGNALS.get('combinations', {}):
            combo_text = SIGNALS['combinations'][combo_key].get('what_it_reveals', '')
    
    # Map perception question keys to dimension names
    perception_to_dimension_name = {
        'perceived_usage': 'Reliance (Usage)',
        'perceived_reliance': 'Reliance',
        'perceived_dependence': 'Reliance (Dependence)'
    }
    
    prompt = f"""
This person's profile has three striking features:

DATA POINT 1 — MOST DISTINCTIVE DIMENSION:
{top_dim_name.replace('_', ' ').title()}: {plain_english_percentile(top_dim_percentile)}

RESEARCH SIGNALS:
{signal_text}

{f'''DATA POINT 2 — PERCEPTION GAP:
{perception_to_dimension_name.get(largest_gap['question'], largest_gap['question'].replace('_', ' ').title())}: 
They estimated {largest_gap['perceived_answer']}, but actually score {largest_gap['actual_percentile']}th percentile. 
Gap: {largest_gap['gap_magnitude']:.1f} points.
''' if largest_gap else ''}

{f'''DATA POINT 3 — RARE COMBINATION:
{combo_text}
''' if combo_text else ''}

Write three paragraphs (50-75 words each) that:
1. Open with what's striking about their most distinctive dimension
2. Observe their perception gap (if exists)
3. Highlight their rare combination (if exists)

Frame as findings, not questions. Use plain language. Speak directly as "you".
Tone: "Here's what stands out about you."
    """
    
    return call_claude_with_resilience(
        client,
        model=MODEL,
        max_tokens=1000,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Opening — Top 3 Findings',
        session_id=session_id
    )


def generate_rare_combinations(results: Dict, client, session_id: str) -> str:
    """API CALL #2: Rare Combinations Analysis"""
    
    logger.info("[2/9] Rare Combinations")
    
    dimensions = results.get('full_results', {}).get('dimension_scores', {})
    rare_combos = get_rare_combinations(results)
    demographics = results.get('demographics', {})
    
    if not rare_combos:
        return "No rare combinations detected in this profile."
    
    combo = rare_combos[0]
    dim1 = combo.get('dimension_1', 'unknown')
    dim2 = combo.get('dimension_2', 'unknown')
    
    combo_key = f"{dim1}_{dim2}"
    combo_signal = SIGNALS.get('combinations', {}).get(combo_key, {})
    
    prompt = f"""
This person has a distinctive combination:

{dim1.title()}: {combo.get('percentile_dim1')}th percentile
{dim2.title()}: {combo.get('percentile_dim2')}th percentile

This combination appears in approximately {combo.get('rarity_percent', 5)}% of HCI's research.

Research shows this combination is interesting because:
{combo_signal.get('why_unusual', 'This reveals a distinctive pattern.')}

What it reveals about their relationship with AI:
{combo_signal.get('what_it_reveals', 'Worth exploring further.')}

Write 150-200 words analyzing what this rare combination suggests about their 
engagement with AI. Ground in research. Speak directly to them.
    """
    
    return call_claude_with_resilience(
        client,
        model=MODEL,
        max_tokens=800,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Rare Combinations',
        session_id=session_id
    )


def generate_behaviour_story(results: Dict, client, session_id: str) -> str:
    """API CALL #3: Behaviour Story"""
    
    logger.info("[3/9] Behaviour Story")
    
    dimensions = results.get('full_results', {}).get('dimension_scores', {})
    demographics = results.get('demographics', {})
    
    # Build dimension summary
    dim_summary = ""
    for dim_name, dim_data in dimensions.items():
        percentile = dim_data.get('percentile_overall', 50)
        dim_summary += f"- {dim_name.title()}: {percentile}th percentile\n"
    
    prompt = f"""
Here is this person's complete profile across all 9 dimensions:

{dim_summary}

Demographics:
- Age group: {demographics.get('age_group', 'unknown')}
- AI usage frequency: {demographics.get('ai_tool_use_frequency', 'unknown')}

Write a 300-400 word narrative that tells the "story" of how this person engages
with AI. Not a list of scores — a connected narrative.

What pattern emerges when you look at all 9 dimensions together?
How do these dimensions relate and support each other?
What's distinctive about their overall approach to AI?

Tone: You're a researcher who has studied this person's data. Tell the story
of their relationship with AI in a way that makes them feel understood.
    """
    
    return call_claude_with_resilience(
        client,
        model=MODEL,
        max_tokens=1000,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Behaviour Story',
        session_id=session_id
    )


def generate_distinctive_responses(results: Dict, client, session_id: str) -> str:
    """API CALL #4: Distinctive Responses"""
    
    logger.info("[4/9] Distinctive Responses")
    
    percentiles = results.get('percentiles', {})
    
    # Find most distinctive responses (furthest from 50th percentile)
    distinctive = []
    for q_key, p_data in percentiles.items():
        if isinstance(p_data, dict):
            percentile = p_data.get('percentile_overall', 50)
        else:
            percentile = p_data
        
        divergence = abs(percentile - 50)
        if divergence > 20:
            distinctive.append((q_key, percentile, divergence))
    
    distinctive.sort(key=lambda x: x[2], reverse=True)
    top_distinctive = distinctive[:3]
    
    distinctive_text = "\n".join([
        f"- {q_key}: {p}th percentile"
        for q_key, p, _ in top_distinctive
    ])
    
    prompt = f"""
This person has these distinctive question-level responses:

{distinctive_text}

Analyze what these distinctive responses reveal:
1. What pattern emerges across these responses?
2. Do they cluster around a theme or dimension?
3. What do they suggest about this person's approach to AI?

Write 200-250 words that illuminate what these specific responses reveal
about their pattern. Ground in the data. Make it personal.
    """
    
    return call_claude_with_resilience(
        client,
        model=MODEL,
        max_tokens=800,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Distinctive Responses',
        session_id=session_id
    )


def generate_perception_gap(results: Dict, client, session_id: str) -> str:
    """API CALL #5: Perception Gap"""
    
    logger.info("[5/9] Perception Gap")
    
    gaps = get_perception_gaps(results)
    
    if not gaps:
        return "No significant perception gaps detected in this profile."
    
    # Map question keys to readable names
    question_to_name = {
        'perceived_usage': 'Usage',
        'perceived_reliance': 'Reliance',
        'perceived_dependence': 'Dependence'
    }
    
    gap_text = "\n".join([
        f"- {question_to_name.get(g['question'], g['question'].replace('_', ' ').title())}: "
        f"Estimated {g['perceived_answer']}, "
        f"actually {g['actual_percentile']}th percentile "
        f"({g['gap_magnitude']:.1f} point gap)"
        for g in gaps[:3]
    ])
    
    prompt = f"""
This person has perception gaps between how they estimate their positioning
and where they actually score:

{gap_text}

Analyze what these gaps reveal:
1. What's the largest and most interesting gap?
2. What do overestimates suggest? Underestimates?
3. What does this self-awareness pattern indicate?

Write 200-250 words that synthesize what these perception gaps reveal.
Frame as observation, not judgment.
    """
    
    return call_claude_with_resilience(
        client,
        model=MODEL,
        max_tokens=800,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Perception Gap',
        session_id=session_id
    )


def generate_trajectory(results: Dict, client, session_id: str) -> str:
    """API CALL #6: Trajectory & Outlook"""
    
    logger.info("[6/9] Trajectory & Outlook")
    
    dimensions = results.get('full_results', {}).get('dimension_scores', {})
    demographics = results.get('demographics', {})
    
    # Get highest and lowest
    sorted_dims = sorted(
        dimensions.items(),
        key=lambda x: x[1].get('percentile_overall', 50)
    )
    
    lowest = sorted_dims[0][0] if sorted_dims else 'unknown'
    highest = sorted_dims[-1][0] if sorted_dims else 'unknown'
    
    prompt = f"""
This person's current profile shows:
- Highest dimension: {highest.title()} 
- Lowest dimension: {lowest.title()}
- Age group: {demographics.get('age_group', 'unknown')}
- Usage frequency: {demographics.get('ai_tool_use_frequency', 'unknown')}

Based on their current positioning and research on how AI engagement patterns
evolve, what trajectory might this person be on?

1. What does research show about people with this profile pattern?
2. Where might they find growth or challenge?
3. What appears worth protecting as their use evolves?
4. What would intentional engagement look like for them?

Write 250-300 words exploring their likely trajectory. 
Tone: Forward-positive, curious about possibilities.
    """
    
    return call_claude_with_resilience(
        client,
        model=MODEL,
        max_tokens=1000,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Trajectory & Outlook',
        session_id=session_id
    )


def generate_deep_dive_1(results: Dict, client, session_id: str) -> str:
    """API CALL #7: Deep Dive Part 1 — Research Lenses"""
    
    logger.info("[7/9] Deep Dive Part 1 — Research Lenses")
    
    dimensions = results.get('full_results', {}).get('dimension_scores', {})
    demographics = results.get('demographics', {})
    
    # Build dimension overview
    dim_overview = "\n".join([
        f"- {k.title()}: {v.get('percentile_overall', 50)}th percentile"
        for k, v in dimensions.items()
    ])
    
    prompt = f"""
This person's complete profile:

{dim_overview}

Age group: {demographics.get('age_group', 'unknown')}
Usage frequency: {demographics.get('ai_tool_use_frequency', 'unknown')}

Examine this profile through multiple research lenses:

LENS 1: INTENTIONALITY
How intentional vs passive does their profile suggest?

LENS 2: AGENCY & BOUNDARY-SETTING  
How well do they maintain human agency?

LENS 3: TRUST & VERIFICATION
How does their trust align with their verification behavior?

LENS 4: RELATIONAL ENGAGEMENT
How relational vs instrumental is their engagement?

LENS 5: COHERENCE
How coherent is their overall pattern?

Write 400-500 words applying these lenses to their specific profile.
Make it deep and specific — not generic. Show how research explains their pattern.

Tone: Research-grounded, analytical, illuminating.
    """
    
    return call_claude_with_resilience(
        client,
        model=MODEL,
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Deep Dive Part 1 — Research Lenses',
        session_id=session_id
    )


def generate_deep_dive_4(results: Dict, client, session_id: str) -> str:
    """API CALL #8: Deep Dive Part 4 — Rare Combination Deep"""
    
    logger.info("[8/9] Deep Dive Part 4 — Rare Combination Deep")
    
    rare_combos = get_rare_combinations(results)
    
    if not rare_combos:
        return "No rare combinations for deep dive."
    
    combo = rare_combos[0]
    
    prompt = f"""
This person has a rare combination:

{combo.get('dimension_1', 'X').title()}: {combo.get('percentile_dim1', 50)}th percentile
{combo.get('dimension_2', 'Y').title()}: {combo.get('percentile_dim2', 50)}th percentile

This combination appears in approximately {combo.get('rarity_percent', 5)}% of the research.

Draw from HCI's 21-dataset research to explore:

1. What do people with this combination typically look like?
2. How does this combination relate to usage patterns?
3. What other dimensions typically co-occur with this combo?
4. What does research show about stability of this combo?
5. What does this combo reveal about their relationship with AI?

Write 350-400 words providing deep, research-grounded context about this
specific combination. Not generic — show what research reveals.

Tone: Research-grounded, illuminating, specific to their data.
    """
    
    return call_claude_with_resilience(
        client,
        model=MODEL,
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Deep Dive Part 4 — Rare Combination Deep',
        session_id=session_id
    )


def generate_deep_dive_5(results: Dict, client, session_id: str) -> str:
    """API CALL #9: Deep Dive Part 5 — Cross-Dimensional Story"""
    
    logger.info("[9/9] Deep Dive Part 5 — Cross-Dimensional Story")
    
    dimensions = results.get('full_results', {}).get('dimension_scores', {})
    
    dim_overview = "\n".join([
        f"- {k.title()}: {v.get('percentile_overall', 50)}th percentile"
        for k, v in dimensions.items()
    ])
    
    prompt = f"""
This person's complete 9-dimension profile:

{dim_overview}

Analyze the cross-dimensional architecture:

1. How do high dimensions enable or reinforce each other?
2. How do low dimensions suggest intentional boundaries?
3. What's the "architecture" — how dimensions relate?
4. Are high dimensions coherent or in tension?
5. Do low dimensions represent passive absence or active boundary-setting?

What does research show about people with THIS specific dimensional architecture?

Write 350-400 words analyzing how dimensions work together and what that
reveals about their relationship with AI.

Tone: Analytical, research-grounded. Explore the architecture not just 
individual dimensions.
    """
    
    return call_claude_with_resilience(
        client,
        model=MODEL,
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Deep Dive Part 5 — Cross-Dimensional Story',
        session_id=session_id
    )

# ============================================================
# DATA-ONLY SECTIONS (NO API CALLS)
# ============================================================

def generate_dashboard(results: Dict) -> Dict:
    """DATA-ONLY: Dashboard of all 9 dimensions"""
    
    logger.info("[Dashboard] Compiling 9 dimensions")
    
    dimensions = results.get('full_results', {}).get('dimension_scores', {})
    
    dashboard = {
        'title': 'Benchmark Dashboard',
        'dimensions': {}
    }
    
    for dim_name, dim_data in dimensions.items():
        percentile = dim_data.get('percentile_overall', 50)
        
        # Get research signal for this dimension
        signal = SIGNALS.get('dimensions', {}).get(dim_name, {})
        if percentile >= 60:
            insight = signal.get('high', 'At the high end of this dimension')
        elif percentile <= 40:
            insight = signal.get('low', 'At the low end of this dimension')
        else:
            insight = signal.get('typical', 'In the middle range')
        
        dashboard['dimensions'][dim_name] = {
            'percentile': percentile,
            'percentile_text': plain_english_percentile(percentile),
            'raw_score': dim_data.get('raw_score', 3.5),
            'research_insight': insight
        }
    
    return dashboard


def generate_how_typical(results: Dict) -> Dict:
    """DATA-ONLY: How typical vs distinctive"""
    
    logger.info("[How Typical] Analyzing distinctive variables")
    
    percentiles = results.get('percentiles', {})
    
    distinctive = []
    typical = []
    
    for q_key, p_data in percentiles.items():
        percentile = p_data.get('percentile_overall', 50) if isinstance(p_data, dict) else p_data
        
        if abs(percentile - 50) > 25:
            distinctive.append((q_key, percentile))
        elif abs(percentile - 50) < 10:
            typical.append((q_key, percentile))
    
    return {
        'title': 'Distinctive vs Typical',
        'distinctive_count': len(distinctive),
        'typical_count': len(typical),
        'distinctive_questions': distinctive[:5],
        'typical_questions': typical[:5]
    }


def generate_question_profile(results: Dict) -> Dict:
    """
    DATA-ONLY: All 39 assessment questions with their percentiles
    
    NOTE: Perception questions (perceived_usage, perceived_reliance, perceived_dependence)
    are EXCLUDED from this profile because:
    1. They have text answers, not 1-7 scale responses
    2. They don't have individual percentiles/histograms
    3. They're analyzed separately in Section 5 (Perception Gap Analysis)
    4. Their contribution is the perception_gaps field, not direct histogram data
    """
    
    logger.info("[Question Profile] Compiling all 39 assessment questions (excluding 3 perception questions)")
    
    percentiles = results.get('percentiles', {})
    responses = results.get('responses', {})
    demographics = results.get('demographics', {})
    
    profile = {
        'title': 'Question Profile',
        'total_questions': 39,  # ONLY assessment questions, not perception
        'questions': []
    }
    
    question_count = 0  # Count for numbering (skip perception questions)
    
    for q_key in sorted(percentiles.keys()):
        # SKIP perception questions - they're handled in Section 5 (perception_gaps)
        # Perception questions have text answers like "Much more than most people", not 1-7 scale
        if is_perception_question(q_key):
            logger.debug(f"[Question Profile] Skipping perception question: {q_key}")
            continue
        
        # Only process assessment questions (39 total)
        if not is_assessment_question(q_key):
            logger.debug(f"[Question Profile] Skipping non-assessment question: {q_key}")
            continue
        
        question_count += 1
        p_data = percentiles[q_key]
        percentile = p_data.get('percentile_overall', 50) if isinstance(p_data, dict) else p_data
        response_value = responses.get(q_key, 4)  # Default to neutral (4 on 1-7 scale)
        
        # Extract all fields from percentiles
        dimension = p_data.get('dimension', 'unknown') if isinstance(p_data, dict) else 'unknown'
        
        # Use question_metadata as source of truth for question text
        # All 39 questions are in QUESTION_MAP
        question_text = get_question_text(q_key)
        
        age_percentile = p_data.get('percentile_age_group', 50) if isinstance(p_data, dict) else 50
        distribution = p_data.get('distribution', []) if isinstance(p_data, dict) else []
        print(f"[DEBUG] Processing {q_key}: p_data type={type(p_data).__name__}")
        if isinstance(p_data, dict):
        print(f"[DEBUG] {q_key} has 'dimension' key? {'dimension' in p_data}")
        print(f"[DEBUG] {q_key} dimension value = {p_data.get('dimension', 'MISSING')}")
        profile['questions'].append({
            'dimension': dimension,
            'number': question_count,  # Correct numbering (1-39, not 1-42)
            'variable': question_text,
            'respondent_answer': response_value,
            'respondent_percentile': percentile,
            'age_group': demographics.get('age_group', '25-34'),
            'age_percentile': age_percentile,
            'distribution': distribution
        })
    
    logger.info(f"[Question Profile] Built profile with {question_count} questions")
    return profile


def generate_cohort_context(results: Dict) -> Dict:
    """DATA-ONLY: Age group / cohort context"""
    
    logger.info("[Cohort Context] Analyzing cohort patterns")
    
    demographics = results.get('demographics', {})
    age_group = demographics.get('age_group', '25-34')
    
    cohort_signal = SIGNALS.get('cohorts', {}).get(age_group, {})
    
    return {
        'title': 'Your Cohort in Research',
        'age_group': age_group,
        'cohort_description': cohort_signal.get('description', 'Unknown cohort'),
        'what_distinctive': cohort_signal.get('what_high', []),
        'pressure_points': cohort_signal.get('what_pressured', []),
        'research_signal': cohort_signal.get('signal', 'Research context available')
    }

# ============================================================
# JSON SERIALIZATION HELPER
# ============================================================

def make_json_safe(obj):
    """
    Recursively convert non-JSON-serializable Python objects to JSON-safe types.
    Handles datetime, UUID, Decimal, and nested structures.
    
    This ensures report_dict can be successfully serialized when saving to database.
    """
    from uuid import UUID
    from decimal import Decimal
    
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_safe(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj

# ============================================================
# MAIN REPORT GENERATOR
# ============================================================

def generate_premium_report(
    results: Dict,
    api_key: str = None,
    session_id: str = None
) -> Dict:
    """
    Generate complete premium report using 9 focused API calls.
    
    ALL 9 CALLS REQUIRED — NO SKIPPING
    NO PARTIAL REPORTS — FAIL COMPLETELY OR SUCCEED COMPLETELY
    """
    
    client = anthropic.Anthropic(api_key=api_key)
    
    session_id = session_id or results.get('session_id', 'unknown')
    demographics = results.get('demographics', {})
    
    logger.info(f"[REPORT] Starting premium report generation — Session {session_id}")
    logger.info(f"[REPORT] Starting 9 API calls (6 core + 3 deep dive)...")
    
    try:
        # ── API CALL #1: Opening ──────────────────────────────────────────────
        opening = generate_opening(results, client, session_id)
        
        # ── DASHBOARD (no API) ────────────────────────────────────────────────
        dashboard = generate_dashboard(results)
        
        # ── HOW TYPICAL (no API) ──────────────────────────────────────────────
        how_typical = generate_how_typical(results)
        
        # ── API CALL #2: Rare Combinations ────────────────────────────────────
        rare_combos = generate_rare_combinations(results, client, session_id)
        
        # ── API CALL #3: Behaviour Story ──────────────────────────────────────
        behaviour_story = generate_behaviour_story(results, client, session_id)
        
        # ── QUESTION PROFILE (no API) ─────────────────────────────────────────
        question_profile = generate_question_profile(results)
        
        # ── API CALL #4: Distinctive Responses ────────────────────────────────
        distinctive_responses = generate_distinctive_responses(results, client, session_id)
        
        # ── API CALL #5: Perception Gap ───────────────────────────────────────
        perception_gap = generate_perception_gap(results, client, session_id)
        
        # ── API CALL #6: Trajectory & Outlook ─────────────────────────────────
        trajectory = generate_trajectory(results, client, session_id)
        
        # ── DEEP DIVE OPENING ─────────────────────────────────────────────────
        deep_dive_opening = """
Your pattern is complete on its own. This deep dive goes deeper, examining your profile 
through multiple research lenses and showing what your specific combination reveals about 
your relationship with AI.
        """.strip()
        
        # ── API CALL #7: Deep Dive Part 1 ────────────────────────────────────
        deep_dive_part_1 = generate_deep_dive_1(results, client, session_id)
        
        # ── COHORT CONTEXT (no API) ───────────────────────────────────────────
        cohort_context = generate_cohort_context(results)
        
        # ── API CALL #8: Deep Dive Part 4 ────────────────────────────────────
        deep_dive_part_4 = generate_deep_dive_4(results, client, session_id)
        
        # ── API CALL #9: Deep Dive Part 5 ────────────────────────────────────
        deep_dive_part_5 = generate_deep_dive_5(results, client, session_id)
        
        # ── Assemble Report ───────────────────────────────────────────────────
        logger.info("[REPORT] Assembling final report...")
        
        report = {
            'metadata': {
                'session_id': session_id,
                'demographics': demographics,
                'generated_at': datetime.utcnow().isoformat(),
                'version': '9.0',
            },
            'opening': opening,
            'section_1_dashboard': dashboard,
            'section_3_how_typical': how_typical,
            'section_4_what_different': rare_combos,
            'section_5_behaviour_story': behaviour_story,
            'section_6_question_profile': question_profile,
            'section_7_distinctive_responses': distinctive_responses,
            'section_8_perception_gap': perception_gap,
            'section_10_trajectory': trajectory,
            'deep_dive': {
                'opening': deep_dive_opening,
                'part_1_research_lenses': deep_dive_part_1,
                'part_3_cohort_context': cohort_context,
                'part_4_rare_combination': deep_dive_part_4,
                'part_5_cross_dimensional': deep_dive_part_5,
            }
        }
        
        logger.info("[REPORT] ✅ Premium report generation complete (9 API calls: 6 core + 3 deep dive)")
        
        # Ensure all objects are JSON serializable before returning
        report = make_json_safe(report)
        return report
    
    except Exception as e:
        user_email = demographics.get('email', 'unknown')
        notify_failure('Report Generation', e, session_id, user_email)
        raise


if __name__ == '__main__':
    print("Report Generator v9.0 loaded successfully")
    print(f"Model: {MODEL}")
    print(f"Timeout: {CALL_TIMEOUT_SECONDS}s per call")
    print(f"Max retries: {MAX_RETRIES_PER_CALL}")
    print("All signal files imported successfully")
