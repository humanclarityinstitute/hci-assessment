"""
report_sections.py

Deterministic report section assembly from canonical report_data.

Important:
- This file does not calculate scores.
- This file does not call Claude.
- Static/pre-written HCI content comes from report_templates.py.
- Claude-written content is read only from report_data["narrative_blocks"].
"""

from __future__ import annotations

from typing import Any, Dict

from report_templates import (
    OPENING_STATEMENT,
    NEXT_STEPS,
    WHAT_TO_PROTECT_TEMPLATES,
    DIMENSION_ORDER,
    DIMENSION_LABELS,
    DIMENSION_DEFINITIONS,
    ordinal,
    percentile_position,
    protect_position,
    typicality_sentence,
    STRENGTH_DEEPENING_COPY,
    MONITORING_COPY,
)


def narrative_block(report_data: Dict[str, Any], key: str, fallback: str = "") -> str:
    return (report_data.get("narrative_blocks") or {}).get(key) or fallback


def build_sections(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build all render-ready report sections.
    """
    opening = build_opening(report_data)
    dashboard = build_dashboard(report_data)
    typicality = build_typicality(report_data)
    rare = build_rare_combinations(report_data)
    story = build_behaviour_story(report_data)
    questions = build_question_profile(report_data)
    distinctive = build_distinctive_responses(report_data)
    perception = build_perception_gap(report_data)
    protect = build_what_to_protect(report_data)
    trajectory = build_if_nothing_changes(report_data)
    next_steps = build_next_steps(report_data)
    deep_dive = build_deep_dive(report_data)

    return {
        # Legacy renderer keys
        "opening": opening,
        "dashboard": dashboard,
        "typicality": typicality,
        "rare": rare,
        "story": story,
        "questions": questions,
        "distinctive": distinctive,
        "perception": perception,
        "protect": protect,
        "trajectory": trajectory,
        "next_steps": next_steps,
        "deep_dive": deep_dive,

        # Explicit locked section keys
        "section_1_dashboard": dashboard,
        "section_3_typicality": typicality,
        "section_4_rare_combinations": rare,
        "section_5_behaviour_story": story,
        "section_6_question_profile": questions,
        "section_7_distinctive_responses": distinctive,
        "section_8_perception_gap": perception,
        "section_9_what_to_protect": protect,
        "section_10_if_nothing_changes": trajectory,
        "section_11_next_steps": next_steps,
        "section_12_deep_dive": deep_dive,
    }


# ---------------------------------------------------------------------
# Opening
# ---------------------------------------------------------------------

def build_opening(report_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": "What stands out immediately",
        "statement": (
            "Your relationship with AI is beginning to form a behavioural pattern.\n\n"
            "This report compares that pattern with more than 10,500 participants across 21 Human Clarity Institute research studies, helping identify where your AI use is typical, where it is distinctive, and which aspects of your relationship with AI are changing most rapidly.\n\n"
            "Rather than judging behaviour as good or bad, this report maps how you currently work with AI and provides evidence you can use to make more informed decisions as that relationship evolves."
        ),
        "findings": narrative_block(report_data, "opening_findings", opening_fallback(report_data)),
    }


def opening_fallback(report_data: Dict[str, Any]) -> str:
    inputs = report_data.get("synthesis_inputs") or {}
    most = inputs.get("most_distinctive_variable") or {}
    gap = inputs.get("largest_perception_gap") or {}
    combo = inputs.get("top_rare_combination") or {}
    top_dims = inputs.get("top_dimensions") or []
    low_dims = inputs.get("lowest_dimensions") or []

    if most:
        most_text = (
            f"The strongest individual signal in your profile is your response to: “{most.get('question_text')}”. "
            f"You answered {most.get('answer_display')}, placing this response at the {most.get('percentile_label')} percentile. "
            "That makes it the clearest single point of difference between your pattern and the wider benchmark. "
            "It is not just a score; it is the behaviour in your profile that most sharply reveals how AI has become part of your day-to-day thinking and functioning."
        )
    else:
        most_text = (
            "No single response dominates your profile. The stronger signal is the overall shape of the pattern: several dimensions appear to be moving together rather than one item standing apart."
        )

    if gap:
        question = gap.get("question") or gap.get("key") or "one self-perception item"
        perceived = gap.get("perceived_answer") or gap.get("perceived") or "your self-estimate"
        actual = gap.get("actual_percentile")
        gap_text = (
            f"There is also a useful gap between how your AI use feels from the inside and where it sits in the benchmark. Around {question}, you described yourself as “{perceived}”, while the data places you around the {ordinal(actual)} percentile. "
            "That kind of difference matters because AI use often normalises itself. Once a behaviour becomes routine, it can stop feeling distinctive even when it remains unusual compared with the wider population."
        )
    else:
        gap_text = (
            "Your self-perception broadly aligns with your benchmark position. That alignment is meaningful because it suggests you are noticing your own AI pattern with reasonable accuracy rather than only discovering it through the report."
        )

    if combo:
        combo_text = (
            f"The clearest combination signal is {combo.get('label_1')} and {combo.get('label_2')}, a pairing that appears in roughly {combo.get('rarity_percent')}% of participants. "
            "This matters because the report is not only about high or low scores. It is about how dimensions interact: where one behaviour reinforces another, where it counterbalances it, and where the overall pattern becomes distinctive."
        )
    else:
        top_labels = [d.get("label") for d in top_dims[:3] if isinstance(d, dict) and d.get("label")]
        low_labels = [d.get("label") for d in low_dims[:2] if isinstance(d, dict) and d.get("label")]
        combo_text = (
            "No rare dimensional combination was detected. What appears instead is a coherent pattern: "
            + (f"your higher dimensions include {', '.join(top_labels)}, " if top_labels else "several dimensions move in the same direction, ")
            + (f"while your lower dimensions include {', '.join(low_labels)}. " if low_labels else "")
            + "That coherence is still informative. It suggests your profile is less defined by unusual tension and more by a recognisable overall direction in how AI is becoming integrated into your behaviour."
        )

    return "\n\n".join([
        "Your most distinctive signal\n" + most_text,
        "How your self-perception compares\n" + gap_text,
        "The shape of the wider pattern\n" + combo_text,
    ])


# ---------------------------------------------------------------------
# Section 1
# ---------------------------------------------------------------------

def build_dashboard(report_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": "Your AI Behaviour Pattern",
        "subtitle": "How you compare across nine dimensions",
        "cards": report_data.get("dashboard", []),
    }



# ---------------------------------------------------------------------
# Section 12: Deep Dive
# ---------------------------------------------------------------------

def build_deep_dive(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optional but high-value personalised Deep Dive.

    This is Claude-written when available, with deterministic fallback.
    """
    return {
        "title": "Deep Dive",
        "body": narrative_block(report_data, "deep_dive", deep_dive_fallback(report_data)),
    }


def deep_dive_fallback(report_data: Dict[str, Any]) -> str:
    inputs = report_data.get("synthesis_inputs") or {}
    most = inputs.get("most_distinctive_variable")
    top = (inputs.get("top_dimensions") or [{}])[0]
    combo = inputs.get("top_rare_combination")

    if combo:
        return (
            f"The most useful place to look more closely is the combination of {combo.get('label_1')} and {combo.get('label_2')}. "
            "This pairing gives the clearest view of how different parts of your AI behaviour interact."
        )

    if most:
        return (
            f"The most useful place to look more closely is your response to “{most.get('question_text')}”. "
            f"You answered {most.get('answer_display')}, which makes this one of the strongest signals in your profile."
        )

    if top:
        return (
            f"The most useful place to look more closely is {top.get('label', 'your highest dimension')}. "
            "This is the clearest organising feature in your current AI behaviour pattern."
        )

    return "The most useful place to look more closely is the overall shape of your profile."

# ---------------------------------------------------------------------
# Section 3
# ---------------------------------------------------------------------

def build_typicality(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source = report_data.get("typicality") or {}

    # Attach light deterministic interpretation from report_templates.py.
    def enrich(items):
        out = []
        for item in items or []:
            enriched = dict(item)
            if not enriched.get("interpretation"):
                enriched["interpretation"] = typicality_sentence(
                    enriched.get("dimension"),
                    enriched.get("percentile"),
                )
            return_item = enriched
            out.append(return_item)
        return out

    distinctive = enrich(source.get("distinctive", []))
    typical = enrich(source.get("typical", []))
    moderate = enrich(source.get("moderate", []))
    all_items = enrich(source.get("all", []))

    return {
        "title": "The Shape of Your Profile",
        "subtitle": "Where your AI behaviour stands out and where it remains closer to the benchmark",
        "distinctive": distinctive,
        "typical": typical,
        "moderate": moderate,
        "benchmark_range": typical + moderate,
        "all": all_items,
        "profile_shape_summary": narrative_block(
            report_data,
            "profile_shape_summary",
            profile_shape_fallback(distinctive, typical + moderate),
        ),
    }


def profile_shape_fallback(distinctive, benchmark_range) -> str:
    """Fallback summary for the profile-shape section if Claude output is unavailable."""
    if distinctive and benchmark_range:
        return (
            "Your profile is shaped by a smaller number of dimensions that stand out against a wider background of behaviours that remain closer to the benchmark population. "
            "That means the most useful reading of your results is not that everything has shifted, but that several specific parts of your AI relationship carry most of the signal."
        )

    if distinctive and not benchmark_range:
        return (
            "Your profile shows a broad pattern of distinction across the HCI dimensions rather than one isolated signal. "
            "This means the overall shape of your AI relationship is best understood as a wider behavioural pattern, not a single unusually high or low score."
        )

    return (
        "Your profile sits largely within the benchmark range across the HCI dimensions. "
        "That does not make it less meaningful; it means your relationship with AI is currently defined more by its overall balance than by one strongly unusual dimension."
    )


# ---------------------------------------------------------------------
# Section 4
# ---------------------------------------------------------------------

def build_rare_combinations(report_data: Dict[str, Any]) -> Dict[str, Any]:
    combos = report_data.get("rare_combinations") or []

    fallback = (
        "No rare dimensional combinations were detected in your profile. "
        "That does not mean the profile is less useful. It means your pattern is less defined by unusual tension between dimensions and more by the overall distribution of your scores."
    )

    return {
        "title": "What Makes You Different",
        "combinations": combos[:2],
        "narrative": narrative_block(report_data, "rare_combinations_narrative", "" if combos else fallback),
        "fallback": fallback if not combos else "",
    }


# ---------------------------------------------------------------------
# Section 5
# ---------------------------------------------------------------------

def build_behaviour_story(report_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": "Your Behaviour Story",
        "body": narrative_block(report_data, "behaviour_story", behaviour_story_fallback(report_data)),
    }


def behaviour_story_fallback(report_data: Dict[str, Any]) -> str:
    dims = sorted(
        (report_data.get("dimensions") or {}).values(),
        key=lambda d: d.get("percentile", 50),
        reverse=True,
    )

    if not dims:
        return "No dimension data was available."

    top = dims[0]
    second = dims[1] if len(dims) > 1 else None
    low = sorted(dims, key=lambda d: d.get("percentile", 50))[0]

    parts = [
        f"Your relationship with AI is characterized primarily by {top.get('label', '').lower()}. This dimension sits at the {ordinal(top.get('percentile'))} percentile, making it one of the clearest organising features in your profile."
    ]

    if second:
        parts.append(
            f"This is paired with {second.get('label', '').lower()}, which sits at the {ordinal(second.get('percentile'))} percentile. Together, these dimensions help explain the basic shape of your pattern."
        )

    parts.append(
        f"At the other end, {low.get('label', '').lower()} sits at the {ordinal(low.get('percentile'))} percentile. That contrast matters because HCI reports are not designed to label you as one type of user; they show the shape of your current pattern."
    )

    return "\n\n".join(parts)


# ---------------------------------------------------------------------
# Section 6
# ---------------------------------------------------------------------

def build_question_profile(report_data: Dict[str, Any]) -> Dict[str, Any]:
    questions = report_data.get("questions") or []
    groups = []

    for dim in DIMENSION_ORDER:
        groups.append({
            "dimension": dim,
            "label": DIMENSION_LABELS[dim],
            "definition": DIMENSION_DEFINITIONS[dim],
            "questions": [q for q in questions if q.get("dimension") == dim],
        })

    return {
        "title": "Your Question-Level Profile",
        "subtitle": "How your individual responses compare",
        "groups": groups,
    }


# ---------------------------------------------------------------------
# Section 7
# ---------------------------------------------------------------------

def build_distinctive_responses(report_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": "Your Most Distinctive Responses",
        "responses": (report_data.get("distinctive_responses") or [])[:7],
        "narrative": narrative_block(report_data, "distinctive_responses_narrative", ""),
    }


# ---------------------------------------------------------------------
# Section 8
# ---------------------------------------------------------------------

def build_perception_gap(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source = report_data.get("perception_gap") or {}
    self_perception = source.get("self_perception", [])

    fallback = (
        "What this section ultimately shows is that your intuition about your AI relationship is broadly accurate, "
        "but the benchmark reveals where that distinctiveness actually sits. Rather than being defined by reliance alone, "
        "your profile is characterised by the way you think with AI, trust it, and incorporate it into important decisions."
    )

    def perceived_direction(answer: Any) -> str:
        text = str(answer or "").lower()
        if any(term in text for term in ["much more", "somewhat more", "more than", "higher", "above"]):
            return "Higher"
        if any(term in text for term in ["much less", "somewhat less", "less than", "lower", "below"]):
            return "Lower"
        if any(term in text for term in ["same", "average", "about the same", "similar"]):
            return "About the same"
        return str(answer or "Not stated")

    comparison_summary = []
    for item in self_perception:
        comparison_summary.append({
            "label": item.get("comparison_label") or item.get("short_label") or item.get("primary_dimension_label") or item.get("question") or "AI relationship",
            "self": perceived_direction(item.get("answer")),
            "benchmark": item.get("actual_percentile"),
            "benchmark_label": item.get("actual_percentile_label"),
            "position": item.get("actual_position"),
        })

    return {
        "title": "How You See Yourself",
        "subtitle": "Comparing your self-perception with your benchmark profile.",
        "self_perception": self_perception,
        "comparison_summary": comparison_summary,
        "gaps": source.get("gaps", []),
        "largest_gap": source.get("largest_gap"),
        "has_significant_gap": source.get("has_significant_gap", False),
        "narrative_heading": "What this comparison suggests",
        "narrative": narrative_block(report_data, "perception_gap_narrative", fallback),
    }


# ---------------------------------------------------------------------
# Section 9
# ---------------------------------------------------------------------

def build_what_to_protect(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source = {x.get("dimension"): x for x in report_data.get("what_to_protect", [])}
    items = []

    for dim, template in WHAT_TO_PROTECT_TEMPLATES.items():
        data = source.get(dim, {})
        percentile = data.get("percentile")
        items.append({
            "dimension": dim,
            "label": DIMENSION_LABELS[dim],
            "definition": DIMENSION_DEFINITIONS[dim],
            "percentile": percentile,
            "positioning": data.get("positioning") or protect_position(percentile),
            **template,
        })

    return {
        "title": "What To Protect",
        "subtitle": "Four capacities worth noticing as your AI use evolves",
        "items": items,
    }


# ---------------------------------------------------------------------
# Section 10
# ---------------------------------------------------------------------

def build_if_nothing_changes(report_data: Dict[str, Any]) -> Dict[str, Any]:
    data = report_data.get("if_nothing_changes") or {}
    strengths = enrich_strengths(data.get("strengths_likely_to_deepen", []))
    monitoring = enrich_monitoring(data.get("areas_worth_monitoring", []))

    return {
        "title": "If Nothing Changes",
        "subtitle": "Observable patterns from HCI research, not predictions or prescriptions.",
        "summary": build_trajectory_summary(strengths, monitoring),
        "likely_to_continue": narrative_block(report_data, "likely_to_continue", likely_to_continue_fallback(data)),
        "strengths_likely_to_deepen": strengths,
        "areas_worth_monitoring": monitoring,
        "monitoring_intro": "These are not concerns or predictions. They are simply the parts of a profile that research shows are most likely to shift as AI becomes more integrated into everyday life.",
        "overall_outlook": narrative_block(report_data, "overall_outlook", overall_outlook_fallback(data)),
    }


def trajectory_band(percentile):
    try:
        p = int(round(float(percentile)))
    except Exception:
        p = 50
    if p >= 71:
        return "High"
    if p >= 41:
        return "Moderate"
    return "Lower"


def build_trajectory_summary(strengths, monitoring):
    """
    Small scan-first summary for Section 10.

    The renderer uses this before the narrative so the reader can immediately see
    what is stable, what may deepen, and what is worth monitoring.
    """
    rows = []
    seen = set()

    for item in strengths or []:
        key = item.get("key") or item.get("dimension") or item.get("label")
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "label": item.get("label"),
            "position": trajectory_band(item.get("percentile")),
            "direction": "Likely to deepen",
        })
        if len(rows) >= 2:
            break

    for item in monitoring or []:
        key = item.get("key") or item.get("dimension") or item.get("label")
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "label": item.get("label"),
            "position": trajectory_band(item.get("percentile")),
            "direction": "Worth monitoring",
        })
        if len(rows) >= 4:
            break

    return rows


def enrich_strengths(strengths):
    out = []
    for d in strengths or []:
        dim = d.get("key") or d.get("dimension")
        item = dict(d)
        item["strength_deepening"] = STRENGTH_DEEPENING_COPY.get(dim, {})
        item["research_summary"] = strength_research_summary(dim)
        item["deepening_summary"] = strength_deepening_summary(dim)
        out.append(item)
    return out


def enrich_monitoring(items):
    out = []
    for d in items or []:
        dim = d.get("key") or d.get("dimension")
        item = dict(d)
        item["monitoring"] = MONITORING_COPY.get(dim, {})
        item["current_position"] = monitoring_position_sentence(dim, item.get("percentile"))
        item["why_monitor"] = monitoring_research_summary(dim)
        item["early_sign"] = monitoring_early_sign(dim)
        out.append(item)
    return out


def strength_research_summary(dim: str) -> str:
    copy = {
        "trust": "Everyday users consistently report higher trust than occasional users, suggesting confidence often grows as AI becomes more familiar and useful.",
        "decision_delegation": "Decision support can become more fluent with repeated use, especially when AI is already involved in shaping options, recommendations, or next steps.",
        "thought_partnership": "People who use AI as a thinking partner often find the interaction becomes more natural as idea development, challenge, and refinement become part of the workflow.",
        "human_agency": "People who maintain clear decision authority while using AI often reinforce that authorship through repeated use rather than passively losing it.",
        "reliance": "When AI is already embedded in a working rhythm, continued use can make that support feel increasingly normal and efficient.",
        "verification": "Strong verification can deepen into a stable checking rhythm when accuracy remains important to the user.",
        "emotional_regulation": "When AI is used for emotional processing, repeated use can make it feel like a more available reflective space.",
        "disclosure": "When disclosure to AI is already high, familiarity can make personal expression in that setting feel increasingly normal.",
        "social_transparency": "When people are already open about AI use, continued exposure can make that transparency easier to maintain.",
    }
    return copy.get(dim, "Research shows this pattern can become more fluent when it is already part of a person's AI relationship.")


def strength_deepening_summary(dim: str) -> str:
    copy = {
        "trust": "Smoother collaboration, faster acceptance of useful outputs, and a more settled sense of when AI is reliable.",
        "decision_delegation": "More natural use of AI to shape options, compare choices, and move from analysis into action.",
        "thought_partnership": "More fluent conversations, faster iteration, and deeper exploration of complex ideas.",
        "human_agency": "Clearer values, sharper judgment calls, and stronger authorship of your decisions.",
        "reliance": "AI feeling more integrated into ordinary tasks, planning, and thinking routines.",
        "verification": "A more deliberate checking rhythm, especially when stakes or uncertainty are higher.",
        "emotional_regulation": "More frequent use of AI as a space to organise feelings, stress, or uncertainty.",
        "disclosure": "Greater ease sharing personal context, private thoughts, or unfinished reflections with AI.",
        "social_transparency": "More comfort naming when and how AI contributed to your thinking or work.",
    }
    return copy.get(dim, "The behaviour becomes easier, more fluent, and more automatic within the existing pattern.")


def monitoring_position_sentence(dim: str, percentile) -> str:
    band = trajectory_band(percentile).lower()
    label = DIMENSION_LABELS.get(dim, "This dimension").lower()
    if band == "high":
        return f"{label.title()} currently sits at the high end of your profile."
    if band == "lower":
        return f"{label.title()} currently sits below the centre of the benchmark."
    return f"{label.title()} currently sits near the middle of the benchmark."


def monitoring_research_summary(dim: str) -> str:
    copy = {
        "verification": "Verification is worth noticing because checking can become more selective when AI use becomes frequent or cognitively easy.",
        "reliance": "Reliance is worth noticing because support that feels useful can gradually become part of the default workflow.",
        "human_agency": "Agency is worth noticing because identity-level control often remains intact while small process-level shifts can still occur.",
        "trust": "Trust is worth noticing because confidence can grow faster than checking behaviour, especially when errors are not immediately visible.",
        "decision_delegation": "Decision delegation is worth noticing because repeated use can make AI-shaped options feel increasingly natural.",
        "thought_partnership": "Thought partnership is worth noticing because deep cognitive use can become the default way ideas are developed.",
        "emotional_regulation": "Emotional regulation is worth noticing because availability can make AI feel like an easy first place to process uncertainty or stress.",
        "disclosure": "Disclosure is worth noticing because repeated personal sharing can shift what feels private or ordinary.",
        "social_transparency": "Social transparency is worth noticing because actual AI use and visible AI use can drift apart.",
    }
    return copy.get(dim, "This area is worth noticing because it is one of the places AI behaviour can shift quietly with repeated use.")


def monitoring_early_sign(dim: str) -> str:
    copy = {
        "verification": "Noticing yourself checking less, or feeling relief when you skip it.",
        "reliance": "Struggling to function without AI, or avoiding tasks that require independent thinking.",
        "human_agency": "Realising AI's framing has become your first instinct before you form your own view.",
        "trust": "Accepting AI outputs more quickly because they usually feel right.",
        "decision_delegation": "Letting AI-shaped recommendations move directly into action without much second-guessing.",
        "thought_partnership": "Finding it harder to develop a first position before consulting AI.",
        "emotional_regulation": "Turning to AI first when you feel stressed, uncertain, or overloaded.",
        "disclosure": "Sharing more personal context with AI than you would have expected.",
        "social_transparency": "Using AI more often than other people can see from the outside.",
    }
    return copy.get(dim, "Noticing the behaviour becoming more automatic than deliberate.")


def likely_to_continue_fallback(data: Dict[str, Any]) -> str:
    high = data.get("highest_dimension") or {}
    if not high:
        return (
            "People with profiles like yours tend to retain the overall shape of their relationship with AI unless usage frequency changes significantly. "
            "If your current pattern holds, the clearest continuity is likely to be the way your strongest behaviours keep organising the rest of the profile. "
            "What tends to remain stable is not only the behaviour itself, but the internal logic that makes the pattern feel coherent."
        )

    return (
        "People with profiles like yours tend to retain the overall shape of their relationship with AI unless usage frequency changes significantly. "
        f"The pattern most likely to hold is the role of {high.get('label', 'your strongest dimension').lower()} as an organising feature in your AI relationship. "
        "When a behaviour already feels useful and coherent, it often remains part of the working rhythm because there is little friction pushing it to change. "
        "What tends to remain stable is not just the behaviour, but the internal logic that makes it feel sufficient."
    )


def overall_outlook_fallback(data: Dict[str, Any]) -> str:
    high = data.get("highest_dimension") or {}
    monitor = data.get("monitoring_anchor") or {}

    return (
        "Overall, your profile is best read as a pattern to stay aware of, not a problem to solve. "
        f"{high.get('label', 'Your strongest dimension')} gives the report its main anchor, while {monitor.get('label', 'one area')} is worth holding in view as usage evolves. "
        "Research consistently shows that people's sense of identity remains remarkably stable, even as the way they think with AI gradually evolves. "
        "What this report offers is not a prediction, but a clearer view of the pattern you have today. How that relationship develops from here remains entirely yours to shape."
    )


# ---------------------------------------------------------------------
# Section 11
# ---------------------------------------------------------------------

def build_next_steps(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Section 11 is intentionally deterministic.

    It closes the report by moving from benchmark awareness to user ownership
    without adding prescription, optimisation language, or another API call.
    """
    return {
        "title": "Your Next Steps",
        "subtitle": "Use this report as a mirror for awareness, clarity, and choice.",
        "action": {
            "step": "STEP 1",
            "title": "Test this report with your AI",
            "intro": "Upload this full report to whichever AI you use most.",
            "prompt_label": "Ask your AI",
            "prompt": (
                "Does this report ring true to how we work together? "
                "Where does it match your sense of how I use you? "
                "Where does it miss?"
            ),
            "reflection_intro": "Then simply compare:",
            "reflection_points": [
                "What AI agrees with",
                "What surprises you",
                "What you disagree with",
            ],
            "privacy_note": "Your data stays with you. Nothing from that conversation returns to HCI.",
        },
        "awareness": {
            "title": "What This Awareness Does",
            "body": [
                "Awareness creates clarity. Clarity makes intentional choices possible.",
                "This report shows where you sit — how you use AI, what you rely on it for, where you are distinctive, and where you are typical. That positioning is neutral. What matters is what you do with it.",
                "The people who flourish with AI are the ones who stay aware of their own pattern and adjust their relationship as it evolves — not through willpower or rigid rules, but through genuine understanding of what serves them.",
            ],
        },
        "alignment": {
            "title": "Stay Aligned With Your Pattern",
            "body": [
                "Return to this assessment whenever your relationship with AI feels like it has shifted significantly.",
                "Retesting lets you notice what has actually changed in your pattern, not only what you think has changed. It is the clearest way to stay within the boundaries that help you flourish.",
            ],
        },
        "mirror": {
            "title": "This Report As A Mirror",
            "intro": "This report is intended to be a mirror rather than a judgement.",
            "points": [
                "your benchmark positioning",
                "your distinctive patterns",
                "your behavioural relationships",
            ],
            "closing": "What you do with that clarity is entirely yours.",
        },
    }
