from typing import List
from tools.hpnet_file_generator.models.data_models import SourceFile, PersonRecord

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
            
        for sf in self.sources:
            matches = name_map.get(sf.normalized_name, [])
            
            if not matches:
                sf.matched_person = None
                continue
                
            if len(matches) == 1:
                sf.matched_person = matches[0]
            else:
                # Multiple records with same name.
                # Try to use STT / secondary key if available
                if sf.stt:
                    stt_matches = [m for m in matches if m.secondary_key == sf.stt]
                    if len(stt_matches) == 1:
                        sf.matched_person = stt_matches[0]
                    else:
                        sf.is_ambiguous = True
                else:
                    sf.is_ambiguous = True
                    
        return self.sources
