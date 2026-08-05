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
    DIMENSION_ORDER,
    DIMENSION_LABELS,
    DIMENSION_DEFINITIONS,
    ordinal,
    percentile_position,
    protect_position,
)


BENCHMARK_LABEL = "HCI participant benchmark"
BENCHMARK_FOUNDATION = "10,000+ participant responses across 21 HCI studies"


def normalise_position_text(value: Any) -> str:
    text = str(value or "").strip()
    return (
        text.replace("the population centre", "the HCI benchmark centre")
        .replace("population centre", "HCI benchmark centre")
        .replace("the benchmark population", "the HCI participant benchmark")
        .replace("benchmark population", "HCI participant benchmark")
    )


def benchmark_percentile_text(percentile: Any) -> str:
    try:
        return f"{ordinal(percentile)} percentile within the {BENCHMARK_LABEL}"
    except Exception:
        return f"position within the {BENCHMARK_LABEL}"


def safe_question_comparison_statement(item: Dict[str, Any]) -> str:
    answer = item.get("answer_display")
    if not answer or answer == "N/A":
        raw_answer = item.get("answer")
        answer = f"{raw_answer}/7" if raw_answer is not None else "No answer recorded"

    overall = item.get("percentile")
    frequency = item.get("percentile_frequency")

    if overall is not None and frequency is not None:
        return (
            f"You answered {answer}. Within the {BENCHMARK_LABEL}, this response "
            f"was at the {ordinal(overall)} percentile overall and the "
            f"{ordinal(frequency)} percentile among participants who use AI "
            "about as frequently as you."
        )
    if overall is not None:
        return (
            f"You answered {answer}. Within the {BENCHMARK_LABEL}, this response "
            f"was at the {ordinal(overall)} percentile overall. A comparable "
            "AI-use-frequency result was not available."
        )
    if frequency is not None:
        return (
            f"You answered {answer}. An overall comparison was not available, "
            f"but this response was at the {ordinal(frequency)} percentile among "
            "participants who use AI about as frequently as you."
        )
    return f"You answered {answer}. A benchmark comparison was not available for this item."


def sanitise_question_card(item: Dict[str, Any]) -> Dict[str, Any]:
    card = dict(item or {})
    card["comparison_statement"] = safe_question_comparison_statement(card)
    return card


def sanitise_dimension_item(item: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(item or {})
    if out.get("position"):
        out["position"] = normalise_position_text(out.get("position"))
    return out


def sanitise_dashboard_card(item: Dict[str, Any]) -> Dict[str, Any]:
    card = dict(item or {})
    percentile = card.get("percentile")
    card["plain_score"] = benchmark_percentile_text(percentile)
    card["benchmark_label"] = BENCHMARK_LABEL
    return card


def safe_typicality_sentence(dimension: Any, percentile: Any) -> str:
    label = DIMENSION_LABELS.get(str(dimension), str(dimension or "This dimension"))
    try:
        p = int(round(float(percentile)))
    except Exception:
        p = 50

    if p >= 76:
        return (
            f"{label} is one of the more elevated parts of your current profile "
            f"within the {BENCHMARK_LABEL}."
        )
    if p <= 24:
        return (
            f"{label} is one of the lower-positioned parts of your current profile "
            f"within the {BENCHMARK_LABEL}."
        )
    return (
        f"{label} sits closer to the central range of the {BENCHMARK_LABEL} "
        "in your current responses."
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
            "Your responses form a current pattern across nine aspects of how you report using AI.\n\n"
            f"This report compares that pattern with the {BENCHMARK_LABEL}, informed by "
            f"{BENCHMARK_FOUNDATION}. It shows where your responses are broadly typical, "
            "where they differ, and which combinations contribute most to the overall shape of your profile.\n\n"
            "The report does not judge the pattern as good or bad. It provides a structured "
            "reference point for understanding your current responses and for comparison if "
            "you complete the assessment again later."
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
            f"The strongest individual signal in your current profile is your response to: "
            f"“{most.get('question_text')}”. You answered {most.get('answer_display')}, "
            f"placing this response at the {most.get('percentile_label')} percentile within "
            f"the {BENCHMARK_LABEL}. It is the clearest single point of difference in your "
            "question-level responses and should be interpreted alongside the wider profile."
        )
    else:
        most_text = (
            "No single response dominates your profile. The more informative feature is the "
            "overall shape created by several dimensions appearing together."
        )

    if gap:
        question = gap.get("question") or gap.get("key") or "one self-perception item"
        perceived = gap.get("perceived_answer") or gap.get("perceived") or "your self-estimate"
        actual = gap.get("actual_percentile")
        gap_text = (
            f"There is also a difference between your self-estimate and your assessment-based "
            f"benchmark position for {question}. You described yourself as “{perceived}”, while "
            f"your responses place you around the {ordinal(actual)} percentile within the "
            f"{BENCHMARK_LABEL}. This is a comparison between two forms of self-report, not a "
            "correction of your self-understanding."
        )
    else:
        gap_text = (
            "Your self-estimate broadly aligns with your assessment-based benchmark position. "
            "This means the two forms of self-report point in a similar direction."
        )

    if combo:
        combo_text = (
            f"The clearest combination signal is {combo.get('label_1')} and "
            f"{combo.get('label_2')}, a pairing reported by roughly "
            f"{combo.get('rarity_percent')}% of participants in the relevant benchmark data. "
            "Its value lies in showing how two reported dimensions appear together; it does "
            "not establish why the combination exists or what outcome it will produce."
        )
    else:
        top_labels = [d.get("label") for d in top_dims[:3] if isinstance(d, dict) and d.get("label")]
        low_labels = [d.get("label") for d in low_dims[:2] if isinstance(d, dict) and d.get("label")]
        combo_text = (
            "No rare dimensional combination was detected. The current profile is instead "
            "defined by its overall balance: "
            + (f"higher dimensions include {', '.join(top_labels)}, " if top_labels else "several dimensions sit in a similar range, ")
            + (f"while lower dimensions include {', '.join(low_labels)}. " if low_labels else "")
            + "This remains informative without implying that one dimension causes another."
        )

    return "\n\n".join([
        "Your most distinctive response\n" + most_text,
        "How your self-perception compares\n" + gap_text,
        "The shape of the wider pattern\n" + combo_text,
    ])



def build_dashboard(report_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": "Your Reported AI Behaviour Pattern",
        "subtitle": f"How your responses compare across nine dimensions within the {BENCHMARK_LABEL}",
        "cards": [
            sanitise_dashboard_card(card)
            for card in (report_data.get("dashboard") or [])
            if isinstance(card, dict)
        ],
    }


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
        position = normalise_position_text(
            d.get("position") or percentile_position(percentile)
        )
        parts.append(
            f"{label}\n"
            f"This dimension reflects {definition.lower()}. "
            f"Your result is at the {ordinal(percentile)} percentile within the "
            f"{BENCHMARK_LABEL}, placing it {str(position).lower()}. "
            "It provides one perspective on your current self-reported pattern and is "
            "most useful when interpreted alongside the other HCI dimensions."
        )

    return "\n\n".join(parts) if parts else "No dimension data was available for the Dimension Deep Dives section."


def build_typicality(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source = report_data.get("typicality") or {}

    # Attach light deterministic interpretation from report_templates.py.
    def enrich(items):
        out = []
        for item in items or []:
            enriched = dict(item)
            if not enriched.get("interpretation"):
                enriched["interpretation"] = safe_typicality_sentence(
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
        "subtitle": "Where your responses stand out and where they remain closer to the HCI participant benchmark",
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
            "Your profile contains a smaller number of dimensions that stand out against "
            f"a wider group that remains closer to the {BENCHMARK_LABEL}. The most useful "
            "reading is therefore to focus on the specific dimensions carrying most of the "
            "difference rather than treating the whole profile as unusual."
        )

    if distinctive and not benchmark_range:
        return (
            "Your profile differs from the benchmark across several dimensions rather than "
            "through one isolated response. The overall shape is therefore more informative "
            "than any single high or low score."
        )

    return (
        f"Your profile sits largely within the central range of the {BENCHMARK_LABEL}. "
        "That does not make it less meaningful; the useful information lies in the balance "
        "between dimensions and the specific responses that contribute to it."
    )


def build_rare_combinations(report_data: Dict[str, Any]) -> Dict[str, Any]:
    combos = report_data.get("rare_combinations") or []

    fallback = (
        "No rare dimensional combinations were detected in your profile. "
        "The profile remains useful because its overall balance and response pattern can still be compared with the HCI participant benchmark."
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
        f"The most elevated dimension in your current responses is "
        f"{top.get('label', '').lower()}, at the {ordinal(top.get('percentile'))} "
        f"percentile within the {BENCHMARK_LABEL}. It is one of the clearest organising "
        "features of the profile."
    ]

    if second:
        parts.append(
            f"This appears alongside {second.get('label', '').lower()}, at the "
            f"{ordinal(second.get('percentile'))} percentile. Together, these dimensions "
            "help describe the current shape of your reported pattern without establishing "
            "why the relationship exists."
        )

    parts.append(
        f"At the other end, {low.get('label', '').lower()} is at the "
        f"{ordinal(low.get('percentile'))} percentile. The contrast is useful because the "
        "assessment describes a profile rather than assigning a fixed user type."
    )

    return "\n\n".join(parts)



def build_question_profile(report_data: Dict[str, Any]) -> Dict[str, Any]:
    questions = report_data.get("questions") or []
    dimensions = report_data.get("dimensions") or {}
    groups = []

    for dim in DIMENSION_ORDER:
        dimension_data = dimensions.get(dim) or {}
        groups.append({
            "dimension": dim,
            "label": dimension_data.get("label") or DIMENSION_LABELS[dim],
            "definition": dimension_data.get("definition") or DIMENSION_DEFINITIONS[dim],
            "questions": [
                sanitise_question_card(q)
                for q in questions
                if isinstance(q, dict) and q.get("dimension") == dim
            ],
        })

    return {
        "title": "Your Question-Level Profile",
        "subtitle": f"How your individual responses compare within the {BENCHMARK_LABEL}",
        "groups": groups,
    }



def build_distinctive_responses(report_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": "Your Most Distinctive Responses",
        "intro": (
            "These responses sit furthest from the centre of the HCI participant benchmark "
            "and contribute strongly to the shape of your current profile. They are "
            "question-level self-report evidence, not proof of a fixed trait or outcome."
        ),
        "responses": [
            sanitise_question_card(item)
            for item in (report_data.get("distinctive_responses") or [])[:7]
            if isinstance(item, dict)
        ],
        "narrative": narrative_block(report_data, "distinctive_responses_narrative", ""),
    }



def build_perception_gap(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source = report_data.get("perception_gap") or {}
    self_perception = source.get("self_perception", [])

    fallback = (
        "This section compares your direct self-estimate with the benchmark position "
        "derived from your other assessment responses. Both are forms of self-report. "
        "The comparison is intended for reflection, not correction or judgement."
    )

    def area_from_question(item: Dict[str, Any]) -> Dict[str, str]:
        text = str(item.get("question") or "").lower()
        if "dependent" in text or "dependence" in text:
            return {
                "area": "AI Dependence",
                "construct": "Dependence-related response pattern",
                "copy": "Based on your responses to the assessment items most directly related to AI dependence."
            }
        if "rely" in text or "reliance" in text:
            return {
                "area": "AI Reliance",
                "construct": "Reliance dimension",
                "copy": "Based on your self-reported responses within the Reliance dimension."
            }
        return {
            "area": "AI Use",
            "construct": "Reported usage frequency",
            "copy": "Based on your reported usage frequency within the HCI participant benchmark."
        }

    def direction(answer: Any) -> str:
        value = str(answer or "").lower()
        if any(t in value for t in ["much more", "somewhat more", "more than", "higher", "above"]):
            return "higher"
        if any(t in value for t in ["much less", "somewhat less", "less than", "lower", "below"]):
            return "lower"
        if any(t in value for t in ["same", "average", "about the same", "similar"]):
            return "about average"
        return "not stated"

    def benchmark_direction(percentile: Any) -> str:
        try:
            p = float(percentile)
        except Exception:
            return "not available"
        if p >= 71:
            return "higher"
        if p <= 40:
            return "lower"
        return "about average"

    def interpretation(area: str, self_dir: str, benchmark_dir: str) -> str:
        lower = area.lower()
        if self_dir == benchmark_dir:
            return f"Your self-estimate broadly matches your assessment-based {lower} position."
        if self_dir in ("lower", "about average") and benchmark_dir == "higher":
            return f"Your assessment-based {lower} position is higher than your direct self-estimate."
        if self_dir == "higher" and benchmark_dir in ("lower", "about average"):
            return f"Your assessment-based {lower} position is lower than your direct self-estimate."
        return f"Your direct self-estimate and assessment-based {lower} position differ."

    cards = []
    for idx, item in enumerate(self_perception, 1):
        if not isinstance(item, dict):
            continue
        area = area_from_question(item)
        self_dir = direction(item.get("answer"))
        benchmark_dir = benchmark_direction(item.get("actual_percentile"))
        cards.append({
            **item,
            "index": idx,
            "area": area["area"],
            "construct": area["construct"],
            "measured_copy": area["copy"],
            "assessment_response_count": 39,
            "self_direction": self_dir,
            "measured_direction": benchmark_dir,
            "interpretation": interpretation(area["area"], self_dir, benchmark_dir),
        })

    return {
        "title": "How You See Yourself",
        "subtitle": "Comparing your direct self-estimate with your assessment-based benchmark position.",
        "intro": (
            "You rated how you think you compare with other people. That self-estimate is "
            "shown beside the position derived from your other assessment responses within "
            f"the {BENCHMARK_LABEL}. The two measures answer related but different questions."
        ),
        "self_perception": cards,
        "gaps": source.get("gaps", []),
        "largest_gap": source.get("largest_gap"),
        "has_significant_gap": source.get("has_significant_gap", False),
        "narrative_heading": "What this comparison may indicate",
        "narrative": narrative_block(report_data, "perception_gap_narrative", fallback),
    }



def build_human_capital(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Section 10: Your Human Capital.

    This section presents capability-related reflections derived from the
    participant's current self-reported pattern. It does not establish that a
    capability has objectively developed, weakened, or changed over time.
    """
    narrative = (report_data.get("narrative_blocks") or {}).get("human_capital") or {}
    if not isinstance(narrative, dict):
        narrative = {}

    return {
        "title": "Your Human Capital",
        "subtitle": (
            "A reflection on human capabilities that may be relevant to, or actively "
            "exercised within, your current reported pattern."
        ),
        "introduction": (
            "Your benchmark profile describes how you currently report relating to AI.\n\n"
            "This section considers the human capabilities connected with those responses, "
            "including authorship, judgement, verification, reflection, privacy boundaries "
            "and human connection.\n\n"
            "These are capability-related interpretations, not objective measurements of "
            "ability and not evidence that a capability has developed, weakened or remained "
            "stable over time."
        ),
        "capabilities_developing": narrative.get("capabilities_developing", []),
        "worth_protecting": narrative.get("worth_protecting", []),
        "worth_watching": narrative.get("worth_watching", []),
        "human_capital_priorities": narrative.get("human_capital_priorities", []),
        "closing": narrative.get("closing", ""),
        "capabilities_developing_label": "Capabilities active in your current pattern",
        "worth_protecting_label": "Capabilities that appear important within this pattern",
        "worth_watching_label": "Capabilities useful to compare at a later measurement",
        "human_capital_priorities_label": "Current capability-related themes",
    }



def build_looking_forward(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source = {
        x.get("dimension"): x
        for x in report_data.get("what_to_protect", [])
        if isinstance(x, dict)
    }

    content = {
        "verification": {
            "title": "Verification effort and selectivity",
            "intro": (
                "Your Verification result describes how consistently you report checking "
                "AI outputs. A later measurement can show whether that reported pattern "
                "remains similar or differs across tasks and contexts."
            ),
            "watch": [
                "Whether checking remains consistent across higher- and lower-stakes tasks",
                "Whether verification feels more or less effortful",
                "Whether familiar outputs receive different levels of checking",
            ],
            "research": (
                "Across relevant HCI studies, verification was widely reported while "
                "verification fatigue and selective checking were also common."
            ),
            "closing": "This is a comparison point, not a prediction that verification will decline.",
        },
        "human_agency": {
            "title": "Decision authorship and control",
            "intro": (
                "Your Human Agency result reflects your reported sense of control and "
                "authorship when AI is involved. A later measurement can compare whether "
                "that self-reported position remains similar."
            ),
            "watch": [
                "Whether you report forming an independent view before AI input",
                "Whether the final decision still feels authored by you",
                "Whether AI is mainly providing input or shaping the available options",
            ],
            "research": (
                "HCI findings show that strong reported responsibility can coexist with "
                "feeling subtly influenced by AI in some situations."
            ),
            "closing": "The current result does not establish identity stability or future change.",
        },
        "emotional_regulation": {
            "title": "The role AI plays in emotional support",
            "intro": (
                "Your Emotional Regulation result describes how often you report using AI "
                "for emotional support. A later comparison can show whether that role is "
                "similar, smaller or larger in your reported pattern."
            ),
            "watch": [
                "The situations in which AI is used for emotional support",
                "How AI support sits alongside support from other people",
                "Whether the role feels clearly bounded or broadly distributed",
            ],
            "research": (
                "A meaningful minority of HCI participants reported receiving some emotional "
                "support from AI while still viewing human emotional connection as distinct."
            ),
            "closing": "The result does not establish emotional substitution, dependency or reduced human connection.",
        },
        "thought_partnership": {
            "title": "Where AI enters the thinking process",
            "intro": (
                "Your Thought Partnership result reflects how often you report using AI to "
                "develop, challenge or refine ideas. A later measurement can compare where "
                "AI enters that process."
            ),
            "watch": [
                "Whether AI is used before or after an initial independent view is formed",
                "Whether AI mainly challenges, extends or generates the first framing",
                "How clearly the final view feels authored by you",
            ],
            "research": (
                "Thought Partnership is strongly associated with AI-use frequency in the HCI "
                "participant benchmark, while some participants also report authorship questions."
            ),
            "closing": "The result does not establish outsourced thinking or loss of independent reasoning.",
        },
    }

    items = []
    for dim in ["verification", "human_agency", "emotional_regulation", "thought_partnership"]:
        data = source.get(dim, {})
        item_content = content[dim]
        percentile = data.get("percentile")
        positioning = data.get("positioning") or protect_position(percentile)
        items.append({
            "dimension": dim,
            "title": item_content["title"],
            "capacity": DIMENSION_LABELS[dim],
            "percentile": percentile,
            "positioning": normalise_position_text(positioning),
            "position_badge": trajectory_band(percentile).upper(),
            "intro": item_content["intro"],
            "watch": item_content["watch"],
            "research": item_content["research"],
            "closing": item_content["closing"],
        })

    return {
        "title": "Looking Forward",
        "subtitle": (
            "Current signals that may provide useful reference points if you repeat "
            "the assessment later."
        ),
        "items": items,
        "closing": (
            "These observations do not predict what will change. They identify parts of "
            "the current profile that may be informative to compare at a later measurement."
        ),
        "final_line": "Your current profile is the reference point.",
    }



def build_what_to_protect(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Backwards-compatible legacy builder.

    It now returns the same participant-safe observation cards as Looking Forward
    rather than the older predictive or advisory template copy.
    """
    section = build_looking_forward(report_data)
    return {
        "title": "Capability-Related Reference Points",
        "subtitle": "Four current signals that may be useful to compare later",
        "items": section.get("items", []),
    }



def build_if_nothing_changes(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Section 11: Later Comparison.

    Legacy upstream field names are retained, but the visible section presents
    current reference signals rather than predicting stability or change.
    """
    data = report_data.get("if_nothing_changes") or {}
    current_high = enrich_hold_signals(data.get("strengths_likely_to_deepen", []))
    later_comparison = enrich_sensitive_signals(data.get("areas_worth_monitoring", []))

    return {
        "title": "What Will Be Useful to Compare Next Time",
        "subtitle": (
            "Current reference signals that may make a later measurement more informative."
        ),
        "signals_likely_to_hold": current_high,
        "signals_most_sensitive_to_change": later_comparison,
        "signals_likely_to_hold_label": "Current high signals",
        "signals_most_sensitive_to_change_label": "Areas for later comparison",
        "intro": narrative_block(
            report_data,
            "looking_ahead_intro",
            looking_ahead_intro_fallback(data),
        ),
        "tipping_points": narrative_block(
            report_data,
            "behavioural_tipping_points",
            behavioural_tipping_points_fallback(),
        ),
        "measurement_questions": narrative_block(
            report_data,
            "measurement_questions",
            measurement_questions_fallback(),
        ),
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
        "trust": "Trust is currently one of the more elevated or prominent parts of this profile. A later measurement can compare whether confidence in AI occupies a similar position.",
        "decision_delegation": "Decision Delegation currently provides a reference point for how much authority the participant reports giving AI. A later result can be compared without assuming the boundary is fixed.",
        "thought_partnership": "Thought Partnership currently describes a prominent part of how the participant reports developing ideas. A later measurement can compare whether AI enters the thinking process in a similar way.",
        "human_agency": "Human Agency currently reflects the participant's reported sense of control and authorship. The present result does not establish that this position is stable over time.",
        "reliance": "Reliance currently contributes strongly to the shape of the participant's reported AI relationship. A later comparison may show whether it occupies a similar position.",
        "verification": "Verification currently provides a reference point for the participant's reported checking pattern. A later measurement can compare consistency and effort without predicting decline.",
        "emotional_regulation": "Emotional Regulation currently describes the reported role AI plays in emotional support. It does not establish that the boundary is fixed or changing.",
        "disclosure": "Disclosure currently provides a reference point for how much personal information the participant reports sharing with AI.",
        "social_transparency": "Social Transparency currently describes how openly the participant reports discussing AI use in different contexts.",
    }
    return copy.get(
        dim,
        "This is currently one of the more prominent signals in the participant's profile and may provide a useful reference point for later comparison."
    )



def sensitive_signal_copy(dim: str) -> str:
    copy = {
        "verification": "A later measurement can compare how consistently verification is reported across familiar, unfamiliar, lower-stakes and higher-stakes tasks.",
        "reliance": "A later measurement can compare how central AI feels within ordinary work and thinking, without assuming that reliance will increase.",
        "human_agency": "A later measurement can compare the participant's reported sense of authorship, independent view formation and decision control.",
        "trust": "A later measurement can compare confidence in AI with reported checking across different task types.",
        "decision_delegation": "A later measurement can compare when AI provides input, shapes options or contributes directly to the final decision.",
        "thought_partnership": "A later measurement can compare whether AI is used mainly to refine an existing view or earlier in idea formation.",
        "emotional_regulation": "A later measurement can compare the reported role AI plays alongside other sources of emotional support.",
        "disclosure": "A later measurement can compare what kinds of personal information are reported as being shared and where boundaries sit.",
        "social_transparency": "A later measurement can compare the gap between reported AI use and how openly that use is discussed.",
    }
    return copy.get(
        dim,
        "This area may provide a useful comparison point at a later measurement without implying that change will occur."
    )



def looking_ahead_intro_fallback(data: Dict[str, Any]) -> str:
    return (
        "Your benchmark profile is a snapshot of your current self-reported relationship "
        "with AI, not a fixed description of who you are. Repeating the assessment may "
        "help show whether the overall pattern remains similar or differs. A single result "
        "cannot establish individual change, stability or direction."
    )



def behavioural_tipping_points_fallback() -> str:
    return (
        "Where thinking begins: A later comparison may examine whether AI is used before "
        "or after an initial independent view is formed.\n\n"
        "How verification is applied: A later comparison may examine whether checking "
        "differs by task familiarity, importance or effort.\n\n"
        "Which roles AI occupies: A later comparison may examine whether AI is reported "
        "in the same areas of work, decision-making and personal life."
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
        return f"{label.title()} currently sits at the high end of the HCI participant benchmark."
    if band == "lower":
        return f"{label.title()} currently sits below the centre of the HCI participant benchmark."
    return f"{label.title()} currently sits near the centre of the HCI participant benchmark."


def monitoring_research_summary(dim: str) -> str:
    return sensitive_signal_copy(dim)



def monitoring_early_sign(dim: str) -> str:
    copy = {
        "verification": "Whether reported checking differs across task types or becomes more selective.",
        "reliance": "Whether AI occupies a more central or less central role in ordinary workflow.",
        "human_agency": "Whether independent view formation and final authorship are reported similarly.",
        "trust": "Whether confidence and checking occupy a similar relationship.",
        "decision_delegation": "Whether AI input, option framing and final decision authority are reported similarly.",
        "thought_partnership": "Whether AI enters before or after an initial view is formed.",
        "emotional_regulation": "Whether the reported role of AI in emotional support is similar.",
        "disclosure": "Whether the scope of personal sharing is similar.",
        "social_transparency": "Whether reported use and reported openness remain similarly aligned.",
    }
    return copy.get(dim, "Whether the reported pattern occupies a similar benchmark position.")


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

    Pure presentation assembly of the Claude Closing Reflection object.
    """
    narrative = (report_data.get("narrative_blocks") or {}).get("closing_reflection") or {}
    if not isinstance(narrative, dict):
        narrative = {}

    return {
        "title": "Closing Reflection",
        "introduction": (
            "Every benchmark profile answers some questions and leaves others open.\n\n"
            "Rather than ending with a recommendation, this report finishes with one "
            "question that may be useful to carry forward from your current responses.\n\n"
            "There is no required answer. Its value lies in providing a reference point "
            "that may become more meaningful if you complete the assessment again later."
        ),
        "one_question": narrative.get("one_question", ""),
        "why_this_question_matters": narrative.get("why_this_question_matters", ""),
        "what_next_time": narrative.get("what_will_be_interesting_next_time", ""),
        "closing_reflection": narrative.get("closing_reflection", ""),
    }

