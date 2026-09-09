from collections import Counter
from typing import List, Dict

import openpyxl
from openpyxl.utils import get_column_letter

from tools.hpnet_file_generator.utils.text_normalizer import normalize_person_name, normalize_excel_identifier
from tools.hpnet_file_generator.models.data_models import PersonRecord, Parcel

class ExcelReader:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.wb = None
        self.sheet_names = []

    def load(self):
        # Dùng workbook thường để đọc được vị trí ô gộp trong phần tiêu đề.
        self.wb = openpyxl.load_workbook(self.file_path, data_only=True, read_only=False)
        self.sheet_names = self.wb.sheetnames

    def _merged_value(self, sheet, row: int, column: int):
        cell = sheet.cell(row, column)
        if cell.value is not None:
            return cell.value
        for merged in sheet.merged_cells.ranges:
            if merged.min_row <= row <= merged.max_row and merged.min_col <= column <= merged.max_col:
                return sheet.cell(merged.min_row, merged.min_col).value
        return None

    def header_depth(self, sheet_name: str, header_row: int = 1) -> int:
        """Nhận diện phần tiêu đề gồm một hay hai dòng."""
        if not self.wb:
            self.load()
        sheet = self.wb[sheet_name]
        next_row = header_row + 1
        for merged in sheet.merged_cells.ranges:
            if merged.min_row <= header_row and merged.max_row >= next_row:
                return 2
            if merged.min_row == header_row == merged.max_row and merged.max_col > merged.min_col:
                if any(sheet.cell(next_row, col).value not in (None, "")
                       for col in range(merged.min_col, merged.max_col + 1)):
                    return 2
        return 1

    def get_headers(self, sheet_name: str, header_row: int = 1) -> List[str]:
        if not self.wb:
            self.load()
        sheet = self.wb[sheet_name]
        depth = self.header_depth(sheet_name, header_row)
        headers = []
        for column in range(1, sheet.max_column + 1):
            parts = []
            for row in range(header_row, header_row + depth):
                value = self._merged_value(sheet, row, column)
                text = str(value).strip() if value is not None else ""
                if text and (not parts or text != parts[-1]):
                    parts.append(text)
            headers.append(" / ".join(parts))

        counts = Counter(header for header in headers if header)
        headers = [
            f"{header} (cột {get_column_letter(index)})" if header and counts[header] > 1 else header
            for index, header in enumerate(headers, start=1)
        ]
        return headers

    def read_data(self, sheet_name: str, header_row: int, mapping: Dict[str, str], remove_duplicates: bool = True) -> List[PersonRecord]:
        """
        mapping: {'ho_ten': 'ColName', 'so_to': 'ColName', 'so_thua': 'ColName', 'secondary_key': 'ColName' (optional)}
        """
        if not self.wb:
            self.load()
        sheet = self.wb[sheet_name]
        
        headers = self.get_headers(sheet_name, header_row)
        
        # Build index map
        col_indices = {}
        for key, col_name in mapping.items():
            if col_name in headers:
                col_indices[key] = headers.index(col_name)
            else:
                col_indices[key] = -1

        person_dict = {} # Keyed by (normalized_name, secondary_key)
        
        row_idx = header_row + self.header_depth(sheet_name, header_row)
        for row in sheet.iter_rows(min_row=row_idx, values_only=True):
            idx_hoten = col_indices.get('ho_ten', -1)
            idx_soto = col_indices.get('so_to', -1)
            idx_sothua = col_indices.get('so_thua', -1)
            idx_secondary = col_indices.get('secondary_key', -1)
            
            if idx_hoten == -1:
                row_idx += 1
                continue
                
            raw_hoten = row[idx_hoten]
            if not raw_hoten:
                row_idx += 1
                continue
                
            ho_ten = str(raw_hoten).strip()
            normalized = normalize_person_name(ho_ten)
            
            so_to = normalize_excel_identifier(row[idx_soto]) if idx_soto != -1 else ""
            so_thua = normalize_excel_identifier(row[idx_sothua]) if idx_sothua != -1 else ""
            
            secondary_key = ""
            if idx_secondary != -1 and row[idx_secondary] is not None:
                secondary_key = str(row[idx_secondary]).strip()
                
            dict_key = (normalized, secondary_key)
            
            if dict_key not in person_dict:
                person_dict[dict_key] = PersonRecord(
                    ho_ten=ho_ten, 
                    normalized_name=normalized,
                    secondary_key=secondary_key,
                    stt=secondary_key # If secondary key is used as STT
                )
            
            record = person_dict[dict_key]
            record.raw_rows.append(row_idx)
            
            if so_to and so_thua:
                parcel = Parcel(so_to=so_to, so_thua=so_thua)
                record.parcels.add(parcel) # set will handle duplicates
                
            row_idx += 1

        # Post-processing: Remove parcels that belong to multiple different persons
        parcel_to_persons = {}
        for person in person_dict.values():
            for parcel in person.parcels:
                parcel_to_persons.setdefault(parcel, []).append(person.normalized_name)
                
        # Find shared parcels (count of unique persons > 1)
        shared_parcels = {parcel for parcel, names in parcel_to_persons.items() if len(set(names)) > 1}
        
        # Remove shared parcels from all persons
        if shared_parcels:
            for person in person_dict.values():
                person.parcels = person.parcels - shared_parcels

        # We close the read_only workbook to release file lock
        self.wb.close()
        
        return list(person_dict.values())
