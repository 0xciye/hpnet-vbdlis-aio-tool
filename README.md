# HPNet VBDLIS AIO Tool

Bộ công cụ desktop dành cho Windows, hợp nhất các quy trình chuẩn bị hồ sơ đất đai, tạo dữ liệu VBDLIS và hỗ trợ xử lý văn bản trên HPNet trong một giao diện duy nhất.

Ứng dụng được thiết kế cho người dùng nghiệp vụ: mỗi công cụ có hướng dẫn tích hợp, bước kiểm tra trước khi xuất hoặc thao tác thật, nhật ký dễ đối soát và phạm vi dữ liệu tách biệt. Bản phát hành là gói portable; máy sử dụng không cần cài Python hay Node.js.

## Thành phần

| Nhóm | Công cụ | Chức năng chính |
| --- | --- | --- |
| Hồ sơ đất đai | **Tạo thông báo đất đai** | Đọc Excel, kiểm tra dữ liệu, xem trước và tạo Word theo Mẫu 22; hỗ trợ cấp số thông báo và xuất nhật ký. |
| Dữ liệu VBDLIS | **VBDLIS Excel Builder** | Ánh xạ cột, xử lý hộ/người/thửa, kiểm tra quy tắc nghiệp vụ và xuất Excel theo biểu mẫu VBDLIS. |
| Quản lý tệp | **Auto Rename** | Đối chiếu Excel để nhân bản và đặt tên PDF/Word theo thông tin thửa đất. |
| Quản lý PDF | **PDF Cleaner** | Ghép cặp PDF thường với bản có hậu tố ký, dọn bản thường và chuẩn hóa tên file. |
| HPNet | **HPNet PDF Downloader** | Lọc hoặc quét toàn bộ Văn bản đi được quyền xem, tải PDF và tạo báo cáo đối soát. |
| HPNet | **HPNet Upload dự thảo** | Tải Word lên HPNet, chọn người duyệt, kiểm tra trùng và hỗ trợ chạy thử trước khi thao tác thật. |
| HPNet | **HPNet Duyệt dự thảo** | Quét danh sách, xác nhận điều kiện và chuyển duyệt văn bản theo người nhận đã chọn. |

Launcher hỗ trợ tìm kiếm công cụ, mở hướng dẫn bằng phím **F1** và hiển thị trạng thái khởi chạy. Ba công cụ HPNet dùng chung một bộ Node.js/Playwright để giảm dung lượng release và tránh đóng gói trùng lặp.

## Điểm nổi bật

- Một giao diện thống nhất cho bảy công cụ nghiệp vụ.
- Bản Windows portable, không yêu cầu cài Python hoặc Node.js trên máy sử dụng.
- Kiểm tra và xem trước dữ liệu trước khi xuất hoặc thực hiện thao tác HPNet.
- Mẫu Word được chuẩn hóa cục bộ tại các dòng placeholder, giữ nguyên cấu trúc và định dạng pháp lý còn lại.
- Nhật ký TXT/CSV và đầu ra Node.js dùng UTF-8, tương thích tiếng Việt trên Windows.
- Runtime HPNet dùng chung nhưng cấu hình, nhật ký và phiên đăng nhập vẫn tách theo từng công cụ.
- Quy trình build tự chạy test, smoke test, kiểm tra tài nguyên và xác minh từng tệp trong ZIP trước khi công bố.

## Cài đặt bản phát hành

### Yêu cầu sử dụng

- Windows 10 hoặc Windows 11 x64.
- Microsoft Edge cho ba công cụ HPNet.
- Kết nối mạng và tài khoản có đúng quyền nghiệp vụ trên HPNet.
- Microsoft Word hoặc ứng dụng tương thích DOCX nếu cần mở bản xem trước/tài liệu đã tạo.

### Khởi chạy

1. Tải `HPNet VBDLIS AIO Tool.zip` từ trang [GitHub Releases](https://github.com/0xciye/hpnet-vbdlis-aio-tool/releases).
2. Giải nén **toàn bộ** ZIP vào một thư mục riêng.
3. Chạy `HPNET & VBDLIS Tools.exe`.
4. Giữ nguyên thư mục `_internal` bên cạnh file EXE.
5. Mở **Hướng dẫn sử dụng** trong ứng dụng hoặc nhấn **F1** trước khi dùng công cụ lần đầu.

Không chạy trực tiếp EXE bên trong cửa sổ xem ZIP vì ứng dụng cần các tài nguyên trong `_internal`.

## An toàn dữ liệu và đăng nhập

- Đăng nhập VNeID được thực hiện tương tác trực tiếp trong Microsoft Edge. Công cụ không yêu cầu người dùng cung cấp mật khẩu hoặc OTP cho mã nguồn/script.
- Phiên trình duyệt được lưu cục bộ trong thư mục riêng của từng công cụ để người vận hành chủ động quản lý. Thư mục này không được đưa vào source hoặc ZIP phát hành.
- Không commit hoặc chia sẻ hồ sơ cá nhân, CCCD, token, khóa ký số, cookies, nhật ký nghiệp vụ hay dữ liệu đăng nhập.
- Luôn kiểm tra dữ liệu đầu vào, người nhận, phạm vi tài khoản và danh sách xem trước trước khi xác nhận thao tác thật.
- Sao lưu dữ liệu trước các thao tác dọn, đổi tên hoặc ghi đè hàng loạt.

> **Lưu ý về PDF:** việc nhận diện `.signed`, `.ldsigned`, `.lsigned` hoặc hậu tố do người dùng chọn chỉ là lọc theo tên file. Chức năng này không xác thực chữ ký số nằm bên trong tài liệu PDF.

## Phát triển từ source

### Yêu cầu môi trường

- Windows x64.
- Python **3.14.x** và Python Launcher (`py`).
- Windows PowerShell 5.1 hoặc PowerShell 7.
- Microsoft Edge để kiểm tra các luồng HPNet.
- Runtime HPNet được khôi phục từ release sạch cùng phiên bản source.

### 1. Clone repository

```powershell
git clone https://github.com/0xciye/hpnet-vbdlis-aio-tool.git
Set-Location hpnet-vbdlis-aio-tool
```

### 2. Tạo môi trường Python 3.14

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r docs\REQUIREMENTS_BUILD.txt
```

Dependencies chạy ứng dụng nằm trong `docs/REQUIREMENTS.txt`; dependencies kiểm thử và đóng gói nằm trong `docs/REQUIREMENTS_BUILD.txt`. `build_release.ps1` kiểm tra phiên bản và dừng ngay nếu `.venv` không dùng Python 3.14.

### 3. Khôi phục runtime HPNet

Repository không lưu Node.js/Playwright portable hoặc các EXE launcher đã biên dịch. Giải nén release sạch cùng phiên bản, sau đó chạy:

```powershell
.\tools\restore_runtime.ps1 -ReleaseFolder 'C:\Tools\HPNET & VBDLIS Tools'
```

Thay đường dẫn ví dụ bằng thư mục chứa `HPNET & VBDLIS Tools.exe` và `_internal`. Script chỉ khôi phục runtime cùng ba launcher HPNet; không sao chép cấu hình cá nhân, nhật ký hoặc phiên đăng nhập. File đã tồn tại nhưng khác nội dung sẽ không bị ghi đè.

Runtime hiện tại sử dụng Node.js 24.19.0 và Playwright 1.62.1. Script hỗ trợ cả release mới dùng runtime chung và release cũ còn đặt một runtime trong từng công cụ.

### 4. Chạy từ source

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
.\.venv\Scripts\python.exe -X utf8 src\launcher.py
```

### 5. Chạy kiểm thử

```powershell
.\.venv\Scripts\python.exe -X utf8 run_tests.py
```

Các workbook tham chiếu riêng có thể được khai báo qua `NOTICE_REAL_WORKBOOK` và `VBDLIS_GOLDEN_WORKBOOK`. Không đưa dữ liệu nghiệp vụ thật vào repository.

Bộ test ngoại tuyến không tải lên, tải xuống hoặc duyệt văn bản thật trên HPNet. Việc kiểm thử live phải được thực hiện riêng bằng tài khoản và dữ liệu thử có quyền phù hợp.

## Build release Windows

Sau khi cài dependencies và khôi phục runtime:

```powershell
.\build_release.ps1
```

Có thể đặt nhãn riêng cho lần build:

```powershell
.\build_release.ps1 -ReleaseId 2026.09.01
```

Quy trình build thực hiện tuần tự:

1. Xác nhận `.venv` đang dùng Python 3.14.
2. Biên dịch ba launcher HPNet dạng Windows GUI.
3. Chạy toàn bộ test Python và kiểm tra ngoại tuyến.
4. Đóng gói bằng PyInstaller.
5. Chạy smoke test trên EXE đã đóng gói.
6. Đối chiếu tài nguyên, Node workers, PowerShell self-test và icon EXE.
7. Tạo ZIP và xác minh tên, số lượng, nội dung, hash của từng tệp.
8. Chỉ thay ZIP công khai sau khi mọi kiểm tra đạt.

Kết quả:

```text
release/
└── HPNet VBDLIS AIO Tool.zip
```

ZIP chỉ chứa ứng dụng và tài nguyên cần chạy; không kèm source test, môi trường phát triển, cấu hình đã sử dụng hoặc phiên đăng nhập. Script chỉ dọn thư mục trung gian của chính lần build hiện tại và giữ nguyên các thư mục lưu trữ do người dùng tạo, ví dụ `release\old build`.

Nếu phần mềm bảo mật cảnh báo nhầm PyInstaller hoặc Python chính thức, không nên tắt bảo vệ trên toàn máy. Hãy gửi yêu cầu false-positive, thêm đúng executable đã xác minh vào danh sách tin cậy hoặc build trên máy phát hành được quản lý riêng.

## Checklist trước khi phát hành

- Test suite hoàn tất không có lỗi.
- Smoke test của EXE trả về `PASS`.
- Ba Node worker qua `--check` và `--self-test`.
- PowerShell self-test của PDF Downloader đạt.
- ZIP giải nén được và không có entry trùng.
- ZIP không chứa `du_lieu_dang_nhap_vneid`, cookies, cấu hình đã dùng, log, PDF tải về hoặc dữ liệu nghiệp vụ.
- Thử mở launcher và bảy trang công cụ trên máy Windows sạch.
- Ghi nhận SHA-256 của ZIP trước khi tải lên GitHub Releases.

## Cấu trúc repository

```text
src/
  launcher.py                    # Điểm vào ứng dụng
  launcher_ui/                   # Giao diện launcher và hướng dẫn
  tools/                         # Bốn công cụ Python
  nodes_tools/                   # Ba công cụ HPNet và runtime cục bộ
  HPNET_VBDLIS_Tools.spec        # Cấu hình PyInstaller
tests/                           # Kiểm thử tích hợp
tools/                           # Build launcher và khôi phục runtime
docs/                            # Dependencies, hướng dẫn và tài liệu kỹ thuật
research/notice_template/        # Bằng chứng mẫu phục vụ regression test
run_tests.py                     # Điểm chạy test thống nhất
verify_release.py                # Kiểm tra thư mục/ZIP release
build_release.ps1                # Quy trình build Windows
```
- SHA-256 của `HPNet VBDLIS AIO Tool.zip`.
- Hướng dẫn sao lưu và nâng cấp cho người dùng hiện tại.
