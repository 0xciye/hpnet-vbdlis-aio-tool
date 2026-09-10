from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from tools.vbdlis_excel_builder.core.diagnostic_logger import DiagnosticContext, DiagnosticFailure, DiagnosticLogger, GUIDANCE
from tools.vbdlis_excel_builder.core.service import BuilderService
from tools.vbdlis_excel_builder.models import MappingProfile, Severity, ValidationIssue


PROJECT = Path(__file__).resolve().parents[1]


class DiagnosticLoggerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "nguon.xlsx"
        self.profile = MappingProfile(commune_code="10930", address="Địa chỉ thử nghiệm", skip_invalid_data=False,
            export_audit_report=False, source_mapping={"household_stt": "A", "person_name": "B",
            "cccd": "C", "birth_date": "D", "sheet_number": "E", "parcel_number": "F",
            "area": "G", "land_location": "H", "gcn_issue_number": "I"})
        self.service = BuilderService(PROJECT / "resources/BieuMauThuThapThongTinGiayChungNhan.xlsx",
                                      PROJECT / "config/template_schema.json", self.root / "logs")

    def source_rows(self, rows):
        wb = Workbook()
        wb.active.title = "Dữ liệu"
        wb.active.append(["STT", "Tên hộ", "CCCD", "Ngày sinh", "Số tờ", "Số thửa", "Diện tích", "Xứ đồng", "Số GCN"])
        for row in rows:
            wb.active.append(row)
        wb.save(self.source)
        wb.close()

    def process(self):
        return self.service.process(self.source, "Dữ liệu", 1, self.profile)

    def text(self, files):
        self.assertEqual(len(files.paths), 2)
        self.assertFalse(files.error)
        return next(p for p in files.paths if p.suffix == ".txt").read_text(encoding="utf-8-sig")

    def valid_row(self):
        return [1, "Nguyễn Văn A", "031080001234", "1980", 10, 300, 100, "Xứ thử"]

    def test_failed_validation_saves_full_friendly_report_without_export(self):
        self.source_rows([self.valid_row(), [None, "Trần Thị B"],
                          [None, None, None, None, 20, 400, None, "Xứ hai"],
                          [None, "Tổng DT", None, None, None, None, 100],
                          [2, "Nguyễn Văn C", "031080001235"]])
        original = self.source.read_bytes()
        result = self.process()
        text = self.text(result.diagnostic_files)
        self.assertFalse(result.can_export)
        for item in ("CHƯA THỂ XUẤT", "Ô C3 — CCCD: [ĐỂ TRỐNG]", "Ô G4 — Diện tích: [ĐỂ TRỐNG]",
                     "Hộ STT: 2", "NGUYỄN VĂN C (dòng 6)", "Ô E6", "Ô F6", "Ô G6",
                     "Không sinh dòng kết quả", "Đã bỏ qua dòng tổng hợp", "Cách xử lý:", "Ctrl+G"):
            self.assertIn(item, text)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(list(self.root.glob("*_bao_cao_kiem_tra.xlsx")), [])

    def test_all_required_output_errors_saved_beyond_old_500_limit(self):
        self.profile.commune_code = ""
        self.profile.address = ""
        next(s for s in self.service.schemas if s.column == "X").required = True
        self.source_rows([[1, "Nguyễn Văn A", "031080001234", "1980", 10, 300, 100]]
                         + [[None, None, None, None, 10, p, 100] for p in range(301, 602)])
        result = self.process()
        missing = [i for i in result.issues if i.code == "MISSING_REQUIRED_OUTPUT"]
        self.assertGreater(len(missing), 500)
        text = self.text(result.diagnostic_files)
        self.assertEqual(text.count("Mã tra cứu cho người hỗ trợ: MISSING_REQUIRED_OUTPUT\n"), len(missing))
        self.assertNotIn("TRUNCATED", text)
        self.assertIn("STT kết quả dự kiến: 302", text)

    def test_output_error_uses_parcel_source_row_not_person_source_row(self):
        self.source_rows([[1, "Nguyễn Văn A", "031080001234", "1980"],
                          [None, None, None, None, 10, 300, 100]])
        self.profile.address = ""
        next(s for s in self.service.schemas if s.column == "X").required = True
        result = self.process()
        records = DiagnosticLogger.entries(result.diagnostic_context, result.issues)
        location = next(r for r in records if r.code == "MISSING_REQUIRED_OUTPUT" and "cột X " in r.location)
        self.assertIn("dòng nguồn: 3", location.location)
        self.assertTrue(any("Ô H3" in v for v in location.evidence))
        self.assertFalse(any("Ô H2" in v for v in location.evidence))

    def test_alias_mapping_and_html_data_are_safe(self):
        malicious = '</script><script>alert("x")</script>'
        self.profile.source_mapping["cccd"] = "CCCD"
        row = self.valid_row()
        row[1], row[2] = malicious, "bad-id"
        self.source_rows([row])
        result = self.process()
        text = self.text(result.diagnostic_files)
        self.assertIn("Ô C2 — CCCD: bad-id", text)
        html = result.diagnostic_files.paths[0].read_text(encoding="utf-8")
        self.assertNotIn(malicious, html)
        self.assertNotIn("</SCRIPT><SCRIPT>", html)
        self.assertIn("&lt;", html)
        self.assertEqual(html.count("<script>"), 1)

    def test_each_run_is_independent_and_snapshots_profile(self):
        self.source_rows([self.valid_row()])
        first, second = self.process(), self.process()
        self.assertTrue(set(first.diagnostic_files.paths).isdisjoint(second.diagnostic_files.paths))
        self.profile.commune_code = "CHANGED"
        self.assertEqual(first.diagnostic_context.profile.commune_code, "10930")
        self.assertIn("CÓ THỂ XUẤT", self.text(first.diagnostic_files))

    def test_successful_export_report_identifies_saved_output(self):
        self.source_rows([self.valid_row()])
        result = self.process()
        before = list(result.diagnostic_files.paths)
        output, audit, verification = self.service.export(result, self.profile, self.root, "ket_qua.xlsx")
        self.assertTrue(verification["pass"])
        self.assertIsNone(audit)  # Automatic diagnostics do not depend on the audit checkbox.
        self.assertNotEqual(before, result.diagnostic_files.paths)
        text = self.text(result.diagnostic_files)
        self.assertIn("ĐÃ XUẤT VÀ KIỂM TRA FILE KẾT QUẢ", text)
        self.assertIn(str(output), text)

    def test_source_read_failure_saves_friendly_report(self):
        with self.assertLogs(level="ERROR"):
            with self.assertRaises(DiagnosticFailure) as raised:
                self.process()
        text = self.text(raised.exception.diagnostic_files)
        self.assertIn("Không tìm thấy file", text)
        self.assertIn("nguon.xlsx", text)
        self.assertIn("FileNotFoundError", text)

    def test_export_permission_failure_saves_report_and_preserves_check_issues(self):
        row = self.valid_row()
        row[2] = "nonstandard"
        self.source_rows([row])
        result = self.process()
        with patch.object(self.service.writer, "write", side_effect=PermissionError("File is open")):
            with self.assertLogs(level="ERROR"):
                with self.assertRaises(DiagnosticFailure) as raised:
                    self.service.export(result, self.profile, self.root, "blocked.xlsx")
        text = self.text(raised.exception.diagnostic_files)
        self.assertIn("Windows không cho phép đọc hoặc ghi", text)
        self.assertIn("Đóng file đang mở trong Excel", text)
        self.assertIn("INVALID_CCCD", text)
        self.assertNotIn("ĐÃ XUẤT VÀ KIỂM TRA FILE KẾT QUẢ", text)

    def test_empty_workbook_has_explicit_error_and_saved_log(self):
        self.source_rows([])
        result = self.process()
        self.assertFalse(result.can_export)
        self.assertIn("NO_OUTPUT_ROWS", [i.code for i in result.issues])
        self.assertIn("Chưa có dòng kết quả nào", self.text(result.diagnostic_files))

    def test_log_directory_failure_is_visible_and_does_not_lose_result(self):
        self.source_rows([self.valid_row()])
        not_directory = self.root / "occupied.txt"
        not_directory.write_text("do not replace", encoding="utf-8")
        self.service.diagnostic_logger.directory = not_directory
        with self.assertLogs(level="ERROR"):
            result = self.process()
        self.assertTrue(result.can_export)
        self.assertTrue(result.diagnostic_files.error)
        self.assertFalse(result.diagnostic_files.paths)
        self.assertEqual(not_directory.read_text(encoding="utf-8"), "do not replace")

    def test_html_failure_keeps_text_report_accessible(self):
        original_open = Path.open
        def fail_html(path, *args, **kwargs):
            if path.suffix == ".html":
                raise PermissionError("HTML denied")
            return original_open(path, *args, **kwargs)
        with patch.object(Path, "open", fail_html):
            files = self.service.diagnostic_logger.write(DiagnosticContext(), [], {})
        self.assertTrue(files.error)
        self.assertEqual([p.suffix for p in files.paths], [".txt"])
        self.assertTrue(files.paths[0].is_file())

    def test_every_current_validation_code_has_plain_language_guidance(self):
        import ast
        codes = set()
        for relative in ("core/household_parser.py", "core/validator.py", "core/transform_engine.py", "core/service.py", "core/input_policy.py"):
            for node in ast.walk(ast.parse((PROJECT / relative).read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ValidationIssue":
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                        codes.add(node.args[1].value)
        self.assertTrue(codes)
        self.assertEqual(codes - GUIDANCE.keys(), set())

    def test_automatic_exclusions_are_logged_and_remaining_people_export(self):
        self.profile.skip_invalid_data = True
        second = self.valid_row()
        second[0], second[1] = 2, "Nguyễn Văn C"
        third = self.valid_row()
        third[0], third[1] = 3, "Nguyễn Văn D"
        self.source_rows([self.valid_row(), [None, "Trần Thị B", "invalid"],
                          second, [None, "Trần Thị C"], third])
        result = self.process()
        self.assertTrue(result.can_export)
        self.assertEqual(result.stats["households_skipped"], 0)
        self.assertEqual(result.stats["people_skipped_individually"], 2)
        self.assertEqual(result.stats["people_skipped"], 2)
        self.assertEqual([r["H"] for r in result.rows], ["NGUYỄN VĂN A", "NGUYỄN VĂN C", "NGUYỄN VĂN D"])
        text = self.text(result.diagnostic_files)
        self.assertNotIn("ĐÃ BỎ QUA TOÀN BỘ HỘ", text)
        self.assertIn("PERSON_SKIPPED", text)
        self.assertIn("Ô C5 — CCCD: [ĐỂ TRỐNG]", text)
        self.assertIn("Ô C3 — CCCD: invalid", text)
        _, _, verification = self.service.export(result, self.profile, self.root, "filtered.xlsx")
        self.assertTrue(verification["pass"])


if __name__ == "__main__":
    unittest.main()
