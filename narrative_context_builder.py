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
    from hci_signals_library import SIGNALS, RESEARCH_NUMBERS
except Exception:
    SIGNALS = {"dimensions": {}, "trends": {}, "combinations": {}, "human_reference": {}}
    RESEARCH_NUMBERS = {}

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
        PRESSURE_POINTS,
    )
except Exception:
    FREQUENCY_GRADIENTS = {}
    AGE_COHORT_PATTERNS = {}
    DISTINCTIVE_FLAGS = {}
    KEY_FINDINGS_FOR_REPORTS = {}
    COHORT_NARRATIVES = {}
    PRESSURE_POINTS = {}

try:
    from report_templates import (
        DIMENSION_LABELS,
        DIMENSION_DEFINITIONS,
        DIMENSION_ORDER,
        percentile_position,
        protect_position,
        STRENGTH_DEEPENING_COPY,
        MONITORING_COPY,
    )
except Exception:
    DIMENSION_LABELS = {}
    DIMENSION_DEFINITIONS = {}
    DIMENSION_ORDER = []
    def percentile_position(p): return "near population centre"
    def protect_position(p): return "in the middle"
    STRENGTH_DEEPENING_COPY = {}
    MONITORING_COPY = {}


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
            "note": "This is close to the population centre.",
        }

    if level == "slightly_divergent":
        return {
            "include_benchmark": True,
            "include_master_synthesis": True,
            "include_human_reference": False,
            "depth": "medium",
            "emphasis_level": "standard",
            "note": "This diverges somewhat from the population centre.",
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
    signals = SIGNALS.get("dimensions", {}) if isinstance(SIGNALS, dict) else {}
    source = signals.get(dimension) or signals.get(DIMENSION_LABELS.get(dimension, dimension)) or {}

    if not isinstance(source, dict):
        source = {"text": str(source)}

    try:
        p = int(round(float(percentile)))
    except Exception:
        p = 50

    if p >= 71:
        selected = source.get("high") or source.get("series") or source.get("definition")
    elif p <= 40:
        selected = source.get("low") or source.get("series") or source.get("definition")
    else:
        selected = source.get("typical") or source.get("series") or source.get("definition")

    return {
        "selected": selected or "",
        "high": source.get("high"),
        "low": source.get("low"),
        "typical": source.get("typical"),
        "series": source.get("series"),
        "pressure_point": source.get("pressure_point"),
        "definition": source.get("definition"),
    }


def combination_signal(d1: str, d2: str) -> Any:
    combos = SIGNALS.get("combinations", {}) if isinstance(SIGNALS, dict) else {}
    for key in [f"{d1}+{d2}", f"{d2}+{d1}", f"{d1}_{d2}", f"{d2}_{d1}"]:
        if key in combos:
            return combos[key]
    return None


def human_reference_context(dimension: str, percentile: Any) -> Dict[str, Any]:
    if HRL is None:
        return {}

    context = {}
    position = "high" if (clean_float(percentile, 50) or 50) >= 71 else "low" if (clean_float(percentile, 50) or 50) <= 40 else "typical"

    for attr in ["HBE_FRAMEWORK", "VALUES_SIGNALS", "REFRAME_LIBRARY", "RESEARCH_INSIGHTS", "HBE_COHORT_REFRAMES"]:
        source = getattr(HRL, attr, None)
        if isinstance(source, dict):
            value = source.get(dimension) or source.get(DIMENSION_LABELS.get(dimension, dimension))
            if value is not None:
                context[attr] = value

    fn = getattr(HRL, "get_values_reframe", None)
    if callable(fn):
        try:
            context["values_reframe"] = fn(dimension, position)
        except Exception:
            try:
                context["values_reframe"] = fn(dimension)
            except Exception:
                pass

    return context


def benchmark_context(dimension: str, frequency: Any, age_group: Any, percentile: Any) -> Dict[str, Any]:
    freq = str(frequency or "").strip()
    age = str(age_group or "").strip()

    return {
        "frequency_gradient": (FREQUENCY_GRADIENTS.get(dimension, {}) or {}).get(freq) or FREQUENCY_GRADIENTS.get(dimension, {}),
        "age_cohort_pattern": AGE_COHORT_PATTERNS.get(age, {}),
        "key_finding": (
            KEY_FINDINGS_FOR_REPORTS.get(f"{dimension}_high")
            if (clean_float(percentile, 50) or 50) >= 71
            else KEY_FINDINGS_FOR_REPORTS.get(f"{dimension}_low")
            if (clean_float(percentile, 50) or 50) <= 40
            else KEY_FINDINGS_FOR_REPORTS.get(f"{dimension}_typical")
        ),
        "cohort_narrative": COHORT_NARRATIVES.get(age, {}),
        "pressure_points": PRESSURE_POINTS.get(dimension, {}),
    }


def distinctive_flags_for_dimension(dimension: str, percentile: Any, frequency: Any) -> List[Dict[str, Any]]:
    p = clean_float(percentile, 50) or 50
    freq = str(frequency or "").strip().lower()
    flags = []

    checks = {
        "high_verification_high_frequency": dimension == "verification" and p >= 71 and freq in {"everyday", "daily", "every day"},
        "low_reliance_high_frequency": dimension == "reliance" and p <= 40 and freq in {"everyday", "daily", "every day"},
        "high_emotional_engagement_low_frequency": dimension == "emotional_regulation" and p >= 71 and freq in {"rarely", "sometimes"},
        "low_disclosure_high_frequency": dimension == "disclosure" and p <= 40 and freq in {"everyday", "daily", "every day"},
        "low_emotional_engagement_high_frequency": dimension == "emotional_regulation" and p <= 40 and freq in {"everyday", "daily", "every day"},
    }

    for key, condition in checks.items():
        if condition:
            data = DISTINCTIVE_FLAGS.get(key, {})
            flags.append({
                "flag": key,
                "rarity": data.get("rarity"),
                "meaning": data.get("meaning"),
                "research_insight": data.get("research_insight"),
            })

    return flags


# ---------------------------------------------------------------------
# Public context builders
# ---------------------------------------------------------------------

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
        "percentile": percentile,
        "raw_score": d.get("raw_score"),
        "position": d.get("position") or percentile_position(percentile),
        "protect_position": d.get("protect_position") or protect_position(percentile),
        "distinctiveness": distinctiveness,
        "signal_layers": signal_layers,
        "dimension_signal": dimension_signal(dimension, percentile),
        "benchmark_context": benchmark_context(dimension, frequency, age_group, percentile),
        "human_reference": human_reference_context(dimension, percentile) if signal_layers.get("include_human_reference") else {},
        "distinctive_flags": distinctive_flags_for_dimension(dimension, percentile, frequency),
        "strength_deepening": STRENGTH_DEEPENING_COPY.get(dimension, {}),
        "monitoring": MONITORING_COPY.get(dimension, {}),
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
            "signals_trends": SIGNALS.get("trends", {}) if isinstance(SIGNALS, dict) else {},
            "signals_combinations": SIGNALS.get("combinations", {}) if isinstance(SIGNALS, dict) else {},
            "signals_human_reference": SIGNALS.get("human_reference", {}) if isinstance(SIGNALS, dict) else {},
            "research_numbers": RESEARCH_NUMBERS,
            "hci_principles": [
                "Describe patterns, not personality types.",
                "Frame scores as awareness and choice, not diagnosis.",
                "Ground claims in HCI data, signals, or report_data.",
                "Do not prescribe behaviour.",
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
    human_capital_inputs = report_data.get("human_capital") or {}

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
            "Translate behavioural benchmark evidence into human capabilities "
            "that appear to be developing, worth protecting, or worth watching."
        ),
        "profile": full.get("profile", {}),
        "human_capital_inputs": human_capital_inputs,
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
            "Translate behaviour into capability.",
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
            "trajectory": {
                "common_patterns": narrative_blocks.get("likely_to_continue"),
                "overall_outlook": narrative_blocks.get("overall_outlook"),
                "at_a_glance": {
                    "highest_dimension": trajectory.get("highest_dimension"),
                    "monitoring_anchor": trajectory.get("monitoring_anchor"),
                    "strengths_that_may_continue_developing": trajectory.get("strengths_likely_to_deepen", []),
                    "areas_worth_monitoring": trajectory.get("areas_worth_monitoring", []),
                },
            },
            "looking_forward": {
                "purpose": "What people with similar profiles often notice first over time.",
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
            "If the profile shows strong retained agency or identity stability, that may be acknowledged as reassuring; otherwise do not make identity-stability claims.",
            "End with the participant's continuing measurement journey, not with organisational promotion.",
        ],
        "global_hci_assets": {
            "hci_principles": (full.get("global_hci_assets", {}) or {}).get("hci_principles", []),
        },
    }



def build_context_for_claude_section(report_data: Dict[str, Any], section: str) -> Dict[str, Any]:
    full = build_full_narrative_context(report_data)

    if section == "opening":
        return {
            "profile": full["profile"],
            "most_distinctive_variable": full["profile"]["most_distinctive_variable"],
            "largest_perception_gap": full["profile"]["largest_perception_gap"],
            "top_rare_combination": full["profile"]["top_rare_combination"],
            "global_hci_assets": full["global_hci_assets"],
        }

    if section == "rare_combinations":
        return {
            "rare_combinations": full["rare_combinations"],
            "dimension_contexts": full["dimension_contexts"],
            "global_hci_assets": full["global_hci_assets"],
        }

    if section == "behaviour_story":
        return {
            "profile": full["profile"],
            "dimension_contexts": full["dimension_contexts"],
            "rare_combinations": full["rare_combinations"],
            "perception_gap": full["perception_gap"],
            "global_hci_assets": full["global_hci_assets"],
        }

    if section == "deep_dive":
        return {
            "profile": full["profile"],
            "deep_dive_candidate": select_deep_dive_candidate(full),
            "dimension_contexts": full["dimension_contexts"],
            "rare_combinations": full["rare_combinations"],
            "distinctive_responses": full["distinctive_responses"][:3],
            "perception_gap": full["perception_gap"],
            "trajectory": full["trajectory"],
            "previous_narrative_blocks": report_data.get("narrative_blocks", {}),
            "global_hci_assets": full["global_hci_assets"],
        }

    if section == "distinctive_responses":
        return {
            "distinctive_responses": full["distinctive_responses"],
            "dimension_contexts": full["dimension_contexts"],
            "global_hci_assets": full["global_hci_assets"],
        }

    if section == "perception_gap":
        return {
            "perception_gap": full["perception_gap"],
            "profile": full["profile"],
            "dimension_contexts": {
                k: v for k, v in full["dimension_contexts"].items()
                if k in {"reliance", "decision_delegation", "thought_partnership"}
            },
            "global_hci_assets": full["global_hci_assets"],
        }

    if section == "human_capital":
        return build_human_capital_context(report_data, full)

    if section == "closing_reflection":
        return build_closing_reflection_context(report_data, full)

    if section == "trajectory":
        return {
            "trajectory": full["trajectory"],
            "dimension_contexts": full["dimension_contexts"],
            "global_hci_assets": full["global_hci_assets"],
        }

    return full



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
                "reason": "The strongest individual response is unusually far from the benchmark centre.",
                "data": most,
            }

    gap = (full_context.get("profile") or {}).get("largest_perception_gap")
    if gap:
        return {
            "type": "perception_gap",
            "reason": "The largest gap between self-perception and benchmark position may reveal a meaningful blind spot or alignment point.",
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
        item["signal"] = combination_signal(d1, d2)
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
    data = report_data.get("if_nothing_changes") or {}

    strengths = []
    for d in data.get("strengths_likely_to_deepen", []):
        dim = d.get("key")
        ctx = dimension_contexts.get(dim, {})
        strengths.append({
            "dimension": dim,
            "label": d.get("label"),
            "percentile": d.get("percentile"),
            "position": d.get("position"),
            "research_signal": d.get("research_insight"),
            "strength_deepening": ctx.get("strength_deepening", {}),
        })

    monitor = []
    for d in data.get("areas_worth_monitoring", []):
        dim = d.get("key")
        ctx = dimension_contexts.get(dim, {})
        monitor.append({
            "dimension": dim,
            "label": d.get("label"),
            "percentile": d.get("percentile"),
            "position": d.get("position"),
            "research_signal": d.get("research_insight"),
            "monitoring": ctx.get("monitoring", {}),
        })

    return {
        "usage_frequency": data.get("usage_frequency"),
        "highest_dimension": slim_dimension(data.get("highest_dimension")),
        "monitoring_anchor": slim_dimension(data.get("monitoring_anchor")),
        "strengths_likely_to_deepen": strengths,
        "areas_worth_monitoring": monitor,
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
