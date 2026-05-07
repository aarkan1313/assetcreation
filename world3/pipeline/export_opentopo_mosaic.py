"""Mosaic multiple single-band OpenTopography rasters into one Godot PNG layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

from export_opentopo_texture import RESAMPLING, percentile_range, target_window, to_u8


def read_aligned(path: Path, args) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(path) as src:
        window, _bounds = target_window(src, args.match_meta)
        arr = src.read(
            1,
            window=window,
            out_shape=(args.size, args.size),
            boundless=window is not None,
            masked=True,
            resampling=RESAMPLING[args.resampling],
        )
    data = np.asarray(arr.filled(np.nan), dtype=np.float32)
    mask = np.ma.getmaskarray(arr) | ~np.isfinite(data)
    return data, mask


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path, help="single-band GeoTIFFs to mosaic")
    ap.add_argument("--output", required=True, type=Path, help="output PNG path")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--match-meta", type=Path, required=True)
    ap.add_argument("--min-value", type=float)
    ap.add_argument("--max-value", type=float)
    ap.add_argument("--low-percentile", type=float, default=2.0)
    ap.add_argument("--high-percentile", type=float, default=98.0)
    ap.add_argument("--resampling", choices=sorted(RESAMPLING), default="bilinear")
    ap.add_argument("--reducer", choices=["max", "mean"], default="max")
    args = ap.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    stack_sum = np.zeros((args.size, args.size), dtype=np.float32)
    stack_count = np.zeros((args.size, args.size), dtype=np.uint16)
    stack_max = np.full((args.size, args.size), np.nan, dtype=np.float32)

    source_stats = []
    for path in args.inputs:
        data, mask = read_aligned(path, args)
        valid = ~mask
        if valid.any():
            stack_sum[valid] += data[valid]
            stack_count[valid] += 1
            replace = valid & (np.isnan(stack_max) | (data > stack_max))
            stack_max[replace] = data[replace]
        source_stats.append({"path": str(path), "valid_pixels": int(valid.sum())})

    if args.reducer == "mean":
        mosaic = np.full((args.size, args.size), np.nan, dtype=np.float32)
        valid = stack_count > 0
        mosaic[valid] = stack_sum[valid] / stack_count[valid]
    else:
        mosaic = stack_max
        valid = np.isfinite(mosaic)

    mask = ~valid
    lo = args.min_value
    hi = args.max_value
    if lo is None or hi is None:
        plo, phi = percentile_range(mosaic, mask, args.low_percentile, args.high_percentile)
        lo = plo if lo is None else lo
        hi = phi if hi is None else hi
    if hi <= lo:
        hi = lo + 1.0

    out = to_u8(mosaic, mask, float(lo), float(hi))
    Image.fromarray(out, mode="L").save(args.output)

    sidecar = {
        "inputs": [str(p) for p in args.inputs],
        "output": str(args.output),
        "size_px": args.size,
        "resampling": args.resampling,
        "reducer": args.reducer,
        "min_value": float(lo),
        "max_value": float(hi),
        "valid_pixels": int(valid.sum()),
        "source_stats": source_stats,
    }
    args.output.with_suffix(args.output.suffix + ".json").write_text(json.dumps(sidecar, indent=2))
    print(f"OK {args.output} ({args.reducer}, {args.size}x{args.size}, valid={int(valid.sum())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
