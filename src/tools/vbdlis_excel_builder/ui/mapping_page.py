from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


from .widgets import ComboBox as QComboBox


SOURCE_FIELDS = [
    ("household_stt", "STT hộ", True),
    ("person_name", "Họ và tên", True),
    ("cccd", "CCCD", True),
    ("birth_date", "Ngày sinh", False),
    ("gender", "Giới tính", False),
    ("sheet_number", "Số tờ", True),
    ("parcel_number", "Số thửa", True),
    ("area", "Diện tích", True),
    ("land_location", "Xứ đồng/Vị trí", False),
    ("land_type", "Loại đất", False),
    ("land_origin", "Nguồn gốc sử dụng", False),
    ("use_form", "Hình thức sử dụng", False),
    ("use_term", "Thời hạn sử dụng", False),
    ("gcn_issue_number", "Số phát hành GCN", False),
    ("gcn_issue_date", "Ngày cấp GCN", False),
    ("gcn_registry_number", "Số vào sổ GCN", False),
    ("gcn_type", "Loại GCN", False),
    ("gcn_authority", "Cơ quan cấp GCN", False),
]

_REQUIRED_BG = QColor("#eff6ff")
_REQUIRED_FG = QColor("#1e3a5f")


class MappingPage(QWidget):
    auto_requested = Signal()
    save_requested = Signal()

    def __init__(self):
        super().__init__()
        self.columns = []

        info = QLabel(
            "Chỉ định cột nào trong file nguồn tương ứng với từng loại dữ liệu. "
            "Gợi ý tự động chỉ chọn khi tên cột đủ rõ ràng để tránh chọn nhầm. "
            "Giới tính tự tính từ số thứ 4 của CCCD: 0 → Nam, 1 → Nữ, khác → để trống."
        )
        info.setProperty("info", True)
        info.setWordWrap(True)

        self.table = QTableWidget(len(SOURCE_FIELDS), 3)
        self.table.setHorizontalHeaderLabels(["Tên trường", "Bắt buộc", "Cột nguồn tương ứng"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setMinimumSectionSize(40)
        self.table.verticalHeader().setDefaultSectionSize(max(40, self.fontMetrics().height() + 18))
        self.table.horizontalHeader().setStretchLastSection(True)

        bold = QFont()
        bold.setBold(True)

        for row, (key, label, required) in enumerate(SOURCE_FIELDS):
            label_item = QTableWidgetItem(label)
            label_item.setData(256, key)
            req_item = QTableWidgetItem("✔  Có" if required else "—")
            req_item.setTextAlignment(Qt.AlignCenter)
            if required:
                for item in (label_item, req_item):
                    item.setBackground(_REQUIRED_BG)
                    item.setForeground(_REQUIRED_FG)
                label_item.setFont(bold)
            self.table.setItem(row, 0, label_item)
            self.table.setItem(row, 1, req_item)
            combo = QComboBox()
            combo.setFrame(False)
            if key == "gender":
                combo.addItem("Tự động từ CCCD", "")
                combo.setEnabled(False)
            self.table.setCellWidget(row, 2, combo)

        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 90)

        auto = QPushButton("⚡  Tự động gợi ý")
        auto.clicked.connect(self.auto_requested)
        save = QPushButton("💾  Lưu vào cấu hình")
        save.clicked.connect(self.save_requested)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(auto)
        buttons.addWidget(save)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(info)
        layout.addLayout(buttons)
        layout.addWidget(self.table)

    def set_columns(self, columns) -> None:
        current = self.mapping()
        self.columns = list(columns)
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 2)
            if self.table.item(row, 0).data(256) == "gender":
                continue
            combo.clear()
            combo.addItem("— Không sử dụng —", "")
            for column in self.columns:
                combo.addItem(column.display, column.letter)
        self.set_mapping(current)

    def mapping(self) -> dict[str, str]:
        result = {}
        for row in range(self.table.rowCount()):
            key = self.table.item(row, 0).data(256)
            combo = self.table.cellWidget(row, 2)
            value = combo.currentData() or ""
            if value:
                result[key] = value
        return result

    def set_mapping(self, mapping: dict[str, str]) -> None:
        for row in range(self.table.rowCount()):
            key = self.table.item(row, 0).data(256)
            combo = self.table.cellWidget(row, 2)
            index = combo.findData(mapping.get(key, ""))
            combo.setCurrentIndex(max(0, index))
