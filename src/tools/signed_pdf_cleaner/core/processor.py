import os
import shutil
from pathlib import Path
from send2trash import send2trash
from tools.signed_pdf_cleaner.core.models import FileActionPlan, ActionType, ProcessStatus

class FileProcessor:
    def __init__(self, use_recycle_bin: bool = True):
        self.use_recycle_bin = use_recycle_bin

    def process_plan(self, plan: FileActionPlan) -> FileActionPlan:
        if plan.status not in (ProcessStatus.READY, ProcessStatus.WARNING):
            return plan

        try:
            if plan.action == ActionType.DELETE_AND_RENAME:
                self._replace_unsigned_with_signed(plan)
                plan.status = ProcessStatus.COMPLETED
            elif plan.action == ActionType.RENAME_SIGNED:
                self._rename_file(plan.signed_path, plan.target_path)
                plan.status = ProcessStatus.COMPLETED
            elif plan.action == ActionType.SKIP:
                plan.status = ProcessStatus.SKIPPED
        except Exception as e:
            plan.status = ProcessStatus.ERROR
            plan.error_message = str(e)

        return plan

    def _replace_unsigned_with_signed(self, plan: FileActionPlan):
        """Giữ được bản đã ký nếu thao tác xóa hoặc đổi tên cuối cùng thất bại."""
        staging = plan.target_path.with_name(plan.target_path.name + ".signed_replacement")
        if staging.exists():
            raise Exception(f"File tạm đã tồn tại, chưa thay thế để tránh ghi đè: {staging.name}")
        self._rename_file(plan.signed_path, staging)
        try:
            self._delete_file(plan.unsigned_path)
            self._rename_file(staging, plan.target_path)
        except Exception:
            # Nếu bản chưa ký vẫn còn, trả bản đã ký về tên cũ. Nếu nó đã bị xóa,
            # giữ bản đã ký ở file tạm thay vì xóa hoặc ghi đè dữ liệu.
            if plan.unsigned_path and plan.unsigned_path.exists() and staging.exists():
                try:
                    self._rename_file(staging, plan.signed_path)
                except Exception:
                    pass
            raise

    def _delete_file(self, file_path: Path):
        if not file_path or not file_path.exists():
            return
            
        try:
            if self.use_recycle_bin:
                send2trash(str(file_path.resolve()))
            else:
                os.remove(file_path)
        except OSError as e:
            raise Exception(f"Không thể xóa file {file_path.name}: File đang được sử dụng hoặc không có quyền truy cập. ({e})")
        except Exception as e:
            raise Exception(f"Lỗi khi xóa file {file_path.name}: {e}")

    def _rename_file(self, source: Path, target: Path):
        if not source or not source.exists():
            raise Exception(f"File nguồn không tồn tại: {source.name}")
            
        if target.exists():
            raise Exception(f"File đích đã tồn tại, không thể đổi tên (xung đột): {target.name}")
            
        try:
            os.rename(source, target)
        except OSError as e:
            raise Exception(f"Không thể đổi tên file {source.name}: {e}")
