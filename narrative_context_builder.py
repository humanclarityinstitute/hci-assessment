"""
narrative_context_builder.py

HCI premium report V2 narrative-context builder.

Purpose
-------
This file does not calculate participant results and does not write report prose.
It converts the deterministic ``hci_report_data_v2`` object into two compact,
auditable context packages for Claude:

1. profile synthesis;
2. baseline and return question.

The builder deliberately excludes broad research-library dumps, trajectory
material, generic cohort narratives and unrelated Human Reference Layer content.
Claude receives only the evidence needed for the locked V2 report sections.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------
# Locked evidence and writing boundaries
# ---------------------------------------------------------------------

BENCHMARK_LABEL = "HCI participant benchmark"
BENCHMARK_SCOPE = "10,000+ participant responses across 21 HCI studies"

EVIDENCE_BOUNDARY = {
    "assessment_basis": (
        "The report is based on the participant's self-reported responses and "
        "their position within the HCI participant benchmark."
    ),
    "measured_finding_rule": (
        "State participant responses, calculated percentiles, supported cohort "
        "comparisons and approved rarity clearly and accurately."
    ),
    "interpretation_rule": (
        "Interpret what the measured pattern may suggest, but do not present an "
        "interpretation as an observed fact about the participant."
    ),
    "prohibited_claims": [
        "diagnosis or clinical classification",
        "personality type or fixed identity",
        "causation",
        "hidden psychological mechanism",
        "objective capability gain or loss",
        "dependency as a diagnosed condition",
        "future prediction",
        "individual change over time from one assessment",
        "general-population claims",
    ],
    "benchmark_language": (
        "Use 'HCI participant benchmark'. Do not call it a population norm, "
        "the general population, everyone or objective reality."
    ),
}

WRITING_PRINCIPLES = [
    "Reveal more. Explain only what improves clarity.",
    "State the measured finding strongly. Qualify the interpretation, not the evidence.",
    "Describe a current response pattern, not a permanent identity.",
    "Prefer direct, specific language over generic AI commentary.",
    "Do not repeat the same finding across multiple outputs.",
    "Do not add advice, prescriptions or behaviour-change instructions.",
]

HUMAN_CAPITAL_ALLOWED_THEMES = {
    "decision_authorship": "Decision authorship",
    "critical_scepticism": "Critical scepticism",
    "intellectual_openness": "Intellectual openness",
    "independent_view_formation": "Independent view formation",
    "privacy_boundaries": "Privacy boundaries",
    "emotional_discernment": "Emotional discernment",
}


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


def compact_list(values: Any) -> List[Any]:
    if not isinstance(values, list):
        return []
    return [item for item in values if item not in (None, "", [], {})]


def dimension_position(item: Dict[str, Any]) -> Dict[str, Any]:
    """Return only the fields Claude needs from one dimension result."""
    if not isinstance(item, dict):
        return {}
    return compact_dict({
        "key": item.get("key") or item.get("dimension"),
        "label": item.get("label"),
        "definition": item.get("definition"),
        "overall_percentile": (
            item.get("overall_percentile")
            if item.get("overall_percentile") is not None
            else item.get("percentile")
        ),
        "frequency_percentile": (
            item.get("frequency_percentile")
            if item.get("frequency_percentile") is not None
            else item.get("percentile_frequency")
        ),
        "age_percentile": (
            item.get("age_percentile")
            if item.get("age_percentile") is not None
            else item.get("percentile_age_group")
        ),
        "position": item.get("position") or item.get("overall_position"),
        "frequency_difference": item.get("frequency_difference"),
        "distance_from_centre": item.get("distance_from_centre"),
        "in_strongest_combination": item.get("in_strongest_combination"),
        "supporting_evidence_count": item.get("supporting_evidence_count"),
    })


def evidence_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Return an auditable question-level evidence object."""
    if not isinstance(item, dict):
        return {}
    return compact_dict({
        "key": item.get("key"),
        "dimension": item.get("dimension"),
        "dimension_label": item.get("dimension_label"),
        "question_text": item.get("question_text"),
        "answer": item.get("answer"),
        "answer_display": item.get("answer_display"),
        "overall_percentile": item.get("percentile"),
        "frequency_percentile": item.get("percentile_frequency"),
        "age_percentile": item.get("percentile_age_group"),
        "comparison_statement": item.get("comparison_statement"),
        "is_reverse_scored": item.get("is_reverse_scored"),
    })


def combination_item(item: Any) -> Optional[Dict[str, Any]]:
    """Return only supported combination fields."""
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
        "mode": "supported_rarity" if rarity_shareable else "combination_without_public_rarity",
        "rarity_percent": item.get("rarity_percent") if rarity_shareable else None,
        "rarity_source": item.get("rarity_source") if rarity_shareable else None,
        "sample_basis": item.get("sample_basis") if rarity_shareable else None,
        "rarity_shareable": rarity_shareable,
        "research_signal": item.get("research_signal"),
    })


def perception_item(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    return compact_dict({
        "key": item.get("key"),
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


def validate_v2_report_data(report_data: Dict[str, Any]) -> None:
    if not isinstance(report_data, dict):
        raise ValueError("report_data must be a dictionary")

    if report_data.get("schema_version") != "hci_report_data_v2":
        raise ValueError(
            "narrative_context_builder requires hci_report_data_v2"
        )

    required = [
        "report_meta",
        "signature",
        "position",
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


# ---------------------------------------------------------------------
# Human Capital Lens selection
# ---------------------------------------------------------------------

def select_human_capital_themes(
    report_data: Dict[str, Any],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    Select three relevant Human Capital themes from measured profile evidence.

    This selects themes only. It does not claim that a capability has developed,
    declined, strengthened or weakened.
    """
    dimensions = report_data.get("dimensions") or {}
    evidence = report_data.get("evidence") or []
    evidence_by_dimension: Dict[str, List[Dict[str, Any]]] = {}

    for item in evidence:
        if not isinstance(item, dict):
            continue
        dim = item.get("dimension")
        if dim:
            evidence_by_dimension.setdefault(dim, []).append(item)

    candidates = [
        {
            "theme_key": "decision_authorship",
            "title": HUMAN_CAPITAL_ALLOWED_THEMES["decision_authorship"],
            "dimensions": ["decision_delegation", "human_agency"],
        },
        {
            "theme_key": "critical_scepticism",
            "title": HUMAN_CAPITAL_ALLOWED_THEMES["critical_scepticism"],
            "dimensions": ["verification", "trust"],
        },
        {
            "theme_key": "intellectual_openness",
            "title": HUMAN_CAPITAL_ALLOWED_THEMES["intellectual_openness"],
            "dimensions": ["thought_partnership"],
        },
        {
            "theme_key": "independent_view_formation",
            "title": HUMAN_CAPITAL_ALLOWED_THEMES["independent_view_formation"],
            "dimensions": ["thought_partnership", "human_agency"],
        },
        {
            "theme_key": "privacy_boundaries",
            "title": HUMAN_CAPITAL_ALLOWED_THEMES["privacy_boundaries"],
            "dimensions": ["disclosure", "social_transparency"],
        },
        {
            "theme_key": "emotional_discernment",
            "title": HUMAN_CAPITAL_ALLOWED_THEMES["emotional_discernment"],
            "dimensions": ["emotional_regulation"],
        },
    ]

    ranked: List[Dict[str, Any]] = []
    for candidate in candidates:
        score = 0.0
        supporting_dimensions = []
        supporting_evidence = []

        for dim in candidate["dimensions"]:
            d = dimensions.get(dim) or {}
            percentile = clean_int(d.get("percentile"), 50) or 50
            score += abs(percentile - 50)
            supporting_dimensions.append(compact_dict({
                "key": dim,
                "label": d.get("label"),
                "percentile": percentile,
                "frequency_percentile": d.get("percentile_frequency"),
            }))

            for item in evidence_by_dimension.get(dim, []):
                supporting_evidence.append(evidence_item(item))
                score += 8

        ranked.append({
            "theme_key": candidate["theme_key"],
            "title": candidate["title"],
            "relevance_score": round(score, 2),
            "supporting_dimensions": supporting_dimensions,
            "supporting_evidence": supporting_evidence[:2],
        })

    ranked.sort(
        key=lambda item: item["relevance_score"],
        reverse=True,
    )
    return ranked[:limit]


# ---------------------------------------------------------------------
# Context package 1: profile synthesis
# ---------------------------------------------------------------------

def build_profile_synthesis_context(
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build the complete input for Claude call 1.

    Expected generated outputs:
    - signature sentence;
    - strongest-combination narrative or coherence narrative;
    - 250–350 word pattern narrative;
    - three short Human Capital Lens descriptions.
    """
    validate_v2_report_data(report_data)

    report_meta = report_data.get("report_meta") or {}
    signature = report_data.get("signature") or {}
    distinctive_pattern = report_data.get("distinctive_pattern") or {}
    perception_summary = report_data.get("perception_summary") or {}

    defining_signals = [
        dimension_position(item)
        for item in report_data.get("defining_signals") or []
    ]
    evidence = [
        evidence_item(item)
        for item in report_data.get("evidence") or []
    ]

    strongest_combination = combination_item(
        signature.get("strongest_combination")
        or distinctive_pattern.get("combination")
    )

    return {
        "task": "profile_synthesis",
        "report_identity": compact_dict({
            "report_version": report_meta.get("report_version"),
            "baseline_date": report_meta.get("baseline_date"),
            "reported_ai_use_frequency": report_meta.get(
                "reported_ai_use_frequency"
            ),
            "age_group": report_meta.get("age_group"),
        }),
        "benchmark_scope": compact_dict({
            "label": BENCHMARK_LABEL,
            "scope": BENCHMARK_SCOPE,
            "version": (
                (report_meta.get("benchmark") or {}).get("version")
            ),
        }),
        "defining_signals": defining_signals,
        "strongest_pattern": {
            "mode": distinctive_pattern.get("mode"),
            "title": distinctive_pattern.get("title"),
            "combination": strongest_combination,
            "supporting_evidence": [
                evidence_item(item)
                for item in distinctive_pattern.get(
                    "supporting_evidence"
                ) or []
            ],
        },
        "main_evidence": evidence,
        "perception": {
            "items": [
                perception_item(item)
                for item in perception_summary.get("items") or []
            ],
            "largest_difference": perception_item(
                perception_summary.get("largest_difference") or {}
            ),
        },
        "human_capital_candidates": select_human_capital_themes(
            report_data,
            limit=3,
        ),
        "required_outputs": {
            "signature_sentence": {
                "length": "one sentence",
                "purpose": (
                    "Describe the participant's current response pattern in a "
                    "specific, memorable way."
                ),
                "must_begin_from_evidence": True,
            },
            "combination_narrative": {
                "length": "two concise paragraphs",
                "structure": [
                    "what the data shows",
                    "what the pattern may suggest",
                ],
            },
            "pattern_narrative": {
                "length": "250–350 words",
                "purpose": (
                    "Explain how the defining results, evidence and perception "
                    "comparison fit together."
                ),
            },
            "human_capital_lens": {
                "count": 3,
                "length": "one concise sentence per theme",
                "rule": (
                    "Explain why each capability is relevant to this profile; "
                    "do not claim it has developed, declined or been measured."
                ),
            },
        },
        "evidence_boundary": deepcopy(EVIDENCE_BOUNDARY),
        "writing_principles": list(WRITING_PRINCIPLES),
    }


# ---------------------------------------------------------------------
# Context package 2: baseline and return question
# ---------------------------------------------------------------------

def build_baseline_context(
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build the complete input for Claude call 2.

    Expected generated outputs:
    - one personalised return question;
    - one short baseline closing sentence.
    """
    validate_v2_report_data(report_data)

    report_meta = report_data.get("report_meta") or {}
    baseline = report_data.get("baseline") or {}

    priorities = []
    for item in baseline.get("comparison_priorities") or []:
        priorities.append(compact_dict({
            "type": item.get("type"),
            "key": item.get("key"),
            "label": item.get("label"),
            "current_percentile": item.get("current_percentile"),
            "reason": item.get("reason"),
        }))

    return {
        "task": "baseline_return",
        "report_identity": compact_dict({
            "baseline_date": baseline.get("baseline_date"),
            "report_version": baseline.get("report_version"),
            "reported_ai_use_frequency": baseline.get(
                "reported_ai_use_frequency"
            ),
            "recommended_reassessment_window": baseline.get(
                "recommended_reassessment_window"
            ),
            "benchmark_version": (
                (baseline.get("benchmark") or {}).get("version")
            ),
        }),
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
            "return_question": {
                "length": "one sentence",
                "purpose": (
                    "Ask a personalised question that only a future assessment "
                    "can answer."
                ),
                "rules": [
                    "Do not predict what will happen.",
                    "Do not instruct the participant to change behaviour.",
                    "Frame the question around comparison over time.",
                ],
            },
            "baseline_closing": {
                "length": "one concise sentence",
                "purpose": (
                    "Reinforce that this report establishes a dated reference "
                    "point for later comparison."
                ),
            },
        },
        "longitudinal_boundary": {
            "permitted": [
                "The current report establishes a baseline.",
                "A future assessment can compare later responses and positions.",
            ],
            "not_yet_permitted": [
                "Claiming personal change from one assessment.",
                "Claiming movement relative to a changed benchmark unless "
                "historical benchmark versioning is operational.",
            ],
        },
        "evidence_boundary": deepcopy(EVIDENCE_BOUNDARY),
        "writing_principles": list(WRITING_PRINCIPLES),
    }


# ---------------------------------------------------------------------
# Public aggregate and compatibility entry points
# ---------------------------------------------------------------------

def build_full_narrative_context(
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Return both locked V2 context packages.

    The name is retained so the next rebuild of ``claude_narrative.py`` can
    transition cleanly without importing the old broad context architecture.
    """
    return {
        "schema_version": "hci_narrative_context_v2",
        "profile_synthesis": build_profile_synthesis_context(report_data),
        "baseline_return": build_baseline_context(report_data),
    }


def build_narrative_context(
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Alias for callers that use the shorter function name."""
    return build_full_narrative_context(report_data)


def assert_narrative_context_contract(context: Dict[str, Any]) -> None:
    if not isinstance(context, dict):
        raise ValueError("narrative context must be a dictionary")
    if context.get("schema_version") != "hci_narrative_context_v2":
        raise ValueError(
            "Unexpected narrative context schema version"
        )
    for key in ("profile_synthesis", "baseline_return"):
        if key not in context:
            raise ValueError(
                f"narrative context missing required package: {key}"
            )

    profile = context["profile_synthesis"]
    baseline = context["baseline_return"]

    if len(profile.get("defining_signals") or []) != 3:
        raise ValueError(
            "profile_synthesis must contain exactly 3 defining signals"
        )
    if not 5 <= len(profile.get("main_evidence") or []) <= 7:
        raise ValueError(
            "profile_synthesis must contain 5–7 evidence items"
        )
    if len(profile.get("human_capital_candidates") or []) != 3:
        raise ValueError(
            "profile_synthesis must contain exactly 3 Human Capital themes"
        )
    if len(baseline.get("comparison_priorities") or []) != 3:
        raise ValueError(
            "baseline_return must contain exactly 3 comparison priorities"
        )
