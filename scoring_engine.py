"""
HCI AI Identity & Behaviour Assessment
Scoring Engine — Version 2

Changes from v1:
- Added variable-level percentile calculation
- Added find_most_distinctive_variable() function
- Added FIXED_HIGHLIGHT_VARIABLES for disclosure and social transparency
- Returns variable_highlights in results object
"""

import json
import numpy as np
from scipy import stats


# ============================================================
# DIMENSION CONFIGURATION
# ============================================================

DIMENSIONS = {
    'trust': {
        'label': 'Trust',
        'subtitle': 'Do I trust AI?',
        'questions': ['trust_q1', 'trust_q2', 'trust_q3', 'trust_q4'],
        'variables': [
            'trust_ai_for_accuracy',
            'confident_relying_on_ai_outputs',
            'worry_ai_presents_false_info',
            'ai_decision_reliance_when_difficult',
        ],
        'reverse': ['trust_q3'],
    },
    'disclosure': {
        'label': 'Disclosure',
        'subtitle': 'What do I tell AI?',
        'questions': ['disc_q1', 'disc_q2', 'disc_q3', 'disc_q4'],
        'variables': [
            'ai_personal_sharing_comfort',
            'ai_emotional_safety_vs_humans',
            'disclosure_untold_things',
            'disclosure_comparative_openness',
        ],
        'reverse': [],
    },
    'reliance': {
        'label': 'Reliance',
        'subtitle': 'How dependent am I becoming?',
        'questions': ['rel_q1', 'rel_q2', 'rel_q3', 'rel_q4', 'rel_q5'],
        'variables': [
            'restless_without_ai',
            'system_reliance_struggle_without',
            'ai_reliance_decisions',
            'delegation_rely_even_if_possible',
            'delegation_skill_decline',
        ],
        'reverse': [],
    },
    'decision_delegation': {
        'label': 'Decision Delegation',
        'subtitle': 'How much judgement do I outsource?',
        'questions': ['del_q1', 'del_q2', 'del_q3', 'del_q4', 'del_q5'],
        'variables': [
            'delegation_regular_handover',
            'accept_ai_output_without_change',
            'override_follow_despite_discomfort',
            'comfort_high_stakes_delegation',
            'delegation_when_uncertain',
        ],
        'reverse': [],
    },
    'verification': {
        'label': 'Verification',
        'subtitle': 'Do I check what AI tells me?',
        'questions': ['ver_q1', 'ver_q2', 'ver_q3', 'ver_q4'],
        'variables': [
            'double_check_ai_info',
            'verify_skip_due_to_effort',
            'proceed_without_checking',
            'verify_use_external_sources',
        ],
        'reverse': ['ver_q2', 'ver_q3'],
    },
    'human_agency': {
        'label': 'Human Agency',
        'subtitle': 'Am I still directing my own thinking?',
        'questions': ['agency_q1', 'agency_q2', 'agency_q3', 'agency_q4', 'agency_q5'],
        'variables': [
            'self_directed_action_feeling',
            'agency_control_feel_in_control',
            'agency_trust_own_judgement',
            'nudging_influenced_unaware',
            'ai_identity_mine_vs_ai',
        ],
        'reverse': ['agency_q3', 'agency_q4', 'agency_q5'],
    },
    'emotional_regulation': {
        'label': 'Emotional Regulation',
        'subtitle': 'Does AI play a role in my emotional life?',
        'questions': ['emot_q1', 'emot_q2', 'emot_q3', 'emot_q4'],
        'variables': [
            'ai_emotion_relief_support',
            'ai_emotional_support_extent',
            'ai_boundaries_change_over_time',
            'emotional_regulation_coping',
        ],
        'reverse': [],
    },
    'thought_partnership': {
        'label': 'Thought Partnership',
        'subtitle': 'Do I use AI as an external thinking partner?',
        'questions': ['thought_q1', 'thought_q2', 'thought_q3', 'thought_q4'],
        'variables': [
            'thought_partnership_sounding_board',
            'thought_partnership_belief_challenge',
            'ai_thinking_depth_engagement',
            'ai_validation_reinforce_beliefs',
        ],
        'reverse': ['thought_q4'],
    },
    'social_transparency': {
        'label': 'Social Transparency',
        'subtitle': 'Do I tell other people about my AI use?',
        'questions': ['soc_q1', 'soc_q2', 'soc_q3', 'soc_q4'],
        'variables': [
            'social_transparency_professional',
            'social_transparency_concealment',
            'social_transparency_comfort',
            'social_transparency_gap',
        ],
        'reverse': ['soc_q2', 'soc_q4'],
    },
}

SCALE_MAX = 7
SCALE_MIN = 1

# ============================================================
# FIXED HIGHLIGHT VARIABLES
# These always appear in the free report regardless of
# individual scores — chosen for universal human interest
# ============================================================

FIXED_HIGHLIGHTS = [
    {
        'question_key': 'disc_q3',
        'variable': 'disclosure_untold_things',
        'dimension': 'disclosure',
        'question_text': 'There are things I have told AI that I have never told another person',
        'why_interesting': 'disclosure',
    },
    {
        'question_key': 'soc_q4',
        'variable': 'social_transparency_gap',
        'dimension': 'social_transparency',
        'question_text': 'There is a gap between how much I actually use AI and what I let others believe',
        'why_interesting': 'social_transparency',
        'reverse': True,
    },
]


# ============================================================
# CORE SCORING FUNCTIONS
# ============================================================

def reverse_score(score, scale_max=SCALE_MAX):
    return (scale_max + 1) - score


def normalise_to_100(raw_score, n_questions):
    min_possible = n_questions * SCALE_MIN
    max_possible = n_questions * SCALE_MAX
    return round((raw_score - min_possible) / (max_possible - min_possible) * 100, 1)


def get_percentile(score_0_100, distribution_raw):
    dist_normalised = [
        (s - SCALE_MIN) / (SCALE_MAX - SCALE_MIN) * 100
        for s in distribution_raw
    ]
    return round(float(stats.percentileofscore(dist_normalised, score_0_100, kind='rank')), 0)


def get_variable_percentile_from_raw(raw_response, variable_name, benchmarks, demographics):
    """
    Get overall and age group percentile for a single raw question response.
    Uses the variable's distribution directly — no normalisation needed
    since we're comparing raw 1-7 scores against raw distributions.
    """
    if variable_name not in benchmarks:
        return {'overall': None, 'age_group': None}

    bench = benchmarks[variable_name]
    result = {}

    # Normalise the single response to 0-100 for comparison
    score_normalised = (raw_response - SCALE_MIN) / (SCALE_MAX - SCALE_MIN) * 100

    if bench.get('overall'):
        result['overall'] = get_percentile(score_normalised, bench['overall'])

    age = demographics.get('age_group')
    if age and bench.get('by_age', {}).get(age):
        result['age_group'] = get_percentile(
            score_normalised, bench['by_age'][age]
        )

    return result


def get_dimension_percentile(normalised_score, dimension_name, variable_name,
                              benchmarks, demographics):
    if variable_name not in benchmarks:
        return {'overall': None}

    bench = benchmarks[variable_name]
    result = {}

    if bench.get('overall'):
        result['overall'] = get_percentile(normalised_score, bench['overall'])

    age = demographics.get('age_group')
    if age and bench.get('by_age', {}).get(age):
        result['age_group'] = get_percentile(
            normalised_score, bench['by_age'][age]
        )

    gender = demographics.get('gender')
    if gender and bench.get('by_gender', {}).get(gender):
        result['gender'] = get_percentile(
            normalised_score, bench['by_gender'][gender]
        )

    country = demographics.get('country')
    if country and bench.get('by_country', {}).get(country):
        result['country'] = get_percentile(
            normalised_score, bench['by_country'][country]
        )

    frequency = demographics.get('ai_tool_use_frequency')
    if frequency and bench.get('by_frequency', {}).get(frequency):
        result['frequency'] = get_percentile(
            normalised_score, bench['by_frequency'][frequency]
        )

    return result


def score_dimension(dimension_name, responses, benchmarks, demographics):
    config = DIMENSIONS[dimension_name]
    questions = config['questions']
    variables = config['variables']
    reverse_questions = config['reverse']

    raw_total = 0
    question_scores = {}

    for i, q_key in enumerate(questions):
        raw = responses.get(q_key)
        if raw is None:
            return None

        score = int(raw)
        if q_key in reverse_questions:
            score = reverse_score(score)

        question_scores[q_key] = {
            'raw': int(raw),
            'scored': score,
            'reversed': q_key in reverse_questions,
            'variable': variables[i],
        }

        raw_total += score

    n_questions = len(questions)
    normalised = normalise_to_100(raw_total, n_questions)

    primary_variable = variables[0]
    percentiles = get_dimension_percentile(
        normalised, dimension_name, primary_variable, benchmarks, demographics
    )

    return {
        'dimension': dimension_name,
        'label': config['label'],
        'subtitle': config['subtitle'],
        'raw_total': raw_total,
        'normalised_score': normalised,
        'percentiles': percentiles,
        'question_scores': question_scores,
        'n_questions': n_questions,
    }


# ============================================================
# VARIABLE-LEVEL HIGHLIGHT FUNCTIONS
# ============================================================

def find_most_distinctive_variable(responses, benchmarks, demographics, dimension_results):
    """
    Find the single question across all 39 where the participant's
    response diverges most from the population — measured by
    distance from 50th percentile (most extreme in either direction).
    Returns the question key, variable name, question text, raw response,
    and percentiles.
    """
    most_distinctive = None
    max_distance = 0

    # Fixed highlights to exclude from personalised slot
    fixed_keys = {h['question_key'] for h in FIXED_HIGHLIGHTS}

    for dim_name, config in DIMENSIONS.items():
        questions = config['questions']
        variables = config['variables']
        reverse_questions = config['reverse']

        for i, q_key in enumerate(questions):
            if q_key in fixed_keys:
                continue

            raw = responses.get(q_key)
            if raw is None:
                continue

            variable = variables[i]
            if variable not in benchmarks:
                continue

            # Use raw response for percentile (scored, respecting reversal)
            scored = int(raw)
            if q_key in reverse_questions:
                scored = reverse_score(scored)

            score_normalised = (scored - SCALE_MIN) / (SCALE_MAX - SCALE_MIN) * 100

            bench = benchmarks[variable]
            if not bench.get('overall'):
                continue

            overall_pct = get_percentile(score_normalised, bench['overall'])
            distance = abs(overall_pct - 50)

            if distance > max_distance:
                max_distance = distance

                # Get age group percentile
                age_pct = None
                age = demographics.get('age_group')
                if age and bench.get('by_age', {}).get(age):
                    age_pct = get_percentile(score_normalised, bench['by_age'][age])

                # Build question text from variable name
                question_text = get_question_text(q_key)

                most_distinctive = {
                    'question_key': q_key,
                    'variable': variable,
                    'dimension': dim_name,
                    'dimension_label': DIMENSIONS[dim_name]['label'],
                    'question_text': question_text,
                    'raw_response': int(raw),
                    'scored_response': scored,
                    'percentiles': {
                        'overall': overall_pct,
                        'age_group': age_pct,
                    },
                    'distance_from_median': distance,
                    'type': 'personalised',
                }

    return most_distinctive


def get_fixed_variable_highlight(highlight_config, responses, benchmarks, demographics):
    """
    Get population-level statistics for a fixed highlight variable.
    Returns the participant's response plus both overall and age percentiles.
    """
    q_key = highlight_config['question_key']
    variable = highlight_config['variable']
    is_reverse = highlight_config.get('reverse', False)

    raw = responses.get(q_key)
    if raw is None:
        return None

    scored = int(raw)
    if is_reverse:
        scored = reverse_score(scored)

    score_normalised = (scored - SCALE_MIN) / (SCALE_MAX - SCALE_MIN) * 100

    bench = benchmarks.get(variable)
    if not bench or not bench.get('overall'):
        return None

    overall_pct = get_percentile(score_normalised, bench['overall'])

    age_pct = None
    age = demographics.get('age_group')
    if age and bench.get('by_age', {}).get(age):
        age_pct = get_percentile(score_normalised, bench['by_age'][age])

    return {
        'question_key': q_key,
        'variable': variable,
        'dimension': highlight_config['dimension'],
        'dimension_label': DIMENSIONS[highlight_config['dimension']]['label'],
        'question_text': highlight_config['question_text'],
        'raw_response': int(raw),
        'scored_response': scored,
        'percentiles': {
            'overall': overall_pct,
            'age_group': age_pct,
        },
        'type': highlight_config['why_interesting'],
    }


def get_question_text(q_key):
    """
    Map question keys to the actual question text shown to participants.
    """
    QUESTION_TEXTS = {
        # Trust
        'trust_q1': 'When AI gives me information, I generally trust it is accurate',
        'trust_q2': 'I feel confident relying on information or recommendations generated by AI',
        'trust_q3': 'I worry that AI will present incorrect information as if it were fact',
        'trust_q4': 'When I feel uncertain, I am more likely to trust guidance from AI systems',
        # Disclosure
        'disc_q1': 'I feel comfortable sharing personal thoughts or emotions with AI that I would not share with most people',
        'disc_q2': 'I feel emotionally safer expressing myself to AI than I do to many people in my life',
        'disc_q3': 'There are things I have told AI that I have never told another person',
        'disc_q4': 'I am more open with AI about some topics than I am with people in my life',
        # Reliance
        'rel_q1': 'I feel uneasy or restless when I cannot use AI tools for an extended period',
        'rel_q2': 'I struggle to function effectively without assistance from digital or AI systems',
        'rel_q3': 'I rely on AI for many everyday work or personal decisions',
        'rel_q4': 'I often rely on AI even when I could work things out on my own',
        'rel_q5': 'Some of my abilities have weakened because AI systems now perform those tasks for me',
        # Decision Delegation
        'del_q1': 'I regularly hand over decisions to AI systems that I previously made myself',
        'del_q2': 'When I use AI for decisions, I usually accept its recommendations without making significant changes',
        'del_q3': 'I sometimes follow AI recommendations even when they do not feel right to me',
        'del_q4': 'I am comfortable relying on AI systems for important decisions that could significantly affect my life or work',
        'del_q5': 'When I feel uncertain about a decision, I am more likely to rely on AI guidance',
        # Verification
        'ver_q1': 'I regularly double-check information provided by AI using other sources',
        'ver_q2': 'I often skip checking AI information because it takes too much time or effort',
        'ver_q3': 'When information feels complicated or mentally demanding, I am more likely to accept it without checking carefully',
        'ver_q4': 'I use independent sources to confirm whether AI-generated information is accurate',
        # Human Agency
        'agency_q1': 'My actions feel self-directed rather than driven by external forces',
        'agency_q2': 'I feel in control of decisions when using AI or automated systems',
        'agency_q3': 'Using AI tools has changed how much I trust my own judgement',
        'agency_q4': 'I sometimes feel influenced by systems without being fully aware of how',
        'agency_q5': 'I sometimes question what is genuinely mine versus shaped by suggestions from AI tools',
        # Emotional Regulation
        'emot_q1': 'AI sometimes gives me a sense of relief or support when I feel emotionally overwhelmed',
        'emot_q2': 'I receive emotional support or comfort from AI tools',
        'emot_q3': 'Over time, my emotional or conversational boundaries with AI have become more open',
        'emot_q4': 'When I feel stressed, anxious, or emotionally overwhelmed, I often turn to AI to help me process my thoughts',
        # Thought Partnership
        'thought_q1': 'I use AI as a sounding board — thinking out loud and developing ideas through conversation',
        'thought_q2': 'I use AI to challenge or stress-test my own beliefs and assumptions',
        'thought_q3': 'AI has changed how deeply I engage with my own thinking',
        'thought_q4': 'I tend to use AI in ways that confirm what I already think rather than challenge it',
        # Social Transparency
        'soc_q1': 'I openly acknowledge when AI has contributed to my work or thinking',
        'soc_q2': 'I downplay or hide how much I use AI when talking to friends or family',
        'soc_q3': 'I feel comfortable telling people in my life how I really use AI',
        'soc_q4': 'There is a gap between how much I actually use AI and what I let others believe',
    }
    return QUESTION_TEXTS.get(q_key, q_key)


# ============================================================
# PERCEPTION GAP ANALYSIS
# ============================================================

PERCEPTION_MAP = {
    'Much less than most people': 10,
    'Somewhat less than most people': 30,
    'About the same as most people': 50,
    'Somewhat more than most people': 70,
    'Much more than most people': 90,
}


def analyse_perception_gap(perceived, actual_percentile, dimension):
    if not perceived or actual_percentile is None:
        return None

    perceived_estimate = PERCEPTION_MAP.get(perceived)
    if perceived_estimate is None:
        return None

    gap = actual_percentile - perceived_estimate
    abs_gap = abs(gap)

    if abs_gap < 15:
        magnitude = 'accurate'
        description = 'Your estimate was close to your actual result'
    elif abs_gap < 30:
        magnitude = 'moderate'
        direction = 'higher' if gap > 0 else 'lower'
        description = f'Your actual result was somewhat {direction} than you estimated'
    else:
        magnitude = 'significant'
        direction = 'higher' if gap > 0 else 'lower'
        description = f'Your actual result was significantly {direction} than you estimated'

    return {
        'dimension': dimension,
        'perceived_estimate': perceived_estimate,
        'actual_percentile': actual_percentile,
        'gap': round(gap, 1),
        'abs_gap': round(abs_gap, 1),
        'magnitude': magnitude,
        'description': description,
        'underestimated': gap > 0,
        'overestimated': gap < 0,
    }


# ============================================================
# DOMINANT PATTERN IDENTIFICATION
# ============================================================

def identify_dominant_patterns(dimension_results):
    scored = [
        (name, data)
        for name, data in dimension_results.items()
        if data and data.get('percentiles', {}).get('overall') is not None
    ]

    sorted_dims = sorted(
        scored,
        key=lambda x: x[1]['percentiles']['overall'],
        reverse=True
    )

    return {
        'highest': [
            {
                'dimension': name,
                'label': data['label'],
                'percentile': data['percentiles']['overall'],
                'normalised_score': data['normalised_score'],
            }
            for name, data in sorted_dims[:3]
        ],
        'lowest': [
            {
                'dimension': name,
                'label': data['label'],
                'percentile': data['percentiles']['overall'],
                'normalised_score': data['normalised_score'],
            }
            for name, data in sorted_dims[-3:]
        ],
        'full_ranking': [
            {
                'dimension': name,
                'label': data['label'],
                'percentile': data['percentiles']['overall'],
                'normalised_score': data['normalised_score'],
            }
            for name, data in sorted_dims
        ],
    }


def generate_headline(dimension_results):
    patterns = identify_dominant_patterns(dimension_results)
    highest = patterns['highest'][0] if patterns['highest'] else None
    lowest = patterns['lowest'][0] if patterns['lowest'] else None

    if not highest or not lowest:
        return 'Your AI Identity Profile is ready'

    headlines = {
        ('trust', 'verification'): 'You trust AI significantly — but rarely check what it tells you',
        ('disclosure', 'social_transparency'): 'You share deeply with AI but keep that private from others',
        ('thought_partnership', 'reliance'): 'You think deeply with AI but show signs of growing dependency',
        ('human_agency', 'decision_delegation'): 'You maintain strong agency while delegating surprisingly few decisions',
        ('emotional_regulation', 'human_agency'): 'AI plays a significant role in your emotional life',
    }

    pair = (highest['dimension'], lowest['dimension'])
    if pair in headlines:
        return headlines[pair]

    return (
        f"Your {highest['label']} score places you in the "
        f"{int(highest['percentile'])}th percentile — "
        f"your {lowest['label']} score is among the lowest"
    )


# ============================================================
# MAIN SCORING FUNCTION
# ============================================================

def score_assessment(responses, demographics, benchmark_path='benchmark_tables.json'):
    """
    Main function — scores a complete assessment.
    Now also returns variable_highlights for the free results page.
    """

    with open(benchmark_path, 'r') as f:
        benchmarks = json.load(f)

    # Score all nine dimensions
    dimension_results = {}
    for dimension_name in DIMENSIONS:
        result = score_dimension(dimension_name, responses, benchmarks, demographics)
        dimension_results[dimension_name] = result

    # Identify dominant patterns
    patterns = identify_dominant_patterns(dimension_results)
    headline = generate_headline(dimension_results)

    # Perception gap analysis
    perception_gaps = {}

    perceived_usage = responses.get('perceived_usage')
    perceived_reliance = responses.get('perceived_reliance')
    perceived_dependence = responses.get('perceived_dependence')

    if perceived_usage and dimension_results.get('trust'):
        trust_percentile = dimension_results['trust']['percentiles'].get('overall')
        perception_gaps['usage_vs_trust'] = analyse_perception_gap(
            perceived_usage, trust_percentile, 'trust'
        )

    if perceived_reliance and dimension_results.get('reliance'):
        reliance_percentile = dimension_results['reliance']['percentiles'].get('overall')
        perception_gaps['reliance'] = analyse_perception_gap(
            perceived_reliance, reliance_percentile, 'reliance'
        )

    if perceived_dependence and dimension_results.get('reliance'):
        reliance_percentile = dimension_results['reliance']['percentiles'].get('overall')
        perception_gaps['dependence'] = analyse_perception_gap(
            perceived_dependence, reliance_percentile, 'reliance'
        )

    # ── NEW: Variable-level highlights ──────────────────────────────────────
    variable_highlights = []

    # 1. Most distinctive personalised variable
    most_distinctive = find_most_distinctive_variable(
        responses, benchmarks, demographics, dimension_results
    )
    if most_distinctive:
        variable_highlights.append(most_distinctive)

    # 2. Fixed highlights — disclosure and social transparency
    for fixed in FIXED_HIGHLIGHTS:
        highlight = get_fixed_variable_highlight(fixed, responses, benchmarks, demographics)
        if highlight:
            variable_highlights.append(highlight)

    # Build complete results object
    results = {
        'demographics': demographics,
        'dimensions': dimension_results,
        'patterns': patterns,
        'headline': headline,
        'perception_gaps': perception_gaps,
        'variable_highlights': variable_highlights,
        'summary': {
            'dimensions_scored': len([d for d in dimension_results.values() if d]),
            'highest_dimension': patterns['highest'][0] if patterns['highest'] else None,
            'lowest_dimension': patterns['lowest'][0] if patterns['lowest'] else None,
        }
    }

    return results


# ============================================================
# TEST
# ============================================================

if __name__ == '__main__':
    sample_responses = {
        'trust_q1': 6, 'trust_q2': 6, 'trust_q3': 2, 'trust_q4': 5,
        'disc_q1': 4, 'disc_q2': 3, 'disc_q3': 3, 'disc_q4': 4,
        'rel_q1': 5, 'rel_q2': 4, 'rel_q3': 5, 'rel_q4': 4, 'rel_q5': 3,
        'del_q1': 4, 'del_q2': 5, 'del_q3': 3, 'del_q4': 3, 'del_q5': 5,
        'ver_q1': 2, 'ver_q2': 6, 'ver_q3': 5, 'ver_q4': 2,
        'agency_q1': 5, 'agency_q2': 4, 'agency_q3': 4, 'agency_q4': 4, 'agency_q5': 3,
        'emot_q1': 2, 'emot_q2': 2, 'emot_q3': 2, 'emot_q4': 2,
        'thought_q1': 6, 'thought_q2': 6, 'thought_q3': 6, 'thought_q4': 2,
        'soc_q1': 4, 'soc_q2': 3, 'soc_q3': 4, 'soc_q4': 3,
        'perceived_usage': 'Somewhat more than most people',
        'perceived_reliance': 'About the same as most people',
        'perceived_dependence': 'Somewhat less than most people',
    }

    sample_demographics = {
        'age_group': '35 - 44',
        'gender': 'Woman',
        'country': 'United States',
        'ai_tool_use_frequency': 'Often',
    }

    results = score_assessment(
        sample_responses,
        sample_demographics,
        'benchmark_tables.json'
    )

    print('SCORING ENGINE V2 TEST')
    print('=' * 60)
    print(f'Headline: {results["headline"]}')
    print()
    print('DIMENSION SCORES:')
    for dim_name, data in results['dimensions'].items():
        if data:
            pct = data['percentiles'].get('overall', 'N/A')
            age_pct = data['percentiles'].get('age_group', 'N/A')
            print(f'  {data["label"]:<25} overall={pct}th  age={age_pct}th')

    print()
    print('VARIABLE HIGHLIGHTS:')
    for h in results['variable_highlights']:
        print(f'  [{h["type"]}] {h["question_key"]}')
        print(f'    Text: {h["question_text"][:60]}...')
        print(f'    Response: {h["raw_response"]}/7')
        print(f'    Overall: {h["percentiles"]["overall"]}th percentile')
        print(f'    Age group: {h["percentiles"].get("age_group")}th percentile')
        print()
