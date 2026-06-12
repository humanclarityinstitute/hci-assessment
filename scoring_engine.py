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
# VARIABLE HIGHLIGHTS CONFIGURATION
# The free results page shows three variable-level cards:
#   1 personalised (the participant's most distinctive answer) + 2 fixed.
# ai_boundaries_change_over_time is excluded — it is a recoded 3-point
# item kept for the composite only, never shown as a histogram card.
# ============================================================

EXCLUDED_FROM_HIGHLIGHTS = {'ai_boundaries_change_over_time'}

# (card type -> the specific variable shown). These two always appear.
FIXED_HIGHLIGHTS = [
    ('disclosure', 'disclosure_untold_things'),
    ('social_transparency', 'social_transparency_gap'),
]

# Exact wording shown on each card, quoted as the participant's item.
# Verbatim from the live assessment form (hci-assessment-form.html),
# mapped question-key -> variable via the DIMENSIONS config above.
QUESTION_TEXT = {
    # Trust
    'trust_ai_for_accuracy': 'When AI gives me information, I generally trust it is accurate.',
    'confident_relying_on_ai_outputs': 'I feel confident relying on information or recommendations generated by AI.',
    'worry_ai_presents_false_info': 'I worry that AI will present incorrect information as if it were fact.',
    'ai_decision_reliance_when_difficult': 'When I feel uncertain, I am more likely to trust guidance from AI systems.',
    # Disclosure
    'ai_personal_sharing_comfort': 'I feel comfortable sharing personal thoughts or emotions with AI that I would not share with most people.',
    'ai_emotional_safety_vs_humans': 'I feel emotionally safer expressing myself to AI than I do to many people in my life.',
    'disclosure_untold_things': 'There are things I have told AI that I have never told another person.',
    'disclosure_comparative_openness': 'I am more open with AI about some topics than I am with people in my life.',
    # Reliance
    'restless_without_ai': 'I feel uneasy or restless when I cannot use AI tools for an extended period.',
    'system_reliance_struggle_without': 'I struggle to function effectively without assistance from digital or AI systems.',
    'ai_reliance_decisions': 'I rely on digital or AI suggestions to make many everyday work or personal decisions.',
    'delegation_rely_even_if_possible': 'I often rely on AI even when I could work things out on my own.',
    'delegation_skill_decline': 'Some of my abilities have weakened because AI systems now perform those tasks for me.',
    # Decision Delegation
    'delegation_regular_handover': 'I regularly hand over decisions to AI systems that I previously made myself.',
    'accept_ai_output_without_change': 'When I use AI for decisions, I usually accept its recommendations without making significant changes.',
    'override_follow_despite_discomfort': 'I sometimes follow AI recommendations even when they do not feel right to me.',
    'comfort_high_stakes_delegation': 'I am comfortable relying on AI systems for important decisions that could significantly affect my life or work.',
    'delegation_when_uncertain': 'When I feel uncertain about a decision, I am more likely to rely on AI guidance.',
    # Verification
    'double_check_ai_info': 'I regularly double-check information provided by AI using other sources.',
    'verify_skip_due_to_effort': 'I often skip checking AI information because it takes too much time or effort.',
    'proceed_without_checking': 'When information feels complicated or mentally demanding, I am more likely to accept it without checking carefully.',
    'verify_use_external_sources': 'I use independent sources to confirm whether AI-generated information is accurate.',
    # Human Agency
    'self_directed_action_feeling': 'My actions feel self-directed rather than driven by external forces.',
    'agency_control_feel_in_control': 'I feel in control of decisions when using AI or automated systems.',
    'agency_trust_own_judgement': 'Using AI tools has changed how much I trust my own judgement.',
    'nudging_influenced_unaware': 'I sometimes feel influenced by systems without being fully aware of how.',
    'ai_identity_mine_vs_ai': 'I sometimes question what is genuinely "mine" versus shaped by suggestions from AI tools.',
    # Emotional Regulation
    'ai_emotion_relief_support': 'AI sometimes gives me a sense of relief or support when I feel emotionally overwhelmed.',
    'ai_emotional_support_extent': 'I receive emotional support or comfort from AI tools.',
    'ai_boundaries_change_over_time': 'Over time, my emotional or conversational boundaries with AI have become more open.',
    'emotional_regulation_coping': 'When I feel stressed, anxious, or emotionally overwhelmed, I often turn to AI to help me process my thoughts.',
    # Thought Partnership
    'thought_partnership_sounding_board': 'I use AI as a sounding board — thinking out loud and developing ideas through conversation.',
    'thought_partnership_belief_challenge': 'I use AI to challenge or stress-test my own beliefs and assumptions.',
    'ai_thinking_depth_engagement': 'AI has changed how deeply I engage with my own thinking.',
    'ai_validation_reinforce_beliefs': 'I tend to use AI in ways that confirm what I already think rather than challenge it.',
    # Social Transparency
    'social_transparency_professional': 'I openly acknowledge when AI has contributed to my work or thinking.',
    'social_transparency_concealment': 'I downplay or hide how much I use AI when talking to friends or family.',
    'social_transparency_comfort': 'I feel comfortable telling people in my life how I really use AI.',
    'social_transparency_gap': 'There is a gap between how much I actually use AI and what I let others believe.',
}


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


def percentile_of_answer(raw_answer, distribution_raw, reverse=False):
    """
    Rank a single raw 1-7 answer against the real population distribution
    for that same question. For reverse-coded items the percentile is
    flipped (100 - p) so a high raw answer contributes a low position to
    the dimension (and vice versa).

    Returns a 0-100 percentile, or None if the distribution is empty.
    """
    if not distribution_raw:
        return None
    p = float(stats.percentileofscore(distribution_raw, raw_answer, kind='rank'))
    if reverse:
        p = 100.0 - p
    return p


# Maps a demographic segment to (its key in the request, its key in the
# benchmark tables). 'overall' is handled separately with no demographic value.
_SEGMENTS = [
    ('age_group', 'by_age'),
    ('gender', 'by_gender'),
    ('country', 'by_country'),
    ('frequency', 'by_frequency'),
]
# The frequency segment is read from a differently-named demographic field.
_DEMO_FIELD = {
    'age_group': 'age_group',
    'gender': 'gender',
    'country': 'country',
    'frequency': 'ai_tool_use_frequency',
}


def get_dimension_percentiles(question_scores, benchmarks, demographics):
    """
    Average-of-percentiles dimension positioning.

    For each item in the dimension, rank the participant's raw answer
    against the REAL population that answered that same question (flipping
    for reverse items), then average those per-item percentiles into a
    single dimension position. Every comparison is like-for-like
    (one answer vs the crowd that answered that one question), so there is
    no composite-vs-single-answer mismatch and no central compression.

    A demographic segment is only reported if at least one of the
    dimension's items has benchmark data for that segment; the average is
    taken over whichever items have it.

    Returns {'overall': p, 'age_group': p, ...} with rounded percentiles.
    """
    # 'overall' plus any demographic segment we can resolve
    targets = [('overall', None, None)]
    for seg, bench_key in _SEGMENTS:
        demo_val = demographics.get(_DEMO_FIELD[seg])
        if demo_val:
            targets.append((seg, bench_key, demo_val))

    result = {}
    for seg, bench_key, demo_val in targets:
        item_percentiles = []
        for qs in question_scores.values():
            bench = benchmarks.get(qs['variable'])
            if not bench:
                continue
            if seg == 'overall':
                dist = bench.get('overall')
            else:
                dist = bench.get(bench_key, {}).get(demo_val)
            p = percentile_of_answer(qs['raw'], dist, qs['reversed'])
            if p is not None:
                item_percentiles.append(p)
        if item_percentiles:
            result[seg] = round(sum(item_percentiles) / len(item_percentiles), 0)

    if 'overall' not in result:
        result['overall'] = None
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

    # Position via average-of-percentiles across EVERY item in the dimension
    # (each item ranked against the real population that answered it).
    percentiles = get_dimension_percentiles(
        question_scores, benchmarks, demographics
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

def _bin_counts(arr):
    """Compact 1-7 distribution (list of 7 counts) from a raw score array."""
    if not arr:
        return None
    counts = [0] * 7
    for s in arr:
        v = int(round(s))
        if 1 <= v <= 7:
            counts[v - 1] += 1
    return counts


def _make_highlight(card_type, variable, raw_answer, benchmarks, demographics):
    """
    Package one variable into the shape the results page expects:
    type, question text, the participant's raw answer, their percentile
    (overall + age), and the 1-7 distribution to draw the histogram from.
    """
    bench = benchmarks.get(variable)
    if not bench:
        return None

    age = demographics.get('age_group')

    overall_dist = bench.get('dist_overall') or _bin_counts(bench.get('overall'))
    age_dist = None
    if age:
        age_dist = (bench.get('dist_by_age', {}).get(age)
                    or _bin_counts(bench.get('by_age', {}).get(age)))

    overall_pct = percentile_of_answer(raw_answer, bench.get('overall'))
    age_pct = percentile_of_answer(raw_answer, bench.get('by_age', {}).get(age)) if age else None

    return {
        'type': card_type,
        'variable': variable,
        'question_text': QUESTION_TEXT.get(variable, variable.replace('_', ' ').capitalize()),
        'raw_response': int(raw_answer),
        'percentiles': {
            'overall': round(overall_pct) if overall_pct is not None else None,
            'age_group': round(age_pct) if age_pct is not None else None,
        },
        'distribution': {
            'overall': overall_dist,
            'age_group': age_dist,
        },
        'n': {
            'overall': sum(overall_dist) if overall_dist else None,
            'age_group': sum(age_dist) if age_dist else None,
        },
        'age_label': age or '',
    }


def build_variable_highlights(dimension_results, benchmarks, demographics):
    """
    Select the three variable cards for the free results page:
      - one PERSONALISED: the participant's most distinctive answer
        (the eligible item whose percentile sits furthest from the
        population centre), and
      - two FIXED: disclosure + social transparency (see FIXED_HIGHLIGHTS).

    ai_boundaries_change_over_time is excluded, and the fixed variables are
    excluded from the personalised search so no card repeats.
    """
    # Flatten variable -> the participant's raw 1-7 answer for that item.
    var_answers = {}
    for dim in dimension_results.values():
        if not dim:
            continue
        for qs in dim['question_scores'].values():
            var_answers[qs['variable']] = qs['raw']

    fixed_vars = {variable for _, variable in FIXED_HIGHLIGHTS}

    # Personalised: rank eligible answers by distance of their percentile from 50.
    candidates = []
    for variable, raw in var_answers.items():
        if variable in EXCLUDED_FROM_HIGHLIGHTS or variable in fixed_vars:
            continue
        bench = benchmarks.get(variable)
        if not bench:
            continue
        pct = percentile_of_answer(raw, bench.get('overall'))
        if pct is None:
            continue
        candidates.append((abs(pct - 50), variable, raw))
    candidates.sort(key=lambda c: (-c[0], c[1]))  # most distinctive first, name tiebreak

    highlights = []
    if candidates:
        _, best_var, best_raw = candidates[0]
        h = _make_highlight('personalised', best_var, best_raw, benchmarks, demographics)
        if h:
            highlights.append(h)

    for card_type, variable in FIXED_HIGHLIGHTS:
        if variable in var_answers:
            h = _make_highlight(card_type, variable, var_answers[variable], benchmarks, demographics)
            if h:
                highlights.append(h)

    return highlights


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

    # Variable-level highlight cards (1 personalised + 2 fixed)
    variable_highlights = build_variable_highlights(
        dimension_results, benchmarks, demographics
    )

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
