"""STAC-based fetchers for regional DEMs that OpenTopography refuses on /globaldem.

Bypasses OpenTopography's job-submission UI entirely by hitting the data
providers' public STAC APIs and pulling Cloud-Optimized GeoTIFFs (COGs)
directly from open S3 buckets — no API key, no quota, no auth.

Datasets supported (lat/lon bbox, returns a single mosaicked GeoTIFF):
  - ArcticDEM (PGC mosaics v4.1, 10m / 32m). 2m available but multi-tile.
      bucket:    s3://pgc-opendata-dems/arcticdem/mosaics/v4.1/
      stac:      https://stac.pgc.umn.edu/api/v1/
      EPSG:      3413 (Polar Stereographic North)
  - REMA (PGC mosaics v2.0, 10m / 32m). 2m available but multi-tile.
      bucket:    s3://pgc-opendata-dems/rema/mosaics/v2.0/
      stac:      https://stac.pgc.umn.edu/api/v1/
      EPSG:      3031 (Polar Stereographic South)
  - LINZ NZ Elevation (1m DEM, 1m DSM)
      bucket:    s3://nz-elevation/ (ap-southeast-2)
      catalog:   https://nz-elevation.s3-ap-southeast-2.amazonaws.com/catalog.json
      EPSG:      2193 (NZ Transverse Mercator)

Strategy: STAC bbox-search → list COGs → use rasterio's windowed-read on the
HTTP COG to extract just the bbox we want → stitch with mosaic if N tiles >1.

Discovered this session 2026-05-06 by inspecting the OpenTopography arcticDem
page form action (/rasterSubmit) and the AWS Open Data Registry references.
The /rasterSubmit POST flow on portal.opentopography.org requires browser
session auth; it is NOT a programmatic API. Direct STAC + S3 is the right path.

Usage:
  python fetch_regional_stac.py --dataset ArcticDEM10m --id disko_test \
      --bbox -53.50 69.25 -53.30 69.40 --size 1024
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import requests

# COLLECTIONS keyed by our dataset name. Each value is a tuple:
# (stac_root_url, collection_id, native_epsg, asset_key)
COLLECTIONS = {
    "ArcticDEM10m": (
        "https://stac.pgc.umn.edu/api/v1",
        "arcticdem-mosaics-v4.1-10m",
        3413,
        "dem",
    ),
    "ArcticDEM32m": (
        "https://stac.pgc.umn.edu/api/v1",
        "arcticdem-mosaics-v4.1-32m",
        3413,
        "dem",
    ),
    "REMA10m": (
        "https://stac.pgc.umn.edu/api/v1",
        "rema-mosaics-v2.0-10m",
        3031,
        "dem",
    ),
    "REMA32m": (
        "https://stac.pgc.umn.edu/api/v1",
        "rema-mosaics-v2.0-32m",
        3031,
        "dem",
    ),
}

# LINZ: a static catalog of 217 regional collections (104 dem_1m). No search
# API — we walk the catalog and find collections whose bbox intersects ours.
LINZ_ROOT = "https://nz-elevation.s3-ap-southeast-2.amazonaws.com/catalog.json"
LINZ_BASE = "https://nz-elevation.s3-ap-southeast-2.amazonaws.com"


def stac_search(stac_root: str, collection: str,
                bbox_lonlat: tuple[float, float, float, float],
                limit: int = 32) -> list[dict]:
    """Return STAC features (with assets) intersecting the lat/lon bbox."""
    url = f"{stac_root}/search"
    params = {
        "collections": collection,
        "bbox": ",".join(str(v) for v in bbox_lonlat),
        "limit": str(limit),
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    feats = r.json().get("features", [])
    return feats


def windowed_cog_read(cog_url: str,
                      bbox_lonlat: tuple[float, float, float, float]) -> tuple:
    """Read just the bbox window from a COG using rasterio.

    Reprojects from the COG's native CRS to lat/lon bbox by way of rasterio's
    WarpedVRT for bilinear sampling. Returns (data, transform, crs).
    """
    import rasterio
    from rasterio.warp import transform_bounds, calculate_default_transform
    from rasterio.vrt import WarpedVRT
    from rasterio.windows import from_bounds

    # rasterio + GDAL HTTP plugin handles s3-style https URLs natively when the
    # bucket is public. Set HTTP options for COG range reads.
    os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
    os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")

    with rasterio.open(cog_url) as src:
        # Convert lat/lon bbox to source CRS bounds
        src_bounds = transform_bounds("EPSG:4326", src.crs, *bbox_lonlat,
                                      densify_pts=21)
        win = from_bounds(*src_bounds, transform=src.transform)
        win = win.round_offsets().round_lengths()
        if win.width <= 0 or win.height <= 0:
            return None, None, None
        data = src.read(1, window=win)
        # Compute the windowed transform
        win_transform = src.window_transform(win)
        return data, win_transform, src.crs


def fetch_pgc(dataset: str, bbox_lonlat: tuple[float, float, float, float],
              out_path: Path, size: int = 1024) -> bool:
    """Pull ArcticDEM/REMA over a lat/lon bbox into a single GeoTIFF.

    Currently single-tile only (most 10m/32m mosaics span entire continents
    per tile, so this is enough for game-scale bboxes). For multi-tile mosaicking
    add rasterio.merge later if needed.
    """
    if dataset not in COLLECTIONS:
        raise SystemExit(f"unknown dataset for STAC fetch: {dataset}")

    stac_root, collection, native_epsg, asset_key = COLLECTIONS[dataset]
    print(f"  STAC search: {collection} bbox={bbox_lonlat}")
    feats = stac_search(stac_root, collection, bbox_lonlat)
    if not feats:
        raise RuntimeError(
            f"no STAC tiles found for {dataset} over bbox {bbox_lonlat} — "
            f"check coverage at https://stac.pgc.umn.edu/api/v1/collections/{collection}"
        )
    print(f"  {len(feats)} tile(s) intersect the bbox")

    import rasterio
    from rasterio.warp import (calculate_default_transform, reproject,
                                Resampling, transform_bounds)
    from rasterio.merge import merge as rio_merge

    # Read windowed data from each tile, then merge if >1.
    sources = []
    for f in feats:
        href = f["assets"][asset_key]["href"]
        print(f"    reading: {href}")
        sources.append(rasterio.open(href))

    if len(sources) > 1:
        # Merge in source CRS, then reproject + resample to target lat/lon grid.
        merged_data, merged_transform = rio_merge(
            sources,
            bounds=transform_bounds("EPSG:4326", sources[0].crs, *bbox_lonlat,
                                    densify_pts=21),
        )
        merged_data = merged_data[0]  # band 1
        src_crs = sources[0].crs
    else:
        from rasterio.windows import from_bounds
        s = sources[0]
        sb = transform_bounds("EPSG:4326", s.crs, *bbox_lonlat, densify_pts=21)
        win = from_bounds(*sb, transform=s.transform).round_offsets().round_lengths()
        merged_data = s.read(1, window=win)
        merged_transform = s.window_transform(win)
        src_crs = s.crs

    for s in sources:
        s.close()

    # Reproject to EPSG:4326 grid at requested size
    dst_w, dst_h = size, size
    src_h, src_w = merged_data.shape
    src_west, src_north = merged_transform * (0, 0)
    src_east, src_south = merged_transform * (src_w, src_h)
    src_bounds = (min(src_west, src_east), min(src_south, src_north),
                  max(src_west, src_east), max(src_south, src_north))
    dst_transform, _, _ = calculate_default_transform(
        src_crs, "EPSG:4326", src_w, src_h, *src_bounds,
        dst_width=dst_w, dst_height=dst_h,
    )
    dst = np.full((dst_h, dst_w), -9999.0, dtype=np.float32)
    reproject(
        source=merged_data.astype(np.float32),
        destination=dst,
        src_transform=merged_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs="EPSG:4326",
        resampling=Resampling.bilinear,
        src_nodata=-9999.0,
        dst_nodata=-9999.0,
    )

    # Sanitize NoData: replace -9999 (and any sub--9000 leftovers from blended
    # sentinel-near-edge pixels) with valid mean so min/max normalize sanely.
    bad = (dst < -9000.0) | np.isnan(dst)
    if bad.any():
        valid = dst[~bad]
        fill = float(valid.mean()) if valid.size else 0.0
        n_bad = int(bad.sum())
        print(f"  [warn] {n_bad}/{dst.size} bad pixels ({100*n_bad/dst.size:.1f}%); "
              f"fill={fill:.1f}m")
        dst = np.where(bad, fill, dst)

    # Write as GeoTIFF
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out_path, "w",
        driver="GTiff",
        height=dst_h, width=dst_w, count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=dst_transform,
        compress="lzw",
        nodata=-9999.0,
    ) as dst_ds:
        dst_ds.write(dst, 1)

    print(f"  wrote {out_path} ({dst_h}x{dst_w}, "
          f"min={float(dst.min()):.1f} max={float(dst.max()):.1f})")
    return True


def _bbox_intersects(a, b) -> bool:
    """STAC bbox is [west, south, east, north]; nested-list-safe."""
    if not a or not b:
        return False
    if isinstance(a[0], list):
        a = a[0]
    if isinstance(b[0], list):
        b = b[0]
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


_LINZ_CATALOG_CACHE = Path(__file__).resolve().parent / "source_dems" / "_linz_catalog_cache.json"


def _linz_load_catalog_index(variant: str) -> list[dict]:
    """Build {url, bbox} index of LINZ collections for a given variant.

    Cached to disk (~104 small JSON fetches takes ~1 min cold; cache lookup is
    instant). Bust the cache by deleting `_linz_catalog_cache.json`.
    """
    cache_key = f"v1::{variant}"
    if _LINZ_CATALOG_CACHE.exists():
        try:
            cache = json.loads(_LINZ_CATALOG_CACHE.read_text(encoding="utf-8"))
            if cache.get("key") == cache_key and "entries" in cache:
                return cache["entries"]
        except Exception:
            pass

    root = requests.get(LINZ_ROOT, timeout=30).json()
    candidates = [l for l in root["links"]
                  if l.get("rel") == "child" and variant in l.get("href", "")]
    entries = []
    for child in candidates:
        href = child["href"]
        url = (href if href.startswith("http")
               else LINZ_BASE + "/" + href.lstrip("./"))
        try:
            col = requests.get(url, timeout=30).json()
        except Exception:
            continue
        bbox = col.get("extent", {}).get("spatial", {}).get("bbox", [])
        entries.append({"url": url, "bbox": bbox})

    _LINZ_CATALOG_CACHE.parent.mkdir(parents=True, exist_ok=True)
    _LINZ_CATALOG_CACHE.write_text(
        json.dumps({"key": cache_key, "entries": entries}, indent=2),
        encoding="utf-8",
    )
    return entries


def linz_find_collections(bbox_lonlat: tuple[float, float, float, float],
                          variant: str = "dem_1m") -> list[tuple[str, list, dict]]:
    """Walk LINZ static catalog, return [(collection_url, bbox, collection_obj), ...].

    variant: 'dem_1m' (terrain) or 'dsm_1m' (surface incl. canopy/buildings).
    """
    index = _linz_load_catalog_index(variant)
    hits = []
    for entry in index:
        if _bbox_intersects(entry["bbox"], list(bbox_lonlat)):
            try:
                col = requests.get(entry["url"], timeout=30).json()
            except Exception:
                continue
            hits.append((entry["url"], entry["bbox"], col))
    return hits


def fetch_linz(dataset: str, bbox_lonlat: tuple[float, float, float, float],
               out_path: Path, size: int = 1024) -> bool:
    """Pull LINZ NZ 1m DEM/DSM over a lat/lon bbox.

    LINZ_1m_DTM = ground bare earth, LINZ_1m_DSM = first-return surface (canopy).
    Walks the static catalog to find regional collection(s), then mosaics matching
    items windowed-read from EPSG:2193 COGs and reprojects to EPSG:4326.
    """
    variant = "dsm_1m" if "DSM" in dataset.upper() else "dem_1m"
    print(f"  LINZ: searching {variant} collections for bbox={bbox_lonlat}")
    hits = linz_find_collections(bbox_lonlat, variant=variant)
    if not hits:
        raise RuntimeError(
            f"no LINZ {variant} collection covers bbox {bbox_lonlat}; check "
            "https://nz-elevation.s3-ap-southeast-2.amazonaws.com/catalog.json"
        )
    print(f"  {len(hits)} collection(s) match")

    # Walk items in each hit, pick those whose item bbox intersects ours.
    # Per-item bbox is only available inside the item.json — N HTTP fetches.
    # Cache per-collection item lists to avoid re-fetching on repeat queries.
    item_urls = []
    items_cache_path = (Path(__file__).resolve().parent / "source_dems"
                        / f"_linz_items_cache.json")
    items_cache = {}
    if items_cache_path.exists():
        try:
            items_cache = json.loads(items_cache_path.read_text(encoding="utf-8"))
        except Exception:
            items_cache = {}

    for col_url, col_bbox, col in hits:
        col_dir = col_url.rsplit("/", 1)[0]
        # Build/load this collection's item index: list of {url, bbox, asset_url}
        if col_url in items_cache:
            print(f"  [item-cache hit] {col_url.split('/')[-2]}: "
                  f"{len(items_cache[col_url])} items")
            col_items = items_cache[col_url]
        else:
            col_items = []
            n_links = sum(1 for l in col.get("links", []) if l.get("rel") == "item")
            print(f"  [item-cache miss] fetching {n_links} item.jsons for "
                  f"{col_url.split('/')[-2]} (~{n_links // 5}s)...")
            for link in col.get("links", []):
                if link.get("rel") != "item":
                    continue
                item_href = link["href"]
                item_url = (item_href if item_href.startswith("http")
                            else col_dir + "/" + item_href.lstrip("./"))
                try:
                    it = requests.get(item_url, timeout=30).json()
                except Exception:
                    continue
                assets = it.get("assets") or {}
                asset_url = ""
                for ak, av in assets.items():
                    href = av.get("href", "")
                    if "tiff" in (av.get("type", "") + href).lower() and "thumb" not in ak.lower():
                        asset_url = (href if href.startswith("http")
                                     else col_dir + "/" + href.lstrip("./"))
                        break
                col_items.append({
                    "url": item_url,
                    "bbox": it.get("bbox"),
                    "asset_url": asset_url,
                })
            items_cache[col_url] = col_items
            items_cache_path.write_text(json.dumps(items_cache), encoding="utf-8")

        for it_entry in col_items:
            if it_entry.get("asset_url") and _bbox_intersects(
                    it_entry.get("bbox"), list(bbox_lonlat)):
                item_urls.append(it_entry["asset_url"])
    if not item_urls:
        raise RuntimeError(f"matched LINZ collection(s) but no items intersect bbox {bbox_lonlat}")
    print(f"  {len(item_urls)} item(s) intersect; first: {item_urls[0]}")

    import rasterio
    from rasterio.merge import merge as rio_merge
    from rasterio.warp import (calculate_default_transform, reproject,
                                Resampling, transform_bounds)
    from rasterio.windows import from_bounds

    os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
    os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")

    sources = [rasterio.open(u) for u in item_urls]
    src_crs = sources[0].crs
    src_bbox_in_native = transform_bounds("EPSG:4326", src_crs, *bbox_lonlat,
                                          densify_pts=21)
    if len(sources) > 1:
        merged_data, merged_transform = rio_merge(sources, bounds=src_bbox_in_native)
        merged_data = merged_data[0]
    else:
        s = sources[0]
        win = from_bounds(*src_bbox_in_native,
                          transform=s.transform).round_offsets().round_lengths()
        merged_data = s.read(1, window=win)
        merged_transform = s.window_transform(win)
    for s in sources:
        s.close()

    src_h, src_w = merged_data.shape
    src_w_world, src_n_world = merged_transform * (0, 0)
    src_e_world, src_s_world = merged_transform * (src_w, src_h)
    src_bounds = (min(src_w_world, src_e_world), min(src_s_world, src_n_world),
                  max(src_w_world, src_e_world), max(src_s_world, src_n_world))
    dst_w, dst_h = size, size
    dst_transform, _, _ = calculate_default_transform(
        src_crs, "EPSG:4326", src_w, src_h, *src_bounds,
        dst_width=dst_w, dst_height=dst_h,
    )
    dst = np.full((dst_h, dst_w), -9999.0, dtype=np.float32)
    reproject(
        source=merged_data.astype(np.float32),
        destination=dst,
        src_transform=merged_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs="EPSG:4326",
        resampling=Resampling.bilinear,
        src_nodata=-9999.0,
        dst_nodata=-9999.0,
    )

    # NoData fill: replace remaining sentinels (-9999, partially-blended edges
    # near sentinel) with the valid-pixel mean so downstream pipelines that
    # don't honour nodata don't blow up min/max normalization.
    bad = (dst < -9000.0) | np.isnan(dst)
    if bad.any():
        valid = dst[~bad]
        fill = float(valid.mean()) if valid.size else 0.0
        n_bad = int(bad.sum())
        print(f"  [warn] {n_bad}/{dst.size} bad pixels in output ({100*n_bad/dst.size:.1f}%); "
              f"fill={fill:.1f}m")
        dst = np.where(bad, fill, dst)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out_path, "w",
        driver="GTiff",
        height=dst_h, width=dst_w, count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=dst_transform,
        compress="lzw",
        nodata=-9999.0,
    ) as dst_ds:
        dst_ds.write(dst, 1)

    print(f"  wrote {out_path} ({dst_h}x{dst_w}, "
          f"min={float(dst.min()):.1f} max={float(dst.max()):.1f})")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    all_ds = list(COLLECTIONS.keys()) + ["LINZ1m_DTM", "LINZ1m_DSM"]
    ap.add_argument("--dataset", required=True, choices=all_ds)
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("W", "S", "E", "N"))
    ap.add_argument("--id", required=True)
    ap.add_argument("--out-dir", type=Path,
                    default=Path(__file__).resolve().parent / "source_dems")
    ap.add_argument("--size", type=int, default=1024)
    args = ap.parse_args()

    bbox_str = f"{args.bbox[0]:+.4f}_{args.bbox[1]:+.4f}_{args.bbox[2]:+.4f}_{args.bbox[3]:+.4f}"
    out_path = args.out_dir / f"{args.dataset}_{bbox_str}.tif"

    if out_path.exists():
        print(f"  cached: {out_path}")
        return 0

    if args.dataset.startswith("LINZ"):
        fetch_linz(args.dataset, tuple(args.bbox), out_path, size=args.size)
    else:
        fetch_pgc(args.dataset, tuple(args.bbox), out_path, size=args.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
