from pathlib import Path

from openpyxl import Workbook, load_workbook

from tools.duplicate_parcel.models import ScanConfig
from tools.duplicate_parcel.report import export_report
from tools.duplicate_parcel.service import apply_cleanup, is_total_dt, normalized_area, normalized_identifier, scan


def make_source(path: Path):
    wb = Workbook(); ws = wb.active; ws.title = "Data"
    ws.append(["", "Họ tên", "", "", "", "", "Số tờ", "Số thửa", "Diện tích", "Xứ đồng"])
    ws.append([]); ws.append([])
    rows = [
        ["", "Nguyễn Văn A", "", "", "", "", 39, 19, 500, "Đồng Cầu"],
        ["", "Nguyễn Thị B", "", "", "", "", "39.0", " 19 ", "500.00", " đồng   cầu "],
        ["", "Nguyễn Văn C", "", "", "", "", 39, 19, 520, "Đồng Cầu"],
        ["", "", "", "", "", "", 39, 20, 10, "Khác"],
        ["", " TỔNG   DT ", "", "", "", "", "protected", "protected", 1030, "protected"],
        ["", "Trần Văn D", "", "", "", "", 39, 19, 500, "Đồng Cầu"],
        ["", "", "", "", "", "", 40, 20, None, "Đồng Mới"],
        ["", "", "", "", "", "", 40, 20, 100, "Đồng Mới"],
        ["", "tổng dt", "", "", "", "", "protected2", "protected2", 600, "protected2"],
    ]
    for row in rows: ws.append(row)
    wb.save(path); wb.close()


def test_household_boundary_duplicate_conflicts_and_cross_household(tmp_path):
    source = tmp_path / "input.xlsx"; make_source(source)
    result = scan(ScanConfig(source, "Data", "B", "G", "H", "I", "J", 4, "G", "X"))
    by_row = {record.row: record for record in result.records}
    assert result.summary_rows == [8, 12]
    duplicate_rows = {4, 5, 6, 9, 10, 11}
    assert all(by_row[row].status == "EXACT_DUPLICATE" and by_row[row].selected for row in duplicate_rows)
    assert set(by_row[4].related_rows) == {5, 6, 9}
    assert set(by_row[10].related_rows) == {11}
    assert by_row[4].household == by_row[7].household == 1
    assert by_row[9].household == 2
    assert by_row[9].household == 2
    assert by_row[10].status == by_row[11].status == "EXACT_DUPLICATE"
    assert by_row[7].status == "KEEP"


def test_apply_only_clears_configured_cells_and_preserves_summary(tmp_path):
    source = tmp_path / "input.xlsx"; make_source(source); original = source.read_bytes()
    result = scan(ScanConfig(source, "Data", "B", "G", "H", "I", "J", 4, "G", "X"))
    output, backup = apply_cleanup(result, tmp_path / "cleaned.xlsx")
    assert source.read_bytes() == original and backup.read_bytes() == original
    wb = load_workbook(output); ws = wb["Data"]
    assert ws["B4"].value == "Nguyễn Văn A"
    assert ws["B5"].value == "Nguyễn Thị B"
    for row in (4, 5, 6, 9, 10, 11):
        assert all(ws.cell(row, column).value is None for column in range(7, 25))
    assert ws["G8"].value == "protected" and ws["B8"].value.strip().startswith("TỔNG")
    wb.close()
    report = export_report(result, tmp_path / "duplicate_parcel_report.xlsx")
    wb = load_workbook(report, read_only=False); assert {"Summary", "Exact Duplicates", "Parcel Conflicts", "Cross Household", "Incomplete Data"} <= set(wb.sheetnames)
    assert wb["Summary"]["A4"].value == "EXACT_DUPLICATE"
    assert wb["Summary"]["B4"].value == 6
    assert wb["Cross Household"].max_row == 1
    assert wb["Summary"]["A1"].fill.fgColor.rgb.endswith("1F4E78")
    wb.close()


def test_normalization_keeps_distinct_parcel_identifiers():
    assert normalized_identifier(39) == normalized_identifier("39.0") == "39"
    assert len({normalized_identifier(value) for value in ("39", "39.1", "39/1", "39A")}) == 4
    assert normalized_area(500) == normalized_area("500.00")
    assert is_total_dt(" Tổng   DT ") and not is_total_dt("Tổng diện tích")
