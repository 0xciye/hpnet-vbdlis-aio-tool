from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from .source_reader import SourceColumn


SYNONYMS: dict[str, tuple[str, ...]] = {
    "household_stt": ("stt", "số thứ tự", "stt hộ", "số hộ"),
    "person_name": ("họ tên", "họ và tên", "tên hộ", "tên chủ sử dụng", "chủ hộ", "họ tên chủ hộ"),
    "cccd": ("cccd", "căn cước", "số cccd", "số định danh cá nhân", "cmnd"),
    "birth_date": ("ngày sinh", "năm sinh", "ngày tháng năm sinh"),
    "gender": ("giới tính", "phái"),
    "sheet_number": ("tờ", "số tờ", "tờ bản đồ", "số hiệu tờ"),
    "parcel_number": ("thửa", "số thửa", "thửa đất", "số thứ tự thửa"),
    "area": ("diện tích", "dt", "diện tích thửa"),
    "land_location": ("xứ đồng", "vị trí", "địa danh", "địa chỉ thửa đất"),
    "land_type": ("loại đất", "mục đích sử dụng"),
    "land_origin": ("nguồn gốc sử dụng",),
    "use_form": ("hình thức sử dụng",),
    "use_term": ("thời hạn sử dụng",),
    "gcn_issue_number": ("số phát hành gcn", "số phát hành giấy chứng nhận", "số gcn"),
    "gcn_issue_date": ("ngày cấp gcn", "ngày cấp giấy chứng nhận"),
    "gcn_registry_number": ("số vào sổ gcn", "số vào sổ"),
    "gcn_type": ("loại giấy chứng nhận", "loại gcn"),
    "gcn_authority": ("cơ quan cấp", "nơi cấp gcn"),
}


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


class AutoMapper:
    def suggest(self, columns: list[SourceColumn]) -> dict[str, str]:
        result: dict[str, str] = {}
        used: set[str] = set()
        for field, synonyms in SYNONYMS.items():
            scored: list[tuple[float, SourceColumn]] = []
            for column in columns:
                if column.letter in used or not column.header:
                    continue
                header = _normalize(column.header)
                scores = []
                for synonym in synonyms:
                    target = _normalize(synonym)
                    if header == target:
                        scores.append(1.0)
                    elif target in header or header in target:
                        scores.append(0.90)
                    else:
                        scores.append(SequenceMatcher(None, header, target).ratio())
                scored.append((max(scores), column))
            scored.sort(key=lambda item: item[0], reverse=True)
            if not scored:
                continue
            best_score, best_column = scored[0]
            second_score = scored[1][0] if len(scored) > 1 else 0.0
            if best_score >= 0.84 and best_score - second_score >= 0.08:
                result[field] = best_column.letter
                used.add(best_column.letter)
        return result
