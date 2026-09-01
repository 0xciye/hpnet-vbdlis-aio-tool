"""Offline smoke test with synthetic data only; shared by standalone and suite."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from openpyxl import Workbook
from .paths import resource, default_template_path, default_template_fields
from .core import BatchConfig,ColumnMapping,NoticeService,inspect_workbook


def run(window):
    assert window.stack.count()==8 and not window.windowIcon().isNull()
    assert not window.confirm_button.isEnabled()
    with TemporaryDirectory(prefix="notice-smoke-") as temporary:
        root=Path(temporary); source=root/"synthetic.xlsx"
        wb=Workbook(); ws=wb.active; ws.title="Thử"
        ws.append(["Tên hộ","Tờ BĐ mới","Thửa BĐ mới","Diện tích bản đồ","Giấy tờ nhân thân","STT hộ"])
        ws.append(["HỘ KIỂM THỬ",72,175,357,"GIẤY TỜ KIỂM THỬ",1]); ws.append([None,72,176,200,None,None]); wb.save(source); wb.close()
        data=inspect_workbook(source,"Thử",1,1,ColumnMapping("A","B","C","D","","E",household_index="F"),require_identity=True)
        config=BatchConfig("12345","Địa chỉ thử","Thôn thử","Xã thử","Địa chỉ thửa thử","Địa danh thử",31,8,2026,start_number=100,template_fields=default_template_fields())
        service=NoticeService(default_template_path(),json.loads(resource("config/legal_defaults.json").read_text(encoding="utf-8")))
        preview=service.preview(data,config,root/"output",0,root/"preview")
        assert not (root/"output").exists()
        result=service.generate(data,config,root/"output",service.approve(preview))
        assert result["success"]==2 and [e.number for e in result["entries"]]==[100,101]
        assert result["txt"].is_file() and result["xlsx"].is_file()
    return {"status":"PASS","eight_steps":True,"preview_gate":True,"word_export":True,"numbering":True,"txt_xlsx_logs":True,"synthetic_only":True}
