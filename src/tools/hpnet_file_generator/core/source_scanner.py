import os
from pathlib import Path
from typing import List
from tools.hpnet_file_generator.models.data_models import SourceFile
from tools.hpnet_file_generator.utils.text_normalizer import normalize_person_name, extract_stt_and_name

class SourceScanner:
    def __init__(self, folder_path: str, extensions: List[str], remove_prefix: bool = True):
        self.folder_path = Path(folder_path)
        # Normalize extensions to always have dot and lowercase
        self.extensions = [ext.lower() if ext.startswith('.') else f".{ext.lower()}" for ext in extensions]
        self.remove_prefix = remove_prefix

    def scan(self) -> List[SourceFile]:
        if not self.folder_path.exists() or not self.folder_path.is_dir():
            return []
            
        source_files = []
        for file_path in self.folder_path.iterdir():
            if not file_path.is_file():
                continue
                
            ext = file_path.suffix.lower()
            if ext not in self.extensions:
                continue
                
            filename_without_ext = file_path.stem
            
            stt = None
            if self.remove_prefix:
                extracted_stt, name_part = extract_stt_and_name(filename_without_ext)
                stt = extracted_stt
                raw_name = name_part
            else:
                raw_name = filename_without_ext
                
            normalized = normalize_person_name(raw_name)
            
            sf = SourceFile(
                original_path=file_path,
                filename=file_path.name,
                normalized_name=normalized,
                extension=file_path.suffix, # keep original case
                stt=stt
            )
            source_files.append(sf)
            
        return source_files
