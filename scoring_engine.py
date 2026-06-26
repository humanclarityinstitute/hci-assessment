"""
scoring_engine.py
HCI Assessment Platform — Scoring Engine

Purpose:
  - Accept 39 assessment responses (1-7 scale)
  - Aggregate into 9 dimension scores
  - Calculate percentiles (overall, age group, frequency user)
  - Detect perception gaps (self-estimate vs actual)
  - Detect rare combinations (unusual dimension pairs)
  - Return complete scoring results for free/premium reports

Input: Assessment responses + demographics + perceptions
Output: Full scoring results (9 dimension percentiles, gaps, rare combos)
"""

import uuid
import json
from datetime import datetime
from benchmark_builder import get_benchmark


# ============================================================
# PERCEPTION GAP ANALYSIS - Map perceived answers to percentiles
# ============================================================

PERCEPTION_MAP = {
    'Much less than most people': 25,
    'Less than most people': 35,
    'About the same as most people': 50,
    'More than most people': 65,
    'Much more than most people': 75,
}


# ============================================================
# HELPER FUNCTIONS (extracted from old scoring_engine.py)
# ============================================================

def analyse_perception_gap(perceived, actual_percentile, dimension):
    """
    Compare self-estimate to actual percentile.
    Returns gap analysis with direction and magnitude.
    """
    if not perceived or actual_percentile is None:
        return None

    perceived_estimate = PERCEPTION_MAP.get(perceived)
    if perceived_estimate is None:
        return None

    gap = actual_percentile - perceived_estimate
    
    return {
        'question': dimension,
        'perceived_answer': perceived,
        'actual_percentile': actual_percentile,
        'gap_magnitude': gap
    }


def identify_dominant_patterns(dimension_scores):
    """
    Identify highest and lowest scoring dimensions from raw scores.
    Returns top 3 and bottom 3 by percentile.
    """
    scored = [
        (name, data)
        for name, data in dimension_scores.items()
        if data and data.get('percentile_overall') is not None
    ]

    sorted_dims = sorted(
        scored,
        key=lambda x: x[1]['percentile_overall'],
        reverse=True
    )

    return {
        'highest': [
            {
                'dimension': name,
                'percentile': data['percentile_overall'],
                'raw_score': data['raw_score'],
            }
            for name, data in sorted_dims[:3]
        ],
        'lowest': [
            {
                'dimension': name,
                'percentile': data['percentile_overall'],
                'raw_score': data['raw_score'],
            }
            for name, data in sorted_dims[-3:]
        ],
        'full_ranking': [
            {
                'dimension': name,
                'percentile': data['percentile_overall'],
                'raw_score': data['raw_score'],
            }
            for name, data in sorted_dims
        ],
    }


def generate_headline(dimension_scores):
    """
    Generate a personalised headline based on dimension contrasts.
    """
    patterns = identify_dominant_patterns(dimension_scores)
    highest = patterns['highest'][0] if patterns['highest'] else None
    lowest = patterns['lowest'][0] if patterns['lowest'] else None

    if not highest or not lowest:
        return 'Your AI Identity Profile is ready'

    # Pre-written headline patterns for common contrasts
    headlines = {
        ('trust', 'verification'): 'You trust AI significantly — but rarely check what it tells you',
        ('disclosure', 'social_transparency'): 'You share deeply with AI but keep that private from others',
        ('thought_partnership', 'reliance'): 'You think deeply with AI but show signs of growing dependency',
        ('human_agency', 'decision_delegation'): 'You maintain strong agency while delegating surprisingly few decisions',
        ('emotional_regulation', 'human_agency'): 'AI plays a significant role in your emotional life',
    }

    pair = (highest['dimension'], lowest['dimension'])
    if pair in headlines:
        return headlines[pair]

    return f"Your profile shows distinctive patterns across dimensions"


def build_variable_highlights(dimension_scores, benchmarks, demographics):
    """
    Select 3 most interesting variable-level insights.
    """
    # Simplified version - returns empty for now
    # Full version would extract variable-level percentiles
    return []


def select_shown_scores(dimension_scores, demographics):
    """
    Select which dimension scores to show (always 9 for free tier).
    """
    return list(dimension_scores.keys())


def find_best_benchmark(demographics, dimension_scores, benchmarks):
    """
    Find the best matching benchmark cohort for comparison.
    """
    age_group = demographics.get('age_group')
    frequency = demographics.get('ai_tool_use_frequency')
    
    return {
        'age_group': age_group,
        'frequency': frequency,
        'description': f"People in your age group ({age_group}) who use AI {frequency}"
    }


# Dimension variable mappings (39 variables → 9 dimensions)
DIMENSION_VARIABLES = {
    'reliance': [
        'rel_q1', 'rel_q2', 'rel_q3', 'rel_q4', 'rel_q5'
    ],
    'trust': [
        'trust_q1', 'trust_q2', 'trust_q3', 'trust_q4'
    ],
    'verification': [
        'ver_q1', 'ver_q2', 'ver_q3', 'ver_q4'
    ],
    'decision_delegation': [
        'del_q1', 'del_q2', 'del_q3', 'del_q4', 'del_q5'
    ],
    'human_agency': [
        'agency_q1', 'agency_q2', 'agency_q3', 'agency_q4', 'agency_q5'
    ],
    'emotional_regulation': [
        'emot_q1', 'emot_q2', 'emot_q3', 'emot_q4'
    ],
    'disclosure': [
        'disc_q1', 'disc_q2', 'disc_q3', 'disc_q4'
    ],
    'thought_partnership': [
        'thought_q1', 'thought_q2', 'thought_q3', 'thought_q4'
    ],
    'social_transparency': [
        'soc_q1', 'soc_q2', 'soc_q3', 'soc_q4'
    ]
}

# Variables that require reverse scoring (8 - response)
# These measure the opposite of the construct and must be flipped before aggregation
# Total: 6 variables reverse-scored (verified against Master_assessment_dataset.xlsx 2026-06-25)
REVERSE_SCORED_VARIABLES = {
    'worry_ai_presents_false_info',        # Trust: HIGH worry = LOW trust → REVERSE
    'verify_skip_due_to_effort',           # Verification: HIGH skipping = LOW verification → REVERSE
    'proceed_without_checking',            # Verification: HIGH no-check = LOW verification → REVERSE
    'nudging_influenced_unaware',          # Human Agency: HIGH unaware influence = LOW agency → REVERSE
    'ai_validation_reinforce_beliefs',     # Thought Partnership: HIGH echo-chamber = LOW partnership → REVERSE
    'social_transparency_concealment'      # Social Transparency: HIGH hiding = LOW transparency → REVERSE
}

# Perception questions (self-estimate)
PERCEPTION_QUESTIONS = {
    'perceived_usage': 'Compared to most people, how much do you use AI?',
    'perceived_reliance': 'Compared to most people, how much do you rely on AI?',
    'perceived_dependence': 'Compared to most people, how dependent on AI are you?'
}

# Rare combination thresholds
RARE_COMBINATION_THRESHOLD = 5.0  # % of population


class ScoringEngine:
    """Score assessment responses and generate comprehensive results."""
    
    def __init__(self, benchmark=None):
        """
        Initialize scoring engine with benchmark data.
        
        Args:
            benchmark: BenchmarkBuilder instance (if None, loads default)
        """
        self.benchmark = benchmark or get_benchmark()
    
    def score_assessment(self, responses, demographics, perceptions=None, session_id=None):
        """
        Score a complete assessment and return full results.
        
        Args:
            responses (dict): All 39 question responses + 3 perception questions
                Example: {'trust_q1': 5, 'trust_q2': 6, ..., 'perceived_usage': '...'}
            demographics (dict): {'age_group', 'gender', 'country', 'ai_tool_use_frequency'}
            perceptions (dict, optional): Perception questions (usually in responses)
            session_id (str, optional): Session identifier (generated if not provided)
        
        Returns:
            dict: Complete scoring results:
            {
                'session_id': str,
                'timestamp': ISO datetime,
                'demographics': dict,
                'dimension_scores': {
                    'reliance': {
                        'raw_score': float (1-7),
                        'percentile_overall': int (0-100),
                        'percentile_age_group': int or None,
                        'percentile_frequency': int or None,
                        'n_overall': int,
                        'n_age_group': int or None,
                        'n_frequency': int or None
                    },
                    ... (8 more dimensions)
                },
                'perception_gaps': [
                    {
                        'question': str,
                        'perceived_answer': str,
                        'actual_percentile': int,
                        'gap_magnitude': float (how far off they are)
                    },
                    ...
                ],
                'rare_combinations': [
                    {
                        'combo': [dim1, dim2],
                        'percentiles': [p1, p2],
                        'frequency_pct': float,
                        'description': str
                    },
                    ...
                ]
            }
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        # Validate inputs
        if not responses or not demographics:
            raise ValueError("responses and demographics required")
        
        # Calculate 9 dimension scores
        dimension_scores = self._calculate_dimension_scores(responses, demographics)
        
        # Detect perception gaps
        perception_gaps = self._detect_perception_gaps(
            responses, dimension_scores, demographics
        )
        
        # Detect rare combinations
        rare_combinations_raw = self._detect_rare_combinations(
            dimension_scores, demographics
        )
        
        # Transform rare combinations to expected format with dimension_1/dimension_2 keys
        rare_combinations = []
        for combo in rare_combinations_raw:
            if combo['combo'] and len(combo['combo']) >= 2:
                rare_combinations.append({
                    'dimension_1': combo['combo'][0],
                    'dimension_2': combo['combo'][1],
                    'percentile_dim1': combo['percentiles'][0],
                    'percentile_dim2': combo['percentiles'][1],
                    'description': combo['description'],
                    'is_distinctive': combo.get('is_distinctive', True),
                    'rarity_percent': combo.get('frequency_pct', 5)
                })
        
        # Transform perception gaps into analyzed format
        perception_gaps_analyzed = []
        for gap in perception_gaps:
            if gap:
                perception_gaps_analyzed.append(gap)
        
        # Generate patterns and headline
        patterns = identify_dominant_patterns(dimension_scores)
        headline = generate_headline(dimension_scores)
        
        # Build complete results object in old format
        results = {
            'demographics': demographics,
            'dimension_scores': dimension_scores,  # ← Changed from 'dimensions' for api.py compatibility
            'patterns': patterns,
            'headline': headline,
            'perception_gaps': perception_gaps_analyzed,
            'variable_highlights': build_variable_highlights(dimension_scores, {}, demographics),
            'shown_scores': select_shown_scores(dimension_scores, demographics),
            'best_benchmark': find_best_benchmark(demographics, dimension_scores, {}),
            'summary': {
                'dimensions_scored': len([d for d in dimension_scores.values() if d]),
                'highest_dimension': patterns['highest'][0]['dimension'] if patterns['highest'] else None,
                'lowest_dimension': patterns['lowest'][0]['dimension'] if patterns['lowest'] else None,
            },
            'rare_combinations': rare_combinations,
            'session_id': session_id,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        return results
    
    def _calculate_dimension_scores(self, responses, demographics):
        """
        Calculate scores for all 9 dimensions.
        
        Args:
            responses (dict): All question responses
            demographics (dict): Participant demographics
        
        Returns:
            dict: Dimension scores with percentiles
        """
        results = {}
        
        for dimension_name, variable_keys in DIMENSION_VARIABLES.items():
            # Extract responses for this dimension's variables
            dimension_responses = []
            for key in variable_keys:
                val = responses.get(key)
                if val is not None:
                    try:
                        val = float(val)
                        
                        # APPLY REVERSE SCORING if this variable is reverse-scored
                        # Flip: 1→7, 2→6, 3→5, 4→4, 5→3, 6→2, 7→1
                        if key in REVERSE_SCORED_VARIABLES:
                            val = 8 - val
                        
                        dimension_responses.append(val)
                    except (TypeError, ValueError):
                        continue
            
            if not dimension_responses:
                # Skip if no valid responses for this dimension
                continue
            
            # Calculate raw score (average) AFTER reverse scoring applied
            raw_score = sum(dimension_responses) / len(dimension_responses)
            
            # Validate score
            if not self.benchmark.validate_dimension_score(dimension_name, raw_score):
                continue
            
            # Calculate percentiles
            percentile_results = self.benchmark.calculate_percentile(
                dimension_name, raw_score, demographics
            )
            
            results[dimension_name] = {
                'raw_score': round(raw_score, 2),
                'percentile_overall': percentile_results['overall_percentile'],
                'percentile_age_group': percentile_results['age_group_percentile'],
                'percentile_frequency': percentile_results['frequency_percentile'],
                'n_overall': percentile_results['n_overall'],
                'n_age_group': percentile_results['n_age_group'],
                'n_frequency': percentile_results['n_frequency']
            }
        
        return results
    
    def _detect_perception_gaps(self, responses, dimension_scores, demographics):
        """
        Detect perception gaps (self-estimate vs actual percentile).
        
        Args:
            responses (dict): All responses (including perception questions)
            dimension_scores (dict): Calculated dimension percentiles
            demographics (dict): Participant demographics
        
        Returns:
            list: Perception gaps with magnitude
        """
        gaps = []
        
        # Map perception questions to dimensions for analysis
        perception_to_dimension = {
            'perceived_usage': 'reliance',
            'perceived_reliance': 'reliance',
            'perceived_dependence': 'reliance'
        }
        
        for perception_key, dimension_name in perception_to_dimension.items():
            perceived_answer = responses.get(perception_key)
            
            if not perceived_answer or dimension_name not in dimension_scores:
                continue
            
            actual_percentile = dimension_scores[dimension_name].get('percentile_overall')
            if actual_percentile is None:
                continue
            
            # Estimate perceived percentile from their answer
            # "Much less" ≈ 20th, "Somewhat less" ≈ 35th, "About same" ≈ 50th,
            # "Somewhat more" ≈ 65th, "Much more" ≈ 80th
            perceived_percentiles = {
                'Much less than most people': 20,
                'Somewhat less than most people': 35,
                'About the same as most people': 50,
                'Somewhat more than most people': 65,
                'Much more than most people': 80
            }
            
            perceived_percentile = perceived_percentiles.get(str(perceived_answer), 50)
            gap_magnitude = abs(perceived_percentile - actual_percentile)
            
            if gap_magnitude > 15:  # Only include significant gaps
                gaps.append({
                    'question': perception_key,
                    'perceived_answer': str(perceived_answer),
                    'actual_percentile': actual_percentile,
                    'perceived_percentile': perceived_percentile,
                    'gap_magnitude': round(gap_magnitude, 1)
                })
        
        # Sort by gap magnitude (largest first)
        return sorted(gaps, key=lambda x: x['gap_magnitude'], reverse=True)
    
    def _detect_rare_combinations(self, dimension_scores, demographics):
        """
        Detect rare dimension combinations in the benchmark data.
        
        Args:
            dimension_scores (dict): All dimension percentiles
            demographics (dict): Participant demographics
        
        Returns:
            list: Rare combinations detected
        """
        combos = []
        
        # Define dimension pairs to check (most interesting combinations)
        dimension_pairs = [
            ('reliance', 'human_agency'),
            ('reliance', 'verification'),
            ('decision_delegation', 'human_agency'),
            ('disclosure', 'trust'),
            ('emotional_regulation', 'thought_partnership'),
            ('trust', 'verification')
        ]
        
        for dim1, dim2 in dimension_pairs:
            if dim1 not in dimension_scores or dim2 not in dimension_scores:
                continue
            
            p1 = dimension_scores[dim1].get('percentile_overall')
            p2 = dimension_scores[dim2].get('percentile_overall')
            
            if p1 is None or p2 is None:
                continue
            
            # Identify if this is a rare combination
            # (High/High, Low/Low, or divergent pairs are typically rare)
            is_rare = False
            combo_description = ""
            
            if p1 > 75 and p2 > 75:
                is_rare = True
                combo_description = f"High {dim1} + High {dim2}"
            elif p1 < 25 and p2 < 25:
                is_rare = True
                combo_description = f"Low {dim1} + Low {dim2}"
            elif (p1 > 75 and p2 < 25) or (p1 < 25 and p2 > 75):
                is_rare = True
                combo_description = f"Divergent: High {dim1}, Low {dim2}" if p1 > 75 else f"Divergent: Low {dim1}, High {dim2}"
            
            if is_rare:
                combos.append({
                    'combo': [dim1, dim2],
                    'percentiles': [p1, p2],
                    'description': combo_description,
                    'is_distinctive': True
                })
        
        return combos


def score_assessment(responses, demographics, perceptions=None, session_id=None):
    """
    Convenience function to score an assessment (creates engine instance).
    
    Args:
        responses (dict): All 39 question + 3 perception responses
        demographics (dict): Age group, gender, country, frequency
        perceptions (dict, optional): Perception question responses (usually in responses)
        session_id (str, optional): Session ID (generated if not provided)
    
    Returns:
        dict: Complete scoring results
    """
    engine = ScoringEngine()
    return engine.score_assessment(responses, demographics, perceptions, session_id)
