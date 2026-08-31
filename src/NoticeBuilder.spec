import os
import sys
from pathlib import Path
system_root=Path(os.environ.get('SystemRoot',r'C:\Windows'))
os.environ['PATH']=os.pathsep.join(map(str,(Path(sys.executable).parent,Path(sys.base_prefix),system_root/'System32',system_root)))
a=Analysis(['notice_builder_entry.py'],pathex=['.'],binaries=[],
    datas=[('tools/notice_builder/template','tools/notice_builder/template'),('tools/notice_builder/config','tools/notice_builder/config'),('tools/notice_builder/assets','tools/notice_builder/assets')],
    hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Tao Thong Bao Dat Dai',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,
    console=False,disable_windowed_traceback=True,icon='tools/notice_builder/assets/app_icon.ico')
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='Tao Thong Bao Dat Dai')
