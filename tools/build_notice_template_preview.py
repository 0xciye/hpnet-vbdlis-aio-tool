"""Build the single two-page placeholder preview used by Notice Builder UI."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size: int):
    candidates = (
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("page_one", type=Path)
    parser.add_argument("page_two", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    pages = [Image.open(path).convert("RGB") for path in (args.page_one, args.page_two)]
    maximum_height = 1500
    pages = [page.resize((round(page.width * maximum_height / page.height), maximum_height), Image.Resampling.LANCZOS)
             for page in pages]
    margin, gap, header = 28, 28, 74
    width = margin * 2 + gap + sum(page.width for page in pages)
    height = margin * 2 + header + maximum_height
    canvas = Image.new("RGB", (width, height), "#E8EEF7")
    draw = ImageDraw.Draw(canvas)
    title_font = font(27); label_font = font(20)
    draw.text((margin, 20), "MẪU WORD VÀ VỊ TRÍ PLACEHOLDER", fill="#17324D", font=title_font)
    x = margin
    for index, page in enumerate(pages, 1):
        y = margin + header
        draw.rounded_rectangle((x - 4, y - 4, x + page.width + 4, y + page.height + 4), radius=6,
                               fill="#FFFFFF", outline="#B8C7DB", width=2)
        canvas.paste(page, (x, y))
        label = f"TRANG {index}"
        box = draw.textbbox((0, 0), label, font=label_font)
        draw.text((x + page.width - (box[2] - box[0]), 28), label, fill="#53657A", font=label_font)
        x += page.width + gap
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, format="PNG", optimize=True)
    print(f"PREVIEW: {args.output} ({canvas.width}x{canvas.height})")


if __name__ == "__main__":
    main()
