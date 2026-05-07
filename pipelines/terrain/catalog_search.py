"""OpenTopography /otCatalog client.

Bbox-based search for what datasets are available at any location. Useful for:
  - Discovering point-cloud LiDAR campaigns we wouldn't know by name
  - Listing federated USGS 3DEP datasets per region
  - Pre-flight check: "what's the highest-res DEM available here?"

Usage:
  # Search a bbox, list all rasters
  python catalog_search.py --bbox -112.20 37.55 -112.00 37.75

  # Include point clouds
  python catalog_search.py --bbox -112.20 37.55 -112.00 37.75 --product PointCloud

  # Include federated (USGS 3DEP) catalog
  python catalog_search.py --bbox -112.20 37.55 -112.00 37.75 --federated

  # Detailed metadata
  python catalog_search.py --bbox -112.20 37.55 -112.00 37.75 --detail

The /otCatalog endpoint does NOT require an API key (it's a metadata search,
not a data download), so this works on the free tier without quota cost.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

URL = "https://portal.opentopography.org/API/otCatalog"


def search(bbox: tuple[float, float, float, float], product: str | None = None,
           detail: bool = False, include_federated: bool = False) -> dict:
    try:
        import requests
    except ImportError:
        raise SystemExit("requests not installed; pip install requests")

    minx, miny, maxx, maxy = bbox
    params = {
        "minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy,
        "outputFormat": "json",
        "detail": "true" if detail else "false",
        "include_federated": "true" if include_federated else "false",
    }
    if product:
        params["productFormat"] = product

    print(f"  GET {URL} bbox={bbox} product={product or 'any'}")
    r = requests.get(URL, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def summarize(result: dict) -> None:
    """Pretty-print catalog hits."""
    if not result:
        print("  no results")
        return
    if isinstance(result, dict) and "Datasets" in result:
        datasets = result["Datasets"]
    elif isinstance(result, list):
        datasets = result
    else:
        # Print whatever we got, raw, and bail
        print(json.dumps(result, indent=2)[:2000])
        return
    print(f"\n=== {len(datasets)} datasets matched ===\n")
    for i, entry in enumerate(datasets, 1):
        # Each entry is wrapped: {"Dataset": {... actual fields ...}}
        d = entry.get("Dataset", entry) if isinstance(entry, dict) else {}
        name = d.get("name") or d.get("title") or "?"
        alternate = d.get("alternateName") or ""
        fmt = d.get("fileFormat") or "?"
        date = d.get("dateCreated") or ""
        url = d.get("url") or ""
        print(f"  {i}. {name}")
        if alternate:
            print(f"     api id:   {alternate}")
        print(f"     format:   {fmt}")
        if date:
            print(f"     created:  {date}")
        if url:
            print(f"     doi/url:  {url}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("minx", "miny", "maxx", "maxy"))
    ap.add_argument("--product", choices=["Raster", "PointCloud"], default=None,
                    help="restrict to one product type")
    ap.add_argument("--detail", action="store_true",
                    help="return full per-dataset metadata")
    ap.add_argument("--federated", action="store_true",
                    help="include federated USGS 3DEP catalog hits")
    ap.add_argument("--out", type=Path, default=None,
                    help="(optional) write full JSON response to file")
    args = ap.parse_args()

    res = search(tuple(args.bbox), args.product, args.detail, args.federated)
    if args.out:
        args.out.write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"  wrote {args.out}")
    summarize(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
