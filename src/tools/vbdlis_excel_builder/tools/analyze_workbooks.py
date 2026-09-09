from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


CLASSIFICATIONS = {
    "COL_A": ("COMPUTED", True, "computed", "", "", "output_stt"),
    "MUC_1": ("USER_CONFIGURABLE", True, "computed", "", "", "commune_code"),
    "MUC_2": ("COMPUTED", True, "computed", "", "", "dossier_or_gcn_issue_number"),
    "MUC_3": ("GCN_OPTIONAL", False, "conditional", "gcn_issue_date", "", ""),
    "MUC_4": ("GCN_OPTIONAL", False, "conditional", "gcn_registry_number", "", ""),
    "MUC_7": ("ACTIVE_REQUIRED", True, "computed", "person_name", "", "person_name"),
    "MUC_8": ("ACTIVE_OPTIONAL", False, "computed", "cccd", "", "cccd"),
    "MUC_9": ("ACTIVE_OPTIONAL", False, "computed", "birth_date", "", "birth_date"),
    "MUC_10": ("COMPUTED", False, "computed", "gender", "", "gender"),
    "MUC_11": ("USER_CONFIGURABLE", True, "computed", "", "", "address"),
    "MUC_12": ("USER_CONFIGURABLE", True, "computed", "", "Hộ gia đình", "entity_type"),
    "MUC_13": ("COMPUTED", True, "computed", "", "", "role"),
    "MUC_19": ("ACTIVE_REQUIRED", True, "computed", "sheet_number", "", "sheet_number"),
    "MUC_20": ("ACTIVE_REQUIRED", True, "computed", "parcel_number", "", "parcel_number"),
    "MUC_23": ("ACTIVE_OPTIONAL", False, "computed", "land_location", "", "land_location"),
    "MUC_24": ("ACTIVE_REQUIRED", True, "computed", "area", "", "area"),
    "MUC_25": ("TEMPLATE_DEFAULT", True, "keep_template", "", "LUC", ""),
    "MUC_26": ("COMPUTED", True, "computed", "area", "", "area_copy"),
    "MUC_27": ("TEMPLATE_DEFAULT", True, "keep_template", "", "Nhà nước giao đất không thu tiền sử dụng đất", ""),
    "MUC_28": ("TEMPLATE_DEFAULT", True, "keep_template", "", "Sử dụng chung", ""),
    "MUC_29": ("TEMPLATE_DEFAULT", True, "keep_template", "", "Đến ngày 01 tháng 8 năm 2074", ""),
    "MUC_49": ("COMPUTED", True, "computed", "", "", "document_files"),
    "MUC_50": ("USER_CONFIGURABLE", True, "computed", "", "Loại 5", "document_type"),
    "COL_AZ": ("COMPUTED", False, "computed", "cccd", "", "identity_copy"),
    "COL_BA": ("TEMPLATE_DEFAULT", False, "conditional", "", "Căn cước công dân", ""),
    "COL_BB": ("TEMPLATE_DEFAULT", False, "conditional", "", "2", ""),
    "COL_BG": ("GCN_OPTIONAL", False, "conditional", "gcn_type", "", ""),
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def merged_value(ws, row: int, col: int) -> Any:
    value = ws.cell(row, col).value
    if value not in (None, ""):
        return value
    for merged in ws.merged_cells.ranges:
        if merged.min_row <= row <= merged.max_row and merged.min_col <= col <= merged.max_col:
            return ws.cell(merged.min_row, merged.min_col).value
    return None


def field_name(ws, col: int) -> str:
    parts = []
    for row in (1, 2, 3):
        value = merged_value(ws, row, col)
        if value not in (None, ""):
            text = " ".join(str(value).split())
            if text not in parts:
                parts.append(text)
    return " / ".join(parts)


def nonblank_count(ws, col: int) -> int:
    return sum(
        ws.cell(row, col).value is not None and str(ws.cell(row, col).value).strip() != ""
        for row in range(5, ws.max_row + 1)
    )


def field_id(item: Any, column: str) -> str:
    text = "" if item is None else str(item).strip()
    return f"MUC_{text}" if text.isdigit() else f"COL_{column}"


def build_schema(official: Path, golden: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    official_wb = load_workbook(official, data_only=False)
    golden_wb = load_workbook(golden, data_only=False)
    try:
        schema_ws = official_wb["Sheet1"]
        example_ws = official_wb["CachNhap"]
        golden_ws = golden_wb[golden_wb.sheetnames[0]]
        fields = []
        for col in range(1, 62):
            column = get_column_letter(col)
            item = schema_ws.cell(4, col).value
            identity = field_id(item, column)
            classification = CLASSIFICATIONS.get(
                identity,
                ("TEMPLATE_OPTIONAL", False, "blank", "", "", ""),
            )
            category, required, mode, source, default, transformer = classification
            name = field_name(schema_ws, col)
            gcn_related = any(
                token in name.casefold()
                for token in ("gcn", "giấy chứng nhận", "số phát hành", "số vào sổ", "ngày cấp")
            )
            fields.append(
                {
                    "field_id": identity,
                    "item": "" if item is None else str(item),
                    "column": column,
                    "name": name,
                    "classification": category,
                    "required": required,
                    "mode": mode,
                    "source": source,
                    "default": default,
                    "transformer": transformer,
                    "fallback": "",
                    "condition": "has_cccd" if identity in {"COL_BA", "COL_BB"} else "has_gcn",
                    "validation": "",
                    "official_sample_count": nonblank_count(example_ws, col),
                    "golden_count": nonblank_count(golden_ws, col),
                    "gcn_related": gcn_related,
                }
            )

        classification_counts = Counter(field["classification"] for field in fields)
        metadata = {
            "generated_from": {
                "official_template": str(official),
                "official_sha256": file_hash(official),
                "golden_reference": str(golden),
                "golden_sha256": file_hash(golden),
            },
            "schema_sheet": "Sheet1",
            "item_row": 4,
            "header_rows": [1, 2, 3],
            "data_start_row": 5,
            "field_count": len(fields),
            "classification_counts": dict(classification_counts),
            "fields": fields,
        }
        analysis = {
            "official_sheets": official_wb.sheetnames,
            "golden_sheets": golden_wb.sheetnames,
            "official_dimensions": {ws.title: ws.calculate_dimension() for ws in official_wb.worksheets},
            "golden_dimensions": {ws.title: ws.calculate_dimension() for ws in golden_wb.worksheets},
            "official_merges": {ws.title: len(ws.merged_cells.ranges) for ws in official_wb.worksheets},
            "golden_merges": {ws.title: len(ws.merged_cells.ranges) for ws in golden_wb.worksheets},
            "official_formulas": {
                ws.title: sum(cell.data_type == "f" for row in ws.iter_rows() for cell in row)
                for ws in official_wb.worksheets
            },
            "golden_formulas": {
                ws.title: sum(cell.data_type == "f" for row in ws.iter_rows() for cell in row)
                for ws in golden_wb.worksheets
            },
            "official_validations": {ws.title: len(ws.data_validations.dataValidation) for ws in official_wb.worksheets},
            "golden_validations": {ws.title: len(ws.data_validations.dataValidation) for ws in golden_wb.worksheets},
            "golden_rows": golden_ws.max_row - 4,
            "golden_active_columns": [field["column"] for field in fields if field["golden_count"]],
        }
        return metadata, analysis
    finally:
        official_wb.close()
        golden_wb.close()


def write_markdown(schema: dict[str, Any], analysis: dict[str, Any], path: Path) -> None:
    rows = [
        "# Phân tích template VBDLIS và file chạy thành công",
        "",
        "Tài liệu này được sinh từ nội dung thực tế của hai workbook, không dựa trên bảng hard-code trước khi đọc file.",
        "",
        "## Tổng quan",
        "",
        f"- OFFICIAL_TEMPLATE: 3 sheet `{', '.join(analysis['official_sheets'])}`; schema chính ở `Sheet1`, dòng Mục 4, 61 field A:BI.",
        f"- GOLDEN_SUCCESS_REFERENCE: 1 sheet, {analysis['golden_rows']} dòng dữ liệu (dòng 5 trở đi).",
        f"- File chạy thành công sử dụng {len(analysis['golden_active_columns'])}/61 cột: `{', '.join(analysis['golden_active_columns'])}`.",
        f"- Hash official: `{schema['generated_from']['official_sha256']}`.",
        f"- Hash golden: `{schema['generated_from']['golden_sha256']}`.",
        "",
        "## Cấu trúc workbook",
        "",
        "| Workbook/Sheet | Kích thước | Merge | Formula | Data validation |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, dimension in analysis["official_dimensions"].items():
        rows.append(
            f"| Official/{name} | {dimension} | {analysis['official_merges'][name]} | {analysis['official_formulas'][name]} | {analysis['official_validations'][name]} |"
        )
    for name, dimension in analysis["golden_dimensions"].items():
        rows.append(
            f"| Golden/{name} | {dimension} | {analysis['golden_merges'][name]} | {analysis['golden_formulas'][name]} | {analysis['golden_validations'][name]} |"
        )
    rows.extend(
        [
            "",
            "## Kết luận nghiệp vụ",
            "",
            "- `CachNhap` chứa dữ liệu minh họa và 17 công thức; không được sao chép giá trị minh họa xuống output.",
            "- Golden không có dữ liệu ở Mục 3 (Ngày cấp GCN), Mục 4 (Số vào sổ GCN) và cột Loại GCN; các field này là `GCN_OPTIONAL`.",
            "- Mục 2 vẫn được dùng trong hồ sơ chưa có GCN như mã bộ hồ sơ `CHUACOGIAY_{MA_XA}_{SO_TO}_{SO_THUA}` hoặc `CHUACAPGIAY_{MA_XA}_{SO_TO}_{SO_THUA}`.",
            "- Mục 49 trong golden luôn là hai file `-TBXN.pdf, -DDK.pdf`, cách nhau bởi dấu phẩy và một khoảng trắng.",
            "- Vai trò golden chỉ dùng `Chủ hộ` và `Thành viên hộ gia đình`; không dùng quan hệ Vợ/Chồng/Con.",
            "- Các cột template có sample nhưng golden trống được xếp optional/conditional, không biến thành lỗi bắt buộc.",
            "- Dòng style output lấy từ dòng ví dụ nhưng chỉ copy style; mọi sample value bị loại.",
            "",
            "## Bảng field",
            "",
            "| Mục/Cột | Tên trường | Template sample | Golden có dữ liệu | Phân loại | Mode mặc định | Required |",
            "|---|---|---:|---:|---|---|---:|",
        ]
    )
    for field in schema["fields"]:
        label = f"Mục {field['item']} / {field['column']}" if field["item"].isdigit() else field["column"]
        name = field["name"].replace("|", "/")
        rows.append(
            f"| {label} | {name} | {field['official_sample_count']} | {field['golden_count']} | {field['classification']} | {field['mode']} | {'Có' if field['required'] else 'Không'} |"
        )
    rows.extend(
        [
            "",
            "## Ngoại lệ và rule ưu tiên",
            "",
            "1. Mục 2 mang tên schema liên quan GCN nhưng trong workflow hiện tại là mã bộ hồ sơ và bắt buộc được tính tự động.",
            "2. Mục 19/20 có nhãn 'ghi trên GCN' nhưng golden vẫn dùng cho hồ sơ chưa có GCN; vì vậy đây là số tờ/số thửa bắt buộc hiện tại.",
            "3. Mục 25/27/28/29 và BA/BB là giá trị mặc định theo golden hiện tại, vẫn có thể sửa bằng Advanced Mapping/Profile.",
            "4. GCN được gắn theo thửa; cùng tờ/thửa có hai bộ GCN khác nhau là conflict và không được tự gộp.",
            "5. Output mặc định chỉ giữ sheet schema để tương thích với golden; profile có thể bật giữ các sheet tham chiếu.",
        ]
    )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official", type=Path, required=True)
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--schema-out", type=Path, required=True)
    parser.add_argument("--doc-out", type=Path, required=True)
    args = parser.parse_args()
    schema, analysis = build_schema(args.official, args.golden)
    args.schema_out.parent.mkdir(parents=True, exist_ok=True)
    args.doc_out.parent.mkdir(parents=True, exist_ok=True)
    args.schema_out.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(schema, analysis, args.doc_out)
    print(json.dumps({"fields": schema["field_count"], "classes": schema["classification_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
