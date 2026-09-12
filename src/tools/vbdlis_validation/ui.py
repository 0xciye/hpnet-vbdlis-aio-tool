from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from tools.qt_worker import Worker
from tools.runtime_paths import tool_settings_path

from .messages import friendly_failure
from .models import ExcelConfig, RunConfig, ValidationMode, ValidationResult
from .service import ValidationService, headers, sheet_names

SOURCE_FIELDS = (
    ("owner", "Tên chủ hộ", True, ("chủ hộ", "họ tên", "tên hộ")),
    ("household_id", "Mã hộ (nếu có)", False, ("mã hộ", "stt hộ", "số thứ tự")),
    ("sheet", "Số tờ", True, ("số tờ", "tờ bản đồ", "tờ bđ")),
    ("parcel", "Số thửa", True, ("số thửa",)),
)
UPLOAD_FIELDS = (
    ("person", "Tên người", True, ("họ tên", "tên người")),
    ("role", "Vai trò", True, ("vai trò", "quan hệ", "đối tượng")),
    ("household_id", "Mã hộ (nếu có)", False, ("mã hộ", "stt hộ")),
    ("sheet", "Số tờ", True, ("số tờ", "tờ bản đồ", "tờ bđ")),
    ("parcel", "Số thửa", True, ("số thửa",)),
    ("tbxn", "Cột TBXN", False, ("tbxn", "thông báo xác nhận")),
    ("ddk", "Cột DDK", False, ("ddk", "đơn đăng ký")),
    ("combined", "Cột tài liệu dùng chung", False, ("tài liệu", "đính kèm", "thành phần hồ sơ")),
)


def validation_icon_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / "tools" / "vbdlis_validation" / "assets" / "app_icon.svg"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VBDLIS Upload Data Validation")
        self.resize(1100, 820)
        self.setMinimumSize(900, 680)
        self.setWindowIcon(QIcon(str(validation_icon_path())))
        self.service = ValidationService()
        self.worker: Worker | None = None
        self.result: ValidationResult | None = None
        self.settings_file = tool_settings_path(
            "VBDLIS Upload Data Validation", "settings.json", Path(__file__).resolve().parent,
            {"upload", "source", "tbxn_folder", "ddk_folder", "output_root"},
        )
        self._saved = self._load_settings()
        self._build_ui()
        self._restore_settings()

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 20, 24, 24)
        title = QLabel("Kiểm tra dữ liệu trước khi upload VBDLIS")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        intro = QLabel(
            "Kiểm tra Excel VBDLIS và TBXN/DDK theo từng hộ, từng thửa; có thể đối chiếu thêm Excel nguồn. "
            "Không sửa hoặc di chuyển file gốc."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        inputs = QGroupBox("1. Chọn dữ liệu")
        form = QFormLayout(inputs)
        self.upload_path, upload_button = self._path_picker("Chọn Excel VBDLIS…", self._browse_upload)
        self.source_path, self.source_button = self._path_picker("Chọn Excel nguồn…", self._browse_source)
        self.tbxn_path, tbxn_button = self._path_picker("Chọn folder TBXN…", lambda: self._browse_folder(self.tbxn_path))
        self.ddk_path, self.ddk_button = self._path_picker("Chọn folder DDK…", lambda: self._browse_folder(self.ddk_path))
        self.output_path, output_button = self._path_picker("Chọn nơi lưu kết quả…", lambda: self._browse_folder(self.output_path))
        form.addRow("Excel Upload VBDLIS", self._row(self.upload_path, upload_button))
        self.vbdlis_only = QCheckBox("Không có Excel nguồn — chỉ kiểm tra dữ liệu VBDLIS và tài liệu PDF")
        self.vbdlis_only.toggled.connect(self._mode_changed)
        form.addRow("Excel dữ liệu nguồn", self._row(self.source_path, self.source_button))
        form.addRow("Chế độ kiểm tra", self.vbdlis_only)
        form.addRow("Folder TBXN", self._row(self.tbxn_path, tbxn_button))
        form.addRow("Folder DDK", self._row(self.ddk_path, self.ddk_button))
        self.shared_folder = QCheckBox("TBXN và DDK dùng chung một folder")
        self.shared_folder.toggled.connect(self._shared_changed)
        form.addRow("", self.shared_folder)
        form.addRow("Nơi lưu kết quả", self._row(self.output_path, output_button))
        layout.addWidget(inputs)

        workbook_box = QGroupBox("2. Sheet và dòng tiêu đề")
        grid = QGridLayout(workbook_box)
        self.upload_sheet, self.source_sheet = QComboBox(), QComboBox()
        self.upload_header, self.source_header = QSpinBox(), QSpinBox()
        self.upload_header_2, self.source_header_2 = QSpinBox(), QSpinBox()
        for spin in (self.upload_header, self.source_header):
            spin.setRange(1, 200)
            spin.setValue(1)
        for spin in (self.upload_header_2, self.source_header_2):
            spin.setRange(0, 200)
            spin.setSpecialValueText("Không dùng")
        self.upload_sheet.currentTextChanged.connect(lambda: self._load_columns("upload"))
        self.source_sheet.currentTextChanged.connect(lambda: self._load_columns("source"))
        self.upload_header.valueChanged.connect(lambda: self._load_columns("upload"))
        self.source_header.valueChanged.connect(lambda: self._load_columns("source"))
        self.upload_header_2.valueChanged.connect(lambda: self._load_columns("upload"))
        self.source_header_2.valueChanged.connect(lambda: self._load_columns("source"))
        grid.addWidget(QLabel("Excel"), 0, 0); grid.addWidget(QLabel("Sheet"), 0, 1)
        grid.addWidget(QLabel("Tiêu đề tầng 1"), 0, 2); grid.addWidget(QLabel("Tiêu đề tầng 2"), 0, 3)
        grid.addWidget(QLabel("VBDLIS"), 1, 0); grid.addWidget(self.upload_sheet, 1, 1)
        grid.addWidget(self.upload_header, 1, 2); grid.addWidget(self.upload_header_2, 1, 3)
        grid.addWidget(QLabel("Nguồn"), 2, 0); grid.addWidget(self.source_sheet, 2, 1)
        grid.addWidget(self.source_header, 2, 2); grid.addWidget(self.source_header_2, 2, 3)
        layout.addWidget(workbook_box)

        mapping_box = QGroupBox("3. Chọn cột dữ liệu (Mapping)")
        mapping_grid = QGridLayout(mapping_box)
        self.source_mapping: dict[str, QComboBox] = {}
        self.upload_mapping: dict[str, QComboBox] = {}
        source_form, upload_form = QFormLayout(), QFormLayout()
        source_form.addRow(QLabel("Excel nguồn"))
        upload_form.addRow(QLabel("Excel VBDLIS"))
        for key, label, required, _ in SOURCE_FIELDS:
            combo = QComboBox(); combo.setAccessibleName(f"Nguồn: {label}")
            self.source_mapping[key] = combo
            source_form.addRow(label + (" *" if required else ""), combo)
        for key, label, required, _ in UPLOAD_FIELDS:
            combo = QComboBox(); combo.setAccessibleName(f"VBDLIS: {label}")
            self.upload_mapping[key] = combo
            upload_form.addRow(label + (" *" if required else ""), combo)
        mapping_grid.addLayout(source_form, 0, 0)
        mapping_grid.addLayout(upload_form, 0, 1)
        layout.addWidget(mapping_box)

        export_box = QGroupBox("4. Các cột giữ lại trong file kết quả")
        export_form = QFormLayout(export_box)
        self.export_start, self.export_end = QLineEdit("A"), QLineEdit("AZ")
        range_row = QHBoxLayout(); range_row.addWidget(self.export_start); range_row.addWidget(QLabel("đến")); range_row.addWidget(self.export_end); range_row.addStretch()
        export_form.addRow("Cột bắt đầu → kết thúc", range_row)
        layout.addWidget(export_box)

        signature_box = QGroupBox("5. Xử lý hồ sơ chưa ký số")
        signature_layout = QVBoxLayout(signature_box)
        self.separate_unsigned = QCheckBox("Tách các thửa chưa ký số khỏi file dữ liệu đã đủ tài liệu")
        self.separate_unsigned.setChecked(False)
        signature_layout.addWidget(QLabel("Mặc định giữ các dòng đã đủ TBXN + DDK trong file ĐỦ TÀI LIỆU (khuyến nghị)."))
        signature_layout.addWidget(self.separate_unsigned)
        layout.addWidget(signature_box)

        actions = QHBoxLayout()
        self.preview_button = QPushButton("KIỂM TRA ĐẦU VÀO")
        self.validate_button = QPushButton("KIỂM TRA & PHÂN LOẠI (VALIDATE DATA)")
        self.preview_button.clicked.connect(self.preview_inputs)
        self.validate_button.clicked.connect(self.validate_data)
        actions.addWidget(self.preview_button); actions.addWidget(self.validate_button); actions.addStretch()
        layout.addLayout(actions)
        self.progress_label = QLabel("Sẵn sàng")
        self.progress = QProgressBar(); self.progress.setRange(0, 100); self.progress.setValue(0)
        layout.addWidget(self.progress_label); layout.addWidget(self.progress)
        self.summary = QTextEdit(); self.summary.setReadOnly(True); self.summary.setMinimumHeight(150)
        layout.addWidget(self.summary)
        open_row = QHBoxLayout()
        self.open_folder = QPushButton("Mở thư mục kết quả")
        self.open_valid = QPushButton("Mở file dữ liệu chính")
        self.open_need_signature = QPushButton("Mở file cần ký")
        self.open_invalid = QPushButton("Mở file thiếu/lỗi")
        self.open_summary = QPushButton("Mở báo cáo")
        for button in (
            self.open_folder, self.open_valid, self.open_need_signature,
            self.open_invalid, self.open_summary,
        ):
            button.setEnabled(False); open_row.addWidget(button)
        self.open_folder.clicked.connect(lambda: self._open_result("output_folder"))
        self.open_valid.clicked.connect(lambda: self._open_result("valid_excel"))
        self.open_need_signature.clicked.connect(lambda: self._open_result("need_signature_excel"))
        self.open_invalid.clicked.connect(lambda: self._open_result("invalid_excel"))
        self.open_summary.clicked.connect(lambda: self._open_result("summary_excel"))
        open_row.addStretch(); layout.addLayout(open_row)
        scroll.setWidget(body)
        self.setCentralWidget(scroll)
        self.statusBar().showMessage("Chọn đủ bốn đầu vào, map cột và kiểm tra trước khi chạy.")

    @staticmethod
    def _row(*widgets) -> QWidget:
        container = QWidget(); row = QHBoxLayout(container); row.setContentsMargins(0, 0, 0, 0)
        for widget in widgets: row.addWidget(widget)
        return container

    @staticmethod
    def _path_picker(placeholder: str, callback) -> tuple[QLineEdit, QPushButton]:
        editor = QLineEdit(); editor.setPlaceholderText(placeholder)
        button = QPushButton("Chọn…"); button.clicked.connect(callback)
        return editor, button

    def _browse_upload(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Excel VBDLIS", self.upload_path.text(), "Excel (*.xlsx *.xlsm)")
        if path:
            self.upload_path.setText(path); self._load_sheets("upload")

    def _browse_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Excel nguồn", self.source_path.text(), "Excel (*.xlsx *.xlsm)")
        if path:
            self.source_path.setText(path); self._load_sheets("source")

    def _browse_folder(self, editor: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục", editor.text())
        if path:
            editor.setText(path)
            if editor is self.tbxn_path and self.shared_folder.isChecked():
                self.ddk_path.setText(path)

    def _shared_changed(self, checked: bool) -> None:
        self.ddk_path.setEnabled(not checked); self.ddk_button.setEnabled(not checked)
        if checked:
            self.ddk_path.setText(self.tbxn_path.text())

    def _mode_changed(self, vbdlis_only: bool) -> None:
        self.source_path.setEnabled(not vbdlis_only)
        self.source_button.setEnabled(not vbdlis_only)
        self.source_sheet.setEnabled(not vbdlis_only)
        self.source_header.setEnabled(not vbdlis_only)
        self.source_header_2.setEnabled(not vbdlis_only)
        for combo in self.source_mapping.values(): combo.setEnabled(not vbdlis_only)

    def _load_sheets(self, which: str) -> None:
        editor = self.upload_path if which == "upload" else self.source_path
        combo = self.upload_sheet if which == "upload" else self.source_sheet
        try:
            names = sheet_names(editor.text())
        except Exception as error:  # noqa: BLE001 - UI converts workbook errors to Vietnamese guidance
            QMessageBox.warning(self, "Không đọc được Excel", friendly_failure(str(error))); return
        saved_name = self._saved.get(f"{which}_sheet", "")
        combo.blockSignals(True); combo.clear(); combo.addItems(names)
        if saved_name in names: combo.setCurrentText(saved_name)
        combo.blockSignals(False)
        self._load_columns(which)

    def _load_columns(self, which: str) -> None:
        path = self.upload_path.text() if which == "upload" else self.source_path.text()
        sheet = self.upload_sheet.currentText() if which == "upload" else self.source_sheet.currentText()
        if not Path(path).is_file() or not sheet:
            return
        header_row = self.upload_header.value() if which == "upload" else self.source_header.value()
        header_row_2_value = self.upload_header_2.value() if which == "upload" else self.source_header_2.value()
        header_row_2 = header_row_2_value or None
        mapping = self.upload_mapping if which == "upload" else self.source_mapping
        fields = UPLOAD_FIELDS if which == "upload" else SOURCE_FIELDS
        try:
            options = headers(ExcelConfig(Path(path), sheet, header_row, {}, header_row_2))
        except Exception as error:  # noqa: BLE001 - UI converts workbook errors to Vietnamese guidance
            self.statusBar().showMessage(friendly_failure(str(error)).splitlines()[0], 7000); return
        saved_mapping = self._saved.get(f"{which}_mapping", {})
        for key, _label, _required, keywords in fields:
            combo = mapping[key]; combo.blockSignals(True); combo.clear(); combo.addItem("— Không dùng —", "")
            for letter, header in options:
                combo.addItem(f"{letter} — {header or '[Không có tiêu đề]'}", letter)
            saved_text = saved_mapping.get(key, "")
            restored = combo.findText(saved_text)
            if restored >= 0:
                combo.setCurrentIndex(restored)
            else:
                folded_options = [(index, combo.itemText(index).casefold()) for index in range(1, combo.count())]
                match = next((index for index, text in folded_options if any(word.casefold() in text for word in keywords)), 0)
                combo.setCurrentIndex(match)
            combo.blockSignals(False)

    def _config(self) -> RunConfig:
        ddk = self.tbxn_path.text() if self.shared_folder.isChecked() else self.ddk_path.text()
        return RunConfig(
            upload=ExcelConfig(
                Path(self.upload_path.text()), self.upload_sheet.currentText(), self.upload_header.value(),
                {key: combo.currentData() or "" for key, combo in self.upload_mapping.items()},
                self.upload_header_2.value() or None,
            ),
            source=None if self.vbdlis_only.isChecked() else ExcelConfig(
                Path(self.source_path.text()), self.source_sheet.currentText(), self.source_header.value(),
                {key: combo.currentData() or "" for key, combo in self.source_mapping.items()},
                self.source_header_2.value() or None,
            ),
            tbxn_folder=Path(self.tbxn_path.text()), ddk_folder=Path(ddk),
            output_root=Path(self.output_path.text()), export_start=self.export_start.text().strip(),
            export_end=self.export_end.text().strip(), shared_document_folder=self.shared_folder.isChecked(),
            validation_mode=(ValidationMode.VBDLIS_ONLY if self.vbdlis_only.isChecked() else ValidationMode.FULL_SOURCE_COMPARE),
            separate_unsigned=self.separate_unsigned.isChecked(),
        )

    def preview_inputs(self) -> None:
        config = self._config()
        self._start_worker(lambda: self.service.preview(config), self._preview_ready)

    def validate_data(self) -> None:
        config = self._config()
        def process(progress):
            preview = self.service.preview(config)
            return preview, self.service.run(config, progress)
        self._start_worker(process, self._validation_ready, with_progress=True)

    def _start_worker(self, function, completed, with_progress: bool = False) -> None:
        if self.worker and self.worker.isRunning():
            return
        self._save_settings()
        self.preview_button.setEnabled(False); self.validate_button.setEnabled(False)
        self.progress.setValue(0); self.progress_label.setText("Đang kiểm tra…")
        self.worker = Worker(function, self, with_progress=with_progress)
        if with_progress:
            self.worker.progress.connect(self._progress_changed)
        self.worker.succeeded.connect(completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _progress_changed(self, value: int, message) -> None:
        self.progress.setValue(value); self.progress_label.setText(str(message))

    def _preview_ready(self, preview: dict[str, int]) -> None:
        warnings = []
        if preview["unknown_pdfs"]:
            warnings.append(
                f"Có {preview['unknown_pdfs']:,} file PDF chưa xác định được là TBXN hay DDK. "
                "Hãy kiểm tra tên file trước khi chạy."
            )
        if not preview["head_rows"]:
            warnings.append(
                "Không tìm thấy dòng nào có vai trò Chủ hộ. Hãy chọn lại cột Vai trò, "
                "hoặc chọn cột Mã hộ nếu file có mã hộ."
            )
        warning = "\nCẢNH BÁO: " + " ".join(warnings) if warnings else ""
        source_text = (
            "Không chạy (chế độ chỉ kiểm tra VBDLIS)"
            if self.vbdlis_only.isChecked()
            else f"{preview['source_rows']:,} dòng; {preview['source_parcels']:,} thửa"
        )
        self.summary.setPlainText(
            f"Số dòng trong Excel VBDLIS: {preview['vbdlis_rows']:,}\n"
            f"Đối chiếu Excel nguồn: {source_text}\n"
            f"Số hộ nhận diện được: {preview['source_households']:,}\n"
            f"Số file TBXN tìm thấy: {preview['tbxn_pdfs']:,}\n"
            f"Số file DDK tìm thấy: {preview['ddk_pdfs']:,}\n"
            f"Số PDF chưa xác định được loại: {preview['unknown_pdfs']:,}{warning}"
        )
        self.progress.setValue(100); self.progress_label.setText("Đã kiểm tra đầu vào")

    def _validation_ready(self, payload) -> None:
        preview, result = payload
        self.result = result
        stats = result.stats
        self.summary.setPlainText(
            "Hoàn thành kiểm tra\n\n"
            f"Hộ: {stats['total_households']:,}\nTổng thửa: {stats['total_parcels']:,}\n"
            f"Dòng VBDLIS: {preview['vbdlis_rows']:,}\n"
            f"Sẵn sàng upload: {stats['ready_to_upload']:,}\n"
            f"Đủ tài liệu nhưng cần ký: {stats['need_signature']:,}\n"
            f"Thiếu tài liệu: {stats['missing_document']:,}\n"
            f"Chữ ký/file không hợp lệ: {stats['signature_invalid']:,}\n"
            f"Dữ liệu chưa khớp: {stats['data_error']:,}\n"
            f"Cần kiểm tra thủ công: {stats['review_required']:,}\n\n"
            f"Thiếu TBXN: {stats['missing_tbxn']:,}\nThiếu DDK: {stats['missing_ddk']:,}\n"
            f"Thiếu cả hai: {stats['missing_both']:,}\nTBXN chưa ký: {stats['tbxn_unsigned']:,}\n"
            f"DDK chưa ký: {stats['ddk_unsigned']:,}\n"
            f"Chữ ký không hợp lệ: {stats['tbxn_signature_invalid'] + stats['ddk_signature_invalid']:,}\n"
            f"Kết quả: {result.output_folder}"
        )
        self.open_valid.setText(
            "Mở Excel sẵn sàng upload"
            if self.separate_unsigned.isChecked()
            else "Mở Excel đủ tài liệu"
        )
        for button in (
            self.open_folder, self.open_valid, self.open_need_signature,
            self.open_invalid, self.open_summary,
        ):
            button.setEnabled(True)
        self.progress.setValue(100); self.progress_label.setText("Hoàn thành kiểm tra")
        self.statusBar().showMessage("Đã tạo đầy đủ Excel kết quả, summary, tài liệu lỗi và validation.log.")

    def _failed(self, message: str) -> None:
        self.progress_label.setText("Chưa thể hoàn tất — dữ liệu gốc vẫn an toàn")
        self.statusBar().showMessage("Chưa thể hoàn tất. Hãy đọc hướng dẫn trong hộp thông báo; dữ liệu gốc chưa bị thay đổi.")
        QMessageBox.warning(self, "Chưa thể hoàn tất kiểm tra", friendly_failure(message))

    def _finished(self) -> None:
        self.preview_button.setEnabled(True); self.validate_button.setEnabled(True); self.worker = None

    def _open_result(self, attribute: str) -> None:
        path = getattr(self.result, attribute, None) if self.result else None
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _load_settings(self) -> dict:
        try:
            return json.loads(self.settings_file.read_text(encoding="utf-8")) if self.settings_file.exists() else {}
        except (OSError, ValueError):
            return {}

    def _restore_settings(self) -> None:
        for key, editor in (
            ("upload", self.upload_path), ("source", self.source_path), ("tbxn_folder", self.tbxn_path),
            ("ddk_folder", self.ddk_path), ("output_root", self.output_path),
        ):
            editor.setText(self._saved.get(key, ""))
        self.upload_header.setValue(int(self._saved.get("upload_header", 1)))
        self.source_header.setValue(int(self._saved.get("source_header", 1)))
        self.upload_header_2.setValue(int(self._saved.get("upload_header_2", 0)))
        self.source_header_2.setValue(int(self._saved.get("source_header_2", 0)))
        self.export_start.setText(self._saved.get("export_start", "A")); self.export_end.setText(self._saved.get("export_end", "AZ"))
        self.shared_folder.setChecked(bool(self._saved.get("shared_folder", False)))
        self.vbdlis_only.setChecked(bool(self._saved.get("vbdlis_only", False)))
        self.separate_unsigned.setChecked(bool(self._saved.get("separate_unsigned", False)))
        if Path(self.upload_path.text()).is_file(): self._load_sheets("upload")
        if Path(self.source_path.text()).is_file(): self._load_sheets("source")

    def _save_settings(self) -> None:
        payload = {
            "upload": self.upload_path.text(), "source": self.source_path.text(),
            "tbxn_folder": self.tbxn_path.text(), "ddk_folder": self.ddk_path.text(),
            "output_root": self.output_path.text(), "upload_sheet": self.upload_sheet.currentText(),
            "source_sheet": self.source_sheet.currentText(), "upload_header": self.upload_header.value(),
            "source_header": self.source_header.value(), "upload_header_2": self.upload_header_2.value(),
            "source_header_2": self.source_header_2.value(), "export_start": self.export_start.text(),
            "export_end": self.export_end.text(), "shared_folder": self.shared_folder.isChecked(),
            "vbdlis_only": self.vbdlis_only.isChecked(),
            "separate_unsigned": self.separate_unsigned.isChecked(),
            "upload_mapping": {key: combo.currentText() for key, combo in self.upload_mapping.items()},
            "source_mapping": {key: combo.currentText() for key, combo in self.source_mapping.items()},
        }
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)
