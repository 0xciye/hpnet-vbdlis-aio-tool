"""Apply explicit exclusion rules without changing the user's source workbook."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import replace

from tools.vbdlis_excel_builder.models import Household, MappingProfile, Severity, ValidationIssue


INCOMPLETE_HOUSEHOLD_CODES = {
    "MISSING_CCCD", "MISSING_PERSON_NAME", "INVALID_PARCEL",
    "HOUSEHOLD_WITHOUT_PERSON", "HOUSEHOLD_WITHOUT_PARCEL",
}


def apply_input_policy(households: list[Household], issues: list[ValidationIssue], profile: MappingProfile):
    if not profile.skip_invalid_data:
        return households, issues, {}
    starts = [h.source_row for h in households]
    grouped: dict[int, list[ValidationIssue]] = {row: [] for row in starts}
    for issue in issues:
        index = bisect_right(starts, issue.source_row) - 1
        if index >= 0:
            grouped[starts[index]].append(issue)
    kept = []
    skipped_households: set[int] = set()
    skipped_people: set[int] = set()
    extra = []
    for household in households:
        related = grouped[household.source_row]
        incomplete = [i for i in related if i.code in INCOMPLETE_HOUSEHOLD_CODES]
        invalid_rows = {i.source_row for i in related if i.code == "INVALID_CCCD"}
        valid_people = [p for p in household.people if p.source_row not in invalid_rows]
        if incomplete or not valid_people:
            skipped_households.add(household.source_row)
            reasons = "; ".join(f"dòng {i.source_row}: {i.message}" for i in incomplete)
            if not incomplete:
                reasons = "Không còn người có CCCD hợp lệ sau khi kiểm tra."
            extra.append(ValidationIssue(
                Severity.WARNING, "HOUSEHOLD_SKIPPED", "Đã bỏ toàn bộ hộ. Lý do: " + reasons,
                household.source_row, household.household_id,
                value=f"Không xuất {len(household.people)} người và {len(household.parcels)} thửa của hộ này.",
                source_fields=("person_name", "cccd", "sheet_number", "parcel_number", "area"),
                disposition="household_skipped"))
        else:
            for person in household.people:
                if person.source_row in invalid_rows:
                    skipped_people.add(person.source_row)
                    extra.append(ValidationIssue(
                        Severity.WARNING, "PERSON_SKIPPED", "Đã bỏ người có CCCD sai định dạng 12 chữ số.",
                        person.source_row, household.household_id, person.name, person.cccd,
                        source_fields=("cccd",), disposition="person_skipped"))
                    if person.is_head:
                        extra.append(ValidationIssue(
                            Severity.WARNING, "HOUSEHOLD_HEAD_SKIPPED",
                            "Người mang vai trò Chủ hộ đã bị bỏ do CCCD sai. Giữ vai trò của những người còn lại, không tự chỉ định chủ hộ mới.",
                            person.source_row, household.household_id, person.name,
                            source_fields=("cccd",), disposition="person_skipped"))
            kept.append(replace(household, people=valid_people))
    updated = []
    for issue in issues:
        index = bisect_right(starts, issue.source_row) - 1
        whole_household_skipped = index >= 0 and starts[index] in skipped_households
        if whole_household_skipped and issue.code != "SUMMARY_ROW_SKIPPED":
            issue = replace(issue, severity=Severity.WARNING if issue.severity == Severity.ERROR else issue.severity,
                            disposition="household_skipped")
        elif issue.source_row in skipped_people:
            issue = replace(issue, severity=Severity.WARNING if issue.severity == Severity.ERROR else issue.severity,
                            disposition="person_skipped")
        elif issue.code == "ROW_WITHOUT_HOUSEHOLD":
            issue = replace(issue, severity=Severity.WARNING, disposition="row_skipped")
        updated.append(issue)
    source_people = sum(len(h.people) for h in households)
    source_parcels = sum(len(h.parcels) for h in households)
    kept_people = sum(len(h.people) for h in kept)
    kept_parcels = sum(len(h.parcels) for h in kept)
    stats = {
        "source_households": len(households), "source_people": source_people, "source_parcels": source_parcels,
        "households": len(kept), "people": kept_people, "parcels": kept_parcels,
        "households_skipped": len(skipped_households), "people_skipped": source_people - kept_people,
        "people_skipped_individually": len(skipped_people), "parcels_skipped": source_parcels - kept_parcels,
    }
    return kept, updated + extra, stats
