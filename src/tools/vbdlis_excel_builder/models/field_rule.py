from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class FieldSource(StrEnum):
    SOURCE_COLUMN = "source_column"
    FIXED = "fixed"
    COMPUTED = "computed"
    KEEP_TEMPLATE = "keep_template"
    BLANK = "blank"
    CONDITIONAL = "conditional"


@dataclass(slots=True)
class FieldRule:
    field_id: str
    mode: FieldSource
    source: str = ""
    default: Any = ""
    transformer: str = ""
    fallback: str = ""
    required: bool = False
    condition: str = "has_gcn"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldRule":
        payload = dict(data)
        payload["mode"] = FieldSource(payload["mode"])
        return cls(**payload)
