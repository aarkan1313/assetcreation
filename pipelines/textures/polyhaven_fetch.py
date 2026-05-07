"""Download CC0 PBR materials from Poly Haven via the public API.

Per the SOTA report: Poly Haven is the curated secondary CC0 source. Their
API requires a unique User-Agent and commercial usage requires custom
permission, so by default we pull only for asset-factory development.

API quick-ref:
  GET https://api.polyhaven.com/assets?type=textures      list assets
  GET https://api.polyhaven.com/info/<asset_id>           single asset
  GET https://api.polyhaven.com/files/<asset_id>          downloadable files
                                                            including PBR maps

Usage:
  python polyhaven_fetch.py --asset rocks_ground_06 --resolution 1k
  python polyhaven_fetch.py --category Rocks --limit 5 --resolution 1k
  python polyhaven_fetch.py --list-categories
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    raise SystemExit("requests not installed; pip install requests")


API_BASE = "https://api.polyhaven.com"
USER_AGENT = "asset-factory-llm-pipeline/0.1 (anthropic claude-code, dev/CC0)"
CATALOG_DIR = Path("D:/assets/world/textures/catalog")
DOWNLOAD_DIR = Path("D:/assets/world/textures/library")


# Poly Haven map name → our canonical name
MAP_NAME_NORMALIZE = {
    "Diffuse": "albedo", "diff": "albedo", "Color": "albedo", "albedo": "albedo",
    "nor_gl": "normal", "normal_gl": "normal", "Normal": "normal", "nor_dx": "normal_dx",
    "rough": "roughness", "Roughness": "roughness",
    "ao": "ao", "AO": "ao",
    "disp": "height", "Displacement": "height",
    "metal": "metallic", "Metal": "metallic",
}


def headers():
    return {"User-Agent": USER_AGENT, "Accept": "application/json"}


def list_assets(category: str | None, limit: int = 10) -> list[tuple[str, dict]]:
    url = f"{API_BASE}/assets"
    params = {"type": "textures"}
    if category:
        params["categories"] = category
    r = requests.get(url, params=params, headers=headers(), timeout=60)
    r.raise_for_status()
    items = list(r.json().items())[:limit]
    return items


def asset_files(asset_id: str) -> dict:
    url = f"{API_BASE}/files/{asset_id}"
    r = requests.get(url, headers=headers(), timeout=60)
    r.raise_for_status()
    return r.json()


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def append_catalog(record: dict):
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    path = CATALOG_DIR / "materials.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def find_download(files_data: dict, kind: str, resolution: str, fmt: str = "png") -> str | None:
    """Walk the files_data to find a URL for a given map kind/resolution/format.

    Poly Haven files JSON layout (varies a bit per asset):
      {
        "Diffuse":   { "1k": { "png": { "url": ..., "md5": ... }, "jpg": {...} }, ... },
        "nor_gl":    { ... },
        "Roughness": { ... },
        ...
      }
    """
    res = files_data.get(kind, {}).get(resolution, {})
    if fmt in res and "url" in res[fmt]:
        return res[fmt]["url"]
    # try jpg fallback
    if "jpg" in res and "url" in res["jpg"]:
        return res["jpg"]["url"]
    return None


def download_asset(asset_id: str, resolution: str = "1k", fmt: str = "png"):
    print(f"[{asset_id}]")
    files_data = asset_files(asset_id)
    asset_dir = DOWNLOAD_DIR / asset_id
    if asset_dir.exists() and any(asset_dir.glob("*")):
        print(f"  already downloaded -> {asset_dir}")
        return
    asset_dir.mkdir(parents=True, exist_ok=True)

    canonical_maps = {}
    for ph_name, our_name in MAP_NAME_NORMALIZE.items():
        if ph_name not in files_data:
            continue
        if our_name in canonical_maps:
            continue  # already got it via another alias
        url = find_download(files_data, ph_name, resolution, fmt)
        if not url:
            continue
        out_path = asset_dir / f"{asset_id}_{our_name}.{Path(url).suffix.lstrip('.') or fmt}"
        try:
            print(f"  GET {ph_name} -> {out_path.name}")
            with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=180) as r:
                r.raise_for_status()
                with out_path.open("wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
            canonical_maps[our_name] = out_path.name
        except Exception as e:
            print(f"    error: {e}")

    if not canonical_maps:
        print("  no maps downloaded")
        return

    # Get info for license + tags
    try:
        info = requests.get(f"{API_BASE}/info/{asset_id}", headers=headers(), timeout=60).json()
    except Exception:
        info = {}

    record = {
        "id": asset_id,
        "source": "polyhaven",
        "source_url": f"https://polyhaven.com/a/{asset_id}",
        "license": "CC0",
        "category": (info.get("categories") or [None])[0],
        "tags": info.get("tags", []),
        "resolution": resolution,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "library_path": str(asset_dir.relative_to(Path("D:/assets"))),
        "maps": canonical_maps,
        "map_completeness": sorted(canonical_maps.keys()),
    }
    append_catalog(record)
    print(f"  saved {len(canonical_maps)} maps -> {asset_dir.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", help="exact poly haven asset id, e.g. rocks_ground_06")
    ap.add_argument("--category", help="poly haven category, e.g. Rocks, Wood, Bricks")
    ap.add_argument("--resolution", default="1k", choices=["1k", "2k", "4k", "8k"])
    ap.add_argument("--fmt", default="png", choices=["png", "jpg"])
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--list-categories", action="store_true")
    args = ap.parse_args()

    if args.list_categories:
        # Poly Haven texture categories (from public API)
        for c in ["Floor", "Wall", "Ground", "Rocks", "Wood", "Brick", "Concrete",
                  "Metal", "Fabric", "Tiles", "Asphalt", "Marble", "Plaster", "Outdoor", "Snow"]:
            print(f"  {c}")
        return

    if args.asset:
        download_asset(args.asset, resolution=args.resolution, fmt=args.fmt)
        return

    if not args.category:
        raise SystemExit("Need --asset or --category")

    print(f"querying Poly Haven: category={args.category} limit={args.limit}")
    items = list_assets(args.category, limit=args.limit)
    print(f"  found {len(items)} assets")
    for asset_id, _meta in items:
        try:
            download_asset(asset_id, resolution=args.resolution, fmt=args.fmt)
            time.sleep(0.5)
        except Exception as e:
            print(f"  ERROR for {asset_id}: {e}")


if __name__ == "__main__":
    main()
