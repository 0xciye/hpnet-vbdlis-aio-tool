"""Local Qt theme: deliberately never changes QApplication's global palette."""
from PySide6.QtGui import QColor, QPalette

COLORS = {
    "canvas":"#F5F7FB", "surface":"#FFFFFF", "text":"#172B42", "muted":"#53657A",
    "primary":"#2458C5", "hover":"#1948A8", "pressed":"#153B88", "tint":"#EAF0FD",
    "border":"#DCE4EF", "focus":"#2458C5", "disabled":"#6B7788", "success":"#2E7D32", "error":"#C53D45",
}


def palette():
    result=QPalette()
    for role,key in ((QPalette.Window,"canvas"),(QPalette.Base,"surface"),(QPalette.WindowText,"text"),
                     (QPalette.Text,"text"),(QPalette.Button,"surface"),(QPalette.ButtonText,"text"),
                     (QPalette.Highlight,"primary")):
        result.setColor(role,QColor(COLORS[key]))
    result.setColor(QPalette.HighlightedText,QColor("white"))
    return result


STYLE = """
QMainWindow, QWidget#launcherView { background: @canvas; }
QWidget { font-family: 'Segoe UI'; font-size: 10pt; color: @text; }
QFrame#navigation { background: @surface; border-right: 1px solid @border; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 17pt; font-weight: 700; }
QLabel#subtitle, QLabel#muted { color: @muted; }
QLabel#navigationLabel { color: @muted; font-size: 9pt; font-weight: 600; }
QLabel#pageTitle { font-size: 22pt; font-weight: 600; }
QLabel#sectionTitle { font-size: 13pt; font-weight: 700; }
QLabel#cardTitle { font-size: 13pt; font-weight: 650; }
QLabel#eyebrow { font-size: 9pt; font-weight: 700; color: @primary; }
QLabel#badge { color: @primary; background: @tint; border-radius: 5px; padding: 4px 8px; font-size: 9pt; }
QPushButton#toolCard { background: @surface; border: 1px solid @border; border-radius: 12px; padding: 0; text-align: left; }
QPushButton#toolCard:hover, QPushButton#toolCard[hovered="true"] { border-color: @primary; background: #FBFCFF; }
QPushButton#toolCard:pressed { background: @tint; border-color: @pressed; }
QPushButton#toolCard:focus { border: 2px solid @focus; }
QPushButton#toolCard:disabled { background: #F8FAFD; color: @text; }
QPushButton#toolCard[cardState="busy"] { border: 2px solid @primary; background: #F7F9FF; }
QPushButton#toolCard[cardState="success"] { border: 2px solid @success; background: #F8FCF8; }
QPushButton#toolCard[cardState="error"] { border: 2px solid @error; background: #FFF9F9; }
QPushButton#toolCard QLabel#cardTitle { color: @text; }
QPushButton#toolCard QLabel#muted { color: @muted; }
QLabel#cardStatus { color: @primary; font-size: 9pt; font-weight: 600; }
QPushButton#toolCard[cardState="success"] QLabel#cardStatus { color: @success; }
QPushButton#toolCard[cardState="error"] QLabel#cardStatus { color: @error; }
QProgressBar#cardProgress { border: none; border-radius: 3px; background: #DCE6FC; text-align: center; }
QProgressBar#cardProgress::chunk { border-radius: 3px; background: @primary; }
QFrame#safetyNote { background: #EDF2F9; border: none; border-radius: 8px; }
QFrame#sidebarNote { background: transparent; border: none; }
QLabel#sidebarNoteTitle { color: #6B7788; font-size: 9pt; font-weight: 600; }
QLabel#sidebarNoteText { color: #77869A; font-size: 9pt; }
QPushButton { background: @surface; color: @text; border: 2px solid transparent; border-radius: 7px;
 padding: 9px 12px; font-weight: 600; min-height: 22px; }
QPushButton:hover { background: @tint; color: @primary; }
QPushButton:pressed { background: #DCE6FC; }
QPushButton:focus { border-color: @focus; }
QPushButton:disabled { color: @disabled; background: #EDF1F6; }
QPushButton#navButton { text-align: left; padding: 12px 10px; }
QPushButton#navButton:checked { background: @tint; color: @primary; }
QLineEdit { background: @surface; color: @text; border: 2px solid @border; border-radius: 8px;
 padding: 10px 12px; min-height: 23px; selection-background-color: @primary; selection-color: white; }
QLineEdit:focus { border-color: @focus; }
QScrollArea, QStackedWidget { border: none; background: @canvas; }
QWidget#toolContent { background: @canvas; }
QTextBrowser { background: @surface; border: 1px solid @border; border-radius: 10px; padding: 16px;
 selection-background-color: @primary; selection-color: white; }
QTextBrowser:focus, QListWidget:focus { border: 2px solid @focus; }
QListWidget { background: @surface; border: 1px solid @border; border-radius: 8px; padding: 5px; outline: 0; }
QListWidget::item { padding: 10px 8px; border-radius: 5px; }
QListWidget::item:selected { background: @tint; color: @primary; }
QListWidget::item:hover { background: #F1F5FC; }
QStatusBar { background: @surface; color: @muted; border-top: 1px solid @border; padding: 5px 16px; }
QScrollBar:vertical { background: @canvas; width: 12px; border: none; }
QScrollBar::handle:vertical { background: #B3C2D6; border-radius: 5px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: #8B9FB9; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: @text; color: white; border: none; padding: 6px; }
QFrame#toast { background: @surface; border: 1px solid @border; border-radius: 10px; }
QFrame#toast[toastState="success"] { border-color: @success; }
QFrame#toast[toastState="error"] { border-color: @error; }
QLabel#toastText { color: @text; font-size: 9.5pt; font-weight: 600; }
QFrame#toast[toastState="success"] QLabel#toastMarker { background: @success; border-radius: 4px; }
QFrame#toast[toastState="error"] QLabel#toastMarker { background: @error; border-radius: 4px; }
"""
for key,value in COLORS.items(): STYLE=STYLE.replace("@"+key,value)
