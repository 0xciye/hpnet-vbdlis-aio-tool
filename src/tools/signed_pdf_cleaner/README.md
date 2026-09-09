# HPNet - Lọc & Đổi tên văn bản đã ký

Ứng dụng giúp bạn tự động dọn dẹp các thư mục chứa nhiều phiên bản PDF của cùng một văn bản.
Ứng dụng sẽ xóa file có hậu tố cần bỏ và đổi tên file có hậu tố cần giữ về tên gốc sạch (chỉ còn `.pdf`).

## Cách sử dụng:

1. **Mở app**: Chạy file `Signed PDF Cleaner.exe` (trong thư mục `dist\Signed PDF Cleaner\`).
2. **Chọn folder**: Nhấn nút "Chọn..." để duyệt tới thư mục chứa các file PDF, hoặc bạn có thể kéo thả thư mục vào giao diện ứng dụng.
3. **Cấu hình (Tùy chọn)**:
   - "Bao gồm thư mục con": Tích vào nếu bạn muốn quét cả các thư mục nằm bên trong thư mục đã chọn.
   - "Hậu tố file cần xóa": Nhập một hoặc nhiều hậu tố, ngăn cách bằng dấu phẩy. Ví dụ: `.signed, .ldsigned`.
   - "Hậu tố file cần đổi tên": Nhập các hậu tố của bản muốn giữ lại. Ví dụ: `.signed.signed, .ldsigned.signed`.
     Phần mềm tự thêm `.pdf` nếu bạn bỏ qua phần mở rộng này. Các hậu tố ở hai ô được ghép theo tên tương ứng; vì vậy `.signed.signed.pdf` sẽ thay cho `.signed.pdf` rồi được đổi tên thành `TênGốc.pdf`, còn `.ldsigned.signed.pdf` sẽ thay cho `.ldsigned.pdf` rồi được đổi tên thành `TênGốc.pdf`.
   - "Chế độ xóa": Mặc định là chuyển file chưa ký vào **Recycle Bin (Thùng rác)** để có thể khôi phục lại khi cần. Bạn cũng có thể chọn Xóa vĩnh viễn (sẽ có cảnh báo).
4. **Nhấn Quét**: Nhấn nút "Quét / Xem trước" để ứng dụng phân tích dữ liệu. Chưa có file nào bị tác động ở bước này.
5. **Kiểm tra Preview**: Xem danh sách các file sẽ được xử lý tại bảng hiển thị bên dưới. 
   - Những cặp file hợp lệ sẽ có trạng thái "Sẵn sàng". 
   - Những file PDF đơn độc (không có bản signed) sẽ có trạng thái "Bỏ qua".
6. **Nhấn Xử lý**: Nhấn "Thực hiện xử lý" để bắt đầu dọn dẹp thư mục.
7. **Kiểm tra kết quả**: Sau khi hoàn thành, ứng dụng sẽ thông báo. Bạn có thể mở thư mục để kiểm tra, hoặc nhấn "Xuất log CSV" để lưu lại báo cáo. Toàn bộ lịch sử các phiên cũng được lưu trong thư mục `logs/` ngay cạnh file ứng dụng.

## Lưu ý An toàn (Quy tắc hoạt động):
- Ứng dụng **chỉ** xóa file cần bỏ khi đã tìm thấy file có hậu tố cần đổi tên tương ứng trong cùng thư mục.
- Khi bật kiểm tra chữ ký, file có hậu tố cần đổi tên phải là PDF đọc được và có trường chữ ký nhúng; nếu chỉ đổi tên file thường, ứng dụng sẽ cảnh báo và bỏ qua.
- Công cụ chưa xác minh chuỗi chứng thư, thời hạn hoặc hiệu lực pháp lý của chữ ký số.
- Nếu chỉ tồn tại bản chưa ký, ứng dụng sẽ **không xóa** (bỏ qua).
- Nếu chỉ tồn tại file cần đổi tên, ứng dụng vẫn đổi tên file về tên gốc sạch, không còn các hậu tố đã cấu hình.
- Tuyệt đối không chạm vào các định dạng file khác ngoài PDF (như Word, Excel, ảnh...).

---
*(Phần mềm được phát triển bởi Antigravity)*
