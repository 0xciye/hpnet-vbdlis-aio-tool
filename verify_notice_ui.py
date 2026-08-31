"""Render the notice and help interfaces offscreen without processing private data."""
import argparse
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtGui import QColor, QPalette, QFontDatabase
from PySide6.QtWidgets import QApplication
from launcher import ToolLauncher


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix='notice-presentation-') as temporary:
        os.environ['APPDATA']=temporary
        app=QApplication(['notice-ui-render','-platform','offscreen']); app.setStyle('Fusion')
        for name in ('segoeui.ttf','segoeuib.ttf','seguisym.ttf'):
            QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name))
        dark=QPalette()
        for role in (QPalette.Window,QPalette.Base,QPalette.Button): dark.setColor(role,QColor('#202020'))
        for role in (QPalette.WindowText,QPalette.Text,QPalette.ButtonText): dark.setColor(role,QColor('white'))
        app.setPalette(dark)
        hub=ToolLauncher(); hub.show(); hub.launch_notice_builder(); window=hub.tool_windows['notice']
        info={'source':'synthetic.xlsx','sheet':'Du lieu','rows':12,'columns':6,'header_row':1,'depth':1,
              'headers':{'A':'Tên hộ','B':'Giấy tờ nhân thân','C':'Tờ bản đồ mới','D':'Thửa bản đồ mới','E':'Diện tích','F':'Xứ đồng'},
              'suggestions':{'owner':'A','identity':'B','sheet':'C','parcel':'D','area':'E','location':'F'}}
        window.columns_ready(info)
        for size in ((1000,650),(1250,830)):
            window.resize(*size)
            for index in range(8):
                window.steps.setCurrentRow(index)
                for _ in range(4): app.processEvents()
                window.grab().save(str(args.output/f'notice-{size[0]}-step-{index+1}.png'))
            window.steps.setCurrentRow(2); app.processEvents()
            combo=window.mapping['owner']; combo.setFocus(); combo.showPopup(); app.processEvents()
            combo.view().window().grab().save(str(args.output/f'notice-{size[0]}-popup.png'))
            combo.hidePopup()
        for size in ((900,660),(1240,860)):
            hub.resize(*size); hub.open_help()
            for index in range(3):
                hub.launcher_view.help_page.contents.setCurrentRow(index)
                for _ in range(4): app.processEvents()
                hub.grab().save(str(args.output/f'help-{size[0]}-page-{index+1}.png'))
        window.close(); hub.close()
    print('UI_RENDER_PASS: all 8 notice steps, popup, 3 independent help pages, simulated dark desktop.')


if __name__=='__main__': main()
