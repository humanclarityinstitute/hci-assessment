"""
Human Reference Layer — Values & HBE-Grounded Reframing

Provides values and human experience baseline (HBE) context for
personalizing signal interpretation to what individuals care about.

Uses HCI's Values Research + HBE framework to reframe technical patterns
into domains of personal meaning: autonomy, authenticity, wellbeing,
clarity, values alignment, human connection.

This is participant-facing interpretive context, not participant-specific
evidence. It should be combined with the participant's actual responses and
benchmark position, and should not be used to infer causation, diagnosis,
capability loss, or individual change over time.
"""

# Values Signals — From HCI's Values Research dataset
VALUES_SIGNALS = {
    'autonomy': {
        'definition': 'Whether decision control and authorship remain with the person',
        'high_reliance_signal': 'Higher reliance can make the boundary between assistance and decision control more important to examine',
        'low_reliance_signal': 'Lower reliance may involve more independent decision steps before AI input',
        'threshold_question': 'Do you still feel in control of important decisions?'
    },
    'authenticity': {
        'definition': 'Whether personal voice and values remain visible in AI-assisted work',
        'high_reliance_signal': 'Extensive AI involvement can make authorship and personal voice more important to examine',
        'low_reliance_signal': 'Lower reliance may leave personal voice more visible before AI input is introduced',
        'threshold_question': 'Does your work still sound like you?'
    },
    'wellbeing': {
        'definition': 'How AI use relates to reported clarity, energy, effort and rest',
        'high_reliance_signal': 'Where AI is used heavily, it is useful to distinguish whether it reduces effort or adds verification and decision load',
        'low_reliance_signal': 'Lower reliance may involve less AI-related verification or decision load, although the effect depends on the task',
        'threshold_question': 'Do you feel clearer or more tired after using AI?'
    },
    'clarity': {
        'definition': 'How clearly a person can identify their own view within AI-assisted thinking',
        'high_reliance_signal': 'Higher reliance can make the sequence of independent reflection and AI input more relevant to examine',
        'low_reliance_signal': 'Lower reliance may involve more independent view formation before AI input',
        'threshold_question': 'Can you articulate your own position before asking AI?'
    },
    'values_alignment': {
        'definition': 'Whether AI-assisted choices remain consistent with what matters to the person',
        'high_reliance_signal': 'Where AI contributes heavily, small differences between suggestions and personal values may be less visible',
        'low_reliance_signal': 'Lower reliance may leave more explicit space for value-based filtering before suggestions are accepted',
        'threshold_question': 'Are your decisions reflecting your actual values?'
    },
    'human_connection': {
        'definition': 'How AI input sits alongside human relationships, context and expertise',
        'high_reliance_signal': 'Where AI is used heavily, it is useful to understand how AI input sits alongside human context and expertise',
        'low_reliance_signal': 'Lower reliance may leave human input more central within the reported pattern',
        'threshold_question': 'Are you deferring to AI over human insight?'
    }
}

# HBE (Human Experience Baseline) Framework
# Provides general human-reference context. It is not a measured pre-AI
# baseline for the individual participant.
HBE_FRAMEWORK = {
    'trust': {
        'hbe_baseline': 'People often begin cautiously with unfamiliar systems and adjust trust through experience',
        'ai_pressure': 'Fluent or consistently helpful outputs may increase confidence faster than the supporting evidence is reviewed',
        'reframe': 'Your reported trust is one part of the pattern. Its meaning depends on the evidence, experience and task context supporting it.'
    },
    'reliance': {
        'hbe_baseline': 'People often delegate tasks that feel routine or low-stakes',
        'ai_pressure': 'Convenient access can broaden which tasks feel suitable for delegation',
        'reframe': 'Your reliance score shows how central AI is in your current responses. It does not by itself establish whether any delegated task is appropriate.'
    },
    'verification': {
        'hbe_baseline': 'People often report checking more when consequences matter and less when they do not',
        'ai_pressure': 'Fluent outputs can make gaps, uncertainty or errors harder to notice',
        'reframe': 'Your verification score describes how often you report checking. Its meaning depends on the task, consequences and evidence available.'
    },
    'disclosure': {
        'hbe_baseline': 'People share different amounts of information across different contexts',
        'ai_pressure': 'Ease of use and the privacy-like feel of the interaction may be associated with deeper disclosure than in some human contexts',
        'reframe': 'Your disclosure score describes what you report sharing with AI. It does not determine whether those choices are right or wrong.'
    },
    'emotional_regulation': {
        'hbe_baseline': 'People often seek emotional support through trusted relationships and conversation',
        'ai_pressure': 'Always-on availability may make AI a readily accessible source of emotional support',
        'reframe': 'Your score shows the role AI currently plays in reported emotional support. It does not establish that AI is replacing human connection.'
    },
    'thought_partnership': {
        'hbe_baseline': 'People often think aloud with trusted partners, and externalising ideas can support clarity',
        'ai_pressure': 'Fast AI generation may shift when independent thinking, authorship and personal judgement enter the process',
        'reframe': 'Your score shows how much AI participates in your thinking. It does not by itself establish whether authorship is retained or displaced.'
    },
    'social_transparency': {
        'hbe_baseline': 'People often disclose tool use selectively, and context influences what they share',
        'ai_pressure': 'Less visible AI use can create differences between private use and what other people understand',
        'reframe': 'Your score describes how open you report being across contexts. The benchmark does not establish why that pattern exists.'
    },
    'human_agency': {
        'hbe_baseline': 'People can retain a sense of authorship while delegating parts of a task',
        'ai_pressure': 'Extensive decision support can make the boundary between input and authorship harder to see',
        'reframe': 'Your agency score reflects your reported sense of control and authorship. It does not prove capability gain, capability loss or stability over time.'
    }
}

# Cohort-specific HBE reframes (age/experience groups)
# These provide group-level context only and should not be treated as fixed
# characteristics of an individual because of age.
HBE_COHORT_REFRAMES = {
    '18-24': {
        'profile': 'In HCI samples, early adoption and high AI engagement are common in this cohort',
        'pressure_point': 'High familiarity can coexist with less visible changes in use, reliance and disclosure',
        'reframe': 'This cohort context may help interpret your responses, but it does not determine why you use AI as you do.'
    },
    '25-34': {
        'profile': 'This cohort often reports integrating AI into already-established professional workflows',
        'pressure_point': 'High workflow demand may be relevant where delegation and authorship questions appear together',
        'reframe': 'The cohort pattern provides context for your current responses but cannot establish how or why your workflow changed.'
    },
    '35-44': {
        'profile': 'This cohort reports comparatively strong work identity, values clarity and control over AI use',
        'pressure_point': 'Selective adoption can coexist with both confidence in established methods and caution about new tools',
        'reframe': 'The cohort comparison describes reported patterns, not whether scepticism or adoption is inherently better.'
    },
    '45-54': {
        'profile': 'This cohort reports deep practical AI integration alongside established professional expertise',
        'pressure_point': 'Professional context may be relevant where high integration and lower confidence without AI appear together',
        'reframe': 'The cohort context does not establish whether integration was chosen, required or likely to remain stable.'
    },
    '55-64': {
        'profile': 'This cohort reports high verification, self-direction and confidence without AI',
        'pressure_point': 'High caution can coexist with lower confidence identifying AI-generated material',
        'reframe': 'The cohort pattern provides context but does not establish superior judgement, capability or protection from error.'
    },
    '65+': {
        'profile': 'This cohort reports high social transparency, self-direction and low concealment',
        'pressure_point': 'Selective engagement may leave some areas of AI use less familiar',
        'reframe': 'The cohort pattern should be interpreted cautiously, including the small sample used for some 65+ comparisons.'
    }
}

# Reframe Library — transforms technical patterns into values language
REFRAME_LIBRARY = {
    'trust_pattern': {
        'technical': 'High reported trust in the current assessment',
        'values_reframe': 'High trust can reflect experience, familiarity, task context or persuasive output. The assessment cannot determine which explanation applies, but the distinction helps interpret what the score may mean.'
    },
    'reliance_escalation': {
        'technical': 'Higher reported delegation or reliance within repeated task types',
        'values_reframe': 'Higher delegation may reflect efficiency, convenience or task fit. Its meaning depends on the stakes of the task and the role the person retains in the final decision.'
    },
    'verification_skip': {
        'technical': 'Lower reported verification within familiar task patterns',
        'values_reframe': 'Lower verification on familiar tasks may reflect prior experience, convenience or perceived low stakes. The assessment does not establish whether checking is sufficient for any particular decision.'
    },
    'disclosure_depth': {
        'technical': 'Higher reported personal disclosure to AI',
        'values_reframe': 'Higher disclosure may reflect the privacy-like feel, availability or usefulness of the interaction. The score describes reported sharing without judging whether that choice is appropriate.'
    },
    'emotional_support_shift': {
        'technical': 'Reported use of AI for emotional support, including AI-first use in some situations',
        'values_reframe': 'AI may be used because it is available, private or easy to access. The assessment can describe the role AI currently plays, but it cannot establish that human connection is being replaced.'
    },
    'collaborative_outsourcing': {
        'technical': 'AI-first drafting or high AI involvement in idea development',
        'values_reframe': 'AI-first drafting can increase speed while making authorship more important to interpret. The assessment cannot determine from frequency alone whether meaning-making or independent reasoning has been displaced.'
    },
    'agency_gap': {
        'technical': 'High reported acceptance of AI recommendations or decision support',
        'values_reframe': 'High acceptance may reflect trust, convenience or perceived quality. The relevant interpretive question is how much reasoning, challenge and final authorship the person reports retaining.'
    }
}

# Research Insight Library — Grounds reframes in HCI behavioral data
RESEARCH_INSIGHTS = {
    'values_held_not_lived': {
        'insight': 'Across some HCI studies, reported values clarity and day-to-day follow-through do not always align',
        'application': 'Where high reliance appears alongside strong autonomy values, the combination may reflect a tension between stated priorities and current practice rather than a contradiction.'
    },
    'drift_mechanism': {
        'insight': 'Across HCI work, small repeated delegations are one possible way behavioural patterns may change gradually',
        'application': 'This framework can help describe cumulative change, but it does not establish that drift has occurred for an individual.'
    },
    'verification_paradox': {
        'insight': 'Fluent or high-confidence outputs may be associated with less motivation to verify, while errors remain possible',
        'application': 'Use this interpretation only where participant responses show high trust alongside lower verification; do not infer increased risk or future decline from trust alone.'
    },
    'signal_confidence_levels': {
        'definitive': 'Observed in a majority of the relevant sample and consistent across available subgroup comparisons; use only when directly supported',
        'strong': 'Observed in a substantial part of the relevant sample and consistent in some subgroup comparisons',
        'structural': 'A repeated pattern that may relate to system design or incentives; do not present the mechanism as proven without direct evidence'
    },
    'dose_response': {
        'insight': 'Higher AI-use frequency is associated with larger reported differences in several HCI behavioural dimensions',
        'application': 'Describe this as a group-level frequency association; do not infer individual progression, inevitability or causation.'
    }
}

def get_values_reframe(dimension: str, score_range: str) -> str:
    """
    Returns values-grounded reframe for a specific dimension and score range.

    Args:
        dimension: One of the 9 HCI dimensions
        score_range: 'low', 'moderate', 'high'

    Returns:
        Plain-language reframe connecting technical pattern to values
    """
    if dimension not in HBE_FRAMEWORK:
        return f"Reframe for {dimension} not available in library."

    baseline = HBE_FRAMEWORK[dimension]['hbe_baseline']
    pressure = HBE_FRAMEWORK[dimension]['ai_pressure']
    reframe = HBE_FRAMEWORK[dimension]['reframe']

    return f"{baseline}\n\nPossible AI-related context: {pressure}\n\nParticipant-facing interpretation: {reframe}"


def get_cohort_reframe(age_group: str) -> dict:
    """
    Returns HBE reframe specific to cohort/age group.

    Args:
        age_group: One of the 6 age buckets (e.g., '25-34')

    Returns:
        Dictionary with profile, pressure point, and reframe
    """
    if age_group not in HBE_COHORT_REFRAMES:
        return {'error': f"Cohort {age_group} not found"}

    return HBE_COHORT_REFRAMES[age_group]


def apply_research_insight(insight_key: str) -> str:
    """
    Returns research insight grounded in HCI behavioral data.

    Args:
        insight_key: Key from RESEARCH_INSIGHTS

    Returns:
        Insight description + participant-facing context
    """
    if insight_key not in RESEARCH_INSIGHTS:
        return f"Insight {insight_key} not found in library."

    insight_data = RESEARCH_INSIGHTS[insight_key]
    return f"Finding: {insight_data['insight']}\n\nParticipant-facing context: {insight_data['application']}"


# Export for use in report generation
__all__ = [
    'VALUES_SIGNALS',
    'HBE_FRAMEWORK',
    'HBE_COHORT_REFRAMES',
    'REFRAME_LIBRARY',
    'RESEARCH_INSIGHTS',
    'get_values_reframe',
    'get_cohort_reframe',
    'apply_research_insight'
]
