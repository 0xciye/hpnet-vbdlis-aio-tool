# VBDLIS Excel Builder

## Bàn giao bản đã dọn

- Gửi người dùng file `release/VBDLIS Excel Builder Windows x64 2026.08.31-logs.zip`.
- Giải nén toàn bộ ZIP vào thư mục mới; giữ `_internal` bên cạnh EXE.
- Các thư mục `config`, `core`, `models`, `ui`, `utils`, `resources`, `tests`,
  `tools` và `docs` là mã nguồn, tài nguyên và tài liệu phục vụ phát triển/build lại.
- Môi trường ảo, cache, kết quả thử nghiệm và build trung gian không cần gửi kèm.
- `outputs` chứa dữ liệu xuất riêng của người dùng; KHÔNG đưa vào ZIP phần mềm.

Để build lại từ source sạch, cài Python 3.14 x64 và chạy lần lượt (bước cài
thư viện cần Internet; bản EXE vẫn hoạt động offline):

```powershell
.\build.bat
.\.venv314\Scripts\python.exe tools\create_user_guide.py
.\tools\package_release.ps1
```

`build.bat` tự tạo lại `.venv314`. Script đóng gói sẽ tạo ZIP, giải nén thử,
đối chiếu file, kiểm tra khởi động và icon Windows.

Ứng dụng desktop Windows nhận file nguồn có cấu trúc linh hoạt và tạo workbook `.xlsx` tương thích với cấu trúc đã chạy thành công của `GOLDEN_SUCCESS_REFERENCE`. Bản build hoạt động offline; template chính thức được bundle trong thư mục `resources` và không bao giờ bị ghi đè.

Ứng dụng **không đăng nhập, không kết nối và không tự upload lên VBDLIS**. Người dùng kiểm tra file kết quả rồi upload thủ công theo quy trình của đơn vị.

Người dùng không chuyên nên mở tài liệu `HƯỚNG DẪN SỬ DỤNG.pdf` nằm ngay trong gói phát hành trước khi chạy lần đầu.

## Cách sử dụng

1. Tab **Dữ liệu**: chọn workbook, sheet và dòng header; kiểm tra preview nguồn.
2. Tab **Ánh xạ**: chọn cột cho STT hộ, người, thửa và GCN. Nút tự động chỉ điền gợi ý có confidence cao.
3. Tab **Cấu hình VBDLIS**: nhập mã xã, địa chỉ, prefix, role, fallback và GCN mode; lưu profile theo xã/đơn vị.
4. Tab **Mapping nâng cao**: sửa mode của từng field (`Source`, `Fixed`, `Computed`, `Keep Template`, `Blank`, `Conditional`).
5. Tab **Kiểm tra & Xuất**: chạy validation, xem output sau transformation, chọn tên/thư mục và tạo file.

ERROR chặn export. WARNING vẫn cho phép export. Trạng thái chưa có GCN trong chế độ tự động chỉ được thống kê, không phát hàng loạt cảnh báo.

## Rule mặc định quan trọng

- Người trên dòng bắt đầu hộ là `Chủ hộ`; các người sau là `Thành viên hộ gia đình`.
- Mỗi hộ sinh `số người × số thửa hợp lệ` dòng; STT chạy liên tục 1 → N.
- Bỏ qua dòng tổng hợp như `Tổng DT`, `Tổng diện tích`, `Tổng cộng` trong cột tên
  (hoặc cột STT khi tên trống), nếu dòng đó không có CCCD/ngày sinh. Không tạo
  người hoặc thửa từ dòng tổng hợp; báo số dòng đã bỏ qua trong kết quả kiểm tra.
- Nếu file có tiêu đề nhiều hàng, chọn hàng tiêu đề cuối để dữ liệu bắt đầu ở
  hàng tiếp theo; ánh xạ theo chữ cột khi ô tiêu đề bị trống do gộp ô.
- Mục 2: `{PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}`.
- Mục 49: `{PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}-TBXN.pdf, {PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}-DDK.pdf`.
- Mặc định tự động bỏ cả hộ thiếu họ tên/CCCD hoặc dữ liệu thửa bắt buộc; CCCD
  có giá trị nhưng sai 12 chữ số thì bỏ riêng người. Không đổi dữ liệu nguồn.
  Có thể tắt tùy chọn này ở Tab 3 để quay về chế độ kiểm tra dừng khi thiếu.
- Giới tính: CCCD đủ 12 số có số thứ 4 là `0` thì Nam, `1` thì Nữ; còn lại trống.
- Thiếu Xứ đồng mặc định dùng địa chỉ profile; dữ liệu Xứ đồng hợp lệ luôn được ưu tiên.
- GCN nằm trên từng thửa; không tạo số/ngày/loại GCN giả.

## Phân tích và kiểm thử

- `docs/template-analysis.md`: so sánh official template và golden reference.
- `config/template_schema.json`: schema 61 field và phân loại machine-readable.
- `tools/analyze_workbooks.py`: tái tạo hai file trên từ workbook thật.
- `tests`: unit tests, edge cases và golden regression.

Chạy test:

```bat
.venv314\Scripts\python.exe -m unittest discover -s tests -v
```

## Build EXE

Chạy `build.bat`. Script tạo môi trường riêng, cài dependency, chạy toàn bộ test, build PyInstaller one-folder/no-console, kiểm tra PE Subsystem và launch smoke-test. File bàn giao:

```text
dist\VBDLIS Excel Builder\VBDLIS Excel Builder.exe
```

Golden reference chỉ dùng cho test phát triển và không được bundle vào `dist`.

Gói ZIP chia sẻ nằm trong `release` và có hậu tố phiên bản. Người nhận phải giải nén toàn bộ ZIP; không chạy hoặc gửi riêng file EXE.

## Dữ liệu ứng dụng

Profile và log runtime được lưu tại `%APPDATA%\VBDLIS Excel Builder`. Không lưu tài khoản, mật khẩu, token hoặc cookie.

Mỗi lần kiểm tra và xuất đều lưu báo cáo HTML/TXT tại `logs/kiem_tra`, kể cả khi
chưa xuất được Excel. Bấm **Mở báo cáo lỗi** ở Tab 5 để xem ô cần sửa, giá trị,
nguyên nhân, ảnh hưởng và cách xử lý. Báo cáo không cắt bớt lỗi lặp; app.log
dành cho hỗ trợ kỹ thuật, xoay vòng 5 MB × tối đa 6 file.
Xem `docs/DIAGNOSTIC_GUIDE.txt` cho quy tắc bỏ qua và bảo mật dữ liệu báo cáo.
