# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project = Path(SPEC).resolve().parent
conflicting_runtime_dlls = {
    "icudt78.dll",
    "icuuc.dll",
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "ucrtbase.dll",
}

a = Analysis(
    [str(project / "main.py")],
    pathex=[str(project)],
    binaries=[],
    datas=[
        (str(project / "resources" / "BieuMauThuThapThongTinGiayChungNhan.xlsx"), "resources"),
        (str(project / "config" / "template_schema.json"), "config"),
        (str(project / "config" / "profiles.json"), "config"),
        (str(project / "resources" / "app_icon.ico"), "resources"),
        (str(project / "resources" / "chevron_down.svg"), "resources"),
        (str(project / "resources" / "check.svg"), "resources"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=1,
)
# These DLLs are collected from unrelated dependencies on Python 3.14. They
# shadow the compatible Windows and Qt runtime libraries and prevent PySide6
# from loading in the frozen application.
a.binaries = [
    entry
    for entry in a.binaries
    if Path(entry[0]).name.lower() not in conflicting_runtime_dlls
    and not Path(entry[0]).name.lower().startswith("api-ms-")
]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VBDLIS Excel Builder",
    icon=str(project / "resources" / "app_icon.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VBDLIS Excel Builder",
)
