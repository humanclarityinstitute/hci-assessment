"""
report_data_builder.py

Canonical HCI report-data builder for the premium report.

This V2 implementation deliberately preserves the original production data
flow and legacy report keys while adding the new V2 structures required by the
locked report layout.

Preserved production guarantees:
- Builds 9 dimension cards.
- Builds 39 question cards.
- Uses full question text from question_metadata.py.
- Recalculates missing dimension age/frequency percentiles from benchmark data.
- Normalises demographic values to benchmark cohort keys.
- Does NOT silently duplicate overall distributions as age-group distributions.
- Stores data_quality warnings so missing cohort data is visible during testing.

V2 additions are derived from the same canonical dimensions, questions,
perception gaps and combinations. They do not recalculate or replace the
original scoring flow.
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
    # Participant-facing reports must use the legally and scientifically
    # restrained signals layer. If it is unavailable, fail closed to empty
    # context rather than falling back to the stronger internal synthesis.
    from hci_signals_library import REPORT_SAFE_SIGNALS as SIGNALS
except Exception:
    SIGNALS = {"dimensions": {}, "trends": {}, "combinations": {}, "human_reference": {}}

try:
    import human_reference_layer as HRL
except Exception:
    HRL = None


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

def safe_dimension_source(dim: str) -> Dict[str, Any]:
    """Return the participant-facing signal dictionary for one dimension."""
    dims = SIGNALS.get("dimensions", {}) if isinstance(SIGNALS, dict) else {}
    signal = dims.get(dim) or dims.get(DIMENSION_LABELS.get(dim, dim)) or {}
    return signal if isinstance(signal, dict) else {}


def definition_for_dimension(dim: str) -> str:
    """Prefer the report-safe definition, with the locked definition as fallback."""
    signal = safe_dimension_source(dim)
    return str(signal.get("definition") or DIMENSION_DEFINITIONS.get(dim, ""))


def signal_for_dimension(dim: str, percentile: Any) -> str:
    signal = safe_dimension_source(dim)
    if not signal:
        return ""

    p = clean_int(percentile, 50) or 50
    if p >= 71:
        text = signal.get("high")
    elif p <= 40:
        text = signal.get("low")
    else:
        text = signal.get("typical")

    text = text or signal.get("series") or signal.get("definition")
    return str(text or "")


def hrl_context(dim: str, percentile: Any = None) -> Dict[str, Any]:
    """
    Return only explicitly approved participant-facing HRL fields.

    Do not pass complete HRL dictionaries through by generic dimension lookup.
    Several HRL libraries use concept, pattern or cohort keys rather than
    dimension keys, and broad passthrough can supply irrelevant interpretation.
    """
    if HRL is None:
        return {}

    framework = getattr(HRL, "HBE_FRAMEWORK", None)
    if not isinstance(framework, dict):
        return {}

    item = framework.get(dim) or framework.get(DIMENSION_LABELS.get(dim, dim))
    if not isinstance(item, dict):
        return {}

    out: Dict[str, Any] = {
        "hbe_framework": {
            key: item.get(key)
            for key in ("hbe_baseline", "ai_pressure", "reframe")
            if item.get(key) is not None
        }
    }

    get_reframe = getattr(HRL, "get_values_reframe", None)
    if callable(get_reframe):
        p = clean_int(percentile, 50) or 50
        position = "high" if p >= 71 else "low" if p <= 40 else "moderate"
        try:
            reframe = get_reframe(dim, position)
            if reframe and "not available in library" not in str(reframe):
                out["values_reframe"] = reframe
        except Exception:
            pass

    return out


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
            "research_insight": signal_for_dimension(dim, p),
            "hrl_context": hrl_context(dim, p),
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
            "research_insight": d["research_insight"],
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
            "interpretation": d.get("research_insight", ""),
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
    """
    Return explicit rarity provenance only.

    The current scoring engine can insert fallback numeric values when aligned
    benchmark co-occurrence is unavailable. A number alone is therefore not
    proof that rarity was calculated.
    """
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
    return "fallback"


def build_rare_combinations(
    scoring_results: Dict[str, Any],
    dimensions: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Preserve the original combination order and fields, while adding provenance
    controls for V2 public rarity claims.
    """
    out = []
    raw_combos = (
        scoring_results.get("rare_combinations")
        or scoring_results.get("patterns", {}).get("rare_combinations", [])
        or []
    )

    # Preserve the original two-combination limit and scorer ordering.
    for item in raw_combos[:2]:
        combo = item.get("combo") or [None, None]
        d1 = item.get("dimension_1") or (combo[0] if len(combo) > 0 else None)
        d2 = item.get("dimension_2") or (combo[1] if len(combo) > 1 else None)

        if not d1 or not d2:
            continue

        percentiles = item.get("percentiles") or [None, None]
        rarity_percent = clean_float(
            item.get("rarity_percent")
            or item.get("frequency_pct")
            or 5
        )
        rarity_source = infer_rarity_source(item)
        rarity_shareable = bool(
            rarity_percent is not None
            and rarity_source in {"calculated", "approved_research_estimate"}
        )

        out.append({
            # Original fields preserved.
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
            "description": (
                item.get("description")
                or f"{DIMENSION_LABELS.get(d1, d1)} + "
                   f"{DIMENSION_LABELS.get(d2, d2)}"
            ),
            "combo_classification": (
                item.get("combo_classification")
                or item.get("classification")
                or (
                    "true_rare"
                    if (rarity_percent or 5) <= 5
                    else "notable"
                )
            ),
            "combination_id": item.get("combination_id"),
            "signal_type": item.get("signal_type"),
            "band_dim1": item.get("band_dim1"),
            "band_dim2": item.get("band_dim2"),
            "research_signal": combo_signal(d1, d2, item),

            # V2 provenance fields. Public copy must check rarity_shareable.
            "rarity_source": rarity_source,
            "rarity_shareable": rarity_shareable,
            "public_rarity_percent": (
                rarity_percent if rarity_shareable else None
            ),
            "sample_basis": (
                item.get("sample_basis")
                or item.get("benchmark_basis")
                or item.get("n")
            ),
        })

    return out


def build_what_to_protect(dimensions: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "dimension": dim,
            "label": DIMENSION_LABELS[dim],
            "definition": definition_for_dimension(dim),
            "percentile": dimensions[dim]["percentile"],
            "positioning": protect_position_phrase(dimensions[dim]["percentile"]),
            "research_insight": dimensions[dim].get("research_insight", ""),
            "hrl_context": dimensions[dim].get("hrl_context", {}),
        }
        for dim in PROTECT_DIMENSIONS
    ]


def build_if_nothing_changes(dimensions: Dict[str, Dict[str, Any]], demographics: Dict[str, Any]) -> Dict[str, Any]:
    ranked = sorted(dimensions.values(), key=lambda d: d["percentile"], reverse=True)

    # Prefer clearly elevated dimensions, but never leave the section empty.
    # If no dimension reaches the high-strength threshold, use the strongest
    # two current dimensions so Section 10 still reflects the participant's
    # most prominent current patterns rather than displaying a missing-data message.
    threshold_strengths = [d for d in ranked if d["percentile"] >= 71]
    strengths = threshold_strengths[:3]
    using_fallback_strengths = len(strengths) == 0

    if len(strengths) < 2:
        for dim in ranked:
            if dim not in strengths:
                strengths.append(dim)
            if len(strengths) >= 2:
                break

    monitor = [dimensions[d] for d in ["verification", "reliance", "human_agency"] if d in dimensions]

    return {
        "usage_frequency": demographics.get("_frequency_benchmark") or demographics.get("ai_tool_use_frequency") or demographics.get("frequency"),
        "strengths_likely_to_deepen": strengths,
        "using_fallback_strengths": using_fallback_strengths,
        "areas_worth_monitoring": monitor[:3],
        "highest_dimension": ranked[0] if ranked else None,
        "monitoring_anchor": monitor[0] if monitor else None,
    }




def build_human_capital_inputs(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare a single synthesis package for the Human Capital narrative."""
    synth = report_data.get("synthesis_inputs", {})
    return {
        "overall_profile": synth,
        "dimensions": report_data.get("dimensions", {}),
        "top_dimensions": synth.get("top_dimensions", []),
        "lowest_dimensions": synth.get("lowest_dimensions", []),
        "rare_combinations": report_data.get("rare_combinations", []),
        "distinctive_responses": report_data.get("distinctive_responses", []),
        "behaviour_story": report_data.get("narrative_blocks", {}).get("behaviour_story"),
        "perception_gap": report_data.get("perception_gap", {}),
        "usage_frequency": report_data.get("demographics", {}).get("_frequency_benchmark"),
        "demographics": report_data.get("demographics", {}),
    }

def build_data_quality(report_data: Dict[str, Any]) -> Dict[str, Any]:
    warnings = []

    if len(report_data.get("dimensions", {})) != 9:
        warnings.append("Expected 9 dimensions.")
    if len(report_data.get("dashboard", [])) != 9:
        warnings.append("Expected 9 dashboard cards.")
    if len(report_data.get("questions", [])) != 39:
        warnings.append(f"Expected 39 question cards, got {len(report_data.get('questions', []))}.")

    dashboard_missing_age = [c["key"] for c in report_data.get("dashboard", []) if not c["comparisons"][1].get("percentile")]
    dashboard_missing_freq = [c["key"] for c in report_data.get("dashboard", []) if not c["comparisons"][0].get("percentile")]

    if dashboard_missing_age:
        warnings.append(f"Dashboard age-group percentile missing for {len(dashboard_missing_age)} dimensions: {dashboard_missing_age}.")
    if dashboard_missing_freq:
        warnings.append(f"Dashboard frequency percentile missing for {len(dashboard_missing_freq)} dimensions: {dashboard_missing_freq}.")

    missing_overall_dist = [q["key"] for q in report_data.get("questions", []) if not q.get("distribution_everyone")]
    missing_freq_dist = [q["key"] for q in report_data.get("questions", []) if not q.get("distribution_frequency")]

    if missing_overall_dist:
        warnings.append(f"{len(missing_overall_dist)} overall question distributions missing.")
    if missing_freq_dist:
        warnings.append(f"{len(missing_freq_dist)} AI-use frequency question distributions missing or below threshold.")

    neutral_question_pcts = [q["key"] for q in report_data.get("questions", []) if q.get("percentile") == 50]
    if len(neutral_question_pcts) > 25:
        warnings.append("Many question percentiles are 50; benchmark question-level lookup may be unavailable or mis-keyed.")

    demographics = report_data.get("demographics") or {}
    if demographics.get("_frequency_original") != demographics.get("_frequency_benchmark"):
        warnings.append(f"Frequency normalised from {demographics.get('_frequency_original')} to {demographics.get('_frequency_benchmark')}.")
    if demographics.get("_age_group_original") != demographics.get("_age_group_benchmark"):
        warnings.append(f"Age group normalised from {demographics.get('_age_group_original')} to {demographics.get('_age_group_benchmark')}.")

    return {
        "ok": not warnings,
        "warnings": warnings,
        "generated_at": now_iso(),
    }



# ---------------------------------------------------------------------
# V2 additive report structures
# ---------------------------------------------------------------------

REPORT_SCHEMA_VERSION = "hci_report_data_v2"
REPORT_VERSION = "2.0"
BENCHMARK_RESPONSE_COUNT_LABEL = "10,000+ participant responses"
BENCHMARK_STUDY_COUNT = 21
MAIN_EVIDENCE_MIN = 5
MAIN_EVIDENCE_MAX = 7
MIN_COMPARISON_SHIFT = 10


def benchmark_metadata(benchmark: Any) -> Dict[str, Any]:
    """Read benchmark provenance without inventing unavailable metadata."""
    data = get_benchmark_data(benchmark)
    metadata = (
        data.get("metadata")
        if isinstance(data.get("metadata"), dict)
        else {}
    )

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
    assessment_timestamp: Optional[str],
    created_at: str,
) -> Dict[str, Any]:
    """
    Build report metadata using the scoring timestamp as the baseline date.

    Rebuilding an existing report must not silently move the participant's
    assessment date.
    """
    baseline_date = assessment_timestamp or created_at
    return {
        "session_id": session_id,
        "email": email,
        "created_at": created_at,
        "assessment_completed_at": baseline_date,
        "baseline_date": baseline_date,
        "report_version": REPORT_VERSION,
        "schema_version": REPORT_SCHEMA_VERSION,
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
    """
    Build nine V2 position cards from the original canonical dimension objects.
    """
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
            "overall_percentile_label": (
                ordinal(overall) if overall is not None else "Unavailable"
            ),
            "overall_position": (
                position_phrase(overall)
                if overall is not None
                else "comparison unavailable"
            ),
            "frequency_percentile": frequency,
            "frequency_percentile_label": (
                ordinal(frequency)
                if frequency is not None
                else "Unavailable"
            ),
            "frequency_label": (
                f"Participants reporting {frequency_label} AI use"
            ),
            "frequency_n": d.get("n_frequency"),
            "frequency_available": frequency is not None,
            "age_percentile": age,
            "age_percentile_label": (
                ordinal(age) if age is not None else "Unavailable"
            ),
            "age_label": f"Age group {age_label}",
            "age_n": d.get("n_age_group"),
            "age_available": age is not None,
            "overall_n": d.get("n_overall"),
            "distance_from_centre": (
                abs(overall - 50) if overall is not None else None
            ),
            "frequency_shift": (
                overall - frequency
                if overall is not None and frequency is not None
                else None
            ),
        })
    return cards


def comparison_meaning(overall: int, frequency: int) -> str:
    shift = overall - frequency
    if abs(shift) < MIN_COMPARISON_SHIFT:
        return (
            "Your overall and similar-use positions are broadly aligned."
        )
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
    minimum_shift: int = MIN_COMPARISON_SHIFT,
) -> List[Dict[str, Any]]:
    """
    Return only meaningful overall-versus-similar-use differences.

    Small differences are treated as alignment rather than promoted as premium
    findings.
    """
    candidates: List[Dict[str, Any]] = []
    for item in position:
        overall = item.get("overall_percentile")
        frequency = item.get("frequency_percentile")
        if overall is None or frequency is None:
            continue

        shift = int(overall) - int(frequency)
        if abs(shift) < minimum_shift:
            continue

        candidates.append({
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
            ),
            "meaning": comparison_meaning(int(overall), int(frequency)),
            "frequency_n": item.get("frequency_n"),
        })

    candidates.sort(
        key=lambda item: (
            item["absolute_shift"],
            abs((item["overall_percentile"] or 50) - 50),
        ),
        reverse=True,
    )
    return candidates[:limit]


def build_comparison_summary(
    position: List[Dict[str, Any]],
    comparison_shifts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    valid = [
        item for item in position
        if item.get("overall_percentile") is not None
        and item.get("frequency_percentile") is not None
    ]
    return {
        "valid_comparison_count": len(valid),
        "meaningful_shift_count": len(comparison_shifts),
        "broadly_aligned": bool(valid) and not comparison_shifts,
        "minimum_shift_threshold": MIN_COMPARISON_SHIFT,
    }


def evidence_counts_by_dimension(
    responses: List[Dict[str, Any]],
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in responses:
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
    Select defining signals using a transparent hierarchy.

    Primary rule: distance from the HCI benchmark centre.
    Tie-breakers only: similar-frequency extremity, strongest-combination
    membership, evidence count, then locked dimension order.

    This avoids arbitrary weighted scoring that could override the canonical
    dimension positions.
    """
    evidence_counts = evidence_counts_by_dimension(distinctive_responses)
    combo_dimensions = set()
    if strongest_combination:
        combo_dimensions.update([
            strongest_combination.get("dimension_1"),
            strongest_combination.get("dimension_2"),
        ])

    ranked: List[Dict[str, Any]] = []
    for order_index, dim in enumerate(DIMENSION_ORDER):
        d = dimensions[dim]
        overall = clean_int(d.get("percentile"), 50) or 50
        frequency = clean_int(d.get("percentile_frequency"))
        distance = abs(overall - 50)
        frequency_extremity = (
            abs(frequency - 50) if frequency is not None else -1
        )

        ranked.append({
            "key": dim,
            "label": d.get("label"),
            "definition": d.get("definition"),
            "overall_percentile": overall,
            "frequency_percentile": frequency,
            "age_percentile": d.get("percentile_age_group"),
            "position": d.get("position"),
            "distance_from_centre": distance,
            "frequency_extremity": (
                frequency_extremity if frequency_extremity >= 0 else None
            ),
            "frequency_difference": (
                overall - frequency if frequency is not None else None
            ),
            "in_strongest_combination": dim in combo_dimensions,
            "supporting_evidence_count": evidence_counts.get(dim, 0),
            "selection_basis": "distance_from_hci_benchmark_centre",
            "_order_index": order_index,
        })

    ranked.sort(
        key=lambda item: (
            item["distance_from_centre"],
            item.get("frequency_extremity")
            if item.get("frequency_extremity") is not None
            else -1,
            1 if item["in_strongest_combination"] else 0,
            item["supporting_evidence_count"],
            -item["_order_index"],
        ),
        reverse=True,
    )

    selected = []
    for item in ranked[:limit]:
        clean_item = dict(item)
        clean_item.pop("_order_index", None)
        selected.append(clean_item)
    return selected


def build_main_evidence(
    questions: List[Dict[str, Any]],
    defining_signals: List[Dict[str, Any]],
    limit: int = MAIN_EVIDENCE_MAX,
) -> List[Dict[str, Any]]:
    """
    Select 5–7 evidence cards without changing question values or percentiles.

    First select the most distinctive available item for each defining signal,
    then fill remaining places by question-level distance from the benchmark
    centre, with a two-item cap per dimension.
    """
    candidates: List[Dict[str, Any]] = []
    for question in questions:
        percentile = question.get("percentile")
        if percentile is None:
            continue

        item = deepcopy(question)
        item["distance_from_centre"] = abs(
            (clean_int(percentile, 50) or 50) - 50
        )
        item["evidence_statement"] = (
            f"This response is one of the clearest items helping explain your "
            f"{question.get('dimension_label')} result."
        )
        item["scoring_note"] = (
            "This item is reverse-scored in the dimension calculation."
            if question.get("is_reverse_scored")
            else None
        )
        candidates.append(item)

    candidates.sort(
        key=lambda item: (
            item["distance_from_centre"],
            item.get("percentile") or 0,
        ),
        reverse=True,
    )

    selected: List[Dict[str, Any]] = []
    selected_keys = set()
    per_dimension: Dict[str, int] = {}

    # Guarantee representation from each defining signal where data exists.
    for signal in defining_signals:
        dim = signal.get("key")
        match = next(
            (
                item for item in candidates
                if item.get("dimension") == dim
                and item.get("key") not in selected_keys
            ),
            None,
        )
        if match:
            selected.append(match)
            selected_keys.add(match.get("key"))
            per_dimension[dim] = per_dimension.get(dim, 0) + 1

    # Fill by distinctiveness while preserving breadth.
    for item in candidates:
        if len(selected) >= limit:
            break
        if item.get("key") in selected_keys:
            continue
        dim = item.get("dimension") or "unknown"
        if per_dimension.get(dim, 0) >= 2:
            continue
        selected.append(item)
        selected_keys.add(item.get("key"))
        per_dimension[dim] = per_dimension.get(dim, 0) + 1

    # Sparse-data fallback.
    if len(selected) < MAIN_EVIDENCE_MIN:
        for item in candidates:
            if len(selected) >= min(limit, MAIN_EVIDENCE_MIN):
                break
            if item.get("key") in selected_keys:
                continue
            selected.append(item)
            selected_keys.add(item.get("key"))

    return selected[:limit]


def select_strongest_combination(
    combinations: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Preserve scorer ordering. The scoring engine already ranks its combinations;
    the builder must not silently replace that ordering with new product logic.
    """
    return deepcopy(combinations[0]) if combinations else None


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
    """
    Join the original perception rows to the exact scoring-engine gap shape.

    The live scorer identifies a gap using ``question`` rather than ``key``.
    """
    gaps = perception_gap.get("gaps") or []
    gap_by_key: Dict[str, Dict[str, Any]] = {}
    for item in gaps:
        if not isinstance(item, dict):
            continue
        gap_key = item.get("key") or item.get("question")
        if gap_key:
            gap_by_key[str(gap_key)] = item

    items: List[Dict[str, Any]] = []
    for row in perception_gap.get("self_perception") or []:
        key = row.get("key")
        gap = gap_by_key.get(str(key)) if key is not None else None
        perceived_percentile = extract_perceived_percentile(gap)

        row_actual = clean_int(row.get("actual_percentile"))
        gap_actual = clean_int(gap.get("actual_percentile")) if gap else None
        # Where the live scoring engine supplied a gap, preserve its exact
        # comparison target. The row-level value is a fallback for non-gap rows.
        actual = gap_actual if gap_actual is not None else row_actual

        signed_difference = (
            actual - perceived_percentile
            if actual is not None and perceived_percentile is not None
            else None
        )
        gap_magnitude = (
            clean_float(gap.get("gap_magnitude"))
            if gap
            else None
        )
        if gap_magnitude is None and signed_difference is not None:
            gap_magnitude = abs(signed_difference)

        items.append({
            "key": key,
            "question": row.get("question"),
            "self_estimate": (
                gap.get("perceived_answer")
                if gap and gap.get("perceived_answer") is not None
                else row.get("answer")
            ),
            "comparison_area": row.get("comparison_area"),
            "assessment_percentile": actual,
            "assessment_position": (
                position_phrase(actual)
                if actual is not None
                else row.get("actual_position")
            ),
            "perceived_percentile": perceived_percentile,
            "difference": signed_difference,
            "gap_magnitude": gap_magnitude,
            "difference_available": signed_difference is not None,
            "direction": (
                "assessment position above self-estimate"
                if signed_difference is not None and signed_difference > 0
                else "assessment position below self-estimate"
                if signed_difference is not None and signed_difference < 0
                else "aligned"
                if signed_difference == 0
                else None
            ),
            "basis": row.get("measured_basis"),
        })

    comparable = [
        item for item in items
        if item.get("gap_magnitude") is not None
    ]
    largest = (
        max(comparable, key=lambda item: item.get("gap_magnitude") or 0)
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
        elif abs(overall - frequency) < MIN_COMPARISON_SHIFT:
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
    priorities = [
        {
            "type": "dimension",
            "key": signal.get("key"),
            "label": signal.get("label"),
            "current_percentile": signal.get("overall_percentile"),
            "reason": (
                "This is one of the three dimensions furthest from the HCI "
                "benchmark centre in your current profile."
            ),
        }
        for signal in defining_signals[:3]
    ]

    return {
        "baseline_date": report_meta.get("baseline_date"),
        "report_version": report_meta.get("report_version"),
        "benchmark": deepcopy(report_meta.get("benchmark") or {}),
        "reported_ai_use_frequency": (
            report_meta.get("reported_ai_use_frequency")
        ),
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
        "benchmark_response_count_label": benchmark.get(
            "response_count_label"
        ),
        "benchmark_study_count": benchmark.get("study_count"),
        "benchmark_version": benchmark.get("version"),
        "benchmark_generated_at": benchmark.get("generated_at"),
        "benchmark_hash": benchmark.get("hash"),
        "minimum_cohort_n": benchmark.get("minimum_cohort_n"),
        "percentile_explanation": (
            "Percentiles show where a participant's self-reported assessment "
            "result sits within the relevant HCI participant benchmark "
            "distribution."
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


def build_v2_data_quality(
    report_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Preserve every original QA check, then add V2 contract checks.
    """
    legacy = build_data_quality(report_data)
    warnings = list(legacy.get("warnings") or [])
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
    if not MAIN_EVIDENCE_MIN <= evidence_count <= MAIN_EVIDENCE_MAX:
        errors.append(
            f"Expected {MAIN_EVIDENCE_MIN}–{MAIN_EVIDENCE_MAX} main evidence "
            f"items, got {evidence_count}."
        )

    if len(report_data.get("defining_signals") or []) != 3:
        errors.append("Expected exactly 3 defining signals.")

    unsupported_rarity = [
        item
        for item in report_data.get("rare_combinations") or []
        if item.get("rarity_percent") is not None
        and not item.get("rarity_shareable")
    ]
    if unsupported_rarity:
        warnings.append(
            f"{len(unsupported_rarity)} combination rarity values are retained "
            "for legacy compatibility but are blocked from public display."
        )

    benchmark = (report_data.get("report_meta") or {}).get("benchmark") or {}
    if not benchmark.get("version"):
        warnings.append("Benchmark version metadata is unavailable.")
    if not benchmark.get("hash"):
        warnings.append("Benchmark hash metadata is unavailable.")

    return {
        "ok": not errors and not warnings,
        "errors": errors,
        "warnings": warnings,
        "legacy_checks_ok": legacy.get("ok"),
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
    """
    Build V2 report_data while preserving the original production data flow.

    The original canonical objects are built first and retained under their
    original keys. V2 sections are then derived from those exact objects.
    """
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
    demographics = normalise_demographics_for_benchmark(
        original_demographics,
        benchmark,
    )

    # -----------------------------------------------------------------
    # Original canonical data flow — deliberately preserved.
    # -----------------------------------------------------------------
    dimensions = normalize_dimensions(
        scoring_results,
        demographics,
        benchmark,
    )
    questions = build_questions(
        responses,
        demographics,
        benchmark,
    )
    perception = build_perception_gap(
        scoring_results,
        responses,
        dimensions,
        demographics,
        benchmark,
    )
    rare = build_rare_combinations(
        scoring_results,
        dimensions,
    )
    distinctive = build_distinctive_responses(
        questions,
        7,
    )

    created_at = now_iso()
    assessment_timestamp = (
        scoring_results.get("timestamp")
        or scoring_results.get("created_at")
        or created_at
    )

    report_data: Dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "legacy_schema_version": "hci_report_data_v1",
        "session_id": session_id,
        "email": email,
        "created_at": created_at,
        "assessment_completed_at": assessment_timestamp,
        "demographics": demographics,
        "responses": responses,

        # Original keys and structures preserved.
        "dimensions": dimensions,
        "dashboard": build_dashboard(dimensions, demographics),
        "typicality": build_typicality(dimensions),
        "rare_combinations": rare,
        "questions": questions,
        "distinctive_responses": distinctive,
        "perception_gap": perception,
        "what_to_protect": build_what_to_protect(dimensions),
        "if_nothing_changes": build_if_nothing_changes(
            dimensions,
            demographics,
        ),

        "synthesis_inputs": {
            "most_distinctive_variable": (
                distinctive[0] if distinctive else None
            ),
            "largest_perception_gap": perception.get("largest_gap"),
            "top_rare_combination": rare[0] if rare else None,
            "top_dimensions": sorted(
                dimensions.values(),
                key=lambda d: d["percentile"],
                reverse=True,
            )[:5],
            "lowest_dimensions": sorted(
                dimensions.values(),
                key=lambda d: d["percentile"],
            )[:3],
            "signals": {
                "trends": (
                    SIGNALS.get("trends", {})
                    if isinstance(SIGNALS, dict)
                    else {}
                ),
                "combinations": (
                    SIGNALS.get("combinations", {})
                    if isinstance(SIGNALS, dict)
                    else {}
                ),
                "human_reference": (
                    SIGNALS.get("human_reference", {})
                    if isinstance(SIGNALS, dict)
                    else {}
                ),
            },
        },

        "narrative_blocks": {},
        "human_capital": {},
    }

    # Preserve the original Human Capital input flow.
    report_data["human_capital"] = build_human_capital_inputs(report_data)

    # -----------------------------------------------------------------
    # V2 additive structures — all derived from canonical objects above.
    # -----------------------------------------------------------------
    strongest_combination = select_strongest_combination(rare)
    defining_signals = build_defining_signals(
        dimensions,
        distinctive,
        strongest_combination,
        limit=3,
    )
    evidence = build_main_evidence(
        questions,
        defining_signals,
        limit=MAIN_EVIDENCE_MAX,
    )
    perception_summary = build_perception_summary(perception)
    report_meta = build_report_meta(
        session_id=session_id,
        email=email,
        demographics=demographics,
        benchmark=benchmark,
        assessment_timestamp=assessment_timestamp,
        created_at=created_at,
    )
    position = build_position(dimensions, demographics)
    comparison_shifts = build_comparison_shifts(
        position,
        limit=5,
    )

    report_data.update({
        "report_meta": report_meta,
        "signature": build_signature_skeleton(
            defining_signals,
            strongest_combination,
            evidence,
            perception_summary,
        ),
        "position": position,
        "comparison_shifts": comparison_shifts,
        "comparison_summary": build_comparison_summary(
            position,
            comparison_shifts,
        ),
        "defining_signals": defining_signals,
        "distinctive_pattern": build_distinctive_pattern(
            strongest_combination,
            defining_signals,
            evidence,
        ),
        "evidence": evidence,
        "perception_summary": perception_summary,
        "pattern_synthesis": {
            "organising_feature": None,
            "pattern_narrative": None,
        },
        "human_capital_lens": [],
        "dimension_reference": build_dimension_reference(dimensions),
        "baseline": build_baseline(
            report_meta,
            position,
            defining_signals,
            strongest_combination,
            perception_summary,
            evidence,
        ),
        "appendix_questions": deepcopy(questions),
        "methodology": build_methodology(report_meta),
    })

    report_data["data_quality"] = build_v2_data_quality(report_data)
    assert_report_data_contract(report_data)
    return report_data


def assert_report_data_contract(report_data: Dict[str, Any]) -> None:
    """
    Validate both the preserved legacy flow and the V2 additive contract.
    """
    legacy_required = [
        "session_id",
        "demographics",
        "dimensions",
        "dashboard",
        "typicality",
        "questions",
        "distinctive_responses",
        "perception_gap",
        "what_to_protect",
        "if_nothing_changes",
        "synthesis_inputs",
        "narrative_blocks",
        "human_capital",
    ]
    v2_required = [
        "schema_version",
        "report_meta",
        "signature",
        "position",
        "comparison_shifts",
        "comparison_summary",
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
        "data_quality",
    ]

    missing = [
        key for key in legacy_required + v2_required
        if key not in report_data
    ]
    if missing:
        raise ValueError(
            f"report_data missing required keys: {missing}"
        )

    if report_data.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {REPORT_SCHEMA_VERSION}"
        )

    # Original contract checks preserved.
    if len(report_data["dimensions"]) != 9:
        raise ValueError("report_data must contain 9 dimensions")
    if len(report_data["dashboard"]) != 9:
        raise ValueError("dashboard must contain 9 cards")
    if len(report_data["questions"]) != 39:
        raise ValueError("questions must contain 39 cards")
    if len(report_data["what_to_protect"]) != 4:
        raise ValueError("what_to_protect must contain 4 fixed sections")

    # V2 additive checks.
    if len(report_data["position"]) != 9:
        raise ValueError("position must contain exactly 9 dimension cards")
    if len(report_data["dimension_reference"]) != 9:
        raise ValueError(
            "dimension_reference must contain exactly 9 dimensions"
        )
    if len(report_data["defining_signals"]) != 3:
        raise ValueError(
            "defining_signals must contain exactly 3 items"
        )
    if len(report_data["appendix_questions"]) != 39:
        raise ValueError(
            "appendix_questions must contain exactly 39 questions"
        )

    evidence_count = len(report_data["evidence"])
    if not MAIN_EVIDENCE_MIN <= evidence_count <= MAIN_EVIDENCE_MAX:
        raise ValueError(
            f"evidence must contain {MAIN_EVIDENCE_MIN}–"
            f"{MAIN_EVIDENCE_MAX} items"
        )

    for combo in report_data.get("rare_combinations") or []:
        if combo.get("rarity_shareable"):
            if combo.get("public_rarity_percent") is None:
                raise ValueError(
                    "Shareable rarity requires public_rarity_percent"
                )
            if combo.get("rarity_source") not in {
                "calculated",
                "approved_research_estimate",
            }:
                raise ValueError(
                    "Shareable rarity requires an approved source"
                )
