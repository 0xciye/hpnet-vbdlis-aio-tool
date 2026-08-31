from __future__ import annotations

from dataclasses import dataclass, field

from .parcel import Parcel
from .person import Person


@dataclass(slots=True)
class Household:
    household_id: str
    source_row: int
    people: list[Person] = field(default_factory=list)
    parcels: list[Parcel] = field(default_factory=list)
