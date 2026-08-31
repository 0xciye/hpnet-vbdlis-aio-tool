from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from .certificate import Certificate


def _norm(value: Any) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).strip().split())
    if text.endswith(".0"):
        text = text[:-2]
    return text.casefold()


def _norm_area(value: Any) -> str:
    text = _norm(value).replace(",", ".")
    try:
        return format(Decimal(text).normalize(), "f")
    except (InvalidOperation, ValueError):
        return text


@dataclass(slots=True)
class Parcel:
    sheet_number: str
    parcel_number: str
    area: Any
    location: str = ""
    certificate: Certificate = field(default_factory=Certificate)
    source_row: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def identity_key(self) -> tuple[str, str]:
        return (_norm(self.sheet_number), _norm(self.parcel_number))

    @property
    def duplicate_key(self) -> tuple[str, str, str, str]:
        return (*self.identity_key, _norm_area(self.area), _norm(self.location))
