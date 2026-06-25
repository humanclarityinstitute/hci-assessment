# Benchmark Context Data for Report Generator
## Source: HCI_benchmark_findings.md (extracted & structured)
## Purpose: Serve as reference layer for API calls

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
        'key_finding': 'People who use AI daily are dramatically more likely to have told AI things they never told another person'
    },
    
    'reliance': {
        'never': 1.10,
        'rarely': 1.45,
        'sometimes': 1.85,
        'often': 2.40,
        'everyday': 2.91,  # Note: HCI uses 4.4 in raw data; this is normalized
        'range': 1.66,
        'note': 'Clear dose-response relationship'
    },
    
    'emotional_regulation': {
        'never': 1.61,
        'rarely': 2.77,
        'sometimes': 3.10,
        'often': 4.20,
        'everyday': 5.23,
        'range': 1.84,
        'note': 'Variable "AI for emotional relief" shows largest single-variable effect: 2.46 range',
        'gender_note': 'Women 3.14, Men 3.01'
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
        'note': 'UNIQUE: Essentially flat across frequency. Age is stronger predictor.',
        'key_finding': 'Verification is a stable individual characteristic, not a habit that develops with use'
    },
    
    'social_transparency': {
        'never': 2.52,
        'rarely': 2.84,
        'sometimes': 3.15,
        'often': 3.60,
        'everyday': 3.95,
        'range': 1.43,
        'note': 'Weak frequency effect. Age is much stronger predictor.'
    },
    
    'decision_delegation': {
        'never': 2.40,
        'rarely': 2.60,
        'sometimes': 2.95,
        'often': 3.45,
        'everyday': 3.80,
        'range': 1.40,
        'key_finding': '26% report reduced oversight over time — drift mechanism'
    },
    
    'human_agency': {
        'never': 4.52,
        'rarely': 4.35,
        'sometimes': 4.18,
        'often': 4.50,
        'everyday': 4.58,
        'range': 0.40,
        'note': 'Minimal frequency effect. Everyday users slightly HIGHER agency.',
        'key_finding': 'Heavy AI users do not feel less in control; if anything, intentional integration suggests higher agency'
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
            'Social norm pressure to hide use'
        ]
    },
    
    '25-34': {
        'description': 'Peak-Career Integrators',
        'reliance_mean': 2.55,
        'emotional_engagement_mean': 3.29,  # PEAK for emotional use
        'proceed_without_checking': 4.40,  # Highest: skip verification most
        'identity_conflict': 3.95,  # High: questions about authorship
        'disclosure_untold_things': 3.34,  # Tell AI things not told others
        'distinctive': [
            'Highest inner conflict about AI influence',
            'Highest disclosure to AI',
            'Highest emotional engagement with AI'
        ],
        'pressure_points': [
            'Peak cognitive demand + highest AI reliance = decision authorship questions',
            'Most likely to struggle with: is this my decision or AI-suggested?'
        ]
    },
    
    '35-44': {
        'description': 'Values-Clear Mid-Career Adults (RESILIENCE COHORT)',
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
        'capacity': 'MOST CAPABLE of current conditions',
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
        'interpretation': 'Furthest along adaptation pathway. High career stakes + high AI integration = most benefit AND most exposure',
        'pressure_points': [
            'Lowest ability to function without AI in their domain',
            'Most dependent on systems working'
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
            'Strongest protective instincts',
            'Highest AI skepticism'
        ],
        'tension': 'Strong protective instincts aimed partially at wrong threats — less able to identify AI-generated content',
        'strength': 'Best sustained attention, strongest self-trust'
    },
    
    '65+': {
        'description': 'Digitally Wary Older Adults',
        'verification_external_sources': 'HIGHEST',
        'proceed_without_checking': 2.74,  # Lowest: verify most consistently
        'social_transparency': 5.82,  # HIGHEST: most open about use
        'concealment': 1.36,  # LOWEST: least likely to hide use
        'agency': 2.95,  # Note: small n=21, use cautiously
        'distinctive': [
            'Most socially transparent about AI use',
            'Highest self-direction',
            'Strongest self-trust',
            'Lowest concealment',
            'Lowest agency pressure'
        ],
        'strength': 'Best sustained attention, strongest sense of self, least socially pressured about AI use',
        'note': 'Most honest about their use; least socially pressured to hide it'
    }
}

DISTINCTIVE_FLAGS = {
    # Patterns that diverge meaningfully from frequency expectations
    
    'high_verification_high_frequency': {
        'rarity': 'Approximately 20% of everyday users',
        'why_rare': 'Most everyday users show lower verification (frequency doesn\'t predict this)',
        'meaning': 'Maintained epistemic care despite heavy use; intentional verification as value',
        'research_insight': 'Less susceptible to AI steering; maintain higher skepticism'
    },
    
    'low_reliance_high_frequency': {
        'rarity': 'Approximately 15% of frequent users',
        'why_rare': 'Most frequent users show higher reliance',
        'meaning': 'Tool-like use rather than integration; maintained independence',
        'research_insight': 'Lower drift; clearer decision authority'
    },
    
    'high_emotional_engagement_low_frequency': {
        'rarity': 'Unusual pattern',
        'why_rare': 'Emotional engagement tracks frequency strongly',
        'meaning': 'When they do use AI, it\'s emotionally significant; possible loneliness signal',
        'research_insight': 'See dose-response: loneliness (1.49) → emotional support from AI (3.15)'
    },
    
    'low_disclosure_high_frequency': {
        'rarity': 'Unusual pattern',
        'why_rare': 'Disclosure shows STRONGEST frequency effect (3.25 range)',
        'meaning': 'Maintains privacy boundaries even with heavy use; intentional compartmentalization',
        'research_insight': 'Unusual to use AI extensively without deepening disclosure'
    },
    
    'high_agency_high_reliance': {
        'rarity': 'Fewer than 5% of participants',
        'why_rare': 'High reliance typically co-occurs with some loss of agency',
        'meaning': 'Intentional integration; deep use without losing sense of control',
        'research_insight': 'One of the rare POSITIVE combinations; correlates with better outcomes'
    },
    
    'low_emotional_engagement_high_frequency': {
        'rarity': 'Unusual pattern',
        'why_rare': 'Emotional engagement is the strongest frequency-effect dimension after disclosure',
        'meaning': 'Instrumental relationship; not turning to AI emotionally despite heavy use',
        'research_insight': 'May indicate clear boundaries around emotional expression'
    }
}

KEY_FINDINGS_FOR_REPORTS = {
    'verification_paradox': {
        'statement': 'Verification is one of the few dimensions where usage frequency predicts almost nothing',
        'implication': 'It\'s a stable individual characteristic — some people check carefully from the start; others don\'t develop the habit regardless of exposure',
        'report_language': 'Verification is not a habit that develops with experience; it\'s something people do (or don\'t) from the start.'
    },
    
    'disclosure_strongest_effect': {
        'statement': 'Disclosure shows the strongest frequency effect of any dimension (range 3.25)',
        'specifics': 'Many people who use AI daily have told it things they\'ve never told another person',
        'implication': 'As AI use deepens, it naturally becomes a space for things that don\'t get said elsewhere',
        'report_language': 'Among people who use AI as frequently as you do, disclosure patterns are remarkably consistent — the longer people use AI, the more it becomes a space for things that don\'t get said elsewhere.'
    },
    
    'age_paradox': {
        'younger_overreliance': 'Younger people (18-34) show higher reliance despite being most digitally native',
        'implication': 'Integration, not incompetence; AI entered their workflows earlier in career formation',
        'older_verification': 'Older adults (55+) verify more consistently',
        'implication': 'Habit of epistemic care, but may be aimed at partially wrong threats'
    },
    
    'concealment_gap': {
        'finding': 'Largest gap between actual and disclosed use is in 18-34 age group (gap=1.41 points)',
        'implication': 'Young people most likely to hide their AI use despite being heaviest users',
        'cause': 'Social norm pressure in professional/social environments where AI use is still being negotiated'
    },
    
    'emotional_engagement_expansion': {
        'finding': '87% believe only humans can meet emotional needs; 27% getting emotional support from AI',
        'trajectory': 'This gap is growing; emotional engagement is strongest frequency effect in recent data',
        'dose_response': 'Loneliness correlates directly with AI emotional support (1.49 → 3.15 on 7-point scale)',
        'gender_note': 'Women slightly higher (3.14) than men (3.01)'
    },
    
    'agency_resilience': {
        'finding': 'Agency does NOT decline with more AI use; range is only 0.40 points',
        'slight_reversal': 'Everyday users (4.58) actually report slightly HIGHER agency than occasional users (4.18)',
        'implication': 'Heavy users develop intentionality about their relationship to AI; not passive drift'
    },
    
    'thought_partnership_inevitability': {
        'finding': 'Thought partnership shows largest single-variable frequency effect (3.26 range)',
        'implication': 'People who use AI frequently almost inevitably begin using it as a thinking partner',
        'nature': 'A natural consequence of deep integration, not a conscious choice',
        'distinction': 'Partnership (using AI to challenge thinking) vs. outsourcing (using AI to replace thinking) — this boundary is worth monitoring'
    },
    
    'universal_finding': {
        'statement': 'Usage frequency is the single strongest predictor of AI behavior across all dimensions',
        'nuance': 'Age and gender add nuance but rarely override frequency signal',
        'implication': 'Personal intentionality matters more than demographics'
    }
}

COHORT_NARRATIVES = {
    # Pre-written observations about each cohort for use in reports
    
    '18-24': {
        'label': 'Daily AI Workers & Young Professionals',
        'pattern': 'Most digitally native but most pressured',
        'paradox': 'Heaviest users; highest concealment. Highest capability and highest cost simultaneously.',
        'observation': 'This generation is simultaneously most capable with AI and most burdened by its expectations. Young adults carry the highest cognitive and emotional costs of the current AI transition.',
        'pressure_points': 'Verification fatigue, identity questions, social norm pressure to hide use despite being the heaviest users',
        'use_in_report': 'Section 5, 7, 10 — when explaining their cohort context'
    },
    
    '25-34': {
        'label': 'Peak-Career Integrators',
        'pattern': 'Highest inner conflict about AI influence',
        'paradox': 'Stable work identity but highest questions about decision authorship',
        'observation': 'Career peak cognitive demand driving highest AI uptake as decision support. Most likely to struggle with: is this decision genuinely mine?',
        'pressure_points': 'Identity authorship questions, especially as AI enters high-stakes professional decisions',
        'use_in_report': 'Section 5, 8 — when explaining agency/decision delegation patterns'
    },
    
    '35-44': {
        'label': 'Values-Clear Mid-Career Adults — RESILIENCE COHORT',
        'pattern': 'Most capable of current conditions',
        'strength': 'Highest values clarity, strongest work identity, most control over AI use',
        'observation': 'Not immune to pressure but best positioned to navigate it. Research shows this cohort retains clearest alignment between values and action.',
        'distinctive': 'Highest verification diligence paired with intentional use — they\'ve chosen verification as a value',
        'use_in_report': 'Section 1, 5 — as anchor for resilience narrative'
    },
    
    '45-54': {
        'label': 'Peak-Career Integrators',
        'pattern': 'Furthest along adaptation pathway',
        'depth': 'Most AI integration paired with highest career stakes',
        'observation': 'Most benefit and most exposure simultaneously. This cohort has committed to AI integration as a functioning necessity in their domain.',
        'distinctive': 'Highest reliance is a practical choice reflecting career demands, not drift',
        'use_in_report': 'Section 4, 5 — when explaining rare combinations of reliance + agency'
    },
    
    '55-64': {
        'label': 'Digitally Wary Older Adults',
        'pattern': 'Strong protective instincts aimed partially at wrong threats',
        'strength': 'Genuine wisdom about maintaining human function; best sustained attention',
        'limitation': 'Environment has changed in ways their existing defenses don\'t fully address; lower AI detection confidence',
        'observation': 'Good judgment but incomplete information. Their caution is real and valuable, but calibrated toward risks that no longer apply.',
        'use_in_report': 'Section 9 — when framing "what to protect" for this age group'
    },
    
    '65+': {
        'label': 'Digitally Wary Older Adults',
        'pattern': 'Most transparent, least socially pressured',
        'strength': 'Strongest sense of self and personal authority; most honest about their use',
        'advantage': 'Least socially pressured by norms around AI use — can be authentically themselves',
        'observation': 'Best sustained attention, strongest sense of self. This group maintains clearest sense of identity and personal authority.',
        'use_in_report': 'Section 11 — when discussing boundaries and intentional choices'
    }
}

PRESSURE_POINTS = {
    # By dimension: where the research shows drift/pressure occurs
    
    'reliance': [
        'Cognitive tasks feel harder without AI',
        'Struggling to function independently',
        'Loss of confidence in own abilities'
    ],
    
    'trust': [
        'Over-acceptance of outputs',
        'Reduced verification burden but increased risk',
        'Confidence outpacing accuracy'
    ],
    
    'verification': [
        'Verification fatigue (43% report it)',
        'Selective checking emerging (54% verify selectively)',
        'Cognitive load accumulation'
    ],
    
    'decision_delegation': [
        'Loss of personal oversight',
        'Skill decline in areas delegated',
        'Habitual acceptance without thinking',
        'Reduced decision-making capacity'
    ],
    
    'human_agency': [
        'Process-level drift (59% feel subtly steered)',
        'Attention fragmentation (65% experience it)',
        'Convenience overrides intentional choice',
        'Values-action gap widens'
    ],
    
    'emotional_regulation': [
        'Emotional substitution (boundary between supplement and replacement blurs)',
        'Reduced human connection',
        'Boundary erosion over time',
        'Dependency formation'
    ],
    
    'disclosure': [
        'Privacy erosion',
        'Normalization of sharing',
        'Data accumulation concerns',
        'Loss of privacy sense'
    ],
    
    'thought_partnership': [
        'Outsourced thinking (34-38% question authorship)',
        'Loss of independent reasoning',
        'Dependency on AI framing',
        'Authenticity questions'
    ],
    
    'social_transparency': [
        'Concealment burden (especially 18-34)',
        'Double-life dynamics',
        'Social norm pressure',
        'Isolation from honest conversation'
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
