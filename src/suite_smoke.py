"""Offline release checks; only creates synthetic files in a temporary directory."""
from pathlib import Path
from tempfile import TemporaryDirectory


def run(hub):
    from launcher_ui.help_page import guide_sources
    from openpyxl import Workbook, load_workbook
    from tools.vbdlis_excel_builder.core.service import BuilderService
    from tools.vbdlis_excel_builder.models import MappingProfile
    from tools.vbdlis_excel_builder.utils.paths import resource_path
    from tools.hpnet_file_generator.core.file_generator import FileGenerator
    from tools.hpnet_file_generator.models.data_models import SourceFile, Parcel, GenerationAction, ActionStatus
    from tools.signed_pdf_cleaner.core.scanner import FileScanner
    from tools.signed_pdf_cleaner.core.processor import FileProcessor
    from tools.signed_pdf_cleaner.core.models import ProcessStatus

    # Presentation-only checks also run inside the packaged Windows executable.
    hub.open_help()
    view = hub.launcher_view
    assert view.pages.currentIndex() == 1
    assert view.help_page.contents.count() == view.help_page.documents.count() == 3
    for index, (_, path) in enumerate(guide_sources()):
        view.help_page.contents.setCurrentRow(index)
        displayed = " ".join(view.help_page.browser.toPlainText().split())
        assert path.is_file(), str(path)
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not set(line) <= {"=", "-"}:
                assert " ".join(line.split()) in displayed, line
    view.help_page.contents.setCurrentRow(0)
    view.help_page.search.setText("giấy tờ nhân thân")
    view.help_page.find_text()
    assert "Đã tìm thấy" in view.help_page.search_status.text()
    view.reset_search()
    assert len(view.visible_tool_keys) == 7

    hub.launch_excel_builder()
    hub.launch_auto_rename()
    hub.launch_pdf_cleaner()
    hub.launch_notice_builder()
    assert set(hub.tool_windows) == {"excel", "rename", "cleaner", "notice"}
    from PySide6.QtWidgets import QListView, QStyle
    notice_window = hub.tool_windows["notice"]
    assert notice_window.steps.count() == notice_window.stack.count() == 8
    for combo in notice_window.mapping.values():
        assert isinstance(combo.view(), QListView)
        assert combo.style().styleHint(QStyle.SH_ComboBox_Popup, None, combo) == 0
    from tools.notice_builder.smoke import run as notice_smoke
    notice = notice_smoke(hub.tool_windows["notice"])
    with TemporaryDirectory(prefix="suite-release-smoke-") as temporary:
        root = Path(temporary)
        source = root / "synthetic.xlsx"
        wb = Workbook()
        wb.active.title = "Du lieu"
        wb.active.append(["STT", "Họ tên", "CCCD", "Số tờ", "Số thửa", "Diện tích"])
        wb.active.append([1, "Nguyễn Văn Kiểm Thử", "031080001234", 10, 300, 100])
        wb.active.append([None, "TỔNG DT", None, None, None, 100])
        wb.save(source)
        wb.close()
        original = source.read_bytes()
        profile = MappingProfile(commune_code="10930", address="Địa chỉ kiểm thử",
            source_mapping={"household_stt": "A", "person_name": "B", "cccd": "C",
                            "sheet_number": "D", "parcel_number": "E", "area": "F"},
            field_rules={"MUC_29": {"mode": "fixed", "default": "Không xác định", "required": True}})
        service = BuilderService(resource_path("resources/BieuMauThuThapThongTinGiayChungNhan.xlsx"),
                                 resource_path("config/template_schema.json"), root / "logs")
        result = service.process(source, "Du lieu", 1, profile)
        assert result.can_export, repr(result.issues)
        assert len(result.rows) == 1
        assert result.stats["summary_rows_skipped"] == 1
        output, report, verification = service.export(result, profile, root, "output.xlsx")
        assert verification["pass"] and report.is_file()
        assert len(result.diagnostic_files.paths) == 2
        saved = load_workbook(output, data_only=True)
        try:
            sheet = saved.worksheets[0]
            assert sheet["AD5"].value == "Không xác định", sheet["AD5"].value
            assert sheet["K5"].value == "Nam", sheet["K5"].value
            assert sheet["I5"].value == "031080001234"
        finally:
            saved.close()
        assert source.read_bytes() == original

        pdf = root / "original.pdf"
        pdf.write_bytes(b"%PDF-offline-synthetic-test")
        action = GenerationAction(SourceFile(pdf, pdf.name, "test", ".pdf"),
                                  Parcel("10", "300"), "TBXN", "copy.pdf", root / "copy.pdf")
        assert FileGenerator().execute_action(action).status == ActionStatus.SUCCESS
        assert action.target_path.read_bytes() == pdf.read_bytes()

        clean_dir = root / "cleaner"
        clean_dir.mkdir()
        signed = clean_dir / "sample.signed.pdf"
        signed.write_bytes(pdf.read_bytes())
        plans = FileScanner().scan_directory(str(clean_dir))
        assert len(plans) == 1
        assert FileProcessor(use_recycle_bin=True).process_plan(plans[0]).status == ProcessStatus.COMPLETED
        assert (clean_dir / "sample.pdf").read_bytes() == pdf.read_bytes()

    return {"status": "PASS", "embedded_help_complete": True, "independent_help_pages": 3, "launcher_tools": 7,
            "python_windows": 4, "notice_builder": notice, "notice_styled_popups": True, "excel_export": True,
            "summary_row_excluded": True, "fixed_item_29": True, "cccd_gender": True,
            "diagnostic_reports": True, "source_unchanged": True,
            "auto_rename_copy": True, "cleaner_rename": True, "hpnet_live_operations": False}
