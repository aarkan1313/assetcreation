"""Generate a single PNG previewing all icons + 9-slice elements at multiple sizes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path,
                    default=Path(r"D:\assets\ui\icons\manifest.json"))
    ap.add_argument("--slice-dir", type=Path,
                    default=Path(r"D:\assets\ui\9slice"))
    ap.add_argument("--out", type=Path,
                    default=Path(r"D:\assets\ui\preview.png"))
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    icons = manifest["icons"]
    sizes = (32, 64, 128)
    pad = 16
    label_h = 16
    cell_w = sum(sizes) + pad * (len(sizes) + 1)
    cell_h = max(sizes) + pad * 2 + label_h
    cols = 2
    rows = (len(icons) + cols - 1) // cols
    img_h_icons = rows * cell_h
    # 9-slice strip
    slice_paths = sorted(args.slice_dir.glob("*.png"))
    slice_h = 0
    if slice_paths:
        slice_h = pad + 200 + pad

    W = cell_w * cols + pad
    H = img_h_icons + slice_h + pad * 3

    canvas = Image.new("RGBA", (W, H), (30, 28, 36, 255))
    draw = ImageDraw.Draw(canvas)

    # Draw icons in cells with multi-size preview
    for i, entry in enumerate(icons):
        row = i // cols
        col = i % cols
        cx = col * cell_w + pad
        cy = row * cell_h + pad
        src = Image.open(Path(r"D:\assets") / entry["path"]).convert("RGBA")
        x = cx
        for s in sizes:
            scaled = src.resize((s, s), Image.LANCZOS)
            canvas.alpha_composite(scaled, (x, cy + (max(sizes) - s) // 2))
            x += s + pad
        draw.text((cx, cy + max(sizes) + 4), entry["id"], fill=(220, 220, 220, 255))

    # 9-slice strip below
    sy = img_h_icons + pad * 2
    sx = pad
    for sp in slice_paths:
        img = Image.open(sp).convert("RGBA")
        # downscale max 200 wide
        if img.width > 200 or img.height > 200:
            sf = min(200 / img.width, 200 / img.height)
            img = img.resize((int(img.width * sf), int(img.height * sf)), Image.LANCZOS)
        canvas.alpha_composite(img, (sx, sy))
        draw.text((sx, sy + img.height + 2), sp.stem, fill=(220, 220, 220, 255))
        sx += 220

    canvas.save(args.out)
    print(f"[preview_grid] -> {args.out} ({W}x{H})")


if __name__ == "__main__":
    main()
