from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ScanConfig:
    source: Path
    sheet_name: str
    name_column: str
    sheet_column: str
    parcel_column: str
    area_column: str
    location_column: str
    start_row: int = 4
    clear_start_column: str = "G"
    clear_end_column: str = "X"


@dataclass
class ParcelRecord:
    household: int
    row: int
    sheet: str
    parcel: str
    area: str | None
    location: str
    status: str = "KEEP"
    action: str = "Giữ"
    related_rows: list[int] = field(default_factory=list)
    selected: bool = False


@dataclass
class ScanResult:
    config: ScanConfig
    records: list[ParcelRecord]
    summary_rows: list[int]
    rows_scanned: int

    @property
    def clear_rows(self):
        return [record.row for record in self.records if record.status == "EXACT_DUPLICATE"]

    def counts(self):
        result = {"ROWS_SCANNED": self.rows_scanned, "HOUSEHOLDS": len({r.household for r in self.records})}
        for record in self.records:
            result[record.status] = result.get(record.status, 0) + 1
        result["SUMMARY_ROWS"] = len(self.summary_rows)
        return result
