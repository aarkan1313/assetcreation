"""Export a Godot-aligned vegetation mask from a NIR/false-color orthophoto."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

from export_opentopo_texture import RESAMPLING, target_window


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="NIR/false-color GeoTIFF")
    ap.add_argument("output", type=Path, help="output grayscale PNG")
    ap.add_argument("--match-meta", required=True, type=Path)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--nir-band", type=int, default=1)
    ap.add_argument("--red-band", type=int, default=2)
    ap.add_argument("--min-value", type=float, default=-0.05)
    ap.add_argument("--max-value", type=float, default=0.25)
    ap.add_argument("--resampling", choices=sorted(RESAMPLING), default="bilinear")
    args = ap.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(args.input) as src:
        if src.count < max(args.nir_band, args.red_band):
            raise SystemExit(f"{args.input} has only {src.count} bands")
        window, bounds = target_window(src, args.match_meta)
        arr = src.read(
            [args.nir_band, args.red_band],
            window=window,
            out_shape=(2, args.size, args.size),
            boundless=window is not None,
            masked=True,
            resampling=RESAMPLING[args.resampling],
        )
        mask = np.ma.getmaskarray(arr).any(axis=0)
        data = np.asarray(arr.filled(0), dtype=np.float32)
        if src.nodata is not None:
            mask |= np.all(data == float(src.nodata), axis=0)
        nir = data[0]
        red = data[1]
        veg = (nir - red) / np.maximum(nir + red, 1.0)

        valid = ~mask & np.isfinite(veg)
        scaled = np.zeros((args.size, args.size), dtype=np.float32)
        span = max(args.max_value - args.min_value, 1e-6)
        scaled[valid] = (veg[valid] - args.min_value) / span
        out = np.clip(scaled * 255.0, 0, 255).astype(np.uint8)
        out[~valid] = 0
        Image.fromarray(out, mode="L").save(args.output)

        values = veg[valid]
        stats = {
            "valid_pixels": int(valid.sum()),
            "min": float(values.min()) if values.size else None,
            "max": float(values.max()) if values.size else None,
            "mean": float(values.mean()) if values.size else None,
            "p50": float(np.percentile(values, 50)) if values.size else None,
            "p95": float(np.percentile(values, 95)) if values.size else None,
            "p99": float(np.percentile(values, 99)) if values.size else None,
        }
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
            "matched_bounds": bounds,
            "size_px": args.size,
            "resampling": args.resampling,
            "nir_band": args.nir_band,
            "red_band": args.red_band,
            "index": "ndvi_like",
            "index_assumption": "Assumes the chosen NIR band is near-infrared and the chosen red band is red.",
            "min_value": args.min_value,
            "max_value": args.max_value,
            "stats": stats,
        }

    args.output.with_suffix(args.output.suffix + ".json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(f"OK {args.output} vegetation mask valid={stats['valid_pixels']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
