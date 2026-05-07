"""Export OpenTopography rasters as square PNG textures for Godot.

This is intentionally small: it converts a GeoTIFF into a fixed-size PNG,
optionally cropped to the bounds from a `build_world.py` meta.json so color,
canopy, and terrain textures line up in the viewer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.windows import from_bounds


RESAMPLING = {
    "nearest": Resampling.nearest,
    "bilinear": Resampling.bilinear,
    "cubic": Resampling.cubic,
}


def target_window(src: rasterio.DatasetReader, meta_path: Path | None):
    if meta_path is None:
        return None, None

    meta = json.loads(meta_path.read_text())
    if meta.get("source_crs") and str(src.crs) != str(meta["source_crs"]):
        raise SystemExit(
            f"CRS mismatch: source is {src.crs}, match meta expects {meta['source_crs']}"
        )

    bounds = meta["source_bounds"]
    window = from_bounds(
        bounds["left"],
        bounds["bottom"],
        bounds["right"],
        bounds["top"],
        transform=src.transform,
    )
    return window, bounds


def percentile_range(data: np.ndarray, mask: np.ndarray, low: float, high: float) -> tuple[float, float]:
    valid = data[~mask]
    if valid.size == 0:
        return 0.0, 1.0
    lo, hi = np.nanpercentile(valid, [low, high])
    if not np.isfinite(lo):
        lo = float(np.nanmin(valid))
    if not np.isfinite(hi) or hi <= lo:
        hi = lo + 1.0
    return float(lo), float(hi)


def to_u8(data: np.ndarray, mask: np.ndarray, lo: float, hi: float) -> np.ndarray:
    scaled = (data.astype(np.float32) - lo) / (hi - lo)
    scaled = np.where(mask, 0.0, scaled)
    scaled = np.nan_to_num(scaled, nan=0.0, posinf=1.0, neginf=0.0)
    out = np.clip(scaled * 255.0, 0, 255).astype(np.uint8)
    out[mask] = 0
    return out


def export_gray(src, args, window, bounds):
    arr = src.read(
        1,
        window=window,
        out_shape=(args.size, args.size),
        boundless=window is not None,
        masked=True,
        resampling=RESAMPLING[args.resampling],
    )
    mask = np.ma.getmaskarray(arr)
    data = np.asarray(arr.filled(0), dtype=np.float32)
    mask = mask | ~np.isfinite(data)

    lo = args.min_value
    hi = args.max_value
    if lo is None or hi is None:
        plo, phi = percentile_range(data, mask, args.low_percentile, args.high_percentile)
        lo = plo if lo is None else lo
        hi = phi if hi is None else hi
    if hi <= lo:
        hi = lo + 1.0

    out = to_u8(data, mask, float(lo), float(hi))
    Image.fromarray(out, mode="L").save(args.output)
    return {
        "mode": "gray",
        "min_value": float(lo),
        "max_value": float(hi),
        "valid_pixels": int((~mask).sum()),
        "matched_bounds": bounds,
    }


def export_rgb(src, args, window, bounds):
    if src.count < 3:
        raise SystemExit(f"RGB export requires at least 3 bands; got {src.count}")

    arr = src.read(
        [1, 2, 3],
        window=window,
        out_shape=(3, args.size, args.size),
        boundless=window is not None,
        masked=True,
        resampling=RESAMPLING[args.resampling],
    )
    mask = np.ma.getmaskarray(arr)
    data = np.asarray(arr.filled(0))

    if np.issubdtype(data.dtype, np.integer) and data.max(initial=0) <= 255:
        out = np.clip(data, 0, 255).astype(np.uint8)
    else:
        out = np.zeros((3, args.size, args.size), dtype=np.uint8)
        for band in range(3):
            lo, hi = percentile_range(
                data[band].astype(np.float32),
                mask[band],
                args.low_percentile,
                args.high_percentile,
            )
            out[band] = to_u8(data[band].astype(np.float32), mask[band], lo, hi)

    combined_mask = mask.any(axis=0)
    out[:, combined_mask] = 0
    Image.fromarray(np.moveaxis(out, 0, 2), mode="RGB").save(args.output)
    return {
        "mode": "rgb",
        "valid_pixels": int((~combined_mask).sum()),
        "matched_bounds": bounds,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="source GeoTIFF")
    ap.add_argument("output", type=Path, help="output PNG path")
    ap.add_argument("--mode", choices=["gray", "rgb"], required=True)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--match-meta", type=Path, help="build_world.py meta.json to align against")
    ap.add_argument("--min-value", type=float)
    ap.add_argument("--max-value", type=float)
    ap.add_argument("--low-percentile", type=float, default=2.0)
    ap.add_argument("--high-percentile", type=float, default=98.0)
    ap.add_argument("--resampling", choices=sorted(RESAMPLING), default="bilinear")
    args = ap.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(args.input) as src:
        window, bounds = target_window(src, args.match_meta)
        if args.mode == "gray":
            export = export_gray(src, args, window, bounds)
        else:
            export = export_rgb(src, args, window, bounds)

        sidecar = {
            "input": str(args.input),
            "output": str(args.output),
            "source_crs": str(src.crs),
            "source_bounds": {
                "left": src.bounds.left,
                "bottom": src.bounds.bottom,
                "right": src.bounds.right,
                "top": src.bounds.top,
            },
            "size_px": args.size,
            "resampling": args.resampling,
            **export,
        }

    args.output.with_suffix(args.output.suffix + ".json").write_text(json.dumps(sidecar, indent=2))
    print(f"OK {args.output} ({args.mode}, {args.size}x{args.size})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
