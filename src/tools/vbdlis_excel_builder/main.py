from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from tools.vbdlis_excel_builder.ui import MainWindow
from tools.vbdlis_excel_builder.utils.paths import app_data_dir, resource_path


STYLE = """
/* ── Base ── */
QWidget {
    font-family: "Segoe UI";
    font-size: 10pt;
    color: #1e293b;
}
QMainWindow {
    background: #f1f5f9;
}

/* ── Tab bar ── */
QTabWidget::pane {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-top: none;
}
QTabBar::tab {
    padding: 10px 20px;
    background: #e2e8f0;
    color: #475569;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-size: 9.5pt;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #0b63ce;
    font-weight: 600;
    border-bottom: 2px solid #ffffff;
}
QTabBar::tab:hover:!selected {
    background: #f0f4fa;
    color: #1e293b;
}

/* ── Inputs ── */
QLineEdit, QComboBox, QSpinBox {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    padding: 5px 8px;
    min-height: 24px;
    selection-background-color: #bfdbfe;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1.5px solid #0b63ce;
    background: #f8fbff;
}
QLineEdit:read-only {
    background: #f8fafc;
    color: #64748b;
}
QComboBox::drop-down {
    border: none;
    width: 26px;
}
QComboBox::down-arrow {
    image: url(__CHEVRON__);
    width: 16px;
    height: 16px;
}
QComboBox {
    padding-right: 28px;
    combobox-popup: 0;
}
QComboBox:disabled, QLineEdit:disabled {
    color: #64748b;
    background-color: #f1f5f9;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    selection-background-color: #dbeafe;
    selection-color: #1e293b;
    outline: none;
}
QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 3px 8px;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #dbeafe;
    color: #15395c;
}
QTableWidget QComboBox, QTableWidget QLineEdit {
    min-height: 0px;
    padding: 3px 6px;
    margin: 2px;
    border-radius: 4px;
}
QTableWidget QComboBox { padding-right: 26px; }
QToolTip {
    background-color: #15395c;
    color: white;
    border: none;
    padding: 6px;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 16px;
    border: none;
    background: transparent;
}

/* ── Buttons ── */
QToolButton {
    background: #f1f5f9;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    padding: 6px 12px;
    min-height: 26px;
}
QToolButton:hover { background: #e2e8f0; border-color: #94a3b8; }
QToolButton:checked { background: #dbeafe; color: #15395c; }
QPushButton {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    padding: 6px 14px;
    min-height: 28px;
    font-weight: 500;
}
QPushButton:hover {
    background: #e2e8f0;
    border-color: #94a3b8;
}
QPushButton:pressed {
    background: #cbd5e1;
}
QPushButton:disabled {
    color: #94a3b8;
    background: #f8fafc;
    border-color: #e2e8f0;
}
QPushButton[accent="true"] {
    background: #0b63ce;
    color: white;
    font-weight: 600;
    border: 1px solid #0950a8;
}
QPushButton[accent="true"]:hover {
    background: #0d74ef;
    border-color: #0b63ce;
}
QPushButton[accent="true"]:pressed {
    background: #0846a0;
}

/* ── Labels ── */
QLabel[warning="true"] {
    background: #fffbeb;
    color: #78350f;
    border: 1px solid #fcd34d;
    border-left: 4px solid #f59e0b;
    border-radius: 4px;
    padding: 8px 12px;
}
QLabel[info="true"] {
    background: #eff6ff;
    color: #1e3a5f;
    border: 1px solid #bfdbfe;
    border-left: 4px solid #3b82f6;
    border-radius: 4px;
    padding: 6px 12px;
}

/* ── Tables ── */
QTableWidget {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    gridline-color: #f0f4f8;
    selection-background-color: #dbeafe;
    selection-color: #1e293b;
    alternate-background-color: #f8fafc;
}
QTableWidget::item {
    padding: 4px 8px;
}
QTableWidget::item:selected {
    background: #dbeafe;
    color: #1e293b;
}
QHeaderView::section {
    background: #1e3a5f;
    color: #ffffff;
    padding: 7px 10px;
    border: none;
    border-right: 1px solid #2c4f7a;
    font-weight: 600;
    font-size: 9pt;
}
QHeaderView::section:last {
    border-right: none;
}
QHeaderView::section:horizontal:hover {
    background: #2c4f7a;
}

/* ── Progress bar ── */
QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    background: #f1f5f9;
    text-align: center;
    height: 10px;
}
QProgressBar::chunk {
    background: #0b63ce;
    border-radius: 3px;
}

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: #f8fafc;
    width: 10px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #f8fafc;
    height: 10px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #cbd5e1;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #94a3b8;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── CheckBox ── */
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid #94a3b8;
    border-radius: 3px;
    background: white;
}
QCheckBox::indicator:checked {
    background: #0b63ce;
    border-color: #0b63ce;
    image: url(__CHECK__);
}
QCheckBox::indicator:hover {
    border-color: #0b63ce;
}

/* ── Splitter ── */
QSplitter::handle {
    background: #e2e8f0;
    width: 4px;
    height: 4px;
}
QSplitter::handle:hover {
    background: #94a3b8;
}

/* ── Status bar ── */
QStatusBar {
    background: #1e3a5f;
    color: #e2e8f0;
    font-size: 9pt;
    padding: 2px 8px;
}
"""


def configure_logging() -> None:
    log_path = app_data_dir() / "logs" / "app.log"
    root = logging.getLogger()
    if not any(getattr(handler, "baseFilename", None) == str(log_path.resolve()) for handler in root.handlers):
        handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        root.addHandler(handler)
    root.setLevel(logging.INFO)


def main() -> int:
    configure_logging()
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VBDLIS.ExcelBuilder.Desktop")
    app = QApplication(sys.argv)
    configure_appearance(app)
    window = MainWindow()
    window.setWindowIcon(app.windowIcon())
    if "--smoke-test" in sys.argv:
        if app.windowIcon().isNull():
            raise RuntimeError("Thiếu icon ứng dụng trong bản đóng gói.")
        QTimer.singleShot(250, app.quit)
    else:
        window.show()
    return app.exec()


def light_palette() -> QPalette:
    palette = QPalette()
    for role, color in (
        (QPalette.Window, "#f1f5f9"), (QPalette.WindowText, "#1e293b"),
        (QPalette.Base, "#ffffff"), (QPalette.AlternateBase, "#f8fafc"),
        (QPalette.Text, "#1e293b"), (QPalette.Button, "#f1f5f9"),
        (QPalette.ButtonText, "#1e293b"), (QPalette.Highlight, "#dbeafe"),
        (QPalette.HighlightedText, "#15395c"), (QPalette.PlaceholderText, "#64748b"),
    ):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#64748b"))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#64748b"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#64748b"))
    return palette


def window_stylesheet() -> str:
    return (STYLE.replace("__CHEVRON__", resource_path("resources/chevron_down.svg").as_posix())
            .replace("__CHECK__", resource_path("resources/check.svg").as_posix()))


def configure_window_appearance(window) -> None:
    """Also style direct launcher construction, without changing other tools."""
    window.setPalette(light_palette())
    window.setStyleSheet(window_stylesheet())
    window.setWindowIcon(QIcon(str(resource_path("resources/app_icon.ico"))))


def configure_appearance(app: QApplication) -> None:
    app.setApplicationName("VBDLIS Excel Builder")
    app.setOrganizationName("VBDLIS Tools")
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    palette = light_palette()
    app.setPalette(palette)
    app.setStyleSheet(window_stylesheet())
    app.setWindowIcon(QIcon(str(resource_path("resources/app_icon.ico"))))


if __name__ == "__main__":
    raise SystemExit(main())
