from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
import hashlib
import json
import re
from .fields import FIELD_LABELS, REQUIRED_COMMON, has_content
from tools.vbdlis_excel_builder.models import Person


class UserError(ValueError):
    """A message suitable for the application's Vietnamese error panel."""


@dataclass(frozen=True)
class ColumnMapping:
    owner: str = "B"
    sheet: str = "G"
    parcel: str = "H"
    area: str = "K"
    location: str = "L"
    identity: str = ""
    household_index: str = "A"
    birth_date: str = ""

    def validate(self, max_columns):
        from openpyxl.utils import column_index_from_string
        used = []
        for field_name, value in asdict(self).items():
            if field_name in ("location", "identity", "birth_date") and not value:
                continue
            try:
                index = column_index_from_string(value)
            except (ValueError, TypeError):
                label = {"owner":"tên hộ","sheet":"tờ BĐ mới","parcel":"thửa BĐ mới","area":"diện tích","location":"xứ đồng","identity":"giấy tờ nhân thân","birth_date":"ngày sinh","household_index":"STT hộ"}[field_name]
                raise UserError(f"Cột {label} chưa được chọn hợp lệ. Hãy quay lại bước Đối chiếu cột.") from None
            if not 1 <= index <= max_columns:
                raise UserError(f"Cột {value} không có trong trang tính đang chọn.")
            used.append(index)
        if len(used) != len(set(used)):
            raise UserError("Một cột nguồn đang được chọn cho nhiều trường khác nhau. Hãy đối chiếu lại cột.")


@dataclass(frozen=True)
class BatchConfig:
    commune_code: str
    owner_address: str
    village: str
    commune_name: str
    administrative_address: str
    place: str
    day: int
    month: int
    year: int
    suffix: str = "TBXN"
    number_mode: str = "start"
    start_number: int = 1
    number_list: str = ""
    continue_number: int | None = None
    number_date_rules: list[dict[str, str]] = field(default_factory=list)
    template_fields: dict[str, str] = field(default_factory=dict)
    optional_empty: str = "blank"
    prefix: str = "CHUACOGIAY"

    def validate(self, required_template_fields=None):
        required = {"Mã đơn vị hành chính": self.commune_code, "Địa chỉ người sử dụng đất": self.owner_address,
                    "Tên thôn": self.village,
                    "Hậu tố tên file": self.suffix}
        required_keys = tuple(REQUIRED_COMMON) if required_template_fields is None else tuple(required_template_fields)
        required.update({FIELD_LABELS.get(key, key.replace("_", " ").title()): self.template_fields.get(key)
                         for key in required_keys})
        missing = [name for name, value in required.items() if not has_content(value)]
        if missing:
            raise UserError("Cần nhập: " + ", ".join(missing) + ".")
        if self.optional_empty not in ("blank", "dots"):
            raise UserError("Cách hiển thị ô không bắt buộc phải là để trống hoặc dấu chấm.")
        if not re.fullmatch(r"[0-9]{5}", self.commune_code.strip()):
            raise UserError("Mã đơn vị hành chính phải có đúng 5 chữ số.")
        if not re.fullmatch(r"[A-Za-z0-9_À-ỹ-]+", self.prefix.strip()):
            raise UserError("Tiền tố tên file chỉ được gồm chữ, số, dấu gạch ngang hoặc gạch dưới.")
        try:
            date(self.year, self.month, self.day)
        except ValueError:
            raise UserError("Ngày, tháng, năm thông báo không hợp lệ.") from None


@dataclass
class NoticeRecord:
    source_row: int
    owner: str
    owner_row: int | None
    sheet: str
    parcel: str
    area: str
    location: str
    errors: list[str] = field(default_factory=list)
    duplicate_rows: list[int] = field(default_factory=list)
    identity: str = ""
    identity_row: int | None = None
    household_number: str = ""
    household_people: list[Person] = field(default_factory=list)

    @property
    def head(self):
        return next((person for person in self.household_people if person.is_head), None)

    @property
    def members(self):
        return [person for person in self.household_people if not person.is_head]

    @property
    def valid(self):
        return not self.errors and not self.duplicate_rows

    @property
    def status(self):
        if self.duplicate_rows:
            return "TRÙNG TỜ/THỬA"
        if self.errors:
            return "LỖI DỮ LIỆU" if any("không hợp lệ" in e for e in self.errors) else "THIẾU DỮ LIỆU"
        return "HỢP LỆ"


@dataclass
class Inspection:
    source: Path
    sheet_name: str
    source_hash: str
    records: list[NoticeRecord]
    total_rows: int
    blank_rows: list[int]
    summary_rows: list[int]
    name_only_rows: list[int]
    header_row: int
    header_depth: int
    mapping: ColumnMapping
    selected_start_row: int | None = None
    selected_end_row: int | None = None

    @property
    def valid_records(self):
        return [r for r in self.records if r.valid]

    def signature(self):
        payload = {"source_hash": self.source_hash, "sheet": self.sheet_name, "header": self.header_row,
                   "depth": self.header_depth, "mapping": asdict(self.mapping), "records": [asdict(r) for r in self.records]}
        if self.selected_start_row is not None:
            payload["selected_rows"] = [self.selected_start_row, self.selected_end_row]
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
