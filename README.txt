TÀI LIỆU HƯỚNG DẪN CÀI ĐẶT VÀ SỬ DỤNG - BỘ CÔNG CỤ HPNET & VBDLIS TOOLS
---
1. Yêu cầu chuẩn bị: Vui lòng giải nén toàn bộ tập tin ZIP này vào một thư mục cố định trên máy tính trước khi sử dụng.
2. Lưu ý hệ thống: KHÔNG sao chép hoặc di chuyển riêng tập tin "HPNET & VBDLIS Tools.exe" ra khỏi thư mục gốc (tập tin EXE phải được đặt cùng vị trí với thư mục _internal). Nếu cần tạo phím tắt tại màn hình Desktop phụ vụ truy cập nhanh, vui lòng nhấp chuột phải vào tập tin EXE -> Chọn thao tác "Send to" -> "Desktop (create shortcut)".
3. Khởi chạy: Nhấp đúp chuột vào tập tin "HPNET & VBDLIS Tools.exe".
4. Tại giao diện chính của phần mềm (Bảng điều khiển/Dashboard), cán bộ xử lý nhấp chọn công cụ tương ứng với nghiệp vụ lưu trữ, kết xuất tài liệu cần thiết.
5. Quy trình nghiệp vụ được giữ lại, nhưng cấu hình của bản riêng lẻ không phải lúc nào cũng tự chuyển sang. Xem docs/HUONG_DAN_BAN_SUA.txt về vị trí cấu hình và cách chuyển an toàn.
6. Kết quả kiểm chứng và giới hạn: docs/KIEM_TOAN_TICH_HOP.md. Không coi việc mở được cửa sổ là bằng chứng toàn bộ thao tác HPNet đã được chạy thật.
7. Build bản sửa bằng build_release.ps1. Sau khi bản mới kiểm tra đạt, script chuyển ZIP cũ và các thư mục build/release trung gian vào Thùng rác.
8. Công cụ Tạo thông báo có ảnh hai trang của mẫu Word chứa placeholder ngay ở bước Chọn file. Bấm “Mở ảnh mẫu để xem rõ” trước khi nhập các trường ở bước Thông tin thông báo.
9. Khung nhật ký của ba công cụ HPNet và các file TXT/CSV sử dụng UTF-8 để hiển thị đúng tiếng Việt.
10. Ở bước “Trang tính, tiêu đề và phạm vi xử lý” của công cụ Tạo thông báo, có thể nhập đủ dòng bắt đầu/dòng kết thúc để chỉ xử lý một phần Excel. Để trống cả hai ô sẽ xử lý toàn bộ như trước.
11. Khi chọn “Danh sách số”, có thể để trống ô Danh sách số rồi bấm “+ Thêm số hoặc khoảng số” để nhập trực tiếp các số còn thiếu cùng ngày áp dụng; các nhóm sẽ chạy theo thứ tự từ trên xuống. Nếu vẫn nhập Danh sách số theo cách cũ, nhóm ngày chỉ gán ngày riêng và số không có nhóm dùng ngày mặc định.
