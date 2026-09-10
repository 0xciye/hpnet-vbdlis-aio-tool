import pytest
from PySide6.QtWidgets import QApplication

from tools.signed_pdf_cleaner.core.scanner import TARGET_ALL, TARGET_ORPHAN_SIGNED, TARGET_PAIRS
from tools.signed_pdf_cleaner.ui.main_window import MainWindow


@pytest.fixture
def window(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication(["pdf-cleaner-ui-test", "-platform", "offscreen"])
    window = MainWindow()
    window.show()
    app.processEvents()
    yield window
    window.close()
    window.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("mode", [TARGET_ALL, TARGET_PAIRS])
def test_pair_modes_show_delete_controls(window, mode):
    window.cmb_target_mode.setCurrentIndex(window.cmb_target_mode.findData(mode))
    assert window.txt_delete_suffix.isVisible()
    assert window.cmb_delete_mode.isVisible()
    assert not window.table.isColumnHidden(1)


def test_orphan_mode_only_shows_suffix_removal_controls(window):
    window.plans = [object()]
    window.btn_process.setEnabled(True)
    window.cmb_target_mode.setCurrentIndex(window.cmb_target_mode.findData(TARGET_ORPHAN_SIGNED))

    assert not window.txt_delete_suffix.isVisible()
    assert not window.cmb_delete_mode.isVisible()
    assert window.lbl_signed_suffix.text() == "Hậu tố ký cần bỏ (vẫn giữ .pdf):"
    assert window.table.isColumnHidden(1)
    assert window.table.horizontalHeaderItem(0).text() == "File cần xóa hậu tố"
    assert window.btn_process.text() == "Xóa hậu tố"
    assert window.plans == []
    assert not window.btn_process.isEnabled()
