from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QProgressBar,
    QVBoxLayout, QWidget)

from launcher_ui.theme import palette, style_for_mode, system_dark_mode
from tools.excel_safety import default_output, open_workbook, timestamp
from tools.qt_worker import Worker
from .models import NormalizeConfig
from .report import export_report
from .service import apply_changes, scan


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Chuẩn hóa Họ tên & Ngày sinh")
        self.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / "assets" / "app_icon.ico")))
        self.resize(1180, 760); self.setMinimumSize(900, 620)
        app = QApplication.instance(); mode = app.property("darkMode") if app else None
        dark = bool(mode) if mode is not None else system_dark_mode()
        self.setStyleSheet(style_for_mode(dark)); self.setPalette(palette(dark))
        self.result = None; self.worker = None; self._build()

    def _build(self):
        root = QWidget(); box = QVBoxLayout(root); box.setContentsMargins(24, 20, 24, 20); box.setSpacing(12)
        title = QLabel("CHUẨN HÓA HỌ TÊN & NGÀY SINH"); title.setObjectName("pageTitle"); box.addWidget(title)
        box.addWidget(QLabel("Utility độc lập: chỉ thay đổi các ô được chọn sau khi xem trước; công thức và ngày không chắc chắn được giữ nguyên."))
        form = QFormLayout(); self.source = QLineEdit(); browse = QPushButton("Chọn…"); browse.clicked.connect(self.browse)
        row = QHBoxLayout(); row.addWidget(self.source, 1); row.addWidget(browse); form.addRow("File Excel", row)
        self.sheet = QComboBox(); form.addRow("Sheet", self.sheet)
        self.start = QSpinBox(); self.start.setRange(1, 1_048_576); self.start.setValue(4); self.start.setMaximumWidth(140)
        self.end = QSpinBox(); self.end.setRange(0, 1_048_576); self.end.setValue(0); self.end.setSpecialValueText("Cuối sheet"); self.end.setMaximumWidth(140)
        range_row = QHBoxLayout(); range_row.addWidget(QLabel("Dòng bắt đầu")); range_row.addWidget(self.start); range_row.addSpacing(20); range_row.addWidget(QLabel("Dòng kết thúc")); range_row.addWidget(self.end); range_row.addStretch()
        form.addRow("Phạm vi chuẩn hóa", range_row)
        self.use_name = QCheckBox("Chuẩn hóa Họ tên"); self.use_name.setChecked(True)
        self.name_column = QLineEdit("B"); self.name_column.setMaximumWidth(120)
        name_row = QHBoxLayout(); name_row.addWidget(self.use_name); name_row.addSpacing(20); name_row.addWidget(QLabel("Cột")); name_row.addWidget(self.name_column); name_row.addStretch(); form.addRow("Họ tên", name_row)
        self.use_birthdate = QCheckBox("Chuẩn hóa Ngày sinh"); self.use_birthdate.setChecked(True)
        self.birthdate_column = QLineEdit("D"); self.birthdate_column.setMaximumWidth(120)
        birth_row = QHBoxLayout(); birth_row.addWidget(self.use_birthdate); birth_row.addSpacing(20); birth_row.addWidget(QLabel("Cột")); birth_row.addWidget(self.birthdate_column); birth_row.addStretch(); form.addRow("Ngày sinh", birth_row)
        self.input_mode = QComboBox(); self.input_mode.addItem("DD/MM/YYYY", "DMY"); self.input_mode.addItem("Tự động phát hiện", "AUTO"); self.input_mode.addItem("MM/DD/YYYY", "MDY"); self.input_mode.addItem("YYYY-MM-DD", "YMD")
        self.output_format = QComboBox(); self.output_format.addItems(["DD/MM/YYYY", "DD-MM-YYYY", "YYYY-MM-DD"])
        self.store_date = QCheckBox("Giữ là kiểu ngày Excel"); self.store_date.setChecked(True)
        format_row = QHBoxLayout(); format_row.addWidget(QLabel("Nguồn")); format_row.addWidget(self.input_mode); format_row.addSpacing(16); format_row.addWidget(QLabel("Đầu ra")); format_row.addWidget(self.output_format); format_row.addSpacing(16); format_row.addWidget(self.store_date); format_row.addStretch(); form.addRow("Định dạng", format_row)
        box.addLayout(form)
        actions = QHBoxLayout(); self.scan_button = QPushButton("QUÉT & XEM TRƯỚC"); self.scan_button.clicked.connect(self.scan_file)
        self.filter = QComboBox(); self.filter.addItems(["Tất cả", "Sẽ thay đổi", "Không thay đổi", "Ngày không hợp lệ", "Ngày mơ hồ", "Ngày thiếu", "Warning"]); self.filter.currentIndexChanged.connect(self.apply_filter)
        self.report_button = QPushButton("Xuất báo cáo"); self.report_button.clicked.connect(self.export); self.report_button.setEnabled(False)
        self.apply_button = QPushButton("Áp dụng chuẩn hóa"); self.apply_button.clicked.connect(self.apply); self.apply_button.setEnabled(False)
        actions.addWidget(self.scan_button); actions.addWidget(self.filter); actions.addStretch(); actions.addWidget(self.report_button); actions.addWidget(self.apply_button); box.addLayout(actions)
        self.summary = QLabel("Chưa quét dữ liệu."); box.addWidget(self.summary)
        self.progress = QProgressBar(); self.progress.setRange(0, 0); self.progress.setVisible(False); self.progress.setAccessibleName("Tiến độ xử lý"); box.addWidget(self.progress)
        self.table = QTableWidget(0, 7); self.table.setHorizontalHeaderLabels(["Chọn", "Dòng", "Trường", "Trước", "Sau", "Trạng thái", "Cảnh báo"]); self.table.horizontalHeader().setStretchLastSection(True); box.addWidget(self.table, 1)
        self.setCentralWidget(root); self.statusBar().showMessage("Quét chỉ đọc dữ liệu và không sửa file.")

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file Excel", "", "Excel (*.xlsx *.xlsm)")
        if not path: return
        self.source.setText(path)
        try:
            wb = open_workbook(path, read_only=True); self.sheet.clear(); self.sheet.addItems(wb.sheetnames); wb.close()
        except Exception as error: self._error(error)

    def config(self):
        if not self.sheet.currentText(): raise ValueError("Hãy chọn file và sheet Excel.")
        end_row = self.end.value() or None
        return NormalizeConfig(Path(self.source.text()), self.sheet.currentText(), self.start.value(), end_row,
                               self.use_name.isChecked(), self.name_column.text().strip().upper(), self.use_birthdate.isChecked(),
                               self.birthdate_column.text().strip().upper(), self.input_mode.currentData(), self.output_format.currentText(), self.store_date.isChecked())

    def _run(self, function, done):
        if self.worker: return
        self._operation_failed = False
        self.setEnabled(False); self.progress.setVisible(True); self.statusBar().showMessage("Đang xử lý…")
        self.worker = Worker(function, self); self.worker.succeeded.connect(done); self.worker.failed.connect(self._worker_error); self.worker.finished.connect(self._finished); self.worker.start()

    def _finished(self):
        worker = self.worker; self.worker = None; self.progress.setVisible(False); self.setEnabled(True)
        if not self._operation_failed and self.statusBar().currentMessage().startswith("Đang xử lý"):
            self.statusBar().showMessage("Hoàn tất.")
        if worker: worker.deleteLater()

    def _worker_error(self, error):
        self._operation_failed = True
        self.statusBar().showMessage("Xử lý thất bại. Xem thông báo và nhật ký.")
        self._error(error)

    def scan_file(self):
        try: config = self.config()
        except Exception as error: self._error(error); return
        self._run(lambda: scan(config), self.show_result)

    def show_result(self, result):
        self.result = result; counts = result.counts(); changes = sum(c.status == "CHANGE" for c in result.changes)
        self.summary.setText(f"Đã quét {result.rows_scanned} dòng · {changes} ô sẽ đổi · {counts.get('BIRTHDATE_AMBIGUOUS', 0)} ngày mơ hồ · {counts.get('BIRTHDATE_INVALID', 0)} ngày lỗi · {counts.get('BIRTHDATE_PARTIAL', 0)} ngày thiếu")
        self.table.setRowCount(len(result.changes))
        for index, change in enumerate(result.changes):
            check = QTableWidgetItem(); check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable); check.setCheckState(Qt.Checked if change.selected else Qt.Unchecked)
            if change.status != "CHANGE": check.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(index, 0, check)
            for column, value in enumerate((change.row, "Họ tên" if change.field == "name" else "Ngày sinh", change.original if change.original is not None else "", change.display_value, change.status, change.warning), 1):
                self.table.setItem(index, column, QTableWidgetItem(str(value)))
        self.report_button.setEnabled(True); self.apply_button.setEnabled(changes > 0); self.apply_filter()
        self.statusBar().showMessage(f"Quét hoàn tất: {result.rows_scanned} dòng, {changes} ô có thể thay đổi.")
        self._log("scan=" + repr(result.counts()) + "\n")

    def apply_filter(self):
        if not self.result: return
        selected = self.filter.currentText()
        for row, change in enumerate(self.result.changes):
            visible = (selected == "Tất cả" or (selected == "Sẽ thay đổi" and change.status == "CHANGE") or
                       (selected == "Không thay đổi" and change.status == "UNCHANGED") or
                       (selected == "Ngày không hợp lệ" and change.status == "INVALID") or
                       (selected == "Ngày mơ hồ" and change.status == "AMBIGUOUS") or
                       (selected == "Ngày thiếu" and change.status == "PARTIAL") or
                       (selected == "Warning" and bool(change.warning)))
            self.table.setRowHidden(row, not visible)

    def selected_changes(self):
        return {(change.row, change.field) for row, change in enumerate(self.result.changes) if self.table.item(row, 0).checkState() == Qt.Checked}

    def export(self):
        if not self.result: return
        path, _ = QFileDialog.getSaveFileName(self, "Lưu báo cáo", str(Path(self.source.text()).with_name("normalization_report.xlsx")), "Excel (*.xlsx)")
        if path: self._run(lambda: export_report(self.result, path), lambda value: QMessageBox.information(self, "Đã xuất báo cáo", str(value)))

    def apply(self):
        selected = self.selected_changes()
        if not selected: self._error("Chưa chọn ô nào để chuẩn hóa."); return
        ambiguous = sum(c.status == "AMBIGUOUS" for c in self.result.changes); invalid = sum(c.status == "INVALID" for c in self.result.changes)
        message = f"Sắp chuẩn hóa {len(selected)} ô.\n{ambiguous} ngày mơ hồ và {invalid} ngày không hợp lệ sẽ được giữ nguyên.\nBackup sẽ được tạo trước khi chỉnh sửa."
        if QMessageBox.question(self, "Xác nhận chuẩn hóa", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        output, _ = QFileDialog.getSaveFileName(self, "Lưu file đã chuẩn hóa", str(default_output(self.source.text(), "normalized")), "Excel (*.xlsx *.xlsm)")
        if output: self._run(lambda: apply_changes(self.result, output, selected), self._applied)

    def _applied(self, value):
        output, backup = value; self._log(f"output={output}\nbackup={backup}\n")
        self.statusBar().showMessage("Chuẩn hóa hoàn tất. File mới và backup đã được tạo.")
        QMessageBox.information(self, "Đã chuẩn hóa", f"File mới: {output}\nBackup: {backup}")

    def _log(self, text):
        folder = Path(os.getenv("APPDATA", str(Path.home()))) / "HPNET_VBDLIS_Tools" / "logs"; folder.mkdir(parents=True, exist_ok=True)
        (folder / f"data_normalization_{timestamp().replace('-', '')}.log").write_text(text, encoding="utf-8")

    def _error(self, error):
        self._log(f"ERROR={error}\n")
        QMessageBox.warning(self, "Không thể xử lý file Excel", f"{error}\n\nHãy kiểm tra file có đang mở, bị khóa hoặc bạn không có quyền truy cập.")
