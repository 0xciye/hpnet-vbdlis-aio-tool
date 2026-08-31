import pytest
from pathlib import Path
from tools.hpnet_file_generator.models.data_models import PersonRecord, Parcel, SourceFile, ProfileConfig, ActionStatus
from tools.hpnet_file_generator.utils.text_normalizer import normalize_person_name, extract_stt_and_name
from tools.hpnet_file_generator.core.person_matcher import PersonMatcher
from tools.hpnet_file_generator.core.naming_engine import NamingEngine
from tools.hpnet_file_generator.core.action_planner import ActionPlanner

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
