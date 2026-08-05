"""
test_report_data_builder_v2.py

Contract and deterministic-selection tests for the HCI premium report V2.

Run from the repository root with:

    python -m unittest test_report_data_builder_v2.py

These tests use a small deterministic benchmark fixture. They do not call
Anthropic, Supabase, Stripe, PDFShift or any external service.
"""

from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

import report_data_builder as rdb


class FakeBenchmark:
    """Minimal benchmark object matching the live BenchmarkBuilder interface."""

    min_sample_size = 30
    version = "test-benchmark-2026-08-05"
    generated_at = "2026-08-05T00:00:00+00:00"
    benchmark_hash = "test-benchmark-hash"

    def __init__(self, include_frequency: bool = True) -> None:
        self.data = {
            "metadata": {
                "version": self.version,
                "generated_at": self.generated_at,
                "benchmark_hash": self.benchmark_hash,
            },
            "dimensions": {},
            "variables": {},
        }

        overall_values = [round(1 + (i * 6 / 99), 4) for i in range(100)]
        age_values = overall_values[:]
        frequency_values = list(reversed(overall_values))

        for dimension in rdb.DIMENSION_ORDER:
            dimension_data = {
                "overall": {
                    "n": len(overall_values),
                    "values": overall_values,
                },
                "by_age_group": {
                    "35-44": {
                        "n": len(age_values),
                        "values": age_values,
                    }
                },
                "by_frequency": {},
            }
            if include_frequency:
                dimension_data["by_frequency"]["Everyday"] = {
                    "n": len(frequency_values),
                    "values": frequency_values,
                }
            self.data["dimensions"][dimension] = dimension_data

        for variables in rdb.DIMENSION_VARIABLES.values():
            for key in variables:
                values = [((i % 7) + 1) for i in range(140)]
                variable_data = {
                    "overall": {
                        "n": len(values),
                        "values": values,
                    },
                    "by_age": {
                        "35-44": {
                            "n": len(values),
                            "values": values,
                        }
                    },
                    "by_frequency": {},
                }
                if include_frequency:
                    variable_data["by_frequency"]["Everyday"] = {
                        "n": len(values),
                        "values": list(reversed(values)),
                    }
                self.data["variables"][key] = variable_data

    def calculate_percentile(self, dimension_name, score, demographics=None):
        demographics = demographics or {}
        dim_data = self.data["dimensions"][dimension_name]

        result = {
            "overall_percentile": rdb.calculate_percentile_from_values(
                score,
                dim_data["overall"]["values"],
            ),
            "age_group_percentile": None,
            "frequency_percentile": None,
            "n_overall": dim_data["overall"]["n"],
            "n_age_group": None,
            "n_frequency": None,
        }

        age = demographics.get("age_group")
        if age in dim_data["by_age_group"]:
            source = dim_data["by_age_group"][age]
            if source["n"] >= self.min_sample_size:
                result["age_group_percentile"] = (
                    rdb.calculate_percentile_from_values(
                        score,
                        source["values"],
                    )
                )
                result["n_age_group"] = source["n"]

        frequency = demographics.get("ai_tool_use_frequency")
        if frequency in dim_data["by_frequency"]:
            source = dim_data["by_frequency"][frequency]
            if source["n"] >= self.min_sample_size:
                result["frequency_percentile"] = (
                    rdb.calculate_percentile_from_values(
                        score,
                        source["values"],
                    )
                )
                result["n_frequency"] = source["n"]

        return result


def make_responses() -> dict:
    """Return all 39 scored responses plus the three perception items."""
    responses = {}
    answer = 1
    for dimension in rdb.DIMENSION_ORDER:
        for key in rdb.DIMENSION_VARIABLES[dimension]:
            responses[key] = answer
            answer = 1 if answer == 7 else answer + 1

    responses.update({
        "perceived_usage": "More than most people",
        "perceived_reliance": "About the same as most people",
        "perceived_dependence": "Less than most people",
    })
    return responses


def make_scoring_results(
    rarity_percent=4.0,
    rarity_source="calculated",
) -> dict:
    """Return a representative scoring result using live dimension keys."""
    percentiles = {
        "reliance": 88,
        "trust": 72,
        "verification": 91,
        "decision_delegation": 84,
        "human_agency": 28,
        "emotional_regulation": 12,
        "disclosure": 44,
        "thought_partnership": 95,
        "social_transparency": 36,
    }

    dimension_scores = {}
    for index, dimension in enumerate(rdb.DIMENSION_ORDER):
        dimension_scores[dimension] = {
            "raw_score": 1.4 + (index * 0.55),
            "percentile_overall": percentiles[dimension],
            # Cohort values are intentionally omitted so the builder exercises
            # the benchmark recalculation path.
        }

    combination = {
        "dimension_1": "thought_partnership",
        "dimension_2": "emotional_regulation",
        "percentile_dim1": 95,
        "percentile_dim2": 12,
        "description": (
            "High Thought Partnership combined with low "
            "Emotional Regulation"
        ),
    }
    if rarity_percent is not None:
        combination["rarity_percent"] = rarity_percent
    if rarity_source is not None:
        combination["rarity_source"] = rarity_source

    return {
        "session_id": "test-session",
        "dimension_scores": dimension_scores,
        "rare_combinations": [combination],
        "perception_gaps": [],
    }


def build_fixture_report(
    *,
    benchmark=None,
    scoring_results=None,
) -> dict:
    benchmark = benchmark or FakeBenchmark()
    scoring_results = scoring_results or make_scoring_results()
    responses = make_responses()
    demographics = {
        "age_group": "35-44",
        "ai_tool_use_frequency": "Everyday",
        "country": "NZ",
    }

    with patch.object(rdb, "get_benchmark_instance", return_value=benchmark):
        return rdb.build_report_data(
            scoring_results=scoring_results,
            responses=responses,
            demographics=demographics,
            email="participant@example.com",
            session_id="test-session",
        )


class ReportDataV2ContractTests(unittest.TestCase):

    def test_builds_locked_v2_contract(self):
        report = build_fixture_report()

        self.assertEqual(report["schema_version"], "hci_report_data_v2")
        self.assertEqual(len(report["position"]), 9)
        self.assertEqual(len(report["dimension_reference"]), 9)
        self.assertEqual(len(report["appendix_questions"]), 39)
        self.assertEqual(len(report["defining_signals"]), 3)
        self.assertGreaterEqual(len(report["evidence"]), 5)
        self.assertLessEqual(len(report["evidence"]), 7)
        self.assertTrue(report["data_quality"]["ok"])

    def test_complete_question_profile_is_preserved_in_appendix(self):
        report = build_fixture_report()

        appendix_keys = {
            item["key"] for item in report["appendix_questions"]
        }
        expected_keys = {
            key
            for dimension in rdb.DIMENSION_ORDER
            for key in rdb.DIMENSION_VARIABLES[dimension]
        }

        self.assertEqual(appendix_keys, expected_keys)
        self.assertEqual(len(appendix_keys), 39)

    def test_main_evidence_is_a_subset_of_appendix(self):
        report = build_fixture_report()

        appendix_keys = {
            item["key"] for item in report["appendix_questions"]
        }
        evidence_keys = {
            item["key"] for item in report["evidence"]
        }

        self.assertTrue(evidence_keys.issubset(appendix_keys))
        self.assertEqual(len(evidence_keys), len(report["evidence"]))

    def test_defining_signals_are_selected_deterministically(self):
        first = build_fixture_report()
        second = build_fixture_report()

        first_keys = [item["key"] for item in first["defining_signals"]]
        second_keys = [item["key"] for item in second["defining_signals"]]

        self.assertEqual(first_keys, second_keys)
        self.assertEqual(len(set(first_keys)), 3)
        self.assertIn("thought_partnership", first_keys)
        self.assertIn("emotional_regulation", first_keys)

    def test_missing_frequency_data_remains_unavailable(self):
        report = build_fixture_report(
            benchmark=FakeBenchmark(include_frequency=False)
        )

        self.assertTrue(
            all(
                item["frequency_percentile"] is None
                for item in report["position"]
            )
        )
        self.assertEqual(report["comparison_shifts"], [])
        self.assertTrue(
            any(
                "No valid similar-frequency" in warning
                for warning in report["data_quality"]["warnings"]
            )
        )

    def test_supported_rarity_is_shareable(self):
        report = build_fixture_report(
            scoring_results=make_scoring_results(
                rarity_percent=4.0,
                rarity_source="calculated",
            )
        )

        combo = report["distinctive_pattern"]["combination"]
        self.assertEqual(combo["rarity_percent"], 4.0)
        self.assertEqual(combo["rarity_source"], "calculated")
        self.assertTrue(combo["rarity_shareable"])
        self.assertTrue(
            report["signature"]["shareable"]["rarity_badge_allowed"]
        )

    def test_missing_rarity_is_not_replaced_with_default_five_percent(self):
        report = build_fixture_report(
            scoring_results=make_scoring_results(
                rarity_percent=None,
                rarity_source=None,
            )
        )

        combo = report["distinctive_pattern"]["combination"]
        self.assertIsNone(combo["rarity_percent"])
        self.assertEqual(combo["rarity_source"], "fallback")
        self.assertFalse(combo["rarity_shareable"])
        self.assertFalse(
            report["signature"]["shareable"]["rarity_badge_allowed"]
        )

    def test_unapproved_rarity_source_is_not_shareable(self):
        report = build_fixture_report(
            scoring_results=make_scoring_results(
                rarity_percent=4.0,
                rarity_source="fallback",
            )
        )

        combo = report["distinctive_pattern"]["combination"]
        self.assertEqual(combo["rarity_percent"], 4.0)
        self.assertEqual(combo["rarity_source"], "fallback")
        self.assertFalse(combo["rarity_shareable"])

    def test_strongest_combination_prefers_supported_rarity(self):
        dimensions = {
            dimension: {
                "percentile": 50,
            }
            for dimension in rdb.DIMENSION_ORDER
        }
        combinations = [
            {
                "dimension_1": "trust",
                "dimension_2": "reliance",
                "percentile_1": 99,
                "percentile_2": 1,
                "rarity_percent": None,
                "rarity_source": "fallback",
                "rarity_shareable": False,
            },
            {
                "dimension_1": "verification",
                "dimension_2": "human_agency",
                "percentile_1": 85,
                "percentile_2": 20,
                "rarity_percent": 7.0,
                "rarity_source": "calculated",
                "rarity_shareable": True,
            },
        ]

        strongest = rdb.select_strongest_combination(combinations)
        self.assertEqual(strongest["dimension_1"], "verification")
        self.assertTrue(strongest["rarity_shareable"])

    def test_baseline_preserves_benchmark_metadata(self):
        report = build_fixture_report()
        baseline = report["baseline"]

        self.assertEqual(
            baseline["benchmark"]["version"],
            FakeBenchmark.version,
        )
        self.assertEqual(
            baseline["benchmark"]["hash"],
            FakeBenchmark.benchmark_hash,
        )
        self.assertEqual(
            baseline["benchmark"]["generated_at"],
            FakeBenchmark.generated_at,
        )
        self.assertEqual(len(baseline["comparison_priorities"]), 3)
        self.assertEqual(
            baseline["recommended_reassessment_window"],
            "6–12 months",
        )

    def test_contract_rejects_wrong_question_count(self):
        report = build_fixture_report()
        malformed = copy.deepcopy(report)
        malformed["appendix_questions"] = malformed[
            "appendix_questions"
        ][:-1]

        with self.assertRaisesRegex(
            ValueError,
            "39 questions",
        ):
            rdb.assert_report_data_contract(malformed)

    def test_contract_rejects_unapproved_shareable_rarity(self):
        report = build_fixture_report()
        malformed = copy.deepcopy(report)
        malformed["rare_combinations"][0]["rarity_shareable"] = True
        malformed["rare_combinations"][0]["rarity_source"] = "fallback"

        with self.assertRaisesRegex(
            ValueError,
            "approved source",
        ):
            rdb.assert_report_data_contract(malformed)


if __name__ == "__main__":
    unittest.main()
