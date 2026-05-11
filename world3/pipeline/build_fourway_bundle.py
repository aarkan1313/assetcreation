"""F.3.5 — fourway bundle builder.

Recreates M11 fourway through our pipeline. Takes the same content
inputs M11 used (real source crop + 3 procedural domains), drives
m11_bundle_lib.build_fourway_bundle, and produces a bundle that
matches M11's emit shape.

Used to validate end-to-end parity: if our pipeline can rebuild
M11 fourway with comparable visual quality on the same inputs,
the pipeline is sound. Then the same code generalizes to any
fourway composition the user specifies in a region request.

Usage:
  python world3/pipeline/build_fourway_bundle.py \
    --out world3/worlds/f35_m11_parity/bundles/m11_fourway_parity \
    --bundle-id m11_fourway_parity \
    --biome-kit grassland \
    --width 1024 --height 1024 \
    --world-size-m 240 \
    --seed 4117 \
    --nw-material m8_grassland_grass_calm_v3 --nw-elev-range-m 22 \
    --ne-material fantasy_lava_field_controlled --ne-elev-range-m 28 \
    --se-material desert_canyon_rock --se-elev-range-m 42 \
    --sw-material scrub_sparse --sw-elev-range-m 12 \
    --source-heightmap world3/toporeview/gloss_mountain_textured_master/heightmap.png \
    --source-meta world3/toporeview/gloss_mountain_textured_master/meta.json \
    --source-macro world3/toporeview/gloss_mountain_textured_master/layers/render_albedo.png \
    --source-crop 80,760,1024,1024 \
    --extra-catalog world3/materials/catalog_comfy_candidates.json \
    --extra-catalog world3/materials/catalog_m11_fourway_generated.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
WORLD3 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD3 / "pipeline"))

import m11_bundle_lib as lib  # noqa: E402


def load_catalogs(primary: Path, extras: list[Path]) -> dict[str, dict]:
    catalog = lib.load_catalog(primary)
    for extra in extras:
        if not extra.exists():
            continue
        data = json.loads(extra.read_text(encoding="utf-8"))
        for entry in data.get("materials", []):
            catalog[entry["id"]] = entry
    return catalog


def parse_crop(s: str) -> tuple[int, int, int, int]:
    parts = [int(p.strip()) for p in s.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("crop must be x,y,w,h")
    return tuple(parts)  # type: ignore[return-value]


def load_source_height_m(heightmap_path: Path, meta_path: Path,
                          macro_size_px: tuple[int, int],
                          crop_in_macro_space: tuple[int, int, int, int],
                          target_w: int, target_h: int) -> np.ndarray:
    """Load a 16-bit heightmap PNG, decode to meters via meta, then
    crop using the MACRO-space crop coords (rescaled into heightmap
    pixel space via the heightmap/macro size ratio). Mirrors eco's
    crop_height_from_macro_space contract."""
    img = Image.open(heightmap_path)
    arr = np.asarray(img)
    if arr.ndim == 3:
        arr = arr[..., 0]
    arr_f = arr.astype(np.float32)
    max_value = 65535.0 if np.issubdtype(arr.dtype, np.integer) else max(float(arr_f.max()), 1.0)
    norm = np.clip(arr_f / max_value, 0.0, 1.0)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    elev_min = float(meta.get("elevation_min_m", 0.0))
    elev_range = float(meta.get("elevation_range_m", 1.0))
    height_m = elev_min + norm * elev_range

    # Rescale macro-space crop into heightmap pixel space
    macro_w, macro_h = macro_size_px
    height_h, height_w = height_m.shape
    x, y, cw, ch = crop_in_macro_space
    hx0 = int(round((x / macro_w) * height_w))
    hy0 = int(round((y / macro_h) * height_h))
    hx1 = int(round(((x + cw) / macro_w) * height_w))
    hy1 = int(round(((y + ch) / macro_h) * height_h))
    hx0 = max(0, min(hx0, height_w - 1))
    hy0 = max(0, min(hy0, height_h - 1))
    hx1 = max(hx0 + 1, min(hx1, height_w))
    hy1 = max(hy0 + 1, min(hy1, height_h))
    cropped = height_m[hy0:hy1, hx0:hx1]

    # Resample to target dims
    pil = Image.fromarray(cropped.astype(np.float32), mode="F")
    pil = pil.resize((target_w, target_h), Image.Resampling.BILINEAR)
    return np.asarray(pil, dtype=np.float32)


def load_source_rgb(macro_path: Path, crop: tuple[int, int, int, int],
                    target_w: int, target_h: int) -> np.ndarray:
    img = Image.open(macro_path).convert("RGB")
    x, y, cw, ch = crop
    cropped = img.crop((x, y, x + cw, y + ch))
    cropped = cropped.resize((target_w, target_h), Image.Resampling.BILINEAR)
    return np.asarray(cropped, dtype=np.float32) / 255.0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--bundle-id", default="fourway_bundle")
    p.add_argument("--biome-kit", default="grassland")
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--height", type=int, default=1024)
    p.add_argument("--world-size-m", type=float, default=240.0)
    p.add_argument("--seed", type=int, default=4117)
    # Quadrant materials + per-quad elev ranges
    p.add_argument("--nw-material", required=True)
    p.add_argument("--ne-material", required=True)
    p.add_argument("--se-material", required=True)
    p.add_argument("--sw-material", required=True)
    p.add_argument("--nw-elev-range-m", type=float, default=22.0)
    p.add_argument("--ne-elev-range-m", type=float, default=28.0)
    p.add_argument("--se-elev-range-m", type=float, default=42.0)
    p.add_argument("--sw-elev-range-m", type=float, default=12.0)
    # Optional real source anchoring (M11 pattern)
    p.add_argument("--source-heightmap", type=Path, default=None)
    p.add_argument("--source-meta", type=Path, default=None)
    p.add_argument("--source-macro", type=Path, default=None)
    p.add_argument("--source-crop", type=parse_crop, default=None,
                   help="x,y,w,h in source macro pixel space")
    # Slot overrides
    p.add_argument("--slot-grass", default=None)
    p.add_argument("--slot-dirt", default=None)
    p.add_argument("--slot-rock-light", default=None)
    p.add_argument("--slot-rock-dark", default=None)
    p.add_argument("--slot-snow", default=None)
    # Extra catalogs (for materials not in the main catalog.json)
    p.add_argument("--catalog", type=Path, default=lib.DEFAULT_CATALOG)
    p.add_argument("--extra-catalog", type=Path, action="append", default=[])
    args = p.parse_args()

    catalog = load_catalogs(args.catalog, args.extra_catalog)

    # Validate all quadrant materials are present
    for label, mid in [("nw", args.nw_material), ("ne", args.ne_material),
                        ("se", args.se_material), ("sw", args.sw_material)]:
        if mid not in catalog:
            print(f"ERROR: material '{mid}' for {label} quadrant not in catalog "
                  f"(loaded {len(catalog)} entries from {args.catalog} + "
                  f"{[str(p) for p in args.extra_catalog]})", file=sys.stderr)
            return 2

    # Optional source loading. Crop is in MACRO pixel space; we need
    # the macro's actual size to rescale into heightmap pixel space.
    source_h_m: np.ndarray | None = None
    source_rgb: np.ndarray | None = None
    if args.source_heightmap and args.source_meta and args.source_crop and args.source_macro:
        macro_img = Image.open(args.source_macro)
        macro_size_px = macro_img.size  # (w, h)
        source_h_m = load_source_height_m(
            args.source_heightmap, args.source_meta,
            macro_size_px, args.source_crop,
            args.width, args.height
        )
        source_rgb = load_source_rgb(
            args.source_macro, args.source_crop, args.width, args.height
        )

    # Slot mapping: defaults follow M11 fourway's convention but allow override
    slot_materials = {
        "grass": args.slot_grass or args.nw_material,
        "dirt": args.slot_dirt or args.ne_material,
        "rock_light": args.slot_rock_light or args.se_material,
        "rock_dark": args.slot_rock_dark or args.sw_material,
        "snow": args.slot_snow or "grassland_dirt",
    }

    out = args.out
    spec = lib.FourwayBundleSpec(
        bundle_id=args.bundle_id,
        biome_kit=args.biome_kit,
        width_px=args.width,
        height_px=args.height,
        world_size_m=(args.world_size_m, args.world_size_m),
        seed=args.seed,
        nw_material_id=args.nw_material,
        ne_material_id=args.ne_material,
        se_material_id=args.se_material,
        sw_material_id=args.sw_material,
        nw_elev_range_m=args.nw_elev_range_m,
        ne_elev_range_m=args.ne_elev_range_m,
        se_elev_range_m=args.se_elev_range_m,
        sw_elev_range_m=args.sw_elev_range_m,
        source_height_m=source_h_m,
        source_rgb=source_rgb,
        bundle_dir=out,
        layers_dir=out / "layers",
        edges_dir=out / "edges",
        slot_materials=slot_materials,
    )
    result = lib.build_fourway_bundle(spec, catalog)

    # Emit a meta.json
    meta = {
        "name": f"F.3.5 fourway parity bundle ({args.bundle_id})",
        "builder": "build_fourway_bundle.py",
        "source": "fourway",
        "heightmap_size_px": [args.width, args.height],
        "world_size_x_m": args.world_size_m,
        "world_size_z_m": args.world_size_m,
        "world_size_m": args.world_size_m,
        "elevation_min_m": result["elev_min_m"],
        "elevation_max_m": result["elev_max_m"],
        "elevation_range_m": result["elev_range_m"],
        "biome_kit": args.biome_kit,
        "fourway": {
            "nw_material": args.nw_material,
            "ne_material": args.ne_material,
            "se_material": args.se_material,
            "sw_material": args.sw_material,
            "slot_materials": slot_materials,
            "source_anchored": source_h_m is not None,
        },
        "layers": {
            "render_albedo": "res://" + str(Path(result["macro"]).resolve().relative_to(WORLD3).as_posix()),
            "source_valid_mask": "res://" + str(Path(result["valid_mask"]).resolve().relative_to(WORLD3).as_posix()),
            "splat_weights_rgba": "res://" + str(Path(result["splat"]).resolve().relative_to(WORLD3).as_posix()),
        },
        "bundle_material_path": "res://" + str(Path(result["material"]).resolve().relative_to(WORLD3).as_posix()),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
