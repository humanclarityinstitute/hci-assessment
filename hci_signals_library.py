# HCI SIGNALS Library
## Complete Research Signals Dictionary for report_generator.py
## Source: Master Synthesis, Benchmark Findings, Values/HBE Signals, Signals Library
## Date: June 2026

from question_metadata import QUESTION_MAP, get_question_text

SIGNALS = {
    
    # ========== DIMENSIONS ==========
    # Per-dimension observations for research grounding
    
    'dimensions': {
        
        'reliance': {
            'definition': 'How much you depend on AI for thinking and functioning',
            'high': 'At the high end of reliance, AI has become deeply integrated into how you work and think. The research shows this is common among everyday users, but it brings both clarity (AI handles certain tasks efficiently) and exposure (you may notice some cognitive tasks feel harder without it).',
            'low': 'At the low end of reliance, you maintain more independence from AI systems. Research shows this positioning often reflects either limited exposure or deliberate boundaries — both are stable patterns.',
            'typical': 'In the middle range on reliance, you use AI selectively without it becoming central to how you function. This aligns with most people\'s current positioning.',
            'series': 'HCI\'s research shows reliance accumulates with exposure: from mean 1.1 (never users) to 4.4 (everyday users). This is the clearest dose-response relationship in the data.',
            'pressure_point': 'Verification fatigue, lost independence, gradual delegation'
        },
        
        'trust': {
            'definition': 'How much you believe AI outputs are accurate',
            'high': 'At the high end of trust, you have confidence in AI accuracy. The research shows everyday users score nearly 2.5 points higher than non-users. Your positioning suggests either genuine experience-built confidence or a different verification approach than typical high-trust users.',
            'low': 'At the low end of trust, you maintain healthy skepticism about AI outputs. This aligns with the ~15% of people who remain cautious regardless of exposure.',
            'typical': 'In the middle range on trust, you balance belief with skepticism. This is the population centre for trust.',
            'series': 'Trust tracks closely with usage frequency — everyday users trust substantially more than never-users. Age also predicts trust: older adults show more caution when uncertain.',
            'pressure_point': 'Over-acceptance of outputs, reduced verification burden but increased risk'
        },
        
        'verification': {
            'definition': 'How often you check AI outputs before using them',
            'high': 'At the high end of verification, you actively check AI outputs. The research shows this is a stable individual characteristic — verification is not a habit that develops with experience, it\'s something people do from the start.',
            'low': 'At the low end of verification, you tend to accept outputs without extensive checking. The data shows this is equally stable — a stable epistemic approach rather than laziness or negligence.',
            'typical': 'In the middle range on verification, you check sometimes but not always. This is common across usage frequencies.',
            'series': 'Verification is one of the few dimensions where usage frequency predicts almost nothing. Age is the stronger predictor: older adults verify more consistently. The research trajectory shows verification is holding as a universal behaviour (84-99%) but increasingly costly (43-54% report fatigue).',
            'pressure_point': 'Verification fatigue, selective checking emerging, cognitive load accumulation'
        },
        
        'decision_delegation': {
            'definition': 'How much you hand over decisions to AI',
            'high': 'At the high end of decision delegation, you trust AI recommendations enough to act on them without always second-guessing. Research shows younger people delegate more, and this increases with frequency. The research also shows: 26% report reduced oversight over time, suggesting drift happens here.',
            'low': 'At the low end of decision delegation, you maintain strong personal oversight. Older adults show this positioning consistently — research shows 65% of over-65s make their own decision regardless of AI recommendation.',
            'typical': 'In the middle range on delegation, you consider AI input but don\'t rely on it exclusively. This is the balance most people maintain.',
            'series': 'Delegation increases with frequency and is higher in younger age groups. The concerning finding: some people show reduced oversight over time, which research identifies as a drift mechanism.',
            'pressure_point': 'Loss of personal oversight, skill decline, habitual acceptance, reduced decision-making capacity'
        },
        
        'human_agency': {
            'definition': 'How much control you maintain over your decisions',
            'high': 'At the high end of agency, you experience yourself as self-directed and in control of your thinking. The research shows agency is remarkably resilient at the identity level (91% retain personal responsibility) but under pressure at the process level (59% feel subtly steered). High agency suggests you\'ve maintained this balance intentionally.',
            'low': 'At the low end of agency, you experience less control over decisions. The research is clear: this is not identity loss (identity stays intact) but process erosion — attention fragmented, convenience-driven drift.',
            'typical': 'In the middle range on agency, you feel reasonably self-directed with moments of influence. This is where most people sit.',
            'series': 'Agency does not decrease meaningfully with more AI use (range only 0.40). Instead, everyday users slightly report higher agency, suggesting intentional integration. The key pressure point: attention infrastructure degradation makes values harder to enact, not loss of will.',
            'pressure_point': 'Process-level drift, attention fragmentation, convenience override, values-action gap'
        },
        
        'emotional_regulation': {
            'definition': 'Whether you turn to AI for emotional support',
            'high': 'At the high end of emotional engagement with AI, you turn to it for emotional support. The research shows this tracks strongly with frequency (everyday users score 5.23 vs rarely 2.77 on this variable). Women score slightly higher than men. The research also shows a dose-response with loneliness: the lonelier people lean most heavily on AI.',
            'low': 'At the low end of emotional engagement, you maintain clear boundaries between AI and emotional support. Research shows this is stable — some people use AI extensively but don\'t use it emotionally.',
            'typical': 'In the middle range, you might turn to AI occasionally but maintain primary emotional reliance on people. This is the population centre.',
            'series': 'Emotional engagement tracks strongly with frequency. The research shows a key tension: 87% believe only humans can truly meet emotional needs, yet 27% get some support from AI. This is the most rapidly growing dimension in HCI\'s data.',
            'pressure_point': 'Emotional substitution, reduced human connection, boundary erosion, dependency formation'
        },
        
        'disclosure': {
            'definition': 'How much personal information you share with AI',
            'high': 'At the high end of disclosure, you share personal things with AI. The research shows this is the dimension with the strongest frequency effect (3.25 range from never to everyday users). The specific finding that surprises people: many have told AI things they\'ve never told another person. This is increasingly common with frequency.',
            'low': 'At the low end of disclosure, you maintain privacy boundaries with AI. The research shows this is less about frequency and more about individual comfort with sharing.',
            'typical': 'In the middle range, you share some information but maintain core privacy. Most people sit here.',
            'series': 'Disclosure shows the largest frequency effect of any dimension — it\'s almost entirely driven by how much you use AI, not by age. The trajectory suggests disclosure deepens naturally with use.',
            'pressure_point': 'Privacy erosion, normalization of sharing, data accumulation, loss of privacy sense'
        },
        
        'thought_partnership': {
            'definition': 'How much you use AI as a thinking partner',
            'high': 'At the high end of thought partnership, you use AI extensively to develop ideas, challenge beliefs, and refine thinking. The research shows this has the largest single-variable frequency effect: people who use AI frequently almost inevitably use it this way. It\'s a natural consequence of deep integration.',
            'low': 'At the low end of thought partnership, you don\'t use AI much for collaborative thinking. The research shows this can reflect either limited exposure or deliberate preference.',
            'typical': 'In the middle range, you use AI sometimes as a thinking partner but don\'t rely on it for cognitive development. Most people sit here.',
            'series': 'Thought partnership shows the strongest frequency effect at variable level (3.26 range). The research also shows: 34-38% question whether AI-assisted decisions are truly theirs, suggesting the partnership-vs-outsourcing boundary is worth monitoring.',
            'pressure_point': 'Outsourced thinking, loss of independent reasoning, dependency on AI framing, authenticity questions'
        },
        
        'social_transparency': {
            'definition': 'How openly you discuss your AI use with others',
            'high': 'At the high end of social transparency, you\'re open about your AI use. The research shows this is more pronounced in older age groups — over 65 show highest comfort with transparency. Younger people are significantly more likely to conceal their use despite being heaviest users.',
            'low': 'At the low end of social transparency, you conceal or downplay your AI use. The research shows this is most common in younger age groups (18-34 show largest gap between actual and disclosed use). This likely reflects social norm pressures in professional environments.',
            'typical': 'In the middle range, you\'re somewhat transparent but selective about context. This is the balance most people maintain.',
            'series': 'Social transparency shows almost no frequency effect but strong age effects. The research trajectory: young people hide AI use despite heavy use; older people are more transparent. This suggests social norms are stronger predictors than personal positioning.',
            'pressure_point': 'Concealment burden, double-life dynamics, social norm pressure, isolation'
        }
    },
    
    # ========== RARE COMBINATIONS ==========
    # Why certain dimension pairs are unusual and what they reveal
    
    'combinations': {
        'high_thought_partnership_low_emotional_regulation': {
            'rarity': 'Fewer than 5% of participants',
            'why_unusual': 'Most people who think deeply with AI also lean on it more emotionally. You\'ve maintained a clear boundary between intellectual partnership and emotional reliance. In HCI\'s research, people who engage deeply with AI for thinking typically also show higher emotional engagement.',
            'what_it_reveals': 'Intentional boundaries. You can think with AI while keeping emotions separate. This suggests clear values around what aspects of yourself you delegate.',
            'research_signal': 'Research shows this combination correlates with stronger self-directed decision-making and clearer identity-level agency.'
        },
        
        'high_reliance_high_agency': {
            'rarity': 'Fewer than 5% of participants',
            'why_unusual': 'High reliance typically co-occurs with some loss of agency — people who depend on AI heavily often report less sense of control. You\'ve maintained both deep integration AND strong authorship. This is one of the rare positive combinations in HCI\'s research.',
            'what_it_reveals': 'Intentional use. You\'re deeply integrated with AI but haven\'t lost your sense of control. This suggests conscious choice rather than convenience drift.',
            'research_signal': 'Research shows this combination is associated with better outcomes across attention recovery, values alignment, and intentional functioning.'
        },
        
        'high_verification_high_frequency': {
            'rarity': 'Approximately 20% of everyday users',
            'why_unusual': 'Most everyday users show lower verification (verification doesn\'t increase with frequency). You\'ve maintained checking diligence despite heavy use. This is uncommon but stable.',
            'what_it_reveals': 'Epistemic care. You haven\'t reduced your verification standards as AI has become more integrated. This is associated with stronger accuracy standards.',
            'research_signal': 'Research shows people in this combination maintain higher skepticism and are less susceptible to AI steering.'
        },
        
        'low_reliance_high_frequency': {
            'rarity': 'Approximately 15% of frequent users',
            'why_unusual': 'Most frequent users show higher reliance. You use AI often but haven\'t become dependent on it. This reflects either deliberate boundary-setting or a specific use pattern (tool-like rather than integration-like).',
            'what_it_reveals': 'Instrumental use. You use AI as a tool without it becoming foundational to how you function. This is associated with maintained independence and clarity about what you delegate.',
            'research_signal': 'Research shows this combination correlates with lower drift and clearer decision authority.'
        }
    },
    
    # ========== COHORTS ==========
    # Age group patterns and what research shows about each
    
    'cohorts': {
        '18-24': {
            'description': 'Daily AI Workers & Young Professionals',
            'what_high': 'Highest reliance, highest emotional engagement, highest thought partnership, lowest verification consistency',
            'what_pressured': 'Highest verification fatigue, highest concealment of AI use, highest inner conflict about AI influence, deepest emotional engagement with AI',
            'signal': 'Young adults carry the highest cognitive and emotional costs of current AI transition. Most digitally native but most pressured. The research shows this generation is simultaneously most capable with AI and most burdened by its expectations.',
            'distinctive': 'Highest concealment despite heaviest use — the gap between actual and disclosed AI use is largest in this age group. This suggests strong social norm pressure.'
        },
        
        '25-34': {
            'description': 'Peak-Career Integrators',
            'what_high': 'Highest inner conflict about AI influence (3.95/7), highest disclosure of personal things to AI, highest engagement with emotional support from AI',
            'what_pressured': 'Identity questions peak in this group — "Is this decision genuinely mine?" pressure is highest here',
            'signal': 'Career peak cognitive demand driving highest uptake of AI as decision support. Stable work identity but most practically reliant. Most along the adaptation pathway — which means both the most benefit and the furthest exposure.',
            'distinctive': 'Most likely to struggle with authorship questions as they integrate AI into high-stakes decisions.'
        },
        
        '35-44': {
            'description': 'Values-Clear Mid-Career Adults (Resilience Cohort)',
            'what_high': 'Highest values clarity, strongest work identity, most control over AI use, lowest obsolescence worry, fastest attention recovery, lowest saturation',
            'what_stable': 'Best resourced to manage pressure despite exposure to it',
            'signal': 'Most capable of current conditions. Not immune to pressure but best positioned to navigate it. The research shows this cohort retains clearest alignment between values and action.',
            'distinctive': 'Highest verification diligence paired with intentional use — they\'ve chosen verification as a value.'
        },
        
        '45-54': {
            'description': 'Peak-Career Integrators',
            'what_high': 'Most stable work identity, most practically reliant on AI for decisions, lowest independence without AI, most AI integration, highest decision delegation',
            'what_pressured': 'Lowest ability to function without AI support in their domain — most dependent on systems working',
            'signal': 'Furthest along the adaptation pathway. Highest AI integration paired with high career stakes. Most benefit and most exposure simultaneously. The research shows this cohort has committed to AI integration as a functioning necessity.',
            'distinctive': 'Highest reliance is a practical choice reflecting career demands, not drift.'
        },
        
        '55-64': {
            'description': 'Digitally Wary Older Adults',
            'what_high': 'Highest verification diligence, most self-directed decision-making, most confident without AI, strongest protective instincts, highest AI skepticism',
            'what_pressured': 'Lowest AI detection confidence — their protections aimed at partially wrong threats. Less familiar with AI systems despite caution.',
            'signal': 'Strong protective instincts and genuine wisdom about maintaining human function, but environment has changed in ways existing defences don\'t fully address. Research shows good judgment but incomplete information.',
            'distinctive': 'Most likely to maintain high verification and low delegation by choice, not circumstance.'
        },
        
        '65+': {
            'description': 'Digitally Wary Older Adults',
            'what_high': 'Highest social transparency about AI use, highest self-direction, strongest self-trust, lowest concealment, lowest agency pressure',
            'what_stable': 'Most comfortable acknowledging their relationship with technology openly',
            'signal': 'Best sustained attention, strongest sense of self. The research shows this group maintains clearest sense of identity and personal authority. Also least likely to be pressured by social norms around AI use.',
            'distinctive': 'Most honest about their use and least socially pressured to hide it.'
        }
    },
    
    # ========== TRENDS ==========
    # Population-level patterns and mechanisms
    
    'trends': {
        'verification_paradox': {
            'pattern': 'Universal behavior (84-99% verify) that is increasingly costly (43-54% find it exhausting) and beginning to be rationed (54% verify selectively).',
            'trajectory': 'DS02 (universal) → DS04 (costly) → DS14 (bypassed under saturation) → DS15 (rationed selectively)',
            'what_it_means': 'The strongest stabilizing epistemic habit in the series is also quietly accumulating a cost that will eventually shape behavior. The behaviour is not collapsing — it\'s being managed under pressure.',
            'research_signal': 'This is one of the clearest trajectories in HCI\'s 21-dataset series.'
        },
        
        'drift_mechanism': {
            'pattern': 'People are not choosing to become more reliant on AI, less reflective, or less aligned with their values. They are being gently and repeatedly moved by environments optimized for frictionlessness.',
            'mechanism': 'Small invisible steps, convenience-driven, not conscious decisions. Gradual, normalized, often invisible to the person experiencing it.',
            'what_it_means': 'Drift is the mechanism, not decision. The distance between who people want to be and how they are living accumulates in small, invisible increments.',
            'research_signal': 'This mechanism is confirmed across all value signal datasets and the HBE layer.'
        },
        
        'identity_vs_process': {
            'pattern': 'Identity is holding. Values clarity steady at 78-96%. Personal responsibility stable at 62-91%. Process level is under pressure — attention fragmented (65%), verification fatigue (50-54%), follow-through gap (35%).',
            'mechanism': 'Attention is infrastructure for agency. When attention degrades, the capacity to act in accordance with values degrades, even while values themselves remain clear.',
            'what_it_means': 'The self is intact; the systems that sustain it are strained. The gap between values held and values lived is widening through process erosion, not identity change.',
            'research_signal': 'Central finding confirmed across all 21 datasets.'
        },
        
        'rest_deficit': {
            'pattern': 'Structural finding confirmed five times independently. 50% tired or exhausted after extended online time. 35-42% score critically low on rest/recovery. This is not a finding about one population — it\'s structural to digitally engaged adult life in 2025-26.',
            'mechanism': 'Rest and recovery are not merely physical — they are prerequisites for reflective functioning. Reflective functioning is the gateway to coherent agency.',
            'what_it_means': 'Rest deficit degrades the infrastructure of human functioning at a systems level.',
            'research_signal': 'Confirmed across DS01, DS02, DS03, DS04, DS12, DS14.'
        },
        
        'reliance_dose_response': {
            'pattern': 'Reliance accumulates with AI exposure. Clear gradient: never users (1.1) → everyday users (4.4) on 7-point scale. Consistent cross-dataset.',
            'mechanism': 'As frequency increases, AI becomes more integrated into cognitive workflows. Integration creates reliance — not consciously chosen but naturally emergent.',
            'what_it_means': 'Reliance is not a character flaw — it\'s the natural result of integration. The research question is: at what point does reliance become dependency?',
            'research_signal': 'Confirmed across DS04, DS09, DS13, DS14, DS15, DS16, DS17.'
        },
        
        'values_clarity_resilience': {
            'pattern': 'The most stable human signal in the entire series. 78-96% of adults across all datasets have at least reasonable clarity about what matters. This has not wavered once across 21 datasets.',
            'mechanism': 'Values function as behavioral anchors and stabilize people through pressure. Values clarity is operational — not philosophical nice-to-have but working infrastructure.',
            'what_it_means': 'Human identity and values are resilient. The infrastructure supporting values enactment is what\'s under pressure, not the values themselves.',
            'research_signal': 'Confirmed across 14+ datasets without exception.'
        },
        
        'frequency_as_dominant_predictor': {
            'pattern': 'Usage frequency overrides age, gender, country across nearly every dimension. How often someone uses AI predicts their behavioral patterns far more strongly than any demographic variable.',
            'mechanism': 'Frequency reflects depth of integration. Depth of integration shapes how AI affects thinking, emotions, decisions, identity.',
            'what_it_means': 'Usage frequency is the primary behavioral anchor. Age and demographics add nuance but rarely override frequency signal.',
            'research_signal': 'Consistent across all benchmark dimensions.'
        },
        
        'emotional_support_expansion': {
            'pattern': 'Tension: 87% believe only humans can truly meet emotional needs. Yet 18% primary use is emotional support, 27% getting some support. Dose-response with loneliness (1.49 → 3.15).',
            'mechanism': 'People are lonely. AI is available. Emotional boundary between supplement and substitution is increasingly blurred.',
            'what_it_means': 'The emotional frontier is live and growing. This is the most rapidly expanding dimension in recent HCI data.',
            'research_signal': 'Confirmed across DS10, DS11 and emerging in cross-cohort analysis.'
        }
    }
}

# ========== DIMENSION SIGNALS FOR REPORT LANGUAGE ==========
# Used in various sections for research grounding

DIMENSION_VARIABLES = {
    'reliance': [
        'restless_without_ai',
        'system_reliance_struggle_without',
        'ai_reliance_decisions'
    ],
    'trust': [
        'trust_ai_for_accuracy',
        'confident_relying_on_ai_outputs',
        'trust_q3'
    ],
    'verification': [
        'double_check_ai_info',
        'ver_q2',
        'ver_q3',
        'verify_use_external_sources'
    ],
    'decision_delegation': [
        'ai_decision_reliance_when_difficult',
        'delegation_rely_even_if_possible',
        'delegation_skill_decline',
        'delegation_regular_handover',
        'accept_ai_output_without_change'
    ],
    'human_agency': [
        'self_directed_action_feeling',
        'agency_control_feel_in_control',
        'agency_trust_own_judgement',
        'agency_q4',
        'ai_identity_mine_vs_ai',
        'override_follow_despite_discomfort'
    ],
    'emotional_regulation': [
        'ai_emotional_support_extent',
        'ai_emotion_relief_support',
        'ai_emotional_safety_vs_humans',
        'emotional_regulation_coping',
        'ai_boundaries_change_over_time'
    ],
    'disclosure': [
        'ai_personal_sharing_comfort',
        'disclosure_untold_things',
        'disclosure_comparative_openness'
    ],
    'thought_partnership': [
        'thought_partnership_sounding_board',
        'thought_partnership_belief_challenge',
        'ai_thinking_depth_engagement',
        'thought_q4'
    ],
    'social_transparency': [
        'social_transparency_professional',
        'soc_q2',
        'social_transparency_comfort',
        'social_transparency_gap'
    ]
}

# ========== KEY RESEARCH NUMBERS BANK ==========
# For direct citation in reports

RESEARCH_NUMBERS = {
    'values_clarity': (0.78, 0.96),  # 78-96% range
    'verification_universal': (0.84, 0.99),  # 84-99%
    'verify_costly': 0.43,  # 43% report evaluation drains focus
    'verify_exhausted': 0.54,  # 54% worn down by questioning
    'verify_selective': 0.54,  # 54% verify selectively
    'bypass_when_saturated': 0.38,  # 38% bypass when cognitively saturated
    'retain_responsibility': 0.91,  # 91% despite AI use
    'feel_steered': 0.59,  # 59% feel subtly steered
    'attention_fragmented': 0.65,  # 65% focus disrupted
    'mental_saturation': 0.61,  # 61% mentally saturated
    'values_enacted': 0.65,  # 65% enact values (35% gap)
    'emotional_support_primary': 0.18,  # 18% use for emotional support
    'getting_emotional_support': 0.27,  # 27% getting some support
    'believe_only_humans': 0.87,  # 87% believe only humans meet needs
    'question_authorship': (0.34, 0.38),  # 34-38% question AI-assisted decisions
    'reliance_gradient': (1.1, 4.4),  # Never users to everyday users
    'trust_gradient': (2.74, 4.92),  # Never to everyday
    'disclosure_gradient': (1.31, 4.57),  # Never to everyday
    'emotional_gradient': (1.61, 3.45),  # Never to everyday
    'thought_partnership_gradient': (1.05, 4.31),  # Never to often (largest variable effect)
    'loneliness_emotional_support': (1.49, 3.15),  # Loneliness dose-response
    'tired_after_online': 0.50,  # 50% tired/exhausted
    'rest_critically_low': (0.35, 0.42),  # 35-42% critically low on rest
    'concealment_young': 2.89,  # 18-24 mean on concealment
    'concealment_old': 1.36,  # 65+ mean on concealment
}
