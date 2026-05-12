"""World splat array builder.

Replaces per-tile splats with a single world-spanning splat stack:
one R8 PNG per biome, all the same world resolution. Loaded by
ScaleWorld at scene init into a Texture2DArray and sampled by the
shader at world XZ for every fragment.

Why one global stack vs per-tile:
- Adjacent tiles share splat pixels by construction at their boundary,
  so bilinear sampling at fragment positions in the boundary zone
  reads continuous values from both sides. No hard line.
- N biomes (not 4): one layer per biome. Today 5; planned for ≥15.
- Per-tile material duplication goes away — every tile uses the
  same global material.

Algorithm (procedural, derived from per-tile biome assignment):
1. Rasterize the per-tile biome map at world splat resolution (e.g.
   256×256 covering 1024m world = 4m/pixel).
2. For each pixel, compute the signed distance to the nearest pixel
   whose biome differs from this pixel's biome (in meters).
3. Each biome's layer at this pixel = a smooth-ramp function of the
   signed distance, weighted s.t. the active biome dominates inside
   its region and neighbors ramp in within `feather_width_m` of the
   boundary.
4. Normalize per-pixel across all biome layers so weights sum to 1.
5. Optional gaussian smooth (sigma ~1.0 px) to remove any per-pixel
   sharpness, then re-normalize.

Output:
    worlds/<bundle>/world_splat/layer_<biome_name>.png    # R8, world-res
    worlds/<bundle>/world_splat/manifest.json             # order + meta

Usage:
    python build_world_splat.py \\
        --bundle "<path>/scale_demo" \\
        --catalog "<path>/biome_catalog.json" \\
        --resolution 256 --feather-width-m 48.0
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

import biome_catalog as bc


class WorldSplatError(RuntimeError):
    pass


def _rasterize_biome_map(
    *, tile_biomes: dict[tuple[int, int], str],
    grid_n: int, splat_res: int,
) -> np.ndarray:
    """Render the per-tile biome assignment as an integer biome-id grid
    at splat resolution. Each pixel is the id of the biome at that
    world position (nearest tile).

    Pixel-to-tile mapping: splat is row-major with row 0 = north (high z),
    matching the tile coord convention used elsewhere (tile_z increases
    south->north in world space, but PIL Image row 0 is the top of the
    image = north edge; tile_z=grid_n-1 is the northmost row).
    """
    biome_names = sorted({b for b in tile_biomes.values()})
    biome_id_of: dict[str, int] = {b: i for i, b in enumerate(biome_names)}
    px_per_tile = splat_res // grid_n
    if px_per_tile * grid_n != splat_res:
        raise WorldSplatError(
            f"splat_res ({splat_res}) must be a multiple of grid_n ({grid_n})")
    out = np.zeros((splat_res, splat_res), dtype=np.int32)
    for (tx, tz), biome in tile_biomes.items():
        # row 0 = north = tile_z = grid_n - 1
        row_start = (grid_n - 1 - tz) * px_per_tile
        col_start = tx * px_per_tile
        out[row_start:row_start + px_per_tile,
            col_start:col_start + px_per_tile] = biome_id_of[biome]
    return out, biome_names


def _signed_distance_to_other_biome(
    biome_map: np.ndarray, biome_id: int, meters_per_pixel: float,
) -> np.ndarray:
    """For each pixel, return the distance (meters) to the nearest pixel
    whose biome != biome_id.

    Inside the biome's region: positive distance, decreasing toward the
    boundary, 0 at the boundary.
    Outside: 0 (or unused — caller masks).
    """
    # scipy.ndimage.distance_transform_edt: distance to nearest 0.
    # Set "this biome" pixels to 1, others to 0, then EDT gives distance
    # from this-biome pixels to the nearest non-this pixel.
    from scipy.ndimage import distance_transform_edt
    mask = (biome_map == biome_id).astype(np.uint8)
    # When the whole image is one biome, EDT returns infinity-style
    # values. Clamp by a large finite cap.
    dist_px = distance_transform_edt(mask)
    return dist_px.astype(np.float32) * meters_per_pixel


def build_world_splat(
    *, bundle_dir: Path | str, catalog: bc.Catalog,
    splat_res: int, feather_width_m: float,
    smooth_sigma_px: float = 1.0,
) -> dict:
    bundle = Path(bundle_dir)
    tiles_dir = bundle / "tiles"
    world_meta_path = bundle / "meta.json"
    if not world_meta_path.is_file():
        raise WorldSplatError(f"missing world meta at {world_meta_path}")
    world_meta = json.loads(world_meta_path.read_text(encoding="utf-8"))
    world_size_m = float(world_meta["world_size_m"])
    grid_n = int(world_meta["grid_n"])
    meters_per_pixel = world_size_m / splat_res

    # Gather per-tile biome assignments.
    tile_biomes: dict[tuple[int, int], str] = {}
    for tile_dir in sorted(tiles_dir.iterdir()):
        if not tile_dir.is_dir() or not tile_dir.name.startswith("tile_"):
            continue
        tm = json.loads((tile_dir / "meta.json").read_text(encoding="utf-8"))
        biome = tm.get("biome")
        if not biome:
            raise WorldSplatError(f"{tile_dir}: meta.json missing biome field")
        tile_biomes[(int(tm["tile_x"]), int(tm["tile_z"]))] = biome

    # Catalog must contain every biome that appears in tile_biomes.
    catalog_biome_names = set(catalog.biome_names())
    for b in set(tile_biomes.values()):
        if b not in catalog_biome_names:
            raise WorldSplatError(
                f"biome {b!r} assigned to a tile but not in catalog")

    # Rasterize per-tile biome map at splat resolution.
    biome_map, present_biomes = _rasterize_biome_map(
        tile_biomes=tile_biomes, grid_n=grid_n, splat_res=splat_res,
    )

    # Per-biome weight field.
    # Use a globally-consistent biome ordering: catalog order. Biomes in
    # the catalog but not on any tile still get a layer (all-zero) so
    # the layer-index <-> biome mapping is stable across regenerations.
    layer_names = list(catalog.biome_names())
    layers = []
    for biome_name in layer_names:
        if biome_name not in present_biomes:
            # All-zero layer; the shader's normalize step handles this.
            w = np.zeros((splat_res, splat_res), dtype=np.float32)
            layers.append(w)
            continue
        biome_id_in_map = present_biomes.index(biome_name)
        # Inside the region: distance >= 0. Outside: 0.
        d_inside = _signed_distance_to_other_biome(
            biome_map, biome_id_in_map, meters_per_pixel,
        )
        # Ramp: 1.0 at distance >= feather_width_m (deep inside),
        # 0.5 at distance == 0 (boundary), continuous in between.
        # Outside the region (d_inside == 0 because mask was 0),
        # we want this biome's weight to ramp DOWN from 0.5 at the
        # boundary to 0.0 at distance >= feather_width_m from the
        # boundary. Compute that via the *other* direction's EDT.
        from scipy.ndimage import distance_transform_edt
        outside_mask = (biome_map != biome_id_in_map).astype(np.uint8)
        d_outside = distance_transform_edt(outside_mask).astype(np.float32) * meters_per_pixel
        # For each pixel:
        #   if in this region: d = d_inside (>=0), weight ramps 0.5 -> 1.0
        #     as d goes 0 -> feather_width
        #   else:              d = d_outside (>=0), weight ramps 0.5 -> 0
        #     as d goes 0 -> feather_width
        inside = (biome_map == biome_id_in_map)
        w = np.zeros((splat_res, splat_res), dtype=np.float32)
        # Inside contribution.
        t_in = np.clip(d_inside / max(feather_width_m, 1e-3), 0.0, 1.0)
        w[inside] = 0.5 + 0.5 * t_in[inside]
        # Outside contribution.
        t_out = np.clip(1.0 - d_outside / max(feather_width_m, 1e-3), 0.0, 1.0)
        w[~inside] = 0.5 * t_out[~inside]
        layers.append(w)

    layers_stack = np.stack(layers, axis=-1)  # (H, W, N)

    # Optional gaussian smooth per layer.
    if smooth_sigma_px > 0:
        for i in range(layers_stack.shape[-1]):
            layers_stack[..., i] = gaussian_filter(
                layers_stack[..., i], sigma=smooth_sigma_px, mode="nearest",
            )

    # Normalize per pixel.
    totals = layers_stack.sum(axis=-1, keepdims=True)
    totals = np.maximum(totals, 1e-6)
    layers_stack = layers_stack / totals

    # Emit one R8 PNG per layer.
    out_dir = bundle / "world_splat"
    out_dir.mkdir(parents=True, exist_ok=True)
    layer_files = []
    for i, biome_name in enumerate(layer_names):
        arr = (layers_stack[..., i] * 255.0 + 0.5).clip(0, 255).astype(np.uint8)
        path = out_dir / f"layer_{biome_name}.png"
        Image.fromarray(arr, mode="L").save(path)
        layer_files.append(path.name)

    manifest = {
        "schema_version": 1,
        "splat_resolution": splat_res,
        "world_size_m": world_size_m,
        "meters_per_pixel": meters_per_pixel,
        "feather_width_m": feather_width_m,
        "smooth_sigma_px": smooth_sigma_px,
        "layers": [
            {"layer": i, "biome": name, "file": file_name}
            for i, (name, file_name) in enumerate(zip(layer_names, layer_files))
        ],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True,
                    help="World bundle dir, e.g. worlds/scale_demo")
    ap.add_argument("--catalog", required=True,
                    help="Path to biome_catalog.json")
    ap.add_argument("--resolution", type=int, default=256,
                    help="Splat resolution in pixels (must be multiple of grid_n).")
    ap.add_argument("--feather-width-m", type=float, default=48.0,
                    help="Boundary feather width in meters.")
    ap.add_argument("--smooth-sigma-px", type=float, default=1.0,
                    help="Gaussian smooth sigma in pixels after raster.")
    args = ap.parse_args()
    cat = bc.load_catalog(args.catalog)
    m = build_world_splat(
        bundle_dir=args.bundle, catalog=cat,
        splat_res=args.resolution,
        feather_width_m=args.feather_width_m,
        smooth_sigma_px=args.smooth_sigma_px,
    )
    print(f"wrote {len(m['layers'])} world splat layers @ {m['splat_resolution']}x{m['splat_resolution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
