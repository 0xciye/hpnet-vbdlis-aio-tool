from typing import List, Dict
import openpyxl
from tools.hpnet_file_generator.utils.text_normalizer import normalize_person_name, normalize_excel_identifier
from tools.hpnet_file_generator.models.data_models import PersonRecord, Parcel

class ExcelReader:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.wb = None
        self.sheet_names = []

    def load(self):
        self.wb = openpyxl.load_workbook(self.file_path, data_only=True, read_only=True)
        self.sheet_names = self.wb.sheetnames

    def get_headers(self, sheet_name: str, header_row: int = 1) -> List[str]:
        if not self.wb:
            self.load()
        sheet = self.wb[sheet_name]
        headers = []
        for row in sheet.iter_rows(min_row=header_row, max_row=header_row, values_only=True):
            for cell in row:
                headers.append(str(cell).strip() if cell is not None else "")
            break
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
        
        row_idx = header_row + 1
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
