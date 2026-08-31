import unicodedata
import re

def normalize_person_name(name: str) -> str:
    if not name:
        return ""
    # Remove extra spaces and trim
    name = re.sub(r'\s+', ' ', str(name)).strip()
    # Normalize unicode
    name = unicodedata.normalize('NFC', name)
    return name.lower()

def extract_stt_and_name(filename_without_ext: str):
    """
    Extracts prefix number and the rest of the name.
    Examples:
    '1. Nguyễn Văn A' -> ('1', 'Nguyễn Văn A')
    '001 - Nguyễn Văn A' -> ('001', 'Nguyễn Văn A')
    'Nguyễn Văn A' -> (None, 'Nguyễn Văn A')
    """
    # Regex to capture optional leading numbers followed by delimiters (. - or spaces)
    match = re.match(r'^(\d+)(?:\s*[\.\-]\s*|\s+)(.+)$', filename_without_ext.strip())
    if match:
        stt = match.group(1).strip()
        name_part = match.group(2).strip()
        return stt, name_part
    return None, filename_without_ext.strip()

def normalize_excel_identifier(val) -> str:
    """
    Converts 70.0 to '70', keeps text as is, trims whitespace.
    """
    if val is None:
        return ""
    
    s_val = str(val).strip()
    # If it ends with .0, it might be a float read from excel
    if s_val.endswith('.0') and s_val.replace('.0', '').isdigit():
        return s_val.replace('.0', '')
    
    return s_val

def sanitize_filename(filename: str) -> str:
    """Removes invalid characters for Windows filenames"""
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        filename = filename.replace(c, '')
    return filename.strip()
