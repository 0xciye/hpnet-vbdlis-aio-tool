"""Create the small, deterministic icon family used by the three HPNet launchers."""
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 20, 24, 32, 48, 64, 128, 256)
ICONS = {
    "Downloader": ("src/nodes_tools/Downloader/app_icon.ico", (39, 93, 190), "down"),
    "Upload": ("src/nodes_tools/Upload/app_icon.ico", (23, 132, 101), "up"),
    "Duyet": ("src/nodes_tools/Duyet/app_icon.ico", (213, 137, 31), "check"),
    "Notice": ("src/tools/notice_builder/assets/app_icon.ico", (67, 84, 160), "doc"),
    "Excel": ("src/tools/vbdlis_excel_builder/resources/app_icon.ico", (35, 113, 88), "grid"),
    "Rename": ("src/tools/hpnet_file_generator/assets/app_icon.ico", (125, 78, 168), "rename"),
    "Duplicate": ("src/tools/duplicate_parcel/assets/app_icon.ico", (193, 79, 74), "link"),
    "Normalize": ("src/tools/data_normalizer/assets/app_icon.ico", (40, 128, 170), "text"),
    "Cleaner": ("src/tools/signed_pdf_cleaner/app_icon.ico", (83, 101, 112), "clean"),
}


def draw_icon(size: int, color: tuple[int, int, int], glyph: str) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = max(1, size // 16)
    draw.rounded_rectangle((margin, margin, size - margin - 1, size - margin - 1), radius=max(2, size // 5), fill=(*color, 255))
    white = (255, 255, 255, 255)
    width = max(1, size // 9)
    center = size // 2
    if glyph == "down":
        draw.line((center, size // 4, center, size * 3 // 4), fill=white, width=width)
        draw.line((size // 3, size // 2, center, size * 3 // 4), fill=white, width=width)
        draw.line((size * 2 // 3, size // 2, center, size * 3 // 4), fill=white, width=width)
    elif glyph == "up":
        draw.line((center, size * 3 // 4, center, size // 4), fill=white, width=width)
        draw.line((size // 3, size // 2, center, size // 4), fill=white, width=width)
        draw.line((size * 2 // 3, size // 2, center, size // 4), fill=white, width=width)
    elif glyph == "check":
        draw.line((size // 4, center, size * 2 // 5, size * 3 // 4), fill=white, width=width)
        draw.line((size * 2 // 5, size * 3 // 4, size * 3 // 4, size // 4), fill=white, width=width)
    elif glyph == "grid":
        for x in (size // 3, size * 2 // 3): draw.line((x, size // 4, x, size * 3 // 4), fill=white, width=width)
        for y in (size // 3, size * 2 // 3): draw.line((size // 4, y, size * 3 // 4, y), fill=white, width=width)
    elif glyph in {"doc", "text", "clean"}:
        draw.rectangle((size // 3, size // 5, size * 2 // 3, size * 4 // 5), outline=white, width=width)
        draw.line((size * 2 // 5, size // 2, size * 3 // 5, size // 2), fill=white, width=width)
        if glyph == "clean": draw.line((size // 2, size // 3, size // 2, size * 2 // 3), fill=white, width=width)
    elif glyph == "rename":
        draw.line((size // 3, size * 2 // 3, size * 2 // 3, size // 3), fill=white, width=width)
        draw.polygon([(size * 2 // 3, size // 3), (size * 3 // 4, size // 4), (size * 3 // 4, size * 2 // 5)], fill=white)
    elif glyph == "link":
        draw.ellipse((size // 5, size * 2 // 5, size * 3 // 5, size * 4 // 5), outline=white, width=width)
        draw.ellipse((size * 2 // 5, size // 5, size * 4 // 5, size * 3 // 5), outline=white, width=width)
    return image


def main() -> None:
    for name, (relative, color, glyph) in ICONS.items():
        output = ROOT / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        images = [draw_icon(size, color, glyph) for size in SIZES]
        images[-1].save(output, format="ICO", sizes=[(size, size) for size in SIZES])
        print(f"ICON_READY: {name} -> {output}")


if __name__ == "__main__":
    main()
