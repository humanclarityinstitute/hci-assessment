"""
Deterministic section assembly for the HCI premium report.

This module receives the canonical report-data object after narrative generation
and converts it into the single presentation contract consumed by the renderer.
It does not calculate scores, call external services or create new findings.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
import json
import re

from report_data_builder import (
    DIMENSION_LABELS,
    DIMENSION_ORDER,
    assert_report_data_contract,
    ordinal,
)


REPORT_SECTIONS_SCHEMA = "hci_report_sections"
BENCHMARK_LABEL = "HCI participant benchmark"

FULL_PERSONAL_INSIGHT_DISCLAIMER = (
    "This assessment is for personal insight only. It is not a psychological, "
    "medical or mental health assessment, diagnosis or advice, and it is not a "
    "clinical instrument. Do not rely on it for any decision that needs "
    "professional advice. If you have concerns about your wellbeing, please "
    "talk to a qualified professional."
)
SHORT_PERSONAL_INSIGHT_DISCLAIMER = (
    "This assessment is for personal insight only."
)

SECTION_ORDER = [
    "cover",
    "signature",
    "position",
    "similar_users",
    "distinctive_pattern",
    "evidence",
    "pattern_synthesis",
    "dimension_reference",
    "baseline",
    "closing",
    "appendix_questions",
    "appendix_methodology",
]

MAIN_SECTION_KEYS = SECTION_ORDER[:10]
APPENDIX_SECTION_KEYS = SECTION_ORDER[10:]


# ---------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------


def clean_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None or value == "":
            return default
        return int(round(float(value)))
    except Exception:
        return default


def compact_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {})
    }


def format_date(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    for candidate in (raw.replace("Z", "+00:00"), raw[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.strftime("%d %B %Y").lstrip("0")
        except Exception:
            continue
    return raw


def benchmark_scope(report_data: Dict[str, Any]) -> Dict[str, Any]:
    report_meta = report_data.get("report_meta") or {}
    benchmark = report_meta.get("benchmark") or {}
    response_count = (
        benchmark.get("response_count_label")
        or "10,000+ participant responses"
    )
    study_count = benchmark.get("study_count") or 21
    return {
        "label": benchmark.get("name") or BENCHMARK_LABEL,
        "foundation": f"{response_count} across {study_count} HCI studies",
        "response_count_label": response_count,
        "study_count": study_count,
        "benchmark_version": benchmark.get("version"),
        "benchmark_generated_at": benchmark.get("generated_at"),
        "benchmark_hash": benchmark.get("hash"),
        "minimum_cohort_n": benchmark.get("minimum_cohort_n"),
    }


def narrative_value(
    report_data: Dict[str, Any],
    nested_path: Iterable[str],
    block_key: str,
) -> Any:
    current: Any = report_data
    for key in nested_path:
        if not isinstance(current, dict):
            current = None
            break
        current = current.get(key)
    if current not in (None, "", [], {}):
        return current
    return (report_data.get("narrative_blocks") or {}).get(block_key)


def public_combination(item: Any) -> Optional[Dict[str, Any]]:
    """Expose the selected combination without leaking unsupported rarity."""
    if not isinstance(item, dict):
        return None

    shareable = bool(
        item.get("rarity_shareable")
        and item.get("public_rarity_percent") is not None
        and item.get("rarity_source") in {
            "calculated",
            "approved_research_estimate",
        }
    )
    rarity = None
    if shareable:
        rarity = compact_dict({
            "percent": item.get("public_rarity_percent"),
            "source": item.get("rarity_source"),
            "sample_basis": item.get("sample_basis"),
        })

    return compact_dict({
        "dimension_1": item.get("dimension_1"),
        "dimension_2": item.get("dimension_2"),
        "label_1": item.get("label_1"),
        "label_2": item.get("label_2"),
        "percentile_1": clean_int(item.get("percentile_1")),
        "percentile_2": clean_int(item.get("percentile_2")),
        "description": item.get("description"),
        "classification": item.get("combo_classification"),
        "rarity": rarity,
        "rarity_available": shareable,
    })


def position_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    overall = clean_int(item.get("overall_percentile"))
    frequency = clean_int(item.get("frequency_percentile"))
    age = clean_int(item.get("age_percentile"))
    return compact_dict({
        "key": item.get("key"),
        "label": item.get("label"),
        "definition": item.get("definition"),
        "overall_percentile": overall,
        "overall_percentile_label": ordinal(overall) if overall is not None else "Unavailable",
        "overall_position": item.get("overall_position"),
        "overall_n": item.get("overall_n"),
        "frequency_percentile": frequency,
        "frequency_percentile_label": ordinal(frequency) if frequency is not None else "Unavailable",
        "frequency_label": item.get("frequency_label"),
        "frequency_n": item.get("frequency_n"),
        "frequency_available": frequency is not None,
        "age_percentile": age,
        "age_percentile_label": ordinal(age) if age is not None else "Unavailable",
        "age_label": item.get("age_label"),
        "age_n": item.get("age_n"),
        "age_available": age is not None,
        "distance_from_centre": item.get("distance_from_centre"),
        "frequency_shift": item.get("frequency_shift"),
    })


def defining_signal_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    overall = clean_int(item.get("overall_percentile"))
    frequency = clean_int(item.get("frequency_percentile"))
    return compact_dict({
        "key": item.get("key"),
        "label": item.get("label"),
        "definition": item.get("definition"),
        "overall_percentile": overall,
        "overall_percentile_label": ordinal(overall) if overall is not None else "Unavailable",
        "frequency_percentile": frequency,
        "frequency_percentile_label": ordinal(frequency) if frequency is not None else "Unavailable",
        "position": item.get("position"),
        "distance_from_centre": item.get("distance_from_centre"),
        "frequency_difference": item.get("frequency_difference"),
        "supporting_evidence_count": item.get("supporting_evidence_count"),
    })




def public_question_text(item: Any, fallback: str) -> str:
    """Return participant-facing question text and fail closed on internal IDs."""
    if not isinstance(item, dict):
        return fallback
    text = str(item.get("question_text") or "").strip()
    if not text:
        return fallback
    if re.fullmatch(
        r"(?:rel|trust|ver|del|agency|emot|disc|thought|soc)_q\d+",
        text,
        flags=re.IGNORECASE,
    ):
        return fallback
    return text

def evidence_card(item: Any, reference: str) -> Dict[str, Any]:
    """Build one visible evidence card without exposing internal question IDs."""
    if not isinstance(item, dict):
        return {}
    overall = clean_int(item.get("percentile"))
    frequency = clean_int(item.get("percentile_frequency"))
    age = clean_int(item.get("percentile_age_group"))
    answer = item.get("answer")
    return compact_dict({
        "reference": reference,
        "dimension": item.get("dimension"),
        "dimension_label": item.get("dimension_label"),
        "question_text": public_question_text(
            item,
            f"Assessment item in {item.get('dimension_label') or 'this dimension'}",
        ),
        "answer": answer,
        "answer_display": item.get("answer_display") or (
            f"{answer}/7" if answer is not None else "No answer recorded"
        ),
        "overall_percentile": overall,
        "overall_percentile_label": ordinal(overall) if overall is not None else "Unavailable",
        "frequency_percentile": frequency,
        "frequency_percentile_label": ordinal(frequency) if frequency is not None else "Unavailable",
        "age_percentile": age,
        "age_percentile_label": ordinal(age) if age is not None else "Unavailable",
        "comparison_statement": item.get("comparison_statement"),
        "evidence_statement": item.get("evidence_statement"),
        "reverse_scored": bool(item.get("is_reverse_scored")),
        "scoring_note": item.get("scoring_note"),
        "distribution_everyone": deepcopy(item.get("distribution_everyone")),
        "distribution_frequency": deepcopy(item.get("distribution_frequency")),
        "distribution_age_group": deepcopy(item.get("distribution_age_group")),
    })


def perception_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    return compact_dict({
        "question": item.get("question"),
        "comparison_area": item.get("comparison_area"),
        "self_estimate": item.get("self_estimate"),
        "assessment_percentile": clean_int(item.get("assessment_percentile")),
        "assessment_position": item.get("assessment_position"),
        "perceived_percentile": clean_int(item.get("perceived_percentile")),
        "difference": item.get("difference"),
        "gap_magnitude": item.get("gap_magnitude"),
        "difference_available": bool(item.get("difference_available")),
        "direction": item.get("direction"),
        "basis": item.get("basis"),
    })


def fallback_signature(report_data: Dict[str, Any]) -> str:
    labels = [
        item.get("label")
        for item in report_data.get("defining_signals") or []
        if isinstance(item, dict) and item.get("label")
    ]
    if len(labels) >= 3:
        return (
            f"Your current profile is most clearly shaped by the relationship "
            f"between {labels[0]}, {labels[1]} and {labels[2]}."
        )
    if labels:
        return "Your current profile is most clearly shaped by " + ", ".join(labels) + "."
    return (
        "Your current responses form a clear reference pattern across the nine "
        "areas measured in this assessment."
    )


def fallback_pattern_narrative(report_data: Dict[str, Any]) -> str:
    signals = [
        defining_signal_item(item)
        for item in report_data.get("defining_signals") or []
    ]
    signal_text = "; ".join(
        f"{item.get('label')} sits at the {item.get('overall_percentile_label')} percentile"
        for item in signals
        if item.get("label") and item.get("overall_percentile") is not None
    )
    perception = perception_item(
        (report_data.get("perception_summary") or {}).get("largest_difference")
    )

    paragraphs = [
        (
            "The organising feature of your profile is the relationship between "
            "the three results that sit furthest from the HCI benchmark centre."
            + (f" In this assessment, {signal_text}." if signal_text else "")
        ),
        (
            "These positions are most useful when read together with the selected "
            "question-level evidence. The evidence shows which responses contributed "
            "most strongly to the overall shape rather than asking one score to carry "
            "the entire interpretation."
        ),
    ]
    if perception.get("difference_available"):
        paragraphs.append(
            "Your direct self-estimate and your assessment-based position also provide "
            "two different views of the same relationship with AI. That difference is "
            "not a correction; it adds a perspective that can be difficult to establish "
            "from experience alone."
        )
    else:
        paragraphs.append(
            "Your direct self-estimates provide a second perspective on the profile. "
            "The report keeps that perspective alongside the benchmark results without "
            "treating either as a complete description of you."
        )
    paragraphs.append(
        "The central finding is therefore the shape of the pattern: the defining "
        "signals, the responses behind them and your own self-view combine into one "
        "dated account of how you currently report relating to AI."
    )
    return "\n\n".join(paragraphs)


def fallback_distinctive_narrative(report_data: Dict[str, Any]) -> str:
    pattern = report_data.get("distinctive_pattern") or {}
    combination = public_combination(pattern.get("combination"))
    if combination:
        rarity_text = ""
        rarity = combination.get("rarity") or {}
        if rarity.get("percent") is not None:
            rarity_text = (
                f" In the supported benchmark source, approximately "
                f"{rarity.get('percent')}% of participants showed this combination."
            )
        return (
            f"The clearest interaction in your profile is between "
            f"{combination.get('label_1')} and {combination.get('label_2')}. "
            f"Those results sit at the {ordinal(combination.get('percentile_1'))} "
            f"and {ordinal(combination.get('percentile_2'))} percentiles respectively."
            f"{rarity_text}\n\n"
            "Read together, the two positions provide more information than either "
            "result does alone. They may indicate an important boundary or organising "
            "feature in your current self-reported relationship with AI, without "
            "establishing why the pattern exists or what it will lead to."
        )

    labels = [
        item.get("label")
        for item in report_data.get("defining_signals") or []
        if isinstance(item, dict) and item.get("label")
    ]
    return (
        "Your profile is not defined by one isolated result. Its clearest feature "
        f"is the way {', '.join(labels[:3]) or 'the defining signals'} combine into "
        "a coherent overall shape.\n\nThat coherence makes the relationship between "
        "the results more informative than any single high or low position by itself."
    )


def fallback_human_capital_lens(report_data: Dict[str, Any]) -> List[Dict[str, str]]:
    mapping = {
        "human_agency": ("Decision authorship", "This lens is relevant because your responses show how control and authorship currently sit within AI-supported decisions."),
        "decision_delegation": ("Decision authorship", "This lens is relevant because your responses show how AI input and final decision authority currently relate."),
        "verification": ("Critical scepticism", "This lens is relevant because checking and evaluating AI outputs are prominent features of the assessed response pattern."),
        "trust": ("Critical scepticism", "This lens is relevant because confidence in AI is most informative when read alongside how outputs are evaluated."),
        "thought_partnership": ("Intellectual openness", "This lens is relevant because AI plays a visible role in how ideas are developed, tested or extended in your responses."),
        "reliance": ("Independent view formation", "This lens is relevant because the role AI occupies in ordinary work and thinking raises questions about where an initial view begins."),
        "disclosure": ("Privacy boundaries", "This lens is relevant because your responses show where personal sharing currently sits within your relationship with AI."),
        "social_transparency": ("Privacy boundaries", "This lens is relevant because openness about AI use and private boundaries form part of the current profile."),
        "emotional_regulation": ("Emotional discernment", "This lens is relevant because your responses show the current role AI plays in emotional support and reflection."),
    }
    selected: List[Dict[str, str]] = []
    seen = set()
    for signal in report_data.get("defining_signals") or []:
        key = signal.get("key") if isinstance(signal, dict) else None
        title, body = mapping.get(
            key,
            ("Human judgement", "This lens provides one useful way to reflect on the human capabilities connected with the current response pattern."),
        )
        if title in seen:
            continue
        seen.add(title)
        selected.append({"title": title, "body": body})
        if len(selected) == 3:
            break
    while len(selected) < 3:
        for title, body in [
            ("Independent view formation", "This lens is relevant to where personal judgement begins and how AI input enters the thinking process."),
            ("Privacy boundaries", "This lens is relevant to the limits placed around personal sharing and openness about AI use."),
            ("Emotional discernment", "This lens is relevant to how AI support is distinguished from other forms of emotional connection."),
        ]:
            if title not in seen:
                seen.add(title)
                selected.append({"title": title, "body": body})
            if len(selected) == 3:
                break
    return selected[:3]


# ---------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------


def build_cover(report_data: Dict[str, Any]) -> Dict[str, Any]:
    meta = report_data.get("report_meta") or {}
    scope = benchmark_scope(report_data)
    baseline_date = meta.get("baseline_date") or report_data.get("assessment_completed_at")
    return {
        "key": "cover",
        "kind": "main",
        "title": "AI Identity & Behaviour Report",
        "subtitle": "Your HCI AI Behaviour Baseline",
        "institute": "Human Clarity Institute",
        "assessment_date": baseline_date,
        "assessment_date_display": format_date(baseline_date),
        "age_group": meta.get("age_group"),
        "reported_ai_use_frequency": meta.get("reported_ai_use_frequency"),
        "benchmark": scope,
        "important_information_title": "Important Assessment Information",
        "important_information": FULL_PERSONAL_INSIGHT_DISCLAIMER,
        "footer_disclaimer": SHORT_PERSONAL_INSIGHT_DISCLAIMER,
    }


def build_signature(report_data: Dict[str, Any]) -> Dict[str, Any]:
    signature = report_data.get("signature") or {}
    sentence = narrative_value(
        report_data,
        ("signature", "signature_sentence"),
        "signature_sentence",
    ) or fallback_signature(report_data)
    combination = public_combination(signature.get("strongest_combination"))
    shape = [position_item(item) for item in report_data.get("position") or []]
    signals = [
        defining_signal_item(item)
        for item in report_data.get("defining_signals") or []
    ]
    return {
        "key": "signature",
        "kind": "main",
        "title": "Your Signature",
        "signature_sentence": sentence,
        "dimension_shape": shape,
        "defining_signals": signals,
        "strongest_combination": combination,
        "rarity_badge_allowed": bool(
            combination and combination.get("rarity_available")
        ),
        "baseline_date": (report_data.get("report_meta") or {}).get("baseline_date"),
        "baseline_date_display": format_date(
            (report_data.get("report_meta") or {}).get("baseline_date")
        ),
        "shareable": {
            "standalone_page": True,
            "contains_contact_details": False,
            "contains_sensitive_detail": False,
        },
    }


def build_position_section(report_data: Dict[str, Any]) -> Dict[str, Any]:
    items = [position_item(item) for item in report_data.get("position") or []]
    available_frequency = sum(1 for item in items if item.get("frequency_available"))
    available_age = sum(1 for item in items if item.get("age_available"))
    return {
        "key": "position",
        "kind": "main",
        "title": "Your Position",
        "subtitle": (
            "Where your self-reported results sit across the nine HCI dimensions."
        ),
        "benchmark": benchmark_scope(report_data),
        "items": items,
        "availability": {
            "overall": len([item for item in items if item.get("overall_percentile") is not None]),
            "similar_use": available_frequency,
            "age_group": available_age,
        },
        "unavailable_rule": (
            "A cohort result is shown as unavailable when the relevant benchmark "
            "sample does not meet the minimum requirement. It is never estimated."
        ),
    }


def build_similar_users(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source_items = report_data.get("comparison_shifts") or []
    items = []
    for item in source_items:
        if not isinstance(item, dict):
            continue
        overall = clean_int(item.get("overall_percentile"))
        frequency = clean_int(item.get("frequency_percentile"))
        if overall is None or frequency is None:
            continue
        items.append(compact_dict({
            "dimension": item.get("dimension"),
            "label": item.get("label"),
            "overall_percentile": overall,
            "overall_percentile_label": ordinal(overall),
            "similar_use_percentile": frequency,
            "similar_use_percentile_label": ordinal(frequency),
            "shift": item.get("shift"),
            "absolute_shift": item.get("absolute_shift"),
            "direction": item.get("direction"),
            "meaning": item.get("meaning"),
            "similar_use_n": item.get("frequency_n"),
        }))

    summary = report_data.get("comparison_summary") or {}
    valid_count = clean_int(summary.get("valid_comparison_count"), 0) or 0
    if valid_count == 0:
        mode = "unavailable"
        summary_text = (
            "A reliable comparison with participants who report similar AI-use "
            "frequency was not available for this assessment."
        )
    elif items:
        mode = "differences"
        summary_text = (
            "These are the dimensions where your overall position changes most "
            "after comparing you only with participants who report using AI about "
            "as frequently as you."
        )
    else:
        mode = "aligned"
        summary_text = (
            "Across the available dimensions, your overall positions remain broadly "
            "aligned with your positions among participants who report similar AI use."
        )

    return {
        "key": "similar_users",
        "kind": "main",
        "title": "Compared With Similar AI Users",
        "question": (
            "Is this distinctive about your wider profile, or common among people "
            "who report using AI as frequently as you?"
        ),
        "mode": mode,
        "summary": summary_text,
        "valid_comparison_count": valid_count,
        "total_dimension_count": 9,
        "items": items,
        "minimum_shift_threshold": summary.get("minimum_shift_threshold"),
    }


def build_distinctive_pattern_section(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source = report_data.get("distinctive_pattern") or {}
    mode = source.get("mode") if source.get("mode") in {"combination", "coherence"} else "coherence"
    combination = public_combination(source.get("combination"))
    title = (
        "What Makes You Different"
        if mode == "combination" and combination
        else "What Makes Your Pattern Coherent"
    )
    narrative = narrative_value(
        report_data,
        ("distinctive_pattern", "narrative"),
        "combination_narrative",
    ) or fallback_distinctive_narrative(report_data)

    evidence_index = {
        item.get("key"): f"E{index}"
        for index, item in enumerate(report_data.get("evidence") or [], 1)
        if isinstance(item, dict) and item.get("key")
    }
    supporting = []
    for item in source.get("supporting_evidence") or []:
        key = item.get("key") if isinstance(item, dict) else None
        supporting.append(evidence_card(item, evidence_index.get(key, "Evidence")))

    return {
        "key": "distinctive_pattern",
        "kind": "main",
        "title": title,
        "mode": "combination" if combination and mode == "combination" else "coherence",
        "combination": combination,
        "supporting_evidence": supporting[:3],
        "narrative": narrative,
        "interpretation_boundary": (
            "The combination describes how measured results appear together. It "
            "does not establish a cause, diagnosis, fixed identity or future outcome."
        ),
    }


def build_evidence_section(report_data: Dict[str, Any]) -> Dict[str, Any]:
    items = [
        evidence_card(item, f"E{index}")
        for index, item in enumerate(report_data.get("evidence") or [], 1)
    ]
    return {
        "key": "evidence",
        "kind": "main",
        "title": "The Evidence",
        "subtitle": (
            "The selected responses that contribute most clearly to the shape of "
            "your current benchmark profile."
        ),
        "intro": (
            "These are question-level self-report findings. They show why the report "
            "reached its conclusions without treating any one response as a fixed trait."
        ),
        "items": items,
    }


def build_pattern_synthesis_section(report_data: Dict[str, Any]) -> Dict[str, Any]:
    synthesis = report_data.get("pattern_synthesis") or {}
    narrative = narrative_value(
        report_data,
        ("pattern_synthesis", "pattern_narrative"),
        "pattern_narrative",
    ) or fallback_pattern_narrative(report_data)
    perception = report_data.get("perception_summary") or {}
    lens = narrative_value(
        report_data,
        ("human_capital_lens",),
        "human_capital_lens",
    )
    if not isinstance(lens, list) or len(lens) != 3:
        lens = fallback_human_capital_lens(report_data)

    cleaned_lens = []
    for item in lens[:3]:
        if not isinstance(item, dict):
            continue
        cleaned_lens.append(compact_dict({
            "title": item.get("title"),
            "body": item.get("body"),
        }))

    return {
        "key": "pattern_synthesis",
        "kind": "main",
        "title": "What Your Pattern Suggests",
        "organising_feature": (
            synthesis.get("organising_feature")
            or (
                (report_data.get("defining_signals") or [{}])[0].get("label")
                if report_data.get("defining_signals")
                else None
            )
        ),
        "narrative": narrative,
        "self_perception": {
            "items": [
                perception_item(item)
                for item in perception.get("items") or []
            ],
            "largest_difference": perception_item(
                perception.get("largest_difference")
            ),
            "has_numeric_difference": bool(
                perception.get("has_numeric_difference")
            ),
            "framing": (
                "This compares two forms of self-report: your direct estimate and "
                "the position derived from your other assessment responses. It is "
                "intended to add perspective, not correct your self-understanding."
            ),
        },
        "human_capital_lens": cleaned_lens,
        "human_capital_note": (
            "These are interpretive lenses connected with the response pattern, "
            "not objective measurements of capability."
        ),
    }


def build_dimension_reference_section(report_data: Dict[str, Any]) -> Dict[str, Any]:
    items = []
    for item in report_data.get("dimension_reference") or []:
        if not isinstance(item, dict):
            continue
        overall = clean_int(item.get("overall_percentile"))
        frequency = clean_int(item.get("frequency_percentile"))
        definition = str(item.get("definition") or "").strip()
        note = str(item.get("behavioural_note") or "").strip()
        summary = " ".join(part for part in [definition, note] if part)
        items.append(compact_dict({
            "key": item.get("key"),
            "label": item.get("label"),
            "definition": definition,
            "overall_percentile": overall,
            "overall_percentile_label": ordinal(overall) if overall is not None else "Unavailable",
            "similar_use_percentile": frequency,
            "similar_use_percentile_label": ordinal(frequency) if frequency is not None else "Unavailable",
            "position": item.get("position"),
            "reference_text": summary,
        }))

    return {
        "key": "dimension_reference",
        "kind": "main",
        "title": "Dimension Reference",
        "subtitle": (
            "A concise guide to what each HCI dimension measures and where your "
            "current result sits."
        ),
        "items": items,
    }


def build_baseline_section(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source = report_data.get("baseline") or {}
    evidence_lookup = {
        item.get("key"): {
            "reference": f"E{index}",
            "dimension_label": item.get("dimension_label"),
            "question_text": public_question_text(
                item,
                f"Assessment item in {item.get('dimension_label') or 'this dimension'}",
            ),
        }
        for index, item in enumerate(report_data.get("evidence") or [], 1)
        if isinstance(item, dict) and item.get("key")
    }
    evidence_references = [
        compact_dict(evidence_lookup.get(key) or {"reference": key})
        for key in source.get("distinctive_evidence_keys") or []
        if key in evidence_lookup
    ]

    return_question = narrative_value(
        report_data,
        ("baseline", "return_question"),
        "return_question",
    )
    if not return_question:
        priorities = source.get("comparison_priorities") or []
        labels = [
            item.get("label")
            for item in priorities
            if isinstance(item, dict) and item.get("label")
        ]
        if len(labels) >= 2:
            return_question = (
                f"When you reassess, will the relationship between {labels[0]} "
                f"and {labels[1]} look similar to the pattern recorded today?"
            )
        else:
            return_question = (
                "When you reassess, which parts of your current AI-use pattern "
                "will look similar and which will look different?"
            )

    baseline_closing = narrative_value(
        report_data,
        ("baseline", "baseline_closing"),
        "baseline_closing",
    ) or (
        "This report establishes a dated reference point for comparing your "
        "self-reported AI behaviour at a later assessment."
    )

    return {
        "key": "baseline",
        "kind": "main",
        "title": "Your Baseline",
        "baseline_date": source.get("baseline_date"),
        "baseline_date_display": format_date(source.get("baseline_date")),
        "benchmark": benchmark_scope(report_data),
        "reported_ai_use_frequency": source.get("reported_ai_use_frequency"),
        "dimension_positions": [
            position_item(item)
            for item in source.get("dimension_positions") or []
        ],
        "defining_signals": [
            defining_signal_item(item)
            for item in source.get("defining_signals") or []
        ],
        "strongest_combination": public_combination(
            source.get("strongest_combination")
        ),
        "largest_perception_difference": perception_item(
            source.get("largest_perception_difference")
        ),
        "evidence_references": evidence_references,
        "comparison_priorities": [
            compact_dict({
                "type": item.get("type"),
                "key": item.get("key"),
                "label": item.get("label"),
                "current_percentile": clean_int(item.get("current_percentile")),
                "current_percentile_label": (
                    ordinal(item.get("current_percentile"))
                    if item.get("current_percentile") is not None
                    else "Unavailable"
                ),
                "reason": item.get("reason"),
            })
            for item in source.get("comparison_priorities") or []
            if isinstance(item, dict)
        ],
        "return_question": return_question,
        "baseline_closing": baseline_closing,
        "recommended_reassessment_window": source.get("recommended_reassessment_window") or "6–12 months",
        "measurement_boundary": (
            "A single assessment establishes a baseline. It cannot establish "
            "personal change, stability or direction over time."
        ),
    }


def build_closing_section(report_data: Dict[str, Any]) -> Dict[str, Any]:
    signature = build_signature(report_data)
    baseline = build_baseline_section(report_data)
    return {
        "key": "closing",
        "kind": "main",
        "title": "Where You Sit Today",
        "signature_sentence": signature.get("signature_sentence"),
        "return_question": baseline.get("return_question"),
        "baseline_date": baseline.get("baseline_date"),
        "baseline_date_display": baseline.get("baseline_date_display"),
        "recommended_reassessment_window": baseline.get("recommended_reassessment_window"),
        "closing_sentence": baseline.get("baseline_closing"),
        "final_line": (
            "This is where your reported pattern sits today. A later measurement "
            "can show what remains similar and what looks different."
        ),
        "footer_disclaimer": SHORT_PERSONAL_INSIGHT_DISCLAIMER,
        "shareable": {
            "standalone_page": True,
            "contains_contact_details": False,
            "contains_sensitive_detail": False,
        },
    }


def appendix_question_item(item: Any, number: int) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    overall = clean_int(item.get("percentile"))
    frequency = clean_int(item.get("percentile_frequency"))
    age = clean_int(item.get("percentile_age_group"))
    answer = item.get("answer")
    return compact_dict({
        "question_number": number,
        "dimension": item.get("dimension"),
        "dimension_label": item.get("dimension_label"),
        "question_text": public_question_text(
            item,
            f"Assessment item {number} in {item.get('dimension_label') or 'this dimension'}",
        ),
        "answer": answer,
        "answer_display": item.get("answer_display") or (
            f"{answer}/7" if answer is not None else "No answer recorded"
        ),
        "overall_percentile": overall,
        "overall_percentile_label": ordinal(overall) if overall is not None else "Unavailable",
        "similar_use_percentile": frequency,
        "similar_use_percentile_label": ordinal(frequency) if frequency is not None else "Unavailable",
        "age_percentile": age,
        "age_percentile_label": ordinal(age) if age is not None else "Unavailable",
        "comparison_statement": item.get("comparison_statement"),
        "reverse_scored": bool(item.get("is_reverse_scored")),
        "distribution_everyone": deepcopy(item.get("distribution_everyone")),
        "distribution_frequency": deepcopy(item.get("distribution_frequency")),
        "distribution_age_group": deepcopy(item.get("distribution_age_group")),
    })


def build_appendix_questions(report_data: Dict[str, Any]) -> Dict[str, Any]:
    questions = [
        appendix_question_item(item, number)
        for number, item in enumerate(report_data.get("appendix_questions") or [], 1)
    ]
    groups = []
    for dimension in DIMENSION_ORDER:
        group_items = [
            item for item in questions
            if item.get("dimension") == dimension
        ]
        groups.append({
            "dimension": dimension,
            "label": DIMENSION_LABELS.get(dimension, dimension),
            "questions": group_items,
        })
    return {
        "key": "appendix_questions",
        "kind": "appendix",
        "title": "Appendix A: Complete 39-Question Profile",
        "subtitle": (
            "Your complete self-reported assessment record with available benchmark "
            "comparisons."
        ),
        "question_count": len(questions),
        "groups": groups,
    }


def build_appendix_methodology(report_data: Dict[str, Any]) -> Dict[str, Any]:
    source = deepcopy(report_data.get("methodology") or {})
    return {
        "key": "appendix_methodology",
        "kind": "appendix",
        "title": "Appendix B: Benchmark and Methodology",
        "assessment_type": source.get("assessment_type"),
        "benchmark": compact_dict({
            "name": source.get("benchmark_name"),
            "response_count_label": source.get("benchmark_response_count_label"),
            "study_count": source.get("benchmark_study_count"),
            "benchmark_version": source.get("benchmark_version"),
            "generated_at": source.get("benchmark_generated_at"),
            "hash": source.get("benchmark_hash"),
            "minimum_cohort_n": source.get("minimum_cohort_n"),
        }),
        "dimensions": deepcopy(source.get("dimensions") or []),
        "percentile_explanation": source.get("percentile_explanation"),
        "cohort_rule": source.get("cohort_rule"),
        "self_report_note": source.get("self_report_note"),
        "important_information": FULL_PERSONAL_INSIGHT_DISCLAIMER,
    }


# ---------------------------------------------------------------------
# Public assembly and validation
# ---------------------------------------------------------------------


def build_sections(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build the complete render-ready section contract in report order."""
    assert_report_data_contract(report_data)

    sections = {
        "cover": build_cover(report_data),
        "signature": build_signature(report_data),
        "position": build_position_section(report_data),
        "similar_users": build_similar_users(report_data),
        "distinctive_pattern": build_distinctive_pattern_section(report_data),
        "evidence": build_evidence_section(report_data),
        "pattern_synthesis": build_pattern_synthesis_section(report_data),
        "dimension_reference": build_dimension_reference_section(report_data),
        "baseline": build_baseline_section(report_data),
        "closing": build_closing_section(report_data),
        "appendix_questions": build_appendix_questions(report_data),
        "appendix_methodology": build_appendix_methodology(report_data),
    }

    output: Dict[str, Any] = {
        "schema": REPORT_SECTIONS_SCHEMA,
        "section_order": list(SECTION_ORDER),
        "main_section_keys": list(MAIN_SECTION_KEYS),
        "appendix_section_keys": list(APPENDIX_SECTION_KEYS),
        **sections,
    }
    output["ordered_sections"] = [
        output[key] for key in SECTION_ORDER
    ]
    assert_sections_contract(output)
    return output


def assert_sections_contract(sections: Dict[str, Any]) -> None:
    """Validate section order, required content and public evidence boundaries."""
    if not isinstance(sections, dict):
        raise ValueError("sections must be a dictionary")
    if sections.get("schema") != REPORT_SECTIONS_SCHEMA:
        raise ValueError("Unexpected report-sections schema")
    if sections.get("section_order") != SECTION_ORDER:
        raise ValueError("Report section order does not match the locked structure")

    missing = [key for key in SECTION_ORDER if key not in sections]
    if missing:
        raise ValueError(f"Report sections missing required entries: {missing}")

    ordered = sections.get("ordered_sections") or []
    if [item.get("key") for item in ordered] != SECTION_ORDER:
        raise ValueError("ordered_sections does not match section_order")

    if len((sections.get("signature") or {}).get("defining_signals") or []) != 3:
        raise ValueError("Signature must contain exactly 3 defining signals")
    if len((sections.get("signature") or {}).get("dimension_shape") or []) != 9:
        raise ValueError("Signature must contain all 9 dimension positions")
    if len((sections.get("position") or {}).get("items") or []) != 9:
        raise ValueError("Your Position must contain exactly 9 dimensions")

    evidence_count = len((sections.get("evidence") or {}).get("items") or [])
    if not 5 <= evidence_count <= 7:
        raise ValueError("The Evidence must contain 5–7 items")
    if len((sections.get("pattern_synthesis") or {}).get("human_capital_lens") or []) != 3:
        raise ValueError("Human Capital Lens must contain exactly 3 items")
    if len((sections.get("dimension_reference") or {}).get("items") or []) != 9:
        raise ValueError("Dimension Reference must contain exactly 9 items")
    if len((sections.get("baseline") or {}).get("comparison_priorities") or []) != 3:
        raise ValueError("Baseline must contain exactly 3 comparison priorities")
    if (sections.get("appendix_questions") or {}).get("question_count") != 39:
        raise ValueError("Appendix A must contain exactly 39 questions")

    combination = (sections.get("distinctive_pattern") or {}).get("combination") or {}
    rarity = combination.get("rarity")
    if rarity:
        if rarity.get("source") not in {
            "calculated",
            "approved_research_estimate",
        }:
            raise ValueError("Public rarity requires an approved source")
        if rarity.get("percent") is None:
            raise ValueError("Public rarity requires a percentage")

    if (sections.get("cover") or {}).get("important_information") != FULL_PERSONAL_INSIGHT_DISCLAIMER:
        raise ValueError("Cover must contain the full personal-insight disclaimer")
    if (sections.get("closing") or {}).get("footer_disclaimer") != SHORT_PERSONAL_INSIGHT_DISCLAIMER:
        raise ValueError("Closing must contain the short personal-insight disclaimer")

    public_text = json.dumps(sections, ensure_ascii=False)
    internal_id_pattern = re.compile(
        r"\b(?:rel|trust|ver|del|agency|emot|disc|thought|soc)_q\d+\b",
        flags=re.IGNORECASE,
    )
    if internal_id_pattern.search(public_text):
        raise ValueError("Report sections expose an internal question ID")
