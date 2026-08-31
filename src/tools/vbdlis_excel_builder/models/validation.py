from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(slots=True)
class ValidationIssue:
    severity: Severity
    code: str
    message: str
    source_row: int = 0
    household: str = ""
    person: str = ""
    value: Any = ""
    source_fields: tuple[str, ...] = ()
    output_column: str = ""
    output_row: int = 0
    disposition: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data
