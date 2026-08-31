# HPNet - Lọc & Đổi tên văn bản đã ký

Ứng dụng giúp bạn tự động dọn dẹp các thư mục chứa cả file văn bản PDF gốc (chưa ký) và bản đã ký số (`.signed.pdf`).
Ứng dụng sẽ xóa bản chưa ký và đổi tên bản đã ký trở về tên chuẩn ban đầu.

## Cách sử dụng:

1. **Mở app**: Chạy file `Signed PDF Cleaner.exe` (trong thư mục `dist\Signed PDF Cleaner\`).
2. **Chọn folder**: Nhấn nút "Chọn..." để duyệt tới thư mục chứa các file PDF, hoặc bạn có thể kéo thả thư mục vào giao diện ứng dụng.
3. **Cấu hình (Tùy chọn)**:
   - "Bao gồm thư mục con": Tích vào nếu bạn muốn quét cả các thư mục nằm bên trong thư mục đã chọn.
   - "Chế độ xóa": Mặc định là chuyển file chưa ký vào **Recycle Bin (Thùng rác)** để có thể khôi phục lại khi cần. Bạn cũng có thể chọn Xóa vĩnh viễn (sẽ có cảnh báo).
4. **Nhấn Quét**: Nhấn nút "Quét / Xem trước" để ứng dụng phân tích dữ liệu. Chưa có file nào bị tác động ở bước này.
5. **Kiểm tra Preview**: Xem danh sách các file sẽ được xử lý tại bảng hiển thị bên dưới. 
   - Những cặp file hợp lệ sẽ có trạng thái "Sẵn sàng". 
   - Những file PDF đơn độc (không có bản signed) sẽ có trạng thái "Bỏ qua".
6. **Nhấn Xử lý**: Nhấn "Thực hiện xử lý" để bắt đầu dọn dẹp thư mục.
7. **Kiểm tra kết quả**: Sau khi hoàn thành, ứng dụng sẽ thông báo. Bạn có thể mở thư mục để kiểm tra, hoặc nhấn "Xuất log CSV" để lưu lại báo cáo. Toàn bộ lịch sử các phiên cũng được lưu trong thư mục `logs/` ngay cạnh file ứng dụng.

## Lưu ý An toàn (Quy tắc hoạt động):
- Ứng dụng **chỉ** xóa file bản chưa ký khi đã tìm thấy bản `.signed.pdf` tương ứng trong cùng thư mục.
- Nếu chỉ tồn tại bản chưa ký, ứng dụng sẽ **không xóa** (bỏ qua).
- Nếu chỉ tồn tại bản đã ký (file có đuôi `.signed.pdf`), ứng dụng vẫn sẽ đổi tên bỏ đi đuôi `.signed` thành tên gốc bình thường.
- Tuyệt đối không chạm vào các định dạng file khác ngoài PDF (như Word, Excel, ảnh...).

---
*(Phần mềm được phát triển bởi Antigravity)*
