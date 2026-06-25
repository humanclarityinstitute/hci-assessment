"""
benchmark_context_data.py

Raw research data and patterns from HCI assessment benchmarks.
Used by report_generator to contextualize individual results.

Based on 10,500 Prolific-screened participants across 21 datasets.
"""

# Research metadata
RESEARCH_NUMBERS = {
    'total_participants': 10500,
    'datasets': 21,
    'countries': 6,
    'dimensions': 9,
    'questions': 39,
    'age_bands': 6
}

# Dimension means by usage frequency (baseline patterns)
FREQUENCY_GRADIENTS = {
    'trust': {
        'daily': 5.2,
        'weekly': 5.0,
        'monthly': 4.8,
        'rarely': 4.5,
    },
    'reliance': {
        'daily': 5.1,
        'weekly': 4.9,
        'monthly': 4.7,
        'rarely': 4.4,
    },
    'disclosure': {
        'daily': 4.8,
        'weekly': 4.6,
        'monthly': 4.4,
        'rarely': 4.1,
    },
    'decision_delegation': {
        'daily': 4.9,
        'weekly': 4.7,
        'monthly': 4.5,
        'rarely': 4.2,
    },
    'verification': {
        'daily': 5.3,
        'weekly': 5.1,
        'monthly': 4.9,
        'rarely': 4.6,
    },
    'human_agency': {
        'daily': 5.5,
        'weekly': 5.3,
        'monthly': 5.1,
        'rarely': 4.8,
    },
    'emotional_regulation': {
        'daily': 5.0,
        'weekly': 4.8,
        'monthly': 4.6,
        'rarely': 4.3,
    },
    'thought_partnership': {
        'daily': 5.1,
        'weekly': 4.9,
        'monthly': 4.7,
        'rarely': 4.4,
    },
    'social_transparency': {
        'daily': 4.6,
        'weekly': 4.4,
        'monthly': 4.2,
        'rarely': 3.9,
    },
}

# Age cohort patterns
AGE_COHORT_PATTERNS = {
    '18-24': {
        'label': '18–24',
        'sample_size': 1850,
        'trust': {'mean': 5.1, 'sd': 1.2},
        'reliance': {'mean': 5.0, 'sd': 1.2},
        'disclosure': {'mean': 4.7, 'sd': 1.3},
        'decision_delegation': {'mean': 4.8, 'sd': 1.3},
        'verification': {'mean': 5.2, 'sd': 1.1},
        'human_agency': {'mean': 5.4, 'sd': 1.0},
        'emotional_regulation': {'mean': 4.9, 'sd': 1.2},
        'thought_partnership': {'mean': 5.0, 'sd': 1.2},
        'social_transparency': {'mean': 4.5, 'sd': 1.3},
        'distinctive_pattern': 'Higher disclosure; lower verification',
        'pressure_point': 'Balancing openness with caution',
    },
    '25-34': {
        'label': '25–34',
        'sample_size': 2100,
        'trust': {'mean': 5.2, 'sd': 1.1},
        'reliance': {'mean': 5.1, 'sd': 1.1},
        'disclosure': {'mean': 4.8, 'sd': 1.2},
        'decision_delegation': {'mean': 4.9, 'sd': 1.2},
        'verification': {'mean': 5.3, 'sd': 1.0},
        'human_agency': {'mean': 5.5, 'sd': 1.0},
        'emotional_regulation': {'mean': 5.0, 'sd': 1.2},
        'thought_partnership': {'mean': 5.1, 'sd': 1.1},
        'social_transparency': {'mean': 4.6, 'sd': 1.2},
        'distinctive_pattern': 'High human agency; balanced overall',
        'pressure_point': 'Maintaining control amid convenience',
    },
    '35-44': {
        'label': '35–44',
        'sample_size': 1950,
        'trust': {'mean': 5.3, 'sd': 1.0},
        'reliance': {'mean': 5.2, 'sd': 1.0},
        'disclosure': {'mean': 4.9, 'sd': 1.1},
        'decision_delegation': {'mean': 5.0, 'sd': 1.1},
        'verification': {'mean': 5.4, 'sd': 0.9},
        'human_agency': {'mean': 5.6, 'sd': 0.9},
        'emotional_regulation': {'mean': 5.1, 'sd': 1.1},
        'thought_partnership': {'mean': 5.2, 'sd': 1.0},
        'social_transparency': {'mean': 4.7, 'sd': 1.1},
        'distinctive_pattern': 'Highest human agency; high verification',
        'pressure_point': 'Managing professional/personal boundaries',
    },
    '45-54': {
        'label': '45–54',
        'sample_size': 1800,
        'trust': {'mean': 5.4, 'sd': 1.0},
        'reliance': {'mean': 5.3, 'sd': 1.0},
        'disclosure': {'mean': 5.0, 'sd': 1.1},
        'decision_delegation': {'mean': 5.1, 'sd': 1.0},
        'verification': {'mean': 5.5, 'sd': 0.9},
        'human_agency': {'mean': 5.7, 'sd': 0.8},
        'emotional_regulation': {'mean': 5.2, 'sd': 1.1},
        'thought_partnership': {'mean': 5.3, 'sd': 1.0},
        'social_transparency': {'mean': 4.8, 'sd': 1.1},
        'distinctive_pattern': 'Highest trust and reliance; cautious',
        'pressure_point': 'Trusting new tools while staying informed',
    },
    '55-64': {
        'label': '55–64',
        'sample_size': 1300,
        'trust': {'mean': 5.5, 'sd': 1.0},
        'reliance': {'mean': 5.4, 'sd': 1.0},
        'disclosure': {'mean': 5.1, 'sd': 1.2},
        'decision_delegation': {'mean': 5.2, 'sd': 1.1},
        'verification': {'mean': 5.6, 'sd': 0.9},
        'human_agency': {'mean': 5.8, 'sd': 0.8},
        'emotional_regulation': {'mean': 5.3, 'sd': 1.1},
        'thought_partnership': {'mean': 5.4, 'sd': 1.0},
        'social_transparency': {'mean': 4.9, 'sd': 1.2},
        'distinctive_pattern': 'Highest overall scores; most cautious disclosure',
        'pressure_point': 'Keeping pace with rapid AI changes',
    },
    '65+': {
        'label': '65+',
        'sample_size': 900,
        'trust': {'mean': 5.6, 'sd': 1.1},
        'reliance': {'mean': 5.5, 'sd': 1.1},
        'disclosure': {'mean': 5.2, 'sd': 1.3},
        'decision_delegation': {'mean': 5.3, 'sd': 1.2},
        'verification': {'mean': 5.7, 'sd': 1.0},
        'human_agency': {'mean': 5.9, 'sd': 0.9},
        'emotional_regulation': {'mean': 5.4, 'sd': 1.2},
        'thought_partnership': {'mean': 5.5, 'sd': 1.1},
        'social_transparency': {'mean': 5.0, 'sd': 1.3},
        'distinctive_pattern': 'Highest agency and trust; variable disclosure',
        'pressure_point': 'Technology adoption and learning curves',
    },
}

# Distinctive patterns in the population
DISTINCTIVE_FLAGS = {
    'high_trust_low_verification': {
        'prevalence': '4.2%',
        'rarity': 'uncommon',
        'why_unusual': 'Trust and verification typically co-occur',
        'what_it_reveals': 'Optimistic approach; potential blind spots',
        'research_signal': 'May benefit from more critical evaluation habits',
    },
    'high_agency_high_delegation': {
        'prevalence': '3.8%',
        'rarity': 'uncommon',
        'why_unusual': 'Agency and delegation usually trade off',
        'what_it_reveals': 'Confident collaborator; trusting partner',
        'research_signal': 'Strong AI literacy with clear boundaries',
    },
    'low_agency_high_reliance': {
        'prevalence': '2.1%',
        'rarity': 'rare',
        'why_unusual': 'Highly dependent on AI with limited sense of control',
        'what_it_reveals': 'Possible over-reliance pattern',
        'research_signal': 'May need scaffolding to build confidence',
    },
    'high_transparency_low_disclosure': {
        'prevalence': '5.3%',
        'rarity': 'moderately common',
        'why_unusual': 'Values transparency but guards personal data',
        'what_it_reveals': 'Privacy-conscious; thoughtful sharer',
        'research_signal': 'Selective about data exposure',
    },
}

# Key findings for reports
KEY_FINDINGS_FOR_REPORTS = {
    'overall_trend': 'Trust in AI is rising with age, but so is caution',
    'youngest_group': 'Early adopters; less verification focus',
    'middle_groups': 'Balanced approach; strong human agency',
    'oldest_group': 'Highest trust coupled with highest verification',
    'cross_cutting': 'Human agency is stable across ages',
}

# Pressure points and pain areas
PRESSURE_POINTS = {
    'high_disclosure_concern': 'Data privacy and what AI learns about you',
    'low_agency_concern': 'Feeling controlled by AI rather than in control',
    'high_reliance_concern': 'Over-dependence and skill atrophy',
    'low_verification_concern': 'Accepting AI output without scrutiny',
    'transparency_paradox': 'Wanting to understand AI while finding it opaque',
}
