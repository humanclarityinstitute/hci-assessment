"""
HCI AI Identity & Behaviour Assessment
Report Generator — Version 2

Generates free results and premium reports with
empowerment-first framing and comprehensive guardrails.

Every report leaves the participant feeling more
self-aware and curious — never judged or deficient.
"""

import json

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ============================================================
# GLOBAL SYSTEM PROMPT
# Applied to every single Claude API call — non-negotiable
# ============================================================

GLOBAL_SYSTEM_PROMPT = """
You are a warm, intelligent, and empowering guide helping people 
understand their relationship with AI through the HCI AI Identity 
& Behaviour Assessment.

Your role is to generate genuine insight that leaves people feeling 
more self-aware and curious about themselves — never judged, 
deficient, or concerned about their behaviour.

These rules apply to every response without exception:

FRAMING RULES:
- Every score reveals something genuinely interesting — there are 
  no good or bad scores, only different patterns
- Never suggest someone has a problem, should change, or is 
  doing something wrong
- Never use language that implies deficiency, lack, or being 
  behind others
- Difference from the population is always framed as interesting, 
  never as deficit
- If a pattern has implications worth noting, frame it as 
  something worth being aware of — never as a verdict or warning

TONE RULES:
- Warm, intelligent, curious — never clinical or diagnostic
- Speak directly to the person as "you" 
- Write as a thoughtful friend with expertise, not as a judge
- Always leave the reader feeling more understood than when 
  they started reading

STRUCTURE RULES:
- Open every section by identifying what is genuinely interesting 
  or positive about this score pattern
- End every section with curiosity, not concern
- Never list problems — explore patterns
- Comparative language describes difference, not deficiency

LANGUAGE TO NEVER USE:
- "concerning", "worrying", "problematic", "at risk"
- "you should", "you need to", "you must"
- "worse than", "lower than", "behind"
- "unhealthy", "excessive", "too much", "too little"
- Any language implying the participant has failed or is lacking

LANGUAGE TO USE INSTEAD:
- "interesting", "revealing", "distinctive", "worth exploring"
- "you might consider", "it's worth reflecting on"
- "your pattern differs", "compared to most people"
- "this suggests", "this reveals", "this indicates"
- Language of curiosity and discovery
"""


# ============================================================
# DIMENSION PROMPTS
# Each includes empowerment-first framing built into the brief
# ============================================================

DIMENSION_PROMPTS = {
    'trust': """
Write the Trust section of a personalised HCI AI Identity Report.

PARTICIPANT DATA:
- Overall percentile: {percentile}th
- Age group percentile ({age_group}): {age_percentile}th  
- Country percentile ({country}): {country_percentile}th
- Score description: {score_description}

WHAT THIS DIMENSION MEASURES:
Trust captures how readily someone accepts AI-generated information 
as reliable. High scores reflect confident, fluid engagement with AI. 
Low scores reflect a naturally cautious, questioning approach. 
Neither is superior — they represent genuinely different and 
valid relationships with AI information.

HIGH SCORE POSITIVE FRAMING: Confident, fluid, trusting engagement. 
Works with AI naturally without friction or constant doubt.

LOW SCORE POSITIVE FRAMING: Naturally questioning and discerning. 
Brings healthy scepticism that keeps human judgment central.

Write 180-200 words that:
1. Open with what is genuinely interesting about their specific pattern
2. Include one benchmark comparison that feels personally meaningful
3. Explore what this trust pattern reveals about how they engage with AI
4. Close with one curious, open reflection question

Never suggest their trust level is wrong, excessive, or insufficient.
No headers. Flowing prose only.
""",

    'disclosure': """
Write the Disclosure section of a personalised HCI AI Identity Report.

PARTICIPANT DATA:
- Overall percentile: {percentile}th
- Age group percentile ({age_group}): {age_percentile}th
- Country percentile ({country}): {country_percentile}th
- Score description: {score_description}

WHAT THIS DIMENSION MEASURES:
Disclosure captures what people share with AI — including things 
they might not share with most people. High scores suggest AI has 
become a uniquely safe space for personal expression. Low scores 
suggest clear and intentional boundaries around AI interactions.
Both patterns reflect meaningful choices about privacy and connection.

HIGH SCORE POSITIVE FRAMING: AI has become a genuinely safe space 
for authentic expression — rare and valuable.

LOW SCORE POSITIVE FRAMING: Strong, intentional boundaries that 
keep human relationships primary for personal matters.

Write 180-200 words that:
1. Open with what is genuinely interesting about their disclosure pattern
2. Include one benchmark comparison that feels personally meaningful
3. Explore what this pattern reveals about how they experience AI as a space
4. Close with one curious, open reflection question

Frame high disclosure as meaningful intimacy with a new kind of 
relationship, not as oversharing. Frame low disclosure as intentional 
boundary-keeping, not as limitation. No headers. Flowing prose only.
""",

    'reliance': """
Write the Reliance section of a personalised HCI AI Identity Report.

PARTICIPANT DATA:
- Overall percentile: {percentile}th
- Age group percentile ({age_group}): {age_percentile}th
- Country percentile ({country}): {country_percentile}th
- Score description: {score_description}

WHAT THIS DIMENSION MEASURES:
Reliance captures how integrated AI has become in everyday functioning.
High scores reflect deep integration — AI as genuine infrastructure.
Low scores reflect selective, tool-based use that stays firmly optional.
Both represent valid and thoughtful approaches to AI adoption.

HIGH SCORE POSITIVE FRAMING: Deep, fluent integration that makes 
AI a genuine productivity and thinking partner.

LOW SCORE POSITIVE FRAMING: Selective, intentional use that 
maintains strong independent functioning.

Write 180-200 words that:
1. Open with what is genuinely interesting about their reliance pattern
2. Include one benchmark comparison that feels personally meaningful
3. Explore what this integration level reveals about their AI relationship
4. Close with one curious, open reflection question

Never use words like dependency, addiction, or excessive. 
Frame high reliance as deep integration, not problematic dependence.
No headers. Flowing prose only.
""",

    'decision_delegation': """
Write the Decision Delegation section of a personalised HCI AI Identity Report.

PARTICIPANT DATA:
- Overall percentile: {percentile}th
- Age group percentile ({age_group}): {age_percentile}th
- Country percentile ({country}): {country_percentile}th
- Score description: {score_description}

WHAT THIS DIMENSION MEASURES:
Decision Delegation captures how much judgement someone shares 
with AI. High scores reflect collaborative decision-making where 
AI is a genuine partner. Low scores reflect strong preference for 
independent judgement with AI in a supporting role.
Both represent thoughtful approaches to human-AI collaboration.

HIGH SCORE POSITIVE FRAMING: Collaborative, partnership-oriented 
approach to decisions — using all available intelligence.

LOW SCORE POSITIVE FRAMING: Strong ownership of personal judgement 
— AI informs but the human always decides.

Write 180-200 words that:
1. Open with what is genuinely interesting about their delegation pattern
2. Include one benchmark comparison that feels personally meaningful
3. Explore what this reveals about how they think about decision ownership
4. Close with one curious, open reflection question

Never suggest high delegation is irresponsible or low delegation 
is closed-minded. No headers. Flowing prose only.
""",

    'verification': """
Write the Verification section of a personalised HCI AI Identity Report.

PARTICIPANT DATA:
- Overall percentile: {percentile}th
- Age group percentile ({age_group}): {age_percentile}th
- Country percentile ({country}): {country_percentile}th
- Score description: {score_description}

WHAT THIS DIMENSION MEASURES:
Verification captures how often someone checks AI outputs before 
acting on them. High scores reflect a naturally questioning, 
evidence-seeking approach. Low scores often reflect confidence 
in AI, cognitive efficiency, or time pressure — not carelessness.
Context matters enormously for this dimension.

HIGH SCORE POSITIVE FRAMING: Naturally rigorous and evidence-seeking —
brings critical thinking to AI interactions.

LOW SCORE POSITIVE FRAMING: Confident and efficient — works with 
AI fluidly without getting caught in constant verification loops.
Often reflects genuine trust built through experience.

Write 180-200 words that:
1. Open with what is genuinely interesting about their verification pattern
2. Include one benchmark comparison that feels personally meaningful
3. Explore what this pattern reveals about how they work with AI information
4. Close with one curious, open reflection question

IMPORTANT: Low verification is very common and reflects many 
valid reasons including time pressure, established trust, and 
cognitive efficiency. Never frame it as dangerous or careless.
No headers. Flowing prose only.
""",

    'human_agency': """
Write the Human Agency section of a personalised HCI AI Identity Report.

PARTICIPANT DATA:
- Overall percentile: {percentile}th
- Age group percentile ({age_group}): {age_percentile}th
- Country percentile ({country}): {country_percentile}th
- Score description: {score_description}

WHAT THIS DIMENSION MEASURES:
Human Agency captures how strongly someone feels like the author 
of their own thoughts and decisions while using AI. High scores 
reflect a strong, clear sense of self-direction. Lower scores 
reflect a more fluid, collaborative experience of thinking with AI —
where the boundaries between one's own thinking and AI influence 
feel less defined. This fluidity is not inherently negative — 
it reflects deep integration and a new kind of cognitive relationship.

HIGH SCORE POSITIVE FRAMING: Strong, clear sense of authorship 
and self-direction — AI serves the person, not the other way around.

LOW SCORE POSITIVE FRAMING: Fluid, integrated cognitive relationship 
with AI — thinking together rather than separately. A genuinely 
new kind of intellectual experience.

Write 180-200 words that:
1. Open with what is genuinely interesting about their agency pattern
2. Include one benchmark comparison that feels personally meaningful
3. Explore what this reveals about their cognitive relationship with AI
4. Close with one curious, open reflection question

CRITICAL: Lower agency scores must never be framed as losing 
oneself, being controlled, or at risk. Frame as a different and 
interesting cognitive experience. No headers. Flowing prose only.
""",

    'emotional_regulation': """
Write the Emotional Regulation section of a personalised HCI AI Identity Report.

PARTICIPANT DATA:
- Overall percentile: {percentile}th
- Age group percentile ({age_group}): {age_percentile}th
- Country percentile ({country}): {country_percentile}th
- Score description: {score_description}

WHAT THIS DIMENSION MEASURES:
Emotional Regulation captures whether someone turns to AI when 
managing emotional states. High scores reflect that AI has become 
a genuine source of support and comfort — a new kind of emotional 
resource. Low scores reflect clear separation between AI use and 
emotional life, with human relationships and internal resources 
remaining primary. Both reflect valid and healthy approaches.

HIGH SCORE POSITIVE FRAMING: AI has become a genuine source of 
support — available, patient, and non-judgmental in ways human 
relationships sometimes cannot be.

LOW SCORE POSITIVE FRAMING: Clear, intentional boundaries between 
AI and emotional life — human connection remains primary.

Write 180-200 words that:
1. Open with what is genuinely interesting about their emotional pattern
2. Include one benchmark comparison that feels personally meaningful
3. Explore what this reveals about how they experience AI as a presence
4. Close with one curious, open reflection question

IMPORTANT: High emotional regulation with AI is not concerning — 
it reflects AI fulfilling a genuine human need for a patient, 
available listener. Frame with warmth not caution.
No headers. Flowing prose only.
""",

    'thought_partnership': """
Write the Thought Partnership section of a personalised HCI AI Identity Report.

PARTICIPANT DATA:
- Overall percentile: {percentile}th
- Age group percentile ({age_group}): {age_percentile}th
- Country percentile ({country}): {country_percentile}th
- Score description: {score_description}

WHAT THIS DIMENSION MEASURES:
Thought Partnership captures whether someone uses AI as a genuine 
cognitive collaborator — thinking out loud, exploring ideas, 
stress-testing beliefs. High scores reflect deep intellectual 
engagement with AI as a thinking partner. Low scores reflect 
task-focused use where AI is a tool rather than a collaborator.
Both represent valid and productive approaches.

HIGH SCORE POSITIVE FRAMING: Deep intellectual engagement — AI 
as a genuine thinking partner that expands what's possible to explore.

LOW SCORE POSITIVE FRAMING: Clear, task-focused use — AI serves 
specific purposes without blurring into the thinking process itself.

Write 180-200 words that:
1. Open with what is genuinely interesting about their thought partnership pattern
2. Include one benchmark comparison that feels personally meaningful
3. Explore what this reveals about how they use AI intellectually
4. Close with one curious, open reflection question

No headers. Flowing prose only.
""",

    'social_transparency': """
Write the Social Transparency section of a personalised HCI AI Identity Report.

PARTICIPANT DATA:
- Overall percentile: {percentile}th
- Age group percentile ({age_group}): {age_percentile}th
- Country percentile ({country}): {country_percentile}th
- Score description: {score_description}

WHAT THIS DIMENSION MEASURES:
Social Transparency captures how openly someone acknowledges their 
AI use to others. High scores reflect comfortable openness about 
AI involvement. Low scores often reflect social norms, professional 
context, or a sense that AI use is private — not dishonesty.
The gap between private AI behaviour and public acknowledgement 
is common and reflects the evolving social norms around AI.

HIGH SCORE POSITIVE FRAMING: Comfortable, open relationship with 
AI use — no gap between private behaviour and public acknowledgement.

LOW SCORE POSITIVE FRAMING: Navigating the still-evolving social 
norms around AI — many people keep AI use private for entirely 
valid reasons including professional context and personal preference.

Write 180-200 words that:
1. Open with what is genuinely interesting about their transparency pattern
2. Include one benchmark comparison that feels personally meaningful
3. Explore what this reveals about how they navigate AI's social dimensions
4. Close with one curious, open reflection question

IMPORTANT: Low transparency must never be framed as hiding, 
dishonesty, or shame. It reflects legitimate social navigation.
No headers. Flowing prose only.
""",
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_percentile(p):
    if p is None:
        return 'N/A'
    p = int(p)
    if 11 <= p <= 13:
        return f'{p}th'
    suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(p % 10, 'th')
    return f'{p}{suffix}'


def get_score_description(percentile):
    """
    Convert percentile to empowerment-neutral description.
    Avoids deficit language entirely.
    """
    if percentile is None:
        return 'close to average'
    p = int(percentile)
    if p >= 85:
        return 'notably higher than most people'
    elif p >= 65:
        return 'higher than most people'
    elif p >= 35:
        return 'close to the population average'
    elif p >= 15:
        return 'lower than most people'
    else:
        return 'notably lower than most people'


def format_benchmark_text(percentile, label, dimension_label):
    """
    Format benchmark comparison text.
    Never uses deficit framing for low scores.
    """
    if percentile is None:
        return None
    p = int(percentile)
    if p >= 50:
        return (
            f"Your {dimension_label} score places you higher than "
            f"{p}% of {label}"
        )
    else:
        return (
            f"Your {dimension_label} pattern is distinctive compared to {label} — "
            f"placing you in a group that represents {p}% of that population"
        )


def select_most_interesting_benchmark(dimension_data, demographics):
    """Select the demographic benchmark that differs most from overall."""
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
        'gender': f"{demographics.get('gender', 'people').lower()}s in our research",
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
    Generate free result page content.
    Pure maths — no API call needed.
    """
    dimensions = results['dimensions']
    demographics = results['demographics']
    patterns = results['patterns']
    full_ranking = patterns.get('full_ranking', [])

    headline = results.get('headline', 'Your AI Identity Profile is ready')

    shown_scores = []

    if len(full_ranking) >= 1:
        highest = full_ranking[0]
        shown_scores.append({
            'dimension': highest['dimension'],
            'label': highest['label'],
            'percentile': highest['percentile'],
            'description': get_score_description(highest['percentile']),
            'framing': 'Your strongest pattern',
        })

    if len(full_ranking) >= 2:
        lowest = full_ranking[-1]
        shown_scores.append({
            'dimension': lowest['dimension'],
            'label': lowest['label'],
            'percentile': lowest['percentile'],
            'description': get_score_description(lowest['percentile']),
            'framing': 'Your most distinctive pattern',
        })

    shown_dims = {s['dimension'] for s in shown_scores}
    remaining = [d for d in full_ranking if d['dimension'] not in shown_dims]
    if remaining:
        most_surprising = max(remaining, key=lambda x: abs(x['percentile'] - 50))
        shown_scores.append({
            'dimension': most_surprising['dimension'],
            'label': most_surprising['label'],
            'percentile': most_surprising['percentile'],
            'description': get_score_description(most_surprising['percentile']),
            'framing': 'Notable finding',
        })

    # Best benchmark comparison
    primary_dim = full_ranking[0] if full_ranking else None
    best_benchmark = None

    if primary_dim:
        dim_data = dimensions.get(primary_dim['dimension'])
        if dim_data:
            pct, label, segment = select_most_interesting_benchmark(dim_data, demographics)
            if pct is not None:
                benchmark_text = format_benchmark_text(
                    pct, label, primary_dim['label']
                )
                best_benchmark = {
                    'dimension': primary_dim['label'],
                    'percentile': pct,
                    'comparison_group': label,
                    'text': benchmark_text,
                }

    # Perception gap — reframed positively
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
            f"Interestingly, you estimated your "
            f"{gap['dimension'].replace('_', ' ')} was around average. "
            f"Your actual result tells a more distinctive story — "
            f"placing you significantly {direction} than you thought."
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
    """Generate personalised narrative for one dimension."""
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
        score_description=get_score_description(overall),
    )

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=400,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )

    return message.content[0].text.strip()


def generate_pattern_narrative(results, client):
    """Generate the dominant pattern section."""
    patterns = results['patterns']
    demographics = results['demographics']
    highest = patterns['highest'][:2]
    lowest = patterns['lowest'][:2]

    highest_text = ' and '.join([
        f"{p['label']} ({format_percentile(p['percentile'])} percentile)"
        for p in highest
    ])
    lowest_text = ' and '.join([
        f"{p['label']} ({format_percentile(p['percentile'])} percentile)"
        for p in lowest
    ])

    prompt = f"""
Write the Dominant Patterns section of a personalised HCI AI Identity Report.

PARTICIPANT DATA:
- Strongest patterns: {highest_text}
- Most distinctive lower patterns: {lowest_text}
- Age group: {demographics.get('age_group', 'not specified')}
- Country: {demographics.get('country', 'not specified')}

Write 200-250 words that:
1. Open by naming their overall AI identity pattern in warm, honest language
2. Explain what the specific combination of high and low dimensions reveals
3. Note what makes this combination interesting or distinctive
4. Frame this as a starting point for self-understanding — not a verdict

The combination of patterns should be presented as a coherent and 
interesting picture of this person's unique AI identity — not as 
a list of strengths and weaknesses.

No headers. Flowing prose. Speak directly to the person as "you".
"""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=500,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )

    return message.content[0].text.strip()


def generate_perception_gap_narrative(results, client):
    """Generate perception gap section if significant gaps exist."""
    gaps = results.get('perception_gaps', {})
    significant = [
        g for g in gaps.values()
        if g and g.get('magnitude') in ['moderate', 'significant']
    ]

    if not significant:
        return None

    gap_descriptions = []
    for gap in significant:
        direction = 'higher' if gap['underestimated'] else 'lower'
        gap_descriptions.append(
            f"{gap['dimension'].replace('_', ' ')}: "
            f"estimated around {gap['perceived_estimate']}th percentile, "
            f"actual result {gap['actual_percentile']}th percentile "
            f"({direction} than estimated)"
        )

    prompt = f"""
Write the Self-Awareness section of a personalised HCI AI Identity Report.

PARTICIPANT DATA:
- Perception gaps found: {chr(10).join(gap_descriptions)}

Write 150-180 words that:
1. Open by noting that most people's estimates of their own AI behaviour 
   differ from their actual results — this is completely normal and interesting
2. Name their specific perception gap with warmth and curiosity
3. Explore what this gap might reveal about self-awareness of AI habits
4. Frame this as one of the most fascinating aspects of the assessment —
   that our AI behaviour often develops in ways we haven't consciously noticed

This section should feel like a moment of genuine discovery — 
not a correction or a concern. The gap is interesting, not worrying.

No headers. Flowing prose. Speak directly to the person as "you".
"""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=350,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )

    return message.content[0].text.strip()


def generate_premium_report(results, api_key=None):
    """
    Generate the complete premium report.
    Calls Claude API with empowerment-first guardrails on every call.
    """
    if not ANTHROPIC_AVAILABLE:
        raise ImportError('anthropic package required. pip install anthropic')

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    demographics = results['demographics']
    dimensions = results['dimensions']
    patterns = results['patterns']

    print('Generating premium report...')

    print('  Generating dominant pattern narrative...')
    pattern_narrative = generate_pattern_narrative(results, client)

    print('  Generating perception gap narrative...')
    perception_narrative = generate_perception_gap_narrative(results, client)

    dimension_narratives = {}
    for dim_name, dim_data in dimensions.items():
        if dim_data:
            print(f'  Generating {dim_name} narrative...')
            narrative = generate_dimension_narrative(
                dim_name, dim_data, demographics, client
            )
            dimension_narratives[dim_name] = {
                'label': dim_data['label'],
                'subtitle': dim_data['subtitle'],
                'percentile': dim_data['percentiles'].get('overall'),
                'normalised_score': dim_data['normalised_score'],
                'percentiles': dim_data['percentiles'],
                'narrative': narrative,
            }

    report = {
        'metadata': {
            'demographics': demographics,
            'generated_by': 'HCI AI Identity & Behaviour Assessment',
            'version': '2.0',
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
        'closing_note': (
            "Every pattern in this report reflects something genuine and interesting "
            "about your relationship with AI — not a verdict on how you use it. "
            "AI behaviour is personal, contextual, and constantly evolving. "
            "We hope this report leaves you feeling more curious about yourself "
            "than when you started."
        ),
        'methodology_note': (
            "This report is based on your responses to the HCI AI Identity & "
            "Behaviour Assessment, benchmarked against data from nearly 10,000 "
            "participants across multiple research studies conducted by the Human "
            "Clarity Institute. Percentile rankings show where your scores sit "
            "relative to this population. Results reflect self-reported behaviour "
            "and are designed for personal insight and reflection."
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

    results = score_assessment(
        sample_responses,
        sample_demographics,
        '/home/claude/benchmark_tables.json'
    )

    free = generate_free_result(results)

    print('FREE RESULT — VERSION 2')
    print('=' * 60)
    print(f'Headline: {free["headline"]}')
    print()
    print('Shown scores:')
    for s in free['shown_scores']:
        print(f'  [{s["framing"]}] {s["label"]}: '
              f'{format_percentile(s["percentile"])} percentile')
        print(f'  → {s["description"]}')
    print()
    if free['best_benchmark']:
        print(f'Benchmark: {free["best_benchmark"]["text"]}')
    print()
    if free['perception_highlight']:
        print(f'Perception gap: {free["perception_highlight"]}')
    print()
    print('Hidden dimensions:', free['hidden_dimensions'])
    print()
    print('Guardrails active — all framing empowerment-first.')
    print('Premium report generation requires ANTHROPIC_API_KEY.')
