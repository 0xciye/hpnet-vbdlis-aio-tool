from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from tools.land_identifier import normalize_land_identifier


def raw_text(value: Any) -> str:
    return "" if value is None else " ".join(str(value).strip().split())


def fold_text(value: Any) -> str:
    text = unicodedata.normalize("NFD", raw_text(value).casefold().replace("đ", "d"))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text).split())


def normalize_name(value: Any) -> str:
    return fold_text(value)


def normalize_role(value: Any) -> str:
    role = fold_text(value)
    if any(token in role for token in ("chu ho", "dai dien", "chu su dung")):
        return "HEAD"
    if role in {"tv", "tv ho"} or any(token in role for token in ("thanh vien", "vo", "chong", "con")):
        return "MEMBER"
    return "UNKNOWN"


def normalize_identifier(value: Any, kind: str = "") -> str:
    text = raw_text(value)
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).casefold().replace("đ", "d")
    prefixes = (
        r"^(?:to|tờ)(?:\s+(?:ban\s+do|bản\s+đồ|so|số))?\s*[:._-]*\s*"
        if kind == "sheet"
        else r"^(?:thua|thửa)(?:\s+(?:dat|đất|so|số))?\s*[:._-]*\s*"
    )
    if kind:
        text = re.sub(prefixes, "", text, flags=re.IGNORECASE)
    text = text.strip().strip('"\'')
    if kind in {"sheet", "parcel"}:
        return normalize_land_identifier(text)
    try:
        number = Decimal(text.replace(",", "."))
        if number == number.to_integral():
            return str(int(number))
        return format(number.normalize(), "f")
    except (InvalidOperation, ValueError):
        pass
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[^0-9a-z./-]", "", fold_text(text).replace(" ", ""))


def normalize_document_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", raw_text(value)).casefold()
    text = Path(text).name
    text = re.sub(r"\.(?:signed|ldsigned|lsigned)(?=\.pdf$)", "", text)
    text = re.sub(r"\.(?:pdf|docx?|xlsx?)$", "", text)
    return re.sub(r"[^0-9a-z]+", "", fold_text(text))


def sanitize_windows_name(value: Any, fallback: str = "UNKNOWN") -> str:
    text = raw_text(value) or fallback
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", text).strip(" .")
    if text.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        text = "_" + text
    return text[:120] or fallback
