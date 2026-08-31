"""Read the complete existing guides inside the launcher, without opening external apps."""
from html import escape
from pathlib import Path
import re
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,
                             QTextBrowser,QListWidget,QListWidgetItem,QSplitter,QStackedWidget)

GUIDES = (
    ("Quy trình hiện hành", "HUONG_DAN_BAN_SUA.txt", "docs/HUONG_DAN_BAN_SUA.txt"),
    ("Hướng dẫn chi tiết ban đầu", "Huong_dan_su_dung_chi_tiet.txt", "Huong_dan_su_dung_chi_tiet.txt"),
    ("Cài đặt và khởi chạy", "README.txt", "README.txt"),
)


def guide_sources():
    root=Path(__file__).resolve().parents[2]
    bundled=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parents[1]))/"launcher_help"
    return [(title, bundled/name if (bundled/name).is_file() else root/relative) for title,name,relative in GUIDES]


def guide_html(sources):
    parts=[]; chapters=[]; texts=[]
    for document,(title,path) in enumerate(sources):
        anchor=f"guide-{document}"; chapters.append((title,anchor))
        parts.append(f'<h1><a name="{anchor}"></a>{escape(title)}</h1>')
        if title==GUIDES[1][0]:
            parts.append('<p class="note">Bản hướng dẫn ban đầu được giữ đầy đủ để tham khảo. Các thay đổi về mẫu 22 và giấy tờ nhân thân nằm trong trang Quy trình hiện hành.</p>')
        try: text=path.read_text(encoding="utf-8-sig")
        except OSError:
            text="Không đọc được tài liệu hướng dẫn. Hãy giải nén lại đầy đủ gói release và giữ thư mục _internal cạnh EXE."
        texts.append(text)
        for number,line in enumerate(text.splitlines()):
            stripped=line.strip()
            if not stripped: continue
            if set(stripped)<={"=","-"}: continue  # Decorative separators become section spacing.
            if re.match(r"^\d+\.\s",stripped) or (stripped.isupper() and len(stripped)<100):
                anchor=f"guide-{document}-{number}"
                parts.append(f'<h2><a name="{anchor}"></a>{escape(stripped)}</h2>')
            else: parts.append(f'<p>{escape(stripped)}</p>')
    return "".join(parts),chapters,texts


class HelpPage(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        box=QVBoxLayout(self); box.setContentsMargins(28,24,28,24); box.setSpacing(16)
        title=QLabel("Hướng dẫn sử dụng"); title.setObjectName("pageTitle"); box.addWidget(title)
        description=QLabel("Chọn một mục bên trái để mở trang riêng. Tìm kiếm chỉ trong trang đang đọc.")
        description.setWordWrap(True); description.setObjectName("muted"); box.addWidget(description)
        search_row=QHBoxLayout(); search_row.setSpacing(8)
        self.search=QLineEdit(); self.search.setPlaceholderText("Tìm trong trang này, ví dụ: Mục 29, giấy tờ, nhật ký…")
        self.search.setAccessibleName("Tìm trong hướng dẫn"); search_row.addWidget(self.search,1)
        previous=QPushButton("Trước"); following=QPushButton("Tiếp")
        previous.setAccessibleName("Kết quả tìm kiếm trước"); following.setAccessibleName("Kết quả tìm kiếm tiếp theo")
        previous.clicked.connect(lambda:self.find_text(True)); following.clicked.connect(lambda:self.find_text(False))
        self.search.returnPressed.connect(lambda:self.find_text(False)); search_row.addWidget(previous); search_row.addWidget(following)
        box.addLayout(search_row)
        self.search_status=QLabel(self.default_search_status())
        self.search_status.setObjectName("muted"); self.search_status.setWordWrap(True); box.addWidget(self.search_status)
        split=QSplitter(Qt.Horizontal); self.contents=QListWidget(); self.contents.setWordWrap(True)
        self.contents.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.contents.setTextElideMode(Qt.ElideRight)
        self.contents.setAccessibleName("Các trang hướng dẫn"); self.contents.setMinimumWidth(170)
        self.contents.setMaximumWidth(270)
        self.documents=QStackedWidget(); self.browsers=[]; self.source_texts=[]; self.search_states=[]
        for index,source in enumerate(guide_sources()):
            title,_=source
            browser=QTextBrowser(); browser.setAccessibleName(f"Nội dung: {title}")
            browser.setOpenExternalLinks(False)
            browser.document().setDefaultStyleSheet("h1 {font-size:19pt; color:#172B42; margin-top:24px;} h2 {font-size:12pt; color:#2458C5; margin-top:22px; margin-bottom:10px;} p {font-size:11pt; line-height:150%; margin:8px 0;} .note {color:#53657A;}")
            html,_,texts=guide_html([source]); browser.setHtml(html)
            self.source_texts.extend(texts); self.browsers.append(browser); self.documents.addWidget(browser)
            self.search_states.append(("",self.default_search_status()))
            item=QListWidgetItem(title); item.setData(Qt.UserRole,index); item.setToolTip(title); self.contents.addItem(item)
        self.contents.currentItemChanged.connect(self.select_chapter)
        split.addWidget(self.contents); split.addWidget(self.documents); split.setSizes([225,650]); split.setStretchFactor(1,1)
        split.setChildrenCollapsible(False); box.addWidget(split,1)
        self.contents.setCurrentRow(0)

    @property
    def browser(self):
        """The active page only; documents, cursor and scroll positions stay separate."""
        return self.documents.currentWidget()

    @staticmethod
    def default_search_status():
        return "Enter để tìm trong trang • Ctrl+F để nhập từ khóa • Có thể sao chép nội dung"

    def select_chapter(self,item,previous=None):
        if not item: return
        previous_index=self.documents.currentIndex()
        self.search_states[previous_index]=(self.search.text(),self.search_status.text())
        index=item.data(Qt.UserRole); self.documents.setCurrentIndex(index)
        query,status=self.search_states[index]
        self.search.setText(query); self.search_status.setText(status)

    def find_text(self,backward=False):
        query=self.search.text().strip()
        if not query:
            self.search_status.setText("Nhập từ khóa cần tìm."); return
        flags=QTextDocument.FindBackward if backward else QTextDocument.FindFlags()
        if not self.browser.find(query,flags):
            cursor=self.browser.textCursor(); cursor.movePosition(QTextCursor.End if backward else QTextCursor.Start)
            self.browser.setTextCursor(cursor)
            if not self.browser.find(query,flags):
                self.search_status.setText(f"Không tìm thấy “{query}” trong trang này. Thử từ khóa khác hoặc chọn trang khác."); return
        self.search_status.setText(f"Đã tìm thấy “{query}” • Bấm Trước/Tiếp để xem kết quả khác")
