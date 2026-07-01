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
from question_metadata import REVERSE_SCORED_KEYS


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

# Reverse-scored keys imported from question_metadata
# These measure the opposite of the construct and must be flipped before aggregation
# Total: 6 variables reverse-scored (verified against Master_assessment_dataset.xlsx 2026-06-25)
# Keys: trust_q3, ver_q2, ver_q3, agency_q4, thought_q4, soc_q2

# Perception questions (self-estimate)
PERCEPTION_QUESTIONS = {
    'perceived_usage': 'Compared to most people, how much do you use AI?',
    'perceived_reliance': 'Compared to most people, how much do you rely on AI?',
    'perceived_dependence': 'Compared to most people, how dependent on AI are you?'
}

# Combination detection thresholds
# The old engine only detected >75/<25 extremes across six pairs, which meant
# many meaningful profiles produced no combination signal. These thresholds are
# intentionally wider: they identify true rare combinations, notable tensions,
# and coherent/no-tension profiles.
COMBO_HIGH_THRESHOLD = 70
COMBO_LOW_THRESHOLD = 30
TRUE_RARE_RARITY_PCT = 5.0
NOTABLE_RARITY_PCT = 15.0

DIMENSION_LABELS = {
    'reliance': 'Reliance',
    'trust': 'Trust',
    'verification': 'Verification',
    'decision_delegation': 'Decision Delegation',
    'human_agency': 'Human Agency',
    'emotional_regulation': 'Emotional Regulation',
    'disclosure': 'Disclosure',
    'thought_partnership': 'Thought Partnership',
    'social_transparency': 'Social Transparency',
}

# Curated HCI pair library. Each rule is directional, so the section explains
# meaningful relationships rather than every mathematically possible pair.
COMBINATION_RULES = [
    {
        'id': 'high_reliance_high_agency',
        'dims': ('reliance', 'human_agency'),
        'bands': ('high', 'high'),
        'description': 'High Reliance + High Human Agency',
        'signal_type': 'integrated_agency',
    },
    {
        'id': 'high_reliance_low_verification',
        'dims': ('reliance', 'verification'),
        'bands': ('high', 'low'),
        'description': 'High Reliance + Low Verification',
        'signal_type': 'integration_with_light_scrutiny',
    },
    {
        'id': 'high_trust_low_verification',
        'dims': ('trust', 'verification'),
        'bands': ('high', 'low'),
        'description': 'High Trust + Low Verification',
        'signal_type': 'acceptance_with_light_scrutiny',
    },
    {
        'id': 'high_decision_delegation_low_human_agency',
        'dims': ('decision_delegation', 'human_agency'),
        'bands': ('high', 'low'),
        'description': 'High Decision Delegation + Low Human Agency',
        'signal_type': 'delegation_pressure',
    },
    {
        'id': 'high_decision_delegation_high_human_agency',
        'dims': ('decision_delegation', 'human_agency'),
        'bands': ('high', 'high'),
        'description': 'High Decision Delegation + High Human Agency',
        'signal_type': 'delegated_input_with_authorship',
    },
    {
        'id': 'high_thought_partnership_low_emotional_regulation',
        'dims': ('thought_partnership', 'emotional_regulation'),
        'bands': ('high', 'low'),
        'description': 'High Thought Partnership + Low Emotional Regulation',
        'signal_type': 'cognitive_emotional_boundary',
    },
    {
        'id': 'high_thought_partnership_high_human_agency',
        'dims': ('thought_partnership', 'human_agency'),
        'bands': ('high', 'high'),
        'description': 'High Thought Partnership + High Human Agency',
        'signal_type': 'collaborative_but_authored',
    },
    {
        'id': 'high_thought_partnership_low_decision_delegation',
        'dims': ('thought_partnership', 'decision_delegation'),
        'bands': ('high', 'low'),
        'description': 'High Thought Partnership + Low Decision Delegation',
        'signal_type': 'thinking_partner_not_decision_proxy',
    },
    {
        'id': 'high_disclosure_low_social_transparency',
        'dims': ('disclosure', 'social_transparency'),
        'bands': ('high', 'low'),
        'description': 'High Disclosure + Low Social Transparency',
        'signal_type': 'private_ai_relationship',
    },
    {
        'id': 'high_disclosure_high_emotional_regulation',
        'dims': ('disclosure', 'emotional_regulation'),
        'bands': ('high', 'high'),
        'description': 'High Disclosure + High Emotional Regulation',
        'signal_type': 'personal_emotional_ai_use',
    },
    {
        'id': 'high_emotional_regulation_low_social_transparency',
        'dims': ('emotional_regulation', 'social_transparency'),
        'bands': ('high', 'low'),
        'description': 'High Emotional Regulation + Low Social Transparency',
        'signal_type': 'private_emotional_support',
    },
    {
        'id': 'high_verification_high_trust',
        'dims': ('verification', 'trust'),
        'bands': ('high', 'high'),
        'description': 'High Verification + High Trust',
        'signal_type': 'trust_with_scrutiny',
    },
    {
        'id': 'high_reliance_high_verification',
        'dims': ('reliance', 'verification'),
        'bands': ('high', 'high'),
        'description': 'High Reliance + High Verification',
        'signal_type': 'integrated_but_careful',
    },
    {
        'id': 'low_reliance_high_thought_partnership',
        'dims': ('reliance', 'thought_partnership'),
        'bands': ('low', 'high'),
        'description': 'Low Reliance + High Thought Partnership',
        'signal_type': 'bounded_cognitive_partnership',
    },
]


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
                        if key in REVERSE_SCORED_KEYS:
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
            
            if gap_magnitude > 8:  # Only include significant gaps
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
        Detect combination signals across the nine dimensions.

        This detects three states:
        1. true_rare: a meaningful directional pair that appears in <=5% of the benchmark
        2. notable: a meaningful directional pair that appears in <=15% of the benchmark
        3. coherent/no-tension: no pair qualifies, but the profile shape is still described

        Important: this function does not assume every high/high or high/low pair is rare.
        It checks a curated HCI pair library and estimates rarity from benchmark dimension
        distributions when the benchmark contains aligned dimension value arrays.
        """
        scored = {}
        for dim, data in (dimension_scores or {}).items():
            try:
                scored[dim] = float(data.get('percentile_overall'))
            except Exception:
                continue

        if len(scored) < 2:
            return []

        combos = []
        for rule in COMBINATION_RULES:
            dim1, dim2 = rule['dims']
            band1, band2 = rule['bands']
            if dim1 not in scored or dim2 not in scored:
                continue

            p1 = scored[dim1]
            p2 = scored[dim2]
            if not self._matches_band(p1, band1) or not self._matches_band(p2, band2):
                continue

            rarity = self._estimate_combo_rarity(dim1, dim2, band1, band2)
            severity = self._classify_combo_signal(p1, p2, rarity)

            # Keep true rare and notable combinations. Anything weaker is treated
            # as part of profile shape rather than a Section 4 combination.
            if severity not in {'true_rare', 'notable'}:
                continue

            distance_score = abs(p1 - 50) + abs(p2 - 50)
            if band1 != band2:
                distance_score += abs(p1 - p2) * 0.35
            if rarity is not None:
                distance_score += max(0, (NOTABLE_RARITY_PCT - rarity)) * 2

            combos.append({
                'combo': [dim1, dim2],
                'percentiles': [int(round(p1)), int(round(p2))],
                'dimension_1': dim1,
                'dimension_2': dim2,
                'percentile_dim1': int(round(p1)),
                'percentile_dim2': int(round(p2)),
                'band_dim1': band1,
                'band_dim2': band2,
                'description': rule['description'],
                'combination_id': rule['id'],
                'signal_type': rule.get('signal_type'),
                'is_distinctive': True,
                'combo_classification': severity,
                'rarity_percent': round(rarity, 1) if rarity is not None else (5.0 if severity == 'true_rare' else 12.0),
                'frequency_pct': round(rarity, 1) if rarity is not None else (5.0 if severity == 'true_rare' else 12.0),
                'distinctiveness_score': round(distance_score, 2),
            })

        # Sort so true rare appears before notable, then by rarity/distinctiveness.
        rank = {'true_rare': 0, 'notable': 1}
        combos.sort(key=lambda x: (rank.get(x.get('combo_classification'), 9), x.get('rarity_percent', 99), -x.get('distinctiveness_score', 0)))
        return combos[:2]

    def _matches_band(self, percentile, band):
        try:
            p = float(percentile)
        except Exception:
            return False
        if band == 'high':
            return p >= COMBO_HIGH_THRESHOLD
        if band == 'low':
            return p <= COMBO_LOW_THRESHOLD
        return False

    def _classify_combo_signal(self, p1, p2, rarity):
        """Classify a matching pair as true rare, notable, or weak."""
        extreme = (
            max(p1, p2) >= 85 and min(p1, p2) <= 35
        ) or (p1 >= 85 and p2 >= 85) or (p1 <= 15 and p2 <= 15)

        if rarity is not None:
            if rarity <= TRUE_RARE_RARITY_PCT:
                return 'true_rare'
            if rarity <= NOTABLE_RARITY_PCT:
                return 'notable'
            if extreme and rarity <= 20:
                return 'notable'
            return 'weak'

        # Fallback if benchmark co-occurrence cannot be calculated.
        if extreme:
            return 'notable'
        if (p1 >= 75 and p2 >= 75) or (p1 <= 25 and p2 <= 25) or (p1 >= 75 and p2 <= 25) or (p1 <= 25 and p2 >= 75):
            return 'notable'
        return 'weak'

    def _estimate_combo_rarity(self, dim1, dim2, band1, band2):
        """
        Estimate benchmark co-occurrence from dimension overall value arrays.

        Returns percentage of benchmark participants matching the same directional
        bands. If aligned arrays are unavailable, returns None and the caller uses
        a conservative fallback.
        """
        try:
            data = getattr(self.benchmark, 'data', {}) or {}
            dims = data.get('dimensions') or {}
            vals1 = (((dims.get(dim1) or {}).get('overall') or {}).get('values') or [])
            vals2 = (((dims.get(dim2) or {}).get('overall') or {}).get('values') or [])
            if not vals1 or not vals2:
                return None
            n = min(len(vals1), len(vals2))
            if n < 30:
                return None
            vals1 = [float(v) for v in vals1[:n] if v is not None]
            vals2 = [float(v) for v in vals2[:n] if v is not None]
            n = min(len(vals1), len(vals2))
            if n < 30:
                return None

            pct1 = self._percentile_ranks(vals1)
            pct2 = self._percentile_ranks(vals2)
            matches = 0
            for a, b in zip(pct1, pct2):
                if self._matches_band(a, band1) and self._matches_band(b, band2):
                    matches += 1
            return (matches / n) * 100
        except Exception:
            return None

    def _percentile_ranks(self, values):
        """Return 1-99 percentile ranks for a list of numeric benchmark values."""
        nums = [float(v) for v in values]
        sorted_vals = sorted(nums)
        n = len(sorted_vals)
        out = []
        for v in nums:
            below = 0
            for x in sorted_vals:
                if x < v:
                    below += 1
                else:
                    break
            pct = int((below / n) * 100) if n else 50
            out.append(max(1, min(99, pct)))
        return out


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
