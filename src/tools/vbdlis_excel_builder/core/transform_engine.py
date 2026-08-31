from __future__ import annotations

from typing import Any

from tools.vbdlis_excel_builder.models import FieldSchema, Household, MappingProfile, Severity, ValidationIssue
from tools.vbdlis_excel_builder.utils.text import is_blank

from .field_rule_engine import FieldRuleEngine, RowContext


class TransformEngine:
    def transform(
        self,
        households: list[Household],
        schemas: list[FieldSchema],
        profile: MappingProfile,
    ) -> tuple[list[dict[str, Any]], list[ValidationIssue], dict[str, int]]:
        engine = FieldRuleEngine(schemas, profile)
        output: list[dict[str, Any]] = []
        issues: list[ValidationIssue] = []
        with_gcn = 0
        without_gcn = 0
        fallback_count = 0
        stt = 0

        for household in households:
            expected = len(household.people) * len(household.parcels)
            household_start = len(output)
            for parcel in household.parcels:
                if parcel.certificate.has_data:
                    with_gcn += 1
                else:
                    without_gcn += 1
                location = parcel.location
                if is_blank(location):
                    if profile.location_fallback == "address":
                        location = profile.address
                    elif profile.location_fallback == "value":
                        location = profile.location_fallback_value
                    else:
                        location = ""
                    if location:
                        fallback_count += 1
                        issues.append(
                            ValidationIssue(
                                Severity.INFO,
                                "LOCATION_FALLBACK",
                                "Đã dùng giá trị fallback vì Xứ đồng trống.",
                                parcel.source_row,
                                household.household_id,
                                value=location,
                            )
                        )
                    else:
                        issues.append(
                            ValidationIssue(
                                Severity.WARNING,
                                "MISSING_LOCATION",
                                "Xứ đồng trống và không có fallback.",
                                parcel.source_row,
                                household.household_id,
                            )
                        )
                for person in household.people:
                    stt += 1
                    output.append(
                        engine.build_row(RowContext(stt, household, person, parcel, profile, str(location)))
                    )
            actual = len(output) - household_start
            if actual != expected:
                issues.append(
                    ValidationIssue(
                        Severity.ERROR,
                        "PERSON_PARCEL_PRODUCT_MISMATCH",
                        f"Người × Thửa sai: dự kiến {expected}, thực tế {actual}.",
                        household.source_row,
                        household.household_id,
                    )
                )

        valid_cccd = sum(1 for row in output if str(row.get("I", "")).isdigit() and len(str(row.get("I", ""))) == 12)
        stats = {
            "output_rows": len(output),
            "with_gcn": with_gcn,
            "without_gcn": without_gcn,
            "valid_cccd": valid_cccd,
            "missing_cccd": len(output) - valid_cccd,
            "location_fallbacks": fallback_count,
        }
        return output, issues, stats
