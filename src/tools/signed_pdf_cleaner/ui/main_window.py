import os
import json
from pathlib import Path
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QCheckBox, QComboBox, QTableWidget, 
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QIcon

from tools.signed_pdf_cleaner.core.scanner import FileScanner
from tools.signed_pdf_cleaner.core.processor import FileProcessor
from tools.signed_pdf_cleaner.utils.logger import AppLogger
from tools.signed_pdf_cleaner.core.models import FileActionPlan, ActionType, ProcessStatus
from tools.runtime_paths import tool_data_dir, tool_settings_path

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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HPNet - Lọc & Đổi tên văn bản đã ký")
        self.resize(900, 600)
        self.setAcceptDrops(True)
        
        # Mod: Use __file__ resolution for unified onedir building instead of MEIPASS (Behavior preserved)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, 'icon.ico')
        
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.plans = []
        self.worker = None
        self.settings_file = tool_settings_path("PDF Cleaner", SETTINGS_FILE, Path(base_dir), {"folder", "recursive", "delete_mode"})
        self.logger = AppLogger(str(tool_data_dir("PDF Cleaner") / "logs"))
        self.setup_ui()
        self.load_settings()

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

        # 2. Options
        options_layout = QHBoxLayout()
        self.chk_recursive = QCheckBox("Bao gồm thư mục con")
        options_layout.addWidget(self.chk_recursive)
        
        options_layout.addWidget(QLabel("Chế độ xóa:"))
        self.cmb_delete_mode = QComboBox()
        self.cmb_delete_mode.addItems(["Đưa vào Recycle Bin", "Xóa vĩnh viễn"])
        options_layout.addWidget(self.cmb_delete_mode)
        options_layout.addStretch()
        main_layout.addLayout(options_layout)

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

    def load_settings(self):
        if self.settings_file.exists():
            try:
                with self.settings_file.open('r', encoding='utf-8-sig') as f:
                    settings = json.load(f)
                    self.txt_folder.setText(settings.get('folder', ''))
                    self.chk_recursive.setChecked(settings.get('recursive', False))
                    self.cmb_delete_mode.setCurrentIndex(settings.get('delete_mode', 0))
            except:
                pass

    def save_settings(self):
        settings = {
            'folder': self.txt_folder.text(),
            'recursive': self.chk_recursive.isChecked(),
            'delete_mode': self.cmb_delete_mode.currentIndex()
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

        scanner = FileScanner()
        self.plans = scanner.scan_directory(folder, self.chk_recursive.isChecked())
        
        self.update_table()
        self.update_stats()
        
        has_ready = any(p.status == ProcessStatus.READY for p in self.plans)
        self.btn_process.setEnabled(has_ready)
        self.btn_export.setEnabled(len(self.plans) > 0)

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
        errors = sum(1 for p in self.plans if p.status in (ProcessStatus.ERROR, ProcessStatus.WARNING))
        
        stats = (f"File signed tìm thấy: {total_signed} | "
                 f"Có bản chưa ký: {has_unsigned} | "
                 f"Chỉ có bản signed: {only_signed} | "
                 f"Chỉ có bản chưa ký (bỏ qua): {only_unsigned} | "
                 f"Lỗi/Xung đột: {errors}")
        self.lbl_stats.setText(stats)

    def process_files(self):
        ready_plans = [p for p in self.plans if p.status == ProcessStatus.READY]
        if not ready_plans:
            QMessageBox.information(self, "Thông báo", "Không có file nào cần xử lý.")
            return
            
        use_recycle_bin = self.cmb_delete_mode.currentIndex() == 0
        if not use_recycle_bin:
            reply = QMessageBox.question(self, 'Xác nhận', 
                                         'Bạn chọn Xóa Vĩnh Viễn. File chưa ký sẽ bị xóa hoàn toàn. Bạn có chắc chắn không?',
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
        if self.cmb_delete_mode.currentIndex() == 0:
            msg += "\n\nCác file chưa ký đã được chuyển vào Recycle Bin."
            
        QMessageBox.information(self, "Kết quả", msg)
        self.update_stats()
        
    def export_csv(self):
        if not self.plans:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Lưu file CSV", "report.csv", "CSV Files (*.csv)")
        if file_path:
            self.logger.export_csv(self.plans, file_path)
            QMessageBox.information(self, "Thành công", f"Đã xuất báo cáo ra {file_path}")
