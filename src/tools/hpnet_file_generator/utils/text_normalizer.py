import unicodedata
import re
from decimal import Decimal, InvalidOperation

def normalize_person_name(name: str) -> str:
    if not name:
        return ""
    # Normalize unicode
    name = unicodedata.normalize('NFC', str(name))
    name = re.sub(r'\s*\(\s*người\s+đại\s+diện\s*\)\s*$', '', name, flags=re.IGNORECASE)
    # Remove extra spaces and trim
    name = re.sub(r'\s+', ' ', name).strip()
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
    name = re.sub(r'(?:[\s_.-]+\d+)+$', '', filename_without_ext.strip())
    match = re.match(r'^(\d+)(?:\s*[._\-]\s*|\s+)(.+)$', name)
    if match:
        stt = match.group(1).strip()
        name_part = match.group(2).strip()
        return stt, name_part
    return None, name

def normalize_excel_identifier(val) -> str:
    """
    Converts 70.0 to '70', keeps text as is, trims whitespace.
    """
    if val is None:
        return ""
    
    s_val = str(val).strip()
    try:
        number = Decimal(s_val)
        if number == number.to_integral_value():
            return str(number.quantize(Decimal("1")))
        return format(number.normalize(), "f")
    except InvalidOperation:
        return s_val

def sanitize_filename(filename: str) -> str:
    """Removes invalid characters for Windows filenames"""
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        filename = filename.replace(c, '')
    return filename.strip()
