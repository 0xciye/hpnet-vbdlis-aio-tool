"""Quy tắc chung cho số tờ/thửa dùng trong các công cụ VBDLIS cục bộ."""

from decimal import Decimal
import re


def normalize_land_identifier(value) -> str:
    """Chuẩn hóa duy nhất số nguyên dương; mọi mã có chữ đều không hợp lệ."""
    if value is None or isinstance(value, bool):
        return ""
    text = " ".join(str(value).split())
    if not text:
        return ""
    if re.fullmatch(r"[0-9]+(?:\.0+)?", text):
        number = Decimal(text)
        if 0 < number <= 2147483647:
            return str(int(number))
        return ""
    return ""
