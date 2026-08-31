from __future__ import annotations

import unittest

from tools.vbdlis_excel_builder.core.household_parser import HouseholdParser
from tools.vbdlis_excel_builder.core.input_policy import apply_input_policy
from tools.vbdlis_excel_builder.models import MappingProfile, Severity


class InputPolicyTests(unittest.TestCase):
    def setUp(self):
        self.profile = MappingProfile(source_mapping={"household_stt": "A", "person_name": "B",
            "cccd": "C", "birth_date": "D", "sheet_number": "E", "parcel_number": "F", "area": "G"})

    def head(self, row=2, stt=1):
        return {"_row": row, "A": stt, "B": "Nguyễn Văn A", "C": "031080001234", "E": 10, "F": 300, "G": 100}

    def run_policy(self, rows):
        households, issues, stats = HouseholdParser().parse(rows, self.profile)
        kept, issues, stats = apply_input_policy(households, issues, self.profile)
        return households, kept, issues, stats

    def test_missing_cccd_discards_whole_household_and_keeps_next(self):
        source, kept, issues, stats = self.run_policy([
            self.head(), {"_row": 3, "B": "Trần Thị B"}, self.head(4, 2)])
        self.assertEqual([h.source_row for h in kept], [4])
        self.assertEqual(stats["households_skipped"], 1)
        self.assertEqual(stats["people_skipped"], 2)
        self.assertEqual(len(source[0].people), 2)
        self.assertFalse(any(i.severity == Severity.ERROR for i in issues))
        missing = next(i for i in issues if i.code == "MISSING_CCCD")
        self.assertEqual(missing.disposition, "household_skipped")

    def test_missing_person_name_with_identity_discards_household(self):
        source, kept, issues, _ = self.run_policy([self.head(), {"_row": 3, "C": "031185001235"}])
        self.assertEqual(kept, [])
        self.assertIn("MISSING_PERSON_NAME", [i.code for i in issues])
        self.assertIn("HOUSEHOLD_SKIPPED", [i.code for i in issues])

    def test_invalid_cccd_discards_only_person_and_keeps_original_roles(self):
        self.profile.invalid_cccd_action = "error"  # Automatic exclusion overrides strict CCCD setting.
        head = self.head()
        head["C"] = "bad"
        source, kept, issues, stats = self.run_policy([head, {"_row": 3, "B": "Trần Thị B", "C": "031185001235"}])
        self.assertEqual([p.source_row for p in kept[0].people], [3])
        self.assertFalse(kept[0].people[0].is_head)
        self.assertEqual(stats["people_skipped_individually"], 1)
        self.assertIn("HOUSEHOLD_HEAD_SKIPPED", [i.code for i in issues])
        self.assertFalse(any(i.severity == Severity.ERROR for i in issues))
        self.assertEqual(len(source[0].people), 2)

    def test_all_people_invalid_discards_household(self):
        head = self.head()
        head["C"] = "bad"
        _, kept, issues, stats = self.run_policy([head])
        self.assertEqual(kept, [])
        self.assertEqual(stats["households_skipped"], 1)
        self.assertEqual(stats["parcels_skipped"], 1)
        self.assertTrue(any(i.code == "HOUSEHOLD_SKIPPED" for i in issues))

    def test_one_incomplete_parcel_discards_entire_household(self):
        for missing in ("E", "F", "G"):
            with self.subTest(missing=missing):
                parcel = {"_row": 3, "E": 20, "F": 400, "G": 200}
                parcel[missing] = None
                _, kept, issues, stats = self.run_policy([self.head(), parcel, self.head(4, 2)])
                self.assertEqual([h.source_row for h in kept], [4])
                self.assertEqual(stats["households_skipped"], 1)
                self.assertIn("INVALID_PARCEL", [i.code for i in issues])

    def test_continuation_rows_and_totals_do_not_trigger_false_exclusions(self):
        _, kept, issues, stats = self.run_policy([
            self.head(), {"_row": 3, "E": 20, "F": 400, "G": 200},
            {"_row": 4, "B": "Trần Thị B", "C": "031185001235"},
            {"_row": 5, "B": "Tổng DT", "G": 300}])
        self.assertEqual((len(kept), len(kept[0].people), len(kept[0].parcels)), (1, 2, 2))
        self.assertEqual(stats["people_skipped"], 0)
        self.assertEqual([i.code for i in issues], ["SUMMARY_ROW_SKIPPED"])

    def test_household_without_any_parcel_is_explicitly_excluded(self):
        _, kept, issues, stats = self.run_policy([{"_row": 2, "A": 1, "B": "Nguyễn Văn A", "C": "031080001234"}])
        self.assertEqual(kept, [])
        self.assertEqual(stats["people_skipped"], 1)
        self.assertIn("HOUSEHOLD_SKIPPED", [i.code for i in issues])

    def test_repeated_stt_does_not_exclude_unrelated_household(self):
        other = self.head(4, 1)
        other["C"] = ""
        _, kept, _, stats = self.run_policy([self.head(), other])
        self.assertEqual([h.source_row for h in kept], [2])
        self.assertEqual(stats["households_skipped"], 1)

    def test_strict_mode_retains_original_errors(self):
        self.profile.skip_invalid_data = False
        head = self.head()
        head["C"] = None
        _, kept, issues, stats = self.run_policy([head])
        self.assertEqual(len(kept), 1)
        self.assertTrue(any(i.code == "MISSING_CCCD" and i.severity == Severity.ERROR for i in issues))
        self.assertEqual(stats, {})


if __name__ == "__main__":
    unittest.main()
