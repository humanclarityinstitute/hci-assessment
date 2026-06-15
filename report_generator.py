"""
HCI AI Identity & Behaviour Assessment
Report Generator — Version 5

Generates free results and premium reports with
empowerment-first framing and comprehensive guardrails.

Premium report uses 13 focused API calls for maximum quality:
- 1 call: Most Surprising Finding + Why Most People Miss This
- 9 calls: Individual dimension profiles (one per dimension)
- 1 call: Cross-dimensional patterns
- 1 call: What Is AI Changing?
- 1 call: Profile Directions + Human Flourishing Reflection

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
# Applied to every single Claude API call
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
- High scores and low scores have equally valid human interpretations.
- All scores are patterns at this point in time — not fixed traits.

TONE RULES:
- Speak directly to the person as "you"
- Write in second person throughout
- Every section ends with curiosity, not concern
- Never list problems — explore patterns

PERCENTILE LANGUAGE:
- Always state scores as plain English first:
  "Higher than 97 out of every 100 people"
- Then percentile as supporting credential: "97th percentile"
- Never lead with the number — lead with the human meaning

LANGUAGE TO NEVER USE:
- concerning, worrying, problematic, at risk
- you should, you need to, you must
- worse than, unhealthy, excessive, too much, too little
- loss of agency, cognitive decline, addiction, dependency problem
- alarming, dangerous, at risk, red flag

LANGUAGE TO USE:
- interesting, revealing, distinctive, worth exploring
- your pattern, your positioning, your profile
- people with similar profiles tend to...
- what appears worth protecting
- raises an interesting question

USING HCI RESEARCH DATA:
- Some sections include real findings from HCI's research series, with figures.
- When you cite a population figure, attribute it lightly to HCI's research, e.g.
  "In HCI's research series, 84-99% of people verify before acting."
- Only use figures explicitly provided in the section data. NEVER invent, estimate,
  or round statistics, percentages, dataset names, or sample sizes. If no figure is
  provided, write qualitatively ("most people", "a growing minority") with no number.
- These are patterns observed across the series at one point in time — never describe
  them as changes measured within an individual over time, and never imply a
  pre-AI baseline the data does not contain.
"""


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


def plain_english_percentile(p):
    if p is None:
        return None
    p = int(p)
    if p >= 50:
        return f'Higher than {p} out of every 100 people'
    return f'Lower than {100 - p} out of every 100 people'


def get_score_description(percentile):
    if percentile is None:
        return 'near the population centre'
    p = int(percentile)
    if p >= 96:
        return 'exceptionally high — fewer than 4% score similarly'
    elif p >= 86:
        return f'notably high — only {100-p}% of participants score similarly'
    elif p >= 71:
        return 'above the population centre'
    elif p >= 41:
        return 'near the population centre'
    elif p >= 26:
        return 'below the population centre'
    elif p >= 11:
        return f'notably low — only {p}% of participants score similarly'
    else:
        return f'exceptionally low — fewer than {p+1}% score similarly'


def get_rarity_text(percentile):
    if percentile is None:
        return None
    p = int(percentile)
    if p >= 97:
        return f'Fewer than {100-p}% of participants score this high'
    elif p >= 86:
        return f'Only {100-p}% of participants score similarly'
    elif p <= 3:
        return f'Fewer than {p+1}% of participants score this low'
    elif p <= 14:
        return f'Only {p}% of participants score similarly'
    return None


def select_best_benchmark(dimension_data, demographics):
    """Select the most interesting demographic benchmark."""
    percentiles = dimension_data.get('percentiles', {})
    overall = percentiles.get('overall')
    if overall is None:
        return None, None

    best_label = 'all participants in the benchmark population'
    best_pct = overall
    max_diff = 0

    segment_labels = {
        'age_group': f"people in your age group ({demographics.get('age_group', '')})",
        'gender': f"{demographics.get('gender', 'people').lower()}s in the benchmark",
        'frequency': 'people who use AI as frequently as you',
        'country': f"people in {demographics.get('country', 'your country')}",
    }

    for segment, label in segment_labels.items():
        seg_pct = percentiles.get(segment)
        if seg_pct is not None:
            diff = abs(seg_pct - overall)
            if diff > max_diff:
                max_diff = diff
                best_pct = seg_pct
                best_label = label

    return best_pct, best_label


# ============================================================
# DIMENSION CONTEXT — what each dimension measures
# ============================================================

DIMENSION_CONTEXT = {
    'trust': {
        'label': 'Trust',
        'what_it_measures': 'how readily someone accepts AI-generated information as reliable',
        'high_framing': 'confident, fluid engagement with AI — working with it naturally without friction or constant doubt',
        'low_framing': 'naturally questioning and discerning — bringing healthy scepticism that keeps human judgement central',
        'human_anchor': 'epistemic confidence and reality orientation',
        'population_pattern': 'People with similar Trust scores tend to move faster through information tasks and report lower friction in AI-assisted work.',
    },
    'disclosure': {
        'label': 'Disclosure',
        'what_it_measures': 'what someone shares with AI, including things they might not share with most people',
        'high_framing': 'AI has become a genuinely safe space for authentic expression — rare and meaningful',
        'low_framing': 'strong, intentional boundaries that keep human relationships primary for personal matters',
        'human_anchor': 'authentic connection and identity coherence',
        'population_pattern': 'People with similar Disclosure scores tend to describe AI conversations as a private thinking space rather than a social one.',
    },
    'reliance': {
        'label': 'Reliance',
        'what_it_measures': 'how integrated AI has become in everyday functioning',
        'high_framing': 'deep, fluent integration that makes AI a genuine productivity and thinking partner',
        'low_framing': 'selective, intentional use that maintains strong independent functioning',
        'human_anchor': 'self-trust, autonomy, and independent judgement',
        'population_pattern': 'People with similar Reliance scores tend to report higher task output but also higher discomfort during AI outages.',
    },
    'decision_delegation': {
        'label': 'Decision Delegation',
        'what_it_measures': 'how much judgement someone shares with AI in decision-making',
        'high_framing': 'collaborative, partnership-oriented approach — using all available intelligence',
        'low_framing': 'strong ownership of personal judgement — AI informs but the human always decides',
        'human_anchor': 'autonomy, responsibility, and self-trust',
        'population_pattern': 'People with similar Delegation scores tend to report faster decisions but are less likely to describe those decisions as fully their own.',
    },
    'verification': {
        'label': 'Verification',
        'what_it_measures': 'how often someone checks AI outputs before acting on them',
        'high_framing': 'naturally rigorous and evidence-seeking — brings critical thinking to AI interactions',
        'low_framing': 'confident and efficient — works with AI fluidly, often reflecting genuine trust built through experience',
        'human_anchor': 'independent judgement and epistemic confidence',
        'population_pattern': 'People with similar Verification scores tend to describe a stronger sense of ownership over conclusions they reach.',
    },
    'human_agency': {
        'label': 'Human Agency',
        'what_it_measures': 'how strongly someone feels like the author of their own thoughts and decisions while using AI',
        'high_framing': 'strong, clear sense of authorship and self-direction — AI serves the person, not the other way around',
        'low_framing': 'fluid, integrated cognitive relationship with AI — thinking together rather than separately, a genuinely new kind of intellectual experience',
        'human_anchor': 'agency, autonomy, and intentionality',
        'population_pattern': 'People with similar Agency scores tend to describe AI as a tool they direct, rather than a system that directs them.',
    },
    'emotional_regulation': {
        'label': 'Emotional Regulation',
        'what_it_measures': 'whether someone turns to AI when managing emotional states',
        'high_framing': 'AI has become a genuine source of support — available, patient, and non-judgmental in ways human relationships sometimes cannot be',
        'low_framing': 'clear, intentional boundaries between AI and emotional life — human connection remains primary',
        'human_anchor': 'emotional stability and resilience',
        'population_pattern': 'People with similar Emotional Regulation scores tend to describe AI as a low-judgement space that makes it easier to process difficult feelings.',
    },
    'thought_partnership': {
        'label': 'Thought Partnership',
        'what_it_measures': 'whether someone uses AI as a genuine cognitive collaborator for thinking, exploring ideas, and stress-testing beliefs',
        'high_framing': 'deep intellectual engagement — AI as a genuine thinking partner that expands what\'s possible to explore',
        'low_framing': 'clear, task-focused use — AI serves specific purposes without blurring into the thinking process itself',
        'human_anchor': 'clarity, intentionality, and depth',
        'population_pattern': 'People with similar Thought Partnership scores tend to describe their thinking process as more externally structured than it used to be.',
    },
    'social_transparency': {
        'label': 'Social Transparency',
        'what_it_measures': 'how openly someone acknowledges their AI use to others',
        'high_framing': 'comfortable, open relationship with AI use — no gap between private behaviour and public acknowledgement',
        'low_framing': 'navigating the still-evolving social norms around AI — many people keep AI use private for entirely valid reasons',
        'human_anchor': 'authenticity and identity coherence',
        'population_pattern': 'People with low Social Transparency scores tend to report social norms around AI use as a significant factor in what they disclose.',
    },
}


# ============================================================
# HCI RESEARCH SIGNALS — sourced findings from the full series
# (21 datasets, ~10,500 participants). Injected into prompts so
# the model writes from real evidence, not placeholders.
# ============================================================

SIGNALS = {
    'dimensions': {
        'trust': {
            'series': "In HCI's series, trust in AI is conditional and built through use: 0% of never-users trust AI for accuracy versus 55% of daily users, yet 77% distrust big tech on AI — trust and scrutiny coexist.",
            'high': "Higher trust usually reflects a working relationship built through experience rather than blind faith.",
            'low': "Lower trust reflects the near-universal stance of active scrutiny; most people treat AI claims as something to weigh, not accept.",
        },
        'disclosure': {
            'series': "In HCI's series, what people share with AI is shaped by stigma and norms: 28% report stigma around workplace AI use, undisclosed AI use triggers a strong betrayal response, and emotional disclosure to AI is emerging.",
            'high': "Higher disclosure can reflect AI becoming a genuinely private thinking or expressive space — uncommon and meaningful.",
            'low': "Lower disclosure reflects intentional boundaries that keep human relationships primary for personal matters.",
        },
        'reliance': {
            'series': "In HCI's series, reliance accumulates with exposure (decision reliance rises from 1.1 to 4.4 from never- to everyday-users) and increases under difficulty (58% of daily users rely on AI when things are hard). Crucially, reliance with a felt sense of control is associated with higher wellbeing than reliance without it — agency over use matters more than how much you use.",
            'high': "Higher reliance reflects deep integration; what most shapes outcomes is whether use feels controlled, not the amount.",
            'low': "Lower reliance reflects selective, intentional use and strong independent functioning.",
        },
        'decision_delegation': {
            'series': "In HCI's series, delegation is selective: 91% retain personal responsibility for their decisions, delegation rises as stakes fall and under overwhelm, and only 2-3% would accept an AI decision with no intervention at all.",
            'high': "Higher delegation reflects a collaborative approach; even high delegators overwhelmingly retain ultimate responsibility.",
            'low': "Lower delegation reflects strong ownership of judgement — AI informs, the person decides.",
        },
        'verification': {
            'series': "In HCI's series, verification is near-universal (84-99% check before acting) but cognitively costly (43% say it drains focus) and beginning to be rationed under load — 54% now verify only selectively and 50-54% find constant questioning exhausting.",
            'high': "Higher verification reflects rigorous, evidence-seeking engagement and a stronger sense of ownership over conclusions.",
            'low': "Lower verification often reflects efficiency and trust built through experience, in a context where verification is becoming genuinely tiring for many.",
        },
        'human_agency': {
            'series': "In HCI's series, agency is intact at the identity level (91% retain responsibility, 88% feel able to override AI) but under pressure at the process level — 59% feel subtly steered toward certain choices, and drift happens through convenience rather than choice.",
            'high': "Higher agency reflects a clear sense of authorship — directing AI rather than being directed.",
            'low': "Lower agency reflects a more fluid, integrated relationship with AI; override capability and felt steering can coexist.",
        },
        'emotional_regulation': {
            'series': "In HCI's series, 18% now use AI for emotional support (confirmed across two datasets) and reliance rises under emotional difficulty — yet 87% still believe only humans can truly meet emotional needs, the most live tension in the data.",
            'high': "Higher scores reflect AI becoming a genuine low-judgement space for processing difficult feelings.",
            'low': "Lower scores reflect clear boundaries that keep human connection primary for emotional life.",
        },
        'thought_partnership': {
            'series': "In HCI's series, AI works best as a clarifier rather than a replacer; 34-38% question whether AI-assisted decisions are genuinely their own, and a clear values anchor is what separates genuine partnership from outsourced thinking.",
            'high': "Higher scores reflect deep intellectual engagement — AI expanding what is possible to explore.",
            'low': "Lower scores reflect task-focused use that keeps the thinking process itself one's own.",
        },
        'social_transparency': {
            'series': "In HCI's series, honesty and transparency are the top two things people demand of AI; AI-use disclosure is shaped by stigma (28%) and evolving norms, and 50% self-censor under surveillance awareness.",
            'high': "Higher transparency reflects no gap between private behaviour and public acknowledgement of AI use.",
            'low': "Lower transparency reflects navigating still-evolving social norms — many keep AI use private for valid reasons.",
        },
    },
    'trends': [
        "Reliance and decision-support use rise steeply with exposure (decision reliance 1.1 to 4.4 from never- to everyday-users) — the clearest gradient in the series.",
        "Trust in AI rises with familiarity (0% of never-users trust AI for accuracy versus 55% of daily users).",
        "Verification stays near-universal but is beginning to be rationed under cognitive load (54% now verify selectively; 50-54% report fatigue).",
        "Agency holds at the identity level (91% retain responsibility; 88% feel able to override AI) even as 59% report feeling subtly steered.",
        "AI is entering emotional regulation (18% use it for emotional support).",
        "Where behaviour shifts, it shifts through convenience and repetition rather than deliberate choice.",
    ],
    'tensions': [
        "Identity holds; the infrastructure that sustains it (attention, reflection, values-enactment) is under pressure.",
        "People hold their values clearly (78-96%) but living them is getting harder — environmental friction, not moral confusion.",
        "Override capability (88%) and felt steering (59%) coexist — influence operates below the threshold at which people choose to intervene.",
        "Verification is universal yet exhausting; a growing minority ration it.",
        "87% believe only humans can truly meet emotional needs, yet 27% already get some emotional support from AI.",
        "Reliance with control is associated with better outcomes than reliance without — agency over use is the key variable.",
    ],
    'human_reference': [
        "Self-authorship — feeling like the active agent shaping your own direction — appears foundational to human stability.",
        "Attention functions as infrastructure for coherent functioning, not just focus; when it degrades, the capacity to act on values degrades with it.",
        "Values clarity is the most stable human signal in the series (78-96%) and works as a behavioural anchor that resists drift.",
        "Living congruently with your values — not just holding them — is what stabilises; the gap between values held and values lived is the thing worth watching.",
        "Self-trust behaves like an internal orientation mechanism; retaining your own decision authority is protective.",
        "Reliance paired with a felt sense of control is associated with higher wellbeing than reliance without it.",
    ],
    'cohorts': {
        'young': "the highest-pressure, leading-edge cohort — carrying the highest cognitive and emotional load, but capable of the best outcomes when use feels controlled and values-aligned",
        'resilient': "the most resourced cohort — highest values clarity, strongest control over AI use, fastest attention recovery",
        'integrator': "the most practically AI-integrated cohort — highest decision reliance and lowest felt independence without AI, alongside a stable work identity",
        'wary': "the most vigilant cohort — the most diligent verifiers and most self-directed decision-makers, though least confident at detecting AI-generated content",
    },
}

_COHORT_BY_AGE = {
    '18 - 24': 'young', '25 - 34': 'young',
    '35 - 44': 'resilient',
    '45 - 54': 'integrator',
    '55 - 65': 'wary', 'Over 65': 'wary',
}

def dimension_signal(dim_name):
    return SIGNALS['dimensions'].get(dim_name, {})

def cohort_signal(age_group):
    key = _COHORT_BY_AGE.get((age_group or '').strip())
    return SIGNALS['cohorts'].get(key) if key else None


# ============================================================
# CALL 1: MOST SURPRISING FINDING + WHY MOST PEOPLE MISS THIS
# ============================================================

def generate_opening(results, client):
    """
    Generate the opening section — Most Surprising Finding and
    Why Most People Miss This. This is what the participant
    remembers most. Must be specific, grounded, memorable.
    """
    demographics = results['demographics']
    perception_gaps = results.get('perception_gaps', {})
    patterns = results['patterns']
    variable_highlights = results.get('variable_highlights', [])

    # Find most significant perception gap
    significant_gaps = [
        g for g in perception_gaps.values()
        if g and g.get('magnitude') in ['significant', 'moderate']
    ]
    significant_gaps.sort(key=lambda x: x.get('abs_gap', 0), reverse=True)

    # Find most extreme dimension
    full_ranking = patterns.get('full_ranking', [])
    most_extreme = max(full_ranking, key=lambda x: abs(x['percentile'] - 50)) if full_ranking else None

    # Find most distinctive variable highlight
    personalised_var = next((h for h in variable_highlights if h['type'] == 'personalised'), None)

    gap_text = ''
    if significant_gaps:
        gap = significant_gaps[0]
        direction = 'higher' if gap['underestimated'] else 'lower'
        gap_text = (
            f"Perception gap found: participant estimated their "
            f"{gap['dimension'].replace('_', ' ')} was around average "
            f"(~{gap['perceived_estimate']}th percentile). "
            f"Actual result: {gap['actual_percentile']}th percentile — "
            f"significantly {direction} than estimated."
        )

    extreme_text = ''
    if most_extreme:
        extreme_text = (
            f"Most extreme dimension: {most_extreme['label']} at "
            f"{format_percentile(most_extreme['percentile'])} percentile overall"
        )

    var_text = ''
    if personalised_var:
        var_text = (
            f"Most distinctive individual response: \"{personalised_var['question_text']}\" "
            f"— participant answered {personalised_var['raw_response']}/7, "
            f"placing them at the {format_percentile(personalised_var['percentiles']['overall'])} "
            f"percentile overall"
        )

    prompt = f"""Write the opening section of a personalised HCI AI Identity & Behaviour Report.

PARTICIPANT DATA:
{gap_text}
{extreme_text}
{var_text}
Age group: {demographics.get('age_group', 'not specified')}
Country: {demographics.get('country', 'not specified')}

This section has TWO parts:

PART 1 — MOST SURPRISING FINDING (~80 words)
The single most striking finding from this participant's profile.
Priority order: perception gap first, then extreme variable, then extreme dimension.
Make it specific — name the actual dimension or question.
State the finding clearly in plain English — no percentile jargon.
This should feel like: "Wait — that's genuinely surprising."
Do NOT start with "Your" — vary the opening.

PART 2 — WHY MOST PEOPLE MISS THIS (~80 words)
Immediately after the finding, one paragraph explaining why this gap
or pattern is so common — grounded in population-level observation.
This makes the finding feel legitimate and researched rather than random.
Start this paragraph with: "Why most people don't see this:"
Frame as population-level observation, never as individual correction.
End with the finding feeling more interesting, not more alarming.

No headers. Write Part 1 then Part 2 as connected prose.
Speak directly to the person as "you".
Warm, precise, intellectually curious tone throughout."""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=600,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text.strip()


# ============================================================
# CALLS 2-10: INDIVIDUAL DIMENSION PROFILES
# ============================================================

def generate_dimension_profile(dim_name, dim_data, demographics,
                                variable_highlights, client):
    """
    Generate a full personalised profile for one dimension.
    Includes: plain English score, demographic comparisons,
    rarity framing, narrative, population pattern, and
    any relevant variable-level highlight.
    """
    ctx = DIMENSION_CONTEXT.get(dim_name, {})
    sig = dimension_signal(dim_name)
    percentiles = dim_data.get('percentiles', {})
    overall = percentiles.get('overall', 50)
    age_pct = percentiles.get('age_group')
    gender_pct = percentiles.get('gender')
    freq_pct = percentiles.get('frequency')

    # Build demographic comparison text
    demo_comparisons = []
    if age_pct is not None:
        demo_comparisons.append(
            f"Among people in your age group ({demographics.get('age_group', '')}): "
            f"{format_percentile(age_pct)} percentile "
            f"({plain_english_percentile(age_pct)})"
        )
    if freq_pct is not None:
        demo_comparisons.append(
            f"Among people who use AI as frequently as you: "
            f"{format_percentile(freq_pct)} percentile "
            f"({plain_english_percentile(freq_pct)})"
        )
    if gender_pct is not None:
        demo_comparisons.append(
            f"Among {demographics.get('gender', 'people').lower()}s: "
            f"{format_percentile(gender_pct)} percentile"
        )

    # Find relevant variable highlight for this dimension
    dim_var = next(
        (h for h in variable_highlights
         if h['dimension'] == dim_name and h['type'] == 'personalised'),
        None
    )

    var_text = ''
    if dim_var:
        var_text = (
            f"\nMost distinctive individual response in this dimension:\n"
            f"Question: \"{dim_var['question_text']}\"\n"
            f"Participant answered: {dim_var['raw_response']}/7\n"
            f"Overall percentile for this specific response: "
            f"{format_percentile(dim_var['percentiles']['overall'])}\n"
            f"Age group percentile: "
            f"{format_percentile(dim_var['percentiles'].get('age_group'))}"
        )

    rarity = get_rarity_text(overall)

    prompt = f"""Write the {ctx.get('label', dim_name)} dimension profile for a personalised HCI AI Identity Report.

PARTICIPANT DATA:
Overall percentile: {format_percentile(overall)} ({plain_english_percentile(overall)})
Score description: {get_score_description(overall)}
{f"Rarity: {rarity}" if rarity else ""}

DEMOGRAPHIC COMPARISONS:
{chr(10).join(demo_comparisons) if demo_comparisons else "No demographic breakdowns available"}
{var_text}

WHAT THIS DIMENSION MEASURES:
{ctx.get('what_it_measures', '')}

FRAMING FOR THIS SCORE LEVEL:
{"High score framing: " + ctx.get('high_framing', '') if overall >= 50 else "Low score framing: " + ctx.get('low_framing', '')}

HUMAN FOUNDATIONS ANCHOR:
{ctx.get('human_anchor', '')}

POPULATION PATTERN (Why It Matters):
{ctx.get('population_pattern', '')}

HCI RESEARCH SIGNAL FOR THIS DIMENSION (real finding — use it, cite lightly as "in HCI's research..."):
{sig.get('series', '')}
{(sig.get('high') if overall >= 50 else sig.get('low')) or ''}

Write 160-200 words that:
1. Open with what is genuinely interesting about their specific pattern
   — make it personal, not generic
2. Include the most striking demographic comparison naturally in the text
   (e.g. "Among people your age, this places you...")
3. If there is a notable variable-level finding, reference it specifically
   — name the actual question behaviour, not the question itself
4. Weave in the HCI research signal naturally — include its figure with light sourcing (e.g. "in HCI's research, 84-99% of people...")
5. Close with one curious, open reflection — not a recommendation

IMPORTANT:
- If overall and age group percentiles differ significantly, note both
  — this contrast is often the most interesting finding
- Never frame any score as a problem or something to fix
- Write as flowing prose, no headers, no bullet points
- Speak directly as "you" throughout"""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=450,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text.strip()


# ============================================================
# CALL 11: CROSS-DIMENSIONAL PATTERNS
# ============================================================

RARE_COMBINATIONS = [
    ('reliance', 'human_agency', 'high', 'high',
     'High Reliance + High Agency — in HCI\'s series, reliance with a felt sense of control is the combination associated with the best outcomes (higher wellbeing than both non-users and uncontrolled users). Deep integration alongside retained authorship is the healthiest version of heavy use, and a distinctive one.'),
    ('trust', 'verification', 'high', 'high',
     'High Trust + High Verification — confident but disciplined: trusts AI yet still cross-checks. Notable because 50-54% of people now find constant verification exhausting, so sustaining both at once is uncommon.'),
    ('disclosure', 'emotional_regulation', 'high', 'low',
     'High Disclosure + Low Emotional Regulation — opens up to AI but keeps emotional dependence low; distinctive against the series trend where 18% now lean on AI for emotional support.'),
    ('thought_partnership', 'decision_delegation', 'high', 'low',
     'High Thought Partnership + Low Decision Delegation — thinks extensively with AI but keeps decisions firmly their own; in the series 34-38% are unsure their AI-assisted decisions are truly theirs, so retaining clear ownership while thinking with AI stands out.'),
    ('reliance', 'verification', 'high', 'high',
     'High Reliance + High Verification — deeply integrated yet consistently cross-checks, against a backdrop where verification is being rationed under load (54% now verify selectively).'),
    ('social_transparency', 'thought_partnership', 'low', 'high',
     'Low Social Transparency + High Thought Partnership — uses AI heavily as a thinking partner but keeps the extent private; fits the series finding that AI-use disclosure is suppressed by stigma (28%).'),
]


def find_rare_combinations(dimension_results):
    """Identify any rare cross-dimensional combinations."""
    found = []
    for dim_a, dim_b, level_a, level_b, description in RARE_COMBINATIONS:
        pct_a = dimension_results.get(dim_a, {})
        pct_b = dimension_results.get(dim_b, {})
        if not pct_a or not pct_b:
            continue
        a = pct_a.get('percentiles', {}).get('overall', 50)
        b = pct_b.get('percentiles', {}).get('overall', 50)
        a_matches = (level_a == 'high' and a >= 65) or (level_a == 'low' and a <= 35)
        b_matches = (level_b == 'high' and b >= 65) or (level_b == 'low' and b <= 35)
        if a_matches and b_matches:
            found.append({
                'dim_a': dim_a, 'dim_b': dim_b,
                'pct_a': a, 'pct_b': b,
                'description': description,
            })
    return found


def generate_cross_dimensional(results, client):
    """Generate cross-dimensional patterns section."""
    patterns = results['patterns']
    dimensions = results['dimensions']
    full_ranking = patterns.get('full_ranking', [])

    # Find rare combinations
    rare = find_rare_combinations(dimensions)

    # Find biggest gap between any two dimensions
    if len(full_ranking) >= 2:
        highest = full_ranking[0]
        lowest = full_ranking[-1]
        gap = highest['percentile'] - lowest['percentile']
    else:
        highest = lowest = None
        gap = 0

    # Build all dimension summary
    dim_summary = '\n'.join([
        f"  {d['label']}: {format_percentile(d['percentile'])} percentile"
        for d in full_ranking
    ])

    tensions_text = 'HCI SERIES TENSIONS (grounding — cite any figures lightly):\n' + '\n'.join('  - ' + t for t in SIGNALS['tensions'])

    rare_text = ''
    if rare:
        rare_text = 'RARE COMBINATIONS DETECTED:\n' + '\n'.join([
            f"  - {r['description']} "
            f"(This participant: {format_percentile(r['pct_a'])} and {format_percentile(r['pct_b'])})"
            for r in rare
        ])

    prompt = f"""Write the Cross-Dimensional Patterns section of a personalised HCI AI Identity Report.

ALL NINE DIMENSION SCORES:
{dim_summary}

{rare_text}

{tensions_text}

BIGGEST CONTRAST:
{f"Highest: {highest['label']} at {format_percentile(highest['percentile'])} percentile" if highest else ""}
{f"Lowest: {lowest['label']} at {format_percentile(lowest['percentile'])} percentile" if lowest else ""}
{f"Gap between highest and lowest: {round(gap)}th percentile points" if gap else ""}

Write 200-250 words that:
1. Open by describing the overall shape of this profile — what kind
   of AI user does this combination of scores suggest?
2. Identify 2-3 specific dimensional relationships that are interesting
   — how do the scores relate to and illuminate each other?
3. If any rare combinations exist, describe what makes them unusual
   and why the combination is interesting
4. Note the biggest contrast in the profile — what does it reveal
   that individual scores alone wouldn't show?
5. Close with a genuine observation about what this pattern suggests
   about this person's relationship with AI — end with curiosity

This section should feel like the report is seeing the whole person,
not just individual scores. The combination tells a story.

No headers. Flowing prose. Speak directly as "you"."""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=550,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text.strip()


# ============================================================
# CALL 12: WHAT IS AI CHANGING?
# ============================================================

def generate_what_is_changing(results, client):
    """
    Generate the 'What Is AI Changing?' section.
    This is the most important section — answers the deepest question
    the participant carries. Must be specific to their profile.
    Population-grounded throughout. Never predictive or prescriptive.
    """
    demographics = results['demographics']
    dimensions = results['dimensions']
    patterns = results['patterns']
    full_ranking = patterns.get('full_ranking', [])

    # Identify dimensions showing strongest alignment with observed changes
    high_dims = [d for d in full_ranking if d['percentile'] >= 65]
    low_dims = [d for d in full_ranking if d['percentile'] <= 35]

    dim_summary = '\n'.join([
        f"  {d['label']}: {format_percentile(d['percentile'])} percentile"
        for d in full_ranking
    ])

    trends_text = '\n'.join('  - ' + t for t in SIGNALS['trends'])

    prompt = f"""Write the "What Is AI Changing?" section of a personalised HCI AI Identity Report.

This is the most important section of the premium report. It speaks to the
question the participant has carried since they started: how do AI use and
their behaviour relate — and where does their own profile sit within that?

PARTICIPANT PROFILE:
{dim_summary}

Age group: {demographics.get('age_group', 'not specified')}
AI usage frequency: {demographics.get('ai_tool_use_frequency', 'not specified')}

DIMENSIONS SHOWING STRONG PATTERNS:
High: {', '.join([d['label'] for d in high_dims]) if high_dims else 'None notably high'}
Low: {', '.join([d['label'] for d in low_dims]) if low_dims else 'None notably low'}

HCI SERIES PATTERNS (real findings — use the figures, cite lightly. These are
patterns observed ACROSS the series at one point in time, NOT changes measured
inside a person over time, and there is NO pre-AI baseline to compare against):
{trends_text}

Write 220-260 words, woven as connected prose, that:

1. Connect 2-3 of this person's actual dimensions to the relevant HCI series
   patterns above — name their dimensions and include a real figure with light
   sourcing ("in HCI's research, reliance rises from 1.1 to 4.4 with use...").

2. Note where their profile sits within those patterns — more or less pronounced
   than the typical position. Describe position, never prediction.

3. Identify which human capacities look most active and most preserved here.

4. Note what people with similar profiles tend to describe — as observation,
   never forecast.

CRITICAL RULES:
- Use ONLY the figures provided above; never invent statistics or a pre-AI baseline.
- Never predict what will happen to this person; describe observed patterns only.
- Never frame anything as change measured inside this individual over time.
- Never alarm — illuminating, not warning. End with curiosity.
- Speak directly as "you" throughout"""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=600,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text.strip()


# ============================================================
# CALL 13: PROFILE DIRECTIONS + HUMAN FLOURISHING REFLECTION
# ============================================================

def generate_closing(results, client):
    """
    Generate the closing two sections:
    1. Profile Directions — non-prescriptive, curiosity-forward
    2. Human Flourishing Reflection — the most distinctive section
       in any AI assessment anywhere

    Combined into one call for coherence — these two sections
    need to flow naturally into each other.
    """
    demographics = results['demographics']
    patterns = results['patterns']
    dimensions = results['dimensions']
    full_ranking = patterns.get('full_ranking', [])

    dim_summary = '\n'.join([
        f"  {d['label']}: {format_percentile(d['percentile'])} percentile"
        for d in full_ranking
    ])

    highest = full_ranking[0] if full_ranking else None
    lowest = full_ranking[-1] if full_ranking else None
    cohort = cohort_signal(demographics.get('age_group'))
    human_ref_text = '\n'.join('  - ' + h for h in SIGNALS['human_reference'])

    prompt = f"""Write the final two sections of a personalised HCI AI Identity Report.

PARTICIPANT PROFILE:
{dim_summary}

Highest dimension: {highest['label'] + ' at ' + format_percentile(highest['percentile']) + ' percentile' if highest else 'N/A'}
Lowest dimension: {lowest['label'] + ' at ' + format_percentile(lowest['percentile']) + ' percentile' if lowest else 'N/A'}
Age group: {demographics.get('age_group', 'not specified')}
{f"Cohort context — people in this age group are {cohort}." if cohort else ""}

HCI HUMAN REFERENCE LAYER (grounding for what is worth protecting; cite any figures lightly):
{human_ref_text}

Write TWO distinct sections:

═══════════════════════════════════
SECTION A: PROFILE DIRECTIONS (~150 words)
═══════════════════════════════════

Three elements — each 2-3 sentences. Non-prescriptive throughout.
Never say "you should" or "you need to" — only observation and curiosity.

STRENGTH:
What does this profile suggest is working well?
Ground in population data: "People with similar profiles tend to..."
Name the specific capacity this reflects.

ONE PATTERN WORTH NOTICING:
One dimensional combination worth being aware of.
Not a warning — an interesting observation.
"One pattern worth noticing in your profile..."

WHAT OTHERS WITH THIS PROFILE OFTEN EXPLORE:
What do people with similar profiles find interesting to pay attention to?
Frame as observation, never instruction.
"People with profiles like yours often find it interesting to notice..."

═══════════════════════════════════
SECTION B: HUMAN FLOURISHING REFLECTION (~180 words)
═══════════════════════════════════

This is the most important closing section HCI produces.
It is unlike anything in any other AI assessment.
It does not evaluate. It observes. It asks what appears worth protecting.

Answer these four questions woven as connected prose:

1. What human strengths does this profile suggest are currently active?
   Name them specifically — grounded in actual dimension scores.

2. What capacities appear well-preserved in how this person relates to AI?
   What does the data suggest remains strongly intact?

3. What does this profile suggest is most worth protecting going forward?
   Frame as observation: "What appears most worth protecting here is..."
   Never as prescription: never "you should protect..."

4. What does this profile suggest about how AI may be shaping this
   person's experience over time?
   Population-grounded. Open. Never alarming. End with genuine curiosity.

CRITICAL: Section B must end with a sentence that leaves the participant
feeling more curious about themselves than when they started reading.
This is the last thing they read. Make it count.

Write Section A then Section B. Use clear section headers:
"Profile Directions" and "Human Flourishing Reflection"
Then flowing prose within each. Speak as "you" throughout."""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=800,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text.strip()


# ============================================================
# GUARDRAIL PROMPTS — paste-in prompts that hold AI in the
# role the person wants. Curated library, selected by profile.
# Deterministic (no API call): the prompt text is never model-
# generated, so it can't drift or hallucinate.
# ============================================================

GUARDRAIL_PROMPTS = [
    {
        'dim': 'verification', 'direction': 'low', 'universal': False,
        'title': 'Make AI show its work',
        'protects': 'your verification and independent judgement',
        'prompt': "When you give me facts, statistics, or recommendations, tell me how confident you are and mark what you're inferring versus what you actually know. Flag explicitly when something is worth my checking elsewhere — don't smooth over uncertainty to sound helpful.",
        'when': 'Set it as a standing instruction in any AI you rely on for information.',
    },
    {
        'dim': 'decision_delegation', 'direction': 'high', 'universal': True,
        'title': 'Options, not answers',
        'protects': 'your ownership of decisions',
        'prompt': "When I ask you to decide for me, don't. Lay out the realistic options with the strongest case for and against each, ask me the one question most likely to change my mind, then let me make the call.",
        'when': "Use it whenever you catch yourself asking AI to just tell you what to do.",
    },
    {
        'dim': 'human_agency', 'direction': 'low', 'universal': False,
        'title': 'Make me think first',
        'protects': 'your sense of authorship',
        'prompt': "Before you give me your answer, ask me what I think and why. Push back on my reasoning, point out what I might be missing, and have me commit to a view before you offer yours.",
        'when': 'Use it on anything where the thinking matters as much as the answer.',
    },
    {
        'dim': 'reliance', 'direction': 'high', 'universal': False,
        'title': 'Do it with me, not for me',
        'protects': 'your independent functioning',
        'prompt': "When you help me with a task, show your working and explain the key choices as you go, so I could do it myself next time — don't just hand me the finished result.",
        'when': "Use it on the tasks you'd least want to lose the ability to do yourself.",
    },
    {
        'dim': 'trust', 'direction': 'high', 'universal': True,
        'title': 'Flag your uncertainty',
        'protects': 'your epistemic calibration',
        'prompt': "Whenever you're speculating, generalising, or unsure, say so plainly. I'd rather you tell me you're not certain than give me a confident answer that turns out to be wrong.",
        'when': 'Keep it on by default — it costs nothing and catches a lot.',
    },
    {
        'dim': 'thought_partnership', 'direction': 'high', 'universal': False,
        'title': "Challenge, don't replace",
        'protects': 'your own thinking',
        'prompt': "Act as a thinking partner, not a ghostwriter. Help me sharpen my own ideas — ask questions, find the holes, offer counterpoints — but let the conclusions be mine.",
        'when': "Use it when you're thinking something through, not just producing output.",
    },
    {
        'dim': 'emotional_regulation', 'direction': 'high', 'universal': False,
        'title': 'Point me back to people',
        'protects': 'your human connection',
        'prompt': "If I'm using you to work through something difficult, help me — and gently remind me to bring the things that matter most to the people in my life, not only to you.",
        'when': 'Use it if AI has become a first port of call for hard moments.',
    },
]


def select_guardrails(dimensions, max_n=4):
    """Pick the guardrail prompts that best fit this profile.

    A rule fires when the person leans into AI on that dimension
    (high >= 65, or low <= 35). The most pronounced leans come first.
    Always returns at least two — falling back to broadly useful ones.
    """
    scored = []
    for r in GUARDRAIL_PROMPTS:
        d = dimensions.get(r['dim'], {})
        pct = d.get('percentiles', {}).get('overall')
        if pct is None:
            continue
        if r['direction'] == 'high' and pct >= 65:
            scored.append((pct - 50, r))
        elif r['direction'] == 'low' and pct <= 35:
            scored.append((50 - pct, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    chosen = [r for _, r in scored[:max_n]]
    if len(chosen) < 2:
        for r in GUARDRAIL_PROMPTS:
            if r.get('universal') and r not in chosen:
                chosen.append(r)
            if len(chosen) >= 2:
                break
    return [
        {'title': r['title'], 'protects': r['protects'],
         'prompt': r['prompt'], 'when': r['when']}
        for r in chosen
    ]


# ============================================================
# VALIDATION PROTOCOL — let the person check this report against
# how they actually use AI, in their own assistant. Deterministic.
# ============================================================

def build_validation_protocol():
    return {
        'title': 'Validate this report against how you actually use AI',
        'intro': (
            "Most assessments stop at what you say about yourself. This one you can "
            "check. The AI you use most has seen how you actually ask, decide, verify, "
            "and reach for help — so you can hold this report up against your real "
            "behaviour and see where it lands."
        ),
        'steps': [
            'Open the AI you use most.',
            'Paste or upload this full report into it.',
            'Send the prompt below and read what it tells you.',
        ],
        'prompt': (
            "Here is a personalised assessment of how I use AI. Based on how I actually "
            "work with you — across our past conversations if you can see them, and how "
            "I'm interacting with you right now — how accurate is each part of this? Where "
            "do you see clear evidence for or against it? Be specific, and don't just agree "
            "with me."
        ),
        'note': (
            "It works richest with an assistant that remembers your history; otherwise it "
            "will reflect on your current conversation. You run this in your own AI — "
            "nothing comes back to us, and we never see your conversations."
        ),
    }


# ============================================================
# FREE RESULT GENERATOR (unchanged)
# ============================================================

def generate_free_result(results):
    """Generate free result page content. Pure maths — no API call."""
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
            pct, label = select_best_benchmark(dim_data, demographics)
            if pct is not None:
                if pct >= 50:
                    benchmark_text = (
                        f"Your {primary_dim['label']} score places you higher than "
                        f"{int(pct)}% of {label}"
                    )
                else:
                    benchmark_text = (
                        f"Your {primary_dim['label']} pattern is distinctive compared "
                        f"to {label} — placing you in a group that represents "
                        f"{int(pct)}% of that population"
                    )
                best_benchmark = {
                    'dimension': primary_dim['label'],
                    'percentile': pct,
                    'comparison_group': label,
                    'text': benchmark_text,
                }

    # Perception gap
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
# PREMIUM REPORT GENERATOR — 13 FOCUSED API CALLS
# ============================================================

def generate_premium_report(results, api_key=None, progress_callback=None):
    """
    Generate the complete premium report using 13 focused API calls.

    progress_callback: optional function(step, total, message) for
    streaming progress updates to the frontend.
    """
    if not ANTHROPIC_AVAILABLE:
        raise ImportError('anthropic package required. pip install anthropic')

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    demographics = results['demographics']
    dimensions = results['dimensions']
    patterns = results['patterns']
    variable_highlights = results.get('variable_highlights', [])

    total_steps = 13
    step = 0

    def progress(message):
        nonlocal step
        step += 1
        print(f'  [{step}/{total_steps}] {message}')
        if progress_callback:
            progress_callback(step, total_steps, message)

    print('Generating premium report — 13 focused calls...')

    # ── Call 1: Opening ──────────────────────────────────────────────────────
    progress('Identifying your most surprising finding...')
    opening = generate_opening(results, client)

    # ── Calls 2-10: Nine dimension profiles ──────────────────────────────────
    dimension_profiles = {}
    dim_order = [
        'reliance', 'trust', 'verification', 'decision_delegation',
        'human_agency', 'disclosure', 'emotional_regulation',
        'thought_partnership', 'social_transparency'
    ]

    dim_labels = {
        'reliance': 'Reliance', 'trust': 'Trust',
        'verification': 'Verification', 'decision_delegation': 'Decision Delegation',
        'human_agency': 'Human Agency', 'disclosure': 'Disclosure',
        'emotional_regulation': 'Emotional Regulation',
        'thought_partnership': 'Thought Partnership',
        'social_transparency': 'Social Transparency',
    }

    for dim_name in dim_order:
        dim_data = dimensions.get(dim_name)
        if dim_data:
            progress(f'Writing your {dim_labels.get(dim_name, dim_name)} profile...')
            narrative = generate_dimension_profile(
                dim_name, dim_data, demographics, variable_highlights, client
            )
            dimension_profiles[dim_name] = {
                'label': dim_data['label'],
                'subtitle': dim_data.get('subtitle', ''),
                'percentile': dim_data['percentiles'].get('overall'),
                'age_percentile': dim_data['percentiles'].get('age_group'),
                'normalised_score': dim_data['normalised_score'],
                'percentiles': dim_data['percentiles'],
                'narrative': narrative,
                'plain_english': plain_english_percentile(
                    dim_data['percentiles'].get('overall')
                ),
                'rarity': get_rarity_text(dim_data['percentiles'].get('overall')),
            }

    # ── Call 11: Cross-dimensional patterns ──────────────────────────────────
    progress('Analysing cross-dimensional patterns...')
    cross_dimensional = generate_cross_dimensional(results, client)

    # ── Call 12: What Is AI Changing? ────────────────────────────────────────
    progress('Writing What Is AI Changing section...')
    what_is_changing = generate_what_is_changing(results, client)

    # ── Call 13: Profile Directions + Human Flourishing ──────────────────────
    progress('Writing your Human Flourishing Reflection...')
    closing = generate_closing(results, client)

    # ── Guardrail prompts + validation protocol (deterministic, no API) ───────
    print('  [+] Selecting your guardrail prompts...')
    guardrails = select_guardrails(dimensions)
    validation = build_validation_protocol()

    # ── Assemble report ──────────────────────────────────────────────────────
    report = {
        'metadata': {
            'demographics': demographics,
            'generated_by': 'HCI AI Identity & Behaviour Assessment',
            'version': '5.0',
            'total_api_calls': 13,
        },
        'headline': results.get('headline'),
        'opening': opening,
        'dimension_profiles': dimension_profiles,
        'dimension_ranking': patterns.get('full_ranking', []),
        'cross_dimensional': cross_dimensional,
        'what_is_changing': what_is_changing,
        'closing': closing,
        'guardrail_prompts': guardrails,
        'validation_protocol': validation,
        'variable_highlights': variable_highlights,
        'perception_gaps': results.get('perception_gaps', {}),
        'methodology_note': (
            "This report is based on your responses to the HCI AI Identity & "
            "Behaviour Assessment — a research-based behavioural instrument "
            "benchmarked against data drawn from more than 10,000 participants "
            "across multiple studies conducted by the Human Clarity Institute. "
            "Scores represent your positioning within the benchmark population. "
            "They describe patterns, not traits. They reflect how you responded "
            "at this point in time and may change as your relationship with AI "
            "evolves. This assessment is designed for personal insight and "
            "reflection. It is not a clinical instrument and should not be used "
            "for diagnosis, professional evaluation, or any purpose beyond "
            "individual self-understanding. Benchmark data and methodology are "
            "publicly available at github.com/humanclarityinstitute."
        ),
    }

    print(f'Premium report generation complete. ({total_steps} API calls)')
    return report


# ============================================================
# TEST
# ============================================================

if __name__ == '__main__':
    import sys
    import os

    print('Report Generator v3 — Test')
    print('Free result generator: ready (no API key needed)')
    print('Premium generator: requires ANTHROPIC_API_KEY')
    print()
    print('Structure: 13 focused API calls')
    print('  1: Most Surprising Finding + Why Most People Miss This')
    print('  2-10: Nine dimension profiles (one per dimension)')
    print('  11: Cross-dimensional patterns')
    print('  12: What Is AI Changing?')
    print('  13: Profile Directions + Human Flourishing Reflection')
    print()
    print('Estimated generation time: 40-70 seconds')
    print('Estimated cost per report: ~$0.08-0.12')
