from dataclasses import asdict
from datetime import date
from pathlib import Path
from threading import Event
import json
import os
import traceback
from PySide6.QtCore import QDate, Qt, QThread, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QIntValidator, QPalette, QPixmap
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QStackedWidget, QLineEdit, QComboBox, QSpinBox, QFormLayout, QFileDialog, QMessageBox,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QCheckBox, QPlainTextEdit,
    QAbstractItemView, QDateEdit, QDialog, QDialogButtonBox)
from .paths import resource, data_dir, default_template_path, saved_template_path
from .core import BatchConfig, ColumnMapping, NoticeService, UserError, inspect_workbook, workbook_info
from .core.fields import REQUIRED_COMMON, OPTIONAL_COMMON
from .core.fields import FIELD_LABELS
from .template_config import template_configs, template_config_for_path

from .presentation import STYLE, apply_presentation


class Job(QThread):
    ready = Signal(object)
    failed = Signal(str)
    advanced = Signal(int, int, int, object)

    def __init__(self, function, parent=None):
        super().__init__(parent); self.function = function; self.cancel_event = Event()

    def run(self):
        try:
            result = self.function(self)
            self.ready.emit(result)
        except Exception as error:
            try:
                with (data_dir() / "debug.log").open("a", encoding="utf-8") as stream:
                    stream.write(traceback.format_exc() + "\n")
            except OSError:
                pass
            if isinstance(error, UserError):
                message = str(error)
            elif isinstance(error, PermissionError):
                message = "Không có quyền đọc/ghi file. Hãy đóng file đang mở và chọn thư mục bạn có quyền ghi."
            else:
                message = "Không hoàn thành được thao tác. Kiểm tra file Excel, mẫu Word và thư mục đầu ra; nhật ký kỹ thuật nằm trong thư mục cấu hình."
            self.failed.emit(message)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tạo thông báo đất đai")
        self.resize(1250, 830); self.setMinimumSize(1000, 650)
        self.setWindowIcon(QIcon(str(resource("assets/app_icon.ico"))))
        palette = QPalette()
        for role,color in ((QPalette.Window,"#f3f6fa"),(QPalette.Base,"#ffffff"),(QPalette.Text,"#20334b"),
                           (QPalette.WindowText,"#20334b"),(QPalette.Button,"#e6f0f2"),(QPalette.ButtonText,"#125a61")):
            palette.setColor(role,QColor(color))
        self.setPalette(palette); self.setStyleSheet(STYLE)
        self.job = None; self.inspection = None; self.preview_result = None; self.service = None; self.result = None
        self.source_info = None; self.saved_source_settings = None; self.batch_errors = 0; self.batch_duplicates = 0
        self.settings_path = data_dir() / "config.json"
        self.pages = []; self.inputs = {}
        central = QWidget(); self.setCentralWidget(central); outer = QVBoxLayout(central)
        header = QLabel("Tạo thông báo từ Excel"); header.setObjectName("heading"); outer.addWidget(header)
        hint = QLabel("Mẫu 22 • Mỗi thửa một file Word • Giấy tờ nhân thân bắt buộc • Xem trước rồi mới tạo hàng loạt")
        hint.setObjectName("hint"); hint.setWordWrap(True); outer.addWidget(hint)
        row = QHBoxLayout(); outer.addLayout(row,1)
        self.steps = QListWidget(); self.steps.setFixedWidth(218)
        self.steps.addItems(["1. Chọn file", "2. Trang tính & tiêu đề", "3. Đối chiếu cột", "4. Thông tin thông báo",
                             "5. Kiểm tra dữ liệu", "6. Xem trước & xác nhận", "7. Tạo hàng loạt", "8. Kết quả & nhật ký"])
        self.stack = QStackedWidget(); row.addWidget(self.steps); row.addWidget(self.stack,1)
        self.steps.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.make_file_page(); self.make_sheet_page(); self.make_mapping_page(); self.make_config_page()
        self.make_validation_page(); self.make_preview_page(); self.make_progress_page(); self.make_result_page()
        footer = QHBoxLayout(); outer.addLayout(footer)
        self.back = self.button("← Quay lại",lambda:self.navigate(-1)); footer.addWidget(self.back)
        footer.addStretch()
        self.cancel = self.button("Dừng sau file đang xử lý", self.cancel_job); self.cancel.setEnabled(False); footer.addWidget(self.cancel)
        self.next = self.button("Tiếp tục →",lambda:self.navigate(1)); footer.addWidget(self.next)
        self.steps.setCurrentRow(0); self.load_settings(); self.refresh_template_config()
        self.statusBar().showMessage("File nguồn chỉ được đọc. Không ghi đè file thông báo đã tồn tại.")
        apply_presentation(self)

    def button(self, text, callback, primary=False):
        button = QPushButton(text); button.clicked.connect(callback)
        if primary: button.setObjectName("primary")
        return button

    def page(self, title, description):
        widget=QWidget(); layout=QVBoxLayout(widget); layout.setContentsMargins(16,12,16,12); layout.setSpacing(12)
        heading=QLabel(title); heading.setObjectName("heading"); layout.addWidget(heading)
        hint=QLabel(description); hint.setObjectName("hint"); hint.setWordWrap(True); layout.addWidget(hint)
        self.pages.append(widget); self.stack.addWidget(widget)
        return layout

    def make_file_page(self):
        box=self.page("Chọn dữ liệu và biểu mẫu", "Chọn đúng file .xlsx và mẫu Word có ô đánh dấu để điền dữ liệu. Không sửa nội dung pháp lý của mẫu gốc.")
        self.source=QLineEdit(); self.source.setPlaceholderText("Chưa chọn Excel...")
        self.template=QLineEdit(str(default_template_path()))
        for label,field,filter_text in (("Excel nguồn",self.source,"Excel (*.xlsx)"),("Mẫu Word",self.template,"Word (*.docx)")):
            box.addWidget(QLabel(label)); line=QHBoxLayout(); line.addWidget(field)
            line.addWidget(self.button("Chọn file…",lambda checked=False,f=field,t=filter_text:self.browse_file(f,t))); box.addLayout(line)
            field.textChanged.connect(self.invalidate)
        known_templates = template_configs()
        template_buttons = QHBoxLayout()
        for config in known_templates:
            template_buttons.addWidget(self.button("Dùng " + config.name,
                lambda checked=False, path=config.path: self.template.setText(str(path))))
        template_buttons.addStretch(1); box.addLayout(template_buttons)
        self.template.textChanged.connect(self.refresh_template_config)
        box.addWidget(self.button("Đọc cấu trúc Excel →",self.read_source,True))
        preview_path=resource("assets/template_placeholder_preview.png")
        preview_title=QLabel("Ảnh tham khảo vị trí placeholder trong mẫu Word")
        preview_title.setObjectName("sectionHeading"); box.addWidget(preview_title)
        preview_note=QLabel("Dùng ảnh này để biết nội dung nào sẽ được điền từ Excel hoặc từ Bước 4. Bấm mở ảnh để đọc rõ cả hai trang.")
        preview_note.setObjectName("muted"); preview_note.setWordWrap(True); box.addWidget(preview_note)
        self.template_preview=QLabel(); self.template_preview.setObjectName("templatePreview")
        self.template_preview.setAlignment(Qt.AlignCenter); self.template_preview.setAccessibleName("Ảnh xem trước mẫu Word có placeholder")
        pixmap=QPixmap(str(preview_path))
        if not pixmap.isNull(): self.template_preview.setPixmap(pixmap.scaled(600,410,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        box.addWidget(self.template_preview,0,Qt.AlignHCenter)
        box.addWidget(self.button("Mở ảnh mẫu để xem rõ",lambda:self.open_path(preview_path))); box.addStretch()

    def make_sheet_page(self):
        box=self.page("Chọn trang tính, tiêu đề và phạm vi xử lý", "Tiêu đề gộp hai tầng: chọn dòng đầu và 2 tầng. Có thể nhập một khoảng dòng Excel để chỉ xử lý dữ liệu mới; để trống cả hai ô sẽ xử lý toàn bộ như trước.")
        form=QFormLayout(); box.addLayout(form)
        self.sheet=QComboBox(); self.header=QSpinBox(); self.header.setRange(1,1048576)
        self.depth=QComboBox(); self.depth.addItem("1 tầng",1); self.depth.addItem("2 tầng",2)
        form.addRow("Trang tính",self.sheet); form.addRow("Dòng đầu tiêu đề",self.header); form.addRow("Số tầng tiêu đề",self.depth)
        self.row_start=QLineEdit(); self.row_end=QLineEdit()
        self.row_start.setPlaceholderText("Để trống nếu xử lý toàn bộ")
        self.row_end.setPlaceholderText("Để trống nếu xử lý toàn bộ")
        self.row_start.setValidator(QIntValidator(1,1048576,self.row_start)); self.row_end.setValidator(QIntValidator(1,1048576,self.row_end))
        form.addRow("Dòng bắt đầu xử lý",self.row_start); form.addRow("Dòng kết thúc xử lý",self.row_end)
        range_note=QLabel("Số dòng tính theo dòng thực tế hiển thị trong Excel và bao gồm cả hai đầu. Phải nhập đủ cả hai ô; khoảng dòng không được chứa phần tiêu đề hoặc vượt quá dòng cuối có dữ liệu.")
        range_note.setObjectName("muted"); range_note.setWordWrap(True); box.addWidget(range_note)
        self.sheet_hint=QLabel(); self.sheet_hint.setWordWrap(True); box.addWidget(self.sheet_hint)
        self.sheet.currentTextChanged.connect(self.sheet_changed)
        self.header.valueChanged.connect(self.invalidate); self.depth.currentIndexChanged.connect(self.invalidate)
        self.row_start.textChanged.connect(self.invalidate); self.row_end.textChanged.connect(self.invalidate)
        box.addWidget(self.button("Cập nhật danh sách cột →",self.update_columns,True)); box.addStretch()

    def make_mapping_page(self):
        box=self.page("Đối chiếu cột nguồn", "Với file Cẩm Đông: G/H là tờ/thửa MỚI; K là diện tích bản đồ, không phải diện tích giao ở M. Gợi ý chỉ là hỗ trợ, cần kiểm tra trước khi xuất.")
        form=QFormLayout(); box.addLayout(form); self.mapping={}
        for key,label in (("household_index","STT hộ * (dòng xác định Chủ hộ)"),("owner","Tên hộ/thành viên *"),("identity","Giấy tờ nhân thân * (CCCD/CMND/khác)"),("birth_date","Ngày sinh chủ hộ/thành viên (mẫu Cẩm Giang)"),("sheet","Tờ BĐ mới *"),("parcel","Thửa BĐ mới *"),("area","Diện tích *"),("location","Xứ đồng (có thể trống)")):
            combo=QComboBox(); combo.addItem("— Chưa chọn —",""); combo.currentIndexChanged.connect(self.invalidate)
            self.mapping[key]=combo; form.addRow(label,combo)
        note=QLabel("Dùng cùng quy tắc với Chuẩn bị hồ sơ VBDLIS: dòng có STT hộ bắt đầu hộ mới; người đầu tiên là Chủ hộ. Tên trên các dòng STT trống là thành viên và không thay thế Chủ hộ. Mẫu Cẩm Giang đưa các thành viên vào trang 3 và loại Chủ hộ khỏi danh sách.")
        note.setWordWrap(True); box.addWidget(note); box.addStretch()

    def make_config_page(self):
        box=self.page("Thông tin dùng cho đợt thông báo", "Dấu * là bắt buộc. Gợi ý màu xám trong ô sẽ tự ẩn khi bạn bắt đầu nhập; hãy thay bằng thông tin của đợt đang làm.")
        scroll=QScrollArea(); scroll.setWidgetResizable(True); content=QWidget(); form=QFormLayout(content); scroll.setWidget(content); box.addWidget(scroll)
        labels={"commune_code":"Mã đơn vị hành chính *","owner_address":"Địa chỉ người sử dụng đất *","village":"Tên thôn *",
                "administrative_address":"Địa chỉ hành chính của thửa","suffix":"Hậu tố tên file *"}
        examples={
            "commune_code":("Ví dụ: 10930", "Mã đơn vị hành chính gồm 5 chữ số. Ví dụ: 10930."),
            "owner_address":("Ví dụ: thôn Tân Hòa, xã đang lập hồ sơ, TP Hải Phòng", "Địa chỉ đầy đủ của người sử dụng đất."),
            "village":("Ví dụ: Tân Hòa", "Tên thôn hoặc tổ dân phố."),
            "administrative_address":("Ví dụ: xã đang lập hồ sơ, TP Hải Phòng", "Địa chỉ hành chính của thửa đất; có thể để trống nếu không dùng."),
            "suffix":("Ví dụ: TBXN", "Hậu tố dùng trong tên file, ví dụ CHUACOGIAY_10930_1_2-TBXN.pdf."),
        }
        for key,label in labels.items():
            default = "TBXN" if key == "suffix" else ""
            field=QLineEdit(default)
            placeholder, tooltip = examples[key]
            field.setPlaceholderText(placeholder); field.setToolTip(tooltip)
            field.textChanged.connect(self.invalidate); self.inputs[key]=field; form.addRow(label,field)
        prefix_field=QLineEdit("CHUACOGIAY")
        prefix_field.setPlaceholderText("Ví dụ: CHUACOGIAY hoặc CHUACAPGIAY")
        prefix_field.setToolTip("Tiền tố đặt đầu tên file. Có thể dùng CHUACOGIAY hoặc CHUACAPGIAY.")
        prefix_field.textChanged.connect(self.invalidate); self.inputs["prefix"]=prefix_field
        form.addRow("Tiền tố tên file", prefix_field)
        date_line=QWidget(); dates=QHBoxLayout(date_line); dates.setContentsMargins(0,0,0,0); today=date.today()
        for key,label,minimum,maximum,default in (("day","Ngày",1,31,today.day),("month","Tháng",1,12,today.month),("year","Năm",1900,2200,today.year)):
            spin=QSpinBox(); spin.setRange(minimum,maximum); spin.setValue(default); spin.valueChanged.connect(self.invalidate); self.inputs[key]=spin
            dates.addWidget(QLabel(label)); dates.addWidget(spin)
        form.addRow("Ngày thông báo mặc định",date_line)
        self.number_mode=QComboBox(); self.number_mode.addItem("Số bắt đầu","start"); self.number_mode.addItem("Danh sách số","list")
        self.start_number=QSpinBox(); self.start_number.setRange(1,2147483647)
        self.number_list=QLineEdit(); self.number_list.setPlaceholderText("Có thể để trống nếu nhập các nhóm số và ngày bên dưới")
        self.continue_check=QCheckBox("Tiếp tục sau khi hết danh sách")
        self.continue_check.setChecked(True)
        self.continue_number=QSpinBox(); self.continue_number.setRange(1,2147483647); self.continue_number.setValue(1)
        form.addRow("Cách cấp số",self.number_mode); form.addRow("Số bắt đầu",self.start_number); form.addRow("Danh sách số (tùy chọn)",self.number_list)
        form.addRow(self.continue_check); form.addRow("Số tiếp nối",self.continue_number)
        self.number_date_rows=[]
        self.number_date_box=QWidget(); date_box=QVBoxLayout(self.number_date_box); date_box.setContentsMargins(0,0,0,0); date_box.setSpacing(8)
        self.numbering_cases_note=QLabel(
            "Cách dùng nhanh:\n"
            "• Số liên tục: chọn “Số bắt đầu”.\n"
            "• Số thiếu cùng ngày: nhập “Danh sách số”, dùng ngày mặc định.\n"
            "• Số thiếu khác ngày: để trống “Danh sách số”, thêm từng nhóm số và ngày bên dưới.\n"
            "• Hết số trong danh sách: ứng dụng mặc định tự cấp tiếp từ số lớn hơn liền kề; có thể sửa ô Số tiếp nối nếu cần chừa khoảng."
        )
        self.numbering_cases_note.setObjectName("muted"); self.numbering_cases_note.setWordWrap(True); date_box.addWidget(self.numbering_cases_note)
        self.number_date_rows_layout=QVBoxLayout(); self.number_date_rows_layout.setContentsMargins(0,0,0,0); self.number_date_rows_layout.setSpacing(6); date_box.addLayout(self.number_date_rows_layout)
        self.add_number_date_button=self.button("+ Thêm số hoặc khoảng số",lambda:self.add_number_date_rule()); date_box.addWidget(self.add_number_date_button)
        form.addRow("Các số cần tạo và ngày",self.number_date_box)
        self.number_mode.currentIndexChanged.connect(self.numbering_changed); self.continue_check.toggled.connect(self.numbering_changed)
        self.start_number.valueChanged.connect(self.invalidate); self.number_list.textChanged.connect(self.numbering_input_changed); self.continue_number.valueChanged.connect(self.invalidate)
        self.output=QLineEdit(); self.output.setPlaceholderText("Ví dụ: D:/Ho so/TB 2026 hoặc bấm Chọn thư mục…"); self.output.setToolTip("Thư mục chứa các file Word được tạo và báo cáo kết quả."); self.output.textChanged.connect(self.invalidate)
        output_row=QWidget(); line=QHBoxLayout(output_row); line.setContentsMargins(0,0,0,0); line.addWidget(self.output); line.addWidget(self.button("Chọn thư mục…",self.browse_output)); form.addRow("Lưu thông báo tại *",output_row)
        defaults=json.loads(resource("config/legal_defaults.json").read_text(encoding="utf-8"))
        self.template_inputs={}
        self.template_field_labels={}
        self.template_static_note=QLabel(); self.template_static_note.setObjectName("hint"); self.template_static_note.setWordWrap(True)
        form.addRow(self.template_static_note)
        config=template_config_for_path(self.template.text())
        form.addRow(QLabel("NỘI DUNG BẮT BUỘC TRONG MẪU WORD"))
        available_fields={**REQUIRED_COMMON, **OPTIONAL_COMMON}
        for key,label in available_fields.items():
            if key==next(iter(OPTIONAL_COMMON)):
                derived_note=QLabel("Diện tích sử dụng chung tự động bằng Diện tích của từng thửa; không cần nhập.")
                derived_note.setObjectName("hint"); derived_note.setWordWrap(True); form.addRow(derived_note)
                form.addRow(QLabel("NỘI DUNG KHÔNG BẮT BUỘC"))
            field=QLineEdit(defaults.get(key, "") if key in REQUIRED_COMMON else "")
            field.setToolTip("Nội dung điền vào ô {{"+key+"}} trong mẫu Word."); field.textChanged.connect(self.invalidate)
            field.setPlaceholderText("Bắt buộc nhập" if key in REQUIRED_COMMON else "Có thể để trống")
            self.template_inputs[key]=field; form.addRow(label,field)
            self.template_field_labels[key]=form.labelForField(field)
        self.optional_empty=QComboBox(); self.optional_empty.addItem("Để trống", "blank"); self.optional_empty.addItem("Điền ....", "dots")
        self.optional_empty.currentIndexChanged.connect(self.invalidate); self.optional_empty_label=QLabel("Ô không bắt buộc chưa có dữ liệu"); form.addRow(self.optional_empty_label,self.optional_empty)
        self.empty_location=QComboBox(); self.empty_location.addItem("Để trống", "blank"); self.empty_location.addItem("Dùng tên thôn", "village")
        self.empty_location.currentIndexChanged.connect(self.invalidate); self.empty_location_label=QLabel("Xứ đồng khi bị trống"); form.addRow(self.empty_location_label, self.empty_location)
        form.addRow(self.button("Xem căn cứ và nội dung gốc",self.show_legal)); form.addRow(self.button("Lưu cấu hình để dùng lại",self.save_settings))
        self.numbering_changed()

    def make_validation_page(self):
        box=self.page("Kiểm tra trước khi cấp số", "Trùng cùng tờ/thửa: loại toàn bộ nhóm. Thiếu tên/giấy tờ nhân thân/tờ/thửa/diện tích: không tạo file, không dùng số; xem ô lỗi trong Chi tiết.")
        toolbar=QHBoxLayout(); toolbar.addWidget(self.button("Kiểm tra dữ liệu",self.validate_source,True))
        toolbar.addWidget(self.button("Xuất báo cáo kiểm tra (không tạo Word)",self.export_validation)); box.addLayout(toolbar)
        self.summary=QLabel("Chưa kiểm tra."); self.summary.setWordWrap(True); box.addWidget(self.summary)
        self.table=QTableWidget(0,10); self.table.setHorizontalHeaderLabels(["Dòng Excel","STT hộ","Chủ hộ","Tờ mới","Thửa mới","Diện tích","Tên từ dòng","Trạng thái","Giấy tờ nhân thân","Chi tiết"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.setAlternatingRowColors(True); self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive); self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(2,185); self.table.setColumnWidth(7,155); self.table.cellDoubleClicked.connect(self.show_record_detail); box.addWidget(self.table,1)

    def make_preview_page(self):
        box=self.page("Xem một thông báo trước khi tạo", "Mở bản Word và kiểm tra cả số lẫn ngày thông báo. Ngày được lấy theo nhóm của chính số dự kiến; nếu file trước đó lỗi, đợt tạo sẽ dùng lại số và ngày gắn với số đó.")
        self.preview_choice=QComboBox(); box.addWidget(self.preview_choice)
        box.addWidget(self.button("Tạo file xem trước",self.make_preview,True)); self.preview_label=QLabel("Chưa có bản xem trước."); self.preview_label.setWordWrap(True); box.addWidget(self.preview_label)
        self.open_preview_button=self.button("Mở bản Word xem trước",self.open_preview); self.open_preview_button.setEnabled(False); box.addWidget(self.open_preview_button)
        self.confirm_button=self.button("Nội dung đúng — xác nhận tạo hàng loạt",self.confirm_batch,True); self.confirm_button.setEnabled(False); box.addWidget(self.confirm_button); box.addStretch()

    def make_progress_page(self):
        box=self.page("Đang tạo thông báo", "Mỗi file được kiểm tra trước khi dùng số. Một file lỗi không làm mất số và không làm dừng các file còn lại, trừ khi không thể ghi nhật ký.")
        self.progress=QProgressBar(); box.addWidget(self.progress); self.progress_label=QLabel("Chỉ bắt đầu sau khi xác nhận bản xem trước."); self.progress_label.setWordWrap(True); box.addWidget(self.progress_label)
        self.progress_detail=QPlainTextEdit(); self.progress_detail.setReadOnly(True); self.progress_detail.setMaximumBlockCount(2000); box.addWidget(self.progress_detail,1)

    def make_result_page(self):
        box=self.page("Kết quả và nhật ký", "Nhật ký cho biết dòng Excel, hộ, tờ/thửa, số đã dùng hoặc được giữ lại và cách kiểm tra lỗi. Không gửi thư mục nhật ký chứa dữ liệu cá nhân cho người không có quyền.")
        self.result_label=QLabel("Chưa tạo thông báo."); self.result_label.setWordWrap(True); box.addWidget(self.result_label)
        box.addWidget(self.button("Mở thư mục kết quả",self.open_result_folder))
        box.addWidget(self.button("Mở nhật ký TXT",lambda:self.open_result_log("txt")))
        box.addWidget(self.button("Mở nhật ký Excel",lambda:self.open_result_log("xlsx"))); box.addStretch()

    def invalidate(self, *_):
        self.inspection=None; self.preview_result=None
        if hasattr(self,"confirm_button"):
            self.confirm_button.setEnabled(False); self.open_preview_button.setEnabled(False)
            self.preview_label.setText("Cấu hình/dữ liệu đã thay đổi. Cần kiểm tra và xem trước lại.")
            self.summary.setText("Cần kiểm tra lại dữ liệu.")

    def numbering_changed(self, *_):
        listing=self.number_mode.currentData()=="list"
        self.start_number.setEnabled(not listing); self.number_list.setEnabled(listing); self.continue_check.setEnabled(listing)
        self.continue_number.setEnabled(listing and self.continue_check.isChecked()); self.number_date_box.setEnabled(listing); self.invalidate()

    def numbering_input_changed(self, *_):
        """Giữ số tiếp nối ở ngay sau số lớn nhất người dùng vừa nhập."""
        if self.number_mode.currentData()=="list" and self.continue_check.isChecked():
            from .core.numbering import parse_numbers
            specifications=[]
            if self.number_list.text().strip():
                specifications.append(self.number_list.text())
            else:
                specifications.extend(field.text() for _,field,_ in self.number_date_rows if field.text().strip())
            try:
                numbers=[number for specification in specifications for number in parse_numbers(specification)]
            except UserError:
                numbers=[]
            if numbers and max(numbers)<2147483647:
                self.continue_number.setValue(max(numbers)+1)
        self.invalidate()

    def add_number_date_rule(self, numbers="", iso_date=""):
        row=QWidget(); layout=QHBoxLayout(row); layout.setContentsMargins(0,0,0,0); layout.setSpacing(8)
        specification=QLineEdit(str(numbers)); specification.setPlaceholderText("Ví dụ: 300-350 hoặc 300,305-310")
        specification.setAccessibleName("Số thông báo hoặc khoảng số của nhóm ngày")
        rule_date=QDateEdit(); rule_date.setCalendarPopup(True); rule_date.setDisplayFormat("dd/MM/yyyy")
        parsed=QDate.fromString(str(iso_date),Qt.ISODate) if iso_date else QDate(self.inputs["year"].value(),self.inputs["month"].value(),self.inputs["day"].value())
        rule_date.setDate(parsed if parsed.isValid() else QDate.currentDate()); rule_date.setAccessibleName("Ngày áp dụng cho nhóm số thông báo")
        remove=self.button("Xóa",lambda checked=False,w=row:self.remove_number_date_rule(w))
        layout.addWidget(specification,1); layout.addWidget(rule_date); layout.addWidget(remove)
        specification.textChanged.connect(self.numbering_input_changed); rule_date.dateChanged.connect(self.invalidate)
        self.number_date_rows_layout.addWidget(row); self.number_date_rows.append((row,specification,rule_date)); self.invalidate()

    def remove_number_date_rule(self, row):
        for item in list(self.number_date_rows):
            if item[0] is row:
                self.number_date_rows.remove(item); self.number_date_rows_layout.removeWidget(row); row.deleteLater(); self.numbering_input_changed(); break

    def number_date_rules(self):
        return [{"numbers":field.text().strip(),"date":date_field.date().toString(Qt.ISODate)}
                for _,field,date_field in self.number_date_rows]

    def browse_file(self, field, filter_text):
        path,_=QFileDialog.getOpenFileName(self,"Chọn file",field.text(),filter_text)
        if path: field.setText(path)

    def browse_output(self):
        path=QFileDialog.getExistingDirectory(self,"Chọn thư mục đầu ra",self.output.text())
        if path: self.output.setText(path)

    def read_source(self):
        source = self.source.text()
        saved = self.saved_source_settings
        restore = saved if saved and saved.get("source") == source else None
        def read(job):
            info = workbook_info(source)
            if restore and restore.get("sheet") in info["sheets"]:
                try:
                    info = workbook_info(source,restore["sheet"],restore.get("header"),restore.get("depth",1))
                    info["restored_mapping"] = restore.get("mapping",{})
                except UserError:
                    pass  # Outdated header: show current detected columns for review.
            return info
        self.run_job(read,self.source_ready)

    def source_ready(self, info):
        self.sheet.blockSignals(True); self.sheet.clear(); self.sheet.addItems(info["sheets"]); self.sheet.setCurrentText(info["sheet"]); self.sheet.blockSignals(False)
        self.header.setValue(info["header_row"]); self.depth.setCurrentIndex(self.depth.findData(info["depth"]))
        self.columns_ready(info); self.steps.setCurrentRow(1)

    def sheet_changed(self, name):
        if name and not self.job:
            source = self.source.text()
            self.run_job(lambda job:workbook_info(source,name),self.source_ready)

    def update_columns(self):
        source,sheet,header,depth=self.source.text(),self.sheet.currentText(),self.header.value(),self.depth.currentData()
        self.run_job(lambda job:workbook_info(source,sheet,header,depth),lambda info:(self.columns_ready(info),self.steps.setCurrentRow(2)))

    def columns_ready(self, info):
        same_source = (self.source_info is not None and self.source_info.get("source") == info.get("source")
                       and self.source_info["sheet"] == info["sheet"])
        selected_mapping = ({key:combo.currentData() or "" for key,combo in self.mapping.items()} if same_source
                            else info.get("restored_mapping",info["suggestions"]))
        self.source_info = info
        self.sheet_hint.setText(f"{info['rows']} dòng · {info['columns']} cột · Dữ liệu bắt đầu tại dòng {info['header_row']+info['depth']}")
        for key,combo in self.mapping.items():
            combo.blockSignals(True); combo.clear(); combo.addItem("— Chưa chọn —","")
            for letter,label in info["headers"].items(): combo.addItem(f"{letter} — {label}",letter)
            selected = selected_mapping.get(key,info["suggestions"].get(key,""))
            combo.setCurrentIndex(max(0,combo.findData(selected))); combo.blockSignals(False)
        self.invalidate()

    def config(self):
        fields={key:(widget.value() if isinstance(widget,QSpinBox) else widget.text().strip()) for key,widget in self.inputs.items()}
        fields.update({"commune_name":"", "place":""})
        template_config=template_config_for_path(self.template.text())
        template_fields={key:self.template_inputs[key].text().strip()
                         for key in (*template_config.user_fields, *template_config.optional_fields)}
        config=BatchConfig(**fields,number_mode=self.number_mode.currentData(),start_number=self.start_number.value(),number_list=self.number_list.text(),
                           number_date_rules=self.number_date_rules(),
                           template_fields=template_fields,optional_empty=self.optional_empty.currentData(),
                           empty_location=self.empty_location.currentData(),
                           continue_number=self.continue_number.value() if self.continue_check.isChecked() and self.number_mode.currentData()=="list" else None)
        config.validate(key for key in template_config.user_fields if key in template_config.required_fields)
        from .core.numbering import NumberPool
        NumberPool.from_config(config)
        if not self.output.text().strip(): raise UserError("Hãy chọn thư mục đầu ra ở bước 4.")
        return config

    def refresh_template_config(self, *_):
        if not hasattr(self, "template_inputs"):
            return
        config=template_config_for_path(self.template.text())
        is_mao = config.id == "MAO_DIEN"
        self.optional_empty.setVisible(not is_mao); self.optional_empty_label.setVisible(not is_mao)
        self.empty_location.setVisible(is_mao); self.empty_location_label.setVisible(is_mao)
        static_text="; ".join(f"{FIELD_LABELS.get(key, key)}: {value}" for key,value in config.static_values.items()
                             if key in {"TEN_XA","DIA_DIEM","DON_VI_LUU","CHI_NHANH_VP_DKDD","CO_QUAN_THUE","NGUOI_KY"})
        self.template_static_note.setText(f"Mẫu đang dùng: {config.name}. Giá trị theo mẫu: {static_text or 'không có giá trị cố định'}. ")
        visible=set(config.user_fields) | set(config.optional_fields)
        for key,field in self.template_inputs.items():
            shown=key in visible
            field.setVisible(shown); self.template_field_labels[key].setVisible(shown)
            required=key in config.required_fields
            field.setPlaceholderText("Bắt buộc nhập" if required else "Có thể để trống")
            label=FIELD_LABELS.get(key, key)
            self.template_field_labels[key].setText(label + (" *" if required else ""))
        self.invalidate()

    def validate_source(self):
        try:
            self.config()
            mapping=ColumnMapping(**{key:combo.currentData() or "" for key,combo in self.mapping.items()})
            source,sheet,header,depth=self.source.text(),self.sheet.currentText(),self.header.value(),self.depth.currentData()
            start,end=self.row_start.text().strip(),self.row_end.text().strip()
            self.run_job(lambda job:inspect_workbook(source,sheet,header,depth,mapping,require_identity=True,
                                                      start_row=start,end_row=end),self.inspection_ready)
        except UserError as exc: self.error(str(exc))

    def inspection_ready(self, result):
        self.inspection=result; self.preview_result=None; self.confirm_button.setEnabled(False); self.open_preview_button.setEnabled(False)
        duplicates=sum(bool(r.duplicate_rows) for r in result.records); invalid=sum(bool(r.errors) and not r.duplicate_rows for r in result.records)
        selected=(f" | Phạm vi: dòng {result.selected_start_row}–{result.selected_end_row}" if result.selected_start_row is not None else " | Phạm vi: toàn bộ dữ liệu")
        self.summary.setText(f"Tổng dòng Excel: {result.total_rows}{selected} | Dòng thửa: {len(result.records)} | Có thể tạo: {len(result.valid_records)} | Trùng: {duplicates} | Thiếu/sai dữ liệu: {invalid}\n"
                             f"Bỏ qua: {len(result.summary_rows)} dòng tổng, {len(result.blank_rows)} dòng trống, {len(result.name_only_rows)} dòng không có thửa. Nhấp đúp dòng để xem chi tiết.")
        self.table.setRowCount(len(result.records)); self.preview_choice.clear()
        for index,r in enumerate(result.records):
            detail=" ".join(r.errors) or ("Trùng các dòng: "+", ".join(map(str,r.duplicate_rows)) if r.duplicate_rows else "Đủ dữ liệu; chưa cấp số")
            for col,value in enumerate([r.source_row,r.household_number,r.owner,r.sheet,r.parcel,r.area,r.owner_row or "",r.status,r.identity,detail]):
                item=QTableWidgetItem(str(value)); item.setToolTip(str(value))
                if not r.valid: item.setBackground(QColor("#fff3df")); item.setForeground(QColor("#783e13"))
                self.table.setItem(index,col,item)
            if r.valid: self.preview_choice.addItem(f"Dòng {r.source_row}: {r.owner} — Tờ {r.sheet}, thửa {r.parcel}")
        self.steps.setCurrentRow(4)

    def show_record_detail(self,row,_):
        if not self.inspection: return
        r=self.inspection.records[row]
        QMessageBox.information(self,"Chi tiết dòng nguồn",f"Trang tính: {self.inspection.sheet_name}\nDòng: {r.source_row}\nSTT hộ: {r.household_number or '[CHƯA XÁC ĐỊNH]'}\nChủ hộ lấy từ dòng: {r.owner_row}\n"
            +("\n".join(r.errors) or "Đủ các trường bắt buộc.")+("\nTrùng tại các dòng: "+", ".join(map(str,r.duplicate_rows)) if r.duplicate_rows else ""))

    def export_validation(self):
        try:
            if not self.inspection: raise UserError("Hãy kiểm tra dữ liệu trước khi xuất báo cáo.")
            if not self.output.text().strip(): raise UserError("Hãy chọn thư mục lưu tại bước 4.")
            from .core.logging import export_inspection
            inspection,output=self.inspection,self.output.text()
            def ready(result):
                QMessageBox.information(self,"Đã xuất báo cáo kiểm tra",f"Chưa tạo Word và chưa dùng số.\n\nTXT: {result['txt']}\n\nExcel: {result['xlsx']}")
            self.run_job(lambda job:export_inspection(inspection,output),ready)
        except UserError as exc: self.error(str(exc))

    def make_preview(self):
        try:
            if not self.inspection: raise UserError("Hãy kiểm tra dữ liệu ở bước 5 trước.")
            config=self.config(); template=self.template.text(); inspection=self.inspection; output=self.output.text(); index=self.preview_choice.currentIndex()
            def work(job):
                service=NoticeService(template,json.loads(resource("config/legal_defaults.json").read_text(encoding="utf-8")))
                preview=service.preview(inspection,config,output,index,data_dir()/"Xem_truoc")
                return service,preview
            self.run_job(work,self.preview_ready)
        except UserError as exc: self.error(str(exc))

    def preview_ready(self, value):
        self.service,self.preview_result=value; self.preview_label.setText(str(self.preview_result.path))
        self.open_preview_button.setEnabled(True); self.confirm_button.setEnabled(True); self.steps.setCurrentRow(5)

    def open_preview(self):
        if self.preview_result: self.open_path(self.preview_result.path)

    def confirm_batch(self):
        try:
            if not self.preview_result or not self.inspection: raise UserError("Chưa có bản xem trước hợp lệ.")
            config=self.config(); output=self.output.text(); inspection=self.inspection
            if self.service.signature(inspection,config,output)!=self.preview_result.signature:
                raise UserError("Thông tin đã thay đổi. Hãy xem trước lại.")
            dialog=QMessageBox(QMessageBox.Question,"Xác nhận tạo thông báo",
                f"Bạn đã kiểm tra bản Word xem trước và đồng ý tạo tối đa {len(inspection.valid_records)} file trong:\n{output}\n\nFile đã có sẽ không bị ghi đè.",parent=self)
            confirm=dialog.addButton("Đồng ý tạo",QMessageBox.AcceptRole)
            back=dialog.addButton("Quay lại kiểm tra",QMessageBox.RejectRole); dialog.setDefaultButton(back); dialog.exec()
            if dialog.clickedButton() is not confirm: return
            approval=self.service.approve(self.preview_result); self.preview_result=None; self.confirm_button.setEnabled(False)
            self.batch_errors=0; self.batch_duplicates=0
            self.progress_detail.clear(); self.steps.setCurrentRow(6)
            self.run_job(lambda job:self.service.generate(inspection,config,output,approval,job.advanced.emit,job.cancel_event.is_set),self.batch_ready)
        except UserError as exc: self.error(str(exc))

    def batch_progress(self,done,total,success,entry):
        if entry.status == "TRÙNG TỜ/THỬA": self.batch_duplicates += 1
        elif entry.status != "THÀNH CÔNG": self.batch_errors += 1
        self.progress.setMaximum(total); self.progress.setValue(done)
        self.progress_label.setText(f"Đã xử lý {done}/{total} · Thành công {success} · Lỗi/bỏ qua {self.batch_errors} · Trùng {self.batch_duplicates} · Còn lại {total-done}")
        self.progress_detail.appendPlainText(f"Dòng {entry.row} — {entry.status} — Số {entry.number if entry.number is not None else 'chưa cấp'}")

    def batch_ready(self,result):
        self.result_output = Path(self.output.text()).resolve()
        self.result=result; self.result_label.setText(f"{'ĐÃ DỪNG' if result['cancelled'] else 'HOÀN TẤT'}\nThành công: {result['success']} file\nĐã xử lý: {result['processed']}/{result['total']} dòng thửa\n"
            f"Không tạo trong các dòng đã xử lý: {result['processed']-result['success']}\nNhật ký: {result['txt']}\n{result['log_error']}")
        self.steps.setCurrentRow(7)

    def run_job(self,function,callback):
        if self.job: return
        self.job=Job(function,self); self.job.ready.connect(callback); self.job.failed.connect(self.error); self.job.advanced.connect(self.batch_progress)
        self.job.finished.connect(self.job_finished)
        for page in self.pages: page.setEnabled(False)
        self.steps.setEnabled(False); self.next.setEnabled(False); self.back.setEnabled(False); self.cancel.setEnabled(True)
        self.statusBar().showMessage("Đang xử lý… Dữ liệu và cấu hình tạm khóa để bảo đảm kết quả nhất quán.")
        self.job.start()

    def job_finished(self):
        job=self.job; self.job=None
        for page in self.pages: page.setEnabled(True)
        self.steps.setEnabled(True); self.next.setEnabled(True); self.back.setEnabled(True); self.cancel.setEnabled(False)
        self.numbering_changed_without_invalidation()
        self.statusBar().showMessage("Sẵn sàng. Kiểm tra kết quả trước khi sử dụng thông báo.")
        if job: job.deleteLater()

    def numbering_changed_without_invalidation(self):
        listing=self.number_mode.currentData()=="list"
        self.start_number.setEnabled(not listing); self.number_list.setEnabled(listing); self.continue_check.setEnabled(listing)
        self.continue_number.setEnabled(listing and self.continue_check.isChecked())

    def cancel_job(self):
        if self.job: self.job.cancel_event.set(); self.cancel.setEnabled(False); self.statusBar().showMessage("Đã yêu cầu dừng. Chờ thao tác hiện tại kết thúc an toàn.")

    def navigate(self,offset):
        current=self.steps.currentRow()
        if offset>0 and current==0:
            self.read_source(); return
        if offset>0 and current==1:
            self.update_columns(); return
        self.steps.setCurrentRow(max(0,min(7,current+offset)))

    def open_result_folder(self):
        if self.result and hasattr(self,"result_output"): self.open_path(self.result_output)
        else: self.error("Chưa tạo thông báo. Hãy kiểm tra và xác nhận bản xem trước.")

    def show_legal(self):
        dialog=QDialog(self); dialog.setWindowTitle("Nội dung cố định — theo bản nghiệp vụ gốc"); dialog.resize(780,580)
        layout=QVBoxLayout(dialog); text=QPlainTextEdit(); text.setReadOnly(True)
        values=json.loads(resource("config/legal_defaults.json").read_text(encoding="utf-8"))
        values.update({key:widget.text().strip() for key,widget in self.template_inputs.items()})
        labels={"SU_DUNG_RIENG":"Sử dụng riêng",
            "NGUON_GOC_SU_DUNG_DAT":"Nguồn gốc sử dụng đất","THUA_LIEN_KE":"Thửa liền kề","TO_LIEN_KE":"Tờ liền kề",
            "CHU_SU_HUU_LIEN_KE":"Chủ sở hữu liền kề","NOI_DUNG_QUYEN_LIEN_KE":"Quyền đối với thửa liền kề","TAI_SAN_DANG_KY":"Tài sản đăng ký",
            "GIAY_TO_DA_NOP":"Giấy tờ đã nộp",
            "CHI_NHANH_VP_DKDD":"Chi nhánh Văn phòng đăng ký đất đai","CO_QUAN_THUE":"Cơ quan thuế","DON_VI_LUU":"Đơn vị lưu","NGUOI_KY":"Người ký"}
        text.setPlainText("\n\n".join(f"{labels.get(key,'Nội dung cố định')}:\n{value or '(Để trống theo mẫu)'}" for key,value in values.items())); layout.addWidget(text)
        note=QLabel("Các ô nhập ở bước 4 được điền theo cấu hình hiện tại. Căn cứ và kết luận viết sẵn trong mẫu Word được giữ nguyên; kiểm tra lại bản xem trước trước khi tạo."); note.setWordWrap(True); layout.addWidget(note)
        button=QDialogButtonBox(QDialogButtonBox.Close); button.rejected.connect(dialog.reject); layout.addWidget(button); dialog.exec()

    def save_settings(self):
        try:
            config=self.config()
            data={"config":asdict(config),"source":self.source.text(),"template":self.template.text(),"output":self.output.text(),
                  "template_kind":"default" if Path(self.template.text()).resolve()==default_template_path().resolve() else "custom",
                  "sheet":self.sheet.currentText(),"header":self.header.value(),"depth":self.depth.currentData(),
                  "row_start":self.row_start.text().strip(),"row_end":self.row_end.text().strip(),
                  "mapping":{key:combo.currentData() for key,combo in self.mapping.items()}}
            temp=self.settings_path.with_suffix(".tmp"); temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); os.replace(temp,self.settings_path)
            self.saved_source_settings=data
            self.statusBar().showMessage("Đã lưu cấu hình. Không lưu CCCD hay toàn bộ bảng dữ liệu.")
        except Exception as exc: self.error(str(exc) if isinstance(exc,UserError) else "Không lưu được cấu hình. Kiểm tra quyền ghi thư mục người dùng.")

    def load_settings(self):
        if not self.settings_path.is_file(): return
        try:
            data=json.loads(self.settings_path.read_text(encoding="utf-8-sig")); config=data.get("config",{})
            for key,widget in self.inputs.items():
                if key in config:
                    if isinstance(widget,QSpinBox): widget.setValue(int(config[key]))
                    else: widget.setText(str(config[key]))
            self.source.setText(data.get("source","")); self.output.setText(data.get("output",""))
            self.row_start.setText(str(data.get("row_start","") or "")); self.row_end.setText(str(data.get("row_end","") or ""))
            self.template.setText(str(saved_template_path(data)))
            self.number_mode.setCurrentIndex(max(0,self.number_mode.findData(config.get("number_mode","start"))))
            self.start_number.setValue(int(config.get("start_number",1))); self.number_list.setText(config.get("number_list",""))
            saved_continuation=config.get("continue_number")
            # Cấu hình cũ không có số tiếp nối là nguyên nhân khiến đợt tạo dừng.
            # Khi mở lại, chuyển an toàn sang mặc định tự tiếp tục; không sửa file cấu hình trên đĩa.
            self.continue_check.setChecked(self.number_mode.currentData()=="list" or saved_continuation is not None)
            if saved_continuation is not None: self.continue_number.setValue(int(saved_continuation))
            for rule in config.get("number_date_rules",[]) or []:
                if isinstance(rule,dict): self.add_number_date_rule(rule.get("numbers",""),rule.get("date",""))
            if saved_continuation is None: self.numbering_input_changed()
            for key,value in config.get("template_fields",{}).items():
                if key in self.template_inputs: self.template_inputs[key].setText(str(value))
            self.optional_empty.setCurrentIndex(max(0,self.optional_empty.findData(config.get("optional_empty","blank"))))
            self.empty_location.setCurrentIndex(max(0,self.empty_location.findData(config.get("empty_location","blank"))))
            self.saved_source_settings=data
        except (OSError,ValueError,TypeError):
            self.statusBar().showMessage("Cấu hình cũ không đọc được. Đã giữ nguyên file, vui lòng nhập lại.")

    def open_path(self,path):
        if path.exists(): QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
        else: self.error("File hoặc thư mục chưa được tạo.")

    def open_result_log(self,key):
        if self.result and self.result.get(key): self.open_path(self.result[key])
        else: self.error("Chưa có nhật ký tương ứng. Hãy kiểm tra kết quả xử lý.")

    def error(self,message):
        QMessageBox.warning(self,"Cần kiểm tra",message)

    def closeEvent(self,event):
        if self.job and self.job.isRunning():
            self.cancel_job(); event.ignore()
            QMessageBox.information(self,"Đang kết thúc an toàn","Đã yêu cầu dừng. Chờ thao tác hiện tại kết thúc rồi đóng cửa sổ lại.")
        else: event.accept()
