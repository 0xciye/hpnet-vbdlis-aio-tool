from pathlib import Path
from typing import List, Sequence, Union
from pypdf import PdfReader
from tools.signed_pdf_cleaner.core.models import FileActionPlan, ActionType, ProcessStatus

SuffixInput = Union[str, Sequence[str]]
TARGET_ALL = "all"
TARGET_PAIRS = "pairs"
TARGET_ORPHAN_SIGNED = "orphan_signed"


def parse_suffixes(value: SuffixInput, default: str) -> List[str]:
    """Normalize one or more suffixes to values that end in ``.pdf``.

    The UI accepts values such as ``.signed, .ldsigned`` as well as the
    previous ``.signed.pdf`` form.  Keeping the normalized value complete
    makes matching case-insensitive and prevents a suffix from matching a
    filename extension other than PDF.
    """
    raw_values = value if isinstance(value, (list, tuple)) else str(value).replace(";", ",").split(",")
    normalized: List[str] = []
    seen = set()
    for raw in raw_values:
        suffix = str(raw).strip().lower()
        if not suffix:
            continue
        if not suffix.startswith("."):
            suffix = "." + suffix
        if suffix in {".", ".pdf"}:
            canonical = ".pdf"
        elif suffix.endswith(".pdf"):
            canonical = suffix
        else:
            canonical = suffix + ".pdf"
        if any(ch in canonical for ch in '\\/:*?"<>|') or canonical.endswith("."):
            raise ValueError(f"Hậu tố không hợp lệ: {raw}")
        if canonical not in seen:
            normalized.append(canonical)
            seen.add(canonical)
    if not normalized:
        raise ValueError(f"Hãy nhập ít nhất một hậu tố (ví dụ: {default})")
    return normalized


class FileScanner:
    def __init__(self, validate_signatures: bool = True, delete_suffix: SuffixInput = '.pdf', signed_suffix: SuffixInput = '.signed.pdf'):
        self.validate_signatures = validate_signatures
        self.delete_suffixes = parse_suffixes(delete_suffix, ".pdf")
        self.signed_suffixes = parse_suffixes(signed_suffix, ".signed")
        # Keep the singular attributes for callers that used the old API.
        self.delete_suffix = self.delete_suffixes[0]
        self.signed_suffix = self.signed_suffixes[0]

    def _delete_suffix_for_signed(self, signed_suffix: str, signed_index: int) -> str:
        """Choose the removable-file suffix corresponding to a kept suffix.

        For the common pairs ``.signed -> .signed.signed`` and
        ``.ldsigned -> .ldsigned.signed``, the removable suffix is inferred
        from the kept suffix. If a custom pair cannot be inferred, values
        fall back to the same-order delete suffix and finally the first
        configured suffix.
        """
        signed_stem = signed_suffix[:-4] if signed_suffix.endswith(".pdf") else signed_suffix
        for delete_suffix in sorted(self.delete_suffixes, key=len, reverse=True):
            delete_stem = delete_suffix[:-4] if delete_suffix.endswith(".pdf") else delete_suffix
            if signed_stem.endswith(delete_stem + ".signed"):
                return delete_suffix
        if signed_index < len(self.delete_suffixes):
            return self.delete_suffixes[signed_index]
        return self.delete_suffixes[0]

    @staticmethod
    def has_embedded_signature(path: Path) -> bool:
        try:
            fields = PdfReader(path, strict=False).get_fields() or {}
            return any(str(field.get("/FT", "")) == "/Sig" and field.get("/V") for field in fields.values())
        except Exception:
            return False

    def scan_directory(self, folder_path: str, recursive: bool = False, target_mode: str = TARGET_ALL) -> List[FileActionPlan]:
        if target_mode not in {TARGET_ALL, TARGET_PAIRS, TARGET_ORPHAN_SIGNED}:
            raise ValueError(f"Mục tiêu xử lý không hợp lệ: {target_mode}")
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
            plans.extend(self._process_single_directory(current_dir, target_mode))
            
        return plans

    def _process_single_directory(self, directory: Path, target_mode: str = TARGET_ALL) -> List[FileActionPlan]:
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
            if any(f.name.lower().endswith(suffix) for suffix in self.signed_suffixes):
                signed_files.append(f)

        # To keep track of processed unsigned files so we can also check for unsigned-only
        matched_unsigned = set()

        ordered_signed_suffixes = sorted(enumerate(self.signed_suffixes), key=lambda item: len(item[1]), reverse=True)
        for signed_f in signed_files:
            original_name = signed_f.name
            signed_name_lower = original_name.lower()
            signed_index, matched_suffix = next(
                ((index, suffix) for index, suffix in ordered_signed_suffixes if signed_name_lower.endswith(suffix)),
                (0, self.signed_suffixes[0]),
            )
            # Remove the complete configured keep suffix. The resulting file
            # always returns to the normal PDF name (for example
            # A.signed.signed.pdf -> A.pdf).
            base_name = original_name[:-len(matched_suffix)]
            target_name = base_name + ".pdf"
            delete_suffix = self._delete_suffix_for_signed(matched_suffix, signed_index)
            delete_name = base_name + delete_suffix
            
            # Keep warning for a configured suffix that still resolves to
            # another configured signed file (usually a duplicated suffix).
            if any(target_name.lower().endswith(suffix) for suffix in self.signed_suffixes):
                plans.append(FileActionPlan(
                    signed_path=signed_f,
                    unsigned_path=None,
                    target_path=directory / target_name,
                    action=ActionType.SKIP,
                    status=ProcessStatus.WARNING,
                    warning_message="Tên file có nhiều hậu tố đã cấu hình, cần kiểm tra lại"
                ))
                continue

            if self.validate_signatures and not self.has_embedded_signature(signed_f):
                plans.append(FileActionPlan(
                    signed_path=signed_f,
                    unsigned_path=None,
                    target_path=directory / target_name,
                    action=ActionType.SKIP,
                    status=ProcessStatus.WARNING,
                    warning_message="File có hậu tố đã cấu hình nhưng không tìm thấy cấu trúc chữ ký số trong PDF"
                ))
                continue

            target_path = directory / target_name
            # The file to remove keeps its configured removable suffix
            # (A.signed.pdf or B.ldsigned.pdf), while the kept file is renamed
            # to the clean base name (A.pdf or B.pdf).
            unsigned_f = all_pdfs.get(delete_name.lower())

            if target_mode == TARGET_PAIRS and unsigned_f is None:
                continue
            if target_mode == TARGET_ORPHAN_SIGNED and unsigned_f is not None:
                continue

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
            if target_mode == TARGET_ORPHAN_SIGNED:
                continue
            if f not in matched_unsigned and f not in signed_files:
                plans.append(FileActionPlan(
                    signed_path=None,
                    unsigned_path=f,
                    target_path=f,
                    action=ActionType.SKIP,
                    status=ProcessStatus.SKIPPED,
                    warning_message="Bỏ qua - không có bản đã ký tương ứng."
                ))

        return plans
