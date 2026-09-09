"""Desktop hub: each tool retains its own data and confirmation gates."""
import subprocess
import sys
import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget)
from auto_update import build_info

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
        self.setWindowTitle("HPNET & VBDLIS Tools • Trung tâm tác nghiệp hồ sơ")
        self.resize(1240, 860)
        self.setMinimumSize(900, 660)
        self.setStyleSheet(HUB_STYLE)
        self.setPalette(launcher_palette())
        self.setWindowIcon(QIcon(resource_path("tools/vbdlis_excel_builder/resources/app_icon.ico")))
        self.open_tools = []
        self.tool_windows = {}
        self.external_processes = {}
        self.external_timers = {}
        self.tool_buttons = {}
        self._excel_logging_ready = False
        self.update_worker = None
        self.latest_worker = None
        self.current_version = str(build_info().get("version", "development"))
        self.setup_ui()
        self.statusBar().showMessage("Chọn công cụ để bắt đầu. Việc mở công cụ không tự động tải lên, duyệt hoặc xóa dữ liệu.")
        self._setup_version_status()

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

    def _setup_version_status(self):
        self.current_version_status = QLabel(f"Đang dùng: {self.current_version}")
        self.current_version_status.setObjectName("versionStatus")
        self.current_version_status.setAccessibleName("Phiên bản hiện tại")
        self.latest_version_status = QLabel("Mới nhất: đang kiểm tra…")
        self.latest_version_status.setObjectName("versionStatus")
        self.latest_version_status.setAccessibleName("Phiên bản mới nhất")
        self.update_now_button = QPushButton("Cập nhật ngay")
        self.update_now_button.setObjectName("updateNow")
        self.update_now_button.setAccessibleName("Cập nhật ngay")
        self.update_now_button.clicked.connect(self.check_for_updates)
        self.statusBar().addPermanentWidget(self.current_version_status)
        self.statusBar().addPermanentWidget(self.latest_version_status)
        self.statusBar().addPermanentWidget(self.update_now_button)

    def set_latest_version(self, version, error=False):
        text = f"Mới nhất: {version or 'không xác định'}"
        if error:
            text += " (chưa kiểm tra được)"
        self.latest_version_status.setText(text)

    def _open_python(self, key, factory):
        window = self.tool_windows.get(key)
        if window is None:
            window = factory()
            window.setAttribute(Qt.WA_DeleteOnClose, True)
            window.destroyed.connect(lambda _=None, tool_key=key: self._tool_closed(tool_key))
            self.tool_windows[key] = window
            self.open_tools.append(window)
        self.hide()
        window.showNormal()
        window.raise_()
        window.activateWindow()
        self.statusBar().showMessage(f"Đã mở {window.windowTitle()}. Các bước xử lý được thực hiện trong cửa sổ công cụ.")

    def _tool_closed(self, key):
        closed = self.tool_windows.pop(key, None)
        if closed is not None:
            self.open_tools = [window for window in self.open_tools if window is not closed]
        try:
            self.showNormal()
            self.raise_()
            self.activateWindow()
        except RuntimeError:
            pass  # Qt may destroy child windows after the launcher during shutdown.

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
            QMessageBox.critical(self, "Không thể mở Excel Builder", str(error))

    def launch_auto_rename(self):
        try:
            from tools.hpnet_file_generator.ui.main_window import MainWindow
            self._open_python("rename", MainWindow)
        except Exception as error:
            if "--smoke-test" in sys.argv:
                raise
            QMessageBox.critical(self, "Không thể mở Auto Rename", str(error))

    def launch_pdf_cleaner(self):
        try:
            from tools.signed_pdf_cleaner.ui.main_window import MainWindow
            self._open_python("cleaner", MainWindow)
        except Exception as error:
            if "--smoke-test" in sys.argv:
                raise
            QMessageBox.critical(self, "Không thể mở PDF Cleaner", str(error))

    def launch_external(self, key):
        folder, executable = EXTERNAL_TOOLS[key]
        self.launch_external_tool(f"nodes_tools/{folder}", executable)

    def launch_notice_builder(self):
        try:
            from tools.notice_builder.ui import MainWindow
            self._open_python("notice", MainWindow)
        except Exception:
            if "--smoke-test" in sys.argv: raise
            QMessageBox.critical(self,"Không thể mở công cụ tạo thông báo",
                "Vui lòng giải nén đầy đủ gói phát hành, giữ thư mục _internal cạnh EXE và kiểm tra quyền đọc/ghi cấu hình người dùng.")

    def launch_duplicate_parcel(self):
        try:
            from tools.duplicate_parcel.ui import MainWindow
            self._open_python("duplicate_parcel", MainWindow)
        except Exception as error:
            if "--smoke-test" in sys.argv: raise
            QMessageBox.critical(self, "Không thể mở công cụ làm sạch thửa trùng", str(error))

    def launch_data_normalizer(self):
        try:
            from tools.data_normalizer.ui import MainWindow
            self._open_python("data_normalizer", MainWindow)
        except Exception as error:
            if "--smoke-test" in sys.argv: raise
            QMessageBox.critical(self, "Không thể mở công cụ chuẩn hóa dữ liệu", str(error))

    def launch_external_tool(self, tool_dir, tool_exe):
        try:
            exe_path = Path(resource_path(tool_dir)) / tool_exe
            if not exe_path.is_file():
                raise FileNotFoundError(f"Không tìm thấy công cụ:\n{exe_path}\nVui lòng giải nén đầy đủ gói phát hành.")
            process = subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
            self.external_processes[tool_exe] = process
            timer = QTimer(self)
            timer.timeout.connect(lambda name=tool_exe: self._poll_external(name))
            timer.start(500)
            self.external_timers[tool_exe] = timer
            self.hide()
            self.statusBar().showMessage(f"Đã mở {tool_exe}. Vui lòng kiểm tra cấu hình trong cửa sổ riêng.")
        except Exception as error:
            QMessageBox.critical(self, "Không mở được công cụ", str(error))

    def _poll_external(self, tool_exe):
        process = self.external_processes.get(tool_exe)
        if process is None or process.poll() is None:
            return
        timer = self.external_timers.pop(tool_exe, None)
        if timer:
            timer.stop(); timer.deleteLater()
        self.external_processes.pop(tool_exe, None)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def open_help(self):
        self.launcher_view.show_help()

    def check_for_updates(self):
        if self.update_worker is not None and self.update_worker.isRunning():
            return
        if not getattr(sys, "frozen", False):
            self.set_latest_version("chỉ có trong bản phát hành")
            self.statusBar().showMessage("Bản phát triển không thể kiểm tra cập nhật tự động.", 5000)
            return
        from auto_update import check_for_update, fetch_latest_version
        from tools.qt_worker import Worker
        self.update_now_button.setEnabled(False)
        self.latest_worker = Worker(fetch_latest_version, self)
        self.latest_worker.succeeded.connect(lambda version: self.set_latest_version(version))
        self.latest_worker.failed.connect(lambda _message: self.set_latest_version(None, error=True))
        self.latest_worker.start()
        self.update_worker = Worker(check_for_update, self)
        self.update_worker.succeeded.connect(self._offer_update)
        self.update_worker.failed.connect(self._update_failed)
        self.update_worker.start()

    def _offer_update(self, release):
        if not release:
            self.update_now_button.setEnabled(True)
            self.statusBar().showMessage("Bạn đang sử dụng phiên bản mới nhất.", 5000)
            return
        answer = QMessageBox.question(self, "Có phiên bản mới",
            f"Phiên bản {release['version']} đã sẵn sàng. Bạn có muốn tải xuống và cài đặt ngay không?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer != QMessageBox.Yes:
            self.update_now_button.setEnabled(True)
            return
        from auto_update import download_update
        from tools.qt_worker import Worker
        self.statusBar().showMessage("Đang tải xuống và kiểm tra bản cập nhật…")
        self.setEnabled(False)
        self.update_worker = Worker(lambda: download_update(release), self)
        self.update_worker.succeeded.connect(self._install_update)
        self.update_worker.failed.connect(self._update_failed)
        self.update_worker.start()

    def _update_failed(self, message):
        self.setEnabled(True)
        self.update_now_button.setEnabled(True)
        QMessageBox.warning(self, "Không thể cập nhật", f"Phiên bản hiện tại vẫn được giữ nguyên.\n\n{message}")

    def _install_update(self, new_app):
        try:
            from auto_update import launch_installer
            for tool in list(self.open_tools):
                tool.close()
            launch_installer(new_app)
        except Exception as error:
            self.setEnabled(True)
            self.update_now_button.setEnabled(True)
            QMessageBox.warning(self, "Không thể cập nhật", f"Phiên bản hiện tại vẫn được giữ nguyên.\n\n{error}")
            return
        QApplication.quit()
        # Give Qt a short grace period, then guarantee the parent process exits
        # so the detached installer can replace the application directory.
        QTimer.singleShot(500, lambda: os._exit(0))


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
