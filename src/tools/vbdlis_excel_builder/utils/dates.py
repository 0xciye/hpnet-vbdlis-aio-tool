from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .text import is_blank, normalize_whitespace


DATE_FORMATS = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
)


def normalize_birth_date(value: Any) -> str:
    if is_blank(value):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, (int, float)) and 1800 <= int(value) <= 2200:
        return str(int(value))
    text = normalize_whitespace(value)
    if text.isdigit() and len(text) == 4:
        return text
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text
