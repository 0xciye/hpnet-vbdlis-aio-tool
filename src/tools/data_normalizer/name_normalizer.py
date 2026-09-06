from __future__ import annotations

import re
import unicodedata

from .models import NameResult


def _capitalize_piece(piece: str) -> str:
    parts = re.split("([-'.])", piece)
    return "".join(part[:1].upper() + part[1:].lower() if part not in {"-", "'", "."} else part for part in parts)


def normalize_person_name(value) -> NameResult:
    if value is None or (isinstance(value, str) and not value.strip()):
        return NameResult(value, None, False)
    original = str(value)
    compact = " ".join(original.split())
    normalized = " ".join(_capitalize_piece(piece) for piece in compact.split(" "))
    normalized = unicodedata.normalize("NFC", normalized)
    warnings = []
    if any(character.isdigit() for character in normalized):
        warnings.append("Tên chứa chữ số; chỉ chuẩn hóa định dạng, không sửa chính tả.")
    return NameResult(value, normalized, normalized != original, warnings)
