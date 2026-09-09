import pytest
from openpyxl import Workbook
from pathlib import Path
from tools.hpnet_file_generator.models.data_models import PersonRecord, Parcel, SourceFile, ProfileConfig, ActionStatus
from tools.hpnet_file_generator.utils.text_normalizer import normalize_person_name, extract_stt_and_name
from tools.hpnet_file_generator.core.person_matcher import PersonMatcher
from tools.hpnet_file_generator.core.naming_engine import NamingEngine
from tools.hpnet_file_generator.core.action_planner import ActionPlanner
from tools.hpnet_file_generator.core.excel_reader import ExcelReader

def test_normalize_person_name():
    assert normalize_person_name(" NGUYỄN   VĂN A ") == "nguyễn văn a"
    assert normalize_person_name("nguyễn văn a") == "nguyễn văn a"
    assert normalize_person_name("ĐỖ ĐỨC ĐẠT") == "đỗ đức đạt"

def test_extract_stt():
    stt, name = extract_stt_and_name("1. Nguyễn Văn A")
    assert stt == "1"
    assert name == "Nguyễn Văn A"
    
    stt, name = extract_stt_and_name("001 - Trần B")
    assert stt == "001"
    assert name == "Trần B"
    
    stt, name = extract_stt_and_name("Lê C")
    assert stt is None
    assert name == "Lê C"

def test_person_matcher():
    records = [
        PersonRecord(ho_ten="Nguyễn Văn A", normalized_name="nguyễn văn a"),
        PersonRecord(ho_ten="Trần B", normalized_name="trần b"),
    ]
    records[0].parcels.add(Parcel("70", "300"))
    
    sources = [
        SourceFile(original_path=Path("1. Nguyễn Văn A.pdf"), filename="1. Nguyễn Văn A.pdf", normalized_name="nguyễn văn a", extension=".pdf"),
        SourceFile(original_path=Path("Lê C.pdf"), filename="Lê C.pdf", normalized_name="lê c", extension=".pdf")
    ]
    
    matcher = PersonMatcher(records, sources)
    matcher.match()
    
    assert sources[0].matched_person == records[0]
    assert sources[1].matched_person is None

def test_person_matcher_ambiguous():
    records = [
        PersonRecord(ho_ten="A", normalized_name="a", secondary_key="1"),
        PersonRecord(ho_ten="A", normalized_name="a", secondary_key="2"),
    ]
    
    sources = [
        SourceFile(original_path=Path("A.pdf"), filename="A.pdf", normalized_name="a", extension=".pdf")
    ]
    
    matcher = PersonMatcher(records, sources)
    matcher.match()
    assert sources[0].matched_person is None
    assert sources[0].is_ambiguous == True

def test_naming_engine():
    config = ProfileConfig(ma_dvhc="10930", prefix="CHUACOGIAY")
    engine = NamingEngine(config)
    
    class DummyAction:
        def __init__(self):
            self.parcel = Parcel("70", "300")
            self.suffix = "TBXN"
            self.source_file = SourceFile(Path("A.pdf"), "A.pdf", "a", ".pdf")
            self.source_file.matched_person = PersonRecord("A", "a")
            self.source_file.stt = "1"
            
    name = engine.generate_filename(DummyAction())
    assert name == "CHUACOGIAY_10930_70_300-TBXN.pdf"

def test_action_planner_conflict(tmp_path):
    config = ProfileConfig(suffixes=["TBXN"])
    
    sf1 = SourceFile(Path("A.pdf"), "A.pdf", "a", ".pdf")
    sf1.matched_person = PersonRecord("A", "a")
    sf1.matched_person.parcels.add(Parcel("70", "300"))
    
    sf2 = SourceFile(Path("B.pdf"), "B.pdf", "b", ".pdf")
    sf2.matched_person = PersonRecord("B", "b")
    # Cùng thửa (giả lập 2 người có thửa trùng nhau, dù đã bị loại ở bước đọc Excel nhưng ở Planner vẫn phải bắt conflict)
    sf2.matched_person.parcels.add(Parcel("70", "300"))
    
    planner = ActionPlanner([sf1, sf2], str(tmp_path), config)
    actions = planner.build_plan()
    
    # 2 actions
    assert len(actions) == 2
    # Một action sẽ READY, một action sẽ CONFLICT
    statuses = [a.status for a in actions]
    assert ActionStatus.READY in statuses
    assert ActionStatus.CONFLICT in statuses


def test_excel_reader_keeps_single_header_behavior(tmp_path):
    path = tmp_path / "single-header.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["STT", "Tên hộ", "Số tờ", "Số thửa"])
    sheet.append([1, "Nguyễn Văn A", 10, 20])
    workbook.save(path)

    reader = ExcelReader(str(path))
    assert reader.header_depth(sheet.title, 1) == 1
    assert reader.get_headers(sheet.title, 1)[:4] == ["STT", "Tên hộ", "Số tờ", "Số thửa"]
    records = reader.read_data(sheet.title, 1, {
        "ho_ten": "Tên hộ", "so_to": "Số tờ", "so_thua": "Số thửa"
    })
    assert records[0].raw_rows == [2]
    assert records[0].parcels == {Parcel("10", "20")}


def test_excel_reader_flattens_two_level_merged_headers_and_skips_both_rows(tmp_path):
    path = tmp_path / "two-level-header.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.merge_cells("A4:A5")
    sheet.merge_cells("B4:B5")
    sheet.merge_cells("C4:E4")
    sheet["A4"] = "STT"
    sheet["B4"] = "Tên hộ"
    sheet["C4"] = "BĐ 2004"
    sheet["C5"] = "Số thửa"
    sheet["D5"] = "Tờ BĐ"
    sheet["E5"] = "Diện tích"
    sheet["A6"] = 1
    sheet["B6"] = "Nguyễn Văn A"
    sheet["C6"] = 55
    sheet["D6"] = 12
    sheet["E6"] = 100
    workbook.save(path)

    reader = ExcelReader(str(path))
    assert reader.header_depth(sheet.title, 4) == 2
    assert reader.get_headers(sheet.title, 4)[:5] == [
        "STT", "Tên hộ", "BĐ 2004 / Số thửa", "BĐ 2004 / Tờ BĐ", "BĐ 2004 / Diện tích"
    ]
    records = reader.read_data(sheet.title, 4, {
        "ho_ten": "Tên hộ",
        "so_to": "BĐ 2004 / Tờ BĐ",
        "so_thua": "BĐ 2004 / Số thửa",
        "secondary_key": "STT",
    })
    assert records[0].raw_rows == [6]
    assert records[0].secondary_key == "1"
    assert records[0].parcels == {Parcel("12", "55")}
