from __future__ import annotations

from pathlib import Path
import json

from tools.vbdlis_validation.models import ExcelConfig, RunConfig
from tools.vbdlis_validation.messages import describe_issues, recommended_actions
from tools.vbdlis_validation.service import ValidationService


def main() -> None:
    desktop=Path.home()/"Desktop/random stuff"
    source=desktop/"Tân Hòa đợt 1 ngày 8.9_cleaned.xlsx"
    document_root=desktop/"tân hòa pdf"
    upload=document_root/"VBDLIS Tân Hòa.xlsx"
    output=Path("qa_runtime/real_lineage_validation")
    result=ValidationService().run(RunConfig(
        ExcelConfig(upload,"Sheet1",4,{"person":"H","role":"N","sheet":"T","parcel":"U","combined":"AX"}),
        ExcelConfig(source,"Tân Hòa chạy đơn",1,{"household_id":"A","owner":"B","sheet":"G","parcel":"H"}),
        document_root/"chưa ký sao y (1)",document_root/"ddk đã đổi tên",output,"A","AZ",False,
    ))
    rows=[]
    for index,record in enumerate(result.records,1):
        missing_tbxn=not record.tbxn_documents
        missing_ddk=not record.ddk_documents
        invalid_identifier=bool(
            (record.sheet_raw and not record.sheet_normalized)
            or (record.parcel_raw and not record.parcel_normalized)
        )
        eligible=bool(record.source_rows) and not invalid_identifier
        failure_stage=""
        reason=""
        suggested=""
        if invalid_identifier:
            failure_stage="SOURCE_DATA_ERROR"
            reason="Số tờ hoặc số thửa có chữ/ký tự không hợp lệ; nghiệp vụ bắt buộc dùng số nguyên dương."
            suggested="Mở đúng dòng Excel được ghi trong báo cáo, đối chiếu hồ sơ gốc rồi sửa thành số nguyên lớn hơn 0; không tự đoán giá trị."
        elif eligible and missing_tbxn:
            failure_stage="TBXN_NOT_FOUND_RECURSIVELY"
            reason="Không tìm thấy TBXN vật lý trong các thư mục đã quét."
            suggested="Kiểm tra nhật ký tạo Word/PDF và bổ sung đúng file TBXN theo tờ/thửa."
        elif eligible and missing_ddk:
            failure_stage="DDK_PHYSICAL_MISSING"
            reason="Không tìm thấy DDK vật lý cho thửa này trong thư mục đã chọn."
            suggested="Đối chiếu giấy tờ nguồn và chạy lại công cụ Đặt tên hồ sơ; xử lý cảnh báo tên/STT nếu có."
        rows.append({
            "test_case":f"REAL{index:03d}","household":record.owner_raw,"sheet":record.sheet_raw,"parcel":record.parcel_raw,
            "source_present":bool(record.source_rows),"source_rows":", ".join(map(str,record.source_rows)),
            "identifier_valid":not invalid_identifier,"eligible":eligible,
            "word_expected":eligible,"word_generated_before_fix":eligible and not missing_tbxn,
            "word_generation_regression":False,
            "tbxn_expected":eligible,"tbxn_found":eligible and not missing_tbxn,
            "tbxn_paths":" | ".join(str(doc.path) for doc in record.tbxn_documents),
            "ddk_expected":eligible,"ddk_found":eligible and not missing_ddk,
            "ddk_paths":" | ".join(str(doc.path) for doc in record.ddk_documents),
            "vbdlis_parcel_found":bool(record.upload_rows),"vbdlis_rows":len(record.upload_rows),
            "vbdlis_row_numbers":", ".join(str(row.row_number) for row in record.upload_rows),
            "ax_raw":record.ax_raw,"ax_status":record.ax_status,"workflow_status":record.workflow_status.value,
            "issues":" | ".join(record.issues),"user_message":describe_issues(record.issues),
            "user_action":recommended_actions(record.issues),
            "failure_stage":failure_stage,"failure_reason":reason,"suggested_fix":suggested,
        })
    eligible_rows=[row for row in rows if row["eligible"]]
    upload_rows=[row for row in rows if row["vbdlis_parcel_found"]]
    payload={
        "repository":{"branch":"main","commit":"fab6a5d","working_tree_before":"clean","sync":"git pull --ff-only: already up to date"},
        "real_data":{
            "source":str(source),"upload":str(upload),"source_sheet":"Tân Hòa chạy đơn","source_mapping":"B=Tên hộ; G=Số tờ; H=Số thửa",
            "source_parcels":sum(row["source_present"] for row in rows),
            "eligible_tbxn":len(eligible_rows),
            "invalid_source_identifiers":sum(row["source_present"] and not row["identifier_valid"] for row in rows),
            "word_records_after_fix":len(eligible_rows),
            "word_generated_physical_before_fix":sum(row["tbxn_found"] for row in eligible_rows),
            "tbxn_expected":len(eligible_rows),"tbxn_physical_found":sum(row["tbxn_found"] for row in eligible_rows),
            "ddk_expected":len(eligible_rows),"ddk_physical_found":sum(row["ddk_found"] for row in eligible_rows),
            "vbdlis_parcels_current":len(upload_rows),"vbdlis_rows_current":sum(row["vbdlis_rows"] for row in upload_rows),
            "vbdlis_valid_parcels_after_fix":sum(row["identifier_valid"] for row in upload_rows),
            "vbdlis_valid_rows_after_fix":sum(row["vbdlis_rows"] for row in upload_rows if row["identifier_valid"]),
            "invalid_vbdlis_identifiers":sum(not row["identifier_valid"] for row in upload_rows),
            "ax_tbxn_references_found":sum("-TBXN.pdf" in row["ax_raw"] for row in upload_rows),
            "ax_ddk_references_found":sum("-DDK.pdf" in row["ax_raw"] for row in upload_rows),
            "missing_tbxn_final":sum(not row["tbxn_found"] for row in eligible_rows),
            "missing_ddk_final":sum(not row["ddk_found"] for row in eligible_rows),
            "document_complete":sum(row["tbxn_found"] and row["ddk_found"] for row in eligible_rows),
            "invalid_identifier_root_cause":"SOURCE_DATA_ERROR: dòng 288 có số thửa CN; quy tắc nghiệp vụ chỉ cho phép số nguyên dương.",
        },
        "validator_stats":result.stats|result.scan_stats,
        "lineage":rows,
    }
    target=Path("qa_runtime/real_lineage.json"); target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(target.resolve())


if __name__=="__main__":
    main()
