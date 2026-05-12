"""Fetch an OpenTopography raster product as a grid of overlapping tiles.

This is for same-type mosaic pilots where the final AOI is intentionally split
into multiple requests before stitching. Raw downloads stay immutable under
`opentopo/raw/<api-family>/<stack-id>/`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

from opentopo_fetch import API_BASE, http_get, load_local_env, looks_like_geotiff, slug_bbox


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def bbox_from_offsets(
    center_lon: float,
    center_lat: float,
    x0_km: float,
    y0_km: float,
    x1_km: float,
    y1_km: float,
) -> dict[str, float]:
    meters_per_deg_lat = 110.574
    cos_lat = max(math.cos(math.radians(center_lat)), 0.05)
    meters_per_deg_lon = 111.320 * cos_lat
    return {
        "west": center_lon + x0_km / meters_per_deg_lon,
        "east": center_lon + x1_km / meters_per_deg_lon,
        "south": center_lat + y0_km / meters_per_deg_lat,
        "north": center_lat + y1_km / meters_per_deg_lat,
    }


def tile_bboxes(args: argparse.Namespace) -> list[dict]:
    tile_width = args.width_km / args.tiles_x
    tile_height = args.height_km / args.tiles_y
    half_width = args.width_km * 0.5
    half_height = args.height_km * 0.5
    half_overlap = args.overlap_km * 0.5
    rows = []
    for row in range(args.tiles_y):
        for col in range(args.tiles_x):
            x0 = -half_width + col * tile_width
            x1 = -half_width + (col + 1) * tile_width
            y0 = -half_height + row * tile_height
            y1 = -half_height + (row + 1) * tile_height
            if col > 0:
                x0 -= half_overlap
            if col < args.tiles_x - 1:
                x1 += half_overlap
            if row > 0:
                y0 -= half_overlap
            if row < args.tiles_y - 1:
                y1 += half_overlap
            bbox = bbox_from_offsets(args.center_lon, args.center_lat, x0, y0, x1, y1)
            width_km = x1 - x0
            height_km = y1 - y0
            rows.append({
                "row": row,
                "col": col,
                "x0_km": x0,
                "x1_km": x1,
                "y0_km": y0,
                "y1_km": y1,
                "width_km": width_km,
                "height_km": height_km,
                "area_km2": width_km * height_km,
                "bbox": bbox,
            })
    return rows


def api_params(args: argparse.Namespace, bbox: dict[str, float], api_key: str) -> tuple[str, dict[str, object]]:
    base = {
        "south": bbox["south"],
        "north": bbox["north"],
        "west": bbox["west"],
        "east": bbox["east"],
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }
    if args.family == "usgsdem":
        return f"{API_BASE}/usgsdem", {"datasetName": args.dataset, **base}
    if args.family == "globaldem":
        return f"{API_BASE}/globaldem", {"demtype": args.dataset, **base}
    raise SystemExit(f"Unsupported family: {args.family}")


def download_tile(args: argparse.Namespace, tile: dict, api_key: str, out_dir: Path) -> Path:
    bbox = tile["bbox"]
    slug = slug_bbox(bbox)
    out = out_dir / f"{args.dataset}_r{tile['row']:02d}_c{tile['col']:02d}_{slug}.tif"
    if args.skip_existing and out.exists() and out.stat().st_size > 0:
        return out

    url, params = api_params(args, bbox, api_key)
    status, data = http_get(url, params, timeout=args.timeout)
    if status == 204 or not data:
        raise RuntimeError(f"No raster returned for tile r{tile['row']} c{tile['col']}")
    if not looks_like_geotiff(data):
        preview = data[:240].decode("utf-8", errors="replace").replace("\n", " ")
        error_path = out.with_suffix(".error.txt")
        error_path.write_text(preview, encoding="utf-8")
        raise RuntimeError(f"Non-GeoTIFF response for tile r{tile['row']} c{tile['col']}: {preview}")
    out.write_bytes(data)
    return out


def main() -> int:
    root = project_root()
    load_local_env(root)
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack-id", required=True)
    ap.add_argument("--family", choices=["usgsdem", "globaldem"], default="usgsdem")
    ap.add_argument("--dataset", default="USGS10m")
    ap.add_argument("--center-lon", type=float, required=True)
    ap.add_argument("--center-lat", type=float, required=True)
    ap.add_argument("--width-km", type=float, required=True)
    ap.add_argument("--height-km", type=float, required=True)
    ap.add_argument("--tiles-x", type=int, default=2)
    ap.add_argument("--tiles-y", type=int, default=2)
    ap.add_argument("--overlap-km", type=float, default=1.0)
    ap.add_argument("--max-tile-area-km2", type=float, default=None)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True)
    args = ap.parse_args()

    api_key = os.environ.get("OPENTOPOGRAPHY_API_KEY") or os.environ.get("OPENTOPO_API_KEY", "")
    if not api_key and not args.dry_run:
        print("Set OPENTOPOGRAPHY_API_KEY before raster downloads.", file=sys.stderr)
        return 2

    out_dir = root / "opentopo" / "raw" / args.family / args.stack_id
    out_dir.mkdir(parents=True, exist_ok=True)
    tiles = tile_bboxes(args)
    over_limit = []
    if args.max_tile_area_km2 is not None:
        for tile in tiles:
            if tile["area_km2"] > args.max_tile_area_km2:
                over_limit.append({
                    "row": tile["row"],
                    "col": tile["col"],
                    "area_km2": tile["area_km2"],
                    "max_tile_area_km2": args.max_tile_area_km2,
                })
    manifest = {
        "stack_id": args.stack_id,
        "family": args.family,
        "dataset": args.dataset,
        "center_lon": args.center_lon,
        "center_lat": args.center_lat,
        "width_km": args.width_km,
        "height_km": args.height_km,
        "tiles_x": args.tiles_x,
        "tiles_y": args.tiles_y,
        "overlap_km": args.overlap_km,
        "max_tile_area_km2": args.max_tile_area_km2,
        "over_limit": over_limit,
        "tiles": tiles,
    }

    if args.dry_run:
        print(json.dumps(manifest, indent=2))
        return 2 if over_limit else 0

    if over_limit:
        print(json.dumps({"error": "tile area limit exceeded", "tiles": over_limit}, indent=2), file=sys.stderr)
        return 2

    downloaded = []
    for tile in tiles:
        try:
            path = download_tile(args, tile, api_key, out_dir)
            tile["path"] = str(path)
            downloaded.append(path)
            print(f"wrote {path}")
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            tile["error"] = str(exc)
            print(f"ERROR tile r{tile['row']} c{tile['col']}: {exc}", file=sys.stderr)

    manifest["downloaded_count"] = len(downloaded)
    manifest_path = out_dir / "tile_grid_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(manifest_path)
    return 0 if len(downloaded) == len(tiles) else 1


if __name__ == "__main__":
    raise SystemExit(main())
