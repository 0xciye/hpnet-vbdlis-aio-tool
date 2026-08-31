from __future__ import annotations

from collections import defaultdict
from typing import Any

from tools.vbdlis_excel_builder.models import Certificate, Household, MappingProfile, Parcel, Person, Severity, ValidationIssue
from tools.vbdlis_excel_builder.utils.dates import normalize_birth_date
from tools.vbdlis_excel_builder.utils.text import (
    excel_identifier,
    infer_gender_from_cccd,
    is_blank,
    is_summary_label,
    normalize_area,
    normalize_cccd,
    normalize_name,
    normalize_whitespace,
)


def _mapped(row: dict[str, Any], mapping: dict[str, str], key: str) -> Any:
    column = mapping.get(key, "")
    return row.get(column) if column else None


def _summary_label(row: dict[str, Any], mapping: dict[str, str]) -> str:
    # Identity information is evidence of a person; keep such rows for normal
    # validation even if their name happens to resemble a total label.
    if any(not is_blank(_mapped(row, mapping, key)) for key in ("cccd", "birth_date")):
        return ""
    name = _mapped(row, mapping, "person_name")
    stt = _mapped(row, mapping, "household_stt")
    if is_summary_label(name):
        return normalize_whitespace(name)
    if is_blank(name) and is_summary_label(stt):
        return normalize_whitespace(stt)
    return ""


class HouseholdParser:
    def parse(
        self,
        rows: list[dict[str, Any]],
        profile: MappingProfile,
    ) -> tuple[list[Household], list[ValidationIssue], dict[str, int]]:
        mapping = profile.source_mapping
        households: list[Household] = []
        issues: list[ValidationIssue] = []
        duplicate_count = 0
        summary_count = 0
        current: Household | None = None
        implicit_id = 0

        def finish(household: Household | None) -> None:
            nonlocal duplicate_count
            if household is None:
                return
            seen: dict[tuple[str, str, str, str], Parcel] = {}
            identity_certificates: dict[tuple[str, str], set[tuple[tuple[str, str], ...]]] = defaultdict(set)
            unique: list[Parcel] = []
            for parcel in household.parcels:
                signature = parcel.certificate.signature
                if signature:
                    identity_certificates[parcel.identity_key].add(signature)
                existing = seen.get(parcel.duplicate_key)
                if existing is not None and existing.certificate.signature == signature:
                    duplicate_count += 1
                    issues.append(
                        ValidationIssue(
                            Severity.INFO,
                            "DUPLICATE_PARCEL_REMOVED",
                            "Đã loại một dòng thửa trùng hoàn toàn trong cùng hộ.",
                            parcel.source_row,
                            household.household_id,
                            value=f"{parcel.sheet_number}/{parcel.parcel_number}",
                        )
                    )
                    continue
                seen[parcel.duplicate_key] = parcel
                unique.append(parcel)
            household.parcels = unique
            for identity, signatures in identity_certificates.items():
                if len(signatures) > 1:
                    issues.append(
                        ValidationIssue(
                            Severity.ERROR,
                            "GCN_CONFLICT",
                            "Cùng tờ/thửa có nhiều bộ thông tin GCN khác nhau; không tự động chọn hoặc gộp.",
                            household.source_row,
                            household.household_id,
                            value=f"{identity[0]}/{identity[1]}",
                        )
                    )
            if not household.people:
                issues.append(
                    ValidationIssue(
                        Severity.ERROR,
                        "HOUSEHOLD_WITHOUT_PERSON",
                        "Hộ không có người hợp lệ.",
                        household.source_row,
                        household.household_id,
                    )
                )
            if not household.parcels:
                issues.append(
                    ValidationIssue(
                        Severity.WARNING,
                        "HOUSEHOLD_WITHOUT_PARCEL",
                        "Hộ không có thửa hợp lệ nên không sinh dòng output.",
                        household.source_row,
                        household.household_id,
                    )
                )
            households.append(household)

        for row in rows:
            source_row = int(row.get("_row", 0))
            label = _summary_label(row, mapping)
            if label:
                summary_count += 1
                issues.append(
                    ValidationIssue(
                        Severity.INFO,
                        "SUMMARY_ROW_SKIPPED",
                        f"Đã bỏ qua dòng tổng hợp '{label}'; không tạo người hoặc thửa từ dòng này.",
                        source_row,
                        current.household_id if current is not None else "",
                        value=label,
                    )
                )
                continue
            household_value = _mapped(row, mapping, "household_stt")
            starts_household = not is_blank(household_value)
            if not profile.household_mode:
                starts_household = True
                household_value = source_row
            if starts_household:
                finish(current)
                implicit_id += 1
                current = Household(excel_identifier(household_value) or str(implicit_id), source_row)
            elif current is None:
                if any(not is_blank(value) for key, value in row.items() if key != "_row"):
                    issues.append(
                        ValidationIssue(
                            Severity.ERROR,
                            "ROW_WITHOUT_HOUSEHOLD",
                            "Dòng dữ liệu xuất hiện trước dòng bắt đầu hộ (STT hộ trống).",
                            source_row,
                        )
                    )
                continue

            name_value = _mapped(row, mapping, "person_name")
            if not is_blank(name_value):
                name = normalize_name(name_value, profile.normalize_names)
                cccd_raw = _mapped(row, mapping, "cccd")
                cccd, cccd_valid = normalize_cccd(cccd_raw)
                if not cccd:
                    issues.append(
                        ValidationIssue(
                            Severity.ERROR,
                            "MISSING_CCCD",
                            "CCCD là bắt buộc; người này đang thiếu CCCD.",
                            source_row,
                            current.household_id,
                            name,
                        )
                    )
                    cccd = ""
                elif not cccd_valid:
                    issues.append(
                        ValidationIssue(
                            Severity.WARNING,
                            "INVALID_CCCD",
                            "CCCD đã có nhưng không ở dạng chuẩn 12 chữ số; cần kiểm tra lại.",
                            source_row,
                            current.household_id,
                            name,
                            cccd,
                        )
                    )
                    if profile.invalid_cccd_action == "error":
                        issues.append(
                            ValidationIssue(
                                Severity.ERROR,
                                "CCCD_BLOCKING",
                                "Cấu hình yêu cầu dừng khi CCCD không ở dạng chuẩn 12 chữ số.",
                                source_row,
                                current.household_id,
                                name,
                                cccd,
                            )
                        )
                person = Person(
                    name=name,
                    cccd=cccd,
                    birth_date=normalize_birth_date(_mapped(row, mapping, "birth_date")),
                    gender=infer_gender_from_cccd(cccd),
                    is_head=len(current.people) == 0,
                    source_row=source_row,
                    raw=dict(row),
                )
                current.people.append(person)
            elif any(not is_blank(_mapped(row, mapping, key)) for key in ("cccd", "birth_date")):
                issues.append(ValidationIssue(
                    Severity.ERROR, "MISSING_PERSON_NAME", "Dòng có CCCD/ngày sinh nhưng chưa có họ tên.",
                    source_row, current.household_id, source_fields=("person_name", "cccd", "birth_date")))

            sheet_number = _mapped(row, mapping, "sheet_number")
            parcel_number = _mapped(row, mapping, "parcel_number")
            area = _mapped(row, mapping, "area")
            location = _mapped(row, mapping, "land_location")
            gcn_values = {
                key: _mapped(row, mapping, key)
                for key in mapping
                if key.startswith("gcn_") and not is_blank(_mapped(row, mapping, key))
            }
            has_parcel_content = any(
                not is_blank(value)
                for value in (sheet_number, parcel_number, area, location, *gcn_values.values())
            )
            if has_parcel_content:
                missing = [
                    label
                    for label, value in (
                        ("Số tờ", sheet_number),
                        ("Số thửa", parcel_number),
                        ("Diện tích", area),
                    )
                    if is_blank(value)
                ]
                if missing:
                    issues.append(
                        ValidationIssue(
                            Severity.WARNING,
                            "INVALID_PARCEL",
                            f"Không tạo thửa vì thiếu: {', '.join(missing)}.",
                            source_row,
                            current.household_id,
                        )
                    )
                else:
                    if profile.gcn_mode == "all_without":
                        gcn_values = {}
                    certificate = Certificate(gcn_values)
                    if profile.gcn_mode == "with_gcn" and not certificate.has_data:
                        issues.append(
                            ValidationIssue(
                                Severity.WARNING,
                                "EXPECTED_GCN_MISSING",
                                "Chế độ dữ liệu có GCN nhưng thửa này chưa có thông tin GCN.",
                                source_row,
                                current.household_id,
                            )
                        )
                    current.parcels.append(
                        Parcel(
                            excel_identifier(sheet_number),
                            excel_identifier(parcel_number),
                            normalize_area(area),
                            normalize_whitespace(location),
                            certificate,
                            source_row,
                            dict(row),
                        )
                    )

        finish(current)
        stats = {
            "households": len(households),
            "people": sum(len(household.people) for household in households),
            "parcels": sum(len(household.parcels) for household in households),
            "duplicates": duplicate_count,
            "summary_rows_skipped": summary_count,
        }
        return households, issues, stats
