"""report_sections.py - deterministic locked report sections from canonical report_data."""
from report_data_builder import DIMENSION_LABELS, DIMENSION_DEFINITIONS, DIMENSION_ORDER, ordinal, protect_position_phrase

OPENING_STATEMENT = """You are uniquely positioned in how you relate to AI. Your profile reflects how you currently engage with AI systems — based on your responses benchmarked against 10,500 participants across 21 research studies.

Use this report to understand your pattern:

• Understand what's distinctive about how you work with AI
• Notice where you're typical and where you stand out
• Explore what's worth protecting as your use evolves
• Make conscious choices about your relationship with AI going forward"""

NEXT_STEPS = [
    {"title":"Step 1: Test This Report With Your AI","body":["Upload this full report to whichever AI you use most.",'Ask it: "Does this report ring true to how we work together? Where does it match your sense of how I use you? Where does it miss?"',"Listen for where it confirms vs. where it challenges. This conversation will deepen your clarity about your actual pattern.","A note: Your data stays with you. Nothing about this conversation returns to HCI."]},
    {"title":"What This Awareness Does","body":["Knowing your pattern is the foundation for clarity. And clarity is what lets you make intentional choices about your boundaries with AI.","This report shows you where you sit — how you use AI, what you rely on it for, where you're distinctive, where you're typical. That positioning is neutral. What matters is what you do with it.","The people who flourish with AI are the ones who stay aware of their own pattern and adjust their relationship as it evolves. Not through willpower or rules, but through genuine understanding of what serves them."]},
    {"title":"Stay Within Your Boundaries","body":["Return to this assessment periodically — quarterly, annually, or whenever your relationship with AI feels like it's shifting significantly.","Retesting lets you notice what's actually changed in your pattern, not what you think has changed. It's the clearest way to stay within the boundaries that help you flourish."]},
    {"title":"This Report As A Mirror","body":["This report is a mirror. What it shows is real — your positioning in a benchmark population, your rare combinations, your observable patterns.","What you do with that clarity is entirely yours."]},
]

WHAT_TO_PROTECT_TEMPLATES = {
    "verification": {"title":"What to Notice: When Verification Becomes Tiring","intro":"Most people verify AI outputs before acting. But the research reveals something important: constant verification can become cognitively costly, and many people move toward selective checking — checking only what feels high-risk or important.","watch":["Noticing yourself checking less than usual","Feeling relief or efficiency when you skip verification","Finding it hard to care whether an output is accurate",'Moving from "verify everything" to "verify selectively" without realizing it'],"research":"Verification fatigue is real and common. It is not laziness — it is the cost of constant cognitive effort. The question worth noticing is whether your verification rhythm serves your needs, or whether you are rationing it because it is exhausting.","closing":"You decide what level of verification matters to you."},
    "human_agency": {"title":"What to Notice: When Drift Happens Without You Choosing It","intro":"Research shows an interesting contrast: at the identity level, agency is often strong — people retain a clear sense of responsibility for their decisions. But at the process level, subtle steering can still happen through AI suggestions, defaults, and framing.","watch":["Accepting AI suggestions without thinking them through first","Using AI defaults instead of customizing your approach","Realizing you have not actually made a decision yourself in days","Noticing AI's framing has become your first instinct","Finding it harder to develop your own position before consulting AI"],"research":"Drift happens through convenience, not collapse. You are not losing agency overnight — you are losing it incrementally through small moments where the path of least resistance happens to align with what AI suggests.","closing":"You decide if this matters to you."},
    "emotional_regulation": {"title":"What to Notice: If Emotional Reliance Becomes Substitution","intro":"This is one of the most live tensions in HCI's research. Many people still believe only humans can truly meet emotional needs, while a growing share already use AI for relief, support, or emotional processing.","watch":["Turning to AI before turning to people when you are struggling","Preferring AI conversations to human ones for processing difficult feelings","Finding it harder to sit with discomfort without AI input","Noticing you are more open with AI about emotions than with people you trust","Realizing emotional support from AI feels more available than human support"],"research":"This is not inherently a problem. For some people, AI offers a genuinely safe space that human relationships do not. But it is worth noticing the difference between AI as a supplement to human connection and AI as a replacement for it.","closing":"You decide if emotional support from AI is right for you."},
    "thought_partnership": {"title":"What to Notice: When Thinking With AI Becomes Thinking For You","intro":"AI works best as a thinking partner — something to develop ideas with, not instead of your own thinking. The important distinction is whether AI is challenging your thinking or quietly replacing it.","watch":["Defaulting to AI's framing instead of developing your own position first","Struggling to think independently when AI is not available","Realizing AI's suggestions have become your first instinct, not your second opinion","Finding it hard to disagree with AI once it has stated a position","Noticing you use AI to avoid the discomfort of thinking through hard problems alone"],"research":"Genuine partnership requires you to know what you think before you ask AI. The people who maintain clear authorship are the ones who use AI to challenge their thinking, not replace it. Values clarity is what keeps that distinction alive.","closing":"You decide if this matters to you."},
}

def nb(report_data, key, fallback=""):
    return (report_data.get("narrative_blocks") or {}).get(key) or fallback

def opening_fallback(report_data):
    inputs=report_data.get("synthesis_inputs",{})
    most=inputs.get("most_distinctive_variable"); gap=inputs.get("largest_perception_gap"); combo=inputs.get("top_rare_combination")
    ps=[]
    if most: ps.append(f"One striking feature of your profile is your response to: “{most.get('question_text')}”. You answered {most.get('answer_display')}, placing this response at the {most.get('percentile_label')} percentile.")
    else: ps.append("One striking feature of your profile is its overall coherence. No single response overwhelms the pattern, so the report is best read as a whole.")
    if gap: ps.append(f"Your largest perception gap appears around {gap.get('question')}. You described yourself as “{gap.get('perceived_answer')}”, while the benchmark places you around the {ordinal(gap.get('actual_percentile'))} percentile.")
    else: ps.append("Your self-perception broadly aligns with your benchmark positioning. That alignment suggests you are noticing your own AI pattern clearly.")
    if combo: ps.append(f"The most unusual combination detected is {combo.get('label_1')} + {combo.get('label_2')}. This combination appears in roughly {combo.get('rarity_percent')}% of participants.")
    else: ps.append("No rare dimensional combination was detected. This suggests your pattern is less defined by tension between dimensions and more by the overall shape of your scores.")
    return "\n\n".join(ps)

def behaviour_fallback(report_data):
    dims=sorted((report_data.get("dimensions") or {}).values(), key=lambda d:d.get("percentile",50), reverse=True)
    if not dims: return "No dimension data was available."
    top=dims[0]; low=sorted(dims, key=lambda d:d.get("percentile",50))[0]
    return f"Your relationship with AI is characterized primarily by {top['label'].lower()}. This dimension sits at the {ordinal(top['percentile'])} percentile, making it one of the clearest organising features in your profile.\n\nAt the other end, {low['label'].lower()} sits at the {ordinal(low['percentile'])} percentile. That contrast matters because HCI reports are not designed to label you as one type of user; they show the shape of your current pattern.\n\nWhat is worth noticing is not whether any score is good or bad, but how the dimensions sit together."

def build_sections(report_data):
    data=report_data.get("if_nothing_changes") or {}; high=data.get("highest_dimension") or {}; monitor=data.get("monitoring_anchor") or {}
    protect=[]; src={x["dimension"]:x for x in report_data.get("what_to_protect",[])}
    for dim,t in WHAT_TO_PROTECT_TEMPLATES.items():
        d=src.get(dim,{})
        protect.append({"dimension":dim,"label":DIMENSION_LABELS[dim],"definition":DIMENSION_DEFINITIONS[dim],"percentile":d.get("percentile"),"positioning":d.get("positioning") or protect_position_phrase(d.get("percentile")), **t})
    qgroups=[]
    for dim in DIMENSION_ORDER:
        qgroups.append({"dimension":dim,"label":DIMENSION_LABELS[dim],"definition":DIMENSION_DEFINITIONS[dim],"questions":[q for q in report_data.get("questions",[]) if q.get("dimension")==dim]})
    return {
        "opening":{"title":"Most Striking Finding","statement":OPENING_STATEMENT,"findings":nb(report_data,"opening_findings",opening_fallback(report_data))},
        "dashboard":{"title":"Your AI Behaviour Pattern","subtitle":"How you compare across nine dimensions","cards":report_data.get("dashboard",[])},
        "typicality":{"title":"How Typical Is Your AI Behaviour?", **(report_data.get("typicality") or {})},
        "rare":{"title":"What Makes You Different","combinations":report_data.get("rare_combinations",[])[:2],"narrative":nb(report_data,"rare_combinations_narrative"),"fallback":"No rare dimensional combinations were detected in your profile."},
        "story":{"title":"Your Behaviour Story","body":nb(report_data,"behaviour_story",behaviour_fallback(report_data))},
        "questions":{"title":"Your Question-Level Profile","subtitle":"How your individual responses compare","groups":qgroups},
        "distinctive":{"title":"Your Most Distinctive Responses","responses":report_data.get("distinctive_responses",[])[:7],"narrative":nb(report_data,"distinctive_responses_narrative")},
        "perception":{"title":"Perception Gap Analysis", **(report_data.get("perception_gap") or {}), "narrative":nb(report_data,"perception_gap_narrative")},
        "protect":{"title":"What To Protect","subtitle":"Four capacities worth noticing as your AI use evolves","items":protect},
        "trajectory":{"title":"If Nothing Changes","likely_to_continue":nb(report_data,"likely_to_continue", f"Based on your current pattern, {high.get('label','your strongest dimension')} is likely to remain one of the clearest organising features in your AI relationship."),"strengths_likely_to_deepen":data.get("strengths_likely_to_deepen",[]),"areas_worth_monitoring":data.get("areas_worth_monitoring",[]),"overall_outlook":nb(report_data,"overall_outlook", f"Overall, your profile is best read as a pattern to stay aware of, not a problem to solve. {monitor.get('label','One area')} is worth monitoring as usage evolves. What happens next remains yours to shape.")},
        "next_steps":{"title":"Your Next Steps","items":NEXT_STEPS},
    }
