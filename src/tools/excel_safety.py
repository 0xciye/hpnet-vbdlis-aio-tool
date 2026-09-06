"""Small, shared safety primitives for Excel tools."""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook


SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm"}


def validate_workbook_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError("File Excel không tồn tại.")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Chỉ hỗ trợ file .xlsx và .xlsm.")
    return path


def open_workbook(path: str | Path, **kwargs):
    path = validate_workbook_path(path)
    return load_workbook(path, keep_vba=path.suffix.lower() == ".xlsm", **kwargs)


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def create_backup(source: str | Path, label: str = "backup") -> Path:
    source = validate_workbook_path(source)
    backup = source.with_name(f"{source.stem}_{label}_{timestamp()}{source.suffix}")
    shutil.copy2(source, backup)
    if not backup.is_file() or backup.stat().st_size != source.stat().st_size:
        raise OSError("Không thể xác minh file backup.")
    return backup


def atomic_save(workbook, output: str | Path) -> Path:
    output = Path(output).expanduser().resolve()
    if output.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("File đầu ra phải có đuôi .xlsx hoặc .xlsm.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.stem}.saving{output.suffix}")
    try:
        workbook.save(temporary)
        check = open_workbook(temporary, read_only=True, data_only=False)
        check.close()
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return output


def default_output(source: str | Path, suffix: str) -> Path:
    source = validate_workbook_path(source)
    return source.with_name(f"{source.stem}_{suffix}{source.suffix}")
