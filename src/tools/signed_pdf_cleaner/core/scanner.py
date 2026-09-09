from pathlib import Path
from typing import List
from pypdf import PdfReader
from tools.signed_pdf_cleaner.core.models import FileActionPlan, ActionType, ProcessStatus

class FileScanner:
    def __init__(self, validate_signatures: bool = True, delete_suffix: str = '.pdf', signed_suffix: str = '.signed.pdf'):
        self.validate_signatures = validate_signatures
        self.delete_suffix = delete_suffix.lower() if delete_suffix.startswith('.') else '.' + delete_suffix.lower()
        self.signed_suffix = signed_suffix.lower() if signed_suffix.startswith('.') else '.' + signed_suffix.lower()

    @staticmethod
    def has_embedded_signature(path: Path) -> bool:
        try:
            fields = PdfReader(path, strict=False).get_fields() or {}
            return any(str(field.get("/FT", "")) == "/Sig" and field.get("/V") for field in fields.values())
        except Exception:
            return False

    def scan_directory(self, folder_path: str, recursive: bool = False) -> List[FileActionPlan]:
        plans = []
        base_path = Path(folder_path)
        
        if not base_path.exists() or not base_path.is_dir():
            return plans

        # If recursive, we iterate through all directories
        directories = [base_path]
        if recursive:
            directories.extend([d for d in base_path.rglob("*") if d.is_dir()])
            
        for current_dir in directories:
            # We process files per directory (no cross-directory matching)
            plans.extend(self._process_single_directory(current_dir))
            
        return plans

    def _process_single_directory(self, directory: Path) -> List[FileActionPlan]:
        plans = []
        # Get all files, ignore dirs
        try:
            files = [f for f in directory.iterdir() if f.is_file()]
        except PermissionError:
            return plans

        # Filter out hidden/temp files (basic check)
        valid_files = []
        for f in files:
            name = f.name
            if name.startswith('~$') or name.endswith('.tmp') or name.endswith('.crdownload') or name.endswith('.part'):
                continue
            # Also only process PDFs based on rules, but wait, if it's not a pdf we just ignore
            if not name.lower().endswith('.pdf'):
                continue
            valid_files.append(f)

        # Separate signed and all pdfs
        signed_files = []
        all_pdfs = {f.name.lower(): f for f in valid_files}
        
        for f in valid_files:
            if f.name.lower().endswith(self.signed_suffix):
                signed_files.append(f)

        # To keep track of processed unsigned files so we can also check for unsigned-only
        matched_unsigned = set()

        for signed_f in signed_files:
            original_name = signed_f.name
            target_name = original_name[:-len(self.signed_suffix)] + self.delete_suffix
            
            # check abnormal name like .signed.signed.pdf
            if target_name.lower().endswith(self.signed_suffix):
                plans.append(FileActionPlan(
                    signed_path=signed_f,
                    unsigned_path=None,
                    target_path=directory / target_name,
                    action=ActionType.SKIP,
                    status=ProcessStatus.WARNING,
                    warning_message="Tên file bất thường (có nhiều .signed)"
                ))
                continue

            if self.validate_signatures and not self.has_embedded_signature(signed_f):
                plans.append(FileActionPlan(
                    signed_path=signed_f,
                    unsigned_path=None,
                    target_path=directory / target_name,
                    action=ActionType.SKIP,
                    status=ProcessStatus.WARNING,
                    warning_message="File có hậu tố .signed nhưng không tìm thấy cấu trúc chữ ký số trong PDF"
                ))
                continue

            target_path = directory / target_name
            unsigned_f = all_pdfs.get(target_name.lower())

            if unsigned_f:
                matched_unsigned.add(unsigned_f)
                plans.append(FileActionPlan(
                    signed_path=signed_f,
                    unsigned_path=unsigned_f,
                    target_path=target_path,
                    action=ActionType.DELETE_AND_RENAME,
                    status=ProcessStatus.READY
                ))
            else:
                plans.append(FileActionPlan(
                    signed_path=signed_f,
                    unsigned_path=None,
                    target_path=target_path,
                    action=ActionType.RENAME_SIGNED,
                    status=ProcessStatus.READY
                ))

        # Now handle unsigned only
        for f in valid_files:
            if f not in matched_unsigned and f not in signed_files:
                plans.append(FileActionPlan(
                    signed_path=None,
                    unsigned_path=f,
                    target_path=f,
                    action=ActionType.SKIP,
                    status=ProcessStatus.SKIPPED,
                    warning_message="Bỏ qua - không có bản signed tương ứng."
                ))

        return plans
