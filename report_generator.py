"""
HCI AI Identity & Behaviour Assessment
Report Generator

Takes a scored results object from the scoring engine and generates:
1. Free result — headline, three key scores, one benchmark comparison
2. Premium report — full personalised narrative across all nine dimensions

Uses the Claude API for personalised narrative generation.

Usage:
    from report_generator import generate_free_result, generate_premium_report
    free = generate_free_result(results)
    premium = generate_premium_report(results)
"""

import json

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ============================================================
# DIMENSION NARRATIVE PROMPTS
# One prompt per dimension — generates the deep dive section
# for the premium report
# ============================================================

DIMENSION_PROMPTS = {
    'trust': """
You are writing the Trust dimension section of a personalised AI Identity & Behaviour Report
for the Human Clarity Institute.

The participant scored at the {percentile}th percentile for Trust overall.
Among people of their age group ({age_group}), they scored at the {age_percentile}th percentile.
Among people in {country}, they scored at the {country_percentile}th percentile.

Trust measures how readily a person accepts AI-generated information as reliable.
High trust means accepting AI outputs with little scepticism.
Low trust means approaching AI with consistent caution.

Write a 180-200 word personalised section that:
1. Opens with a direct, honest statement about what their score means behaviourally
2. Provides one specific benchmark comparison that will surprise or resonate
3. Explores what this pattern might mean for them in practice
4. Closes with one genuinely interesting reflection question — not prescriptive, just curious

Tone: warm, intelligent, non-judgmental. This is insight not advice.
Do not use headers. Write in flowing prose. Do not mention the score number directly.
""",

    'disclosure': """
You are writing the Disclosure dimension section of a personalised AI Identity & Behaviour Report
for the Human Clarity Institute.

The participant scored at the {percentile}th percentile for Disclosure overall.
Among people of their age group ({age_group}), they scored at the {age_percentile}th percentile.
Among people in {country}, they scored at the {country_percentile}th percentile.

Disclosure measures what people share with AI — including things they would not share with most humans.
High disclosure suggests AI has become a uniquely safe space for personal expression.
Low disclosure suggests clear boundaries around what is shared with non-human systems.

Write a 180-200 word personalised section that:
1. Opens with a direct, honest statement about what their score means behaviourally
2. Provides one specific benchmark comparison that will surprise or resonate
3. Explores what this pattern might mean about their relationship with AI
4. Closes with one genuinely interesting reflection question — not prescriptive, just curious

Tone: warm, intelligent, non-judgmental. This is insight not advice.
Do not use headers. Write in flowing prose. Do not mention the score number directly.
""",

    'reliance': """
You are writing the Reliance dimension section of a personalised AI Identity & Behaviour Report
for the Human Clarity Institute.

The participant scored at the {percentile}th percentile for Reliance overall.
Among people of their age group ({age_group}), they scored at the {age_percentile}th percentile.
Among people in {country}, they scored at the {country_percentile}th percentile.

Reliance measures how dependent someone has become on AI for everyday functioning and thinking.
High reliance means AI has become necessary infrastructure — difficult to operate without.
Low reliance means AI remains an occasional tool used selectively.

Write a 180-200 word personalised section that:
1. Opens with a direct, honest statement about what their score means behaviourally
2. Provides one specific benchmark comparison that will surprise or resonate
3. Explores what this pattern of reliance might mean over time
4. Closes with one genuinely interesting reflection question — not prescriptive, just curious

Tone: warm, intelligent, non-judgmental. This is insight not advice.
Do not use headers. Write in flowing prose. Do not mention the score number directly.
""",

    'decision_delegation': """
You are writing the Decision Delegation dimension section of a personalised AI Identity & Behaviour Report
for the Human Clarity Institute.

The participant scored at the {percentile}th percentile for Decision Delegation overall.
Among people of their age group ({age_group}), they scored at the {age_percentile}th percentile.
Among people in {country}, they scored at the {country_percentile}th percentile.

Decision Delegation measures how much judgement a person outsources to AI.
High delegation means regularly asking AI what to do and following that guidance.
Low delegation means using AI for information while retaining full ownership of judgement.

Write a 180-200 word personalised section that:
1. Opens with a direct, honest statement about what their score means behaviourally
2. Provides one specific benchmark comparison that will surprise or resonate
3. Explores what this delegation pattern means for their autonomy and decision ownership
4. Closes with one genuinely interesting reflection question — not prescriptive, just curious

Tone: warm, intelligent, non-judgmental. This is insight not advice.
Do not use headers. Write in flowing prose. Do not mention the score number directly.
""",

    'verification': """
You are writing the Verification dimension section of a personalised AI Identity & Behaviour Report
for the Human Clarity Institute.

The participant scored at the {percentile}th percentile for Verification overall.
Among people of their age group ({age_group}), they scored at the {age_percentile}th percentile.
Among people in {country}, they scored at the {country_percentile}th percentile.

Verification measures whether someone independently checks AI outputs before acting on them.
High verification means treating AI as a starting point requiring confirmation.
Low verification means accepting AI outputs at face value without cross-checking.
Note: low verification scores often reflect friction and fatigue rather than deliberate choice.

Write a 180-200 word personalised section that:
1. Opens with a direct, honest statement about what their score means behaviourally
2. Provides one specific benchmark comparison that will surprise or resonate
3. Explores what this verification pattern means in practice — without being alarmist
4. Closes with one genuinely interesting reflection question — not prescriptive, just curious

Tone: warm, intelligent, non-judgmental. This is insight not advice.
Do not use headers. Write in flowing prose. Do not mention the score number directly.
""",

    'human_agency': """
You are writing the Human Agency dimension section of a personalised AI Identity & Behaviour Report
for the Human Clarity Institute.

The participant scored at the {percentile}th percentile for Human Agency overall.
Among people of their age group ({age_group}), they scored at the {age_percentile}th percentile.
Among people in {country}, they scored at the {country_percentile}th percentile.

Human Agency measures whether someone still feels like the author of their own thoughts and decisions.
High agency means AI feels like a tool under conscious control.
Low agency means a growing sense that AI is shaping thinking in ways that are hard to identify or resist.
This is the deepest dimension — it captures not just behaviour but the felt experience of remaining human.

Write a 180-200 word personalised section that:
1. Opens with a direct, honest statement about what their score means behaviourally
2. Provides one specific benchmark comparison that will surprise or resonate
3. Explores what this agency profile means for their sense of self and direction
4. Closes with one genuinely interesting reflection question — not prescriptive, just curious

Tone: warm, intelligent, non-judgmental. This is insight not advice.
Do not use headers. Write in flowing prose. Do not mention the score number directly.
""",

    'emotional_regulation': """
You are writing the Emotional Regulation dimension section of a personalised AI Identity & Behaviour Report
for the Human Clarity Institute.

The participant scored at the {percentile}th percentile for Emotional Regulation overall.
Among people of their age group ({age_group}), they scored at the {age_percentile}th percentile.
Among people in {country}, they scored at the {country_percentile}th percentile.

Emotional Regulation measures whether someone turns to AI to manage emotional states —
seeking comfort, processing difficult experiences, or working through personal struggles.
High scores suggest AI has taken on a role traditionally filled by trusted humans.
Low scores suggest clear separation between AI use and emotional life.
Many people engage in this behaviour without having consciously chosen to do so.

Write a 180-200 word personalised section that:
1. Opens with a direct, honest statement about what their score means behaviourally
2. Provides one specific benchmark comparison that will surprise or resonate
3. Explores what this emotional pattern means without judgment
4. Closes with one genuinely interesting reflection question — not prescriptive, just curious

Tone: warm, intelligent, non-judgmental. This is insight not advice.
Do not use headers. Write in flowing prose. Do not mention the score number directly.
""",

    'thought_partnership': """
You are writing the Thought Partnership dimension section of a personalised AI Identity & Behaviour Report
for the Human Clarity Institute.

The participant scored at the {percentile}th percentile for Thought Partnership overall.
Among people of their age group ({age_group}), they scored at the {age_percentile}th percentile.
Among people in {country}, they scored at the {country_percentile}th percentile.

Thought Partnership measures whether someone uses AI as a genuine cognitive collaborator —
thinking out loud, exploring ideas, stress-testing beliefs, developing understanding through dialogue.
High scores mean AI has become an active participant in how someone develops their thinking.
Low scores mean AI is used instrumentally for tasks rather than as an intellectual companion.
Note: someone can score high on thought partnership while still maintaining strong human agency —
these are different and independent dimensions.

Write a 180-200 word personalised section that:
1. Opens with a direct, honest statement about what their score means behaviourally
2. Provides one specific benchmark comparison that will surprise or resonate
3. Explores what this pattern of intellectual engagement with AI means
4. Closes with one genuinely interesting reflection question — not prescriptive, just curious

Tone: warm, intelligent, non-judgmental. This is insight not advice.
Do not use headers. Write in flowing prose. Do not mention the score number directly.
""",

    'social_transparency': """
You are writing the Social Transparency dimension section of a personalised AI Identity & Behaviour Report
for the Human Clarity Institute.

The participant scored at the {percentile}th percentile for Social Transparency overall.
Among people of their age group ({age_group}), they scored at the {age_percentile}th percentile.
Among people in {country}, they scored at the {country_percentile}th percentile.

Social Transparency measures whether someone openly acknowledges their AI use to others.
High transparency means AI use is openly discussed in professional and personal contexts.
Low transparency means AI use is largely private, understated, or concealed.
The gap between someone's actual AI behaviour and what they acknowledge publicly
is itself one of the most revealing data points in the entire assessment.

Write a 180-200 word personalised section that:
1. Opens with a direct, honest statement about what their score means behaviourally
2. Provides one specific benchmark comparison that will surprise or resonate
3. Explores what this transparency pattern reveals — without judgment
4. Closes with one genuinely interesting reflection question — not prescriptive, just curious

Tone: warm, intelligent, non-judgmental. This is insight not advice.
Do not use headers. Write in flowing prose. Do not mention the score number directly.
""",
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_percentile(p):
    """Format percentile with correct suffix."""
    if p is None:
        return 'N/A'
    p = int(p)
    if 11 <= p <= 13:
        return f'{p}th'
    suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(p % 10, 'th')
    return f'{p}{suffix}'


def get_percentile_description(percentile):
    """Convert percentile to plain English description."""
    if percentile is None:
        return 'average'
    p = int(percentile)
    if p >= 90:
        return 'significantly higher than most people'
    elif p >= 75:
        return 'higher than most people'
    elif p >= 60:
        return 'somewhat above average'
    elif p >= 40:
        return 'close to average'
    elif p >= 25:
        return 'somewhat below average'
    elif p >= 10:
        return 'lower than most people'
    else:
        return 'significantly lower than most people'


def select_most_interesting_benchmark(dimension_data, demographics):
    """
    Select the most interesting benchmark comparison to surface
    in the free result. Picks the demographic comparison that
    differs most from the overall percentile.
    """
    percentiles = dimension_data.get('percentiles', {})
    overall = percentiles.get('overall')

    if overall is None:
        return None, None, None

    best_segment = 'overall'
    best_percentile = overall
    best_label = 'people in our research population'
    max_diff = 0

    segment_labels = {
        'age_group': f"people in your age group ({demographics.get('age_group', '')})",
        'gender': f"{demographics.get('gender', 'people').lower()}s",
        'country': f"people in {demographics.get('country', 'your country')}",
        'frequency': 'people who use AI as frequently as you',
    }

    for segment, label in segment_labels.items():
        seg_percentile = percentiles.get(segment)
        if seg_percentile is not None:
            diff = abs(seg_percentile - overall)
            if diff > max_diff:
                max_diff = diff
                best_segment = segment
                best_percentile = seg_percentile
                best_label = label

    return best_percentile, best_label, best_segment


# ============================================================
# FREE RESULT GENERATOR
# ============================================================

def generate_free_result(results):
    """
    Generate the free result page content.
    Returns three headline scores, one benchmark comparison,
    and the personalised headline.
    """
    dimensions = results['dimensions']
    demographics = results['demographics']
    patterns = results['patterns']

    # Headline
    headline = results.get('headline', 'Your AI Identity Profile is ready')

    # Three scores to show — highest, lowest, most surprising
    full_ranking = patterns.get('full_ranking', [])

    shown_scores = []

    if len(full_ranking) >= 1:
        highest = full_ranking[0]
        shown_scores.append({
            'dimension': highest['dimension'],
            'label': highest['label'],
            'percentile': highest['percentile'],
            'description': get_percentile_description(highest['percentile']),
            'framing': 'Your strongest pattern',
        })

    if len(full_ranking) >= 2:
        lowest = full_ranking[-1]
        shown_scores.append({
            'dimension': lowest['dimension'],
            'label': lowest['label'],
            'percentile': lowest['percentile'],
            'description': get_percentile_description(lowest['percentile']),
            'framing': 'Your lowest pattern',
        })

    # Most surprising — furthest from 50th percentile excluding already shown
    shown_dims = {s['dimension'] for s in shown_scores}
    remaining = [d for d in full_ranking if d['dimension'] not in shown_dims]
    if remaining:
        most_surprising = max(remaining, key=lambda x: abs(x['percentile'] - 50))
        shown_scores.append({
            'dimension': most_surprising['dimension'],
            'label': most_surprising['label'],
            'percentile': most_surprising['percentile'],
            'description': get_percentile_description(most_surprising['percentile']),
            'framing': 'Notable finding',
        })

    # Single most interesting benchmark comparison
    primary_dim = full_ranking[0] if full_ranking else None
    best_benchmark = None

    if primary_dim:
        dim_data = dimensions.get(primary_dim['dimension'])
        if dim_data:
            pct, label, segment = select_most_interesting_benchmark(dim_data, demographics)
            if pct is not None:
                best_benchmark = {
                    'dimension': primary_dim['label'],
                    'percentile': pct,
                    'comparison_group': label,
                    'text': (
                        f"Your {primary_dim['label']} score places you higher than "
                        f"{int(pct)}% of {label}"
                    ) if pct >= 50 else (
                        f"Your {primary_dim['label']} score is lower than "
                        f"{100 - int(pct)}% of {label}"
                    ),
                }

    # Perception gap highlight if significant
    perception_highlight = None
    gaps = results.get('perception_gaps', {})
    significant_gaps = [
        g for g in gaps.values()
        if g and g.get('magnitude') == 'significant'
    ]
    if significant_gaps:
        gap = significant_gaps[0]
        direction = 'higher' if gap['underestimated'] else 'lower'
        perception_highlight = (
            f"You estimated your {gap['dimension'].replace('_', ' ')} "
            f"was around average. Your actual result was significantly "
            f"{direction} than you thought."
        )

    return {
        'headline': headline,
        'shown_scores': shown_scores,
        'best_benchmark': best_benchmark,
        'perception_highlight': perception_highlight,
        'hidden_dimensions': [
            d['label'] for d in full_ranking
            if d['dimension'] not in {s['dimension'] for s in shown_scores}
        ],
        'cta': 'See Your Full AI Identity Report',
    }


# ============================================================
# PREMIUM REPORT GENERATOR
# ============================================================

def generate_dimension_narrative(dimension_name, dimension_data, demographics, client):
    """
    Generate personalised narrative for one dimension using Claude API.
    """
    percentiles = dimension_data.get('percentiles', {})
    overall = percentiles.get('overall', 50)
    age_percentile = percentiles.get('age_group', overall)
    country_percentile = percentiles.get('country', overall)

    prompt = DIMENSION_PROMPTS[dimension_name].format(
        percentile=int(overall),
        age_group=demographics.get('age_group', 'your age group'),
        age_percentile=int(age_percentile),
        country=demographics.get('country', 'your country'),
        country_percentile=int(country_percentile),
    )

    message = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=400,
        messages=[{'role': 'user', 'content': prompt}],
    )

    return message.content[0].text.strip()


def generate_pattern_narrative(results, client):
    """
    Generate the dominant pattern section of the premium report.
    """
    patterns = results['patterns']
    demographics = results['demographics']
    highest = patterns['highest'][:2]
    lowest = patterns['lowest'][:2]

    highest_text = ' and '.join([f"{p['label']} ({format_percentile(p['percentile'])} percentile)" for p in highest])
    lowest_text = ' and '.join([f"{p['label']} ({format_percentile(p['percentile'])} percentile)" for p in lowest])

    prompt = f"""
You are writing the Dominant Patterns section of a personalised AI Identity & Behaviour Report
for the Human Clarity Institute.

This participant's strongest patterns are: {highest_text}
Their lowest patterns are: {lowest_text}
Their age group: {demographics.get('age_group', 'not specified')}
Their country: {demographics.get('country', 'not specified')}

Write a 200-250 word section that:
1. Opens by naming their dominant AI identity pattern in plain, honest language
2. Explains what the combination of their highest and lowest dimensions reveals about them
3. Notes what makes this specific combination interesting or unusual
4. Frames this as a starting point for self-understanding — not a verdict

Do not use headers. Write in flowing prose. Tone: warm, insightful, non-judgmental.
Do not mention specific score numbers. Speak directly to the person as "you".
"""

    message = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=500,
        messages=[{'role': 'user', 'content': prompt}],
    )

    return message.content[0].text.strip()


def generate_perception_gap_narrative(results, client):
    """
    Generate the perception gap section if significant gaps exist.
    """
    gaps = results.get('perception_gaps', {})
    significant = [g for g in gaps.values() if g and g.get('magnitude') in ['moderate', 'significant']]

    if not significant:
        return None

    gap_descriptions = []
    for gap in significant:
        direction = 'higher' if gap['underestimated'] else 'lower'
        gap_descriptions.append(
            f"{gap['dimension'].replace('_', ' ')}: estimated ~{gap['perceived_estimate']}th percentile, "
            f"actual {gap['actual_percentile']}th percentile ({direction} than estimated)"
        )

    prompt = f"""
You are writing the Self-Awareness section of a personalised AI Identity & Behaviour Report
for the Human Clarity Institute.

This participant estimated their AI behaviour in certain areas, and their actual results differed:
{chr(10).join(gap_descriptions)}

Write a 150-180 word section that:
1. Opens by acknowledging that most people's self-estimates differ from their actual results
2. Names their specific perception gap honestly and directly
3. Explores what this gap might reveal — without judgment
4. Notes that this kind of blind spot is both common and interesting

Do not use headers. Write in flowing prose. Tone: warm, curious, non-judgmental.
Do not mention score numbers. Speak directly to the person as "you".
"""

    message = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=350,
        messages=[{'role': 'user', 'content': prompt}],
    )

    return message.content[0].text.strip()


def generate_premium_report(results, api_key=None):
    """
    Generate the complete premium report.

    Args:
        results: scored results object from scoring_engine
        api_key: Anthropic API key (optional if set in environment)

    Returns:
        Complete premium report as structured dict
    """
    if not ANTHROPIC_AVAILABLE:
        raise ImportError('anthropic package required. Install with: pip install anthropic')
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    demographics = results['demographics']
    dimensions = results['dimensions']
    patterns = results['patterns']

    print('Generating premium report...')

    # Generate pattern narrative
    print('  Generating dominant pattern narrative...')
    pattern_narrative = generate_pattern_narrative(results, client)

    # Generate perception gap narrative if applicable
    print('  Generating perception gap narrative...')
    perception_narrative = generate_perception_gap_narrative(results, client)

    # Generate dimension narratives
    dimension_narratives = {}
    for dim_name, dim_data in dimensions.items():
        if dim_data:
            print(f'  Generating {dim_name} narrative...')
            narrative = generate_dimension_narrative(dim_name, dim_data, demographics, client)
            dimension_narratives[dim_name] = {
                'label': dim_data['label'],
                'subtitle': dim_data['subtitle'],
                'percentile': dim_data['percentiles'].get('overall'),
                'normalised_score': dim_data['normalised_score'],
                'percentiles': dim_data['percentiles'],
                'narrative': narrative,
            }

    # Build complete report structure
    report = {
        'metadata': {
            'demographics': demographics,
            'generated_by': 'HCI AI Identity & Behaviour Assessment',
            'version': '1.0',
        },
        'headline': results.get('headline'),
        'pattern_narrative': pattern_narrative,
        'perception_narrative': perception_narrative,
        'dimensions': dimension_narratives,
        'summary': {
            'highest': patterns['highest'],
            'lowest': patterns['lowest'],
            'full_ranking': patterns['full_ranking'],
        },
        'methodology_note': (
            "This report is based on your responses to the HCI AI Identity & Behaviour Assessment, "
            "benchmarked against data from nearly 10,000 participants across multiple research studies "
            "conducted by the Human Clarity Institute. Percentile rankings show where your scores sit "
            "relative to this population. Results reflect self-reported behaviour and are designed "
            "for personal insight and reflection."
        ),
    }

    print('Premium report generation complete.')
    return report


# ============================================================
# TEST
# ============================================================

if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/home/claude')
    from scoring_engine import score_assessment

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

    # Score the assessment
    results = score_assessment(
        sample_responses,
        sample_demographics,
        '/home/claude/benchmark_tables.json'
    )

    # Generate free result
    free = generate_free_result(results)
    print('FREE RESULT:')
    print('=' * 60)
    print(f'Headline: {free["headline"]}')
    print()
    print('Shown scores:')
    for s in free['shown_scores']:
        print(f'  {s["label"]}: {format_percentile(s["percentile"])} percentile — {s["description"]}')
    print()
    if free['best_benchmark']:
        print(f'Benchmark: {free["best_benchmark"]["text"]}')
    print()
    if free['perception_highlight']:
        print(f'Perception gap: {free["perception_highlight"]}')
    print()
    print(f'Hidden dimensions: {free["hidden_dimensions"]}')
    print()

    # Generate premium report (requires API key)
    print('Generating premium report (requires Claude API)...')
    try:
        report = generate_premium_report(results)

        print()
        print('PREMIUM REPORT SAMPLE:')
        print('=' * 60)
        print(f'Headline: {report["headline"]}')
        print()
        print('DOMINANT PATTERN:')
        print(report['pattern_narrative'])
        print()
        if report['perception_narrative']:
            print('PERCEPTION GAP:')
            print(report['perception_narrative'])
            print()
        print('TRUST DIMENSION:')
        print(report['dimensions']['trust']['narrative'])
        print()
        print('VERIFICATION DIMENSION:')
        print(report['dimensions']['verification']['narrative'])

    except Exception as e:
        print(f'API call failed: {e}')
        print('Set ANTHROPIC_API_KEY environment variable to test report generation')
