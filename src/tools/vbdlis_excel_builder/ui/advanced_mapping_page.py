from __future__ import annotations

import unicodedata

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QApplication,
)


from .widgets import ComboBox as QComboBox


MODES = [
    ("Lấy từ cột nguồn",         "source_column"),
    ("Giá trị cố định",          "fixed"),
    ("Tự động tính",              "computed"),
    ("Giữ mặc định biểu mẫu",   "keep_template"),
    ("Để trống",                  "blank"),
    ("Có điều kiện",              "conditional"),
]

# Màu nền nhẹ theo phân loại
_CLASS_COLORS: dict[str, QColor] = {
    "ACTIVE_REQUIRED":   QColor("#eff6ff"),
    "ACTIVE_OPTIONAL":   QColor("#f0fdf4"),
    "COMPUTED":          QColor("#faf5ff"),
    "GCN_OPTIONAL":      QColor("#fff7ed"),
    "TEMPLATE_DEFAULT":  QColor("#f8fafc"),
    "TEMPLATE_OPTIONAL": QColor("#f8fafc"),
    "USER_CONFIGURABLE": QColor("#fefce8"),
}

_CLASS_COLORS_DARK: dict[str, QColor] = {
    "ACTIVE_REQUIRED":   QColor("#243853"),
    "ACTIVE_OPTIONAL":   QColor("#1F3A2B"),
    "COMPUTED":          QColor("#33244D"),
    "GCN_OPTIONAL":      QColor("#4A321B"),
    "TEMPLATE_DEFAULT":  QColor("#30343B"),
    "TEMPLATE_OPTIONAL": QColor("#30343B"),
    "USER_CONFIGURABLE": QColor("#443B1B"),
}

# Dịch phân loại sang tiếng Việt
_CLASS_LABELS: dict[str, str] = {
    "ACTIVE_REQUIRED":   "Bắt buộc",
    "ACTIVE_OPTIONAL":   "Tùy chọn",
    "COMPUTED":          "Tự động tính",
    "GCN_OPTIONAL":      "GCN (tùy chọn)",
    "TEMPLATE_DEFAULT":  "Mặc định biểu mẫu",
    "TEMPLATE_OPTIONAL": "Biểu mẫu (tùy chọn)",
    "USER_CONFIGURABLE": "Người dùng cấu hình",
}


class AdvancedMappingPage(QWidget):
    rules_changed = Signal()

    def __init__(self, schemas):
        super().__init__()
        self.schemas = list(schemas)
        app = QApplication.instance()
        self._dark_mode = bool(app.property("darkMode")) if app and app.property("darkMode") is not None else False

        warning = QLabel(
            "⚠️  Lưu ý: thay đổi Mục 49 hoặc trường bắt buộc có thể làm file không tương thích VBDLIS. "
            "Chế độ «Có điều kiện»: nếu thửa có GCN thì lấy dữ liệu nguồn, không có thì dùng giá trị thay thế hoặc để trống."
        )
        warning.setWordWrap(True)
        warning.setProperty("warning", True)

        # Bảng giải thích chế độ
        explain = QLabel(
            "📖  Giải thích các chế độ:\n"
            "• Lấy từ cột nguồn — lấy dữ liệu từ cột trong file Excel nguồn.\n"
            "• Giá trị cố định — luôn điền một giá trị do bạn nhập sẵn.\n"
            "• Tự động tính — ứng dụng tự điền (VD: STT, vai trò, Mục 2, Mục 49).\n"
            "• Giữ mặc định biểu mẫu — giữ nguyên giá trị có sẵn trong biểu mẫu gốc.\n"
            "• Để trống — cố ý bỏ trống ô này.\n"
            "• Có điều kiện — chỉ điền khi thửa đáp ứng điều kiện (VD: có GCN)."
        )
        explain.setWordWrap(True)
        explain.setProperty("info", True)
        explain.setVisible(False)

        help_button = QToolButton()
        help_button.setText("Giải thích các chế độ")
        help_button.setCheckable(True)
        help_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        help_button.setArrowType(Qt.RightArrow)
        help_button.toggled.connect(explain.setVisible)
        help_button.toggled.connect(
            lambda checked: help_button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        )

        save = QPushButton("💾  Lưu thay đổi vào cấu hình")
        save.setProperty("accent", True)
        save.clicked.connect(self.rules_changed)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(save)
        buttons.addWidget(help_button)
        buttons.addStretch(1)
        buttons.addWidget(QLabel(f"{len(self.schemas)} trường • Di chuột lên tên để xem đầy đủ"))

        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText("Tìm mục, cột hoặc tên trường… Ví dụ: 29, AD, thời hạn sử dụng")
        self.search.setAccessibleName("Tìm quy tắc theo mục, cột hoặc tên trường")
        self.visible_count = QLabel(f"{len(self.schemas)} / {len(self.schemas)} trường")
        search_row = QHBoxLayout()
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.visible_count)
        self.field_details = QLabel("Muốn điền cùng nội dung cho mọi dòng: chọn Giá trị cố định → nhập ở cột Mặc định → Lưu cấu hình.")
        self.field_details.setWordWrap(True)
        self.field_details.setProperty("info", True)

        self.table = QTableWidget(len(self.schemas), 9)
        self.table.setHorizontalHeaderLabels(
            ["Mục", "Cột", "Tên trường", "Phân loại", "Chế độ", "Nguồn", "Mặc định", "Bắt buộc", "Thay thế"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setMinimumSectionSize(40)
        self.table.verticalHeader().setDefaultSectionSize(max(40, self.fontMetrics().height() + 18))
        self.table.setWordWrap(False)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.horizontalHeader().setStretchLastSection(True)

        for row, schema in enumerate(self.schemas):
            row_bg = self._row_color(schema.classification.value)
            cls_label = _CLASS_LABELS.get(schema.classification.value, schema.classification.value)

            item_cell = QTableWidgetItem(schema.item or "—")
            item_cell.setData(256, schema.field_id)
            item_cell.setBackground(row_bg)

            col_item = QTableWidgetItem(schema.column)
            col_item.setBackground(row_bg)
            col_item.setTextAlignment(Qt.AlignCenter)

            name_item = QTableWidgetItem(schema.name)
            name_item.setToolTip(schema.name)
            name_item.setBackground(row_bg)

            cls_item = QTableWidgetItem(cls_label)
            cls_item.setBackground(row_bg)
            cls_item.setTextAlignment(Qt.AlignCenter)
            cls_item.setForeground(self._text_color())

            self.table.setItem(row, 0, item_cell)
            self.table.setItem(row, 1, col_item)
            self.table.setItem(row, 2, name_item)
            self.table.setItem(row, 3, cls_item)
            for item in (item_cell, col_item, name_item):
                item.setForeground(self._text_color())

            mode = QComboBox()
            mode.setFrame(False)
            for label, value in MODES:
                mode.addItem(label, value)
            mode.setCurrentIndex(max(0, mode.findData(schema.mode)))
            self.table.setCellWidget(row, 4, mode)

            src = QLineEdit(schema.source)
            src.setFrame(False)
            self.table.setCellWidget(row, 5, src)

            default_val = "" if schema.default is None else str(schema.default)
            dflt = QLineEdit(default_val)
            dflt.setPlaceholderText("Nội dung cố định…")
            dflt.setToolTip("Khi chọn Giá trị cố định, nội dung này áp dụng cho mọi dòng xuất. Ví dụ: Không xác định.")
            dflt.setFrame(False)
            self.table.setCellWidget(row, 6, dflt)

            required = QCheckBox()
            required.setChecked(schema.required)
            req_wrapper = QWidget()
            req_layout = QHBoxLayout(req_wrapper)
            req_layout.setContentsMargins(0, 0, 0, 0)
            req_layout.setAlignment(Qt.AlignCenter)
            req_layout.addWidget(required)
            self.table.setCellWidget(row, 7, req_wrapper)

            fallback = QLineEdit(schema.fallback)
            fallback.setFrame(False)
            self.table.setCellWidget(row, 8, fallback)
            if schema.transformer == "gender":
                # This business rule also applies to previously saved profiles.
                mode.setCurrentIndex(mode.findData("computed"))
                mode.setEnabled(False)
                src.setText("cccd")
                for editor in (src, dflt, fallback):
                    editor.setEnabled(False)
                dflt.clear()
                fallback.clear()
                note = "Mục 10 tự tính từ CCCD: số thứ 4 là 0 → Nam; 1 → Nữ; còn lại để trống."
                for control in (mode, src, dflt, fallback):
                    control.setToolTip(note)
                name_item.setToolTip(schema.name + "\n" + note)

        # Độ rộng cột
        self.table.setColumnWidth(0, 55)
        self.table.setColumnWidth(1, 45)
        self.table.setColumnWidth(2, 280)
        self.table.setColumnWidth(3, 165)
        self.table.setColumnWidth(4, 195)
        self.table.setColumnWidth(5, 160)
        self.table.setColumnWidth(6, 200)
        self.table.setColumnWidth(7, 80)
        self.table.setColumnWidth(8, 180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(warning)
        layout.addLayout(buttons)
        layout.addWidget(explain)
        layout.addLayout(search_row)
        layout.addWidget(self.field_details)
        layout.addWidget(self.table)
        self.search.textChanged.connect(self._filter_rows)
        self.table.currentCellChanged.connect(self._show_field_details)

    def _row_color(self, classification: str) -> QColor:
        colors = _CLASS_COLORS_DARK if self._dark_mode else _CLASS_COLORS
        return colors.get(classification, QColor("#30343B" if self._dark_mode else "#ffffff"))

    def _text_color(self) -> QColor:
        return QColor("#F2F4F7" if self._dark_mode else "#1F2937")

    def apply_theme(self, dark: bool) -> None:
        """Refresh explicit cell colors when the launcher switches theme."""
        self._dark_mode = bool(dark)
        foreground = self._text_color()
        for row, schema in enumerate(self.schemas):
            background = self._row_color(schema.classification.value)
            for column in range(4):
                item = self.table.item(row, column)
                if item is not None:
                    item.setBackground(background)
                    item.setForeground(foreground)

    @staticmethod
    def _search_text(text: str) -> str:
        text = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
        return "".join(char for char in text if not unicodedata.combining(char))

    def _filter_rows(self, query: str) -> None:
        words = self._search_text(query).split()
        count = 0
        for row, schema in enumerate(self.schemas):
            text = self._search_text(f"mục {schema.item} {schema.column} {schema.name} {_CLASS_LABELS.get(schema.classification.value, '')}")
            visible = all(word in text for word in words)
            self.table.setRowHidden(row, not visible)
            count += visible
        self.visible_count.setText(f"{count} / {len(self.schemas)} trường")

    def _show_field_details(self, row: int, _column: int, _previous_row: int, _previous_column: int) -> None:
        if 0 <= row < len(self.schemas):
            schema = self.schemas[row]
            self.field_details.setText(f"Mục {schema.item or 'STT'} • Cột {schema.column}: {schema.name}\nGiá trị cố định: nhập ở cột Mặc định. Thay đổi áp dụng khi tạo lại file, không sửa file đã xuất.")

    def rules(self) -> dict[str, dict]:
        result = {}
        schema_by_id = {schema.field_id: schema for schema in self.schemas}
        for row in range(self.table.rowCount()):
            field_id = self.table.item(row, 0).data(256)
            schema = schema_by_id[field_id]
            mode = self.table.cellWidget(row, 4).currentData()
            source = self.table.cellWidget(row, 5).text().strip()
            default = self.table.cellWidget(row, 6).text()
            req_widget = self.table.cellWidget(row, 7)
            required_cb = req_widget.findChild(QCheckBox)
            required = required_cb.isChecked() if required_cb else False
            fallback = self.table.cellWidget(row, 8).text()
            result[field_id] = {
                "field_id": field_id,
                "mode": mode,
                "source": source,
                "default": default,
                "transformer": schema.transformer,
                "fallback": fallback,
                "required": required,
                "condition": schema.condition,
            }
        return result

    def load_rules(self, rules: dict[str, dict]) -> None:
        if not rules:
            return
        for row in range(self.table.rowCount()):
            field_id = self.table.item(row, 0).data(256)
            if self.schemas[row].transformer == "gender":
                continue
            rule = rules.get(field_id)
            if not rule:
                continue
            mode = self.table.cellWidget(row, 4)
            index = mode.findData(rule.get("mode", "blank"))
            mode.setCurrentIndex(max(0, index))
            self.table.cellWidget(row, 5).setText(str(rule.get("source", "")))
            self.table.cellWidget(row, 6).setText(str(rule.get("default", "")))
            req_widget = self.table.cellWidget(row, 7)
            required_cb = req_widget.findChild(QCheckBox)
            if required_cb:
                required_cb.setChecked(bool(rule.get("required", False)))
            self.table.cellWidget(row, 8).setText(str(rule.get("fallback", "")))
