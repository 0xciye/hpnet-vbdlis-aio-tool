from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class NormalizeConfig:
    source: Path
    sheet_name: str
    start_row: int = 4
    end_row: int | None = None
    normalize_names: bool = True
    name_column: str = "B"
    normalize_birthdates: bool = True
    birthdate_column: str = "D"
    input_mode: str = "DMY"
    output_format: str = "DD/MM/YYYY"
    store_as_date: bool = True


@dataclass
class CellChange:
    row: int
    field: str
    column: str
    original: object
    normalized: object = None
    display_value: str = ""
    status: str = "UNCHANGED"
    warning: str = ""
    changed: bool = False
    selected: bool = False


@dataclass
class NameResult:
    original: object
    normalized: str | None
    changed: bool
    warnings: list[str] = field(default_factory=list)


@dataclass
class DateResult:
    original: object
    parsed_value: date | None
    display_value: str
    status: str
    changed: bool = False
    warning: str = ""
    detected_format: str = ""


@dataclass
class NormalizeScanResult:
    config: NormalizeConfig
    changes: list[CellChange]
    rows_scanned: int

    def counts(self):
        result = {"ROWS_SCANNED": self.rows_scanned}
        for change in self.changes:
            key = f"{change.field.upper()}_{change.status}"
            result[key] = result.get(key, 0) + 1
        return result
