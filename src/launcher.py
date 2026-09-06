"""Desktop hub: each tool retains its own data and confirmation gates."""
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget)

EXTERNAL_TOOLS = {
    "downloader": ("Downloader/HPNet PDF Downloader - VNEID APP", "HPNet PDF Downloader.exe"),
    "upload": ("Upload/HPNet Upload VB Du Thao - VNEID APP", "HPNet Upload VB Du Thao.exe"),
    "approve": ("Duyet/HPNet Duyet VB Du Thao - VNEID APP", "HPNet Duyet VB Du Thao.exe"),
}

def resource_path(relative_path):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / relative_path)

from launcher_ui.theme import STYLE as HUB_STYLE, palette as launcher_palette
from launcher_ui.view import LauncherView

class ToolLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HPNET & VBDLIS Tools • Không gian làm việc")
        self.resize(1240, 860)
        self.setMinimumSize(900, 660)
        self.setStyleSheet(HUB_STYLE)
        self.setPalette(launcher_palette())
        self.setWindowIcon(QIcon(resource_path("tools/vbdlis_excel_builder/resources/app_icon.ico")))
        self.open_tools = []
        self.tool_windows = {}
        self.tool_buttons = {}
        self._excel_logging_ready = False
        self.update_worker = None
        self.setup_ui()
        self.statusBar().showMessage("Chọn công cụ để bắt đầu. Mở công cụ không tự tải lên, duyệt hay xóa dữ liệu.")

    @staticmethod
    def label(text, name=None):
        widget = QLabel(text)
        widget.setWordWrap(True)
        if name:
            widget.setObjectName(name)
        return widget

    def setup_ui(self):
        self.launcher_view = LauncherView(self)
        self.setCentralWidget(self.launcher_view)

    def _open_python(self, key, factory):
        window = self.tool_windows.get(key)
        if window is None:
            window = factory()
            self.tool_windows[key] = window
            self.open_tools.append(window)
        window.showNormal()
        window.raise_()
        window.activateWindow()
        self.statusBar().showMessage(f"Đã mở {window.windowTitle()}. Các bước xử lý nằm trong cửa sổ công cụ.")

    def launch_excel_builder(self):
        try:
            from tools.vbdlis_excel_builder.main import configure_logging
            from tools.vbdlis_excel_builder.ui.main_window import MainWindow
            if not self._excel_logging_ready:
                configure_logging()
                self._excel_logging_ready = True
            self._open_python("excel", MainWindow)
        except Exception as error:
            if "--smoke-test" in sys.argv:
                raise
            QMessageBox.critical(self, "Không mở được Excel Builder", str(error))

    def launch_auto_rename(self):
        try:
            from tools.hpnet_file_generator.ui.main_window import MainWindow
            self._open_python("rename", MainWindow)
        except Exception as error:
            if "--smoke-test" in sys.argv:
                raise
            QMessageBox.critical(self, "Không mở được Auto Rename", str(error))

    def launch_pdf_cleaner(self):
        try:
            from tools.signed_pdf_cleaner.ui.main_window import MainWindow
            self._open_python("cleaner", MainWindow)
        except Exception as error:
            if "--smoke-test" in sys.argv:
                raise
            QMessageBox.critical(self, "Không mở được PDF Cleaner", str(error))

    def launch_external(self, key):
        folder, executable = EXTERNAL_TOOLS[key]
        self.launch_external_tool(f"nodes_tools/{folder}", executable)

    def launch_notice_builder(self):
        try:
            from tools.notice_builder.ui import MainWindow
            self._open_python("notice", MainWindow)
        except Exception:
            if "--smoke-test" in sys.argv: raise
            QMessageBox.critical(self,"Không mở được công cụ tạo thông báo",
                "Hãy giải nén đầy đủ gói phát hành, giữ thư mục _internal cạnh EXE và kiểm tra quyền đọc/ghi cấu hình người dùng.")

    def launch_duplicate_parcel(self):
        try:
            from tools.duplicate_parcel.ui import MainWindow
            self._open_python("duplicate_parcel", MainWindow)
        except Exception as error:
            if "--smoke-test" in sys.argv: raise
            QMessageBox.critical(self, "Không mở được công cụ làm sạch thửa trùng", str(error))

    def launch_data_normalizer(self):
        try:
            from tools.data_normalizer.ui import MainWindow
            self._open_python("data_normalizer", MainWindow)
        except Exception as error:
            if "--smoke-test" in sys.argv: raise
            QMessageBox.critical(self, "Không mở được công cụ chuẩn hóa dữ liệu", str(error))

    def launch_external_tool(self, tool_dir, tool_exe):
        try:
            exe_path = Path(resource_path(tool_dir)) / tool_exe
            if not exe_path.is_file():
                raise FileNotFoundError(f"Không tìm thấy công cụ:\n{exe_path}\nHãy giải nén đầy đủ gói phát hành.")
            subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
            self.statusBar().showMessage(f"Đã mở {tool_exe}. Kiểm tra cấu hình trong cửa sổ riêng.")
        except Exception as error:
            QMessageBox.critical(self, "Không mở được công cụ", str(error))

    def open_help(self):
        self.launcher_view.show_help()

    def check_for_updates(self):
        if not getattr(sys, "frozen", False):
            return
        from auto_update import check_for_update
        from tools.qt_worker import Worker
        self.update_worker = Worker(check_for_update, self)
        self.update_worker.succeeded.connect(self._offer_update)
        self.update_worker.start()

    def _offer_update(self, release):
        if not release:
            return
        answer = QMessageBox.question(self, "Có bản cập nhật mới",
            f"Phiên bản {release['version']} đã sẵn sàng. Tải và cài đặt ngay?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer != QMessageBox.Yes:
            return
        from auto_update import download_update
        from tools.qt_worker import Worker
        self.statusBar().showMessage("Đang tải và kiểm tra bản cập nhật…")
        self.setEnabled(False)
        self.update_worker = Worker(lambda: download_update(release), self)
        self.update_worker.succeeded.connect(self._install_update)
        self.update_worker.failed.connect(self._update_failed)
        self.update_worker.start()

    def _update_failed(self, message):
        self.setEnabled(True)
        QMessageBox.warning(self, "Không cập nhật được", f"Bản hiện tại vẫn được giữ nguyên.\n\n{message}")

    def _install_update(self, new_app):
        try:
            from auto_update import launch_installer
            launch_installer(new_app)
        except Exception as error:
            self.setEnabled(True)
            QMessageBox.warning(self, "Không cập nhật được", f"Bản hiện tại vẫn được giữ nguyên.\n\n{error}")
            return
        QApplication.quit()


def main():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HPNET.VBDLIS.Tools.Suite")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("HPNET & VBDLIS Tools")
    app.setWindowIcon(QIcon(resource_path("tools/vbdlis_excel_builder/resources/app_icon.ico")))
    window = ToolLauncher()
    if "--smoke-test" in sys.argv:
        import json
        import traceback
        try:
            from suite_smoke import run
            report = run(window)
        except Exception:
            report = {"status": "FAIL", "error": traceback.format_exc()}
        finally:
            for tool in window.open_tools:
                tool.close()
        if "--smoke-report" in sys.argv:
            target = Path(sys.argv[sys.argv.index("--smoke-report") + 1])
            target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if report["status"] == "PASS" else 1
    else:
        window.show()
        QTimer.singleShot(1500, window.check_for_updates)
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
