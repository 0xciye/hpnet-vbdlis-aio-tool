# Kiểm tra trước khi commit

## Giữ trong Git

- Mã Python, PowerShell, Node; test, script kiểm thử và file PyInstaller `.spec`.
- Icon/SVG/style, schema và cấu hình mặc định không chứa dữ liệu cá nhân.
- Ba mẫu Word/Excel ứng dụng và mẫu Word đối chiếu kèm `template-evidence.json` đã khai báo ngoại lệ trong `.gitignore`.
- README, ba TXT dùng cho hướng dẫn trong launcher, requirements và script phục hồi runtime.

## Chỉ giữ ở máy / GitHub Releases

- `.venv`, build, release, EXE, runtime Node/Playwright, cache.
- Phiên VNeID, `cau_hinh.json`, `profiles.json` của HPNet, lịch sử upload, log.
- Workbook nguồn/kết quả, Word/PDF đầu ra, thư mục review/research (trừ hai file đối chiếu test nói trên) và báo cáo rà soát nội bộ.

File bị ignore không có nghĩa bị xóa. Test và mẫu ứng dụng không phải rác.

## Sau clone

1. Cài Python/dependencies như README.
2. Tải release sạch cùng phiên bản và giải nén.
3. Chạy `tools/restore_runtime.ps1 -ReleaseFolder <thư mục chứa EXE và _internal>`.
4. Chạy `run_tests.py`, rồi `build_release.ps1` nếu cần đóng gói lại.

Không lấy runtime từ thư mục phần mềm đã dùng có phiên đăng nhập; script chỉ phục hồi runtime và EXE, không nhập cấu hình.

## Trước khi push

- Xem `git status --short --untracked-files=all`, sau đó `git diff --cached`.
- Không đưa dữ liệu thật, token, mật khẩu, chứng thư/khóa riêng vào source hoặc mẫu.
- Nếu trước đây đã track file nhạy cảm: `.gitignore` không tự gỡ khỏi lịch sử. Kiểm tra và xử lý riêng; không tự viết lại lịch sử repository.
- Nếu file mẫu mới cần commit, thêm ngoại lệ cụ thể sau khi xác nhận không có dữ liệu cá nhân, không mở toàn bộ `*.xlsx`/`*.docx`.
- Thư mục hiện tại chưa được tự `git init`, commit hoặc push; chủ repository tự thực hiện.
- PDF Cleaner giữ nguyên tính năng nhận diện theo tên `.signed.pdf`, không có kiểm tra chữ ký số.
