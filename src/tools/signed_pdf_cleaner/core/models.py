from enum import Enum
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

class ActionType(Enum):
    RENAME_SIGNED = "Đổi tên signed"
    DELETE_AND_RENAME = "Xóa bản chưa ký + đổi tên signed"
    SKIP = "Bỏ qua"

class ProcessStatus(Enum):
    READY = "Sẵn sàng"
    SKIPPED = "Bỏ qua"
    WARNING = "Cảnh báo"
    ERROR = "Lỗi"
    COMPLETED = "Hoàn thành"

@dataclass
class FileActionPlan:
    signed_path: Optional[Path]
    unsigned_path: Optional[Path]
    target_path: Path
    action: ActionType
    status: ProcessStatus
    warning_message: str = ""
    error_message: str = ""
