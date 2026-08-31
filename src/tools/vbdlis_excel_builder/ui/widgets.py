from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QListView


class ComboBox(QComboBox):
    """Use a styled list popup consistently, including on dark Windows themes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView(self)
        view.setUniformItemSizes(True)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setView(view)
        self.setMaxVisibleItems(12)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        # Scrolling a form/table must not silently change its configuration.
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()
