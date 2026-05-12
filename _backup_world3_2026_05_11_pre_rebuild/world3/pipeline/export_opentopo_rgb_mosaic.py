"""Mosaic multiple RGB GeoTIFFs into one Godot-aligned PNG layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

from export_opentopo_texture import RESAMPLING, target_window


def read_rgb_aligned(path: Path, args) -> tuple[np.ndarray, np.ndarray, dict]:
    with rasterio.open(path) as src:
        if src.count < 3:
            raise SystemExit(f"{path} has {src.count} bands; RGB mosaic needs at least 3")
        window, bounds = target_window(src, args.match_meta)
        arr = src.read(
            [1, 2, 3],
            window=window,
            out_shape=(3, args.size, args.size),
            boundless=window is not None,
            masked=True,
            resampling=RESAMPLING[args.resampling],
        )
        data = np.asarray(arr.filled(0), dtype=np.float32)
        mask = np.ma.getmaskarray(arr).any(axis=0)
        if src.nodata is not None:
            mask |= np.all(data == float(src.nodata), axis=0)
        else:
            mask |= np.all(data == 0, axis=0)
        info = {
            "path": str(path),
            "source_crs": str(src.crs),
            "source_bounds": {
                "left": src.bounds.left,
                "bottom": src.bounds.bottom,
                "right": src.bounds.right,
                "top": src.bounds.top,
            },
            "matched_bounds": bounds,
            "valid_pixels": int((~mask).sum()),
        }
    return data, mask, info


def normalize_rgb(data: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = np.zeros(data.shape, dtype=np.uint8)
    if data.max(initial=0) <= 255 and data.min(initial=0) >= 0:
        out = np.clip(data, 0, 255).astype(np.uint8)
    else:
        for band in range(3):
            values = data[band][~mask]
            if values.size == 0:
                continue
            lo, hi = np.nanpercentile(values, [2, 98])
            if not np.isfinite(hi) or hi <= lo:
                hi = lo + 1.0
            scaled = (data[band] - lo) / (hi - lo)
            out[band] = np.clip(scaled * 255.0, 0, 255).astype(np.uint8)
    out[:, mask] = 0
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path, help="RGB GeoTIFF inputs")
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--match-meta", required=True, type=Path)
    ap.add_argument("--resampling", choices=sorted(RESAMPLING), default="bilinear")
    ap.add_argument("--reducer", choices=["first", "last", "mean"], default="last")
    args = ap.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    accum = np.zeros((3, args.size, args.size), dtype=np.float64)
    count = np.zeros((args.size, args.size), dtype=np.uint16)
    composite = np.zeros((3, args.size, args.size), dtype=np.float32)
    composite_valid = np.zeros((args.size, args.size), dtype=bool)
    sources = []

    for path in args.inputs:
        data, mask, info = read_rgb_aligned(path, args)
        valid = ~mask
        sources.append(info)
        if args.reducer == "mean":
            accum[:, valid] += data[:, valid]
            count[valid] += 1
        elif args.reducer == "first":
            fill = valid & ~composite_valid
            composite[:, fill] = data[:, fill]
            composite_valid[fill] = True
        else:
            composite[:, valid] = data[:, valid]
            composite_valid[valid] = True

    if args.reducer == "mean":
        composite_valid = count > 0
        composite[:, composite_valid] = (accum[:, composite_valid] / count[composite_valid]).astype(np.float32)

    out = normalize_rgb(composite, ~composite_valid)
    Image.fromarray(np.moveaxis(out, 0, 2), mode="RGB").save(args.output)

    sidecar = {
        "inputs": [str(p) for p in args.inputs],
        "output": str(args.output),
        "size_px": args.size,
        "resampling": args.resampling,
        "reducer": args.reducer,
        "valid_pixels": int(composite_valid.sum()),
        "source_stats": sources,
    }
    args.output.with_suffix(args.output.suffix + ".json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(f"OK {args.output} ({args.reducer}, {args.size}x{args.size}, valid={int(composite_valid.sum())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
