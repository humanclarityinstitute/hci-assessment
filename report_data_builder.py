"""
report_data_builder.py
Clean HCI report data contract. Builds ONE canonical report_data object.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

try:
    from scoring_engine import DIMENSION_VARIABLES, PERCEPTION_QUESTIONS
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
    PERCEPTION_QUESTIONS = {}
try:
    from question_metadata import QUESTION_MAP, REVERSE_SCORED_KEYS, get_question_text
except Exception:
    QUESTION_MAP, REVERSE_SCORED_KEYS = {}, set()
    def get_question_text(key): return key
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

DIMENSION_ORDER = [
    "reliance", "trust", "verification", "decision_delegation", "human_agency",
    "disclosure", "emotional_regulation", "thought_partnership", "social_transparency"
]
DIMENSION_LABELS = {
    "reliance": "Reliance", "trust": "Trust", "verification": "Verification",
    "decision_delegation": "Decision Delegation", "human_agency": "Human Agency",
    "emotional_regulation": "Emotional Regulation", "disclosure": "Disclosure",
    "thought_partnership": "Thought Partnership", "social_transparency": "Social Transparency",
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
    "perceived_usage": ("Compared to most people, how much do you use AI?", "reliance", "thought_partnership"),
    "perceived_reliance": ("Compared to most people, how much do you rely on AI?", "reliance", None),
    "perceived_dependence": ("Compared to most people, how dependent on AI are you?", "reliance", "decision_delegation"),
}
PROTECT_DIMENSIONS = ["verification", "human_agency", "emotional_regulation", "thought_partnership"]

def now_iso(): return datetime.now(timezone.utc).isoformat()
def clean_int(v, default=None):
    try:
        if v is None or v == "": return default
        return int(round(float(v)))
    except Exception: return default
def clean_float(v, default=None):
    try:
        if v is None or v == "": return default
        return float(v)
    except Exception: return default
def ordinal(n):
    n = clean_int(n, 0) or 0
    suffix = "th" if 10 <= n % 100 <= 20 else {1:"st",2:"nd",3:"rd"}.get(n%10,"th")
    return f"{n}{suffix}"
def position_phrase(p):
    p = clean_int(p, 50) or 50
    if p >= 96: return "exceptionally high"
    if p >= 86: return "notably high"
    if p >= 71: return "above population centre"
    if p >= 41: return "near population centre"
    if p >= 26: return "below population centre"
    if p >= 11: return "notably low"
    return "exceptionally low"
def protect_position_phrase(p):
    p = clean_int(p, 50) or 50
    return "at the high end" if p >= 71 else "in the middle" if p >= 41 else "at the low end"
def get_benchmark_instance():
    try: return get_benchmark() if callable(get_benchmark) else None
    except Exception: return None

def signal_for_dimension(dim, percentile):
    dims = SIGNALS.get("dimensions", {}) if isinstance(SIGNALS, dict) else {}
    sig = dims.get(dim) or dims.get(DIMENSION_LABELS.get(dim, dim)) or {}
    if not isinstance(sig, dict): return str(sig or "")
    p = clean_int(percentile, 50) or 50
    return str((sig.get("high") if p >= 50 else sig.get("low")) or sig.get("series") or sig.get("definition") or "")

def hrl_context(dim):
    if HRL is None: return {}
    out = {}
    for attr in ["HBE_FRAMEWORK", "VALUES_SIGNALS", "HUMAN_REFERENCE_LAYER"]:
        src = getattr(HRL, attr, None)
        if isinstance(src, dict):
            item = src.get(dim) or src.get(DIMENSION_LABELS.get(dim, dim))
            if item: out[attr.lower()] = item
    return out

def safe_question_percentile(benchmark, key, answer, segment=None):
    if answer is None: return None
    if benchmark is not None and hasattr(benchmark, "get_percentile"):
        try: return clean_int(benchmark.get_percentile(key, answer, segment=segment))
        except TypeError:
            try: return clean_int(benchmark.get_percentile(key, answer))
            except Exception: pass
        except Exception: pass
    return 50

def normalize_distribution(raw):
    """Return 7 percentage values for response options 1..7."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        for k in ["percentages", "distribution", "counts", "values"]:
            if k in raw:
                return normalize_distribution(raw[k])
        raw = [raw.get(str(i), raw.get(i, 0)) for i in range(1, 8)]
    if not isinstance(raw, list) or not raw:
        return None
    nums = [clean_float(x, 0) or 0 for x in raw]
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

def safe_question_distribution(benchmark, key, segment=None):
    """Read question response distributions from benchmark.data['variables']."""
    if benchmark is None:
        return None

    data = getattr(benchmark, "data", None)
    if isinstance(data, dict):
        var_data = (data.get("variables") or {}).get(key)
        if isinstance(var_data, dict):
            source = None
            if segment and isinstance(segment, tuple) and len(segment) == 2:
                segment_type, segment_value = segment
                segment_key = f"by_{segment_type}"
                source = (var_data.get(segment_key) or {}).get(segment_value)
            if source is None:
                source = var_data.get("overall")
            dist = normalize_distribution(source)
            if dist:
                return dist

    return None

def normalize_dimensions(scoring_results, demographics):
    src = scoring_results.get("dimension_scores") or scoring_results.get("dimensions") or {}
    dims = {}
    for dim in DIMENSION_ORDER:
        raw = src.get(dim, {}) if isinstance(src, dict) else {}
        p = clean_int(raw.get("percentile_overall"), 50)
        dims[dim] = {
            "key": dim, "label": DIMENSION_LABELS[dim], "definition": DIMENSION_DEFINITIONS[dim],
            "raw_score": clean_float(raw.get("raw_score")),
            "percentile": p, "percentile_overall": p,
            "percentile_age_group": clean_int(raw.get("percentile_age_group")),
            "percentile_frequency": clean_int(raw.get("percentile_frequency")),
            "n_overall": clean_int(raw.get("n_overall")), "n_age_group": clean_int(raw.get("n_age_group")), "n_frequency": clean_int(raw.get("n_frequency")),
            "position": position_phrase(p), "protect_position": protect_position_phrase(p),
            "research_insight": signal_for_dimension(dim, p), "hrl_context": hrl_context(dim),
        }
    return dims

def build_dashboard(dimensions, demographics):
    usage = demographics.get("ai_tool_use_frequency") or demographics.get("frequency") or "Your usage group"
    age = demographics.get("age_group") or "your age group"
    cards = []
    for dim in DIMENSION_ORDER:
        d = dimensions[dim]
        cards.append({
            "key": dim, "label": d["label"], "definition": d["definition"], "percentile": d["percentile"],
            "percentile_label": ordinal(d["percentile"]), "plain_score": f"Higher than {d['percentile']} of 100 people",
            "comparisons": [
                {"label": f"{usage} users", "percentile": d.get("percentile_frequency"), "percentile_label": ordinal(d.get("percentile_frequency")) if d.get("percentile_frequency") is not None else "N/A", "n": d.get("n_frequency")},
                {"label": f"Your age group ({age})", "percentile": d.get("percentile_age_group"), "percentile_label": ordinal(d.get("percentile_age_group")) if d.get("percentile_age_group") is not None else "N/A", "n": d.get("n_age_group")},
            ],
            "research_insight": d["research_insight"],
        })
    return cards

def build_typicality(dimensions):
    items=[]
    for dim in DIMENSION_ORDER:
        d=dimensions[dim]; p=d["percentile"]
        bucket = "distinctive" if p > 75 or p < 25 else "typical" if 35 <= p <= 65 else "moderate"
        items.append({"dimension":dim,"label":d["label"],"percentile":p,"position":position_phrase(p),"bucket":bucket,"distance_from_centre":abs(p-50),"interpretation":d.get("research_insight","")})
    return {"distinctive": sorted([x for x in items if x["bucket"]=="distinctive"], key=lambda x:x["distance_from_centre"], reverse=True), "typical":[x for x in items if x["bucket"]=="typical"], "moderate":[x for x in items if x["bucket"]=="moderate"], "all": items}

def build_questions(responses, demographics):
    bench=get_benchmark_instance(); age=demographics.get("age_group"); usage=demographics.get("ai_tool_use_frequency") or demographics.get("frequency")
    qs=[]
    reverse_set = set(REVERSE_SCORED_KEYS or [])
    for dim in DIMENSION_ORDER:
        for key in DIMENSION_VARIABLES.get(dim, []):
            ans=responses.get(key)
            pct=safe_question_percentile(bench,key,ans)
            pct_age=safe_question_percentile(bench,key,ans,segment=("age_group", age)) if age else None
            pct_freq=safe_question_percentile(bench,key,ans,segment=("frequency", usage)) if usage else None
            try:
                text = get_question_text(key)
            except Exception:
                text = (QUESTION_MAP.get(key, {}) or {}).get("text", key) if isinstance(QUESTION_MAP, dict) else key
            qs.append({"key":key,"dimension":dim,"dimension_label":DIMENSION_LABELS[dim],"question_text":text,"answer":clean_int(ans),"answer_display":f"{ans}/7" if ans is not None else "N/A","percentile":pct,"percentile_label":ordinal(pct) if pct is not None else "N/A","percentile_age_group":pct_age,"percentile_frequency":pct_freq,"distribution_everyone":safe_question_distribution(bench,key),"distribution_age_group":safe_question_distribution(bench,key,segment=("age_group", age)) if age else None,"comparison_statement":f"You answered {ans}/7 — higher than {pct} of 100 people overall" + (f", and higher than {pct_age} of 100 people your age." if pct_age is not None else "."),"is_reverse_scored":key in reverse_set})
    return qs

def build_distinctive_responses(questions, limit=7):
    c=[]
    for q in questions:
        if q.get("percentile") is not None:
            item=deepcopy(q); item["distance_from_centre"]=abs((clean_int(item["percentile"],50) or 50)-50); c.append(item)
    return sorted(c, key=lambda x:(x["distance_from_centre"], x.get("percentile") or 0), reverse=True)[:limit]

def build_perception_gap(scoring_results, responses, dimensions):
    gaps=scoring_results.get("perception_gaps") or []
    rows=[]
    for key,(question,primary,secondary) in SELF_PERCEPTION_MAP.items():
        rows.append({"key":key,"question":question,"answer":responses.get(key),"primary_dimension":primary,"primary_dimension_label":DIMENSION_LABELS[primary],"actual_percentile":dimensions[primary]["percentile"],"actual_position":position_phrase(dimensions[primary]["percentile"]),"secondary_dimension":secondary,"secondary_percentile":dimensions.get(secondary,{}).get("percentile") if secondary else None})
    return {"self_perception": rows, "gaps": gaps, "largest_gap": gaps[0] if gaps else None, "has_significant_gap": bool(gaps)}

def combo_signal(d1,d2):
    combos=SIGNALS.get("combinations", {}) if isinstance(SIGNALS, dict) else {}
    for key in [f"{d1}+{d2}", f"{d2}+{d1}", f"{d1}_{d2}", f"{d2}_{d1}"]:
        val=combos.get(key)
        if isinstance(val, str): return val
        if isinstance(val, dict): return str(val.get("insight") or val.get("series") or val.get("text") or "")
    return ""

def build_rare_combinations(scoring_results, dimensions):
    out=[]
    for item in (scoring_results.get("rare_combinations") or [])[:2]:
        combo=item.get("combo") or [None,None]
        d1=item.get("dimension_1") or combo[0]; d2=item.get("dimension_2") or combo[1]
        if not d1 or not d2: continue
        out.append({"dimension_1":d1,"dimension_2":d2,"label_1":DIMENSION_LABELS.get(d1,d1),"label_2":DIMENSION_LABELS.get(d2,d2),"percentile_1":clean_int(item.get("percentile_dim1") or (item.get("percentiles") or [None,None])[0] or dimensions.get(d1,{}).get("percentile")),"percentile_2":clean_int(item.get("percentile_dim2") or (item.get("percentiles") or [None,None])[1] or dimensions.get(d2,{}).get("percentile")),"rarity_percent":clean_float(item.get("rarity_percent") or item.get("frequency_pct") or 5),"description":item.get("description") or f"{DIMENSION_LABELS.get(d1,d1)} + {DIMENSION_LABELS.get(d2,d2)}","research_signal":combo_signal(d1,d2)})
    return out

def build_what_to_protect(dimensions):
    return [{"dimension":dim,"label":DIMENSION_LABELS[dim],"definition":DIMENSION_DEFINITIONS[dim],"percentile":dimensions[dim]["percentile"],"positioning":protect_position_phrase(dimensions[dim]["percentile"]),"research_insight":dimensions[dim].get("research_insight",""),"hrl_context":dimensions[dim].get("hrl_context",{})} for dim in PROTECT_DIMENSIONS]

def build_if_nothing_changes(dimensions, demographics):
    ranked=sorted(dimensions.values(), key=lambda d:d["percentile"], reverse=True)
    strengths=[d for d in ranked if d["percentile"]>71][:3]
    monitor=[dimensions[d] for d in ["verification","reliance","human_agency"] if d in dimensions]
    return {"usage_frequency":demographics.get("ai_tool_use_frequency") or demographics.get("frequency"),"strengths_likely_to_deepen":strengths,"areas_worth_monitoring":monitor[:3],"highest_dimension":ranked[0] if ranked else None,"monitoring_anchor":monitor[0] if monitor else None}

def build_data_quality(report_data):
    warnings=[]
    if len(report_data.get("dimensions",{})) != 9: warnings.append("Expected 9 dimensions.")
    if len(report_data.get("dashboard",[])) != 9: warnings.append("Expected 9 dashboard cards.")
    if len(report_data.get("questions",[])) != 39: warnings.append(f"Expected 39 question cards, got {len(report_data.get('questions',[]))}.")
    missing=[q["key"] for q in report_data.get("questions",[]) if not q.get("distribution_everyone")]
    if missing: warnings.append(f"{len(missing)} question distributions missing; renderer will show fallback.")
    if sum(1 for q in report_data.get("questions",[]) if q.get("percentile")==50) > 25: warnings.append("Many question percentiles are 50; benchmark question-level lookup may be unavailable or mis-keyed.")
    return {"ok": not warnings, "warnings": warnings, "generated_at": now_iso()}

def build_report_data(scoring_results: Dict[str,Any], responses: Optional[Dict[str,Any]]=None, demographics: Optional[Dict[str,Any]]=None, email: Optional[str]=None, session_id: Optional[str]=None) -> Dict[str,Any]:
    if not isinstance(scoring_results, dict): raise ValueError("scoring_results must be a dict")
    responses = responses or scoring_results.get("responses") or {}
    demographics = demographics or scoring_results.get("demographics") or {}
    session_id = session_id or scoring_results.get("session_id") or str(uuid.uuid4())
    dimensions=normalize_dimensions(scoring_results, demographics)
    questions=build_questions(responses, demographics)
    perception=build_perception_gap(scoring_results, responses, dimensions)
    rare=build_rare_combinations(scoring_results, dimensions)
    distinctive=build_distinctive_responses(questions, 7)
    report_data={"schema_version":"hci_report_data_v1","session_id":session_id,"email":email,"created_at":now_iso(),"demographics":demographics,"responses":responses,"dimensions":dimensions,"dashboard":build_dashboard(dimensions, demographics),"typicality":build_typicality(dimensions),"rare_combinations":rare,"questions":questions,"distinctive_responses":distinctive,"perception_gap":perception,"what_to_protect":build_what_to_protect(dimensions),"if_nothing_changes":build_if_nothing_changes(dimensions, demographics),"synthesis_inputs":{"most_distinctive_variable":distinctive[0] if distinctive else None,"largest_perception_gap":perception.get("largest_gap"),"top_rare_combination":rare[0] if rare else None,"top_dimensions":sorted(dimensions.values(), key=lambda d:d["percentile"], reverse=True)[:5],"lowest_dimensions":sorted(dimensions.values(), key=lambda d:d["percentile"])[:3],"signals":{"trends":SIGNALS.get("trends",{}) if isinstance(SIGNALS,dict) else {},"combinations":SIGNALS.get("combinations",{}) if isinstance(SIGNALS,dict) else {},"human_reference":SIGNALS.get("human_reference",{}) if isinstance(SIGNALS,dict) else {}}},"narrative_blocks":{}}
    report_data["data_quality"]=build_data_quality(report_data)
    return report_data

def assert_report_data_contract(report_data: Dict[str,Any]) -> None:
    required=["session_id","demographics","dimensions","dashboard","typicality","questions","distinctive_responses","perception_gap","what_to_protect","if_nothing_changes"]
    missing=[k for k in required if k not in report_data]
    if missing: raise ValueError(f"report_data missing required keys: {missing}")
    if len(report_data["dimensions"]) != 9: raise ValueError("report_data must contain 9 dimensions")
    if len(report_data["dashboard"]) != 9: raise ValueError("dashboard must contain 9 cards")
    if len(report_data["questions"]) != 39: raise ValueError("questions must contain 39 cards")
    if len(report_data["what_to_protect"]) != 4: raise ValueError("what_to_protect must contain 4 fixed sections")
