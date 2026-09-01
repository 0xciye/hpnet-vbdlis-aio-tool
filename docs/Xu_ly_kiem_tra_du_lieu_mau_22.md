# HƯỚNG DẪN KIỂM TRA DỮ LIỆU & XỬ LÝ TÌNH HUỐNG (MẪU 22)
*Tài liệu này mô tả chi tiết cách phần mềm Tạo Thông Báo Đất Đai liên tục bắt lỗi và xử lý các tình huống đặc biệt đối với dữ liệu Excel nguồn.*

---

## 1. Nguyên Tắc Cốt Lõi Về Chủ Hộ và Kế Thừa

Phần mềm dùng **Cột STT hộ** làm căn cứ pháp lý để xác định *Chủ hộ*.
- **Chỉ dòng nào có giá trị STT hộ (là số nguyên dương)** mới được xác lập là một "Hộ mới".
- **Tên hộ và Giấy tờ nhân thân (CCCD/CMND)** chỉ được đọc trên dòng có STT hộ.
- Các dòng bên dưới nếu bỏ trống STT hộ sẽ được coi là **Các thửa đất của cùng một hộ** (hoặc dòng của thành viên). Phần mềm sẽ **Tự động thừa kế** Tên Chử Hộ và CCCD/CMND từ dòng có STT gần nhất phía trên.
- Nếu dòng không có STT nhưng lại ghi tên người khác/CCCD của người khác (dòng Thành viên), phần mềm sẽ **Bỏ qua** Tên/CCCD đó và giữ nguyên quyền thừa kế của Chủ Hộ chính nhằm tránh làm sai lệch pháp lý.

---

## 2. Các Tình Huống Lỗi Và Cách Trình Bày

Dưới đây là các kịch bản thường gặp khi lập bảng Excel và cách phần mềm ứng xử:

### Tình huống 1: Dòng thành viên / Thửa thứ hai
**Mô tả:** Hộ [Nguyễn Văn A] có 2 thửa. Dòng 1 ghi đủ STT, Tên, CCCD. Dòng 2 chỉ ghi tên "Nguyễn Thị B" (vợ) và CCCD của vợ, bỏ trống STT.
- **Hệ thống xử lý:** TRẠNG THÁI: `HỢP LỆ`. 
- Thửa của dòng 2 sẽ tự động mang tên "Nguyễn Văn A" và CCCD của Nguyễn Văn A. Thông tin của "Nguyễn Thị B" bị bỏ qua để bảo vệ tính nhất quán toàn vẹn của file Thông báo.

### Tình huống 2: STT bị lỗi báo công thức `#REF!`
**Mô tả:** Trong quá trình copy/paste Excel, cột STT hoặc Tên hộ bị lỗi `#REF!`, `#VALUE!`.
- **Hệ thống xử lý:** TRẠNG THÁI: `LỖI DỮ LIỆU`.
- Hệ thống lập tức ngắt toàn bộ việc kế thừa dữ liệu cho tới tận khi gặp STT hợp lệ tiếp theo. Các dòng phía dưới sẽ báo lỗi: *"Không xác định được chủ hộ; không kế thừa tên của hộ phía trên"*.
- **Cách sửa:** Mở file Excel, tìm đến dòng bị lỗi, xóa công thức lỗi và gõ lại giá trị STT/Tên hộ bằng tay.

### Tình huống 3: Thiếu giấy tờ nhân thân (CCCD/CMND)
**Mô tả:** Dòng STT có Tên hộ, nhưng lại để trống Giấy tờ nhân thân. (Hoặc dòng STT để trống, cố tình ghi CCCD xuống dòng của vợ phía dưới).
- **Hệ thống xử lý:** TRẠNG THÁI: `THIẾU DỮ LIỆU`. 
- Báo lỗi: *"Thiếu giấy tờ nhân thân tại dòng X. Chọn đúng cột và bổ sung giấy tờ của hộ này; không lấy giấy tờ của hộ trước"*. (Hệ thống tuyệt đối **không** dùng tạm CCCD của hộ bên trên để đắp vào hộ bên dưới).

### Tình huống 4: Trùng Tờ / Thửa
**Mô tả:** Nhiều dòng có cùng chung "Tờ BĐ mới" và "Thửa BĐ mới" (Ví dụ: đồng thừa kế nhưng vô tình bị lặp dữ liệu thành 2 dòng riêng).
- **Hệ thống xử lý:** TRẠNG THÁI: `TRÙNG TỜ/THỬA`.
- Hệ thống sẽ **từ chối toàn bộ nhóm này** (không xuất file nào thay vì xuất đè lên nhau, và không tiêu thụ số thông báo).
- **Cách sửa:** Nhấp đúp vào Chi tiết trên UI để xem các dòng bị trùng. Xóa dòng thừa trong Excel.

### Tình huống 5: Dòng trống hoặc Dòng bẳng Tổng cộng
**Mô tả:** Trong bảng có các dòng tính tổng (Ví dụ: "Tổng DT", "Cộng") hoặc các dòng trống trơn ngắt cách giữa các trang.
- **Hệ thống xử lý:** TỰ ĐỘNG BỎ QUA. 
- Hệ thống thông minh tự nhận diện các từ khóa chỉ tính chất tính toán (Tổng cộng, Tổng, Cộng...) và sẽ loại bỏ vĩnh viễn khỏi danh sách tính, hoàn toàn không ảnh hưởng tới tiến trình kế thừa STT hộ.

### Tình huống 6: Thiếu Tờ, Thửa, Diện tích
**Mô tả:** Hộ có đầy đủ STT, Tên, nhưng thiếu Diện tích quy chủ.
- **Hệ thống xử lý:** TRẠNG THÁI: `THIẾU DỮ LIỆU`. Lỗi cụ thể sẽ chỉ điểm dòng lỗi trong file Excel để người dùng nhập bù.

---

## 3. Nhật Ký Xử Lý (Logs) Quyền Năng Và Số Thông Báo

- Hệ thống bảo vệ **Số Thông Báo** 100%. Nếu file bị trùng thửa, thiếu dữ liệu, lỗi tên thì Số Thông báo *sẽ không bị cấp dư ra (tiêu hao)*. Số dư (Number) đó được tự động đẩy cho hộ hợp lệ tiếp theo.
- Kể cả khi quá trình xuất Word đang diễn ra bị gián đoạn giữa chừng do Hết dung lượng ổ đĩa, Quyền Write (Permission Access), thì Số Thông báo cũng không bị mất.
- Kết quả tạo ở cuối phiên sẽ xuất ra **Nhật ký TXT** và **Nhật ký Bảng Excel** (màu xanh navy) mô tả đầy đủ: Dòng số mấy trên Excel, Trạng thái, Số được cấp, Tên File Word và Lý do lỗi chi tiết để kiểm tra chéo (Ctrl + G để nhảy đến đúng dòng).
