"""Repeatable offline QA. Never generates an official batch from real input."""
import argparse
from dataclasses import asdict
from datetime import date
from pathlib import Path
from time import perf_counter
import json
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from openpyxl import Workbook
from tools.notice_builder.core import BatchConfig,ColumnMapping,NoticeService,inspect_workbook,workbook_info
from tools.notice_builder.paths import resource, default_template_path, default_template_fields


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',required=True); parser.add_argument('--real'); parser.add_argument('--count',type=int,default=1000); args=parser.parse_args()
    root=Path(args.output).resolve(); root.mkdir(parents=True,exist_ok=False)
    os.environ['APPDATA']=str(root/'profile'); os.environ['QT_QPA_PLATFORM']='offscreen'
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase
    from tools.notice_builder.ui import MainWindow
    app=QApplication.instance() or QApplication(['notice-qa']); app.setStyle('Fusion')
    for filename in ('segoeui.ttf','segoeuib.ttf','seguisym.ttf'):
        font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/filename
        if font.exists(): QFontDatabase.addApplicationFont(str(font))
    window=MainWindow()
    window.show(); app.processEvents()
    source=root/'synthetic.xlsx'; wb=Workbook(); ws=wb.active; ws.title='Kiểm thử'
    ws.append(['Tên hộ','Tờ BĐ mới','Thửa BĐ mới','Diện tích bản đồ','Giấy tờ nhân thân'])
    for i in range(args.count): ws.append([f'HỘ KIỂM THỬ {i+1}',72,i+1,357.25,f'GIẤY TỜ KIỂM THỬ {i+1}'])
    wb.save(source); wb.close()
    config=BatchConfig('12345','Địa chỉ thử','Thôn thử','Xã thử','Xã thử, thành phố thử','Xã thử',1,9,2026,start_number=100,template_fields=default_template_fields())
    data=inspect_workbook(source,'Kiểm thử',1,1,ColumnMapping('A','B','C','D','','E'),require_identity=True)
    service=NoticeService(default_template_path(),json.loads(resource('config/legal_defaults.json').read_text(encoding='utf-8')))
    preview=service.preview(data,config,root/'synthetic_output',0,root/'preview_synthetic')
    start=perf_counter(); result=service.generate(data,config,root/'synthetic_output',service.approve(preview)); seconds=perf_counter()-start
    assert result['success']==args.count and not result['log_error']
    assert [e.number for e in result['entries']]==list(range(100,100+args.count))
    report={'synthetic_batch':{'count':args.count,'success':result['success'],'seconds':round(seconds,3),'numbering_contiguous':True},'official_real_batch_created':False}
    window.source.setText(str(source)); window.output.setText(str(root/'not_generated_from_ui')); window.source_ready(workbook_info(source))
    for key,value in asdict(config).items():
        field=window.inputs.get(key)
        if field:
            if hasattr(field,'setValue'): field.setValue(value)
            else: field.setText(str(value))
    window.inspection_ready(data)
    for size in [(1250,830),(1000,650)]:
        window.resize(*size)
        for step in range(8):
            window.steps.setCurrentRow(step); app.processEvents()
            window.grab().save(str(root/f'ui-{size[0]}-step-{step+1}.png'))
    if args.real:
        info=workbook_info(args.real); real=inspect_workbook(args.real,info['sheet'],info['header_row'],info['depth'],ColumnMapping(identity='D'),require_identity=True)
        actual_config=BatchConfig('10930','Thôn Cẩm Đông, xã Mao Điền, Thành phố Hải Phòng','Cẩm Đông','Mao Điền','xã Mao Điền, Thành phố Hải Phòng','Mao Điền',1,9,2026,start_number=1,template_fields=default_template_fields())
        actual_preview=service.preview(real,actual_config,root/'NOT_AN_OFFICIAL_BATCH',0,root/'Xem_truoc_Cam_Dong')
        report['real']={'source':str(real.source),'sha256':real.source_hash,'sheet':real.sheet_name,'rows':real.total_rows,'records':len(real.records),
            'valid':len(real.valid_records),'duplicates':[asdict(r) for r in real.records if r.duplicate_rows],
            'invalid':[asdict(r) for r in real.records if r.errors],'summary_rows':real.summary_rows,'blank_rows':real.blank_rows,'name_only_rows':real.name_only_rows,
            'preview':str(actual_preview.path),'preview_number':1,'preview_date':'01/09/2026','preview_not_official':True}
        lines=["KIỂM TRA DỮ LIỆU CẨM ĐÔNG — CHƯA TẠO HÀNG LOẠT",f"Trang tính: {real.sheet_name}",f"Tổng dòng: {real.total_rows}; dòng thửa: {len(real.records)}; hợp lệ: {len(real.valid_records)}; trùng: {len(report['real']['duplicates'])}",
            'Cột: B tên hộ, D giấy tờ nhân thân, G tờ mới, H thửa mới, K diện tích bản đồ, L xứ đồng. Không dùng I/J hoặc tự lấy M thay K.',
            'Bản xem trước dùng số dự kiến 1, ngày 01/09/2026. Phải nhập số/ngày đợt thực tế và xác nhận nội dung trước khi tạo chính thức.',
            'Thiếu giấy tờ/diện tích không tự đoán hoặc lấy M thay K. Cách tìm: mở trang tính trên, Ctrl+G, nhập ô lỗi.',
            *[f"Dòng {r.source_row}, tờ {r.sheet}, thửa {r.parcel}: {' '.join(r.errors)}" for r in real.records if r.errors]]
        (root/'KET_QUA_DU_LIEU_THAT.txt').write_text('\n'.join(lines),encoding='utf-8-sig')
    (root/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); window.close()
    print(json.dumps({'synthetic':report['synthetic_batch'],'real_valid':report.get('real',{}).get('valid'),'report':str(root/'verification.json')},ensure_ascii=False))


if __name__=='__main__': main()
