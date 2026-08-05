"""
Contract and integration tests for the HCI narrative pipeline.

Run from the repository root:

    python -m unittest test_narrative_pipeline.py

The tests use deterministic fixtures and never call external services.
"""

from __future__ import annotations

import copy
import inspect
import json
import re
import unittest
from unittest.mock import patch

import claude_narrative as cn
import narrative_context_builder as ncb
from test_report_data_builder import (
    build_fixture_report,
    make_scoring_results,
)


class NarrativeContextTests(unittest.TestCase):

    def test_context_matches_canonical_report_contract(self):
        report = build_fixture_report()
        context = ncb.build_narrative_context(report)

        self.assertEqual(context["schema"], "hci_narrative_context")
        self.assertEqual(len(context["profile_synthesis"]["profile_shape"]), 9)
        self.assertEqual(
            len(context["profile_synthesis"]["defining_signals"]),
            3,
        )
        self.assertGreaterEqual(
            len(context["profile_synthesis"]["main_evidence"]),
            5,
        )
        self.assertLessEqual(
            len(context["profile_synthesis"]["main_evidence"]),
            7,
        )
        self.assertEqual(
            len(context["baseline_return"]["comparison_priorities"]),
            3,
        )

    def test_context_excludes_contact_details_and_full_question_dump(self):
        report = build_fixture_report()
        context = ncb.build_narrative_context(report)
        serialized = json.dumps(context, ensure_ascii=False)

        self.assertNotIn("participant@example.com", serialized)
        self.assertNotIn("test-session", serialized)
        self.assertNotIn('"questions"', serialized)
        self.assertNotIn('"responses"', serialized)

    def test_context_excludes_internal_question_ids(self):
        report = build_fixture_report()
        context = ncb.build_narrative_context(report)
        serialized = json.dumps(context, ensure_ascii=False)

        self.assertIsNone(
            re.search(
                r"\b(?:rel|trust|ver|del|agency|emot|disc|thought|soc)_q\d+\b",
                serialized,
                flags=re.IGNORECASE,
            )
        )

    def test_unsupported_rarity_is_not_exposed(self):
        report = build_fixture_report(
            scoring_results=make_scoring_results(
                rarity_percent=5.0,
                rarity_source=None,
            )
        )
        combination = ncb.build_narrative_context(report)[
            "profile_synthesis"
        ]["strongest_pattern"]["combination"]

        self.assertFalse(
            combination["rarity_available_for_public_use"]
        )
        self.assertNotIn("rarity_percent", combination)
        self.assertNotIn("rarity_basis", combination)

    def test_approved_rarity_is_exposed(self):
        report = build_fixture_report(
            scoring_results=make_scoring_results(
                rarity_percent=4.0,
                rarity_source="calculated",
            )
        )
        combination = ncb.build_narrative_context(report)[
            "profile_synthesis"
        ]["strongest_pattern"]["combination"]

        self.assertTrue(
            combination["rarity_available_for_public_use"]
        )
        self.assertEqual(combination["rarity_percent"], 4.0)
        self.assertEqual(combination["rarity_basis"], "calculated")

    def test_human_capital_selection_follows_defining_signal_order(self):
        report = build_fixture_report()
        themes = ncb.select_human_capital_themes(report)

        self.assertEqual(len(themes), 3)
        self.assertEqual(
            [item["title"] for item in themes],
            [
                "Intellectual openness",
                "Critical scepticism",
                "Independent view formation",
            ],
        )
        self.assertEqual(
            len({item["theme"] for item in themes}),
            3,
        )
        self.assertTrue(
            all(
                item["selection_basis"] == "ordered defining signals"
                for item in themes
            )
        )
        self.assertTrue(
            all("relevance_score" not in item for item in themes)
        )

    def test_context_uses_report_benchmark_metadata(self):
        report = build_fixture_report()
        context = ncb.build_narrative_context(report)
        benchmark = context["profile_synthesis"]["benchmark_scope"]

        self.assertEqual(benchmark["label"], "HCI participant benchmark")
        self.assertEqual(
            benchmark["response_count_label"],
            "10,000+ participant responses",
        )
        self.assertEqual(benchmark["study_count"], 21)
        self.assertEqual(
            benchmark["benchmark_identifier"],
            "test-benchmark-2026-08-05",
        )


class ClaudeNarrativeTests(unittest.TestCase):

    def test_no_api_key_uses_complete_fallback_without_network(self):
        report = build_fixture_report()

        with patch.object(cn, "call_claude_structured") as call:
            result = cn.add_claude_narratives(report, api_key=None)

        call.assert_not_called()
        self.assertEqual(
            result["narrative_generation"]["status"],
            "skipped_no_api_key",
        )
        self.assertTrue(result["signature"]["signature_sentence"])
        self.assertTrue(result["distinctive_pattern"]["narrative"])
        self.assertTrue(result["pattern_synthesis"]["pattern_narrative"])
        self.assertEqual(len(result["human_capital_lens"]), 3)
        self.assertTrue(result["baseline"]["return_question"].endswith("?"))
        self.assertTrue(result["baseline"]["baseline_closing"])

    def test_successful_run_makes_exactly_two_structured_calls(self):
        report = build_fixture_report()
        context = ncb.build_narrative_context(report)
        titles = [
            item["title"]
            for item in context["profile_synthesis"]["human_capital_themes"]
        ]
        profile_output = {
            "signature_sentence": "Your current pattern combines distinct forms of engagement with clear differences across the benchmark.",
            "combination_narrative": "The selected results form one connected pattern.\n\nTogether, they may clarify how you currently involve AI in thinking and decisions.",
            "pattern_narrative": "The defining signals establish the main shape of the profile.\n\nThe selected evidence supports that shape.\n\nThe similar-user comparison adds context.\n\nTogether, these results form a clear current reference point.",
            "human_capital_lens": [
                {"title": title, "body": f"{title} is relevant to the current response pattern."}
                for title in titles
            ],
        }
        baseline_output = {
            "return_question": "When you reassess, will the relationship among your defining signals look similar to the pattern recorded today?",
            "baseline_closing": "This report establishes a dated reference point for comparing your reported AI-use pattern later.",
        }

        with patch.object(
            cn,
            "call_claude_structured",
            side_effect=[profile_output, baseline_output],
        ) as call:
            result = cn.add_claude_narratives(report, api_key="test-key")

        self.assertEqual(call.call_count, 2)
        self.assertEqual(
            result["narrative_generation"]["successful_calls"],
            2,
        )
        self.assertEqual(
            result["signature"]["signature_sentence"],
            profile_output["signature_sentence"],
        )
        self.assertEqual(
            result["baseline"]["return_question"],
            baseline_output["return_question"],
        )

    def test_one_failed_call_does_not_block_the_other(self):
        report = build_fixture_report()
        baseline_output = {
            "return_question": "When you reassess, will your defining results retain the same relationship recorded in this baseline?",
            "baseline_closing": "This report establishes a dated reference point for a later comparison of your reported pattern.",
        }

        with patch.object(
            cn,
            "call_claude_structured",
            side_effect=[RuntimeError("profile failed"), baseline_output],
        ) as call:
            result = cn.add_claude_narratives(report, api_key="test-key")

        self.assertEqual(call.call_count, 2)
        self.assertEqual(
            result["narrative_generation"]["status"],
            "partial_using_fallbacks",
        )
        self.assertTrue(result["signature"]["signature_sentence"])
        self.assertEqual(
            result["baseline"]["return_question"],
            baseline_output["return_question"],
        )

    def test_locked_human_capital_titles_are_enforced(self):
        report = build_fixture_report()
        context = ncb.build_narrative_context(report)["profile_synthesis"]
        output = cn.profile_fallback(context)
        output["human_capital_lens"][0]["title"] = "Changed title"

        with self.assertRaisesRegex(ValueError, "locked Human Capital"):
            cn.validate_profile_output(output, context)

    def test_report_input_is_not_mutated(self):
        report = build_fixture_report()
        original = copy.deepcopy(report)

        cn.add_claude_narratives(report, api_key=None)

        self.assertEqual(report, original)

    def test_generated_outputs_use_only_canonical_narrative_keys(self):
        report = build_fixture_report()
        result = cn.add_claude_narratives(report, api_key=None)

        self.assertEqual(
            set(result["narrative_blocks"].keys()),
            {
                "signature_sentence",
                "combination_narrative",
                "pattern_narrative",
                "human_capital_lens",
                "return_question",
                "baseline_closing",
            },
        )

    def test_obsolete_report_workflows_are_absent(self):
        source = inspect.getsource(cn)
        obsolete_names = [
            "generate_trajectory_narrative",
            "generate_deep_dive_narrative",
            "generate_human_capital_narrative",
            "generate_closing_reflection_narrative",
            "generate_distinctive_and_perception_narrative",
            "build_context_for_claude_section",
        ]
        for name in obsolete_names:
            self.assertNotIn(name, source)

    def test_report_version_labels_are_absent_from_production_symbols(self):
        context_source = inspect.getsource(ncb)
        narrative_source = inspect.getsource(cn)
        combined = context_source + "\n" + narrative_source

        prohibited = [
            "hci_report_data_" + "v" + "1",
            "hci_report_data_" + "v" + "2",
            "hci_narrative_context_" + "v" + "2",
            "build_" + "v" + "2",
            "_add_" + "v" + "2",
            "REPORT_" + "V" + "2",
            "legacy_schema",
        ]
        for value in prohibited:
            self.assertNotIn(value, combined)


if __name__ == "__main__":
    unittest.main()
