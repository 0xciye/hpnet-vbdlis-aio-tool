"""Presentation only: retain existing inputs, models, callbacks and workflow state."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFormLayout, QFrame, QLabel, QLayout, QLineEdit, QListView,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QProxyStyle, QStyle,
)
from .paths import resource

COLORS = {
    'canvas': '#F5F7FB', 'surface': '#FFFFFF', 'text': '#172B42',
    'muted': '#53657A', 'primary': '#2458C5', 'hover': '#1948A8',
    'tint': '#EAF0FD', 'border': '#BCCBDF', 'subtle': '#DCE4EF',
}

STYLE = """
QWidget { font-family: 'Segoe UI'; font-size: 10pt; color: @text; }
QMainWindow { background: @canvas; }
QLabel { background: transparent; border: none; }
QLabel#heading { font-size: 19pt; font-weight: 700; color: @text; }
QLabel#windowHeading { font-size: 23pt; font-weight: 700; }
QLabel#hint { color: @muted; background: @tint; border-radius: 7px; padding: 10px 12px; }
QLabel#sectionHeading { font-size: 10pt; font-weight: 700; color: @primary; padding-top: 14px; padding-bottom: 6px; }
QLabel#muted, QLabel#stepCounter { color: @muted; }
QLabel#templatePreview { background: #E8EEF7; border: 1px solid @border; border-radius: 8px; padding: 8px; }
QLabel#sideTitle { font-size: 9pt; font-weight: 700; color: @muted; padding: 8px 10px; }
QFrame#stepPanel { background: @surface; border: 1px solid @subtle; border-radius: 10px; }
QStackedWidget { background: @surface; border: 1px solid @subtle; border-radius: 10px; }
QWidget#noticePage { background: @surface; }
QScrollArea { background: @surface; border: none; }
QScrollArea > QWidget > QWidget { background: @surface; }
QLineEdit, QSpinBox, QDateEdit, QComboBox, QPlainTextEdit {
 background: @surface; color: @text; border: 2px solid @border; border-radius: 6px;
 padding: 7px 10px; min-height: 24px; selection-background-color: @primary; selection-color: white;
}
QLineEdit:hover, QSpinBox:hover, QDateEdit:hover, QComboBox:hover { border-color: #809ABF; }
QLineEdit:focus, QSpinBox:focus, QDateEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: @primary; }
QLineEdit:disabled, QSpinBox:disabled, QDateEdit:disabled, QComboBox:disabled { color: #6B7788; background: #EEF2F7; border-color: @subtle; }
QLineEdit:read-only, QPlainTextEdit:read-only { background: #F8FAFD; }
QComboBox { padding-right: 36px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 30px; border: none; background: transparent; }
QComboBox::down-arrow { image: url('@down'); width: 16px; height: 16px; }
QComboBox QAbstractItemView { background: @surface; color: @text; border: 1px solid @border;
 padding: 4px; outline: 0; selection-background-color: @tint; selection-color: @primary; }
QComboBox QAbstractItemView::item { min-height: 28px; padding: 6px 10px; border: none; }
QComboBox QAbstractItemView::item:selected { background: @tint; color: @primary; }
QSpinBox { padding-right: 28px; }
QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 25px; border: none; background: transparent; }
QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 25px; border: none; background: transparent; }
QSpinBox::up-arrow { image: url('@up'); width: 12px; height: 12px; }
QSpinBox::down-arrow { image: url('@down'); width: 12px; height: 12px; }
QPushButton { background: @surface; color: @text; border: 2px solid @subtle; border-radius: 7px;
 padding: 9px 14px; min-height: 22px; font-weight: 600; }
QPushButton:hover { background: @tint; border-color: #A6BBDD; color: @primary; }
QPushButton:pressed { background: #DCE6FC; }
QPushButton:focus { border-color: @primary; }
QPushButton#primary { background: @primary; color: white; border-color: @primary; }
QPushButton#primary:hover { background: @hover; border-color: @hover; }
QPushButton#primary:focus { border-color: @text; }
QPushButton#primary:pressed { background: #153B88; }
QPushButton:disabled, QPushButton#primary:disabled { color: #6B7788; background: #EEF2F7; border-color: @subtle; }
QListWidget#steps { background: @surface; color: @text; border: 2px solid transparent; border-radius: 7px; padding: 4px; outline: 0; }
QListWidget#steps:focus { border-color: @primary; }
QListWidget#steps::item { padding: 12px 10px; border: none; border-left: 3px solid transparent; border-radius: 5px; }
QListWidget#steps::item:hover { background: #F1F5FC; }
QListWidget#steps::item:selected { background: @tint; color: @primary; border-left-color: @primary; }
QListWidget#steps:disabled { color: #6B7788; background: #F8FAFD; }
QTableWidget { background: @surface; color: @text; alternate-background-color: #F5F8FC;
 border: 1px solid @subtle; gridline-color: @subtle; selection-background-color: @tint; selection-color: @text; }
QTableWidget:focus { border: 1px solid @primary; }
QHeaderView::section { background: #EDF2F9; color: @text; font-weight: 600; padding: 10px 8px;
 border: none; border-bottom: 1px solid @border; border-right: 1px solid @subtle; }
QTableCornerButton::section { background: #EDF2F9; border: none; }
QProgressBar { border: 1px solid @border; border-radius: 6px; background: @surface; color: @text; text-align: center; min-height: 30px; }
QProgressBar::chunk { background: #BED1F6; border-radius: 5px; }
QCheckBox { spacing: 9px; padding: 7px 0; }
QCheckBox::indicator { width: 18px; height: 18px; border: 2px solid #809ABF; border-radius: 4px; background: @surface; }
QCheckBox::indicator:checked { background: @primary; border-color: @primary; image: url('@check'); }
QCheckBox::indicator:focus { border-color: @text; }
QCheckBox::indicator:disabled { border-color: @border; background: #EEF2F7; }
QCheckBox:disabled { color: #6B7788; }
QStatusBar { background: @surface; color: @muted; border-top: 1px solid @subtle; padding: 4px 16px; }
QScrollBar:vertical { width: 12px; background: #F5F7FB; border: none; }
QScrollBar::handle:vertical { background: #B3C2D6; border-radius: 5px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: #8B9FB9; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 12px; background: #F5F7FB; border: none; }
QScrollBar::handle:horizontal { background: #B3C2D6; border-radius: 5px; min-width: 32px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QToolTip { background: @text; color: white; border: none; padding: 6px; }
"""
for key, value in COLORS.items():
    STYLE = STYLE.replace('@'+key, value)
for key, filename in (('down', 'ui-chevron-down.svg'), ('up', 'ui-chevron-up.svg'), ('check', 'ui-check.svg')):
    STYLE = STYLE.replace('@'+key, resource('assets/'+filename).as_posix())


def light_palette():
    palette = QPalette()
    for role, color in (
        (QPalette.Window, COLORS['canvas']), (QPalette.Base, COLORS['surface']),
        (QPalette.AlternateBase, '#F5F8FC'), (QPalette.Text, COLORS['text']),
        (QPalette.WindowText, COLORS['text']), (QPalette.Button, COLORS['surface']),
        (QPalette.ButtonText, COLORS['text']), (QPalette.Highlight, COLORS['primary']),
        (QPalette.HighlightedText, '#FFFFFF'), (QPalette.PlaceholderText, COLORS['muted']),
        (QPalette.ToolTipBase, COLORS['text']), (QPalette.ToolTipText, '#FFFFFF'),
    ):
        palette.setColor(role, QColor(color))
    return palette


def section_label(text):
    label = QLabel(text)
    label.setObjectName('sectionHeading')
    label.setWordWrap(True)
    return label


class ListPopupStyle(QProxyStyle):
    """Use a regular list popup, without native menu scroller strips."""
    def __init__(self, parent):
        super().__init__('Fusion')
        self.setParent(parent)

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.SH_ComboBox_Popup:
            return 0
        return super().styleHint(hint, option, widget, returnData)


def apply_presentation(window):
    """Decorate existing widgets only. Do not replace their models or signals."""
    window.setPalette(light_palette())
    central = window.centralWidget().layout()
    central.setContentsMargins(20, 20, 20, 12)
    central.setSpacing(14)
    central.itemAt(0).widget().setObjectName('windowHeading')
    window.steps.setObjectName('steps')
    window.steps.setAccessibleName('Các bước tạo thông báo đất đai')
    window.steps.setWordWrap(True)
    window.steps.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    window.steps.setSpacing(4)
    window.steps.setMinimumWidth(0)
    window.steps.setMaximumWidth(16777215)
    for index in range(window.steps.count()):
        item = window.steps.item(index)
        item.setToolTip(item.text())
    row = central.itemAt(2).layout()
    row.setSpacing(16)
    row.removeWidget(window.steps)
    sidebar = QFrame(); sidebar.setObjectName('stepPanel'); sidebar.setFixedWidth(244)
    sidebar_layout = QVBoxLayout(sidebar); sidebar_layout.setContentsMargins(8, 12, 8, 8)
    title = QLabel('QUY TRÌNH · 8 BƯỚC'); title.setObjectName('sideTitle')
    sidebar_layout.addWidget(title); sidebar_layout.addWidget(window.steps, 1)
    row.insertWidget(0, sidebar)

    for combo in window.findChildren(QComboBox):
        # Force a styled list instead of the dark Windows native popup.
        # setView retains the original QComboBox model, item data and selection.
        view = QListView(combo)
        view.setUniformItemSizes(True)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        combo.setView(view); combo.setMaxVisibleItems(12)
        combo.setStyle(ListPopupStyle(combo))
        popup = view.window()
        popup.setPalette(window.palette())
        popup.setObjectName('noticeComboPopup')
        popup.setStyleSheet('QFrame#noticeComboPopup { background: #FFFFFF; border: 1px solid #BCCBDF; }')
        combo.setFocusPolicy(Qt.StrongFocus)
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(18)
        combo.setMinimumWidth(0)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    for field in window.findChildren(QLineEdit):
        field.setMinimumWidth(0)
    for button in window.findChildren(QPushButton):
        button.setCursor(Qt.PointingHandCursor)
        button.setAccessibleName(button.text())

    for form in window.findChildren(QFormLayout):
        form.setHorizontalSpacing(20); form.setVerticalSpacing(10)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for index in range(form.rowCount()):
            label_item = form.itemAt(index, QFormLayout.LabelRole)
            field_item = form.itemAt(index, QFormLayout.FieldRole)
            if label_item and isinstance(label_item.widget(), QLabel):
                label = label_item.widget(); label.setWordWrap(True)
                if field_item and field_item.widget():
                    field = field_item.widget(); label.setBuddy(field); field.setAccessibleName(label.text())

    config_scroll = window.pages[3].findChild(QScrollArea)
    form = config_scroll.widget().layout()
    form.setContentsMargins(12, 4, 16, 16)
    for field, title in (
        (window.inputs['commune_code'], 'ĐỊA PHƯƠNG & NGƯỜI SỬ DỤNG ĐẤT'),
        (window.inputs['day'].parentWidget(), 'NGÀY THÔNG BÁO'),
        (window.number_mode, 'CẤP SỐ THÔNG BÁO'),
        (window.output.parentWidget(), 'THƯ MỤC ĐẦU RA'),
    ):
        index, _ = form.getWidgetPosition(field)
        if index >= 0: form.insertRow(index, section_label(title))
    for label in config_scroll.findChildren(QLabel):
        if label.text() in ('NỘI DUNG BẮT BUỘC TRONG MẪU WORD', 'NỘI DUNG KHÔNG BẮT BUỘC'):
            label.setObjectName('sectionHeading'); label.setWordWrap(True)

    for index, page in enumerate(window.pages):
        page.setObjectName('noticePage')
        page.layout().setContentsMargins(22, 20, 22, 20)
        page.layout().setSpacing(16)
        for label in page.findChildren(QLabel):
            if label.objectName() == 'heading': label.setWordWrap(True)
        if index in (0, 1, 2, 5, 7):
            # Forms can scroll on small screens. The table, config and progress
            # already own their scrolling area and must not be nested.
            window.stack.removeWidget(page)
            scroll = QScrollArea(); scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            page.layout().setSizeConstraint(QLayout.SetMinimumSize)
            scroll.setWidget(page); window.stack.insertWidget(index, scroll)
    window.stack.setCurrentIndex(window.steps.currentRow())
    window.table.verticalHeader().setDefaultSectionSize(38)
    window.table.horizontalHeader().setMinimumHeight(42)
    for index in range(window.table.columnCount()):
        header = window.table.horizontalHeaderItem(index)
        if header: header.setToolTip(header.text())
    for label in (window.summary, window.preview_label, window.result_label):
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    counter = QLabel(); counter.setObjectName('stepCounter')
    counter.setAccessibleName('Bước hiện tại')
    def show_step(index):
        counter.setText(f'Bước {index+1} / 8')
    window.steps.currentRowChanged.connect(show_step)
    show_step(window.steps.currentRow()); central.itemAt(3).layout().insertWidget(1, counter)
