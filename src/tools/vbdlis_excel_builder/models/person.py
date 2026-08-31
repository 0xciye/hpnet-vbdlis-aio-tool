from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Person:
    name: str
    cccd: str = ""
    birth_date: str = ""
    gender: str = ""
    is_head: bool = False
    source_row: int = 0
    raw: dict[str, Any] = field(default_factory=dict)
