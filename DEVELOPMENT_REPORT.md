# Development Report

Tài liệu này bổ sung lịch sử phát triển; không thay thế README hay các báo cáo phát hành trước đó.

# Duplicate Parcel Cleanup Tool

## Architecture

Tool nằm độc lập tại `src/tools/duplicate_parcel`, gồm models, service, report và UI. UI chỉ thu cấu hình, gọi worker/service và hiển thị change plan.

## Household Detection

Household là block dòng từ đầu vùng quét tới marker `Tổng DT`. Tên của từng thành viên không tạo ranh giới hộ.

## Total DT Detection

Marker được trim, collapse whitespace và so khớp không phân biệt hoa thường. Dòng marker không được đưa vào parcel index và được kiểm tra bảo vệ lần nữa trước khi clear.

## Duplicate Detection

Khóa parcel là cặp số tờ/số thửa đã chuẩn hóa có kiểm soát. `39`, `39.0` và chuỗi có khoảng trắng tương đương; `39.1`, `39/1` và `39A` vẫn khác nhau. Diện tích dùng `Decimal`; xứ đồng trim/collapse/casefold nhưng không bỏ dấu.

## Conflict Classification

Các trạng thái gồm `EXACT_DUPLICATE`, `SAME_PARCEL_DIFFERENT_AREA`, `SAME_PARCEL_DIFFERENT_LOCATION`, `SAME_PARCEL_DIFFERENT_AREA_AND_LOCATION`, `INCOMPLETE_DATA` và `CROSS_HOUSEHOLD_DUPLICATE`. Mọi dòng có cùng cặp Số tờ + Số thửa trên toàn bộ các hộ đều được gom vào một nhóm duplicate; nếu nhóm có 2, 3 hoặc 4 dòng thì cả nhóm được chọn clear mặc định, không giữ dòng đại diện.

## Cleanup Strategy

Scan không sửa nguồn. Sau confirm, tool tạo backup bắt buộc, chỉ gán `None` trong range cột cấu hình cho các dòng đã chọn, lưu file tạm, mở lại xác minh và mới finalize output. Không delete/shift row. Nguồn `.xlsm` chỉ được lưu thành `.xlsm` để giữ VBA.

## Tests

Test tổng hợp bao phủ nhiều thành viên trong hộ, nhiều dạng `Tổng DT`, exact/mixed/conflict/cross-household, thiếu dữ liệu, normalization, vùng clear, bảo vệ summary, backup, reopen và workbook report.

Synthetic end-to-end ngày 2026-09-06: quét 11 dòng thuộc 2 hộ, clear toàn bộ các dòng thuộc nhóm Số tờ + Số thửa bị trùng (kể cả khác hộ), giữ nguyên hai dòng `Tổng DT` 12/14, nguồn không đổi, backup/output/report đều mở lại thành công.

## Known Limitations

Marker hộ hiện được đọc từ cột Họ và tên đã chọn. Tool không tự suy đoán household nếu file thiếu marker `Tổng DT`.

# Name & Birthdate Normalizer

## Architecture

Tool độc lập tại `src/tools/data_normalizer`; không import hoặc gọi logic household/parcel. Name parser và date parser là các hàm thuần có thể test riêng.

## Name Normalization Rules

Trim/collapse mọi whitespace, NFC Unicode và title-case từng thành phần, kể cả tên có dấu gạch nối, apostrophe hoặc dấu chấm. Không bỏ dấu, không sửa chính tả và không xóa prefix/suffix.

## Date Parsing Rules

Hỗ trợ mode DMY, MDY, YMD và AUTO; output DD/MM/YYYY, DD-MM-YYYY hoặc YYYY-MM-DD. Date/datetime và serial có Excel date format được xử lý theo metadata workbook. Mặc định giữ kiểu date Excel và chỉ đổi number format cần thiết.

## Ambiguous Date Handling

AUTO không đoán chuỗi có ngày/tháng đều không vượt 12. Ngày không tồn tại, ngày thiếu và năm hai chữ số giữ nguyên, không được chọn apply mặc định. Formula và non-anchor merged cell được bảo vệ.

## Excel Date Handling

Numeric value chỉ được coi là serial khi number format của cell là date. Giá trị số thông thường được phân loại partial và giữ nguyên.

## Preview / Change Plan

Preview có before/after/status/warning, filter trạng thái và checkbox riêng cho từng thay đổi. Apply chỉ ghi những ô `CHANGE` vẫn được chọn.

## Tests

Test bao phủ uppercase/lowercase/whitespace/Unicode/tên ghép, DMY/YMD/AUTO, leap year, invalid/ambiguous/partial/two-digit year, Excel date, numeric non-date, formula, mode name-only/date-only, backup, reopen và report.

Synthetic end-to-end ngày 2026-09-06: đổi 3 tên và 2 ngày chắc chắn; giữ nguyên 1 ngày mơ hồ, 1 ngày lỗi, 1 ngày thiếu và 2 formula. Nguồn không đổi; backup/output/report đều mở lại thành công. Tất cả sheet output/report đã render và không còn tiêu đề/cảnh báo bị cắt.

## Known Limitations

Không có spell-check tên và không có rule suy diễn năm hai chữ số theo thiết kế an toàn. Tool chỉ xử lý một sheet trong mỗi lượt.

# Launcher Integration

## New Tool Entries

Launcher có hai card riêng: `Kiểm tra & Làm sạch thửa trùng` và `Chuẩn hóa Họ tên & Ngày sinh`. Mỗi card tạo và giữ một top-level window riêng.

## Shared Components

Hai tool dùng theme/icon system hiện hữu, `openpyxl` đã có, `tools.excel_safety` cho load/backup/atomic save và `tools.qt_worker` cho tác vụ nền.

## Regression Test

`run_tests.py`: 281 passed, 4 skipped (golden/private data không có trong checkout), 80 subtests passed. `verify_suite_ui.py`: PASS tại các viewport 900/1240/1600. Frozen smoke: PASS, nhận đủ 9 launcher entries và 6 Python windows; existing Notice Builder, Excel export, Auto Rename và PDF Cleaner smoke vẫn pass.

## Build Result

Build chính thức bằng Python 3.14.7 chạy hết test nhưng bị policy máy loại file PyInstaller executable ngay tại COLLECT (hai lần, exit code 5), nên không được ghi nhận là release chính thức. Fallback bằng Python 3.12.3 build thành công, frozen smoke PASS và `verify_release.py --zip` PASS: 426 files, 186 HPNet files khớp byte-for-byte, 3 Node self-tests, 2 PowerShell tests, icon/guides/runtime sạch. ZIP fallback sau synthetic end-to-end có SHA-256 `EE18671AB20FEA76F05566A50717EA52623E66466BC4DCC2F390720167A5397F`.

Known release limitation: gói đã kiểm chứng dùng Python 3.12 fallback, không thỏa policy Python 3.14 của `build_release.ps1`. Cần whitelist/khắc phục security policy đối với PyInstaller Python 3.14 rồi chạy lại pipeline chính thức trước khi coi đây là release production chuẩn.
