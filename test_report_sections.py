"""Contract and integration tests for deterministic report-section assembly."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import unittest

from claude_narrative import add_claude_narratives
from report_sections import (
    FULL_PERSONAL_INSIGHT_DISCLAIMER,
    REPORT_SECTIONS_SCHEMA,
    SECTION_ORDER,
    SHORT_PERSONAL_INSIGHT_DISCLAIMER,
    assert_sections_contract,
    build_sections,
)
from test_report_data_builder import (
    FakeBenchmark,
    build_fixture_report,
    make_scoring_results,
)


class ReportSectionsTests(unittest.TestCase):

    def built_sections(self, *, benchmark=None, scoring_results=None, narratives=True):
        report = build_fixture_report(
            benchmark=benchmark,
            scoring_results=scoring_results,
        )
        if narratives:
            report = add_claude_narratives(report, api_key=None)
        return report, build_sections(report)

    def test_builds_locked_report_order(self):
        _, sections = self.built_sections()
        self.assertEqual(sections["schema"], REPORT_SECTIONS_SCHEMA)
        self.assertEqual(sections["section_order"], SECTION_ORDER)
        self.assertEqual(
            [item["key"] for item in sections["ordered_sections"]],
            SECTION_ORDER,
        )

    def test_contains_only_current_named_sections(self):
        _, sections = self.built_sections()
        obsolete = {
            "opening",
            "dashboard",
            "typicality",
            "rare",
            "story",
            "deep_dive",
            "trajectory",
            "looking_forward",
            "closing_reflection",
        }
        self.assertTrue(obsolete.isdisjoint(sections.keys()))

    def test_cover_contains_report_identity_and_full_disclaimer(self):
        _, sections = self.built_sections()
        cover = sections["cover"]
        self.assertEqual(cover["title"], "AI Identity & Behaviour Report")
        self.assertEqual(cover["subtitle"], "Your HCI AI Behaviour Baseline")
        self.assertEqual(cover["important_information"], FULL_PERSONAL_INSIGHT_DISCLAIMER)
        self.assertEqual(cover["benchmark"]["study_count"], 21)
        self.assertTrue(cover["assessment_date_display"])

    def test_signature_contains_shape_signals_and_dated_baseline(self):
        _, sections = self.built_sections()
        signature = sections["signature"]
        self.assertEqual(len(signature["dimension_shape"]), 9)
        self.assertEqual(len(signature["defining_signals"]), 3)
        self.assertTrue(signature["signature_sentence"])
        self.assertEqual(signature["baseline_date"], "2026-08-05T03:15:00")
        self.assertFalse(signature["shareable"]["contains_contact_details"])

    def test_position_contains_all_dimensions(self):
        _, sections = self.built_sections()
        position = sections["position"]
        self.assertEqual(len(position["items"]), 9)
        self.assertEqual(
            [item["key"] for item in position["items"]],
            list(build_fixture_report()["dimensions"].keys()),
        )

    def test_missing_frequency_comparisons_remain_unavailable(self):
        _, sections = self.built_sections(
            benchmark=FakeBenchmark(include_frequency=False),
        )
        position = sections["position"]
        self.assertEqual(position["availability"]["similar_use"], 0)
        self.assertTrue(
            all(not item.get("frequency_available") for item in position["items"])
        )
        self.assertEqual(sections["similar_users"]["mode"], "unavailable")
        self.assertEqual(sections["similar_users"]["items"], [])

    def test_similar_user_section_uses_only_valid_meaningful_shifts(self):
        report, sections = self.built_sections()
        source = report["comparison_shifts"]
        rendered = sections["similar_users"]["items"]
        self.assertEqual(len(rendered), len(source))
        self.assertTrue(
            all(item["absolute_shift"] >= 10 for item in rendered)
        )
        self.assertTrue(
            all(item.get("similar_use_percentile") is not None for item in rendered)
        )

    def test_unsupported_rarity_is_not_exposed(self):
        _, sections = self.built_sections(
            scoring_results=make_scoring_results(
                rarity_percent=5.0,
                rarity_source=None,
            ),
        )
        combination = sections["distinctive_pattern"]["combination"]
        self.assertFalse(combination["rarity_available"])
        self.assertNotIn("rarity", combination)
        self.assertFalse(sections["signature"]["rarity_badge_allowed"])

    def test_approved_rarity_is_exposed_with_provenance(self):
        _, sections = self.built_sections(
            scoring_results=make_scoring_results(
                rarity_percent=4.0,
                rarity_source="calculated",
            ),
        )
        combination = sections["distinctive_pattern"]["combination"]
        self.assertTrue(combination["rarity_available"])
        self.assertEqual(combination["rarity"]["percent"], 4.0)
        self.assertEqual(combination["rarity"]["source"], "calculated")

    def test_evidence_contains_five_to_seven_auditable_items(self):
        _, sections = self.built_sections()
        items = sections["evidence"]["items"]
        self.assertGreaterEqual(len(items), 5)
        self.assertLessEqual(len(items), 7)
        self.assertEqual(
            [item["reference"] for item in items],
            [f"E{index}" for index in range(1, len(items) + 1)],
        )
        self.assertTrue(all(item.get("question_text") for item in items))

    def test_public_sections_do_not_expose_internal_question_ids(self):
        _, sections = self.built_sections()
        text = json.dumps(sections, ensure_ascii=False)
        self.assertIsNone(
            re.search(
                r"\b(?:rel|trust|ver|del|agency|emot|disc|thought|soc)_q\d+\b",
                text,
                flags=re.IGNORECASE,
            )
        )

    def test_pattern_synthesis_contains_one_narrative_and_three_lenses(self):
        _, sections = self.built_sections()
        pattern = sections["pattern_synthesis"]
        self.assertTrue(pattern["narrative"])
        self.assertEqual(len(pattern["human_capital_lens"]), 3)
        self.assertTrue(pattern["human_capital_note"])

    def test_dimension_reference_contains_nine_concise_entries(self):
        _, sections = self.built_sections()
        reference = sections["dimension_reference"]
        self.assertEqual(len(reference["items"]), 9)
        self.assertTrue(
            all(item.get("reference_text") for item in reference["items"])
        )

    def test_baseline_contains_required_measurement_package(self):
        _, sections = self.built_sections()
        baseline = sections["baseline"]
        self.assertEqual(len(baseline["dimension_positions"]), 9)
        self.assertEqual(len(baseline["defining_signals"]), 3)
        self.assertEqual(len(baseline["comparison_priorities"]), 3)
        self.assertTrue(baseline["return_question"].endswith("?"))
        self.assertTrue(baseline["baseline_closing"])
        self.assertEqual(baseline["recommended_reassessment_window"], "6–12 months")

    def test_closing_mirrors_signature_and_baseline(self):
        _, sections = self.built_sections()
        closing = sections["closing"]
        self.assertEqual(
            closing["signature_sentence"],
            sections["signature"]["signature_sentence"],
        )
        self.assertEqual(
            closing["return_question"],
            sections["baseline"]["return_question"],
        )
        self.assertEqual(closing["footer_disclaimer"], SHORT_PERSONAL_INSIGHT_DISCLAIMER)

    def test_appendix_contains_complete_question_profile(self):
        _, sections = self.built_sections()
        appendix = sections["appendix_questions"]
        self.assertEqual(appendix["question_count"], 39)
        self.assertEqual(len(appendix["groups"]), 9)
        self.assertEqual(
            sum(len(group["questions"]) for group in appendix["groups"]),
            39,
        )

    def test_methodology_contains_benchmark_and_self_report_boundaries(self):
        _, sections = self.built_sections()
        methodology = sections["appendix_methodology"]
        self.assertEqual(methodology["benchmark"]["study_count"], 21)
        self.assertTrue(methodology["percentile_explanation"])
        self.assertTrue(methodology["cohort_rule"])
        self.assertTrue(methodology["self_report_note"])
        self.assertEqual(methodology["important_information"], FULL_PERSONAL_INSIGHT_DISCLAIMER)

    def test_sections_are_complete_without_narrative_api_step(self):
        _, sections = self.built_sections(narratives=False)
        self.assertTrue(sections["signature"]["signature_sentence"])
        self.assertTrue(sections["distinctive_pattern"]["narrative"])
        self.assertTrue(sections["pattern_synthesis"]["narrative"])
        self.assertEqual(len(sections["pattern_synthesis"]["human_capital_lens"]), 3)
        self.assertTrue(sections["baseline"]["return_question"])

    def test_build_sections_does_not_mutate_report_data(self):
        report = add_claude_narratives(build_fixture_report(), api_key=None)
        original = copy.deepcopy(report)
        build_sections(report)
        self.assertEqual(report, original)

    def test_contract_rejects_damaged_position_section(self):
        _, sections = self.built_sections()
        damaged = copy.deepcopy(sections)
        damaged["position"]["items"] = damaged["position"]["items"][:-1]
        with self.assertRaisesRegex(ValueError, "9 dimensions"):
            assert_sections_contract(damaged)

    def test_source_contains_no_report_generation_labels_or_obsolete_architecture(self):
        source = Path(__file__).with_name("report_sections.py").read_text(encoding="utf-8").lower()
        self.assertIsNone(re.search(r"hci_report_data_[a-z]\d", source))
        for prohibited in (
            "behaviour story",
            "dimension deep dives",
            "looking forward",
            "closing reflection",
        ):
            self.assertNotIn(prohibited, source)


if __name__ == "__main__":
    unittest.main()
