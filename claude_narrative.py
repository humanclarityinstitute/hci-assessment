"""
Claude narrative layer for the HCI premium report.

The report uses two structured Anthropic calls:

1. profile synthesis;
2. baseline and return question.

All measured results, selected evidence, comparisons and rarity controls are
prepared before this module runs. Claude writes only the six approved narrative
outputs and cannot alter the deterministic report data.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List
import json
import os
import re
import time
import traceback
import urllib.error
import urllib.request

from narrative_context_builder import (
    assert_narrative_context_contract,
    build_narrative_context,
)


CLAUDE_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
REQUEST_TIMEOUT_SECONDS = 120
MAX_REQUEST_ATTEMPTS = 2

PROFILE_OUTPUT_FIELDS = {
    "signature_sentence",
    "combination_narrative",
    "pattern_narrative",
    "human_capital_lens",
}
BASELINE_OUTPUT_FIELDS = {
    "return_question",
    "baseline_closing",
}

REPORT_CLAIM_GUARDRAILS = """
Evidence boundary:
- This is a structured self-report assessment. Treat answers, scores, benchmark
  positions and combinations as evidence of reported patterns, not direct
  observation of the participant's real-world behaviour.
- State supplied measurements clearly. Use proportionate language such as
  "appears", "suggests", "may reflect" or "is consistent with" only when
  moving from measurement into interpretation.
- Do not repeat legal qualifiers mechanically. Preserve a clear, human,
  premium-report voice.
- Do not present an association or benchmark difference as a proven cause,
  mechanism, predictor, inevitable progression or verified outcome.
- Do not infer individual change over time from one assessment. The result is a
  current reference point for possible later comparison.
- Do not claim that AI has developed, strengthened, weakened, eroded, preserved
  or removed a human capability.
- Do not imply clinical assessment, diagnosis, addiction, impairment,
  psychological measurement, objective observation or independently verified
  behaviour.
- Refer to the HCI participant benchmark. Do not describe it as the general
  population, everyone or a population norm.
- Do not diagnose directly reported reliance, unease or dependence-related
  experiences as dependency.
"""


def add_claude_narratives(
    report_data: Dict[str, Any],
    api_key: str | None = None,
) -> Dict[str, Any]:
    """Add the six approved narrative outputs to canonical report data."""
    if not isinstance(report_data, dict):
        raise ValueError("report_data must be a dictionary")

    result = deepcopy(report_data)
    result.setdefault("signature", {})
    result.setdefault("distinctive_pattern", {})
    result.setdefault("pattern_synthesis", {})
    result.setdefault("human_capital_lens", [])
    result.setdefault("baseline", {})
    result.setdefault("narrative_blocks", {})

    context = build_narrative_context(result)
    assert_narrative_context_contract(context)

    # Install complete deterministic text before any network request. The report
    # remains renderable when the API key is absent or either request fails.
    apply_profile_output(
        result,
        profile_fallback(context["profile_synthesis"]),
    )
    apply_baseline_output(
        result,
        baseline_fallback(context["baseline_return"]),
    )

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    status = {
        "status": "started" if api_key else "skipped_no_api_key",
        "workflow": "two_structured_calls",
        "model": CLAUDE_MODEL,
        "expected_calls": 2,
        "attempted_calls": 0,
        "successful_calls": 0,
        "calls": {},
    }

    if not api_key:
        result["narrative_generation"] = status
        return result

    status["attempted_calls"] += 1
    try:
        profile_output = generate_profile_synthesis(
            context["profile_synthesis"],
            api_key,
        )
        validate_profile_output(
            profile_output,
            context["profile_synthesis"],
        )
        apply_profile_output(result, profile_output)
        status["successful_calls"] += 1
        status["calls"]["profile_synthesis"] = "success"
    except Exception as exc:
        print(f"[CLAUDE] profile_synthesis failed: {exc}")
        traceback.print_exc()
        status["calls"]["profile_synthesis"] = f"failed: {str(exc)}"

    status["attempted_calls"] += 1
    try:
        baseline_output = generate_baseline_return(
            context["baseline_return"],
            api_key,
        )
        validate_baseline_output(baseline_output)
        apply_baseline_output(result, baseline_output)
        status["successful_calls"] += 1
        status["calls"]["baseline_return"] = "success"
    except Exception as exc:
        print(f"[CLAUDE] baseline_return failed: {exc}")
        traceback.print_exc()
        status["calls"]["baseline_return"] = f"failed: {str(exc)}"

    if status["successful_calls"] == 2:
        status["status"] = "complete"
    elif status["successful_calls"] == 1:
        status["status"] = "partial_using_fallbacks"
    else:
        status["status"] = "failed_using_fallbacks"

    result["narrative_generation"] = status
    return result


def generate_profile_synthesis(
    context: Dict[str, Any],
    api_key: str,
) -> Dict[str, Any]:
    """Generate signature, pattern synthesis and Human Capital Lens text."""
    print("[CLAUDE] Starting profile_synthesis...")
    start = time.time()

    prompt = f"""
Write four narrative outputs for the Human Clarity Institute AI Identity &
Behaviour Report.

{REPORT_CLAIM_GUARDRAILS}

Core product rule:
Reveal more. Explain only what improves clarity.

Use only the supplied context. Do not select, calculate, change or estimate any
score, percentile, cohort comparison, rarity, defining signal or evidence item.

Return exactly these fields:

1. signature_sentence
- Exactly one sentence, approximately 18–35 words.
- Describe the relationship among the defining signals in a memorable but
  restrained way.
- Do not create a persona, type, diagnosis, identity label or permanent trait.

2. combination_narrative
- Exactly two concise paragraphs, approximately 130–210 words total.
- First explain what the supplied combination or coherent pattern shows.
- Then explain what that pattern may suggest about the participant's current
  relationship with AI.
- Mention prevalence only when an approved rarity percentage is supplied.
- Do not redefine every dimension or introduce advice.

3. pattern_narrative
- Approximately 250–350 words in three or four flowing paragraphs.
- Explain the organising feature of the profile and how the defining signals,
  selected evidence, similar-user comparisons and self-perception fit together.
- Use numbers selectively. Do not repeat every result.
- End with one clear synthesis of the current response pattern.
- Do not discuss future trajectory, recommendations or capability change.

4. human_capital_lens
- Exactly three objects with title and body.
- Use exactly the three supplied titles, unchanged and in the same order.
- Each body must be one concise sentence, approximately 18–38 words.
- Explain why the capability is relevant to this response pattern.
- Do not claim that it is strong, weak, developing, declining, protected, lost
  or objectively measured.
- Do not include scores or percentile language.

General writing rules:
- Write directly to "you".
- Use plain English with a calm, precise, premium tone.
- Describe self-reported patterns, not observed behaviour.
- State supplied evidence clearly; qualify interpretation rather than weakening
  the evidence.
- No Markdown, headings, bullets, coaching, diagnosis, causation, prediction,
  general-population claims or internal variable IDs.

Context:
{compact_context(context, max_chars=24000)}
"""

    capability_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["title", "body"],
        "additionalProperties": False,
    }
    schema = {
        "signature_sentence": {
            "type": "string",
            "description": (
                "One evidence-led sentence describing the current response pattern."
            ),
        },
        "combination_narrative": {
            "type": "string",
            "description": (
                "Two concise paragraphs explaining the selected combination or "
                "coherent pattern."
            ),
        },
        "pattern_narrative": {
            "type": "string",
            "description": (
                "A 250–350 word synthesis of the defining signals, selected "
                "evidence, similar-user comparisons and self-perception."
            ),
        },
        "human_capital_lens": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": capability_schema,
        },
    }

    output = call_claude_structured(api_key, prompt, schema)
    print(
        f"[CLAUDE] profile_synthesis completed in "
        f"{time.time() - start:.1f}s"
    )
    return output


def generate_baseline_return(
    context: Dict[str, Any],
    api_key: str,
) -> Dict[str, str]:
    """Generate the personalised return question and baseline closing."""
    print("[CLAUDE] Starting baseline_return...")
    start = time.time()

    prompt = f"""
Write the two generated fields for the Baseline and Closing pages of the Human
Clarity Institute AI Identity & Behaviour Report.

{REPORT_CLAIM_GUARDRAILS}

Return exactly these fields:

1. return_question
- Exactly one question, approximately 18–36 words.
- It must be answerable only by comparing a later assessment with this dated
  baseline.
- Base it on the supplied comparison priorities or strongest combination.
- Do not predict a direction of change.
- Do not instruct the participant to improve, reduce, protect, increase or
  monitor anything.
- Do not use "should".

2. baseline_closing
- Exactly one sentence, approximately 18–32 words.
- Explain that this report establishes a dated reference point for later
  comparison.
- Do not promote HCI, sell another report or introduce new interpretation.

Use only the supplied context. No Markdown, advice, prediction, diagnosis,
causal claim, general-population language or internal variable IDs.

Context:
{compact_context(context, max_chars=12000)}
"""

    schema = {
        "return_question": {
            "type": "string",
            "description": "One personalised question for a future comparison.",
        },
        "baseline_closing": {
            "type": "string",
            "description": (
                "One sentence describing the value of the dated baseline."
            ),
        },
    }

    output = call_claude_structured(api_key, prompt, schema)
    print(
        f"[CLAUDE] baseline_return completed in "
        f"{time.time() - start:.1f}s"
    )
    return output


def apply_profile_output(
    report_data: Dict[str, Any],
    output: Dict[str, Any],
) -> None:
    """Place profile narrative outputs into their canonical report fields."""
    signature_sentence = clean_narrative_text(
        str(output.get("signature_sentence") or "")
    )
    combination_narrative = clean_narrative_text(
        str(output.get("combination_narrative") or "")
    )
    pattern_narrative = clean_narrative_text(
        str(output.get("pattern_narrative") or "")
    )

    lens = []
    for item in output.get("human_capital_lens") or []:
        if not isinstance(item, dict):
            continue
        title = clean_narrative_text(str(item.get("title") or ""))
        body = clean_narrative_text(str(item.get("body") or ""))
        if title and body:
            lens.append({"title": title, "body": body})
    lens = lens[:3]

    report_data["signature"]["signature_sentence"] = signature_sentence
    report_data["distinctive_pattern"]["narrative"] = combination_narrative
    report_data["pattern_synthesis"]["pattern_narrative"] = pattern_narrative
    report_data["human_capital_lens"] = lens

    defining = report_data.get("defining_signals") or []
    report_data["pattern_synthesis"]["organising_feature"] = (
        defining[0].get("label")
        if defining and isinstance(defining[0], dict)
        else None
    )

    report_data["narrative_blocks"].update({
        "signature_sentence": signature_sentence,
        "combination_narrative": combination_narrative,
        "pattern_narrative": pattern_narrative,
        "human_capital_lens": deepcopy(lens),
    })


def apply_baseline_output(
    report_data: Dict[str, Any],
    output: Dict[str, Any],
) -> None:
    """Place baseline narrative outputs into their canonical report fields."""
    question = clean_narrative_text(
        str(output.get("return_question") or "")
    )
    closing = clean_narrative_text(
        str(output.get("baseline_closing") or "")
    )

    report_data["baseline"]["return_question"] = question
    report_data["baseline"]["baseline_closing"] = closing
    report_data["narrative_blocks"].update({
        "return_question": question,
        "baseline_closing": closing,
    })


def profile_fallback(context: Dict[str, Any]) -> Dict[str, Any]:
    """Create complete deterministic profile text when Claude is unavailable."""
    defining = context.get("defining_signals") or []
    labels = [
        item.get("label")
        for item in defining
        if isinstance(item, dict) and item.get("label")
    ]

    if len(labels) >= 3:
        signature = (
            f"Your current profile is most clearly shaped by the relationship "
            f"between {labels[0]}, {labels[1]} and {labels[2]}."
        )
    elif labels:
        signature = (
            "Your current profile is most clearly shaped by "
            + join_labels(labels)
            + "."
        )
    else:
        signature = (
            "Your current responses form a distinct pattern across the nine "
            "areas measured in this assessment."
        )

    strongest_pattern = context.get("strongest_pattern") or {}
    combination = strongest_pattern.get("combination") or {}
    if combination.get("label_1") and combination.get("label_2"):
        prevalence = ""
        if combination.get("rarity_percent") is not None:
            prevalence = (
                f" The approved benchmark estimate places this combination "
                f"at approximately {combination.get('rarity_percent'):g}% of "
                "the relevant sample."
            )
        combination_narrative = (
            f"The clearest interaction in your profile is between "
            f"{combination.get('label_1')} and {combination.get('label_2')}. "
            "These two positions provide more information together than either "
            f"result does alone.{prevalence}\n\n"
            "Taken together, they may indicate that these aspects of your "
            "reported AI use are operating as one connected pattern rather than "
            "as separate behaviours. This interaction is therefore one of the "
            "most useful ways to understand the wider shape of your profile."
        )
    else:
        combination_narrative = (
            "Your profile is not defined by one isolated result. Its clearest "
            "feature is the way the defining signals combine into a coherent "
            "overall shape.\n\n"
            "That coherence suggests the relationship between the results is "
            "more informative than any one dimension by itself. The pattern is "
            "therefore best understood through the way the leading signals "
            "reinforce, balance or qualify one another."
        )

    measurement_sentences = []
    for item in defining:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        percentile = item.get("overall_percentile")
        similar = item.get("similar_use_percentile")
        if label and percentile is not None:
            sentence = (
                f"{label} sits at the {ordinal(percentile)} percentile within "
                "the HCI participant benchmark"
            )
            if similar is not None:
                sentence += (
                    f" and at the {ordinal(similar)} percentile among "
                    "participants reporting similar AI-use frequency"
                )
            measurement_sentences.append(sentence + ".")

    first_paragraph = (
        "The organising feature of your current profile is the relationship "
        "between its defining signals. "
        + " ".join(measurement_sentences)
    ).strip()

    similar_shifts = context.get("similar_user_comparisons") or []
    if similar_shifts:
        strongest_shift = similar_shifts[0]
        similar_paragraph = (
            f"The comparison with similar AI users adds an important layer. "
            f"For {strongest_shift.get('label')}, "
            f"{strongest_shift.get('meaning', '').lower()} This helps separate "
            "what may be associated with frequent AI use from what remains "
            "especially distinctive within your own response pattern."
        )
    else:
        similar_paragraph = (
            "Where similar-use comparisons are available, the profile is best "
            "read as a combination of overall position and context. The absence "
            "of a large shift is also informative because it shows where your "
            "standing is broadly consistent across the two benchmark views."
        )

    perception = context.get("self_perception") or {}
    largest = perception.get("largest_difference") or {}
    if largest.get("difference_available"):
        perception_paragraph = (
            "Your self-perception and assessment-based position provide two "
            "views of the same relationship with AI. Their largest difference "
            "does not invalidate your self-understanding; it adds a benchmark "
            "perspective that is difficult to establish from personal "
            "experience alone."
        )
    else:
        perception_paragraph = (
            "Your self-perception provides a second perspective on the profile. "
            "The report keeps that view alongside the response-based benchmark "
            "position without treating either as a complete account by itself."
        )

    concluding_paragraph = (
        "The value of the profile is therefore not a single high or low score. "
        "It lies in the way the defining signals, selected evidence and "
        "self-perception comparison combine into one clear account of where "
        "your reported relationship with AI sits today."
    )
    pattern_narrative = "\n\n".join([
        first_paragraph,
        similar_paragraph,
        perception_paragraph,
        concluding_paragraph,
    ])

    lens = []
    for theme in context.get("human_capital_themes") or []:
        title = theme.get("title") or "Human capability"
        dimension_labels = [
            item.get("label")
            for item in theme.get("supporting_dimensions") or []
            if isinstance(item, dict) and item.get("label")
        ]
        if dimension_labels:
            body = (
                f"This capability is relevant because your reported "
                f"{join_labels(dimension_labels)} pattern contributes directly "
                "to the overall shape of the profile."
            )
        else:
            body = (
                "This capability offers a useful human lens for interpreting "
                "the current response pattern without treating it as measured."
            )
        lens.append({"title": title, "body": body})

    return {
        "signature_sentence": signature,
        "combination_narrative": combination_narrative,
        "pattern_narrative": pattern_narrative,
        "human_capital_lens": lens[:3],
    }


def baseline_fallback(context: Dict[str, Any]) -> Dict[str, str]:
    """Create deterministic baseline text when Claude is unavailable."""
    priorities = context.get("comparison_priorities") or []
    labels = [
        item.get("label")
        for item in priorities
        if isinstance(item, dict) and item.get("label")
    ]

    if len(labels) >= 2:
        question = (
            f"When you reassess, will the relationship between {labels[0]} "
            f"and {labels[1]} look similar to the pattern recorded today?"
        )
    elif labels:
        question = (
            f"When you reassess, will your reported {labels[0]} position look "
            "similar to the pattern recorded today?"
        )
    else:
        question = (
            "When you reassess, which parts of your current AI-use pattern "
            "will look similar and which will look different?"
        )

    baseline_date = (
        (context.get("report_identity") or {}).get("baseline_date")
        or "this assessment date"
    )
    closing = (
        f"This report records your current response pattern as a dated "
        f"baseline from {display_date(baseline_date)} for later comparison."
    )
    return {
        "return_question": question,
        "baseline_closing": closing,
    }


def validate_profile_output(
    output: Dict[str, Any],
    context: Dict[str, Any],
) -> None:
    """Validate Claude's first structured response before applying it."""
    if not isinstance(output, dict):
        raise ValueError("profile output must be a dictionary")
    missing = PROFILE_OUTPUT_FIELDS.difference(output.keys())
    if missing:
        raise ValueError(f"profile output missing fields: {sorted(missing)}")

    for key in (
        "signature_sentence",
        "combination_narrative",
        "pattern_narrative",
    ):
        if not isinstance(output.get(key), str) or not output[key].strip():
            raise ValueError(f"{key} must be a non-empty string")

    lens = output.get("human_capital_lens")
    if not isinstance(lens, list) or len(lens) != 3:
        raise ValueError("human_capital_lens must contain exactly 3 items")

    expected_titles = [
        item.get("title")
        for item in context.get("human_capital_themes") or []
    ]
    returned_titles = [
        item.get("title") if isinstance(item, dict) else None
        for item in lens
    ]
    if returned_titles != expected_titles:
        raise ValueError("Claude changed the locked Human Capital theme titles")

    validate_output_language(output)


def validate_baseline_output(output: Dict[str, Any]) -> None:
    """Validate Claude's second structured response before applying it."""
    if not isinstance(output, dict):
        raise ValueError("baseline output must be a dictionary")
    missing = BASELINE_OUTPUT_FIELDS.difference(output.keys())
    if missing:
        raise ValueError(f"baseline output missing fields: {sorted(missing)}")

    for key in BASELINE_OUTPUT_FIELDS:
        if not isinstance(output.get(key), str) or not output[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
    if not output["return_question"].strip().endswith("?"):
        raise ValueError("return_question must end with a question mark")

    validate_output_language(output)


def validate_output_language(output: Any) -> None:
    """Reject unsupported or unsafe model language before rendering."""
    text = json.dumps(output, ensure_ascii=False).lower()
    prohibited = {
        "internal_variable_id": (
            r"\b(?:rel|trust|ver|del|agency|emot|disc|thought|soc)_q\d+\b"
        ),
        "diagnosis": r"\bdiagnos(?:e|ed|is|tic)\b",
        "addiction": r"\baddict(?:ion|ed|ive)?\b",
        "causal_certainty": r"\bcaused by\b|\bproves\b|\bconfirms that\b",
        "prediction": (
            r"\bwill inevitably\b|\bwill definitely\b|\bis certain to\b"
        ),
        "coaching": r"\byou should\b|\btry to\b|\bmake sure\b",
        "population_scope": r"\bgeneral population\b|\bpopulation norm\b",
        "objective_claim": r"\bobjective reality\b|\bmeasured reality\b",
        "capability_change": (
            r"\bcapabilit(?:y|ies) (?:has|have) (?:developed|declined|weakened|strengthened)\b"
        ),
    }
    found = [
        label
        for label, pattern in prohibited.items()
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]
    if found:
        raise ValueError(
            f"narrative output contains prohibited content: {found}"
        )


def clean_narrative_text(text: str) -> str:
    """Remove accidental internal IDs and light Markdown from model output."""
    if not text:
        return text

    text = re.sub(
        r"\b(?:rel|trust|ver|del|agency|emot|disc|thought|soc)_q\d+\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compact_context(context: Any, max_chars: int) -> str:
    """Serialise compact context and fail rather than silently truncating it."""
    text = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    if len(text) > max_chars:
        raise ValueError(
            f"Narrative context is {len(text)} characters; maximum is {max_chars}"
        )
    return text


def _clean_structured_value(value: Any) -> Any:
    if isinstance(value, str):
        return clean_narrative_text(value.strip())
    if isinstance(value, list):
        return [_clean_structured_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _clean_structured_value(item)
            for key, item in value.items()
        }
    return value


def call_claude_structured(
    api_key: str,
    prompt: str,
    properties: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Request a structured Anthropic tool-use response with bounded retries."""
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
        "tool_choice": {
            "type": "tool",
            "name": "write_hci_report_blocks",
        },
        "messages": [{"role": "user", "content": prompt}],
    }

    print(
        f"[CLAUDE-API] Starting request: model={CLAUDE_MODEL}, "
        f"properties={list(properties.keys())}"
    )

    last_error: Exception | None = None
    for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
        start_time = time.time()
        request = urllib.request.Request(
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
            with urllib.request.urlopen(
                request,
                timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                raw = json.loads(response.read().decode("utf-8"))
                elapsed = time.time() - start_time
                usage = raw.get("usage") or {}
                print(
                    f"[CLAUDE-API] Response received in {elapsed:.1f}s | "
                    f"tokens: {usage.get('input_tokens', '?')}→"
                    f"{usage.get('output_tokens', '?')}"
                )
                break
        except urllib.error.HTTPError as exc:
            elapsed = time.time() - start_time
            body = exc.read().decode("utf-8", errors="replace")
            retryable = exc.code in {429, 500, 502, 503, 504}
            print(
                f"[CLAUDE-API] HTTP {exc.code} after {elapsed:.1f}s "
                f"on attempt {attempt}: {body[:500]}"
            )
            last_error = RuntimeError(
                f"Anthropic HTTP {exc.code}: {body[:500]}"
            )
            if not retryable or attempt >= MAX_REQUEST_ATTEMPTS:
                raise last_error
        except urllib.error.URLError as exc:
            elapsed = time.time() - start_time
            print(
                f"[CLAUDE-API] Network failure after {elapsed:.1f}s "
                f"on attempt {attempt}: {exc}"
            )
            last_error = RuntimeError(f"Anthropic network error: {exc}")
            if attempt >= MAX_REQUEST_ATTEMPTS:
                raise last_error

        time.sleep(float(attempt))
    else:
        raise last_error or RuntimeError("Anthropic request failed")

    for block in raw.get("content", []):
        if isinstance(block, dict) and block.get("type") == "tool_use":
            data = block.get("input") or {}
            return {
                key: _clean_structured_value(data.get(key, ""))
                for key in properties.keys()
            }

    raise RuntimeError(
        f"No tool_use block returned by Claude. Raw keys: {list(raw.keys())}"
    )


def ordinal(value: Any) -> str:
    try:
        number = int(round(float(value)))
    except Exception:
        return "unavailable"
    suffix = (
        "th"
        if 10 <= number % 100 <= 20
        else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    )
    return f"{number}{suffix}"


def join_labels(values: List[str]) -> str:
    values = [str(value) for value in values if value]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def display_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "this assessment date"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%-d %B %Y")
    except Exception:
        return text[:10] if "T" in text else text
