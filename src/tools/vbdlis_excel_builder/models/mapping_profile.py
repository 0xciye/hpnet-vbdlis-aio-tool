from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


DEFAULT_ITEM_2 = "{PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}"
DEFAULT_ITEM_49 = (
    "{PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}-TBXN.pdf, "
    "{PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}-DDK.pdf"
)


@dataclass(slots=True)
class MappingProfile:
    profile_name: str = "Mặc định"
    commune_code: str = ""
    address: str = ""
    prefix: str = "CHUACOGIAY"
    entity_type: str = "Hộ gia đình"
    owner_value: str = "Chủ hộ"
    member_value: str = "Thành viên hộ gia đình"
    document_type: str = "Loại 5"
    item_2_template: str = DEFAULT_ITEM_2
    item_49_template: str = DEFAULT_ITEM_49
    location_fallback: str = "address"
    location_fallback_value: str = ""
    gcn_mode: str = "auto"
    invalid_cccd_action: str = "keep"
    normalize_names: bool = True
    normalize_cccd: bool = True
    gender_mode: str = "cccd"
    household_mode: bool = True
    skip_invalid_data: bool = True
    source_mapping: dict[str, str] = field(default_factory=dict)
    field_rules: dict[str, dict[str, Any]] = field(default_factory=dict)
    output_folder: str = ""
    output_filename: str = "VBDLIS_Output.xlsx"
    export_audit_report: bool = True
    keep_reference_sheets: bool = False
    last_sheet: str = ""
    header_row: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MappingProfile":
        allowed = cls.__dataclass_fields__.keys()
        payload = {key: value for key, value in data.items() if key in allowed}
        # CCCD luôn phải có. Giá trị đã có nhưng chưa chuẩn có thể giữ để người dùng kiểm tra.
        payload["invalid_cccd_action"] = "error" if payload.get("invalid_cccd_action") == "error" else "keep"
        payload["normalize_cccd"] = True
        # Migrate existing/imported profiles to the mandatory CCCD gender rule.
        payload["gender_mode"] = "cccd"
        return cls(**payload)
