"""Render the editable vector mark into the Windows multi-resolution icon."""
from pathlib import Path
from io import BytesIO
import struct

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def windows_icon(image: Image.Image, sizes: list[tuple[int, int]]) -> bytes:
    """Use classic 32-bit DIB + AND masks for small icons, PNG for 256px."""
    frames = []
    for width, height in sizes:
        frame = image.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
        if width == 256:
            stream = BytesIO()
            frame.save(stream, format="PNG")
            payload = stream.getvalue()
        else:
            xor = frame.tobytes("raw", "BGRA", 0, -1)
            stride = ((width + 31) // 32) * 4
            mask = bytearray(stride * height)
            for y in range(height):
                for x in range(width):
                    if frame.getpixel((x, height - 1 - y))[3] == 0:
                        mask[y * stride + x // 8] |= 0x80 >> (x % 8)
            header = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32,
                                 0, len(xor) + len(mask), 0, 0, 0, 0)
            payload = header + xor + mask
        frames.append((width, height, payload))
    directory = bytearray(struct.pack("<HHH", 0, 1, len(frames)))
    offset = 6 + len(frames) * 16
    for width, height, payload in frames:
        directory.extend(struct.pack("<BBBBHHII", width % 256, height % 256, 0, 0,
                                     1, 32, len(payload), offset))
        offset += len(payload)
    return bytes(directory) + b"".join(payload for _, _, payload in frames)


def main() -> None:
    resources = Path(__file__).resolve().parents[1] / "resources"
    renderer = QSvgRenderer(str(resources / "app_icon.svg"))
    if not renderer.isValid():
        raise RuntimeError("Invalid application icon SVG")
    canvas = QImage(512, 512, QImage.Format_ARGB32)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    renderer.render(painter)
    painter.end()
    png = resources / "app_icon.png"
    if not canvas.save(str(png)):
        raise RuntimeError("Cannot save application icon PNG")
    sizes = [(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
    with Image.open(png) as image:
        (resources / "app_icon.ico").write_bytes(windows_icon(image, sizes))
    print(f"Application icon: {len(sizes)} Windows sizes")


if __name__ == "__main__":
    main()
