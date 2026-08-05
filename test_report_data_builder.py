"""
test_report_data_builder_v2.py

Data-flow, contract and deterministic-selection tests for the HCI premium
report V2.

Run from repository root:

    python -m unittest test_report_data_builder_v2.py

These tests use scoring-engine-shaped fixtures and do not call external
services.
"""

from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

import report_data_builder as rdb


class FakeBenchmark:
    """Minimal benchmark matching the live BenchmarkBuilder interface."""

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
        frequency_values = overall_values[:]

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
                        "values": values,
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
    """Return all 39 scored responses plus live perception answer values."""
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
    *,
    rarity_percent=5.0,
    rarity_source=None,
    include_perception_gap=True,
) -> dict:
    """
    Return the exact field shapes produced by the live scoring engine.
    """
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
            "percentile_age_group": None,
            "percentile_frequency": None,
            "n_overall": 358,
            "n_age_group": None,
            "n_frequency": None,
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
        "is_distinctive": True,
        "combo_classification": "true_rare",
        "combination_id": (
            "high_thought_partnership_low_emotional_regulation"
        ),
        "signal_type": "cognitive_emotional_separation",
    }
    if rarity_percent is not None:
        combination["rarity_percent"] = rarity_percent
    if rarity_source is not None:
        combination["rarity_source"] = rarity_source

    perception_gaps = []
    if include_perception_gap:
        perception_gaps.append({
            "question": "perceived_usage",
            "comparison_source": "usage_frequency",
            "perceived_answer": "More than most people",
            "actual_percentile": 90,
            "perceived_percentile": 65,
            "gap_magnitude": 25.0,
        })

    return {
        "session_id": "test-session",
        "timestamp": "2026-08-05T03:15:00",
        "demographics": {
            "age_group": "35-44",
            "ai_tool_use_frequency": "Everyday",
            "country": "NZ",
        },
        "dimension_scores": dimension_scores,
        "patterns": {
            "highest": [],
            "lowest": [],
            "full_ranking": [],
        },
        "headline": "Test profile",
        "perception_gaps": perception_gaps,
        "rare_combinations": [combination],
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


class ReportDataV2Tests(unittest.TestCase):

    def test_original_data_flow_keys_are_preserved(self):
        report = build_fixture_report()

        legacy_keys = {
            "dimensions",
            "dashboard",
            "typicality",
            "rare_combinations",
            "questions",
            "distinctive_responses",
            "perception_gap",
            "what_to_protect",
            "if_nothing_changes",
            "synthesis_inputs",
            "narrative_blocks",
            "human_capital",
        }
        self.assertTrue(legacy_keys.issubset(report.keys()))
        self.assertEqual(len(report["dimensions"]), 9)
        self.assertEqual(len(report["dashboard"]), 9)
        self.assertEqual(len(report["questions"]), 39)
        self.assertEqual(len(report["distinctive_responses"]), 7)
        self.assertEqual(len(report["what_to_protect"]), 4)
        self.assertTrue(report["if_nothing_changes"])
        self.assertTrue(report["human_capital"])

    def test_legacy_distinctive_response_selection_is_unchanged(self):
        report = build_fixture_report()
        expected = rdb.build_distinctive_responses(
            report["questions"],
            7,
        )
        self.assertEqual(report["distinctive_responses"], expected)

    def test_builds_locked_v2_additions(self):
        report = build_fixture_report()

        self.assertEqual(report["schema_version"], "hci_report_data_v2")
        self.assertEqual(
            report["legacy_schema_version"],
            "hci_report_data_v1",
        )
        self.assertEqual(len(report["position"]), 9)
        self.assertEqual(len(report["dimension_reference"]), 9)
        self.assertEqual(len(report["appendix_questions"]), 39)
        self.assertEqual(len(report["defining_signals"]), 3)
        self.assertGreaterEqual(len(report["evidence"]), 5)
        self.assertLessEqual(len(report["evidence"]), 7)
        self.assertEqual(report["data_quality"]["errors"], [])

    def test_appendix_is_derived_from_original_question_objects(self):
        report = build_fixture_report()
        self.assertEqual(
            report["appendix_questions"],
            report["questions"],
        )
        self.assertIsNot(
            report["appendix_questions"],
            report["questions"],
        )

    def test_main_evidence_is_a_subset_of_original_questions(self):
        report = build_fixture_report()

        question_keys = {item["key"] for item in report["questions"]}
        evidence_keys = {item["key"] for item in report["evidence"]}

        self.assertTrue(evidence_keys.issubset(question_keys))
        self.assertEqual(len(evidence_keys), len(report["evidence"]))

    def test_defining_signals_use_extremity_not_weighted_override(self):
        report = build_fixture_report()

        selected = [
            item["key"] for item in report["defining_signals"]
        ]
        expected = [
            item["key"]
            for item in sorted(
                report["dimensions"].values(),
                key=lambda item: abs(item["percentile"] - 50),
                reverse=True,
            )[:3]
        ]
        self.assertEqual(selected, expected)

    def test_only_meaningful_similar_user_shifts_are_selected(self):
        position = [
            {
                "key": "trust",
                "label": "Trust",
                "overall_percentile": 80,
                "frequency_percentile": 74,
                "frequency_n": 100,
            },
            {
                "key": "verification",
                "label": "Verification",
                "overall_percentile": 75,
                "frequency_percentile": 58,
                "frequency_n": 100,
            },
        ]
        shifts = rdb.build_comparison_shifts(position)
        self.assertEqual(len(shifts), 1)
        self.assertEqual(shifts[0]["dimension"], "verification")
        self.assertEqual(shifts[0]["absolute_shift"], 17)

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
                "frequency percentile missing" in warning.lower()
                for warning in report["data_quality"]["warnings"]
            )
        )

    def test_scoring_engine_perception_gap_shape_is_mapped(self):
        report = build_fixture_report()
        summary = report["perception_summary"]
        usage = next(
            item for item in summary["items"]
            if item["key"] == "perceived_usage"
        )

        self.assertEqual(usage["assessment_percentile"], 90)
        self.assertEqual(usage["perceived_percentile"], 65)
        self.assertEqual(usage["difference"], 25)
        self.assertEqual(usage["gap_magnitude"], 25.0)
        self.assertEqual(
            summary["largest_difference"]["key"],
            "perceived_usage",
        )

    def test_baseline_uses_real_scoring_timestamp(self):
        report = build_fixture_report()

        self.assertEqual(
            report["assessment_completed_at"],
            "2026-08-05T03:15:00",
        )
        self.assertEqual(
            report["report_meta"]["baseline_date"],
            "2026-08-05T03:15:00",
        )
        self.assertEqual(
            report["baseline"]["baseline_date"],
            "2026-08-05T03:15:00",
        )

    def test_live_scoring_rarity_without_provenance_is_blocked(self):
        report = build_fixture_report(
            scoring_results=make_scoring_results(
                rarity_percent=5.0,
                rarity_source=None,
            )
        )
        combo = report["rare_combinations"][0]

        self.assertEqual(combo["rarity_percent"], 5.0)
        self.assertEqual(combo["rarity_source"], "fallback")
        self.assertFalse(combo["rarity_shareable"])
        self.assertIsNone(combo["public_rarity_percent"])
        self.assertFalse(
            report["signature"]["shareable"]["rarity_badge_allowed"]
        )

    def test_explicit_calculated_rarity_is_shareable(self):
        report = build_fixture_report(
            scoring_results=make_scoring_results(
                rarity_percent=4.0,
                rarity_source="calculated",
            )
        )
        combo = report["rare_combinations"][0]

        self.assertTrue(combo["rarity_shareable"])
        self.assertEqual(combo["public_rarity_percent"], 4.0)
        self.assertTrue(
            report["signature"]["shareable"]["rarity_badge_allowed"]
        )

    def test_strongest_combination_preserves_scorer_order(self):
        combinations = [
            {
                "dimension_1": "trust",
                "dimension_2": "reliance",
                "rarity_shareable": False,
            },
            {
                "dimension_1": "verification",
                "dimension_2": "human_agency",
                "rarity_shareable": True,
            },
        ]
        strongest = rdb.select_strongest_combination(combinations)
        self.assertEqual(strongest["dimension_1"], "trust")

    def test_reverse_scored_evidence_wording_is_direction_neutral(self):
        questions = [
            {
                "key": "trust_q3",
                "dimension": "trust",
                "dimension_label": "Trust",
                "question_text": "Reverse item",
                "answer": 7,
                "percentile": 99,
                "percentile_frequency": 95,
                "is_reverse_scored": True,
            }
        ]
        defining = [{"key": "trust"}]
        evidence = rdb.build_main_evidence(
            questions,
            defining,
            limit=7,
        )

        self.assertIn(
            "helping explain",
            evidence[0]["evidence_statement"],
        )
        self.assertNotIn(
            "supporting your",
            evidence[0]["evidence_statement"],
        )
        self.assertIn(
            "reverse-scored",
            evidence[0]["scoring_note"],
        )

    def test_original_qa_checks_are_retained(self):
        report = build_fixture_report()
        damaged = copy.deepcopy(report)
        damaged["questions"][0]["distribution_everyone"] = None
        quality = rdb.build_v2_data_quality(damaged)

        self.assertTrue(
            any(
                "overall question distributions missing" in warning
                for warning in quality["warnings"]
            )
        )

    def test_safe_signal_layer_is_imported(self):
        from hci_signals_library import REPORT_SAFE_SIGNALS
        self.assertIs(rdb.SIGNALS, REPORT_SAFE_SIGNALS)

    def test_contract_rejects_wrong_question_count(self):
        report = build_fixture_report()
        malformed = copy.deepcopy(report)
        malformed["appendix_questions"] = malformed[
            "appendix_questions"
        ][:-1]

        with self.assertRaisesRegex(ValueError, "39 questions"):
            rdb.assert_report_data_contract(malformed)

    def test_contract_rejects_unapproved_shareable_rarity(self):
        report = build_fixture_report()
        malformed = copy.deepcopy(report)
        malformed["rare_combinations"][0][
            "rarity_shareable"
        ] = True
        malformed["rare_combinations"][0][
            "public_rarity_percent"
        ] = 5.0
        malformed["rare_combinations"][0][
            "rarity_source"
        ] = "fallback"

        with self.assertRaisesRegex(ValueError, "approved source"):
            rdb.assert_report_data_contract(malformed)


if __name__ == "__main__":
    unittest.main()
