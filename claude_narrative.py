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
import time
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

    # Run all calls sequentially for stability and predictability.
    # Each call can optionally use narrative_blocks from prior calls as context.
    
    # Call 1: Profile Narrative
    try:
        blocks = generate_profile_narrative(report_data, api_key)
        report_data["narrative_blocks"].update(blocks)
        status["calls"]["profile_narrative"] = "success"
    except Exception as e:
        print(f"[CLAUDE] profile_narrative failed: {e}")
        traceback.print_exc()
        status["calls"]["profile_narrative"] = f"failed: {str(e)}"

    # Call 2: Distinctive and Perception Narrative
    try:
        blocks = generate_distinctive_and_perception_narrative(report_data, api_key)
        report_data["narrative_blocks"].update(blocks)
        status["calls"]["distinctive_and_perception"] = "success"
    except Exception as e:
        print(f"[CLAUDE] distinctive_and_perception failed: {e}")
        traceback.print_exc()
        status["calls"]["distinctive_and_perception"] = f"failed: {str(e)}"

    # Call 3: Trajectory Narrative
    try:
        blocks = generate_trajectory_narrative(report_data, api_key)
        report_data["narrative_blocks"].update(blocks)
        status["calls"]["trajectory"] = "success"
    except Exception as e:
        print(f"[CLAUDE] trajectory failed: {e}")
        traceback.print_exc()
        status["calls"]["trajectory"] = f"failed: {str(e)}"

    # Call 4: Human Capital Narrative
    try:
        blocks = generate_human_capital_narrative(report_data, api_key)
        report_data["narrative_blocks"].update(blocks)
        status["calls"]["human_capital"] = "success"
    except Exception as e:
        print(f"[CLAUDE] human_capital failed: {e}")
        traceback.print_exc()
        status["calls"]["human_capital"] = f"failed: {str(e)}"

    # Call 5: Deep Dive Narrative
    try:
        blocks = generate_deep_dive_narrative(report_data, api_key)
        report_data["narrative_blocks"].update(blocks)
        status["calls"]["deep_dive"] = "success"
    except Exception as e:
        print(f"[CLAUDE] deep_dive failed: {e}")
        traceback.print_exc()
        status["calls"]["deep_dive"] = f"failed: {str(e)}"

    # Call 6: Closing Reflection Narrative
    try:
        blocks = generate_closing_reflection_narrative(report_data, api_key)
        report_data["narrative_blocks"].update(blocks)
        status["calls"]["closing_reflection"] = "success"
    except Exception as e:
        print(f"[CLAUDE] closing_reflection failed: {e}")
        traceback.print_exc()
        status["calls"]["closing_reflection"] = f"failed: {str(e)}"

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
The purpose of this section is not simply to describe what stands out.

Its purpose is to immediately demonstrate that the report genuinely understands this person's relationship with AI.

Each finding should answer four questions:

• What stands out?
• Why does it matter?
• What does it reveal about their relationship with AI?
• Why is this one of the defining characteristics of their overall profile?

Avoid simply describing benchmark differences. Always connect observations back to the participant's wider relationship with AI.

This is the first personalised interpretation the reader sees. It must make the reader feel the report has actually analysed their pattern.

Write 330-430 words total.
Use exactly three short editorial subheadings, each followed by one substantial paragraph.
Write the subheadings as plain text only. Do not wrap subheadings in Markdown bold markers such as **Heading** and do not prefix them with #, ##, or ###.
Do not use boxes, bullets, numbering, labels like "Behavioural finding", or fields such as "Data:" / "Interpretation:" / "Why it matters:".

The three subheadings should cover:
1. The strongest organising feature of the participant's profile. This will usually be their most distinctive signal, but its purpose is to explain why this feature shapes the wider behavioural pattern rather than simply describing an extreme score.
2. How the participant's self-understanding compares with the benchmark. Where differences exist, frame them as insight rather than correction. Where alignment exists, explain why accurate self-awareness is itself meaningful.
3. The overall shape emerging across the participant's profile. If a rare combination exists, use it as the organising example. If not, explain the wider behavioural pattern that best characterises the participant. The purpose is to introduce the relationship that the remainder of the report will gradually unpack.

Each paragraph should naturally conclude by explaining why this observation matters within the participant's broader relationship with AI.
Avoid ending on statistics or description.
End on meaning.

Assume later sections will provide detailed evidence.
This opening should introduce the participant to the overall story of their relationship with AI, not attempt to fully explain it.

Also write profile_shape_summary as one separate 50-80 word paragraph for the later section titled "The Shape of Your Profile". This paragraph should answer: "What does this profile look like?" Keep it visual, concise, and descriptive rather than analytical. Summarise the overall shape created by all nine dimensions without explaining why the shape exists. Do not repeat the opening findings. Do not discuss every dimension individually. Describe whether the profile is concentrated around a few defining signals or broadly aligned with the benchmark population. Avoid percentages and percentile language. Do not drift into Behaviour Story; later sections will explain why these dimensions appear together.

For rare_combinations_narrative, write the narrative for the section titled "What Makes You Different".
Keep the existing deterministic combination selection as the source of truth.
If rare combinations exist, focus the narrative almost entirely on the strongest combination.
Other detected combinations may be mentioned briefly only where they genuinely strengthen the interpretation.
Do not try to explain every detected combination equally.

Make the participant the centre of the narrative from the beginning.
Use this flow naturally:
1. Start with what is unusual about this participant's combination.
2. Give brief benchmark context in approximately one paragraph.
3. Spend the largest part of the narrative explaining how this participant departs from the usual pattern.
4. Explain what the combination appears to signal about their relationship with AI.
5. End with one concise synthesis explaining why this combination is one of the defining features of their wider profile.

Assume the participant already understands what the individual dimensions mean from earlier sections.
Do not spend significant time re-explaining Thought Partnership, Emotional Regulation, Human Agency, or other dimensions individually.
Focus on the interaction between dimensions rather than defining each dimension again.

Reduce benchmark exposition, academic explanation, repeated dimension explanation, and lengthy theoretical discussion.
Use plain behavioural language.
Do not use Markdown, bold markers, headings with #, or shorthand such as %ile.
Prefer careful signalling language such as "This appears to signal...", "This pattern often reflects...", and "This combination suggests...".
Avoid certainty language such as "This proves..." or "This demonstrates...".
Do not give advice, predict future behaviour, introduce strengths or shadows, discuss worth protecting, human capability, future monitoring, or observation guidance.
The participant should finish this section understanding what makes their relationship with AI genuinely different from most people and why that distinction matters, without being told what to do.

For behaviour_story, write the narrative centre of the report: an observational behavioural story, not a dramatic narrative.
This section should answer: "What kind of relationship with AI is emerging, and why do these patterns exist together?"
Write approximately 450 words total, in 4-5 flowing paragraphs, with no internal headings or bullets.
Open with one concise paragraph describing the participant's overall relationship with AI. Begin with the participant's story, not with dimensions, scores, or mechanics.
Treat dimensions as evidence for the story, not the story itself.
Assume earlier sections have already introduced the dimensions. Briefly reference Thought Partnership, Human Agency, Reliance, Emotional Regulation, Trust, Verification, Disclosure, or Social Transparency only when needed to explain how the pattern works.
Do not re-teach individual dimensions. Do not try to cover every dimension. Do not list all nine dimensions. Do not restate the dashboard.
Explain the 2-3 behavioural mechanisms that best account for the profile. Focus on behavioural boundaries, interaction style, trust dynamics, reliance patterns, cognitive structure, and how these elements appear to sustain the overall relationship with AI.
Where supported by the context, surface hidden patterns that may sit beneath the benchmark scores, such as quiet normalisation, perception gaps, subtle tensions, invisible behavioural shifts, or the difference between visible use and underlying dependence.
Use HCI research as supporting evidence, not as the main subject of the section. Suitable phrasing includes "Across HCI's benchmark studies...", "HCI's research consistently shows...", or "Looking across the measured behaviours..." but only where it adds clarity.
Avoid repeating comparisons already shown earlier in the report, such as age-group comparisons, everyday-user comparisons, or bare percentile rankings.
Do not use means, averages, statistical shorthand, or technical language.
Do not give advice, make recommendations, predict future behaviour, discuss what to protect, translate the profile into human capability or human capital language, add reflection questions, or introduce future trajectory.
End with one clear, memorable behavioural insight about the participant's relationship with AI. This should be a conclusion, not a teaser or transition.
The participant should finish this section thinking: "This explains the story my profile is telling."

Style the opening_findings subheadings like a premium research report, for example:
Your strongest organising feature
How your self-understanding compares
The shape of the wider pattern
Return those headings as plain lines only, not Markdown.

Use benchmark statistics sparingly.
Only include numbers when they strengthen understanding.
Never allow numbers to become the focus of the narrative.
Never use means, averages, standard deviations, effect sizes, raw score averages, or statistical shorthand that a general reader has to interpret. Do not write phrases such as "mean of 1.1" or "average of 4.4". If cohort differences matter, explain them in plain behavioural language, for example: "everyday AI users report higher reliance, but your pattern sits beyond that already-high group."

Tone:
- observational
- research-grounded
- plain English
- direct to "you"
- curious, not dramatic
- insightful rather than impressive
- avoid long academic explanations where one clear behavioural insight communicates the same idea
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
            "description": "330-430 word opening synthesis with exactly three short editorial subheadings, each followed by one substantial paragraph. Subheadings must be plain text lines only, with no Markdown bold markers and no # heading markers. No bullets, no numbering, no 'Behavioural finding', no Data/Interpretation/Why-it-matters labels, and no means/averages/statistical shorthand."
        },
        "profile_shape_summary": {
            "type": "string",
            "description": "50-80 word paragraph for The Shape of Your Profile. Describe what the overall profile looks like across all nine dimensions. Keep it visual and descriptive, do not explain why the shape exists, do not repeat the opening findings, do not list every dimension, and avoid percentages/percentiles."
        },
        "rare_combinations_narrative": {
            "type": "string",
            "description": "If rare combinations exist, focus the narrative almost entirely on the strongest combination in 300-420 words. Keep benchmark context brief, make the participant central, explain what the combination appears to signal and why it matters within the wider AI relationship. Mention other detected combinations only briefly if they strengthen the interpretation. If none exist, write 120-180 words explaining what no rare combo means."
        },
        "behaviour_story": {
            "type": "string",
            "description": "Approximately 450 word behavioural story in 4-5 flowing paragraphs. Begin with the participant's overall relationship with AI, treat dimensions as evidence rather than the story, explain the 2-3 mechanisms that make the profile coherent, surface hidden patterns where supported, use HCI research lightly as support, avoid dashboard repetition, no predictions, no advice, no capability translation, no future trajectory."
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
- This section is titled "Your Most Distinctive Responses" and its job is validation, not new interpretation.
- The cards already show the dimension, question, participant response, percentile, and benchmark comparison. The narrative should explain why each response is important evidence supporting the participant's overall benchmark profile.
- Assume the participant has already read the Behaviour Story and earlier benchmark sections. Treat those conclusions as established; do not repeat or expand them.
- You MUST explain all 7 distinctive responses provided.
- Write exactly 7 concise evidence annotations, one per response.
- Each annotation must be 25-50 words, usually 1-2 sentences. Be strict: do not write mini-essays.
- Do NOT write an introductory paragraph. The renderer already provides the section introduction.
- Do NOT use Markdown, bold markers, bullets, numbered lists, tables, or headings with **.
- Do NOT use raw variable names or codes such as del_q3, agency_q1, trust_q3, rel_q1.
- Start each annotation with a short plain-language evidence label, followed by a colon. Use natural labels such as "Trusting AI accuracy:" or "Hiding AI use socially:" rather than copying the full question every time.
- For each response, explain only:
  1. why the response is statistically distinctive,
  2. how it supports the participant's overall benchmark profile.
- Do not redefine behavioural dimensions such as Human Agency, Trust, Reliance, Verification, or Thought Partnership. Reference the dimension only when necessary.
- Do not introduce new interpretations, repeat the Behaviour Story, provide coaching, recommend actions, discuss human capability, future guidance, Human Capital, worth protecting, strengths, shadows, or observation guidance.
- Avoid repeating the dashboard, age-group comparisons, frequency comparisons, or multiple statistics. The card already shows answer and benchmark position.
- Keep the writing concise, evidence-based, confidence-building, highly readable, and participant-focused.

For Section 8:
- This section is now titled "How You See Yourself". Write the narrative for the heading "What this comparison suggests".
- This section exists to compare the participant's self-perception with their measured benchmark profile. Its purpose is reflection rather than interpretation.
- Write exactly four concise paragraphs, 190-240 words total.
- Focus on helping the participant understand where their intuition aligns with the benchmark and where the benchmark provides additional perspective.
- Treat the benchmark as complementary to the participant's own understanding rather than replacing it.
- Paragraph 1 must begin by summarising self-perception using the phrase "You described yourself as" or a close natural variation.
- Paragraph 2 must explain benchmark positioning using the phrase "The benchmark places you" or a close natural variation.
- Paragraph 3 must focus on alignment, difference, and perspective. Do not explain mechanisms or why the pattern exists.
- Paragraph 4 must be a reflective closing synthesis. Prefer this intent: "The benchmark does not replace your own understanding of yourself. It simply provides a perspective that is difficult to see from the inside. Together, your self-perception and the benchmark offer a more complete picture of your relationship with AI." Adapt only as needed to match the data.
- Compare self-perception to benchmark positioning.
- Frame gaps as illuminating, not corrective.
- Never say "you were wrong".
- If alignment is strong, explain why accurate self-perception matters.
- Avoid long behavioural explanations, research summaries, mechanism explanations, or heavy-user generalisations. Those belong in other sections.
- Avoid repeating the same dimension label sentence after sentence. Vary language naturally with phrases such as AI relationship, AI engagement, behavioural profile, benchmark positioning, self-view, measured pattern, and interaction with AI.
- Separate data from reflection: assume the renderer has already shown the card data and comparison table, so do not restate every card.
- Do not introduce Behaviour Story, future discussion, Human Capital, worth protecting, advice, recommendations, or coaching.

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
            "description": "Exactly 7 concise evidence annotations, 25-50 words each. No introductory paragraph, no Markdown, no bold markers, no bullets, no numbering, no variable IDs. Each annotation should explain why the response is statistically distinctive and how it supports the participant\'s overall benchmark profile, without redefining dimensions or adding advice."
        },
        "perception_gap_narrative": {
            "type": "string",
            "description": "Exactly four concise paragraphs, 190-240 words total, for Section 8's 'What this comparison suggests'. Reflect on how self-perception aligns with benchmark positioning and where the benchmark adds perspective. Treat the benchmark as complementary, not corrective. Avoid mechanism explanation, research exposition, advice, future discussion, and Human Capital framing."
        },
    }

    return call_claude_structured(api_key, prompt, schema)


# ---------------------------------------------------------------------
# Call 3: Section 10
# ---------------------------------------------------------------------

def generate_trajectory_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    context = build_context_for_claude_section(report_data, "trajectory")

    prompt = f"""
Write HCI report Section 11 narrative blocks for the redesigned section: "Looking Ahead".

This section replaces the old "Trajectory / If Nothing Changes" section.
Its job is not to interpret the participant again, predict their future, or repeat Human Capital.
Its job is to turn the report into a measurement roadmap.

The section answers one question:
What will be most interesting to measure next time?

Write only these blocks:
- looking_ahead_intro
- behavioural_tipping_points
- measurement_questions

The renderer will deterministically display these fixed subsections:
1. Signals Likely to Hold
2. Signals Most Sensitive to Change
3. Behavioural Tipping Points
4. Questions for Your Next Measurement

Do not create extra sections.
Do not mention "Why Return" because later report sections already handle the longitudinal meaning and closing reflection.
Do not write an overall outlook.
Do not write "Commonly observed", "Strengths That May Continue Developing", "Areas Worth Monitoring", or an at-a-glance table.

For looking_ahead_intro:
- Write 80-120 words in 1-2 paragraphs.
- Explain that the profile is a snapshot, not a verdict or fixed identity.
- Explain that the value of measuring again is not chasing better scores; it is noticing whether the behavioural architecture remains stable or begins to shift.
- Use plain, direct language.
- Do not summarise the full profile again.
- Do not give advice.

For behavioural_tipping_points:
- Write exactly three tipping points.
- Format each as: Short heading: one concise explanation.
- Separate each tipping point with a blank line.
- Each explanation should describe a real-world behavioural shift that may precede measurable score change.
- Use these three concepts unless the context strongly requires a different wording:
  1. Earlier AI initiation — AI becomes the first place thinking begins rather than a place to refine an existing view.
  2. Reduced verification friction — checking starts to feel less necessary because AI feels fluent, familiar, or usually right.
  3. Expanding role boundaries — AI begins entering areas of work, decision-making, or personal life where it previously played little role.
- Keep this observational, not alarming.
- Do not say these changes will happen.

For measurement_questions:
- Write exactly five questions.
- Put each question on its own line.
- Do not use bullets, numbering, or Markdown.
- Questions should be specific enough that the participant can compare their behaviour at the next measurement.
- Focus on noticing change, not judging whether change is good or bad.
- Include at least one question about whether they form an independent view before using AI.
- Include at least one question about verification.
- Include at least one question about whether AI has entered more areas of life or work.
- Include at least one question about boundaries.

Rules:
- No predictions.
- No coaching.
- No recommendations.
- No urgency.
- No alarmism.
- No "you should".
- No optimisation language.
- No clinical language.
- No moral judgement about high or low scores.
- Do not repeat the Human Capital section.
- Do not re-explain the profile.
- Do not include percentages or statistics unless absolutely necessary.
- Prefer measurement language: observe, compare, notice, re-measure, next measurement, behavioural architecture, signals.
- Tone: premium, concise, scientifically disciplined, practical, HCI-specific.

The participant should finish this section thinking:
"I know what to pay attention to between now and my next measurement."

Use only this context:
{compact_context(context)}
"""

    schema = {
        "looking_ahead_intro": {
            "type": "string",
            "description": "80-120 words. Introduce Looking Ahead as a measurement roadmap: profile as snapshot, next measurement as a way to notice whether behavioural architecture holds or shifts. No advice, no prediction, no full profile summary."
        },
        "behavioural_tipping_points": {
            "type": "string",
            "description": "Exactly three tipping points, each formatted 'Short heading: one concise explanation', separated by blank lines. Observational real-world behavioural shifts only. No prediction or alarmism."
        },
        "measurement_questions": {
            "type": "string",
            "description": "Exactly five questions, one per line, no bullets or numbering. Questions for the next measurement focused on independent view formation, verification, expanding AI role, boundaries, and unnoticed change."
        },
    }

    return call_claude_structured(api_key, prompt, schema)



# ---------------------------------------------------------------------
# Call 4: Section 9 Human Capital
# ---------------------------------------------------------------------

def generate_human_capital_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    context = build_context_for_claude_section(report_data, "human_capital")

    prompt = f"""
Write HCI report Section 9: "Your Human Capital".

This is a translation section, not an interpretation section, not a benchmark section, and not advice.
Its job is to translate the participant's behavioural benchmark profile into the human capabilities their current relationship with AI appears to support, maintain, or gradually influence.

Core question:
"What does my current relationship with AI appear to be building, preserving, or gradually changing within me?"

Use the complete participant context, including dimension scores, question-level evidence, rare combinations, Behaviour Story, distinctive responses, Profile Shape, Perception Gap, usage frequency, demographics where relevant, and HCI signals.

The section must feel human, concise, and evidence-led.
It should not primarily talk about AI, scores, dimensions, percentiles, or benchmark mechanics.
It should translate measured behavioural evidence into human capabilities.

Return exactly these fields:
- capabilities_developing
- worth_protecting
- worth_watching
- human_capital_priorities
- human_capital_closing

Output requirements:
1. capabilities_developing
   - Exactly 3 items.
   - Each item has:
     - title
     - body
   - Title: a plain human capability, 2-6 words.
   - Body: 40-60 words.
   - Explain why this capability appears to be actively exercised or developing, what behavioural evidence supports it, and why it matters.
   - Do not call these "strengths".

2. worth_protecting
   - Exactly 3 items.
   - Each item has:
     - title
     - body
   - Title: a plain human capability, 2-6 words.
   - Body: 40-60 words.
   - Identify capabilities that appear central to how this participant currently works with AI and seem valuable to preserve as the relationship evolves.
   - These are not necessarily the highest scores.

3. worth_watching
   - Exactly 3 items.
   - Each item has:
     - title
     - body
   - Title: a plain human capability, 2-6 words.
   - Body: 40-60 words.
   - Identify capabilities that naturally deserve observation over time.
   - These are not weaknesses, risks, warnings, or problems to solve.
   - Explain why they are worth watching without creating anxiety.

4. human_capital_priorities
   - Exactly 3 items.
   - Each item has:
     - title
     - body
   - Title: short, concrete, human, 2-5 words.
   - Body: approximately 30 words.
   - These are the three capabilities that best capture this participant's Human Capital today.
   - They should be memorable and suitable for a visually prominent summary block.

5. human_capital_closing
   - 80-120 words.
   - Use this intent:
     Human capabilities rarely change all at once. More often they evolve gradually through repeated habits and everyday interactions. This benchmark provides a starting point for understanding that journey, not a final judgement about where it leads. The value comes from returning over time and observing how these capabilities continue to develop.
   - Tailor lightly to the participant's profile without giving advice.

Writing rules:
- Translate behaviour into capability.
- Use plain human language.
- Stay directly traceable to evidence elsewhere in the report.
- Use cautious language: "appears", "suggests", "currently", "may", "seems".
- Avoid inflated or aspirational claims.
- Do not invent qualities unsupported by the participant's data.
- Do not mention percentiles.
- Do not mention dimension names.
- Do not mention raw scores.
- Do not use benchmark jargon.
- Do not repeat the Behaviour Story.
- Do not give behavioural advice.
- Do not predict future outcomes.
- Do not judge behaviour.
- Do not use "you should", "try", "consider", or coaching language.
- Do not introduce Looking Forward content, observation cards, reflection questions, strengths/shadows, or recommendations.

The participant should finish this section thinking:
"I now understand what my benchmark profile means for me as a person — not just how I compare with other people."

Use only this context:
{compact_context(context, max_chars=30000)}
"""

    capability_item_schema = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Plain human capability title."
            },
            "body": {
                "type": "string",
                "description": "Evidence-led translation of the capability."
            },
        },
        "required": ["title", "body"],
        "additionalProperties": False,
    }

    schema = {
        "capabilities_developing": {
            "type": "array",
            "description": "Exactly 3 capabilities currently developing. No dimensions, scores, percentiles, advice, or benchmark jargon.",
            "minItems": 3,
            "maxItems": 3,
            "items": capability_item_schema,
        },
        "worth_protecting": {
            "type": "array",
            "description": "Exactly 3 capabilities worth protecting. No dimensions, scores, percentiles, advice, or benchmark jargon.",
            "minItems": 3,
            "maxItems": 3,
            "items": capability_item_schema,
        },
        "worth_watching": {
            "type": "array",
            "description": "Exactly 3 capabilities worth watching over time. Not risks, warnings, weaknesses, or advice.",
            "minItems": 3,
            "maxItems": 3,
            "items": capability_item_schema,
        },
        "human_capital_priorities": {
            "type": "array",
            "description": "Exactly 3 concise Human Capital priorities with short bodies suitable for a visually prominent summary block.",
            "minItems": 3,
            "maxItems": 3,
            "items": capability_item_schema,
        },
        "human_capital_closing": {
            "type": "string",
            "description": "80-120 word closing paragraph. Reflective, human, non-prescriptive, no predictions or advice.",
        },
    }

    blocks = call_claude_structured(api_key, prompt, schema)
    if isinstance(blocks, dict) and "human_capital_closing" in blocks and "closing" not in blocks:
        blocks["closing"] = blocks.get("human_capital_closing")
    return {"human_capital": blocks}



# ---------------------------------------------------------------------
# Call 5: Final Deep Dive
# ---------------------------------------------------------------------

def generate_deep_dive_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, str]:
    context = build_context_for_claude_section(report_data, "deep_dive")

    prompt = f"""
Write the HCI report section titled "Dimension Deep Dives".

This section exists to help the participant understand each behavioural dimension in greater depth.
Its purpose is exploration, not overall interpretation.
Assume the participant has already read the earlier sections of the report.
Do not re-establish the overall story of the profile.
Your job is to help them explore each HCI behavioural dimension with more nuance and context than earlier sections provided.

Write a reference-style explanation of the participant's HCI dimensions.
For each dimension included in the context, stay focused on that dimension only.

Each dimension entry should naturally answer exactly four questions:
1. What does this dimension measure?
2. Where does the participant sit?
3. What does this typically look like behaviourally?
4. Why does understanding this dimension matter?

Structure:
- Use the dimension name as a plain heading.
- Do not prefix dimension headings with #, ##, ###, bold markers, or any Markdown syntax.
- Do not insert horizontal separators such as --- between dimension entries.
- Under each heading, write 3-4 concise paragraphs.
- Keep each dimension entry clear, educational, and scannable.
- The full section should feel like a high-quality reference manual for the participant's behavioural dimensions, not another Behaviour Story.
- Do not make every entry dramatic or memorable. Make it reliable, precise, useful, and easy to understand.

Content rules:
- Use the participant's benchmark position as context.
- Use HCI research and signals only where they help explain the dimension more deeply.
- Include behavioural examples where useful.
- Explain what higher, lower, or benchmark-range positioning typically looks like for that dimension.
- Increase understanding of the construct rather than repeating basic definitions from earlier sections.
- Stay focused on one dimension at a time.
- Briefly mention the wider profile only if absolutely necessary for context.

Do not:
- Re-explain the participant's Behaviour Story.
- Summarise the overall profile.
- Explain how multiple dimensions interact.
- Repeat conclusions already established earlier in the report.
- Introduce Human Capital, human capability, worth protecting, strengths/shadows, future trajectory, monitoring, advice, behavioural recommendations, or reflection questions.
- Use future language such as "over time", "as AI develops", "watch for", "this may become", or "long term".
- Use coaching language such as "consider", "try", "you should", or "it may help".
- Use Markdown formatting, bold markers, bullet lists, numbered lists, or horizontal rules such as ---.
- Diagnose, prescribe, alarm, or exaggerate uniqueness.

End each dimension entry with one short concluding paragraph explaining why that dimension is useful to understand as one part of the participant's relationship with AI.
The ending should be consistent in purpose across dimensions, but not identical in wording.
A suitable style is: "This dimension provides one perspective on your relationship with AI. Like every HCI dimension, it is most meaningful when interpreted alongside the rest of your benchmark profile."

Tone:
- exploratory
- educational
- research-grounded
- direct to "you"
- plain English
- professional
- not dramatic
- not self-help
- not prescriptive

Use only this context:
{compact_context(context, max_chars=32000)}
"""

    schema = {
        "deep_dive": {
            "type": "string",
            "description": "Dimension Deep Dives section. Reference-style explanations for the HCI dimensions in the context. Each dimension should use a plain heading and answer what it measures, where the participant sits, what it typically looks like, and why understanding it matters. Exploration only; no overall profile synthesis, no advice, no future trajectory, no Human Capital framing."
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
# Call 6: Closing Reflection
# ---------------------------------------------------------------------

def build_closing_reflection_context(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build compact whole-report context for the final Closing Reflection.

    This intentionally uses the completed report_data and narrative_blocks rather
    than asking Claude to generate new evidence. The final section should distil
    the report into one enduring question and a hopeful conclusion.
    """
    narrative_blocks = report_data.get("narrative_blocks") or {}
    synthesis_inputs = report_data.get("synthesis_inputs") or {}

    return {
        "section_purpose": (
            "Distil the completed HCI report into one enduring question and one "
            "calm, hopeful closing reflection. This is reflection, not advice."
        ),
        "profile": {
            "session_id": report_data.get("session_id"),
            "demographics": report_data.get("demographics", {}),
            "usage_frequency": (report_data.get("demographics") or {}).get("ai_tool_use_frequency")
                or (report_data.get("demographics") or {}).get("frequency"),
        },
        "benchmark_overview": {
            "top_dimensions": synthesis_inputs.get("top_dimensions", []),
            "lowest_dimensions": synthesis_inputs.get("lowest_dimensions", []),
            "most_distinctive_variable": synthesis_inputs.get("most_distinctive_variable"),
            "largest_perception_gap": synthesis_inputs.get("largest_perception_gap"),
            "top_rare_combination": synthesis_inputs.get("top_rare_combination"),
        },
        "profile_shape": report_data.get("typicality", {}),
        "rare_combinations": report_data.get("rare_combinations", []),
        "distinctive_responses": (report_data.get("distinctive_responses") or [])[:7],
        "perception_gap": report_data.get("perception_gap", {}),
        "human_capital_inputs": report_data.get("human_capital", {}),
        "trajectory_inputs": report_data.get("if_nothing_changes", {}),
        "looking_forward_inputs": report_data.get("looking_forward") or report_data.get("what_to_protect", []),
        "completed_narrative_blocks": {
            "opening_findings": narrative_blocks.get("opening_findings"),
            "profile_shape_summary": narrative_blocks.get("profile_shape_summary"),
            "rare_combinations_narrative": narrative_blocks.get("rare_combinations_narrative"),
            "behaviour_story": narrative_blocks.get("behaviour_story"),
            "distinctive_responses_narrative": narrative_blocks.get("distinctive_responses_narrative"),
            "perception_gap_narrative": narrative_blocks.get("perception_gap_narrative"),
            "human_capital": narrative_blocks.get("human_capital"),
            "likely_to_continue": narrative_blocks.get("likely_to_continue"),
            "overall_outlook": narrative_blocks.get("overall_outlook"),
            "deep_dive": narrative_blocks.get("deep_dive"),
        },
        "writing_rules": [
            "Do not introduce new evidence.",
            "Do not give advice or recommendations.",
            "Do not predict outcomes.",
            "The personalised question must be answerable only over time, not today.",
            "End with the participant's ongoing measurement journey, not with promotion.",
        ],
    }


def generate_closing_reflection_narrative(report_data: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    context = build_context_for_claude_section(report_data, "closing_reflection")

    prompt = f"""
Write HCI report Section 12: "Closing Reflection".

Primary job:
Reflection and inspiration. This section concludes the participant's journey. It should not introduce new evidence, recommendations, coaching, predictions, or action steps. It should help the participant step back from the benchmark and consider the broader meaning of their relationship with AI.

Core question for this section:
Why is continuing to understand my relationship with AI worthwhile?

Distil the participant's entire benchmark profile into one meaningful question and one thoughtful conclusion. The participant should finish feeling understood, curious, hopeful, and motivated to continue observing their relationship with AI over time.

Return exactly one object under these fields:
- one_question
- why_this_question_matters
- what_will_be_interesting_next_time
- closing_reflection

Output requirements:

1. one_question
- Exactly one question.
- Approximately 15-30 words.
- It must emerge naturally from the complete benchmark profile.
- It should summarise the deepest tension, opportunity, or curiosity revealed by the report.
- It should feel personal, memorable, emotionally resonant, evidence-based, and unresolved.
- It must not be answerable today; it should become more meaningful as time passes.

2. why_this_question_matters
- 80-120 words.
- Explain why this question fits this participant.
- Connect it directly to the overall behavioural pattern already established in the report.
- Explain why it is worth carrying forward.
- Do not give advice, instructions, or motivation.

3. what_will_be_interesting_next_time
- 100-120 words.
- Bridge today's benchmark with future measurement.
- Explain that the value of returning is not simply comparing scores, but discovering how the participant's relationship with AI has evolved.
- Include that behavioural change is usually gradual and that relationships with AI naturally evolve.
- Include an explicit, gentle recommendation to return in around six months.
- Include the carry-forward principle: this report does not ask the participant to carry forward another rule or recommendation; it asks them to carry forward one question. Over time, that question becomes a lens through which they may notice how their relationship with AI continues evolving.

4. closing_reflection
- 180-250 words.
- Finish the report with perspective, not findings or recommendations.
- Begin with a brief looking-back moment. Use this idea naturally: "You've now seen where your relationship with AI sits today, what makes it distinctive, which human capabilities appear most important, and what is worth paying attention to as that relationship continues evolving."
- Then transition naturally to: one question remains.
- Widen the lens beyond today's benchmark.
- Reinforce human agency, curiosity, intentional AI use, and human flourishing.
- Explain that AI will continue evolving, human relationships with AI will continue evolving, and there is no single correct way to use AI.
- The value lies in remaining aware of how that relationship changes.
- Mention Human Clarity Institute only if it feels natural and non-promotional. If mentioned, use this meaning: HCI exists to help people measure, understand, and protect the human capabilities that continue shaping their relationship with AI over time.
- End with the participant, not the organisation. Do not include the report's final standalone sentence here; the renderer adds it after this paragraph.

Profile-dependent reassurance rule:
- If the participant demonstrates evidence of strong retained agency, authorship, or identity stability, the closing may acknowledge that as one reassuring feature of the profile.
- If the evidence does not support that, do not mention identity stability or retained agency as a reassurance.

Writing rules:
- Be personal, calm, evidence-led, hopeful, and reflective.
- Encourage curiosity, agency, and longitudinal measurement.
- Do not introduce new evidence.
- Do not summarise the whole report mechanically.
- Do not give advice.
- Do not predict outcomes.
- Do not use fear, urgency, or coaching language.
- Do not sound promotional.
- Do not repeat earlier sections.
- Do not say "you should", "try", "make sure", or "the next step is".
- Avoid generic motivational language.
- Use direct plain English.

The participant should finish thinking:
"I understand my relationship with AI. I know what is worth paying attention to. I have one meaningful question to carry forward. I'm curious to discover how my relationship changes over time."

Use only this completed-report context:
{compact_context(context, max_chars=34000)}
"""

    schema = {
        "one_question": {
            "type": "string",
            "description": "Exactly one personalised evidence-based question, 15-30 words, unresolved and meaningful over time.",
        },
        "why_this_question_matters": {
            "type": "string",
            "description": "80-120 words explaining why the question fits the participant's established benchmark profile. No advice or new evidence.",
        },
        "what_will_be_interesting_next_time": {
            "type": "string",
            "description": "100-120 words connecting the question to future measurement and a gentle return in around six months. No coaching or prediction.",
        },
        "closing_reflection": {
            "type": "string",
            "description": "180-250 word final reflection with looking-back transition, agency, curiosity, and HCI purpose if natural. Do not include the final standalone sentence; the renderer adds it.",
        },
    }

    blocks = call_claude_structured(api_key, prompt, schema)
    return {"closing_reflection": blocks}



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
            cleaned = {}
            for k in properties.keys():
                value = data.get(k, "")
                if isinstance(value, str):
                    cleaned[k] = clean_narrative_text(value.strip())
                else:
                    cleaned[k] = value
            return cleaned

    raise RuntimeError(f"No tool_use block returned by Claude. Raw keys: {list(raw.keys())}")
