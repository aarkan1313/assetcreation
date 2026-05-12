"""Build and validate a manifest for a fused OpenTopography Godot stack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def layer_role(name: str) -> str:
    lower = name.lower()
    if "render_albedo" in lower:
        return "final_render_texture"
    if "orthophoto_rgb" in lower:
        return "color_reference"
    if "orthophoto_nir" in lower:
        return "nir_reference"
    if "vegetation" in lower or "canopy" in lower or "chm" in lower:
        return "vegetation"
    if "source_valid" in lower or "render_fill" in lower:
        return "render_repair_mask"
    if "cliff" in lower or "mask" in lower:
        return "material_mask_source"
    if "pointcloud" in lower:
        return "pointcloud_reference"
    if "slope" in lower or "roughness" in lower:
        return "material_mask_source"
    if "hillshade" in lower:
        return "terrain_reference"
    return "layer"


def image_info(path: Path) -> dict:
    with Image.open(path) as img:
        return {"size": [img.width, img.height], "mode": img.mode}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack-dir", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--site", required=True)
    ap.add_argument("--description", default="")
    args = ap.parse_args()

    meta_path = args.stack_dir / "meta.json"
    if not meta_path.exists():
        raise SystemExit(f"Missing {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    heightmap_path = args.stack_dir / "heightmap.png"
    heightmap = image_info(heightmap_path)
    layers_dir = args.stack_dir / "layers"
    layers = []
    validation = []

    for path in sorted(layers_dir.glob("*.png")):
        info = image_info(path)
        sidecar_path = path.with_suffix(path.suffix + ".json")
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8")) if sidecar_path.exists() else None
        valid_pixels = None
        if isinstance(sidecar, dict):
            valid_pixels = sidecar.get("valid_pixels")
            if valid_pixels is None and isinstance(sidecar.get("stats"), dict):
                valid_pixels = sidecar["stats"].get("valid_pixels")
        status = "pass" if info["size"] == heightmap["size"] else "fail"
        validation.append({"layer": path.name, "status": status, "size": info["size"]})
        layers.append({
            "name": path.stem,
            "path": str(path.relative_to(args.stack_dir)),
            "role": layer_role(path.stem),
            "mode": info["mode"],
            "size": info["size"],
            "sidecar": str(sidecar_path.relative_to(args.stack_dir)) if sidecar_path.exists() else None,
            "source": sidecar.get("input") if isinstance(sidecar, dict) else None,
            "inputs": sidecar.get("inputs") if isinstance(sidecar, dict) else None,
            "valid_pixels": valid_pixels,
        })

    status = "pass" if all(row["status"] == "pass" for row in validation) else "fail"
    manifest = {
        "name": args.name,
        "site": args.site,
        "description": args.description,
        "status": status,
        "target_crs": meta["source_crs"],
        "target_bounds": meta["source_bounds"],
        "heightmap": {
            "path": "heightmap.png",
            "meta": "meta.json",
            "size": heightmap["size"],
            "mode": heightmap["mode"],
            "elevation_min_m": meta["elevation_min_m"],
            "elevation_max_m": meta["elevation_max_m"],
            "world_size_m": meta["world_size_m"],
        },
        "layers": layers,
        "validation": validation,
    }
    out = args.stack_dir / "stack_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(out)
    print(json.dumps({"status": status, "layers": len(layers)}, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
