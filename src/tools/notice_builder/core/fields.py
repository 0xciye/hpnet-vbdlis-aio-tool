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
FIELD_LABELS = {
    "TEN_XA": "Tên xã", "SO_TB": "Số thông báo", "DIA_DIEM": "Địa điểm",
    "NGAY": "Ngày", "THANG": "Tháng", "NAM": "Năm", "HO_TEN": "Họ tên",
    "NGAY_SINH": "Ngày sinh chủ hộ",
    "GIAY_TO_NHAN_THAN": "Giấy tờ nhân thân", "DIA_CHI_NGUOI_SU_DUNG_DAT": "Địa chỉ",
    "SO_TO": "Số tờ", "SO_THUA": "Số thửa", "TEN_THON": "Tên thôn",
    "DIEN_TICH": "Diện tích", "SU_DUNG_CHUNG": "Diện tích sử dụng chung",
    **REQUIRED_COMMON,
}
OPTIONAL_COMMON = {
    "SU_DUNG_RIENG": "Diện tích sử dụng riêng",
    "THUA_LIEN_KE": "Thửa liền kề",
    "TO_LIEN_KE": "Tờ bản đồ liền kề",
    "CHU_SU_HUU_LIEN_KE": "Chủ sử dụng thửa liền kề",
    "NOI_DUNG_QUYEN_LIEN_KE": "Nội dung quyền đối với thửa liền kề",
}
REQUIRED_TOKENS = {key: FIELD_LABELS[key] for key in (
    "TEN_XA", "SO_TB", "DIA_DIEM", "NGAY", "THANG", "NAM", "HO_TEN",
    "GIAY_TO_NHAN_THAN", "DIA_CHI_NGUOI_SU_DUNG_DAT", "SO_TO", "SO_THUA",
    "TEN_THON", "DIEN_TICH", "SU_DUNG_CHUNG", *REQUIRED_COMMON,
)}


def has_content(value):
    text = "" if value is None else str(value).strip()
    return bool(text and any(c.isalnum() for c in text) and "{{" not in text and not text.startswith("#"))


def missing_required(values, required_tokens=None):
    tokens = required_tokens or REQUIRED_TOKENS
    return [FIELD_LABELS.get(token, token.replace("_", " ").title())
            for token in tokens if not has_content(values.get(token))]
