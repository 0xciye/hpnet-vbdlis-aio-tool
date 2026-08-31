from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Certificate:
    values: dict[str, Any] = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        return any(value is not None and str(value).strip() for value in self.values.values())

    @property
    def signature(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted(
                (key, str(value).strip())
                for key, value in self.values.items()
                if value is not None and str(value).strip()
            )
        )
