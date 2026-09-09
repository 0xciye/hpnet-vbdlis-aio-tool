from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


from .widgets import ComboBox as QComboBox


class DataPage(QWidget):
    load_requested = Signal(str, str, int)
    file_selected = Signal(str)

    def __init__(self):
        super().__init__()

        # Thanh thông tin
        info = QLabel(
            "Chọn file Excel nguồn, trang tính và dòng tiêu đề. "
            "Bảng xem trước chỉ đọc — file nguồn không bị chỉnh sửa."
        )
        info.setProperty("info", True)
        info.setWordWrap(True)

        # Chọn file
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText("Chưa chọn file…")
        choose = QPushButton("📂  Chọn file Excel…")
        choose.clicked.connect(self._choose_file)
        file_row = QHBoxLayout()
        file_row.setSpacing(8)
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(choose)

        self.sheet_combo = QComboBox()
        self.header_spin = QSpinBox()
        self.header_spin.setRange(1, 1000)
        self.header_spin.setValue(1)
        self.header_spin.setFixedWidth(80)
        self.header_spin.setToolTip("Số dòng trong Excel chứa tên các cột; không phải số dòng dữ liệu. Ví dụ tên cột ở dòng 6 thì nhập 6.")

        form = QFormLayout()
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(16)
        form.addRow("File dữ liệu", file_row)
        form.addRow("Trang tính", self.sheet_combo)
        header_row = QHBoxLayout()
        header_row.addWidget(self.header_spin)
        hint = QLabel("Dòng chứa tên cột trong Excel. Ví dụ: tên cột ở dòng 6 → nhập 6.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        header_row.addWidget(hint, 1)
        form.addRow("Dòng tiêu đề", header_row)

        read = QPushButton("▶  Đọc dữ liệu")
        read.setProperty("accent", True)
        read.setMinimumHeight(40)
        read.clicked.connect(
            lambda: self.load_requested.emit(
                self.file_edit.text(), self.sheet_combo.currentText(), self.header_spin.value()
            )
        )

        # Bảng xem trước
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.preview_status = QLabel("Chưa có dữ liệu xem trước. Chọn file Excel, kiểm tra trang tính rồi bấm Đọc dữ liệu.")
        self.preview_status.setWordWrap(True)
        self.preview_status.setStyleSheet("color: palette(mid); padding: 4px 0;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(info)
        layout.addLayout(form)
        layout.addWidget(read, 0)
        layout.addWidget(self.preview_status)
        layout.addWidget(self.table, 1)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file dữ liệu", "", "Excel (*.xlsx *.xlsm)")
        if path:
            self.file_edit.setText(path)
            self.file_selected.emit(path)

    def set_sheets(self, sheets: list[str], selected: str) -> None:
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        self.sheet_combo.addItems(sheets)
        self.sheet_combo.setCurrentText(selected)
        self.sheet_combo.blockSignals(False)

    def show_preview(self, headers, rows: list[dict]) -> None:
        self.preview_status.setText(f"Xem trước {len(rows)} dòng • {len(headers)} cột • Chỉ đọc. Tiếp tục sang tab 2 để kiểm tra ánh xạ cột.")
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels([column.display for column in headers])
        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, column in enumerate(headers):
                value = row.get(column.letter, "")
                self.table.setItem(row_idx, col_idx, QTableWidgetItem("" if value is None else str(value)))
        self.table.resizeColumnsToContents()
