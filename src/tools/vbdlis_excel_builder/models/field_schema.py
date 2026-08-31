from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class FieldClassification(StrEnum):
    ACTIVE_REQUIRED = "ACTIVE_REQUIRED"
    ACTIVE_OPTIONAL = "ACTIVE_OPTIONAL"
    TEMPLATE_OPTIONAL = "TEMPLATE_OPTIONAL"
    GCN_OPTIONAL = "GCN_OPTIONAL"
    TEMPLATE_DEFAULT = "TEMPLATE_DEFAULT"
    COMPUTED = "COMPUTED"
    USER_CONFIGURABLE = "USER_CONFIGURABLE"


@dataclass(slots=True)
class FieldSchema:
    field_id: str
    item: str
    column: str
    name: str
    classification: FieldClassification
    required: bool = False
    mode: str = "blank"
    source: str = ""
    default: Any = ""
    transformer: str = ""
    fallback: str = ""
    condition: str = "has_gcn"
    validation: str = ""
    official_sample_count: int = 0
    golden_count: int = 0
    gcn_related: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["classification"] = self.classification.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldSchema":
        payload = dict(data)
        payload["classification"] = FieldClassification(payload["classification"])
        return cls(**payload)
