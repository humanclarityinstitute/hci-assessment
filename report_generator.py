"""
report_generator.py — HCI Premium Report Generator

Transforms assessment data (from Supabase) into complete report_dict
ready for rendering by page_builder.

Main entry point: generate_premium_report(results, api_key, session_id)

Input: {session_id, email, responses, demographics, full_results}
Output: {'success': True, 'report': {complete report_dict}}
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime

try:
    import anthropic
    from anthropic import APITimeoutError
except ImportError:
    raise ImportError("anthropic package required. pip install anthropic")

from question_metadata import QUESTION_MAP, get_question_text, get_dimension
from hci_signals_library import SIGNALS
from benchmark_builder import get_benchmark

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
    
    for attempt in range(2):  # Try once, then retry
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
            
            logger.info(f"[{call_name}] ✓ Success in {duration:.1f}s ({len(response_text)} chars)")
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
# HELPER: Build percentiles dict (KEY TRANSFORMATION)
# ============================================================

def build_percentiles_dict(responses: Dict, demographics: Dict, benchmark) -> Dict:
    """
    Build percentiles dict by querying benchmark for each question.
    
    This is the CRITICAL transformation that scoring_engine doesn't provide.
    
    Args:
        responses: All 39 + 3 responses from assessment
        demographics: User demographics
        benchmark: BenchmarkBuilder instance
    
    Returns:
        Dict mapping question_key → {percentile, distribution, dimension, question_text, response_value}
    """
    percentiles = {}
    
    logger.info("[PERCENTILES] Building percentiles dict for 39 questions...")
    
    for question_key, response_value in responses.items():
        # Skip perception and demographic questions (not in QUESTION_MAP)
        if question_key not in QUESTION_MAP:
            continue
        
        question_data = QUESTION_MAP[question_key]
        dimension = question_data.get('dimension')
        question_text = question_data.get('text', 'Question text not available')
        
        try:
            # Query benchmark for percentiles
            percentile_data = benchmark.get_percentile(
                question_key,
                response_value,
                segment=demographics.get('ai_tool_use_frequency') if demographics else None
            )
            
            if percentile_data:
                percentiles[question_key] = {
                    'question_text': question_text,
                    'response_value': response_value,
                    'percentile_overall': percentile_data.get('percentile_overall', 50),
                    'percentile_age_group': percentile_data.get('percentile_age_group'),
                    'percentile_frequency': percentile_data.get('percentile_frequency'),
                    'dimension': dimension,
                    'distribution': percentile_data.get('distribution', [])
                }
        except Exception as e:
            logger.warning(f"[PERCENTILES] Failed to get percentile for {question_key}: {e}")
            # Fallback: create minimal entry
            percentiles[question_key] = {
                'question_text': question_text,
                'response_value': response_value,
                'percentile_overall': 50,
                'dimension': dimension,
                'distribution': []
            }
    
    logger.info(f"[PERCENTILES] Built percentiles for {len(percentiles)} questions")
    return percentiles


# ============================================================
# OPENING SECTION
# ============================================================

def extract_most_distinctive_variable(percentiles: Dict) -> Optional[Dict]:
    """
    Find the single question with largest distance from 50th percentile.
    
    Returns:
        Dict with question details or None
    """
    if not percentiles:
        logger.warning("[Opening] No percentiles data")
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
        'question_text': q_data.get('question_text', 'Question text not available'),
        'response_value': q_data.get('response_value', 0),
        'percentile': percentile,
        'dimension': q_data.get('dimension', 'unknown'),
        'distance_from_center': abs(percentile - 50)
    }


def extract_largest_perception_gap(perception_gaps: list) -> Optional[Dict]:
    """
    Find the perception gap with largest magnitude.
    
    Returns:
        Dict with gap details or None
    """
    if not perception_gaps:
        logger.info("[Opening] No perception gaps")
        return None
    
    sorted_gaps = sorted(
        perception_gaps,
        key=lambda x: abs(x.get('gap_magnitude', 0)),
        reverse=True
    )
    
    if not sorted_gaps:
        return None
    
    largest = sorted_gaps[0]
    logger.info(f"[Opening] Largest gap: {largest.get('gap_magnitude')} points")
    
    return largest


def extract_rarest_combination(rare_combinations: list) -> Optional[Dict]:
    """
    Find the rarest (lowest rarity %) dimensional combination.
    
    Returns:
        Dict with combination details or None
    """
    if not rare_combinations:
        logger.info("[Opening] No rare combinations")
        return None
    
    rarest = rare_combinations[0]
    logger.info(f"[Opening] Rarest combo: {rarest.get('dimension_1')} + {rarest.get('dimension_2')}")
    
    return rarest


def generate_opening_findings(results: Dict, client, session_id: str) -> str:
    """
    Generate the 3 findings paragraphs via Claude.
    
    Input: results dict with percentiles, full_results, demographics
    Output: 3-paragraph string (findings separated by \n\n)
    """
    logger.info(f"[Opening] Extracting data...")
    
    percentiles = results.get('percentiles', {})
    full_results = results.get('full_results', {})
    perception_gaps = full_results.get('perception_gaps', [])
    rare_combinations = full_results.get('rare_combinations', [])
    demographics = results.get('demographics', {})
    
    most_distinctive = extract_most_distinctive_variable(percentiles)
    largest_gap = extract_largest_perception_gap(perception_gaps)
    rarest_combo = extract_rarest_combination(rare_combinations)
    age_group = demographics.get('age_group', 'Unknown')
    
    if not most_distinctive:
        logger.error("[Opening] No distinctive variable found")
        raise Exception("Cannot build opening section without distinctive variable")
    
    # Format the 3 data points for Claude
    logger.info("[Opening] Building prompt...")
    
    dp1_text = f"""FINDING 1 — MOST DISTINCTIVE VARIABLE:
Question: "{most_distinctive['question_text']}"
Their response: {most_distinctive['response_value']}/7
This puts them at the {most_distinctive['percentile']}th percentile"""
    
    dp2_text = ""
    if largest_gap and largest_gap.get('gap_magnitude', 0) != 0:
        dp2_text = f"""FINDING 2 — PERCEPTION GAP:
They perceive themselves as: "{largest_gap.get('perceived_answer', '')}"
Their actual data shows: {largest_gap.get('actual_percentile', 50)}th percentile
Gap magnitude: {abs(largest_gap.get('gap_magnitude', 0))} percentile points"""
    else:
        dp2_text = """FINDING 2 — PERCEPTION GAP:
No significant perception gap detected."""
    
    dp3_text = ""
    if rarest_combo:
        dp3_text = f"""FINDING 3 — RARE COMBINATION:
{rarest_combo.get('dimension_1', 'unknown').title()}: {rarest_combo.get('percentile_dim1', 50)}th percentile
{rarest_combo.get('dimension_2', 'unknown').title()}: {rarest_combo.get('percentile_dim2', 50)}th percentile
This combination appears in {rarest_combo.get('rarity_percent', 5)}% of people."""
    else:
        dp3_text = """FINDING 3 — RARE COMBINATION:
No rare combinations detected."""
    
    prompt = f"""This person's profile has three striking features:

{dp1_text}

{dp2_text}

{dp3_text}

Write exactly three paragraphs (50-75 words each) that synthesize these findings:
1. What's striking about their most distinctive variable
2. What the perception gap (or lack thereof) reveals
3. What the rare combination (or absence) tells us

Frame each as a genuine finding, not a question. Use plain language, no jargon.
Speak directly as "you". Tone: "Here's what stands out about you."
Ensure each paragraph flows naturally and makes intuitive sense."""
    
    logger.info("[Opening] Calling Claude API...")
    
    findings = call_claude_with_resilience(
        client=client,
        model=MODEL,
        max_tokens=1000,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Opening Findings',
        session_id=session_id
    )
    
    logger.info("[Opening] ✓ Findings generated")
    
    return findings


# ============================================================
# SECTION 1: BENCHMARK DASHBOARD (9 dimension cards)
# ============================================================

MIN_SAMPLE_SIZE = 30  # Don't show comparison if fewer responses

def build_dashboard_card(
    dimension_name: str,
    dimension_scores: Dict,
    demographics: Dict,
    benchmark_data: Dict = None
) -> Dict:
    """
    Build a single dimension card for the dashboard.
    
    Args:
        dimension_name: e.g. 'trust', 'reliance'
        dimension_scores: Full dimension_scores dict from full_results
        demographics: User demographics (for comparisons)
        benchmark_data: Pre-fetched benchmark data (optional)
    
    Returns:
        Dict with card content for rendering
    """
    
    dim_data = dimension_scores.get(dimension_name, {})
    
    if not dim_data:
        logger.warning(f"[Dashboard] No data for {dimension_name}")
        return None
    
    percentile_overall = dim_data.get('percentile_overall', 50)
    raw_score = dim_data.get('raw_score', 0)
    percentile_age_group = dim_data.get('percentile_age_group')
    percentile_frequency = dim_data.get('percentile_frequency')
    n_age_group = dim_data.get('n_age_group', 0)
    n_frequency = dim_data.get('n_frequency', 0)
    
    # Get definition and insight from SIGNALS
    definition = SIGNALS.get('dimensions', {}).get(dimension_name, {}).get('definition', '')
    
    # Select insight: high vs low vs series
    if percentile_overall >= 50:
        insight = SIGNALS.get('dimensions', {}).get(dimension_name, {}).get('high', '')
    else:
        insight = SIGNALS.get('dimensions', {}).get(dimension_name, {}).get('low', '')
    
    if not insight:
        insight = SIGNALS.get('dimensions', {}).get(dimension_name, {}).get('series', '')
    
    # Build comparisons only if sample size is adequate
    comparison_vs_daily_users = None
    if percentile_frequency is not None and n_frequency >= MIN_SAMPLE_SIZE:
        diff = percentile_frequency - percentile_overall
        comparison_vs_daily_users = f"+{diff}" if diff > 0 else str(diff)
    
    comparison_vs_age_group = None
    if percentile_age_group is not None and n_age_group >= MIN_SAMPLE_SIZE:
        diff = percentile_age_group - percentile_overall
        comparison_vs_age_group = f"+{diff}" if diff > 0 else str(diff)
    
    # Build plain English description
    plain_english = f"Higher than {percentile_overall} of 100"
    
    card = {
        'percentile': percentile_overall,
        'raw_score': round(raw_score, 2),
        'definition': definition,
        'percentile_by_frequency': percentile_frequency,
        'percentile_by_age_group': percentile_age_group,
        'comparison_vs_daily_users': comparison_vs_daily_users,
        'comparison_vs_age_group': comparison_vs_age_group,
        'plain_english_score': plain_english,
        'insight': insight,
        'sample_size_frequency': n_frequency,
        'sample_size_age_group': n_age_group
    }
    
    return card


def generate_dashboard_section(results: Dict) -> Dict:
    """
    Build complete Section 1: Dashboard with all 9 dimension cards.
    
    Args:
        results: Enriched results dict with dimension_scores
    
    Returns:
        Dict mapping dimension_name → card_dict
    """
    
    logger.info("[Dashboard] Building 9 dimension cards...")
    
    full_results = results.get('full_results', {})
    dimension_scores = full_results.get('dimension_scores', {})
    demographics = results.get('demographics', {})
    
    dashboard = {}
    
    # The 9 dimensions in order
    dimensions = [
        'reliance',
        'trust',
        'verification',
        'decision_delegation',
        'human_agency',
        'emotional_regulation',
        'disclosure',
        'thought_partnership',
        'social_transparency'
    ]
    
    for dimension_name in dimensions:
        card = build_dashboard_card(
            dimension_name,
            dimension_scores,
            demographics
        )
        if card:
            dashboard[dimension_name] = card
        else:
            logger.warning(f"[Dashboard] Failed to build card for {dimension_name}")
    
    logger.info(f"[Dashboard] ✓ Built {len(dashboard)}/9 cards")
    
    return dashboard


# ============================================================
# SECTION 3: HOW TYPICAL
# ============================================================

def generate_how_typical_section(results: Dict) -> Dict:
    """
    Build Section 3: How Typical - positioning for each dimension.
    
    Args:
        results: Enriched results
    
    Returns:
        Dict mapping dimension → {percentile, positioning, signal_text}
    """
    
    logger.info("[How Typical] Building typicality analysis...")
    
    full_results = results.get('full_results', {})
    dimension_scores = full_results.get('dimension_scores', {})
    
    how_typical = {}
    
    dimensions = [
        'reliance', 'trust', 'verification', 'decision_delegation',
        'human_agency', 'emotional_regulation', 'disclosure',
        'thought_partnership', 'social_transparency'
    ]
    
    for dimension_name in dimensions:
        dim_data = dimension_scores.get(dimension_name, {})
        percentile = dim_data.get('percentile_overall', 50)
        
        # Determine positioning
        if percentile >= 65:
            positioning = 'notably high'
        elif percentile >= 55:
            positioning = 'above the population centre'
        elif percentile >= 45:
            positioning = 'near the population centre'
        elif percentile >= 35:
            positioning = 'below the population centre'
        else:
            positioning = 'notably low'
        
        # Get signal text
        if percentile >= 50:
            signal_text = SIGNALS.get('dimensions', {}).get(dimension_name, {}).get('high', '')
        else:
            signal_text = SIGNALS.get('dimensions', {}).get(dimension_name, {}).get('low', '')
        
        if not signal_text:
            signal_text = SIGNALS.get('dimensions', {}).get(dimension_name, {}).get('series', '')
        
        how_typical[dimension_name] = {
            'percentile': percentile,
            'positioning': positioning,
            'signal_text': signal_text
        }
    
    logger.info("[How Typical] ✓ Complete")
    
    return how_typical


# ============================================================
# SECTION 6: QUESTION PROFILE (39 questions)
# ============================================================

def generate_question_profile_section(results: Dict) -> Dict:
    """
    Build Section 6: Question Profile with all 39 questions.
    
    Args:
        results: Enriched results with percentiles
    
    Returns:
        Dict mapping question_key → {question_text, dimension, response, percentile, distribution}
    """
    
    logger.info("[Question Profile] Building 39-question profile...")
    
    percentiles = results.get('percentiles', {})
    
    question_profile = {}
    
    for question_key, q_data in percentiles.items():
        question_profile[question_key] = {
            'question_text': q_data.get('question_text', ''),
            'dimension': q_data.get('dimension', ''),
            'response_value': q_data.get('response_value', 0),
            'percentile': q_data.get('percentile_overall', 50),
            'percentile_age_group': q_data.get('percentile_age_group'),
            'percentile_frequency': q_data.get('percentile_frequency'),
            'population_distribution': q_data.get('distribution', [])
        }
    
    logger.info(f"[Question Profile] ✓ Built {len(question_profile)} questions")
    
    return question_profile


# ============================================================
# SECTION 9: WHAT TO PROTECT
# ============================================================

def generate_what_to_protect_section(results: Dict) -> Dict:
    """
    Build Section 9: What to Protect - guidance for lowest-scoring dimensions.
    
    Args:
        results: Enriched results
    
    Returns:
        Dict with subsections for top 3 lowest dimensions
    """
    
    logger.info("[What to Protect] Building protective guidance...")
    
    full_results = results.get('full_results', {})
    dimension_scores = full_results.get('dimension_scores', {})
    
    # Find lowest 3 dimensions
    sorted_dims = sorted(
        dimension_scores.items(),
        key=lambda x: x[1].get('percentile_overall', 50)
    )
    
    lowest_3 = sorted_dims[:3]
    
    subsections = {}
    
    for dimension_name, dim_data in lowest_3:
        percentile = dim_data.get('percentile_overall', 50)
        
        # Get protective guidance from SIGNALS
        # Use dimension name to find protective signals
        definition = SIGNALS.get('dimensions', {}).get(dimension_name, {}).get('definition', '')
        
        # Build title: "Protect Your [Dimension]"
        title = f"Protect Your {dimension_name.replace('_', ' ').title()}"
        
        # Build content from pressure point signal
        pressure_point = SIGNALS.get('dimensions', {}).get(dimension_name, {}).get('pressure_point', '')
        if not pressure_point:
            pressure_point = f"You show lower engagement with {dimension_name}. This is worth protecting because..."
        
        subsections[dimension_name] = {
            'title': title,
            'definition': definition,
            'percentile': percentile,
            'content': pressure_point
        }
    
    logger.info("[What to Protect] ✓ Guidance complete")
    
    return {
        'subsections': subsections
    }


# ============================================================
# SECTION 4: RARE COMBINATIONS (API CALL #2)
# ============================================================

def generate_rare_combinations_section(results: Dict, client, session_id: str) -> str:
    """
    Generate prose about rare combinations via Claude API.
    
    Args:
        results: Enriched results with rare_combinations
        client: Anthropic client
        session_id: Session ID for logging
    
    Returns:
        str: Prose about rare combinations (or "No rare combinations detected")
    """
    
    full_results = results.get('full_results', {})
    rare_combinations = full_results.get('rare_combinations', [])
    
    if not rare_combinations:
        logger.info("[Rare Combos] No rare combinations detected")
        return "No rare dimensional combinations were detected in your profile."
    
    logger.info("[Rare Combos] Generating narrative...")
    
    # Format the combinations for Claude
    combo_text = ""
    for i, combo in enumerate(rare_combinations[:3], 1):  # Top 3
        dim1 = combo.get('dimension_1', 'unknown')
        dim2 = combo.get('dimension_2', 'unknown')
        p1 = combo.get('percentile_dim1', 50)
        p2 = combo.get('percentile_dim2', 50)
        rarity = combo.get('rarity_percent', 5)
        
        combo_text += f"\nCombination {i}: {dim1} ({p1}th %ile) + {dim2} ({p2}th %ile) — appears in {rarity}% of people"
    
    prompt = f"""This person's profile includes these unusual dimensional combinations:
{combo_text}

Write 2-3 paragraphs that:
1. Describe what's interesting about these combinations
2. Explain what they reveal about their relationship with AI
3. Connect them to the broader pattern

Be specific to their combinations. Use plain language, no jargon.
Speak directly as "you". Frame as genuine insight, not concern."""
    
    rare_combo_text = call_claude_with_resilience(
        client=client,
        model=MODEL,
        max_tokens=800,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Rare Combinations',
        session_id=session_id
    )
    
    logger.info("[Rare Combos] ✓ Generated")
    
    return rare_combo_text


# ============================================================
# SECTION 5: BEHAVIOUR STORY (API CALL #3)
# ============================================================

def generate_behaviour_story_section(results: Dict, client, session_id: str) -> str:
    """
    Generate the behaviour story via Claude API.
    
    Args:
        results: Enriched results
        client: Anthropic client
        session_id: Session ID for logging
    
    Returns:
        str: Prose narrative about behaviour pattern
    """
    
    logger.info("[Behaviour Story] Extracting distinctive dimensions...")
    
    full_results = results.get('full_results', {})
    dimension_scores = full_results.get('dimension_scores', {})
    patterns = full_results.get('patterns', {})
    
    # Get top 3-4 distinctive dimensions (highest and lowest)
    highest = patterns.get('highest', [])[:2]
    lowest = patterns.get('lowest', [])[:2]
    
    dims_text = "HIGHEST DIMENSIONS:\n"
    for h in highest:
        dim = h.get('dimension', 'unknown')
        perc = h.get('percentile', 50)
        dims_text += f"- {dim}: {perc}th percentile\n"
    
    dims_text += "\nLOWEST DIMENSIONS:\n"
    for l in lowest:
        dim = l.get('dimension', 'unknown')
        perc = l.get('percentile', 50)
        dims_text += f"- {dim}: {perc}th percentile\n"
    
    prompt = f"""This person's profile shows a clear behaviour pattern:

{dims_text}

Write 2-3 paragraphs that tell the story of how they work with AI:
1. What their highest dimensions suggest about their approach
2. What their lowest dimensions reveal about boundaries/caution
3. How these elements work together to form their pattern

Make it specific and personal. Use plain language. Speak directly as "you".
Frame as a coherent narrative, not a list."""
    
    story = call_claude_with_resilience(
        client=client,
        model=MODEL,
        max_tokens=800,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Behaviour Story',
        session_id=session_id
    )
    
    logger.info("[Behaviour Story] ✓ Generated")
    
    return story


# ============================================================
# SECTION 7: DISTINCTIVE (API CALL #4)
# ============================================================

def generate_distinctive_section(results: Dict, client, session_id: str) -> str:
    """
    Generate prose about most distinctive responses via Claude API.
    
    Args:
        results: Enriched results with percentiles
        client: Anthropic client
        session_id: Session ID for logging
    
    Returns:
        str: Prose about distinctive responses
    """
    
    logger.info("[Distinctive] Identifying outlier responses...")
    
    percentiles = results.get('percentiles', {})
    
    # Find top 3-5 most distinctive (furthest from 50)
    sorted_q = sorted(
        percentiles.items(),
        key=lambda x: abs(x[1].get('percentile_overall', 50) - 50),
        reverse=True
    )
    
    distinctive_qs = sorted_q[:5]
    
    qs_text = ""
    for q_key, q_data in distinctive_qs:
        text = q_data.get('question_text', 'Unknown question')
        response = q_data.get('response_value', 0)
        perc = q_data.get('percentile_overall', 50)
        
        if perc > 50:
            direction = "higher"
        else:
            direction = "lower"
        
        qs_text += f"\n- {text}\n  Your response: {response}/7 ({perc}th percentile — {direction} than most)"
    
    prompt = f"""This person gave notably distinctive responses to these questions:
{qs_text}

Write 2-3 paragraphs that:
1. Highlight what makes these responses stand out
2. Explain what they reveal about their relationship with AI
3. Connect to the broader pattern

Be specific. Use plain language, no jargon. Speak directly as "you".
Frame outliers as interesting, not unusual in a negative sense."""
    
    distinctive = call_claude_with_resilience(
        client=client,
        model=MODEL,
        max_tokens=800,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Distinctive Responses',
        session_id=session_id
    )
    
    logger.info("[Distinctive] ✓ Generated")
    
    return distinctive


# ============================================================
# SECTION 8: PERCEPTION GAP (API CALL #5)
# ============================================================

def generate_perception_gap_section(results: Dict, client, session_id: str) -> str:
    """
    Generate prose about perception gaps via Claude API.
    
    Args:
        results: Enriched results
        client: Anthropic client
        session_id: Session ID for logging
    
    Returns:
        str: Prose about perception gaps (or "No significant gaps")
    """
    
    full_results = results.get('full_results', {})
    perception_gaps = full_results.get('perception_gaps', [])
    
    if not perception_gaps:
        logger.info("[Perception Gap] No significant gaps detected")
        return "Your self-perception aligns closely with your actual responses. There are no significant gaps between how you think you relate to AI and how your actual responses show you do."
    
    logger.info("[Perception Gap] Generating narrative...")
    
    # Format gaps for Claude
    gaps_text = ""
    for gap in perception_gaps[:3]:  # Top 3 gaps
        question = gap.get('question', 'unknown')
        perceived = gap.get('perceived_answer', 'unknown')
        actual = gap.get('actual_percentile', 50)
        magnitude = abs(gap.get('gap_magnitude', 0))
        
        gaps_text += f"\n- {question}\n  You perceive: {perceived}\n  Actual: {actual}th percentile (gap: {magnitude} points)"
    
    prompt = f"""This person shows these perception gaps — differences between how they see themselves 
and what their actual responses show:
{gaps_text}

Write 2-3 paragraphs that:
1. Describe what these gaps reveal about self-awareness
2. Explain what might drive these specific misperceptions
3. Connect to their overall pattern

Frame as insight about awareness, not criticism. Use plain language.
Speak directly as "you". Keep it genuine and thoughtful."""
    
    gap_text = call_claude_with_resilience(
        client=client,
        model=MODEL,
        max_tokens=800,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Perception Gap',
        session_id=session_id
    )
    
    logger.info("[Perception Gap] ✓ Generated")
    
    return gap_text


# ============================================================
# SECTION 10: TRAJECTORY (API CALL #6)
# ============================================================

def generate_trajectory_section(results: Dict, client, session_id: str) -> str:
    """
    Generate prose about trajectory and evolution via Claude API.
    
    Args:
        results: Enriched results
        client: Anthropic client
        session_id: Session ID for logging
    
    Returns:
        str: Prose about potential trajectory
    """
    
    logger.info("[Trajectory] Analyzing patterns...")
    
    full_results = results.get('full_results', {})
    dimension_scores = full_results.get('dimension_scores', {})
    patterns = full_results.get('patterns', {})
    demographics = results.get('demographics', {})
    
    # Get usage frequency context
    frequency = demographics.get('ai_tool_use_frequency', 'unknown')
    
    # Get highest and lowest
    highest = patterns.get('highest', [])[:3]
    lowest = patterns.get('lowest', [])[:3]
    
    dims_text = "HIGHEST:\n"
    for h in highest:
        dims_text += f"- {h.get('dimension', 'unknown')}: {h.get('percentile', 50)}th percentile\n"
    
    dims_text += "\nLOWEST:\n"
    for l in lowest:
        dims_text += f"- {l.get('dimension', 'unknown')}: {l.get('percentile', 50)}th percentile\n"
    
    prompt = f"""This person's current profile shows:
{dims_text}

They report using AI: {frequency}

Write 2-3 paragraphs that explore:
1. How their pattern typically evolves as usage increases
2. What pressure points might cause drift in their profile
3. What stability they already show (where they're unlikely to shift)

Frame as possibilities, not predictions. Use plain language. Speak directly as "you".
Ground in research about how patterns shift with exposure/usage."""
    
    trajectory = call_claude_with_resilience(
        client=client,
        model=MODEL,
        max_tokens=800,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Trajectory',
        session_id=session_id
    )
    
    logger.info("[Trajectory] ✓ Generated")
    
    return trajectory


# ============================================================
# SECTION 9: WHAT TO PROTECT
# ============================================================

def generate_what_to_protect_section(results: Dict) -> Dict:
    """
    Build Section 9: What to Protect - guidance for lowest-scoring dimensions.
    
    Args:
        results: Enriched results
    
    Returns:
        Dict with subsections for top 3 lowest dimensions
    """
    
    logger.info("[What to Protect] Building protective guidance...")
    
    full_results = results.get('full_results', {})
    dimension_scores = full_results.get('dimension_scores', {})
    
    # Find lowest 3 dimensions
    sorted_dims = sorted(
        dimension_scores.items(),
        key=lambda x: x[1].get('percentile_overall', 50)
    )
    
    lowest_3 = sorted_dims[:3]
    
    subsections = {}
    
    for dimension_name, dim_data in lowest_3:
        percentile = dim_data.get('percentile_overall', 50)
        
        # Get protective guidance from SIGNALS
        # Use dimension name to find protective signals
        definition = SIGNALS.get('dimensions', {}).get(dimension_name, {}).get('definition', '')
        
        # Build title: "Protect Your [Dimension]"
        title = f"Protect Your {dimension_name.replace('_', ' ').title()}"
        
        # Build content from pressure point signal
        pressure_point = SIGNALS.get('dimensions', {}).get(dimension_name, {}).get('pressure_point', '')
        if not pressure_point:
            pressure_point = f"You show lower engagement with {dimension_name}. This is worth protecting because..."
        
        subsections[dimension_name] = {
            'title': title,
            'definition': definition,
            'percentile': percentile,
            'content': pressure_point
        }
    
    logger.info("[What to Protect] ✓ Guidance complete")
    
    return {
        'subsections': subsections
    }


# ============================================================
# SECTION 11: NEXT STEPS
# ============================================================

def generate_next_steps_section(results: Dict) -> Dict:
    """
    Build Section 11: Next Steps with personalized prompts.
    
    Args:
        results: Enriched results
    
    Returns:
        Dict with prompts and guidance
    """
    
    logger.info("[Next Steps] Building personalized prompts...")
    
    full_results = results.get('full_results', {})
    dimension_scores = full_results.get('dimension_scores', {})
    percentiles = results.get('percentiles', {})
    
    # Get highest and lowest dimensions
    sorted_dims = sorted(
        dimension_scores.items(),
        key=lambda x: x[1].get('percentile_overall', 50),
        reverse=True
    )
    
    highest_dim = sorted_dims[0][0] if sorted_dims else 'trust'
    lowest_dim = sorted_dims[-1][0] if sorted_dims else 'verification'
    
    # Build 3-5 personalized prompts based on pattern
    prompts = [
        {
            'title': f'Explore Your {highest_dim.title()}',
            'prompt': f'Tell me about how you use AI for {highest_dim.lower()} decisions. What makes this part of your AI use most important?'
        },
        {
            'title': f'Strengthen Your {lowest_dim.title()}',
            'prompt': f'If you wanted to be more intentional about {lowest_dim.lower()}, what would you want to change first?'
        },
        {
            'title': 'Share Your Experience',
            'prompt': 'What surprised you most about your AI profile? What would you want others to know about how you work with AI?'
        }
    ]
    
    logger.info("[Next Steps] ✓ Prompts complete")
    
    return {
        'intro': 'Here are some ways to go deeper with your profile:',
        'prompts': prompts,
        'closing': 'Your AI identity is not fixed. As your usage and needs evolve, so will your relationship with AI.'
    }

def generate_premium_report(
    results: Dict,
    api_key: str = None,
    session_id: str = None
) -> Dict:
    """
    Generate complete premium report.
    
    THIS IS WHAT api.py calls when user pays.
    
    Input:
        results: Dict from db.get_assessment(session_id) containing:
            - session_id, email, responses, demographics, full_results
        api_key: Anthropic API key
        session_id: Session ID
    
    Output:
        Dict with 'success' bool and 'report' dict
        
        report dict contains all sections ready for page_builder
    """
    
    try:
        logger.info(f"[REPORT] Generating premium report for {session_id}")
        
        # Initialize clients
        client = anthropic.Anthropic(api_key=api_key)
        benchmark = get_benchmark()
        
        # Extract input data
        responses = results.get('responses', {})
        demographics = results.get('demographics', {})
        full_results = results.get('full_results', {})
        email = results.get('email', '')
        
        # KEY TRANSFORMATION: Build percentiles dict
        logger.info("[REPORT] Building percentiles dict...")
        percentiles = build_percentiles_dict(responses, demographics, benchmark)
        
        # Restructure for report generation
        enriched_results = {
            'session_id': session_id,
            'email': email,
            'responses': responses,
            'demographics': demographics,
            'percentiles': percentiles,
            'full_results': full_results
        }
        
        # Build the report structure
        report = {
            'metadata': {
                'session_id': session_id,
                'email': email,
                'demographics': demographics,
                'generated_at': datetime.utcnow().isoformat(),
                'version': '3.0-complete-6-api-calls'
            }
        }
        
        # ── OPENING SECTION ────────────────────────────────────────
        logger.info("[REPORT] Building Opening section...")
        
        # Get pre-written opening statement from SIGNALS
        opening_statement = SIGNALS.get('opening', {}).get('prewritten_statement', '')
        if not opening_statement:
            logger.error("[REPORT] Pre-written opening statement not found in SIGNALS")
            return {
                'success': False,
                'error': 'Pre-written opening statement not configured'
            }
        
        # Generate the 3 findings
        findings = generate_opening_findings(enriched_results, client, session_id)
        
        # Add to report
        report['opening_statement'] = opening_statement
        report['top_3_findings'] = findings
        
        logger.info("[REPORT] ✓ Opening section complete")
        
        # ── SECTION 1: DASHBOARD ───────────────────────────────────
        logger.info("[REPORT] Building Section 1: Dashboard...")
        dashboard = generate_dashboard_section(enriched_results)
        report['section_1_dashboard'] = dashboard
        logger.info("[REPORT] ✓ Section 1 complete")
        
        # ── SECTION 3: HOW TYPICAL ─────────────────────────────────
        logger.info("[REPORT] Building Section 3: How Typical...")
        how_typical = generate_how_typical_section(enriched_results)
        report['section_3_how_typical'] = how_typical
        logger.info("[REPORT] ✓ Section 3 complete")
        
        # ── SECTION 6: QUESTION PROFILE ────────────────────────────
        logger.info("[REPORT] Building Section 6: Question Profile...")
        question_profile = generate_question_profile_section(enriched_results)
        report['section_6_question_profile'] = question_profile
        logger.info("[REPORT] ✓ Section 6 complete")
        
        # ── SECTION 9: WHAT TO PROTECT ────────────────────────────
        logger.info("[REPORT] Building Section 9: What to Protect...")
        what_to_protect = generate_what_to_protect_section(enriched_results)
        report['section_9_what_to_protect'] = what_to_protect
        logger.info("[REPORT] ✓ Section 9 complete")
        
        # ── SECTION 4: RARE COMBINATIONS (API #2) ──────────────────
        logger.info("[REPORT] Building Section 4: Rare Combinations (API #2)...")
        section_4 = generate_rare_combinations_section(enriched_results, client, session_id)
        report['section_4_rare_combos'] = section_4
        logger.info("[REPORT] ✓ Section 4 complete")
        
        # ── SECTION 5: BEHAVIOUR STORY (API #3) ────────────────────
        logger.info("[REPORT] Building Section 5: Behaviour Story (API #3)...")
        section_5 = generate_behaviour_story_section(enriched_results, client, session_id)
        report['section_5_behaviour_story'] = section_5
        logger.info("[REPORT] ✓ Section 5 complete")
        
        # ── SECTION 7: DISTINCTIVE (API #4) ────────────────────────
        logger.info("[REPORT] Building Section 7: Distinctive (API #4)...")
        section_7 = generate_distinctive_section(enriched_results, client, session_id)
        report['section_7_distinctive'] = section_7
        logger.info("[REPORT] ✓ Section 7 complete")
        
        # ── SECTION 8: PERCEPTION GAP (API #5) ─────────────────────
        logger.info("[REPORT] Building Section 8: Perception Gap (API #5)...")
        section_8 = generate_perception_gap_section(enriched_results, client, session_id)
        report['section_8_perception_gap'] = section_8
        logger.info("[REPORT] ✓ Section 8 complete")
        
        # ── SECTION 10: TRAJECTORY (API #6) ────────────────────────
        logger.info("[REPORT] Building Section 10: Trajectory (API #6)...")
        section_10 = generate_trajectory_section(enriched_results, client, session_id)
        report['section_10_trajectory'] = section_10
        logger.info("[REPORT] ✓ Section 10 complete")
        
        # ── SECTION 11: NEXT STEPS ─────────────────────────────────
        logger.info("[REPORT] Building Section 11: Next Steps...")
        section_11 = generate_next_steps_section(enriched_results)
        report['section_11_next_steps'] = section_11
        logger.info("[REPORT] ✓ Section 11 complete")
        
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
# FOR TESTING
# ============================================================

if __name__ == '__main__':
    print("report_generator.py loaded successfully")
    print("Entry point: generate_premium_report(results, api_key, session_id)")
    print("\n6 API CALLS + 5 DATA-ONLY SECTIONS:")
    print("  ✓ Opening: Pre-written + 3 findings (API #1)")
    print("  ✓ Section 1: Dashboard (9 dimension cards)")
    print("  ✓ Section 3: How Typical (typicality positioning)")
    print("  ✓ Section 4: Rare Combinations (API #2)")
    print("  ✓ Section 5: Behaviour Story (API #3)")
    print("  ✓ Section 6: Question Profile (39 questions)")
    print("  ✓ Section 7: Distinctive (API #4)")
    print("  ✓ Section 8: Perception Gap (API #5)")
    print("  ✓ Section 9: What to Protect (lowest 3 dims)")
    print("  ✓ Section 10: Trajectory (API #6)")
    print("  ✓ Section 11: Next Steps (personalized prompts)")
    print("\nTotal: 6 API calls, 11 sections, ~35-39 pages")
    print("Ready for integration with api.py")
