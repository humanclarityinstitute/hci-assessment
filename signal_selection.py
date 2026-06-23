# Signal Selection Logic for Report Generator
## Functions that intelligently select which research signals apply per context
## Implements Option B: Layered by Significance (light treatment for expected, full treatment for distinctive)

from benchmark_context_data import (
    FREQUENCY_GRADIENTS, AGE_COHORT_PATTERNS, DISTINCTIVE_FLAGS,
    KEY_FINDINGS_FOR_REPORTS, COHORT_NARRATIVES, PRESSURE_POINTS
)
from hci_signals_library import SIGNALS, RESEARCH_NUMBERS
from human_reference_layer import (
    HBE_SIGNALS, VALUES_SIGNALS, REFRAMING_RULES, COHERENCE_PATTERNS,
    PRESSURE_POINT_ASSESSMENTS
)

# ============================================================
# CORE LOGIC: CALCULATE DISTINCTIVENESS
# ============================================================

def calculate_distinctiveness(actual_score, frequency_expectation, age_expectation=None):
    """
    Calculate how much actual score diverges from what frequency (and age) would predict.
    
    Returns:
    {
        'divergence': float,
        'divergence_pct': float,
        'level': 'expected' | 'slightly_divergent' | 'distinctive' | 'highly_distinctive',
        'direction': 'above' | 'below',
        'significance': float (0-1, how much treatment to give)
    }
    """
    
    # Calculate divergence from frequency expectation
    divergence = actual_score - frequency_expectation
    divergence_pct = (divergence / frequency_expectation * 100) if frequency_expectation != 0 else 0
    
    # Determine level based on divergence magnitude
    abs_div = abs(divergence)
    
    if abs_div <= 0.3:  # Less than 0.3 points divergence
        level = 'expected'
        significance = 0.3  # Light treatment
    elif abs_div <= 0.8:  # 0.3-0.8 points divergence
        level = 'slightly_divergent'
        significance = 0.6  # Medium treatment
    elif abs_div <= 1.5:  # 0.8-1.5 points divergence
        level = 'distinctive'
        significance = 0.85  # Full treatment
    else:  # More than 1.5 points
        level = 'highly_distinctive'
        significance = 1.0  # Full treatment + emphasis
    
    direction = 'above' if divergence > 0 else 'below'
    
    return {
        'divergence': round(divergence, 2),
        'divergence_pct': round(divergence_pct, 1),
        'level': level,
        'direction': direction,
        'significance': significance
    }


def get_distinctiveness_flag(dimension, actual_score, frequency, age_group, divergence_info):
    """
    Check if this score matches any pre-identified distinctive flags.
    
    Returns list of applicable flags with their meanings.
    """
    applicable_flags = []
    
    # Map dimension scores to check against DISTINCTIVE_FLAGS
    high_threshold = 0.75  # Percentile threshold for "high"
    low_threshold = 0.35
    
    actual_pct = actual_score / 7.0  # Normalize to 0-1 (7-point scale)
    
    flag_checks = {
        'high_verification_high_frequency': 
            dimension == 'verification' and actual_pct > high_threshold and frequency == 'everyday',
        
        'low_reliance_high_frequency':
            dimension == 'reliance' and actual_pct < low_threshold and frequency == 'everyday',
        
        'high_emotional_engagement_low_frequency':
            dimension == 'emotional_regulation' and actual_pct > high_threshold and frequency in ['rarely', 'sometimes'],
        
        'low_disclosure_high_frequency':
            dimension == 'disclosure' and actual_pct < low_threshold and frequency == 'everyday',
        
        'low_emotional_engagement_high_frequency':
            dimension == 'emotional_regulation' and actual_pct < low_threshold and frequency == 'everyday',
    }
    
    for flag_name, condition in flag_checks.items():
        if condition:
            flag_data = DISTINCTIVE_FLAGS.get(flag_name, {})
            applicable_flags.append({
                'flag': flag_name,
                'rarity': flag_data.get('rarity'),
                'meaning': flag_data.get('meaning'),
                'research_insight': flag_data.get('research_insight')
            })
    
    return applicable_flags


# ============================================================
# LAYER SELECTION: CHOOSE SIGNAL DEPTH
# ============================================================

def select_signal_layers(dimension, frequency, age_group, distinctiveness_info):
    """
    Based on distinctiveness level, select which research layers to include.
    
    Implements Option B: Light for expected, full for distinctive
    
    Returns:
    {
        'include_benchmark': bool,
        'include_master_synthesis': bool,
        'include_human_reference': bool,
        'depth': 'light' | 'medium' | 'full',
        'emphasis_level': 'brief' | 'standard' | 'detailed'
    }
    """
    
    level = distinctiveness_info['level']
    significance = distinctiveness_info['significance']
    
    if level == 'expected':
        # Expected pattern: keep it brief, just benchmark context
        return {
            'include_benchmark': True,
            'include_master_synthesis': False,
            'include_human_reference': False,
            'depth': 'light',
            'emphasis_level': 'brief',
            'note': 'This is a normal pattern for their frequency + age'
        }
    
    elif level == 'slightly_divergent':
        # Slightly unusual: benchmark + brief master synthesis
        return {
            'include_benchmark': True,
            'include_master_synthesis': True,
            'include_human_reference': False,
            'depth': 'medium',
            'emphasis_level': 'standard',
            'note': 'This diverges slightly from what frequency would predict'
        }
    
    elif level == 'distinctive':
        # Distinctive: full three-layer treatment
        return {
            'include_benchmark': True,
            'include_master_synthesis': True,
            'include_human_reference': True,
            'depth': 'full',
            'emphasis_level': 'detailed',
            'note': 'This pattern is distinctly unusual and reveals something meaningful'
        }
    
    else:  # highly_distinctive
        # Highly distinctive: full treatment with emphasis
        return {
            'include_benchmark': True,
            'include_master_synthesis': True,
            'include_human_reference': True,
            'depth': 'full',
            'emphasis_level': 'detailed',
            'add_emphasis': True,
            'note': 'This is a rare and particularly meaningful pattern'
        }


# ============================================================
# BENCHMARK SIGNAL SELECTION
# ============================================================

def select_benchmark_signals(dimension, frequency, age_group, actual_percentile, divergence_info):
    """
    Select specific benchmark findings relevant to this score.
    
    Returns:
    {
        'frequency_context': str,
        'age_context': str,
        'rarity_statement': str,
        'comparison_statement': str
    }
    """
    
    freq_grad = FREQUENCY_GRADIENTS.get(dimension, {})
    age_cohort = AGE_COHORT_PATTERNS.get(age_group, {})
    
    # Frequency context
    frequency_context = (
        f"For your {frequency} usage level, HCI's benchmark shows {dimension.replace('_', ' ')} "
        f"typically clusters around {int(freq_grad.get('range', 0))} points of variation. "
        f"Most {frequency} users score around the {int(actual_percentile - (divergence_info['divergence'] / 0.07))}th percentile."
    )
    
    # Age context
    age_note = age_cohort.get('distinctive', [])
    if age_note:
        age_context = f"For your age group ({age_group}), research shows: {age_note[0] if age_note else 'standard positioning'}"
    else:
        age_context = ""
    
    # Rarity statement
    if actual_percentile >= 97:
        rarity_statement = f"Fewer than {100 - actual_percentile}% of participants score this high"
    elif actual_percentile >= 86:
        rarity_statement = f"Only {100 - actual_percentile}% of participants score similarly"
    elif actual_percentile <= 3:
        rarity_statement = f"Fewer than {actual_percentile + 1}% of participants score this low"
    elif actual_percentile <= 14:
        rarity_statement = f"Only {actual_percentile}% of participants score similarly"
    else:
        rarity_statement = None
    
    # Comparison statement
    freq_expectation_pct = freq_grad.get('range', 50)  # Placeholder
    if abs(divergence_info['divergence']) > 0.5:
        comparison_statement = (
            f"This diverges from typical {frequency} user positioning by {divergence_info['divergence_pct']}%, "
            f"suggesting {divergence_info['direction']} typical frequency-based adaptation"
        )
    else:
        comparison_statement = (
            f"This aligns with typical {frequency} user positioning"
        )
    
    return {
        'frequency_context': frequency_context,
        'age_context': age_context,
        'rarity_statement': rarity_statement,
        'comparison_statement': comparison_statement
    }


# ============================================================
# MASTER SYNTHESIS SIGNAL SELECTION
# ============================================================

def select_master_synthesis_signals(dimension, actual_percentile, divergence_direction, frequency, age_group):
    """
    Select Master Synthesis findings relevant to this dimension/positioning.
    
    Returns:
    {
        'definitive_finding': str,
        'research_quote': str,
        'mechanism': str,
        'implication': str,
        'relevant_dataset': str
    }
    """
    
    # Get dimension signals from SIGNALS library
    dim_signals = SIGNALS['dimensions'].get(dimension, {})
    
    if actual_percentile >= 71:
        positioning_key = 'high'
    elif actual_percentile >= 41:
        positioning_key = 'typical'
    else:
        positioning_key = 'low'
    
    positioning_context = dim_signals.get(positioning_key, '')
    series_finding = dim_signals.get('series', '')
    pressure_point = dim_signals.get('pressure_point', '')
    
    # Select from KEY_FINDINGS based on dimension
    key_finding = KEY_FINDINGS_FOR_REPORTS.get(dimension + '_' + positioning_key, {})
    
    return {
        'positioning_context': positioning_context,
        'series_finding': series_finding,
        'pressure_point': pressure_point,
        'key_finding': key_finding.get('statement', ''),
        'implication': key_finding.get('implication', ''),
        'research_signal': dim_signals.get('definition', '')
    }


# ============================================================
# HUMAN REFERENCE LAYER SIGNAL SELECTION
# ============================================================

def select_human_reference_signals(dimension, actual_percentile, divergence_info, frequency, age_group):
    """
    Select HBE and Values signals that reframe the technical score as human functioning.
    
    Returns:
    {
        'hbe_signals': [list of relevant HBE insights],
        'values_signals': [list of relevant Values insights],
        'reframe_options': [suggested reframing language],
        'coherence_pattern': str (if applicable),
        'pressure_point_assessment': str (if risk detected)
    }
    """
    
    reframe_key = dimension
    reframe_options = REFRAMING_RULES.get(reframe_key, {}).get(
        'high' if actual_percentile >= 71 else ('low' if actual_percentile <= 40 else 'typical'),
        []
    )
    
    # Select HBE signals
    hbe_applicable = []
    if divergence_info['level'] in ['distinctive', 'highly_distinctive']:
        # High distinctiveness warrants HBE layer
        for signal_name, signal_data in HBE_SIGNALS.items():
            if dimension in str(signal_data.get('for_reports', [])):
                hbe_applicable.append({
                    'signal': signal_name,
                    'insight': signal_data.get('core_finding', ''),
                    'application': signal_data['for_reports'][0] if signal_data.get('for_reports') else ''
                })
    
    # Select Values signals
    values_applicable = []
    if divergence_info['level'] in ['distinctive', 'highly_distinctive']:
        # Check if this dimension relates to any values signals
        for signal_name, signal_data in VALUES_SIGNALS.items():
            if dimension in str(signal_data.get('for_reports', [])):
                values_applicable.append({
                    'signal': signal_name,
                    'insight': signal_data.get('core_finding', ''),
                    'application': signal_data['for_reports'][0] if signal_data.get('for_reports') else ''
                })
    
    # Assess for pressure points
    pressure_point_assessment = None
    pressure_keys = {
        'verification': 'verification_fatigue_emerging',
        'emotional_regulation': 'emotional_substitution_signal',
        'decision_delegation': 'decision_authority_erosion',
        'reliance': 'drift_mechanism_active'
    }
    
    if frequency == 'everyday' and actual_percentile < 40:
        ppa_key = pressure_keys.get(dimension)
        if ppa_key:
            pressure_point_assessment = PRESSURE_POINT_ASSESSMENTS.get(ppa_key, {})
    
    # Identify coherence pattern
    coherence_pattern = None
    if divergence_info['level'] in ['distinctive', 'highly_distinctive']:
        # Check if pattern matches known coherence patterns
        if dimension == 'human_agency' and actual_percentile > 71:
            if frequency == 'everyday':
                coherence_pattern = 'intentional_integration'
        elif dimension == 'verification' and actual_percentile > 71 and frequency == 'everyday':
            coherence_pattern = 'instrumental_mastery'
    
    return {
        'hbe_signals': hbe_applicable,
        'values_signals': values_applicable,
        'reframe_options': reframe_options,
        'coherence_pattern': coherence_pattern,
        'pressure_point_assessment': pressure_point_assessment
    }


# ============================================================
# UNIFIED SIGNAL SELECTION
# ============================================================

def prepare_complete_signal_context(dimension, actual_score, frequency, age_group, actual_percentile):
    """
    Master function: Calculate distinctiveness and select all appropriate signals.
    
    This is the core function called by report_generator.py for each dimension.
    
    Returns complete context object ready for API call.
    """
    
    # Step 1: Calculate distinctiveness
    frequency_expectation = FREQUENCY_GRADIENTS[dimension][frequency]
    distinctiveness = calculate_distinctiveness(actual_score, frequency_expectation)
    
    # Step 2: Determine signal layers
    signal_layers = select_signal_layers(dimension, frequency, age_group, distinctiveness)
    
    # Step 3: Collect all applicable signals
    context = {
        'dimension': dimension,
        'actual_score': actual_score,
        'actual_percentile': actual_percentile,
        'frequency': frequency,
        'age_group': age_group,
        'distinctiveness': distinctiveness,
        'signal_layers': signal_layers
    }
    
    # Benchmark signals (always included)
    context['benchmark_signals'] = select_benchmark_signals(
        dimension, frequency, age_group, actual_percentile, distinctiveness
    )
    
    # Master Synthesis signals (if significance >= 0.6)
    if signal_layers['include_master_synthesis']:
        context['master_synthesis_signals'] = select_master_synthesis_signals(
            dimension, actual_percentile, distinctiveness['direction'], frequency, age_group
        )
    
    # Human Reference signals (if significance >= 0.85)
    if signal_layers['include_human_reference']:
        context['human_reference_signals'] = select_human_reference_signals(
            dimension, actual_percentile, distinctiveness, frequency, age_group
        )
    
    # Check for distinctive flags
    context['distinctive_flags'] = get_distinctiveness_flag(
        dimension, actual_score, frequency, age_group, distinctiveness
    )
    
    # Add relevant pressure points
    if dimension in PRESSURE_POINTS:
        context['pressure_points'] = PRESSURE_POINTS[dimension]
    
    return context


# ============================================================
# UTILITY FUNCTIONS FOR REPORT GENERATOR
# ============================================================

def format_signal_context_for_api_prompt(context, section_name):
    """
    Convert signal context into Claude-ready prompt text.
    
    Takes the output from prepare_complete_signal_context()
    and formats it for injection into API call prompts.
    """
    
    prompt_parts = []
    
    # Always include benchmark context
    if context['benchmark_signals']['frequency_context']:
        prompt_parts.append(f"FREQUENCY CONTEXT: {context['benchmark_signals']['frequency_context']}")
    
    if context['benchmark_signals']['age_context']:
        prompt_parts.append(f"AGE COHORT CONTEXT: {context['benchmark_signals']['age_context']}")
    
    # Include distinctiveness assessment
    if context['distinctiveness']['level'] != 'expected':
        prompt_parts.append(
            f"DISTINCTIVENESS: This score is {context['distinctiveness']['level']} "
            f"({context['distinctiveness']['divergence_pct']}% divergence from frequency expectation)"
        )
    
    # Add Master Synthesis if included
    if 'master_synthesis_signals' in context:
        ms = context['master_synthesis_signals']
        if ms.get('series_finding'):
            prompt_parts.append(f"RESEARCH SIGNAL: {ms['series_finding']}")
        if ms.get('key_finding'):
            prompt_parts.append(f"KEY FINDING: {ms['key_finding']}")
    
    # Add Human Reference if included
    if 'human_reference_signals' in context:
        hr = context['human_reference_signals']
        if hr.get('reframe_options'):
            prompt_parts.append(
                f"REFRAMING SUGGESTION: Instead of '{context['dimension']}', consider: {hr['reframe_options'][0]}"
            )
        if hr.get('pressure_point_assessment'):
            ppa = hr['pressure_point_assessment']
            prompt_parts.append(f"PRESSURE POINT ALERT: {ppa.get('research', '')}")
    
    # Add distinctive flags
    if context['distinctive_flags']:
        flag = context['distinctive_flags'][0]
        prompt_parts.append(f"DISTINCTIVE FLAG: {flag['flag']} - {flag['meaning']}")
    
    return "\n".join(prompt_parts)


def should_emphasize_dimension(dimension, distinctiveness_level):
    """
    Returns True if this dimension should get prominent coverage in report.
    """
    return distinctiveness_level in ['distinctive', 'highly_distinctive']


# ============================================================
# SUMMARY
# ============================================================

"""
This module implements Option B: Layered by Significance

For each dimension, it:
1. Calculates how much the score diverges from frequency expectations
2. Determines signal layer depth based on distinctiveness
3. Selects appropriate signals from all three research layers
4. Formats signals for injection into API prompts

Expected pattern (low divergence)
  → Brief benchmark context only
  → "This is normal for your usage level"
  
Slightly divergent (medium divergence)
  → Benchmark + Master Synthesis
  → "This pattern diverges slightly from typical"
  
Distinctive (high divergence)
  → All three layers (Benchmark + Master Synthesis + Human Reference)
  → "This reveals something meaningful about your pattern"
  
Highly distinctive (very high divergence)
  → All three layers with emphasis
  → "This is rare and particularly revealing"

This keeps the report focused on what's actually interesting about each person
while ensuring every claim is grounded in research.
"""
