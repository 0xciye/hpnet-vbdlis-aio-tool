# HPNet Parcel File Builder (Excel File Generator)

Phần mềm chuyên dụng để tự động nhân bản và đổi tên file PDF/DOCX hàng loạt dựa trên dữ liệu thửa đất trích xuất từ file Excel.

## Các tính năng chính
- Tự động lấy tên file (VD: `1. Nguyễn Văn A.pdf`), làm sạch và đối chiếu với dữ liệu Excel.
- Hỗ trợ nhân bản file thông minh: Nếu một hộ dân có 3 thửa đất, file gốc sẽ được nhân bản thành 3 file riêng biệt.
- Xử lý xung đột chuyên nghiệp: Không bao giờ ghi đè file cũ. Các file bị trùng tên sẽ được đưa vào thư mục an toàn `CONFLICT`.
- Tùy chỉnh tên đầu ra: Cung cấp hệ thống Template linh hoạt `{PREFIX}_{MA_DVHC}_{SO_TO}_{SO_THUA}-{HAU_TO}`.
- Tự động bỏ qua các thửa đất dùng chung giữa nhiều hộ khác nhau để tránh trùng lặp.

## Hướng dẫn sử dụng:
1. **Dữ liệu Excel**: Chọn file Excel, chọn Sheet và nhập dòng bắt đầu của tiêu đề. Phần mềm tự nhận diện tiêu đề một hoặc hai tầng, kể cả ô gộp, sau đó gợi ý các cột cần dùng.
2. **File Nguồn**: Chọn thư mục chứa file PDF/DOCX gốc (tên file tương ứng với họ tên).
3. **Ánh xạ & Match**: Chọn các cột tương ứng (Họ Tên, Số Tờ, Số Thửa) từ Excel. Bấm *Phân tích Match* để xem trước kết quả ánh xạ.
4. **Tên File & Output**: Nhập Prefix, Mã ĐVHC, và chọn hậu tố (TBXN/DDK...). Chọn thư mục đích (Output).
5. **Kiểm tra & Tạo**: Bấm *Xem trước* để kiểm tra Action Plan, cuối cùng bấm *Tạo File*.

## Nguyên tắc An toàn
- Phần mềm **KHÔNG** làm thay đổi bất kỳ file nào trong thư mục gốc. Mọi file được tạo ra đều là bản copy an toàn.
- Nếu bạn thấy có file nằm trong thư mục `CONFLICT`, hãy kiểm tra lại bằng tay do có khả năng dữ liệu đầu vào bị trùng lặp.
