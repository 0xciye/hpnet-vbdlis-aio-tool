from __future__ import annotations

import unittest
from pathlib import Path

from tools.vbdlis_excel_builder.core.household_parser import HouseholdParser
from tools.vbdlis_excel_builder.core.template_schema_reader import TemplateSchemaReader
from tools.vbdlis_excel_builder.core.transform_engine import TransformEngine
from tools.vbdlis_excel_builder.core.validator import Validator
from tools.vbdlis_excel_builder.models import MappingProfile, Severity


PROJECT = Path(__file__).resolve().parents[1]


def profile() -> MappingProfile:
    return MappingProfile(
        commune_code="10930",
        address="thôn Test, xã Test, Thành phố Hải Phòng",
        source_mapping={
            "household_stt": "A",
            "person_name": "B",
            "cccd": "C",
            "birth_date": "D",
            "gender": "E",
            "sheet_number": "F",
            "parcel_number": "G",
            "area": "H",
            "land_location": "I",
            "gcn_issue_number": "J",
            "gcn_issue_date": "K",
            "gcn_registry_number": "L",
            "gcn_type": "M",
        },
    )


def schemas():
    reader = TemplateSchemaReader(PROJECT / "config" / "template_schema.json")
    return reader.read(PROJECT / "resources" / "BieuMauThuThapThongTinGiayChungNhan.xlsx")[2]


class TransformTests(unittest.TestCase):
    def test_gender_uses_only_cccd_marker_even_with_source_gender(self):
        p = profile()
        fields = schemas()
        cases = [(f"001{marker}90000001", {"0": "Nam", "1": "Nữ"}.get(marker, ""))
                 for marker in "0123456789"]
        cases += [("", ""), ("001", ""), ("00109000001", ""),
                  ("0010900000012", ""), ("0010A0000001", ""),
                  ("００１０９００００００１", "")]
        for cccd, expected in cases:
            with self.subTest(cccd=cccd):
                rows = [{"_row": 2, "A": 1, "B": "NGƯỜI KIỂM THỬ", "C": cccd,
                         "E": "Nữ" if expected == "Nam" else "Nam", "F": 1, "G": 2, "H": 3}]
                households, _, _ = HouseholdParser().parse(rows, p)
                output, _, _ = TransformEngine().transform(households, fields, p)
                self.assertEqual(households[0].people[0].gender, expected)
                self.assertEqual(output[0]["K"], expected)

    def test_legacy_gender_settings_cannot_override_cccd_rule(self):
        fields = schemas()
        gender_field = next(s for s in fields if s.transformer == "gender")
        for legacy_mode in ("source", "source_then_cccd", "fixed"):
            for marker, expected in (("0", "Nam"), ("1", "Nữ"), ("2", "")):
                for field_mode in ("fixed", "source_column", "conditional", "blank"):
                    with self.subTest(legacy_mode=legacy_mode, marker=marker, field_mode=field_mode):
                        p = profile()
                        p.gender_mode = legacy_mode
                        p.field_rules[gender_field.field_id] = {
                            "mode": field_mode, "source": "gender", "default": "Nam", "fallback": "Nữ",
                        }
                        rows = [{"_row": 2, "A": 1, "B": "NGƯỜI KIỂM THỬ",
                                 "C": f"001{marker}90000001", "E": "Nữ", "F": 1, "G": 2, "H": 3}]
                        households, _, _ = HouseholdParser().parse(rows, p)
                        output, _, _ = TransformEngine().transform(households, fields, p)
                        self.assertEqual(output[0]["K"], expected)
        self.assertEqual(MappingProfile.from_dict({"gender_mode": "source_then_cccd"}).gender_mode, "cccd")

    def test_two_people_times_two_parcels_and_item49(self):
        rows = [
            {"_row": 2, "A": 1, "B": "Nguyễn  Văn a", "C": "031204001234", "D": "1980", "F": 10, "G": 300, "H": 100, "I": "Xứ Một"},
            {"_row": 3, "A": None, "B": "Trần Thị b", "C": "031205001235", "D": "01/02/1985", "F": 40, "G": 500, "H": 200, "I": "Xứ Hai"},
        ]
        households, issues, base = HouseholdParser().parse(rows, profile())
        output, transform_issues, stats = TransformEngine().transform(households, schemas(), profile())
        self.assertEqual(base["households"], 1)
        self.assertEqual(base["people"], 2)
        self.assertEqual(base["parcels"], 2)
        self.assertEqual(stats["output_rows"], 4)
        self.assertEqual([row["A"] for row in output], [1, 2, 3, 4])
        self.assertEqual([row["H"] for row in output], ["NGUYỄN VĂN A", "TRẦN THỊ B", "NGUYỄN VĂN A", "TRẦN THỊ B"])
        self.assertEqual([row["N"] for row in output], ["Chủ hộ", "Thành viên hộ gia đình"] * 2)
        self.assertEqual(
            output[0]["AX"],
            "CHUACOGIAY_10930_10_300-TBXN.pdf, CHUACOGIAY_10930_10_300-DDK.pdf",
        )
        self.assertFalse([issue for issue in issues + transform_issues if issue.severity == Severity.ERROR])

    def test_missing_location_falls_back_to_address(self):
        p = profile()
        rows = [{"_row": 2, "A": 1, "B": "A", "C": "031204001234", "F": 1, "G": 2, "H": 3, "I": "   "}]
        households, _, _ = HouseholdParser().parse(rows, p)
        output, issues, stats = TransformEngine().transform(households, schemas(), p)
        self.assertEqual(output[0]["X"], p.address)
        self.assertEqual(stats["location_fallbacks"], 1)
        self.assertIn("LOCATION_FALLBACK", {issue.code for issue in issues})

    def test_four_people_times_three_parcels(self):
        p = profile()
        rows = [
            {"_row": 2, "A": 1, "B": "A", "C": "031204001234", "F": 1, "G": 10, "H": 100},
            {"_row": 3, "A": None, "B": "B", "C": "031204001235", "F": 2, "G": 20, "H": 200},
            {"_row": 4, "A": None, "B": "C", "C": "031204001236", "F": 3, "G": 30, "H": 300},
            {"_row": 5, "A": None, "B": "D", "C": "031204001237"},
        ]
        households, _, _ = HouseholdParser().parse(rows, p)
        output, _, stats = TransformEngine().transform(households, schemas(), p)
        self.assertEqual(stats["output_rows"], 12)
        self.assertEqual([row["A"] for row in output], list(range(1, 13)))

    def test_location_blank_mode_and_invalid_parcel(self):
        p = profile()
        p.location_fallback = "blank"
        rows = [
            {"_row": 2, "A": 1, "B": "A", "C": "031204001234", "F": 1, "G": 2, "H": 3},
            {"_row": 3, "A": None, "F": 4, "G": None, "H": 5},
        ]
        households, parse_issues, _ = HouseholdParser().parse(rows, p)
        output, transform_issues, stats = TransformEngine().transform(households, schemas(), p)
        self.assertEqual(stats["output_rows"], 1)
        self.assertEqual(output[0]["X"], "")
        self.assertIn("INVALID_PARCEL", {issue.code for issue in parse_issues})
        self.assertIn("MISSING_LOCATION", {issue.code for issue in transform_issues})

    def test_cccd_leading_zero_and_nonstandard_value_is_kept_with_warning(self):
        p = profile()
        p.invalid_cccd_action = "keep"  # Profile cũ cũng không được hạ CCCD xuống cảnh báo.
        rows = [
            {"_row": 2, "A": 1, "B": "A", "C": "031204001234", "F": 1, "G": 2, "H": 3},
            {"_row": 3, "A": None, "B": "B", "C": "123", "F": None, "G": None, "H": None},
        ]
        households, issues, _ = HouseholdParser().parse(rows, p)
        output, _, _ = TransformEngine().transform(households, schemas(), p)
        validation = Validator().validate_output(output, schemas(), p)
        self.assertEqual(output[0]["I"], "031204001234")
        self.assertEqual(output[1]["I"], "123")
        self.assertEqual(output[1]["BA"], "Căn cước công dân")
        self.assertIn("INVALID_CCCD", {issue.code for issue in issues})
        self.assertTrue(any(issue.code == "INVALID_CCCD" and issue.severity == Severity.WARNING for issue in issues))
        self.assertFalse([issue for issue in validation if issue.code == "MISSING_REQUIRED_CCCD_OUTPUT"])

    def test_missing_cccd_is_blocking_error(self):
        p = profile()
        rows = [{"_row": 2, "A": 1, "B": "A", "C": "", "F": 1, "G": 2, "H": 3}]
        households, issues, _ = HouseholdParser().parse(rows, p)
        output, _, _ = TransformEngine().transform(households, schemas(), p)
        validation = Validator().validate_output(output, schemas(), p)
        self.assertIn("MISSING_CCCD", {issue.code for issue in issues})
        self.assertTrue(any(issue.code == "MISSING_CCCD" and issue.severity == Severity.ERROR for issue in issues))
        self.assertIn("MISSING_REQUIRED_CCCD_OUTPUT", {issue.code for issue in validation})

    def test_cccd_mapping_is_required(self):
        p = profile()
        p.source_mapping.pop("cccd")
        issues = Validator().validate_profile(p)
        self.assertTrue(
            any(
                issue.code == "MISSING_MAPPING"
                and issue.severity == Severity.ERROR
                and "CCCD" in issue.message
                for issue in issues
            )
        )

    def test_mixed_gcn_is_allowed(self):
        p = profile()
        rows = [
            {"_row": 2, "A": 1, "B": "A", "C": "031204001234", "F": 1, "G": 2, "H": 3},
            {"_row": 3, "A": None, "B": None, "F": 4, "G": 5, "H": 6, "J": "CS123", "K": "20/08/2026", "L": "VAO123", "M": "11"},
        ]
        households, parse_issues, _ = HouseholdParser().parse(rows, p)
        output, transform_issues, stats = TransformEngine().transform(households, schemas(), p)
        self.assertEqual(stats["with_gcn"], 1)
        self.assertEqual(stats["without_gcn"], 1)
        self.assertEqual(output[0]["D"], "")
        self.assertEqual(output[1]["C"], "CS123")
        self.assertEqual(output[1]["D"], "20/08/2026")
        self.assertEqual(output[1]["E"], "VAO123")
        self.assertFalse([issue for issue in parse_issues + transform_issues if issue.code == "EXPECTED_GCN_MISSING"])

    def test_duplicate_and_gcn_conflict(self):
        p = profile()
        rows = [
            {"_row": 2, "A": 1, "B": "A", "C": "031204001234", "F": 1, "G": 2, "H": 3, "I": "X", "J": "GCN-A"},
            {"_row": 3, "A": None, "B": None, "F": 1, "G": 2, "H": 3, "I": "X", "J": "GCN-A"},
            {"_row": 4, "A": None, "B": None, "F": 1, "G": 2, "H": 3, "I": "X", "J": "GCN-B"},
        ]
        households, issues, stats = HouseholdParser().parse(rows, p)
        self.assertEqual(stats["duplicates"], 1)
        self.assertEqual(len(households[0].parcels), 2)
        self.assertIn("GCN_CONFLICT", {issue.code for issue in issues})
        self.assertTrue(any(issue.severity == Severity.ERROR for issue in issues if issue.code == "GCN_CONFLICT"))

    def test_missing_gcn_mapping_is_not_error(self):
        p = profile()
        for key in list(p.source_mapping):
            if key.startswith("gcn_"):
                p.source_mapping.pop(key)
        rows = [{"_row": 2, "A": 1, "B": "A", "C": "031204001234", "F": 1, "G": 2, "H": 3}]
        households, issues, _ = HouseholdParser().parse(rows, p)
        output, transform_issues, _ = TransformEngine().transform(households, schemas(), p)
        validation = Validator().validate_output(output, schemas(), p)
        self.assertFalse([issue for issue in issues + transform_issues + validation if issue.severity == Severity.ERROR])


if __name__ == "__main__":
    unittest.main()
