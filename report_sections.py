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
        "title": "Executive Summary",
        "statement": (
            "Your relationship with AI is beginning to form a behavioural pattern.\n\n"
            "This report compares that pattern with more than 10,500 participants across 21 Human Clarity Institute research studies, helping you understand where your AI use is typical, where it is distinctive, and which aspects of your relationship with AI are changing most rapidly.\n\n"
            "Rather than measuring behaviour as good or bad, this report maps how you currently work with AI and provides evidence you can use to make more informed decisions as that relationship evolves."
        ),
        "findings": narrative_block(report_data, "opening_findings", opening_fallback(report_data)),
    }


def opening_fallback(report_data: Dict[str, Any]) -> str:
    inputs = report_data.get("synthesis_inputs") or {}
    most = inputs.get("most_distinctive_variable") or {}
    gap = inputs.get("largest_perception_gap") or {}
    combo = inputs.get("top_rare_combination") or {}
    top_dims = inputs.get("top_dimensions") or []

    if most:
        f1_data = f"You answered {most.get('answer_display')} to “{most.get('question_text')}”, placing this response at the {most.get('percentile_label')} percentile."
        f1_interp = "This is the strongest individual signal in your profile. It shows where your AI behaviour differs most clearly from the benchmark population."
        f1_why = "The most distinctive response often reveals the part of AI use that has become most visible in daily behaviour."
    else:
        f1_data = "No single response dominated the profile."
        f1_interp = "The clearest signal is the overall shape of the profile rather than one unusually high or low answer."
        f1_why = "Some profiles are defined by one standout behaviour; others are defined by consistency across dimensions."

    if gap:
        question = gap.get("question") or gap.get("key") or "one self-perception item"
        perceived = gap.get("perceived_answer") or gap.get("perceived") or "your self-estimate"
        actual = gap.get("actual_percentile")
        f2_data = f"Around {question}, you described yourself as “{perceived}”, while the benchmark places you around the {ordinal(actual)} percentile."
        f2_interp = "This shows a meaningful difference between how your AI use feels from the inside and where your responses sit in the wider benchmark."
        f2_why = "Perception gaps matter because AI use often normalises itself; what becomes routine may stop feeling distinctive."
    else:
        f2_data = "Your self-perception broadly aligns with your benchmark positioning."
        f2_interp = "This suggests you are noticing your own AI pattern with reasonable accuracy."
        f2_why = "Alignment matters because accurate self-perception makes later choices about AI use more deliberate."

    if combo:
        f3_data = f"The most unusual combination detected is {combo.get('label_1')} + {combo.get('label_2')}, appearing in roughly {combo.get('rarity_percent')}% of participants."
        f3_interp = "This pairing shows where two parts of your AI behaviour interact in a way that is less common in the benchmark."
        f3_why = "Combinations matter because they reveal pattern shape, not just isolated scores."
    else:
        labels = [d.get("label") for d in top_dims[:4] if isinstance(d, dict) and d.get("label")]
        f3_data = "No rare dimensional combination was detected." + (f" Your highest dimensions are {', '.join(labels)}." if labels else "")
        f3_interp = "Your profile is less defined by unusual tension between dimensions and more by the way several dimensions move in the same direction."
        f3_why = "A coherent profile can be just as meaningful as a rare one, because it shows the overall direction of your AI relationship."

    blocks = [
        ("Your relationship with AI has become load-bearing", f1_data, f1_interp, f1_why),
        ("Your self-perception sits slightly behind your actual pattern", f2_data, f2_interp, f2_why),
        ("Your dimensions move together as a coherent whole", f3_data, f3_interp, f3_why),
    ]

    return "\n\n".join(
        f"Headline: {headline}\nData: {data}\nInterpretation: {interp}\nWhy it matters: {why}"
        for headline, data, interp, why in blocks
    )


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

    return {
        "title": "How Typical Is Your AI Behaviour?",
        "distinctive": enrich(source.get("distinctive", [])),
        "typical": enrich(source.get("typical", [])),
        "moderate": enrich(source.get("moderate", [])),
        "all": enrich(source.get("all", [])),
    }


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

    fallback = (
        "Your self-perception and actual benchmark positioning are shown above. "
        "The most useful way to read this section is not as a correction, but as a comparison between how your AI use feels from the inside and where your responses place you in the wider benchmark."
    )

    return {
        "title": "Perception Gap Analysis",
        "self_perception": source.get("self_perception", []),
        "gaps": source.get("gaps", []),
        "largest_gap": source.get("largest_gap"),
        "has_significant_gap": source.get("has_significant_gap", False),
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

    return {
        "title": "If Nothing Changes",
        "likely_to_continue": narrative_block(report_data, "likely_to_continue", likely_to_continue_fallback(data)),
        "strengths_likely_to_deepen": enrich_strengths(data.get("strengths_likely_to_deepen", [])),
        "areas_worth_monitoring": enrich_monitoring(data.get("areas_worth_monitoring", [])),
        "overall_outlook": narrative_block(report_data, "overall_outlook", overall_outlook_fallback(data)),
    }


def enrich_strengths(strengths):
    out = []
    for d in strengths or []:
        dim = d.get("key") or d.get("dimension")
        item = dict(d)
        item["strength_deepening"] = STRENGTH_DEEPENING_COPY.get(dim, {})
        out.append(item)
    return out


def enrich_monitoring(items):
    out = []
    for d in items or []:
        dim = d.get("key") or d.get("dimension")
        item = dict(d)
        item["monitoring"] = MONITORING_COPY.get(dim, {})
        out.append(item)
    return out


def likely_to_continue_fallback(data: Dict[str, Any]) -> str:
    high = data.get("highest_dimension") or {}
    if not high:
        return "If your current AI usage stays steady, the main pattern likely to continue is the overall shape already visible in your profile."

    return (
        f"Based on your current pattern, {high.get('label', 'your strongest dimension').lower()} is likely to remain one of the clearest organising features in your AI relationship. "
        f"It sits at the {ordinal(high.get('percentile'))} percentile, which means it is already strongly visible in the benchmark."
    )


def overall_outlook_fallback(data: Dict[str, Any]) -> str:
    high = data.get("highest_dimension") or {}
    monitor = data.get("monitoring_anchor") or {}

    return (
        f"Overall, your profile is best read as a pattern to stay aware of, not a problem to solve. "
        f"{high.get('label', 'Your strongest dimension')} gives the report its main anchor. "
        f"{monitor.get('label', 'One area')} is worth monitoring as usage evolves. What happens next remains yours to shape."
    )


# ---------------------------------------------------------------------
# Section 11
# ---------------------------------------------------------------------

def build_next_steps(report_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": "Your Next Steps",
        "items": NEXT_STEPS,
    }
