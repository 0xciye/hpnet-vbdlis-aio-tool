import os
import pytest
from pathlib import Path
from pypdf import PdfWriter
from tools.signed_pdf_cleaner.core.scanner import FileScanner, parse_suffixes, TARGET_PAIRS, TARGET_ORPHAN_SIGNED
from tools.signed_pdf_cleaner.core.processor import FileProcessor
from tools.signed_pdf_cleaner.core.models import ActionType, FileActionPlan, ProcessStatus
from tools.signed_pdf_cleaner.utils.logger import AppLogger

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
    
    scanner = FileScanner(validate_signatures=False)
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
    
    scanner = FileScanner(validate_signatures=False)
    plans = scanner.scan_directory(str(temp_dir))
    
    assert len(plans) == 1
    assert plans[0].action == ActionType.RENAME_SIGNED
    
    processor = FileProcessor(use_recycle_bin=False)
    processor.process_plan(plans[0])
    
    assert not (temp_dir / "A.signed.pdf").exists()
    assert (temp_dir / "A.pdf").exists()


def test_target_mode_orphan_signed_only(temp_dir):
    create_file(temp_dir, "A.signed.pdf", "SIGNED")
    create_file(temp_dir, "B.pdf", "UNSIGNED")
    create_file(temp_dir, "B.signed.pdf", "SIGNED_PAIR")

    scanner = FileScanner(validate_signatures=False)
    plans = scanner.scan_directory(str(temp_dir), target_mode=TARGET_ORPHAN_SIGNED)

    assert len(plans) == 1
    assert plans[0].signed_path.name == "A.signed.pdf"
    assert plans[0].action == ActionType.RENAME_SIGNED


def test_target_mode_pairs_excludes_orphan_signed(temp_dir):
    create_file(temp_dir, "A.signed.pdf", "SIGNED")
    create_file(temp_dir, "B.pdf", "UNSIGNED")
    create_file(temp_dir, "B.signed.pdf", "SIGNED_PAIR")

    scanner = FileScanner(validate_signatures=False)
    plans = scanner.scan_directory(str(temp_dir), target_mode=TARGET_PAIRS)

    assert len(plans) == 1
    assert plans[0].action == ActionType.DELETE_AND_RENAME
    assert plans[0].signed_path.name == "B.signed.pdf"

def test_3_only_unsigned(temp_dir):
    # Test 3: A.pdf -> A.pdf (không xóa)
    create_file(temp_dir, "A.pdf", "UNSIGNED")
    
    scanner = FileScanner(validate_signatures=False)
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
    
    scanner = FileScanner(validate_signatures=False)
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

def test_multiple_suffix_pairs_are_normalized_and_processed(temp_dir):
    """Each kept file loses all configured suffixes and returns to base.pdf."""
    create_file(temp_dir, "A.signed.pdf", "OLD_SIGNED")
    create_file(temp_dir, "A.signed.signed.pdf", "NEW_SIGNED")
    create_file(temp_dir, "B.ldsigned.pdf", "OLD_LDSIGNED")
    create_file(temp_dir, "B.ldsigned.signed.pdf", "NEW_LDSIGNED")

    scanner = FileScanner(
        validate_signatures=False,
        delete_suffix=".signed, .ldsigned",
        signed_suffix=".signed.signed, .ldsigned.signed",
    )
    assert scanner.delete_suffixes == [".signed.pdf", ".ldsigned.pdf"]
    assert scanner.signed_suffixes == [".signed.signed.pdf", ".ldsigned.signed.pdf"]
    plans = scanner.scan_directory(str(temp_dir))

    ready = [p for p in plans if p.status == ProcessStatus.READY]
    assert len(ready) == 2
    assert {p.target_path.name for p in ready} == {"A.pdf", "B.pdf"}
    assert {p.unsigned_path.name for p in ready} == {"A.signed.pdf", "B.ldsigned.pdf"}
    assert all(p.action == ActionType.DELETE_AND_RENAME for p in ready)

    processor = FileProcessor(use_recycle_bin=False)
    for plan in ready:
        processor.process_plan(plan)

    assert (temp_dir / "A.pdf").read_text(encoding="utf-8") == "NEW_SIGNED"
    assert (temp_dir / "B.pdf").read_text(encoding="utf-8") == "NEW_LDSIGNED"
    assert not (temp_dir / "A.signed.signed.pdf").exists()
    assert not (temp_dir / "B.ldsigned.signed.pdf").exists()

def test_parse_suffixes_accepts_commas_and_legacy_pdf_form():
    assert parse_suffixes("signed, .SIGNED.pdf, .ldsigned", ".signed") == [
        ".signed.pdf", ".ldsigned.pdf"
    ]
    with pytest.raises(ValueError):
        parse_suffixes("*.signed", ".signed")


def test_signed_suffix_cannot_be_plain_pdf():
    with pytest.raises(ValueError, match="phải có phần đứng trước"):
        FileScanner(validate_signatures=False, signed_suffix=".pdf")


def test_scan_progress_reports_each_pdf(temp_dir):
    create_file(temp_dir, "A.pdf", "UNSIGNED")
    create_file(temp_dir, "A.signed.pdf", "SIGNED")
    create_file(temp_dir, "note.txt", "IGNORED")
    progress = []

    FileScanner(validate_signatures=False).scan_directory(
        str(temp_dir),
        progress_callback=lambda done, total: progress.append((done, total)),
    )

    assert progress[0] == (0, 2)
    assert progress[-1] == (2, 2)

def test_5_complex_names(temp_dir):
    # CHUACOGIAY_10930_10_300-TBXN
    n1 = "CHUACOGIAY_10930_10_300-TBXN"
    n2 = "CHUACOGIAY_10930_10_300-DDK"
    
    create_file(temp_dir, f"{n1}.pdf", "1_UNSIGNED")
    create_file(temp_dir, f"{n1}.signed.pdf", "1_SIGNED")
    create_file(temp_dir, f"{n2}.pdf", "2_UNSIGNED")
    create_file(temp_dir, f"{n2}.signed.pdf", "2_SIGNED")
    
    scanner = FileScanner(validate_signatures=False)
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
    
    scanner = FileScanner(validate_signatures=False)
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
    
    scanner = FileScanner(validate_signatures=False)
    plans = scanner.scan_directory(str(temp_dir))
    
    assert len(plans) == 1
    assert plans[0].status == ProcessStatus.WARNING
    assert plans[0].action == ActionType.SKIP
    assert plans[0].warning_message == "Tên file có nhiều hậu tố đã cấu hình, cần kiểm tra lại"

def test_file_lock(temp_dir):
    create_file(temp_dir, "A.pdf")
    create_file(temp_dir, "A.signed.pdf")
    
    scanner = FileScanner(validate_signatures=False)
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


def test_fake_signed_suffix_is_not_processed(temp_dir):
    writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
    with (temp_dir / "A.signed.pdf").open("wb") as stream: writer.write(stream)
    plans = FileScanner().scan_directory(str(temp_dir))
    assert len(plans) == 1
    assert plans[0].action == ActionType.SKIP
    assert plans[0].status == ProcessStatus.WARNING
    assert "không tìm thấy cấu trúc chữ ký" in plans[0].warning_message


def test_csv_log_escapes_excel_formula(tmp_path):
    logger = AppLogger(str(tmp_path / "logs"))
    report = tmp_path / "report.csv"
    logger.export_csv([FileActionPlan(Path("=HYPERLINK(1).signed.pdf"), None, Path("safe.pdf"), ActionType.RENAME_SIGNED, ProcessStatus.READY)], report)
    assert "'=HYPERLINK(1).signed.pdf" in report.read_text(encoding="utf-8-sig")
