"""Make focused repeat-preview sheets for OpenTopo texture pilot outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


Image.MAX_IMAGE_PIXELS = None


POLICIES = ["source", "tileable_real", "stylized_pixel"]


def load_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def find_product(manifest: dict, crop_class: str, crop_size_m: int) -> dict:
    products = manifest.get("products", [])
    for product in products:
        if product.get("kind") != "crop":
            continue
        if str(product.get("crop_class")) == crop_class and int(product.get("crop_size_m")) == crop_size_m:
            return product
    raise SystemExit(f"No product for {crop_class}_{crop_size_m:03d}m")


def repeat_panel(path: Path, repeat: int, cell_px: int) -> Image.Image:
    with Image.open(path) as img:
        tile = ImageOps.exif_transpose(img).convert("RGB").resize((cell_px, cell_px), Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (repeat * cell_px, repeat * cell_px))
    for y in range(repeat):
        for x in range(repeat):
            panel.paste(tile, (x * cell_px, y * cell_px))
    return panel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--crop-class", required=True)
    ap.add_argument("--crop-size-m", type=int, default=64)
    ap.add_argument("--repeat", type=int, default=16)
    ap.add_argument("--cell-px", type=int, default=64)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    product = find_product(manifest, args.crop_class, args.crop_size_m)
    panel_size = args.repeat * args.cell_px
    margin = 30
    gutter = 18
    title_h = 82
    caption_h = 72
    cols = len(POLICIES)
    width = margin * 2 + cols * panel_size + (cols - 1) * gutter
    height = margin * 2 + title_h + panel_size + caption_h
    sheet = Image.new("RGB", (width, height), (13, 16, 15))
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(30, True)
    sub_font = load_font(16)
    label_font = load_font(16, True)
    note_font = load_font(13)
    draw.text((margin, margin - 2), f"{args.crop_class} {args.crop_size_m} m - {args.repeat}x{args.repeat} exact repeat", font=title_font, fill=(236, 239, 232))
    draw.text((margin, margin + 38), "Exact square repeat preview. Hex anti-tile is shader-only and captured separately in Godot.", font=sub_font, fill=(176, 185, 174))

    outputs = product["outputs"]
    for idx, policy in enumerate(POLICIES):
        albedo = Path(outputs[policy]["albedo"])
        x = margin + idx * (panel_size + gutter)
        y = margin + title_h
        panel = repeat_panel(albedo, args.repeat, args.cell_px)
        sheet.paste(panel, (x, y))
        draw.rectangle((x, y + panel_size, x + panel_size, y + panel_size + caption_h), fill=(27, 32, 29))
        draw.text((x + 12, y + panel_size + 10), policy, font=label_font, fill=(236, 239, 232))
        policy_note = outputs[policy].get("policy", "")
        draw.text((x + 12, y + panel_size + 34), policy_note, font=note_font, fill=(176, 185, 174))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    sidecar = {
        "output": str(args.output),
        "manifest": str(args.manifest),
        "crop_class": args.crop_class,
        "crop_size_m": args.crop_size_m,
        "repeat": args.repeat,
        "cell_px": args.cell_px,
        "policies": POLICIES,
        "note": "Exact square repeat; hex anti-tile requires Godot shader capture.",
    }
    args.output.with_suffix(args.output.suffix + ".json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(f"OK {args.output} ({sheet.width}x{sheet.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
