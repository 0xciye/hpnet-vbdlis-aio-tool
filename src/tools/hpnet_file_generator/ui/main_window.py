import os
import json
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QCheckBox, QComboBox, QTableWidget, 
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QProgressBar,
    QTabWidget, QFormLayout, QGroupBox, QSplitter, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QIcon

from tools.hpnet_file_generator.models.data_models import ProfileConfig, ActionStatus
from tools.hpnet_file_generator.core.excel_reader import ExcelReader
from tools.hpnet_file_generator.core.source_scanner import SourceScanner
from tools.hpnet_file_generator.core.person_matcher import PersonMatcher
from tools.hpnet_file_generator.core.action_planner import ActionPlanner
from tools.hpnet_file_generator.core.file_generator import FileGenerator
from tools.runtime_paths import tool_settings_path
from launcher_ui.theme import palette, style_for_mode, system_dark_mode

CONFIG_FILE = "settings.json"

class Worker(QThread):
    progress = Signal(int, int)
    finished = Signal()
    error = Signal(str)

    def __init__(self, actions, generator):
        super().__init__()
        self.actions = actions
        self.generator = generator
        self.is_running = True

    def run(self):
        total = len(self.actions)
        for i, action in enumerate(self.actions):
            if not self.is_running:
                break
            self.generator.execute_action(action)
            self.progress.emit(i + 1, total)
        self.finished.emit()

    def stop(self):
        self.is_running = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HPNet Excel File Generator")
        self.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[1] / "assets" / "app_icon.ico")))
        self.resize(1000, 700)
        app = QApplication.instance(); mode = app.property("darkMode") if app else None
        dark = bool(mode) if mode is not None else system_dark_mode()
        self.setStyleSheet(style_for_mode(dark))
        self.setPalette(palette(dark))
        
        self.config = ProfileConfig()
        self.excel_records = []
        self.source_files = []
        self.action_plan = []
        self.worker = None
        self.settings_file = tool_settings_path("Auto Rename", CONFIG_FILE, Path(__file__).resolve().parents[1], {"excel", "source", "output"})
        
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        self.setup_tab_excel()
        self.setup_tab_source()
        self.setup_tab_match()
        self.setup_tab_output()
        self.setup_tab_generate()
        
    def setup_tab_excel(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # File selector
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("File Excel:"))
        self.txt_excel = QLineEdit()
        self.txt_excel.setReadOnly(True)
        h1.addWidget(self.txt_excel)
        btn_browse = QPushButton("Chọn...")
        btn_browse.clicked.connect(self.browse_excel)
        h1.addWidget(btn_browse)
        layout.addLayout(h1)
        
        # Sheet & Header
        form = QFormLayout()
        self.cmb_sheet = QComboBox()
        self.spin_header = QLineEdit("1")
        form.addRow("Sheet:", self.cmb_sheet)
        form.addRow("Dòng bắt đầu tiêu đề:", self.spin_header)
        layout.addLayout(form)
        
        btn_load = QPushButton("Đọc dữ liệu Excel")
        btn_load.clicked.connect(self.load_excel_headers)
        layout.addWidget(btn_load)
        
        self.lbl_excel_status = QLabel("Chưa tải file.")
        layout.addWidget(self.lbl_excel_status)
        layout.addStretch()
        
        self.tabs.addTab(tab, "1. Dữ liệu Excel")
        
    def setup_tab_source(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Thư mục File Nguồn:"))
        self.txt_source_dir = QLineEdit()
        self.txt_source_dir.setReadOnly(True)
        h1.addWidget(self.txt_source_dir)
        btn_browse = QPushButton("Chọn...")
        btn_browse.clicked.connect(self.browse_source)
        h1.addWidget(btn_browse)
        layout.addLayout(h1)
        
        self.chk_remove_prefix = QCheckBox("Bỏ STT đầu tên file (VD: '1. Nguyễn Văn A' -> 'Nguyễn Văn A')")
        self.chk_remove_prefix.setChecked(True)
        layout.addWidget(self.chk_remove_prefix)
        
        btn_scan = QPushButton("Quét thư mục")
        btn_scan.clicked.connect(self.scan_source)
        layout.addWidget(btn_scan)
        
        self.tbl_source = QTableWidget(0, 3)
        self.tbl_source.setHorizontalHeaderLabels(["Tên file gốc", "Tên nhận diện", "Trạng thái"])
        self.tbl_source.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_source)
        
        self.tabs.addTab(tab, "2. File Nguồn")
        
    def setup_tab_match(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        form = QFormLayout()
        self.cmb_map_name = QComboBox()
        self.cmb_map_sheet = QComboBox()
        self.cmb_map_parcel = QComboBox()
        self.cmb_map_stt = QComboBox()
        
        form.addRow("Cột Họ Tên (Bắt buộc):", self.cmb_map_name)
        form.addRow("Cột Số Tờ (Bắt buộc):", self.cmb_map_sheet)
        form.addRow("Cột Số Thửa (Bắt buộc):", self.cmb_map_parcel)
        form.addRow("Cột STT / Khóa phụ:", self.cmb_map_stt)
        layout.addLayout(form)
        
        btn_match = QPushButton("Phân tích Match")
        btn_match.clicked.connect(self.run_match)
        layout.addWidget(btn_match)
        
        self.tbl_match = QTableWidget(0, 4)
        self.tbl_match.setHorizontalHeaderLabels(["File", "Người trong Excel", "Số thửa", "Ghi chú"])
        self.tbl_match.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_match)
        
        self.tabs.addTab(tab, "3. Ánh xạ & Match")
        
    def setup_tab_output(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        form = QFormLayout()
        self.txt_ma_dvhc = QLineEdit(self.config.ma_dvhc)
        self.txt_prefix = QLineEdit(self.config.prefix)
        self.txt_template = QLineEdit(self.config.template)
        
        self.cmb_suffix1 = QCheckBox("TBXN")
        self.cmb_suffix2 = QCheckBox("DDK")
        self.cmb_suffix1.setChecked(True)
        
        form.addRow("Mã ĐVHC:", self.txt_ma_dvhc)
        form.addRow("Prefix:", self.txt_prefix)
        form.addRow("Template Tên:", self.txt_template)
        
        suffix_layout = QHBoxLayout()
        suffix_layout.addWidget(self.cmb_suffix1)
        suffix_layout.addWidget(self.cmb_suffix2)
        form.addRow("Hậu tố (Suffix):", suffix_layout)
        
        h1 = QHBoxLayout()
        self.txt_out_dir = QLineEdit()
        self.txt_out_dir.setReadOnly(True)
        h1.addWidget(self.txt_out_dir)
        btn_browse = QPushButton("Chọn...")
        btn_browse.clicked.connect(self.browse_out)
        h1.addWidget(btn_browse)
        form.addRow("Thư mục Output:", h1)
        
        layout.addLayout(form)
        
        lbl_hint = QLabel("Placeholders: {PREFIX}, {MA_DVHC}, {SO_TO}, {SO_THUA}, {HAU_TO}, {HO_TEN}, {STT}, {SOURCE_NAME}")
        layout.addWidget(lbl_hint)
        layout.addStretch()
        
        self.tabs.addTab(tab, "4. Tên File & Output")
        
    def setup_tab_generate(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        btn_plan = QPushButton("1. Xem trước (Preview Action Plan)")
        btn_plan.clicked.connect(self.build_action_plan)
        layout.addWidget(btn_plan)
        
        self.tbl_plan = QTableWidget(0, 6)
        self.tbl_plan.setHorizontalHeaderLabels(["Nguồn", "Người", "Tờ", "Thửa", "Output", "Trạng thái"])
        self.tbl_plan.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tbl_plan)
        
        self.lbl_stats = QLabel("Thống kê...")
        layout.addWidget(self.lbl_stats)
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        btn_run = QPushButton("2. Tạo File")
        btn_run.clicked.connect(self.run_generation)
        layout.addWidget(btn_run)
        
        self.tabs.addTab(tab, "5. Kiểm tra & Tạo")
        
    def browse_excel(self):
        file, _ = QFileDialog.getOpenFileName(self, "Chọn file Excel", "", "Excel Files (*.xlsx *.xls)")
        if file:
            self.txt_excel.setText(file)
            reader = ExcelReader(file)
            reader.load()
            self.cmb_sheet.clear()
            self.cmb_sheet.addItems(reader.sheet_names)
            
    def load_excel_headers(self):
        file = self.txt_excel.text()
        sheet = self.cmb_sheet.currentText()
        if not file or not sheet:
            return
            
        try:
            row = int(self.spin_header.text())
            reader = ExcelReader(file)
            headers = reader.get_headers(sheet, row)
            depth = reader.header_depth(sheet, row)
            visible_headers = [header for header in headers if header]
            
            for cmb in [self.cmb_map_name, self.cmb_map_sheet, self.cmb_map_parcel, self.cmb_map_stt]:
                cmb.clear()
                cmb.addItem("")
                cmb.addItems(visible_headers)

            self._select_header(self.cmb_map_name, visible_headers, ("tên hộ", "họ và tên", "họ tên"))
            self._select_header(
                self.cmb_map_sheet, visible_headers,
                ("tờ bản đồ", "tờ bđ", "số tờ"), excluded_names=("số thửa",)
            )
            self._select_header(self.cmb_map_parcel, visible_headers, ("số thửa",))
            self._select_header(self.cmb_map_stt, visible_headers, ("stt", "số thứ tự"))
                
            self.lbl_excel_status.setText(
                f"Đã nhận diện {len(visible_headers)} cột từ {depth} dòng tiêu đề. "
                "Hãy kiểm tra các cột phần mềm đã chọn sẵn."
            )
            self.tabs.setCurrentIndex(1)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", str(e))

    @staticmethod
    def _select_header(combo, headers, preferred_names, excluded_names=()):
        for preferred in preferred_names:
            for index, header in enumerate(headers, start=1):
                folded = header.casefold()
                if (preferred.casefold() in folded
                        and not any(excluded.casefold() in folded for excluded in excluded_names)):
                    combo.setCurrentIndex(index)
                    return
            
    def browse_source(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục Nguồn")
        if folder:
            self.txt_source_dir.setText(folder)
            
    def scan_source(self):
        folder = self.txt_source_dir.text()
        if not folder:
            return
            
        scanner = SourceScanner(folder, self.config.extensions, self.chk_remove_prefix.isChecked())
        self.source_files = scanner.scan()
        
        self.tbl_source.setRowCount(0)
        for i, sf in enumerate(self.source_files):
            self.tbl_source.insertRow(i)
            self.tbl_source.setItem(i, 0, QTableWidgetItem(sf.filename))
            self.tbl_source.setItem(i, 1, QTableWidgetItem(sf.normalized_name))
            self.tbl_source.setItem(i, 2, QTableWidgetItem("Đã quét"))
            
        self.tabs.setCurrentIndex(2)

    def run_match(self):
        # 1. Read Excel records
        file = self.txt_excel.text()
        sheet = self.cmb_sheet.currentText()
        if not file or not self.cmb_map_name.currentText():
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file Excel và map cột Họ tên.")
            return
            
        mapping = {
            'ho_ten': self.cmb_map_name.currentText(),
            'so_to': self.cmb_map_sheet.currentText(),
            'so_thua': self.cmb_map_parcel.currentText(),
        }
        if self.cmb_map_stt.currentText():
            mapping['secondary_key'] = self.cmb_map_stt.currentText()
            
        reader = ExcelReader(file)
        try:
            self.excel_records = reader.read_data(sheet, int(self.spin_header.text()), mapping)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi đọc Excel", str(e))
            return
            
        # 2. Match
        matcher = PersonMatcher(self.excel_records, self.source_files)
        matcher.match()
        
        self.tbl_match.setRowCount(0)
        for i, sf in enumerate(self.source_files):
            self.tbl_match.insertRow(i)
            self.tbl_match.setItem(i, 0, QTableWidgetItem(sf.filename))
            if sf.is_ambiguous:
                self.tbl_match.setItem(i, 1, QTableWidgetItem("TRÙNG TÊN (Ambiguous)"))
                self.tbl_match.setItem(i, 2, QTableWidgetItem("-"))
                self.tbl_match.setItem(i, 3, QTableWidgetItem("Cần khóa phụ để phân biệt"))
            elif sf.matched_person:
                self.tbl_match.setItem(i, 1, QTableWidgetItem(sf.matched_person.ho_ten))
                self.tbl_match.setItem(i, 2, QTableWidgetItem(str(len(sf.matched_person.parcels))))
                self.tbl_match.setItem(i, 3, QTableWidgetItem("OK"))
            else:
                self.tbl_match.setItem(i, 1, QTableWidgetItem("Không tìm thấy"))
                self.tbl_match.setItem(i, 2, QTableWidgetItem("0"))
                self.tbl_match.setItem(i, 3, QTableWidgetItem("WARNING"))
                
        self.tabs.setCurrentIndex(3)
        
    def browse_out(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục Output")
        if folder:
            self.txt_out_dir.setText(folder)
            
    def build_action_plan(self):
        if not self.txt_out_dir.text():
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục Output.")
            return
            
        # Update config
        self.config.ma_dvhc = self.txt_ma_dvhc.text()
        self.config.prefix = self.txt_prefix.text()
        self.config.template = self.txt_template.text()
        
        suffixes = []
        if self.cmb_suffix1.isChecked(): suffixes.append("TBXN")
        if self.cmb_suffix2.isChecked(): suffixes.append("DDK")
        self.config.suffixes = suffixes if suffixes else [""] # fallback
        
        planner = ActionPlanner(self.source_files, self.txt_out_dir.text(), self.config)
        self.action_plan = planner.build_plan()
        
        self.tbl_plan.setRowCount(0)
        for i, a in enumerate(self.action_plan):
            self.tbl_plan.insertRow(i)
            self.tbl_plan.setItem(i, 0, QTableWidgetItem(a.source_file.filename))
            self.tbl_plan.setItem(i, 1, QTableWidgetItem(a.source_file.matched_person.ho_ten if a.source_file.matched_person else ""))
            self.tbl_plan.setItem(i, 2, QTableWidgetItem(a.parcel.so_to if a.parcel else ""))
            self.tbl_plan.setItem(i, 3, QTableWidgetItem(a.parcel.so_thua if a.parcel else ""))
            self.tbl_plan.setItem(i, 4, QTableWidgetItem(a.target_filename))
            
            status_text = a.status.value
            if a.status == ActionStatus.CONFLICT:
                status_text += f" ({a.conflict_path.name})"
            item = QTableWidgetItem(status_text)
            if a.status == ActionStatus.CONFLICT: item.setBackground(QColor(255, 200, 0))
            if a.status == ActionStatus.WARNING: item.setBackground(QColor(255, 150, 150))
            self.tbl_plan.setItem(i, 5, item)
            
        # Stats
        ready = sum(1 for a in self.action_plan if a.status == ActionStatus.READY)
        conflicts = sum(1 for a in self.action_plan if a.status == ActionStatus.CONFLICT)
        self.lbl_stats.setText(f"File sẽ tạo (READY): {ready} | CONFLICT: {conflicts}")

    def run_generation(self):
        valid_actions = [a for a in self.action_plan if a.status in (ActionStatus.READY, ActionStatus.CONFLICT)]
        if not valid_actions:
            QMessageBox.warning(self, "Lỗi", "Không có file nào để tạo.")
            return
            
        generator = FileGenerator()
        self.progress.setVisible(True)
        self.progress.setMaximum(len(valid_actions))
        
        self.worker = Worker(valid_actions, generator)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.on_generate_finished)
        self.worker.start()
        
    def on_generate_finished(self):
        self.progress.setVisible(False)
        success = sum(1 for a in self.action_plan if a.status == ActionStatus.SUCCESS)
        QMessageBox.information(self, "Hoàn thành", f"Đã xử lý xong {success} file.")

    def load_settings(self):
        if self.settings_file.exists():
            try:
                with self.settings_file.open('r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                    self.txt_excel.setText(data.get('excel', ''))
                    self.txt_source_dir.setText(data.get('source', ''))
                    self.txt_out_dir.setText(data.get('output', ''))
            except:
                pass
                
    def closeEvent(self, event):
        data = {
            'excel': self.txt_excel.text(),
            'source': self.txt_source_dir.text(),
            'output': self.txt_out_dir.text()
        }
        with self.settings_file.open('w', encoding='utf-8') as f:
            json.dump(data, f)
        event.accept()
