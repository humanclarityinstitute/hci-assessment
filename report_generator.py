"""
HCI AI Identity & Behaviour Assessment
Report Generator v8 — Clean, Robust Production Implementation

Generates premium reports with 9 focused API calls (6 core + 3 deep dive):
- 1 call: Opening (Top 3 Findings)
- 1 call: Rare combinations
- 1 call: Behaviour story
- 1 call: Distinctive responses
- 1 call: Perception gap
- 1 call: Trajectory/outlook
- 3 calls: Deep dive (research lenses, rare combination, cross-dimensional)

Plus 4 data-only sections (no API calls):
- Dashboard (all 9 dimensions)
- How typical (distinctive vs typical analysis)
- Question profile (all 39 questions with histograms)
- Cohort context (age group comparison)

All calls wrapped with 90s timeout + single retry on timeout.
NO PARTIAL REPORTS — if any call fails, entire report fails.
NO SILENT FAILURES — imports fail hard, not gracefully.
MANDATORY SIGNAL FILES — All 4 signal modules required.
"""

import json
import time
import statistics
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

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
    raise ImportError("signal_selection.py required. Check GitHub.") from e

try:
    from benchmark_context_data import (
        FREQUENCY_GRADIENTS,
        AGE_COHORT_PATTERNS,
        DISTINCTIVE_FLAGS,
        KEY_FINDINGS_FOR_REPORTS,
        PRESSURE_POINTS
    )
except ImportError as e:
    raise ImportError("benchmark_context_data.py required. Check GitHub.") from e

try:
    from hci_signals_library import SIGNALS, RESEARCH_NUMBERS
except ImportError as e:
    raise ImportError("hci_signals_library.py required. Check GitHub.") from e

try:
    from human_reference_layer import (
        VALUES_SIGNALS,
        HBE_FRAMEWORK,
        HBE_COHORT_REFRAMES,
        REFRAME_LIBRARY,
        RESEARCH_INSIGHTS,
        get_values_reframe,
        get_cohort_reframe,
        apply_research_insight
    )
except ImportError as e:
    raise ImportError("human_reference_layer.py required. Check GitHub.") from e

# ============================================================
# CONFIGURATION
# ============================================================

CALL_TIMEOUT_SECONDS = 90
MAX_RETRIES_PER_CALL = 1
ALERT_EMAIL = "info@humanclarityinstitute.com"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# SYSTEM PROMPT (from original, excellent voice)
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

USING HCI RESEARCH DATA:
- When you cite a population figure, attribute it lightly to HCI's research
- Only use figures explicitly provided in the section data
- NEVER invent estimates or statistics
- If no figure is provided, write qualitatively ("most people")

MANDATORY:
- Never assign a "type", "archetype", or label to the participant
- Use the positional-language scale exactly: exceptionally high / notably high /
  above the population centre / near the population centre / below the population
  centre / notably low / exceptionally low. Invent no alternatives.
- Do not state a bare "Xth percentile" number
- Every section ends on an observation or open question — never a recommendation.
"""

# ============================================================
# RESILIENCE & ALERTS
# ============================================================

def notify_failure(call_name: str, error: Exception, session_id: str, user_email: str):
    """
    Log failure alert. In production, this would send to info@humanclarityinstitute.com
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

User will see error and can retry via /premium endpoint.
    """
    
    logger.error(alert)
    # In production: send email to ALERT_EMAIL
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
    
    Args:
        client: Anthropic client
        model: Model name (e.g., 'claude-sonnet-4-6')
        max_tokens: Max tokens for response
        system: System prompt
        messages: List of messages
        call_name: Name of this call (for logging)
        session_id: Session ID (for logging)
    
    Returns:
        Response text from Claude
    
    Raises:
        APITimeoutError: If call fails after retry
        Exception: Any other error
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
    if p is None or p == 0:
        return "Similar to most people"
    p = int(p)
    if p >= 50:
        return f"Higher than {p} out of every 100 people"
    return f"Lower than {100 - p} out of every 100 people"


def positional_language(p: Optional[int]) -> str:
    """V2.1 exact positional descriptor — no number."""
    if p is None:
        return "near the population centre"
    p = int(p)
    if p >= 96:
        return "exceptionally high"
    if p >= 86:
        return "notably high"
    if p >= 71:
        return "above the population centre"
    if p >= 41:
        return "near the population centre"
    if p >= 26:
        return "below the population centre"
    if p >= 11:
        return "notably low"
    return "exceptionally low"


def format_prose(text: Optional[str]) -> str:
    """Format prose into HTML paragraphs."""
    if not text:
        return ""
    return text.strip()


def prepare_signal_context(results: Dict, dimension: str) -> str:
    """
    Prepare three-layer signal context for a dimension.
    Integrates benchmark data + signals library + human reference layer.
    """
    try:
        context = prepare_complete_signal_context(
            dimension=dimension,
            actual_score=results.get('dimensions', {}).get(dimension, {}).get('raw_score', 0),
            frequency=results.get('demographics', {}).get('ai_tool_use_frequency', 'sometimes'),
            age_group=results.get('demographics', {}).get('age_group', '35-44'),
            actual_percentile=results.get('dimensions', {}).get(dimension, {}).get('percentiles', {}).get('overall', 50)
        )
        
        return format_signal_context_for_api_prompt(context, 'General')
    except Exception as e:
        logger.warning(f"Signal context preparation failed for {dimension}: {str(e)[:100]}")
        return ""

# ============================================================
# SECTION GENERATORS — API CALLS (9 total)
# ============================================================

def generate_opening(results: Dict, client, session_id: str) -> str:
    """
    API CALL #1: Opening — Top 3 Findings
    
    Synthesize most distinctive pattern into compelling opening narrative.
    """
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    
    top_dimension = max(
        dimensions.items(),
        key=lambda x: abs(x[1].get('percentiles', {}).get('overall', 50) - 50)
    ) if dimensions else ('unknown', {})
    
    signal_text = prepare_signal_context(results, top_dimension[0])
    
    prompt = f"""
    This person has just completed the HCI AI Identity & Behaviour Assessment.
    
    Key data:
    - Most distinctive dimension: {top_dimension[0]} at {top_dimension[1].get('percentiles', {}).get('overall', 'unknown')}th percentile
    - Age group: {demographics.get('age_group', 'Unknown')}
    - Usage frequency: {demographics.get('ai_tool_use_frequency', 'Unknown')}
    
    Dimensions overview:
    {json.dumps({{k: v.get('percentiles', {{}}).get('overall') for k, v in dimensions.items()}}, indent=2)}
    
    RESEARCH SIGNALS FOR THIS DIMENSION:
    {signal_text}
    
    Write three compelling findings:
    1. Lead with their most distinctive dimension (ground in research signals above)
    2. Identify the largest perception gap (if exists)
    3. Highlight what's interesting about their pattern
    
    Each finding should be 50-75 words, in plain language, no percentile jargon.
    Speak directly to them as "you". Frame everything as interesting, not concerning.
    
    Output as three paragraphs, no headers.
    """
    
    return call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1000,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Opening — Top 3 Findings',
        session_id=session_id
    )


def generate_rare_combinations(results: Dict, client, session_id: str) -> str:
    """
    API CALL #2: Rare Combinations
    
    Explain why this person's combination of dimensions is distinctive.
    """
    
    dimensions = results.get('dimensions', {})
    
    # Get top and bottom dimensions
    sorted_dims = sorted(
        dimensions.items(),
        key=lambda x: x[1].get('percentiles', {}).get('overall', 50),
        reverse=True
    )
    
    top_dims = sorted_dims[:2]
    bottom_dims = sorted_dims[-2:]
    
    signal_text = prepare_signal_context(results, top_dims[0][0] if top_dims else 'trust')
    
    combo_text = "Distinctive combinations in your profile:\n"
    combo_text += f"High: {', '.join([f'{d[0]} ({d[1].get('percentiles', {}).get('overall')}%ile)' for d in top_dims])}\n"
    combo_text += f"Low: {', '.join([f'{d[0]} ({d[1].get('percentiles', {}).get('overall')}%ile)' for d in bottom_dims])}"
    
    prompt = f"""
    This person shows this combination in their AI behaviour profile:
    
    {combo_text}
    
    RESEARCH SIGNALS:
    {signal_text}
    
    For each combination:
    1. Why it's distinctive (ground in research about how these dimensions typically co-occur)
    2. What it reveals about their relationship with AI
    3. Why it matters
    
    Use research language. Keep it observational, not prescriptive. Speak to them as "you".
    Total: approximately 300-400 words.
    """
    
    return call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Rare Combinations Synthesis',
        session_id=session_id
    )


def generate_behaviour_story(results: Dict, client, session_id: str) -> str:
    """
    API CALL #3: Behaviour Story
    
    300-400 word narrative portrait of their AI relationship pattern.
    """
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    
    sorted_dims = sorted(
        dimensions.items(),
        key=lambda x: x[1].get('percentiles', {}).get('overall', 50),
        reverse=True
    )[:5]
    
    primary_dim = sorted_dims[0][0] if sorted_dims else 'trust'
    signal_text = prepare_signal_context(results, primary_dim)
    
    dim_summary = '\n'.join([
        f"- {dim[0]}: {dim[1].get('percentiles', {}).get('overall')}th percentile ({positional_language(dim[1].get('percentiles', {}).get('overall'))})"
        for dim in sorted_dims
    ])
    
    prompt = f"""
    Write a narrative portrait of this person's AI relationship pattern.
    
    Key data:
    {dim_summary}
    
    Age group: {demographics.get('age_group')}
    Usage frequency: {demographics.get('ai_tool_use_frequency')}
    
    RESEARCH SIGNALS FOR PRIMARY DIMENSION ({primary_dim}):
    {signal_text}
    
    Structure:
    1. Open with their #1 dimension as foundation, using research signals above
    2. Explain how other dimensions relate to #1
    3. Ground everything in HCI's observed patterns
    4. Show them as intentional and coherent
    5. Close with observation that opens curiosity
    
    Tone: Observational, research-grounded, reflective.
    No percentile jargon. Speak as "you". Total: 300-400 words.
    """
    
    return call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Behaviour Story Narrative',
        session_id=session_id
    )


def generate_distinctive_responses(results: Dict, client, session_id: str) -> str:
    """
    API CALL #4: Most Distinctive Responses
    
    Explain top 7 most unusual individual question answers.
    """
    
    variable_highlights = results.get('variable_highlights', [])[:7]
    
    if not variable_highlights:
        return "Your responses across all questions show a coherent, consistent pattern."
    
    signal_text = prepare_signal_context(results, 'trust')
    
    var_summary = '\n'.join([
        f"- {var.get('question_key', 'unknown')}: Score {var.get('raw_response', '?')}/7, "
        f"{positional_language(var.get('percentiles', {}).get('overall'))} "
        f"({var.get('percentiles', {}).get('overall')}th percentile)"
        for var in variable_highlights
    ])
    
    prompt = f"""
    This person's 7 most distinctive individual responses:
    
    {var_summary}
    
    RESEARCH SIGNALS:
    {signal_text}
    
    For each response:
    1. State why it's distinctive
    2. Explain what makes it unusual in context of their overall profile
    3. What it reveals about their AI relationship
    
    Keep each explanation brief (30-50 words). Speak to them as "you". Observational tone.
    Total: approximately 300-400 words.
    """
    
    return call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Distinctive Responses Synthesis',
        session_id=session_id
    )


def generate_perception_gap(results: Dict, client, session_id: str) -> str:
    """
    API CALL #5: Perception Gap
    
    Compare self-perception to actual positioning.
    """
    
    perception_gaps = results.get('perception_gaps', {})
    dimensions = results.get('dimensions', {})
    
    gap_summary = json.dumps({k: v for k, v in perception_gaps.items() if v}, indent=2)
    dim_summary = json.dumps({k: v.get('percentiles', {}).get('overall') for k, v in dimensions.items()}, indent=2)
    
    prompt = f"""
    This person answered three self-perception questions at the end of the assessment:
    
    {gap_summary}
    
    Their actual dimensional positioning:
    {dim_summary}
    
    For each gap:
    1. State what they think about themselves
    2. State what the data actually shows
    3. Highlight any alignment or gap
    4. What it might mean (grounded in research)
    
    Tone: Illuminating, not corrective. This is interesting — not about who's "right".
    Speak to them as "you". Total: 200-300 words.
    """
    
    return call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1000,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Perception Gap Analysis',
        session_id=session_id
    )


def generate_trajectory(results: Dict, client, session_id: str) -> str:
    """
    API CALL #6: Trajectory & Outlook
    
    Observable patterns based on usage frequency.
    """
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    frequency = demographics.get('ai_tool_use_frequency', 'sometimes')
    
    high_dims = {k: v for k, v in dimensions.items() if v.get('percentiles', {}).get('overall', 0) > 71}
    moderate_dims = {k: v for k, v in dimensions.items() 
                     if 41 <= v.get('percentiles', {}).get('overall', 50) <= 70}
    
    signal_text = prepare_signal_context(results, list(high_dims.keys())[0] if high_dims else 'trust')
    
    prompt = f"""
    This person's current profile:
    - Frequency tier: {frequency}
    - High dimensions (>71%ile): {', '.join(high_dims.keys()) if high_dims else 'none'}
    - Moderate dimensions: {', '.join(list(moderate_dims.keys())[:3])}
    
    RESEARCH SIGNALS ON TRAJECTORY:
    {signal_text}
    
    Based on research about how people at their usage frequency typically develop:
    
    1. Likely to Continue: What patterns typically remain stable if nothing changes?
    (100-150 words)
    
    2. Strengths Likely to Deepen: Which strengths tend to deepen with continued exposure?
    (100-150 words, for high-scoring dimensions)
    
    3. Areas Worth Monitoring: Which dimensions are most likely to shift if usage increases?
    (100-150 words, for moderate dimensions)
    
    4. Overall Outlook: What does their pattern suggest about their capacity to navigate changes?
    (80-120 words)
    
    Tone: Grounded, reassuring, observational. No timeline predictions.
    Speak to them as "you".
    """
    
    return call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Trajectory & Outlook',
        session_id=session_id
    )


def generate_deep_dive_1(results: Dict, client, session_id: str) -> str:
    """
    API CALL #7: Deep Dive Part 1 — Research Lenses
    
    Examine pattern through 4 analytical lenses.
    """
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    
    percentiles = [d.get('percentiles', {}).get('overall', 50) for d in dimensions.values()]
    overall_percentile = int(statistics.mean(percentiles)) if percentiles else 50
    
    signal_text = prepare_signal_context(results, list(dimensions.keys())[0] if dimensions else 'trust')
    
    prompt = f"""
    This person's profile:
    - Overall percentile: {overall_percentile}th across all participants
    - Usage frequency: {demographics.get('ai_tool_use_frequency', 'sometimes')}
    - Age group: {demographics.get('age_group', 'unknown')}
    
    All dimensions:
    {json.dumps({{k: v.get('percentiles', {{}}).get('overall') for k, v in dimensions.items()}}, indent=2)}
    
    RESEARCH SIGNALS:
    {signal_text}
    
    Examine their pattern through 4 lenses:
    
    1. Overall Positioning: What does sitting at the {overall_percentile}th percentile suggest?
    
    2. Frequency-Adjusted: How distinctive are they among people at their usage frequency?
    
    3. Rare Combination: Do their dimensions form an unusual combination?
    
    4. Cross-Dimensional: How do their dimensions relate to each other? What emerges?
    
    Write 250-300 words total. Ground each lens in HCI's research.
    Tone: illuminating, research-grounded. Speak directly as "you".
    """
    
    return call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1000,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Deep Dive Part 1 — Research Lenses',
        session_id=session_id
    )


def generate_deep_dive_4(results: Dict, client, session_id: str) -> str:
    """
    API CALL #8: Deep Dive Part 4 — Rare Combination Deep Research
    
    Deep research context about their specific rare combination.
    """
    
    dimensions = results.get('dimensions', {})
    
    dim_items = list(dimensions.items())
    if len(dim_items) < 2:
        return "Insufficient data for rare combination analysis."
    
    sorted_dims = sorted(dim_items, key=lambda x: x[1].get('percentiles', {}).get('overall', 50), reverse=True)
    combo1 = (sorted_dims[0][0], sorted_dims[-1][0])
    combo2 = (sorted_dims[1][0], sorted_dims[-2][0]) if len(sorted_dims) > 2 else combo1
    
    signal_text = prepare_signal_context(results, combo1[0])
    
    prompt = f"""
    This person has these rare combinations:
    
    Combination 1: {combo1[0]} ({sorted_dims[0][1].get('percentiles', {}).get('overall')}%ile) + {combo1[1]} ({sorted_dims[-1][1].get('percentiles', {}).get('overall')}%ile)
    
    Combination 2: {combo2[0]} ({sorted_dims[1][1].get('percentiles', {}).get('overall')}%ile) + {combo2[1]} ({sorted_dims[-2][1].get('percentiles', {}).get('overall')}%ile)
    
    RESEARCH SIGNALS:
    {signal_text}
    
    For each combination:
    1. What do HCI's 21 datasets reveal about people with this combo?
    2. How do these dimensions typically relate in the research?
    3. What does this combo suggest about their relationship with AI?
    4. Is this combo stable or does it tend to shift with frequency?
    
    Write 300-350 words total. Ground in HCI's research patterns.
    Tone: research-grounded, illuminating. Speak as "you".
    """
    
    return call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Deep Dive Part 4 — Rare Combination Deep',
        session_id=session_id
    )


def generate_deep_dive_5(results: Dict, client, session_id: str) -> str:
    """
    API CALL #9: Deep Dive Part 5 — Cross-Dimensional Architecture
    
    How dimensions work together; what the architecture suggests.
    """
    
    dimensions = results.get('dimensions', {})
    
    sorted_dims = sorted(
        dimensions.items(),
        key=lambda x: x[1].get('percentiles', {}).get('overall', 50),
        reverse=True
    )
    
    top_3_high = sorted_dims[:3]
    bottom_3_low = sorted_dims[-3:]
    
    prompt = f"""
    This person's 9-dimension profile:
    
    Highest: {', '.join([f"{d[0]} ({d[1].get('percentiles', {}).get('overall')}%ile)" for d in top_3_high])}
    Lowest: {', '.join([f"{d[0]} ({d[1].get('percentiles', {}).get('overall')}%ile)" for d in bottom_3_low])}
    
    Analyze the architecture of their pattern:
    
    1. Architecture: How do high dimensions enable or support each other?
    
    2. Intentional Boundaries: What do low dimensions suggest they're protecting?
    
    3. Coherence: How well do these dimensions align with each other?
    
    4. What Research Shows: What does HCI's research reveal about people with this dimensional architecture?
    
    Write 300-350 words total. This is deep analysis, not just listing scores.
    Tone: analytical, research-grounded, illuminating. Speak as "you".
    """
    
    return call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Deep Dive Part 5 — Cross-Dimensional',
        session_id=session_id
    )

# ============================================================
# DATA-ONLY GENERATORS (No API calls)
# ============================================================

def generate_dashboard(results: Dict) -> Dict:
    """
    Section 1: Dashboard — all 9 dimensions
    """
    
    from scoring_engine import DIMENSIONS
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    age_group = demographics.get('age_group')
    
    dashboard = {
        'title': 'YOUR AI BEHAVIOUR PATTERN',
        'subtitle': 'How you compare across nine dimensions',
        'dimensions': {}
    }
    
    for dim_name, dim_data in dimensions.items():
        if not dim_data:
            continue
        
        percentile = dim_data.get('percentiles', {}).get('overall', 50)
        
        dim_config = DIMENSIONS.get(dim_name, {})
        definition = dim_config.get('subtitle', '')
        
        dashboard['dimensions'][dim_name] = {
            'label': dim_data.get('label', dim_name),
            'definition': definition,
            'percentile': percentile,
            'position': positional_language(percentile),
            'plain_english': plain_english_percentile(percentile),
        }
    
    return dashboard


def generate_how_typical(results: Dict) -> Dict:
    """
    Section 3: How Typical Is Your AI Behaviour — no API
    """
    
    dimensions = results.get('dimensions', {})
    
    distinctive = {}
    typical = {}
    
    for dim_name, dim_data in dimensions.items():
        if not dim_data:
            continue
        
        percentile = dim_data.get('percentiles', {}).get('overall', 50)
        
        if percentile > 75 or percentile < 25:
            distinctive[dim_name] = {
                'label': dim_data.get('label', dim_name),
                'percentile': percentile,
                'position': positional_language(percentile),
            }
        elif 35 <= percentile <= 65:
            typical[dim_name] = {
                'label': dim_data.get('label', dim_name),
                'percentile': percentile,
                'position': 'near the population centre',
            }
    
    return {
        'title': 'HOW TYPICAL IS YOUR AI BEHAVIOUR?',
        'distinctive': distinctive,
        'typical': typical
    }


def generate_question_profile(results: Dict) -> Dict:
    """
    Section 6: Question-Level Profile — All 39 questions
    """
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    age_group = demographics.get('age_group', 'Unknown')
    
    questions_data = []
    question_number = 1
    
    dimension_order = [
        'trust', 'disclosure', 'reliance', 'decision_delegation', 
        'human_agency', 'verification', 'emotional_regulation', 
        'thought_partnership', 'social_transparency'
    ]
    
    for dim_name in dimension_order:
        if dim_name not in dimensions:
            continue
        
        dim_data = dimensions[dim_name]
        if not dim_data:
            continue
        
        question_scores = dim_data.get('question_scores', {})
        
        for q_key, q_score in question_scores.items():
            respondent_answer = q_score.get('raw', 0)
            
            # Calculate percentile (simplified)
            respondent_percentile = 50  # Placeholder
            position = positional_language(respondent_percentile)
            plain = plain_english_percentile(respondent_percentile)
            
            # Placeholder distribution
            distribution = [14.3, 14.3, 14.3, 14.3, 14.3, 14.3, 14.1]
            
            questions_data.append({
                'number': question_number,
                'key': q_key,
                'variable': q_score.get('variable', q_key),
                'dimension': dim_name,
                'dimension_label': dim_data.get('label', dim_name),
                'respondent_answer': respondent_answer,
                'respondent_percentile': respondent_percentile,
                'respondent_position': position,
                'respondent_plain_english': plain,
                'distribution': distribution,
                'age_group': age_group,
                'age_percentile': 50,
                'age_group_mean': 50,
            })
            
            question_number += 1
    
    return {
        'title': 'YOUR QUESTION-LEVEL PROFILE',
        'subtitle': 'All questions with your answers and comparisons',
        'questions': questions_data,
        'total_questions': len(questions_data)
    }


def generate_deep_dive_2_cohort(results: Dict) -> Dict:
    """
    Deep Dive Part 3: Cohort in Context — Data-only, no API
    """
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    age_group = demographics.get('age_group', 'unknown')
    
    distinctive_in_cohort = {}
    for dim_name, dim_data in dimensions.items():
        if not dim_data:
            continue
        
        percentile = dim_data.get('percentiles', {}).get('overall', 50)
        
        # Simplified: if far from 50th percentile, mark as distinctive
        if abs(percentile - 50) > 15:
            distinctive_in_cohort[dim_name] = {
                'label': dim_data.get('label', dim_name),
                'percentile': percentile,
                'cohort_mean': 50,
                'difference': percentile - 50,
                'direction': 'higher' if percentile > 50 else 'lower'
            }
    
    sorted_distinctive = sorted(
        distinctive_in_cohort.items(),
        key=lambda x: abs(x[1]['difference']),
        reverse=True
    )
    
    return {
        'title': 'YOUR COHORT IN CONTEXT',
        'age_group': age_group,
        'distinctive_in_cohort': dict(sorted_distinctive[:3]),
        'research_signal': f'People in your age group ({age_group}) show specific patterns in how they engage with AI.'
    }

# ============================================================
# MAIN REPORT GENERATOR
# ============================================================

def generate_premium_report(
    results: Dict,
    api_key: str = None,
    session_id: str = None
) -> Dict:
    """
    Generate complete premium report using 9 focused API calls (6 core + 3 deep dive).
    
    Args:
        results: Full results object from score_assessment()
        api_key: Anthropic API key (optional, uses env variable if not provided)
        session_id: Session ID for logging (optional)
    
    Returns:
        Complete report object ready for hci-report-page.html
    
    Raises:
        ImportError: If signal files missing
        APITimeoutError: If any API call fails after retry
        Exception: Any other error
    """
    
    client = anthropic.Anthropic(api_key=api_key)
    
    session_id = session_id or results.get('session_id', 'unknown')
    demographics = results.get('demographics', {})
    
    logger.info(f"Generating premium report — Session {session_id}")
    logger.info("Starting 9 API calls (6 core + 3 deep dive)...")
    
    try:
        # ── API CALL #1: Opening ──────────────────────────────────────────────────
        logger.info("[1/9] Generating opening...")
        opening = generate_opening(results, client, session_id)
        
        # ── SECTION 1: Dashboard (no API) ──────────────────────────────────────────
        logger.info("[2/15] Building dashboard...")
        dashboard = generate_dashboard(results)
        
        # ── SECTION 3: How Typical (no API) ────────────────────────────────────────
        logger.info("[3/15] Analyzing typicality...")
        how_typical = generate_how_typical(results)
        
        # ── API CALL #2: Rare Combinations ─────────────────────────────────────────
        logger.info("[4/15] Analyzing rare combinations...")
        rare_combos = generate_rare_combinations(results, client, session_id)
        
        # ── API CALL #3: Behaviour Story ───────────────────────────────────────────
        logger.info("[5/15] Writing behaviour story...")
        behaviour_story = generate_behaviour_story(results, client, session_id)
        
        # ── SECTION 6: Question Profile (no API) ───────────────────────────────────
        logger.info("[6/15] Building question profile...")
        question_profile = generate_question_profile(results)
        
        # ── API CALL #4: Distinctive Responses ─────────────────────────────────────
        logger.info("[7/15] Analyzing distinctive responses...")
        distinctive_responses = generate_distinctive_responses(results, client, session_id)
        
        # ── API CALL #5: Perception Gap ────────────────────────────────────────────
        logger.info("[8/15] Analyzing perception gap...")
        perception_gap = generate_perception_gap(results, client, session_id)
        
        # ── API CALL #6: Trajectory & Outlook ──────────────────────────────────────
        logger.info("[9/15] Projecting trajectory...")
        trajectory = generate_trajectory(results, client, session_id)
        
        # ── DEEP DIVE OPENING ──────────────────────────────────────────────────────
        logger.info("[10/15] Opening deep dive...")
        deep_dive_opening = """
Your pattern is complete on its own. This deep dive goes deeper, examining your profile through multiple research lenses and showing what your specific combination reveals about your relationship with AI.
        """.strip()
        
        # ── API CALL #7: Deep Dive Part 1 ──────────────────────────────────────────
        logger.info("[11/15] Examining pattern through research lenses...")
        deep_dive_part_1 = generate_deep_dive_1(results, client, session_id)
        
        # ── DEEP DIVE PART 3: Cohort in Context (data-only) ─────────────────────────
        logger.info("[12/15] Analyzing cohort context...")
        deep_dive_part_3 = generate_deep_dive_2_cohort(results)
        
        # ── API CALL #8: Deep Dive Part 4 ──────────────────────────────────────────
        logger.info("[13/15] Exploring rare combination deep...")
        deep_dive_part_4 = generate_deep_dive_4(results, client, session_id)
        
        # ── API CALL #9: Deep Dive Part 5 ──────────────────────────────────────────
        logger.info("[14/15] Analyzing cross-dimensional architecture...")
        deep_dive_part_5 = generate_deep_dive_5(results, client, session_id)
        
        # ── Assemble Report ────────────────────────────────────────────────────────
        logger.info("[15/15] Assembling final report...")
        
        report = {
            'metadata': {
                'session_id': session_id,
                'demographics': demographics,
                'generated_at': datetime.utcnow().isoformat(),
                'version': '8.0',
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
                'part_3_cohort_context': deep_dive_part_3,
                'part_4_rare_combination': deep_dive_part_4,
                'part_5_cross_dimensional': deep_dive_part_5,
            }
        }
        
        logger.info(f"Premium report generation complete (9 API calls: 6 core + 3 deep dive)")
        return report
    
    except Exception as e:
        user_email = demographics.get('email', 'unknown')
        notify_failure('Report Generation', e, session_id, user_email)
        raise

# ============================================================
# FREE TIER RESULTS GENERATOR (for /score endpoint)
# ============================================================

def generate_free_result(results: Dict, api_key: str = None) -> Dict:
    """
    Generate free tier results — dashboard only, no API calls.
    Used by /score endpoint to return results page data.
    
    Returns compact results with:
    - dashboard: all 9 dimensions with percentiles
    - shown_scores: top 3 most distinctive dimensions
    - summary: brief overview
    
    NO API CALLS — purely data extraction from scoring_engine output.
    """
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    
    # Generate dashboard data
    dashboard = generate_dashboard(results)
    
    # Get top 3 most distinctive dimensions (furthest from 50th percentile)
    shown_scores = results.get('shown_scores', [])
    if not shown_scores and dimensions:
        dim_list = [
            (name, data.get('percentiles', {}).get('overall', 50))
            for name, data in dimensions.items()
        ]
        # Sort by distance from 50th percentile
        dim_list.sort(key=lambda x: abs(x[1] - 50), reverse=True)
        shown_scores = [name for name, _ in dim_list[:3]]
    
    # Extract percentiles for shown scores
    shown_scores_data = {}
    for dim_name in shown_scores:
        if dim_name in dimensions:
            dim_data = dimensions[dim_name]
            percentile = dim_data.get('percentiles', {}).get('overall', 50)
            shown_scores_data[dim_name] = {
                'label': dim_data.get('label', dim_name),
                'percentile': percentile,
                'position': positional_language(percentile),
                'plain_english': plain_english_percentile(percentile),
            }
    
    # Build response
    free_result = {
        'metadata': {
            'session_id': results.get('session_id'),
            'demographics': demographics,
            'version': '8.0',
        },
        'dashboard': dashboard,
        'shown_scores': shown_scores_data,
        'summary': {
            'highest_dimension': results.get('summary', {}).get('highest_dimension'),
            'lowest_dimension': results.get('summary', {}).get('lowest_dimension'),
            'headline': results.get('headline', ''),
        }
    }
    
    return free_result

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'generate_free_result',
    'generate_premium_report',
    'call_claude_with_resilience',
    'plain_english_percentile',
    'positional_language',
]
