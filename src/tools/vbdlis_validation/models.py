from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class DocumentType(str, Enum):
    TBXN = "TBXN"
    DDK = "DDK"
    UNKNOWN = "UNKNOWN"


class SignatureStatus(str, Enum):
    SIGNED_VALID = "SIGNED_VALID"
    SIGNED_INVALID = "SIGNED_INVALID"
    UNSIGNED = "UNSIGNED"
    SIGNATURE_ERROR = "SIGNATURE_ERROR"


class ValidationMode(str, Enum):
    FULL_SOURCE_COMPARE = "FULL_SOURCE_COMPARE"
    VBDLIS_ONLY = "VBDLIS_ONLY"


class DocumentCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    MISSING_TBXN = "MISSING_TBXN"
    MISSING_DDK = "MISSING_DDK"
    MISSING_BOTH = "MISSING_BOTH"
    AMBIGUOUS_DOCUMENT = "AMBIGUOUS_DOCUMENT"
    DUPLICATE_DOCUMENT = "DUPLICATE_DOCUMENT"
    INVALID_DOCUMENT = "INVALID_DOCUMENT"


class SignatureReadiness(str, Enum):
    SIGNED_READY = "SIGNED_READY"
    TBXN_UNSIGNED = "TBXN_UNSIGNED"
    DDK_UNSIGNED = "DDK_UNSIGNED"
    BOTH_UNSIGNED = "BOTH_UNSIGNED"
    TBXN_SIGNATURE_INVALID = "TBXN_SIGNATURE_INVALID"
    DDK_SIGNATURE_INVALID = "DDK_SIGNATURE_INVALID"
    BOTH_SIGNATURE_INVALID = "BOTH_SIGNATURE_INVALID"
    SIGNATURE_CHECK_ERROR = "SIGNATURE_CHECK_ERROR"
    NOT_CHECKED = "NOT_CHECKED"


class WorkflowStatus(str, Enum):
    READY_TO_UPLOAD = "READY_TO_UPLOAD"
    NEED_SIGNATURE = "NEED_SIGNATURE"
    MISSING_DOCUMENT = "MISSING_DOCUMENT"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    DATA_ERROR = "DATA_ERROR"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(slots=True)
class SignatureResult:
    status: SignatureStatus
    signature_count: int = 0
    cryptographic_integrity: bool = False
    trust_verified: bool = False
    certificates: list[dict[str, str]] = field(default_factory=list)
    message: str = ""
    invalid_pdf: bool = False
    file_access_error: bool = False
    signature_present: bool = False
    certificate_time_validity: bool | None = None
    document_modified_after_signing: bool | None = None


@dataclass(slots=True)
class DocumentRecord:
    path: Path
    document_type: DocumentType
    owner_raw: str = ""
    owner_normalized: str = ""
    sheet_raw: str = ""
    sheet_normalized: str = ""
    parcel_raw: str = ""
    parcel_normalized: str = ""
    parse_confidence: float = 0.0
    signature: SignatureResult | None = None
    relative_path: str = ""
    parent_folder: str = ""
    parse_status: str = "PARSED"
    match_status: str = "UNMATCHED"
    matched_parcels: list[str] = field(default_factory=list)
    match_method: str = "NONE"

    @property
    def index_key(self) -> tuple[str, str, DocumentType]:
        return self.sheet_normalized, self.parcel_normalized, self.document_type


@dataclass(slots=True)
class UploadRow:
    row_number: int
    person_raw: str
    person_normalized: str
    role: str
    sheet_raw: str
    sheet_normalized: str
    parcel_raw: str
    parcel_normalized: str
    household_id: str = ""
    tbxn_reference: str = ""
    ddk_reference: str = ""
    combined_reference: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParcelRecord:
    owner_raw: str
    owner_normalized: str
    sheet_raw: str
    sheet_normalized: str
    parcel_raw: str
    parcel_normalized: str
    household_id: str = ""
    source_rows: list[int] = field(default_factory=list)
    upload_rows: list[UploadRow] = field(default_factory=list)
    tbxn_documents: list[DocumentRecord] = field(default_factory=list)
    ddk_documents: list[DocumentRecord] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    suggested_match: str = ""
    confidence: float = 1.0
    matching_rule: str = ""
    match_evidence: str = ""
    document_completeness: DocumentCompleteness = DocumentCompleteness.MISSING_BOTH
    signature_readiness: SignatureReadiness = SignatureReadiness.NOT_CHECKED
    workflow_status: WorkflowStatus = WorkflowStatus.REVIEW_REQUIRED
    ax_raw: str = ""
    ax_status: str = "NOT_CHECKED"

    @property
    def key(self) -> tuple[str, str, str]:
        return self.owner_normalized, self.sheet_normalized, self.parcel_normalized

    @property
    def valid(self) -> bool:
        return self.workflow_status == WorkflowStatus.READY_TO_UPLOAD


@dataclass(slots=True)
class ExcelConfig:
    path: Path
    sheet: str
    header_row: int
    columns: dict[str, str]
    header_row_2: int | None = None


@dataclass(slots=True)
class RunConfig:
    upload: ExcelConfig
    source: ExcelConfig | None
    tbxn_folder: Path
    ddk_folder: Path
    output_root: Path
    export_start: str = "A"
    export_end: str = "AZ"
    shared_document_folder: bool = False
    validation_mode: ValidationMode = ValidationMode.FULL_SOURCE_COMPARE
    separate_unsigned: bool = False


@dataclass(slots=True)
class ValidationResult:
    records: list[ParcelRecord]
    total_upload_rows: int
    total_source_rows: int
    output_folder: Path | None = None
    valid_excel: Path | None = None
    invalid_excel: Path | None = None
    summary_excel: Path | None = None
    log_file: Path | None = None
    documents: list[DocumentRecord] = field(default_factory=list)
    validation_mode: ValidationMode = ValidationMode.FULL_SOURCE_COMPARE
    scan_stats: dict[str, int] = field(default_factory=dict)
    ready_excel: Path | None = None
    need_signature_excel: Path | None = None
    document_complete_excel: Path | None = None
    document_actions: Path | None = None

    @property
    def stats(self) -> dict[str, int | float]:
        source_records = [record for record in self.records if record.source_rows]
        ready = [record for record in self.records if record.workflow_status == WorkflowStatus.READY_TO_UPLOAD]
        households = {record.owner_normalized for record in self.records if record.owner_normalized}
        counts: dict[str, int | float] = {
            "total_households": len(households),
            "total_source_parcels": len(source_records),
            "total_parcels": len(self.records),
            "total_vbdlis_rows": self.total_upload_rows,
            "total_matched_parcels": sum(bool(record.source_rows and record.upload_rows) for record in self.records),
            "total_valid_parcels": len(ready),
            "total_invalid_parcels": len(self.records) - len(ready),
            "document_complete_parcels": sum(record.document_completeness == DocumentCompleteness.COMPLETE for record in self.records),
        }
        counts.update({status.value.lower(): sum(record.workflow_status == status for record in self.records) for status in WorkflowStatus})
        tracked = (
            "MISSING_TBXN", "MISSING_DDK", "MISSING_BOTH", "TBXN_UNSIGNED", "DDK_UNSIGNED",
            "BOTH_UNSIGNED", "TBXN_SIGNATURE_INVALID", "DDK_SIGNATURE_INVALID",
            "BOTH_SIGNATURE_INVALID", "SIGNATURE_CHECK_ERROR", "AMBIGUOUS_MATCH", "DATA_MISMATCH",
            "DUPLICATE_TBXN", "DUPLICATE_DDK", "SOURCE_PARCEL_NOT_FOUND", "VBDLIS_PARCEL_NOT_FOUND",
            "SOURCE_ONLY", "VBDLIS_ONLY", "PARCEL_MISMATCH", "HOUSEHOLD_NOT_FOUND",
            "REVIEW_REQUIRED", "INVALID_PDF", "FILE_ACCESS_ERROR", "MISSING_ROLE",
        )
        counts.update({issue.lower(): sum(issue in record.issues for record in self.records) for issue in tracked})
        counts["orphan_tbxn"] = sum(d.document_type == DocumentType.TBXN and d.match_status == "ORPHAN" for d in self.documents)
        counts["orphan_ddk"] = sum(d.document_type == DocumentType.DDK and d.match_status == "ORPHAN" for d in self.documents)
        counts["invalid_pdfs"] = sum(bool(d.signature and d.signature.invalid_pdf) for d in self.documents)
        counts["ax_match"] = sum(r.ax_status == "MATCH" for r in self.records)
        counts["ax_mismatch"] = sum(r.ax_status == "MISMATCH" for r in self.records)
        counts["ax_blank"] = sum(r.ax_status == "EMPTY" for r in self.records)
        counts["ax_parse_error"] = sum(r.ax_status == "PARSE_ERROR" for r in self.records)
        total = len(self.records)
        counts["valid_percentage"] = round(len(ready) * 100 / total, 2) if total else 0.0
        counts["error_percentage"] = round((total - len(ready)) * 100 / total, 2) if total else 0.0
        return counts
