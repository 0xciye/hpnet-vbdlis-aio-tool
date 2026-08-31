from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from tools.vbdlis_excel_builder.core import BuilderService
from tools.vbdlis_excel_builder.core.diagnostic_logger import DiagnosticContext, DiagnosticFailure, DiagnosticFiles
from tools.vbdlis_excel_builder.core.profile_store import ProfileStore
from tools.vbdlis_excel_builder.models import MappingProfile
from tools.vbdlis_excel_builder.models.mapping_profile import DEFAULT_ITEM_49
from tools.vbdlis_excel_builder.utils.paths import app_data_dir, resource_path

from .advanced_mapping_page import AdvancedMappingPage
from .data_page import DataPage
from .export_page import ExportPage
from .mapping_page import MappingPage
from .settings_page import SettingsPage


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(object)


class TaskWorker(QRunnable):
    def __init__(self, function: Callable[[], Any]):
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.finished.emit(self.function())
        except Exception as exc:  # UI boundary: log full traceback, show concise error.
            logging.exception("Background task failed")
            self.signals.failed.emit(exc)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Imported lazily: standalone main imports this window too.
        from tools.vbdlis_excel_builder.main import configure_window_appearance
        configure_window_appearance(self)
        self.setWindowTitle("VBDLIS Excel Builder")
        self.resize(1450, 900)
        self.setMinimumSize(1100, 700)
        self.thread_pool = QThreadPool.globalInstance()
        self.profile_store = ProfileStore()
        self.profiles = self._load_profiles()
        self._profile_guard = False
        self.source_columns = []
        self.current_result = None
        self.service = BuilderService(
            resource_path("resources/BieuMauThuThapThongTinGiayChungNhan.xlsx"),
            resource_path("config/template_schema.json"),
        )

        self.data_page = DataPage()
        self.mapping_page = MappingPage()
        self.settings_page = SettingsPage()
        self.advanced_page = AdvancedMappingPage(self.service.schemas)
        self.export_page = ExportPage()
        tabs = QTabWidget()
        self.tabs = tabs
        tabs.setDocumentMode(True)
        tabs.setUsesScrollButtons(True)
        tabs.addTab(self.data_page, "1. Dữ liệu")
        tabs.addTab(self.mapping_page, "2. Ánh xạ cột")
        tabs.addTab(self.settings_page, "3. Cấu hình VBDLIS")
        tabs.addTab(self.advanced_page, "4. Quy tắc nâng cao")
        tabs.addTab(self.export_page, "5. Kiểm tra và Xuất")
        self.setCentralWidget(tabs)
        for index, hint in enumerate((
            "Bước 1: chọn Excel nguồn và kiểm tra dòng tiêu đề.",
            "Bước 2: ghép các trường cần dùng với cột trong Excel nguồn.",
            "Bước 3: kiểm tra mã xã, địa chỉ và cách xử lý dữ liệu thiếu.",
            "Tùy chọn nâng cao: tìm mục cần sửa; giá trị cố định điền ở cột Mặc định.",
            "Bước cuối: kiểm tra, xem trước, rồi tạo file VBDLIS và đọc báo cáo.",
        )):
            tabs.setTabToolTip(index, hint)
        self.statusBar().showMessage("Bắt đầu ở tab 1. File Excel nguồn chỉ được đọc, không bị chỉnh sửa.")

        self.data_page.file_selected.connect(self._source_file_selected)
        self.data_page.load_requested.connect(self._load_source_preview)
        self.mapping_page.auto_requested.connect(self._auto_map)
        self.mapping_page.save_requested.connect(lambda: self._profile_action("save"))
        self.settings_page.profile_changed.connect(self._profile_changed)
        self.settings_page.profile_action.connect(self._profile_action)
        self.advanced_page.rules_changed.connect(lambda: self._profile_action("save"))
        self.export_page.action_requested.connect(self._export_action)
        self._refresh_profile_combo(self.profile_store.load_last_profile())

    def _load_profiles(self) -> dict[str, MappingProfile]:
        profiles = self.profile_store.load_all()
        bundled = resource_path("config/profiles.json")
        if set(profiles) == {"Mặc định"} and bundled.exists():
            try:
                payload = json.loads(bundled.read_text(encoding="utf-8"))
                profiles = {name: MappingProfile.from_dict(data) for name, data in payload.items()}
            except (OSError, ValueError, TypeError):
                pass
        return profiles

    def _refresh_profile_combo(self, selected: str) -> None:
        self._profile_guard = True
        self.settings_page.profile_combo.clear()
        self.settings_page.profile_combo.addItems(sorted(self.profiles))
        if selected in self.profiles:
            self.settings_page.profile_combo.setCurrentText(selected)
        self._profile_guard = False
        self._profile_changed(self.settings_page.profile_combo.currentText())

    def _profile_changed(self, name: str) -> None:
        if self._profile_guard or name not in self.profiles:
            return
        profile = self.profiles[name]
        self.settings_page.load_profile(profile)
        self.mapping_page.set_mapping(profile.source_mapping)
        self.advanced_page.load_rules(profile.field_rules)
        self.export_page.filename.setText(profile.output_filename)
        self.export_page.folder.setText(profile.output_folder)
        self.export_page.report.setChecked(profile.export_audit_report)
        self.profile_store.save_last_profile(name)

    def _current_profile(self) -> MappingProfile:
        name = self.settings_page.profile_combo.currentText() or "Mặc định"
        profile = self.profiles.get(name, MappingProfile(profile_name=name))
        self.settings_page.update_profile(profile)
        profile.source_mapping = self.mapping_page.mapping()
        profile.field_rules = self.advanced_page.rules()
        profile.output_filename = self.export_page.filename.text().strip()
        profile.output_folder = self.export_page.folder.text().strip()
        profile.export_audit_report = self.export_page.report.isChecked()
        profile.last_sheet = self.data_page.sheet_combo.currentText()
        profile.header_row = self.data_page.header_spin.value()
        self.profiles[name] = profile
        return profile

    def _profile_action(self, action: str) -> None:
        current_name = self.settings_page.profile_combo.currentText() or "Mặc định"
        if action == "new":
            name, ok = QInputDialog.getText(self, "Tạo cấu hình mới", "Tên cấu hình")
            if ok and name.strip():
                name = name.strip()
                if name in self.profiles:
                    QMessageBox.warning(self, "Cấu hình", "Tên cấu hình đã tồn tại.")
                    return
                self.profiles[name] = MappingProfile(profile_name=name)
                self._refresh_profile_combo(name)
        elif action == "save":
            profile = self._current_profile()
            if profile.item_49_template != DEFAULT_ITEM_49:
                QMessageBox.warning(
                    self,
                    "Cảnh báo Mục 49",
                    "Bạn đang thay đổi cấu trúc tên tài liệu dùng để upload VBDLIS.",
                )
            self.profile_store.save_all(self.profiles)
            self.statusBar().showMessage("Đã lưu cấu hình.", 4000)
        elif action == "delete":
            if len(self.profiles) == 1:
                QMessageBox.warning(self, "Cấu hình", "Cần giữ ít nhất một cấu hình.")
                return
            if QMessageBox.question(self, "Xóa cấu hình", f"Xóa cấu hình '{current_name}'?") == QMessageBox.Yes:
                self.profiles.pop(current_name, None)
                self.profile_store.save_all(self.profiles)
                self._refresh_profile_combo(next(iter(self.profiles)))
        elif action == "export":
            path, _ = QFileDialog.getSaveFileName(self, "Xuất cấu hình ra file", f"{current_name}.json", "Tệp cấu hình (*.json)")
            if path:
                self.profile_store.export_profile(self._current_profile(), path)
        elif action == "import":
            path, _ = QFileDialog.getOpenFileName(self, "Nhập cấu hình từ file", "", "Tệp cấu hình (*.json)")
            if path:
                try:
                    profile = self.profile_store.import_profile(path)
                    name = profile.profile_name or Path(path).stem
                    self.profiles[name] = profile
                    self.profile_store.save_all(self.profiles)
                    self._refresh_profile_combo(name)
                except Exception as exc:
                    QMessageBox.critical(self, "Không thể nhập", str(exc))

    def _source_file_selected(self, path: str) -> None:
        try:
            profile = self._current_profile()
            sheets, selected, header, columns, preview = self.service.source_setup(path, profile.last_sheet)
            self.source_columns = columns
            self.data_page.set_sheets(sheets, selected)
            self.data_page.header_spin.setValue(header)
            self.data_page.show_preview(columns, preview)
            self.mapping_page.set_columns(columns)
            self.mapping_page.set_mapping(profile.source_mapping)
            self.statusBar().showMessage("Đã đọc file nguồn. Hãy kiểm tra ánh xạ cột ở Tab 2.", 5000)
        except Exception as exc:
            logging.exception("Cannot load source")
            self._worker_failed(exc)

    def _load_source_preview(self, path: str, sheet: str, header_row: int) -> None:
        if not path:
            QMessageBox.warning(self, "Thiếu file", "Hãy chọn file dữ liệu trước.")
            return
        try:
            columns, preview = self.service.source_reader.preview(path, sheet, header_row, 50)
            self.source_columns = columns
            self.data_page.show_preview(columns, preview)
            self.mapping_page.set_columns(columns)
            self.current_result = None
        except Exception as exc:
            failure = self.service.failure(exc, DiagnosticContext(path, sheet, header_row), "Đọc xem trước dữ liệu")
            self._worker_failed(failure)

    def _auto_map(self) -> None:
        suggestions = self.service.auto_mapper.suggest(self.source_columns)
        self.mapping_page.set_mapping({**self.mapping_page.mapping(), **suggestions})
        self.statusBar().showMessage(f"Đã gợi ý {len(suggestions)} trường có độ tin cậy cao.", 5000)

    def _process_parameters(self):
        path = self.data_page.file_edit.text()
        if not path:
            raise ValueError("Chưa chọn file dữ liệu nguồn.")
        profile = deepcopy(self._current_profile())
        return (
            path,
            self.data_page.sheet_combo.currentText(),
            self.data_page.header_spin.value(),
            profile,
        )

    def _process_sync(self, parameters):
        path, sheet, header_row, profile = parameters
        return self.service.process(
            path,
            sheet,
            header_row,
            profile,
        )

    def _run_worker(self, function: Callable[[], Any], finished: Callable[[Any], None], message: str) -> None:
        self.current_result = None
        self.export_page.set_diagnostic_files(DiagnosticFiles())
        self.export_page.set_busy(True, message)
        worker = TaskWorker(function)
        worker.signals.finished.connect(lambda value: self._worker_finished(value, finished))
        worker.signals.failed.connect(self._worker_failed)
        self.thread_pool.start(worker)

    def _worker_finished(self, value: Any, callback: Callable[[Any], None]) -> None:
        self.export_page.set_busy(False)
        callback(value)

    def _worker_failed(self, error: Exception) -> None:
        self.export_page.set_busy(False)
        self.current_result = None
        if not isinstance(error, DiagnosticFailure):
            error = self.service.failure(error, DiagnosticContext(
                self.data_page.file_edit.text(), self.data_page.sheet_combo.currentText(),
                self.data_page.header_spin.value()), "Thao tác trong ứng dụng")
        self.export_page.set_diagnostic_files(error.diagnostic_files)
        self.export_page.stats.setText("Thao tác chưa hoàn tất. Xem báo cáo lỗi để biết nguyên nhân và cách xử lý.")
        self.export_page.preview_table.setRowCount(0)
        self.export_page.issues_table.setRowCount(0)
        QMessageBox.critical(self, "Không thể hoàn thành", str(error))

    def _export_action(self, action: str) -> None:
        if action in {"open_log", "open_log_folder"}:
            paths = self.export_page.log_paths
            target = (paths[0].parent if action == "open_log_folder" else paths[0]) if paths else None
            if target is None or not target.exists() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
                QMessageBox.warning(self, "Báo cáo", "Không mở được báo cáo. Kiểm tra file còn tồn tại và ứng dụng mặc định để mở HTML/TXT.")
            return
        try:
            parameters = self._process_parameters()
        except Exception as exc:
            QMessageBox.warning(self, "Thiếu dữ liệu", str(exc))
            return
        if action in {"validate", "preview"}:
            self._run_worker(
                lambda: self._process_sync(parameters),
                self._show_process_result,
                "Đang phân tích, biến đổi và kiểm tra dữ liệu…",
            )
            return

        def export_task():
            result = self._process_sync(parameters)
            if not result.can_export:
                return (result, None)
            profile = parameters[3]
            if not profile.output_folder:
                raise ValueError("Chưa chọn thư mục xuất.")
            exported = self.service.export(
                result,
                profile,
                profile.output_folder,
                profile.output_filename,
            )
            return (result, exported)

        self._run_worker(export_task, self._show_export_result, "Đang tạo và kiểm tra file VBDLIS…")

    def _show_process_result(self, result) -> None:
        self.current_result = result
        self.export_page.show_result(result)
        if result.can_export:
            self.statusBar().showMessage("Kiểm tra đạt — có thể xuất file.", 6000)
        else:
            self.statusBar().showMessage("Còn lỗi — xem bảng cảnh báo để xử lý.", 6000)

    def _show_export_result(self, payload) -> None:
        result, exported = payload
        self._show_process_result(result)
        if exported is None:
            QMessageBox.warning(self, "Chưa thể xuất", "Dữ liệu còn lỗi. Hãy xem bảng cảnh báo.")
            return
        output_path, report_path, verification = exported
        self.profile_store.save_all(self.profiles)
        text = (
            f"ĐÃ HOÀN THÀNH\n\nFile: {output_path}\n"
            f"Số dòng: {result.stats.get('output_rows', 0)}\n"
            f"Cảnh báo: {result.stats.get('warnings', 0)}\n"
            f"Kiểm tra sau lưu: {'Đạt' if verification.get('pass') else 'Không đạt'}"
        )
        if report_path:
            text += f"\nBáo cáo: {report_path}"
        QMessageBox.information(self, "Hoàn thành", text)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_path.parent)))
