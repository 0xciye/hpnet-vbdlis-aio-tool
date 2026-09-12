"""Local, complete, plain-language diagnostics, independent of Excel export."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import BadZipFile

from tools.vbdlis_excel_builder.models import FieldSchema, Household, MappingProfile, Severity, ValidationIssue
from tools.vbdlis_excel_builder.utils.paths import app_data_dir
from tools.vbdlis_excel_builder.utils.text import is_blank


LABELS = {
    "household_stt": "STT hộ", "person_name": "Họ và tên", "cccd": "CCCD",
    "birth_date": "Ngày sinh", "gender": "Giới tính", "sheet_number": "Số tờ",
    "parcel_number": "Số thửa", "area": "Diện tích", "land_location": "Xứ đồng",
    "land_type": "Loại đất", "land_origin": "Nguồn gốc sử dụng",
    "use_form": "Hình thức sử dụng", "use_term": "Thời hạn sử dụng",
    "gcn_issue_number": "Số phát hành giấy chứng nhận",
    "gcn_issue_date": "Ngày cấp giấy chứng nhận", "gcn_registry_number": "Số vào sổ",
    "gcn_type": "Loại giấy chứng nhận", "gcn_authority": "Cơ quan cấp giấy chứng nhận",
}
PARCEL_FIELDS = ("sheet_number", "parcel_number", "area")
CONFIG_LABELS = {
    "commune_code": "Tab 3 → Mã xã", "address": "Tab 3 → Địa chỉ",
    "entity_type": "Tab 3 → Loại đối tượng", "role": "Tab 3 → Vai trò chủ hộ/thành viên",
    "document_type": "Tab 3 → Loại tài liệu", "dossier_name": "Tab 3 → Quy tắc Mục 2",
    "dossier_or_gcn_issue_number": "Tab 3 → Quy tắc Mục 2 / Tab 2 → Số phát hành giấy chứng nhận",
    "document_files": "Tab 3 → Quy tắc Mục 49", "output_stt": "STT kết quả do ứng dụng tạo",
}
# Title, effect, concrete action. Internal codes are retained only as support references.
GUIDANCE = {
    "MISSING_PERSON_NAME": ("Có thông tin cá nhân nhưng thiếu họ tên", "Chưa xác định được người tại dòng này.", "Đối chiếu giấy tờ và bổ sung họ tên ở ô được chỉ ra; kiểm tra cột Họ và tên tại Tab 2."),
    "HOUSEHOLD_SKIPPED": ("ĐÃ BỎ QUA TOÀN BỘ HỘ", "Không xuất bất kỳ người/thửa nào của hộ này.", "Đối chiếu các dòng và ô bên dưới, bổ sung dữ liệu còn thiếu. Sau khi sửa, chạy lại để đưa hộ vào kết quả."),
    "PERSON_SKIPPED": ("ĐÃ BỎ QUA NGƯỜI CÓ CCCD SAI", "Không xuất người này; những người hợp lệ khác của hộ vẫn được giữ.", "Sửa CCCD theo giấy tờ, bảo đảm đúng 12 chữ số, sau đó chạy lại để đưa người này vào kết quả."),
    "HOUSEHOLD_HEAD_SKIPPED": ("Cần kiểm tra vai trò sau khi bỏ chủ hộ", "Những người còn lại vẫn giữ vai trò ban đầu; ứng dụng không tự chỉ định chủ hộ mới.", "Đối chiếu chủ hộ thực tế và CCCD, sửa nguồn rồi chạy lại trước khi sử dụng kết quả."),
    "MISSING_CCCD": ("Chưa điền CCCD", "Chưa thể xuất file; người này vẫn được giữ lại.", "Mở ô CCCD được chỉ ra, đối chiếu giấy tờ và bổ sung số đúng. Không điền số giả hoặc xóa người để hết lỗi."),
    "INVALID_CCCD": ("CCCD chưa đúng 12 chữ số", "Giữ giá trị hiện có và cảnh báo; giới tính có thể để trống.", "Đối chiếu giấy tờ. Định dạng ô là Văn bản để giữ số 0 đầu; không tự thêm số nếu chưa xác minh."),
    "CCCD_BLOCKING": ("Cấu hình yêu cầu dừng vì CCCD chưa chuẩn", "Chưa thể xuất file.", "Kiểm tra và sửa CCCD theo giấy tờ tại ô được chỉ ra."),
    "MISSING_REQUIRED_CCCD_OUTPUT": ("CCCD chưa được điền vào kết quả", "Chưa thể xuất file.", "Kiểm tra CCCD nguồn ở Tab 2 và quy tắc CCCD tại Tab 4; không để chế độ Để trống."),
    "INVALID_PARCEL": ("Không tạo được thửa vì thiếu dữ liệu", "Dòng này không tạo thửa; các thửa khác của hộ vẫn được xử lý.", "Bổ sung đủ Số tờ, Số thửa và Diện tích trên cùng dòng. Nếu Excel đã có số, kiểm tra lại cột đã chọn tại Tab 2."),
    "INVALID_PARCEL_IDENTIFIER": ("Số tờ hoặc Số thửa không phải số nguyên dương", "Dòng này không tạo thửa; dữ liệu có chữ cái, số 0, số âm hoặc số lẻ bị từ chối.", "Đối chiếu hồ sơ địa chính và sửa Số tờ/Số thửa thành số nguyên dương đúng; không tự đổi mã chữ nếu chưa xác minh."),
    "HOUSEHOLD_WITHOUT_PARCEL": ("Hộ chưa có thửa để tạo kết quả", "Không sinh dòng kết quả cho những người trong hộ này.", "Kiểm tra các ô tờ/thửa/diện tích của hộ bên dưới. Nếu hộ có đất, bổ sung dữ liệu vào đúng dòng; nếu không có đất, xác nhận việc không xuất hộ này là phù hợp."),
    "HOUSEHOLD_WITHOUT_PERSON": ("Hộ chưa có tên người", "Chưa thể xuất file; không có người để ghép với thửa.", "Bổ sung tên chủ hộ/thành viên và CCCD; kiểm tra cột Họ và tên tại Tab 2."),
    "ROW_WITHOUT_HOUSEHOLD": ("Dòng chưa thuộc hộ nào", "Dòng này chưa được đưa vào hộ nên không tạo người/thửa.", "Kiểm tra Dòng tiêu đề tại Tab 1. Nếu là dữ liệu thật, điền STT ở dòng bắt đầu hộ; nếu là tiêu đề phụ, chọn hàng tiêu đề cuối cùng."),
    "SUMMARY_ROW_SKIPPED": ("Đã bỏ qua dòng tổng hợp", "Không tạo người hoặc thửa từ dòng tổng; đây không phải lỗi.", "Không cần sửa nếu đây là Tổng DT/Tổng cộng. Không dùng số tổng thay cho diện tích từng thửa."),
    "DUPLICATE_PARCEL_REMOVED": ("Đã bỏ một dòng thửa trùng hoàn toàn", "Giữ một thửa trong cùng hộ, không nhân đôi kết quả.", "Đối chiếu tờ/thửa, diện tích, vị trí và giấy chứng nhận; không cần sửa nếu dòng thực sự trùng."),
    "DUPLICATE_PERSON_ROW_MERGED": ("Một người lặp lại ở nhiều dòng thửa", "Chỉ giữ một người trong hộ nhưng vẫn giữ đủ các thửa; đây không phải lỗi.", "Không cần sửa nếu nguồn cố ý lặp tên người cho từng thửa; hãy kiểm tra CCCD nếu đây là hai người khác nhau trùng tên."),
    "GCN_CONFLICT": ("Cùng tờ/thửa có thông tin giấy chứng nhận khác nhau", "Chưa thể xuất; ứng dụng không tự chọn bộ thông tin nào.", "So sánh các dòng thửa được liệt kê và xác minh giấy chứng nhận đúng trước khi sửa nguồn."),
    "EXPECTED_GCN_MISSING": ("Thửa chưa có thông tin giấy chứng nhận", "Vẫn tạo thửa nhưng cần kiểm tra chế độ giấy chứng nhận.", "Nếu thửa đã có giấy, bổ sung thông tin và ánh xạ cột ở Tab 2; nếu chưa có, chọn chế độ phù hợp tại Tab 3."),
    "MISSING_LOCATION": ("Xứ đồng đang trống", "Thửa vẫn được tạo, nhưng vị trí trong kết quả đang thiếu.", "Điền Xứ đồng tại ô nguồn hoặc cấu hình giá trị thay thế tại Tab 3; chỉ dùng địa chỉ đã xác minh phù hợp với thửa đất."),
    "LOCATION_FALLBACK": ("Đã dùng địa chỉ thay cho Xứ đồng trống", "Thửa vẫn được tạo với giá trị thay thế ghi bên dưới.", "Kiểm tra giá trị thay thế có đúng với vị trí thửa đất không."),
    "MISSING_MAPPING": ("Chưa chọn cột dữ liệu bắt buộc", "Chưa thể xuất file.", "Mở Tab 2, chọn đúng chữ cột trong Excel cho trường được chỉ ra."),
    "MISSING_COMMUNE_CODE": ("Chưa nhập mã xã", "Chưa thể xuất file; lỗi này có thể kéo theo nhiều ô kết quả trống.", "Mở Tab 3 → Mã xã, nhập mã được đơn vị xác nhận rồi bấm Kiểm tra lại."),
    "ROLE_RULE_CHANGED": ("Giá trị vai trò đã thay đổi", "Có thể làm kết quả khác quy tắc mặc định.", "Kiểm tra Tab 3; mặc định là Chủ hộ và Thành viên hộ gia đình."),
    "INVALID_TEMPLATE_RULE": ("Quy tắc đặt tên tài liệu chưa đúng", "Chưa thể hoàn thành việc tạo kết quả.", "Kiểm tra quy tắc Mục 2/Mục 49 ở Tab 3 và các tên biến được cho phép trong hướng dẫn."),
    "MISSING_REQUIRED_OUTPUT": ("Một trường bắt buộc trong kết quả đang trống", "Chưa thể xuất file. Đây có thể là lỗi phát sinh từ một cấu hình hoặc ô nguồn đã báo ở trên.", "Kiểm tra vị trí nguồn/cấu hình được chỉ ra và quy tắc trường này tại Tab 4; sửa nguyên nhân rồi chạy Kiểm tra lại."),
    "INVALID_ROLE": ("Vai trò trong kết quả chưa đúng", "Chưa thể xuất file.", "Kiểm tra giá trị vai trò tại Tab 3 và quy tắc tại Tab 4; dùng Chủ hộ/Thành viên hộ gia đình nếu không có yêu cầu khác."),
    "INVALID_ITEM_49": ("Danh sách tài liệu ở Mục 49 chưa đúng", "Chưa thể xuất file.", "Kiểm tra Tab 3 → Mục 49 và quy tắc Tab 4; cần hai tên tài liệu kết thúc bằng -TBXN.pdf và -DDK.pdf, ngăn cách bằng dấu phẩy và khoảng trắng."),
    "INVALID_OUTPUT_STT": ("STT kết quả không liên tục", "Chưa thể xuất file.", "Khôi phục chế độ Tự động tính cho STT ở Tab 4 và chạy lại; nếu vẫn lỗi, gửi báo cáo này cho người hỗ trợ."),
    "PERSON_PARCEL_PRODUCT_MISMATCH": ("Số dòng kết quả không khớp số người × số thửa", "Chưa thể xuất file.", "Giữ nguyên file nguồn, gửi báo cáo này cho người hỗ trợ kiểm tra ứng dụng."),
    "NO_OUTPUT_ROWS": ("Chưa có dòng kết quả nào", "Không thể tạo file VBDLIS trống.", "Kiểm tra các cảnh báo về hộ, người, thửa, dòng tiêu đề và ánh xạ cột bên dưới."),
}


@dataclass
class DiagnosticContext:
    source_path: str = ""
    sheet_name: str = ""
    header_row: int = 0
    profile: MappingProfile = field(default_factory=MappingProfile)
    columns: list[Any] = field(default_factory=list)
    source_rows: list[dict[str, Any]] = field(default_factory=list)
    households: list[Household] = field(default_factory=list)
    schemas: list[FieldSchema] = field(default_factory=list)
    output_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DiagnosticEntry:
    severity: str
    code: str
    title: str
    location: str
    subject: str
    reason: str
    effect: str
    action: str
    evidence: list[str] = field(default_factory=list)
    source_issue: ValidationIssue | None = field(default=None, repr=False)


@dataclass
class DiagnosticFiles:
    paths: list[Path] = field(default_factory=list)
    error: str = ""


class DiagnosticFailure(RuntimeError):
    def __init__(self, message: str, files: DiagnosticFiles):
        self.diagnostic_files = files
        detail = f"\nBáo cáo chi tiết: {files.paths[0]}" if files.paths else ""
        if files.error:
            detail += f"\n{files.error}"
        super().__init__(message + detail)


def display_value(value: Any) -> str:
    if is_blank(value):
        return "[ĐỂ TRỐNG]"
    text = str(value)
    return text if text == text.strip() else repr(text) + " (có khoảng trắng đầu/cuối)"


def plain_message(message: str) -> str:
    for original, replacement in (("output", "kết quả"), ("fallback", "giá trị thay thế"),
                                  ("field", "trường"), ("rule", "quy tắc")):
        message = message.replace(original, replacement)
    return message


class DiagnosticLogger:
    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory).resolve() if directory is not None else None

    @staticmethod
    def entries(context: DiagnosticContext, issues: list[ValidationIssue]) -> list[DiagnosticEntry]:
        raw_by_row = {int(row.get("_row", 0)): row for row in context.source_rows}
        schema_by_column = {s.column: s for s in context.schemas}
        skipped = {i.source_row for i in issues if i.code == "SUMMARY_ROW_SKIPPED"}
        household_positions = {h.source_row: pos for pos, h in enumerate(context.households)}

        def cell_evidence(token: str, number: int, label: str) -> str:
            if not token:
                return f"{label}: chưa chọn cột nguồn tại Tab 2."
            exact = [c.letter for c in context.columns if c.letter == token]
            aliases = [c.letter for c in context.columns if c.header == token]
            # SourceReader resolves a duplicate header to its last occurrence.
            letter = (exact or aliases)[-1] if (exact or aliases) else ""
            row = raw_by_row.get(number)
            if row is None:
                return f"{label}: dòng {number}, cột {token}; chưa đọc được giá trị nguồn."
            address = f"Ô {letter}{number}" if letter else f"dòng {number}, cột '{token}' (chưa xác định chữ cột)"
            return f"{address} — {label}: {display_value(row.get(token))}"

        records = []
        for issue in issues:
            title, effect, action = GUIDANCE.get(issue.code, (
                "Có vấn đề cần kiểm tra", "Xem nội dung chi tiết trước khi tiếp tục.",
                "Kiểm tra dòng và cấu hình được chỉ ra; nếu chưa rõ, gửi báo cáo này cho người hỗ trợ.",
            ))
            numbers = [issue.source_row] if issue.source_row else []
            fields = list(issue.source_fields)
            location = f"Trang tính: {context.sheet_name or '[chưa chọn]'}"
            subject = f"Hộ STT: {issue.household or '[không xác định]'}"
            if issue.person:
                subject += f"; người: {issue.person}"
            evidence = []
            if issue.disposition == "household_skipped":
                effect = "Hộ này đã bị bỏ toàn bộ theo cấu hình; không xuất người/thửa của hộ. Đây là lý do cần đối chiếu, không chặn những hộ còn lại."
            elif issue.disposition == "person_skipped":
                effect = "Người có CCCD sai đã bị bỏ theo cấu hình; không xuất người này. Những người còn lại giữ vai trò ban đầu."
            elif issue.disposition == "row_skipped":
                effect = "Dòng này chưa thuộc hộ nào nên đã bỏ qua; kiểm tra dòng tiêu đề hoặc STT hộ để tránh bỏ sót dữ liệu thật."
            if issue.code in {"MISSING_CCCD", "INVALID_CCCD", "CCCD_BLOCKING"}:
                fields = ["cccd"]
            elif issue.code in {"INVALID_PARCEL", "INVALID_PARCEL_IDENTIFIER", "HOUSEHOLD_WITHOUT_PARCEL", "DUPLICATE_PARCEL_REMOVED"}:
                fields = list(PARCEL_FIELDS)
            elif issue.code == "DUPLICATE_PERSON_ROW_MERGED":
                fields = ["person_name", "cccd", "sheet_number", "parcel_number"]
            elif issue.code in {"MISSING_LOCATION", "LOCATION_FALLBACK"}:
                fields = ["land_location", "sheet_number", "parcel_number"]
            elif issue.code == "HOUSEHOLD_WITHOUT_PERSON":
                fields = ["household_stt", "person_name"]
            elif issue.code == "ROW_WITHOUT_HOUSEHOLD":
                fields = ["household_stt", "person_name"]
            elif issue.code == "SUMMARY_ROW_SKIPPED":
                fields = ["household_stt", "person_name"]
            elif issue.code in {"GCN_CONFLICT", "EXPECTED_GCN_MISSING"}:
                fields = list(PARCEL_FIELDS) + [k for k in context.profile.source_mapping if k.startswith("gcn_")]
                if issue.code == "GCN_CONFLICT":
                    household = next((h for h in context.households if h.source_row == issue.source_row), None)
                    if household:
                        numbers = [p.source_row for p in household.parcels if f"{p.sheet_number}/{p.parcel_number}" == issue.value]
            if issue.code.startswith("HOUSEHOLD_WITHOUT_") or issue.code == "HOUSEHOLD_SKIPPED":
                pos = household_positions.get(issue.source_row)
                if pos is not None:
                    h = context.households[pos]
                    end = context.households[pos + 1].source_row if pos + 1 < len(context.households) else float("inf")
                    numbers = [n for n in raw_by_row if h.source_row <= n < end and n not in skipped]
                    subject += f"; {len(h.people)} người; {len(h.parcels)} thửa trong nguồn"
                    if h.people:
                        evidence.append("Người trong hộ: " + "; ".join(f"{p.name} (dòng {p.source_row})" for p in h.people))
            if issue.output_row:
                location += f"; STT kết quả dự kiến: {issue.output_row}, cột {issue.output_column} (không phải số dòng Excel nguồn)"
                output = context.output_rows[issue.output_row - 1] if issue.output_row <= len(context.output_rows) else {}
                meta = output.get("_meta", {})
                if meta.get("parcel"):
                    subject += f"; tờ/thửa: {meta['parcel']}"
                schema = schema_by_column.get(issue.output_column)
                if schema:
                    evidence.append(f"Trường kết quả: Mục {schema.item or schema.column} — {schema.name}")
                    rule = context.profile.field_rules.get(schema.field_id) or schema.to_dict()
                    mode = rule.get("mode", "")
                    source = rule.get("source", "") if mode in {"source_column", "conditional"} else rule.get("transformer", "")
                    source = {"identity_copy": "cccd", "area_copy": "area"}.get(source, source)
                    if mode in {"fixed", "blank", "keep_template"}:
                        fields = []
                        location += f"; cần kiểm tra Tab 4 → Mục {schema.item or schema.column}"
                    elif source in CONFIG_LABELS:
                        fields = []
                        location += "; cần kiểm tra " + CONFIG_LABELS[source]
                    elif source:
                        fields = [source]
                        is_parcel = source in (*PARCEL_FIELDS, "land_location") or source.startswith("gcn_")
                        numbers = [meta.get("parcel_source_row" if is_parcel else "person_source_row", issue.source_row)]
            if issue.code == "MISSING_MAPPING":
                location = "Tab 2 → " + ", ".join(LABELS.get(f, f) for f in fields)
            elif issue.code == "MISSING_COMMUNE_CODE":
                location = "Tab 3 → Mã xã (đang để trống)"
            elif issue.code in {"INVALID_TEMPLATE_RULE", "ROLE_RULE_CHANGED", "INVALID_ROLE", "INVALID_ITEM_49"}:
                location += "; kiểm tra cấu hình Tab 3 và quy tắc Tab 4"
            if numbers:
                location += "; dòng nguồn: " + ", ".join(map(str, numbers))
            for number in numbers:
                for key in fields:
                    token = context.profile.source_mapping.get(key, "") if key in LABELS else key
                    evidence.append(cell_evidence(token, number, LABELS.get(key, key)))
            if not is_blank(issue.value):
                evidence.append("Giá trị được ghi nhận: " + display_value(issue.value))
            records.append(DiagnosticEntry(issue.severity.value, issue.code, title, location, subject,
                                           plain_message(issue.message), effect, action, evidence, issue))
        # Configuration/input errors before their downstream output errors; retain every occurrence.
        return sorted(records, key=lambda r: ({"ERROR": 0, "WARNING": 1, "INFO": 2}[r.severity],
                                              r.code in {"MISSING_REQUIRED_OUTPUT", "MISSING_REQUIRED_CCCD_OUTPUT"}))

    def write(self, context: DiagnosticContext, issues: list[ValidationIssue], stats: dict[str, Any],
              *, fatal: Exception | None = None, stage: str = "Kiểm tra dữ liệu",
              exported_paths: list[str] | None = None) -> DiagnosticFiles:
        files = DiagnosticFiles()
        try:
            directory = self.directory if self.directory is not None else app_data_dir() / "logs" / "kiem_tra"
            directory.mkdir(parents=True, exist_ok=True)
            now = datetime.now().astimezone()
            stem = f"Kiem_tra_{now:%Y%m%d_%H%M%S_%f}_{uuid4().hex[:8]}"
            records = self.entries(context, issues)
            if fatal is not None:
                reason, action = explain_failure(fatal)
                records.insert(0, DiagnosticEntry("ERROR", "OPERATION_FAILED", "Không hoàn thành: " + stage,
                               f"File: {context.source_path or '[chưa chọn]'}; trang tính: {context.sheet_name or '[chưa xác định]'}",
                               "Lỗi thao tác, không phải kết luận dữ liệu của một người bị sai.", reason,
                               "Thao tác chưa hoàn tất. Nếu đã có file kết quả, chưa dùng file đó trước khi kiểm tra lại.",
                               action, ["Thông tin dành cho người hỗ trợ: " + type(fatal).__name__ + ": " + str(fatal)]))
            counts = {severity: sum(r.severity == severity for r in records) for severity in ("ERROR", "WARNING", "INFO")}
            blocked = fatal is not None or counts["ERROR"] > 0 or not stats.get("output_rows")
            metadata = [
                "BÁO CÁO KIỂM TRA DỮ LIỆU — VBDLIS EXCEL BUILDER",
                f"Thời gian: {now:%d/%m/%Y %H:%M:%S %z}", f"Công việc: {stage}",
                f"File nguồn: {context.source_path or '[chưa chọn]'}", f"Trang tính: {context.sheet_name or '[chưa xác định]'}",
                f"Dòng tiêu đề: {context.header_row}; bắt đầu đọc từ dòng: {context.header_row + 1}",
                f"Cấu hình: {context.profile.profile_name}; mã xã: {display_value(context.profile.commune_code)}",
                "Trạng thái: " + ("CHƯA THỂ XUẤT / CHƯA HOÀN TẤT" if blocked else "ĐÃ KIỂM TRA — CÓ THỂ XUẤT; CHƯA PHẢI XÁC NHẬN ĐÃ LƯU FILE"),
                f"Lỗi cần sửa: {counts['ERROR']} | Cảnh báo cần đối chiếu: {counts['WARNING']} | Thông tin xử lý: {counts['INFO']}",
                f"Hộ: {stats.get('households', 0)} | Người: {stats.get('people', 0)} | Thửa đã tạo: {stats.get('parcels', 0)} | Dòng kết quả dự kiến: {stats.get('output_rows', 0)}",
                f"Hộ chưa có thửa: {sum(not h.parcels for h in context.households)} | Dòng thửa thiếu dữ liệu: {sum(i.code == 'INVALID_PARCEL' for i in issues)} | Dòng tổng hợp bỏ qua: {stats.get('summary_rows_skipped', 0)}",
                "Báo cáo giữ đầy đủ mọi lần phát hiện, không cắt bớt lỗi lặp. Một ô nguồn có thể ảnh hưởng nhiều dòng kết quả; số lỗi không phải số người hoặc số thửa.",
                "Cách đọc: sửa LỖI trước, đối chiếu CẢNH BÁO, xem THÔNG TIN để biết dòng đã bỏ qua/thay thế. Sau khi sửa, chạy Kiểm tra lại.",
                "Cách tìm ô: mở đúng file và trang tính trong Excel, nhấn Ctrl+G, nhập địa chỉ ô (ví dụ D279), nhấn Enter. Lỗi cấu hình sửa tại Tab được chỉ ra.",
                "Dữ liệu là giá trị ứng dụng đọc được tại thời điểm kiểm tra; ô công thức dùng kết quả đã lưu trong Excel. Báo cáo không sửa file nguồn.",
                "BẢO MẬT: Báo cáo có thể chứa họ tên, CCCD và thông tin đất đai. Chỉ lưu/chia sẻ cho người được phép; báo cáo hoạt động hoàn toàn ngoại tuyến.",
                "Các cột đã chọn: " + "; ".join(f"{LABELS.get(k, k)} = {v}" for k, v in context.profile.source_mapping.items()),
            ]
            metadata.append("Chế độ tự động bỏ qua dữ liệu thiếu/sai: " + ("BẬT" if context.profile.skip_invalid_data else "TẮT"))
            if context.profile.skip_invalid_data:
                metadata.append("Quy tắc: thiếu họ tên/CCCD của người hoặc thiếu tờ/thửa/diện tích của thửa thì bỏ cả hộ. CCCD đã có nhưng sai định dạng thì bỏ riêng người. Ô trống bình thường trên dòng nối tiếp và dòng tổng hợp không tự bị coi là thiếu dữ liệu.")
                metadata.append(f"Trước khi loại dữ liệu: {stats.get('source_households', 0)} hộ, {stats.get('source_people', 0)} người, {stats.get('source_parcels', 0)} thửa.")
            metadata.append(f"ĐÃ BỎ QUA: {stats.get('households_skipped', 0)} hộ; {stats.get('people_skipped', 0)} người (kể cả người trong hộ bị bỏ); {stats.get('parcels_skipped', 0)} thửa. Người bị bỏ riêng do CCCD sai: {stats.get('people_skipped_individually', 0)}.")
            if exported_paths and not blocked:
                metadata[7] = "Trạng thái: ĐÃ XUẤT VÀ KIỂM TRA FILE KẾT QUẢ"
                metadata.extend("File đã lưu: " + path for path in exported_paths)
            severity_labels = {"ERROR": "LỖI CẦN SỬA", "WARNING": "CẢNH BÁO CẦN ĐỐI CHIẾU", "INFO": "THÔNG TIN XỬ LÝ"}
            text_parts = ["\n".join(metadata)]
            cards = []
            for index, r in enumerate(records, 1):
                lines = [f"{index}. [{severity_labels[r.severity]}] {r.title}",
                         "Ở đâu: " + r.location, "Liên quan: " + r.subject, "Vấn đề: " + r.reason,
                         "Ảnh hưởng: " + r.effect, "Cách xử lý: " + r.action,
                         "Dữ liệu tại vị trí cần kiểm tra:", *(r.evidence or ["Không có ô dữ liệu cụ thể; xem vị trí cấu hình/thao tác ở trên."]),
                         "Mã tra cứu cho người hỗ trợ: " + r.code]
                text_parts.append("\n".join(lines))
                cards.append(f'<article class="issue {r.severity}" data-severity="{r.severity}"><h2>{escape(lines[0])}</h2>'
                             + "".join(f"<p>{escape(line)}</p>" for line in lines[1:6])
                             + '<details open><summary>Dữ liệu tại vị trí cần kiểm tra</summary><ul>'
                             + "".join(f"<li>{escape(v)}</li>" for v in r.evidence) + "</ul></details>"
                             + f'<small>{escape(lines[-1])}</small></article>')
            if not records:
                text_parts.append("Không phát hiện lỗi hoặc cảnh báo trong lần kiểm tra này.")
            # Each file is exclusive and self-contained. Keep a successfully written TXT if HTML fails.
            txt = directory / (stem + ".txt")
            with txt.open("x", encoding="utf-8-sig") as stream:
                stream.write("\n\n".join(text_parts) + "\n")
            files.paths.append(txt)
            html = directory / (stem + ".html")
            prominent = [0, 7, 8, 9] + [n for n, line in enumerate(metadata) if line.startswith("ĐÃ BỎ QUA:")]
            header = "".join(f"<p>{escape(metadata[n])}</p>" for n in prominent)
            header += "<details><summary>File nguồn, cấu hình và hướng dẫn tìm ô cần sửa</summary>"
            header += "".join(f"<p>{escape(line)}</p>" for n, line in enumerate(metadata) if n not in prominent) + "</details>"
            with html.open("x", encoding="utf-8") as stream:
                stream.write(HTML_START + "<header>" + header
                             + "</header>" + HTML_FILTER + "".join(cards) + HTML_END)
            files.paths.insert(0, html)
        except Exception as exc:
            # Diagnostics must never discard the processing result or hide a write failure.
            files.error = "Không lưu được đầy đủ báo cáo lỗi. Kiểm tra dung lượng ổ đĩa và quyền ghi thư mục. Chi tiết: " + str(exc)
        return files


def explain_failure(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, FileNotFoundError):
        return "Không tìm thấy file hoặc thư mục cần dùng.", "Kiểm tra đường dẫn, chọn lại file nguồn/thư mục xuất; giữ đầy đủ thư mục _internal bên cạnh EXE."
    if isinstance(exc, PermissionError):
        return "Windows không cho phép đọc hoặc ghi file.", "Đóng file đang mở trong Excel, kiểm tra quyền truy cập và chọn thư mục có quyền ghi, sau đó thử lại."
    if isinstance(exc, BadZipFile):
        return "File không đọc được như một workbook .xlsx hợp lệ.", "Mở file bằng Excel, dùng Lưu thành để tạo bản .xlsx mới. Không chỉ đổi đuôi tên file."
    if isinstance(exc, KeyError):
        return "Không tìm thấy trang tính hoặc thành phần dữ liệu đã chọn.", "Chọn lại file và trang tính ở Tab 1; kiểm tra lại cột ở Tab 2."
    if isinstance(exc, OSError):
        return "Có lỗi khi truy cập ổ đĩa hoặc file.", "Kiểm tra ổ đĩa còn trống, file còn tồn tại và quyền ghi; thử thư mục khác nếu cần."
    if isinstance(exc, ValueError):
        return "Dữ liệu hoặc cấu hình của thao tác chưa phù hợp.", "Kiểm tra dòng tiêu đề, ánh xạ cột, quy tắc và thư mục xuất. Xem thông tin chi tiết ở cuối mục này."
    return "Ứng dụng gặp sự cố trong khi xử lý.", "Giữ nguyên file nguồn, thử lại. Nếu vẫn lỗi, gửi báo cáo này và app.log cho người hỗ trợ."


HTML_START = '''<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Báo cáo kiểm tra VBDLIS</title><style>
body{font:16px/1.6 "Segoe UI",sans-serif;background:#f1f5f9;color:#172b45;margin:0;padding:24px;overflow-wrap:anywhere}
main{max-width:1080px;margin:auto}header,.issue,.filters{background:white;border:1px solid #ccd6e0;border-radius:8px;padding:20px;margin-bottom:16px}
header p:first-child{font-size:24px;font-weight:700}p{margin:7px 0;white-space:pre-wrap}h2{font-size:20px;margin:0 0 12px}
.ERROR{border-left:6px solid #bb2828}.WARNING{border-left:6px solid #b56a00}.INFO{border-left:6px solid #2171ad}
input,select{font:inherit;padding:8px;max-width:100%;box-sizing:border-box}input{width:65%}small{color:#536477}
summary{cursor:pointer;font-weight:600}li{white-space:pre-wrap}label{display:block}.filters{position:sticky;top:0;z-index:1}
[hidden]{display:none!important}@media print{.filters{display:none}.issue{break-inside:avoid}body{padding:0;background:white}}</style></head><body><main>'''
HTML_FILTER = '''<div class="filters"><label for="search">Tìm theo ô Excel, dòng, hộ, tên người hoặc nội dung</label>
<input id="search" type="search" placeholder="Ví dụ: D279 hoặc Hộ STT: 25">
<select id="severity" aria-label="Mức độ"><option value="">Tất cả</option><option value="ERROR">Lỗi cần sửa</option>
<option value="WARNING">Cảnh báo</option><option value="INFO">Thông tin</option></select><p id="count" aria-live="polite"></p></div>'''
HTML_END = '''<script>
const search=document.getElementById('search'),level=document.getElementById('severity');
const cards=Array.from(document.querySelectorAll('.issue'));
const fold=s=>s.toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d');
const text=cards.map(c=>fold(c.textContent));
function filter(){let visible=0;const q=fold(search.value).trim();
cards.forEach((c,i)=>{c.hidden=!!((level.value&&c.dataset.severity!==level.value)||!text[i].includes(q));if(!c.hidden)visible++});
document.getElementById('count').textContent='Đang hiện '+visible+' / '+cards.length+' mục. Xóa bộ lọc để xem toàn bộ.';}
search.addEventListener('input',filter);level.addEventListener('change',filter);filter();
</script></main></body></html>'''
