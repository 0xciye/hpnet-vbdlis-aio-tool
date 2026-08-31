from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


PREVIEW_COLUMNS = [
    ("A", "STT"), ("H", "Họ tên"), ("I", "CCCD"), ("J", "Ngày sinh"),
    ("N", "Vai trò"), ("T", "Số tờ"), ("U", "Số thửa"), ("Y", "Diện tích"),
    ("X", "Xứ đồng"), ("C", "Mục 2"), ("AX", "Mục 49"),
]

_SEV_COLORS = {
    "ERROR":   (QColor("#fef2f2"), QColor("#b91c1c")),
    "WARNING": (QColor("#fffbeb"), QColor("#92400e")),
    "INFO":    (QColor("#eff6ff"), QColor("#1e40af")),
}

_SEV_LABELS = {
    "ERROR":   "LỖI",
    "WARNING": "CẢNH BÁO",
    "INFO":    "THÔNG TIN",
}


class ExportPage(QWidget):
    action_requested = Signal(str)

    def __init__(self):
        super().__init__()

        # Cấu hình file xuất
        self.filename = QLineEdit("VBDLIS_Output.xlsx")
        self.filename.setPlaceholderText("Tên file kết quả (.xlsx tự thêm nếu thiếu)")
        self.folder = QLineEdit()
        self.folder.setPlaceholderText("Chưa chọn thư mục…")
        choose_folder = QPushButton("📁  Chọn thư mục…")
        choose_folder.clicked.connect(self._choose_folder)
        self.report = QCheckBox("Xuất báo cáo kiểm tra (5 trang tính)")
        self.report.setChecked(True)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(choose_folder)

        form = QGridLayout()
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(16)
        form.setColumnMinimumWidth(0, 90)
        form.addWidget(QLabel("Tên file"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        form.addWidget(self.filename, 0, 1)
        form.addWidget(QLabel("Thư mục"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        form.addLayout(folder_row, 1, 1)
        form.addWidget(self.report, 2, 1)

        # Các nút thao tác
        btn_validate = QPushButton("🔍  Kiểm tra")
        btn_preview  = QPushButton("👁  Xem trước")
        btn_export   = QPushButton("✅  Tạo file VBDLIS")
        btn_export.setProperty("accent", True)
        btn_export.setMinimumHeight(34)

        for btn, action in ((btn_validate, "validate"), (btn_preview, "preview"), (btn_export, "export")):
            btn.clicked.connect(lambda _=False, v=action: self.action_requested.emit(v))

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(btn_validate)
        buttons.addWidget(btn_preview)
        buttons.addStretch(1)
        buttons.addWidget(btn_export)

        self.log_paths = []
        self.log_status = QLabel("Báo cáo lỗi tự động được lưu sau mỗi lần kiểm tra, kể cả khi chưa xuất được.")
        self.log_status.setWordWrap(True)
        self.log_status.setTextFormat(Qt.PlainText)
        self.open_log = QPushButton("Mở báo cáo lỗi")
        self.open_log_folder = QPushButton("Thư mục báo cáo")
        self.open_log.setEnabled(False)
        self.open_log_folder.setEnabled(False)
        self.open_log.clicked.connect(lambda: self.action_requested.emit("open_log"))
        self.open_log_folder.clicked.connect(lambda: self.action_requested.emit("open_log_folder"))
        log_row = QHBoxLayout()
        log_row.addWidget(self.log_status, 1)
        log_row.addWidget(self.open_log)
        log_row.addWidget(self.open_log_folder)

        # Thanh tiến trình & thống kê
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)

        self.stats = QLabel("Chưa kiểm tra dữ liệu.")
        self.stats.setWordWrap(True)
        self.stats.setStyleSheet(
            "background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px;"
            "padding: 8px 12px; color: #374151; font-size: 9pt;"
        )

        # Đường kẻ phân cách
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #e2e8f0;")

        # Bảng xem trước kết quả
        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.preview_table.verticalHeader().setDefaultSectionSize(26)

        preview_label = QLabel("Xem trước dữ liệu sau xử lý")
        preview_label.setStyleSheet("font-weight: 600; color: #374151; padding-bottom: 4px;")
        preview_box = QWidget()
        pv_layout = QVBoxLayout(preview_box)
        pv_layout.setContentsMargins(0, 0, 0, 0)
        pv_layout.setSpacing(6)
        pv_layout.addWidget(preview_label)
        pv_layout.addWidget(self.preview_table)

        # Bảng lỗi / cảnh báo
        self.issues_table = QTableWidget()
        self.issues_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.issues_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.issues_table.verticalHeader().setDefaultSectionSize(26)

        issues_label = QLabel("Lỗi / Cảnh báo / Thông tin")
        issues_label.setStyleSheet("font-weight: 600; color: #374151; padding-bottom: 4px;")
        issue_box = QWidget()
        iss_layout = QVBoxLayout(issue_box)
        iss_layout.setContentsMargins(0, 0, 0, 0)
        iss_layout.setSpacing(6)
        iss_layout.addWidget(issues_label)
        iss_layout.addWidget(self.issues_table)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(preview_box)
        splitter.addWidget(issue_box)
        splitter.setSizes([500, 500])

        # Bố cục chính
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.progress)
        layout.addWidget(self.stats)
        layout.addLayout(log_row)
        layout.addWidget(sep)
        layout.addWidget(splitter, 1)

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất")
        if path:
            self.folder.setText(path)

    def set_busy(self, busy: bool, text: str = "") -> None:
        self.open_log.setEnabled(not busy and bool(self.log_paths))
        self.open_log_folder.setEnabled(not busy and bool(self.log_paths))
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, 0)
            if text:
                self.stats.setText(f"⏳  {text}")
        else:
            self.progress.setRange(0, 100)

    def set_diagnostic_files(self, files) -> None:
        self.log_paths = list(files.paths)
        self.open_log.setEnabled(bool(self.log_paths))
        self.open_log_folder.setEnabled(bool(self.log_paths))
        if files.error:
            self.log_status.setText(files.error + (" Bản chữ đã lưu; dùng nút Mở báo cáo." if self.log_paths else ""))
            self.log_status.setStyleSheet("color: #b91c1c;")
        elif self.log_paths:
            self.log_status.setText("Đã lưu báo cáo chi tiết. Bấm Mở báo cáo lỗi để tìm ô cần sửa và cách xử lý.")
            self.log_status.setStyleSheet("color: #166534;")
        else:
            self.log_status.setText("Chưa có báo cáo của lần chạy này.")
            self.log_status.setStyleSheet("")
        self.log_status.setToolTip("\n".join(str(p) for p in self.log_paths))

    def show_result(self, result, preview_limit: int = 100) -> None:
        self.set_diagnostic_files(result.diagnostic_files)
        stats = result.stats
        error_count   = stats.get("errors", 0)
        warning_count = stats.get("warnings", 0)

        status_icon = "✅" if result.can_export else "❌"
        status_text = (
            "Sẵn sàng xuất file"
            if result.can_export
            else f"Còn {error_count} lỗi — phải sửa trước khi xuất"
        )

        parts = [
            f"Hộ: {stats.get('households', 0)}",
            f"Người: {stats.get('people', 0)}",
            f"Thửa: {stats.get('parcels', 0)}",
            f"Dòng kết quả: {stats.get('output_rows', 0)}",
            f"CCCD hợp lệ: {stats.get('valid_cccd', 0)}",
            f"Có GCN: {stats.get('with_gcn', 0)}",
            f"Chưa có GCN: {stats.get('without_gcn', 0)}",
            f"Dùng địa chỉ thay xứ đồng: {stats.get('location_fallbacks', 0)}",
            f"Lỗi: {error_count}",
            f"Cảnh báo: {warning_count}",
        ]
        if stats.get("summary_rows_skipped", 0):
            parts.append(f"Dòng tổng hợp đã bỏ qua: {stats['summary_rows_skipped']}")
        if stats.get("households_skipped", 0) or stats.get("people_skipped", 0):
            parts.append(f"Đã bỏ: {stats.get('households_skipped', 0)} hộ / {stats.get('people_skipped', 0)} người / {stats.get('parcels_skipped', 0)} thửa")
        self.stats.setText(f"{status_icon}  {status_text}\n{' | '.join(parts)}")
        color = "#f0fdf4" if result.can_export else "#fef2f2"
        border = "#86efac" if result.can_export else "#fca5a5"
        self.stats.setStyleSheet(
            f"background: {color}; border: 1px solid {border}; border-radius: 4px;"
            "padding: 8px 12px; color: #1f2937; font-size: 9pt;"
        )

        # Bảng xem trước
        rows = result.rows[:preview_limit]
        self.preview_table.setColumnCount(len(PREVIEW_COLUMNS))
        self.preview_table.setHorizontalHeaderLabels([label for _, label in PREVIEW_COLUMNS])
        self.preview_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, (key, _) in enumerate(PREVIEW_COLUMNS):
                value = row.get(key, "")
                self.preview_table.setItem(row_idx, col_idx, QTableWidgetItem("" if value is None else str(value)))
        self.preview_table.resizeColumnsToContents()

        # Bảng lỗi/cảnh báo với màu theo mức độ
        self.issues_table.setColumnCount(7)
        self.issues_table.setHorizontalHeaderLabels(
            ["Mức độ", "Mã", "Dòng nguồn", "Hộ", "Người", "Thông báo", "Giá trị"]
        )
        visible_issues = result.issues[:1000]
        self.issues_table.setRowCount(len(visible_issues))
        if len(result.issues) > len(visible_issues) and not result.diagnostic_files.error:
            self.log_status.setText(self.log_status.text() + f" Bảng chỉ hiện 1.000/{len(result.issues)} mục; báo cáo lưu đủ tất cả.")
        bold = QFont()
        bold.setBold(True)
        for row_idx, issue in enumerate(visible_issues):
            sev = str(issue.severity.value)
            sev_display = _SEV_LABELS.get(sev, sev)
            values = [sev_display, issue.code, issue.source_row, issue.household,
                      issue.person, issue.message, issue.value]
            bg, fg = _SEV_COLORS.get(sev, (QColor("#ffffff"), QColor("#1f2937")))
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setBackground(bg)
                item.setForeground(fg)
                if col_idx == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFont(bold)
                self.issues_table.setItem(row_idx, col_idx, item)
        self.issues_table.resizeColumnsToContents()
