from __future__ import annotations

import os
import re
import sys
from pathlib import Path


INVALID_FILENAME = re.compile(r'[\\/:*?"<>|]')


def resource_path(relative: str) -> Path:
    # Mod: Removed sys._MEIPASS dependency for unified onedir building. File structure tracks correctly via __file__. (Behavior preserved)
    base = Path(__file__).resolve().parents[1]
    return base / relative


def app_data_dir() -> Path:
    root = Path(os.getenv("APPDATA", Path.home())) / "VBDLIS Excel Builder"
    root.mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    return root


def ensure_xlsx_name(name: str) -> str:
    name = name.strip()
    if not name:
        name = "VBDLIS_Output.xlsx"
    if INVALID_FILENAME.search(name):
        raise ValueError('Tên file không được chứa \\ / : * ? " < > |')
    if not name.lower().endswith(".xlsx"):
        name += ".xlsx"
    return name


def unique_output_path(folder: str | Path, filename: str, overwrite: bool = False) -> Path:
    directory = Path(folder).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / ensure_xlsx_name(filename)
    if overwrite or not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    index = 1
    while True:
        alternative = directory / f"{stem}_{index}{suffix}"
        if not alternative.exists():
            return alternative
        index += 1
