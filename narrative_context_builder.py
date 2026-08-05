"""
Narrative context builder for the HCI premium report.

This module does not calculate participant results and does not write report
prose. It converts the canonical report-data object into two compact,
auditable context packages for the two Claude calls used by the report:

1. profile synthesis;
2. baseline and return question.

Only selected measurement evidence is exposed. The full question set, contact
details, broad research libraries and unsupported rarity values are excluded.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional
import re


REPORT_DATA_SCHEMA = "hci_report_data"
NARRATIVE_CONTEXT_SCHEMA = "hci_narrative_context"

EVIDENCE_BOUNDARY = {
    "assessment_basis": (
        "This assessment is based on the participant's self-reported responses "
        "and comparison with the HCI participant benchmark."
    ),
    "measured_finding_rule": (
        "State supplied responses, percentiles, valid cohort comparisons and "
        "approved rarity clearly and accurately."
    ),
    "interpretation_rule": (
        "Interpret what the measured pattern may suggest, but do not present an "
        "interpretation as an observed fact about the participant."
    ),
    "benchmark_language": (
        "Use 'HCI participant benchmark'. Do not describe the benchmark as the "
        "general population, everyone, a population norm or objective reality."
    ),
    "prohibited_claims": [
        "diagnosis or clinical classification",
        "personality type or fixed identity",
        "causation or hidden psychological mechanism",
        "objective capability gain or loss",
        "dependency as a diagnosed condition",
        "future prediction",
        "individual change over time from one assessment",
    ],
}

WRITING_PRINCIPLES = [
    "Reveal more. Explain only what improves clarity.",
    "State the measured finding strongly. Qualify the interpretation, not the evidence.",
    "Describe a current response pattern, not a permanent identity.",
    "Prefer direct, specific language over generic AI commentary.",
    "Do not repeat the same finding across multiple outputs.",
    "Do not add advice, prescriptions or behaviour-change instructions.",
]

HUMAN_CAPITAL_THEMES = {
    "decision_authorship": "Decision authorship",
    "critical_scepticism": "Critical scepticism",
    "intellectual_openness": "Intellectual openness",
    "independent_view_formation": "Independent view formation",
    "privacy_boundaries": "Privacy boundaries",
    "emotional_discernment": "Emotional discernment",
}

# Ordered options let each defining signal contribute a distinct capability
# theme wherever possible. Selection follows the defining-signal order already
# established by report_data_builder.py; no second scoring system is introduced.
DIMENSION_THEME_OPTIONS = {
    "decision_delegation": ["decision_authorship", "independent_view_formation"],
    "human_agency": ["decision_authorship", "independent_view_formation"],
    "verification": ["critical_scepticism", "independent_view_formation"],
    "trust": ["critical_scepticism", "intellectual_openness"],
    "thought_partnership": ["intellectual_openness", "independent_view_formation"],
    "reliance": ["independent_view_formation", "decision_authorship"],
    "disclosure": ["privacy_boundaries", "emotional_discernment"],
    "social_transparency": ["privacy_boundaries", "decision_authorship"],
    "emotional_regulation": ["emotional_discernment", "privacy_boundaries"],
}

INTERNAL_QUESTION_ID = re.compile(
    r"^(?:rel|trust|ver|del|agency|emot|disc|thought|soc)_q\d+$",
    flags=re.IGNORECASE,
)


FALLBACK_THEME_ORDER = [
    "decision_authorship",
    "critical_scepticism",
    "intellectual_openness",
    "independent_view_formation",
    "privacy_boundaries",
    "emotional_discernment",
]


def compact_dict(value: Any) -> Dict[str, Any]:
    """Remove empty values while preserving valid zero and False values."""
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {})
    }


def clean_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None or value == "":
            return default
        return int(round(float(value)))
    except Exception:
        return default


def validate_report_data(report_data: Dict[str, Any]) -> None:
    """Validate the narrative inputs without recalculating report results."""
    if not isinstance(report_data, dict):
        raise ValueError("report_data must be a dictionary")
    if report_data.get("schema") != REPORT_DATA_SCHEMA:
        raise ValueError(
            f"narrative context requires schema {REPORT_DATA_SCHEMA}"
        )

    required = [
        "report_meta",
        "dimensions",
        "signature",
        "position",
        "comparison_shifts",
        "defining_signals",
        "distinctive_pattern",
        "evidence",
        "perception_summary",
        "baseline",
    ]
    missing = [key for key in required if key not in report_data]
    if missing:
        raise ValueError(
            f"report_data missing required narrative inputs: {missing}"
        )

    if len(report_data.get("defining_signals") or []) != 3:
        raise ValueError("report_data must contain exactly 3 defining signals")
    evidence_count = len(report_data.get("evidence") or [])
    if not 5 <= evidence_count <= 7:
        raise ValueError("report_data must contain 5–7 evidence items")


def benchmark_scope(report_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Use benchmark metadata supplied by the report-data builder."""
    benchmark = report_meta.get("benchmark") or {}
    return compact_dict({
        "label": benchmark.get("name") or "HCI participant benchmark",
        "response_count_label": benchmark.get("response_count_label"),
        "study_count": benchmark.get("study_count"),
        "benchmark_identifier": benchmark.get("version"),
        "minimum_cohort_n": benchmark.get("minimum_cohort_n"),
    })


def dimension_position(item: Dict[str, Any]) -> Dict[str, Any]:
    """Return the measurement fields needed from one dimension result."""
    if not isinstance(item, dict):
        return {}
    overall = (
        item.get("overall_percentile")
        if item.get("overall_percentile") is not None
        else item.get("percentile")
    )
    frequency = (
        item.get("frequency_percentile")
        if item.get("frequency_percentile") is not None
        else item.get("percentile_frequency")
    )
    age = (
        item.get("age_percentile")
        if item.get("age_percentile") is not None
        else item.get("percentile_age_group")
    )
    return compact_dict({
        "dimension": item.get("key") or item.get("dimension"),
        "label": item.get("label"),
        "definition": item.get("definition"),
        "overall_percentile": overall,
        "similar_use_percentile": frequency,
        "age_percentile": age,
        "position": item.get("position") or item.get("overall_position"),
        "distance_from_benchmark_centre": item.get("distance_from_centre"),
        "similar_use_difference": item.get("frequency_difference"),
        "supporting_evidence_count": item.get("supporting_evidence_count"),
    })


def evidence_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Return selected question evidence without exposing internal variable IDs."""
    if not isinstance(item, dict):
        return {}

    question_text = str(item.get("question_text") or "").strip()
    if INTERNAL_QUESTION_ID.fullmatch(question_text):
        question_text = "Question wording unavailable"

    return compact_dict({
        "dimension": item.get("dimension"),
        "dimension_label": item.get("dimension_label"),
        "question_text": question_text,
        "answer_display": item.get("answer_display"),
        "overall_percentile": item.get("percentile"),
        "similar_use_percentile": item.get("percentile_frequency"),
        "age_percentile": item.get("percentile_age_group"),
        "comparison_statement": item.get("comparison_statement"),
        "reverse_scored": item.get("is_reverse_scored"),
        "evidence_statement": item.get("evidence_statement"),
    })


def combination_item(item: Any) -> Optional[Dict[str, Any]]:
    """Expose the selected combination while blocking unsupported rarity."""
    if not isinstance(item, dict):
        return None

    rarity_shareable = bool(item.get("rarity_shareable"))
    return compact_dict({
        "dimension_1": item.get("dimension_1"),
        "dimension_2": item.get("dimension_2"),
        "label_1": item.get("label_1"),
        "label_2": item.get("label_2"),
        "percentile_1": item.get("percentile_1"),
        "percentile_2": item.get("percentile_2"),
        "description": item.get("description"),
        "rarity_available_for_public_use": rarity_shareable,
        "rarity_percent": (
            item.get("public_rarity_percent") if rarity_shareable else None
        ),
        "rarity_basis": (
            item.get("rarity_source") if rarity_shareable else None
        ),
        "sample_basis": item.get("sample_basis") if rarity_shareable else None,
    })


def perception_item(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    return compact_dict({
        "question": item.get("question"),
        "comparison_area": item.get("comparison_area"),
        "self_estimate": item.get("self_estimate"),
        "assessment_percentile": item.get("assessment_percentile"),
        "assessment_position": item.get("assessment_position"),
        "perceived_percentile": item.get("perceived_percentile"),
        "difference": item.get("difference"),
        "difference_available": item.get("difference_available"),
        "basis": item.get("basis"),
    })


def comparison_shift(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    return compact_dict({
        "dimension": item.get("dimension"),
        "label": item.get("label"),
        "overall_percentile": item.get("overall_percentile"),
        "similar_use_percentile": item.get("frequency_percentile"),
        "difference": item.get("shift"),
        "direction": item.get("direction"),
        "meaning": item.get("meaning"),
        "similar_use_sample_size": item.get("frequency_n"),
    })


def _find_evidence_for_dimensions(
    evidence: Iterable[Dict[str, Any]],
    dimensions: Iterable[str],
    limit: int = 2,
) -> List[Dict[str, Any]]:
    dimension_set = {value for value in dimensions if value}
    selected = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        if item.get("dimension") in dimension_set:
            selected.append(evidence_item(item))
        if len(selected) >= limit:
            break
    return selected


def select_human_capital_themes(
    report_data: Dict[str, Any],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    Select capability lenses from the ordered defining signals.

    The report-data builder already determines which signals define the profile.
    This function translates those signals into unique capability themes without
    introducing weights, scores or a second ranking model.
    """
    defining_signals = report_data.get("defining_signals") or []
    evidence = report_data.get("evidence") or []
    dimensions = report_data.get("dimensions") or {}

    selected_theme_keys: List[str] = []
    theme_source_dimensions: Dict[str, List[str]] = {}

    for signal in defining_signals:
        if not isinstance(signal, dict):
            continue
        dimension = signal.get("key") or signal.get("dimension")
        options = DIMENSION_THEME_OPTIONS.get(dimension, [])
        chosen = next(
            (theme for theme in options if theme not in selected_theme_keys),
            None,
        )
        if chosen is None:
            continue
        selected_theme_keys.append(chosen)
        theme_source_dimensions.setdefault(chosen, []).append(dimension)
        if len(selected_theme_keys) >= limit:
            break

    for theme in FALLBACK_THEME_ORDER:
        if len(selected_theme_keys) >= limit:
            break
        if theme not in selected_theme_keys:
            selected_theme_keys.append(theme)
            theme_source_dimensions.setdefault(theme, [])

    output: List[Dict[str, Any]] = []
    for theme in selected_theme_keys[:limit]:
        source_dimensions = theme_source_dimensions.get(theme, [])
        supporting_dimensions = []
        for dimension in source_dimensions:
            data = dimensions.get(dimension) or {}
            supporting_dimensions.append(compact_dict({
                "dimension": dimension,
                "label": data.get("label"),
                "overall_percentile": data.get("percentile"),
                "similar_use_percentile": data.get("percentile_frequency"),
            }))

        output.append({
            "theme": theme,
            "title": HUMAN_CAPITAL_THEMES[theme],
            "selection_basis": "ordered defining signals",
            "supporting_dimensions": supporting_dimensions,
            "supporting_evidence": _find_evidence_for_dimensions(
                evidence,
                source_dimensions,
                limit=2,
            ),
        })
    return output


def build_profile_synthesis_context(
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the complete context for the profile-synthesis Claude call."""
    validate_report_data(report_data)

    report_meta = report_data.get("report_meta") or {}
    distinctive_pattern = report_data.get("distinctive_pattern") or {}
    perception_summary = report_data.get("perception_summary") or {}

    return {
        "task": "profile_synthesis",
        "report_identity": compact_dict({
            "baseline_date": report_meta.get("baseline_date"),
            "reported_ai_use_frequency": report_meta.get(
                "reported_ai_use_frequency"
            ),
            "age_group": report_meta.get("age_group"),
        }),
        "benchmark_scope": benchmark_scope(report_meta),
        "profile_shape": [
            dimension_position(item)
            for item in report_data.get("position") or []
        ],
        "defining_signals": [
            dimension_position(item)
            for item in report_data.get("defining_signals") or []
        ],
        "similar_user_comparisons": [
            comparison_shift(item)
            for item in report_data.get("comparison_shifts") or []
        ],
        "strongest_pattern": {
            "mode": distinctive_pattern.get("mode"),
            "title": distinctive_pattern.get("title"),
            "combination": combination_item(
                distinctive_pattern.get("combination")
            ),
            "supporting_evidence": [
                evidence_item(item)
                for item in distinctive_pattern.get(
                    "supporting_evidence"
                ) or []
            ],
        },
        "main_evidence": [
            evidence_item(item)
            for item in report_data.get("evidence") or []
        ],
        "self_perception": {
            "items": [
                perception_item(item)
                for item in perception_summary.get("items") or []
            ],
            "largest_difference": perception_item(
                perception_summary.get("largest_difference") or {}
            ),
        },
        "human_capital_themes": select_human_capital_themes(
            report_data,
            limit=3,
        ),
        "required_outputs": {
            "signature_sentence": "one sentence",
            "combination_narrative": "two concise paragraphs",
            "pattern_narrative": "250–350 words",
            "human_capital_lens": "three one-sentence capability reflections",
        },
        "evidence_boundary": deepcopy(EVIDENCE_BOUNDARY),
        "writing_principles": list(WRITING_PRINCIPLES),
    }


def build_baseline_context(
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the complete context for the baseline Claude call."""
    validate_report_data(report_data)

    report_meta = report_data.get("report_meta") or {}
    baseline = report_data.get("baseline") or {}

    priorities = []
    for item in baseline.get("comparison_priorities") or []:
        priorities.append(compact_dict({
            "type": item.get("type"),
            "dimension": item.get("key"),
            "label": item.get("label"),
            "current_percentile": item.get("current_percentile"),
            "reason": item.get("reason"),
        }))

    return {
        "task": "baseline_return",
        "report_identity": compact_dict({
            "baseline_date": baseline.get("baseline_date"),
            "reported_ai_use_frequency": baseline.get(
                "reported_ai_use_frequency"
            ),
            "recommended_reassessment_window": baseline.get(
                "recommended_reassessment_window"
            ),
        }),
        "benchmark_scope": benchmark_scope(report_meta),
        "comparison_priorities": priorities,
        "defining_signals": [
            dimension_position(item)
            for item in baseline.get("defining_signals") or []
        ],
        "strongest_combination": combination_item(
            baseline.get("strongest_combination")
        ),
        "largest_perception_difference": perception_item(
            baseline.get("largest_perception_difference") or {}
        ),
        "required_outputs": {
            "return_question": (
                "one personalised question answerable only through a later "
                "comparison"
            ),
            "baseline_closing": (
                "one concise sentence describing the value of the dated baseline"
            ),
        },
        "longitudinal_boundary": {
            "permitted": [
                "The current report establishes a baseline.",
                "A future assessment can compare later responses and positions.",
            ],
            "not_permitted": [
                "Claiming personal change from one assessment.",
                "Claiming movement against a changed benchmark without a valid "
                "historical benchmark reference.",
            ],
        },
        "evidence_boundary": deepcopy(EVIDENCE_BOUNDARY),
        "writing_principles": list(WRITING_PRINCIPLES),
    }


def build_narrative_context(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """Return both narrative context packages under one canonical contract."""
    context = {
        "schema": NARRATIVE_CONTEXT_SCHEMA,
        "profile_synthesis": build_profile_synthesis_context(report_data),
        "baseline_return": build_baseline_context(report_data),
    }
    assert_narrative_context_contract(context)
    return context


def assert_narrative_context_contract(context: Dict[str, Any]) -> None:
    """Validate the compact narrative context contract."""
    if not isinstance(context, dict):
        raise ValueError("narrative context must be a dictionary")
    if context.get("schema") != NARRATIVE_CONTEXT_SCHEMA:
        raise ValueError(
            f"narrative context schema must be {NARRATIVE_CONTEXT_SCHEMA}"
        )

    for key in ("profile_synthesis", "baseline_return"):
        if key not in context:
            raise ValueError(
                f"narrative context missing required package: {key}"
            )

    profile = context["profile_synthesis"]
    baseline = context["baseline_return"]

    if len(profile.get("profile_shape") or []) != 9:
        raise ValueError("profile_synthesis must contain 9 dimension positions")
    if len(profile.get("defining_signals") or []) != 3:
        raise ValueError("profile_synthesis must contain 3 defining signals")
    if not 5 <= len(profile.get("main_evidence") or []) <= 7:
        raise ValueError("profile_synthesis must contain 5–7 evidence items")
    if len(profile.get("human_capital_themes") or []) != 3:
        raise ValueError(
            "profile_synthesis must contain 3 Human Capital themes"
        )
    if len(baseline.get("comparison_priorities") or []) != 3:
        raise ValueError(
            "baseline_return must contain 3 comparison priorities"
        )
