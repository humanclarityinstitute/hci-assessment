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
    },
    
    # ========== OPENING SECTION ==========
    # Pre-written static opening statement for premium reports
    'opening': {
        'prewritten_statement': """You are uniquely positioned in how you relate to AI. Your profile reflects how you currently engage with AI systems — based on your responses benchmarked against 10,500 participants across 21 research studies.

Use this report to understand your pattern:
• Understand what's distinctive about how you work with AI
• Notice where you're typical and where you stand out
• Explore what's worth protecting as your use evolves
• Make conscious choices about your relationship with AI going forward"""
    }
}


# ========== PARTICIPANT-FACING REPORT-SAFE SIGNALS ==========
#
# The original SIGNALS dictionary above is retained unchanged as HCI's internal
# research synthesis. It may contain exploratory hypotheses, shorthand and stronger
# internal interpretations that should not be passed directly into participant-facing
# reports.
#
# REPORT_SAFE_SIGNALS preserves the strongest supported descriptive evidence while
# separating measured findings from interpretation and evidential limits.
#
# Only REPORT_SAFE_SIGNALS should be supplied to Claude or inserted into customer
# reports. The existing keys are mirrored for straightforward downstream integration.
# Trend entries also include an explicit "evidence_boundary" field so the context
# builder can pass Claude the line it must not cross.

REPORT_SAFE_SIGNALS = {

    'dimensions': {

        'reliance': {
            'definition': 'How central AI is within your reported thinking and day-to-day functioning',
            'high': 'At the higher end of reliance, you report that AI is deeply integrated into how you work and think. This is common among everyday users in HCI samples. It may provide efficiency and clarity in familiar tasks, while also making AI availability more relevant to how easily some tasks feel.',
            'low': 'At the lower end of reliance, you report greater independence from AI systems. Within HCI samples, this pattern appears among both less frequent users and some frequent users who keep AI within narrower roles.',
            'typical': 'In the middle range on reliance, you report using AI selectively without making it central to how you function. This sits near the centre of the HCI participant benchmark.',
            'series': 'In the relevant HCI measure, average reliance increased from 1.1 among never-users to 4.4 among everyday users. This was one of the strongest frequency-related differences in the data and shows that reliance is closely associated with how embedded AI is in participants’ everyday workflows.',
            'pressure_point': 'Verification effort, independent task practice, and clarity about decision boundaries'
        },

        'trust': {
            'definition': 'How much confidence you report having in the accuracy of AI outputs',
            'high': 'At the higher end of trust, you report greater confidence in AI accuracy. Everyday users in the relevant HCI comparison scored nearly 2.5 points higher than non-users. Your position may reflect experience with AI, the kinds of tasks you use it for, or how you approach checking its outputs.',
            'low': 'At the lower end of trust, you report greater caution about AI outputs. Around 15% of participants remained cautious regardless of exposure in the relevant HCI analysis. This describes a more sceptical pattern, not whether that level of caution is right for every task.',
            'typical': 'In the middle range on trust, you report balancing confidence with caution. This sits near the centre of the HCI participant benchmark.',
            'series': 'Trust was substantially higher among everyday users than never-users in HCI samples. Older adults also reported more caution when uncertain. These are group-level differences rather than proof that frequency or age causes an individual’s trust level.',
            'pressure_point': 'Calibration between confidence, task importance, and verification'
        },

        'verification': {
            'definition': 'How often you report checking AI outputs before using them',
            'high': 'At the higher end of verification, checking is one of the more consistent features of your reported AI use. Across HCI studies, 84–99% of participants reported verifying AI outputs in at least some circumstances, although the consistency and effort involved varied.',
            'low': 'At the lower end of verification, you report using AI outputs with less extensive checking. This describes your current response pattern and should not be interpreted as laziness, negligence, or a fixed personal trait.',
            'typical': 'In the middle range on verification, you report checking some outputs but not others. This is common across different AI-use frequencies in the HCI participant benchmark.',
            'series': 'Verification differed less by AI-use frequency than most other dimensions in HCI samples. Age-group differences were more visible, with older adults generally reporting more consistent checking. At the same time, 43–54% of participants in relevant studies reported verification fatigue or exhaustion.',
            'pressure_point': 'Verification effort, selective checking, and cognitive load'
        },

        'decision_delegation': {
            'definition': 'How readily you report allowing AI recommendations to shape or determine decisions',
            'high': 'At the higher end of decision delegation, you report acting on AI recommendations more readily and with less independent reconsideration. HCI samples show higher delegation among some younger and more frequent user groups. In one relevant study, 26% reported reduced oversight over time.',
            'low': 'At the lower end of decision delegation, you report retaining more personal oversight over decisions. In one HCI study, 65% of participants aged over 65 reported making their own decision regardless of the AI recommendation.',
            'typical': 'In the middle range on delegation, you report considering AI input while retaining a meaningful role in the final decision. This sits near the centre of the HCI participant benchmark.',
            'series': 'Delegation was generally higher among more frequent users and younger age groups in HCI samples. Some participants also reported less oversight than they recalled having previously, but a one-time assessment cannot establish whether an individual’s oversight has changed.',
            'pressure_point': 'Personal oversight, habitual acceptance, and clarity about responsibility'
        },

        'human_agency': {
            'definition': 'How much control and authorship you report retaining over your decisions',
            'high': 'At the higher end of agency, you report feeling self-directed and responsible for your thinking and decisions. Across relevant HCI studies, 91% retained personal responsibility even while 59% reported feeling subtly steered in some situations. High agency places authorship among the clearer features of your current pattern.',
            'low': 'At the lower end of agency, you report less control or authorship in some decisions involving AI. This does not establish identity loss or reduced capability; it describes how control feels within your current response pattern.',
            'typical': 'In the middle range on agency, you report being generally self-directed while also experiencing some influence from AI. This sits near the centre of the HCI participant benchmark.',
            'series': 'Agency varied relatively little across AI-use frequencies in HCI samples, with a range of only 0.40 in the cited comparison. Everyday users reported slightly higher agency on average, while many participants still reported subtle AI influence. These findings show that agency and AI integration do not move in a simple one-directional relationship.',
            'pressure_point': 'Attention, convenience, and alignment between intention and action'
        },

        'emotional_regulation': {
            'definition': 'How often you report turning to AI for emotional support or regulation',
            'high': 'At the higher end of emotional engagement, you report using AI for emotional support more often. In the relevant HCI comparison, everyday users scored 5.23 compared with 2.77 among rare users. Emotional use was also higher among participants reporting greater loneliness.',
            'low': 'At the lower end of emotional engagement, you report keeping a clearer boundary between AI use and emotional support. Some participants use AI extensively for practical or cognitive tasks while reporting little emotional use.',
            'typical': 'In the middle range, you report turning to AI for emotional support occasionally rather than making it a central source of support. This sits near the centre of the HCI participant benchmark.',
            'series': 'Emotional engagement was strongly associated with AI-use frequency in HCI samples. A notable tension also appeared: 87% said only humans can truly meet emotional needs, while 27% reported receiving some emotional support from AI. This supports careful attention to the role AI currently plays without diagnosing substitution or dependency.',
            'pressure_point': 'Balance with human support, emotional boundaries, and reliance on AI availability'
        },

        'disclosure': {
            'definition': 'How much personal information you report sharing with AI',
            'high': 'At the higher end of disclosure, you report sharing more personal information with AI. Disclosure showed a 3.25-point range between never-users and everyday users in the relevant HCI measure, one of the largest frequency-related differences among the dimensions.',
            'low': 'At the lower end of disclosure, you report maintaining stronger privacy boundaries with AI. This may reflect the kinds of tasks you use AI for, your comfort with sharing, or deliberate limits.',
            'typical': 'In the middle range, you report sharing some personal information while retaining boundaries around other areas. This sits near the centre of the HCI participant benchmark.',
            'series': 'Disclosure showed one of the strongest associations with AI-use frequency in HCI samples and much less variation by age. This means frequent users tended to report more sharing, but it does not establish that disclosure inevitably increases for every individual.',
            'pressure_point': 'Privacy boundaries, normalisation of sharing, and awareness of accumulated information'
        },

        'thought_partnership': {
            'definition': 'How much you report using AI to develop, challenge, or refine your thinking',
            'high': 'At the higher end of thought partnership, you report using AI extensively to develop ideas, challenge beliefs, and refine thinking. The relevant HCI measure showed a 3.26-point difference across frequency groups, the largest single-variable frequency effect cited in this library.',
            'low': 'At the lower end of thought partnership, you report using AI less often for collaborative thinking. This may reflect limited exposure, the tasks you use AI for, or a preference to form ideas independently.',
            'typical': 'In the middle range, you report using AI as a thinking partner in some situations without making it central to how you develop ideas. This sits near the centre of the HCI participant benchmark.',
            'series': 'Thought partnership was strongly associated with AI-use frequency in HCI samples. Across related studies, 34–38% of participants questioned whether AI-assisted decisions felt fully their own, showing that collaborative thinking and authorship can coexist as an active tension.',
            'pressure_point': 'Independent view formation, reliance on AI framing, and authorship questions'
        },

        'social_transparency': {
            'definition': 'How openly you report discussing or acknowledging your AI use with other people',
            'high': 'At the higher end of social transparency, you report being more open about your AI use. Participants aged 65 and over showed the highest reported comfort with transparency in the cited HCI comparison.',
            'low': 'At the lower end of social transparency, you report concealing or downplaying some AI use. This pattern was more common among younger participants, particularly those aged 18–34, who showed the largest gap between reported use and disclosure.',
            'typical': 'In the middle range, you report being open in some contexts and more selective in others. This sits near the centre of the HCI participant benchmark.',
            'series': 'Social transparency showed little relationship with AI-use frequency but clear age-group differences in HCI samples. Social and professional context may help explain those differences, but the data does not establish a single cause.',
            'pressure_point': 'Comfort with disclosure, context, and perceived social expectations'
        }
    },

    'combinations': {
        'high_thought_partnership_low_emotional_regulation': {
            'rarity': 'Fewer than 5% of participants',
            'why_unusual': 'Within the HCI participant benchmark, high Thought Partnership more often appears alongside higher Emotional Regulation scores. Your responses show a less common separation: extensive cognitive engagement with AI alongside low reported emotional use.',
            'what_it_reveals': 'This combination suggests a clear current distinction between using AI as a thinking partner and using it for emotional support. The benchmark does not establish why that distinction exists, but it is one of the defining features of this profile.',
            'research_signal': 'Within HCI samples, this combination can coexist with comparatively strong reported agency and decision authorship. It should not be treated as proof of stronger identity or better outcomes.'
        },

        'high_reliance_high_agency': {
            'rarity': 'Fewer than 5% of participants',
            'why_unusual': 'Higher reliance often appears alongside lower reported agency in the HCI participant benchmark, but the relationship is not automatic. Your responses show deep integration alongside a strong current sense of control and authorship.',
            'what_it_reveals': 'This combination shows that relying heavily on AI and retaining a strong sense of authorship are distinct aspects of the relationship. It may reflect an integrated but still self-directed pattern, without proving how that pattern developed or how it will change.',
            'research_signal': 'This combination is distinctive because it departs from the more common relationship between reliance and agency. The available evidence does not support claims that it produces better attention, values alignment, or life outcomes.'
        },

        'high_verification_high_frequency': {
            'rarity': 'Approximately 20% of everyday users',
            'why_unusual': 'Verification did not rise consistently with AI-use frequency in HCI samples. Your responses show frequent use alongside consistently high checking, a pattern seen in only about one fifth of everyday users.',
            'what_it_reveals': 'This combination suggests that verification remains an active feature of your current AI use even where the technology is familiar and frequently used.',
            'research_signal': 'Within HCI samples, frequent use can coexist with high reported verification and continued scepticism about outputs. The data does not establish that this makes a participant less susceptible to steering.'
        },

        'low_reliance_high_frequency': {
            'rarity': 'Approximately 15% of frequent users',
            'why_unusual': 'Frequent AI use is generally associated with higher reliance in the HCI participant benchmark. Your responses show frequent use without a correspondingly high reported dependence on AI for functioning.',
            'what_it_reveals': 'This combination suggests a more instrumental or bounded current pattern of use. It may reflect deliberate limits, task-specific use, or another explanation not measured by the assessment.',
            'research_signal': 'This combination demonstrates that frequency and reliance are related but not interchangeable. It does not prove lower drift, greater independence, or clearer decision authority.'
        }
    },

    'cohorts': {
        '18-24': {
            'description': 'Daily AI Workers & Young Professionals',
            'what_high': 'Highest reported reliance, emotional engagement and thought partnership, alongside the lowest verification consistency',
            'what_pressured': 'Highest reported verification fatigue, concealment of AI use and inner conflict about AI influence',
            'signal': 'Within HCI samples, this cohort combined the most extensive AI engagement with some of the highest reported cognitive and emotional pressure. This is a strong cohort-level pattern, not a judgement about capability or burden for every individual.',
            'distinctive': 'This group showed the largest gap between reported AI use and disclosed AI use, indicating that concealment is especially relevant within the cohort. The data does not establish a single cause.'
        },

        '25-34': {
            'description': 'Peak-Career Integrators',
            'what_high': 'Highest reported inner conflict about AI influence, personal disclosure to AI and emotional engagement with AI',
            'what_pressured': 'Authorship questions were most pronounced in this group, including whether AI-assisted decisions felt fully their own',
            'signal': 'Within HCI samples, this cohort combined substantial AI integration with the highest reported uncertainty about authorship and influence. That distinction is evidence-based; claims about career demand causing the pattern would go beyond the available data.',
            'distinctive': 'Participants in this group were more likely than other cohorts to report questions about ownership of AI-assisted decisions.'
        },

        '35-44': {
            'description': 'Values-Clear Mid-Career Adults',
            'what_high': 'Highest reported values clarity, work identity and control over AI use, alongside the lowest obsolescence worry and saturation',
            'what_stable': 'Fastest reported attention recovery and comparatively high verification diligence',
            'signal': 'Within HCI samples, this cohort reported the clearest alignment between values, work identity and current AI-use boundaries. The evidence supports that comparative description, but not a conclusion that the cohort is inherently more capable or resilient.',
            'distinctive': 'This group combined the highest reported values clarity with comparatively strong verification and lower saturation.'
        },

        '45-54': {
            'description': 'Highly Integrated Mid-Career Users',
            'what_high': 'Highest reported AI integration, decision delegation and practical reliance, alongside the lowest reported independence without AI',
            'what_pressured': 'Greatest reported dependence on AI systems remaining available within their work domain',
            'signal': 'Within HCI samples, this cohort showed the deepest practical integration of AI into work and decisions. The evidence does not establish whether that integration arose from necessity, preference, career demands or gradual adoption.',
            'distinctive': 'This group’s high reliance appears alongside extensive use in consequential work and decision contexts.'
        },

        '55-64': {
            'description': 'Cautious Older AI Users',
            'what_high': 'Highest reported verification diligence, self-directed decision-making, confidence without AI and scepticism about AI outputs',
            'what_pressured': 'Lowest reported confidence in detecting AI-generated or unreliable material',
            'signal': 'Within HCI samples, this cohort combined strong caution and personal oversight with lower confidence in identifying some AI-system cues. The evidence supports both sides of that pattern without implying superior judgement or incomplete defences.',
            'distinctive': 'This group was the most likely to combine high verification with low decision delegation.'
        },

        '65+': {
            'description': 'Transparent and Self-Directed Older Users',
            'what_high': 'Highest reported social transparency, self-direction and self-trust, alongside the lowest concealment and agency pressure',
            'what_stable': 'Highest reported comfort acknowledging AI use openly',
            'signal': 'Within HCI samples, this cohort reported the strongest combination of personal authority and openness about technology use. These are comparative self-report findings, not fixed age-based traits or proof of a stronger identity.',
            'distinctive': 'This group reported the least concealment of AI use among the age cohorts studied.'
        }
    },

    'trends': {
        'verification_paradox': {
            'pattern': 'Across relevant HCI studies, 84–99% of participants reported verifying AI outputs in at least some circumstances. At the same time, 43–54% reported verification fatigue or exhaustion, and 54% reported verifying selectively.',
            'trajectory': 'Across the cited datasets, verification appears first as widespread, then as effortful, and later as increasingly selective under cognitive pressure.',
            'what_it_means': 'Verification remains one of the most widely reported safeguards in HCI research, but the effort involved appears to influence when and how consistently participants apply it.',
            'research_signal': 'This is one of the clearest recurring patterns across the HCI dataset series.',
            'evidence_boundary': 'The datasets show repeated cross-sectional and self-reported patterns. They do not prove that verification will weaken for an individual or that fatigue causes selective checking.'
        },

        'drift_mechanism': {
            'pattern': 'Across HCI values and human-experience datasets, some participants report greater reliance, less reflection, or a gap between what matters to them and how they act in environments designed for speed and convenience.',
            'mechanism': 'A plausible HCI interpretation is that small, repeated and convenience-driven changes may be less visible than deliberate decisions, allowing behavioural patterns to shift without a single clear turning point.',
            'what_it_means': 'The concept of drift helps explain why intention and day-to-day behaviour may diverge gradually rather than through one conscious choice.',
            'research_signal': 'Related signals recur across multiple HCI values and human-experience datasets.',
            'evidence_boundary': 'Drift is an interpretive framework, not a demonstrated universal mechanism. The available data does not establish that frictionless environments cause change in every participant.'
        },

        'identity_vs_process': {
            'pattern': 'Across HCI samples, 78–96% reported at least reasonable values clarity and 62–91% retained personal responsibility. At the same time, 65% reported attention disruption, 50–54% verification fatigue, and 35% a gap between values and follow-through.',
            'mechanism': 'One interpretation is that knowing what matters and being able to act consistently on it are distinct. Attention and cognitive load may affect the ease of follow-through even when values remain clear.',
            'what_it_means': 'The evidence suggests that clear values can coexist with practical difficulty enacting them. This distinction is more precise than claiming identity loss or an unmeasured decline in the processes supporting action.',
            'research_signal': 'The separation between values clarity and day-to-day enactment appears across multiple HCI datasets.',
            'evidence_boundary': 'The data does not establish that attention disruption causes reduced agency, that identity is objectively stable, or that capability has eroded.'
        },

        'rest_deficit': {
            'pattern': 'Across six cited HCI datasets, 50% of participants reported feeling tired or exhausted after extended online activity, while 35–42% recorded very low rest or recovery scores.',
            'mechanism': 'Rest and recovery may be relevant to sustained attention, reflection and decision-making, although the datasets do not establish the direction or cause of those relationships.',
            'what_it_means': 'Digital fatigue is a recurring and substantial context for interpreting attention, verification and decision-related responses.',
            'research_signal': 'Related findings appeared across DS01, DS02, DS03, DS04, DS12 and DS14.',
            'evidence_boundary': 'These findings should not be generalised to all digitally engaged adults or presented as proof that low rest causes reduced human functioning.'
        },

        'reliance_dose_response': {
            'pattern': 'In the relevant HCI measure, average reliance rose from 1.1 among never-users to 4.4 among everyday users. Similar frequency-related patterns appeared across seven cited datasets.',
            'mechanism': 'The strength and consistency of this gradient suggest that reliance is closely connected with how embedded AI becomes in participants’ workflows.',
            'what_it_means': 'Reliance is not a character judgement. It is an important behavioural dimension that tends to be higher among people who use AI more often and more centrally.',
            'research_signal': 'The frequency–reliance association appeared across DS04, DS09, DS13, DS14, DS15, DS16 and DS17.',
            'evidence_boundary': 'This is a strong association, not proof that frequent use inevitably causes reliance or that reliance has become clinical dependency.'
        },

        'values_clarity_resilience': {
            'pattern': 'Across more than 14 HCI datasets, 78–96% of participants reported at least reasonable clarity about what matters to them.',
            'mechanism': 'Values clarity may provide a reference point during pressure or change, but the evidence does not show that clarity alone guarantees consistent action.',
            'what_it_means': 'Knowing what matters appears to be one of the most consistent human signals in the HCI research series, while acting consistently on those values remains a separate question.',
            'research_signal': 'High reported values clarity recurred across more than 14 datasets.',
            'evidence_boundary': 'The pattern supports a strong descriptive claim about reported values clarity, not proof of identity resilience, protection from pressure, or stable behaviour over time.'
        },

        'frequency_as_dominant_predictor': {
            'pattern': 'Across the HCI benchmark dimensions, AI-use frequency showed stronger relationships with many behavioural differences than age, gender or country.',
            'mechanism': 'Frequency may partly reflect how deeply AI is integrated into everyday activity, making it a useful comparison variable across reliance, trust, disclosure, emotional engagement and thought partnership.',
            'what_it_means': 'Usage frequency is one of the most informative organising variables in the HCI benchmark. Demographic differences still add context, but often explain less variation.',
            'research_signal': 'Frequency-related differences appeared across nearly all benchmark dimensions.',
            'evidence_boundary': 'Frequency is associated with these patterns but should not be described as a causal predictor of an individual’s thinking, emotions, decisions or identity.'
        },

        'emotional_support_expansion': {
            'pattern': 'Across relevant HCI studies, 87% said only humans can truly meet emotional needs, while 18% reported emotional support as a primary AI use and 27% reported receiving some emotional support from AI. Emotional-support scores also rose from 1.49 to 3.15 across the cited loneliness comparison.',
            'mechanism': 'Availability, privacy and ease of access may help explain why some participants turn to AI for emotional support, but the available data does not establish a single reason.',
            'what_it_means': 'Emotional use is a significant and emerging part of the human–AI relationship, with a clear tension between receiving support from AI and viewing human connection as distinct.',
            'research_signal': 'Related patterns appeared across DS10, DS11 and cross-cohort analyses.',
            'evidence_boundary': 'The evidence does not establish emotional substitution, dependency, reduced human connection, or growth over time for an individual.'
        }
    },

    'opening': {
        'prewritten_statement': """Your profile reflects how you currently report engaging with AI, compared with the HCI participant benchmark. The benchmark is informed by more than 10,000 participant responses across 21 HCI studies.

Use this report to understand your current pattern:
• See what is distinctive about your responses
• Notice where you are broadly typical and where you differ
• Explore the human capabilities connected with your current pattern
• Establish a reference point that can be compared with a later measurement"""
    }
}

# ========== DIMENSION SIGNALS FOR REPORT LANGUAGE ==========
# Used in various sections for research grounding

DIMENSION_VARIABLES = {
    'reliance': [
        'rel_q1',
        'rel_q2',
        'rel_q3',
        'rel_q4',
        'rel_q5'
    ],
    'trust': [
        'trust_q1',
        'trust_q2',
        'trust_q3',
        'trust_q4'
    ],
    'verification': [
        'ver_q1',
        'ver_q2',
        'ver_q3',
        'ver_q4'
    ],
    'decision_delegation': [
        'del_q1',
        'del_q2',
        'del_q3',
        'del_q4',
        'del_q5'
    ],
    'human_agency': [
        'agency_q1',
        'agency_q2',
        'agency_q3',
        'agency_q4',
        'agency_q5'
    ],
    'emotional_regulation': [
        'emot_q1',
        'emot_q2',
        'emot_q3',
        'emot_q4'
    ],
    'disclosure': [
        'disc_q1',
        'disc_q2',
        'disc_q3',
        'disc_q4'
    ],
    'thought_partnership': [
        'thought_q1',
        'thought_q2',
        'thought_q3',
        'thought_q4'
    ],
    'social_transparency': [
        'soc_q1',
        'soc_q2',
        'soc_q3',
        'soc_q4'
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
