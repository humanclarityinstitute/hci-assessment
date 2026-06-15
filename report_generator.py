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
- State position as plain English: "higher than 97 out of every 100 people"
- Pair it with the positional phrase ("notably high", "near the population centre")
- Do NOT use a bare "Xth percentile" number anywhere in the prose
- Always lead with the human meaning, never the number

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

V2.1 COMPLIANCE (mandatory):
- Never assign a "type", "archetype", category, or label to the participant.
  Describe patterns, not identities.
- Describe cross-dimensional combinations as "interesting combinations" or
  "combinations worth noticing" — NEVER as tensions, contradictions, conflicts,
  or problems.
- Use the positional-language scale exactly: exceptionally high / notably high /
  above the population centre / near the population centre / below the population
  centre / notably low / exceptionally low. Invent no alternative positional phrases.
- Do not state a bare "Xth percentile" number. Express position as a plain-English
  comparison ("higher than 84 out of 100 people") plus the positional phrase.
- Every section ends on an observation or open question — never a recommendation
  or instruction.
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


def positional_language(p):
    """Section 3 positional descriptor — exact v2.1 scale, no number."""
    if p is None:
        return 'near the population centre'
    p = int(p)
    if p >= 96: return 'exceptionally high'
    if p >= 86: return 'notably high'
    if p >= 71: return 'above the population centre'
    if p >= 41: return 'near the population centre'
    if p >= 26: return 'below the population centre'
    if p >= 11: return 'notably low'
    return 'exceptionally low'


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
    'combinations': [
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

    combos_text = 'INTERESTING COMBINATIONS observed across HCI\'s series (grounding — cite any figures lightly):\n' + '\n'.join('  - ' + t for t in SIGNALS['combinations'])

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

{combos_text}

WIDEST SPREAD IN THIS PROFILE:
{f"Highest: {highest['label']} ({positional_language(highest['percentile'])})" if highest else ""}
{f"Lowest: {lowest['label']} ({positional_language(lowest['percentile'])})" if lowest else ""}

Write 200-250 words that:
1. Open by describing the overall shape of this profile — what kind
   of AI user does this combination of scores suggest?
2. Identify 2-3 specific dimensional relationships that are interesting
   — how do the scores relate to and illuminate each other?
3. If any rare combinations exist, describe what makes them unusual
   and why the combination is interesting.
4. Note the widest spread in the profile — what does that difference
   reveal that individual scores alone wouldn't show?
5. Close with a genuine observation about what this pattern suggests
   about this person's relationship with AI — end with curiosity.

Describe these strictly as INTERESTING COMBINATIONS — never as tensions,
contradictions, conflicts, or problems. This section should feel like the
report is seeing the whole person, not just individual scores.

No headers. Flowing prose. Speak directly as "you"."""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=550,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text.strip()


# ============================================================
# Population Context (benchmark + demographic comparisons)
# ============================================================

def generate_population_context(results, client):
    """Population Context (v2.1) — two or three benchmark comparisons that place
    the participant in specific population context, including their age group
    where available. Replaces the former 'What Is AI Changing' section."""
    demographics = results['demographics']
    patterns = results['patterns']
    full_ranking = patterns.get('full_ranking', [])
    cohort = cohort_signal(demographics.get('age_group'))

    high_dims = [d for d in full_ranking if d['percentile'] >= 71]
    low_dims = [d for d in full_ranking if d['percentile'] <= 29]

    dim_summary = '\n'.join([
        f"  {d['label']}: {positional_language(d['percentile'])} "
        f"(higher than {int(d['percentile'])} of 100 people)"
        for d in full_ranking
    ])

    prompt = f"""Write the Population Context section of a personalised HCI AI Identity Report.

This section places the participant in the benchmark population with two or three
concrete comparisons. It is grounded and factual — the most data-solid moment in
the report.

PARTICIPANT PROFILE (positional language + plain-English comparison):
{dim_summary}

Most distinctive (high): {', '.join([d['label'] for d in high_dims]) if high_dims else 'none stand out high'}
Most distinctive (low): {', '.join([d['label'] for d in low_dims]) if low_dims else 'none stand out low'}
Age group: {demographics.get('age_group', 'not specified')}
{f"Cohort context — people in this age group are {cohort}." if cohort else ""}

Write ~100 words that:
1. Give two or three precise population comparisons from the profile above — where
   this person sits relative to everyone, in plain English.
2. Where an age group is given, add one comparison to people their own age, using
   the cohort context above as light grounding.
3. Describe difference, never deficiency. Position, never prediction.

Use ONLY the positions provided above. Plain-English comparisons, no bare percentile
numbers, positional language from the scale. End on an observation, not a
recommendation. Speak directly as "you"."""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=400,
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
SECTION A: PUTTING THIS TO WORK (~190 words)
═══════════════════════════════════

Four elements — each 2-3 sentences. Non-prescriptive throughout.
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

USE THIS REPORT AS A MIRROR:
Describe — as an option they may find interesting, never an instruction — that they can
hand this full report to the AI they use most (ideally one that remembers their history)
and ask it to reflect on the report, check it against how they actually work together,
show them the evidence for and against, and, if THEY decide they want to shift something,
help them do the heavy lifting. Note briefly that they run it in their own AI and nothing
returns to HCI. Frame the whole thing as a possibility worth exploring; end this element
on an open question, not a directive.

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

4. What human advantages appear most prominent in this pattern?
   Population-grounded. Open. Never alarming. End with genuine curiosity.

CRITICAL: Section B must end with a sentence that leaves the participant
feeling more curious about themselves than when they started reading.
This is the last thing they read. Make it count.

Write Section A then Section B. Use clear section headers:
"Putting This to Work" and "Human Flourishing Reflection"
Then flowing prose within each. Speak as "you" throughout."""

    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=950,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text.strip()


# ============================================================
# Your AI Identity — Overview  (v2.1, no archetype)
# ============================================================

def generate_overview(results, client):
    """Integrative overview paragraph naming the 2-3 most distinctive patterns.
    No archetype, type, category, or label of any kind."""
    patterns = results['patterns']
    full_ranking = patterns.get('full_ranking', [])
    dim_summary = '\n'.join([
        f"  {d['label']}: {positional_language(d['percentile'])} "
        f"(higher than {int(d['percentile'])} of 100 people)"
        for d in full_ranking
    ])
    top = full_ranking[:3]
    prompt = f"""Write the "Your AI Identity — Overview" section of a personalised HCI AI Identity Report.

A single integrative paragraph describing the overall shape of this person's profile
across all nine dimensions — written fresh, as a whole, not assembled from fragments.

ALL NINE (positional language + plain-English comparison):
{dim_summary}

Centre the paragraph on the most distinctive patterns: {', '.join(d['label'] for d in top)}

Write ~200 words that:
1. Name the two or three most distinctive patterns and how they relate — what kind of
   relationship with AI does the whole picture suggest?
2. Stay integrative — a coherent whole, not a list of scores.
3. Plain-English comparisons and positional language; no bare percentile numbers.

ABSOLUTE RULE: do NOT assign a type, archetype, category, or label of any kind.
Describe patterns, not an identity. End on an observation that sets up curiosity for
the detail that follows. Speak directly as "you"."""
    message = client.messages.create(
        model='claude-sonnet-4-6', max_tokens=520,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text.strip()


# ============================================================
# Perception Gap Analysis  (Section 6) — or Perception Alignment
# ============================================================

def generate_perception_gap(results, client):
    """Dedicated perception-gap section. If no meaningful gap, retitled
    'Perception Alignment' and notes consistency. Never manufactures a finding."""
    gaps = results.get('perception_gaps', {}) or {}
    candidates = []
    if isinstance(gaps, dict):
        candidates = [g for g in gaps.values() if isinstance(g, dict)]
    elif isinstance(gaps, list):
        candidates = [g for g in gaps if isinstance(g, dict)]
    sig = None
    for g in candidates:
        a, p = g.get('actual_percentile'), g.get('perceived_estimate')
        if a is None or p is None:
            continue
        if abs(a - p) >= 25 and (sig is None or abs(a - p) > abs(sig['actual_percentile'] - sig['perceived_estimate'])):
            sig = g

    if sig:
        a = int(sig['actual_percentile'])
        dim = sig.get('dimension', 'one dimension')
        prompt = f"""Write the Perception Gap Analysis section (~100 words) of an HCI report.

Dimension: {dim}
Where they placed themselves: around the middle / their own estimate.
Where the benchmark places them: higher than {a} of 100 people ({positional_language(a)}).

Frame the gap to ILLUMINATE, never to correct. Permitted: "One finding worth noting...",
"Your estimated positioning and your actual score tell different stories.", "That gap is
itself a finding worth sitting with." PROHIBITED: "you underestimated...", "you may not
realise...", "you were wrong", "you lack self-awareness". Plain-English comparison, no bare
percentile number. End on an observation, not a recommendation. Speak as "you"."""
    else:
        prompt = """Write a short "Perception Alignment" section (~70 words) of an HCI report.

This participant's self-estimates and their benchmarked scores are broadly consistent.
Note this plainly and with genuine interest — consistency between how someone sees
themselves and where they actually sit is itself worth noting. Do NOT manufacture a gap
or a finding. End on an observation. Speak as "you"."""

    message = client.messages.create(
        model='claude-sonnet-4-6', max_tokens=350,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text.strip()


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

# ============================================================
# PER-QUESTION BREAKDOWN  (deterministic, no API) — spec v2.1
# Curated 1-2 distinctive questions per dimension + full appendix.
# ============================================================

QUESTION_TEXT = {
    # Trust
    "trust_q1": "When AI gives me information, I generally trust it is accurate.",
    "trust_q2": "I feel confident relying on information or recommendations generated by AI.",
    "trust_q3": "I worry that AI will present incorrect information as if it were fact.",
    "trust_q4": "When I feel uncertain, I am more likely to trust guidance from AI systems.",
    # Disclosure
    "disc_q1": "I feel comfortable sharing personal thoughts or emotions with AI that I would not share with most people.",
    "disc_q2": "I feel emotionally safer expressing myself to AI than I do to many people in my life.",
    "disc_q3": "There are things I have told AI that I have never told another person.",
    "disc_q4": "I am more open with AI about some topics than I am with people in my life.",
    # Reliance
    "rel_q1": "I feel uneasy or restless when I cannot use AI tools for an extended period.",
    "rel_q2": "I struggle to function effectively without assistance from digital or AI systems.",
    "rel_q3": "I rely on AI for many everyday work or personal decisions.",
    "rel_q4": "I often rely on AI even when I could work things out on my own.",
    "rel_q5": "Some of my abilities have weakened because AI systems now perform those tasks for me.",
    # Decision Delegation
    "del_q1": "I regularly hand over decisions to AI systems that I previously made myself.",
    "del_q2": "When I use AI for decisions, I usually accept its recommendations without making significant changes.",
    "del_q3": "I sometimes follow AI recommendations even when they do not feel right to me.",
    "del_q4": "I am comfortable relying on AI systems for important decisions that could significantly affect my life or work.",
    "del_q5": "When I feel uncertain about a decision, I am more likely to rely on AI guidance.",
    # Verification
    "ver_q1": "I regularly double-check information provided by AI using other sources.",
    "ver_q2": "I often skip checking AI information because it takes too much time or effort.",
    "ver_q3": "When information feels complicated or mentally demanding, I am more likely to accept it without checking carefully.",
    "ver_q4": "I use independent sources to confirm whether AI-generated information is accurate.",
    # Human Agency
    "agency_q1": "My actions feel self-directed rather than driven by external forces.",
    "agency_q2": "I feel in control of decisions when using AI or automated systems.",
    "agency_q3": "Using AI tools has changed how much I trust my own judgement.",
    "agency_q4": "I sometimes feel influenced by systems without being fully aware of how.",
    "agency_q5": "I sometimes question what is genuinely \"mine\" versus shaped by suggestions from AI tools.",
    # Emotional Regulation
    "emot_q1": "AI sometimes gives me a sense of relief or support when I feel emotionally overwhelmed.",
    "emot_q2": "I receive emotional support or comfort from AI tools.",
    "emot_q3": "Over time, my emotional or conversational boundaries with AI have become more open.",
    "emot_q4": "When I feel stressed, anxious, or emotionally overwhelmed, I often turn to AI to help me process my thoughts.",
    # Thought Partnership
    "thought_q1": "I use AI as a sounding board — thinking out loud and developing ideas through conversation.",
    "thought_q2": "I use AI to challenge or stress-test my own beliefs and assumptions.",
    "thought_q3": "AI has changed how deeply I engage with my own thinking.",
    "thought_q4": "I tend to use AI in ways that confirm what I already think rather than challenge it.",
    # Social Transparency
    "soc_q1": "I openly acknowledge when AI has contributed to my work or thinking.",
    "soc_q2": "I downplay or hide how much I use AI when talking to friends or family.",
    "soc_q3": "I feel comfortable telling people in my life how I really use AI.",
    "soc_q4": "There is a gap between how much I actually use AI and what I let others believe.",
}

import json as _json

_BENCHMARK_CACHE = {}

def _load_benchmark(path):
    if path in _BENCHMARK_CACHE:
        return _BENCHMARK_CACHE[path]
    try:
        with open(path) as f:
            data = _json.load(f)
    except Exception as e:
        print(f'  [!] question breakdown: could not load benchmark ({e})')
        data = {}
    _BENCHMARK_CACHE[path] = data
    return data

def _bin7(arr):
    bins = [0] * 7
    for v in arr or []:
        try:
            iv = int(round(float(v)))
        except (TypeError, ValueError):
            continue
        if 1 <= iv <= 7:
            bins[iv - 1] += 1
    return bins

def _pct_of(dist, ans):
    total = sum(dist) or 1
    ans = max(1, min(7, int(ans)))
    below = sum(dist[:ans - 1])
    at = dist[ans - 1]
    return round((below + 0.5 * at) / total * 100)

def build_question_breakdown(results, benchmark_path='benchmark_tables.json'):
    """Assemble per-question data grouped by dimension. Each question carries the
    raw answer, the overall and your-age 7-bin distributions, both plain-English
    percentiles, and a 'distinctive' flag (the 1-2 furthest-from-average per
    dimension). Returns {} if the benchmark or per-question data is unavailable."""
    bench = _load_benchmark(benchmark_path)
    if not bench:
        return {}
    demographics = results.get('demographics', {})
    age = (demographics.get('age_group') or '').strip()
    dims = results.get('dimensions', {})

    out = {}
    for dim_key, dim_data in dims.items():
        qscores = dim_data.get('question_scores') or {}
        if not qscores:
            continue
        questions = []
        for q_key, qs in qscores.items():
            variable = qs.get('variable')
            answer = qs.get('raw')
            bvar = bench.get(variable, {})
            dist_overall = _bin7(bvar.get('overall'))
            if sum(dist_overall) == 0:
                continue
            by_age = bvar.get('by_age', {}) or {}
            age_arr = by_age.get(age) if age else None
            dist_age = _bin7(age_arr) if age_arr else None
            if dist_age is not None and sum(dist_age) == 0:
                dist_age = None
            pct_overall = _pct_of(dist_overall, answer)
            pct_age = _pct_of(dist_age, answer) if dist_age else None
            questions.append({
                'q_key': q_key,
                'variable': variable,
                'text': QUESTION_TEXT.get(q_key, variable),
                'answer': int(answer) if answer is not None else None,
                'dist_overall': dist_overall,
                'dist_age': dist_age,
                'pct_overall': pct_overall,
                'pct_age': pct_age,
                'distinctive': False,
            })
        if not questions:
            continue
        # flag the 1-2 most distinctive (furthest from the population centre)
        ranked = sorted(questions, key=lambda q: abs(q['pct_overall'] - 50), reverse=True)
        for q in ranked[:2]:
            q['distinctive'] = True
        out[dim_key] = {
            'label': dim_data.get('label', dim_key),
            'questions': questions,
        }
    return out


def generate_premium_report(results, api_key=None, progress_callback=None, benchmark_path='benchmark_tables.json'):
    """
    Generate the complete premium report using 15 focused API calls (spec v2.1).

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

    total_steps = 15
    step = 0

    def progress(message):
        nonlocal step
        step += 1
        print(f'  [{step}/{total_steps}] {message}')
        if progress_callback:
            progress_callback(step, total_steps, message)

    print('Generating premium report — 15 focused calls (spec v2.1)...')

    # ── Call 1: Opening ──────────────────────────────────────────────────────
    progress('Identifying your most surprising finding...')
    opening = generate_opening(results, client)

    # ── Call 2: Overview ─────────────────────────────────────────────────────
    progress('Writing your AI Identity overview...')
    overview = generate_overview(results, client)

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
                'position': positional_language(
                    dim_data['percentiles'].get('overall')
                ),
                'rarity': get_rarity_text(dim_data['percentiles'].get('overall')),
            }

    # ── Cross-dimensional patterns ───────────────────────────────────────────
    progress('Analysing cross-dimensional patterns...')
    cross_dimensional = generate_cross_dimensional(results, client)

    # ── Perception Gap Analysis ──────────────────────────────────────────────
    progress('Writing your perception gap analysis...')
    perception_gap = generate_perception_gap(results, client)

    # ── Population Context ───────────────────────────────────────────────────
    progress('Placing you in population context...')
    population_context = generate_population_context(results, client)

    # ── Putting This to Work + Human Flourishing ─────────────────────────────
    progress('Writing your Human Flourishing Reflection...')
    closing = generate_closing(results, client)

    # ── Per-question breakdown (deterministic, no API) ───────────────────────
    print('  [+] Building per-question breakdown...')
    question_breakdown = build_question_breakdown(results, benchmark_path)

    # ── Assemble report ──────────────────────────────────────────────────────
    report = {
        'metadata': {
            'demographics': demographics,
            'generated_by': 'HCI AI Identity & Behaviour Assessment',
            'version': '2.1',
            'total_api_calls': 15,
        },
        'headline': results.get('headline'),
        'opening': opening,
        'overview': overview,
        'dimension_profiles': dimension_profiles,
        'dimension_ranking': patterns.get('full_ranking', []),
        'cross_dimensional': cross_dimensional,
        'perception_gap': perception_gap,
        'closing': closing,
        'population_context': population_context,
        'question_breakdown': question_breakdown,
        'variable_highlights': variable_highlights,
        'perception_gaps': results.get('perception_gaps', {}),
        'methodology_note': (
            "This report is based on your responses to the HCI AI Identity & "
            "Behaviour Assessment — a research-based behavioural instrument "
            "benchmarked against data from more than 10,000 participants across "
            "multiple studies conducted by the Human Clarity Institute.\n\n"
            "Scores represent your positioning within the benchmark population. "
            "They describe patterns, not traits. They reflect how you responded "
            "at this point in time and may change as your relationship with AI "
            "evolves.\n\n"
            "This assessment is designed for personal insight and reflection. It "
            "is not a clinical instrument and should not be used for diagnosis, "
            "professional evaluation, or any purpose beyond individual "
            "self-understanding.\n\n"
            "Benchmark data and methodology are publicly available at "
            "github.com/humanclarityinstitute."
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
    print('Structure: 15 focused API calls (spec v2.1)')
    print('  1: Most Surprising Finding')
    print('  2: Your AI Identity — Overview (no archetype)')
    print('  3-11: Nine dimension profiles')
    print('  12: Cross-dimensional (interesting combinations)')
    print('  13: Perception Gap Analysis')
    print('  14: Population Context')
    print('  15: Putting This to Work + Human Flourishing')
    print()
    print('Estimated generation time: 40-70 seconds')
    print('Estimated cost per report: ~$0.08-0.12')
