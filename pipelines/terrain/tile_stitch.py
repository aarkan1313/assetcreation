"""Tile-stitched DEM pull — fetch a huge bbox as N×M tiles and seamlessly stitch.

The OpenTopography API has per-request bbox limits (250 km² for USGS1m, 25,000
km² for USGS10m, 450,000 km² for most 30m global, etc). For game terrain that
needs to span e.g. all of Yosemite at 1m LiDAR, we can't pull it in one call —
we have to tile-fetch and stitch.

This tool:
  1. Splits a target bbox into tile_rows × tile_cols child bboxes with overlap.
  2. Pulls each tile via import_dem.py (which caches each tile individually).
  3. Stitches them into a single 16-bit GeoTIFF (and our standard bundle).
  4. Optional: writes a `tile_grid.json` provenance describing which tiles
     contributed to each pixel — useful for debugging seams.

Seam blending: in the overlap regions, we use a **linear feather** between
adjacent tiles. Real DEM data doesn't drift across tile boundaries (they're
stitched server-side from the same source), but the feather hides float-rounding
mismatches at <1m amplitude.

Usage:
  # Pull a 4x4 grid of USGS1m tiles covering all of Yosemite Valley
  python tile_stitch.py --id yosemite_full_1m --bbox -119.70 37.65 -119.45 37.85 \
    --dataset USGS1m --rows 3 --cols 3 --overlap 0.002 --size 4096

  # Or one big 30m mountain range (single call would still be under limits but
  # we want a 4096-pixel internal heightmap for displacement detail)
  python tile_stitch.py --id andes_full_30m --bbox -73.5 -52 -71 -49 \
    --dataset COP30 --rows 2 --cols 2 --size 4096

If a tile fetch fails, the script logs and continues; the final stitched output
will have NaN holes where tiles failed. Re-run; cache hits skip the successful
ones.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = 1_000_000_000

REPO = Path(r"D:\assets")
TERRAIN_DIR = REPO / "pipelines" / "terrain"
SOURCE_CACHE = TERRAIN_DIR / "source_dems"
OUT_DIR = TERRAIN_DIR / "output"


def split_bbox(bbox: tuple[float, float, float, float], rows: int, cols: int,
               overlap_deg: float) -> list[tuple[int, int, tuple[float, float, float, float]]]:
    """Split a bbox into rows*cols child bboxes with a degree-overlap.

    Returns list of (row_idx, col_idx, child_bbox).
    """
    w, s, e, n = bbox
    width = e - w
    height = n - s
    cw = width / cols
    ch = height / rows
    out = []
    for r in range(rows):
        for c in range(cols):
            cw_min = w + c * cw - overlap_deg
            cw_max = w + (c + 1) * cw + overlap_deg
            cs_min = s + r * ch - overlap_deg
            cs_max = s + (r + 1) * ch + overlap_deg
            # Clip to original bbox to avoid going outside
            cw_min = max(cw_min, w)
            cw_max = min(cw_max, e)
            cs_min = max(cs_min, s)
            cs_max = min(cs_max, n)
            out.append((r, c, (cw_min, cs_min, cw_max, cs_max)))
    return out


def fetch_tile(tile_bbox: tuple[float, float, float, float], dataset: str) -> np.ndarray | None:
    """Fetch one tile via the existing fetch_opentopo (caches automatically)."""
    sys.path.insert(0, str(TERRAIN_DIR))
    from import_dem import fetch_opentopo
    try:
        return fetch_opentopo(tile_bbox, dataset=dataset)
    except SystemExit as e:
        print(f"  [tile error] {e}")
        return None
    except Exception as e:
        print(f"  [tile error] {type(e).__name__}: {e}")
        return None


def feather_weight(h: int, w: int, feather_px: int) -> np.ndarray:
    """Build a 2D weight mask that feathers from 1.0 in the center down to 0.0
    over the outer feather_px pixels. Used for seam blending."""
    fy = np.ones(h, dtype=np.float32)
    fx = np.ones(w, dtype=np.float32)
    if feather_px > 0:
        ramp = np.linspace(0.0, 1.0, feather_px, dtype=np.float32)
        fy[:feather_px] = ramp
        fy[-feather_px:] = ramp[::-1]
        fx[:feather_px] = ramp
        fx[-feather_px:] = ramp[::-1]
    return np.outer(fy, fx)


def stitch(tiles: list[dict], out_size: int, target_bbox: tuple[float, float, float, float],
           feather_px: int = 16) -> np.ndarray:
    """Stitch tiles into a single output_size × output_size float32 array.

    Each tile dict has: row, col, bbox (child_bbox), arr (np.ndarray meters).
    """
    w, s, e, n = target_bbox
    width = e - w
    height = n - s

    accum = np.zeros((out_size, out_size), dtype=np.float32)
    weight = np.zeros((out_size, out_size), dtype=np.float32)

    for t in tiles:
        if t.get("arr") is None:
            continue
        cw, cs, ce, cn = t["bbox"]
        # Project this tile's coverage into output pixel space
        x_min = int(round((cw - w) / width * out_size))
        x_max = int(round((ce - w) / width * out_size))
        y_min = int(round((1.0 - (cn - s) / height) * out_size))   # north → y=0
        y_max = int(round((1.0 - (cs - s) / height) * out_size))
        x_min = max(0, x_min); x_max = min(out_size, x_max)
        y_min = max(0, y_min); y_max = min(out_size, y_max)
        if x_max <= x_min or y_max <= y_min:
            continue
        h_tile = y_max - y_min
        w_tile = x_max - x_min

        # Resample tile to fit exactly into the output rect
        tile_im = Image.fromarray(t["arr"], mode="F").resize((w_tile, h_tile), Image.LANCZOS)
        tile_arr = np.asarray(tile_im, dtype=np.float32)
        tile_w = feather_weight(h_tile, w_tile, feather_px)

        accum[y_min:y_max, x_min:x_max] += tile_arr * tile_w
        weight[y_min:y_max, x_min:x_max] += tile_w

    # Normalize by accumulated weights
    safe = np.where(weight > 1e-6, weight, 1.0)
    out = accum / safe
    out = np.where(weight > 1e-6, out, np.nan)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("W", "S", "E", "N"))
    ap.add_argument("--dataset", default="COP30")
    ap.add_argument("--rows", type=int, default=2)
    ap.add_argument("--cols", type=int, default=2)
    ap.add_argument("--overlap", type=float, default=0.002,
                    help="overlap between adjacent tiles in degrees (default 0.002 ≈ 220m)")
    ap.add_argument("--size", type=int, default=2048,
                    help="final stitched heightmap resolution (square)")
    ap.add_argument("--feather-px", type=int, default=16,
                    help="seam blending feather radius in pixels (default 16)")
    args = ap.parse_args()

    target_bbox = tuple(args.bbox)
    tile_specs = split_bbox(target_bbox, args.rows, args.cols, args.overlap)
    print(f"plan: {args.rows}×{args.cols} = {len(tile_specs)} tiles of {args.dataset}")
    for r, c, b in tile_specs:
        print(f"  [{r},{c}] bbox={b}")

    tiles = []
    for r, c, child_bbox in tile_specs:
        print(f"\n--- tile [{r},{c}] {child_bbox} ---")
        arr = fetch_tile(child_bbox, args.dataset)
        if arr is None:
            print(f"  [skip] tile [{r},{c}] failed")
        else:
            print(f"  [ok] tile [{r},{c}] shape={arr.shape} range=[{arr.min():.1f}, {arr.max():.1f}]m")
        tiles.append({"row": r, "col": c, "bbox": child_bbox, "arr": arr})

    print(f"\n--- stitch ({args.size}×{args.size} output) ---")
    stitched = stitch(tiles, args.size, target_bbox, feather_px=args.feather_px)

    # Sanitize NoData sentinels in two passes:
    #  1. Hard threshold: anything outside earth-physical (-12km..+9km) is junk.
    #  2. Percentile threshold: trim 0.1%/99.9% to kill any remaining garbage
    #     pixels (e.g. tile edges with partial weight that produced near-zero
    #     valid weight + tiny stray contribution from NoData).
    sentinel_mask = (stitched < -12000.0) | (stitched > 9000.0) | np.isnan(stitched)
    n_hard = int(sentinel_mask.sum())
    if n_hard:
        valid = stitched[~sentinel_mask]
        mean = float(valid.mean()) if valid.size else 0.0
        print(f"  [warn] {n_hard} bad pixels (NoData/sentinels); fill mean={mean:.1f}m")
        stitched = np.where(sentinel_mask, mean, stitched)

    # Percentile clamp to sane range for normalization (preserves real terrain).
    p_lo, p_hi = float(np.percentile(stitched, 0.1)), float(np.percentile(stitched, 99.9))
    print(f"  percentile clamp: [{p_lo:.1f}, {p_hi:.1f}]m (raw range "
          f"[{float(stitched.min()):.1f}, {float(stitched.max()):.1f}]m)")
    stitched = np.clip(stitched, p_lo, p_hi)

    # Normalize to 0..1 then save like import_dem.py does
    elev_min = float(stitched.min())
    elev_max = float(stitched.max())
    print(f"  elevation: min={elev_min:.1f}m max={elev_max:.1f}m")
    h_norm = (stitched - elev_min) / (elev_max - elev_min + 1e-9)
    h_norm = np.clip(h_norm, 0.0, 1.0)

    out_dir = OUT_DIR / args.id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "godot").mkdir(exist_ok=True)
    (out_dir / "height_16.png").parent.mkdir(parents=True, exist_ok=True)

    # Save as 16-bit PNG matching the standard bundle contract
    arr16 = (h_norm * 65535.0).astype(np.uint16)
    Image.fromarray(arr16, mode="I;16").save(out_dir / "height_16.png")

    # Provenance
    prov = {
        "id": args.id,
        "source": "tile_stitch",
        "target_bbox": list(target_bbox),
        "dataset": args.dataset,
        "rows": args.rows,
        "cols": args.cols,
        "overlap_deg": args.overlap,
        "size": args.size,
        "feather_px": args.feather_px,
        "elevation_range_m": [elev_min, elev_max],
        "tiles": [
            {"row": t["row"], "col": t["col"], "bbox": list(t["bbox"]),
             "shape": list(t["arr"].shape) if t["arr"] is not None else None,
             "ok": t["arr"] is not None}
            for t in tiles
        ],
        "tiles_ok": sum(1 for t in tiles if t["arr"] is not None),
        "tiles_failed": sum(1 for t in tiles if t["arr"] is None),
    }
    (out_dir / "tile_grid.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")

    print(f"\nwrote {out_dir / 'height_16.png'}")
    print(f"  provenance: {out_dir / 'tile_grid.json'}")
    print(f"  tiles ok: {prov['tiles_ok']}/{len(tiles)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
