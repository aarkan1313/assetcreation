"""Download CC0 PBR materials from ambientCG via the v2 API.

Per the SOTA report: ambientCG is the default programmatic CC0 source. This
script:
  1. Queries the v2 full_json endpoint for materials matching a category.
  2. Downloads the requested resolution ZIP (1K/2K/4K).
  3. Extracts albedo/normal/roughness/AO/height/metallic into a clean folder.
  4. Appends a record to world/textures/catalog/materials.jsonl with
     license, source URL, hash, and map presence.

Usage:
  python ambientcg_fetch.py --category Ground --limit 5 --resolution 1K
  python ambientcg_fetch.py --asset Rock035 --resolution 2K
  python ambientcg_fetch.py --list-categories
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    raise SystemExit("requests not installed; pip install requests")


API_BASE = "https://ambientcg.com/api/v2"
USER_AGENT = "asset-factory-llm-pipeline/0.1 (+https://github.com/anthropics/claude-code)"
CATALOG_DIR = Path("D:/assets/world/textures/catalog")
DOWNLOAD_DIR = Path("D:/assets/world/textures/library")


MAP_PATTERNS = {
    "albedo":   re.compile(r"_color\.|_basecolor\.|_albedo\.", re.I),
    "normal":   re.compile(r"_normalgl\.|_normal\.|_norm\.", re.I),
    "roughness": re.compile(r"_roughness\.|_rough\.", re.I),
    "ao":       re.compile(r"_ambientocclusion\.|_ao\.|_occlusion\.", re.I),
    "height":   re.compile(r"_displacement\.|_height\.|_disp\.", re.I),
    "metallic": re.compile(r"_metalness\.|_metallic\.|_metal\.", re.I),
}


def headers():
    return {"User-Agent": USER_AGENT, "Accept": "application/json"}


def list_assets(category: str, limit: int = 10) -> list[dict]:
    url = f"{API_BASE}/full_json"
    params = {"type": "Material", "category": category, "limit": limit, "include": "downloadData,licenseData"}
    r = requests.get(url, params=params, headers=headers(), timeout=60)
    r.raise_for_status()
    return r.json().get("foundAssets", [])


def fetch_asset(asset_id: str) -> dict:
    url = f"{API_BASE}/full_json"
    params = {"id": asset_id, "include": "downloadData,licenseData"}
    r = requests.get(url, params=params, headers=headers(), timeout=60)
    r.raise_for_status()
    found = r.json().get("foundAssets", [])
    if not found:
        raise RuntimeError(f"asset {asset_id} not found")
    return found[0]


def pick_download(asset: dict, resolution: str = "1K", fmt: str = "PNG") -> dict | None:
    """Pick a download record matching the given resolution + format.

    Attribute format is e.g. "1K-PNG", "2K-JPG", "4K-PNG".
    """
    target = f"{resolution}-{fmt}"
    folders = asset.get("downloadFolders", {})
    for fname, folder in folders.items():
        cats = folder.get("downloadFiletypeCategories", {})
        for cname, cat in cats.items():
            for d in cat.get("downloads", []):
                if d.get("attribute") == target:
                    return d
    # fallback: any matching resolution
    for fname, folder in folders.items():
        cats = folder.get("downloadFiletypeCategories", {})
        for cname, cat in cats.items():
            for d in cat.get("downloads", []):
                attr = d.get("attribute", "")
                if attr.startswith(f"{resolution}-"):
                    return d
    return None


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_map(name: str) -> str | None:
    for kind, pat in MAP_PATTERNS.items():
        if pat.search(name):
            return kind
    return None


def extract_zip(zip_path: Path, dest: Path) -> dict:
    """Extract ZIP, classify maps, return {map_kind: relative_path}."""
    dest.mkdir(parents=True, exist_ok=True)
    maps = {}
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.endswith("/"):
                continue
            data = zf.read(member)
            base = Path(member).name
            kind = classify_map(base)
            out_path = dest / base
            out_path.write_bytes(data)
            if kind and kind not in maps:
                maps[kind] = base
    return maps


def append_catalog(record: dict):
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    path = CATALOG_DIR / "materials.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def download_one(asset: dict, resolution: str = "1K") -> dict | None:
    asset_id = asset.get("assetId")
    print(f"[{asset_id}]")
    pick = pick_download(asset, resolution=resolution, fmt="PNG")
    if not pick:
        print(f"  no PNG download at {resolution}, skipping")
        return None
    download_url = pick.get("downloadLink") or pick.get("fullDownloadPath") or pick.get("rawLink")
    if not download_url:
        # API responses vary; pull anything URL-shaped from the record
        for v in pick.values():
            if isinstance(v, str) and v.startswith("http"):
                download_url = v
                break
    if not download_url:
        print(f"  no download URL in record")
        return None

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    asset_dir = DOWNLOAD_DIR / asset_id
    if asset_dir.exists() and any(asset_dir.glob("*")):
        print(f"  already downloaded -> {asset_dir}")
        return None
    asset_dir.mkdir(parents=True, exist_ok=True)

    zip_path = asset_dir / f"{asset_id}_{resolution}.zip"
    print(f"  GET {download_url}")
    with requests.get(download_url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=180) as r:
        r.raise_for_status()
        with zip_path.open("wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    sha = sha256_of(zip_path)
    maps = extract_zip(zip_path, asset_dir)
    zip_path.unlink()

    record = {
        "id": asset_id,
        "source": "ambientcg",
        "source_url": f"https://ambientcg.com/view?id={asset_id}",
        "license": "CC0",
        "category": asset.get("dataTagCategory") or asset.get("category"),
        "tags": asset.get("tags", []),
        "resolution": resolution,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "zip_sha256": sha,
        "library_path": str(asset_dir.relative_to(Path("D:/assets"))),
        "maps": maps,
        "map_completeness": sorted(maps.keys()),
    }
    append_catalog(record)
    print(f"  saved {len(maps)} maps -> {asset_dir.name}")
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", help="ambientCG category, e.g. Ground, Rock, Wood")
    ap.add_argument("--asset", help="exact asset ID, e.g. Rock035")
    ap.add_argument("--resolution", default="1K", choices=["1K", "2K", "4K", "8K"])
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--list-categories", action="store_true")
    args = ap.parse_args()

    if args.list_categories:
        # ambientCG categories are well-documented; print common ones
        for c in ["Ground", "Rock", "Wood", "Bricks", "Concrete", "Metal", "Fabric", "Tiles",
                  "Wallpaper", "Asphalt", "Marble", "Snow", "Plastic", "Leather"]:
            print(f"  {c}")
        return

    if args.asset:
        asset = fetch_asset(args.asset)
        download_one(asset, resolution=args.resolution)
        return

    if not args.category:
        raise SystemExit("Need --asset or --category")

    print(f"querying ambientCG: category={args.category} limit={args.limit}")
    assets = list_assets(args.category, limit=args.limit)
    print(f"  found {len(assets)} assets")
    for a in assets:
        try:
            download_one(a, resolution=args.resolution)
            time.sleep(0.5)  # be polite to the API
        except Exception as e:
            print(f"  ERROR for {a.get('assetId')}: {e}")


if __name__ == "__main__":
    main()
