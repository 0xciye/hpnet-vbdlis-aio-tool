from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.vbdlis_excel_builder.models import MappingProfile
from tools.vbdlis_excel_builder.core.profile_store import ProfileStore
from tools.vbdlis_excel_builder.utils.dates import normalize_birth_date
from tools.vbdlis_excel_builder.utils.paths import ensure_xlsx_name, unique_output_path
from tools.vbdlis_excel_builder.utils.text import normalize_cccd, normalize_name, safe_template_replace


class UtilityTests(unittest.TestCase):
    def test_text_and_date_normalization(self):
        self.assertEqual(normalize_name(" Nguyễn   văn an "), "NGUYỄN VĂN AN")
        self.assertEqual(normalize_cccd("031204001234"), ("031204001234", True))
        self.assertEqual(normalize_birth_date(1985), "1985")
        self.assertEqual(normalize_birth_date("1985"), "1985")

    def test_safe_template_only_accepts_whitelist(self):
        value = safe_template_replace(
            "{PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}",
            {"PREFIX": "P", "MA_XA": 1, "SO_TO": 2, "SO_THUA": 3},
        )
        self.assertEqual(value, "P_1_2_3")
        with self.assertRaises(ValueError):
            safe_template_replace("{__import__}", {})

    def test_output_name_and_profile_roundtrip(self):
        self.assertEqual(ensure_xlsx_name("abc"), "abc.xlsx")
        with self.assertRaises(ValueError):
            ensure_xlsx_name("a:b.xlsx")
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "abc.xlsx"
            first.touch()
            self.assertEqual(unique_output_path(directory, "abc.xlsx").name, "abc_1.xlsx")
            store = ProfileStore(directory)
            original = MappingProfile(profile_name="X", commune_code="10930")
            exported = Path(directory) / "profile.json"
            store.export_profile(original, exported)
            restored = store.import_profile(exported)
            self.assertEqual(restored.commune_code, "10930")


if __name__ == "__main__":
    unittest.main()
