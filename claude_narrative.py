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
from concurrent.futures import ThreadPoolExecutor, as_completed
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

    # Run the first three calls in parallel because they are independent.
    # Then run Deep Dive last so it can use earlier narrative_blocks as context.
    parallel_calls = [
        ("profile_narrative", generate_profile_narrative),
        ("distinctive_and_perception", generate_distinctive_and_perception_narrative),
        ("trajectory", generate_trajectory_narrative),
    ]

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_map = {
            executor.submit(fn, report_data, api_key): name
            for name, fn in parallel_calls
        }

        for future in as_completed(future_map):
            name = future_map[future]
            try:
                blocks = future.result()
                report_data["narrative_blocks"].update(blocks)
                status["calls"][name] = "success"
            except Exception as e:
                print(f"[CLAUDE] {name} failed: {e}")
                traceback.print_exc()
                status["calls"][name] = f"failed: {str(e)}"

    # Deep Dive runs after the first three so it can synthesize the whole report.
    try:
        blocks = generate_deep_dive_narrative(report_data, api_key)
        report_data["narrative_blocks"].update(blocks)
        status["calls"]["deep_dive"] = "success"
    except Exception as e:
        print(f"[CLAUDE] deep_dive failed: {e}")
        traceback.print_exc()
        status["calls"]["deep_dive"] = f"failed: {str(e)}"

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
- profile_shape_summary
- rare_combinations_narrative
- behaviour_story

For opening_findings, write the opening synthesis for the report.
This is the first personalised interpretation the reader sees. It must make the reader feel the report has actually analysed their pattern.

Write 330-430 words total.
Use exactly three short editorial subheadings, each followed by one substantial paragraph.
Do not use boxes, bullets, numbering, labels like "Behavioural finding", or fields such as "Data:" / "Interpretation:" / "Why it matters:".

The three subheadings should cover:
1. The most distinctive signal in the profile.
2. How the participant's self-perception compares with the benchmark, or alignment if there is no gap.
3. The wider pattern shape: rare combination if present, otherwise coherent/no-combo interpretation.

Also write profile_shape_summary as one separate 60-90 word paragraph for the later section titled "The Shape of Your Profile". This paragraph should summarise the overall shape created by all nine dimensions. Do not repeat the opening findings. Do not discuss every dimension individually. Describe whether the profile is concentrated around a few distinctive dimensions or broadly aligned with the benchmark population. Avoid percentages and percentile language.

For behaviour_story, write an observational behavioural profile, not a dramatic narrative.
This section should feel like an HCI researcher reflecting the participant's pattern back to them.
Write 300-350 words total, in 3-4 flowing paragraphs, with no internal headings or bullets.
Begin with the single strongest behavioural signal or organising feature in the participant's profile, but do not spend the whole opening explaining one question. Use that anchor to explain what it reveals about the wider pattern.
Identify the 2-3 underlying mechanisms that best account for the profile. Do not try to cover every dimension. Do not list all nine dimensions. Do not restate the dashboard.
Use HCI research as supporting evidence, not as the main subject of the section. Suitable phrasing includes "Across HCI's benchmark studies...", "HCI's research consistently shows...", or "Looking across the measured behaviours..." but only where it adds clarity.
Avoid repeating comparisons already shown earlier in the report, such as age-group comparisons, everyday-user comparisons, or bare percentile rankings.
Do not use means, averages, statistical shorthand, or technical language. Do not predict what will happen. Do not give advice.
End with a clear concluding observation that naturally leads into the rest of the report, for example by pointing to the tension, alignment, or mechanism the following sections will examine more closely.

Style the opening_findings subheadings like a premium research report, for example:
Your most distinctive signal
How your self-perception compares
The shape of the wider pattern

Use one or two key statistics where useful, but do not overload the opening with numbers. Later sections provide the evidence.
Never use means, averages, standard deviations, effect sizes, raw score averages, or statistical shorthand that a general reader has to interpret. Do not write phrases such as "mean of 1.1" or "average of 4.4". If cohort differences matter, explain them in plain behavioural language, for example: "everyday AI users report higher reliance, but your pattern sits beyond that already-high group."

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
            "description": "330-430 word opening synthesis with exactly three short editorial subheadings, each followed by one substantial paragraph. No bullets, no numbering, no 'Behavioural finding', no Data/Interpretation/Why-it-matters labels, and no means/averages/statistical shorthand."
        },
        "profile_shape_summary": {
            "type": "string",
            "description": "60-90 word paragraph for The Shape of Your Profile. Summarise the overall profile shape across all nine dimensions. Do not repeat the opening findings, do not list every dimension, and avoid percentages/percentiles."
        },
        "rare_combinations_narrative": {
            "type": "string",
            "description": "If rare combinations exist, explain top 1-2 in 350-500 words total. If none exist, write 120-180 words explaining what no rare combo means."
        },
        "behaviour_story": {
            "type": "string",
            "description": "300-350 word observational behavioural profile in 3-4 flowing paragraphs. Begin with the strongest behavioural signal or organising feature, explain the 2-3 mechanisms that best account for the profile, use HCI research lightly as support, avoid dashboard repetition, no predictions, no advice, no means/averages/statistical shorthand."
        },
    }

    return call_claude_structured(api_key, prompt, schema)



def build_compact_distinctive_perception_context(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compact, guaranteed-complete context for Sections 7 and 8.

    This intentionally removes raw variable keys from the Claude-facing context,
    so codes like del_q3 never appear in the generated report.
    """
    dimensions = report_data.get("dimensions") or {}
    distinctive = report_data.get("distinctive_responses") or []

    cleaned_responses = []
    for i, q in enumerate(distinctive[:7], 1):
        dim = q.get("dimension")
        dim_data = dimensions.get(dim, {})
        cleaned_responses.append({
            "rank": i,
            "dimension_label": q.get("dimension_label") or dim_data.get("label"),
            "question_text": q.get("question_text"),
            "answer_display": q.get("answer_display"),
            "percentile": q.get("percentile"),
            "percentile_label": q.get("percentile_label"),
            "age_group_percentile": q.get("percentile_age_group"),
            "comparison_statement": q.get("comparison_statement"),
            "dimension_percentile": dim_data.get("percentile"),
            "dimension_position": dim_data.get("position"),
            "dimension_research_signal": dim_data.get("research_insight"),
            "is_reverse_scored": q.get("is_reverse_scored"),
        })

    perception = report_data.get("perception_gap") or {}
    cleaned_perception = {
        "self_perception": perception.get("self_perception", []),
        "gaps": perception.get("gaps", []),
        "largest_gap": perception.get("largest_gap"),
        "has_significant_gap": perception.get("has_significant_gap"),
    }

    top_dims = []
    for d in sorted(dimensions.values(), key=lambda x: x.get("percentile", 50), reverse=True)[:5]:
        top_dims.append({
            "label": d.get("label"),
            "percentile": d.get("percentile"),
            "position": d.get("position"),
            "research_signal": d.get("research_insight"),
        })

    low_dims = []
    for d in sorted(dimensions.values(), key=lambda x: x.get("percentile", 50))[:3]:
        low_dims.append({
            "label": d.get("label"),
            "percentile": d.get("percentile"),
            "position": d.get("position"),
            "research_signal": d.get("research_insight"),
        })

    return {
        "distinctive_response_count": len(cleaned_responses),
        "distinctive_responses": cleaned_responses,
        "perception_gap": cleaned_perception,
        "top_dimensions": top_dims,
        "lowest_dimensions": low_dims,
        "instruction": "Use only plain labels and question text. Never output variable IDs.",
    }


# ---------------------------------------------------------------------
# Call 2: Section 7 + Section 8
# ---------------------------------------------------------------------

def generate_distinctive_and_perception_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    context = build_compact_distinctive_perception_context(report_data)

    prompt = f"""
Write two HCI report narrative blocks:
1. Section 7: Your Most Distinctive Responses
2. Section 8: Perception Gap Analysis

The raw data lists/tables already exist. Explain what they mean.

For Section 7:
- You MUST explain all 7 distinctive responses provided.
- Do NOT use raw variable names or codes such as del_q3, agency_q1, trust_q3, rel_q1.
- Label each response by its plain question text or a short human-readable label.
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
- Never write "[context truncated]" or imply any response data was unavailable.
- If all 7 responses are present in context, write all 7.

Use only this compact context:
{compact_context(context, max_chars=18000)}
"""

    schema = {
        "distinctive_responses_narrative": {
            "type": "string",
            "description": "Intro paragraph plus exactly 7 clearly separated response explanations. 40-70 words per response. Never include variable IDs."
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



def clean_narrative_text(text: str) -> str:
    """
    Final safety cleanup for model output.

    Removes raw variable-code labels if Claude accidentally includes them.
    It does not remove question text or substantive content.
    """
    if not text:
        return text

    import re

    # Remove markdown labels like **1. del_q3 — "...":
    text = re.sub(
        r'(\*\*\s*\d+\.\s+)([a-z]+_q\d+\s*[—-]\s*)',
        r'\1',
        text,
        flags=re.IGNORECASE,
    )

    # Remove standalone variable-code prefixes at line starts.
    text = re.sub(
        r'(?m)^(\s*(?:\*\*)?\d+\.\s+)([a-z]+_q\d+\s*[—-]\s*)',
        r'\1',
        text,
        flags=re.IGNORECASE,
    )

    # Remove bracketed placeholder failure text.
    text = re.sub(
        r'\n?\s*\*\*?\s*\d+\.\s*\[Seventh distinctive response[^\]]*\].*?(?=\n\s*\*\*?\s*\d+\.|\Z)',
        '',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return text.strip()


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
            return {k: clean_narrative_text(str(data.get(k, "")).strip()) for k in properties.keys()}

    raise RuntimeError(f"No tool_use block returned by Claude. Raw keys: {list(raw.keys())}")
