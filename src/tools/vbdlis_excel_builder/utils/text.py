from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from string import Formatter
from typing import Any


SAFE_PLACEHOLDERS = {
    "PREFIX",
    "MA_XA",
    "SO_TO",
    "SO_THUA",
    "HO_TEN",
    "CCCD",
    "DIA_CHI",
    "XU_DONG",
    "STT",
}


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.casefold() in {"nan", "none", "null"}


def normalize_whitespace(value: Any) -> str:
    if is_blank(value):
        return ""
    return " ".join(str(value).replace("\u00a0", " ").split())


def normalize_name(value: Any, uppercase: bool = True) -> str:
    text = unicodedata.normalize("NFC", normalize_whitespace(value))
    return text.upper() if uppercase else text


def is_summary_label(value: Any) -> bool:
    """Match complete total labels, never arbitrary names containing 'Tổng'."""
    text = unicodedata.normalize("NFC", normalize_whitespace(value)).casefold()
    text = re.sub(r"\s*\(\s*m[2²]\s*\)\s*$", "", text)
    text = normalize_whitespace(re.sub(r"[.:;,\-–—_=]+", " ", text))
    # Keep Vietnamese accents: 'Tống Công' is a name, not 'Tổng cộng'.
    return text in {
        "tổng dt", "tong dt", "tổng d t", "tong d t",
        "tổng diện tích", "tong dien tich", "tổng cộng", "tong cong",
        "cộng dt", "cong dt", "cộng diện tích", "cong dien tich",
    }


def excel_identifier(value: Any) -> str:
    if is_blank(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = normalize_whitespace(value)
    if re.fullmatch(r"[+-]?\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def normalize_cccd(value: Any) -> tuple[str, bool]:
    text = excel_identifier(value).replace(" ", "")
    if not text:
        return "", False
    if re.fullmatch(r"[0-9]{12}", text):
        return text, True
    return text, False


def normalize_area(value: Any) -> Any:
    if is_blank(value):
        return ""
    if isinstance(value, (int, float)):
        return value
    text = normalize_whitespace(value)
    try:
        number = Decimal(text.replace(",", "."))
        return int(number) if number == number.to_integral() else float(number)
    except (InvalidOperation, ValueError):
        return text


def safe_template_replace(template: str, values: dict[str, Any]) -> str:
    formatter = Formatter()
    pieces: list[str] = []
    for literal, field_name, format_spec, conversion in formatter.parse(template):
        pieces.append(literal)
        if field_name is None:
            continue
        if field_name not in SAFE_PLACEHOLDERS:
            raise ValueError(f"Biến không được hỗ trợ: {{{field_name}}}")
        value = "" if values.get(field_name) is None else str(values.get(field_name, ""))
        if conversion or format_spec:
            raise ValueError("Không hỗ trợ biểu thức hoặc định dạng nâng cao trong template.")
        pieces.append(value)
    return "".join(pieces)


def infer_gender_from_cccd(cccd: str) -> str:
    """Project rule: only markers 0 and 1 in a valid 12-digit CCCD are used."""
    if not isinstance(cccd, str) or not re.fullmatch(r"[0-9]{12}", cccd):
        return ""
    marker = cccd[3]
    if marker == "0":
        return "Nam"
    if marker == "1":
        return "Nữ"
    return ""
