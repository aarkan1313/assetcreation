"""Cache-only bulk fetch — calls fetch_opentopo per wishlist region and stops.

Skips the post-processing pipeline (slope/biome/splat) that depends on the
archived terrain_bundle module. Just builds the dems/ raw TIFF cache.

Usage:
    python pipelines/terrain/bulk_fetch_to_cache.py --tier premium
    python pipelines/terrain/bulk_fetch_to_cache.py --tier all --limit 10
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(r"D:\assets")
TERRAIN_DIR = REPO / "pipelines" / "terrain"
WISHLIST = REPO / "art_lab" / "biomes" / "data_wishlist.json"
CALL_LOG = Path.home() / ".opentopo_calls.jsonl"

# Make sibling import_dem importable so we can call fetch_opentopo directly.
sys.path.insert(0, str(TERRAIN_DIR))


def gather_regions(wishlist: dict, tier: str | None) -> list[dict]:
    out = []
    for tier_name, tier_data in wishlist.get("tiers", {}).items():
        if tier and tier != "all" and tier_name != tier:
            continue
        default_dataset = tier_data.get("default_dataset")
        for r in tier_data.get("regions", []):
            merged = dict(r)
            merged.setdefault("dataset", default_dataset)
            merged["_tier"] = tier_name
            out.append(merged)
    return out


def log_api_call(region: dict, success: bool) -> None:
    entry = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "region_id": region["id"],
        "dataset": region.get("dataset", "auto"),
        "bbox": region["bbox"],
        "success": success,
    }
    with CALL_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def calls_in_last_24h() -> int:
    if not CALL_LOG.exists():
        return 0
    cutoff = time.time() - 24 * 3600
    n = 0
    with CALL_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                if rec.get("ts", 0) >= cutoff:
                    n += 1
            except json.JSONDecodeError:
                pass
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wishlist", type=Path, default=WISHLIST)
    ap.add_argument("--tier", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--throttle-sec", type=float, default=2.0)
    ap.add_argument("--quota", type=int, default=400)
    args = ap.parse_args()

    wishlist = json.loads(args.wishlist.read_text(encoding="utf-8"))
    regions = gather_regions(wishlist, args.tier)
    if args.limit:
        regions = regions[:args.limit]

    used = calls_in_last_24h()
    remaining = max(0, args.quota - used)
    print(f"plan: {len(regions)} regions  tier={args.tier or 'any'}  dry_run={args.dry_run}")
    print(f"quota: {used} calls in last 24h, {remaining}/{args.quota} remaining")

    # Lazy import — sets up rasterio etc.
    if not args.dry_run:
        from import_dem import fetch_opentopo, _cache_key

    cache_hits = 0
    new_pulls = 0
    failures: list[tuple[str, str]] = []
    last_call_t = 0.0
    real_calls = 0

    for i, r in enumerate(regions, 1):
        rid = r["id"]
        dataset = r.get("dataset", "COP30")
        bbox = tuple(r["bbox"])

        if not args.dry_run:
            cached = _cache_key(bbox, dataset)
            already_cached = cached.exists()

            if not already_cached and real_calls >= remaining:
                print(f"\n[stop] hit estimated daily quota ({args.quota}). Resume tomorrow.")
                break

            print(f"\n[{i}/{len(regions)}] tier={r['_tier']}  id={rid}  ds={dataset}")
            if already_cached:
                print(f"  [cache hit] {cached.name}")
                cache_hits += 1
                continue

            # Throttle between real calls
            if last_call_t:
                elapsed = time.monotonic() - last_call_t
                if elapsed < args.throttle_sec:
                    time.sleep(args.throttle_sec - elapsed)

            try:
                arr = fetch_opentopo(bbox, dataset=dataset, cache=True)
                last_call_t = time.monotonic()
                real_calls += 1
                log_api_call(r, True)
                shape = arr.shape if hasattr(arr, "shape") else "?"
                emin = float(arr.min()) if hasattr(arr, "min") else 0.0
                emax = float(arr.max()) if hasattr(arr, "max") else 0.0
                print(f"  [pulled] shape={shape} elev={emin:.0f}..{emax:.0f}m -> {cached.name}")
                new_pulls += 1
            except Exception as e:
                last_call_t = time.monotonic()
                real_calls += 1
                log_api_call(r, False)
                msg = str(e)[:120]
                print(f"  [FAIL] {msg}")
                failures.append((rid, msg))
        else:
            print(f"  would: {dataset}  bbox={bbox}  id={rid}")

    print(f"\n=== bulk_fetch_to_cache done ===")
    print(f"  cache hits:  {cache_hits}")
    print(f"  new pulls:   {new_pulls}")
    print(f"  failures:    {len(failures)}")
    if failures:
        print("\nfailures:")
        for fid, reason in failures[:30]:
            print(f"  {fid}: {reason}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
