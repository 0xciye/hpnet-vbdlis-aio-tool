from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QListView
from launcher_ui.theme import palette as theme_palette, system_dark_mode


class ComboBox(QComboBox):
    """Use a styled list popup consistently, including on dark Windows themes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView(self)
        view.setUniformItemSizes(True)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setView(view)
        application = QApplication.instance()
        dark = bool(application.property("darkMode")) if application and application.property("darkMode") is not None else system_dark_mode()
        view.setPalette(theme_palette(dark))
        self.setMaxVisibleItems(12)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        # Scrolling a form/table must not silently change its configuration.
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()
