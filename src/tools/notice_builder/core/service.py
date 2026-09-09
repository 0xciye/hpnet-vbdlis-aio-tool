from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from tempfile import mkstemp
import hashlib
import json
import os
import re
import uuid
from .models import UserError, file_hash
from .numbering import NumberPool
from .renderer import WordTemplate
from .logging import LogEntry, RunLog
from .fields import OPTIONAL_COMMON, REQUIRED_COMMON, REQUIRED_TOKENS, missing_required


@dataclass(frozen=True)
class Preview:
    path: Path
    signature: str
    token: str
    digest: str


def safe_filename(config, record):
    raw = f"{config.prefix.strip()}_{config.commune_code.strip()}_{record.sheet}_{record.parcel}-{config.suffix.strip()}.docx"
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", raw).rstrip(" .")
    if len(name) > 180:
        raise UserError("Tên file quá dài. Hãy rút ngắn hậu tố tên file.")
    return name, raw != name


def publish(payload, target):
    """Same-directory staging; never overwrite an existing target."""
    target = Path(target)
    fd, name = mkstemp(prefix=".thongbao-", suffix=".tmp", dir=target.parent)
    staging = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        WordTemplate.verify(staging.read_bytes())
        if os.name == "nt":
            os.rename(staging, target)  # Windows rename fails if target exists.
        else:
            os.link(staging, target)
            staging.unlink()
    finally:
        if staging.exists():
            staging.unlink()


class NoticeService:
    def __init__(self, template_path, legal_values):
        self.template = WordTemplate(template_path)
        self.legal = dict(legal_values)
        self.approvals = {}

    def values(self, record, config, number, notice_date=None):
        notice_date = notice_date or date(config.year, config.month, config.day)
        values = {key: str(value) for key,value in self.legal.items()}
        # New required fields are explicit inputs, never silently restored from old legal defaults.
        for key in (*REQUIRED_COMMON, *OPTIONAL_COMMON):
            values[key] = str(config.template_fields.get(key, "")).strip()
        values.update({"SO_TB":str(number), "TEN_XA":config.commune_name.strip(), "DIA_DIEM":config.place.strip(),
                       "NGAY":f"{notice_date.day:02d}","THANG":f"{notice_date.month:02d}","NAM":str(notice_date.year),
                       "HO_TEN":record.owner, "GIAY_TO_NHAN_THAN":record.identity, "DIA_CHI_NGUOI_SU_DUNG_DAT":config.owner_address.strip(),
                       "SO_TO":record.sheet,"SO_THUA":record.parcel,"DIEN_TICH":record.area,
                        "SU_DUNG_CHUNG":record.area,
                        "XU_DONG":record.location, "TEN_THON":config.village.strip(),
                        "DIA_CHI_HANH_CHINH":config.administrative_address.strip()})
        empty = "...." if config.optional_empty == "dots" else ""
        for key in self.template.tokens - REQUIRED_TOKENS.keys():
            if not values.get(key): values[key] = empty
        return values

    def signature(self, inspection, config, output):
        payload = (inspection.signature(), asdict(config), str(Path(output).resolve()), self.template.digest, self.legal)
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def check_unchanged(self, inspection):
        if file_hash(inspection.source) != inspection.source_hash:
            raise UserError("Excel nguồn đã thay đổi. Hãy kiểm tra và xem trước lại trước khi tạo hàng loạt.")
        if file_hash(self.template.path) != self.template.digest:
            raise UserError("Mẫu Word đã thay đổi. Hãy mở lại công cụ và kiểm tra lại mẫu.")

    def preview(self, inspection, config, output, record_index, preview_dir):
        config.validate(); self.check_unchanged(inspection)
        records = inspection.valid_records
        if not 0 <= record_index < len(records):
            raise UserError("Hãy chọn một thửa hợp lệ để xem trước.")
        pool = NumberPool.from_config(config)
        number = pool.preview_number(record_index)
        if number is None:
            raise UserError("Danh sách số chưa đủ cho thửa xem trước. Bổ sung số hoặc đặt số tiếp nối.")
        target = Path(preview_dir) / ("XEM_TRUOC_" + uuid.uuid4().hex[:10] + ".docx")
        target.parent.mkdir(parents=True, exist_ok=True)
        publish(self.template.render(self.values(records[record_index], config, number,
                                                 pool.date_for(number, date(config.year, config.month, config.day)))), target)
        return Preview(target, self.signature(inspection, config, output), uuid.uuid4().hex, file_hash(target))

    def approve(self, preview):
        if not preview.path.is_file() or file_hash(preview.path) != preview.digest:
            raise UserError("File xem trước đã thay đổi hoặc không còn. Hãy tạo và xem lại bản mới.")
        self.approvals[preview.token] = preview.signature
        return preview.token

    def generate(self, inspection, config, output, approval, progress=None, cancelled=None):
        config.validate(); self.check_unchanged(inspection)
        if self.approvals.pop(approval, None) != self.signature(inspection, config, output):
            raise UserError("Chưa xác nhận bản xem trước cho cấu hình hiện tại. Hãy xem trước và xác nhận lại.")
        directory = Path(output).resolve(); directory.mkdir(parents=True, exist_ok=True)
        pool = NumberPool.from_config(config)
        success = 0; aborted = False; log_error = ""
        filenames = {}
        for record in inspection.valid_records:
            name, _ = safe_filename(config, record)
            filenames.setdefault(name.casefold(), []).append(record.source_row)
        log = RunLog(directory, inspection)
        try:
            for index, record in enumerate(inspection.records):
                if cancelled and cancelled():
                    aborted = True; break
                number = None; filename = ""; status = record.status; error_type = ""; detail = ""
                if not record.valid:
                    detail = " ".join(record.errors)
                    if record.duplicate_rows:
                        detail += " Trùng tờ/thửa tại các dòng " + ", ".join(map(str,record.duplicate_rows)) + "; bỏ toàn bộ nhóm, chưa cấp số."
                    error_type = status
                elif missing := missing_required(self.values(record, config, 1)):
                    status = error_type = "THIẾU DỮ LIỆU"
                    detail = "Thiếu mục bắt buộc: " + ", ".join(missing) + f". Kiểm tra dòng {record.source_row}, tên hộ từ dòng {record.owner_row} và thông tin bước 4. Không tạo file, không dùng số."
                else:
                    number = pool.peek()
                    filename, cleaned = safe_filename(config, record)
                    target = directory / filename
                    if len(filenames[filename.casefold()]) > 1:
                        status = error_type = "TRÙNG TÊN FILE"
                        detail = "Các thửa tạo cùng tên file sau làm sạch. Không tạo file, không dùng số."
                        number = None
                    elif target.exists():
                        status = error_type = "FILE ĐÃ TỒN TẠI"
                        detail = "Không ghi đè file đã có. Số chưa được sử dụng; hãy kiểm tra file cũ hoặc chọn thư mục khác."
                    elif number is None:
                        status = error_type = "HẾT SỐ THÔNG BÁO"
                        detail = "Chưa có số để tạo file. Bổ sung danh sách hoặc số tiếp nối và chạy lại sau khi kiểm tra."
                    else:
                        try:
                            notice_date = pool.date_for(number, date(config.year, config.month, config.day))
                            payload = self.template.render(self.values(record, config, number, notice_date))
                        except Exception as exc:
                            status = error_type = "LỖI TEMPLATE"
                            detail = f"Không điền được mẫu Word: {exc}. Số {number} chưa dùng, giữ cho thửa tiếp theo."
                        else:
                            try:
                                publish(payload, target)
                            except FileExistsError:
                                status = error_type = "FILE ĐÃ TỒN TẠI"
                                detail = f"File vừa xuất hiện trong thư mục. Không ghi đè; số {number} chưa dùng."
                            except Exception as exc:
                                status = error_type = "LỖI GHI FILE"
                                reason = "Không đủ quyền ghi hoặc file đang bị khóa." if isinstance(exc,PermissionError) else "Kiểm tra quyền ghi, dung lượng, đường dẫn và file đang mở."
                                code = getattr(exc,"winerror",None) or getattr(exc,"errno",None)
                                detail = f"Không lưu được file tại {target}. {reason}"
                                if code: detail += f" Mã lỗi hệ thống: {code}."
                                detail += f" Số {number} chưa dùng, giữ cho thửa tiếp theo."
                            else:
                                pool.commit(number); success += 1; status = "THÀNH CÔNG"
                                detail = f"Đã kiểm tra DOCX và sử dụng số {number}, ngày {notice_date:%d/%m/%Y}. Dữ liệu từ dòng {record.source_row}, tên hộ từ dòng {record.owner_row}."
                                if cleaned: detail += " Đã làm sạch ký tự không hợp lệ trong tên file; nguồn không thay đổi."
                entry = LogEntry(record.source_row, record.owner, record.sheet, record.parcel, number, status, error_type, detail, filename)
                try:
                    log.append(entry)
                except OSError:
                    log_error = "Không ghi tiếp được nhật ký. Đã dừng để tránh mất dấu vết; file thành công trước đó được giữ nguyên."
                    aborted = True; break
                if progress: progress(index + 1, len(inspection.records), success, entry)
        finally:
            if aborted and not log_error:
                for record in inspection.records[len(log.entries):]:
                    try:
                        log.append(LogEntry(record.source_row,record.owner,record.sheet,record.parcel,None,
                                            "CHƯA XỬ LÝ","ĐÃ DỪNG","Người dùng yêu cầu dừng. Chưa tạo file và chưa dùng số."))
                    except OSError:
                        log_error = "Không ghi đủ được các dòng chưa xử lý vào nhật ký. Kiểm tra quyền ghi/dung lượng."; break
            try:
                log.finish()
            except Exception:
                log_error = (log_error + " Không xuất được nhật ký XLSX. Hãy xem TXT và kiểm tra quyền ghi/dung lượng.").strip()
                if not log.handle.closed: log.handle.close()
        return {"success":success,"processed":sum(e.status != "CHƯA XỬ LÝ" for e in log.entries),"total":len(inspection.records),"cancelled":aborted,
                "txt":log.txt,"xlsx":log.xlsx if log.xlsx.exists() else None,"log_error":log_error,"entries":log.entries}
