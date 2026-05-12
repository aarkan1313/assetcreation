"""Pack a PBR material into Terrain3D channel-packed format.

Per Terrain3D docs: each texture set wants two PNGs.
  albedo_height.png   -- RGB = albedo, A = height
  normal_roughness.png -- RGB = normal (OpenGL +Y), A = roughness

Usage:
  python pack_terrain3d.py --material D:/assets/world/textures/library/Rock035
  python pack_terrain3d.py --all
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


CATALOG = Path("D:/assets/world/textures/catalog/materials.jsonl")
LIBRARY = Path("D:/assets/world/textures/library")


def load_manifest_for(material_dir: Path) -> dict | None:
    if not CATALOG.exists():
        return None
    target = material_dir.name
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("id") == target:
            return rec
    return None


def load_image(path: Path, mode: str) -> Image.Image:
    return Image.open(path).convert(mode)


def pack(material_dir: Path):
    manifest = load_manifest_for(material_dir)
    if not manifest:
        print(f"  [{material_dir.name}] no manifest, skipping")
        return
    maps = manifest.get("maps", {})
    needed = ["albedo", "normal"]
    missing = [m for m in needed if m not in maps]
    if missing:
        print(f"  [{material_dir.name}] missing required maps: {missing}")
        return

    albedo = load_image(material_dir / maps["albedo"], "RGB")
    size = albedo.size

    height = (
        load_image(material_dir / maps["height"], "L").resize(size)
        if "height" in maps
        else Image.new("L", size, 128)
    )
    rgba_ah = Image.merge("RGBA", (*albedo.split(), height))

    normal = load_image(material_dir / maps["normal"], "RGB").resize(size)
    rough = (
        load_image(material_dir / maps["roughness"], "L").resize(size)
        if "roughness" in maps
        else Image.new("L", size, 128)
    )
    rgba_nr = Image.merge("RGBA", (*normal.split(), rough))

    out_dir = material_dir / "terrain3d"
    out_dir.mkdir(parents=True, exist_ok=True)
    rgba_ah.save(out_dir / "albedo_height.png")
    rgba_nr.save(out_dir / "normal_roughness.png")

    info = {
        "id": material_dir.name,
        "size": list(size),
        "files": {
            "albedo_height": "terrain3d/albedo_height.png",
            "normal_roughness": "terrain3d/normal_roughness.png",
        },
        "channels": {
            "albedo_height.png": "RGB=albedo, A=height",
            "normal_roughness.png": "RGB=normalGL, A=roughness",
        },
        "source_maps": maps,
    }
    (out_dir / "terrain3d.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"  [{material_dir.name}] packed -> {out_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--material", type=Path)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.material:
        pack(args.material)
    elif args.all:
        for p in LIBRARY.iterdir():
            if p.is_dir():
                pack(p)
    else:
        ap.error("provide --material or --all")


if __name__ == "__main__":
    main()
