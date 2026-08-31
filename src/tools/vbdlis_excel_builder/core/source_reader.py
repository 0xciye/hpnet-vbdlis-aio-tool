from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


@dataclass(slots=True)
class SourceColumn:
    index: int
    letter: str
    header: str

    @property
    def display(self) -> str:
        return f"{self.letter} - {self.header or '[Không có tiêu đề]'}"


class SourceReader:
    def sheet_names(self, path: str | Path) -> list[str]:
        workbook = load_workbook(path, read_only=True, data_only=False)
        try:
            return list(workbook.sheetnames)
        finally:
            workbook.close()

    def detect_header_row(self, path: str | Path, sheet_name: str, scan_rows: int = 20) -> int:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            ws = workbook[sheet_name]
            best_row, best_score = 1, -1
            keywords = {
                "stt", "họ tên", "họ và tên", "cccd", "ngày sinh", "số tờ",
                "tờ bản đồ", "số thửa", "diện tích", "xứ đồng", "vị trí",
            }
            for row_idx in range(1, min(scan_rows, ws.max_row) + 1):
                values = [cell.value for cell in ws[row_idx]]
                nonblank = [str(value).strip() for value in values if value not in (None, "")]
                matches = sum(
                    1 for text in nonblank
                    if any(keyword in text.casefold() for keyword in keywords)
                )
                score = len(nonblank) + matches * 5
                if score > best_score:
                    best_row, best_score = row_idx, score
            return best_row
        finally:
            workbook.close()

    def headers(self, path: str | Path, sheet_name: str, header_row: int) -> list[SourceColumn]:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            ws = workbook[sheet_name]
            return [
                SourceColumn(index, get_column_letter(index), "" if value is None else str(value).strip())
                for index, value in enumerate(
                    next(ws.iter_rows(min_row=header_row, max_row=header_row, values_only=True)), 1
                )
            ]
        finally:
            workbook.close()

    def preview(
        self,
        path: str | Path,
        sheet_name: str,
        header_row: int,
        limit: int = 50,
    ) -> tuple[list[SourceColumn], list[dict[str, Any]]]:
        headers = self.headers(path, sheet_name, header_row)
        rows = self.read_rows(path, sheet_name, header_row, max_rows=limit)
        return headers, rows

    def read_rows(
        self,
        path: str | Path,
        sheet_name: str,
        header_row: int,
        max_rows: int | None = None,
    ) -> list[dict[str, Any]]:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            ws = workbook[sheet_name]
            header_values = list(
                next(ws.iter_rows(min_row=header_row, max_row=header_row, values_only=True))
            )
            result: list[dict[str, Any]] = []
            for offset, values in enumerate(
                ws.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1
            ):
                if max_rows is not None and len(result) >= max_rows:
                    break
                if not any(value is not None and str(value).strip() for value in values):
                    continue
                row: dict[str, Any] = {"_row": offset}
                for index, value in enumerate(values, 1):
                    letter = get_column_letter(index)
                    row[letter] = value
                    if index <= len(header_values):
                        header = header_values[index - 1]
                        if header is not None and str(header).strip():
                            row[str(header).strip()] = value
                result.append(row)
            return result
        finally:
            workbook.close()
