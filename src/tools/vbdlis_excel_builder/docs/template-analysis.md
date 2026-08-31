# Phân tích template VBDLIS và file chạy thành công

Tài liệu này được sinh từ nội dung thực tế của hai workbook, không dựa trên bảng hard-code trước khi đọc file.

## Tổng quan

- OFFICIAL_TEMPLATE: 3 sheet `Sheet1, TrangThaiXacThucSoGiayTo, CachNhap`; schema chính ở `Sheet1`, dòng Mục 4, 61 field A:BI.
- GOLDEN_SUCCESS_REFERENCE: 1 sheet, 174 dòng dữ liệu (dòng 5 trở đi).
- File chạy thành công sử dụng 24/61 cột: `A, B, C, H, I, J, K, L, M, N, T, U, X, Y, Z, AA, AB, AC, AD, AX, AY, AZ, BA, BB`.
- Hash official: `42A138353A95D2C9AB17BAF4DA5719FF1199785BC8F35AA4A464043F5EAFC826`.
- Hash golden: `41A8FB5484950BA96E75FCC25BA52E89C173B8754D3228CC3C7C205AF97762C2`.

## Cấu trúc workbook

| Workbook/Sheet | Kích thước | Merge | Formula | Data validation |
|---|---:|---:|---:|---:|
| Official/Sheet1 | A1:BI4 | 46 | 0 | 0 |
| Official/TrangThaiXacThucSoGiayTo | A1:B11 | 1 | 0 | 0 |
| Official/CachNhap | A1:BK61 | 114 | 17 | 0 |
| Golden/tk1+tk2 (chạy vb lượt 2) | A1:BL178 | 46 | 0 | 0 |

## Kết luận nghiệp vụ

- `CachNhap` chứa dữ liệu minh họa và 17 công thức; không được sao chép giá trị minh họa xuống output.
- Golden không có dữ liệu ở Mục 3 (Ngày cấp GCN), Mục 4 (Số vào sổ GCN) và cột Loại GCN; các field này là `GCN_OPTIONAL`.
- Mục 2 vẫn được dùng trong hồ sơ chưa có GCN như mã bộ hồ sơ `CHUACOGIAY_{MA_XA}_{SO_TO}_{SO_THUA}`.
- Mục 49 trong golden luôn là hai file `-TBXN.pdf, -DDK.pdf`, cách nhau bởi dấu phẩy và một khoảng trắng.
- Vai trò golden chỉ dùng `Chủ hộ` và `Thành viên hộ gia đình`; không dùng quan hệ Vợ/Chồng/Con.
- Các cột template có sample nhưng golden trống được xếp optional/conditional, không biến thành lỗi bắt buộc.
- Dòng style output lấy từ dòng ví dụ nhưng chỉ copy style; mọi sample value bị loại.

## Bảng field

| Mục/Cột | Tên trường | Template sample | Golden có dữ liệu | Phân loại | Mode mặc định | Required |
|---|---|---:|---:|---|---|---:|
| A | Số TT | 32 | 174 | COMPUTED | computed | Có |
| Mục 1 / B | Mã ĐVHC cấp xã | 20 | 174 | USER_CONFIGURABLE | computed | Có |
| Mục 2 / C | Thông tin về giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất / Số phát hành GCN | 20 | 174 | COMPUTED | computed | Có |
| Mục 3 / D | Thông tin về giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất / Ngày cấp GCN | 24 | 0 | GCN_OPTIONAL | conditional | Không |
| Mục 4 / E | Thông tin về giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất / Số vào sổ GCN | 12 | 0 | GCN_OPTIONAL | conditional | Không |
| Mục 5 / F | Thông tin về tổ chức sử dụng đất / Tên tổ chức | 5 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 6 / G | Thông tin về tổ chức sử dụng đất / Số định danh tổ chức | 5 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 7 / H | Thông tin về chủ sử dụng/người đại diện theo pháp luật của tổ chức / Họ và tên chủ sử dụng/ / Họ tên người đại diện tổ chức | 16 | 174 | ACTIVE_REQUIRED | computed | Có |
| Mục 8 / I | Thông tin về chủ sử dụng/người đại diện theo pháp luật của tổ chức / Số định danh cá nhân/CCCD | 16 | 174 | ACTIVE_OPTIONAL | computed | Không |
| Mục 9 / J | Thông tin về chủ sử dụng/người đại diện theo pháp luật của tổ chức / Ngày, tháng, năm sinh | 30 | 174 | ACTIVE_OPTIONAL | computed | Không |
| Mục 10 / K | Thông tin về chủ sử dụng/người đại diện theo pháp luật của tổ chức / Giới tính | 46 | 174 | COMPUTED | computed | Không |
| Mục 11 / L | Thông tin về chủ sử dụng/người đại diện theo pháp luật của tổ chức / Địa chỉ thường trú | 23 | 174 | USER_CONFIGURABLE | computed | Có |
| Mục 12 / M | Thông tin về chủ sử dụng/người đại diện theo pháp luật của tổ chức / Pháp nhân trên GCN | 20 | 174 | USER_CONFIGURABLE | computed | Có |
| Mục 13 / N | Thông tin về chủ sử dụng/người đại diện theo pháp luật của tổ chức / Vai trò pháp nhân trên GCN | 16 | 174 | COMPUTED | computed | Có |
| Mục 14 / O | Thông tin người sử dụng đất hiện tại (trường hợp không phải là chủ sử dụng pháp lý) / Tên người sử dụng hiện tại | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 15 / P | Thông tin người sử dụng đất hiện tại (trường hợp không phải là chủ sử dụng pháp lý) / Số định danh cá nhân (CCCD) | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 16 / Q | Thông tin người sử dụng đất hiện tại (trường hợp không phải là chủ sử dụng pháp lý) / Địa chỉ thường trú (2 cấp) | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 17 / R | Thông tin người sử dụng đất hiện tại (trường hợp không phải là chủ sử dụng pháp lý) / Lý do thay đổi (thừa kế, tặng cho, chuyển nhượng...) | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 18 / S | Thông tin thửa đất / Mã định danh thửa đất | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 19 / T | Thông tin thửa đất / Số tờ bản đồ ghi trên GCN | 21 | 174 | ACTIVE_REQUIRED | computed | Có |
| Mục 20 / U | Thông tin thửa đất / Số thứ tự thửa đất ghi trên GCN | 19 | 174 | ACTIVE_REQUIRED | computed | Có |
| Mục 21 / V | Thông tin thửa đất / Số hiệu tờ trên bản đồ địa chính | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 22 / W | Thông tin thửa đất / Số thứ tự thửa trên bản đồ địa chính | 6 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 23 / X | Thông tin thửa đất / Địa chỉ thửa đất | 19 | 174 | ACTIVE_OPTIONAL | computed | Không |
| Mục 24 / Y | Thông tin thửa đất / Diện tích thửa đất | 19 | 174 | ACTIVE_REQUIRED | computed | Có |
| Mục 25 / Z | Thông tin thửa đất / Loại đất 1 (Mục đích sử dụng) / Loại đất | 19 | 174 | TEMPLATE_DEFAULT | keep_template | Có |
| Mục 26 / AA | Thông tin thửa đất / Loại đất 1 (Mục đích sử dụng) / Diện tích | 19 | 174 | COMPUTED | computed | Có |
| Mục 27 / AB | Thông tin thửa đất / Loại đất 1 (Mục đích sử dụng) / Nguồn gốc sử dụng | 19 | 174 | TEMPLATE_DEFAULT | keep_template | Có |
| Mục 28 / AC | Thông tin thửa đất / Loại đất 1 (Mục đích sử dụng) / Hình thức sử dụng | 19 | 174 | TEMPLATE_DEFAULT | keep_template | Có |
| Mục 29 / AD | Thông tin thửa đất / Loại đất 1 (Mục đích sử dụng) / Thời hạn sử dụng | 19 | 174 | TEMPLATE_DEFAULT | keep_template | Có |
| Mục 30 / AE | Thông tin thửa đất / Loại đất 2 (Mục đích sử dụng) / Loại đất | 12 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 31 / AF | Thông tin thửa đất / Loại đất 2 (Mục đích sử dụng) / Diện tích | 8 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 32 / AG | Thông tin thửa đất / Loại đất 2 (Mục đích sử dụng) / Nguồn gốc sử dụng | 8 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 33 / AH | Thông tin thửa đất / Loại đất 2 (Mục đích sử dụng) / Hình thức sử dụng | 8 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 34 / AI | Thông tin thửa đất / Loại đất 2 (Mục đích sử dụng) / Thời hạn sử dụng | 8 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 35 / AJ | Thông tin thửa đất / Loại đất 3 (Mục đích sử dụng) / Loại đất | 8 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 36 / AK | Thông tin thửa đất / Loại đất 3 (Mục đích sử dụng) / Diện tích | 8 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 37 / AL | Thông tin thửa đất / Loại đất 3 (Mục đích sử dụng) / Nguồn gốc sử dụng | 8 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 38 / AM | Thông tin thửa đất / Loại đất 3 (Mục đích sử dụng) / Hình thức sử dụng | 8 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 39 / AN | Thông tin thửa đất / Loại đất 3 (Mục đích sử dụng) / Thời hạn sử dụng | 8 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 40 / AO | Thông tin nhà ở / Loại tài sản gắn liền với đất | 7 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 41 / AP | Thông tin nhà ở / Khu nhà chung cư, nhà hỗn hợp | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 42 / AQ | Thông tin nhà ở / Nhà chung cư | 1 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 43 / AR | Thông tin nhà ở / Số căn hộ | 4 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 44 / AS | Thông tin nhà ở / Diện tích xây dựng | 7 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 45 / AT | Thông tin nhà ở / Diện tích sàn | 7 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 46 / AU | Thông tin nhà ở / Hình thức sở hữu | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 47 / AV | Thông tin nhà ở / Thời hạn sở hữu | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 48 / AW | Thông tin nhà ở / Cấp hạng | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| Mục 49 / AX | Thông tin HSQ / Tên file quét GCN/CCCD | 36 | 174 | COMPUTED | computed | Có |
| Mục 50 / AY | Phân loại thửa đất | 35 | 174 | USER_CONFIGURABLE | computed | Có |
| AZ | Thông tin bổ sung / Chủ sử dụng / Số giấy tờ 1 | 15 | 174 | COMPUTED | computed | Không |
| BA | Thông tin bổ sung / Chủ sử dụng / Loại giấy tờ 1 | 15 | 174 | TEMPLATE_DEFAULT | conditional | Không |
| BB | Thông tin bổ sung / Chủ sử dụng / Trạng thái xác thực số giấy tờ 1 | 15 | 174 | TEMPLATE_DEFAULT | conditional | Không |
| BC | Thông tin bổ sung / Chủ sử dụng / Số giấy tờ 2 | 3 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| BD | Thông tin bổ sung / Chủ sử dụng / Loại giấy tờ 2 | 3 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| BE | Thông tin bổ sung / Chủ sử dụng / Trạng thái xác thực số giấy tờ 2 | 3 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| BF | Thông tin bổ sung / Hồ sơ quét / Có file hồ sơ quét | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| BG | Thông tin bổ sung / Giấy chứng nhận / Loại giấy chứng nhận | 18 | 0 | GCN_OPTIONAL | conditional | Không |
| BH | Không gian / Thông tin tọa độ (hệ quy chiếu WGS84) | 10 | 0 | TEMPLATE_OPTIONAL | blank | Không |
| BI | Thông tin hệ thống / (Lưu ý: Không được thay đổi) / Guid | 0 | 0 | TEMPLATE_OPTIONAL | blank | Không |

## Ngoại lệ và rule ưu tiên

1. Mục 2 mang tên schema liên quan GCN nhưng trong workflow hiện tại là mã bộ hồ sơ và bắt buộc được tính tự động.
2. Mục 19/20 có nhãn 'ghi trên GCN' nhưng golden vẫn dùng cho hồ sơ chưa có GCN; vì vậy đây là số tờ/số thửa bắt buộc hiện tại.
3. Mục 25/27/28/29 và BA/BB là giá trị mặc định theo golden hiện tại, vẫn có thể sửa bằng Advanced Mapping/Profile.
4. GCN được gắn theo thửa; cùng tờ/thửa có hai bộ GCN khác nhau là conflict và không được tự gộp.
5. Output mặc định chỉ giữ sheet schema để tương thích với golden; profile có thể bật giữ các sheet tham chiếu.
