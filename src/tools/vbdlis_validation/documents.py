from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from pathlib import Path

from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.sign.validation.settings import KeyUsageConstraints
from pyhanko_certvalidator import ValidationContext

from .models import DocumentRecord, DocumentType, SignatureResult, SignatureStatus
from .normalization import normalize_identifier, normalize_name

_TYPE_PATTERN = re.compile(r"(?:^|[-_.\s])(TBXN|DDK)(?:$|[-_.\s])", re.IGNORECASE)
_PROJECT_PATTERN = re.compile(r"^(?P<body>.+?)-(?P<kind>TBXN|DDK)$", re.IGNORECASE)
_GENERIC_PARCEL_PATTERN = re.compile(
    r"(?:^|[_\s-])(?:to|tờ)(?:[_\s-]*(?:so|số|ban[_\s-]*do|bản[_\s-]*đồ))?[_\s-]*(?P<sheet>[0-9]+(?:[./-][0-9a-z]+)*)"
    r".*?(?:thua|thửa)(?:[_\s-]*(?:so|số|dat|đất))?[_\s-]*(?P<parcel>[0-9]+(?:[./-][0-9a-z]+)*)",
    re.IGNORECASE,
)


def _strip_extensions(filename: str) -> str:
    stem = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    while re.search(r"\.(?:signed|ldsigned|lsigned)$", stem, flags=re.IGNORECASE):
        stem = re.sub(r"\.(?:signed|ldsigned|lsigned)$", "", stem, flags=re.IGNORECASE)
    return stem


def parse_document(path: Path, hinted_type: DocumentType = DocumentType.UNKNOWN) -> DocumentRecord:
    base = _strip_extensions(path.name)
    type_match = _TYPE_PATTERN.search(base)
    document_type = DocumentType(type_match.group(1).upper()) if type_match else hinted_type
    owner_raw = sheet_raw = parcel_raw = ""
    confidence = 0.25 if document_type != DocumentType.UNKNOWN else 0.0

    project = _PROJECT_PATTERN.match(base)
    if project:
        document_type = DocumentType(project.group("kind").upper())
        parts = [part for part in project.group("body").split("_") if part]
        if len(parts) >= 3 and parts[0].upper() in {"CHUACOGIAY", "CHUACAPGIAY"}:
            sheet_raw, parcel_raw = parts[-2], parts[-1]
            confidence = 1.0

    if not sheet_raw:
        generic = _GENERIC_PARCEL_PATTERN.search(base)
        if generic:
            sheet_raw, parcel_raw = generic.group("sheet"), generic.group("parcel")
            owner_raw = re.split(r"(?:^|[_\s-])(?:to|tờ)(?:[_\s-]|$)", base, maxsplit=1, flags=re.IGNORECASE)[0]
            confidence = max(confidence, 0.9 if document_type != DocumentType.UNKNOWN else 0.7)

    return DocumentRecord(
        path=path,
        document_type=document_type,
        owner_raw=owner_raw,
        owner_normalized=normalize_name(owner_raw),
        sheet_raw=sheet_raw,
        sheet_normalized=normalize_identifier(sheet_raw, "sheet"),
        parcel_raw=parcel_raw,
        parcel_normalized=normalize_identifier(parcel_raw, "parcel"),
        parse_confidence=confidence,
    )


class SignatureValidator:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, int, int], SignatureResult] = {}
        # pyHanko reports expected validation failures with full tracebacks. The
        # application records the compact status instead of exposing that noise.
        logging.getLogger("pyhanko").setLevel(logging.CRITICAL)
        logging.getLogger("pyhanko_certvalidator").setLevel(logging.CRITICAL)

    def validate(self, path: Path) -> SignatureResult:
        try:
            stat = path.stat()
            key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
        except OSError as error:
            return SignatureResult(
                SignatureStatus.SIGNATURE_ERROR,
                message=str(error),
                file_access_error=True,
            )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._validate_uncached(path)
        self._cache[key] = result
        return result

    @staticmethod
    def _certificate_info(embedded_signature) -> dict[str, str]:
        certificate = embedded_signature.signer_cert
        validity = certificate["tbs_certificate"]["validity"].native
        return {
            "subject": certificate.subject.human_friendly,
            "issuer": certificate.issuer.human_friendly,
            "serial_number": str(certificate.serial_number),
            "not_before": str(validity.get("not_before", "")),
            "not_after": str(validity.get("not_after", "")),
        }

    def _validate_uncached(self, path: Path) -> SignatureResult:
        try:
            with path.open("rb") as stream:
                reader = PdfFileReader(stream, strict=False)
                signatures = list(reader.embedded_signatures)
                if not signatures:
                    return SignatureResult(
                        SignatureStatus.UNSIGNED,
                        message="PDF không có chữ ký số nhúng.",
                        signature_present=False,
                    )
                validation_context = ValidationContext(
                    trust_roots=[], allow_fetching=False, revocation_mode="soft-fail"
                )
                usage = KeyUsageConstraints(key_usage=set(), explicit_extd_key_usage_required=False)
                integrity_results: list[bool] = []
                trust_results: list[bool] = []
                modification_results: list[bool] = []
                certificates: list[dict[str, str]] = []
                messages: list[str] = []
                for signature_index, signature in enumerate(signatures):
                    byte_range = signature.sig_object.get("/ByteRange")
                    if not byte_range or len(byte_range) != 4:
                        integrity_results.append(False)
                        trust_results.append(False)
                        messages.append("Chữ ký thiếu ByteRange hợp lệ.")
                        continue
                    try:
                        status = validate_pdf_signature(
                            signature,
                            signer_validation_context=validation_context,
                            key_usage_settings=usage,
                            # Earlier signatures are necessarily followed by later
                            # revisions. Full modification analysis on the latest
                            # signature is sufficient; CMS integrity is still
                            # checked for every signature.
                            skip_diff=signature_index < len(signatures) - 1,
                        )
                        intact = bool(status.intact and status.valid and status.docmdp_ok is not False)
                        integrity_results.append(intact)
                        trust_results.append(bool(status.trusted))
                        modification_results.append(status.docmdp_ok is False)
                        messages.append(status.summary())
                    except Exception as error:  # noqa: BLE001 - malformed third-party CMS must not abort the batch
                        integrity_results.append(False)
                        trust_results.append(False)
                        modification_results.append(False)
                        messages.append(f"Không xác minh được CMS/PKCS#7: {error}")
                    try:
                        certificates.append(self._certificate_info(signature))
                    except Exception:  # noqa: BLE001 - certificate metadata is diagnostic only
                        certificates.append({})
                cryptographic_integrity = bool(integrity_results) and all(integrity_results)
                result_status = (
                    SignatureStatus.SIGNED_VALID if cryptographic_integrity else SignatureStatus.SIGNED_INVALID
                )
                return SignatureResult(
                    result_status,
                    signature_count=len(signatures),
                    cryptographic_integrity=cryptographic_integrity,
                    trust_verified=bool(trust_results) and all(trust_results),
                    certificates=certificates,
                    message=" | ".join(messages),
                    signature_present=True,
                    certificate_time_validity=None,
                    document_modified_after_signing=any(modification_results),
                )
        except PermissionError as error:
            return SignatureResult(
                SignatureStatus.SIGNATURE_ERROR,
                message=str(error),
                file_access_error=True,
            )
        except Exception as error:  # noqa: BLE001 - corrupt PDFs can raise several parser/crypto errors
            return SignatureResult(
                SignatureStatus.SIGNATURE_ERROR,
                message=f"Không đọc được cấu trúc PDF: {error}",
                invalid_pdf=True,
            )


class DocumentScanner:
    def __init__(self, signature_validator: SignatureValidator | None = None) -> None:
        self.signature_validator = signature_validator or SignatureValidator()
        self.last_stats: dict[str, int] = {}

    @staticmethod
    def _pdfs(folder: Path) -> Iterable[Path]:
        if not folder.is_dir():
            raise ValueError(f"Thư mục không tồn tại hoặc không thể đọc: {folder}")
        return sorted(
            (
                path
                for path in folder.rglob("*")
                if path.is_file()
                and path.suffix.casefold() == ".pdf"
                and not any(part.upper().startswith("VBDLIS_VALIDATION") for part in path.parts)
            ),
            key=lambda path: str(path).casefold(),
        )

    def scan(
        self,
        tbxn_folder: Path,
        ddk_folder: Path,
        shared_folder: bool,
        progress: Callable[[int, int], None] | None = None,
        validate_signatures: bool = True,
    ) -> list[DocumentRecord]:
        sources = (
            [(tbxn_folder, DocumentType.UNKNOWN)]
            if shared_folder or tbxn_folder.resolve() == ddk_folder.resolve()
            else [(tbxn_folder, DocumentType.TBXN), (ddk_folder, DocumentType.DDK)]
        )
        paths: list[tuple[Path, DocumentType]] = []
        seen: set[Path] = set()
        for folder, hint in sources:
            for path in self._pdfs(folder):
                resolved = path.resolve()
                if resolved not in seen:
                    paths.append((path, hint))
                    seen.add(resolved)
        def scan_stats(folder: Path, prefix: str) -> dict[str, int]:
            pdfs = [path for path, _ in paths if path == folder or folder in path.parents]
            depths = [len(path.relative_to(folder).parts) - 1 for path in pdfs]
            directories = {folder, *(path.parent for path in pdfs)}
            return {
                f"{prefix}_directories_visited": len(directories),
                f"{prefix}_maximum_depth": max(depths, default=0),
                f"{prefix}_pdfs_found": len(pdfs),
            }
        self.last_stats = scan_stats(tbxn_folder, "tbxn") | scan_stats(ddk_folder, "ddk")
        documents: list[DocumentRecord] = []
        total = len(paths)
        for index, (path, hint) in enumerate(paths, 1):
            document = parse_document(path, hint)
            root = tbxn_folder if hint == DocumentType.TBXN else ddk_folder
            if shared_folder:
                root = tbxn_folder
            try:
                document.relative_path = str(path.relative_to(root))
            except ValueError:
                document.relative_path = path.name
            document.parent_folder = path.parent.name
            document.parse_status = "PARSED" if document.sheet_normalized and document.parcel_normalized else "PARSE_ERROR"
            if validate_signatures:
                document.signature = self.signature_validator.validate(path)
            documents.append(document)
            if progress:
                progress(index, total)
        return documents


def best_document_candidates(
    documents: Iterable[DocumentRecord], sheet: str, parcel: str, document_type: DocumentType
) -> list[DocumentRecord]:
    candidates = [document for document in documents if document.document_type == document_type]
    exact_sheet = [document for document in candidates if document.sheet_normalized == sheet]
    exact_parcel = [document for document in candidates if document.parcel_normalized == parcel]
    return (exact_sheet or exact_parcel)[:3]
