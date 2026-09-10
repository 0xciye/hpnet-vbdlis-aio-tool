from collections import Counter
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
        has_secondary_keys = any(normalize_excel_identifier(record.secondary_key) for record in self.records)
        source_name_counts = Counter(source.normalized_name for source in self.sources)
            
        for sf in self.sources:
            sf.matched_person = None
            sf.is_ambiguous = False
            sf.match_issue = ""
            matches = name_map.get(sf.normalized_name, [])
            
            if not matches:
                sf.match_issue = "Không tìm thấy tên trong Excel"
                continue

            # A name that is unique in both inputs is safe even when manual STT
            # numbering drifted. Repeated names must also match STT; otherwise
            # multiple source files can be assigned to one Excel person.
            repeated_name = len(matches) > 1 or source_name_counts[sf.normalized_name] > 1
            if repeated_name and sf.stt and has_secondary_keys:
                source_stt = normalize_excel_identifier(sf.stt)
                stt_matches = [
                    match for match in matches
                    if normalize_excel_identifier(match.secondary_key) == source_stt
                ]
                if len(stt_matches) == 1:
                    sf.matched_person = stt_matches[0]
                elif len(stt_matches) > 1:
                    sf.is_ambiguous = True
                    sf.match_issue = f"Tên và STT {source_stt} khớp nhiều dòng Excel"
                else:
                    sf.match_issue = f"Tên khớp nhưng STT {source_stt} không khớp Excel"
                continue

            if len(matches) == 1 and not repeated_name:
                sf.matched_person = matches[0]
            else:
                sf.is_ambiguous = True
                sf.match_issue = "Tên bị lặp nhưng không có STT đủ tin cậy để xác định đúng người"
                    
        return self.sources
