from __future__ import annotations

import unittest
import unicodedata

from tools.vbdlis_excel_builder.core.household_parser import HouseholdParser
from tools.vbdlis_excel_builder.core.transform_engine import TransformEngine
from tools.vbdlis_excel_builder.models import Severity
from tools.vbdlis_excel_builder.tests.test_transform_engine import profile, schemas
from tools.vbdlis_excel_builder.utils.text import is_summary_label


class SummaryRowTests(unittest.TestCase):
    def head(self, row=2, stt=1, name="Nguyễn Văn A"):
        return {"_row": row, "A": stt, "B": name, "C": "031080001234",
                "F": 10, "G": 300, "H": 100}

    def test_label_variants_and_real_names(self):
        for label in ("TỔNG DT", "  tổng\u00a0DT: ", "Tong DT", "TỔNG D.T.",
                      "Tổng diện tích", "TONG DIEN TICH", "Tổng DT (m²)",
                      "Tổng cộng", "Cộng diện tích", unicodedata.normalize("NFD", "TỔNG DT")):
            with self.subTest(label=label):
                self.assertTrue(is_summary_label(label))
        for name in (None, "", "Tống Công", "Nguyễn Văn Tổng", "Tổng Văn An",
                     "Lê Thị Cộng", "Tổng DT Nguyễn Văn A", "Tổng", "Cộng"):
            with self.subTest(name=name):
                self.assertFalse(is_summary_label(name))

    def test_subtotal_does_not_create_person_or_parcel(self):
        rows = [self.head(),
                {"_row": 3, "F": 20, "G": 400, "H": 200},
                # Fully populated parcel columns still represent a total row.
                {"_row": 4, "B": "TỔNG DT", "F": 999, "G": 999, "H": 300},
                self.head(row=5, stt=2, name="Trần Thị B"),
                {"_row": 6, "B": "TỔNG DT", "H": 100}]
        households, issues, stats = HouseholdParser().parse(rows, profile())
        self.assertEqual((stats["households"], stats["people"], stats["parcels"]), (2, 2, 3))
        self.assertEqual(stats["summary_rows_skipped"], 2)
        skipped = [i for i in issues if i.code == "SUMMARY_ROW_SKIPPED"]
        self.assertEqual([i.source_row for i in skipped], [4, 6])
        self.assertTrue(all(i.severity == Severity.INFO for i in skipped))
        self.assertFalse(any(i.severity == Severity.ERROR for i in issues))
        output, _, _ = TransformEngine().transform(households, schemas(), profile())
        self.assertEqual([r["H"] for r in output], ["NGUYỄN VĂN A", "NGUYỄN VĂN A", "TRẦN THỊ B"])
        self.assertEqual([r["A"] for r in output], [1, 2, 3])
        self.assertTrue(all(r["N"] == "Chủ hộ" for r in output))

    def test_skip_before_household_creation_or_orphan_check(self):
        for summary in ({"B": "TỔNG DT"}, {"A": "Tổng cộng"}, {"A": 999, "B": "TỔNG DT"}):
            with self.subTest(summary=summary):
                rows = [{"_row": 2, **summary, "H": 500}, self.head(row=3)]
                households, issues, stats = HouseholdParser().parse(rows, profile())
                self.assertEqual(len(households), 1)
                self.assertEqual(households[0].source_row, 3)
                self.assertEqual(stats["summary_rows_skipped"], 1)
                self.assertEqual([i.code for i in issues], ["SUMMARY_ROW_SKIPPED"])

    def test_subtotal_does_not_split_current_household(self):
        rows = [self.head(), {"_row": 3, "A": "Tổng cộng", "H": 100},
                {"_row": 4, "B": "Trần Thị B", "C": "031185001235"},
                {"_row": 5, "F": 20, "G": 400, "H": 200}]
        households, issues, stats = HouseholdParser().parse(rows, profile())
        self.assertEqual((stats["households"], stats["people"], stats["parcels"]), (1, 2, 2))
        self.assertEqual([p.is_head for p in households[0].people], [True, False])
        self.assertFalse(any(i.severity == Severity.ERROR for i in issues))

    def test_missing_identity_on_real_person_is_still_an_error(self):
        rows = [self.head(), {"_row": 3, "B": "Tống Công"},
                {"_row": 4, "B": "Nguyễn Văn Tổng"}]
        households, issues, stats = HouseholdParser().parse(rows, profile())
        self.assertEqual(stats["people"], 3)
        self.assertEqual(stats["summary_rows_skipped"], 0)
        self.assertEqual([i.source_row for i in issues if i.code == "MISSING_CCCD"], [3, 4])

    def test_identity_information_prevents_automatic_skip(self):
        for identity in ({"C": "031080001234"}, {"C": "invalid"}, {"D": "1980"}):
            with self.subTest(identity=identity):
                households, issues, stats = HouseholdParser().parse(
                    [self.head(), {"_row": 3, "B": "Tổng cộng", **identity}], profile())
                self.assertEqual(stats["people"], 2)
                self.assertEqual(stats["summary_rows_skipped"], 0)

    def test_do_not_search_unrelated_columns_or_discard_named_people(self):
        rows = [self.head(), {"_row": 3, "A": "Tổng cộng", "B": "Nguyễn Văn Tổng",
                             "F": 20, "G": 400, "H": 200, "I": "TỔNG DT"}]
        households, issues, stats = HouseholdParser().parse(rows, profile())
        self.assertEqual(stats["people"], 2)
        self.assertEqual(stats["summary_rows_skipped"], 0)
        self.assertIn("MISSING_CCCD", [i.code for i in issues])

    def test_non_household_mode_and_summary_only_input(self):
        p = profile()
        p.household_mode = False
        rows = [self.head(), {"_row": 3, "B": "TỔNG DT", "H": 100}]
        _, issues, stats = HouseholdParser().parse(rows, p)
        self.assertEqual((stats["households"], stats["people"]), (1, 1))
        self.assertEqual(stats["summary_rows_skipped"], 1)
        households, issues, stats = HouseholdParser().parse(rows[1:], p)
        self.assertEqual(households, [])
        self.assertEqual([i.code for i in issues], ["SUMMARY_ROW_SKIPPED"])


if __name__ == "__main__":
    unittest.main()
