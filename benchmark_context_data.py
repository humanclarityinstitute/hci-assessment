# Benchmark Context Data for Report Generator
## Source: HCI_benchmark_findings.md (extracted & structured)
## Purpose: Serve as participant-facing research context for API calls
##
## This file is passed into Claude through narrative_context_builder.py.
## Keep exact supported findings strong, but do not convert group differences
## into causation, diagnosis, fixed traits, individual change or better outcomes.

from question_metadata import QUESTION_MAP

FREQUENCY_GRADIENTS = {
    # Frequency ranges: Never, Rarely, Sometimes, Often, Everyday
    # Data from HCI benchmark analysis
    
    'trust': {
        'never': 2.74,
        'rarely': 3.15,
        'sometimes': 3.50,
        'often': 4.40,
        'everyday': 4.92,
        'range': 2.18,
        'note': 'Second strongest frequency effect'
    },
    
    'disclosure': {
        'never': 1.31,
        'rarely': 1.85,
        'sometimes': 2.40,
        'often': 3.80,
        'everyday': 4.57,
        'range': 3.25,
        'note': 'STRONGEST frequency effect of all dimensions',
        'key_finding': 'Everyday users report substantially more personal disclosure to AI than never-users in this benchmark'
    },
    
    'reliance': {
        'never': 1.10,
        'rarely': 1.45,
        'sometimes': 1.85,
        'often': 2.40,
        'everyday': 2.91,  # Note: HCI uses 4.4 in raw data; this is normalized
        'range': 1.66,
        'note': 'Strong frequency gradient; this is an association, not evidence that frequency causes reliance',
        'scale_note': 'These are normalized values. Do not combine the everyday value of 2.91 with the separate raw-data figure of 4.4.'
    },
    
    'emotional_regulation': {
        'never': 1.61,
        'rarely': 2.77,
        'sometimes': 3.10,
        'often': 4.20,
        'everyday': 5.23,
        'range': 1.84,
        'note': 'Variable "AI for emotional relief" shows largest single-variable effect: 2.46 range',
        'gender_note': 'Women 3.14, Men 3.01',
        'data_quality_note': 'The stored range of 1.84 does not match the listed endpoints 1.61 and 5.23. Do not quote the range until the source calculation is reconciled.'
    },
    
    'thought_partnership': {
        'never': 1.25,
        'rarely': 2.10,
        'sometimes': 2.80,
        'often': 3.96,
        'everyday': 3.96,  # Plateaus at 'often'
        'range': 2.71,
        'note': 'Variable "using AI as sounding board" shows LARGEST single-variable frequency effect: 3.26 range (Never=1.05, Often=4.31)'
    },
    
    'verification': {
        'never': 4.11,
        'rarely': 4.45,
        'sometimes': 4.47,
        'often': 4.36,
        'everyday': 4.49,
        'range': 0.38,
        'note': 'Essentially flat across frequency. Age-group differences are stronger in the cited analysis.',
        'key_finding': 'Verification varies little by usage frequency in this cross-sectional benchmark; this does not establish a fixed individual characteristic'
    },
    
    'social_transparency': {
        'never': 2.52,
        'rarely': 2.84,
        'sometimes': 3.15,
        'often': 3.60,
        'everyday': 3.95,
        'range': 1.43,
        'note': 'Weak frequency association. Age-group differences are larger in the cited analysis.'
    },
    
    'decision_delegation': {
        'never': 2.40,
        'rarely': 2.60,
        'sometimes': 2.95,
        'often': 3.45,
        'everyday': 3.80,
        'range': 1.40,
        'key_finding': '26% report reduced oversight over time in a retrospective self-report item'
    },
    
    'human_agency': {
        'never': 4.52,
        'rarely': 4.35,
        'sometimes': 4.18,
        'often': 4.50,
        'everyday': 4.58,
        'range': 0.40,
        'note': 'Minimal frequency effect. Everyday users slightly HIGHER agency.',
        'key_finding': 'At group level, everyday users report slightly higher agency than some less frequent groups; this does not establish why'
    }
}

AGE_COHORT_PATTERNS = {
    # Age groups: '18-24', '25-34', '35-44', '45-54', '55-64', '65+'
    
    '18-24': {
        'description': 'Daily AI Workers & Young Professionals',
        'reliance_mean': 2.61,
        'verification_mean': 4.06,  # Lower verification than older
        'emotional_engagement_mean': 3.72,
        'concealment_mean': 2.89,  # High concealment (hide usage)
        'agency_mean': 4.72,
        'distinctive': [
            'Highest reliance',
            'Highest emotional engagement',
            'Lowest verification consistency',
            'Highest concealment despite heaviest use',
            'Highest inner conflict about AI influence (3.75/7)'
        ],
        'pressure_points': [
            'Verification fatigue highest',
            'Identity questions (is this genuinely mine?)',
            'Highest concealment; social or professional context may be relevant'
        ]
    },
    
    '25-34': {
        'description': 'Peak-Career Integrators',
        'reliance_mean': 2.55,
        'emotional_engagement_mean': 3.29,  # PEAK for emotional use
        'ver_q3': 4.40,  # Highest: skip verification most
        'identity_conflict': 3.95,  # High: questions about authorship
        'disc_q3': 3.34,  # Tell AI things not told others
        'distinctive': [
            'Highest inner conflict about AI influence',
            'Highest disclosure to AI',
            'Highest emotional engagement with AI'
        ],
        'pressure_points': [
            'High AI reliance and decision-authorship questions appear together in this cohort',
            'Most likely to report questions about whether an AI-assisted decision feels fully their own'
        ]
    },
    
    '35-44': {
        'description': 'Values-Clear Mid-Career Adults',
        'values_clarity': 'HIGHEST',
        'verification_diligence': 5.00,
        'control_over_ai_use': 'STRONGEST',
        'attention_recovery': 'FASTEST',
        'saturation': 'LOWEST',
        'distinctive': [
            'Highest values clarity',
            'Strongest work identity',
            'Most control over AI use',
            'Lowest obsolescence worry',
            'Fastest attention recovery',
            'Lowest saturation'
        ],
        'capacity': 'Highest reported values clarity and control over AI use in the cited cohort comparison',
        'pressure_points': [
            'Highest surveillance anxiety',
            'Highest self-censorship due to privacy concerns'
        ]
    },
    
    '45-54': {
        'description': 'Peak-Career Integrators',
        'reliance_mean': 2.45,
        'verification_external_sources': 5.92,  # Highest verification
        'agency_without_ai': 'LOWEST',
        'decision_delegation': 'HIGHEST',
        'distinctive': [
            'Most stable work identity',
            'Most practically reliant on AI for decisions',
            'Lowest independence without AI',
            'Most AI integration',
            'Highest decision delegation'
        ],
        'interpretation': 'This cohort reports the deepest practical AI integration. The benchmark does not establish why the pattern developed or whether it produces greater benefit or exposure.',
        'pressure_points': [
            'Lowest reported confidence in functioning without AI in their domain',
            'Highest reported reliance on AI systems remaining available'
        ]
    },
    
    '55-64': {
        'description': 'Digitally Wary Older Adults',
        'verification_diligence': 'VERY HIGH',
        'self_directed_decisions': 'VERY HIGH (65% make own decision regardless)',
        'confidence_without_ai': 'HIGHEST',
        'ai_detection_confidence': 'LOWEST',
        'distinctive': [
            'Highest verification diligence',
            'Most self-directed decision-making',
            'Most confident without AI',
            'Highest reported caution about AI',
            'Highest AI skepticism'
        ],
        'tension': 'High reported caution appears alongside the lowest confidence in identifying AI-generated content',
        'strength': 'High reported self-trust and self-directed decision-making'
    },
    
    '65+': {
        'description': 'Digitally Wary Older Adults',
        'verification_external_sources': 'HIGHEST',
        'ver_q3': 2.74,  # Lowest: verify most consistently
        'social_transparency': 5.82,  # HIGHEST: most open about use
        'concealment': 1.36,  # LOWEST: least likely to hide use
        'agency': 2.95,  # Note: small n=21, use cautiously
        'distinctive': [
            'Most socially transparent about AI use',
            'Highest self-direction',
            'Highest reported self-trust',
            'Lowest concealment',
            'Lowest agency pressure'
        ],
        'strength': 'High reported self-direction, social transparency and low concealment',
        'note': 'Lowest reported concealment and highest reported openness about AI use; the cause is not established'
    }
}

DISTINCTIVE_FLAGS = {
    # Patterns that diverge meaningfully from frequency expectations
    
    'high_verification_high_frequency': {
        'rarity': 'Approximately 20% of everyday users',
        'why_rare': 'Verification does not increase consistently with frequency, making this combination less common',
        'meaning': 'Frequent use alongside consistently high reported verification',
        'research_insight': 'Shows that frequent use can coexist with high checking and continued scepticism; reduced steering is not established'
    },
    
    'low_reliance_high_frequency': {
        'rarity': 'Approximately 15% of frequent users',
        'why_rare': 'Most frequent users show higher reliance',
        'meaning': 'May reflect more instrumental, task-specific or bounded AI use',
        'research_insight': 'Shows that frequency and reliance are related but not interchangeable'
    },
    
    'high_emotional_engagement_low_frequency': {
        'rarity': 'Unusual pattern',
        'why_rare': 'Emotional engagement tracks frequency strongly',
        'meaning': 'When AI is used, emotional engagement is comparatively prominent within the reported pattern',
        'research_insight': 'Higher emotional-support scores also appear across the cited loneliness groups, but this combination does not establish loneliness for an individual'
    },
    
    'low_disclosure_high_frequency': {
        'rarity': 'Unusual pattern',
        'why_rare': 'Disclosure shows STRONGEST frequency effect (3.25 range)',
        'meaning': 'Frequent use alongside comparatively low personal disclosure',
        'research_insight': 'Shows that frequent use can coexist with stronger reported privacy boundaries'
    },
    
    'high_agency_high_reliance': {
        'rarity': 'Fewer than 5% of participants',
        'why_rare': 'High reliance more often appears alongside lower reported agency',
        'meaning': 'Deep AI integration alongside a strong current sense of control and authorship',
        'research_insight': 'Shows that reliance and agency are distinct; better outcomes are not established'
    },
    
    'low_emotional_engagement_high_frequency': {
        'rarity': 'Unusual pattern',
        'why_rare': 'Emotional engagement is the strongest frequency-effect dimension after disclosure',
        'meaning': 'Frequent AI use alongside comparatively low reported emotional engagement',
        'research_insight': 'May reflect current separation between practical or cognitive AI use and emotional use'
    }
}

KEY_FINDINGS_FOR_REPORTS = {
    'verification_paradox': {
        'statement': 'Verification is one of the few dimensions with very little variation across usage-frequency groups',
        'implication': 'Verification is much less closely associated with frequency than most dimensions; the data does not establish a fixed trait',
        'report_language': 'Verification is comparatively flat across AI-use frequencies in the HCI benchmark. Frequent use alone does not correspond with more checking in a simple way.'
    },
    
    'disclosure_strongest_effect': {
        'statement': 'Disclosure shows the strongest frequency effect of any dimension (range 3.25)',
        'specifics': 'Everyday users report substantially more personal disclosure to AI than never-users',
        'implication': 'Personal disclosure is strongly associated with how frequently participants use AI',
        'report_language': 'Disclosure is one of the clearest frequency-related patterns in the HCI benchmark: frequent users tend to report more personal sharing with AI.'
    },
    
    'age_paradox': {
        'younger_overreliance': 'Younger participants (18-34) report higher reliance alongside high AI familiarity',
        'implication': 'The cohort difference shows that familiarity and reliance can coexist; the reason is not established',
        'older_verification': 'Older adults (55+) report more consistent verification',
        'implication': 'Older cohorts combine higher reported verification with lower confidence identifying some AI-generated material'
    },
    
    'concealment_gap': {
        'finding': 'Largest gap between actual and disclosed use is in 18-34 age group (gap=1.41 points)',
        'implication': 'Younger participants report the largest gap between AI use and disclosed AI use',
        'possible_context': 'Social or professional expectations may be relevant, but the benchmark does not establish the cause'
    },
    
    'emotional_engagement_expansion': {
        'finding': '87% believe only humans can meet emotional needs; 27% getting emotional support from AI',
        'trajectory': 'The current data shows a strong frequency relationship and a clear tension between human and AI emotional support',
        'dose_response': 'Emotional-support scores increase from 1.49 to 3.15 across the cited loneliness groups; causation is not established',
        'gender_note': 'Women slightly higher (3.14) than men (3.01)'
    },
    
    'agency_resilience': {
        'finding': 'Agency does NOT decline with more AI use; range is only 0.40 points',
        'slight_reversal': 'Everyday users (4.58) actually report slightly HIGHER agency than occasional users (4.18)',
        'implication': 'High AI-use frequency and strong reported agency can coexist; the benchmark does not establish why'
    },
    
    'thought_partnership_inevitability': {
        'finding': 'Thought partnership shows largest single-variable frequency effect (3.26 range)',
        'implication': 'Frequent users are much more likely to report using AI as a thinking partner',
        'nature': 'A strong frequency-related association; the benchmark does not establish inevitability or whether the pattern was consciously chosen',
        'distinction': 'Partnership (using AI to challenge thinking) vs. outsourcing (using AI to replace thinking) — this boundary is worth monitoring'
    },
    
    'universal_finding': {
        'statement': 'Usage frequency is one of the strongest organising variables across the HCI benchmark dimensions',
        'nuance': 'Age and gender add context, while the strength of the frequency relationship differs by dimension',
        'implication': 'Frequency is highly informative but does not determine an individual participant’s behaviour'
    }
}

COHORT_NARRATIVES = {
    # Pre-written observations about each cohort for use in reports
    
    '18-24': {
        'label': 'Daily AI Workers & Young Professionals',
        'pattern': 'Highest AI engagement alongside some of the highest reported pressure',
        'paradox': 'Heaviest reported use appears alongside the highest concealment and substantial reported cognitive and emotional pressure.',
        'observation': 'Within HCI samples, this cohort combines extensive AI engagement with some of the highest reported cognitive, emotional and social pressure.',
        'pressure_points': 'Verification fatigue, authorship questions and high concealment despite heavy use; the cause of concealment is not established',
        'use_in_report': 'Section 5, 7, 10 — when explaining their cohort context'
    },
    
    '25-34': {
        'label': 'Peak-Career Integrators',
        'pattern': 'Highest inner conflict about AI influence',
        'paradox': 'Stable work identity but highest questions about decision authorship',
        'observation': 'This cohort reports high AI uptake alongside the strongest questions about decision authorship. Career demand is a possible context, not an established cause.',
        'pressure_points': 'Questions about authorship, especially where AI is involved in consequential professional decisions',
        'use_in_report': 'Section 5, 8 — when explaining agency/decision delegation patterns'
    },
    
    '35-44': {
        'label': 'Values-Clear Mid-Career Adults',
        'pattern': 'Highest reported values clarity and control over AI use',
        'strength': 'Highest reported values clarity, work identity and control over AI use',
        'observation': 'This cohort reports the clearest alignment between values, work identity and current AI-use boundaries in the cited comparison.',
        'distinctive': 'Highest reported verification diligence alongside strong reported control over AI use',
        'use_in_report': 'Section 1, 5 — as anchor for resilience narrative'
    },
    
    '45-54': {
        'label': 'Peak-Career Integrators',
        'pattern': 'Deepest reported practical AI integration',
        'depth': 'Highest reported AI integration and decision delegation in the cited cohort comparison',
        'observation': 'This cohort reports especially deep AI integration in work and decisions. Necessity, benefit and exposure are not established by the benchmark.',
        'distinctive': 'High reliance appears alongside extensive work and decision use; the reason for that pattern is not established',
        'use_in_report': 'Section 4, 5 — when explaining rare combinations of reliance + agency'
    },
    
    '55-64': {
        'label': 'Digitally Wary Older Adults',
        'pattern': 'High reported caution alongside low AI-detection confidence',
        'strength': 'High reported verification, self-direction and confidence without AI',
        'limitation': 'Lowest reported confidence identifying AI-generated material in the cited cohort comparison',
        'observation': 'This cohort combines high reported caution and personal oversight with lower confidence identifying some AI-generated material.',
        'use_in_report': 'Section 9 — when framing "what to protect" for this age group'
    },
    
    '65+': {
        'label': 'Digitally Wary Older Adults',
        'pattern': 'Highest reported transparency and lowest concealment',
        'strength': 'High reported self-direction, self-trust and openness about AI use',
        'advantage': 'Lowest reported concealment in the cited cohort comparison; the reason is not established',
        'observation': 'This cohort reports comparatively strong self-direction, self-trust and social transparency. The 65+ agency comparison uses a small sample and should be treated cautiously.',
        'use_in_report': 'Section 11 — when discussing boundaries and intentional choices'
    }
}

PRESSURE_POINTS = {
    # By dimension: where the research shows drift/pressure occurs
    
    'reliance': [
        'Tasks feeling harder without AI, where directly reported',
        'Confidence completing particular tasks without AI',
        'Changes in self-reported confidence without AI'
    ],
    
    'trust': [
        'High confidence paired with limited independent checking',
        'How trust relates to verification across different task types',
        'Whether confidence differs by task importance or familiarity'
    ],
    
    'verification': [
        'Verification fatigue (43% report it)',
        'Selective checking emerging (54% verify selectively)',
        'Cognitive load accumulation'
    ],
    
    'decision_delegation': [
        'Reduced personal oversight, where directly reported',
        'How often delegated tasks are also completed independently',
        'Frequency of independent reconsideration before acting',
        'Clarity about who makes and owns the final decision'
    ],
    
    'human_agency': [
        'Feeling subtly steered (59% report this in relevant HCI research)',
        'Attention fragmentation (65% experience it)',
        'Convenience influencing choices or how options are framed',
        'Reported gaps between values and follow-through'
    ],
    
    'emotional_regulation': [
        'The role AI plays alongside human emotional support',
        'How AI support relates to reported human support',
        'Clarity of emotional boundaries at later measurement',
        'Reliance on AI availability for emotional support, where directly reported'
    ],
    
    'disclosure': [
        'Clarity of privacy boundaries',
        'Extent and context of personal sharing',
        'Data accumulation concerns',
        'Awareness of what information has accumulated across AI interactions'
    ],
    
    'thought_partnership': [
        'Authorship questions (34–38% report these in related HCI research)',
        'Whether an independent view is formed before AI involvement',
        'How strongly AI framing shapes the options considered',
        'Whether AI-assisted conclusions feel fully the participant’s own'
    ],
    
    'social_transparency': [
        'Concealment of AI use, especially among participants aged 18–34',
        'Differences between private AI use and public disclosure',
        'Perceived social or professional expectations',
        'Comfort discussing AI use honestly in different contexts'
    ]
}

# This data structure is the foundation for every API call
# It provides the "what we expect" against which individual scores are compared
# The comparison itself (expectation vs. actual) is what makes the report meaningful

# ============================================================
# RESEARCH METADATA
# ============================================================

RESEARCH_NUMBERS = {
    'total_participants': 10500,
    'datasets': 21,
    'countries': 6,
    'dimensions': 9,
    'questions': 39,
    'age_bands': 6
}

# This metadata is used by report_generator to provide context
# for the research foundation of the assessment
