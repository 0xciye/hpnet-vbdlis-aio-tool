from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
from pathlib import Path

class ActionStatus(Enum):
    READY = "Ready"
    CONFLICT = "Conflict"
    WARNING = "Warning"
    SKIPPED = "Skipped"
    SUCCESS = "Success"
    ERROR = "Error"

@dataclass
class Parcel:
    so_to: str
    so_thua: str

    def __hash__(self):
        return hash((self.so_to, self.so_thua))

    def __eq__(self, other):
        if not isinstance(other, Parcel):
            return False
        return self.so_to == other.so_to and self.so_thua == other.so_thua

@dataclass
class PersonRecord:
    ho_ten: str
    normalized_name: str
    parcels: set[Parcel] = field(default_factory=set)
    stt: Optional[str] = None
    secondary_key: Optional[str] = None
    raw_rows: list[int] = field(default_factory=list)

@dataclass
class SourceFile:
    original_path: Path
    filename: str
    normalized_name: str
    extension: str
    stt: Optional[str] = None
    matched_person: Optional[PersonRecord] = None
    is_ambiguous: bool = False
    match_issue: str = ""

@dataclass
class GenerationAction:
    source_file: SourceFile
    parcel: Parcel
    suffix: str
    target_filename: str
    target_path: Path
    status: ActionStatus = ActionStatus.READY
    conflict_path: Optional[Path] = None
    reason: str = ""

@dataclass
class ProfileConfig:
    ma_dvhc: str = ""
    prefix: str = "CHUACOGIAY"
    template: str = "{PREFIX}_{MA_DVHC}_{SO_TO}_{SO_THUA}-{HAU_TO}"
    suffixes: List[str] = field(default_factory=lambda: ["TBXN"])
    remove_duplicate_parcels: bool = True
    remove_prefix_numbers: bool = True
    extensions: List[str] = field(default_factory=lambda: [".pdf", ".docx", ".doc"])
    conflict_strategy: str = "CONFLICT"
    
