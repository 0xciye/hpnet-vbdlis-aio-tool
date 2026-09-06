from __future__ import annotations

import re
from datetime import date, datetime, time

from openpyxl.styles.numbers import is_date_format
from openpyxl.utils.datetime import from_excel

from .models import DateResult


FORMATS = {"DD/MM/YYYY": "%d/%m/%Y", "DD-MM-YYYY": "%d-%m-%Y", "YYYY-MM-DD": "%Y-%m-%d"}


def _display(value: date, output_format: str) -> str:
    return value.strftime(FORMATS[output_format])


def normalize_birthdate(value, input_mode="DMY", output_format="DD/MM/YYYY", *, number_format="General", epoch=None) -> DateResult:
    if value is None or (isinstance(value, str) and not value.strip()):
        return DateResult(value, None, "", "EMPTY")
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        display = _display(value, output_format)
        return DateResult(value, value, display, "VALID", True, detected_format="EXCEL_DATE")
    if isinstance(value, (int, float)):
        if is_date_format(number_format):
            try:
                parsed = from_excel(value, epoch).date() if isinstance(from_excel(value, epoch), datetime) else from_excel(value, epoch)
                return DateResult(value, parsed, _display(parsed, output_format), "VALID", True, detected_format="EXCEL_SERIAL")
            except (ValueError, OverflowError):
                return DateResult(value, None, "", "INVALID", warning="Excel date serial không hợp lệ.")
        return DateResult(value, None, "", "PARTIAL", warning="Giá trị số không có định dạng ngày Excel; giữ nguyên.")

    text = str(value).strip()
    if re.fullmatch(r"\d{4}", text) or re.fullmatch(r"(?:\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2})", text):
        return DateResult(value, None, "", "PARTIAL", warning="Ngày tháng bị thiếu; không tự thêm ngày.")
    match = re.fullmatch(r"(\d{1,4})[/-](\d{1,2})[/-](\d{1,4})", text)
    if not match:
        return DateResult(value, None, "", "INVALID", warning="Không nhận diện được định dạng ngày.")
    first, second, third = map(int, match.groups())
    detected = input_mode
    if input_mode == "AUTO":
        if len(match.group(1)) == 4:
            detected = "YMD"
        elif first > 12 and second <= 12:
            detected = "DMY"
        elif second > 12 and first <= 12:
            detected = "MDY"
        elif first <= 12 and second <= 12:
            return DateResult(value, None, "", "AMBIGUOUS", warning="Không thể xác định chắc chắn ngày và tháng.")
        else:
            return DateResult(value, None, "", "INVALID", warning="Ngày và tháng không hợp lệ.")
    year_text = match.group(1) if detected == "YMD" else match.group(3)
    if len(year_text) == 2:
        return DateResult(value, None, "", "PARTIAL", warning="Năm 2 chữ số không được tự suy diễn.", detected_format=detected)
    try:
        if detected == "DMY": day, month, year = first, second, third
        elif detected == "MDY": month, day, year = first, second, third
        elif detected == "YMD": year, month, day = first, second, third
        else: raise ValueError("Định dạng nguồn không hợp lệ.")
        parsed = date(year, month, day)
    except ValueError:
        return DateResult(value, None, "", "INVALID", warning="Ngày không tồn tại trong lịch.", detected_format=detected)
    display = _display(parsed, output_format)
    return DateResult(value, parsed, display, "VALID", display != text, detected_format=detected)
