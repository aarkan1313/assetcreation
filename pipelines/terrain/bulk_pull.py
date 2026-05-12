"""Bulk-pull DEMs from a wishlist file.

Walks data_wishlist.json (and optionally data_wishlist_mystery.json) and runs
import_dem.py per region. Builds the source TIFF cache so future region_pipeline
runs are instant.

Usage:
  # Pull only premium tier (recommended first; ~12GB)
  python bulk_pull.py --tier premium

  # Pull everything in the main wishlist
  python bulk_pull.py --tier all

  # Pull mystery regions (300 random unknowns)
  python bulk_pull.py --wishlist art_lab/biomes/data_wishlist_mystery.json

  # Stop after N regions (great for trying it out)
  python bulk_pull.py --tier showcase --limit 3

  # Dry run — print what would be pulled
  python bulk_pull.py --tier all --dry-run

If a region requires Pro (e.g. USGS_1m), and your API key is free-tier, that
specific region will fail — script logs and continues. Resumable: cache hits
make re-runs near-instant.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"D:\assets")
TERRAIN_DIR = REPO / "pipelines" / "terrain"
DEFAULT_WISHLIST = REPO / "art_lab" / "biomes" / "data_wishlist.json"


def gather_regions(wishlist: dict, tier: str | None) -> list[dict]:
    out = []
    if "tiers" in wishlist:
        for tier_name, tier_data in wishlist["tiers"].items():
            if tier and tier != "all" and tier_name != tier:
                continue
            default_dataset = tier_data.get("default_dataset")
            for r in tier_data.get("regions", []):
                merged = dict(r)
                merged.setdefault("dataset", default_dataset)
                merged["_tier"] = tier_name
                out.append(merged)
    elif "regions" in wishlist:
        # Mystery file format
        for r in wishlist["regions"]:
            merged = dict(r)
            merged["_tier"] = "mystery"
            out.append(merged)
    return out


def run_import(region: dict, dry_run: bool) -> tuple[bool, float]:
    cmd = [sys.executable, str(TERRAIN_DIR / "import_dem.py"),
           "--id", region["id"], "--source", "opentopo",
           "--bbox", *[str(v) for v in region["bbox"]],
           "--size", "1024"]
    if region.get("dataset"):
        cmd += ["--dataset", region["dataset"]]
    if region.get("bathymetry") or "bath_" in region["id"]:
        cmd += ["--bathymetry"]
    if region.get("res"):
        cmd += ["--res", str(region["res"])]
    print(f"  $ {' '.join(cmd)}")
    if dry_run:
        return True, 0.0
    t0 = time.monotonic()
    rc = subprocess.run(cmd).returncode
    return (rc == 0), (time.monotonic() - t0)


CALL_LOG = Path.home() / ".opentopo_calls.jsonl"


def log_api_call(region: dict, success: bool) -> None:
    """Append a one-line record of every (real) API call we made, so we can
    track our daily quota burn against the OpenTopo rate limits."""
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
    count = 0
    with CALL_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                if rec.get("ts", 0) >= cutoff:
                    count += 1
            except json.JSONDecodeError:
                continue
    return count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wishlist", type=Path, default=DEFAULT_WISHLIST)
    ap.add_argument("--tier", default=None,
                    help="restrict to one tier: showcase, premium, standard, bathymetric, highres_open, all")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N regions")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--continue-on-error", action="store_true", default=True)
    ap.add_argument("--quota", type=int, default=400,
                    help="rate-limit assumption (default: 400/24h = 200 globaldem + 200 USGS, "
                         "OT+ subscriber tier). 50 free non-academic; 400 OT+; 400 academic.")
    ap.add_argument("--throttle-sec", type=float, default=2.0,
                    help="minimum seconds between API calls (default: 2s)")
    ap.add_argument("--no-catalog-refresh", action="store_true",
                    help="skip refreshing world3/data_catalog.json after pulls. "
                         "Default: catalog refresh runs after a successful pull "
                         "so downstream tools see new DEMs immediately.")
    args = ap.parse_args()

    if not args.wishlist.exists():
        raise SystemExit(f"wishlist not found: {args.wishlist}")
    wishlist = json.loads(args.wishlist.read_text(encoding="utf-8"))

    regions = gather_regions(wishlist, args.tier)
    if args.limit:
        regions = regions[:args.limit]

    used = calls_in_last_24h()
    remaining = max(0, args.quota - used)
    print(f"plan: {len(regions)} regions from {args.wishlist}")
    print(f"      tier={args.tier or 'any'}  dry_run={args.dry_run}")
    print(f"      quota: ~{used} calls in last 24h, ~{remaining} remaining of {args.quota}")
    if remaining < len(regions) and not args.dry_run:
        print(f"      [WARN] would exceed quota; will stop after ~{remaining} successful calls.")

    successes = 0
    failures: list[tuple[str, str]] = []
    total_time = 0.0
    last_call_t = 0.0
    for i, r in enumerate(regions, 1):
        if not args.dry_run and successes >= remaining:
            print(f"\n[stop] hit estimated daily quota ({args.quota}). "
                  f"Resume tomorrow or pass --quota with a higher value.")
            break

        # Throttle between real calls so we don't burst
        if not args.dry_run and last_call_t:
            elapsed = time.monotonic() - last_call_t
            if elapsed < args.throttle_sec:
                time.sleep(args.throttle_sec - elapsed)

        print(f"\n[{i}/{len(regions)}] tier={r['_tier']}  id={r['id']}  ds={r.get('dataset', 'auto')}")
        try:
            ok, elapsed = run_import(r, args.dry_run)
            total_time += elapsed
            if not args.dry_run:
                last_call_t = time.monotonic()
                log_api_call(r, ok)
            if ok:
                successes += 1
            else:
                failures.append((r['id'], 'rc!=0'))
                if not args.continue_on_error:
                    break
        except KeyboardInterrupt:
            print("\n[abort] Ctrl-C — stopping early")
            break
        except Exception as e:
            failures.append((r['id'], str(e)))
            print(f"  [error] {e}")
            if not args.dry_run:
                log_api_call(r, False)
            if not args.continue_on_error:
                break

    print(f"\n=== bulk_pull done ===")
    print(f"  ok:     {successes}/{len(regions)}")
    print(f"  failed: {len(failures)}")
    print(f"  total:  {total_time:.1f}s")
    if failures:
        print("\nfailed:")
        for fid, reason in failures[:30]:
            print(f"  {fid}: {reason}")

    # Post-hook: refresh world3/data_catalog.json so downstream tools see new DEMs.
    # Skip on --no-catalog-refresh, dry-run, or zero successful pulls.
    if not args.no_catalog_refresh and not args.dry_run and successes > 0:
        refresh_master_catalog()

    return 0 if not failures else 1


def refresh_master_catalog() -> None:
    """Call build_master_catalog.py so world3/data_catalog.json reflects
    any new DEMs/textures/bundles. Added 2026-05-11 (Phase D.3) so the
    catalog doesn't drift after bulk pulls."""
    import subprocess
    catalog_builder = Path(__file__).resolve().parent / "build_master_catalog.py"
    if not catalog_builder.exists():
        print(f"\n[catalog-refresh] skipped: {catalog_builder} not found")
        return
    print(f"\n=== refreshing world3/data_catalog.json ===")
    try:
        result = subprocess.run(
            [sys.executable, str(catalog_builder)],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Surface only the summary lines (build_master_catalog prints
        # totals at the end) — full output is too verbose to inline.
        for line in result.stdout.splitlines()[-12:]:
            print(f"  {line}")
        if result.returncode != 0:
            print(f"  [warn] catalog refresh exit={result.returncode}; "
                  "run `python pipelines/terrain/build_master_catalog.py` manually")
    except subprocess.TimeoutExpired:
        print("  [warn] catalog refresh timed out (>60s)")
    except Exception as e:
        print(f"  [warn] catalog refresh failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
