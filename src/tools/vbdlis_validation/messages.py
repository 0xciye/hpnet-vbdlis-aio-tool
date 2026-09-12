from __future__ import annotations

from collections.abc import Iterable

ISSUE_MESSAGES = {
    "VALID": "Hồ sơ thửa đất đã đủ dữ liệu và đủ hai tài liệu có chữ ký số hợp lệ.",
    "MISSING_TBXN": "Chưa tìm thấy file Thông báo xác nhận (TBXN) của thửa đất này.",
    "MISSING_DDK": "Chưa tìm thấy file Đơn đăng ký (DDK) của thửa đất này.",
    "MISSING_BOTH": "Chưa tìm thấy cả file TBXN và file DDK của thửa đất này.",
    "TBXN_UNSIGNED": "File TBXN chưa có chữ ký số PDF.",
    "DDK_UNSIGNED": "File DDK chưa có chữ ký số PDF.",
    "BOTH_UNSIGNED": "Cả file TBXN và file DDK đều chưa có chữ ký số PDF.",
    "TBXN_SIGNATURE_INVALID": "Chữ ký số trong file TBXN không còn nguyên vẹn hoặc không xác minh được.",
    "DDK_SIGNATURE_INVALID": "Chữ ký số trong file DDK không còn nguyên vẹn hoặc không xác minh được.",
    "BOTH_SIGNATURE_INVALID": "Chữ ký số trong cả file TBXN và file DDK đều không hợp lệ.",
    "SIGNATURE_CHECK_ERROR": "Ứng dụng không thể hoàn tất việc kiểm tra chữ ký của file PDF này.",
    "SOURCE_PARCEL_NOT_FOUND": "Có dữ liệu VBDLIS nhưng không tìm thấy thửa tương ứng trong Excel nguồn.",
    "VBDLIS_PARCEL_NOT_FOUND": "Có thửa trong Excel nguồn nhưng chưa có dòng tương ứng trong Excel VBDLIS.",
    "SOURCE_ONLY": "Thửa này chỉ có trong Excel nguồn, chưa có trong Excel VBDLIS.",
    "VBDLIS_ONLY": "Thửa này chỉ có trong Excel VBDLIS, không có trong Excel nguồn.",
    "HOUSEHOLD_NOT_FOUND": "Chưa xác định được hộ gia đình của dòng dữ liệu này.",
    "AMBIGUOUS_MATCH": "Có nhiều hồ sơ có thể khớp; ứng dụng không tự chọn để tránh ghép nhầm.",
    "DUPLICATE_TBXN": "Tìm thấy nhiều hơn một file TBXN cho cùng thửa đất.",
    "DUPLICATE_DDK": "Tìm thấy nhiều hơn một file DDK cho cùng thửa đất.",
    "INVALID_PDF": "File PDF bị lỗi hoặc không đọc được cấu trúc chữ ký số.",
    "FILE_ACCESS_ERROR": "Ứng dụng không đọc được file PDF này; file có thể đang mở hoặc bạn chưa có quyền truy cập.",
    "DATA_MISMATCH": "Thông tin trong Excel và tên tài liệu thực tế chưa khớp nhau.",
    "PARCEL_MISMATCH": "Số tờ hoặc số thửa trong Excel VBDLIS không khớp với Excel nguồn của hộ này.",
    "REVIEW_REQUIRED": "Trường hợp này cần người dùng kiểm tra và xác nhận thủ công.",
    "UNKNOWN_ROLE": "Giá trị trong cột Vai trò chưa nhận diện được là Chủ hộ hay Thành viên.",
    "HOUSEHOLD_WITHOUT_HEAD": "Nhóm dữ liệu này chưa có dòng Chủ hộ để xác định hộ gia đình.",
    "MULTIPLE_HOUSEHOLD_HEADS": "Nhóm dữ liệu có nhiều người khác nhau cùng được ghi là Chủ hộ.",
    "MISSING_NAME": "Dòng dữ liệu chưa có họ và tên.",
    "MISSING_ROLE": "Dòng dữ liệu chưa có vai trò Chủ hộ/Thành viên.",
    "MISSING_SHEET": "Dòng dữ liệu chưa có số tờ bản đồ.",
    "MISSING_PARCEL": "Dòng dữ liệu chưa có số thửa đất.",
    "INVALID_SHEET_IDENTIFIER": "Số tờ không hợp lệ. Số tờ bắt buộc phải là số nguyên dương và không được có chữ cái.",
    "INVALID_PARCEL_IDENTIFIER": "Số thửa không hợp lệ. Số thửa bắt buộc phải là số nguyên dương và không được có chữ cái.",
    "AX_EMPTY": "Cột Thông tin hồ sơ quét đang để trống.",
    "AX_PARSE_ERROR": "Không đọc được tên TBXN/DDK trong cột Thông tin hồ sơ quét.",
    "AX_DATA_MISMATCH": "Tên tài liệu trong Excel chưa khớp với file PDF thực tế.",
    "AX_MISSING_TBXN_REFERENCE": "Có file TBXN thực tế nhưng Excel chưa ghi đúng tên file này.",
    "AX_MISSING_DDK_REFERENCE": "Có file DDK thực tế nhưng Excel chưa ghi đúng tên file này.",
    "AX_REFERENCES_MISSING_TBXN": "Excel có ghi tên TBXN nhưng chưa tìm thấy file TBXN tương ứng.",
    "AX_REFERENCES_MISSING_DDK": "Excel có ghi tên DDK nhưng chưa tìm thấy file DDK tương ứng.",
}

ISSUE_ACTIONS = {
    "VALID": "Không cần xử lý.",
    "MISSING_TBXN": "Bổ sung đúng file TBXN đã ký số cho thửa này.",
    "MISSING_DDK": "Bổ sung đúng file DDK đã ký số cho thửa này.",
    "MISSING_BOTH": "Bổ sung đủ file TBXN và DDK đã ký số cho thửa này.",
    "TBXN_UNSIGNED": "Mở đúng file TBXN đã được ký số, sau đó chọn lại thư mục tài liệu.",
    "DDK_UNSIGNED": "Mở đúng file DDK đã được ký số, sau đó chọn lại thư mục tài liệu.",
    "BOTH_UNSIGNED": "Thay cả hai file bằng bản đã được ký số.",
    "TBXN_SIGNATURE_INVALID": "Đề nghị ký lại TBXN hoặc lấy lại bản PDF đã ký nguyên vẹn.",
    "DDK_SIGNATURE_INVALID": "Đề nghị ký lại DDK hoặc lấy lại bản PDF đã ký nguyên vẹn.",
    "BOTH_SIGNATURE_INVALID": "Lấy lại hoặc ký lại cả file TBXN và file DDK.",
    "SIGNATURE_CHECK_ERROR": "Đóng file PDF nếu đang mở, thử mở PDF để kiểm tra, rồi chạy lại.",
    "SOURCE_PARCEL_NOT_FOUND": "Đối chiếu số tờ, số thửa và chủ hộ; chỉ upload khi thửa có trong nguồn.",
    "VBDLIS_PARCEL_NOT_FOUND": "Bổ sung các dòng VBDLIS của thửa, gồm đầy đủ thành viên liên quan.",
    "SOURCE_ONLY": "Kiểm tra và bổ sung thửa còn thiếu vào Excel VBDLIS nếu đúng nghiệp vụ.",
    "VBDLIS_ONLY": "Kiểm tra lại dòng VBDLIS; sửa số tờ/thửa hoặc loại dòng nếu nhập thừa.",
    "HOUSEHOLD_NOT_FOUND": "Chọn lại cột Vai trò hoặc Mã hộ và bảo đảm có dòng Chủ hộ.",
    "AMBIGUOUS_MATCH": "Mở file gợi ý, đối chiếu chủ hộ + số tờ + số thửa rồi chọn đúng tài liệu.",
    "DUPLICATE_TBXN": "Giữ lại đúng một TBXN của thửa hoặc tách file dư khỏi thư mục kiểm tra.",
    "DUPLICATE_DDK": "Giữ lại đúng một DDK của thửa hoặc tách file dư khỏi thư mục kiểm tra.",
    "INVALID_PDF": "Mở thử PDF; nếu không mở được, lấy lại file gốc hoặc xuất lại PDF.",
    "FILE_ACCESS_ERROR": "Đóng file PDF đang mở, kiểm tra quyền truy cập rồi chạy lại.",
    "DATA_MISMATCH": "So sánh tên file trong Excel với file thực tế và sửa tại file nguồn phù hợp.",
    "PARCEL_MISMATCH": "Đối chiếu Excel nguồn rồi sửa đúng số tờ và số thửa trong Excel VBDLIS.",
    "REVIEW_REQUIRED": "Không upload trường hợp này trước khi đã kiểm tra thủ công.",
    "UNKNOWN_ROLE": "Chuẩn hóa giá trị cột Vai trò thành Chủ hộ hoặc Thành viên hộ gia đình.",
    "HOUSEHOLD_WITHOUT_HEAD": "Bổ sung hoặc xác định đúng dòng Chủ hộ trước khi tiếp tục.",
    "MULTIPLE_HOUSEHOLD_HEADS": "Đối chiếu và giữ đúng một người Chủ hộ trong cùng nhóm hộ.",
    "MISSING_NAME": "Bổ sung họ tên tại dòng Excel được ghi trong báo cáo.",
    "MISSING_ROLE": "Bổ sung vai trò Chủ hộ hoặc Thành viên hộ gia đình tại dòng Excel.",
    "MISSING_SHEET": "Bổ sung đúng số tờ bản đồ.",
    "MISSING_PARCEL": "Bổ sung đúng số thửa đất.",
    "INVALID_SHEET_IDENTIFIER": "Mở dòng Excel được ghi trong báo cáo và sửa Số tờ thành một số nguyên lớn hơn 0.",
    "INVALID_PARCEL_IDENTIFIER": "Mở dòng Excel được ghi trong báo cáo và sửa Số thửa thành một số nguyên lớn hơn 0.",
    "AX_EMPTY": "Bổ sung tên TBXN và DDK vào cột Thông tin hồ sơ quét nếu nghiệp vụ yêu cầu.",
    "AX_PARSE_ERROR": "Ghi rõ tên file TBXN và DDK, phân cách bằng dấu phẩy hoặc dấu chấm phẩy.",
    "AX_DATA_MISMATCH": "Đối chiếu và cập nhật tên file trong Excel cho đúng với PDF thực tế.",
    "AX_MISSING_TBXN_REFERENCE": "Cập nhật đúng tên file TBXN vào Excel.",
    "AX_MISSING_DDK_REFERENCE": "Cập nhật đúng tên file DDK vào Excel.",
    "AX_REFERENCES_MISSING_TBXN": "Bổ sung đúng file TBXN được Excel tham chiếu hoặc sửa tên tham chiếu.",
    "AX_REFERENCES_MISSING_DDK": "Bổ sung đúng file DDK được Excel tham chiếu hoặc sửa tên tham chiếu.",
}


def _unique_messages(codes: Iterable[str], lookup: dict[str, str]) -> list[str]:
    result: list[str] = []
    for code in codes:
        message = lookup.get(code, f"Cần kiểm tra thêm (mã: {code}).")
        if message not in result:
            result.append(message)
    return result


def _display_codes(codes: Iterable[str]) -> list[str]:
    result = list(codes)
    invalid_identifiers = {
        "INVALID_SHEET_IDENTIFIER", "INVALID_PARCEL_IDENTIFIER"
    }.intersection(result)
    if invalid_identifiers:
        # The bad identifier is the actionable root cause. Hide downstream
        # matching/document symptoms so a non-technical user gets one clear job.
        return [code for code in result if code in invalid_identifiers]
    if "BOTH_UNSIGNED" in result:
        result = [code for code in result if code not in {"TBXN_UNSIGNED", "DDK_UNSIGNED"}]
    if "BOTH_SIGNATURE_INVALID" in result:
        result = [code for code in result if code not in {"TBXN_SIGNATURE_INVALID", "DDK_SIGNATURE_INVALID"}]
    return result


def describe_issues(codes: Iterable[str]) -> str:
    return " ".join(_unique_messages(_display_codes(codes), ISSUE_MESSAGES))


def recommended_actions(codes: Iterable[str]) -> str:
    return " ".join(_unique_messages(_display_codes(codes), ISSUE_ACTIONS))


def friendly_failure(message: str) -> str:
    detail = message.strip()
    lowered = detail.casefold()
    if any(token in lowered for token in ("permission denied", "winerror 5", "được sử dụng bởi")):
        return (
            "Ứng dụng không thể đọc hoặc tạo file vì file đang mở hoặc bạn chưa có quyền truy cập.\n\n"
            "Hãy đóng file Excel/PDF đang mở, chọn một thư mục kết quả mà bạn có quyền ghi, rồi thử lại."
        )
    if any(token in lowered for token in ("badzipfile", "file is not a zip", "not a zip file")):
        return (
            "File Excel đã chọn bị lỗi hoặc không đúng định dạng .xlsx/.xlsm.\n\n"
            "Hãy mở file bằng Excel, chọn “Save As” để lưu lại thành .xlsx, rồi chọn file mới."
        )
    if any(token in lowered for token in ("no such file", "cannot find", "không tìm thấy")):
        return f"Không tìm thấy file hoặc thư mục đã chọn.\n\n{detail}\n\nHãy chọn lại đúng đường dẫn rồi thử lại."
    if detail and not any(token in detail for token in ("Traceback", "KeyError", "Errno")):
        return f"{detail}\n\nHãy kiểm tra lại các mục đã chọn và thử lại. Dữ liệu gốc chưa bị thay đổi."
    return (
        "Ứng dụng chưa thể hoàn tất kiểm tra. Dữ liệu gốc chưa bị thay đổi.\n\n"
        "Hãy đóng các file đang mở, kiểm tra lại file Excel và thư mục PDF, rồi thử lại. "
        "Nếu lỗi vẫn còn, gửi file validation.log cho người hỗ trợ."
    )
