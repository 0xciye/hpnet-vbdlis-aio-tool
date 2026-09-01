"""Mẫu 22 input contract, confirmed by the user on 2026-09-01."""
REQUIRED_COMMON = {
    "NGUON_GOC_SU_DUNG_DAT": "Nguồn gốc sử dụng đất",
    "TAI_SAN_DANG_KY": "Tài sản đăng ký (nhập Không nếu không có)",
    "GIAY_TO_DA_NOP": "Giấy tờ đã nộp",
    "NGUOI_KY": "Người ký",
    "CHI_NHANH_VP_DKDD": "Chi nhánh Văn phòng đăng ký đất đai",
    "CO_QUAN_THUE": "Cơ quan thuế",
    "DON_VI_LUU": "Đơn vị lưu",
}
OPTIONAL_COMMON = {
    "SU_DUNG_CHUNG": "Diện tích sử dụng chung",
    "SU_DUNG_RIENG": "Diện tích sử dụng riêng",
    "THUA_LIEN_KE": "Thửa liền kề",
    "TO_LIEN_KE": "Tờ bản đồ liền kề",
    "CHU_SU_HUU_LIEN_KE": "Chủ sử dụng thửa liền kề",
    "NOI_DUNG_QUYEN_LIEN_KE": "Nội dung quyền đối với thửa liền kề",
}
REQUIRED_TOKENS = {
    "TEN_XA": "Tên xã", "SO_TB": "Số thông báo", "DIA_DIEM": "Địa điểm",
    "NGAY": "Ngày", "THANG": "Tháng", "NAM": "Năm", "HO_TEN": "Họ tên",
    "GIAY_TO_NHAN_THAN": "Giấy tờ nhân thân", "DIA_CHI_NGUOI_SU_DUNG_DAT": "Địa chỉ",
    "SO_TO": "Số tờ", "SO_THUA": "Số thửa", "TEN_THON": "Tên thôn", "DIEN_TICH": "Diện tích",
    **REQUIRED_COMMON,
}


def has_content(value):
    text = "" if value is None else str(value).strip()
    return bool(text and any(c.isalnum() for c in text) and "{{" not in text and not text.startswith("#"))


def missing_required(values):
    return [label for token,label in REQUIRED_TOKENS.items() if not has_content(values.get(token))]
