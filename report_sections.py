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
    deep_dive = build_deep_dive(report_data)
    perception = build_perception_gap(report_data)
    human_capital = build_human_capital(report_data)
    trajectory = build_if_nothing_changes(report_data)
    looking_forward = build_looking_forward(report_data)
    closing_reflection = build_closing_reflection(report_data)

    return {
        # Legacy renderer keys
        "opening": opening,
        "dashboard": dashboard,
        "typicality": typicality,
        "rare": rare,
        "story": story,
        "questions": questions,
        "distinctive": distinctive,
        "deep_dive": deep_dive,
        "perception": perception,
        "human_capital": human_capital,
        "trajectory": trajectory,
        "looking_forward": looking_forward,
        "closing_reflection": closing_reflection,

        # Explicit locked section keys
        "section_1_dashboard": dashboard,
        "section_3_typicality": typicality,
        "section_4_rare_combinations": rare,
        "section_5_behaviour_story": story,
        "section_6_question_profile": questions,
        "section_7_distinctive_responses": distinctive,
        "section_8_dimension_deep_dives": deep_dive,
        "section_9_perception_gap": perception,
        "section_10_human_capital": human_capital,
        "section_11_trajectory": trajectory,
        "section_12_looking_forward": looking_forward,
        "section_13_closing_reflection": closing_reflection,
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
# Dimension Deep Dives
# ---------------------------------------------------------------------

def build_deep_dive(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dimension reference section.

    This is Claude-written when available, with deterministic fallback.
    """
    return {
        "title": "Dimension Deep Dives",
        "subtitle": "A closer look at each behavioural dimension in your benchmark profile.",
        "body": narrative_block(report_data, "deep_dive", deep_dive_fallback(report_data)),
    }


def deep_dive_fallback(report_data: Dict[str, Any]) -> str:
    dims = report_data.get("dimensions") or {}
    if not dims:
        return "No dimension data was available for the Dimension Deep Dives section."

    parts = []
    for dim in DIMENSION_ORDER:
        d = dims.get(dim) or {}
        if not d:
            continue
        label = d.get("label") or DIMENSION_LABELS.get(dim, dim)
        definition = d.get("definition") or DIMENSION_DEFINITIONS.get(dim, "")
        percentile = d.get("percentile")
        position = d.get("position") or percentile_position(percentile)
        parts.append(
            f"{label}\n"
            f"This dimension measures {definition.lower()}. "
            f"Your result sits at the {ordinal(percentile)} percentile, placing it {str(position).lower()} relative to the benchmark. "
            "This gives one focused perspective on your relationship with AI and is most useful when interpreted alongside the other HCI dimensions."
        )

    return "\n\n".join(parts) if parts else "No dimension data was available for the Dimension Deep Dives section."

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
        "intro": "The responses below contributed most strongly to the overall shape of your benchmark profile. Together they provide the clearest evidence supporting the conclusions described throughout the earlier sections of this report.",
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
        "This section compares how you see your own AI relationship with the measured benchmark pattern from your assessment. "
        "It is a reflective comparison, not a correction or judgement."
    )

    def area_from_question(item: Dict[str, Any]) -> Dict[str, str]:
        text = str(item.get("question") or "").lower()
        if "dependent" in text or "dependence" in text:
            return {"area": "AI Dependence", "construct": "Dependence construct", "copy": "Based on your responses across the assessment mapped to AI dependence."}
        if "rely" in text or "reliance" in text:
            return {"area": "AI Reliance", "construct": "Reliance dimension", "copy": "Based on your responses across the assessment mapped to AI reliance."}
        return {"area": "AI Use", "construct": "Usage frequency", "copy": "Based on your reported usage frequency and wider assessment pattern."}

    def direction(answer: Any) -> str:
        text = str(answer or "").lower()
        if any(t in text for t in ["much more", "somewhat more", "more than", "higher", "above"]): return "higher"
        if any(t in text for t in ["much less", "somewhat less", "less than", "lower", "below"]): return "lower"
        if any(t in text for t in ["same", "average", "about the same", "similar"]): return "about average"
        return "not stated"

    def measured_direction(percentile: Any) -> str:
        try: p = float(percentile)
        except Exception: return "not available"
        if p >= 71: return "higher"
        if p <= 40: return "lower"
        return "about average"

    def interpretation(area: str, self_dir: str, measured_dir: str) -> str:
        lower = area.lower()
        if self_dir == measured_dir:
            return f"Your self-view broadly matches your measured {lower}."
        if self_dir in ("lower", "about average") and measured_dir == "higher":
            return "Your measured pattern suggests this area is more elevated than it feels from the inside."
        if self_dir == "higher" and measured_dir in ("lower", "about average"):
            return "Your measured pattern suggests this area is less elevated than it feels from the inside."
        return f"Your self-view and measured {lower} sit in different places."

    cards = []
    for idx, item in enumerate(self_perception, 1):
        area = area_from_question(item)
        self_dir = direction(item.get("answer"))
        measured_dir = measured_direction(item.get("actual_percentile"))
        cards.append({**item, "index": idx, "area": area["area"], "construct": area["construct"], "measured_copy": area["copy"], "assessment_response_count": 39, "self_direction": self_dir, "measured_direction": measured_dir, "interpretation": interpretation(area["area"], self_dir, measured_dir)})

    return {
        "title": "How You See Yourself",
        "subtitle": "Comparing your self-perception with your measured AI behaviour.",
        "intro": "You rated how you think you compare with most people. Below, that self-view is placed beside your measured benchmark pattern, offering a second perspective on your relationship with AI.",
        "self_perception": cards,
        "gaps": source.get("gaps", []),
        "largest_gap": source.get("largest_gap"),
        "has_significant_gap": source.get("has_significant_gap", False),
        "narrative_heading": "What this comparison suggests",
        "narrative": narrative_block(report_data, "perception_gap_narrative", fallback),
    }


# ---------------------------------------------------------------------
# Section 10
# ---------------------------------------------------------------------

def build_human_capital(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Section 10: Your Human Capital.

    Pure presentation assembly. This section does not calculate, rank, infer,
    or translate capabilities. It only packages the Human Capital narrative
    object produced by the single Claude Human Capital call.
    """
    narrative = (report_data.get("narrative_blocks") or {}).get("human_capital") or {}
    if not isinstance(narrative, dict):
        narrative = {}

    return {
        "title": "Your Human Capital",
        "subtitle": (
            "Translating your behavioural benchmark into the human capabilities "
            "your current relationship with AI appears to be strengthening, "
            "preserving, or placing under gradual pressure."
        ),
        "introduction": (
            "Your benchmark profile describes how you currently relate to AI.\n\n"
            "This section translates those behavioural patterns into the human capabilities they appear to support, maintain, or gradually influence.\n\n"
            "These are not fixed traits or judgements.\n\n"
            "They are capacities that are actively exercised through your current relationship with AI and may strengthen, remain stable, or gradually change over time."
        ),
        "capabilities_developing": narrative.get("capabilities_developing", []),
        "worth_protecting": narrative.get("worth_protecting", []),
        "worth_watching": narrative.get("worth_watching", []),
        "human_capital_priorities": narrative.get("human_capital_priorities", []),
        "closing": narrative.get("closing", ""),
    }



# ---------------------------------------------------------------------
# Section 11
# ---------------------------------------------------------------------

def build_looking_forward(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source = {x.get("dimension"): x for x in report_data.get("what_to_protect", [])}
    items = []

    # Looking Forward is intentionally deterministic. These observation cards
    # reuse the Human Skills / What To Protect structure without adding advice,
    # prediction, scoring, or Claude generation.
    short_intros = {
        "verification": (
            "Most people verify AI outputs before acting. Over time, however, checking can become mentally demanding, "
            "leading many people to verify only what feels important or high-risk."
        ),
        "human_agency": (
            "Agency usually remains strong at the identity level, but the process can still drift. Small suggestions, "
            "defaults, and framings can quietly shape decisions before you fully notice."
        ),
        "emotional_regulation": (
            "AI can offer a useful space for relief, support, or reflection. The key distinction is whether it supplements "
            "human connection or gradually begins to replace it."
        ),
        "thought_partnership": (
            "AI works best as a thinking partner: something to develop ideas with, not instead of your own thinking. "
            "The important question is whether it is challenging your thought or quietly replacing it."
        ),
    }

    def clean_title(title: Any) -> str:
        text = str(title or "").strip()
        lower = text.lower()
        prefix = "what to notice:"
        if lower.startswith(prefix):
            return text[len(prefix):].strip()
        return text

    def position_badge(positioning: Any) -> str:
        text = str(positioning or "").lower()
        if "high" in text:
            return "HIGH"
        if "middle" in text or "centre" in text or "center" in text:
            return "MIDDLE"
        if "low" in text:
            return "LOW"
        return "CURRENT"

    for dim, template in WHAT_TO_PROTECT_TEMPLATES.items():
        data = source.get(dim, {})
        percentile = data.get("percentile")
        positioning = data.get("positioning") or protect_position(percentile)
        title = clean_title(template.get("title"))
        items.append({
            "dimension": dim,
            "title": title,
            "capacity": DIMENSION_LABELS[dim],
            "percentile": percentile,
            "positioning": positioning,
            "position_badge": position_badge(positioning),
            "intro": short_intros.get(dim) or template.get("intro", ""),
            "watch": template.get("watch", []),
            "research": template.get("research", ""),
            "closing": template.get("closing", ""),
        })

    return {
        "title": "Looking Forward",
        "subtitle": (
            "Your relationship with AI will continue evolving, but not all changes happen at once. "
            "The observations below are not predictions. They are patterns that people with similar profiles "
            "often become aware of first. Whether they happen—and whether they matter—is something only you "
            "can observe over time."
        ),
        "items": items,
        "closing": (
            "These observations are not a checklist and they are not expectations. They simply highlight the kinds "
            "of subtle shifts that often emerge gradually rather than suddenly. Whether they appear in your own "
            "experience is something only you can observe over time—which is why measuring again in the future can be valuable."
        ),
        "final_line": "You decide.",
    }


# ---------------------------------------------------------------------
# Legacy unused builder: previous Section 9
# ---------------------------------------------------------------------

def build_what_to_protect(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source = {x.get("dimension"): x for x in report_data.get("what_to_protect", [])}
    items = []

    # Section 9 is intentionally deterministic. These short introductions keep
    # the four universal capacity cards scannable while preserving the locked
    # research meaning from the templates.
    short_intros = {
        "verification": (
            "Most people verify AI outputs before acting. Over time, however, checking can become mentally demanding, "
            "leading many people to verify only what feels important or high-risk."
        ),
        "human_agency": (
            "Agency usually remains strong at the identity level, but the process can still drift. Small suggestions, "
            "defaults, and framings can quietly shape decisions before you fully notice."
        ),
        "emotional_regulation": (
            "AI can offer a useful space for relief, support, or reflection. The key distinction is whether it supplements "
            "human connection or gradually begins to replace it."
        ),
        "thought_partnership": (
            "AI works best as a thinking partner: something to develop ideas with, not instead of your own thinking. "
            "The important question is whether it is challenging your thought or quietly replacing it."
        ),
    }

    def clean_title(title: Any) -> str:
        text = str(title or "").strip()
        lower = text.lower()
        prefix = "what to notice:"
        if lower.startswith(prefix):
            return text[len(prefix):].strip()
        return text

    def position_badge(positioning: Any) -> str:
        text = str(positioning or "").lower()
        if "high" in text:
            return "HIGH"
        if "middle" in text or "centre" in text or "center" in text:
            return "MIDDLE"
        if "low" in text:
            return "LOW"
        return "CURRENT"

    for dim, template in WHAT_TO_PROTECT_TEMPLATES.items():
        data = source.get(dim, {})
        percentile = data.get("percentile")
        positioning = data.get("positioning") or protect_position(percentile)
        title = clean_title(template.get("title"))
        items.append({
            "dimension": dim,
            "title": title,
            "capacity": DIMENSION_LABELS[dim],
            "percentile": percentile,
            "positioning": positioning,
            "position_badge": position_badge(positioning),
            "intro": short_intros.get(dim) or template.get("intro", ""),
            "watch": template.get("watch", []),
            "research": template.get("research", ""),
            "closing": template.get("closing", ""),
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
    """
    Section 11: Looking Ahead.

    This section replaces the older "If Nothing Changes" trajectory section.
    Its job is not to add another interpretation layer. It gives the participant
    a compact measurement roadmap: what looks likely to hold, what is most
    sensitive to change, what behavioural tipping points to notice, and which
    questions are worth carrying into the next measurement.
    """
    data = report_data.get("if_nothing_changes") or {}
    hold = enrich_hold_signals(data.get("strengths_likely_to_deepen", []))
    sensitive = enrich_sensitive_signals(data.get("areas_worth_monitoring", []))

    return {
        "title": "What Will Be Most Interesting to Measure Next Time",
        "subtitle": "The signals that may tell the clearest story as your relationship with AI continues evolving.",
        "signals_likely_to_hold": hold,
        "signals_most_sensitive_to_change": sensitive,
        "intro": narrative_block(report_data, "looking_ahead_intro", looking_ahead_intro_fallback(data)),
        "tipping_points": narrative_block(report_data, "behavioural_tipping_points", behavioural_tipping_points_fallback()),
        "measurement_questions": narrative_block(report_data, "measurement_questions", measurement_questions_fallback()),
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


def enrich_hold_signals(items):
    out = []
    for d in items or []:
        dim = d.get("key") or d.get("dimension")
        item = dict(d)
        item["hold_copy"] = hold_signal_copy(dim)
        out.append(item)
    return out[:3]


def enrich_sensitive_signals(items):
    out = []
    for d in items or []:
        dim = d.get("key") or d.get("dimension")
        item = dict(d)
        item["sensitive_copy"] = sensitive_signal_copy(dim)
        out.append(item)
    return out[:3]


def hold_signal_copy(dim: str) -> str:
    copy = {
        "trust": "This currently appears to be part of the participant's settled working posture toward AI. It may change over time, but it is less likely to shift quickly unless accuracy experiences or verification habits change substantially.",
        "decision_delegation": "This currently appears to reflect a relatively established boundary around how much decision authority AI is given. It may change, but the present pattern suggests the boundary is not simply accidental.",
        "thought_partnership": "This currently appears to be an established part of how the participant develops ideas and works through complexity. It is likely to remain informative because it shapes the way AI enters the thinking process.",
        "human_agency": "This currently appears to be one of the stabilising features of the profile: the participant experiences AI as something they direct rather than something that owns the decision process.",
        "reliance": "This currently appears to be a defining part of the participant's working relationship with AI. It may not shift quickly because embedded tools often become part of the normal operating environment.",
        "verification": "This currently appears to be part of the participant's checking rhythm. It may hold where accuracy remains important, but it is still worth comparing carefully at the next measurement.",
        "emotional_regulation": "This currently appears to reflect a clear boundary around AI's role in emotional life. Where this boundary is strong, it can become one of the more stable features of the profile.",
        "disclosure": "This currently appears to reflect a bounded approach to personal sharing with AI. It may remain stable where privacy habits and role boundaries are already clear.",
        "social_transparency": "This currently appears to reflect a settled pattern around how visible AI use is to others. It may change as norms shift, but it is not usually the fastest-moving signal.",
    }
    return copy.get(dim, "This currently appears to be one of the more established features of the participant's relationship with AI. It may still evolve, but it is less likely to be the first signal to move.")


def sensitive_signal_copy(dim: str) -> str:
    copy = {
        "verification": "Checking behaviour can become more selective as AI use becomes familiar, fast, and cognitively easy. Small changes here can meaningfully alter how much AI shapes thinking before accuracy is tested.",
        "reliance": "Reliance can deepen quietly when AI becomes part of the default workflow. The important change is often not more use, but AI becoming harder to separate from ordinary thinking and work.",
        "human_agency": "Agency is worth re-measuring because a strong identity-level sense of control can remain intact while smaller process-level shifts occur underneath it.",
        "trust": "Trust can shift gradually when AI outputs repeatedly feel useful. The meaningful signal is whether confidence grows faster than the checking habits that keep it calibrated.",
        "decision_delegation": "Decision delegation can change when AI moves from providing input to shaping options, recommendations, or next steps that are accepted with less friction.",
        "thought_partnership": "Thought partnership can expand as AI moves earlier into idea formation, planning, and problem-solving. The key signal is whether AI becomes the starting point rather than the refinement stage.",
        "emotional_regulation": "Emotional regulation can change when AI becomes an easy first place to process stress, uncertainty, or overload. Even small increases can alter the role AI plays in daily life.",
        "disclosure": "Disclosure can shift as repeated use changes what feels normal to share. This signal is sensitive because privacy boundaries often move gradually rather than all at once.",
        "social_transparency": "Social transparency can change as the gap widens or narrows between actual AI use and what other people can see. This often reflects changing norms as much as personal preference.",
    }
    return copy.get(dim, "This is one of the areas where repeated AI use can create gradual change. It is worth comparing at the next measurement because small habit shifts may become visible over time.")


def looking_ahead_intro_fallback(data: Dict[str, Any]) -> str:
    return (
        "Your benchmark profile is a snapshot of your relationship with AI today, not a fixed description of who you are. "
        "The value of measuring again is not simply seeing whether individual scores rise or fall. It is noticing whether the behavioural architecture described throughout this report remains broadly intact or begins to change in ways that would otherwise be easy to miss."
    )


def behavioural_tipping_points_fallback() -> str:
    return (
        "Earlier AI initiation: Notice whether AI becomes the first place you begin thinking rather than a place where you refine an existing view.\n\n"
        "Reduced verification friction: Notice whether checking starts to feel less necessary, especially when outputs are fluent or familiar.\n\n"
        "Expanding role boundaries: Notice whether AI begins entering parts of work, decision-making, or personal life where it previously played little role."
    )


def measurement_questions_fallback() -> str:
    return (
        "Do I still form my own view before turning to AI?\n"
        "Has AI become part of more areas of everyday life than it was before?\n"
        "Am I verifying important outputs as consistently as I used to?\n"
        "Which of my current boundaries still feel clear?\n"
        "What feels different about my relationship with AI that I might not have noticed without measuring it?"
    )


# Backwards-compatible helpers retained for any older report_data or imports.
def build_trajectory_summary(strengths, monitoring):
    rows = []
    seen = set()
    for item in (strengths or []) + (monitoring or []):
        key = item.get("key") or item.get("dimension") or item.get("label")
        if key in seen:
            continue
        seen.add(key)
        rows.append({"label": item.get("label"), "position": trajectory_band(item.get("percentile")), "direction": "Worth re-measuring"})
        if len(rows) >= 4:
            break
    return rows


def enrich_strengths(strengths):
    return enrich_hold_signals(strengths)


def enrich_monitoring(items):
    return enrich_sensitive_signals(items)


def strength_research_summary(dim: str) -> str:
    return hold_signal_copy(dim)


def strength_deepening_summary(dim: str) -> str:
    return hold_signal_copy(dim)


def monitoring_position_sentence(dim: str, percentile) -> str:
    band = trajectory_band(percentile).lower()
    label = DIMENSION_LABELS.get(dim, "This dimension").lower()
    if band == "high":
        return f"{label.title()} currently sits at the high end of your profile."
    if band == "lower":
        return f"{label.title()} currently sits below the centre of the benchmark."
    return f"{label.title()} currently sits near the middle of the benchmark."


def monitoring_research_summary(dim: str) -> str:
    return sensitive_signal_copy(dim)


def monitoring_early_sign(dim: str) -> str:
    copy = {
        "verification": "Noticing checking becoming more selective or easier to skip.",
        "reliance": "Noticing AI becoming harder to separate from ordinary workflow.",
        "human_agency": "Noticing AI's framing appearing before your own first view is formed.",
        "trust": "Accepting AI outputs more quickly because they usually feel right.",
        "decision_delegation": "Letting AI-shaped recommendations move directly into action with less second-guessing.",
        "thought_partnership": "Finding it harder to develop a first position before consulting AI.",
        "emotional_regulation": "Turning to AI first when you feel stressed, uncertain, or overloaded.",
        "disclosure": "Sharing more personal context with AI than you would previously have expected.",
        "social_transparency": "Using AI more often than other people can see from the outside.",
    }
    return copy.get(dim, "Noticing the behaviour becoming more automatic than deliberate.")


def likely_to_continue_fallback(data: Dict[str, Any]) -> str:
    return looking_ahead_intro_fallback(data)


def overall_outlook_fallback(data: Dict[str, Any]) -> str:
    return behavioural_tipping_points_fallback()

# ---------------------------------------------------------------------
# Section 11
# ---------------------------------------------------------------------

def build_closing_reflection(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Final section: Closing Reflection.

    Pure presentation assembly. This section does not calculate, infer, or
    interpret. It packages the Closing Reflection narrative object produced by
    the single Claude Closing Reflection call.
    """
    narrative = (report_data.get("narrative_blocks") or {}).get("closing_reflection") or {}
    if not isinstance(narrative, dict):
        narrative = {}

    return {
        "title": "Closing Reflection",
        "introduction": (
            "Every benchmark profile answers many questions—but it also leaves one unanswered.\n\n"
            "Rather than ending with another recommendation, this report finishes with one question "
            "that appears most relevant to your current relationship with AI.\n\n"
            "There isn't a right answer today.\n\n"
            "The value comes from noticing how your answer evolves over time."
        ),
        "one_question": narrative.get("one_question", ""),
        "why_this_question_matters": narrative.get("why_this_question_matters", ""),
        "what_next_time": narrative.get("what_will_be_interesting_next_time", ""),
        "closing_reflection": narrative.get("closing_reflection", ""),
    }
