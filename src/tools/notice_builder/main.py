import sys
import json
import argparse
from pathlib import Path
from PySide6.QtWidgets import QApplication
from .ui import MainWindow


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--smoke-report"); args=parser.parse_args()
    if sys.platform=="win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HPNET.VBDLIS.NoticeBuilder")
    app=QApplication(sys.argv); app.setStyle("Fusion"); app.setApplicationName("Tạo thông báo đất đai")
    window=MainWindow(); app.setWindowIcon(window.windowIcon()); window.show()
    if args.smoke_report:
        import traceback
        from .smoke import run
        try: result=run(window)
        except Exception: result={"status":"FAIL","error":traceback.format_exc()}
        Path(args.smoke_report).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        window.close()
        return 0 if result["status"]=="PASS" else 1
    return app.exec()
