"""
claude_narrative.py

Claude narrative layer for the clean HCI report system.

Claude writes ONLY the narrative blocks required by the locked report spec.
All deterministic/static content remains in report_templates.py/report_sections.py.

Outputs:
report_data["narrative_blocks"] = {
    "opening_findings": "...",
    "rare_combinations_narrative": "...",
    "behaviour_story": "...",
    "deep_dive": "...",
    "perception_gap_narrative": "...",
    "distinctive_responses_narrative": "...",
    "likely_to_continue": "...",
    "overall_outlook": "..."
}
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List
import json
import os
import traceback
import urllib.request

from narrative_context_builder import build_context_for_claude_section


CLAUDE_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def add_claude_narratives(report_data: Dict[str, Any], api_key: str | None = None) -> Dict[str, Any]:
    """
    Fill report_data["narrative_blocks"] with HCI-grounded Claude output.

    Safe:
    - If no API key, returns report_data unchanged with status.
    - If one call fails, other calls still run.
    - Renderer can always fall back to deterministic sections.
    """
    report_data = deepcopy(report_data)
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    report_data.setdefault("narrative_blocks", {})
    report_data.setdefault("narrative_generation", {})

    if not api_key:
        report_data["narrative_generation"] = {
            "status": "skipped_no_api_key",
            "calls": {},
        }
        return report_data

    status = {
        "status": "started",
        "calls": {},
    }

    calls = [
        ("profile_narrative", generate_profile_narrative),
        ("distinctive_and_perception", generate_distinctive_and_perception_narrative),
        ("trajectory", generate_trajectory_narrative),
        ("deep_dive", generate_deep_dive_narrative),
    ]

    for name, fn in calls:
        try:
            blocks = fn(report_data, api_key)
            report_data["narrative_blocks"].update(blocks)
            status["calls"][name] = "success"
        except Exception as e:
            print(f"[CLAUDE] {name} failed: {e}")
            traceback.print_exc()
            status["calls"][name] = f"failed: {str(e)}"

    status["status"] = "complete"
    report_data["narrative_generation"] = status
    return report_data


# ---------------------------------------------------------------------
# Call 1: Opening + Section 4 + Section 5 + Section 8
# ---------------------------------------------------------------------

def generate_profile_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    context = {
        "opening": build_context_for_claude_section(report_data, "opening"),
        "rare_combinations": build_context_for_claude_section(report_data, "rare_combinations"),
        "behaviour_story": build_context_for_claude_section(report_data, "behaviour_story"),
    }

    prompt = f"""
You are writing selected narrative blocks for a Human Clarity Institute premium report.

The report structure is locked. You are NOT creating sections, deciding layout, scoring, or adding advice.
You are filling only these three narrative blocks:
1. opening_findings
2. rare_combinations_narrative
3. behaviour_story

Use only the provided report data and HCI context.
The tone must be:
- observational
- research-grounded
- plain English
- direct to "you"
- curious, not dramatic
- not clinical
- not self-help
- not prescriptive
- no diagnosis
- no unsupported predictions

Avoid percentile jargon except where unavoidable. Convert statistics into meaning.
Use "HCI's research" or "the data shows" lightly and only when grounded in the context.

CONTEXT:
{json.dumps(context, ensure_ascii=False, indent=2)}

Return VALID JSON ONLY with these exact keys:
{{
  "opening_findings": "Three paragraphs, 50-75 words each. Finding 1: most distinctive response. Finding 2: perception gap or alignment. Finding 3: rare combination or coherent/no-combo fallback.",
  "rare_combinations_narrative": "If rare combinations exist, explain top 1-2 combinations in 350-500 words total. If none exist, write 120-180 words explaining that no rare combination means the pattern is less defined by tension and more by the score distribution.",
  "behaviour_story": "300-400 word flowing narrative portrait. Anchor in the highest dimension. Explain cross-dimensional relationships. Ground in HCI observed patterns. No prescriptions."
}}
"""
    return call_claude_json(
        api_key,
        prompt,
        expected_keys=[
            "opening_findings",
            "rare_combinations_narrative",
            "behaviour_story",
        ],
    )


# ---------------------------------------------------------------------
# Call 2: Section 7
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# Call 4: Final Deep Dive
# ---------------------------------------------------------------------

def generate_deep_dive_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    context = build_context_for_claude_section(report_data, "deep_dive")

    prompt = f"""
You are writing the final HCI report Deep Dive.

This is the capstone section at the end of the report. It should be the most valuable interpretive insight in the report.

The Deep Dive should synthesize the whole report, including earlier narrative blocks when available, while focusing on the single most information-rich pattern selected in the context:
- rare combination if present,
- otherwise the most distinctive response,
- otherwise the largest perception gap,
- otherwise the highest dimension / overall pattern.

Rules:
- Write one coherent 600-800 word final section.
- Explain why this pattern matters.
- Explain how it connects to the wider profile.
- Ground the explanation in HCI signals, human reference framing, and benchmark context.
- Do not prescribe action.
- Do not diagnose.
- Do not exaggerate uniqueness.
- Do not turn this into generic self-help.
- Use direct plain English and speak to "you".

CONTEXT:
{json.dumps(context, ensure_ascii=False, indent=2)}

Return VALID JSON ONLY:
{{
  "deep_dive": "600-800 word final capstone deep dive. Use 4-6 short paragraphs. Synthesize the report while focusing on the selected pattern. Observational, research-grounded, specific, and autonomy-preserving."
}}
"""
    return call_claude_json(
        api_key,
        prompt,
        expected_keys=["deep_dive"],
    )


# ---------------------------------------------------------------------
# Call 2: Section 7 + Section 8
# ---------------------------------------------------------------------

def generate_distinctive_and_perception_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    context = {
        "distinctive_responses": build_context_for_claude_section(report_data, "distinctive_responses"),
        "perception_gap": build_context_for_claude_section(report_data, "perception_gap"),
    }

    prompt = f"""
You are writing two HCI report narrative blocks:
1. Section 7: Your Most Distinctive Responses
2. Section 8: Perception Gap Analysis

The raw data lists/tables already exist. Your job is to explain what they mean.

For Section 7:
- Write an intro paragraph, then 7 clearly separated response explanations.
- For each response, explain what is distinctive, why it matters in HCI behavioural terms, and how it connects to the wider profile.

For Section 8:
- Compare self-perception to benchmark positioning.
- Frame gaps as illuminating, not corrective.
- Never say "you were wrong".
- If alignment is strong, explain why accurate self-perception matters.

Rules:
- Direct to "you".
- Observational, research-grounded, curious.
- No diagnosis.
- No prescriptions.
- No unsupported claims.
- Use provided HCI context only.

CONTEXT:
{json.dumps(context, ensure_ascii=False, indent=2)}

Return VALID JSON ONLY:
{{
  "distinctive_responses_narrative": "Intro paragraph plus 7 clearly separated response explanations. 40-70 words per response. Use bold response labels if helpful.",
  "perception_gap_narrative": "250-300 words comparing self-perception to benchmark positioning. If no significant gaps, explain alignment as meaningful. Illuminating, not corrective."
}}
"""
    return call_claude_json(
        api_key,
        prompt,
        expected_keys=["distinctive_responses_narrative", "perception_gap_narrative"],
    )


# ---------------------------------------------------------------------
# Call 3: Section 10
# ---------------------------------------------------------------------

def generate_trajectory_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    context = build_context_for_claude_section(report_data, "trajectory")

    prompt = f"""
You are writing HCI report Section 10: "If Nothing Changes".

This is not prediction, advice, urgency, or self-help.
It is an observational synthesis based on what tends to remain stable or shift when current usage patterns hold.

Write only:
1. likely_to_continue
2. overall_outlook

The deterministic parts of Section 10 — strengths likely to deepen and areas worth monitoring — are handled elsewhere. Do not rewrite those lists.

Rules:
- No timeline predictions.
- No "you should".
- No alarmism.
- No optimization language.
- Ground observations in the provided HCI context.
- Speak directly to "you".

CONTEXT:
{json.dumps(context, ensure_ascii=False, indent=2)}

Return VALID JSON ONLY:
{{
  "likely_to_continue": "100-160 words. What pattern is most likely to remain stable if usage and behaviour stay similar.",
  "overall_outlook": "90-140 words. Coherent closing: main strength, main monitoring area, and autonomy-preserving ending."
}}
"""
    return call_claude_json(
        api_key,
        prompt,
        expected_keys=["likely_to_continue", "overall_outlook"],
    )


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

    with urllib.request.urlopen(req, timeout=120) as response:
        raw = json.loads(response.read().decode("utf-8"))

    text = extract_text_from_anthropic_response(raw)
    data = parse_json_from_text(text)

    missing = [k for k in expected_keys if k not in data]
    if missing:
        raise ValueError(f"Claude JSON missing keys: {missing}. Got keys: {list(data.keys())}")

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

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "```" in text:
        stripped = text.replace("```json", "```")
        for part in stripped.split("```"):
            candidate = part.strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])

    raise ValueError(f"Could not parse JSON from Claude response: {text[:500]}")
