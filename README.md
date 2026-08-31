# HPNet VBDLIS AIO Tool

Bộ công cụ desktop dành cho Windows, hỗ trợ chuẩn bị hồ sơ đất đai, tạo dữ liệu VBDLIS và xử lý văn bản trên HPNet trong một giao diện khởi chạy thống nhất.

Dự án kết hợp các ứng dụng xử lý Excel, Word, PDF và tự động hóa trình duyệt. Mỗi công cụ có quy trình nghiệp vụ và cấu hình riêng; launcher cung cấp điểm truy cập chung và hướng dẫn tích hợp.

## Tính năng

| Công cụ | Chức năng chính |
| --- | --- |
| Tạo thông báo đất đai | Tạo Word theo Mẫu 22 từ Excel; kiểm tra dữ liệu, xem trước, cấp số thông báo và xuất nhật ký. |
| VBDLIS Excel Builder | Ánh xạ cột, xử lý hộ/người/thửa, cấu hình quy tắc và xuất Excel theo biểu mẫu VBDLIS. |
| Auto Rename | Đối chiếu dữ liệu Excel để nhân bản và đặt tên PDF/Word theo thông tin thửa đất. |
| PDF Cleaner | Ghép cặp PDF thường và `.signed.pdf`, dọn bản thường và chuẩn hóa tên file. |
| HPNet PDF Downloader | Lọc Văn bản đi, quét nhiều trang, tải PDF và ghi báo cáo đối soát. |
| HPNet Upload dự thảo | Tải Word lên HPNet, chọn người duyệt và kiểm tra trùng. |
| HPNet Duyệt dự thảo | Quét, xác nhận danh sách và chuyển duyệt văn bản theo người nhận đã chọn. |

Launcher hỗ trợ tìm kiếm công cụ và đọc hướng dẫn ngay trong ứng dụng. Các công cụ xử lý hồ sơ có bước kiểm tra/xem trước trước khi xuất; thao tác HPNet sử dụng phiên đăng nhập VNeID của người vận hành.

**Phạm vi hiện tại:** PDF Downloader nhận tên theo mẫu CHUACOGIAY và ngoại lệ thiếu mã xã. Chế độ tải theo hậu tố tên file đang ở giai đoạn lập kế hoạch, chưa được triển khai. PDF Cleaner nhận diện theo hậu tố tên, **không xác thực chữ ký số** bên trong tài liệu.

## Công nghệ

- **Python / PySide6:** launcher và các ứng dụng xử lý hồ sơ.
- **openpyxl, ReportLab, pypdf:** xử lý dữ liệu và tài liệu.
- **PowerShell / Node.js / Playwright:** các công cụ HPNet.
- **PyInstaller:** đóng gói ứng dụng Windows.

## Cài đặt bản phát hành

Tải `HPNet VBDLIS AIO Tool.zip` tại mục **Releases**, giải nén toàn bộ rồi chạy `HPNET & VBDLIS Tools.exe`. Giữ thư mục `_internal` cạnh EXE; máy sử dụng không cần Python.

Ba công cụ HPNet cần Microsoft Edge, kết nối mạng và tài khoản có quyền phù hợp. Word hoặc ứng dụng tương thích DOCX cần thiết để đọc bản xem trước, nhưng không bắt buộc cho bước tạo Word.

Hướng dẫn nghiệp vụ nằm trong mục **Hướng dẫn sử dụng** của launcher, truy cập bằng **F1**.

## Phát triển từ source

### Yêu cầu

- Windows x64.
- Python 3.14 và PowerShell.
- Microsoft Edge để sử dụng các công cụ HPNet.
- Runtime HPNet từ bản phát hành tương ứng với phiên bản source.

### 1. Cài môi trường Python

Sau khi clone repository, mở PowerShell tại thư mục gốc:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r docs\REQUIREMENTS_BUILD.txt
```

Phụ thuộc ứng dụng được khai báo trong `docs/REQUIREMENTS.txt`; phụ thuộc kiểm thử và đóng gói nằm trong `docs/REQUIREMENTS_BUILD.txt`.

### 2. Khôi phục runtime HPNet

Repository không chứa runtime Node/Playwright hoặc EXE biên dịch. Giải nén bản release cùng phiên bản, sau đó chạy:

```powershell
.\tools\restore_runtime.ps1 -ReleaseFolder 'C:\Tools\HPNET & VBDLIS Tools'
```

Thay đường dẫn ví dụ bằng thư mục chứa EXE và `_internal` của bản release. Script phục hồi runtime cùng ba EXE khởi chạy HPNet, không nhập cấu hình cá nhân, nhật ký hoặc phiên đăng nhập. File đã tồn tại với nội dung khác sẽ không bị ghi đè.

Runtime của bản hiện tại dùng Node 24.19.0 và Playwright 1.62.1. Bước khôi phục cần thiết để chạy đủ bảy công cụ, bộ test tích hợp và build bản đầy đủ. Nếu không có gói release tương ứng, chưa thể tái tạo đầy đủ các thành phần nhị phân chỉ từ repository này.

### 3. Chạy launcher

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
.\.venv\Scripts\python.exe -X utf8 src\launcher.py
```

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -X utf8 run_tests.py
```

Bộ test bao gồm kiểm thử các ứng dụng Python, hồi quy giao diện và tích hợp launcher. Workbook tham chiếu riêng có thể được cung cấp qua `NOTICE_REAL_WORKBOOK` và `VBDLIS_GOLDEN_WORKBOOK`; không đưa dữ liệu nghiệp vụ thật vào repository.

Các kiểm thử ngoại tuyến không thực hiện tải lên hoặc duyệt trên HPNet thật, và không thay thế kiểm thử tích hợp với hệ thống HPNet.

## Build bản Windows

Sau khi cài dependencies và phục hồi runtime:

```powershell
.\build_release.ps1
```

Script chạy kiểm thử, đóng gói PyInstaller, kiểm tra EXE/tài nguyên và tạo ZIP:

```text
release/
└── HPNet VBDLIS AIO Tool.zip
```

ZIP chỉ chứa ứng dụng và tài nguyên cần chạy; không kèm source test, môi trường phát triển hoặc phiên đăng nhập. ZIP release trước được chuyển vào Thùng rác sau khi gói mới kiểm tra đạt. Thư mục build theo phiên bản được giữ riêng.

Có thể chỉ định nhãn thư mục build bằng `-ReleaseId`; tên ZIP công khai vẫn cố định. Các file `.spec`, mẫu Word/Excel và tài nguyên giao diện phải được giữ để build thành công.

## Cấu trúc dự án

```text
src/
  launcher.py                   # Điểm vào ứng dụng
  launcher_ui/                  # Giao diện launcher và hướng dẫn
  tools/                        # Bốn ứng dụng Python
  nodes_tools/                  # Ba công cụ HPNet
  HPNET_VBDLIS_Tools.spec        # Cấu hình PyInstaller
tests/                          # Kiểm thử tích hợp
tools/                          # Tiện ích phát triển và phục hồi runtime
docs/                           # Dependencies, hướng dẫn và kế hoạch phát triển
research/notice_template22/      # Mẫu đối chiếu phục vụ test bảo toàn định dạng
run_tests.py
build_release.ps1
```

## Dữ liệu và phạm vi sử dụng

- Không đưa hồ sơ cá nhân, CCCD, khóa ký số, token, log nghiệp vụ hoặc phiên VNeID vào repository.
- Kiểm tra dữ liệu, người nhận và phạm vi tài khoản trước khi thực hiện nghiệp vụ; sao lưu trước các thao tác dọn file.
- Mẫu tài liệu và kết quả xuất cần được người phụ trách nghiệp vụ kiểm tra trước khi sử dụng.
- Dự án chưa khai báo giấy phép riêng trong repository. Các phụ thuộc bên thứ ba giữ giấy phép tương ứng.
