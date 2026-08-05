"""
narrative_context_builder.py

Clean replacement for the old signal_selection.py.

Purpose
-------
This file does NOT write report prose.
It prepares HCI-grounded context for Claude sections.

It combines:
- report_data
- hci_signals_library.py
- human_reference_layer.py
- benchmark_context_data.py
- distinctiveness/routing logic from deleted signal_selection.py

Claude receives this as grounding. The renderer remains deterministic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from copy import deepcopy

try:
    # Participant-facing narrative context must use the restrained source layer.
    # Fail closed to empty context rather than reverting to the internal synthesis.
    from hci_signals_library import REPORT_SAFE_SIGNALS as SIGNALS
except Exception:
    SIGNALS = {"dimensions": {}, "trends": {}, "combinations": {}, "human_reference": {}}

try:
    import human_reference_layer as HRL
except Exception:
    HRL = None

try:
    from benchmark_context_data import (
        FREQUENCY_GRADIENTS,
        AGE_COHORT_PATTERNS,
        DISTINCTIVE_FLAGS,
        KEY_FINDINGS_FOR_REPORTS,
        COHORT_NARRATIVES,
    )
except Exception:
    FREQUENCY_GRADIENTS = {}
    AGE_COHORT_PATTERNS = {}
    DISTINCTIVE_FLAGS = {}
    KEY_FINDINGS_FOR_REPORTS = {}
    COHORT_NARRATIVES = {}

try:
    from report_templates import (
        DIMENSION_LABELS,
        DIMENSION_DEFINITIONS,
        DIMENSION_ORDER,
        percentile_position,
        protect_position,
    )
except Exception:
    DIMENSION_LABELS = {}
    DIMENSION_DEFINITIONS = {}
    DIMENSION_ORDER = []
    def percentile_position(p): return "near the HCI benchmark centre"
    def protect_position(p): return "in the middle"


GLOBAL_EVIDENCE_BOUNDARY = {
    "assessment_basis": (
        "This assessment is based on the participant's self-reported responses "
        "and comparison with the HCI participant benchmark."
    ),
    "permitted_claims": (
        "State participant responses, benchmark positions, exact supported group "
        "differences and cautiously worded possible interpretations."
    ),
    "prohibited_inferences": (
        "Do not infer diagnosis, personality type, causation, fixed traits, "
        "objective capability, individual change over time, future outcomes, "
        "dependency, impairment or better outcomes."
    ),
    "comparison_scope": (
        "Use HCI participant benchmark language. Do not describe the benchmark "
        "as the general population or a population norm."
    ),
}

EVIDENCE_TYPE_DEFINITIONS = {
    "participant_response": "A response or score derived from this participant's self-report.",
    "benchmark_position": "The participant's position within the HCI participant benchmark.",
    "observed_group_pattern": "A supported difference or recurring pattern observed across HCI participant groups.",
    "possible_interpretation": "A cautious explanatory frame that is not established as cause or participant-specific fact.",
}

DIMENSION_KEY_FINDING_MAP = {
    "verification": "verification_paradox",
    "disclosure": "disclosure_strongest_effect",
    "emotional_regulation": "emotional_engagement_expansion",
    "human_agency": "agency_resilience",
    "thought_partnership": "thought_partnership_inevitability",
    "social_transparency": "concealment_gap",
}

FREQUENCY_ALIASES = {
    "daily": "everyday",
    "every day": "everyday",
    "every_day": "everyday",
    "veryoften": "very often",
    "very_often": "very often",
    "very-often": "very often",
    "occasionally": "sometimes",
    "occasional": "sometimes",
}


# ---------------------------------------------------------------------
# Distinctiveness logic
# ---------------------------------------------------------------------

def clean_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def calculate_distinctiveness_from_percentile(percentile: Any) -> Dict[str, Any]:
    """
    Percentile-based distinctiveness used for report routing.

    This is more reliable than raw score vs frequency expectation because the current
    benchmark pipeline already calculates percentile positions.
    """
    p = clean_float(percentile, 50) or 50
    distance = abs(p - 50)

    if distance <= 15:
        level = "expected"
        significance = 0.3
    elif distance <= 25:
        level = "slightly_divergent"
        significance = 0.6
    elif distance <= 40:
        level = "distinctive"
        significance = 0.85
    else:
        level = "highly_distinctive"
        significance = 1.0

    direction = "above" if p > 50 else "below" if p < 50 else "at"

    return {
        "percentile": int(round(p)),
        "distance_from_centre": int(round(distance)),
        "level": level,
        "direction": direction,
        "significance": significance,
        "positioning_language": percentile_position(p),
    }


def select_signal_layers(distinctiveness: Dict[str, Any]) -> Dict[str, Any]:
    level = distinctiveness.get("level", "expected")

    if level == "expected":
        return {
            "include_benchmark": True,
            "include_master_synthesis": False,
            "include_human_reference": False,
            "depth": "light",
            "emphasis_level": "brief",
            "note": "This is close to the HCI benchmark centre.",
        }

    if level == "slightly_divergent":
        return {
            "include_benchmark": True,
            "include_master_synthesis": True,
            "include_human_reference": False,
            "depth": "medium",
            "emphasis_level": "standard",
            "note": "This diverges somewhat from the HCI benchmark centre.",
        }

    return {
        "include_benchmark": True,
        "include_master_synthesis": True,
        "include_human_reference": True,
        "depth": "full",
        "emphasis_level": "detailed",
        "note": "This pattern is distinctive enough to receive full HCI interpretation.",
    }


# ---------------------------------------------------------------------
# Asset selection
# ---------------------------------------------------------------------


def dimension_signal(dimension: str, percentile: Any) -> Dict[str, Any]:
    """Select only participant-safe dimension fields and label their evidence type."""
    signals = SIGNALS.get("dimensions", {}) if isinstance(SIGNALS, dict) else {}
    source = signals.get(dimension) or signals.get(DIMENSION_LABELS.get(dimension, dimension)) or {}

    if not isinstance(source, dict):
        source = {}

    try:
        p = int(round(float(percentile)))
    except Exception:
        p = 50

    if p >= 71:
        selected = source.get("high")
        band = "high"
    elif p <= 40:
        selected = source.get("low")
        band = "low"
    else:
        selected = source.get("typical")
        band = "typical"

    selected = selected or source.get("series") or source.get("definition") or ""

    observed_group_pattern = source.get("series")
    return {
        "definition": source.get("definition"),
        "participant_position_band": band,
        "selected": {
            "evidence_type": "possible_interpretation",
            "text": selected,
        },
        "observed_group_pattern": (
            {
                "evidence_type": "observed_group_pattern",
                "text": observed_group_pattern,
            }
            if observed_group_pattern
            else None
        ),
        "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
    }



def combination_signal(d1: str, d2: str, item: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resolve one participant-safe rare-combination signal without passing the full library."""
    combos = SIGNALS.get("combinations", {}) if isinstance(SIGNALS, dict) else {}
    item = item or {}

    candidate_keys = []
    for key in [
        item.get("combination_id"),
        item.get("research_key"),
        item.get("signal_type"),
        f"{d1}+{d2}",
        f"{d2}+{d1}",
        f"{d1}_{d2}",
        f"{d2}_{d1}",
    ]:
        if key:
            candidate_keys.append(str(key))

    b1 = item.get("band_dim1")
    b2 = item.get("band_dim2")
    if b1 and b2:
        candidate_keys.extend([
            f"{b1}_{d1}_{b2}_{d2}",
            f"{b2}_{d2}_{b1}_{d1}",
        ])

    source = None
    for key in candidate_keys:
        value = combos.get(key)
        if value is not None:
            source = value
            break

    if isinstance(source, dict):
        return {
            "rarity": source.get("rarity") or item.get("rarity_percent"),
            "observed_group_pattern": {
                "evidence_type": "observed_group_pattern",
                "text": source.get("why_unusual"),
            },
            "possible_interpretation": {
                "evidence_type": "possible_interpretation",
                "text": source.get("what_it_reveals"),
            },
            "research_context": {
                "evidence_type": "observed_group_pattern",
                "text": source.get("research_signal"),
            },
            "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
        }

    fallback = item.get("research_signal")
    return {
        "rarity": item.get("rarity_percent"),
        "observed_group_pattern": None,
        "possible_interpretation": (
            {
                "evidence_type": "possible_interpretation",
                "text": str(fallback),
            }
            if fallback
            else None
        ),
        "research_context": None,
        "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
    }



def human_reference_context(
    dimension: str,
    percentile: Any,
    age_group: Any = None,
) -> Dict[str, Any]:
    """
    Whitelist participant-safe HRL fields.

    Human-reference content is possible interpretation, not participant-specific
    evidence. Raw Values Signals, Reframe Library and Research Insights are not
    passed through generically.
    """
    if HRL is None:
        return {}

    context: Dict[str, Any] = {
        "evidence_type": "possible_interpretation",
        "dimension_context": {},
        "cohort_context": {},
        "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
    }

    framework = getattr(HRL, "HBE_FRAMEWORK", None)
    if isinstance(framework, dict):
        value = framework.get(dimension) or framework.get(DIMENSION_LABELS.get(dimension, dimension))
        if isinstance(value, dict):
            context["dimension_context"] = {
                "general_human_context": value.get("hbe_baseline"),
                "possible_ai_context": value.get("ai_pressure"),
                "participant_safe_reframe": value.get("reframe"),
            }
            context["dimension_context"] = {
                key: value
                for key, value in context["dimension_context"].items()
                if value is not None
            }

    p = clean_float(percentile, 50) or 50
    position = "high" if p >= 71 else "low" if p <= 40 else "moderate"

    fn = getattr(HRL, "get_values_reframe", None)
    if callable(fn):
        try:
            value = fn(dimension, position)
            if value and "not available in library" not in str(value):
                context["values_reframe"] = value
        except Exception:
            pass

    cohorts = getattr(HRL, "HBE_COHORT_REFRAMES", None)
    age = str(age_group or "").strip()
    if isinstance(cohorts, dict) and age in cohorts and isinstance(cohorts[age], dict):
        cohort = cohorts[age]
        context["cohort_context"] = {
            "observed_cohort_context": cohort.get("profile"),
            "possible_context": cohort.get("pressure_point"),
            "participant_safe_reframe": cohort.get("reframe"),
        }
        context["cohort_context"] = {
            key: value
            for key, value in context["cohort_context"].items()
            if value is not None
        }

    if not context["dimension_context"] and not context["cohort_context"] and not context.get("values_reframe"):
        return {}

    return context



def normalise_frequency_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = " ".join(text.split())
    return FREQUENCY_ALIASES.get(text, text)


def safe_frequency_gradient(dimension: str, frequency: Any) -> Dict[str, Any]:
    source = FREQUENCY_GRADIENTS.get(dimension, {})
    if not isinstance(source, dict):
        return {}

    freq = normalise_frequency_key(frequency)
    group_keys = ["never", "rarely", "sometimes", "often", "very often", "everyday"]
    group_values = {
        key: source.get(key)
        for key in group_keys
        if isinstance(source.get(key), (int, float))
    }

    context = {
        "evidence_type": "observed_group_pattern",
        "participant_frequency": freq or None,
        "participant_group_value": source.get(freq) if freq else None,
        "group_values": group_values,
        "range": source.get("range"),
        "note": source.get("note"),
        "key_finding": source.get("key_finding"),
        "scale_note": source.get("scale_note"),
        "data_quality_note": source.get("data_quality_note"),
        "gender_note": source.get("gender_note"),
        "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
    }

    # Do not pass a known disputed range into Claude as evidence.
    if context.get("data_quality_note"):
        context["range"] = None

    return {key: value for key, value in context.items() if value not in (None, {}, [])}


def safe_age_cohort_context(age_group: Any) -> Dict[str, Any]:
    age = str(age_group or "").strip()
    source = AGE_COHORT_PATTERNS.get(age, {})
    if not isinstance(source, dict):
        return {}

    evidence_fields = {}
    for key, value in source.items():
        if isinstance(value, (int, float)) or key.endswith("_mean") or key in {
            "values_clarity",
            "verification_diligence",
            "control_over_ai_use",
            "attention_recovery",
            "saturation",
            "agency_without_ai",
            "decision_delegation",
            "self_directed_decisions",
            "confidence_without_ai",
            "ai_detection_confidence",
            "verification_external_sources",
            "social_transparency",
            "concealment",
            "agency",
            "ver_q3",
            "identity_conflict",
            "disc_q3",
        }:
            evidence_fields[key] = value

    possible_context = [
        source.get(key)
        for key in ("interpretation", "tension", "strength", "capacity", "note")
        if source.get(key)
    ]

    return {
        "cohort": age or None,
        "description": source.get("description"),
        "observed_group_pattern": {
            "evidence_type": "observed_group_pattern",
            "values": evidence_fields,
            "distinctive": list(source.get("distinctive") or []),
        },
        "possible_interpretation": (
            {
                "evidence_type": "possible_interpretation",
                "text": possible_context,
            }
            if possible_context
            else None
        ),
        "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
    }


def key_finding_for_dimension(dimension: str) -> Dict[str, Any]:
    """
    Select the actual dimension-level key finding.

    The source dictionary is keyed by research finding names, not by
    <dimension>_<high|low|typical>. An explicit map avoids the previous
    always-None lookup.
    """
    finding_key = DIMENSION_KEY_FINDING_MAP.get(dimension)
    source = KEY_FINDINGS_FOR_REPORTS.get(finding_key, {}) if finding_key else {}
    if not isinstance(source, dict):
        return {}

    observed_keys = (
        "statement",
        "finding",
        "specifics",
        "slight_reversal",
        "younger_overreliance",
        "older_verification",
        "dose_response",
        "gender_note",
    )
    interpretation_keys = (
        "implication",
        "nature",
        "nuance",
        "possible_context",
        "trajectory",
        "distinction",
        "report_language",
    )

    observed = {
        key: source.get(key)
        for key in observed_keys
        if source.get(key) is not None
    }
    interpretation = {
        key: source.get(key)
        for key in interpretation_keys
        if source.get(key) is not None
    }

    return {
        "finding_key": finding_key,
        "observed_group_pattern": (
            {
                "evidence_type": "observed_group_pattern",
                "values": observed,
            }
            if observed
            else None
        ),
        "possible_interpretation": (
            {
                "evidence_type": "possible_interpretation",
                "values": interpretation,
            }
            if interpretation
            else None
        ),
        "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
    }


def safe_cohort_narrative(age_group: Any) -> Dict[str, Any]:
    age = str(age_group or "").strip()
    source = COHORT_NARRATIVES.get(age, {})
    if not isinstance(source, dict):
        return {}

    observed = {
        key: source.get(key)
        for key in ("label", "pattern", "strength", "depth", "distinctive")
        if source.get(key) is not None
    }
    interpretation = {
        key: source.get(key)
        for key in ("paradox", "observation", "limitation", "advantage")
        if source.get(key) is not None
    }

    return {
        "cohort": age or None,
        "observed_group_pattern": (
            {
                "evidence_type": "observed_group_pattern",
                "values": observed,
            }
            if observed
            else None
        ),
        "possible_interpretation": (
            {
                "evidence_type": "possible_interpretation",
                "values": interpretation,
            }
            if interpretation
            else None
        ),
        "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
    }



def benchmark_context(dimension: str, frequency: Any, age_group: Any, percentile: Any) -> Dict[str, Any]:
    """
    Return a compact, consistently shaped benchmark context.

    Raw pressure-point lists and entire interpretive dictionaries are excluded.
    """
    return {
        "frequency_gradient": safe_frequency_gradient(dimension, frequency),
        "age_cohort_pattern": safe_age_cohort_context(age_group),
        "key_finding": key_finding_for_dimension(dimension),
        "cohort_narrative": safe_cohort_narrative(age_group),
        "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
    }



def distinctive_flags_for_dimension(dimension: str, percentile: Any, frequency: Any) -> List[Dict[str, Any]]:
    p = clean_float(percentile, 50) or 50
    freq = normalise_frequency_key(frequency)
    flags = []

    checks = {
        "high_verification_high_frequency": dimension == "verification" and p >= 71 and freq == "everyday",
        "low_reliance_high_frequency": dimension == "reliance" and p <= 40 and freq == "everyday",
        "high_emotional_engagement_low_frequency": dimension == "emotional_regulation" and p >= 71 and freq in {"rarely", "sometimes"},
        "low_disclosure_high_frequency": dimension == "disclosure" and p <= 40 and freq == "everyday",
        "low_emotional_engagement_high_frequency": dimension == "emotional_regulation" and p <= 40 and freq == "everyday",
    }

    for key, condition in checks.items():
        if not condition:
            continue

        data = DISTINCTIVE_FLAGS.get(key, {})
        if not isinstance(data, dict):
            data = {}

        flags.append({
            "flag": key,
            "rarity": data.get("rarity"),
            "observed_group_pattern": {
                "evidence_type": "observed_group_pattern",
                "text": data.get("why_rare"),
            },
            "possible_interpretation": {
                "evidence_type": "possible_interpretation",
                "meaning": data.get("meaning"),
                "research_context": data.get("research_insight"),
            },
            "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
        })

    return flags



def build_dimension_context(report_data: Dict[str, Any], dimension: str) -> Dict[str, Any]:
    dimensions = report_data.get("dimensions") or {}
    d = dimensions.get(dimension) or {}
    demographics = report_data.get("demographics") or {}
    percentile = d.get("percentile")

    frequency = demographics.get("_frequency_benchmark") or demographics.get("ai_tool_use_frequency") or demographics.get("frequency")
    age_group = demographics.get("_age_group_benchmark") or demographics.get("age_group")

    distinctiveness = calculate_distinctiveness_from_percentile(percentile)
    signal_layers = select_signal_layers(distinctiveness)

    return {
        "dimension": dimension,
        "label": d.get("label") or DIMENSION_LABELS.get(dimension, dimension),
        "definition": d.get("definition") or DIMENSION_DEFINITIONS.get(dimension, ""),
        "participant_response": {
            "evidence_type": "participant_response",
            "raw_score": d.get("raw_score"),
        },
        "benchmark_position": {
            "evidence_type": "benchmark_position",
            "percentile": percentile,
            "position": d.get("position") or percentile_position(percentile),
            "protect_position": d.get("protect_position") or protect_position(percentile),
        },
        # Retain the established scalar fields for downstream compatibility.
        "percentile": percentile,
        "raw_score": d.get("raw_score"),
        "position": d.get("position") or percentile_position(percentile),
        "protect_position": d.get("protect_position") or protect_position(percentile),
        "distinctiveness": distinctiveness,
        "signal_layers": signal_layers,
        "dimension_signal": dimension_signal(dimension, percentile),
        "benchmark_context": benchmark_context(dimension, frequency, age_group, percentile),
        "human_reference": (
            human_reference_context(dimension, percentile, age_group)
            if signal_layers.get("include_human_reference")
            else {}
        ),
        "distinctive_flags": distinctive_flags_for_dimension(dimension, percentile, frequency),
        # Legacy keys remain present but unsafe future-oriented template copy is
        # not forwarded into Claude context.
        "strength_deepening": {},
        "monitoring": {},
        "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
    }


def build_full_narrative_context(report_data: Dict[str, Any]) -> Dict[str, Any]:
    dimensions = report_data.get("dimensions") or {}
    dimension_contexts = {
        dim: build_dimension_context(report_data, dim)
        for dim in DIMENSION_ORDER
        if dim in dimensions
    }

    return {
        "profile": {
            "session_id": report_data.get("session_id"),
            "demographics": report_data.get("demographics", {}),
            "top_dimensions": slim_dimensions((report_data.get("synthesis_inputs") or {}).get("top_dimensions", [])),
            "lowest_dimensions": slim_dimensions((report_data.get("synthesis_inputs") or {}).get("lowest_dimensions", [])),
            "most_distinctive_variable": slim_question((report_data.get("synthesis_inputs") or {}).get("most_distinctive_variable")),
            "largest_perception_gap": (report_data.get("synthesis_inputs") or {}).get("largest_perception_gap"),
            "top_rare_combination": (report_data.get("synthesis_inputs") or {}).get("top_rare_combination"),
        },
        "dimension_contexts": dimension_contexts,
        "rare_combinations": enrich_rare_combinations(report_data),
        "distinctive_responses": enrich_distinctive_responses(report_data),
        "perception_gap": report_data.get("perception_gap", {}),
        "trajectory": build_trajectory_context(report_data, dimension_contexts),
        "global_hci_assets": {
            "benchmark_scope": {
                "benchmark_label": "HCI participant benchmark",
                "participant_responses": "10,000+",
                "studies": 21,
            },
            "evidence_type_definitions": EVIDENCE_TYPE_DEFINITIONS,
            "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
            "hci_principles": [
                "Describe self-reported patterns, not personality types.",
                "Distinguish participant responses, benchmark positions, observed group patterns and possible interpretations.",
                "State supported evidence clearly; qualify interpretation rather than weakening the evidence.",
                "Do not convert association into causation or group patterns into individual facts.",
                "Do not diagnose, prescribe behaviour, predict outcomes or claim capability development or loss.",
                "Use HCI participant benchmark language, not general-population language.",
                "Use direct plain English.",
            ],
        },
    }


def build_human_capital_context(report_data: Dict[str, Any], full: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the full evidence context for Section 9: Your Human Capital.

    This context is intentionally broad. Human Capital translates the complete
    participant profile into human capabilities, so Claude should synthesize
    across the whole report rather than rely on any single dimension.
    """
    narrative_blocks = report_data.get("narrative_blocks") or {}
    question_evidence = []
    for q in report_data.get("questions") or []:
        if not isinstance(q, dict):
            continue
        question_evidence.append({
            "dimension": q.get("dimension"),
            "dimension_label": q.get("dimension_label"),
            "question_text": q.get("question_text"),
            "answer_display": q.get("answer_display"),
            "percentile": q.get("percentile"),
            "percentile_frequency": q.get("percentile_frequency"),
            "comparison_statement": q.get("comparison_statement"),
            "is_reverse_scored": q.get("is_reverse_scored"),
        })

    profile_shape = report_data.get("typicality") or {}

    return {
        "section_purpose": (
            "Translate current self-reported benchmark patterns into capability-related "
            "themes without claiming that a capability is developing, declining or objectively measured."
        ),
        "profile": full.get("profile", {}),
        "dimension_contexts": full.get("dimension_contexts", {}),
        "profile_shape": {
            "distinctive": slim_dimensions(profile_shape.get("distinctive", [])),
            "typical": slim_dimensions(profile_shape.get("typical", [])),
            "moderate": slim_dimensions(profile_shape.get("moderate", [])),
            "all": slim_dimensions(profile_shape.get("all", [])),
        },
        "rare_combinations": full.get("rare_combinations", []),
        "distinctive_responses": full.get("distinctive_responses", []),
        "question_level_evidence": question_evidence,
        "perception_gap": full.get("perception_gap", {}),
        "trajectory": full.get("trajectory", {}),
        "previous_narrative_blocks": {
            "opening_findings": narrative_blocks.get("opening_findings"),
            "profile_shape_summary": narrative_blocks.get("profile_shape_summary"),
            "rare_combinations_narrative": narrative_blocks.get("rare_combinations_narrative"),
            "behaviour_story": narrative_blocks.get("behaviour_story"),
            "distinctive_responses_narrative": narrative_blocks.get("distinctive_responses_narrative"),
            "perception_gap_narrative": narrative_blocks.get("perception_gap_narrative"),
        },
        "global_hci_assets": full.get("global_hci_assets", {}),
        "translation_rules": [
            "Translate reported behaviour into capability-related themes, not measured capability.",
            "Use plain human language.",
            "Do not mention dimensions, percentiles, scores, or benchmark mechanics in the final prose.",
            "Do not invent aspirational qualities unsupported by the evidence.",
            "Do not give advice, predict future outcomes, or judge behaviour.",
        ],
    }



def build_closing_reflection_context(report_data: Dict[str, Any], full: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build synthesized whole-report context for Section 12: Closing Reflection.

    This is intentionally different from earlier context builders. The closing
    reflection should look back across the completed report narrative and render-
    ready section evidence rather than receive a fresh dump of raw benchmark
    mechanics. Its job is to help Claude distil the report into one enduring
    question and one calm conclusion.
    """
    narrative_blocks = report_data.get("narrative_blocks") or {}

    # Human Capital may be stored either as a nested object from the latest
    # architecture or as flat legacy keys from earlier Claude outputs.
    human_capital = narrative_blocks.get("human_capital")
    if not isinstance(human_capital, dict):
        human_capital = {
            "capabilities_developing": narrative_blocks.get("capabilities_developing", []),
            "worth_protecting": narrative_blocks.get("worth_protecting", []),
            "worth_watching": narrative_blocks.get("worth_watching", []),
            "human_capital_priorities": narrative_blocks.get("human_capital_priorities", []),
            "closing": narrative_blocks.get("human_capital_closing") or narrative_blocks.get("closing"),
        }

    looking_forward_items = []
    for item in report_data.get("what_to_protect") or []:
        if not isinstance(item, dict):
            continue
        looking_forward_items.append({
            "dimension": item.get("dimension") or item.get("key"),
            "label": item.get("label") or item.get("capacity"),
            "title": item.get("title"),
            "positioning": item.get("positioning"),
        })

    trajectory = full.get("trajectory", {})

    return {
        "section_purpose": (
            "Distil the completed benchmark report into one enduring question "
            "and one hopeful closing reflection."
        ),
        "profile": full.get("profile", {}),
        "synthesized_report_context": {
            "initial_analysis": narrative_blocks.get("opening_findings"),
            "profile_shape": narrative_blocks.get("profile_shape_summary"),
            "rare_combinations": narrative_blocks.get("rare_combinations_narrative"),
            "behaviour_story": narrative_blocks.get("behaviour_story"),
            "distinctive_responses": narrative_blocks.get("distinctive_responses_narrative"),
            "self_perception": narrative_blocks.get("perception_gap_narrative"),
            "dimension_deep_dives": narrative_blocks.get("deep_dive"),
            "human_capital": human_capital,
            "remeasurement_context": {
                "highest_dimension": trajectory.get("highest_dimension"),
                "comparison_anchor": trajectory.get("comparison_anchor"),
                "current_high_signals": trajectory.get("current_high_signals", []),
                "areas_for_later_comparison": trajectory.get("areas_for_later_comparison", []),
            },
            "looking_forward": {
                "purpose": "Current signals that may be useful to compare at a later measurement.",
                "items": looking_forward_items,
            },
        },
        "evidence_anchors": {
            "top_dimensions": full.get("profile", {}).get("top_dimensions", []),
            "lowest_dimensions": full.get("profile", {}).get("lowest_dimensions", []),
            "most_distinctive_variable": full.get("profile", {}).get("most_distinctive_variable"),
            "largest_perception_gap": full.get("profile", {}).get("largest_perception_gap"),
            "top_rare_combination": full.get("profile", {}).get("top_rare_combination"),
            "rare_combinations": full.get("rare_combinations", [])[:2],
            "distinctive_responses": full.get("distinctive_responses", [])[:5],
        },
        "closing_rules": [
            "Use synthesized evidence already established elsewhere in the report.",
            "Do not introduce new benchmark evidence or new interpretation.",
            "Do not give advice, recommendations, coaching, or action steps.",
            "Distil the report into one question the participant can carry forward.",
            "The question should not be answerable today; it should become more meaningful over time.",
            "Strong reported agency may be acknowledged as part of the current pattern. Do not make identity-stability claims.",
            "End with the participant's continuing measurement journey, not with organisational promotion.",
        ],
        "global_hci_assets": {
            "hci_principles": (full.get("global_hci_assets", {}) or {}).get("hci_principles", []),
        },
    }



def with_evidence_boundary(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload or {})
    out["evidence_boundary"] = GLOBAL_EVIDENCE_BOUNDARY
    return out


def build_context_for_claude_section(report_data: Dict[str, Any], section: str) -> Dict[str, Any]:
    full = build_full_narrative_context(report_data)

    if section == "opening":
        return with_evidence_boundary({
            "profile": full["profile"],
            "most_distinctive_variable": full["profile"]["most_distinctive_variable"],
            "largest_perception_gap": full["profile"]["largest_perception_gap"],
            "top_rare_combination": full["profile"]["top_rare_combination"],
            "global_hci_assets": full["global_hci_assets"],
        })

    if section == "rare_combinations":
        return with_evidence_boundary({
            "rare_combinations": full["rare_combinations"],
            "dimension_contexts": full["dimension_contexts"],
            "global_hci_assets": full["global_hci_assets"],
        })

    if section == "behaviour_story":
        return with_evidence_boundary({
            "profile": full["profile"],
            "dimension_contexts": full["dimension_contexts"],
            "rare_combinations": full["rare_combinations"],
            "perception_gap": full["perception_gap"],
            "global_hci_assets": full["global_hci_assets"],
        })

    if section == "deep_dive":
        return with_evidence_boundary({
            "profile": full["profile"],
            "deep_dive_candidate": select_deep_dive_candidate(full),
            "dimension_contexts": full["dimension_contexts"],
            "rare_combinations": full["rare_combinations"],
            "distinctive_responses": full["distinctive_responses"][:3],
            "perception_gap": full["perception_gap"],
            "trajectory": full["trajectory"],
            "previous_narrative_blocks": report_data.get("narrative_blocks", {}),
            "global_hci_assets": full["global_hci_assets"],
        })

    if section == "distinctive_responses":
        return with_evidence_boundary({
            "distinctive_responses": full["distinctive_responses"],
            "dimension_contexts": full["dimension_contexts"],
            "global_hci_assets": full["global_hci_assets"],
        })

    if section == "perception_gap":
        return with_evidence_boundary({
            "perception_gap": full["perception_gap"],
            "profile": full["profile"],
            "dimension_contexts": {
                k: v for k, v in full["dimension_contexts"].items()
                if k in {"reliance", "decision_delegation", "thought_partnership"}
            },
            "global_hci_assets": full["global_hci_assets"],
        })

    if section == "human_capital":
        return with_evidence_boundary(build_human_capital_context(report_data, full))

    if section == "closing_reflection":
        return with_evidence_boundary(build_closing_reflection_context(report_data, full))

    if section == "trajectory":
        return with_evidence_boundary({
            "trajectory": full["trajectory"],
            "dimension_contexts": full["dimension_contexts"],
            "global_hci_assets": full["global_hci_assets"],
        })

    return with_evidence_boundary(full)



def select_deep_dive_candidate(full_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Select the most valuable Deep Dive focus.

    Priority:
    1. Rare combination if present.
    2. Most distinctive response if very extreme.
    3. Largest perception gap if significant.
    4. Highest dimension as fallback.
    """
    rare = full_context.get("rare_combinations") or []
    if rare:
        return {
            "type": "rare_combination",
            "reason": "Rare combinations are the most information-rich HCI pattern when present.",
            "data": rare[0],
        }

    most = (full_context.get("profile") or {}).get("most_distinctive_variable")
    if isinstance(most, dict):
        pct = clean_float(most.get("percentile"), 50) or 50
        if abs(pct - 50) >= 35:
            return {
                "type": "distinctive_response",
                "reason": "The strongest individual response is unusually far from the HCI benchmark centre.",
                "data": most,
            }

    gap = (full_context.get("profile") or {}).get("largest_perception_gap")
    if gap:
        return {
            "type": "perception_gap",
            "reason": "The largest difference between self-perception and benchmark position may be a useful point of interpretation.",
            "data": gap,
        }

    top = (full_context.get("profile") or {}).get("top_dimensions") or []
    if top:
        return {
            "type": "highest_dimension",
            "reason": "The highest dimension is the clearest organising feature of the profile.",
            "data": top[0],
        }

    return {
        "type": "overall_pattern",
        "reason": "No single rare pattern dominates, so the Deep Dive should focus on the overall profile shape.",
        "data": full_context.get("profile", {}),
    }

# ---------------------------------------------------------------------
# Enrichers
# ---------------------------------------------------------------------

def enrich_rare_combinations(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    enriched = []
    for combo in report_data.get("rare_combinations") or []:
        item = deepcopy(combo)
        d1 = item.get("dimension_1")
        d2 = item.get("dimension_2")
        item["signal"] = combination_signal(d1, d2, item)
        item["dimension_1_context"] = build_dimension_context(report_data, d1) if d1 else {}
        item["dimension_2_context"] = build_dimension_context(report_data, d2) if d2 else {}
        enriched.append(item)
    return enriched


def enrich_distinctive_responses(report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for q in report_data.get("distinctive_responses") or []:
        item = deepcopy(q)
        dim = item.get("dimension")
        item["dimension_context"] = build_dimension_context(report_data, dim) if dim else {}
        out.append(item)
    return out[:7]



def build_trajectory_context(report_data: Dict[str, Any], dimension_contexts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert legacy future-oriented report_data fields into current-state and
    remeasurement context for Claude. No future change is inferred.
    """
    data = report_data.get("if_nothing_changes") or {}

    current_high_signals = []
    for d in data.get("strengths_likely_to_deepen", []):
        if not isinstance(d, dict):
            continue
        current_high_signals.append({
            "dimension": d.get("key"),
            "label": d.get("label"),
            "percentile": d.get("percentile"),
            "position": d.get("position"),
            "research_signal": d.get("research_insight"),
            "evidence_type": "benchmark_position",
        })

    later_comparison = []
    for d in data.get("areas_worth_monitoring", []):
        if not isinstance(d, dict):
            continue
        later_comparison.append({
            "dimension": d.get("key"),
            "label": d.get("label"),
            "percentile": d.get("percentile"),
            "position": d.get("position"),
            "research_signal": d.get("research_insight"),
            "evidence_type": "benchmark_position",
        })

    return {
        "usage_frequency": data.get("usage_frequency"),
        "highest_dimension": slim_dimension(data.get("highest_dimension")),
        "comparison_anchor": slim_dimension(data.get("monitoring_anchor")),
        "current_high_signals": current_high_signals,
        "areas_for_later_comparison": later_comparison,
        "evidence_boundary": GLOBAL_EVIDENCE_BOUNDARY,
    }


def slim_dimension(d: Any) -> Dict[str, Any] | None:
    if not isinstance(d, dict):
        return None
    return {
        "key": d.get("key"),
        "label": d.get("label"),
        "definition": d.get("definition"),
        "percentile": d.get("percentile"),
        "position": d.get("position"),
        "research_insight": d.get("research_insight"),
    }


def slim_dimensions(items: Any) -> List[Dict[str, Any]]:
    return [x for x in (slim_dimension(i) for i in list(items or [])) if x]


def slim_question(q: Any) -> Dict[str, Any] | None:
    if not isinstance(q, dict):
        return None
    return {
        "key": q.get("key"),
        "dimension": q.get("dimension"),
        "dimension_label": q.get("dimension_label"),
        "question_text": q.get("question_text"),
        "answer": q.get("answer"),
        "answer_display": q.get("answer_display"),
        "percentile": q.get("percentile"),
        "percentile_label": q.get("percentile_label"),
        "percentile_age_group": q.get("percentile_age_group"),
        "comparison_statement": q.get("comparison_statement"),
    }
