"""
Human Reference Layer — Values & HBE-Grounded Reframing

Provides values and human experience baseline (HBE) context for 
personalizing signal interpretation to what individuals care about.

Uses HCI's Values Research + HBE framework to reframe technical patterns 
into domains of personal meaning: autonomy, authenticity, wellbeing, 
clarity, values alignment, human connection.
"""

# Values Signals — From HCI's Values Research dataset
VALUES_SIGNALS = {
    'autonomy': {
        'definition': 'Control over decisions, not automated away',
        'high_reliance_signal': 'May feel decisions are being made for you rather than with you',
        'low_reliance_signal': 'Maintains active choice in using AI as a tool',
        'threshold_question': 'Do you still feel in control of important decisions?'
    },
    'authenticity': {
        'definition': 'Your own voice, values visible in how you work',
        'high_reliance_signal': 'Your communication may increasingly reflect AI patterns',
        'low_reliance_signal': 'You adapt AI output to match your voice',
        'threshold_question': 'Does your work still sound like you?'
    },
    'wellbeing': {
        'definition': 'Mental clarity, energy, rest, not drained by tools',
        'high_reliance_signal': 'Tool use may be creating decision fatigue or cognitive load',
        'low_reliance_signal': 'You feel the tools reduce cognitive load appropriately',
        'threshold_question': 'Do you feel clearer or more tired after using AI?'
    },
    'clarity': {
        'definition': 'Understanding your own thinking, not outsourcing reflection',
        'high_reliance_signal': 'You may skip the step of forming your own view first',
        'low_reliance_signal': 'You think first, then use AI to test or refine your thinking',
        'threshold_question': 'Can you articulate your own position before asking AI?'
    },
    'values_alignment': {
        'definition': 'Tools and outputs reflect what matters to you',
        'high_reliance_signal': 'Values drift — you accept suggestions that slightly misalign',
        'low_reliance_signal': 'You filter for alignment before accepting suggestions',
        'threshold_question': 'Are your decisions reflecting your actual values?'
    },
    'human_connection': {
        'definition': 'Relationships and collaboration remain primary',
        'high_reliance_signal': 'Human input may feel less valuable than AI suggestions',
        'low_reliance_signal': 'You still prioritize human context and expertise',
        'threshold_question': 'Are you deferring to AI over human insight?'
    }
}

# HBE (Human Experience Baseline) Framework
# Maps dimensions to expected baseline behaviors (pre-AI exposure)
HBE_FRAMEWORK = {
    'trust': {
        'hbe_baseline': 'People start skeptical of new systems; trust builds through proven track record',
        'ai_pressure': 'Constant positive feedback can accelerate trust beyond evidence',
        'reframe': 'Your trust level is normal. The question is: what evidence supports it?'
    },
    'reliance': {
        'hbe_baseline': 'People naturally delegate tasks that feel routine or low-stakes',
        'ai_pressure': 'Easy access can shift "low-stakes" perception; delegation may expand',
        'reframe': 'Notice which tasks you\'re delegating. Are they still actually low-stakes?'
    },
    'verification': {
        'hbe_baseline': 'People verify when consequences matter; skip verification when they don\'t',
        'ai_pressure': 'High output quality can hide gaps in understanding',
        'reframe': 'Your verification habits are sound. Just extend them to domains that matter more.'
    },
    'disclosure': {
        'hbe_baseline': 'People share different amounts of information in different contexts',
        'ai_pressure': 'Easy input can lead to deeper disclosure than typical human conversation',
        'reframe': 'You\'re right to be cautious. AI systems have different confidentiality boundaries.'
    },
    'emotional_regulation': {
        'hbe_baseline': 'People seek support from trusted sources; conversation itself is regulatory',
        'ai_pressure': 'Always-on availability can reduce seeking human support',
        'reframe': 'AI can supplement human connection, not replace it. Notice if the balance shifts.'
    },
    'thought_partnership': {
        'hbe_baseline': 'People think aloud with trusted partners; externalization aids clarity',
        'ai_pressure': 'Quick outsourcing can skip the personalization step of authentic partnership',
        'reframe': 'Thinking out loud with AI works best when you maintain your own judgment.'
    },
    'social_transparency': {
        'hbe_baseline': 'People disclose tool use selectively; context shapes disclosure',
        'ai_pressure': 'Invisibility of AI use can create expectation misalignment',
        'reframe': 'You choose when and how to disclose. Just choose consciously.'
    },
    'human_agency': {
        'hbe_baseline': 'People maintain sense of authorship even when delegating tasks',
        'ai_pressure': 'Outsourcing decisions can create gap between intent and authorship',
        'reframe': 'Your agency remains intact when you stay in the loop of meaning-making.'
    }
}

# Cohort-specific HBE reframes (age/experience groups)
HBE_COHORT_REFRAMES = {
    '18-24': {
        'profile': 'Digital natives; AI is normal tool in ecosystem; high early adoption',
        'pressure_point': 'May normalize AI use without questioning baseline shifts',
        'reframe': 'Familiarity is an asset. Your question is: Does this still feel like *my* choice?'
    },
    '25-34': {
        'profile': 'Pre-AI professionals; now integrating AI into established workflows',
        'pressure_point': 'Workflow pressure can accelerate delegation beyond original comfort',
        'reframe': 'Notice what your workflow looked like before. Is the change intentional?'
    },
    '35-44': {
        'profile': 'Mid-career; investment in proven methods; selective AI adoption',
        'pressure_point': 'May over-rely on past expertise; under-integrate available tools',
        'reframe': 'Your skepticism is wise. Your experience is also your anchor.'
    },
    '45-54': {
        'profile': 'Established expertise; conscious relationship with technology',
        'pressure_point': 'May feel pressure to adopt rapidly to stay competitive',
        'reframe': 'Your pace is yours. Intentional integration serves you better than forced speed.'
    },
    '55-64': {
        'profile': 'Approaching lifecycle transition; values clarification natural',
        'pressure_point': 'May defer to AI for efficiency; values alignment less visible',
        'reframe': 'Your experience with what matters is your compass. Use it.'
    },
    '65+': {
        'profile': 'Life experience; clarity on values; selective engagement typical',
        'pressure_point': 'May be underestimating relevance of AI to lived domains',
        'reframe': 'Your selectivity is an advantage. You know what matters to you.'
    }
}

# Reframe Library — transforms technical patterns into values language
REFRAME_LIBRARY = {
    'trust_pattern': {
        'technical': 'High trust score; sustained confidence over time',
        'values_reframe': 'You feel confident in this tool. The question is: What evidence supports that confidence? Is it tracking record, familiarity, or persuasiveness? All are valid—just know which one you\'re relying on.'
    },
    'reliance_escalation': {
        'technical': 'Increased delegation on repeated task type',
        'values_reframe': 'You\'re using this tool more because it works. That\'s rational. The question is: Have the stakes of the task changed? If not, your pattern is sound. If yes—notice it.'
    },
    'verification_skip': {
        'technical': 'Reduced verification on familiar task pattern',
        'values_reframe': 'You trust the output because you\'ve checked it before and it was accurate. That\'s learning. The question is: Have the consequences of error changed? Your verification instinct will tell you if they have.'
    },
    'disclosure_depth': {
        'technical': 'Deeper input disclosure than typical conversation',
        'values_reframe': 'You\'re being more candid with AI than you might with a colleague. That can be useful—you\'re thinking out loud. The question is: Are you comfortable that this information sits with an AI system? If yes, that\'s your choice.'
    },
    'emotional_support_shift': {
        'technical': 'Seeking AI support before human connection on emotional topics',
        'values_reframe': 'You turn to AI first because it\'s always available and non-judgmental. That\'s valuable. The question is: Is it supplementing human connection or replacing it? The answer matters for your wellbeing.'
    },
    'collaborative_outsourcing': {
        'technical': 'Moving from co-authorship to AI-first drafting',
        'values_reframe': 'You\'re getting output faster by using AI as primary generator. That\'s efficient. The question is: Are you still engaged enough to maintain authorship? If yes, you\'re using it well. If no—you\'ve outsourced meaning-making.'
    },
    'agency_gap': {
        'technical': 'Decision taken by AI; user acceptance rate high',
        'values_reframe': 'You\'re comfortable accepting this decision because the reasoning feels sound. That\'s trust. The question is: Did you understand the reasoning well enough to challenge it if you disagreed? If yes—your agency is intact. If no—you might notice and build that habit back in.'
    }
}

# Research Insight Library — Grounds reframes in HCI behavioral data
RESEARCH_INSIGHTS = {
    'values_held_not_lived': {
        'insight': 'People often articulate values (e.g., autonomy) but patterns show different lived priorities',
        'application': 'If your scores show high reliance but values emphasize autonomy, that\'s not contradiction. It\'s information. What would change if you acted on the value?'
    },
    'drift_mechanism': {
        'insight': 'Behavioral drift isn\'t sudden; it\'s incremental outsourcing of consecutive micro-decisions',
        'application': 'Notice patterns of small delegations. One question answered by AI is fine. Fifty questions answered by AI shifts where you think.'
    },
    'verification_paradox': {
        'insight': 'High-confidence outputs reduce verification motivation, which paradoxically increases risk when errors occur',
        'application': 'If this tool is impressive and accurate, that\'s exactly when to maintain verification on high-stakes decisions.'
    },
    'signal_confidence_levels': {
        'definitive': 'Observed in majority of sample; consistent across demographics; strong effect size',
        'strong': 'Observed in plurality; consistent in some demographic groups; moderate effect',
        'structural': 'Explained by system design or incentive structure; observed where structure predicts it'
    },
    'dose_response': {
        'insight': 'Reliance is dose-dependent: more use → larger behavioral changes (usually gradual, sometimes sudden)',
        'application': 'Track your own dose. Notice what changes at different frequencies.'
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
    
    return f"{baseline}\n\nIn your case: {pressure}\n\nWhat this means: {reframe}"


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
        Insight description + application guidance
    """
    if insight_key not in RESEARCH_INSIGHTS:
        return f"Insight {insight_key} not found in library."
    
    insight_data = RESEARCH_INSIGHTS[insight_key]
    return f"Finding: {insight_data['insight']}\n\nFor you: {insight_data['application']}"


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
