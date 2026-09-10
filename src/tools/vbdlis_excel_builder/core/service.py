from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from tools.vbdlis_excel_builder.models import FieldSchema, Household, MappingProfile, Severity, ValidationIssue

from .auto_mapper import AutoMapper
from .diagnostic_logger import DiagnosticContext, DiagnosticFailure, DiagnosticFiles, DiagnosticLogger, explain_failure
from .household_parser import HouseholdParser
from .input_policy import apply_input_policy
from .report_writer import ReportWriter
from .source_reader import SourceColumn, SourceReader
from .template_schema_reader import TemplateSchemaReader
from .transform_engine import TransformEngine
from .validator import Validator
from .workbook_writer import WorkbookWriter


@dataclass(slots=True)
class ProcessResult:
    households: list[Household] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    diagnostic_files: DiagnosticFiles = field(default_factory=DiagnosticFiles)
    diagnostic_context: DiagnosticContext | None = field(default=None, repr=False)

    @property
    def can_export(self) -> bool:
        return bool(self.rows) and not any(issue.severity == Severity.ERROR for issue in self.issues)


class BuilderService:
    def __init__(self, template_path: str | Path, schema_path: str | Path,
                 diagnostics_dir: str | Path | None = None):
        self.template_path = Path(template_path)
        self.schema_path = Path(schema_path)
        self.source_reader = SourceReader()
        self.auto_mapper = AutoMapper()
        self.schema_reader = TemplateSchemaReader(self.schema_path)
        self.household_parser = HouseholdParser()
        self.transform_engine = TransformEngine()
        self.validator = Validator()
        self.writer = WorkbookWriter(self.template_path, self.schema_reader)
        self.report_writer = ReportWriter()
        self.diagnostic_logger = DiagnosticLogger(diagnostics_dir)
        _, _, self.schemas = self.schema_reader.read(self.template_path)

    def source_setup(self, path: str | Path, sheet_name: str | None = None) -> tuple[list[str], str, int, list[SourceColumn], list[dict[str, Any]]]:
        try:
            return self._source_setup(path, sheet_name)
        except Exception as exc:
            raise self.failure(exc, DiagnosticContext(str(path), sheet_name or ""), "Đọc file nguồn") from exc

    def _source_setup(self, path: str | Path, sheet_name: str | None = None):
        sheets = self.source_reader.sheet_names(path)
        if not sheets:
            raise ValueError("Workbook nguồn không có sheet.")
        selected = sheet_name if sheet_name in sheets else sheets[0]
        header_row = self.source_reader.detect_header_row(path, selected)
        headers, preview = self.source_reader.preview(path, selected, header_row, 50)
        return sheets, selected, header_row, headers, preview

    def process(
        self,
        source_path: str | Path,
        sheet_name: str,
        header_row: int,
        profile: MappingProfile,
        header_row_2: int | None = None,
        progress: Callable[[int, str], None] | None = None,
    ) -> ProcessResult:
        notify = progress or (lambda _value, _message: None)
        context = DiagnosticContext(str(Path(source_path).resolve()), sheet_name, header_row,
                                    deepcopy(profile), schemas=self.schemas)
        issues: list[ValidationIssue] = []
        stats: dict[str, Any] = {}
        stage = "Kiểm tra cấu hình"
        try:
            notify(5, stage)
            issues = self.validator.validate_profile(profile)
            stage = "Đọc dữ liệu nguồn"
            notify(10, stage)
            context.columns = self.source_reader.headers(source_path, sheet_name, header_row, header_row_2)
            household_column = profile.source_mapping.get("household_stt", "")
            context.source_rows = self.source_reader.read_rows(
                source_path,
                sheet_name,
                header_row,
                header_row_2=header_row_2,
                formula_presence_columns={household_column} if household_column else None,
            )
            stage = "Nhận diện hộ, người và thửa"
            notify(30, stage)
            households, parse_issues, base_stats = self.household_parser.parse(context.source_rows, profile)
            context.households = households
            households, parse_issues, policy_stats = apply_input_policy(households, parse_issues, profile)
            issues.extend(parse_issues)
            stats.update(base_stats)
            stats.update(policy_stats)
            stage = "Tạo dữ liệu kết quả theo quy tắc"
            notify(45, stage)
            transformed, transform_issues, transform_stats = self.transform_engine.transform(households, self.schemas, profile)
            context.output_rows = transformed
            issues.extend(transform_issues)
            stats.update(transform_stats)
            stage = "Kiểm tra các trường kết quả"
            notify(60, stage)
            issues.extend(self.validator.validate_output(transformed, self.schemas, profile))
            if not transformed:
                issues.append(ValidationIssue(Severity.ERROR, "NO_OUTPUT_ROWS", "Chưa có người và thửa đủ điều kiện để tạo dòng kết quả."))
        except Exception as exc:
            raise self.failure(exc, context, stage, issues, stats) from exc
        stats["errors"] = sum(issue.severity == Severity.ERROR for issue in issues)
        stats["warnings"] = sum(issue.severity == Severity.WARNING for issue in issues)
        stats["info"] = sum(issue.severity == Severity.INFO for issue in issues)
        notify(65, "Đã xử lý và kiểm tra dữ liệu")
        logging.info(
            "Processed source=%s sheet=%s profile=%s stats=%s",
            source_path,
            sheet_name,
            profile.profile_name,
            stats,
        )
        files = self.diagnostic_logger.write(context, issues, stats)
        if files.error:
            logging.error("Diagnostic report write failed: %s", files.error)
        return ProcessResult(households, transformed, issues, stats, files, context)

    def failure(self, exc: Exception, context: DiagnosticContext, stage: str,
                issues: list[ValidationIssue] | None = None, stats: dict[str, Any] | None = None) -> DiagnosticFailure:
        if isinstance(exc, DiagnosticFailure):
            return exc
        logging.error("Operation failed: %s", stage, exc_info=(type(exc), exc, exc.__traceback__))
        files = self.diagnostic_logger.write(context, issues or [], stats or {}, fatal=exc, stage=stage)
        reason, action = explain_failure(exc)
        return DiagnosticFailure(f"{stage}: {reason}\n{action}", files)

    def export(
        self,
        result: ProcessResult,
        profile: MappingProfile,
        output_folder: str | Path,
        output_filename: str,
        progress: Callable[[int, str], None] | None = None,
    ) -> tuple[Path, Path | None, dict[str, Any]]:
        context = result.diagnostic_context or DiagnosticContext(profile=deepcopy(profile), schemas=self.schemas,
                                                                 households=result.households, output_rows=result.rows)
        try:
            exported = self._export(result, profile, output_folder, output_filename, progress)
        except Exception as exc:
            failure = self.failure(exc, context, "Xuất file VBDLIS", result.issues, result.stats)
            result.diagnostic_files = failure.diagnostic_files
            raise failure from exc
        result.diagnostic_files = self.diagnostic_logger.write(
            context, result.issues, result.stats, stage="Xuất file VBDLIS",
            exported_paths=[str(p) for p in exported[:2] if p is not None])
        return exported

    def _export(self, result: ProcessResult, profile: MappingProfile, output_folder: str | Path,
                output_filename: str,
                progress: Callable[[int, str], None] | None = None) -> tuple[Path, Path | None, dict[str, Any]]:
        notify = progress or (lambda _value, _message: None)
        if not result.can_export:
            raise ValueError("Dữ liệu còn lỗi hoặc chưa có dòng kết quả; chưa thể xuất.")
        output_path, verification = self.writer.write(
            result.rows,
            self.schemas,
            profile,
            output_folder,
            output_filename,
            progress=progress,
        )
        if not verification.get("pass"):
            raise RuntimeError(f"Kiểm tra sau khi lưu không đạt: {verification}")
        report_path = None
        if profile.export_audit_report:
            notify(98, "Đang tạo báo cáo kiểm tra")
            report_path = output_path.with_name(f"{output_path.stem}_bao_cao_kiem_tra.xlsx")
            self.report_writer.write(
                report_path,
                {**result.stats, **{f"verify_{k}": v for k, v in verification.items()}},
                result.households,
                result.issues,
                self.schemas,
                result.rows,
                diagnostic_context=result.diagnostic_context,
            )
        logging.info("Exported output=%s report=%s", output_path, report_path)
        notify(100, "Đã tạo xong file VBDLIS")
        return output_path, report_path, verification
