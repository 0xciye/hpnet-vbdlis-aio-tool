"""Check the reported layout regressions and optionally refresh guide screenshots."""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from unittest.mock import patch
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QComboBox

from tools.vbdlis_excel_builder.main import configure_appearance
from tools.vbdlis_excel_builder.ui import MainWindow
from tools.vbdlis_excel_builder.core.service import ProcessResult
from tools.vbdlis_excel_builder.core.diagnostic_logger import DiagnosticFiles
from tools.vbdlis_excel_builder.models import Severity, ValidationIssue


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="vbdlis-ui-") as app_data:
        os.environ["APPDATA"] = app_data
        app = QApplication(["ui-check", "-platform", "offscreen"])
        # The offscreen plugin does not discover Windows system fonts itself.
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
            if (fonts / name).exists():
                QFontDatabase.addApplicationFont(str(fonts / name))
        dark = QPalette()
        dark.setColor(QPalette.Base, QColor("#202020"))
        app.setPalette(dark)
        configure_appearance(app)
        assert not app.windowIcon().isNull(), "Application icon missing"
        window = MainWindow()
        window.show()
        tabs = window.centralWidget()
        checked = 0
        for width, height in ((1100, 700), (1450, 900)):
            window.resize(width, height)
            for index in range(tabs.count()):
                tabs.setCurrentIndex(index)
                app.processEvents()
                if index in (1, 3):
                    table = (window.mapping_page if index == 1 else window.advanced_page).table
                    for row in range(table.rowCount()):
                        for col in range(table.columnCount()):
                            editor = table.cellWidget(row, col)
                            if editor is not None:
                                assert editor.height() <= table.rowHeight(row), (index, row, col, editor.height())
                                assert editor.minimumSizeHint().height() <= table.rowHeight(row), (index, row, col)
                                checked += 1
                if args.screenshots and width == 1450:
                    args.screenshots.mkdir(parents=True, exist_ok=True)
                    window.grab().save(str(args.screenshots / f"tab_{index + 1}.png"))
        for combo in window.findChildren(QComboBox):
            assert combo.view().palette().color(QPalette.Base).lightness() > 200, "Dark popup palette"
        gender_row = next(i for i, s in enumerate(window.service.schemas) if s.transformer == "gender")
        field_id = window.service.schemas[gender_row].field_id
        window.advanced_page.load_rules({field_id: {"mode": "fixed", "default": "Nam"}})
        assert window.advanced_page.rules()[field_id]["mode"] == "computed"
        assert not window.advanced_page.table.cellWidget(gender_row, 4).isEnabled()
        assert window.settings_page.skip_invalid_data.isChecked()
        assert not window.settings_page.invalid_cccd.isEnabled()
        assert not window.export_page.open_log.isEnabled()
        sample = ProcessResult(issues=[ValidationIssue(Severity.ERROR, "MISSING_COMMUNE_CODE", "Chưa nhập mã xã.")],
                               stats={"errors": 1}, diagnostic_files=DiagnosticFiles([Path(__file__).resolve()]))
        window.export_page.show_result(sample)
        assert window.export_page.open_log.isEnabled()
        with patch("tools.vbdlis_excel_builder.ui.main_window.QDesktopServices.openUrl", return_value=True) as opener:
            window.export_page.open_log.click()
            assert opener.call_args.args[0].toLocalFile() == str(Path(__file__).resolve()).replace('\\', '/')
            window.export_page.open_log_folder.click()
            assert opener.call_args.args[0].toLocalFile() == str(Path(__file__).resolve().parent).replace('\\', '/')
        window.export_page.set_diagnostic_files(DiagnosticFiles(error="Không lưu được báo cáo"))
        assert not window.export_page.open_log.isEnabled()
        assert "Không lưu" in window.export_page.log_status.text()
        if args.screenshots:
            tabs.setCurrentIndex(3)
            combo = window.advanced_page.table.cellWidget(0, 4)
            combo.showPopup()
            app.processEvents()
            combo.view().window().grab().save(str(args.screenshots / "mode_popup.png"))
            combo.hidePopup()
        window.close()
        print(f"UI PASS: {checked} cell geometries; light popups; icon; CCCD rule; diagnostic buttons/failure; 1100/1450px")


if __name__ == "__main__":
    main()
