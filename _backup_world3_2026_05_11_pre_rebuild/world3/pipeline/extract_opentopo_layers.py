"""Extract higher-level layers from existing OpenTopography representative data."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio


ROOT = Path(__file__).resolve().parents[1]
OT = ROOT / "opentopo"


DTM_DSM_PAIRS = [
    ("bor_yukon_canada", "Yukon Canada"),
    ("tcf_bc_coast_canada", "BC Coast Canada"),
]

GEDI_SITES = [
    "tmf_amazon_brazil",
    "tgs_serengeti_tanzania",
]


def first(folder: Path, pattern: str) -> Path:
    matches = sorted(folder.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No match {folder}/{pattern}")
    return matches[0]


def write_like(path: Path, profile: dict, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = profile.copy()
    profile.update(driver="GTiff", dtype="float32", count=1, compress="deflate", tiled=True, nodata=-9999.0)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype(np.float32), 1)


def stats(arr: np.ndarray, nodata: float = -9999.0) -> dict:
    finite = np.isfinite(arr) & (arr != nodata)
    if not finite.any():
        return {"valid": 0}
    data = arr[finite]
    return {
        "valid": int(data.size),
        "min": round(float(data.min()), 3),
        "max": round(float(data.max()), 3),
        "mean": round(float(data.mean()), 3),
        "std": round(float(data.std()), 3),
        "p05": round(float(np.percentile(data, 5)), 3),
        "p95": round(float(np.percentile(data, 95)), 3),
    }


def extract_surface_height() -> list[dict]:
    rows = []
    for site_id, label in DTM_DSM_PAIRS:
        folder = OT / "raw" / "cog" / site_id
        dtm = first(folder, "CA_MRDEM_DTM_*.tif")
        dsm = first(folder, "CA_MRDEM_DSM_*.tif")
        with rasterio.open(dtm) as dtm_src, rasterio.open(dsm) as dsm_src:
            dtm_arr = dtm_src.read(1, masked=True).filled(-9999.0)
            dsm_arr = dsm_src.read(1, masked=True).filled(-9999.0)
            valid = (dtm_arr != -9999.0) & (dsm_arr != -9999.0)
            diff = np.full(dtm_arr.shape, -9999.0, dtype=np.float32)
            diff[valid] = np.maximum(dsm_arr[valid] - dtm_arr[valid], 0.0)
            out = OT / "processed" / "extracted" / "surface_height" / site_id / "dsm_minus_dtm.tif"
            write_like(out, dtm_src.profile, diff)
            rows.append({"site_id": site_id, "label": label, "output": str(out), **stats(diff)})
    return rows


def extract_gedi_metrics() -> list[dict]:
    rows = []
    for site_id in GEDI_SITES:
        folder = OT / "raw" / "cog" / site_id
        elev = first(folder, "GEDI_L3_ELEV_*.tif")
        rh100 = first(folder, "GEDI_L3_RH100_*.tif")
        with rasterio.open(elev) as elev_src, rasterio.open(rh100) as rh_src:
            elev_arr = elev_src.read(1, masked=True).filled(-9999.0)
            rh_arr = rh_src.read(1, masked=True).filled(-9999.0)
            out = OT / "processed" / "extracted" / "gedi" / site_id / "rh100_height_metric.tif"
            write_like(out, rh_src.profile, rh_arr)
            rows.append({
                "site_id": site_id,
                "rh100_output": str(out),
                "elevation": stats(elev_arr),
                "rh100": stats(rh_arr),
            })
    return rows


def main() -> int:
    report = {
        "surface_height_dsm_minus_dtm": extract_surface_height(),
        "gedi_metrics": extract_gedi_metrics(),
    }
    out = OT / "processed" / "comparison" / "extracted_layers.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
