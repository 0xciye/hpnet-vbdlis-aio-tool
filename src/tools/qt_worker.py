"""Reusable background worker for the two Excel utilities."""
from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, function, parent=None, with_progress=False):
        super().__init__(parent)
        self.function = function
        self.with_progress = with_progress

    def run(self):
        try:
            result = self.function(self.progress.emit) if self.with_progress else self.function()
            self.succeeded.emit(result)
        except Exception as error:
            self.failed.emit(str(error) or type(error).__name__)
