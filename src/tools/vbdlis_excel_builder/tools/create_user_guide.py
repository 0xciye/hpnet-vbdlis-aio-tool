from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.utils import ImageReader


PROJECT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT / "output" / "pdf" / "HƯỚNG DẪN SỬ DỤNG VBDLIS EXCEL BUILDER.pdf"
ASSETS = PROJECT / "docs" / "assets"

BLUE = colors.HexColor("#1F4E78")
ACCENT = colors.HexColor("#0B63CE")
LIGHT_BLUE = colors.HexColor("#EAF3FB")
LIGHT_YELLOW = colors.HexColor("#FFF7DF")
LIGHT_GREEN = colors.HexColor("#EAF7EE")
LIGHT_RED = colors.HexColor("#FDECEC")
TEXT = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#5B677A")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("ArialVN", r"C:\Windows\Fonts\arial.ttf"))
    pdfmetrics.registerFont(TTFont("ArialVN-Bold", r"C:\Windows\Fonts\arialbd.ttf"))
    pdfmetrics.registerFont(TTFont("ArialVN-Italic", r"C:\Windows\Fonts\ariali.ttf"))


def styles():
    base = getSampleStyleSheet()
    return {
        "cover": ParagraphStyle(
            "Cover", parent=base["Title"], fontName="ArialVN-Bold", fontSize=25,
            leading=31, textColor=BLUE, alignment=TA_CENTER, spaceAfter=14,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"], fontName="ArialVN", fontSize=13,
            leading=19, textColor=MUTED, alignment=TA_CENTER, spaceAfter=10,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName="ArialVN-Bold", fontSize=18,
            leading=23, textColor=BLUE, spaceBefore=4, spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName="ArialVN-Bold", fontSize=13,
            leading=17, textColor=ACCENT, spaceBefore=8, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName="ArialVN", fontSize=10.2,
            leading=15, textColor=TEXT, spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName="ArialVN", fontSize=8.8,
            leading=12, textColor=MUTED, spaceAfter=4,
        ),
        "code": ParagraphStyle(
            "Code", parent=base["Code"], fontName="Courier", fontSize=8.2,
            leading=11, textColor=colors.HexColor("#253858"), leftIndent=5, rightIndent=5,
        ),
        "table": ParagraphStyle(
            "TableText", parent=base["BodyText"], fontName="ArialVN", fontSize=8.8,
            leading=12, textColor=TEXT,
        ),
        "table_header": ParagraphStyle(
            "TableHeader", parent=base["BodyText"], fontName="ArialVN-Bold", fontSize=8.8,
            leading=11, textColor=colors.white, alignment=TA_CENTER,
        ),
    }


def para(text: str, style) -> Paragraph:
    return Paragraph(text, style)


def bullets(items: list[str], style) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, style), leftIndent=12) for item in items],
        bulletType="bullet", start="circle", leftIndent=18, bulletFontName="ArialVN",
        bulletFontSize=7, bulletColor=ACCENT, spaceAfter=7,
    )


def numbered(items: list[str], style) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(item, style), leftIndent=14) for item in items],
        bulletType="1", leftIndent=20, bulletFontName="ArialVN-Bold", bulletFontSize=9,
        bulletColor=BLUE, spaceAfter=7,
    )


def callout(text: str, style, fill=LIGHT_BLUE, border=ACCENT) -> Table:
    table = Table([[Paragraph(text, style)]], colWidths=[172 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("BOX", (0, 0), (-1, -1), 0.8, border),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def screenshot(filename: str, max_height_mm: float = 165) -> Image:
    path = ASSETS / filename
    reader = ImageReader(str(path))
    width, height = reader.getSize()
    max_width = 174 * mm
    max_height = max_height_mm * mm
    scale = min(max_width / width, max_height / height)
    image = Image(str(path), width=width * scale, height=height * scale)
    image.hAlign = "CENTER"
    return image


def data_table(rows: list[list[str]], widths: list[float], s) -> Table:
    if any(len(row) != len(widths) for row in rows):
        raise ValueError("Số độ rộng cột không khớp bảng hướng dẫn.")
    converted = []
    for r, row in enumerate(rows):
        style = s["table_header"] if r == 0 else s["table"]
        converted.append([Paragraph(str(value), style) for value in row])
    table = Table(converted, colWidths=[value * mm for value in widths], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C6D9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
            ]
        )
    )
    return table


def header_footer(canvas, doc) -> None:
    canvas.saveState()
    page = canvas.getPageNumber()
    width, height = A4
    if page > 1:
        canvas.setStrokeColor(colors.HexColor("#D7E0EA"))
        canvas.line(18 * mm, height - 13 * mm, width - 18 * mm, height - 13 * mm)
        canvas.setFont("ArialVN", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, height - 10 * mm, "VBDLIS Excel Builder - Hướng dẫn sử dụng")
    canvas.setStrokeColor(colors.HexColor("#D7E0EA"))
    canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
    canvas.setFont("ArialVN", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 8.5 * mm, "Tạo file Excel theo GOLDEN - Tải lên VBDLIS thủ công")
    canvas.drawRightString(width - 18 * mm, 8.5 * mm, f"Trang {page}")
    canvas.restoreState()


def build_story(s):
    story = []
    story.extend(
        [
            Spacer(1, 28 * mm),
            para("VBDLIS EXCEL BUILDER", s["cover"]),
            para("Hướng dẫn sử dụng dành cho người không chuyên công nghệ", s["subtitle"]),
            Spacer(1, 8 * mm),
            callout(
                "<b>Mục tiêu duy nhất của ứng dụng:</b> nhận file Excel nguồn, xử lý dữ liệu hộ - người - thửa và tạo ra file Excel có cấu trúc tương thích với <b>GOLDEN_SUCCESS_REFERENCE</b>. Người dùng tự tải file kết quả lên VBDLIS bằng quy trình thủ công hiện có.",
                s["body"], LIGHT_GREEN, colors.HexColor("#3A8D5D"),
            ),
            Spacer(1, 8 * mm),
            para("Ứng dụng không đăng nhập VBDLIS, không lưu tài khoản/mật khẩu và không tự tải file lên.", s["subtitle"]),
            Spacer(1, 34 * mm),
            para("Phiên bản Windows x64 - Hoạt động offline", s["subtitle"]),
            para("Cập nhật: 31/08/2026", s["subtitle"]),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("1. Bắt đầu trong 3 phút", s["h1"]),
            para("Làm đúng 6 bước dưới đây là đủ cho lần sử dụng đầu tiên:", s["body"]),
            numbered(
                [
                    "Giải nén toàn bộ file ZIP vào một thư mục riêng. Không chạy EXE trực tiếp bên trong ZIP.",
                    "Mở thư mục <b>VBDLIS Excel Builder</b> và nhấp đúp <b>VBDLIS Excel Builder.exe</b>.",
                    "Chọn file Excel nguồn, chọn sheet và dòng tiêu đề.",
                    "Kiểm tra ánh xạ các cột bắt buộc: STT hộ, Họ tên, CCCD, Số tờ, Số thửa và Diện tích.",
                    "Nhập Mã xã, Địa chỉ; giữ nguyên Mục 2, Mục 49 và hai giá trị vai trò nếu không có yêu cầu nghiệp vụ khác.",
                    "Nhấn <b>Kiểm tra</b>. Khi không còn LỖI, chọn thư mục lưu và nhấn <b>Tạo file VBDLIS</b>.",
                ],
                s["body"],
            ),
            callout(
                "<b>Quan trọng:</b> hãy gửi cho người khác cả thư mục sau khi giải nén hoặc nguyên file ZIP. Không gửi riêng file EXE vì EXE cần thư mục <b>_internal</b> nằm bên cạnh.",
                s["body"], LIGHT_YELLOW, colors.HexColor("#D6A100"),
            ),
            para("Windows SmartScreen", s["h2"]),
            para(
                "Nếu Windows hiện cảnh báo do ứng dụng chưa có chữ ký số thương mại: chọn <b>Thông tin thêm</b>, kiểm tra tên ứng dụng là VBDLIS Excel Builder rồi chọn <b>Vẫn chạy</b>. Chỉ làm việc này với đúng gói ZIP được người phụ trách chia sẻ.",
                s["body"],
            ),
            para("Ứng dụng tạo ra những gì?", s["h2"]),
            bullets(
                [
                    "Một file Excel VBDLIS theo tên và thư mục người dùng chọn.",
                    "Một file báo cáo kiểm tra riêng nếu bật lựa chọn <b>Xuất báo cáo kiểm tra</b>.",
                    "Không sửa file Excel nguồn và không sửa biểu mẫu chính thức nằm trong ứng dụng.",
                ],
                s["body"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("2. Chuẩn bị file Excel nguồn", s["h1"]),
            para("File nguồn có thể đặt các cột ở vị trí khác nhau. Ứng dụng không bắt buộc cột B phải là Họ tên hay cột G phải là Số tờ; người dùng sẽ ánh xạ ở Tab 2.", s["body"]),
            para("Các cột tối thiểu", s["h2"]),
            data_table(
                [
                    ["Thông tin", "Bắt buộc?", "Lưu ý"],
                    ["STT hộ", "Có", "Dòng có STT bắt đầu một hộ mới."],
                    ["Họ và tên", "Có", "Người ở dòng STT là Chủ hộ; người sau có STT trống là thành viên."],
                    ["Số tờ", "Có", "Không được tự tạo nếu thiếu."],
                    ["Số thửa", "Có", "Không được tự tạo nếu thiếu."],
                    ["Diện tích", "Có", "Thửa thiếu diện tích không được xuất."],
                    ["CCCD", "Có", "Bắt buộc. Được xử lý dạng text để giữ số 0 đầu."],
                    ["Ngày sinh", "Không", "Thiếu sẽ cảnh báo hoặc để trống."],
                    ["Giới tính", "Tự động", "Lấy từ số thứ 4 của CCCD: 0 là Nam, 1 là Nữ; trường hợp khác để trống."],
                    ["Xứ đồng", "Không", "Có thể dùng địa chỉ thay thế từ cấu hình."],
                    ["Các trường GCN", "Không", "Chỉ ánh xạ khi nguồn thực sự có dữ liệu GCN."],
                ],
                [40, 28, 104], s,
            ),
            Spacer(1, 4 * mm),
            para("Cách nhận biết một hộ", s["h2"]),
            data_table(
                [
                    ["STT", "Họ tên", "Kết quả hiểu"],
                    ["1", "NGUYỄN VĂN A", "Chủ hộ của hộ 1"],
                    ["trống", "NGUYỄN THỊ B", "Thành viên hộ 1"],
                    ["trống", "NGUYỄN VĂN C", "Thành viên hộ 1"],
                    ["2", "TRẦN VĂN D", "Chủ hộ của hộ 2"],
                ],
                [25, 70, 77], s,
            ),
            callout(
                "Không tự điền tên Chủ hộ vào các ô tên đang trống có chủ ý. Nếu một dòng chỉ chứa thông tin thửa, tên có thể để trống và thửa vẫn được gắn vào hộ hiện tại.",
                s["body"], LIGHT_YELLOW, colors.HexColor("#D6A100"),
            ),
            para("Một hộ có nhiều người và nhiều thửa", s["h2"]),
            para("Ứng dụng tạo mọi tổ hợp Người x Thửa. Ví dụ 2 người và 2 thửa sẽ tạo 4 dòng, STT mới chạy liên tục 1, 2, 3, 4.", s["body"]),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("3. Tab 1 - Dữ liệu", s["h1"]),
            screenshot("tab_1.png", 150),
            Spacer(1, 4 * mm),
            numbered(
                [
                    "Nhấn <b>Chọn file Excel...</b> và chọn file nguồn `.xlsx` hoặc `.xlsm`.",
                    "Ở ô <b>Trang tính</b>, chọn đúng trang tính chứa danh sách cần xử lý.",
                    "Kiểm tra <b>Dòng tiêu đề</b>. Đây là dòng ghi tên cột, ví dụ STT, Họ tên, CCCD, Số tờ. Nếu ứng dụng chọn sai, sửa số dòng rồi nhấn <b>Đọc dữ liệu</b>.",
                    "Xem bảng xem trước phía dưới để chắc rằng tên cột và dữ liệu được đọc đúng.",
                ],
                s["body"],
            ),
            callout("Nếu file đang bị khóa hoặc hỏng, ứng dụng sẽ báo lỗi. Hãy đóng file trong Excel rồi thử lại. File nguồn không bị chỉnh sửa.", s["body"], LIGHT_BLUE, ACCENT),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("4. Tab 2 - Ánh xạ cột", s["h1"]),
            screenshot("tab_2.png", 155),
            Spacer(1, 4 * mm),
            para("Ánh xạ nghĩa là nói cho ứng dụng biết cột nào trong file nguồn tương ứng với từng loại dữ liệu.", s["body"]),
            numbered(
                [
                    "Nhấn <b>Tự động gợi ý</b>. Ứng dụng chỉ tự chọn khi tên cột đủ rõ.",
                    "Kiểm tra thủ công 6 trường bắt buộc: STT hộ, Họ và tên, CCCD, Số tờ, Số thửa, Diện tích.",
                    "Chọn Ngày sinh và Xứ đồng nếu nguồn có. Giới tính tự tính từ CCCD, không cần chọn cột nguồn.",
                    "Chỉ chọn các trường GCN khi file nguồn thực sự có cột GCN. Không có GCN vẫn xuất được bình thường.",
                    "Nhấn <b>Lưu vào cấu hình</b> nếu muốn dùng lại ánh xạ cho lần sau.",
                ],
                s["body"],
            ),
            callout("Không chọn đại một cột khi không chắc. Ánh xạ sai nguy hiểm hơn việc để trống rồi kiểm tra lại.", s["body"], LIGHT_RED, colors.HexColor("#C84B4B")),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("5. Tab 3 - Cấu hình VBDLIS", s["h1"]),
            screenshot("tab_3.png", 155),
            Spacer(1, 3 * mm),
            data_table(
                [
                    ["Ô cấu hình", "Cách điền"],
                    ["Mã xã", "Nhập chính xác mã đơn vị hành chính của đợt dữ liệu."],
                    ["Địa chỉ", "Nhập địa chỉ dùng cho người sử dụng đất và dùng thay thế khi thiếu Xứ đồng."],
                    ["Tiền tố tên file", "Mặc định CHUACOGIAY; có thể dùng CHUACAPGIAY khi hồ sơ yêu cầu."],
                    ["Vai trò", "Giữ Chủ hộ và Thành viên hộ gia đình."],
                    ["Mục 2", "Giữ `{PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}` nếu không có yêu cầu khác."],
                    ["Mục 49", "Giữ nguyên cấu trúc TBXN + DDK ở dưới."],
                    ["Chế độ GCN", "Nên dùng Tự động theo từng thửa."],
                    ["CCCD bất thường", "Mặc định Giữ nguyên + cảnh báo."],
                ],
                [45, 127], s,
            ),
            Spacer(1, 3 * mm),
            callout(
                "Mục 49 mặc định:<br/><font name='Courier' size='8'>{PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}-TBXN.pdf, {PREFIX}_{MA_XA}_{SO_TO}_{SO_THUA}-DDK.pdf</font><br/>Giữa hai tên file là dấu phẩy và đúng một khoảng trắng. Không có dấu phẩy ở cuối.",
                s["body"], LIGHT_YELLOW, colors.HexColor("#D6A100"),
            ),
            PageBreak(),
            para("Cấu hình (lưu cho từng xã)", s["h2"]),
            para("Mỗi xã/đơn vị có thể tạo một bộ cấu hình riêng. Cấu hình lưu mã xã, địa chỉ, ánh xạ, chế độ GCN và các quy tắc xuất file; không lưu dữ liệu người dân, mật khẩu hay tài khoản.", s["body"]),
            bullets(
                [
                    "<b>Tạo mới:</b> tạo bộ cấu hình mới.",
                    "<b>Lưu:</b> lưu các thay đổi hiện tại.",
                    "<b>Xuất ra file:</b> gửi cấu hình cho máy khác.",
                    "<b>Nhập từ file:</b> nhận cấu hình đã được người phụ trách kiểm tra.",
                ],
                s["body"],
            ),
            para("Cách dùng cấu hình an toàn", s["h2"]),
            data_table(
                [
                    ["Tình huống", "Nên làm"],
                    ["Lần đầu dùng cho một xã", "Tạo cấu hình mới, nhập mã xã/địa chỉ, kiểm tra ánh xạ rồi Lưu."],
                    ["Đợt dữ liệu tiếp theo", "Chọn lại cấu hình đã lưu, nhưng vẫn kiểm tra trang tính, dòng tiêu đề và 6 trường bắt buộc."],
                    ["Chuyển sang máy khác", "Xuất ra file từ máy đã kiểm tra; người nhận Nhập từ file rồi đối chiếu lại mã xã và ánh xạ."],
                    ["Nguồn đổi tên cột", "Không tin tuyệt đối cấu hình cũ. Đọc dữ liệu lại và rà soát Tab 2."],
                    ["Gửi cho người khác", "Chỉ gửi file cấu hình; không ghép file nguồn chứa dữ liệu cá nhân vào gói ứng dụng."],
                ],
                [48, 124], s,
            ),
            callout("Cấu hình chỉ giúp tiết kiệm thao tác. Nó không thay thế bước Kiểm tra ở Tab 5 và không tự tải dữ liệu lên VBDLIS.", s["body"], LIGHT_BLUE, ACCENT),
            Spacer(1, 5 * mm),
            para("Giới tính tự động từ CCCD (Mục 10)", s["h2"]),
            data_table(
                [
                    ["Số thứ 4 của CCCD", "Giới tính xuất ra"],
                    ["0", "Nam"],
                    ["1", "Nữ"],
                    ["2 đến 9", "Để trống"],
                    ["CCCD thiếu hoặc không đủ 12 chữ số", "Để trống"],
                ],
                [95, 77], s,
            ),
            para("Chỉ đếm từ trái sang phải trên CCCD đã chuẩn hóa và đủ 12 chữ số. Quy tắc này áp dụng cho cả chủ hộ và thành viên; không lấy giới tính từ cột nguồn hay giá trị cố định trong cấu hình cũ.", s["body"]),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("6. Tab 4 - Quy tắc nâng cao", s["h1"]),
            screenshot("tab_4.png", 158),
            Spacer(1, 3 * mm),
            callout("Người dùng thông thường không cần thay đổi tab này. Chỉ sửa khi đã biết rõ Mục/cột đích VBDLIS cần thay đổi.", s["body"], LIGHT_YELLOW, colors.HexColor("#D6A100")),
            para("Giải thích các cột trong bảng quy tắc", s["h2"]),
            data_table(
                [
                    ["Cột", "Ý nghĩa"],
                    ["Mục", "Số mục trong biểu mẫu VBDLIS (VD: Mục 2, Mục 49)."],
                    ["Cột", "Ký tự cột Excel tương ứng (VD: A, B, H, AX)."],
                    ["Tên trường", "Tên trường theo biểu mẫu chính thức. Di chuột lên tên bị rút gọn để xem đầy đủ."],
                    ["Phân loại", "Loại trường: Bắt buộc / Tùy chọn / Tự động tính / GCN / Mặc định biểu mẫu..."],
                    ["Chế độ", "Cách ứng dụng lấy giá trị cho trường này (xem bảng bên dưới)."],
                    ["Nguồn", "Tên cột trong file Excel nguồn (chỉ dùng khi Chế độ = Lấy từ cột nguồn)."],
                    ["Mặc định", "Giá trị điền sẵn khi không có dữ liệu nguồn."],
                    ["Bắt buộc", "Tích ô này nếu trường phải có giá trị, file không xuất được khi để trống."],
                    ["Thay thế", "Giá trị dùng thay thế khi điều kiện không thỏa (chỉ dùng với Chế độ Có điều kiện)."],
                ],
                [40, 132], s,
            ),
            PageBreak(),
            para("Giải thích từng Chế độ", s["h2"]),
            para("Nhấn nút Giải thích các chế độ để mở hoặc thu gọn phần trợ giúp. Mục 10 được khóa ở chế độ Tự động tính theo CCCD; các giá trị mặc định và thay thế không áp dụng cho trường này.", s["body"]),
            data_table(
                [
                    ["Chế độ", "Ý nghĩa chi tiết", "Ví dụ"],
                    ["Lấy từ cột nguồn", "Lấy dữ liệu từ cột trong file Excel nguồn được chỉ định ở cột Nguồn.", "Họ tên lấy từ cột B của file nguồn."],
                    ["Giá trị cố định", "Luôn điền một giá trị không đổi do người dùng nhập ở cột Mặc định, bỏ qua file nguồn.", "Loại hồ sơ luôn là 'Loại 5'."],
                    ["Tự động tính", "Ứng dụng tự tính và điền, người dùng không cần làm gì.", "STT tự chạy 1→N; Mục 2 ghép từ tiền tố + mã xã + tờ + thửa."],
                    ["Giữ mặc định biểu mẫu", "Giữ nguyên giá trị đã có sẵn trong biểu mẫu gốc đã được xác minh.", "Các ô tiêu đề, định dạng cố định của VBDLIS."],
                    ["Để trống", "Cố ý bỏ trống ô này trong file kết quả.", "Trường không áp dụng cho loại hồ sơ hiện tại."],
                    ["Có điều kiện", "Lấy giá trị từ cột Nguồn nếu thửa có GCN; nếu không thì dùng cột Thay thế hoặc để trống.", "Số phát hành GCN chỉ điền khi thửa có GCN."],
                ],
                [38, 76, 58], s,
            ),
            Spacer(1, 3 * mm),
            para("Giải thích màu nền trong bảng quy tắc", s["h2"]),
            data_table(
                [
                    ["Màu nền", "Phân loại", "Ý nghĩa"],
                    ["Xanh nhạt", "Bắt buộc", "Trường phải có dữ liệu; để trống sẽ báo lỗi khi kiểm tra."],
                    ["Xanh lá nhạt", "Tùy chọn", "Trường hoạt động nhưng không bắt buộc."],
                    ["Tím nhạt", "Tự động tính", "Ứng dụng tự điền, không cần cấu hình thêm."],
                    ["Cam nhạt", "GCN (tùy chọn)", "Chỉ điền khi thửa có thông tin Giấy chứng nhận."],
                    ["Xám nhạt", "Mặc định biểu mẫu", "Giữ nguyên theo biểu mẫu chính thức."],
                    ["Vàng nhạt", "Người dùng cấu hình", "Có thể điều chỉnh theo yêu cầu của từng đơn vị."],
                ],
                [30, 50, 92], s,
            ),
            callout(
                "Các trường phân loại Mặc định biểu mẫu hoặc Biểu mẫu (tùy chọn) không nên chuyển thành Bắt buộc nếu chưa có yêu cầu nghiệp vụ rõ ràng từ người phụ trách.",
                s["body"], LIGHT_YELLOW, colors.HexColor("#D6A100")
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("7. Tab 5 - Kiểm tra và Xuất", s["h1"]),
            screenshot("tab_5.png", 150),
            Spacer(1, 4 * mm),
            numbered(
                [
                    "Nhập <b>Tên file</b>. Nếu thiếu `.xlsx`, ứng dụng tự thêm.",
                    "Chọn <b>Thư mục</b> lưu kết quả.",
                    "Giữ dấu chọn <b>Xuất báo cáo kiểm tra</b> trong các lần chạy quan trọng.",
                    "Nhấn <b>Kiểm tra</b> để xem thống kê, lỗi và cảnh báo.",
                    "Nhấn <b>Xem trước</b> để kiểm tra các dòng sau khi chuyển đổi dữ liệu, đặc biệt Họ tên, Vai trò, Tờ, Thửa, Mục 2 và Mục 49.",
                    "Khi không còn LỖI, nhấn <b>Tạo file VBDLIS</b>. Ứng dụng lưu file rồi tự mở lại để kiểm tra trước khi báo hoàn thành.",
                ],
                s["body"],
            ),
            para("Nếu tên file đã tồn tại, ứng dụng tự tạo tên mới có hậu tố `_1`, `_2`... để tránh ghi đè ngoài ý muốn.", s["body"]),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("8. Hiểu LỖI, CẢNH BÁO và THÔNG TIN", s["h1"]),
            data_table(
                [
                    ["Mức", "Có xuất được?", "Ví dụ và cách xử lý"],
                    ["LỖI", "Không", "Thiếu ánh xạ bắt buộc, thiếu mã xã, thiếu CCCD, xung đột GCN, STT/kết quả sai. Phải sửa trước."],
                    ["CẢNH BÁO", "Có", "Thiếu ngày sinh, thửa không hợp lệ bị bỏ, thiếu Xứ đồng. Cần xem xét."],
                    ["THÔNG TIN", "Có", "Đã dùng địa chỉ thay thế hoặc đã loại dòng trùng hoàn toàn."],
                ],
                [28, 34, 110], s,
            ),
            para("Các lỗi thường gặp", s["h2"]),
            data_table(
                [
                    ["Thông báo", "Cách xử lý"],
                    ["Chưa ánh xạ trường bắt buộc", "Quay lại Tab 2 và chọn đúng cột."],
                    ["Không tạo thửa vì thiếu...", "Bổ sung Số tờ/Số thửa/Diện tích hoặc xác nhận dòng đó không phải thửa cần xuất."],
                    ["GCN_CONFLICT", "Cùng tờ/thửa có hai bộ GCN khác nhau. Kiểm tra file nguồn; ứng dụng không tự chọn."],
                    ["CCCD không hợp lệ", "Kiểm tra đủ 12 chữ số. Không thêm số 0 bằng phỏng đoán."],
                    ["File đang được mở trong Excel", "Đóng file kết quả hoặc chọn tên khác rồi xuất lại."],
                    ["Không tìm thấy biểu mẫu", "Dùng lại nguyên gói ZIP/thư mục phát hành; không tách riêng EXE."],
                ],
                [58, 114], s,
            ),
            callout("Trạng thái chưa có GCN là bình thường. Ở chế độ Tự động, ứng dụng chỉ thống kê Có GCN/Chưa có GCN và không tạo hàng loạt cảnh báo thiếu GCN.", s["body"], LIGHT_GREEN, colors.HexColor("#3A8D5D")),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("9. Những quy tắc giúp file giống mẫu chuẩn", s["h1"]),
            bullets(
                [
                    "File kết quả giữ cấu trúc 61 cột, hàng tiêu đề, ô gộp, phông chữ, đường viền, độ rộng cột và định dạng chính thức.",
                    "Chỉ 24 cột đang hoạt động theo mẫu chuẩn được điền mặc định; trường chỉ có trong biểu mẫu không bị ép nhập.",
                    "Vai trò chỉ là <b>Chủ hộ</b> hoặc <b>Thành viên hộ gia đình</b>; không ghi Vợ, Chồng, Con.",
                    "Mỗi Người x Thửa tạo một dòng; STT kết quả chạy liên tục từ 1 đến N.",
                    "CCCD ghi dạng văn bản để giữ số 0 đầu; CCCD bất thường không được bịa.",
                    "Giới tính (Mục 10): số thứ 4 của CCCD là <b>0 thì Nam</b>, <b>1 thì Nữ</b>, còn lại để trống. Không suy đoán từ họ tên hoặc từ các chữ số khác.",
                    "Mục 49 luôn có hai file TBXN và DDK đúng dấu phẩy + một khoảng trắng.",
                    "Hồ sơ chưa có GCN vẫn được xuất; các trường GCN để trống.",
                    "Nếu thửa có GCN, dữ liệu GCN được gắn theo từng thửa, không gắn cứng cho cả hộ.",
                    "Dòng trùng hoàn toàn được loại. Xung đột GCN bị chặn để người dùng kiểm tra.",
                    "Biểu mẫu gốc và file nguồn không bị ghi đè.",
                ],
                s["body"],
            ),
            para("Báo cáo kiểm tra", s["h2"]),
            bullets(
                [
                    "<b>Tong_quan:</b> số hộ, người, thửa, kết quả, CCCD, GCN, lỗi/cảnh báo.",
                    "<b>Theo_ho:</b> số người, số thửa và số dòng dự kiến của từng hộ.",
                    "<b>Canh_bao:</b> toàn bộ LỖI/CẢNH BÁO/THÔNG TIN và dòng nguồn liên quan.",
                    "<b>GCN:</b> trạng thái GCN theo thửa, trường thiếu và xung đột.",
                    "<b>Trang báo cáo ánh xạ:</b> quy tắc đang áp dụng cho 61 trường.",
                ],
                s["body"],
            ),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("10. Danh sách kiểm tra trước khi tải lên thủ công", s["h1"]),
            para("Ứng dụng dừng ở bước tạo Excel. Việc đăng nhập và tải lên VBDLIS được thực hiện thủ công theo quy trình của đơn vị.", s["body"]),
            data_table(
                [
                    ["Kiểm tra", "Đã xong"],
                    ["Đúng file nguồn, trang tính và dòng tiêu đề", "[   ]"],
                    ["Đúng Mã xã và Địa chỉ", "[   ]"],
                    ["6 ánh xạ bắt buộc đã đúng (STT hộ, Họ tên, CCCD, Số tờ, Số thửa, Diện tích)", "[   ]"],
                    ["Vai trò chỉ Chủ hộ / Thành viên hộ gia đình", "[   ]"],
                    ["Giới tính theo số thứ 4 của CCCD: 0 = Nam, 1 = Nữ, còn lại trống", "[   ]"],
                    ["Xem trước Tờ, Thửa, Diện tích và Xứ đồng hợp lý", "[   ]"],
                    ["Mục 2 đúng tiền tố/mã xã/tờ/thửa", "[   ]"],
                    ["Mục 49 có đúng TBXN + DDK", "[   ]"],
                    ["Không còn LỖI", "[   ]"],
                    ["Đã xem CẢNH BÁO và chấp nhận", "[   ]"],
                    ["File kết quả mở được bằng Excel", "[   ]"],
                    ["Đã lưu báo cáo kiểm tra cùng đợt dữ liệu", "[   ]"],
                    ["Đã chọn đúng file kết quả để tải lên thủ công", "[   ]"],
                ],
                [145, 27], s,
            ),
            callout("Không sửa trực tiếp hàng/cột/dòng tiêu đề của file kết quả sau khi ứng dụng đã xác minh, trừ khi người phụ trách nghiệp vụ yêu cầu rõ ràng.", s["body"], LIGHT_RED, colors.HexColor("#C84B4B")),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("11. Chia sẻ ứng dụng cho người khác", s["h1"]),
            para("Gửi file <b>VBDLIS Excel Builder Windows x64.zip</b>. Người nhận không cần cài Python và không cần kết nối Internet để tạo Excel.", s["body"]),
            para("Người gửi", s["h2"]),
            numbered(
                [
                    "Gửi nguyên file ZIP, không lấy riêng EXE.",
                    "Nếu có cấu hình chuẩn của xã, gửi thêm file JSON cấu hình đã được kiểm tra.",
                    "Không đưa file Excel nguồn chứa dữ liệu cá nhân vào ZIP ứng dụng chung.",
                    "Thông báo cho người nhận vị trí tài liệu này: <b>HƯỚNG DẪN SỬ DỤNG.pdf</b>.",
                ],
                s["body"],
            ),
            para("Người nhận", s["h2"]),
            numbered(
                [
                    "Tải ZIP về máy.",
                    "Nhấp chuột phải, chọn <b>Giải nén tất cả</b>.",
                    "Mở thư mục vừa giải nén, đọc file <b>BẮT ĐẦU TẠI ĐÂY.txt</b>.",
                    "Chạy <b>VBDLIS Excel Builder.exe</b> trong cùng thư mục với `_internal`.",
                    "Tạo hoặc nhập cấu hình, sau đó thực hiện từ Tab 1 đến Tab 5.",
                ],
                s["body"],
            ),
            callout("Gói phát hành không chứa GOLDEN_SUCCESS_REFERENCE, không chứa file nguồn của người dùng và không chứa tài khoản/mật khẩu/token.", s["body"], LIGHT_GREEN, colors.HexColor("#3A8D5D")),
            PageBreak(),
        ]
    )

    story.extend(
        [
            para("12. Hỏi đáp nhanh", s["h1"]),
            para("<b>Không có GCN có xuất được không?</b><br/>Có. Đây là trạng thái bình thường; các trường GCN được để trống.", s["body"]),
            para("<b>Một hộ có nhiều thửa thì sao?</b><br/>Ứng dụng lấy mọi người trong hộ nhân với mọi thửa hợp lệ và tạo STT mới liên tục.", s["body"]),
            para("<b>Các thửa trong cùng hộ có GCN khác nhau được không?</b><br/>Được. GCN được gắn theo từng thửa.", s["body"]),
            para("<b>Có cần đổi Mục 49 không?</b><br/>Thông thường không. Chỉ đổi khi có yêu cầu nghiệp vụ mới và đã hiểu ảnh hưởng đến tên tài liệu được tải lên.", s["body"]),
            para("<b>Có thể dùng cho xã khác không?</b><br/>Có. Tạo cấu hình mới, đổi mã xã, địa chỉ và ánh xạ; không cần sửa mã nguồn.", s["body"]),
            para("<b>Tại sao Giới tính bị để trống?</b><br/>Chỉ CCCD đủ 12 chữ số có số thứ 4 là 0 hoặc 1 mới được điền Nam hoặc Nữ. Các trường hợp khác để trống, kể cả khi file nguồn có ghi giới tính.", s["body"]),
            para("<b>Ứng dụng có tự tải dữ liệu lên không?</b><br/>Không. Ứng dụng chỉ tạo và kiểm tra Excel. Người dùng tự tải lên thủ công.", s["body"]),
            para("<b>Có thể gửi riêng EXE không?</b><br/>Không. Hãy gửi nguyên ZIP hoặc cả thư mục phát hành vì EXE cần thư mục `_internal`.", s["body"]),
            para("<b>File kết quả có giống từng byte với mẫu chuẩn không?</b><br/>Không cần giống từng byte. Mục tiêu là tương đương về cấu trúc, dữ liệu, kiểu, định dạng cần thiết và các quy tắc đã chạy thành công.", s["body"]),
            Spacer(1, 6 * mm),
            callout("Khi gặp dữ liệu bất thường chưa biết xử lý, dừng lại ở bước Kiểm tra, giữ file nguồn nguyên trạng và gửi kèm báo cáo kiểm tra cho người phụ trách nghiệp vụ.", s["body"], LIGHT_BLUE, ACCENT),
            Spacer(1, 16 * mm),
            para("HẾT HƯỚNG DẪN", ParagraphStyle("End", parent=s["h1"], alignment=TA_CENTER)),
        ]
    )
    return story


def main() -> int:
    register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    s = styles()
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm, title="Hướng dẫn sử dụng VBDLIS Excel Builder",
        author="VBDLIS Excel Builder",
    )
    doc.build(build_story(s), onFirstPage=header_footer, onLaterPages=header_footer)
    reader = PdfReader(str(OUTPUT))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if len(reader.pages) < 10:
        raise RuntimeError(f"Hướng dẫn quá ngắn: {len(reader.pages)} trang")
    for required in ("GOLDEN_SUCCESS_REFERENCE", "tải lên thủ công", "Mục 49", "Không có GCN"):
        if required not in text:
            raise RuntimeError(f"Thiếu nội dung bắt buộc: {required}")
    print(f"user-guide.pdf | pages={len(reader.pages)} | bytes={OUTPUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
