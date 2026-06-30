"""
claude_narrative.py

Three-call Claude narrative layer for the clean HCI report system.

Purpose
-------
Takes canonical report_data and fills:

report_data["narrative_blocks"] = {
    "opening_findings": "...",
    "rare_combinations_narrative": "...",
    "behaviour_story": "...",
    "perception_gap_narrative": "...",
    "distinctive_responses_narrative": "...",
    "likely_to_continue": "...",
    "overall_outlook": "..."
}

Design
------
- Claude writes narrative only.
- Claude does NOT decide report structure.
- Dashboard, question cards, What To Protect, and Next Steps stay deterministic.
- Each call receives HCI Signals + Human Reference Layer context.
- If a Claude call fails, deterministic fallbacks still render.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List
import json
import os
import urllib.request
import traceback


try:
    from hci_signals_library import SIGNALS
except Exception:
    SIGNALS = {"dimensions": {}, "trends": {}, "combinations": {}, "human_reference": {}}

try:
    import human_reference_layer as HRL
except Exception:
    HRL = None


CLAUDE_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------

def add_claude_narratives(report_data: Dict[str, Any], api_key: str | None = None) -> Dict[str, Any]:
    """
    Add HCI-grounded Claude narrative blocks to report_data.

    Safe behaviour:
    - Returns original report_data with existing deterministic fallback if no key.
    - Never mutates structure outside report_data["narrative_blocks"].
    - Does not fail the report if Claude fails.
    """
    report_data = deepcopy(report_data)
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        print("[CLAUDE] No ANTHROPIC_API_KEY. Rendering deterministic fallback narratives.")
        report_data.setdefault("narrative_blocks", {})
        report_data.setdefault("narrative_generation", {})
        report_data["narrative_generation"]["status"] = "skipped_no_api_key"
        return report_data

    report_data.setdefault("narrative_blocks", {})
    status = {
        "status": "started",
        "calls": {},
    }

    # Call 1: profile narrative
    try:
        profile_blocks = generate_profile_narrative(report_data, api_key)
        report_data["narrative_blocks"].update(profile_blocks)
        status["calls"]["profile_narrative"] = "success"
    except Exception as e:
        print(f"[CLAUDE] profile_narrative failed: {e}")
        traceback.print_exc()
        status["calls"]["profile_narrative"] = f"failed: {str(e)}"

    # Call 2: top 7 distinctive responses
    try:
        response_blocks = generate_distinctive_responses_narrative(report_data, api_key)
        report_data["narrative_blocks"].update(response_blocks)
        status["calls"]["distinctive_responses"] = "success"
    except Exception as e:
        print(f"[CLAUDE] distinctive_responses failed: {e}")
        traceback.print_exc()
        status["calls"]["distinctive_responses"] = f"failed: {str(e)}"

    # Call 3: trajectory / if nothing changes
    try:
        trajectory_blocks = generate_trajectory_narrative(report_data, api_key)
        report_data["narrative_blocks"].update(trajectory_blocks)
        status["calls"]["trajectory"] = "success"
    except Exception as e:
        print(f"[CLAUDE] trajectory failed: {e}")
        traceback.print_exc()
        status["calls"]["trajectory"] = f"failed: {str(e)}"

    status["status"] = "complete"
    report_data["narrative_generation"] = status
    return report_data


# ---------------------------------------------------------------------
# Claude calls
# ---------------------------------------------------------------------

def generate_profile_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    """
    Call 1:
    - opening_findings
    - rare_combinations_narrative
    - behaviour_story
    - perception_gap_narrative
    """
    brief = build_profile_brief(report_data)
    hci_context = build_hci_context(report_data)

    prompt = f"""
You are writing HCI premium report narrative blocks.

You are NOT creating report structure. The structure already exists.
You are filling exactly four narrative blocks.

Use the HCI Signals and Human Reference Layer below as grounding.
Write in the Human Clarity Institute voice:
- observational
- research-grounded
- plain English
- direct to "you"
- not clinical
- not self-help
- not alarming
- not prescriptive
- no diagnosis
- no exaggerated claims
- no unsupported predictions

Avoid bare percentile jargon. You may mention positioning sparingly when useful.
Use "HCI's research" or "the data shows" lightly where appropriate.

HCI CONTEXT:
{json.dumps(hci_context, ensure_ascii=False, indent=2)}

USER REPORT BRIEF:
{json.dumps(brief, ensure_ascii=False, indent=2)}

Return VALID JSON ONLY with these exact keys:
{{
  "opening_findings": "Three paragraphs, 50-75 words each. Finding 1: most distinctive response. Finding 2: perception gap or alignment. Finding 3: rare combination or coherent/no-combo fallback.",
  "rare_combinations_narrative": "If rare combinations exist, explain top 1-2 combinations in 350-500 words total. If none exist, write 120-180 words explaining that no rare combination means the pattern is less defined by tension and more by overall score distribution.",
  "behaviour_story": "300-400 word flowing narrative portrait. Anchor in the highest dimension. Explain cross-dimensional relationships. Ground in HCI observed patterns. No prescriptions.",
  "perception_gap_narrative": "250-300 words comparing self-perception to benchmark positioning. If no significant gaps, explain alignment as meaningful. Illuminating, not corrective."
}}
"""
    return call_claude_json(api_key, prompt, expected_keys=[
        "opening_findings",
        "rare_combinations_narrative",
        "behaviour_story",
        "perception_gap_narrative",
    ])


def generate_distinctive_responses_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    """
    Call 2:
    - distinctive_responses_narrative
    """
    brief = build_distinctive_responses_brief(report_data)
    hci_context = build_hci_context(report_data)

    prompt = f"""
You are writing the HCI report section "Your Most Distinctive Responses".

Write response-by-response explanations for the top 7 individual answers.
Do not collapse them into one general essay.

Use the HCI Signals and Human Reference Layer below as grounding.
For each response:
1. State what is distinctive.
2. Explain why it matters in HCI behavioural terms.
3. Connect it to the person's wider pattern when useful.
4. Keep it observational and research-grounded.

Tone:
- curious
- precise
- plain English
- direct to "you"
- not clinical
- not diagnostic
- not alarmist
- not prescriptive

HCI CONTEXT:
{json.dumps(hci_context, ensure_ascii=False, indent=2)}

TOP 7 RESPONSE BRIEF:
{json.dumps(brief, ensure_ascii=False, indent=2)}

Return VALID JSON ONLY:
{{
  "distinctive_responses_narrative": "Intro paragraph plus 7 clearly separated response explanations. 40-70 words per response. Use markdown-style bold response labels if helpful."
}}
"""
    return call_claude_json(api_key, prompt, expected_keys=[
        "distinctive_responses_narrative",
    ])


def generate_trajectory_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    """
    Call 3:
    - likely_to_continue
    - overall_outlook
    """
    brief = build_trajectory_brief(report_data)
    hci_context = build_hci_context(report_data)

    prompt = f"""
You are writing HCI report Section 10: "If Nothing Changes".

This is NOT prediction, advice, urgency, or self-help.
It is an observational synthesis based on patterns that tend to hold or shift when usage stays similar.

Use the HCI Signals and Human Reference Layer as grounding.
Do not make timeline predictions.
Do not say "you should".
Do not make claims that are not supported by the provided data/context.

Tone:
- grounded
- reassuring
- observational
- direct to "you"
- research-aware
- autonomy-preserving

HCI CONTEXT:
{json.dumps(hci_context, ensure_ascii=False, indent=2)}

TRAJECTORY BRIEF:
{json.dumps(brief, ensure_ascii=False, indent=2)}

Return VALID JSON ONLY:
{{
  "likely_to_continue": "100-160 words. What pattern is most likely to remain stable if usage and behaviour stay similar.",
  "overall_outlook": "90-140 words. Coherent closing: main strength, main monitoring area, and autonomy-preserving ending."
}}
"""
    return call_claude_json(api_key, prompt, expected_keys=[
        "likely_to_continue",
        "overall_outlook",
    ])


# ---------------------------------------------------------------------
# Brief builders
# ---------------------------------------------------------------------

def build_profile_brief(report_data: Dict[str, Any]) -> Dict[str, Any]:
    dimensions = list((report_data.get("dimensions") or {}).values())
    ranked_high = sorted(dimensions, key=lambda d: d.get("percentile", 50), reverse=True)
    ranked_low = sorted(dimensions, key=lambda d: d.get("percentile", 50))

    perception = report_data.get("perception_gap") or {}

    return {
        "demographics": report_data.get("demographics", {}),
        "highest_dimensions": slim_dimensions(ranked_high[:5]),
        "lowest_dimensions": slim_dimensions(ranked_low[:3]),
        "most_distinctive_variable": slim_question(
            (report_data.get("synthesis_inputs") or {}).get("most_distinctive_variable")
        ),
        "rare_combinations": report_data.get("rare_combinations", [])[:2],
        "perception_gap": {
            "self_perception": perception.get("self_perception", []),
            "gaps": perception.get("gaps", []),
            "has_significant_gap": perception.get("has_significant_gap", False),
            "largest_gap": perception.get("largest_gap"),
        },
        "typicality": report_data.get("typicality", {}),
    }


def build_distinctive_responses_brief(report_data: Dict[str, Any]) -> Dict[str, Any]:
    responses = report_data.get("distinctive_responses") or []
    dimensions = report_data.get("dimensions") or {}

    return {
        "demographics": report_data.get("demographics", {}),
        "top_7_responses": [slim_question(q) for q in responses[:7]],
        "dimension_context": {
            k: {
                "label": v.get("label"),
                "definition": v.get("definition"),
                "percentile": v.get("percentile"),
                "position": v.get("position"),
                "research_insight": v.get("research_insight"),
                "hrl_context": v.get("hrl_context"),
            }
            for k, v in dimensions.items()
        },
    }


def build_trajectory_brief(report_data: Dict[str, Any]) -> Dict[str, Any]:
    data = report_data.get("if_nothing_changes") or {}
    return {
        "demographics": report_data.get("demographics", {}),
        "usage_frequency": data.get("usage_frequency"),
        "highest_dimension": slim_dimension(data.get("highest_dimension")),
        "monitoring_anchor": slim_dimension(data.get("monitoring_anchor")),
        "strengths_likely_to_deepen": slim_dimensions(data.get("strengths_likely_to_deepen", [])),
        "areas_worth_monitoring": slim_dimensions(data.get("areas_worth_monitoring", [])),
        "all_dimensions": slim_dimensions((report_data.get("dimensions") or {}).values()),
        "what_to_protect": report_data.get("what_to_protect", []),
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
        "hrl_context": d.get("hrl_context"),
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


# ---------------------------------------------------------------------
# HCI context builder
# ---------------------------------------------------------------------

def build_hci_context(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compact HCI grounding context for Claude.

    Pulls from:
    - hci_signals_library.SIGNALS
    - human_reference_layer.py if available
    - dimension-specific hrl_context already attached in report_data
    """
    relevant_dimensions = set()

    for d in (report_data.get("dimensions") or {}).keys():
        relevant_dimensions.add(d)

    compact_dimensions = {}
    signal_dims = SIGNALS.get("dimensions", {}) if isinstance(SIGNALS, dict) else {}

    for dim in relevant_dimensions:
        signal = signal_dims.get(dim) or signal_dims.get(dim.replace("_", " ").title()) or {}
        if not isinstance(signal, dict):
            signal = {"text": str(signal)}
        compact_dimensions[dim] = {
            "signal": signal,
            "human_reference": get_human_reference_for_dimension(dim),
        }

    return {
        "principles": {
            "do": [
                "Explain behavioural patterns, not personality types.",
                "Use HCI's human reference framing: why the behaviour matters for judgement, agency, verification, emotional boundaries, disclosure, and thought partnership.",
                "Frame scores as awareness and choice, not diagnosis.",
                "Preserve user autonomy.",
                "Use plain English.",
            ],
            "do_not": [
                "Do not prescribe actions.",
                "Do not use therapy language.",
                "Do not say a score is good or bad.",
                "Do not overclaim from a percentile.",
                "Do not invent statistics not present in the data.",
            ],
        },
        "signals_dimensions": compact_dimensions,
        "signals_trends": SIGNALS.get("trends", {}) if isinstance(SIGNALS, dict) else {},
        "signals_combinations": SIGNALS.get("combinations", {}) if isinstance(SIGNALS, dict) else {},
        "signals_human_reference": SIGNALS.get("human_reference", {}) if isinstance(SIGNALS, dict) else {},
        "human_reference_layer": get_global_hrl_context(),
    }


def get_human_reference_for_dimension(dim: str) -> Dict[str, Any]:
    if HRL is None:
        return {}

    out = {}
    for attr in ["HBE_FRAMEWORK", "VALUES_SIGNALS", "HUMAN_REFERENCE_LAYER", "REFRAME_LIBRARY", "RESEARCH_INSIGHTS"]:
        source = getattr(HRL, attr, None)
        if isinstance(source, dict):
            value = source.get(dim)
            if value is None:
                value = source.get(dim.replace("_", " ").title())
            if value is not None:
                out[attr] = value

    for fn_name in ["get_values_reframe", "get_cohort_reframe", "apply_research_insight"]:
        fn = getattr(HRL, fn_name, None)
        if callable(fn):
            try:
                out[fn_name] = fn(dim)
            except TypeError:
                try:
                    out[fn_name] = fn(dim, "moderate")
                except Exception:
                    pass
            except Exception:
                pass

    return out


def get_global_hrl_context() -> Dict[str, Any]:
    if HRL is None:
        return {}

    out = {}
    for attr in [
        "HBE_FRAMEWORK",
        "VALUES_SIGNALS",
        "HBE_COHORT_REFRAMES",
        "REFRAME_LIBRARY",
        "RESEARCH_INSIGHTS",
    ]:
        value = getattr(HRL, attr, None)
        if isinstance(value, dict):
            # Keep it compact enough for prompt use.
            out[attr] = value
    return out


# ---------------------------------------------------------------------
# Anthropic API wrapper
# ---------------------------------------------------------------------

def call_claude_json(api_key: str, prompt: str, expected_keys: List[str]) -> Dict[str, str]:
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 4096,
        "temperature": 0.35,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=90) as response:
        raw = json.loads(response.read().decode("utf-8"))

    text = extract_text_from_anthropic_response(raw)
    data = parse_json_from_text(text)

    missing = [k for k in expected_keys if k not in data]
    if missing:
        raise ValueError(f"Claude JSON missing keys: {missing}. Got keys: {list(data.keys())}")

    # Ensure all values are strings.
    return {k: str(data.get(k, "")).strip() for k in expected_keys}


def extract_text_from_anthropic_response(raw: Dict[str, Any]) -> str:
    parts = []
    for block in raw.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    text = "\n".join(parts).strip()
    if not text:
        raise ValueError("No text content returned from Claude")
    return text


def parse_json_from_text(text: str) -> Dict[str, Any]:
    text = text.strip()

    # Best case: exact JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Common case: fenced code block.
    if "```" in text:
        stripped = text.replace("```json", "```")
        parts = stripped.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

    # Last resort: extract outer braces.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        return json.loads(candidate)

    raise ValueError(f"Could not parse JSON from Claude response: {text[:500]}")
