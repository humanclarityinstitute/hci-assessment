"""
HCI AI Identity & Behaviour Assessment
Scoring Engine

Takes a completed set of assessment responses and produces
a full results object containing:
- Nine dimension scores normalised to 0-100
- Nine percentile rankings overall
- Percentile rankings by demographic cohort
- Dominant patterns (highest and lowest dimensions)
- Perception gap analysis

Usage:
    from scoring_engine import score_assessment
    results = score_assessment(responses, demographics, 'benchmark_tables.json')
"""

import json
import numpy as np
from scipy import stats


# ============================================================
# DIMENSION CONFIGURATION
# Each dimension maps question keys to variables
# Reverse scored questions are flipped before scoring
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
# CORE SCORING FUNCTIONS
# ============================================================

def reverse_score(score, scale_max=SCALE_MAX):
    """Flip a score on the scale. 7 becomes 1, 6 becomes 2 etc."""
    return (scale_max + 1) - score


def normalise_to_100(raw_score, n_questions):
    """
    Convert raw sum score to 0-100 scale.
    Formula: (raw - min_possible) / (max_possible - min_possible) * 100
    """
    min_possible = n_questions * SCALE_MIN
    max_possible = n_questions * SCALE_MAX
    return round((raw_score - min_possible) / (max_possible - min_possible) * 100, 1)


def get_percentile(score_0_100, distribution_raw):
    """
    Get percentile of a normalised score against a raw distribution.
    Converts distribution to 0-100 scale before comparison.
    """
    n_questions = 1
    dist_normalised = [
        (s - SCALE_MIN) / (SCALE_MAX - SCALE_MIN) * 100
        for s in distribution_raw
    ]
    return round(float(stats.percentileofscore(dist_normalised, score_0_100, kind='rank')), 0)


def get_dimension_percentile(normalised_score, dimension_name, variable_name,
                              benchmarks, demographics):
    """
    Get overall and demographic percentiles for a dimension score.
    Returns dict with overall and available demographic percentiles.
    """
    if variable_name not in benchmarks:
        return {'overall': None}

    bench = benchmarks[variable_name]
    result = {}

    # Overall percentile
    if bench.get('overall'):
        result['overall'] = get_percentile(normalised_score, bench['overall'])

    # Age group percentile
    age = demographics.get('age_group')
    if age and bench.get('by_age', {}).get(age):
        result['age_group'] = get_percentile(
            normalised_score, bench['by_age'][age]
        )

    # Gender percentile
    gender = demographics.get('gender')
    if gender and bench.get('by_gender', {}).get(gender):
        result['gender'] = get_percentile(
            normalised_score, bench['by_gender'][gender]
        )

    # Country percentile
    country = demographics.get('country')
    if country and bench.get('by_country', {}).get(country):
        result['country'] = get_percentile(
            normalised_score, bench['by_country'][country]
        )

    # Frequency percentile
    frequency = demographics.get('ai_tool_use_frequency')
    if frequency and bench.get('by_frequency', {}).get(frequency):
        result['frequency'] = get_percentile(
            normalised_score, bench['by_frequency'][frequency]
        )

    return result


def score_dimension(dimension_name, responses, benchmarks, demographics):
    """
    Score a single dimension.
    Returns normalised score, percentiles, and question-level detail.
    """
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

    # Use first variable for benchmark lookup
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
# PERCEPTION GAP ANALYSIS
# Compares self-estimates against actual percentile scores
# ============================================================

PERCEPTION_MAP = {
    'Much less than most people': 10,
    'Somewhat less than most people': 30,
    'About the same as most people': 50,
    'Somewhat more than most people': 70,
    'Much more than most people': 90,
}


def analyse_perception_gap(perceived, actual_percentile, dimension):
    """
    Compare self-estimate to actual percentile.
    Returns gap analysis with direction and magnitude.
    """
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
    """
    Identify highest and lowest scoring dimensions.
    Returns top 3 and bottom 3 by overall percentile.
    """
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
    """
    Generate a personalised one-line headline based on
    the most extreme dimension scores.
    """
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

    Args:
        responses: dict of question_key -> score (1-7)
                   Keys follow the pattern defined in DIMENSIONS above
                   e.g. {'trust_q1': 5, 'trust_q2': 6, ...}

        demographics: dict with keys:
                      age_group, gender, country, ai_tool_use_frequency

        benchmark_path: path to benchmark_tables.json

    Returns:
        Complete results object with all scores, percentiles,
        patterns, and perception gap analysis
    """

    # Load benchmark tables
    with open(benchmark_path, 'r') as f:
        benchmarks = json.load(f)

    # Score all nine dimensions
    dimension_results = {}
    for dimension_name in DIMENSIONS:
        result = score_dimension(dimension_name, responses, benchmarks, demographics)
        dimension_results[dimension_name] = result

    # Identify dominant patterns
    patterns = identify_dominant_patterns(dimension_results)

    # Generate headline
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

    # Build complete results object
    results = {
        'demographics': demographics,
        'dimensions': dimension_results,
        'patterns': patterns,
        'headline': headline,
        'perception_gaps': perception_gaps,
        'summary': {
            'dimensions_scored': len([d for d in dimension_results.values() if d]),
            'highest_dimension': patterns['highest'][0] if patterns['highest'] else None,
            'lowest_dimension': patterns['lowest'][0] if patterns['lowest'] else None,
        }
    }

    return results


# ============================================================
# TEST WITH SAMPLE RESPONSES
# ============================================================

if __name__ == '__main__':

    # Sample responses — simulating a high trust, low verification user
    sample_responses = {
        # Trust (high trust profile)
        'trust_q1': 6,
        'trust_q2': 6,
        'trust_q3': 2,  # reverse scored — low worry = high trust
        'trust_q4': 5,

        # Disclosure (moderate)
        'disc_q1': 4,
        'disc_q2': 3,
        'disc_q3': 3,
        'disc_q4': 4,

        # Reliance (moderate-high)
        'rel_q1': 5,
        'rel_q2': 4,
        'rel_q3': 5,
        'rel_q4': 4,
        'rel_q5': 3,

        # Decision Delegation (moderate)
        'del_q1': 4,
        'del_q2': 5,
        'del_q3': 3,
        'del_q4': 3,
        'del_q5': 5,

        # Verification (low — skips checking)
        'ver_q1': 2,
        'ver_q2': 6,  # reverse scored — high effort avoidance
        'ver_q3': 5,  # reverse scored — proceeds without checking
        'ver_q4': 2,

        # Human Agency (moderate)
        'agency_q1': 5,
        'agency_q2': 4,
        'agency_q3': 4,  # reverse scored
        'agency_q4': 4,  # reverse scored
        'agency_q5': 3,  # reverse scored

        # Emotional Regulation (low)
        'emot_q1': 2,
        'emot_q2': 2,
        'emot_q3': 2,
        'emot_q4': 2,

        # Thought Partnership (high)
        'thought_q1': 6,
        'thought_q2': 6,
        'thought_q3': 6,
        'thought_q4': 2,  # reverse scored — low echo chamber

        # Social Transparency (moderate)
        'soc_q1': 4,
        'soc_q2': 3,  # reverse scored
        'soc_q3': 4,
        'soc_q4': 3,  # reverse scored

        # Perceived normality
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
        '/home/claude/benchmark_tables.json'
    )

    print('SCORING ENGINE TEST RESULTS')
    print('=' * 60)
    print(f'Headline: {results["headline"]}')
    print()
    print('DIMENSION SCORES:')
    print(f'{"Dimension":<25} | {"Score":>6} | {"Percentile":>10}')
    print('-' * 50)
    for dim_name, data in results['dimensions'].items():
        if data:
            score = data['normalised_score']
            pct = data['percentiles'].get('overall', 'N/A')
            label = data['label']
            print(f'{label:<25} | {score:>6.1f} | {pct:>9}th')

    print()
    print('DOMINANT PATTERNS:')
    print('Highest:')
    for p in results['patterns']['highest']:
        print(f"  {p['label']}: {p['percentile']}th percentile")
    print('Lowest:')
    for p in results['patterns']['lowest']:
        print(f"  {p['label']}: {p['percentile']}th percentile")

    print()
    print('PERCEPTION GAPS:')
    for key, gap in results['perception_gaps'].items():
        if gap:
            print(f"  {gap['dimension']}: estimated {gap['perceived_estimate']}th, actual {gap['actual_percentile']}th — {gap['description']}")

    print()
    print('DEMOGRAPHIC PERCENTILES (Trust dimension):')
    trust_percentiles = results['dimensions']['trust']['percentiles']
    for seg, pct in trust_percentiles.items():
        print(f'  {seg}: {pct}th percentile')
