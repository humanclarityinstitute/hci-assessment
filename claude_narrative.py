"""
claude_narrative.py

Claude narrative layer for the clean HCI report system.

This version uses Anthropic tool calls for structured output instead of asking
Claude to return raw JSON. This avoids JSONDecodeError failures caused by
unescaped quotes/newlines in long narrative text.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List
import json
import os
import traceback
import urllib.request
import urllib.error

from narrative_context_builder import build_context_for_claude_section


CLAUDE_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def add_claude_narratives(report_data: Dict[str, Any], api_key: str | None = None) -> Dict[str, Any]:
    """
    Fill report_data["narrative_blocks"] with HCI-grounded Claude output.

    Safe:
    - If no API key, returns report_data unchanged with status.
    - If one call fails, other calls still run.
    - Renderer falls back to deterministic text where blocks are missing.
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
        "model": CLAUDE_MODEL,
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


def compact_context(context: Any, max_chars: int = 26000) -> str:
    """
    Keep prompts smaller and faster.

    Anthropic receives complete enough context, but we avoid huge prompt bloat.
    """
    text = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[CONTEXT TRUNCATED FOR PROMPT SIZE]"


# ---------------------------------------------------------------------
# Call 1: Opening + Section 4 + Section 5
# ---------------------------------------------------------------------

def generate_profile_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    context = {
        "opening": build_context_for_claude_section(report_data, "opening"),
        "rare_combinations": build_context_for_claude_section(report_data, "rare_combinations"),
        "behaviour_story": build_context_for_claude_section(report_data, "behaviour_story"),
    }

    prompt = f"""
Write selected narrative blocks for a Human Clarity Institute premium report.

The report structure is locked. Do not create sections, score anything, or give advice.

Fill exactly these blocks:
- opening_findings
- rare_combinations_narrative
- behaviour_story

Tone:
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

Use only this context:
{compact_context(context)}
"""

    schema = {
        "opening_findings": {
            "type": "string",
            "description": "Three paragraphs, 50-75 words each. Finding 1: most distinctive response. Finding 2: perception gap or alignment. Finding 3: rare combination or coherent/no-combo fallback."
        },
        "rare_combinations_narrative": {
            "type": "string",
            "description": "If rare combinations exist, explain top 1-2 in 350-500 words total. If none exist, write 120-180 words explaining what no rare combo means."
        },
        "behaviour_story": {
            "type": "string",
            "description": "300-400 word flowing narrative portrait anchored in the highest dimension and cross-dimensional relationships."
        },
    }

    return call_claude_structured(api_key, prompt, schema)


# ---------------------------------------------------------------------
# Call 2: Section 7 + Section 8
# ---------------------------------------------------------------------

def generate_distinctive_and_perception_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    context = {
        "distinctive_responses": build_context_for_claude_section(report_data, "distinctive_responses"),
        "perception_gap": build_context_for_claude_section(report_data, "perception_gap"),
    }

    prompt = f"""
Write two HCI report narrative blocks:
1. Section 7: Your Most Distinctive Responses
2. Section 8: Perception Gap Analysis

The raw data lists/tables already exist. Explain what they mean.

For Section 7:
- Intro paragraph, then 7 clearly separated response explanations.
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

Use only this context:
{compact_context(context)}
"""

    schema = {
        "distinctive_responses_narrative": {
            "type": "string",
            "description": "Intro paragraph plus 7 clearly separated response explanations. 40-70 words per response."
        },
        "perception_gap_narrative": {
            "type": "string",
            "description": "250-300 words comparing self-perception to benchmark positioning. Illuminating, not corrective."
        },
    }

    return call_claude_structured(api_key, prompt, schema)


# ---------------------------------------------------------------------
# Call 3: Section 10
# ---------------------------------------------------------------------

def generate_trajectory_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    context = build_context_for_claude_section(report_data, "trajectory")

    prompt = f"""
Write HCI report Section 10 narrative blocks: "If Nothing Changes".

This is not prediction, advice, urgency, or self-help.
It is observational synthesis based on what tends to remain stable or shift when current usage patterns hold.

Write only:
- likely_to_continue
- overall_outlook

The deterministic parts of Section 10 are handled elsewhere. Do not rewrite those lists.

Rules:
- No timeline predictions.
- No "you should".
- No alarmism.
- No optimization language.
- Ground observations in the provided HCI context.
- Speak directly to "you".

Use only this context:
{compact_context(context)}
"""

    schema = {
        "likely_to_continue": {
            "type": "string",
            "description": "100-160 words. What pattern is most likely to remain stable if usage and behaviour stay similar."
        },
        "overall_outlook": {
            "type": "string",
            "description": "90-140 words. Coherent closing: main strength, main monitoring area, and autonomy-preserving ending."
        },
    }

    return call_claude_structured(api_key, prompt, schema)


# ---------------------------------------------------------------------
# Call 4: Final Deep Dive
# ---------------------------------------------------------------------

def generate_deep_dive_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    context = build_context_for_claude_section(report_data, "deep_dive")

    prompt = f"""
Write the final HCI report Deep Dive.

This is the capstone section at the end of the report. It should be the most valuable interpretive insight in the report.

The Deep Dive should synthesize the whole report, including earlier narrative blocks when available, while focusing on the single most information-rich pattern selected in the context.

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

Use only this context:
{compact_context(context, max_chars=32000)}
"""

    schema = {
        "deep_dive": {
            "type": "string",
            "description": "600-800 word final capstone deep dive. Use 4-6 short paragraphs. Synthesize the report while focusing on the selected pattern."
        },
    }

    return call_claude_structured(api_key, prompt, schema)


# ---------------------------------------------------------------------
# Anthropic structured-output wrapper
# ---------------------------------------------------------------------

def call_claude_structured(api_key: str, prompt: str, properties: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """
    Force Claude to return a tool_use block with structured fields.
    This avoids freeform JSON parsing errors.
    """
    tool_schema = {
        "name": "write_hci_report_blocks",
        "description": "Return HCI report narrative blocks.",
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties.keys()),
            "additionalProperties": False,
        },
    }

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 5000,
        "temperature": 0.25,
        "tools": [tool_schema],
        "tool_choice": {"type": "tool", "name": "write_hci_report_blocks"},
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

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic HTTP {e.code}: {body[:500]}")

    for block in raw.get("content", []):
        if isinstance(block, dict) and block.get("type") == "tool_use":
            data = block.get("input") or {}
            return {k: str(data.get(k, "")).strip() for k in properties.keys()}

    raise RuntimeError(f"No tool_use block returned by Claude. Raw keys: {list(raw.keys())}")
