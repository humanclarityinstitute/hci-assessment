"""
data_enrichment.py

Enriches assessment data before passing to report_generator.
Calculates demographic percentiles, perception gaps, rare combinations,
distinctive responses, and question distributions.

Called from api.py /premium endpoint (Phase 1 implementation).
"""

from hci_signals_library import SIGNALS
from benchmark_builder import get_benchmark
import os


def enrich_results_for_report(full_results, demographics, benchmark_path):
    """
    Main enrichment function: takes full_results and adds all calculated data.
    
    Adds:
    - demographic_percentiles: percentiles by age group and frequency
    - perception_gaps: dimension misalignments > 30 percentile points
    - rare_combinations: unusual dimension pairings (rarity <= 10%)
    - distinctive_responses: extreme responses (0-10th or 90-100th %ile)
    - question_distributions: population distribution per question
    
    Args:
        full_results (dict): Complete scoring results from /score endpoint
        demographics (dict): Age group, frequency, etc.
        benchmark_path (str): Path to benchmark_tables.json
    
    Returns:
        dict: full_results enriched with all calculated data
    """
    
    try:
        benchmark = get_benchmark()
    except Exception as e:
        print(f'WARNING: Could not load benchmark: {e}')
        benchmark = None
    
    # TASK 1.1: Calculate demographic percentiles
    print('Enriching: Calculating demographic percentiles...')
    demographic_percentiles = _calculate_demographic_percentiles(
        full_results,
        demographics,
        benchmark
    )
    full_results['demographic_percentiles'] = demographic_percentiles
    
    # TASK 1.2: Identify perception gaps
    print('Enriching: Identifying perception gaps...')
    perception_gaps = _identify_perception_gaps(full_results)
    full_results['perception_gaps'] = perception_gaps
    
    # TASK 1.3: Identify rare combinations
    print('Enriching: Identifying rare combinations...')
    rare_combinations = _identify_rare_combinations(full_results)
    full_results['rare_combinations'] = rare_combinations
    
    # TASK 1.4: Extract distinctive responses
    print('Enriching: Extracting distinctive responses...')
    distinctive_responses = _extract_distinctive_responses(full_results)
    full_results['distinctive_responses'] = distinctive_responses
    
    # TASK 1.5: Add question distributions
    print('Enriching: Adding question distributions...')
    question_distributions = _get_question_distributions(
        full_results,
        benchmark
    )
    full_results['question_distributions'] = question_distributions
    
    return full_results


# ============================================================================
# TASK 1.1: Calculate Demographic Percentiles
# ============================================================================

def _calculate_demographic_percentiles(full_results, demographics, benchmark):
    """
    Calculate percentile comparisons by age group and frequency.
    
    Returns: {
        'trust': {
            'percentile_by_frequency': 69,
            'percentile_by_age': 79
        },
        ...
    }
    """
    
    demographic_percentiles = {}
    
    if not benchmark:
        # Return empty if benchmark not available
        for dim_name in full_results.get('dimension_scores', {}).keys():
            demographic_percentiles[dim_name] = {
                'percentile_by_frequency': None,
                'percentile_by_age': None
            }
        return demographic_percentiles
    
    for dim_name, dim_data in full_results.get('dimension_scores', {}).items():
        raw_score = dim_data.get('raw_score')
        
        percentile_by_frequency = None
        percentile_by_age = None
        
        if raw_score is not None:
            # Percentile by frequency and age using the correct function
            try:
                percentile_results = benchmark.calculate_percentile(
                    dim_name,
                    raw_score,
                    demographics
                )
                percentile_by_frequency = percentile_results.get("frequency_percentile")
                percentile_by_age = percentile_results.get("age_group_percentile")
                
                print(f'  {dim_name} (daily users): {percentile_by_frequency}th %ile')
                if percentile_by_age:
                    age_group = demographics.get('age_group')
                    print(f'  {dim_name} ({age_group}): {percentile_by_age}th %ile')
            except Exception as e:
                print(f'  WARNING: Could not calculate percentiles for {dim_name}: {e}')
                percentile_by_frequency = None
                percentile_by_age = None
        
        demographic_percentiles[dim_name] = {
            'percentile_by_frequency': percentile_by_frequency,
            'percentile_by_age': percentile_by_age
        }
    
    return demographic_percentiles


# ============================================================================
# TASK 1.2: Identify Perception Gaps
# ============================================================================

def _identify_perception_gaps(full_results):
    """
    Identify where two dimensions show divergent patterns (gap > 30).
    
    Returns: [
        {
            'dimension_1': 'decision_delegation',
            'dimension_2': 'verification',
            'percentile_1': 20,
            'percentile_2': 75,
            'gap_magnitude': 55
        },
        ...
    ]
    """
    
    perception_gaps = []
    dimension_scores = full_results.get('dimension_scores', {})
    
    if not dimension_scores:
        return perception_gaps
    
    dim_names = list(dimension_scores.keys())
    
    # Check all unique pairs
    for i, dim1 in enumerate(dim_names):
        for dim2 in dim_names[i+1:]:
            p1 = dimension_scores[dim1].get('percentile', 50)
            p2 = dimension_scores[dim2].get('percentile', 50)
            
            gap = abs(p1 - p2)
            
            # Only significant gaps (> 30 percentile points)
            if gap > 30:
                perception_gaps.append({
                    'dimension_1': dim1,
                    'dimension_2': dim2,
                    'percentile_1': p1,
                    'percentile_2': p2,
                    'gap_magnitude': gap,
                    'interpretation': f'{dim1} ({p1}th) and {dim2} ({p2}th) show divergent patterns'
                })
                print(f'  Gap: {dim1} ({p1}) vs {dim2} ({p2}) = {gap} points')
    
    # Sort by gap magnitude
    perception_gaps = sorted(
        perception_gaps,
        key=lambda x: x['gap_magnitude'],
        reverse=True
    )
    
    return perception_gaps


# ============================================================================
# TASK 1.3: Identify Rare Combinations
# ============================================================================

def _identify_rare_combinations(full_results):
    """
    Identify unusual dimensional pairings (rarity <= 10%).
    
    Returns: [
        {
            'dimension_1': 'decision_delegation',
            'dimension_2': 'human_agency',
            'percentile_1': 20,
            'percentile_2': 24,
            'rarity_percent': 5,
            'why_unusual': '...',
            'what_reveals': '...'
        },
        ...
    ]
    """
    
    rare_combinations = []
    dimension_scores = full_results.get('dimension_scores', {})
    
    if not dimension_scores:
        return rare_combinations
    
    dim_names = list(dimension_scores.keys())
    
    # Check all unique pairs
    for i, dim1 in enumerate(dim_names):
        for dim2 in dim_names[i+1:]:
            p1 = dimension_scores[dim1].get('percentile', 50)
            p2 = dimension_scores[dim2].get('percentile', 50)
            
            # Check SIGNALS library for this combination
            combo_key = f'{dim1}_{dim2}'
            combo_data = SIGNALS.get('combinations', {}).get(combo_key)
            
            if not combo_data:
                # Try reverse order
                combo_key = f'{dim2}_{dim1}'
                combo_data = SIGNALS.get('combinations', {}).get(combo_key)
            
            if combo_data:
                rarity_percent = combo_data.get('rarity_percent', 5)
                
                # Only rare combos (10% or less)
                if rarity_percent <= 10:
                    rare_combinations.append({
                        'dimension_1': dim1,
                        'dimension_2': dim2,
                        'percentile_1': p1,
                        'percentile_2': p2,
                        'rarity_percent': rarity_percent,
                        'why_unusual': combo_data.get('why_unusual', ''),
                        'what_reveals': combo_data.get('what_it_reveals', '')
                    })
                    print(f'  Rare combo: {dim1} ({p1}) + {dim2} ({p2}) = {rarity_percent}% rarity')
    
    # Sort by rarity (most rare first)
    rare_combinations = sorted(
        rare_combinations,
        key=lambda x: x['rarity_percent']
    )[:2]  # Top 2 combos
    
    return rare_combinations


# ============================================================================
# TASK 1.4: Extract Distinctive Responses
# ============================================================================

def _extract_distinctive_responses(full_results):
    """
    Extract responses at extremes (0-10th or 90-100th percentile).
    
    Returns: [
        {
            'question_key': 'reliance_q2',
            'question_text': 'I struggle to function...',
            'respondent_answer': 6,
            'respondent_percentile': 97,
            'dimension': 'reliance'
        },
        ...
    ]
    """
    
    distinctive_responses = []
    question_scores = full_results.get('question_scores', {})
    
    if not question_scores:
        return distinctive_responses
    
    # Extract only extreme responses
    for q_key, q_data in question_scores.items():
        percentile = q_data.get('percentile', 50)
        
        # Only extremes: 0-10th or 90-100th percentile
        if percentile <= 10 or percentile >= 90:
            distinctive_responses.append({
                'question_key': q_key,
                'question_text': q_data.get('question_text', ''),
                'respondent_answer': q_data.get('respondent_answer', 0),
                'respondent_percentile': percentile,
                'dimension': q_data.get('dimension', 'unknown'),
                'position': 'extreme'
            })
            print(f'  Extreme: {q_key} (respondent: {q_data.get("respondent_answer")}, %ile: {percentile})')
    
    # Sort by distance from 50th (most extreme first)
    distinctive_responses = sorted(
        distinctive_responses,
        key=lambda x: abs(x['respondent_percentile'] - 50),
        reverse=True
    )[:5]  # Top 5 distinctive
    
    return distinctive_responses


# ============================================================================
# TASK 1.5: Add Question Distributions
# ============================================================================

def _get_question_distributions(full_results, benchmark):
    """
    Get population distribution for each question (for histograms).
    
    Returns: {
        'trust_q1': [5, 8, 12, 18, 25, 22, 10],  # percentages per scale point
        ...
    }
    """
    
    question_distributions = {}
    question_scores = full_results.get('question_scores', {})
    
    if not question_scores:
        return question_distributions
    
    for q_key in question_scores.keys():
        try:
            if benchmark:
                dist = benchmark.get_question_distribution(q_key)
                if dist:
                    question_distributions[q_key] = dist
                    print(f'  Distribution for {q_key}: loaded from benchmark')
                else:
                    # Fallback: uniform distribution
                    question_distributions[q_key] = [14, 14, 14, 14, 14, 14, 14]
                    print(f'  Distribution for {q_key}: using fallback')
            else:
                # No benchmark: use fallback
                question_distributions[q_key] = [14, 14, 14, 14, 14, 14, 14]
                print(f'  Distribution for {q_key}: using fallback (no benchmark)')
        except Exception as e:
            print(f'  WARNING: Could not get distribution for {q_key}: {e}')
            question_distributions[q_key] = [14, 14, 14, 14, 14, 14, 14]
    
    return question_distributions
