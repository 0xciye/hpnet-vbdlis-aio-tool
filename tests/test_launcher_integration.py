import json
import logging
import os
from pathlib import Path
import threading
import time
from unittest.mock import patch

import pytest
from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QComboBox, QMessageBox, QTableWidget

from launcher import EXTERNAL_TOOLS, ToolLauncher, resource_path
from tools.runtime_paths import tool_settings_path


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication(["integration", "-platform", "offscreen"])
    app.setStyle("Fusion")
    fonts = Path(os.getenv("WINDIR", "C:/Windows")) / "Fonts"
    for filename in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
        if (fonts / filename).exists():
            QFontDatabase.addApplicationFont(str(fonts / filename))
    palette = QPalette()
    for role in (QPalette.Window, QPalette.Base, QPalette.Button):
        palette.setColor(role, QColor("#202020"))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        palette.setColor(role, QColor("#ffffff"))
    app.setPalette(palette)
    return app


@pytest.fixture
def hub(app, monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.chdir(tmp_path)
    window = ToolLauncher()
    def fail_dialog(*args):
        raise AssertionError(f"Tool startup failed: {args[-1]}")
    with patch("launcher.QMessageBox.critical", side_effect=fail_dialog):
        yield window
    for tool in window.open_tools:
        tool.close()
    window.close()
    for logger in [logging.getLogger(), logging.getLogger("SignedPdfCleaner")]:
        for handler in logger.handlers[:]:
            filename = getattr(handler, "baseFilename", "")
            if filename and str(tmp_path) in filename:
                handler.close()
                logger.removeHandler(handler)
    app.processEvents()


def test_nine_cards_and_resource_paths_independent_of_cwd(hub):
    assert set(hub.tool_buttons) == {"excel", "rename", "cleaner", "downloader", "upload", "approve", "notice", "duplicate_parcel", "data_normalizer"}
    assert Path(resource_path("tools/vbdlis_excel_builder/config/template_schema.json")).is_file()
    assert not hub.windowIcon().isNull()


def test_new_excel_utilities_open_as_independent_windows(hub):
    hub.launch_duplicate_parcel(); hub.launch_data_normalizer()
    assert hub.tool_windows["duplicate_parcel"].windowTitle() == "Kiểm tra & Làm sạch thửa trùng"
    assert hub.tool_windows["data_normalizer"].windowTitle() == "Chuẩn hóa Họ tên & Ngày sinh"
    assert hub.tool_windows["duplicate_parcel"] is not hub.tool_windows["data_normalizer"]


def test_excel_utilities_show_real_worker_completion_and_error_states(hub, app):
    for launch, key in ((hub.launch_duplicate_parcel, "duplicate_parcel"), (hub.launch_data_normalizer, "data_normalizer")):
        launch(); window = hub.tool_windows[key]
        gate = threading.Event()
        window._run(lambda: gate.wait(2) or "done", lambda _: window.statusBar().showMessage("Hoàn tất kiểm thử."))
        app.processEvents()
        assert window.progress.isVisible() and not window.isEnabled()
        gate.set()
        deadline = time.monotonic() + 3
        while window.worker and time.monotonic() < deadline:
            app.processEvents(); time.sleep(0.01)
        assert window.worker is None and window.isEnabled() and not window.progress.isVisible()
        assert window.statusBar().currentMessage().startswith("Hoàn tất")
        with patch.object(QMessageBox, "warning"):
            window._run(lambda: (_ for _ in ()).throw(ValueError("synthetic failure")), lambda _: None)
            deadline = time.monotonic() + 3
            while window.worker and time.monotonic() < deadline:
                app.processEvents(); time.sleep(0.01)
        assert "thất bại" in window.statusBar().currentMessage()


def test_notice_builder_reuse_theme_and_offline_service(hub,app):
    from tools.notice_builder.smoke import run
    original=app.palette().color(QPalette.Base)
    hub.tool_buttons["notice"].click(); app.processEvents(); window=hub.tool_windows["notice"]
    window.inputs["village"].setText("Thôn đang nhập")
    hub.launch_notice_builder()
    assert hub.tool_windows["notice"] is window and window.inputs["village"].text()=="Thôn đang nhập"
    assert app.palette().color(QPalette.Base)==original
    assert window.palette().color(QPalette.Base).lightness()>220
    assert run(window)["status"]=="PASS"


def test_excel_direct_from_launcher_has_light_theme_without_changing_app(hub, app):
    original = app.palette().color(QPalette.Base)
    hub.tool_buttons["excel"].click()
    app.processEvents()
    window = hub.tool_windows["excel"]
    app.processEvents()
    assert app.palette().color(QPalette.Base) == original
    assert window.palette().color(QPalette.Base).lightness() > 220
    assert window.palette().color(QPalette.WindowText).lightness() < 100
    assert window.styleSheet() and not window.windowIcon().isNull()
    assert window.tabs.count() == 5
    for combo in window.findChildren(QComboBox):
        assert combo.view().palette().color(QPalette.Base).lightness() > 200
    assert (Path(os.environ["APPDATA"]) / "VBDLIS Excel Builder/logs/app.log").exists()


def test_opening_twice_reuses_window_and_preserves_unsaved_fields(hub):
    hub.launch_excel_builder()
    first = hub.tool_windows["excel"]
    first.settings_page.commune_code.setText("10930")
    hub.launch_excel_builder()
    assert hub.tool_windows["excel"] is first
    assert len(hub.open_tools) == 1
    assert first.settings_page.commune_code.text() == "10930"


def test_search_muc29_does_not_change_hidden_rules_and_fixed_value_is_saved(hub, app):
    hub.launch_excel_builder()
    page = hub.tool_windows["excel"].advanced_page
    before = page.rules()
    page.search.setText("thoi han su dung")
    app.processEvents()
    row = next(i for i, schema in enumerate(page.schemas) if schema.field_id == "MUC_29")
    assert not page.table.isRowHidden(row)
    assert page.rules() == before
    page.table.setCurrentCell(row, 6)
    assert "Thời hạn sử dụng" in page.field_details.text()
    mode = page.table.cellWidget(row, 4)
    mode.setCurrentIndex(mode.findData("fixed"))
    page.table.cellWidget(row, 6).setText("Không xác định")
    assert page.rules()["MUC_29"]["default"] == "Không xác định"
    assert page.rules()["MUC_29"]["mode"] == "fixed"
    page.search.clear()
    assert all(not page.table.isRowHidden(i) for i in range(page.table.rowCount()))
    for key in before.keys() - {"MUC_29"}:
        assert page.rules()[key] == before[key]


def test_other_python_tools_open_and_persist_separate_settings(hub, app, tmp_path):
    hub.launch_auto_rename()
    hub.launch_pdf_cleaner()
    rename, cleaner = hub.tool_windows["rename"], hub.tool_windows["cleaner"]
    assert rename.settings_file != cleaner.settings_file
    rename.txt_excel.setText("C:/Dữ liệu/nguồn.xlsx")
    cleaner.txt_folder.setText("C:/Dữ liệu/PDF")
    rename.close(); cleaner.close()
    assert json.loads(rename.settings_file.read_text(encoding="utf-8"))["excel"].endswith("nguồn.xlsx")
    assert json.loads(cleaner.settings_file.read_text(encoding="utf-8"))["folder"].endswith("PDF")
    assert not (tmp_path / "settings.json").exists()
    assert not (tmp_path / "config.json").exists()
    assert cleaner.logger.log_dir.is_relative_to(Path(os.environ["APPDATA"]))


def test_legacy_settings_migration_is_non_destructive(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.chdir(tmp_path)
    old = tmp_path / "settings.json"
    old.write_text(json.dumps({"excel":"gốc.xlsx", "source":"files", "output":"out"}), encoding="utf-8")
    snapshot = old.read_bytes()
    target = tool_settings_path("Auto Rename", "settings.json", tmp_path, {"excel", "source", "output"})
    assert target.read_bytes() == snapshot == old.read_bytes()
    target.write_text('{"keep":"new settings"}', encoding="utf-8")
    tool_settings_path("Auto Rename", "settings.json", tmp_path, {"excel", "source", "output"})
    assert json.loads(target.read_text())["keep"] == "new settings"
    assert old.read_bytes() == snapshot


def test_external_tools_route_to_own_exe_and_working_folder_without_running(hub,app):
    with patch("launcher.subprocess.Popen") as popen:
        for key, (folder, executable) in EXTERNAL_TOOLS.items():
            hub.tool_buttons[key].click()
            app.processEvents()
            args, kwargs = popen.call_args
            target = Path(resource_path(f"nodes_tools/{folder}")) / executable
            assert target.is_file()
            assert args[0] == [str(target)]
            assert kwargs["cwd"] == str(target.parent)
    assert popen.call_count == 3


def test_all_tabs_editor_heights_under_dark_desktop(hub, app):
    hub.launch_excel_builder()
    window = hub.tool_windows["excel"]
    checked = 0
    for width, height in ((1100,700),(1450,900)):
        window.resize(width,height)
        for index in range(window.tabs.count()):
            window.tabs.setCurrentIndex(index)
            app.processEvents()
            for table in window.tabs.currentWidget().findChildren(QTableWidget):
                for row in range(table.rowCount()):
                    for col in range(table.columnCount()):
                        editor = table.cellWidget(row,col)
                        if editor:
                            assert editor.minimumSizeHint().height() <= table.rowHeight(row)
                            checked += 1
    assert checked >= 646
