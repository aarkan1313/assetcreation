"""Greedy shelf atlas packer for icons.

Reads `ui/icons/manifest.json` (or any compatible list of {id, path}) and
produces:

  ui/atlas/atlas.png        the packed image
  ui/atlas/atlas.json       {atlas: ..., regions: {<id>: {x,y,w,h}}, padding}

The atlas is power-of-two if possible. Padding (default 2 px) avoids edge
bleed. We pack by descending icon height with a simple shelf algorithm -
adequate for tens-to-hundreds of icons and avoids pulling external libs like
rectpack.

CLI:
  python pack_atlas.py --manifest ui/icons/manifest.json --out ui/atlas
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image


def _next_pot(n: int) -> int:
    return 1 << (max(int(math.ceil(math.log2(max(n, 1)))), 1))


def pack_shelf(images: list[tuple[str, Image.Image]], padding: int = 2,
               max_w: int = 4096) -> tuple[Image.Image, dict[str, dict]]:
    # sort by descending height for shelf stability
    images = sorted(images, key=lambda kv: -kv[1].height)
    # estimate target width
    total_area = sum((img.width + padding) * (img.height + padding)
                     for _, img in images)
    target_w = min(max_w, _next_pot(int(math.sqrt(total_area * 1.2))))
    cur_x = padding
    cur_y = padding
    shelf_h = 0
    placements: dict[str, dict] = {}
    for sid, img in images:
        w, h = img.size
        if cur_x + w + padding > target_w:
            cur_x = padding
            cur_y += shelf_h + padding
            shelf_h = 0
        placements[sid] = {"x": cur_x, "y": cur_y, "w": w, "h": h}
        cur_x += w + padding
        shelf_h = max(shelf_h, h)
    atlas_h = _next_pot(cur_y + shelf_h + padding)
    atlas = Image.new("RGBA", (target_w, atlas_h), (0, 0, 0, 0))
    for sid, img in images:
        p = placements[sid]
        atlas.paste(img, (p["x"], p["y"]))
    return atlas, placements


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path,
                    default=Path(r"D:\assets\ui\icons\manifest.json"))
    ap.add_argument("--out", type=Path,
                    default=Path(r"D:\assets\ui\atlas"))
    ap.add_argument("--padding", type=int, default=2)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    icons = manifest["icons"]
    images: list[tuple[str, Image.Image]] = []
    for entry in icons:
        path = Path(r"D:\assets") / entry["path"]
        images.append((entry["id"], Image.open(path).convert("RGBA")))
    atlas, placements = pack_shelf(images, padding=args.padding)
    args.out.mkdir(parents=True, exist_ok=True)
    atlas_path = args.out / "atlas.png"
    json_path = args.out / "atlas.json"
    atlas.save(atlas_path)
    json_path.write_text(json.dumps({
        "atlas": atlas_path.name,
        "size": list(atlas.size),
        "padding": args.padding,
        "regions": placements,
        "source_manifest": str(args.manifest),
    }, indent=2))
    print(f"[pack_atlas] {len(icons)} icons packed into {atlas.size[0]}x{atlas.size[1]} "
          f"-> {atlas_path}")


if __name__ == "__main__":
    main()
