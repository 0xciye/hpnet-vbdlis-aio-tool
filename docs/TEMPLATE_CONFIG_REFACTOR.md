# Báo cáo cấu hình mẫu thông báo

## Phạm vi rà soát

| File | Vị trí | Cơ chế cũ | Kết quả |
|---|---|---|---|
| `src/tools/notice_builder/core/models.py` | `BatchConfig.validate` | `commune_name` và `place` là dữ liệu bắt buộc dùng chung | Không còn tham gia xác thực mẫu; giữ trường rỗng để đọc cấu hình người dùng cũ |
| `src/tools/notice_builder/core/service.py` | `NoticeService.values` | Word lấy `TEN_XA` và `DIA_DIEM` từ `BatchConfig` dùng chung | Lấy từ `TemplateConfig.static_values` của mẫu đang chọn |
| `src/tools/notice_builder/ui.py` | bước Thông tin thông báo | Có ô nhập tên xã và địa điểm dùng cho mọi mẫu | Đã bỏ hai ô; giao diện hiển thị giá trị cố định của mẫu đang chọn |
| `src/tools/notice_builder/paths.py` | mẫu mặc định và giá trị ban đầu | Hợp đồng trường dùng chung toàn cục | Mẫu mặc định và trường nhập được lấy từ cấu hình mẫu |
| `src/tools/notice_builder/core/fields.py` | xác thực placeholder | Một danh sách bắt buộc dùng cho mọi mẫu | `missing_required` nhận danh sách riêng của mẫu |

## Nguồn cấu hình

`src/tools/notice_builder/config/template_configs.json` là nguồn duy nhất cho giá trị cố định, ánh xạ, trường bắt buộc, quy tắc xác thực và quy tắc tài liệu của từng mẫu. Mẫu 22 Mao Điền được đánh dấu mặc định. Mẫu Cẩm Giang có cấu hình độc lập và không kế thừa giá trị của Mao Điền.

## Chủ hộ và thành viên

Trình đọc thông báo dùng model `Person` của công cụ Chuẩn bị hồ sơ VBDLIS. Quy tắc xác định chủ hộ được giữ giống `HouseholdParser`: người đầu tiên sau dòng có STT hộ nhận `Person.is_head=True`; các tên tiếp theo khi STT hộ trống nhận `False`. Chỉ các phần tử có `is_head=False` được đưa vào bảng trang 3 của mẫu Cẩm Giang.

Số thông báo và ngày thông báo ở trang đầu và trang 3 dùng chung các placeholder `SO_TB`, `NGAY`, `THANG`, `NAM`. Một bộ giá trị được kết xuất cho cả hai vị trí.
