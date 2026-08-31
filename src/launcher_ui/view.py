"""Launcher presentation and help navigation. Callbacks never process user data."""
import unicodedata
from PySide6.QtCore import Qt, QSize, QEvent
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QLineEdit,QVBoxLayout,QHBoxLayout,
    QGridLayout,QScrollArea,QStackedWidget,QButtonGroup,QSizePolicy,QApplication,QLayout)
from .icons import icon
from .help_page import HelpPage

TOOLS = (
    ("notice","prepare","MẪU 22","Tạo thông báo đất đai","Từ Excel đến thông báo Word. Kiểm tra dữ liệu, xem trước rồi xác nhận tạo."),
    ("excel","prepare","VBDLIS","Excel Builder","Chuẩn hóa dữ liệu, ánh xạ cột và xuất biểu mẫu hồ sơ VBDLIS."),
    ("rename","prepare","TỆP HỒ SƠ","Auto Rename","Nhân bản và đặt tên Word, PDF theo thông tin hộ và thửa đất."),
    ("cleaner","prepare","PDF ĐÃ KÝ","PDF Cleaner","Quét, xem trước và xử lý tệp PDF; chuẩn hóa tên văn bản đã ký."),
    ("downloader","hpnet","TẢI XUỐNG","PDF Downloader","Lọc, đối soát và tải PDF đã ký từ mục Văn bản đi trên HPNet."),
    ("upload","hpnet","TẢI LÊN","Upload Dự Thảo","Kiểm tra trùng và tải tệp Word vào Văn bản dự thảo trên HPNet."),
    ("approve","hpnet","CHUYỂN DUYỆT","Duyệt Dự Thảo","Quét hồ sơ, kiểm tra người nhận và xác nhận chuyển duyệt."),
)


def folded(text):
    return "".join(c for c in unicodedata.normalize("NFD",text.casefold().replace("đ","d")) if not unicodedata.combining(c))


def label(text,name=None):
    item=QLabel(text); item.setWordWrap(True)
    if name: item.setObjectName(name)
    return item


class ToolCard(QFrame):
    def __init__(self,tool,handler,parent=None):
        super().__init__(parent); key,group,category,title,description=tool
        self.setObjectName("toolCard"); self.setMinimumHeight(224)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        box=QVBoxLayout(self); box.setContentsMargins(20,20,20,18); box.setSpacing(12)
        row=QHBoxLayout(); symbol=QLabel(); symbol.setPixmap(icon(key).pixmap(32,32)); symbol.setFixedSize(36,36)
        row.addWidget(symbol); row.addStretch(); badge=label(category,"badge"); row.addWidget(badge); box.addLayout(row)
        box.addWidget(label(title,"cardTitle"))
        text=label(description,"muted"); text.setMinimumHeight(46); box.addWidget(text,1)
        self.button=QPushButton("Mở công cụ"); self.button.setObjectName("openTool")
        self.button.setIcon(icon("arrow","#FFFFFF")); self.button.setIconSize(QSize(18,18))
        self.button.setLayoutDirection(Qt.RightToLeft); self.button.setAccessibleName(f"Mở {title}")
        self.button.setToolTip(f"Mở {title} trong cửa sổ riêng"); self.button.setCursor(Qt.PointingHandCursor)
        self.button.clicked.connect(handler); box.addWidget(self.button)


class LauncherView(QWidget):
    def __init__(self,hub):
        super().__init__(hub); self.hub=hub; self.setObjectName("launcherView")
        self.category="all"; self.cards={}; self.groups={}; self.grid_columns=0
        outer=QHBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        sidebar=QFrame(); sidebar.setObjectName("navigation"); sidebar.setFixedWidth(230)
        side=QVBoxLayout(sidebar); side.setContentsMargins(16,28,16,20); side.setSpacing(8)
        branding=QHBoxLayout(); logo=QLabel(); logo.setPixmap(hub.windowIcon().pixmap(40,40)); branding.addWidget(logo)
        brand_text=QVBoxLayout(); brand_text.setSpacing(2); brand_text.addWidget(label("HPNET","brand")); brand_text.addWidget(label("& VBDLIS Tools","muted"))
        branding.addLayout(brand_text,1); side.addLayout(branding); side.addSpacing(32)
        side.addWidget(label("KHÔNG GIAN LÀM VIỆC","navigationLabel")); side.addSpacing(6)
        self.nav_group=QButtonGroup(self); self.nav_buttons={}
        for key,text,symbol in (("all","Tất cả công cụ","grid"),("prepare","Chuẩn bị hồ sơ","folder"),
                                ("hpnet","Làm việc với HPNet","approve"),("help","Hướng dẫn sử dụng","help")):
            if key=="help":
                side.addSpacing(24); side.addWidget(label("TRỢ GIÚP","navigationLabel")); side.addSpacing(6)
            button=QPushButton(text); button.setObjectName("navButton"); button.setCheckable(True)
            button.setIcon(icon(symbol)); button.setIconSize(QSize(20,20)); button.setCursor(Qt.PointingHandCursor)
            button.setAccessibleName(text); button.clicked.connect(lambda checked=False,k=key:self.navigate(k))
            self.nav_group.addButton(button); self.nav_buttons[key]=button; side.addWidget(button)
        side.addStretch(1)
        note=QFrame(); note.setObjectName("safetyNote"); note_box=QVBoxLayout(note); note_box.setContentsMargins(12,14,12,14)
        note_box.addWidget(label("Bạn luôn kiểm soát","eyebrow"))
        note_box.addWidget(label("Mở công cụ không tự tải lên, duyệt hoặc xóa dữ liệu.","muted")); side.addWidget(note)
        side.addSpacing(12); side.addWidget(label("7 công cụ · Một nơi làm việc","muted")); outer.addWidget(sidebar)
        self.pages=QStackedWidget(); outer.addWidget(self.pages,1)
        self.tools_page=QWidget(); page=QVBoxLayout(self.tools_page); page.setContentsMargins(28,26,28,20); page.setSpacing(16)
        self.eyebrow=label("BỘ CÔNG CỤ XỬ LÝ HỒ SƠ","eyebrow"); page.addWidget(self.eyebrow)
        self.heading=label("Chọn công cụ. Bắt đầu công việc.","pageTitle"); page.addWidget(self.heading)
        self.description=label("Chuẩn bị hồ sơ và làm việc với HPNet, trong các cửa sổ riêng quen thuộc.","muted"); page.addWidget(self.description)
        search_row=QHBoxLayout(); search_row.setSpacing(12)
        self.search=QLineEdit(); self.search.setPlaceholderText("Tìm công cụ, ví dụ: Excel, Word, PDF, duyệt…")
        self.search.setAccessibleName("Tìm công cụ"); self.search.setClearButtonEnabled(True)
        self.search.addAction(icon("search","#53657A"),QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self.filter_tools); search_row.addWidget(self.search,1)
        self.count=label("7 công cụ","muted"); search_row.addWidget(self.count); page.addLayout(search_row)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content=QWidget(); content.setObjectName("toolContent"); body=QVBoxLayout(content); body.setContentsMargins(0,4,12,8); body.setSpacing(20)
        body.setSizeConstraint(QLayout.SetMinimumSize)
        handlers={"notice":hub.launch_notice_builder,"excel":hub.launch_excel_builder,"rename":hub.launch_auto_rename,
                  "cleaner":hub.launch_pdf_cleaner,"downloader":lambda:hub.launch_external("downloader"),
                  "upload":lambda:hub.launch_external("upload"),"approve":lambda:hub.launch_external("approve")}
        for key,title,description in (("prepare","Chuẩn bị dữ liệu & hồ sơ","Tạo biểu mẫu, chuẩn hóa dữ liệu và sắp xếp tệp."),
                                      ("hpnet","Làm việc với HPNet","Tự đăng nhập VNeID trong cửa sổ của từng công cụ.")):
            section=QWidget(); section_box=QVBoxLayout(section); section_box.setContentsMargins(0,0,0,0); section_box.setSpacing(12)
            section_box.setSizeConstraint(QLayout.SetMinimumSize)
            section_box.addWidget(label(title,"sectionTitle")); section_box.addWidget(label(description,"muted"))
            grid=QGridLayout(); grid.setContentsMargins(0,0,0,0); grid.setSpacing(16); section_box.addLayout(grid)
            self.groups[key]=(section,grid)
            for tool in TOOLS:
                if tool[1]==key:
                    card=ToolCard(tool,handlers[tool[0]]); self.cards[tool[0]]=card; hub.tool_buttons[tool[0]]=card.button
            body.addWidget(section)
        self.empty=QFrame(); self.empty.setObjectName("safetyNote"); empty_box=QVBoxLayout(self.empty); empty_box.setContentsMargins(24,32,24,32)
        empty_box.addWidget(label("Không tìm thấy công cụ","sectionTitle"))
        empty_box.addWidget(label("Thử tên ngắn hơn, bỏ dấu hoặc quay lại tất cả công cụ.","muted"))
        reset=QPushButton("Hiện tất cả công cụ"); reset.clicked.connect(self.reset_search); empty_box.addWidget(reset,0,Qt.AlignLeft)
        body.addWidget(self.empty); self.empty.hide(); body.addStretch(1)
        self.scroll.setWidget(content); page.addWidget(self.scroll,1)
        self.pages.addWidget(self.tools_page); self.help_page=HelpPage(); self.pages.addWidget(self.help_page)
        self.scroll.viewport().installEventFilter(self)
        self.nav_buttons["all"].setChecked(True); self.filter_tools()
        self.help_shortcut=QShortcut(QKeySequence("F1"),self); self.help_shortcut.activated.connect(self.show_help)
        self.search_shortcut=QShortcut(QKeySequence.Find,self); self.search_shortcut.activated.connect(self.focus_search)
        self.search_shortcut.setContext(Qt.WidgetWithChildrenShortcut); self.help_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        QApplication.instance().focusChanged.connect(self.keep_focus_visible)

    def keep_focus_visible(self,old,now):
        if now and self.scroll.isAncestorOf(now): self.scroll.ensureWidgetVisible(now,12,16)

    def eventFilter(self,watched,event):
        if watched is self.scroll.viewport() and event.type()==QEvent.Resize:
            columns=3 if event.size().width()>=1120 else 2 if event.size().width()>=620 else 1
            if columns!=self.grid_columns: self.grid_columns=columns; self.filter_tools()
        return super().eventFilter(watched,event)

    def filter_tools(self,*_):
        query=folded(self.search.text().strip()); visible=[]; columns=max(1,self.grid_columns)
        for group,(section,grid) in self.groups.items():
            while grid.count(): grid.takeAt(0)
            for column in range(3): grid.setColumnStretch(column,0)
            matching=[t for t in TOOLS if t[1]==group and self.category in ("all",group)
                      and all(word in folded(" ".join(t)) for word in query.split())]
            section.setVisible(bool(matching))
            for tool in TOOLS:
                if tool[1]==group: self.cards[tool[0]].setVisible(tool in matching)
            for index,tool in enumerate(matching):
                grid.addWidget(self.cards[tool[0]],index//columns,index%columns); grid.setColumnStretch(index%columns,1)
                visible.append(tool[0])
            # Recompute after re-showing a filtered section or changing grid columns.
            grid.invalidate(); section.layout().invalidate(); section.layout().activate()
            section.updateGeometry()
        self.count.setText(f"{len(visible)} / 7 công cụ"); self.empty.setVisible(not visible)
        self.visible_tool_keys=visible
        controls=[self.search,*[self.hub.tool_buttons[key] for key in visible]]
        for before,after in zip(controls,controls[1:]): QWidget.setTabOrder(before,after)

    def navigate(self,key):
        self.nav_buttons[key].setChecked(True)
        if key=="help":
            self.pages.setCurrentIndex(1); return
        self.pages.setCurrentIndex(0); self.category=key
        self.heading.setText({"all":"Chọn công cụ. Bắt đầu công việc.","prepare":"Chuẩn bị hồ sơ, rõ ràng từng bước.","hpnet":"Làm việc với HPNet."}[key])
        self.filter_tools()

    def show_help(self): self.navigate("help")

    def focus_search(self):
        field=self.help_page.search if self.pages.currentIndex()==1 else self.search
        field.setFocus(); field.selectAll()

    def reset_search(self): self.search.clear(); self.navigate("all")
