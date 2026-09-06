import os
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List
from tools.signed_pdf_cleaner.core.models import FileActionPlan

class AppLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.log_file = self.log_dir / f"{timestamp}.log"
        
        self.logger = logging.getLogger("SignedPdfCleaner")
        self.logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
            
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
    def log_plan_result(self, plan: FileActionPlan):
        msg = []
        msg.append(f"[{plan.status.name}]")
        if plan.unsigned_path:
            msg.append(f"Unsigned: {plan.unsigned_path.name}")
        if plan.signed_path:
            msg.append(f"Signed: {plan.signed_path.name}")
            
        if plan.status.name == "COMPLETED":
            if plan.action.name == "DELETE_AND_RENAME":
                msg.append(f"-> Đã xóa bản chưa ký")
            msg.append(f"-> Đã đổi {plan.signed_path.name} thành {plan.target_path.name}")
        elif plan.status.name == "SKIPPED":
            if plan.warning_message:
                msg.append(f"-> {plan.warning_message}")
        elif plan.status.name == "ERROR":
            msg.append(f"-> {plan.error_message}")
            
        self.logger.info("\n".join(msg))
        
    def export_csv(self, plans: List[FileActionPlan], export_path: str):
        with open(export_path, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["Thư mục", "File signed", "File chưa ký", "Hành động", "Tên sau xử lý", "Trạng thái", "Lỗi/Cảnh báo"])
            for p in plans:
                folder = str(p.target_path.parent) if p.target_path else ""
                signed = p.signed_path.name if p.signed_path else ""
                unsigned = p.unsigned_path.name if p.unsigned_path else ""
                action = p.action.value
                target = p.target_path.name if p.target_path else ""
                status = p.status.value
                error = p.error_message or p.warning_message
                values = [folder, signed, unsigned, action, target, status, error]
                writer.writerow([f"'{value}" if str(value).lstrip().startswith(("=", "+", "-", "@")) else value for value in values])
