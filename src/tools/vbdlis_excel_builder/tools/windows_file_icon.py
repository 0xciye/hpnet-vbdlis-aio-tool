"""Inspect and refresh one EXE's Windows Shell icon, without clearing global caches."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


class SHFILEINFO(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HICON), ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", wintypes.WCHAR * 260), ("szTypeName", wintypes.WCHAR * 80),
    ]


def same_visible_icon(left: QImage, right: QImage) -> bool:
    # Shell image lists premultiply/unpremultiply alpha; this can change RGB by
    # a few levels at translucent edges even when both icons have identical art.
    if left.size() != right.size():
        return False
    for y in range(left.height()):
        for x in range(left.width()):
            a, b = left.pixelColor(x, y), right.pixelColor(x, y)
            if a.alpha() != b.alpha():
                return False
            if a.alpha() == 0:
                continue
            if any(abs(c1 * a.alpha() - c2 * b.alpha()) > 4 * 255
                   for c1, c2 in zip(a.getRgb()[:3], b.getRgb()[:3])):
                return False
    return True


def refresh_file_icon(path: Path) -> None:
    """Notify only the affected file (SHCNE_UPDATEITEM, SHCNF_PATHW | FLUSH)."""
    notify = ctypes.windll.shell32.SHChangeNotify
    notify.argtypes = [ctypes.c_long, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p]
    notify.restype = None
    notify(0x2000, 0x0005 | 0x1000, ctypes.c_wchar_p(str(path.resolve())), None)


def inspect_icons(path: Path, output: Path) -> bool:
    shell = ctypes.windll.shell32
    get_info = shell.SHGetFileInfoW
    get_info.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(SHFILEINFO), wintypes.UINT, wintypes.UINT]
    get_info.restype = ctypes.c_size_t
    extract = shell.ExtractIconExW
    extract.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.HICON), wintypes.UINT]
    extract.restype = wintypes.UINT
    destroy = ctypes.windll.user32.DestroyIcon
    destroy.argtypes = [wintypes.HICON]
    destroy.restype = wintypes.BOOL
    output.mkdir(parents=True, exist_ok=True)
    matches = True
    for size, flag in (("small", 1), ("large", 0)):
        info = SHFILEINFO()
        handle = wintypes.HICON()
        try:
            if not get_info(str(path), 0, ctypes.byref(info), ctypes.sizeof(info), 0x100 | flag):
                raise OSError("SHGetFileInfoW failed")
            count = extract(str(path), 0, ctypes.byref(handle) if flag == 0 else None,
                            ctypes.byref(handle) if flag == 1 else None, 1)
            if count != 1 or not handle.value:
                raise OSError("ExtractIconExW failed")
            cached = QImage.fromHICON(info.hIcon)
            embedded = QImage.fromHICON(handle.value)
            if cached.isNull() or embedded.isNull():
                raise RuntimeError("Windows returned an empty icon")
            cached.save(str(output / f"shell-{size}.png"))
            embedded.save(str(output / f"embedded-{size}.png"))
            # An enlarged diagnostic preview makes the actual 16px icon readable.
            cached.scaled(cached.width() * 8, cached.height() * 8,
                          Qt.KeepAspectRatio, Qt.FastTransformation).save(str(output / f"shell-{size}-preview.png"))
            match = same_visible_icon(cached, embedded)
            matches = matches and match
            print(f"{size}: {cached.width()}px; shell == embedded: {match}; cache index={info.iIcon}")
        finally:
            if info.hIcon:
                destroy(info.hIcon)
            if handle.value:
                destroy(handle)
    return matches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("tmp/icon-check"))
    args = parser.parse_args()
    path = args.executable.resolve(strict=True)
    if path.suffix.lower() != ".exe":
        raise ValueError("Expected an EXE path")
    ctypes.windll.ole32.CoInitialize(None)
    try:
        if args.refresh:
            refresh_file_icon(path)
        if not inspect_icons(path, args.output):
            raise SystemExit("Windows Shell still uses a different icon")
    finally:
        ctypes.windll.ole32.CoUninitialize()


if __name__ == "__main__":
    main()
