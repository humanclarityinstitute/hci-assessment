"""
HCI AI Identity & Behaviour Assessment
Benchmark Builder Script

Reads the locked benchmark Excel file and produces percentile
lookup tables for every variable, segmented by demographics.

Run this script whenever the benchmark data is updated.
Output: benchmark_tables.json
"""

import pandas as pd
import numpy as np
import json
from scipy import stats

# ============================================================
# TAB NAME TO VARIABLE NAME MAPPING
# Handles Excel's 31-character tab name limit and legacy names
# ============================================================

TAB_TO_VARIABLE = {
    # Trust
    'trust_ai_for_accuracy':                'trust_ai_for_accuracy',
    'confident_relying_on_ai_outputs':      'confident_relying_on_ai_outputs',
    'worry_ai_presents_false_info':         'worry_ai_presents_false_info',
    'ai_decision_reliance_when_diffi':      'ai_decision_reliance_when_difficult',

    # Disclosure
    'ai_personal_sharing_comfort':          'ai_personal_sharing_comfort',
    'ai_emotional_safety_vs_humans':        'ai_emotional_safety_vs_humans',
    'disclosure_untold_things':             'disclosure_untold_things',
    'disclosure_comparative_open':          'disclosure_comparative_openness',

    # Reliance
    'restless_without_ai':                  'restless_without_ai',
    'system_reliance_struggle_withou':      'system_reliance_struggle_without',
    'rely_ai_suggestions_decisions':        'ai_reliance_decisions',
    'delegation_rely_even_if_possibl':      'delegation_rely_even_if_possible',
    'delegation_skill_decline':             'delegation_skill_decline',

    # Decision Delegation
    'delegation_regular_handover':          'delegation_regular_handover',
    'accept_ai_output_without_change':      'accept_ai_output_without_change',
    'override_follow_despite_discomf':      'override_follow_despite_discomfort',
    'comfort_high_stakes_delegation':       'comfort_high_stakes_delegation',
    'delegation_when_uncertain':            'delegation_when_uncertain',

    # Verification
    'double_check_ai_info':                 'double_check_ai_info',
    'verify_skip_due_to_effort':            'verify_skip_due_to_effort',
    'proceed_without_checking':             'proceed_without_checking',
    'verify_use_external_sources':          'verify_use_external_sources',

    # Human Agency
    'self_directed_action_feeling':         'self_directed_action_feeling',
    'agency_control_feel_in_control':       'agency_control_feel_in_control',
    'agency_trust_own_judgement':           'agency_trust_own_judgement',
    'nudging_influenced_unaware':           'nudging_influenced_unaware',
    'ai_identity_mine_vs_ai':              'ai_identity_mine_vs_ai',

    # Emotional Regulation
    'ai_emotion_relief_support':            'ai_emotion_relief_support',
    'ai_emotional_support_extent':          'ai_emotional_support_extent',
    'ai_boundaries_change_over_time':       'ai_boundaries_change_over_time',
    'emotional_regulation_coping':          'emotional_regulation_coping',

    # Thought Partnership
    'thought_partner_sounding_board':       'thought_partnership_sounding_board',
    'thought_partner_belief_challang':      'thought_partnership_belief_challenge',
    'ai_thinking_depth_engagement':         'ai_thinking_depth_engagement',
    'ai_validation_reinforce_beliefs':      'ai_validation_reinforce_beliefs',

    # Social Transparency
    'ai_professional_transparency':         'social_transparency_professional',
    'social_transparency_concealment':      'social_transparency_concealment',
    'social_transparency_comfort':          'social_transparency_comfort',
    'social_transparency_gap':              'social_transparency_gap',
}


# ============================================================
# DIMENSION CONFIGURATION
# Maps each dimension to its variables and scoring direction
# ============================================================

DIMENSIONS = {
    'trust': {
        'variables': [
            'trust_ai_for_accuracy',
            'confident_relying_on_ai_outputs',
            'worry_ai_presents_false_info',
            'ai_decision_reliance_when_difficult',
        ],
        'reverse': ['worry_ai_presents_false_info'],
    },
    'disclosure': {
        'variables': [
            'ai_personal_sharing_comfort',
            'ai_emotional_safety_vs_humans',
            'disclosure_untold_things',
            'disclosure_comparative_openness',
        ],
        'reverse': [],
    },
    'reliance': {
        'variables': [
            'restless_without_ai',
            'system_reliance_struggle_without',
            'ai_reliance_decisions',
            'delegation_rely_even_if_possible',
            'delegation_skill_decline',
        ],
        'reverse': [],
    },
    'decision_delegation': {
        'variables': [
            'delegation_regular_handover',
            'accept_ai_output_without_change',
            'override_follow_despite_discomfort',
            'comfort_high_stakes_delegation',
            'delegation_when_uncertain',
        ],
        'reverse': [],
    },
    'verification': {
        'variables': [
            'double_check_ai_info',
            'verify_skip_due_to_effort',
            'proceed_without_checking',
            'verify_use_external_sources',
        ],
        'reverse': [
            'verify_skip_due_to_effort',
            'proceed_without_checking',
        ],
    },
    'human_agency': {
        'variables': [
            'self_directed_action_feeling',
            'agency_control_feel_in_control',
            'agency_trust_own_judgement',
            'nudging_influenced_unaware',
            'ai_identity_mine_vs_ai',
        ],
        'reverse': [
            'agency_trust_own_judgement',
            'nudging_influenced_unaware',
            'ai_identity_mine_vs_ai',
        ],
    },
    'emotional_regulation': {
        'variables': [
            'ai_emotion_relief_support',
            'ai_emotional_support_extent',
            'ai_boundaries_change_over_time',
            'emotional_regulation_coping',
        ],
        'reverse': [],
    },
    'thought_partnership': {
        'variables': [
            'thought_partnership_sounding_board',
            'thought_partnership_belief_challenge',
            'ai_thinking_depth_engagement',
            'ai_validation_reinforce_beliefs',
        ],
        'reverse': ['ai_validation_reinforce_beliefs'],
    },
    'social_transparency': {
        'variables': [
            'social_transparency_professional',
            'social_transparency_concealment',
            'social_transparency_comfort',
            'social_transparency_gap',
        ],
        'reverse': [
            'social_transparency_concealment',
            'social_transparency_gap',
        ],
    },
}

# Minimum sample size for a demographic segment to be included
MIN_SAMPLE = 30


def reverse_score(score, scale_max=7):
    return (scale_max + 1) - score


def get_percentile_from_distribution(score, distribution):
    """Calculate percentile of a score within a distribution."""
    return round(float(stats.percentileofscore(distribution, score, kind='rank')), 1)


def build_variable_benchmarks(df, variable_name):
    """
    Build percentile lookup tables for one variable.
    Returns dict with overall and demographic distributions.
    """
    scores = pd.to_numeric(df['response'], errors='coerce').dropna().tolist()

    if len(scores) < MIN_SAMPLE:
        return None

    benchmarks = {
        'variable': variable_name,
        'n_total': len(scores),
        'mean': round(float(np.mean(scores)), 3),
        'std': round(float(np.std(scores)), 3),
        'overall': scores,
        'by_age': {},
        'by_gender': {},
        'by_country': {},
        'by_frequency': {},
    }

    # By age group
    if 'age_group' in df.columns:
        for age in df['age_group'].dropna().unique():
            subset = pd.to_numeric(
                df[df['age_group'] == age]['response'], errors='coerce'
            ).dropna().tolist()
            if len(subset) >= MIN_SAMPLE:
                benchmarks['by_age'][age] = subset

    # By gender
    if 'gender' in df.columns:
        for gender in df['gender'].dropna().unique():
            subset = pd.to_numeric(
                df[df['gender'] == gender]['response'], errors='coerce'
            ).dropna().tolist()
            if len(subset) >= MIN_SAMPLE:
                benchmarks['by_gender'][gender] = subset

    # By country
    if 'country' in df.columns:
        for country in df['country'].dropna().unique():
            subset = pd.to_numeric(
                df[df['country'] == country]['response'], errors='coerce'
            ).dropna().tolist()
            if len(subset) >= MIN_SAMPLE:
                benchmarks['by_country'][country] = subset

    # By AI usage frequency
    if 'ai_tool_use_frequency' in df.columns:
        for freq in df['ai_tool_use_frequency'].dropna().unique():
            subset = pd.to_numeric(
                df[df['ai_tool_use_frequency'] == freq]['response'], errors='coerce'
            ).dropna().tolist()
            if len(subset) >= MIN_SAMPLE:
                benchmarks['by_frequency'][freq] = subset

    return benchmarks


def build_all_benchmarks(excel_path):
    """
    Main function — reads Excel file and builds all benchmark tables.
    Returns complete benchmark dictionary.
    """
    print(f'Reading benchmark file: {excel_path}')
    all_sheets = pd.read_excel(excel_path, sheet_name=None, dtype=str)
    print(f'Found {len(all_sheets)} tabs')
    print()

    benchmarks = {}
    skipped = []

    for tab_name, df in all_sheets.items():
        # Map tab name to canonical variable name
        variable_name = TAB_TO_VARIABLE.get(tab_name)

        if not variable_name:
            print(f'  SKIPPED (no mapping): {tab_name}')
            skipped.append(tab_name)
            continue

        result = build_variable_benchmarks(df, variable_name)

        if result:
            benchmarks[variable_name] = result
            print(f'  ✓ {variable_name} (n={result["n_total"]})')
        else:
            print(f'  ✗ {variable_name} — insufficient data')
            skipped.append(tab_name)

    print()
    print(f'Built benchmarks for {len(benchmarks)} variables')
    if skipped:
        print(f'Skipped: {skipped}')

    return benchmarks


def save_benchmarks(benchmarks, output_path='benchmark_tables.json'):
    """Save benchmark tables to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(benchmarks, f, indent=2)
    print(f'Saved to {output_path}')


def load_benchmarks(path='benchmark_tables.json'):
    """Load benchmark tables from JSON file."""
    with open(path, 'r') as f:
        return json.load(f)


if __name__ == '__main__':
    import sys

    excel_path = sys.argv[1] if len(sys.argv) > 1 else 'HCI_benchmark_data_CLEAN_LOCKED.xlsx'
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'benchmark_tables.json'

    benchmarks = build_all_benchmarks(excel_path)
    save_benchmarks(benchmarks, output_path)

    print()
    print('BENCHMARK BUILD COMPLETE')
    print(f'Variables benchmarked: {len(benchmarks)}')
    total_points = sum(b["n_total"] for b in benchmarks.values())
    print(f'Total data points: {total_points:,}')
