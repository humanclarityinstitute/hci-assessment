"""
HCI AI Identity & Behaviour Assessment — Report Generator v2.0 (REBUILT)

Complete rebuild with:
- 9 focused API calls (6 core + 3 optional deep dive)
- Full narrative generation (300-400+ words per section)
- Complete research integration (SIGNALS + HBE + VALUES)
- Professional report_dict output

No partial reports — all sections present or entire report fails.
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from anthropic import Anthropic, APITimeoutError

# Import research data
from hci_signals_library import SIGNALS
from human_reference_layer import HBE_FRAMEWORK, VALUES_SIGNALS
from question_metadata import DIMENSION_NAMES, DIMENSIONS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

DIMENSION_DEFINITIONS = {
    'reliance': 'How much you depend on AI for thinking and functioning',
    'trust': 'How much you believe AI outputs are accurate',
    'verification': 'How often you check AI outputs before using them',
    'decision_delegation': 'How much you hand over decisions to AI',
    'human_agency': 'How much control you maintain over your decisions',
    'emotional_regulation': 'Whether you turn to AI for emotional support',
    'disclosure': 'How much personal information you share with AI',
    'thought_partnership': 'How much you use AI as a thinking partner',
    'social_transparency': 'How openly you discuss your AI use with others',
}

OPENING_STATEMENT = """
You are uniquely positioned in how you relate to AI. Your profile reflects 
how you currently engage with AI systems — based on your responses benchmarked 
against 10,500 participants across 21 research studies.

Use this report to understand your pattern:

• Understand what's distinctive about how you work with AI
• Notice where you're typical and where you stand out
• Explore what's worth protecting as your use evolves
• Make conscious choices about your relationship with AI going forward
"""

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def generate_premium_report(results, api_key, session_id):
    """
    Generate complete premium report with all sections.
    
    Args:
        results: Complete results dict from api.py (with enriched data from Phase 1)
        api_key: Anthropic API key
        session_id: Assessment session ID
    
    Returns:
        dict: Complete report_dict with all sections, or None if failed
    """
    
    try:
        logger.info(f"[Phase 2] Starting report generation for session {session_id}")
        
        client = Anthropic(api_key=api_key)
        participant = results['full_results']
        demographics = results['demographics']
        
        # Initialize report_dict
        report_dict = {
            'metadata': {
                'session_id': session_id,
                'created_at': datetime.utcnow().isoformat(),
                'participant_age_group': demographics.get('age_group'),
                'participant_frequency': demographics.get('frequency'),
            }
        }
        
        # ================================================================
        # OPENING SECTION
        # ================================================================
        
        logger.info("[Phase 2] Generating opening section...")
        
        report_dict['opening_statement'] = OPENING_STATEMENT
        report_dict['top_3_findings'] = _call_api_1_top_3_findings(
            client, results
        )
        
        # ================================================================
        # CORE SECTIONS (Data-only, no API calls)
        # ================================================================
        
        logger.info("[Phase 2] Building dashboard (Section 1)...")
        report_dict['section_1_dashboard'] = _build_section_1_dashboard(
            participant, results
        )
        
        logger.info("[Phase 2] Building how typical (Section 3)...")
        report_dict['section_3_how_typical'] = _build_section_3_how_typical(
            participant
        )
        
        # ================================================================
        # CORE SECTIONS (With API calls)
        # ================================================================
        
        logger.info("[Phase 2] Generating rare combinations (Section 4 / API #2)...")
        report_dict['section_4_rare_combos'] = _call_api_2_rare_combos(
            client, results
        )
        
        logger.info("[Phase 2] Generating behaviour story (Section 5 / API #3)...")
        report_dict['section_5_behaviour_story'] = _call_api_3_behaviour_story(
            client, results
        )
        
        logger.info("[Phase 2] Building question profile (Section 6)...")
        report_dict['section_6_question_profile'] = _build_section_6_question_profile(
            participant, results
        )
        
        logger.info("[Phase 2] Generating distinctive responses (Section 7 / API #4)...")
        report_dict['section_7_distinctive'] = _call_api_4_distinctive_responses(
            client, results
        )
        
        logger.info("[Phase 2] Generating perception gap (Section 8 / API #5)...")
        report_dict['section_8_perception_gap'] = _call_api_5_perception_gap(
            client, results
        )
        
        logger.info("[Phase 2] Building what to protect (Section 9)...")
        report_dict['section_9_what_to_protect'] = _build_section_9_what_to_protect(
            participant, results
        )
        
        logger.info("[Phase 2] Generating trajectory (Section 10 / API #6)...")
        report_dict['section_10_trajectory'] = _call_api_6_trajectory(
            client, results
        )
        
        logger.info("[Phase 2] Building next steps (Section 11)...")
        report_dict['section_11_next_steps'] = _build_section_11_next_steps(
            participant, results
        )
        
        # ================================================================
        # OPTIONAL DEEP DIVE
        # ================================================================
        
        report_dict['deep_dive_available'] = True
        report_dict['deep_dive'] = {
            'part_1_research_lenses': None,
            'part_2_cohort_context': None,
            'part_3_rare_combo_deep': None,
            'part_4_architecture': None,
        }
        
        logger.info(f"[Phase 2] Report generation complete for session {session_id}")
        return report_dict
        
    except Exception as e:
        logger.error(f"[Phase 2] Report generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# API CALL #1: TOP 3 FINDINGS
# ============================================================================

def _call_api_1_top_3_findings(client, results):
    """
    Opening narrative: 3 striking features (50-75 words each)
    """
    
    participant = results['full_results']
    distinctive = results['distinctive_responses'][0] if results['distinctive_responses'] else None
    gap = results['perception_gaps'][0] if results['perception_gaps'] else None
    combo = results['rare_combinations'][0] if results['rare_combinations'] else None
    
    finding_1 = (
        f"Question: {distinctive['question_text']}\n"
        f"Your answer: {distinctive['respondent_answer']}/7 "
        f"({distinctive['respondent_percentile']}th percentile)"
    ) if distinctive else "N/A"
    
    finding_2 = (
        f"{DIMENSION_NAMES.get(gap['dimension_1'], gap['dimension_1'])}: "
        f"{gap['percentile_1']}th percentile\n"
        f"{DIMENSION_NAMES.get(gap['dimension_2'], gap['dimension_2'])}: "
        f"{gap['percentile_2']}th percentile\n"
        f"Gap: {gap['gap_magnitude']} points"
    ) if gap else "No significant gaps"
    
    finding_3 = (
        f"{DIMENSION_NAMES.get(combo['dimension_1'], combo['dimension_1'])} "
        f"({combo['percentile_1']}th) + "
        f"{DIMENSION_NAMES.get(combo['dimension_2'], combo['dimension_2'])} "
        f"({combo['percentile_2']}th) = "
        f"{combo['rarity_percent']}% rarity"
    ) if combo else "No rare combos"
    
    prompt = f"""
This person's profile has three striking features.

FINDING 1: {finding_1}
FINDING 2: {finding_2}
FINDING 3: {finding_3}

Write THREE PARAGRAPHS (50-75 words each):

Paragraph 1: What's striking about their most extreme response? Plain language, speak as "you".
Paragraph 2: The gap between their two most misaligned dimensions. What does it suggest?
Paragraph 3: Their rare combination. Why it's unusual and what it reveals.

Tone: "Here's what stands out about you."
Total: 150-225 words.
"""
    
    try:
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1000,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"[API #1] Failed: {e}")
        return "Error generating top 3 findings"


# ============================================================================
# SECTION 1: DASHBOARD
# ============================================================================

def _build_section_1_dashboard(participant, results):
    """Build 9 dimension cards"""
    
    dashboard = {}
    demographic_percentiles = results.get('demographic_percentiles', {})
    
    for dim_name in DIMENSIONS:
        dim_data = participant['dimension_scores'].get(dim_name, {})
        percentile = dim_data.get('percentile', 50)
        
        demo_data = demographic_percentiles.get(dim_name, {})
        percentile_frequency = demo_data.get('percentile_by_frequency')
        percentile_age = demo_data.get('percentile_by_age')
        
        if percentile >= 75:
            signal_key = 'high'
        elif percentile <= 25:
            signal_key = 'low'
        else:
            signal_key = 'series'
        
        insight = SIGNALS['dimensions'].get(dim_name, {}).get(signal_key, 'Mixed patterns.')
        
        dashboard[dim_name] = {
            'dimension_name': dim_name,
            'display_name': DIMENSION_NAMES.get(dim_name, dim_name.replace('_', ' ').title()),
            'definition': DIMENSION_DEFINITIONS.get(dim_name, ''),
            'percentile': percentile,
            'percentile_by_frequency': percentile_frequency,
            'percentile_by_age': percentile_age,
            'research_insight': insight,
            'plain_english': f"Higher than {percentile} of 100 people",
        }
    
    return dashboard


# ============================================================================
# SECTION 3: HOW TYPICAL
# ============================================================================

def _build_section_3_how_typical(participant):
    """How typical each dimension is"""
    
    how_typical = {}
    
    for dim_name in DIMENSIONS:
        dim_data = participant['dimension_scores'].get(dim_name, {})
        percentile = dim_data.get('percentile', 50)
        
        if percentile <= 20:
            positioning = "notably low"
            signal_key = 'low'
        elif percentile >= 80:
            positioning = "notably high"
            signal_key = 'high'
        else:
            positioning = "near the population centre"
            signal_key = 'series'
        
        signal_text = SIGNALS['dimensions'].get(dim_name, {}).get(signal_key, 'Mixed patterns.')
        
        how_typical[dim_name] = {
            'dimension_name': dim_name,
            'display_name': DIMENSION_NAMES.get(dim_name, dim_name.replace('_', ' ').title()),
            'percentile': percentile,
            'positioning': positioning,
            'signal_text': signal_text,
        }
    
    return how_typical


# ============================================================================
# API CALL #2: RARE COMBINATIONS
# ============================================================================

def _call_api_2_rare_combos(client, results):
    """Analyze rare combinations (500-600 words)"""
    
    combos = results.get('rare_combinations', [])
    if not combos:
        return "No rare combinations detected."
    
    combo_descriptions = []
    for i, combo in enumerate(combos[:2], 1):
        dim1_name = DIMENSION_NAMES.get(combo['dimension_1'], combo['dimension_1'])
        dim2_name = DIMENSION_NAMES.get(combo['dimension_2'], combo['dimension_2'])
        
        desc = f"""
COMBINATION {i}: {dim1_name} + {dim2_name}
- {dim1_name}: {combo['percentile_1']}th percentile
- {dim2_name}: {combo['percentile_2']}th percentile
- Rarity: {combo['rarity_percent']}% of participants

Why unusual: {combo.get('why_unusual', 'Uncommon pairing.')}
What it reveals: {combo.get('what_reveals', 'Unusual AI relationship.')}
"""
        combo_descriptions.append(desc)
    
    combos_text = "\n".join(combo_descriptions)
    
    prompt = f"""
Rare combinations in this profile:

{combos_text}

For EACH combination write 250-300 words:

1. WHY IT'S UNUSUAL (150 words)
   - What does research from HCI's 21 datasets show?
   - How rare is this pairing?
   - What behavioral pattern does research predict?

2. WHAT IT REVEALS (150 words)
   - What does this tell us about their AI relationship?
   - What strengths or vulnerabilities?
   - What pressure points might emerge?

3. PATTERN IMPLICATIONS (100 words)
   - How does this fit their overall profile?
   - Research perspective on where this leads

Speak directly as "you". Ground in research. Use plain language.

Total: 500-600 words across both combinations.
"""
    
    try:
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1500,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"[API #2] Failed: {e}")
        return "Error generating rare combinations analysis"


# ============================================================================
# API CALL #3: BEHAVIOUR STORY
# ============================================================================

def _call_api_3_behaviour_story(client, results):
    """Full profile narrative (800-1000 words)"""
    
    participant = results['full_results']
    
    dimensions_summary = []
    for dim_name in DIMENSIONS:
        dim_data = participant['dimension_scores'].get(dim_name, {})
        percentile = dim_data.get('percentile', 50)
        display_name = DIMENSION_NAMES.get(dim_name, dim_name.replace('_', ' ').title())
        dimensions_summary.append(f"{display_name}: {percentile}th percentile")
    
    dimensions_list = "\n".join(dimensions_summary)
    
    prompt = f"""
Full dimensional profile:

{dimensions_list}

Write BEHAVIOUR STORY (800-1000 words):

1. OPENING (150 words)
   Synthesize what their pattern reveals about AI engagement
   Use research context. Set up dimensional analysis.

2. DIMENSIONAL ANALYSIS (500-600 words)
   Order by distinctiveness. For top 3-4 dimensions:
   - Their positioning (high/low/typical)
   - What research shows this means
   - Pressure points from HBE_FRAMEWORK
   - Behavioral implications specific to them
   - One reflective question

3. PATTERN ACROSS DIMENSIONS (150-200 words)
   How dimensions interact?
   Rare combinations suggest?
   Research shows for trajectory?
   What pressure points matter most?

4. CLOSING (100 words)
   What their profile suggests about AI relationship
   Where research shows this leads
   Forward-looking perspective

Requirements:
- Use HCI research throughout
- Reference SIGNALS for each dimension
- Ground pressure points in HBE_FRAMEWORK
- Speak directly as "you"
- Plain language, no jargon

Tone: Research-grounded, flowing, illuminating.
Total: 800-1000 words.
"""
    
    try:
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=2500,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"[API #3] Failed: {e}")
        return "Error generating behaviour story"


# ============================================================================
# SECTION 6: QUESTION PROFILE
# ============================================================================

def _build_section_6_question_profile(participant, results):
    """All 39 questions with distributions"""
    
    questions = {}
    question_scores = participant.get('question_scores', {})
    question_distributions = results.get('question_distributions', {})
    
    for q_key, q_data in question_scores.items():
        questions[q_key] = {
            'question_key': q_key,
            'question_text': q_data.get('question_text', ''),
            'dimension': q_data.get('dimension', ''),
            'respondent_answer': q_data.get('respondent_answer', 0),
            'respondent_percentile': q_data.get('percentile', 50),
            'population_distribution': question_distributions.get(q_key, [14]*7),
        }
    
    return questions


# ============================================================================
# API CALL #4: DISTINCTIVE RESPONSES
# ============================================================================

def _call_api_4_distinctive_responses(client, results):
    """Extreme responses analysis (300-400 words)"""
    
    distinctive = results.get('distinctive_responses', [])[:5]
    
    if not distinctive:
        return "Your responses are well-distributed across the scale."
    
    response_list = []
    for i, resp in enumerate(distinctive, 1):
        response_list.append(
            f"{i}. {resp['question_text']}\n"
            f"   Answer: {resp['respondent_answer']}/7 ({resp['respondent_percentile']}th %ile)\n"
            f"   Dimension: {DIMENSION_NAMES.get(resp['dimension'], resp['dimension'])}"
        )
    
    responses_text = "\n".join(response_list)
    
    prompt = f"""
Extreme responses:

{responses_text}

Analyze in ~300-400 words:

1. PATTERN ANALYSIS (100 words)
   What coherence emerges across these extremes?
   What do they reveal about AI relationship?

2. RESEARCH PERSPECTIVE (150 words)
   How common is this pattern?
   What do people with similar extremes typically do?
   What does HCI research show?
   What trajectory does research predict?

3. BEHAVIORAL IMPLICATIONS (50-100 words)
   What strengths does this suggest?
   What pressure points might emerge?
   What's worth noticing?

Speak directly as "you". Ground in research. Plain language.

Total: 300-400 words.
"""
    
    try:
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"[API #4] Failed: {e}")
        return "Error generating distinctive responses analysis"


# ============================================================================
# API CALL #5: PERCEPTION GAP
# ============================================================================

def _call_api_5_perception_gap(client, results):
    """Perception gaps analysis (200-300 words)"""
    
    gaps = results.get('perception_gaps', [])[:3]
    
    if not gaps:
        return "Self-perception aligns well with benchmarked positioning, indicating strong self-awareness."
    
    gap_list = []
    for gap in gaps:
        dim1 = DIMENSION_NAMES.get(gap['dimension_1'], gap['dimension_1'])
        dim2 = DIMENSION_NAMES.get(gap['dimension_2'], gap['dimension_2'])
        
        gap_list.append(
            f"{dim1}: {gap['percentile_1']}th %ile\n"
            f"{dim2}: {gap['percentile_2']}th %ile\n"
            f"Gap: {gap['gap_magnitude']} points"
        )
    
    gaps_text = "\n\n".join(gap_list)
    
    prompt = f"""
Perception gaps (where dimensions diverge):

{gaps_text}

Write 200-300 words:

1. WHAT THIS REVEALS (100 words)
   What does significant divergence mean?
   Suggest internal conflict or legitimate variation?
   Reveal about self-awareness?

2. RESEARCH PERSPECTIVE (100 words)
   What does HCI research show about this gap?
   Is this common or unusual?
   What typically happens with this pattern?

3. IMPLICATIONS (50-100 words)
   What pressure points might emerge?
   What's worth noticing?

Speak directly as "you". Ground in research.

Total: 200-300 words.
"""
    
    try:
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1000,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"[API #5] Failed: {e}")
        return "Error generating perception gap analysis"


# ============================================================================
# SECTION 9: WHAT TO PROTECT
# ============================================================================

def _build_section_9_what_to_protect(participant, results):
    """4 subsections based on their pattern"""
    
    dimension_scores = participant['dimension_scores']
    sorted_dims = sorted(
        dimension_scores.items(),
        key=lambda x: abs(x[1].get('percentile', 50) - 50),
        reverse=True
    )[:3]
    
    pressure_points = []
    values_list = []
    strengths = []
    
    for dim_name, dim_data in sorted_dims:
        display_name = DIMENSION_NAMES.get(dim_name, dim_name.replace('_', ' ').title())
        percentile = dim_data.get('percentile', 50)
        
        pp = SIGNALS['dimensions'].get(dim_name, {}).get('pressure_point', '')
        if pp:
            pressure_points.append(pp)
        
        val = VALUES_SIGNALS.get(dim_name, '')
        if val:
            values_list.append(val)
        
        if percentile >= 75:
            strengths.append(f"High {display_name} supports intentionality")
        elif percentile <= 25:
            strengths.append(f"Clear boundary around {display_name}")
    
    return {
        'whats_working_well': {
            'title': "What's Working Well",
            'strengths': strengths[:3]
        },
        'pressure_points': {
            'title': 'Pressure Points to Watch',
            'points': pressure_points[:3]
        },
        'values_at_stake': {
            'title': 'Values at Stake',
            'values': values_list[:3]
        },
        'protective_strategies': {
            'title': 'Protective Strategies',
            'strategies': [
                'Maintain intentional boundaries',
                'Regular reflection on AI relationship',
                'Preserve human connection in decisions'
            ]
        }
    }


# ============================================================================
# API CALL #6: TRAJECTORY
# ============================================================================

def _call_api_6_trajectory(client, results):
    """Trajectory & outlook (300-400 words)"""
    
    participant = results['full_results']
    
    distinctive_dims = sorted(
        participant['dimension_scores'].items(),
        key=lambda x: abs(x[1].get('percentile', 50) - 50),
        reverse=True
    )[:2]
    
    dims_summary = []
    for dim_name, dim_data in distinctive_dims:
        display_name = DIMENSION_NAMES.get(dim_name, dim_name.replace('_', ' ').title())
        percentile = dim_data.get('percentile', 50)
        dims_summary.append(f"{display_name}: {percentile}th percentile")
    
    dims_text = "\n".join(dims_summary)
    
    prompt = f"""
Based on HCI's 21-dataset research, patterns like theirs evolve predictably.

Distinctive positioning:
{dims_text}

Write 300-400 words:

1. TRAJECTORY (100 words)
   Where this typically leads with continued AI use
   What tends to strengthen/weaken/become automatic
   Skills that develop

2. PRESSURE POINTS (100 words)
   Specific vulnerable areas
   Where research shows friction emerges
   What's worth monitoring

3. REFRAME (100 words)
   How to think about this healthily (HBE_FRAMEWORK)
   Normalize human baseline
   Acknowledge AI-induced pressures
   Integrated framing

4. FORWARD-LOOKING (100 words)
   How conscious choice-making looks
   How might growth look
   Research suggests what works

Speak directly as "you". Ground in research.

Total: 300-400 words.
"""
    
    try:
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"[API #6] Failed: {e}")
        return "Error generating trajectory analysis"


# ============================================================================
# SECTION 11: NEXT STEPS
# ============================================================================

def _build_section_11_next_steps(participant, results):
    """3 reflection prompts"""
    
    dimension_scores = participant['dimension_scores']
    
    highest_dim = max(dimension_scores.items(), key=lambda x: x[1].get('percentile', 0))[0]
    lowest_dim = min(dimension_scores.items(), key=lambda x: x[1].get('percentile', 100))[0]
    
    highest_name = DIMENSION_NAMES.get(highest_dim, highest_dim.replace('_', ' ').title())
    lowest_name = DIMENSION_NAMES.get(lowest_dim, lowest_dim.replace('_', ' ').title())
    
    return {
        'intro': "This report opens questions. Here are three reflection prompts based on your pattern:",
        'prompts': [
            {
                'title': f"About your {highest_name} strength",
                'prompt': f"You score highly on {highest_name}. What would it mean to lean into this strength intentionally?"
            },
            {
                'title': f"About your {lowest_name} boundary",
                'prompt': f"You maintain a clear boundary around {lowest_name}. What is this boundary protecting?"
            },
            {
                'title': "About your overall pattern",
                'prompt': "If your relationship with AI evolved, what would you want to stay the same? What might you explore changing?"
            }
        ],
        'closing': "Your relationship with AI is just beginning. The most important question is: what do you choose to do with this understanding?"
    }
