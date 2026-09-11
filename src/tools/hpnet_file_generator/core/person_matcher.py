from difflib import get_close_matches
from typing import List
from tools.hpnet_file_generator.models.data_models import SourceFile, PersonRecord
from tools.hpnet_file_generator.utils.text_normalizer import normalize_excel_identifier

class PersonMatcher:
    def __init__(self, excel_records: List[PersonRecord], source_files: List[SourceFile]):
        self.records = excel_records
        self.sources = source_files

    def match(self) -> List[SourceFile]:
        """
        Gán PersonRecord tương ứng vào mỗi SourceFile.
        Đánh dấu is_ambiguous nếu có xung đột.
        """
        # Build dictionaries for fast lookup
        # 1. By exact normalized name -> list of records (to detect duplicates)
        name_map = {}
        for r in self.records:
            name_map.setdefault(r.normalized_name, []).append(r)
        def suggestion_text(source_name: str) -> str:
            close_names = get_close_matches(
                source_name, list(name_map), n=3, cutoff=0.82
            )
            if not close_names:
                return ""
            details = []
            for name in close_names:
                people = name_map[name]
                stts = ", ".join(normalize_excel_identifier(p.secondary_key) or "không có STT" for p in people)
                details.append(f"{people[0].ho_ten} (STT: {stts})")
            return " Gợi ý tên gần giống để kiểm tra: " + "; ".join(details) + "."
            
        for sf in self.sources:
            sf.matched_person = None
            sf.is_ambiguous = False
            sf.match_issue = ""
            matches = name_map.get(sf.normalized_name, [])
            
            if not matches:
                sf.match_issue = "Không tìm thấy tên trong Excel." + suggestion_text(sf.normalized_name)
                continue

            # Tên khớp duy nhất là đủ; STT chỉ dùng để phân biệt khi Excel có
            # nhiều người trùng tên.
            repeated_name = len(matches) > 1
            if repeated_name and sf.stt:
                source_stt = normalize_excel_identifier(sf.stt)
                stt_matches = [
                    match for match in matches
                    if normalize_excel_identifier(match.secondary_key) == source_stt
                ]
                if len(stt_matches) == 1:
                    sf.matched_person = stt_matches[0]
                elif len(stt_matches) > 1:
                    sf.is_ambiguous = True
                    candidates = ", ".join(normalize_excel_identifier(m.secondary_key) or "không có STT" for m in matches)
                    sf.match_issue = f"Tên và STT {source_stt} khớp nhiều dòng Excel. Các STT cần kiểm tra: {candidates}."
                else:
                    candidates = ", ".join(normalize_excel_identifier(m.secondary_key) or "không có STT" for m in matches)
                    sf.match_issue = f"Tên khớp nhưng STT {source_stt} không khớp Excel. STT Excel cùng tên: {candidates}."
                continue

            if len(matches) == 1:
                sf.matched_person = matches[0]
            else:
                sf.is_ambiguous = True
                candidates = ", ".join(normalize_excel_identifier(m.secondary_key) or "không có STT" for m in matches)
                sf.match_issue = (
                    "Tên bị lặp nhưng file PDF không có STT đủ tin cậy để xác định đúng người. "
                    f"Các STT Excel cùng tên: {candidates}."
                )
                    
        return self.sources
