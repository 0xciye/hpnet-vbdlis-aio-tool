# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# Build subprocess only: do not let unrelated software on PATH supply ICU/UCRT.
# Qt expects the Windows ICU API, not Poppler's differently exported icuuc.dll.
system_root = Path(os.environ.get('SystemRoot', r'C:\Windows'))
os.environ['PATH'] = os.pathsep.join(map(str, (
    Path(sys.executable).parent, Path(sys.base_prefix),
    system_root / 'System32', system_root,
)))

datas = [
    ('tools/notice_builder/template', 'tools/notice_builder/template'),
    ('tools/notice_builder/config', 'tools/notice_builder/config'),
    ('tools/notice_builder/assets', 'tools/notice_builder/assets'),
    ('../docs/HUONG_DAN_BAN_SUA.txt', 'launcher_help'),
    ('../Huong_dan_su_dung_chi_tiet.txt', 'launcher_help'),
    ('../README.txt', 'launcher_help'),
    ('nodes_tools', 'nodes_tools'),
    ('tools/vbdlis_excel_builder/resources', 'tools/vbdlis_excel_builder/resources'),
    ('tools/vbdlis_excel_builder/config', 'tools/vbdlis_excel_builder/config'),
    ('tools/signed_pdf_cleaner/icon.ico', 'tools/signed_pdf_cleaner'),
]

hiddenimports = [
    'tools.notice_builder.ui',
    'tools.notice_builder.smoke',
    'tools.vbdlis_excel_builder.main',
    'tools.hpnet_file_generator.main',
    'tools.signed_pdf_cleaner.main',
    'tools.vbdlis_excel_builder.ui.main_window',
    'tools.hpnet_file_generator.ui.main_window',
    'tools.signed_pdf_cleaner.ui.main_window',
    'openpyxl',
    'pypdf',
    'reportlab',
    'send2trash'
]

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HPNET & VBDLIS Tools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=os.environ.get('SUITE_BUILD_CONSOLE') == '1',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='tools/vbdlis_excel_builder/resources/app_icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='HPNET & VBDLIS Tools',
)
