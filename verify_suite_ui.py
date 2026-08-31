"""Offline UI rendering through the real launcher; no HPNet requests."""
import argparse
import logging
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication
from launcher import ToolLauncher

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="suite-ui-") as temp:
        os.environ["APPDATA"] = temp
        app = QApplication(["suite-ui", "-platform", "offscreen"])
        app.setStyle("Fusion")
        for filename in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
            font = Path(os.getenv("WINDIR", "C:/Windows")) / "Fonts" / filename
            if font.exists(): QFontDatabase.addApplicationFont(str(font))
        dark = QPalette()
        for role in (QPalette.Base, QPalette.Window, QPalette.Button): dark.setColor(role, QColor("#202020"))
        for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText): dark.setColor(role, QColor("#ffffff"))
        app.setPalette(dark)
        hub = ToolLauncher(); hub.show(); app.processEvents()
        hub.grab().save(str(args.screenshots / "launcher.png"))
        hub.resize(960,680); app.processEvents()
        hub.grab().save(str(args.screenshots / "launcher-small.png"))
        for size in ((900,660),(1240,860),(1600,1000)):
            hub.resize(*size); hub.launcher_view.reset_search(); app.processEvents()
            hub.grab().save(str(args.screenshots/f"launcher-{size[0]}.png"))
            hub.launcher_view.navigate("hpnet"); app.processEvents()
            hub.grab().save(str(args.screenshots/f"hpnet-{size[0]}.png"))
            hub.open_help(); app.processEvents()
            hub.grab().save(str(args.screenshots/f"help-{size[0]}.png"))
        hub.launcher_view.help_page.search.setText("giấy tờ nhân thân")
        hub.launcher_view.help_page.find_text(); app.processEvents()
        hub.grab().save(str(args.screenshots/"help-search.png"))
        hub.launch_excel_builder()
        window = hub.tool_windows["excel"]
        for index in range(window.tabs.count()):
            window.tabs.setCurrentIndex(index); app.processEvents()
            window.grab().save(str(args.screenshots / f"excel-tab-{index+1}.png"))
        window.tabs.setCurrentIndex(3)
        window.advanced_page.search.setText("thoi han")
        app.processEvents()
        window.grab().save(str(args.screenshots / "excel-search.png"))
        window.close(); hub.close()
        for handler in logging.getLogger().handlers[:]:
            if str(temp) in str(getattr(handler,"baseFilename","")):
                handler.close(); logging.getLogger().removeHandler(handler)
    print("UI render PASS: launcher + 5 Excel tabs + search, from simulated dark desktop.")

if __name__ == "__main__": main()
