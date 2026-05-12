"""Create a labeled PNG comparison sheet from existing image assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def parse_item(raw: str) -> dict:
    parts = raw.split("|")
    if len(parts) < 2:
        raise SystemExit("--item must be 'label|path' or 'label|path|note'")
    label = parts[0].strip()
    path = Path(parts[1].strip())
    note = parts[2].strip() if len(parts) > 2 else ""
    if not path.exists():
        raise SystemExit(f"Missing image: {path}")
    return {"label": label, "path": path, "note": note}


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    if not text:
        return []
    words = text.split()
    lines = []
    line = ""
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def fit_image(path: Path, box: tuple[int, int]) -> Image.Image:
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img.thumbnail(box, Image.Resampling.LANCZOS)
        out = Image.new("RGB", box, (20, 24, 22))
        x = (box[0] - img.width) // 2
        y = (box[1] - img.height) // 2
        out.paste(img, (x, y))
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--item", action="append", required=True, help="'label|path|optional note'")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--cell-width", type=int, default=720)
    ap.add_argument("--image-height", type=int, default=480)
    ap.add_argument("--caption-height", type=int, default=116)
    args = ap.parse_args()

    items = [parse_item(item) for item in args.item]
    cols = max(1, args.cols)
    rows = (len(items) + cols - 1) // cols
    margin = 32
    gutter = 18
    title_h = 92 if args.subtitle else 68
    cell_h = args.image_height + args.caption_height
    width = margin * 2 + cols * args.cell_width + (cols - 1) * gutter
    height = margin * 2 + title_h + rows * cell_h + (rows - 1) * gutter

    bg = (13, 16, 15)
    panel = (28, 34, 31)
    text = (235, 238, 231)
    muted = (176, 185, 174)
    accent = (128, 176, 104)
    sheet = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(30, bold=True)
    subtitle_font = load_font(17)
    label_font = load_font(18, bold=True)
    note_font = load_font(14)

    draw.text((margin, margin - 2), args.title, font=title_font, fill=text)
    if args.subtitle:
        draw.text((margin, margin + 40), args.subtitle, font=subtitle_font, fill=muted)

    y0 = margin + title_h
    for idx, item in enumerate(items):
        row = idx // cols
        col = idx % cols
        x = margin + col * (args.cell_width + gutter)
        y = y0 + row * (cell_h + gutter)
        draw.rounded_rectangle(
            (x, y, x + args.cell_width, y + cell_h),
            radius=8,
            fill=panel,
            outline=(54, 63, 57),
            width=1,
        )
        img = fit_image(item["path"], (args.cell_width, args.image_height))
        sheet.paste(img, (x, y))
        draw.rectangle((x, y + args.image_height, x + args.cell_width, y + args.image_height + 2), fill=accent)
        tx = x + 16
        ty = y + args.image_height + 14
        draw.text((tx, ty), item["label"], font=label_font, fill=text)
        note_y = ty + 30
        for line in wrap_text(draw, item["note"], note_font, args.cell_width - 32)[:4]:
            draw.text((tx, note_y), line, font=note_font, fill=muted)
            note_y += 20

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    sidecar = {
        "output": str(args.output),
        "title": args.title,
        "subtitle": args.subtitle,
        "items": [
            {"label": item["label"], "path": str(item["path"]), "note": item["note"]}
            for item in items
        ],
        "size_px": [sheet.width, sheet.height],
    }
    sidecar_path = args.output.with_suffix(args.output.suffix + ".json")
    with sidecar_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(sidecar, indent=2) + "\n")
    print(f"OK {args.output} ({sheet.width}x{sheet.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
