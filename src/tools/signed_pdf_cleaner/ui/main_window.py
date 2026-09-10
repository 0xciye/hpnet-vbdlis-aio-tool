import os
import json
from pathlib import Path
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QComboBox, QTableWidget, 
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QIcon

from tools.signed_pdf_cleaner.core.scanner import FileScanner, TARGET_ALL, TARGET_PAIRS, TARGET_ORPHAN_SIGNED
from tools.signed_pdf_cleaner.core.processor import FileProcessor
from tools.signed_pdf_cleaner.utils.logger import AppLogger
from tools.signed_pdf_cleaner.core.models import FileActionPlan, ActionType, ProcessStatus
from tools.runtime_paths import tool_data_dir, tool_settings_path
from launcher_ui.theme import palette, style_for_mode, system_dark_mode

SETTINGS_FILE = "config.json"

class Worker(QThread):
    progress = Signal(int, int)
    finished = Signal()
    error = Signal(str)

    def __init__(self, plans, processor, logger):
        super().__init__()
        self.plans = plans
        self.processor = processor
        self.logger = logger
        self.is_running = True

    def run(self):
        total = len(self.plans)
        for i, plan in enumerate(self.plans):
            if not self.is_running:
                break
            try:
                self.processor.process_plan(plan)
                self.logger.log_plan_result(plan)
            except Exception as e:
                plan.status = ProcessStatus.ERROR
                plan.error_message = str(e)
            self.progress.emit(i + 1, total)
        self.finished.emit()

    def stop(self):
        self.is_running = False


class ScanWorker(QThread):
    progress = Signal(int, int)
    completed = Signal(object)
    error = Signal(str)

    def __init__(self, scanner, folder, recursive, target_mode):
        super().__init__()
        self.scanner = scanner
        self.folder = folder
        self.recursive = recursive
        self.target_mode = target_mode

    def run(self):
        try:
            plans = self.scanner.scan_directory(
                self.folder,
                self.recursive,
                self.target_mode,
                progress_callback=lambda done, total: self.progress.emit(done, total),
            )
            self.completed.emit(plans)
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HPNet - Lọc & Đổi tên văn bản đã ký")
        self.resize(900, 600)
        self.setAcceptDrops(True)
        app = QApplication.instance(); mode = app.property("darkMode") if app else None
        dark = bool(mode) if mode is not None else system_dark_mode()
        self.setStyleSheet(style_for_mode(dark))
        self.setPalette(palette(dark))
        
        # Mod: Use __file__ resolution for unified onedir building instead of MEIPASS (Behavior preserved)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, 'app_icon.ico')
        
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.plans = []
        self.worker = None
        self.scan_worker = None
        self.settings_file = tool_settings_path("PDF Cleaner", SETTINGS_FILE, Path(base_dir), {"folder", "recursive", "delete_mode"})
        self.logger = AppLogger(str(tool_data_dir("PDF Cleaner") / "logs"))
        self.setup_ui()
        self.load_settings()
        self.update_target_ui(reset_preview=False)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 1. Folder Selection
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Thư mục:"))
        self.txt_folder = QLineEdit()
        self.txt_folder.setReadOnly(True)
        folder_layout.addWidget(self.txt_folder)
        
        btn_browse = QPushButton("Chọn...")
        btn_browse.clicked.connect(self.browse_folder)
        folder_layout.addWidget(btn_browse)
        main_layout.addLayout(folder_layout)

        # 2. Processing target
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Mục tiêu xử lý:"))
        self.cmb_target_mode = QComboBox()
        self.cmb_target_mode.addItem("Cả cặp và file ký đơn độc", TARGET_ALL)
        self.cmb_target_mode.addItem("Chỉ cặp có file gốc + file ký", TARGET_PAIRS)
        self.cmb_target_mode.addItem("Chỉ file ký không có file gốc: xóa hậu tố", TARGET_ORPHAN_SIGNED)
        self.cmb_target_mode.setToolTip("Giao diện và danh sách xem trước sẽ đổi theo mục tiêu đã chọn.")
        self.cmb_target_mode.currentIndexChanged.connect(self.update_target_ui)
        target_layout.addWidget(self.cmb_target_mode, 1)
        main_layout.addLayout(target_layout)

        # 3. Options
        options_layout = QHBoxLayout()
        self.chk_recursive = QCheckBox("Bao gồm thư mục con")
        options_layout.addWidget(self.chk_recursive)
        self.lbl_delete_suffix = QLabel("Hậu tố file cũ cần xóa:")
        options_layout.addWidget(self.lbl_delete_suffix)
        self.txt_delete_suffix = QLineEdit(".pdf"); self.txt_delete_suffix.setMaximumWidth(220)
        self.txt_delete_suffix.setToolTip("Nhập một hoặc nhiều hậu tố, cách nhau bằng dấu phẩy. Có thể bỏ phần .pdf.")
        options_layout.addWidget(self.txt_delete_suffix)
        self.lbl_signed_suffix = QLabel("Hậu tố file ký cần giữ:")
        options_layout.addWidget(self.lbl_signed_suffix)
        self.txt_signed_suffix = QLineEdit(".signed.pdf"); self.txt_signed_suffix.setMaximumWidth(240)
        self.txt_signed_suffix.setToolTip("Nhập một hoặc nhiều hậu tố, cách nhau bằng dấu phẩy. Có thể bỏ phần .pdf.")
        options_layout.addWidget(self.txt_signed_suffix)
        
        self.lbl_delete_mode = QLabel("Chế độ xóa:")
        options_layout.addWidget(self.lbl_delete_mode)
        self.cmb_delete_mode = QComboBox()
        self.cmb_delete_mode.addItems(["Đưa vào Recycle Bin", "Xóa vĩnh viễn"])
        options_layout.addWidget(self.cmb_delete_mode)
        options_layout.addStretch()
        main_layout.addLayout(options_layout)

        self.suffix_hint = QLabel()
        self.suffix_hint.setWordWrap(True)
        self.suffix_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        main_layout.addWidget(self.suffix_hint)

        # 3. Stats
        self.lbl_stats = QLabel("Sẵn sàng.")
        main_layout.addWidget(self.lbl_stats)

        # 4. Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_scan = QPushButton("Quét / Xem trước")
        self.btn_scan.clicked.connect(self.scan_files)
        
        self.btn_process = QPushButton("Thực hiện xử lý")
        self.btn_process.clicked.connect(self.process_files)
        self.btn_process.setEnabled(False)
        
        self.btn_export = QPushButton("Xuất log CSV")
        self.btn_export.clicked.connect(self.export_csv)
        self.btn_export.setEnabled(False)
        
        btn_layout.addWidget(self.btn_scan)
        btn_layout.addWidget(self.btn_process)
        btn_layout.addWidget(self.btn_export)
        main_layout.addLayout(btn_layout)

        # 5. Table Preview
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["File signed", "File chưa ký", "Hành động", "Tên sau xử lý", "Trạng thái"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.table)

        # 6. Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

    def update_target_ui(self, _index=None, reset_preview=True):
        mode = self.cmb_target_mode.currentData()
        orphan_only = mode == TARGET_ORPHAN_SIGNED
        for widget in (self.lbl_delete_suffix, self.txt_delete_suffix, self.lbl_delete_mode, self.cmb_delete_mode):
            widget.setVisible(not orphan_only)

        self.lbl_signed_suffix.setText("Hậu tố ký cần bỏ (vẫn giữ .pdf):" if orphan_only else "Hậu tố file ký cần giữ:")
        headers = (["File cần xóa hậu tố", "File gốc", "Hành động", "Tên mới", "Trạng thái"] if orphan_only else
                   ["File ký cần giữ", "File cũ sẽ xóa", "Hành động", "Tên sau xử lý", "Trạng thái"])
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setColumnHidden(1, orphan_only)
        if orphan_only:
            self.suffix_hint.setText("Ví dụ nhập .signed.pdf: A.signed.pdf → A.pdf. Chỉ bỏ .signed, luôn giữ định dạng .pdf và không xóa file nào.")
            self.btn_scan.setText("Quét file cần xóa hậu tố")
            self.btn_process.setText("Xóa hậu tố")
        elif mode == TARGET_PAIRS:
            self.suffix_hint.setText("Chỉ tìm theo cặp. Ví dụ: xóa A.pdf, sau đó đổi A.signed.pdf thành A.pdf.")
            self.btn_scan.setText("Quét cặp file")
            self.btn_process.setText("Xóa file cũ và đổi tên")
        else:
            self.suffix_hint.setText("Xử lý cả cặp file và file ký đơn độc. Có thể nhập nhiều hậu tố, cách nhau bằng dấu phẩy.")
            self.btn_scan.setText("Quét / Xem trước")
            self.btn_process.setText("Thực hiện xử lý")

        if reset_preview:
            self.plans = []
            self.table.setRowCount(0)
            self.btn_process.setEnabled(False)
            self.btn_export.setEnabled(False)
            self.lbl_stats.setText("Đã đổi mục tiêu xử lý. Hãy quét lại.")

    def load_settings(self):
        if self.settings_file.exists():
            try:
                with self.settings_file.open('r', encoding='utf-8-sig') as f:
                    settings = json.load(f)
                    self.txt_folder.setText(settings.get('folder', ''))
                    self.chk_recursive.setChecked(settings.get('recursive', False))
                    self.cmb_delete_mode.setCurrentIndex(settings.get('delete_mode', 0))
                    self.txt_delete_suffix.setText(settings.get('delete_suffix', '.pdf'))
                    self.txt_signed_suffix.setText(settings.get('signed_suffix', '.signed.pdf'))
                    target_mode = settings.get('target_mode', TARGET_ALL)
                    index = self.cmb_target_mode.findData(target_mode)
                    self.cmb_target_mode.setCurrentIndex(index if index >= 0 else 0)
            except:
                pass

    def save_settings(self):
        settings = {
            'folder': self.txt_folder.text(),
            'recursive': self.chk_recursive.isChecked(),
            'delete_mode': self.cmb_delete_mode.currentIndex(),
            'delete_suffix': self.txt_delete_suffix.text(),
            'signed_suffix': self.txt_signed_suffix.text(),
            'target_mode': self.cmb_target_mode.currentData()
        }
        with self.settings_file.open('w', encoding='utf-8') as f:
            json.dump(settings, f)

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.txt_folder.setText(path)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        if folder:
            self.txt_folder.setText(folder)

    def scan_files(self):
        folder = self.txt_folder.text()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục hợp lệ.")
            return

        target_mode = self.cmb_target_mode.currentData()
        delete_suffix = ".pdf" if target_mode == TARGET_ORPHAN_SIGNED else self.txt_delete_suffix.text()
        try:
            scanner = FileScanner(delete_suffix=delete_suffix, signed_suffix=self.txt_signed_suffix.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Hậu tố không hợp lệ", str(exc))
            return
        self.plans = []
        self.table.setRowCount(0)
        self.btn_scan.setEnabled(False)
        self.btn_process.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.cmb_target_mode.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.lbl_stats.setText("Đang quét: 0 file...")

        self.scan_worker = ScanWorker(scanner, folder, self.chk_recursive.isChecked(), target_mode)
        self.scan_worker.progress.connect(self.on_scan_progress)
        self.scan_worker.completed.connect(self.on_scan_finished)
        self.scan_worker.error.connect(self.on_scan_error)
        self.scan_worker.finished.connect(self.on_scan_thread_finished)
        self.scan_worker.start()

    def on_scan_progress(self, done, total):
        total = max(total, 1)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(min(done, total))
        percent = min(100, int(done * 100 / total)) if total else 100
        self.lbl_stats.setText(f"Đang quét: {done}/{total} file ({percent}%)")

    def on_scan_finished(self, plans):
        self.plans = plans
        self.update_table()
        self.update_stats()
        has_ready = any(p.status == ProcessStatus.READY for p in self.plans)
        self.btn_process.setEnabled(has_ready)
        self.btn_export.setEnabled(bool(self.plans))
        self.progress_bar.setValue(self.progress_bar.maximum())

    def on_scan_error(self, message):
        self.lbl_stats.setText(f"Lỗi khi quét: {message}")
        QMessageBox.warning(self, "Lỗi quét", message)

    def on_scan_thread_finished(self):
        self.btn_scan.setEnabled(True)
        self.cmb_target_mode.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.scan_worker = None

    def update_table(self):
        self.table.setRowCount(0)
        for row, plan in enumerate(self.plans):
            self.table.insertRow(row)
            
            signed_name = plan.signed_path.name if plan.signed_path else "Không có"
            unsigned_name = plan.unsigned_path.name if plan.unsigned_path else "Không có"
            target_name = plan.target_path.name if plan.target_path else ""
            status_text = plan.status.value
            if plan.error_message:
                status_text += f" - {plan.error_message}"
            elif plan.warning_message:
                status_text += f" - {plan.warning_message}"
                
            item_signed = QTableWidgetItem(signed_name)
            item_unsigned = QTableWidgetItem(unsigned_name)
            item_action = QTableWidgetItem(plan.action.value)
            item_target = QTableWidgetItem(target_name)
            item_status = QTableWidgetItem(status_text)
            
            if plan.status == ProcessStatus.SKIPPED:
                color = QColor(200, 200, 200) # Gray
            elif plan.status == ProcessStatus.WARNING:
                color = QColor(255, 200, 0) # Orange
            elif plan.status == ProcessStatus.ERROR:
                color = QColor(255, 100, 100) # Red
            elif plan.status == ProcessStatus.READY:
                color = QColor(255, 255, 255)
            elif plan.status == ProcessStatus.COMPLETED:
                color = QColor(100, 255, 100) # Green
            else:
                color = QColor(255, 255, 255)
                
            for col, item in enumerate([item_signed, item_unsigned, item_action, item_target, item_status]):
                item.setBackground(color)
                self.table.setItem(row, col, item)

    def update_stats(self):
        total_signed = sum(1 for p in self.plans if p.signed_path is not None)
        has_unsigned = sum(1 for p in self.plans if p.unsigned_path and p.signed_path)
        only_signed = sum(1 for p in self.plans if p.signed_path and not p.unsigned_path)
        only_unsigned = sum(1 for p in self.plans if p.unsigned_path and not p.signed_path)
        ready = sum(1 for p in self.plans if p.status == ProcessStatus.READY)
        errors = sum(1 for p in self.plans if p.status in (ProcessStatus.ERROR, ProcessStatus.WARNING))

        mode = self.cmb_target_mode.currentData()
        if mode == TARGET_ORPHAN_SIGNED:
            stats = f"File cần xóa hậu tố: {total_signed} | Sẵn sàng: {ready} | Cảnh báo: {errors}"
        elif mode == TARGET_PAIRS:
            stats = f"Cặp file tìm thấy: {has_unsigned} | Sẵn sàng: {ready} | Cảnh báo: {errors}"
        else:
            stats = (f"File ký tìm thấy: {total_signed} | Có file gốc: {has_unsigned} | "
                     f"File ký đơn độc: {only_signed} | File gốc đơn độc (bỏ qua): {only_unsigned} | "
                     f"Lỗi/Xung đột: {errors}")
        self.lbl_stats.setText(stats)

    def process_files(self):
        ready_plans = [p for p in self.plans if p.status == ProcessStatus.READY]
        if not ready_plans:
            QMessageBox.information(self, "Thông báo", "Không có file nào cần xử lý.")
            return
            
        deletes_old_files = any(p.action == ActionType.DELETE_AND_RENAME for p in ready_plans)
        use_recycle_bin = self.cmb_delete_mode.currentIndex() == 0
        if deletes_old_files and not use_recycle_bin:
            reply = QMessageBox.question(self, 'Xác nhận', 
                                         'Bạn chọn Xóa Vĩnh Viễn. File cũ sẽ bị xóa hoàn toàn. Bạn có chắc chắn không?',
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        processor = FileProcessor(use_recycle_bin=use_recycle_bin)
        
        self.btn_scan.setEnabled(False)
        self.btn_process.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(ready_plans))
        
        self.worker = Worker(ready_plans, processor, self.logger)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, value, total):
        self.progress_bar.setValue(value)
        self.lbl_stats.setText(f"Đang xử lý {value} / {total}")
        
    def on_finished(self):
        self.btn_scan.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.update_table()
        
        completed = sum(1 for p in self.plans if p.status == ProcessStatus.COMPLETED)
        errors = sum(1 for p in self.plans if p.status == ProcessStatus.ERROR)
        
        msg = f"HOÀN THÀNH\nFile xử lý thành công: {completed}\nLỗi: {errors}"
        recycled = any(p.status == ProcessStatus.COMPLETED and p.action == ActionType.DELETE_AND_RENAME for p in self.plans)
        if recycled and self.cmb_delete_mode.currentIndex() == 0:
            msg += "\n\nCác file cũ đã được chuyển vào Recycle Bin."
            
        QMessageBox.information(self, "Kết quả", msg)
        self.update_stats()
        
    def export_csv(self):
        if not self.plans:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Lưu file CSV", "report.csv", "CSV Files (*.csv)")
        if file_path:
            self.logger.export_csv(self.plans, file_path)
            QMessageBox.information(self, "Thành công", f"Đã xuất báo cáo ra {file_path}")
