"""
benchmark_builder.py
HCI Assessment Platform — Benchmark Data Builder

Purpose:
  - Load benchmark_tables.json (pre-computed from Excel)
  - Provide percentile calculation utilities
  - Enable demographic-specific comparisons (age groups, frequency segments)

The benchmark_tables.json is built once from HCI_benchmark_data_CLEAN_LOCKED.xlsx
and consumed by scoring_engine.py for fast percentile lookups.
"""

import json
import os
import re
import numpy as np


class BenchmarkBuilder:
    """Load and provide access to benchmark data for percentile calculations."""
    
    def __init__(self, benchmark_path='benchmark_tables.json'):
        """
        Initialize benchmark data from JSON file.
        
        Args:
            benchmark_path (str): Path to benchmark_tables.json
        
        Raises:
            FileNotFoundError: If benchmark file not found
            ValueError: If benchmark data invalid
        """
        if not os.path.exists(benchmark_path):
            raise FileNotFoundError(f"Benchmark file not found: {benchmark_path}")
        
        with open(benchmark_path, 'r') as f:
            self.data = json.load(f)
        
        self.dimensions = self.data.get('dimensions', {})
        self.metadata = self.data.get('metadata', {})
        self.min_sample_size = self.metadata.get('min_sample_size', 30)
        
        # Validate structure
        if not self.dimensions:
            raise ValueError("Benchmark data has no dimensions")
        
        print(f"✓ Benchmark loaded: {len(self.dimensions)} dimensions, "
              f"{self.metadata.get('total_variables', 0)} variables")
    
    def get_dimension_data(self, dimension_name):
        """
        Retrieve all benchmark data for a dimension.
        
        Args:
            dimension_name (str): e.g., 'reliance', 'trust', etc.
        
        Returns:
            dict: Dimension data with overall, by_age_group, by_frequency stats
        """
        if dimension_name not in self.dimensions:
            raise ValueError(f"Unknown dimension: {dimension_name}")
        
        return self.dimensions[dimension_name]
    
    def calculate_percentile(self, dimension_name, score, demographics=None):
        """
        Calculate percentile for a dimension score against benchmark data.
        
        Args:
            dimension_name (str): e.g., 'reliance'
            score (float): Participant's dimension score (1-7)
            demographics (dict, optional): {'age_group', 'ai_tool_use_frequency'}
        
        Returns:
            dict: {
                'overall_percentile': 0-100,
                'age_group_percentile': 0-100 or None,
                'frequency_percentile': 0-100 or None,
                'n_overall': int,
                'n_age_group': int or None,
                'n_frequency': int or None
            }
        """
        dim_data = self.get_dimension_data(dimension_name)
        result = {
            'overall_percentile': None,
            'age_group_percentile': None,
            'frequency_percentile': None,
            'n_overall': None,
            'n_age_group': None,
            'n_frequency': None
        }
        
        # Overall percentile
        if 'overall' in dim_data:
            overall_values = dim_data['overall'].get('values', [])
            if overall_values:
                percentile = self._calculate_percentile_from_distribution(
                    score, overall_values
                )
                result['overall_percentile'] = percentile
                result['n_overall'] = dim_data['overall'].get('n', 0)
        
        # Age group percentile (if demographics provided)
        if demographics and 'age_group' in demographics:
            age_group = demographics['age_group']
            age_data = self._get_segment_data(dim_data, ('age_group', age_group))
            if age_data and age_data.get('n', 0) >= self.min_sample_size:
                values = age_data.get('values', [])
                percentile = self._calculate_percentile_from_distribution(score, values)
                result['age_group_percentile'] = percentile
                result['n_age_group'] = age_data.get('n', 0)
        
        # Frequency user percentile (if demographics provided)
        if demographics and 'ai_tool_use_frequency' in demographics:
            frequency = demographics['ai_tool_use_frequency']
            freq_data = self._get_segment_data(dim_data, ('frequency', frequency))
            if freq_data and freq_data.get('n', 0) >= self.min_sample_size:
                values = freq_data.get('values', [])
                percentile = self._calculate_percentile_from_distribution(score, values)
                result['frequency_percentile'] = percentile
                result['n_frequency'] = freq_data.get('n', 0)
        
        return result
    
    @staticmethod
    def _calculate_percentile_from_distribution(score, values):
        """
        Calculate percentile rank of a score within a distribution.
        
        Args:
            score (float): The score to rank
            values (list): Sorted list of benchmark values
        
        Returns:
            int: Percentile (0-100)
        """
        if not values:
            return 50  # Default to median if no data
        
        # Use numpy's percentileofscore equivalent
        arr = np.array(values)
        percentile = (np.sum(arr < score) / len(arr)) * 100
        
        # Cap at 99 (nobody is >99th percentile)
        return int(min(percentile, 99)) if percentile > 0 else 1
    
    def get_dimension_mean(self, dimension_name, demographics=None):
        """
        Get population mean for a dimension (for context in reports).
        
        Args:
            dimension_name (str): e.g., 'reliance'
            demographics (dict, optional): If provided, returns cohort mean
        
        Returns:
            float: Mean score for population (or cohort if demographics provided)
        """
        dim_data = self.get_dimension_data(dimension_name)
        
        if demographics and 'age_group' in demographics:
            age_group = demographics['age_group']
            age_segments = dim_data.get('by_age_group', {})
            age_key = self._match_segment_key(age_group, age_segments.keys())
            age_data = age_segments.get(age_key) if age_key else None
            if age_data:
                return age_data.get('mean', 0)
        
        overall = dim_data.get('overall', {})
        return overall.get('mean', 0)
    
    def validate_dimension_score(self, dimension_name, score):
        """
        Validate that a dimension score is within expected range.
        
        Args:
            dimension_name (str): e.g., 'reliance'
            score (float): Dimension score to validate
        
        Returns:
            bool: True if valid (1-7 or reasonable aggregate), False otherwise
        """
        if not isinstance(score, (int, float)):
            return False
        
        # Dimension scores are typically 1-7 (average of variable responses)
        # Allow slight flexibility for rounding
        return 0.5 <= score <= 7.5

    @staticmethod
    def _normalise_key(value):
        """
        Normalise demographic/segment keys for robust matching.

        Canonical age values:
        18-24, 25-34, 35-44, 45-54, 55-64, 65+
        """
        if value is None:
            return None
        text = str(value).strip().lower()
        if not text:
            return None

        # Normalise dashes/spaces.
        text = text.replace('–', '-').replace('—', '-').replace('−', '-')
        text = re.sub(r'\s+', ' ', text)
        compact = text.replace(' ', '')

        aliases = {
            '18-24': '18-24', '18to24': '18-24', '18_24': '18-24',
            '25-34': '25-34', '25to34': '25-34', '25_34': '25-34',
            '35-44': '35-44', '35to44': '35-44', '35_44': '35-44',
            '45-54': '45-54', '45to54': '45-54', '45_54': '45-54',
            '55-64': '55-64', '55to64': '55-64', '55_64': '55-64', '55-65': '55-64', '55to65': '55-64',
            '65+': '65+', 'over65': '65+', '65andover': '65+', '65plus': '65+',
            'everyday': 'everyday', 'every day': 'everyday', 'daily': 'everyday',
            'often': 'often', 'veryoften': 'often', 'very often': 'often',
            'sometimes': 'sometimes', 'occasionally': 'sometimes', 'occasional': 'sometimes',
            'rarely': 'rarely', 'rare': 'rarely',
            'never': 'never',
        }
        return aliases.get(compact, aliases.get(text, compact))

    @classmethod
    def _match_segment_key(cls, requested_value, available_keys):
        """Return the actual benchmark key matching requested_value, or None."""
        if requested_value is None:
            return None
        available_keys = list(available_keys or [])
        if requested_value in available_keys:
            return requested_value

        requested_norm = cls._normalise_key(requested_value)
        for key in available_keys:
            if cls._normalise_key(key) == requested_norm:
                return key
        return None

    def _get_segment_data(self, item_data, segment):
        """
        Return segment data for variables/dimensions using robust key matching.
        If a segment is requested and unavailable, return None. Never fall back to overall.
        """
        if not segment:
            return item_data.get('overall')

        try:
            segment_type, segment_value = segment
        except Exception:
            return None

        # Support both schemas currently present in benchmark_tables.json:
        # - dimensions: by_age_group
        # - variables:  by_age
        # This keeps the benchmark JSON as the source of truth while making lookups robust.
        possible_segment_keys = [f'by_{segment_type}']

        if segment_type == 'age_group':
            possible_segment_keys.extend(['by_age', 'by_age_group'])
        elif segment_type == 'age':
            possible_segment_keys.extend(['by_age_group', 'by_age'])
        elif segment_type == 'frequency':
            possible_segment_keys.extend(['by_frequency', 'by_ai_tool_use_frequency'])
        elif segment_type == 'ai_tool_use_frequency':
            possible_segment_keys.extend(['by_frequency', 'by_ai_tool_use_frequency'])

        # De-duplicate while preserving order.
        seen = set()
        possible_segment_keys = [
            k for k in possible_segment_keys
            if not (k in seen or seen.add(k))
        ]

        for segment_key in possible_segment_keys:
            segments = item_data.get(segment_key) or {}
            if not isinstance(segments, dict) or not segments:
                continue

            actual_key = self._match_segment_key(segment_value, segments.keys())
            if actual_key is not None:
                return segments.get(actual_key)

        return None

    def get_percentile(self, variable_key, response_value, segment=None):
        """
        Calculate percentile for a specific variable response.

        Important behaviour:
        - Overall lookup uses overall values.
        - Segment lookup uses only the requested segment if it exists and meets MIN_SAMPLE.
        - Segment lookup NEVER falls back to overall or median/50.
        - Missing/underpowered segment returns None.
        """
        try:
            if 'variables' not in self.data:
                return None
            if variable_key not in self.data['variables']:
                return None

            var_data = self.data['variables'][variable_key]
            source = self._get_segment_data(var_data, segment)
            if not isinstance(source, dict):
                return None

            if segment and source.get('n', 0) < self.min_sample_size:
                return None

            values = source.get('values', [])
            if not values:
                return None

            return self._calculate_percentile_from_distribution(response_value, values)

        except Exception as e:
            print(f"Error calculating percentile for {variable_key}: {str(e)}")
            return None

    def get_sample_size(self, variable_key, segment=None):
        """
        Get the sample size (n) for a variable in the benchmark.

        Important behaviour:
        - If a segment is requested and missing, return 0.
        - Never return overall n for a missing segment.
        """
        try:
            if 'variables' not in self.data:
                return 0
            if variable_key not in self.data['variables']:
                return 0

            var_data = self.data['variables'][variable_key]
            source = self._get_segment_data(var_data, segment)
            if isinstance(source, dict):
                return source.get('n', 0)
            return 0

        except Exception as e:
            print(f"Error getting sample size for {variable_key}: {str(e)}")
            return 0


# Singleton instance (loaded once on import)
_benchmark_instance = None


def load_benchmark(benchmark_path='benchmark_tables.json'):
    """
    Load benchmark data (called once at startup).
    
    Args:
        benchmark_path (str): Path to benchmark_tables.json
    
    Returns:
        BenchmarkBuilder: Benchmark instance
    """
    global _benchmark_instance
    if _benchmark_instance is None:
        _benchmark_instance = BenchmarkBuilder(benchmark_path)
    return _benchmark_instance


def get_benchmark():
    """
    Get loaded benchmark instance (assumes load_benchmark() called first).
    
    Returns:
        BenchmarkBuilder: Benchmark instance
    """
    global _benchmark_instance
    if _benchmark_instance is None:
        _benchmark_instance = load_benchmark()
    return _benchmark_instance
