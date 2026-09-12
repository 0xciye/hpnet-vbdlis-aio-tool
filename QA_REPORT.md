# QA REPORT — HPNET & VBDLIS Tools

Ngày kiểm tra: 12/09/2026  
Phạm vi dữ liệu thật: chỉ đọc, không sửa file nguồn hoặc thư mục hồ sơ sản xuất.

## 1. Repository status

| Mục | Kết quả |
|---|---|
| Branch | `main` |
| Commit trước audit | `fab6a5d feat: add VBDLIS validation and source comparison` |
| Working tree trước audit | Sạch |
| Đồng bộ | `git fetch --all --prune`; `git pull --ff-only` — Already up to date |
| Thao tác phá hủy | Không dùng `reset --hard`, `clean -fd`, `checkout .` |
| Trạng thái thay đổi audit | Được commit và push khi bàn giao task này |

## 2. Applications discovered

| App | Entry point | Mục đích | Input | Output | Phụ thuộc/chuyển tiếp | Scope |
|---|---|---|---|---|---|---|
| Desktop hub | `src/launcher.py` | Mở các công cụ | Không có dữ liệu nghiệp vụ | Cửa sổ công cụ | PySide6, mọi app bên dưới | Included, chỉ smoke UI |
| Tạo thông báo đất đai | `src/tools/notice_builder/main.py` | Excel → thông báo Word theo từng thửa | Excel, template DOCX, danh sách số thông báo | DOCX và log XLSX/TXT | openpyxl, python-docx | Included, P0 |
| Chuẩn bị hồ sơ VBDLIS | `src/tools/vbdlis_excel_builder/main.py` | Chuyển Excel nguồn thành Excel đúng mẫu VBDLIS | Excel nguồn và template VBDLIS | XLSX VBDLIS | openpyxl | Included, P0 |
| Kiểm tra dữ liệu upload VBDLIS | `src/tools/vbdlis_validation/ui.py` | Đối chiếu source ↔ VBDLIS ↔ TBXN ↔ DDK ↔ chữ ký | 2 Excel và các thư mục PDF | Báo cáo/nhóm file theo trạng thái | openpyxl, pypdf, pyHanko | Included, P0 |
| VBDLIS - Đặt tên hồ sơ | `src/tools/hpnet_file_generator/main.py` | Ghép người với file nguồn, copy và đặt tên DDK/TBXN | Excel, thư mục Word/PDF | File đã đặt tên và log hành động | openpyxl, PySide6 | Included, P0; tên thư mục là tên cũ |
| Làm sạch PDF đã ký | `src/tools/signed_pdf_cleaner/main.py` | Kiểm tra và chuẩn hóa tên PDF đã ký | PDF | PDF đã chuẩn hóa | pypdf, send2trash | Included, P1 |
| Kiểm tra thửa đất trùng | `src/tools/duplicate_parcel/ui.py` | Xem trước/xử lý thửa trùng trong Excel | XLSX | XLSX đã xử lý | openpyxl | Included |
| Chuẩn hóa họ tên/ngày sinh | `src/tools/data_normalizer/ui.py` | Chuẩn hóa dữ liệu Excel | XLSX | XLSX đã chuẩn hóa | openpyxl | Included |
| HPNet PDF Downloader | `src/nodes_tools/Downloader/...exe` | Tải PDF từ HPNet | HPNet | PDF | Trình duyệt/runtime ngoài | **EXCLUDED** |
| HPNet Upload Dự Thảo | `src/nodes_tools/Upload/...exe` | Upload dự thảo lên HPNet | Word/HPNet | Trạng thái trên HPNet | Runtime ngoài | **EXCLUDED** |
| HPNet Duyệt Dự Thảo | `src/nodes_tools/Duyet/...exe` | Chuyển duyệt trên HPNet | HPNet | Trạng thái trên HPNet | Runtime ngoài | **EXCLUDED** |

**EXCLUDED: All HPNet-related applications/modules.** `hpnet_file_generator` vẫn được kiểm tra vì mã nguồn/UI chứng minh đây là công cụ VBDLIS đặt tên hồ sơ, không phải tác vụ web HPNet.

## 3. Critical VBDLIS pipeline

```text
Excel nguồn (B=Tên hộ, G=Số tờ, H=Số thửa)
  → Tạo thông báo Word theo từng thửa
  → Word → PDF (bước Office/người dùng bên ngoài repository)
  → TBXN PDF + DDK PDF
  → VBDLIS - Đặt tên hồ sơ (quét đệ quy, ghép, copy/đổi tên)
  → Chuẩn bị Excel VBDLIS (household → parcels → member rows)
  → ghi đồng thời TBXN và DDK vào AX
  → Validation source ↔ VBDLIS ↔ PDF ↔ chữ ký
```

Quy tắc chuẩn dùng chung sau sửa:

- Số tờ và số thửa bắt buộc là **số nguyên dương**.
- Chấp nhận giá trị Excel tương đương như `10`, `10.0`, `"10"` và chuẩn hóa thành `10`.
- Không chấp nhận chữ cái, số 0, số âm hoặc số thập phân thực.
- Mã không hợp lệ phải thành lỗi rõ ràng, không được silently skip và không được tính là thiếu tài liệu.

## 4. Kết quả dữ liệu thật Tân Hòa

Nguồn: `Tân Hòa đợt 1 ngày 8.9_cleaned.xlsx`, sheet `Tân Hòa chạy đơn`.  
VBDLIS hiện tại: `tân hòa pdf/VBDLIS Tân Hòa.xlsx`.

| Checkpoint | Kết quả |
|---|---:|
| Dòng nguồn có tờ/thửa | 207 |
| Thửa hợp lệ cần xử lý | 206 |
| Dòng nguồn bị từ chối rõ ràng | 1 (`Lê Văn Dũng`, dòng 288, tờ `92`, thửa `CN`) |
| Word records được chọn sau sửa | 206 |
| TBXN expected / physical found | **206 / 206** |
| Missing TBXN trong tập hợp lệ | **0** |
| DDK expected / physical found | **206 / 202** |
| Missing DDK trong tập hợp lệ | **4** |
| VBDLIS hiện tại | 207 parcel / 209 member-parcel rows; có 1 parcel `CN` không hợp lệ |
| Builder sau sửa | 206 parcel / 208 member-parcel rows |
| AX hiện tại chứa TBXN / DDK | 207 / 207; một cặp thuộc dòng `CN` không hợp lệ |

Kết luận nguyên nhân “thiếu TBXN”: với quy tắc nghiệp vụ mới, **không có thửa hợp lệ nào thiếu TBXN**. Ca từng bị nhìn như thiếu là `92/CN`; bản thân số thửa có chữ nên thuộc `SOURCE_DATA_ERROR`, không phải `TBXN_NOT_FOUND`. Ứng dụng hiện báo: “Số thửa bắt buộc phải là số nguyên dương và không được có chữ cái”, kèm đúng dòng Excel cần sửa.

Bốn DDK vật lý còn thiếu:

| Hộ | Tờ | Thửa | Dòng nguồn | Phân loại |
|---|---:|---:|---:|---|
| Lê Thị Dịu | 92 | 330 | 146 | DDK_PHYSICAL_MISSING; VBDLIS ghi tên Lê Thị Êm nên cần đối chiếu người |
| Nguyễn Bá Tải | 92 | 294 | 149 | DDK_PHYSICAL_MISSING |
| Nguyễn Bá Tải | 80 | 183 | 150 | DDK_PHYSICAL_MISSING |
| Nguyễn Bá Tải | 80 | 294 | 151 | DDK_PHYSICAL_MISSING |

## 5. Audit theo stage

| Stage | Kiểm tra | Kết quả |
|---|---|---|
| Excel → Word | sheet/header; hai tầng header; merged/blank owner; hidden row; float/string; nhiều thửa/hộ; same-name households; duplicate member rows; nội dung DOCX được mở lại | PASS |
| Cấp số thông báo | danh sách số nhập tay hết thì tiếp tục số kế tiếp; cấu hình cũ được chuyển sang tiếp tục tự động | PASS |
| Word → PDF | Repository không có bộ chuyển Word sang PDF; golden dùng PDF synthetic đúng contract và mở/parse lại | **BLOCKED / EXTERNAL** |
| TBXN scan | quét thư mục lồng; canonical tờ+thửa; ambiguous không lấy `candidates[0]` | PASS |
| DDK rename/copy | đếm input/action/output; va chạm output làm tất cả candidate thành CONFLICT; lỗi dữ liệu được log | PASS |
| VBDLIS prepare | household → parcels → member rows; không nhân sai parcel; không mất member; `5 members × 10 parcels = 50 rows` | PASS |
| AX reference | TBXN và DDK cùng tồn tại; không overwrite; mọi member row theo template có reference nhất quán | PASS |
| Validation | FULL_SOURCE_COMPARE; VBDLIS_ONLY không claim completeness; source/AX/PDF/chữ ký; lỗi thân thiện | PASS |
| Input safety | hash Excel nguồn trước/sau golden không đổi; dữ liệu thật chỉ đọc | PASS |

## 6. Bugs and fixes

### B-001 — P0 — Tờ/thửa không hợp lệ bị xử lý không nhất quán

- Trước sửa: một số app silently skip mã có chữ, app khác cho mã đi vào VBDLIS; validator diễn đạt hậu quả thành thiếu tài liệu.
- Root cause: mỗi app có normalizer riêng và nhánh `continue` không luôn tạo lỗi.
- Sửa: thêm canonical `land_identifier.py`; bắt buộc số nguyên dương trong Word reader, file generator, VBDLIS builder và validator; giữ raw value/dòng nguồn; hiển thị một hướng dẫn dễ hiểu.
- Regression: `CN`, `0`, số âm, số thập phân bị chặn; `10`, `10.0`, `"10"` khớp nhau.
- Sau sửa: `92/CN` kết thúc `SOURCE_DATA_ERROR`, không tạo Word/file/VBDLIS mới và không tính vào missing TBXN/DDK.

### B-002 — P1 — Tạo thông báo dừng khi hết danh sách số nhập vào

- Trước sửa: UI mặc định không tiếp tục nên chỉ tạo số người dùng nhập rồi kết thúc.
- Sửa: bật tiếp tục tự động theo mặc định; danh sách `300-400` gợi ý số kế tiếp `401`; migrate cấu hình cũ chưa có lựa chọn này.
- Regression: PASS.

### B-003 — P0 — Row thành viên/row thửa lặp có thể gây đếm sai

- Sửa: dedup thành viên theo tên + CCCD trong hộ; collapse cùng một parcel có area/location giống nhau; vẫn chặn duplicate giữa hai hộ.
- Regression: 3 members × 2 parcels → 2 TBXN; 5 members × 10 parcels → 10 parcels và 50 VBDLIS rows.

### B-004 — P0 — Collision output chỉ đánh dấu file sau

- Trước sửa: candidate đầu có thể vẫn ở trạng thái sẵn sàng khi nhiều file cùng nhắm một output.
- Sửa: tất cả candidate cạnh tranh cùng output đều là CONFLICT; không copy/overwrite tự động.
- Regression: PASS.

### B-005 — P1 — Scanner đặt tên hồ sơ không đọc thư mục lồng

- Sửa: chuyển sang quét đệ quy; đường dẫn nested có Unicode/khoảng trắng được test.
- Regression: PASS.

### B-006 — P1 — Parcel dùng chung nhiều tên bị loại mà cảnh báo chưa đủ rõ

- Sửa: giữ nguyên nguyên tắc không tự ghép để tránh sai hộ, nhưng xuất cảnh báo theo từng dòng và lý do cần kiểm tra.
- Regression: PASS.

### B-007 — P0 — PDF Cleaner có thể xóa bản cũ trước khi thay thế hoàn tất

- Sửa: chuẩn bị replacement an toàn trước; nếu delete/rename lỗi thì giữ dữ liệu và báo lỗi.
- Regression: PASS.

### B-008 — P2/P3 — Nhận diện app và thông báo lỗi kỹ thuật

- Sửa: tên cửa sổ/binary thành `VBDLIS - Đặt tên hồ sơ`; icon riêng được đóng gói; lỗi quyền/file/path được dịch thành hướng dẫn thao tác cho người không chuyên.
- Regression + executable smoke: PASS.

## 7. Test results

| Nhóm | Kết quả |
|---|---|
| Full regression | **436 passed, 4 skipped, 84 subtests passed** |
| QA integration/end-to-end | **5 passed** |
| Golden E2E | 5 hộ, 10 parcels, 10 Word, 10 TBXN, 10 DDK, 10 VBDLIS parcels, 10 AX TBXN, 10 AX DDK, 0 silent loss |
| Large smoke | 5,000 parcels |
| One owner many parcels | 20/20 parcels survive |
| Many members many parcels | 5 × 10 → 50 rows, 10 parcel entities |
| Mixed missing/duplicate/unsigned/ambiguous | Đúng explicit classification |
| Workbook report reopen | 8 sheets, 0 formula error |

Bốn test skipped là fixture/reference riêng không có trong môi trường kiểm tra; không phải failure của production path.

## 8. Builds and UI

| App | Packaging | Executable smoke |
|---|---|---|
| Tạo thông báo đất đai | PyInstaller PASS | PASS |
| VBDLIS - Đặt tên hồ sơ | PyInstaller PASS, icon riêng, tên mới | PASS (còn chạy sau 3 giây) |
| PDF Cleaner | PyInstaller PASS | PASS |
| VBDLIS Excel Builder | PyInstaller PASS | PASS |
| VBDLIS Validation | Không có spec độc lập | Source/service/UI smoke PASS |
| Duplicate Parcel | Nằm trong suite; không build riêng | Source/UI smoke PASS |
| Data Normalizer | Nằm trong suite; không build riêng | Source/UI smoke PASS |
| Unified suite | Không build trong audit vì spec đóng gói cả ba HPNet apps đã bị loại trừ | NOT RUN |

Tất cả 7 cửa sổ included được tạo và hiển thị icon. Ba HPNet executable không được chạy.

## 9. QA artifacts

- `qa/fixtures/golden_expected.json`: kỳ vọng golden độc lập với output hiện tại.
- `qa/generators/pipeline_fixture.py`: tạo và thực thi pipeline golden.
- `qa/tests/test_end_to_end_lineage.py`: conservation, integration, large/mixed cases.
- `qa/generators/real_lineage_snapshot.py`: snapshot chỉ đọc từ dữ liệu thật.
- `qa/reports/DATA_LINEAGE_REPORT.xlsx`: lineage theo parcel, phân tích TBXN/DDK và lỗi dữ liệu nguồn.
- `qa_runtime/`: input/expected/actual/logs và build tạm; đã ignore Git.

## 10. Remaining issues

1. Cần người dùng đối chiếu hồ sơ gốc rồi sửa ô `H288 = CN` thành đúng số nguyên dương; phần mềm không tự đoán số.
2. Cần bổ sung/đối chiếu 4 DDK vật lý nêu trên.
3. Bước Word → PDF phụ thuộc Microsoft Office/quy trình bên ngoài và không tồn tại trong source, nên trạng thái là BLOCKED/EXTERNAL chứ không được ghi PASS.
4. Bước Word → PDF vẫn cần được kiểm tra trong môi trường có Microsoft Office nếu sau này đưa converter vào source.

## 11. Acceptance conclusion

- Golden: `SOURCE_ELIGIBLE_PARCELS = 10 = 10 generated + 0 rejected`; không silent loss.
- Tân Hòa: `207 source rows = 206 eligible + 1 explicit SOURCE_DATA_ERROR`.
- Tân Hòa TBXN: `206 expected = 206 physical + 0 missing`.
- Không thấy owner → single parcel overwrite, filename overwrite, false duplicate do member rows hoặc AX overwrite trong regression hiện tại.
- Pipeline đáp ứng điều kiện: mỗi parcel hợp lệ đi đến output hoặc có lỗi/review rõ ràng; mã tờ/thửa có chữ bị chặn nhất quán.
