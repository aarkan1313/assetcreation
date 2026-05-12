"""Audit local OpenTopography samples and write a comparison report."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import rasterio


ROOT = Path(__file__).resolve().parents[1]
OT = ROOT / "opentopo"


GROUPS = {
    "global_surface_dsm": [
        ("COP30", OT / "raw" / "cog" / "des_mojave_usa", "COP30_*.tif"),
        ("AW3D30", OT / "raw" / "cog" / "des_mojave_usa", "AW3D30_*.tif"),
    ],
    "global_terrain_dem": [
        ("NASADEM", OT / "raw" / "cog" / "tcf_sierra_madre_mexico", "NASADEM_*.tif"),
        ("SRTMGL1", OT / "raw" / "cog" / "tcf_sierra_madre_mexico", "SRTMGL1_*.tif"),
    ],
    "bathymetry_topobathy": [
        ("SRTM15Plus", OT / "raw" / "cog" / "man_sundarbans", "SRTM15Plus_*.tif"),
        ("GEBCOIceTopo", OT / "raw" / "cog" / "man_sundarbans", "GEBCOIceTopo_*.tif"),
    ],
    "paired_dtm_dsm": [
        ("CA_MRDEM_DTM", OT / "raw" / "cog" / "tcf_bc_coast_canada", "CA_MRDEM_DTM_*.tif"),
        ("CA_MRDEM_DSM", OT / "raw" / "cog" / "tcf_bc_coast_canada", "CA_MRDEM_DSM_*.tif"),
    ],
    "gedi_metrics": [
        ("GEDI_L3_ELEV", OT / "raw" / "cog" / "tmf_amazon_brazil", "GEDI_L3_ELEV_*.tif"),
        ("GEDI_L3_RH100", OT / "raw" / "cog" / "tmf_amazon_brazil", "GEDI_L3_RH100_*.tif"),
    ],
    "usgs_high_resolution": [
        ("USGS10m", OT / "raw" / "usgsdem" / "med_california_chaparral", "USGS10m_*.tif"),
        ("USGS1m", OT / "raw" / "usgsdem" / "med_california_chaparral", "USGS1m_*.tif"),
    ],
}


POINT_CLOUDS = [
    ("CA14_Lowe", OT / "raw" / "pointcloud" / "CA14_Lowe" / "ot_335000_3809000.laz"),
    ("WA12_Legg", OT / "raw" / "pointcloud" / "WA12_Legg" / "ot_583000_5176000.laz"),
]


DERIVED = [
    ("rugged_mountain", OT / "processed" / "derived" / "tcf_pnw_cascades_usa" / "COP30"),
    ("flat_grassland", OT / "processed" / "derived" / "tgr_great_plains_usa" / "COP30"),
]


def cellsize_m(src: rasterio.DatasetReader) -> tuple[float, float]:
    dx = abs(src.transform.a)
    dy = abs(src.transform.e)
    if src.crs and src.crs.is_geographic:
        lat_mid = (src.bounds.top + src.bounds.bottom) * 0.5
        return dx * 111_320.0 * math.cos(math.radians(lat_mid)), dy * 111_320.0
    return dx, dy


def raster_stats(path: Path) -> dict:
    with rasterio.open(path) as src:
        arr = src.read(1, masked=True)
        valid = int(arr.count()) if hasattr(arr, "count") else int(arr.size)
        dx, dy = cellsize_m(src)
        out = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "width": src.width,
            "height": src.height,
            "crs": str(src.crs),
            "cellsize_x_m": round(float(dx), 3),
            "cellsize_y_m": round(float(dy), 3),
            "valid_pixels": valid,
        }
        if valid:
            data = arr.compressed() if np.ma.is_masked(arr) else arr.ravel()
            out.update({
                "min": round(float(np.min(data)), 3),
                "max": round(float(np.max(data)), 3),
                "mean": round(float(np.mean(data)), 3),
                "std": round(float(np.std(data)), 3),
                "p05": round(float(np.percentile(data, 5)), 3),
                "p95": round(float(np.percentile(data, 95)), 3),
            })
    return out


def first_match(folder: Path, pattern: str) -> Path | None:
    matches = sorted(folder.glob(pattern))
    return matches[0] if matches else None


def markdown(report: dict) -> str:
    lines = ["# OpenTopography Sample Comparison", ""]
    lines.append("Generated from local files in `world3/opentopo`.")
    lines.append("")
    for group, rows in report["raster_groups"].items():
        lines.append(f"## {group}")
        lines.append("")
        lines.append("| source | px | cell m | elev/metric range | std | size MB |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for row in rows:
            if "missing" in row:
                lines.append(f"| {row['source']} | missing | | | | |")
                continue
            lines.append(
                f"| {row['source']} | {row['width']}x{row['height']} | "
                f"{row['cellsize_x_m']:.1f} | {row.get('min', 0):.1f}..{row.get('max', 0):.1f} | "
                f"{row.get('std', 0):.1f} | {row['bytes'] / 1_000_000:.2f} |"
            )
        lines.append("")
    lines.append("## point_cloud_laz")
    lines.append("")
    lines.append("| sample | file size MB |")
    lines.append("|---|---:|")
    for row in report["point_clouds"]:
        lines.append(f"| {row['source']} | {row['bytes'] / 1_000_000:.2f} |")
    lines.append("")
    lines.append("## derived_rasters")
    lines.append("")
    lines.append("| sample | hillshade MB | slope max deg | roughness max m |")
    lines.append("|---|---:|---:|---:|")
    for row in report["derived"]:
        lines.append(
            f"| {row['source']} | {row['hillshade_bytes'] / 1_000_000:.2f} | "
            f"{row['slope_max_deg']:.1f} | {row['roughness_max_m']:.1f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    report: dict = {"raster_groups": {}, "point_clouds": [], "derived": []}
    for group, specs in GROUPS.items():
        rows = []
        for source, folder, pattern in specs:
            path = first_match(folder, pattern)
            if path is None:
                rows.append({"source": source, "missing": True})
                continue
            row = raster_stats(path)
            row["source"] = source
            rows.append(row)
        report["raster_groups"][group] = rows

    for source, path in POINT_CLOUDS:
        report["point_clouds"].append({"source": source, "path": str(path), "bytes": path.stat().st_size})

    for source, folder in DERIVED:
        slope = raster_stats(folder / "slope_deg.tif")
        rough = raster_stats(folder / "roughness.tif")
        hill = folder / "hillshade.tif"
        report["derived"].append({
            "source": source,
            "hillshade_bytes": hill.stat().st_size,
            "slope_max_deg": slope["max"],
            "roughness_max_m": rough["max"],
        })

    out_dir = OT / "processed" / "comparison"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sample_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "sample_comparison.md").write_text(markdown(report), encoding="utf-8")
    print(out_dir / "sample_comparison.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
