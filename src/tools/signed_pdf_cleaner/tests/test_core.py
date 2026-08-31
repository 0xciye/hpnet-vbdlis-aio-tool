import os
import pytest
from pathlib import Path
from tools.signed_pdf_cleaner.core.scanner import FileScanner
from tools.signed_pdf_cleaner.core.processor import FileProcessor
from tools.signed_pdf_cleaner.core.models import ActionType, ProcessStatus

@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path

def create_file(dir_path: Path, filename: str, content: str = ""):
    file_path = dir_path / filename
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path

def test_1_signed_and_unsigned(temp_dir):
    # Test 1: A.pdf and A.signed.pdf -> A.pdf (content SIGNED)
    create_file(temp_dir, "A.pdf", "UNSIGNED")
    create_file(temp_dir, "A.signed.pdf", "SIGNED")
    
    scanner = FileScanner()
    plans = scanner.scan_directory(str(temp_dir))
    
    assert len(plans) == 1
    assert plans[0].action == ActionType.DELETE_AND_RENAME
    assert plans[0].status == ProcessStatus.READY
    
    processor = FileProcessor(use_recycle_bin=False) # Xóa thẳng để test
    processor.process_plan(plans[0])
    
    assert not (temp_dir / "A.signed.pdf").exists()
    assert (temp_dir / "A.pdf").exists()
    with open(temp_dir / "A.pdf", "r", encoding="utf-8") as f:
        assert f.read() == "SIGNED"

def test_2_only_signed(temp_dir):
    # Test 2: A.signed.pdf -> A.pdf
    create_file(temp_dir, "A.signed.pdf", "SIGNED")
    
    scanner = FileScanner()
    plans = scanner.scan_directory(str(temp_dir))
    
    assert len(plans) == 1
    assert plans[0].action == ActionType.RENAME_SIGNED
    
    processor = FileProcessor(use_recycle_bin=False)
    processor.process_plan(plans[0])
    
    assert not (temp_dir / "A.signed.pdf").exists()
    assert (temp_dir / "A.pdf").exists()

def test_3_only_unsigned(temp_dir):
    # Test 3: A.pdf -> A.pdf (không xóa)
    create_file(temp_dir, "A.pdf", "UNSIGNED")
    
    scanner = FileScanner()
    plans = scanner.scan_directory(str(temp_dir))
    
    assert len(plans) == 1
    assert plans[0].action == ActionType.SKIP
    assert plans[0].status == ProcessStatus.SKIPPED
    
    processor = FileProcessor(use_recycle_bin=False)
    processor.process_plan(plans[0])
    
    assert (temp_dir / "A.pdf").exists()

def test_4_multiple_pairs(temp_dir):
    create_file(temp_dir, "A.pdf")
    create_file(temp_dir, "A.signed.pdf")
    create_file(temp_dir, "B.pdf")
    create_file(temp_dir, "B.signed.pdf")
    
    scanner = FileScanner()
    plans = scanner.scan_directory(str(temp_dir))
    
    assert len(plans) == 2
    for p in plans:
        assert p.action == ActionType.DELETE_AND_RENAME
        
    processor = FileProcessor(use_recycle_bin=False)
    for p in plans:
        processor.process_plan(p)
        
    assert (temp_dir / "A.pdf").exists()
    assert (temp_dir / "B.pdf").exists()
    assert not (temp_dir / "A.signed.pdf").exists()
    assert not (temp_dir / "B.signed.pdf").exists()

def test_5_complex_names(temp_dir):
    # CHUACOGIAY_10930_10_300-TBXN
    n1 = "CHUACOGIAY_10930_10_300-TBXN"
    n2 = "CHUACOGIAY_10930_10_300-DDK"
    
    create_file(temp_dir, f"{n1}.pdf", "1_UNSIGNED")
    create_file(temp_dir, f"{n1}.signed.pdf", "1_SIGNED")
    create_file(temp_dir, f"{n2}.pdf", "2_UNSIGNED")
    create_file(temp_dir, f"{n2}.signed.pdf", "2_SIGNED")
    
    scanner = FileScanner()
    plans = scanner.scan_directory(str(temp_dir))
    
    assert len(plans) == 2
    processor = FileProcessor(use_recycle_bin=False)
    for p in plans:
        processor.process_plan(p)
        
    with open(temp_dir / f"{n1}.pdf", "r") as f:
        assert f.read() == "1_SIGNED"
    with open(temp_dir / f"{n2}.pdf", "r") as f:
        assert f.read() == "2_SIGNED"

def test_ignore_unrelated_files(temp_dir):
    create_file(temp_dir, "A.pdf")
    create_file(temp_dir, "A.signed.pdf")
    create_file(temp_dir, "DanhSach.xlsx")
    create_file(temp_dir, "GhiChu.txt")
    create_file(temp_dir, "B.pdf")
    
    scanner = FileScanner()
    plans = scanner.scan_directory(str(temp_dir))
    
    processor = FileProcessor(use_recycle_bin=False)
    for p in plans:
        processor.process_plan(p)
        
    assert (temp_dir / "A.pdf").exists()
    assert (temp_dir / "DanhSach.xlsx").exists()
    assert (temp_dir / "GhiChu.txt").exists()
    assert (temp_dir / "B.pdf").exists()

def test_abnormal_signed_name(temp_dir):
    create_file(temp_dir, "A.signed.signed.pdf")
    
    scanner = FileScanner()
    plans = scanner.scan_directory(str(temp_dir))
    
    assert len(plans) == 1
    assert plans[0].status == ProcessStatus.WARNING
    assert plans[0].action == ActionType.SKIP
    assert plans[0].warning_message == "Tên file bất thường (có nhiều .signed)"

def test_file_lock(temp_dir):
    create_file(temp_dir, "A.pdf")
    create_file(temp_dir, "A.signed.pdf")
    
    scanner = FileScanner()
    plans = scanner.scan_directory(str(temp_dir))
    
    # Simulate file lock by opening the file
    with open(temp_dir / "A.pdf", "r") as f:
        processor = FileProcessor(use_recycle_bin=False) # will try to use os.remove
        # Windows will block os.remove on an opened file
        processor.process_plan(plans[0])
        
    assert plans[0].status == ProcessStatus.ERROR
    assert "Không thể xóa file" in plans[0].error_message
    
    # Original files should remain
    assert (temp_dir / "A.signed.pdf").exists()
