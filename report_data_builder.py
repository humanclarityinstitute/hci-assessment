"""
report_data_builder.py

Canonical data builder for the HCI AI Identity & Behaviour Report V2.

This file owns report measurement and deterministic selection. It does not
write premium narrative prose and it does not render HTML.

V2 guarantees:
- Preserves the existing scoring and benchmark plumbing.
- Builds all 9 dimension positions and all 39 question-level results.
- Separates main-report evidence from the complete appendix.
- Selects defining signals, comparable-user shifts and baseline priorities
  deterministically.
- Never invents missing cohort percentiles or public rarity claims.
- Stores benchmark and data-quality metadata for longitudinal comparison.
- Retains a small set of legacy aliases while downstream V2 files are rebuilt.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid


# ---------------------------------------------------------------------
# Imports from existing HCI assets
# ---------------------------------------------------------------------

try:
    from scoring_engine import DIMENSION_VARIABLES
except Exception:
    DIMENSION_VARIABLES = {
        "reliance": ["rel_q1", "rel_q2", "rel_q3", "rel_q4", "rel_q5"],
        "trust": ["trust_q1", "trust_q2", "trust_q3", "trust_q4"],
        "verification": ["ver_q1", "ver_q2", "ver_q3", "ver_q4"],
        "decision_delegation": ["del_q1", "del_q2", "del_q3", "del_q4", "del_q5"],
        "human_agency": ["agency_q1", "agency_q2", "agency_q3", "agency_q4", "agency_q5"],
        "emotional_regulation": ["emot_q1", "emot_q2", "emot_q3", "emot_q4"],
        "disclosure": ["disc_q1", "disc_q2", "disc_q3", "disc_q4"],
        "thought_partnership": ["thought_q1", "thought_q2", "thought_q3", "thought_q4"],
        "social_transparency": ["soc_q1", "soc_q2", "soc_q3", "soc_q4"],
    }

try:
    from question_metadata import (
        QUESTION_MAP,
        REVERSE_SCORED_KEYS,
        get_question_text,
        PERCEPTION_QUESTIONS,
    )
except Exception:
    QUESTION_MAP = {}
    REVERSE_SCORED_KEYS = set()
    PERCEPTION_QUESTIONS = {}
    def get_question_text(key):
        return key

try:
    from benchmark_builder import get_benchmark
except Exception:
    get_benchmark = None

try:
    from hci_signals_library import SIGNALS
except Exception:
    SIGNALS = {"dimensions": {}, "trends": {}, "combinations": {}, "human_reference": {}}



# ---------------------------------------------------------------------
# Locked constants
# ---------------------------------------------------------------------

DIMENSION_ORDER = [
    "reliance",
    "trust",
    "verification",
    "decision_delegation",
    "human_agency",
    "disclosure",
    "emotional_regulation",
    "thought_partnership",
    "social_transparency",
]

DIMENSION_LABELS = {
    "reliance": "Reliance",
    "trust": "Trust",
    "verification": "Verification",
    "decision_delegation": "Decision Delegation",
    "human_agency": "Human Agency",
    "emotional_regulation": "Emotional Regulation",
    "disclosure": "Disclosure",
    "thought_partnership": "Thought Partnership",
    "social_transparency": "Social Transparency",
}

DIMENSION_DEFINITIONS = {
    "reliance": "How central AI is in your reported thinking and task completion",
    "trust": "How much confidence you report in AI outputs",
    "verification": "How often you report checking AI outputs before using them",
    "decision_delegation": "How much involvement you report giving AI in decisions",
    "human_agency": "How much control and authorship you report retaining in decisions",
    "emotional_regulation": "How often you report turning to AI for emotional support",
    "disclosure": "How much personal information you report sharing with AI",
    "thought_partnership": "How much you report using AI to develop or test ideas",
    "social_transparency": "How openly you report discussing your AI use with others",
}

SELF_PERCEPTION_MAP = {
    "perceived_usage": {
        "question": "Compared to most people, how much do you use AI?",
        "comparison_area": "AI Use",
        "comparison_source": "usage_frequency",
        "primary_dimension": None,
        "secondary_dimension": None,
    },
    "perceived_reliance": {
        "question": "Compared to most people, how much do you rely on AI?",
        "comparison_area": "AI Reliance",
        "comparison_source": "reliance_dimension",
        "primary_dimension": "reliance",
        "secondary_dimension": None,
    },
    "perceived_dependence": {
        "question": "Compared to most people, how dependent on AI are you?",
        "comparison_area": "Dependence-related responses",
        "comparison_source": "dependence_derived",
        "primary_dimension": None,
        "secondary_dimension": None,
    },
}

DEPENDENCE_VARIABLES = ["rel_q1", "rel_q2", "rel_q5"]

FREQUENCY_ORDER = [
    "Never",
    "Rarely",
    "Sometimes",
    "Often",
    "Very often",
    "Everyday",
]

PROTECT_DIMENSIONS = [
    "verification",
    "human_agency",
    "emotional_regulation",
    "thought_partnership",
]

COUNTRY_DISPLAY_NAMES = {
    "NZ": "New Zealand",
    "AU": "Australia",
    "US": "United States",
    "USA": "United States",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "IE": "Ireland",
    "CA": "Canada",
}


# ---------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str) and value.strip().lower() in {"none", "null", "nan", "n/a"}:
            return default
        return int(round(float(value)))
    except Exception:
        return default


def clean_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def ordinal(n: Any) -> str:
    n = clean_int(n, 0) or 0
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"



def position_phrase(percentile: Any) -> str:
    p = clean_int(percentile, 50) or 50
    if p >= 96:
        return "exceptionally high"
    if p >= 86:
        return "notably high"
    if p >= 71:
        return "above the HCI benchmark centre"
    if p >= 41:
        return "near the HCI benchmark centre"
    if p >= 26:
        return "below the HCI benchmark centre"
    if p >= 11:
        return "notably low"
    return "exceptionally low"


def protect_position_phrase(percentile: Any) -> str:
    p = clean_int(percentile, 50) or 50
    if p >= 71:
        return "at the high end"
    if p >= 41:
        return "in the middle"
    return "at the low end"


def get_benchmark_instance():
    try:
        return get_benchmark() if callable(get_benchmark) else None
    except Exception:
        return None


def get_benchmark_data(benchmark: Any) -> Dict[str, Any]:
    data = getattr(benchmark, "data", None)
    return data if isinstance(data, dict) else {}


def get_min_sample_size(benchmark: Any) -> int:
    return clean_int(getattr(benchmark, "min_sample_size", None), 30) or 30


# ---------------------------------------------------------------------
# Demographic normalisation
# ---------------------------------------------------------------------

def canonical_lookup(value: Any, available_keys: List[str]) -> Optional[str]:
    """
    Robust lookup into benchmark cohort keys.

    Handles:
    - 18-24 / 18 - 24 / 18 – 24 / 18 to 24
    - 65+ / Over 65 / 65 plus
    - everyday / every day / daily
    """
    if value is None:
        return None

    def norm(v: Any) -> str:
        text = str(v).strip().lower()
        text = text.replace("–", "-").replace("—", "-").replace("−", "-")
        text = " ".join(text.split())
        compact = text.replace(" ", "")
        aliases = {
            "18-24": "18-24", "18to24": "18-24", "18_24": "18-24",
            "25-34": "25-34", "25to34": "25-34", "25_34": "25-34",
            "35-44": "35-44", "35to44": "35-44", "35_44": "35-44",
            "45-54": "45-54", "45to54": "45-54", "45_54": "45-54",
            "55-64": "55-64", "55to64": "55-64", "55_64": "55-64",
            "55-65": "55-64", "55to65": "55-64",
            "65+": "65+", "over65": "65+", "65andover": "65+", "65plus": "65+",

            "everyday": "everyday",
            "every day": "everyday",
            "every_day": "everyday",
            "daily": "everyday",

            "veryoften": "very often",
            "very often": "very often",
            "very_often": "very often",
            "very-often": "very often",

            "often": "often",

            "sometimes": "sometimes",
            "occasionally": "sometimes",
            "occasional": "sometimes",

            "rarely": "rarely",
            "rare": "rarely",

            "never": "never",
        }
        return aliases.get(compact, aliases.get(text, compact))

    requested = norm(value)
    for key in list(available_keys or []):
        if norm(key) == requested:
            return key
    return None


def country_display_name(value: Any) -> str:
    if value is None or value == "":
        return ""
    text = str(value).strip()
    return COUNTRY_DISPLAY_NAMES.get(text.upper(), text)


def infer_available_segment_keys(benchmark: Any, segment_key: str) -> List[str]:
    """
    Collect available segment keys across dimensions and variables.
    segment_key examples:
    - "by_age_group"
    - "by_frequency"
    """
    data = get_benchmark_data(benchmark)
    keys = set()

    for collection_name in ["dimensions", "variables"]:
        collection = data.get(collection_name) or {}
        if isinstance(collection, dict):
            for item in collection.values():
                if isinstance(item, dict):
                    seg = item.get(segment_key) or {}
                    if isinstance(seg, dict):
                        keys.update(seg.keys())

    return sorted(keys)


def normalise_demographics_for_benchmark(demographics: Dict[str, Any], benchmark: Any) -> Dict[str, Any]:
    """
    Preserve original values, but add benchmark-normalised cohort values.
    """
    demographics = dict(demographics or {})

    # Age keys can exist under by_age_group for dimensions and by_age for variables.
    age_keys = sorted(set(
        infer_available_segment_keys(benchmark, "by_age_group")
        + infer_available_segment_keys(benchmark, "by_age")
    ))
    freq_keys = sorted(set(
        infer_available_segment_keys(benchmark, "by_frequency")
        + infer_available_segment_keys(benchmark, "by_ai_tool_use_frequency")
    ))

    age_original = demographics.get("age_group")
    freq_original = demographics.get("ai_tool_use_frequency") or demographics.get("frequency")
    country_original = demographics.get("country")

    demographics["_age_group_original"] = age_original
    demographics["_country_original"] = country_original
    demographics["country_display"] = country_display_name(country_original)
    demographics["_frequency_original"] = freq_original
    demographics["_age_group_benchmark"] = canonical_lookup(age_original, age_keys) or age_original
    demographics["_frequency_benchmark"] = canonical_lookup(freq_original, freq_keys) or freq_original

    # These are what BenchmarkBuilder.calculate_percentile expects.
    # Do this only inside report_data_builder; we do not mutate upstream app state.
    demographics["_benchmark_demographics"] = {
        "age_group": demographics["_age_group_benchmark"],
        "gender": demographics.get("gender"),
        "country": demographics.get("country"),
        "ai_tool_use_frequency": demographics["_frequency_benchmark"],
    }

    demographics["_available_age_groups"] = age_keys
    demographics["_available_frequencies"] = freq_keys

    return demographics


# ---------------------------------------------------------------------
# Signal / HRL helpers
# ---------------------------------------------------------------------

def definition_for_dimension(dim: str) -> str:
    """Return the locked participant-facing definition for one dimension."""
    return str(DIMENSION_DEFINITIONS.get(dim, ""))


# ---------------------------------------------------------------------
# Percentile / distribution helpers
# ---------------------------------------------------------------------

def calculate_percentile_from_values(score: Any, values: List[Any]) -> Optional[int]:
    score_f = clean_float(score)
    if score_f is None or not values:
        return None

    nums = [clean_float(v) for v in values]
    nums = [v for v in nums if v is not None]
    if not nums:
        return None

    below = sum(1 for v in nums if v < score_f)
    pct = int((below / len(nums)) * 100)
    if pct <= 0:
        return 1
    return min(pct, 99)


def calculate_question_percentile_from_values(score: Any, values: List[Any]) -> Optional[int]:
    """
    Calculate question-level standing for discrete 1-7 responses.

    For individual question cards, include participants who gave the same
    response as the user. This keeps the displayed standing aligned with the
    histogram: if 18% of respondents selected 1, an answer of 1 should display
    around 18/100 rather than 1/100.
    """
    score_f = clean_float(score)
    if score_f is None or not values:
        return None

    nums = [clean_float(v) for v in values]
    nums = [v for v in nums if v is not None]
    if not nums:
        return None

    at_or_below = sum(1 for v in nums if v <= score_f)
    pct = int(round((at_or_below / len(nums)) * 100))
    return max(1, min(pct, 99))


def safe_dimension_percentiles(benchmark: Any, dim: str, raw_score: Any, demographics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate overall/age/frequency dimension percentiles directly from benchmark.
    """
    out = {
        "overall": None,
        "age_group": None,
        "frequency": None,
        "n_overall": None,
        "n_age_group": None,
        "n_frequency": None,
    }

    bench_demo = demographics.get("_benchmark_demographics") or demographics

    # Preferred: existing BenchmarkBuilder method.
    if benchmark is not None and hasattr(benchmark, "calculate_percentile"):
        try:
            result = benchmark.calculate_percentile(dim, raw_score, bench_demo) or {}
            out["overall"] = clean_int(result.get("overall_percentile"))
            out["age_group"] = clean_int(result.get("age_group_percentile"))
            out["frequency"] = clean_int(result.get("frequency_percentile"))
            out["n_overall"] = clean_int(result.get("n_overall"))
            out["n_age_group"] = clean_int(result.get("n_age_group"))
            out["n_frequency"] = clean_int(result.get("n_frequency"))
        except Exception:
            pass

    # Direct fallback from benchmark.data.
    data = get_benchmark_data(benchmark)
    dim_data = (data.get("dimensions") or {}).get(dim) or {}
    min_n = get_min_sample_size(benchmark)

    if isinstance(dim_data, dict):
        overall = dim_data.get("overall") or {}
        if out["overall"] is None:
            out["overall"] = calculate_percentile_from_values(raw_score, overall.get("values") or [])
        out["n_overall"] = out["n_overall"] if out["n_overall"] is not None else clean_int(overall.get("n"))

        age_key = bench_demo.get("age_group")
        age_segments = dim_data.get("by_age_group") or {}
        age_actual_key = canonical_lookup(age_key, list(age_segments.keys())) if age_key else None
        age_data = age_segments.get(age_actual_key) if age_actual_key else None
        if isinstance(age_data, dict) and clean_int(age_data.get("n"), 0) >= min_n:
            if out["age_group"] is None:
                out["age_group"] = calculate_percentile_from_values(raw_score, age_data.get("values") or [])
            out["n_age_group"] = out["n_age_group"] if out["n_age_group"] is not None else clean_int(age_data.get("n"))

        freq_key = bench_demo.get("ai_tool_use_frequency")
        freq_segments = dim_data.get("by_frequency") or {}
        freq_actual_key = canonical_lookup(freq_key, list(freq_segments.keys())) if freq_key else None
        freq_data = freq_segments.get(freq_actual_key) if freq_actual_key else None
        if isinstance(freq_data, dict) and clean_int(freq_data.get("n"), 0) >= min_n:
            if out["frequency"] is None:
                out["frequency"] = calculate_percentile_from_values(raw_score, freq_data.get("values") or [])
            out["n_frequency"] = out["n_frequency"] if out["n_frequency"] is not None else clean_int(freq_data.get("n"))

    return out



def get_variable_source(benchmark: Any, key: str, segment: Optional[Tuple[str, str]] = None) -> Optional[Dict[str, Any]]:
    """
    Get variable source data from benchmark.data.

    Important:
    - Segment requests never fall back to overall.
    - benchmark_tables.json currently stores variable age cohorts under by_age.
    - Dimension age cohorts use by_age_group.
    - This function supports both so question-level age histograms can populate.
    """
    data = get_benchmark_data(benchmark)
    var_data = (data.get("variables") or {}).get(key)
    if not isinstance(var_data, dict):
        return None

    if segment and isinstance(segment, tuple) and len(segment) == 2:
        seg_type, seg_value = segment

        possible_keys = [f"by_{seg_type}"]

        if seg_type == "age_group":
            possible_keys.extend(["by_age", "by_age_group"])
        elif seg_type == "age":
            possible_keys.extend(["by_age_group", "by_age"])
        elif seg_type == "frequency":
            possible_keys.extend(["by_frequency", "by_ai_tool_use_frequency"])
        elif seg_type == "ai_tool_use_frequency":
            possible_keys.extend(["by_frequency", "by_ai_tool_use_frequency"])

        # De-duplicate while preserving order.
        seen = set()
        possible_keys = [k for k in possible_keys if not (k in seen or seen.add(k))]

        for seg_key in possible_keys:
            segments = var_data.get(seg_key) or {}
            if not isinstance(segments, dict) or not segments:
                continue

            actual_key = canonical_lookup(seg_value, list(segments.keys()))
            if actual_key is not None:
                return segments.get(actual_key)

        return None

    return var_data.get("overall")

def safe_question_percentile(benchmark: Any, key: str, answer: Any, segment: Optional[Tuple[str, str]] = None) -> Optional[int]:
    if answer is None:
        return None

    min_n = get_min_sample_size(benchmark)
    source = get_variable_source(benchmark, key, segment)

    # For cohort percentiles, require an actual cohort and enough sample.
    if segment:
        if not isinstance(source, dict):
            return None
        if clean_int(source.get("n"), 0) < min_n:
            return None
        return calculate_question_percentile_from_values(answer, source.get("values") or [])

    # Overall percentile.
    if isinstance(source, dict):
        pct = calculate_question_percentile_from_values(answer, source.get("values") or [])
        if pct is not None:
            return pct

    # Last fallback only for overall, never for cohorts.
    if benchmark is not None and hasattr(benchmark, "get_percentile"):
        try:
            return clean_int(benchmark.get_percentile(key, answer, segment=None))
        except Exception:
            pass

    return None


def normalize_distribution(raw: Any) -> Optional[List[int]]:
    """
    Convert raw values/counts/percentages into 7 percentage values for response options 1..7.
    """
    if raw is None:
        return None

    if isinstance(raw, dict):
        for key in ["percentages", "distribution", "counts", "values"]:
            if key in raw:
                return normalize_distribution(raw.get(key))
        raw = [raw.get(str(i), raw.get(i, 0)) for i in range(1, 8)]

    if not isinstance(raw, list) or not raw:
        return None

    nums = [clean_float(v, 0) or 0 for v in raw]

    # Long array = raw response values.
    if len(nums) > 7:
        counts = [0] * 7
        for v in nums:
            iv = clean_int(v)
            if iv is not None and 1 <= iv <= 7:
                counts[iv - 1] += 1
        total = sum(counts)
        if total <= 0:
            return None
        return [int(round((c / total) * 100)) for c in counts]

    if len(nums) < 7:
        return None

    nums = nums[:7]
    total = sum(nums)
    if total <= 0:
        return None

    if not (95 <= total <= 105):
        nums = [(x / total) * 100 for x in nums]

    return [int(round(x)) for x in nums]


def safe_question_distribution(benchmark: Any, key: str, segment: Optional[Tuple[str, str]] = None) -> Optional[List[int]]:
    """
    Read distribution from benchmark.data["variables"].
    If a cohort segment is missing or below MIN_SAMPLE, return None.
    Do NOT silently fallback to overall for age/frequency rows.
    """
    source = get_variable_source(benchmark, key, segment)
    if not isinstance(source, dict):
        return None

    if segment and clean_int(source.get("n"), 0) < get_min_sample_size(benchmark):
        return None

    return normalize_distribution(source)


def safe_question_sample_size(benchmark: Any, key: str, segment: Optional[Tuple[str, str]] = None) -> Optional[int]:
    source = get_variable_source(benchmark, key, segment)
    if isinstance(source, dict):
        return clean_int(source.get("n"), 0)
    return 0 if segment else None


# ---------------------------------------------------------------------
# Main builders
# ---------------------------------------------------------------------

def normalize_dimensions(scoring_results: Dict[str, Any], demographics: Dict[str, Any], benchmark: Any) -> Dict[str, Dict[str, Any]]:
    src = scoring_results.get("dimension_scores") or scoring_results.get("dimensions") or {}
    dimensions: Dict[str, Dict[str, Any]] = {}

    for dim in DIMENSION_ORDER:
        raw = src.get(dim, {}) if isinstance(src, dict) else {}
        raw_score = raw.get("raw_score") if isinstance(raw, dict) else None

        # Start with scoring_engine values.
        overall = clean_int(raw.get("percentile_overall"), None) if isinstance(raw, dict) else None
        age = clean_int(raw.get("percentile_age_group"), None) if isinstance(raw, dict) else None
        freq = clean_int(raw.get("percentile_frequency"), None) if isinstance(raw, dict) else None
        n_overall = clean_int(raw.get("n_overall"), None) if isinstance(raw, dict) else None
        n_age = clean_int(raw.get("n_age_group"), None) if isinstance(raw, dict) else None
        n_freq = clean_int(raw.get("n_frequency"), None) if isinstance(raw, dict) else None

        # Recalculate missing values from benchmark.
        recalculated = safe_dimension_percentiles(benchmark, dim, raw_score, demographics) if raw_score is not None else {}

        if overall is None:
            overall = clean_int(recalculated.get("overall"), 50)
        if age is None:
            age = clean_int(recalculated.get("age_group"))
        if freq is None:
            freq = clean_int(recalculated.get("frequency"))

        n_overall = n_overall if n_overall is not None else clean_int(recalculated.get("n_overall"))
        n_age = n_age if n_age is not None else clean_int(recalculated.get("n_age_group"))
        n_freq = n_freq if n_freq is not None else clean_int(recalculated.get("n_frequency"))

        p = clean_int(overall, 50)

        dimensions[dim] = {
            "key": dim,
            "label": DIMENSION_LABELS[dim],
            "definition": definition_for_dimension(dim),
            "raw_score": clean_float(raw_score),
            "percentile": p,
            "percentile_overall": p,
            "percentile_age_group": age,
            "percentile_frequency": freq,
            "n_overall": n_overall,
            "n_age_group": n_age,
            "n_frequency": n_freq,
            "position": position_phrase(p),
            "protect_position": protect_position_phrase(p),
        }

    return dimensions



def build_dashboard(dimensions: Dict[str, Dict[str, Any]], demographics: Dict[str, Any]) -> List[Dict[str, Any]]:
    freq_label = demographics.get("_frequency_benchmark") or demographics.get("ai_tool_use_frequency") or "AI users"
    age_label = demographics.get("_age_group_benchmark") or demographics.get("age_group") or "your age group"

    cards = []
    for dim in DIMENSION_ORDER:
        d = dimensions[dim]
        cards.append({
            "key": dim,
            "label": d["label"],
            "definition": d["definition"],
            "percentile": d["percentile"],
            "percentile_label": ordinal(d["percentile"]),
            "plain_score": (
                f"{ordinal(d['percentile'])} percentile within the "
                "HCI participant benchmark"
            ),
            "comparisons": [
                {
                    "type": "frequency",
                    "label": f"{freq_label} users",
                    "percentile": d.get("percentile_frequency"),
                    "percentile_label": ordinal(d.get("percentile_frequency")) if d.get("percentile_frequency") is not None else "N/A — limited data",
                    "n": d.get("n_frequency"),
                },
                {
                    "type": "age_group",
                    "label": f"Your age group ({age_label})",
                    "percentile": d.get("percentile_age_group"),
                    "percentile_label": ordinal(d.get("percentile_age_group")) if d.get("percentile_age_group") is not None else "N/A — limited data",
                    "n": d.get("n_age_group"),
                },
            ],
            "research_insight": "",
        })

    return cards


def build_typicality(dimensions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    items = []
    for dim in DIMENSION_ORDER:
        d = dimensions[dim]
        p = d["percentile"]
        bucket = "distinctive" if p > 75 or p < 25 else "typical" if 35 <= p <= 65 else "moderate"
        items.append({
            "dimension": dim,
            "label": d["label"],
            "percentile": p,
            "position": position_phrase(p),
            "bucket": bucket,
            "distance_from_centre": abs(p - 50),
            "interpretation": "",
        })

    return {
        "distinctive": sorted([x for x in items if x["bucket"] == "distinctive"], key=lambda x: x["distance_from_centre"], reverse=True),
        "typical": [x for x in items if x["bucket"] == "typical"],
        "moderate": [x for x in items if x["bucket"] == "moderate"],
        "all": items,
    }


def build_questions(responses: Dict[str, Any], demographics: Dict[str, Any], benchmark: Any) -> List[Dict[str, Any]]:
    age = demographics.get("_age_group_benchmark") or demographics.get("age_group")
    freq = demographics.get("_frequency_benchmark") or demographics.get("ai_tool_use_frequency") or demographics.get("frequency")
    age_segment = ("age_group", age) if age else None
    freq_segment = ("frequency", freq) if freq else None

    questions = []
    reverse_set = set(REVERSE_SCORED_KEYS or [])

    for dim in DIMENSION_ORDER:
        for key in DIMENSION_VARIABLES.get(dim, []):
            answer = responses.get(key)
            pct = safe_question_percentile(benchmark, key, answer)
            pct_age = safe_question_percentile(benchmark, key, answer, segment=age_segment) if age_segment else None
            pct_freq = safe_question_percentile(benchmark, key, answer, segment=freq_segment) if freq_segment else None

            n_overall = safe_question_sample_size(benchmark, key)
            n_age = safe_question_sample_size(benchmark, key, segment=age_segment) if age_segment else None
            n_freq = safe_question_sample_size(benchmark, key, segment=freq_segment) if freq_segment else None

            try:
                q_text = get_question_text(key)
            except Exception:
                q_text = (QUESTION_MAP.get(key, {}) or {}).get("text", key) if isinstance(QUESTION_MAP, dict) else key

            questions.append({
                "key": key,
                "dimension": dim,
                "dimension_label": DIMENSION_LABELS[dim],
                "question_text": q_text,
                "answer": clean_int(answer),
                "answer_display": f"{answer}/7" if answer is not None else "N/A",
                "percentile": pct,
                "percentile_label": ordinal(pct) if pct is not None else "N/A",
                "percentile_age_group": pct_age,
                "percentile_frequency": pct_freq,
                "n_overall": n_overall,
                "n_age_group": n_age,
                "n_frequency": n_freq,
                "distribution_everyone": safe_question_distribution(benchmark, key),
                "distribution_age_group": safe_question_distribution(benchmark, key, segment=age_segment) if age_segment else None,
                "distribution_frequency": safe_question_distribution(benchmark, key, segment=freq_segment) if freq_segment else None,
                "comparison_statement": build_question_comparison_statement(answer, pct, pct_freq),
                "is_reverse_scored": key in reverse_set,
            })

    return questions



def build_question_comparison_statement(
    answer: Any,
    pct: Optional[int],
    pct_frequency: Optional[int],
) -> str:
    if answer is None:
        return "No answer was recorded for this item."

    if pct is None and pct_frequency is None:
        return (
            f"You answered {answer}/7. A benchmark comparison is unavailable "
            "for this item."
        )

    if pct is not None and pct_frequency is not None:
        return (
            f"You answered {answer}/7. Within the HCI participant benchmark, "
            f"this response was at the {ordinal(pct)} percentile overall and "
            f"the {ordinal(pct_frequency)} percentile among participants who "
            "use AI about as frequently as you."
        )

    if pct is not None:
        return (
            f"You answered {answer}/7. Within the HCI participant benchmark, "
            f"this response was at the {ordinal(pct)} percentile overall. "
            "A comparable AI-use-frequency result was unavailable."
        )

    return (
        f"You answered {answer}/7. An overall comparison was unavailable, but "
        f"this response was at the {ordinal(pct_frequency)} percentile among "
        "participants who use AI about as frequently as you."
    )


def build_distinctive_responses(questions: List[Dict[str, Any]], limit: int = 7, max_per_dimension: int = 2) -> List[Dict[str, Any]]:
    """Select the most distinctive question-level responses.

    We cap each dimension so this section does not get dominated by one
    construct. The user has already seen the full 39-question profile in
    Section 6; Section 7 should provide a spread of the strongest evidence
    across the profile.
    """
    candidates = []
    for q in questions:
        pct = q.get("percentile")
        if pct is not None:
            item = deepcopy(q)
            item["distance_from_centre"] = abs((clean_int(pct, 50) or 50) - 50)
            candidates.append(item)

    sorted_candidates = sorted(
        candidates,
        key=lambda x: (x["distance_from_centre"], x.get("percentile") or 0),
        reverse=True,
    )

    selected = []
    counts: Dict[str, int] = {}
    for item in sorted_candidates:
        dim = item.get("dimension") or "unknown"
        if counts.get(dim, 0) >= max_per_dimension:
            continue
        selected.append(item)
        counts[dim] = counts.get(dim, 0) + 1
        if len(selected) >= limit:
            break

    # Safety fallback: if the cap leaves fewer than limit because of missing
    # dimension metadata, fill remaining slots from the original ranking.
    if len(selected) < limit:
        seen = {q.get("key") for q in selected}
        for item in sorted_candidates:
            if item.get("key") in seen:
                continue
            selected.append(item)
            if len(selected) >= limit:
                break

    return selected[:limit]




def usage_frequency_percentile(
    demographics: Dict[str, Any],
    benchmark: Any,
) -> Optional[int]:
    """
    Estimate where the participant's reported AI-use frequency sits within the
    HCI participant benchmark.

    This uses benchmark frequency-cohort sample sizes rather than any single
    assessment dimension. If those benchmark counts are unavailable, the
    comparison is left unavailable rather than replaced with an invented
    percentile.
    """
    bench_demo = demographics.get("_benchmark_demographics") or demographics
    frequency = (
        bench_demo.get("ai_tool_use_frequency")
        or demographics.get("ai_tool_use_frequency")
    )
    if not frequency:
        return None

    data = get_benchmark_data(benchmark)
    dimensions = data.get("dimensions") or {}

    frequency_counts: Dict[str, int] = {}
    for dim_data in dimensions.values():
        if not isinstance(dim_data, dict):
            continue
        by_frequency = dim_data.get("by_frequency") or {}
        if not isinstance(by_frequency, dict) or not by_frequency:
            continue
        frequency_counts = {
            str(k): clean_int(v.get("n"), 0) or 0
            for k, v in by_frequency.items()
            if isinstance(v, dict)
        }
        if frequency_counts:
            break

    if not frequency_counts:
        return None

    actual_key = canonical_lookup(frequency, list(frequency_counts.keys()))
    if actual_key is None:
        return None

    order = [key for key in FREQUENCY_ORDER if key in frequency_counts]
    for key in frequency_counts:
        if key not in order:
            order.append(key)

    total = sum(frequency_counts.values())
    current_n = frequency_counts.get(actual_key, 0)
    if total <= 0 or current_n <= 0:
        return None

    below = 0
    for key in order:
        if key == actual_key:
            break
        below += frequency_counts.get(key, 0)

    # Place the participant at the midpoint of the reported frequency cohort.
    pct_value = ((below + (current_n / 2)) / total) * 100
    return max(1, min(99, int(round(pct_value))))



def derived_dependence_percentile(
    responses: Dict[str, Any],
    benchmark: Any,
) -> Optional[int]:
    """
    Derive a dependence-related response percentile from three Reliance items
    that most directly ask about difficulty, unease or perceived weakening
    when AI is unavailable or performs the task.

    This is an assessment-derived comparison, not a clinical or diagnostic
    measure of dependence.
    """
    percentiles = []
    for key in DEPENDENCE_VARIABLES:
        answer = responses.get(key)
        if answer is None:
            continue
        pct_value = safe_question_percentile(benchmark, key, answer)
        if pct_value is not None:
            percentiles.append(pct_value)

    if not percentiles:
        return None

    return max(1, min(99, int(round(sum(percentiles) / len(percentiles)))))



def perception_comparison_value(
    key: str,
    meta: Dict[str, Any],
    responses: Dict[str, Any],
    dimensions: Dict[str, Dict[str, Any]],
    demographics: Dict[str, Any],
    benchmark: Any,
) -> Dict[str, Any]:
    """
    Resolve the assessment-based comparison value for each self-perception item.

    The returned ``measured_basis`` key is retained for compatibility, but its
    content describes the self-reported assessment basis rather than an
    independent or objective measurement.
    """
    source = meta.get("comparison_source")

    if source == "usage_frequency":
        percentile = usage_frequency_percentile(demographics, benchmark)
        return {
            "comparison_area": "AI Use",
            "comparison_source": "usage_frequency",
            "primary_dimension": None,
            "primary_dimension_label": "Reported Usage Frequency",
            "actual_percentile": clean_int(percentile),
            "actual_position": (
                position_phrase(percentile)
                if percentile is not None
                else "comparison unavailable"
            ),
            "measured_basis": (
                "Reported AI-use frequency compared with the frequency "
                "distribution within the HCI participant benchmark."
            ),
        }

    if source == "dependence_derived":
        percentile = derived_dependence_percentile(responses, benchmark)
        return {
            "comparison_area": "Dependence-related responses",
            "comparison_source": "dependence_derived",
            "primary_dimension": None,
            "primary_dimension_label": "Dependence-related responses",
            "actual_percentile": clean_int(percentile),
            "actual_position": (
                position_phrase(percentile)
                if percentile is not None
                else "comparison unavailable"
            ),
            "measured_basis": (
                "Derived from three self-reported Reliance items related to "
                "unease without AI, difficulty functioning without AI and "
                "perceived ability weakening."
            ),
        }

    primary = meta.get("primary_dimension") or "reliance"
    percentile = dimensions.get(primary, {}).get("percentile")
    label = DIMENSION_LABELS.get(primary, primary)
    return {
        "comparison_area": meta.get("comparison_area") or label,
        "comparison_source": source or primary,
        "primary_dimension": primary,
        "primary_dimension_label": label,
        "actual_percentile": clean_int(percentile),
        "actual_position": (
            position_phrase(percentile)
            if percentile is not None
            else "comparison unavailable"
        ),
        "measured_basis": (
            f"Based on your self-reported responses within the {label} dimension."
        ),
    }


def build_perception_gap(
    scoring_results: Dict[str, Any],
    responses: Dict[str, Any],
    dimensions: Dict[str, Dict[str, Any]],
    demographics: Optional[Dict[str, Any]] = None,
    benchmark: Any = None,
) -> Dict[str, Any]:
    gaps = scoring_results.get("perception_gaps") or []
    rows = []
    demographics = demographics or {}

    for key, meta in SELF_PERCEPTION_MAP.items():
        # Prefer metadata file text if present.
        question = meta["question"]
        if isinstance(PERCEPTION_QUESTIONS, dict) and isinstance(PERCEPTION_QUESTIONS.get(key), dict):
            question = PERCEPTION_QUESTIONS[key].get("text") or question

        comparison = perception_comparison_value(
            key=key,
            meta=meta,
            responses=responses,
            dimensions=dimensions,
            demographics=demographics,
            benchmark=benchmark,
        )

        secondary = meta.get("secondary_dimension")

        rows.append({
            "key": key,
            "question": question,
            "answer": responses.get(key),
            "comparison_area": comparison.get("comparison_area"),
            "comparison_source": comparison.get("comparison_source"),
            "measured_basis": comparison.get("measured_basis"),
            "primary_dimension": comparison.get("primary_dimension"),
            "primary_dimension_label": comparison.get("primary_dimension_label"),
            "actual_percentile": comparison.get("actual_percentile"),
            "actual_position": comparison.get("actual_position"),
            "secondary_dimension": secondary,
            "secondary_percentile": dimensions.get(secondary, {}).get("percentile") if secondary else None,
        })

    return {
        "self_perception": rows,
        "gaps": gaps,
        "largest_gap": gaps[0] if gaps else None,
        "has_significant_gap": bool(gaps),
    }


def combo_signal(d1: str, d2: str, item: Optional[Dict[str, Any]] = None) -> str:
    """Return the best available research signal for a dimension combination.

    The signals library uses semantic keys such as
    high_reliance_high_agency, while scoring outputs also include generic
    dimension pairs. This helper supports both so Section 4 gets the
    intended HCI research language whenever possible.
    """
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

    # Directional fallback keys from bands, e.g. high_reliance_low_verification.
    b1 = item.get("band_dim1")
    b2 = item.get("band_dim2")
    if b1 and b2:
        candidate_keys.extend([
            f"{b1}_{d1}_{b2}_{d2}",
            f"{b2}_{d2}_{b1}_{d1}",
        ])

    for key in candidate_keys:
        val = combos.get(key)
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            parts = [
                val.get("why_unusual"),
                val.get("what_it_reveals"),
                val.get("research_signal"),
                val.get("insight"),
                val.get("series"),
                val.get("text"),
            ]
            return " ".join(str(x) for x in parts if x)

    return str(item.get("research_signal") or "")


def infer_rarity_source(item: Dict[str, Any]) -> str:
    """Classify the provenance of a combination rarity value."""
    explicit = str(
        item.get("rarity_source")
        or item.get("source")
        or item.get("evidence_source")
        or ""
    ).strip().lower()

    if explicit in {"calculated", "benchmark_calculated", "benchmark"}:
        return "calculated"
    if explicit in {
        "approved_research_estimate",
        "research_estimate",
        "library_estimate",
        "approved",
    }:
        return "approved_research_estimate"

    # A value returned directly by the scoring pipeline is treated as calculated
    # only where the source object actually contains the rarity field.
    if item.get("rarity_percent") is not None or item.get("frequency_pct") is not None:
        return "calculated"

    return "fallback"


def build_rare_combinations(
    scoring_results: Dict[str, Any],
    dimensions: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Normalize detected combinations without inventing a rarity value.

    A combination may still be useful when prevalence is unavailable, but it
    cannot receive a public rarity badge unless ``rarity_shareable`` is true.
    """
    out: List[Dict[str, Any]] = []
    raw_combos = (
        scoring_results.get("rare_combinations")
        or (scoring_results.get("patterns") or {}).get("rare_combinations")
        or []
    )

    for item in raw_combos:
        if not isinstance(item, dict):
            continue

        combo = item.get("combo") or [None, None]
        d1 = item.get("dimension_1") or (combo[0] if len(combo) > 0 else None)
        d2 = item.get("dimension_2") or (combo[1] if len(combo) > 1 else None)
        if not d1 or not d2:
            continue

        percentiles = item.get("percentiles") or [None, None]
        rarity_percent = clean_float(
            item.get("rarity_percent")
            if item.get("rarity_percent") is not None
            else item.get("frequency_pct")
        )
        rarity_source = infer_rarity_source(item)
        rarity_shareable = bool(
            rarity_percent is not None
            and rarity_source in {"calculated", "approved_research_estimate"}
        )

        classification = (
            item.get("combo_classification")
            or item.get("classification")
            or (
                "true_rare"
                if rarity_percent is not None and rarity_percent <= 5
                else "notable"
            )
        )

        out.append({
            "dimension_1": d1,
            "dimension_2": d2,
            "label_1": DIMENSION_LABELS.get(d1, d1),
            "label_2": DIMENSION_LABELS.get(d2, d2),
            "percentile_1": clean_int(
                item.get("percentile_dim1")
                or (percentiles[0] if len(percentiles) > 0 else None)
                or dimensions.get(d1, {}).get("percentile")
            ),
            "percentile_2": clean_int(
                item.get("percentile_dim2")
                or (percentiles[1] if len(percentiles) > 1 else None)
                or dimensions.get(d2, {}).get("percentile")
            ),
            "rarity_percent": rarity_percent,
            "rarity_source": rarity_source,
            "rarity_shareable": rarity_shareable,
            "sample_basis": (
                item.get("sample_basis")
                or item.get("benchmark_basis")
                or item.get("n")
            ),
            "description": (
                item.get("description")
                or f"{DIMENSION_LABELS.get(d1, d1)} + {DIMENSION_LABELS.get(d2, d2)}"
            ),
            "combo_classification": classification,
            "combination_id": item.get("combination_id"),
            "signal_type": item.get("signal_type"),
            "band_dim1": item.get("band_dim1"),
            "band_dim2": item.get("band_dim2"),
            "research_signal": combo_signal(d1, d2, item),
        })

    # Keep all valid detections in the canonical data. Downstream presentation
    # normally uses only the strongest one.
    return out


def combination_sort_key(item: Dict[str, Any]) -> tuple:
    """Rank combinations by supported rarity and profile extremity."""
    shareable = 1 if item.get("rarity_shareable") else 0
    rarity = item.get("rarity_percent")
    rarity_score = (100 - float(rarity)) if rarity is not None else 0
    p1 = clean_int(item.get("percentile_1"), 50) or 50
    p2 = clean_int(item.get("percentile_2"), 50) or 50
    extremity = abs(p1 - 50) + abs(p2 - 50)
    return (shareable, rarity_score, extremity)


def select_strongest_combination(
    combinations: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not combinations:
        return None
    return deepcopy(max(combinations, key=combination_sort_key))



# ---------------------------------------------------------------------
# V2 deterministic report structures
# ---------------------------------------------------------------------

REPORT_SCHEMA_VERSION = "hci_report_data_v2"
REPORT_VERSION = "2.0"
BENCHMARK_RESPONSE_COUNT_LABEL = "10,000+ participant responses"
BENCHMARK_STUDY_COUNT = 21
MAIN_EVIDENCE_MIN = 5
MAIN_EVIDENCE_MAX = 7


def benchmark_metadata(benchmark: Any) -> Dict[str, Any]:
    """Read available benchmark provenance without inventing missing metadata."""
    data = get_benchmark_data(benchmark)
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

    def first_value(*values: Any) -> Any:
        for value in values:
            if value not in (None, ""):
                return value
        return None

    return {
        "name": "HCI participant benchmark",
        "response_count_label": BENCHMARK_RESPONSE_COUNT_LABEL,
        "study_count": BENCHMARK_STUDY_COUNT,
        "version": first_value(
            getattr(benchmark, "version", None),
            metadata.get("version"),
            data.get("version"),
        ),
        "generated_at": first_value(
            getattr(benchmark, "generated_at", None),
            metadata.get("generated_at"),
            metadata.get("created_at"),
            data.get("generated_at"),
        ),
        "hash": first_value(
            getattr(benchmark, "benchmark_hash", None),
            getattr(benchmark, "hash", None),
            metadata.get("benchmark_hash"),
            metadata.get("hash"),
        ),
        "minimum_cohort_n": get_min_sample_size(benchmark),
    }


def build_report_meta(
    session_id: str,
    email: Optional[str],
    demographics: Dict[str, Any],
    benchmark: Any,
) -> Dict[str, Any]:
    created_at = now_iso()
    return {
        "session_id": session_id,
        "email": email,
        "created_at": created_at,
        "report_version": REPORT_VERSION,
        "schema_version": REPORT_SCHEMA_VERSION,
        "baseline_date": created_at,
        "reported_ai_use_frequency": (
            demographics.get("_frequency_benchmark")
            or demographics.get("ai_tool_use_frequency")
            or demographics.get("frequency")
        ),
        "age_group": (
            demographics.get("_age_group_benchmark")
            or demographics.get("age_group")
        ),
        "country_display": demographics.get("country_display"),
        "benchmark": benchmark_metadata(benchmark),
    }


def build_position(
    dimensions: Dict[str, Dict[str, Any]],
    demographics: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build the nine deterministic position cards used by the V2 report."""
    frequency_label = (
        demographics.get("_frequency_benchmark")
        or demographics.get("ai_tool_use_frequency")
        or "similar AI use"
    )
    age_label = (
        demographics.get("_age_group_benchmark")
        or demographics.get("age_group")
        or "your age group"
    )

    cards: List[Dict[str, Any]] = []
    for dim in DIMENSION_ORDER:
        d = dimensions[dim]
        overall = clean_int(d.get("percentile"))
        frequency = clean_int(d.get("percentile_frequency"))
        age = clean_int(d.get("percentile_age_group"))

        cards.append({
            "key": dim,
            "label": d.get("label"),
            "definition": d.get("definition"),
            "raw_score": d.get("raw_score"),
            "overall_percentile": overall,
            "overall_percentile_label": ordinal(overall) if overall is not None else "Unavailable",
            "overall_position": position_phrase(overall) if overall is not None else "comparison unavailable",
            "frequency_percentile": frequency,
            "frequency_percentile_label": ordinal(frequency) if frequency is not None else "Unavailable",
            "frequency_label": f"Participants reporting {frequency_label} AI use",
            "frequency_n": d.get("n_frequency"),
            "frequency_available": frequency is not None,
            "age_percentile": age,
            "age_percentile_label": ordinal(age) if age is not None else "Unavailable",
            "age_label": f"Age group {age_label}",
            "age_n": d.get("n_age_group"),
            "age_available": age is not None,
            "overall_n": d.get("n_overall"),
            "distance_from_centre": abs((overall if overall is not None else 50) - 50),
            "frequency_shift": (
                overall - frequency
                if overall is not None and frequency is not None
                else None
            ),
        })
    return cards


def comparison_meaning(overall: int, frequency: int) -> str:
    """Return a concise deterministic explanation of a cohort shift."""
    shift = overall - frequency
    magnitude = abs(shift)

    if magnitude < 10:
        return "Your overall and similar-use positions are broadly aligned."
    if shift > 0:
        return (
            "This stands out more in the overall benchmark than it does among "
            "participants who report using AI about as frequently as you."
        )
    return (
        "This remains especially distinctive even among participants who "
        "report using AI about as frequently as you."
    )


def build_comparison_shifts(
    position: List[Dict[str, Any]],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for item in position:
        overall = item.get("overall_percentile")
        frequency = item.get("frequency_percentile")
        if overall is None or frequency is None:
            continue

        shift = int(overall) - int(frequency)
        row = {
            "dimension": item.get("key"),
            "label": item.get("label"),
            "overall_percentile": overall,
            "frequency_percentile": frequency,
            "shift": shift,
            "absolute_shift": abs(shift),
            "direction": (
                "less distinctive among similar users"
                if shift > 0
                else "more distinctive among similar users"
                if shift < 0
                else "aligned"
            ),
            "meaning": comparison_meaning(int(overall), int(frequency)),
            "frequency_n": item.get("frequency_n"),
        }
        candidates.append(row)

    candidates.sort(
        key=lambda x: (x["absolute_shift"], abs((x["overall_percentile"] or 50) - 50)),
        reverse=True,
    )
    return candidates[:limit]


def evidence_counts_by_dimension(
    distinctive_responses: List[Dict[str, Any]],
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in distinctive_responses:
        dim = item.get("dimension")
        if dim:
            counts[dim] = counts.get(dim, 0) + 1
    return counts


def build_defining_signals(
    dimensions: Dict[str, Dict[str, Any]],
    distinctive_responses: List[Dict[str, Any]],
    strongest_combination: Optional[Dict[str, Any]],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    Select the dimensions carrying the most information in the current profile.

    Selection considers:
    - distance from the HCI benchmark centre;
    - distinction from similar-frequency users;
    - involvement in the strongest combination;
    - number of main evidence responses.
    """
    evidence_counts = evidence_counts_by_dimension(distinctive_responses)
    combo_dimensions = set()
    if strongest_combination:
        combo_dimensions.update([
            strongest_combination.get("dimension_1"),
            strongest_combination.get("dimension_2"),
        ])

    ranked: List[Dict[str, Any]] = []
    for dim in DIMENSION_ORDER:
        d = dimensions[dim]
        overall = clean_int(d.get("percentile"), 50) or 50
        frequency = clean_int(d.get("percentile_frequency"))
        extremity = abs(overall - 50)
        frequency_distinction = abs(overall - frequency) if frequency is not None else 0
        combination_bonus = 35 if dim in combo_dimensions else 0
        evidence_bonus = min(evidence_counts.get(dim, 0), 2) * 8

        information_score = (
            extremity
            + (0.45 * frequency_distinction)
            + combination_bonus
            + evidence_bonus
        )

        ranked.append({
            "key": dim,
            "label": d.get("label"),
            "definition": d.get("definition"),
            "overall_percentile": overall,
            "frequency_percentile": frequency,
            "age_percentile": d.get("percentile_age_group"),
            "position": d.get("position"),
            "distance_from_centre": extremity,
            "frequency_difference": (
                overall - frequency if frequency is not None else None
            ),
            "in_strongest_combination": dim in combo_dimensions,
            "supporting_evidence_count": evidence_counts.get(dim, 0),
            "information_score": round(information_score, 2),
        })

    ranked.sort(
        key=lambda x: (
            x["information_score"],
            x["distance_from_centre"],
            x["overall_percentile"],
        ),
        reverse=True,
    )
    return ranked[:limit]


def build_main_evidence(
    questions: List[Dict[str, Any]],
    defining_signals: List[Dict[str, Any]],
    limit: int = MAIN_EVIDENCE_MAX,
) -> List[Dict[str, Any]]:
    """Select 5–7 auditable evidence cards for the main report."""
    defining = {item.get("key") for item in defining_signals}
    candidates: List[Dict[str, Any]] = []

    for question in questions:
        percentile = question.get("percentile")
        if percentile is None:
            continue

        item = deepcopy(question)
        distance = abs((clean_int(percentile, 50) or 50) - 50)
        frequency = clean_int(question.get("percentile_frequency"))
        frequency_distance = abs((clean_int(percentile, 50) or 50) - frequency) if frequency is not None else 0
        defining_bonus = 18 if question.get("dimension") in defining else 0
        item["evidence_score"] = round(
            distance + (0.35 * frequency_distance) + defining_bonus,
            2,
        )
        item["distance_from_centre"] = distance
        item["evidence_statement"] = (
            f"This response is one of the clearest pieces of evidence "
            f"supporting your {question.get('dimension_label')} result."
        )
        candidates.append(item)

    candidates.sort(
        key=lambda x: (
            x.get("evidence_score", 0),
            x.get("distance_from_centre", 0),
        ),
        reverse=True,
    )

    selected: List[Dict[str, Any]] = []
    per_dimension: Dict[str, int] = {}

    # First pass: preserve breadth across the profile.
    for item in candidates:
        dim = item.get("dimension") or "unknown"
        if per_dimension.get(dim, 0) >= 2:
            continue
        selected.append(item)
        per_dimension[dim] = per_dimension.get(dim, 0) + 1
        if len(selected) >= limit:
            break

    # Fill remaining places if sparse benchmark data prevented a full set.
    if len(selected) < MAIN_EVIDENCE_MIN:
        seen = {item.get("key") for item in selected}
        for item in candidates:
            if item.get("key") in seen:
                continue
            selected.append(item)
            if len(selected) >= min(limit, MAIN_EVIDENCE_MIN):
                break

    return selected[:limit]


def extract_perceived_percentile(
    gap_item: Optional[Dict[str, Any]],
) -> Optional[int]:
    if not isinstance(gap_item, dict):
        return None
    for key in (
        "perceived_percentile",
        "self_percentile",
        "expected_percentile",
        "perceived_position_percentile",
    ):
        value = clean_int(gap_item.get(key))
        if value is not None:
            return value
    return None


def build_perception_summary(
    perception_gap: Dict[str, Any],
) -> Dict[str, Any]:
    gaps = perception_gap.get("gaps") or []
    gap_by_key = {
        str(item.get("key")): item
        for item in gaps
        if isinstance(item, dict) and item.get("key")
    }

    items: List[Dict[str, Any]] = []
    for row in perception_gap.get("self_perception") or []:
        key = row.get("key")
        gap = gap_by_key.get(str(key))
        perceived_percentile = extract_perceived_percentile(gap)
        actual = clean_int(row.get("actual_percentile"))
        difference = (
            actual - perceived_percentile
            if actual is not None and perceived_percentile is not None
            else None
        )

        items.append({
            "key": key,
            "question": row.get("question"),
            "self_estimate": row.get("answer"),
            "comparison_area": row.get("comparison_area"),
            "assessment_percentile": actual,
            "assessment_position": row.get("actual_position"),
            "perceived_percentile": perceived_percentile,
            "difference": difference,
            "difference_available": difference is not None,
            "basis": row.get("measured_basis"),
        })

    comparable = [item for item in items if item.get("difference") is not None]
    largest = (
        max(comparable, key=lambda x: abs(x.get("difference") or 0))
        if comparable
        else None
    )
    return {
        "items": items,
        "largest_difference": largest,
        "has_numeric_difference": bool(comparable),
    }


def build_dimension_reference(
    dimensions: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    reference: List[Dict[str, Any]] = []
    for dim in DIMENSION_ORDER:
        d = dimensions[dim]
        overall = clean_int(d.get("percentile"))
        frequency = clean_int(d.get("percentile_frequency"))

        if overall is None:
            note = "A benchmark position was unavailable for this dimension."
        elif frequency is None:
            note = (
                f"Your result sits at the {ordinal(overall)} percentile within "
                "the HCI participant benchmark."
            )
        elif abs(overall - frequency) < 10:
            note = (
                "Your overall position and your position among participants "
                "with similar AI-use frequency are broadly aligned."
            )
        elif overall > frequency:
            note = (
                "This result is more distinctive in the overall benchmark than "
                "among participants with similar AI-use frequency."
            )
        else:
            note = (
                "This result remains especially distinctive among participants "
                "with similar AI-use frequency."
            )

        reference.append({
            "key": dim,
            "label": d.get("label"),
            "definition": d.get("definition"),
            "overall_percentile": overall,
            "frequency_percentile": frequency,
            "position": d.get("position"),
            "behavioural_note": note,
        })
    return reference


def build_baseline(
    report_meta: Dict[str, Any],
    position: List[Dict[str, Any]],
    defining_signals: List[Dict[str, Any]],
    strongest_combination: Optional[Dict[str, Any]],
    perception_summary: Dict[str, Any],
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Create the immutable current-reference package used by the Baseline section.

    The final personalised return question is generated later. The comparison
    priorities themselves are deterministic.
    """
    priorities: List[Dict[str, Any]] = []

    for signal in defining_signals:
        priorities.append({
            "type": "dimension",
            "key": signal.get("key"),
            "label": signal.get("label"),
            "current_percentile": signal.get("overall_percentile"),
            "reason": (
                "This is one of the three signals carrying the most information "
                "in your current profile."
            ),
        })

    # Keep exactly three priorities. Defining signals already contain three
    # under a valid nine-dimension report.
    priorities = priorities[:3]

    return {
        "baseline_date": report_meta.get("baseline_date"),
        "report_version": report_meta.get("report_version"),
        "benchmark": deepcopy(report_meta.get("benchmark") or {}),
        "reported_ai_use_frequency": report_meta.get("reported_ai_use_frequency"),
        "dimension_positions": deepcopy(position),
        "defining_signals": deepcopy(defining_signals),
        "strongest_combination": deepcopy(strongest_combination),
        "largest_perception_difference": deepcopy(
            perception_summary.get("largest_difference")
        ),
        "distinctive_evidence_keys": [
            item.get("key") for item in evidence if item.get("key")
        ],
        "comparison_priorities": priorities,
        "recommended_reassessment_window": "6–12 months",
        "return_question": None,
        "baseline_closing": None,
    }


def build_methodology(
    report_meta: Dict[str, Any],
) -> Dict[str, Any]:
    benchmark = report_meta.get("benchmark") or {}
    return {
        "assessment_type": "Self-report behavioural benchmark",
        "dimensions": [
            {
                "key": dim,
                "label": DIMENSION_LABELS[dim],
                "definition": DIMENSION_DEFINITIONS[dim],
            }
            for dim in DIMENSION_ORDER
        ],
        "benchmark_name": benchmark.get("name"),
        "benchmark_response_count_label": benchmark.get("response_count_label"),
        "benchmark_study_count": benchmark.get("study_count"),
        "benchmark_version": benchmark.get("version"),
        "benchmark_generated_at": benchmark.get("generated_at"),
        "benchmark_hash": benchmark.get("hash"),
        "minimum_cohort_n": benchmark.get("minimum_cohort_n"),
        "percentile_explanation": (
            "Percentiles show where a participant's self-reported assessment "
            "result sits within the relevant HCI participant benchmark distribution."
        ),
        "cohort_rule": (
            "Age and AI-use-frequency comparisons are shown only where the "
            "relevant benchmark cohort meets the minimum sample requirement."
        ),
        "self_report_note": (
            "Results reflect the participant's self-reported responses and are "
            "not an independent observation of behaviour."
        ),
    }


def build_signature_skeleton(
    defining_signals: List[Dict[str, Any]],
    strongest_combination: Optional[Dict[str, Any]],
    evidence: List[Dict[str, Any]],
    perception_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Prepare the deterministic ingredients for the generated Signature page."""
    return {
        "signature_sentence": None,
        "defining_signals": deepcopy(defining_signals),
        "strongest_combination": deepcopy(strongest_combination),
        "strongest_evidence": deepcopy(evidence[0] if evidence else None),
        "largest_perception_difference": deepcopy(
            perception_summary.get("largest_difference")
        ),
        "shareable": {
            "rarity_badge_allowed": bool(
                strongest_combination
                and strongest_combination.get("rarity_shareable")
            ),
            "sensitive_detail_included": False,
        },
    }


def build_distinctive_pattern(
    strongest_combination: Optional[Dict[str, Any]],
    defining_signals: List[Dict[str, Any]],
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if strongest_combination:
        relevant_dims = {
            strongest_combination.get("dimension_1"),
            strongest_combination.get("dimension_2"),
        }
        support = [
            deepcopy(item)
            for item in evidence
            if item.get("dimension") in relevant_dims
        ][:3]
        return {
            "mode": "combination",
            "title": "What Makes You Different",
            "combination": deepcopy(strongest_combination),
            "supporting_evidence": support,
            "narrative": None,
        }

    return {
        "mode": "coherence",
        "title": "What Makes Your Pattern Coherent",
        "combination": None,
        "defining_signals": deepcopy(defining_signals),
        "supporting_evidence": deepcopy(evidence[:3]),
        "narrative": None,
    }


def build_v2_data_quality(report_data: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []

    if report_data.get("schema_version") != REPORT_SCHEMA_VERSION:
        errors.append("Unexpected report schema version.")

    if len(report_data.get("position") or []) != 9:
        errors.append("Expected exactly 9 position cards.")

    if len(report_data.get("appendix_questions") or []) != 39:
        errors.append(
            f"Expected 39 appendix questions, got "
            f"{len(report_data.get('appendix_questions') or [])}."
        )

    evidence_count = len(report_data.get("evidence") or [])
    if evidence_count < MAIN_EVIDENCE_MIN or evidence_count > MAIN_EVIDENCE_MAX:
        warnings.append(
            f"Expected {MAIN_EVIDENCE_MIN}–{MAIN_EVIDENCE_MAX} main evidence "
            f"items, got {evidence_count}."
        )

    if len(report_data.get("defining_signals") or []) != 3:
        errors.append("Expected exactly 3 defining signals.")

    if not report_data.get("comparison_shifts"):
        warnings.append("No valid similar-frequency comparison shifts were available.")

    unsupported_rarity = [
        item
        for item in report_data.get("rare_combinations") or []
        if item.get("rarity_percent") is not None
        and not item.get("rarity_shareable")
    ]
    if unsupported_rarity:
        warnings.append(
            f"{len(unsupported_rarity)} combination rarity values are retained "
            "internally but are not approved for public display."
        )

    missing_frequency = [
        item.get("key")
        for item in report_data.get("position") or []
        if item.get("frequency_percentile") is None
    ]
    if missing_frequency:
        warnings.append(
            f"Similar-frequency position unavailable for {len(missing_frequency)} "
            f"dimensions: {missing_frequency}."
        )

    benchmark = (report_data.get("report_meta") or {}).get("benchmark") or {}
    if not benchmark.get("version"):
        warnings.append("Benchmark version metadata is unavailable.")
    if not benchmark.get("hash"):
        warnings.append("Benchmark hash metadata is unavailable.")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "generated_at": now_iso(),
    }



# ---------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------

def build_report_data(
    scoring_results: Dict[str, Any],
    responses: Optional[Dict[str, Any]] = None,
    demographics: Optional[Dict[str, Any]] = None,
    email: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the canonical HCI premium-report V2 data object."""
    if not isinstance(scoring_results, dict):
        raise ValueError("scoring_results must be a dict")

    responses = responses or scoring_results.get("responses") or {}
    original_demographics = (
        demographics or scoring_results.get("demographics") or {}
    )
    session_id = (
        session_id
        or scoring_results.get("session_id")
        or str(uuid.uuid4())
    )

    benchmark = get_benchmark_instance()
    normalised_demographics = normalise_demographics_for_benchmark(
        original_demographics,
        benchmark,
    )

    dimensions = normalize_dimensions(
        scoring_results,
        normalised_demographics,
        benchmark,
    )
    questions = build_questions(
        responses,
        normalised_demographics,
        benchmark,
    )
    raw_perception = build_perception_gap(
        scoring_results,
        responses,
        dimensions,
        normalised_demographics,
        benchmark,
    )
    perception_summary = build_perception_summary(raw_perception)

    rare_combinations = build_rare_combinations(
        scoring_results,
        dimensions,
    )
    strongest_combination = select_strongest_combination(
        rare_combinations,
    )

    # Initial distinctiveness is used only as an input to defining-signal
    # selection. Main-report evidence is then selected against those signals.
    initial_distinctive = build_distinctive_responses(
        questions,
        MAIN_EVIDENCE_MAX,
    )
    defining_signals = build_defining_signals(
        dimensions,
        initial_distinctive,
        strongest_combination,
        limit=3,
    )
    evidence = build_main_evidence(
        questions,
        defining_signals,
        limit=MAIN_EVIDENCE_MAX,
    )

    report_meta = build_report_meta(
        session_id,
        email,
        normalised_demographics,
        benchmark,
    )
    position = build_position(
        dimensions,
        normalised_demographics,
    )
    comparison_shifts = build_comparison_shifts(
        position,
        limit=5,
    )
    dimension_reference = build_dimension_reference(dimensions)
    signature = build_signature_skeleton(
        defining_signals,
        strongest_combination,
        evidence,
        perception_summary,
    )
    distinctive_pattern = build_distinctive_pattern(
        strongest_combination,
        defining_signals,
        evidence,
    )
    baseline = build_baseline(
        report_meta,
        position,
        defining_signals,
        strongest_combination,
        perception_summary,
        evidence,
    )
    methodology = build_methodology(report_meta)

    report_data: Dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_meta": report_meta,
        "session_id": session_id,
        "email": email,
        "created_at": report_meta["created_at"],
        "demographics": normalised_demographics,
        "responses": responses,

        # Locked V2 report contract.
        "signature": signature,
        "position": position,
        "comparison_shifts": comparison_shifts,
        "defining_signals": defining_signals,
        "distinctive_pattern": distinctive_pattern,
        "evidence": evidence,
        "perception_summary": perception_summary,
        "pattern_synthesis": {
            "organising_feature": None,
            "pattern_narrative": None,
        },
        "human_capital_lens": [],
        "dimension_reference": dimension_reference,
        "baseline": baseline,
        "appendix_questions": deepcopy(questions),
        "methodology": methodology,
        "narrative_blocks": {},

        # Internal evidence retained for later context selection and QA.
        "dimensions": dimensions,
        "rare_combinations": rare_combinations,
        "questions": questions,
        "perception_gap": raw_perception,
    }

    # Temporary compatibility aliases. These allow the existing API and old
    # downstream files to import the V2 builder while Items 4–8 are rebuilt.
    # They are not the V2 presentation contract.
    report_data.update({
        "dashboard": build_dashboard(
            dimensions,
            normalised_demographics,
        ),
        "typicality": build_typicality(dimensions),
        "distinctive_responses": evidence,
        "what_to_protect": [],
        "if_nothing_changes": {},
        "human_capital": {},
        "synthesis_inputs": {
            "most_distinctive_variable": evidence[0] if evidence else None,
            "largest_perception_gap": perception_summary.get(
                "largest_difference"
            ),
            "top_rare_combination": strongest_combination,
            "top_dimensions": defining_signals,
            "lowest_dimensions": sorted(
                dimensions.values(),
                key=lambda d: d.get("percentile", 50),
            )[:3],
        },
    })

    report_data["data_quality"] = build_v2_data_quality(report_data)
    assert_report_data_contract(report_data)
    return report_data


def assert_report_data_contract(report_data: Dict[str, Any]) -> None:
    """Validate the locked HCI report-data V2 contract."""
    required = [
        "schema_version",
        "report_meta",
        "session_id",
        "demographics",
        "signature",
        "position",
        "comparison_shifts",
        "defining_signals",
        "distinctive_pattern",
        "evidence",
        "perception_summary",
        "pattern_synthesis",
        "human_capital_lens",
        "dimension_reference",
        "baseline",
        "appendix_questions",
        "methodology",
        "narrative_blocks",
        "data_quality",
    ]
    missing = [key for key in required if key not in report_data]
    if missing:
        raise ValueError(f"report_data missing required V2 keys: {missing}")

    if report_data.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {REPORT_SCHEMA_VERSION}"
        )
    if len(report_data.get("position") or []) != 9:
        raise ValueError("position must contain exactly 9 dimension cards")
    if len(report_data.get("dimension_reference") or []) != 9:
        raise ValueError(
            "dimension_reference must contain exactly 9 dimensions"
        )
    if len(report_data.get("defining_signals") or []) != 3:
        raise ValueError("defining_signals must contain exactly 3 items")
    if len(report_data.get("appendix_questions") or []) != 39:
        raise ValueError(
            "appendix_questions must contain exactly 39 questions"
        )

    evidence_count = len(report_data.get("evidence") or [])
    if not MAIN_EVIDENCE_MIN <= evidence_count <= MAIN_EVIDENCE_MAX:
        raise ValueError(
            f"evidence must contain {MAIN_EVIDENCE_MIN}–"
            f"{MAIN_EVIDENCE_MAX} items"
        )

    for combo in report_data.get("rare_combinations") or []:
        if combo.get("rarity_shareable"):
            if combo.get("rarity_percent") is None:
                raise ValueError(
                    "Shareable rarity requires rarity_percent"
                )
            if combo.get("rarity_source") not in {
                "calculated",
                "approved_research_estimate",
            }:
                raise ValueError(
                    "Shareable rarity requires an approved source"
                )

