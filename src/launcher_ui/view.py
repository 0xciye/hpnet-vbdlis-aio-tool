"""Launcher presentation and help navigation. Callbacks never process user data."""
import unicodedata
from PySide6.QtCore import Qt, QSize, QEvent, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QColor
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QLineEdit,QVBoxLayout,QHBoxLayout,
    QGridLayout,QScrollArea,QStackedWidget,QButtonGroup,QSizePolicy,QApplication,QLayout,
    QGraphicsDropShadowEffect,QProgressBar)
from .icons import icon
from .help_page import HelpPage

TOOLS = (
    ("notice","prepare","MẪU 22","Tạo thông báo đất đai","Từ Excel đến thông báo Word. Kiểm tra dữ liệu, xem trước rồi xác nhận tạo."),
    ("excel","prepare","VBDLIS","Excel Builder","Chuẩn hóa dữ liệu, ánh xạ cột và xuất biểu mẫu hồ sơ VBDLIS."),
    ("duplicate_parcel","prepare","EXCEL AN TOÀN","Kiểm tra & Làm sạch thửa trùng","Tách hộ theo Tổng DT, xem trước và chỉ clear các bản ghi trùng hoàn toàn."),
    ("data_normalizer","prepare","EXCEL TIỆN ÍCH","Chuẩn hóa Họ tên & Ngày sinh","Chuẩn hóa định dạng tên và ngày sinh độc lập, không đoán dữ liệu mơ hồ."),
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


class ToolCard(QPushButton):
    launch_finished=Signal(str,bool,str)

    def __init__(self,tool,handler,parent=None):
        super().__init__(parent); key,group,category,title,description=tool
        self.key=key; self.title=title; self.handler=handler; self.busy=False; self.hovered=False
        self.button=self  # Compatibility for launch routing; there is no nested action button.
        self.setObjectName("toolCard"); self.setMinimumHeight(206)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        self.setCursor(Qt.PointingHandCursor); self.setAccessibleName(f"Mở {title}")
        self.setAccessibleDescription(description); self.setToolTip(f"Bấm vào thẻ để mở {title} trong cửa sổ riêng")
        self.setProperty("cardState","idle")
        self.shadow=QGraphicsDropShadowEffect(self); self.shadow.setBlurRadius(12); self.shadow.setOffset(0,3)
        self.shadow.setColor(QColor(23,43,66,22)); self.setGraphicsEffect(self.shadow)
        self.feedback_timer=QTimer(self); self.feedback_timer.setSingleShot(True); self.feedback_timer.timeout.connect(self.reset_feedback)
        box=QVBoxLayout(self); box.setContentsMargins(20,20,20,16); box.setSpacing(11)
        row=QHBoxLayout(); self.symbol=QLabel(); self.symbol.setPixmap(icon(key).pixmap(32,32)); self.symbol.setFixedSize(36,36)
        self.symbol.setAttribute(Qt.WA_TransparentForMouseEvents)
        row.addWidget(self.symbol); row.addStretch(); self.badge=label(category,"badge"); row.addWidget(self.badge); box.addLayout(row)
        self.title_label=label(title,"cardTitle"); box.addWidget(self.title_label)
        self.description_label=label(description,"muted"); self.description_label.setMinimumHeight(46); box.addWidget(self.description_label,1)
        footer=QHBoxLayout(); footer.setSpacing(8)
        self.progress=QProgressBar(); self.progress.setObjectName("cardProgress"); self.progress.setRange(0,0); self.progress.setFixedSize(54,6); self.progress.hide()
        self.status=label("","cardStatus"); self.status.hide(); footer.addWidget(self.progress); footer.addWidget(self.status); footer.addStretch(1)
        self.arrow=QLabel(); self.arrow.setPixmap(icon("arrow","#2458C5").pixmap(18,18)); self.arrow.setFixedSize(20,20); self.arrow.hide(); footer.addWidget(self.arrow)
        box.addLayout(footer)
        for child in (self.badge,self.title_label,self.description_label,self.progress,self.status,self.arrow):
            child.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.clicked.connect(self.start_launch)

    def refresh_style(self):
        self.style().unpolish(self); self.style().polish(self); self.update()

    def set_hovered(self,value):
        self.hovered=value; self.setProperty("hovered",value)
        if value:
            self.shadow.setBlurRadius(24); self.shadow.setOffset(0,6); self.shadow.setColor(QColor(36,88,197,62))
        else:
            self.shadow.setBlurRadius(12); self.shadow.setOffset(0,3); self.shadow.setColor(QColor(23,43,66,22))
        self.arrow.setVisible((value or self.hasFocus()) and not self.busy)
        self.refresh_style()

    def enterEvent(self,event): self.set_hovered(True); super().enterEvent(event)
    def leaveEvent(self,event): self.set_hovered(False); super().leaveEvent(event)
    def focusInEvent(self,event):
        self.arrow.setVisible(not self.busy); super().focusInEvent(event)
    def focusOutEvent(self,event):
        self.arrow.setVisible(self.hovered and not self.busy); super().focusOutEvent(event)

    def start_launch(self):
        if self.busy: return
        self.feedback_timer.stop(); self.busy=True; self.setEnabled(False); self.setCursor(Qt.ArrowCursor)
        self.setProperty("cardState","busy"); self.status.setText("Đang mở công cụ…"); self.status.show(); self.progress.show(); self.arrow.hide()
        self.refresh_style()
        QTimer.singleShot(0,self.invoke_handler)

    def invoke_handler(self):
        try:
            status_bar=self.window().statusBar() if hasattr(self.window(),"statusBar") else None
            if status_bar: status_bar.clearMessage()
            result=self.handler()
            core_status=status_bar.currentMessage() if status_bar else ""
            success=result is not False and (result is True or core_status.startswith("Đã mở"))
            message="Đã mở công cụ" if success else "Không thể mở công cụ"
        except Exception:
            success=False; message="Không thể mở công cụ"
        self.finish_launch(success,message)

    def finish_launch(self,success,message):
        self.busy=False; self.setEnabled(True); self.setCursor(Qt.PointingHandCursor)
        self.progress.hide(); self.status.setText(message); self.status.show()
        self.setProperty("cardState","success" if success else "error"); self.refresh_style()
        self.launch_finished.emit(self.title,success,message); self.feedback_timer.start(3000)

    def reset_feedback(self):
        if self.busy: return
        self.status.hide(); self.status.clear(); self.setProperty("cardState","idle")
        self.arrow.setVisible(self.hovered or self.hasFocus()); self.refresh_style()


class Toast(QFrame):
    def __init__(self,parent):
        super().__init__(parent); self.setObjectName("toast"); self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setProperty("toastState","success"); self.setFixedWidth(310); self.hide()
        row=QHBoxLayout(self); row.setContentsMargins(14,12,14,12); row.setSpacing(10)
        self.marker=QLabel(); self.marker.setObjectName("toastMarker"); self.marker.setFixedSize(8,8); row.addWidget(self.marker)
        self.text=QLabel(); self.text.setWordWrap(True); self.text.setObjectName("toastText"); row.addWidget(self.text,1)
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.hide)

    def show_message(self,title,success):
        self.setProperty("toastState","success" if success else "error")
        self.text.setText(f"{title}\n{'Đã mở trong cửa sổ riêng.' if success else 'Không thể mở. Kiểm tra thông báo lỗi.'}")
        self.style().unpolish(self); self.style().polish(self); self.adjustSize(); self.setFixedWidth(310)
        self.move(max(16,self.parentWidget().width()-self.width()-24),max(16,self.parentWidget().height()-self.height()-24))
        self.show(); self.raise_(); self.timer.start(3000)


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
        outer.addWidget(sidebar)
        self.pages=QStackedWidget(); outer.addWidget(self.pages,1)
        self.tools_page=QWidget(); page=QVBoxLayout(self.tools_page); page.setContentsMargins(28,26,28,20); page.setSpacing(16)
        self.eyebrow=label("BỘ CÔNG CỤ XỬ LÝ HỒ SƠ","eyebrow"); page.addWidget(self.eyebrow)
        self.heading=label("Chọn công cụ. Bắt đầu công việc.","pageTitle"); page.addWidget(self.heading)
        self.description=label("Chuẩn bị hồ sơ và làm việc với HPNet, trong các cửa sổ riêng quen thuộc.","muted"); page.addWidget(self.description)
        search_row=QHBoxLayout(); search_row.setSpacing(12); search_row.setContentsMargins(0,0,0,10); search_row.addStretch(1)
        self.search=QLineEdit(); self.search.setPlaceholderText("Tìm công cụ, ví dụ: Excel, Word, PDF, duyệt…")
        self.search.setMaximumWidth(680)
        self.search.setAccessibleName("Tìm công cụ"); self.search.setClearButtonEnabled(True)
        self.search.addAction(icon("search","#53657A"),QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self.filter_tools); search_row.addWidget(self.search,1)
        self.count=label(f"{len(TOOLS)} công cụ","muted"); search_row.addWidget(self.count); search_row.addStretch(1); page.addLayout(search_row)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content=QWidget(); content.setObjectName("toolContent"); body=QVBoxLayout(content); body.setContentsMargins(0,4,12,8); body.setSpacing(20)
        body.setSizeConstraint(QLayout.SetMinimumSize)
        handlers={"notice":hub.launch_notice_builder,"excel":hub.launch_excel_builder,"rename":hub.launch_auto_rename,
                  "duplicate_parcel":hub.launch_duplicate_parcel,"data_normalizer":hub.launch_data_normalizer,
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
                    card=ToolCard(tool,handlers[tool[0]]); card.launch_finished.connect(self.show_launch_result)
                    self.cards[tool[0]]=card; hub.tool_buttons[tool[0]]=card
            body.addWidget(section)
        self.empty=QFrame(); self.empty.setObjectName("safetyNote"); empty_box=QVBoxLayout(self.empty); empty_box.setContentsMargins(24,32,24,32)
        empty_box.addWidget(label("Không tìm thấy công cụ","sectionTitle"))
        empty_box.addWidget(label("Thử tên ngắn hơn, bỏ dấu hoặc quay lại tất cả công cụ.","muted"))
        reset=QPushButton("Hiện tất cả công cụ"); reset.clicked.connect(self.reset_search); empty_box.addWidget(reset,0,Qt.AlignLeft)
        body.addWidget(self.empty); self.empty.hide(); body.addStretch(1)
        self.scroll.setWidget(content); page.addWidget(self.scroll,1)
        self.pages.addWidget(self.tools_page); self.help_page=HelpPage(); self.pages.addWidget(self.help_page)
        self.toast=Toast(self); self.toast.hide()
        self.scroll.viewport().installEventFilter(self)
        self.nav_buttons["all"].setChecked(True); self.filter_tools()
        self.help_shortcut=QShortcut(QKeySequence("F1"),self); self.help_shortcut.activated.connect(self.show_help)
        self.search_shortcut=QShortcut(QKeySequence.Find,self); self.search_shortcut.activated.connect(self.focus_search)
        self.search_shortcut.setContext(Qt.WidgetWithChildrenShortcut); self.help_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        QApplication.instance().focusChanged.connect(self.keep_focus_visible)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,"toast") and self.toast.isVisible():
            self.toast.move(max(16,self.width()-self.toast.width()-24),max(16,self.height()-self.toast.height()-24))

    def show_launch_result(self,title,success,message):
        self.toast.show_message(title,success)
        self.hub.statusBar().showMessage(f"{message}: {title}.",3000)

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
        self.count.setText(f"{len(visible)} / {len(TOOLS)} công cụ"); self.empty.setVisible(not visible)
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
