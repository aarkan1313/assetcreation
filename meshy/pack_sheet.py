"""Pack baked sprite frames into one or more sprite sheet atlases.

Usage:
    python pack_sheet.py <sprite_dir> [<out_path>] [options]

Where sprite_dir is the output of bake.py (must contain manifest.json).

Output:
    <out_path>.png         the packed atlas image
    <out_path>.json        atlas metadata (frame coords, size, etc.)

Layout: rows = angles, columns = frames (row-major grid). Each cell is the rendered tile size.

Options:
    --tile-size N    optional resize per-frame (default: keep source resolution)
    --bg COLOR       background color, "transparent" (default) or "#RRGGBB" or "white"
    --crop           tight-crop each frame to its non-transparent bbox before packing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError as e:
    raise SystemExit(
        "Pillow is required. Install with: pip install Pillow"
    ) from e


def parse_color(s: str):
    if s == "transparent":
        return (0, 0, 0, 0)
    if s == "white":
        return (255, 255, 255, 255)
    if s.startswith("#") and len(s) == 7:
        return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16), 255)
    raise ValueError(f"unknown color: {s}")


def tight_crop_alpha(im: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Crop image to its non-transparent bounding box. Returns (cropped, bbox)."""
    if im.mode != "RGBA":
        return im, (0, 0, im.width, im.height)
    bbox = im.getbbox()
    if not bbox:
        return im, (0, 0, im.width, im.height)
    return im.crop(bbox), bbox


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sprite_dir", type=Path)
    ap.add_argument("out_path", type=Path, nargs="?", default=None,
                    help="output prefix for .png + .json (default: <sprite_dir>/sheet)")
    ap.add_argument("--tile-size", type=int, default=None)
    ap.add_argument("--bg", default="transparent")
    ap.add_argument("--crop", action="store_true",
                    help="tight-crop each frame to its non-transparent bbox before packing")
    args = ap.parse_args()

    sprite_dir = args.sprite_dir
    if not sprite_dir.is_dir():
        raise SystemExit(f"not a directory: {sprite_dir}")

    manifest_path = sprite_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"missing manifest.json in {sprite_dir}")
    manifest = json.loads(manifest_path.read_text())

    angles = manifest["angles"]
    frames_per_angle = manifest["frames"]
    bg = parse_color(args.bg)

    if args.out_path is None:
        args.out_path = sprite_dir / "sheet"
    out_png = args.out_path.with_suffix(".png")
    out_json = args.out_path.with_suffix(".json")

    # Load all frames first, grouped by angle
    by_angle: dict[int, list] = {}
    for record in manifest["renders"]:
        path = sprite_dir / record["file"]
        if not path.exists():
            raise SystemExit(f"missing frame: {path}")
        im = Image.open(path).convert("RGBA")
        by_angle.setdefault(record["angle"], []).append({
            "record": record,
            "image": im,
        })

    # If --crop, compute UNION bbox per angle (across all frames in that angle)
    # so the figure stays put across frames in an animation. Without this,
    # per-frame independent crops cause jitter as the silhouette grows/shrinks.
    if args.crop:
        for angle, items in by_angle.items():
            union = None
            for it in items:
                bb = it["image"].getbbox()
                if not bb:
                    continue
                if union is None:
                    union = list(bb)
                else:
                    union[0] = min(union[0], bb[0])
                    union[1] = min(union[1], bb[1])
                    union[2] = max(union[2], bb[2])
                    union[3] = max(union[3], bb[3])
            if union is None:
                continue
            for it in items:
                it["image"] = it["image"].crop(union)
                it["src_bbox"] = tuple(union)

    # Now collect cells with optional resize
    cells = []
    max_w = max_h = 0
    for angle, items in by_angle.items():
        for it in items:
            im = it["image"]
            if args.tile_size is not None:
                side = args.tile_size
                r = min(side / im.width, side / im.height)
                new_w, new_h = int(round(im.width * r)), int(round(im.height * r))
                im = im.resize((new_w, new_h), Image.LANCZOS)
                sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
                sq.paste(im, ((side - new_w) // 2, (side - new_h) // 2))
                im = sq
            max_w = max(max_w, im.width)
            max_h = max(max_h, im.height)
            cells.append({
                "angle": it["record"]["angle"],
                "frame_index": it["record"]["frame_index"],
                "src_frame": it["record"]["src_frame"],
                "image": im,
                "src_bbox": it.get("src_bbox", (0, 0, im.width, im.height)),
            })

    # Pad varied-sized cells (different angles can still have different shapes
    # because each angle's crop is independent — only inter-frame jitter is fixed).
    for c in cells:
        if c["image"].width != max_w or c["image"].height != max_h:
            padded = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
            padded.paste(c["image"], ((max_w - c["image"].width) // 2,
                                       (max_h - c["image"].height) // 2))
            c["image"] = padded

    # Build the atlas — rows = angles, cols = frames
    atlas_w = max_w * frames_per_angle
    atlas_h = max_h * angles
    atlas = Image.new("RGBA", (atlas_w, atlas_h), bg)

    # Map (angle_index, frame_index) -> cell
    grid = {}
    angle_list = sorted({c["angle"] for c in cells})
    angle_index = {a: i for i, a in enumerate(angle_list)}
    for c in cells:
        ai = angle_index[c["angle"]]
        fi = c["frame_index"]
        x = fi * max_w
        y = ai * max_h
        atlas.paste(c["image"], (x, y), c["image"])
        grid[f"angle_{c['angle']:03d}_frame_{fi:04d}"] = {
            "x": x, "y": y, "w": max_w, "h": max_h,
            "angle": c["angle"], "frame_index": fi, "src_frame": c["src_frame"],
        }

    out_png.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(out_png)

    sheet_meta = {
        "source_dir": str(sprite_dir),
        "atlas_size": [atlas_w, atlas_h],
        "tile_size": [max_w, max_h],
        "rows": angles,
        "cols": frames_per_angle,
        "angles": angle_list,
        "background": args.bg,
        "cropped": args.crop,
        "frames": grid,
    }
    out_json.write_text(json.dumps(sheet_meta, indent=2))

    print(f"atlas: {out_png}  ({atlas_w}x{atlas_h}, {len(cells)} cells, tile {max_w}x{max_h})")
    print(f"meta:  {out_json}")


if __name__ == "__main__":
    main()
