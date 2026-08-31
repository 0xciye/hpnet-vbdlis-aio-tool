# Kiến trúc VBDLIS Excel Builder

Ứng dụng tách giao diện khỏi nghiệp vụ. UI chỉ thu thập cấu hình, gọi `BuilderService` và hiển thị kết quả. Core gồm bốn tầng:

1. `SourceReader` + `AutoMapper`: đọc workbook nguồn theo sheet/header do người dùng chọn, không hard-code vị trí cột.
2. `HouseholdParser`: dựng hộ, người, thửa và GCN theo từng thửa; loại duplicate chính xác và chặn conflict GCN.
3. `FieldRuleEngine` + `TransformEngine`: áp dụng sáu mode field, fallback và phép nhân Người × Thửa với STT liên tục.
4. `WorkbookWriter` + `Validator`: ghi vào bản sao template, copy style mà không copy sample data, lưu, mở lại và kiểm tra.

`config/template_schema.json` là schema machine-readable 61 field. Template mới được đọc động; field chưa biết được đưa vào `TEMPLATE_OPTIONAL` thay vì tự động trở thành bắt buộc. Profile JSON giữ mapping, mã xã, địa chỉ, GCN mode, rule từng field và output settings.

GCN thuộc `Parcel`, không thuộc `Household`, vì vậy cùng file có thể trộn thửa có/chưa GCN và các thửa trong một hộ có GCN khác nhau. Nếu cùng tờ/thửa xuất hiện với hai bộ GCN khác nhau, parser phát `GCN_CONFLICT` và không tự chọn dữ liệu.

Không dữ liệu nguồn, CCCD đầy đủ hay thông tin đăng nhập nào được lưu vào profile. Log ứng dụng ghi đường dẫn, profile, thống kê và lỗi; không ghi toàn bộ CCCD.
