# Kế hoạch: tải PDF theo hậu tố tên file

**Trạng thái:** đã triển khai và kiểm thử ngoại tuyến ngày 01/09/2026; chờ/đã đóng gói theo quy trình release của repository.

## 1. Mục tiêu và phạm vi

Cho phép tải PDF có tên bất kỳ, ví dụ `Kế Hoạch.signed.pdf`, theo hậu tố người dùng chọn. Không bắt buộc CHUACOGIAY, mã xã, số tờ/thửa hoặc TBXN trong chế độ mới. Giữ chế độ tên cũ và toàn bộ lựa chọn lọc/tải hiện có.

Chỉ thay đổi PDF Downloader, hướng dẫn liên quan và kiểm thử/đóng gói. Không sửa Upload, Duyệt, Excel Builder, Auto Rename, Tạo thông báo hay PDF Cleaner. Nhận diện `.signed` ở đây là lọc tên, không xác thực chữ ký số.

## 2. Hiện trạng cần xử lý

Trong `src/nodes_tools/Downloader/HPNet PDF Downloader - VNEID APP/`:

- `hpnet-downloader.cjs`: `buildValidPdfNamePattern()` cố định `CHUACOGIAY_...-TBXN.(signed|ldsigned|lsigned).pdf`.
- Mã xã được kiểm tra bắt buộc ngay khi đọc cấu hình, dù sau này chế độ hậu tố không cần mã xã.
- Điều kiện tên file được dùng ở nhiều chỗ: chọn tên khi trùng URL, lọc file hợp lệ, báo file sai mẫu và ghi ngoại lệ thiếu mã xã. Phải cập nhật đồng bộ, không chỉ sửa một regex.
- `buildFilters()` yêu cầu ít nhất một trong bốn bộ lọc: trích yếu, số thông báo, ký hiệu, ngày. UI PowerShell cũng chặn khi cả bốn tắt. Chỉ thêm hậu tố sẽ chưa đủ để tải toàn bộ file có hậu tố đó.
- `HPNet-PDF-Downloader.ps1`: đọc/lưu cấu hình phiên bản 3, hiển thị mẫu tên cũ và điều khiển bật/tắt các ô nhập.

## 3. Hành vi đề xuất

### A. Tách lọc văn bản và lọc tên tệp

Quyết định tải gồm hai bước độc lập: văn bản thuộc phạm vi đã chọn, sau đó tệp đính kèm khớp quy tắc tên.

**Phạm vi văn bản:**

1. **Theo bộ lọc:** giữ nguyên trích yếu, số thông báo, ký hiệu, ngày chính xác/khoảng ngày, trạng thái đã xem/chưa xem. AND giữa các nhóm bật; OR giữa nhiều giá trị trong một nhóm. Giữ yêu cầu có ít nhất một bộ lọc nội dung/ngày như hiện tại.
2. **Toàn bộ Văn bản đi được quyền xem:** lựa chọn chủ động mới, bỏ qua các bộ lọc văn bản, kể cả trạng thái đã/chưa xem. UI tạm vô hiệu hóa các ô lọc nhưng giữ giá trị để quay lại. Hiển thị xác nhận rõ phạm vi tải rộng trước khi chạy.

“Toàn bộ” vẫn chỉ là danh sách Văn bản đi tài khoản hiện tại được xem. Không đổi endpoint, không tự chuyển API sang `all=true`, không bao gồm dự thảo/upload hoặc mở rộng quyền truy cập.

### B. Hai chế độ tên file

| Chế độ | Quy tắc | Mã xã |
| --- | --- | --- |
| Mẫu hồ sơ CHUACOGIAY (hiện tại) | Giữ nguyên mẫu tên TBXN, các đuôi signed/ldsigned/lsigned và ngoại lệ thiếu mã xã | Giữ nguyên kiểm tra 5 chữ số và lựa chọn ngoại lệ |
| Theo hậu tố tên file (mới) | Tên bất kỳ kết thúc bằng hậu tố đã chọn, ngay trước `.pdf` | Không bắt buộc; vô hiệu hóa ô mã xã và ngoại lệ, không xóa giá trị đã lưu |

Chế độ cũ vẫn sẵn có, không bị thay thế bằng một mẫu tên mới.

### C. Quy tắc hậu tố

- Mặc định của chế độ mới: `.signed`. Có lựa chọn sẵn `.ldsigned`, `.lsigned` và ô nhập hậu tố khác; cho phép nhiều hậu tố, khớp một hậu tố là đủ.
- Chấp nhận nhập `signed`, `.signed` hoặc `.signed.pdf` và chuẩn hóa về `.signed`; bỏ khoảng trắng hai đầu, bỏ mục trùng, so sánh không phân biệt hoa/thường.
- Chỉ nhận file kết thúc `.pdf`. “Hậu tố” được hiểu là phần cuối tên ngay trước `.pdf`, không phải tìm chuỗi `.signed` ở bất kỳ vị trí nào.
- Tên tiếng Việt, khoảng trắng và Unicode được hỗ trợ; giữ nguyên tên hợp lệ khi lưu, không thêm CHUACOGIAY/mã xã.
- Dấu chấm có nghĩa ký tự thật. Không nhận regex, wildcard hoặc đường dẫn; chặn hậu tố rỗng, ký tự điều khiển, `/`, `\\`, `*`, `?`, `:`, tên chỉ gồm `.pdf` và danh sách không còn mục hợp lệ.
- Không có lựa chọn “mọi PDF” ngầm khi hậu tố rỗng. Báo lỗi để người dùng chọn lại.

Ví dụ khi chỉ chọn `.signed`:

| Tên file | Kết quả |
| --- | --- |
| `Kế Hoạch.signed.pdf` | Tải nếu văn bản thuộc phạm vi đã chọn |
| `Thông báo 01.SIGNED.PDF` | Tải |
| `CHUACOGIAY_10930_10_20-TBXN.signed.pdf` | Tải, không cần xử lý riêng tiền tố |
| `Kế Hoạch.pdf` | Bỏ qua: không khớp hậu tố |
| `Kế Hoạch.ldsigned.pdf` | Bỏ qua, trừ khi chọn thêm `.ldsigned` |
| `Kế Hoạch.signed.bak.pdf` | Bỏ qua: hậu tố không nằm ngay trước `.pdf` |
| `Kế Hoạch.signed.pdf.docx` | Bỏ qua: không phải tên PDF |
| `signed.pdf` | Bỏ qua: thiếu tên văn bản trước hậu tố `.signed` |

## 4. Tương thích cấu hình

Đề xuất nâng `configVersion` lên 4, bổ sung các trường sau vào cấu hình hiện có:

```json
{
  "configVersion": 4,
  "documentScope": "filtered",
  "fileNameMode": "legacy",
  "fileSuffixes": [".signed"]
}
```

- `documentScope`: `filtered` hoặc `all_visible`; `fileNameMode`: `legacy` hoặc `suffix`.
- Thiếu trường mới ở cấu hình cũ → `filtered` + `legacy`. Không tự đổi sang tải toàn bộ hoặc thay tập file được tải.
- Cài mới cũng khởi đầu với phạm vi có lọc; người dùng chủ động chọn hậu tố hoặc tải toàn bộ.
- Giữ các trường cũ, gồm `downloadMode`, `onlyUnread`, cờ lọc, giá trị lọc, `communeCode`, `allowMissingCommuneCode`, thư mục lưu và kích thước trang.
- `fileSuffixes` chỉ được kiểm tra khi chế độ `suffix` hoạt động; mã xã chỉ kiểm tra trong `legacy`. Giá trị chế độ lạ phải báo lỗi, không âm thầm mở rộng phạm vi.
- Chuyển chế độ không xóa thiết lập của chế độ còn lại. Lưu/mở lại phải khôi phục đúng lựa chọn.
- Không tự ghi đè cấu hình đang dùng chỉ để nâng phiên bản; lưu khi người dùng xác nhận thao tác như luồng hiện tại.

## 5. Các bước triển khai

### Bước 1 — Tách chính sách khớp tên, thêm test trước khi nối UI

Tạo các hàm thuần dự kiến `parseFileSuffixes()`, `buildFileNamePolicy()` và `matchPdfFileName()`. Chế độ legacy tiếp tục dùng hàm mẫu tên hiện tại. Matcher trả kết quả kèm lý do để UI/log dùng thống nhất.

Tách phạm vi `filtered/all_visible` khỏi điều kiện tên. Kiểm thử cấu hình cũ, tất cả bộ lọc cũ, hậu tố tùy chỉnh và dữ liệu cấu hình lỗi. Không thay logic nghiệp vụ của các công cụ khác.

### Bước 2 — Cập nhật UI PowerShell

- Thêm lựa chọn phạm vi văn bản, chế độ tên file và nhóm chọn/nhập hậu tố.
- Hiển thị trực tiếp ví dụ tên khớp, như `Kế Hoạch.signed.pdf`, và giải thích đây không phải kiểm tra chữ ký số.
- Chỉ bật ô liên quan tới chế độ hiện tại; bảo toàn giá trị khi chuyển qua lại.
- Cập nhật phần tóm tắt và hộp xác nhận: phạm vi, các bộ lọc thực sự có hiệu lực, hậu tố, thư mục lưu.
- Khóa các điều khiển mới khi worker đang chạy; bật lại đúng trạng thái khi hoàn tất/lỗi/dừng.
- Bảo đảm không chồng ô, không cắt chữ ở DPI 100%/125%/150%, điều hướng Tab hợp lý. Giữ WinForms hiện tại, không thêm framework UI.

### Bước 3 — Nối vào toàn bộ luồng tải

- Áp dụng cùng một chính sách ở bước chọn tên cho URL trùng, lọc tệp và ghi nhận tệp bị loại.
- Ưu tiên tên tệp đính kèm do HPNet cung cấp; chỉ dùng tên giải mã từ URL khi thiếu tên, như luồng hiện tại. Không vô tình nhận file theo URL nếu tên đính kèm thực tế không khớp.
- Chế độ suffix không được gọi kiểm tra mã xã hoặc ghi nhầm “ngoại lệ thiếu mã xã” cho tên như `Kế Hoạch.signed.pdf`.
- Một văn bản có nhiều tệp: tải mọi tệp khớp, ghi lý do riêng cho từng tệp bị loại; không bỏ cả văn bản chỉ vì một file không khớp.
- Với tên tự do, kiểm tra an toàn đường dẫn Windows trước khi ghi: không thoát thư mục đích, không dùng tên thiết bị dành riêng, không ghi đè; tên không an toàn được bỏ qua và ghi lý do, không âm thầm đổi thành tên khác.

### Bước 4 — Giữ nguyên cơ chế tải và đối soát

Không bỏ hoặc làm yếu các cơ chế hiện có:

- Quét nhiều trang; dừng ngay khi số mã riêng biệt đạt tổng HPNet hợp lệ; khi thiếu tổng thì đọc đến trang rỗng. Trang lặp hoặc trang rỗng trước khi đủ tổng vẫn bị chặn.
- Phân biệt số văn bản và số PDF; không lấy số PDF làm bằng chứng quét đủ văn bản.
- Bỏ qua liên kết đã xử lý; tên trùng được so nội dung SHA-256. Khác nội dung lưu vào thư mục `Trùng` với hậu tố số; không ghi đè bản đã có.
- Kiểm tra đầu dữ liệu `%PDF-`, lưu qua `.part`, kiểm tra sau lưu, tiếp tục với file khác khi một file lỗi.
- Giữ các bộ lọc ngày văn bản, số thông báo, ký hiệu, trích yếu, trạng thái xem; không đổi nghĩa ngày văn bản thành ngày upload.
- Giữ TXT/CSV và CSV đối soát toàn bộ, gồm văn bản bị lọc và file không khớp.

Log mới ghi chế độ tên/hậu tố/phạm vi hiệu lực và lý do “Không khớp hậu tố đã chọn”. Chế độ legacy giữ ý nghĩa thông báo sai mẫu tên cũ. Nếu cần thêm cột CSV, thêm cuối bảng, không đổi tên hoặc xóa cột hiện có.

### Bước 5 — Kiểm thử hồi quy và tích hợp

| Nhóm | Tình huống bắt buộc |
| --- | --- |
| Legacy | Cấu hình v3 không có trường mới; có/thiếu mã xã; ba đuôi signed/ldsigned/lsigned; sai mẫu tên |
| Hậu tố | Toàn bộ ví dụ ở mục 3; tên tiếng Việt; Unicode tổ hợp; hoa/thường; nhiều hậu tố; nhập trùng/rỗng/ký tự regex/đường dẫn |
| Phạm vi | Chế độ filtered giữ nguyên yêu cầu và kết quả cũ; all_visible chỉ bật khi chọn rõ; không đổi endpoint/quyền xem |
| Bộ lọc | Hậu tố kết hợp từng bộ lọc và kết hợp nhiều nhóm; AND/OR giữ nguyên; ngày chính xác/khoảng ngày/trạng thái xem |
| Tệp đính kèm | Một văn bản nhiều file; cùng URL nhiều tên; URL mã hóa; thiếu tên; tất cả/không có file khớp |
| Lưu file | Trùng tên giống/khác nội dung; tên chỉ khác hoa/thường; đường dẫn nguy hiểm; PDF giả; lỗi tải hoặc ghi đĩa |
| Số lượng | Hơn 1.000 văn bản; trang lặp/rỗng/tổng không khớp; đối chiếu từng nhóm trạng thái và số file |
| UI/cấu hình | Chuyển mode, lưu/mở lại, giá trị bị vô hiệu hóa không mất; tóm tắt đúng phạm vi; khóa UI khi chạy |
| Release | Node self-test, PowerShell SelfTest/UiSelfTest, toàn bộ test Python, smoke EXE và bản giải nén từ ZIP |

Dùng API/trình duyệt giả lập và dữ liệu tổng hợp trước. Không tự tải, upload hoặc duyệt trên tài khoản HPNet thật để kiểm thử; chạy thử thực tế là bước riêng cần được cho phép và giới hạn phạm vi.

### Bước 6 — Tài liệu và đóng gói

Cập nhật hướng dẫn của Downloader và hướng dẫn tích hợp trong launcher; chuyển phần README từ “kế hoạch” sang tính năng đã có chỉ sau khi hoàn tất kiểm thử.

Build `HPNet VBDLIS AIO Tool.zip`, kiểm tra cấu hình cũ lẫn mới, rồi mới thay ZIP release cũ theo quy trình hiện tại. Không xóa bản đang dùng trước khi có gói thay thế đạt kiểm tra.

## 6. Tiêu chí hoàn thành

- Chọn suffix `.signed` có thể tải `Kế Hoạch.signed.pdf` mà không yêu cầu CHUACOGIAY hoặc mã xã.
- Chọn “Toàn bộ Văn bản đi được quyền xem” + `.signed` tải mọi tệp khớp trong phạm vi đó, không bị chặn bởi yêu cầu phải nhập trích yếu/số/ngày.
- Khi chọn “Theo bộ lọc”, mọi lựa chọn lọc hiện có tiếp tục có hiệu lực như trước.
- Cấu hình cũ giữ nguyên kết quả; chế độ legacy vẫn chọn được và không thay đổi tập tên hợp lệ.
- Không có nhận nhầm theo chuỗi con, tải file không phải PDF, ghi đè hoặc bỏ sót file khớp trong cùng văn bản do matcher không đồng nhất.
- Nhật ký giải thích được file tải/bỏ qua/lỗi và phân biệt quét chưa đủ với không khớp bộ lọc.
- Sáu công cụ còn lại không thay đổi logic; bộ test và gói release vượt kiểm tra ngoại tuyến.

## 7. Ngoài phạm vi

Kiểm tra chữ ký số, tải Word/Excel, tùy chỉnh regex, thay cơ chế đăng nhập/quyền HPNet, sửa các giới hạn đã chấp nhận của công cụ khác và tự động chạy nghiệp vụ thật.
