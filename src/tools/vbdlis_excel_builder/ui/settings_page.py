from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from tools.vbdlis_excel_builder.models import MappingProfile
from .widgets import ComboBox as QComboBox


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "font-weight: 600; font-size: 9pt; color: palette(mid);"
        "border-bottom: 1px solid palette(midlight); padding-bottom: 4px; margin-top: 8px;"
    )
    return lbl


def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: palette(midlight);")
    return line


class SettingsPage(QWidget):
    profile_changed = Signal(str)
    profile_action = Signal(str)

    def __init__(self):
        super().__init__()

        # Vùng cuộn
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        container = QWidget()
        container.setObjectName("settingsContent")
        container.setStyleSheet("QWidget#settingsContent { background: palette(window); }")
        main_form = QVBoxLayout(container)
        main_form.setContentsMargins(20, 16, 20, 16)
        main_form.setSpacing(4)
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # CẤU HÌNH (thay Profile)
        main_form.addWidget(_section_label("CẤU HÌNH"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(200)
        self.profile_combo.currentTextChanged.connect(self.profile_changed)

        profile_buttons = QHBoxLayout()
        profile_buttons.setSpacing(6)
        for text, action in (
            ("＋ Tạo mới", "new"),
            ("💾 Lưu", "save"),
            ("🗑 Xóa", "delete"),
            ("📥 Nhập từ file", "import"),
            ("📤 Xuất ra file", "export"),
        ):
            button = QPushButton(text)
            button.clicked.connect(lambda _=False, value=action: self.profile_action.emit(value))
            profile_buttons.addWidget(button)
        profile_buttons.addStretch(1)

        form0 = QFormLayout()
        form0.setVerticalSpacing(8)
        form0.setHorizontalSpacing(16)
        form0.addRow("Cấu hình hiện tại", self.profile_combo)
        main_form.addLayout(form0)
        main_form.addLayout(profile_buttons)
        main_form.addWidget(_hline())

        # THÔNG TIN ĐỊA PHƯƠNG
        main_form.addWidget(_section_label("THÔNG TIN ĐỊA PHƯƠNG"))
        self.commune_code = QLineEdit()
        self.commune_code.setPlaceholderText("VD: 00481")
        self.address = QLineEdit()
        self.address.setPlaceholderText("Địa chỉ dùng khi thiếu xứ đồng")
        self.prefix = QLineEdit("CHUACOGIAY")
        self.entity_type = QLineEdit("Hộ gia đình")

        form1 = QFormLayout()
        form1.setVerticalSpacing(8)
        form1.setHorizontalSpacing(16)
        form1.addRow("Mã xã *", self.commune_code)
        form1.addRow("Địa chỉ", self.address)
        self.prefix.setToolTip("Có thể dùng CHUACOGIAY hoặc CHUACAPGIAY theo quy ước hồ sơ.")
        form1.addRow("Tiền tố tên file", self.prefix)
        form1.addRow("Loại chủ thể", self.entity_type)
        main_form.addLayout(form1)
        main_form.addWidget(_hline())

        # VAI TRÒ & HỒ SƠ
        main_form.addWidget(_section_label("VAI TRÒ & HỒ SƠ"))
        self.owner_value = QLineEdit("Chủ hộ")
        self.member_value = QLineEdit("Thành viên hộ gia đình")
        self.document_type = QLineEdit("Loại 5")
        self.item2 = QLineEdit()
        self.item2.setPlaceholderText("{PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}")
        self.item49 = QLineEdit()
        self.item49.setPlaceholderText("{PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}-TBXN.pdf, …-DDK.pdf")

        form2 = QFormLayout()
        form2.setVerticalSpacing(8)
        form2.setHorizontalSpacing(16)
        form2.addRow("Vai trò chủ hộ", self.owner_value)
        form2.addRow("Vai trò thành viên", self.member_value)
        form2.addRow("Loại hồ sơ", self.document_type)
        form2.addRow("Mục 2", self.item2)
        form2.addRow("Mục 49", self.item49)
        main_form.addLayout(form2)
        main_form.addWidget(_hline())

        # KHI THIẾU XỨ ĐỒNG
        main_form.addWidget(_section_label("KHI THIẾU XỨ ĐỒNG"))
        self.fallback = QComboBox()
        self.fallback.addItem("Dùng địa chỉ đã nhập ở trên", "address")
        self.fallback.addItem("Để trống", "blank")
        self.fallback.addItem("Dùng giá trị khác", "value")
        self.fallback_value = QLineEdit()
        self.fallback_value.setPlaceholderText("Chỉ dùng khi chọn «Dùng giá trị khác»")

        form3 = QFormLayout()
        form3.setVerticalSpacing(8)
        form3.setHorizontalSpacing(16)
        form3.addRow("Cách xử lý", self.fallback)
        form3.addRow("Giá trị thay thế", self.fallback_value)
        main_form.addLayout(form3)
        main_form.addWidget(_hline())

        # CHẾ ĐỘ GCN & CCCD
        main_form.addWidget(_section_label("CHẾ ĐỘ GCN & CCCD"))
        self.gcn_mode = QComboBox()
        self.gcn_mode.addItem("Tự động theo từng thửa", "auto")
        self.gcn_mode.addItem("Toàn bộ chưa có GCN", "all_without")
        self.gcn_mode.addItem("Dữ liệu có GCN", "with_gcn")
        self.invalid_cccd = QComboBox()
        self.invalid_cccd.addItem("Giữ nguyên + cảnh báo", "keep")
        self.invalid_cccd.addItem("Dừng nếu không đủ 12 số", "error")
        self.skip_invalid_data = QCheckBox("Bỏ hộ thiếu dữ liệu bắt buộc; bỏ người có CCCD sai; ghi báo cáo đầy đủ")
        self.skip_invalid_data.setChecked(True)
        self.skip_invalid_data.setToolTip("Thiếu họ tên/CCCD hoặc tờ/thửa/diện tích: bỏ cả hộ. CCCD có giá trị nhưng sai 12 số: bỏ riêng người. Không kiểm tra ô trống bình thường ở dòng nối tiếp như một người/thửa mới.")
        self.invalid_cccd.setEnabled(False)
        self.skip_invalid_data.toggled.connect(lambda checked: self.invalid_cccd.setEnabled(not checked))

        form4 = QFormLayout()
        form4.setVerticalSpacing(8)
        form4.setHorizontalSpacing(16)
        form4.addRow("Chế độ GCN", self.gcn_mode)
        form4.addRow("CCCD bất thường", self.invalid_cccd)
        form4.addRow("Tự động bỏ qua", self.skip_invalid_data)
        gender_note = QLabel("Tự động từ CCCD: số thứ 4 là 0 → Nam, 1 → Nữ.\nCác số khác hoặc CCCD không đủ 12 chữ số → để trống.")
        gender_note.setWordWrap(True)
        gender_note.setProperty("info", True)
        form4.addRow("Giới tính (Mục 10)", gender_note)
        main_form.addLayout(form4)
        main_form.addWidget(_hline())

        # TÙY CHỌN XỬ LÝ
        main_form.addWidget(_section_label("TÙY CHỌN XỬ LÝ"))
        self.household_mode = QCheckBox("File có cấu trúc hộ gia đình (dòng STT bắt đầu hộ)")
        self.household_mode.setChecked(True)
        self.normalize_names = QCheckBox("Chuẩn hóa họ tên: sửa dấu, bỏ khoảng trắng thừa, IN HOA")
        self.normalize_names.setChecked(True)
        self.normalize_cccd = QCheckBox("Chuẩn hóa CCCD và giữ số 0 đầu (luôn bật)")
        self.normalize_cccd.setChecked(True)
        self.normalize_cccd.setEnabled(False)

        main_form.addWidget(self.household_mode)
        main_form.addWidget(self.normalize_names)
        main_form.addWidget(self.normalize_cccd)
        main_form.addStretch(1)

    @staticmethod
    def _set_combo(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def load_profile(self, profile: MappingProfile) -> None:
        self.commune_code.setText(profile.commune_code)
        self.address.setText(profile.address)
        self.prefix.setText(profile.prefix)
        self.entity_type.setText(profile.entity_type)
        self.owner_value.setText(profile.owner_value)
        self.member_value.setText(profile.member_value)
        self.document_type.setText(profile.document_type)
        self.item2.setText(profile.item_2_template)
        self.item49.setText(profile.item_49_template)
        self._set_combo(self.fallback, profile.location_fallback)
        self.fallback_value.setText(profile.location_fallback_value)
        self._set_combo(self.gcn_mode, profile.gcn_mode)
        self._set_combo(self.invalid_cccd, profile.invalid_cccd_action)
        self.skip_invalid_data.setChecked(profile.skip_invalid_data)
        self.invalid_cccd.setEnabled(not profile.skip_invalid_data)
        self.household_mode.setChecked(profile.household_mode)
        self.normalize_names.setChecked(profile.normalize_names)
        self.normalize_cccd.setChecked(profile.normalize_cccd)

    def update_profile(self, profile: MappingProfile) -> MappingProfile:
        profile.profile_name = self.profile_combo.currentText() or profile.profile_name
        profile.commune_code = self.commune_code.text().strip()
        profile.address = self.address.text().strip()
        profile.prefix = self.prefix.text().strip() or "CHUACOGIAY"
        profile.entity_type = self.entity_type.text().strip()
        profile.owner_value = self.owner_value.text().strip()
        profile.member_value = self.member_value.text().strip()
        profile.document_type = self.document_type.text().strip()
        profile.item_2_template = self.item2.text().strip()
        profile.item_49_template = self.item49.text().strip()
        profile.location_fallback = self.fallback.currentData()
        profile.location_fallback_value = self.fallback_value.text().strip()
        profile.gcn_mode = self.gcn_mode.currentData()
        profile.invalid_cccd_action = self.invalid_cccd.currentData()
        profile.skip_invalid_data = self.skip_invalid_data.isChecked()
        profile.household_mode = self.household_mode.isChecked()
        profile.normalize_names = self.normalize_names.isChecked()
        profile.normalize_cccd = True
        return profile
