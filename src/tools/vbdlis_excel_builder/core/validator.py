from __future__ import annotations

import re
from typing import Any

from tools.vbdlis_excel_builder.models import FieldSchema, MappingProfile, Severity, ValidationIssue
from tools.vbdlis_excel_builder.utils.text import is_blank


REQUIRED_SOURCE_MAPPINGS = {
    "household_stt": "STT hộ",
    "person_name": "Họ và tên",
    "cccd": "CCCD",
    "sheet_number": "Số tờ",
    "parcel_number": "Số thửa",
    "area": "Diện tích",
}


class Validator:
    def validate_profile(self, profile: MappingProfile) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for key, label in REQUIRED_SOURCE_MAPPINGS.items():
            if profile.household_mode or key != "household_stt":
                if not profile.source_mapping.get(key):
                    issues.append(
                        ValidationIssue(Severity.ERROR, "MISSING_MAPPING", f"Chưa ánh xạ trường bắt buộc: {label}.", source_fields=(key,))
                    )
        if not profile.commune_code.strip():
            issues.append(ValidationIssue(Severity.ERROR, "MISSING_COMMUNE_CODE", "Chưa nhập mã xã."))
        if profile.owner_value != "Chủ hộ" or profile.member_value != "Thành viên hộ gia đình":
            issues.append(
                ValidationIssue(
                    Severity.WARNING,
                    "ROLE_RULE_CHANGED",
                    "Giá trị vai trò đã khác rule chạy thành công: Chủ hộ / Thành viên hộ gia đình.",
                )
            )
        try:
            from tools.vbdlis_excel_builder.utils.text import safe_template_replace

            placeholders = {
                "PREFIX": "P", "MA_XA": "1", "SO_TO": "2", "SO_THUA": "3",
                "HO_TEN": "A", "CCCD": "0", "DIA_CHI": "D", "XU_DONG": "X", "STT": 1,
            }
            safe_template_replace(profile.item_2_template, placeholders)
            safe_template_replace(profile.item_49_template, placeholders)
        except ValueError as exc:
            issues.append(ValidationIssue(Severity.ERROR, "INVALID_TEMPLATE_RULE", str(exc)))
        return issues

    def validate_output(
        self,
        rows: list[dict[str, Any]],
        schemas: list[FieldSchema],
        profile: MappingProfile,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        required = [schema for schema in schemas if schema.required]
        actual_stt = [row.get("A") for row in rows]
        expected_stt = list(range(1, len(rows) + 1))
        if actual_stt != expected_stt:
            issues.append(ValidationIssue(Severity.ERROR, "INVALID_OUTPUT_STT", "STT output không liên tục từ 1 đến N."))

        allowed_roles = {profile.owner_value, profile.member_value}
        item_49_pattern = re.compile(r"^.+-TBXN\.pdf, .+-DDK\.pdf$")
        for index, row in enumerate(rows, 1):
            meta = row.get("_meta", {})
            for schema in required:
                if is_blank(row.get(schema.column)):
                    issues.append(
                        ValidationIssue(
                            Severity.ERROR,
                            "MISSING_REQUIRED_OUTPUT",
                            f"Thiếu trường bắt buộc {schema.item or schema.column}: {schema.name}",
                            meta.get("source_row", 0),
                            meta.get("household", ""),
                            meta.get("person", ""),
                            output_column=schema.column,
                            output_row=index,
                        )
                    )
            cccd = str(row.get("I", "") or "").strip()
            if is_blank(cccd):
                issues.append(
                    ValidationIssue(
                        Severity.ERROR,
                        "MISSING_REQUIRED_CCCD_OUTPUT",
                        "CCCD output là bắt buộc và không được để trống.",
                        meta.get("source_row", 0),
                        meta.get("household", ""),
                        meta.get("person", ""),
                        cccd,
                        source_fields=("cccd",),
                        output_column="I",
                        output_row=index,
                    )
                )
            if row.get("N") not in allowed_roles:
                issues.append(
                    ValidationIssue(
                        Severity.ERROR,
                        "INVALID_ROLE",
                        "Vai trò output không hợp lệ.",
                        meta.get("source_row", 0),
                        meta.get("household", ""),
                        meta.get("person", ""),
                        row.get("N", ""),
                        output_column="N",
                        output_row=index,
                    )
                )
            if not item_49_pattern.fullmatch(str(row.get("AX", ""))):
                issues.append(
                    ValidationIssue(
                        Severity.ERROR,
                        "INVALID_ITEM_49",
                        "Mục 49 không đúng cấu trúc TBXN + DDK.",
                        meta.get("source_row", 0),
                        meta.get("household", ""),
                        meta.get("person", ""),
                        row.get("AX", ""),
                        output_column="AX",
                        output_row=index,
                    )
                )
        # Preserve every occurrence for the saved diagnostic report.
        return issues
