"""
report_data_builder.py

Clean HCI report data contract.

This is the single source-of-truth builder for premium report_data.

Core guarantees:
- Builds 9 dimension cards.
- Builds 39 question cards.
- Uses full question text from question_metadata.py.
- Recalculates missing dimension age/frequency percentiles from benchmark data.
- Normalises demographic values to benchmark cohort keys.
- Does NOT silently duplicate overall distributions as age-group distributions.
- Stores data_quality warnings so missing cohort data is visible during testing.
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
    "reliance": "How much you depend on AI for thinking and functioning",
    "trust": "How much you believe AI outputs are accurate",
    "verification": "How often you check AI outputs before using them",
    "decision_delegation": "How much you hand over decisions to AI",
    "human_agency": "How much control you maintain over your decisions",
    "emotional_regulation": "Whether you turn to AI for emotional support",
    "disclosure": "How much personal information you share with AI",
    "thought_partnership": "How much you use AI as a thinking partner",
    "social_transparency": "How openly you discuss your AI use with others",
}

SELF_PERCEPTION_MAP = {
    "perceived_usage": {
        "question": "Compared to most people, how much do you use AI?",
        "primary_dimension": "reliance",
        "secondary_dimension": "thought_partnership",
    },
    "perceived_reliance": {
        "question": "Compared to most people, how much do you rely on AI?",
        "primary_dimension": "reliance",
        "secondary_dimension": None,
    },
    "perceived_dependence": {
        "question": "Compared to most people, how dependent on AI are you?",
        "primary_dimension": "reliance",
        "secondary_dimension": "decision_delegation",
    },
}

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
        return "above population centre"
    if p >= 41:
        return "near population centre"
    if p >= 26:
        return "below population centre"
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
            "everyday": "everyday", "every day": "everyday", "daily": "everyday",
            "often": "often", "veryoften": "often", "very often": "often",
            "sometimes": "sometimes", "occasionally": "sometimes", "occasional": "sometimes",
            "rarely": "rarely", "rare": "rarely",
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

def signal_for_dimension(dim: str, percentile: Any) -> str:
    dims = SIGNALS.get("dimensions", {}) if isinstance(SIGNALS, dict) else {}
    signal = dims.get(dim) or dims.get(DIMENSION_LABELS.get(dim, dim)) or {}
    if not isinstance(signal, dict):
        return str(signal or "")

    p = clean_int(percentile, 50) or 50
    text = (signal.get("high") if p >= 50 else signal.get("low")) or signal.get("series") or signal.get("definition")
    return str(text or "")


def hrl_context(dim: str) -> Dict[str, Any]:
    if HRL is None:
        return {}

    out: Dict[str, Any] = {}
    for attr in ["HBE_FRAMEWORK", "VALUES_SIGNALS", "HUMAN_REFERENCE_LAYER", "REFRAME_LIBRARY", "RESEARCH_INSIGHTS"]:
        source = getattr(HRL, attr, None)
        if isinstance(source, dict):
            item = source.get(dim) or source.get(DIMENSION_LABELS.get(dim, dim))
            if item is not None:
                out[attr.lower()] = item
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
        return calculate_percentile_from_values(answer, source.get("values") or [])

    # Overall percentile.
    if isinstance(source, dict):
        pct = calculate_percentile_from_values(answer, source.get("values") or [])
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
            "definition": DIMENSION_DEFINITIONS[dim],
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
            "hrl_context": hrl_context(dim),
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
            "plain_score": f"Higher than {d['percentile']} of 100 people",
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
                "comparison_statement": build_question_comparison_statement(answer, pct, pct_age),
                "is_reverse_scored": key in reverse_set,
            })

    return questions


def build_question_comparison_statement(answer: Any, pct: Optional[int], pct_age: Optional[int]) -> str:
    if answer is None:
        return "No answer was recorded for this item."

    if pct is None and pct_age is None:
        return f"You answered {answer}/7. Benchmark comparison is unavailable for this item."

    if pct is not None and pct_age is not None:
        return f"You answered {answer}/7 — higher than {pct} of 100 people overall, and higher than {pct_age} of 100 people your age."

    if pct is not None:
        return f"You answered {answer}/7 — higher than {pct} of 100 people overall. Age-group comparison is unavailable."

    return f"You answered {answer}/7. Overall comparison is unavailable, but your age-group percentile is {pct_age}."


def build_distinctive_responses(questions: List[Dict[str, Any]], limit: int = 7) -> List[Dict[str, Any]]:
    candidates = []
    for q in questions:
        pct = q.get("percentile")
        if pct is not None:
            item = deepcopy(q)
            item["distance_from_centre"] = abs((clean_int(pct, 50) or 50) - 50)
            candidates.append(item)

    return sorted(candidates, key=lambda x: (x["distance_from_centre"], x.get("percentile") or 0), reverse=True)[:limit]


def build_perception_gap(scoring_results: Dict[str, Any], responses: Dict[str, Any], dimensions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    gaps = scoring_results.get("perception_gaps") or []
    rows = []

    for key, meta in SELF_PERCEPTION_MAP.items():
        # Prefer metadata file text if present.
        question = meta["question"]
        if isinstance(PERCEPTION_QUESTIONS, dict) and isinstance(PERCEPTION_QUESTIONS.get(key), dict):
            question = PERCEPTION_QUESTIONS[key].get("text") or question

        primary = meta["primary_dimension"]
        secondary = meta.get("secondary_dimension")

        rows.append({
            "key": key,
            "question": question,
            "answer": responses.get(key),
            "primary_dimension": primary,
            "primary_dimension_label": DIMENSION_LABELS[primary],
            "actual_percentile": dimensions[primary]["percentile"],
            "actual_position": position_phrase(dimensions[primary]["percentile"]),
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


def build_rare_combinations(scoring_results: Dict[str, Any], dimensions: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    raw_combos = scoring_results.get("rare_combinations") or scoring_results.get("patterns", {}).get("rare_combinations", []) or []

    for item in raw_combos[:2]:
        combo = item.get("combo") or [None, None]
        d1 = item.get("dimension_1") or combo[0]
        d2 = item.get("dimension_2") or combo[1]

        if not d1 or not d2:
            continue

        out.append({
            "dimension_1": d1,
            "dimension_2": d2,
            "label_1": DIMENSION_LABELS.get(d1, d1),
            "label_2": DIMENSION_LABELS.get(d2, d2),
            "percentile_1": clean_int(item.get("percentile_dim1") or (item.get("percentiles") or [None, None])[0] or dimensions.get(d1, {}).get("percentile")),
            "percentile_2": clean_int(item.get("percentile_dim2") or (item.get("percentiles") or [None, None])[1] or dimensions.get(d2, {}).get("percentile")),
            "rarity_percent": clean_float(item.get("rarity_percent") or item.get("frequency_pct") or 5),
            "description": item.get("description") or f"{DIMENSION_LABELS.get(d1, d1)} + {DIMENSION_LABELS.get(d2, d2)}",
            "combo_classification": item.get("combo_classification") or item.get("classification") or ("true_rare" if clean_float(item.get("rarity_percent") or item.get("frequency_pct") or 5) <= 5 else "notable"),
            "combination_id": item.get("combination_id"),
            "signal_type": item.get("signal_type"),
            "band_dim1": item.get("band_dim1"),
            "band_dim2": item.get("band_dim2"),
            "research_signal": combo_signal(d1, d2, item),
        })

    return out


def build_what_to_protect(dimensions: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "dimension": dim,
            "label": DIMENSION_LABELS[dim],
            "definition": DIMENSION_DEFINITIONS[dim],
            "percentile": dimensions[dim]["percentile"],
            "positioning": protect_position_phrase(dimensions[dim]["percentile"]),
            "research_insight": dimensions[dim].get("research_insight", ""),
            "hrl_context": dimensions[dim].get("hrl_context", {}),
        }
        for dim in PROTECT_DIMENSIONS
    ]


def build_if_nothing_changes(dimensions: Dict[str, Dict[str, Any]], demographics: Dict[str, Any]) -> Dict[str, Any]:
    ranked = sorted(dimensions.values(), key=lambda d: d["percentile"], reverse=True)
    strengths = [d for d in ranked if d["percentile"] > 71][:3]
    monitor = [dimensions[d] for d in ["verification", "reliance", "human_agency"] if d in dimensions]

    return {
        "usage_frequency": demographics.get("_frequency_benchmark") or demographics.get("ai_tool_use_frequency") or demographics.get("frequency"),
        "strengths_likely_to_deepen": strengths,
        "areas_worth_monitoring": monitor[:3],
        "highest_dimension": ranked[0] if ranked else None,
        "monitoring_anchor": monitor[0] if monitor else None,
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
    missing_age_dist = [q["key"] for q in report_data.get("questions", []) if not q.get("distribution_age_group")]

    if missing_overall_dist:
        warnings.append(f"{len(missing_overall_dist)} overall question distributions missing.")
    if missing_age_dist:
        warnings.append(f"{len(missing_age_dist)} age-group question distributions missing or below threshold.")

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
# Public builder
# ---------------------------------------------------------------------

def build_report_data(
    scoring_results: Dict[str, Any],
    responses: Optional[Dict[str, Any]] = None,
    demographics: Optional[Dict[str, Any]] = None,
    email: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not isinstance(scoring_results, dict):
        raise ValueError("scoring_results must be a dict")

    responses = responses or scoring_results.get("responses") or {}
    original_demographics = demographics or scoring_results.get("demographics") or {}
    session_id = session_id or scoring_results.get("session_id") or str(uuid.uuid4())

    benchmark = get_benchmark_instance()
    demographics = normalise_demographics_for_benchmark(original_demographics, benchmark)

    dimensions = normalize_dimensions(scoring_results, demographics, benchmark)
    questions = build_questions(responses, demographics, benchmark)
    perception = build_perception_gap(scoring_results, responses, dimensions)
    rare = build_rare_combinations(scoring_results, dimensions)
    distinctive = build_distinctive_responses(questions, 7)

    report_data = {
        "schema_version": "hci_report_data_v1",
        "session_id": session_id,
        "email": email,
        "created_at": now_iso(),
        "demographics": demographics,
        "responses": responses,

        "dimensions": dimensions,
        "dashboard": build_dashboard(dimensions, demographics),
        "typicality": build_typicality(dimensions),
        "rare_combinations": rare,
        "questions": questions,
        "distinctive_responses": distinctive,
        "perception_gap": perception,
        "what_to_protect": build_what_to_protect(dimensions),
        "if_nothing_changes": build_if_nothing_changes(dimensions, demographics),

        "synthesis_inputs": {
            "most_distinctive_variable": distinctive[0] if distinctive else None,
            "largest_perception_gap": perception.get("largest_gap"),
            "top_rare_combination": rare[0] if rare else None,
            "top_dimensions": sorted(dimensions.values(), key=lambda d: d["percentile"], reverse=True)[:5],
            "lowest_dimensions": sorted(dimensions.values(), key=lambda d: d["percentile"])[:3],
            "signals": {
                "trends": SIGNALS.get("trends", {}) if isinstance(SIGNALS, dict) else {},
                "combinations": SIGNALS.get("combinations", {}) if isinstance(SIGNALS, dict) else {},
                "human_reference": SIGNALS.get("human_reference", {}) if isinstance(SIGNALS, dict) else {},
            },
        },

        "narrative_blocks": {},
    }

    report_data["data_quality"] = build_data_quality(report_data)
    return report_data


def assert_report_data_contract(report_data: Dict[str, Any]) -> None:
    required = [
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
    ]
    missing = [k for k in required if k not in report_data]
    if missing:
        raise ValueError(f"report_data missing required keys: {missing}")

    if len(report_data["dimensions"]) != 9:
        raise ValueError("report_data must contain 9 dimensions")
    if len(report_data["dashboard"]) != 9:
        raise ValueError("dashboard must contain 9 cards")
    if len(report_data["questions"]) != 39:
        raise ValueError("questions must contain 39 cards")
    if len(report_data["what_to_protect"]) != 4:
        raise ValueError("what_to_protect must contain 4 fixed sections")
