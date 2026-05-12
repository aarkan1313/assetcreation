"""Pull all stitched mega-stacks in priority order.

Reads art_lab/biomes/data_wishlist.json, walks the stitched tier in a
priority order, and runs tile_stitch.py per entry. Skips entries already
fully done. Logs per-entry status to /d/tmp/bulk_pull_logs/megastack_status.json
so it can be resumed.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"d:/assets")
WISH = REPO / "art_lab/biomes/data_wishlist.json"
OUTPUT = REPO / "pipelines/terrain/output"
TILE_STITCH = REPO / "pipelines/terrain/tile_stitch.py"
STATUS_FILE = Path("/d/tmp/bulk_pull_logs/megastack_status.json")
LOGS_DIR = Path("/d/tmp/bulk_pull_logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Priority: 1m hi-res first, then biome-gap-fill COP30, then 10m, then 30m
# regional, then bathy.
PRIORITY = [
    # USGS1m new (highest value, hardest to redo)
    "sequoia_high_country_1m",
    "shenandoah_full_1m",
    "great_basin_full_1m",
    "haleakala_full_1m",
    "north_cascades_full_1m",
    "lassen_volcanic_full_1m",
    "adirondacks_full_1m",
    "guadalupe_peak_full_1m",
    "kilauea_full_1m",
    "smoky_mtns_north_1m",
    "rocky_mtn_co_estes_1m",
    "wind_river_wy_1m",
    "yellowstone_grand_1m",
    "glacier_park_mt_1m",
    "white_mtns_nh_1m",
    "olympic_lower_1m",
    # NZ 1m
    "nz_aoraki_full_1m",
    "nz_milford_full_1m",
    "nz_taranaki_full_1m",
    # Foreign biome-gap (COP30 30m, dirt-cheap, lots of biome value)
    "kilimanjaro_kenya_full",
    "atlas_morocco_full",
    "tasmanian_full",
    "kamchatka_full",
    "pamirs_full",
    "mt_roraima_full",
    "iguazu_full",
    "great_dividing_au_full",
    "halong_bay_full",
    "guilin_karst_full",
    "sundarbans_full",
    "galapagos_isabela_full",
    # US 10m regional (medium cost, big visual value)
    "sierra_nevada_10m",
    "wasatch_range_10m",
    "olympic_full_10m",
    "white_mtns_full_10m",
    "cascade_volcanic_10m",
    "san_juan_co_10m",
    "ozarks_10m",
    "blue_ridge_full_10m",
    # Large 30m regional (cheap, continental scale)
    "alps_central_full",
    "andes_southern_full",
    "himalaya_central_full",
    "japan_alps_full",
    "kilimanjaro_region",
    "saharan_atlas_region",
    "patagonia_glacier_region",
    "scottish_highlands",
    "iceland_central_full",
    "alaska_range_full",
    "siberian_baikal",
    "new_zealand_south_alps",
    "ethiopian_simiens",
    "pyrenees_full",
    "carpathians_high",
    "kunlun_china",
    "altai_russia",
    # AW3D30 alternates
    "norwegian_fjord_full",
    "philippines_volcanic",
    "indonesia_volcano_chain",
    # GEBCO bathy
    "hawaiian_chain_bathy",
    "great_barrier_reef_full",
    "maldives_full_bathy",
    "indonesia_sunda_bathy",
    "galapagos_full_bathy",
]


def is_done(rid: str) -> bool:
    """Quick check: stitched output exists."""
    return (OUTPUT / rid / "height_16.png").exists()


def load_status() -> dict:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_status(status: dict):
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, indent=2), encoding="utf-8")


def pull_one(rid: str, entry: dict) -> dict:
    """Run tile_stitch.py for one entry. Return status dict."""
    bbox = entry["bbox"]
    ds = entry.get("dataset", "COP30")
    rows = entry.get("rows", 3)
    cols = entry.get("cols", 3)
    size = entry.get("size", 4096)
    log_path = LOGS_DIR / f"megastack_{rid}.log"

    cmd = [
        sys.executable, str(TILE_STITCH),
        "--id", rid,
        "--bbox", *[str(v) for v in bbox],
        "--dataset", ds,
        "--rows", str(rows), "--cols", str(cols),
        "--size", str(size),
        "--overlap", "0.002",
    ]
    print(f"\n>>> [{rid}] {ds} {rows}x{cols} bbox={bbox}")
    print(f"    log: {log_path}")
    t0 = time.monotonic()
    try:
        with log_path.open("w", encoding="utf-8") as f:
            rc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT,
                                timeout=2400).returncode
        elapsed = time.monotonic() - t0
        ok = is_done(rid)
        # Count successful tiles by re-checking cache
        log_text = log_path.read_text(encoding="utf-8", errors="ignore")
        ok_tiles = log_text.count("[ok] tile")
        print(f"    {'DONE' if ok else 'INCOMPLETE'}  {ok_tiles}/{rows*cols} tiles  rc={rc}  {elapsed:.0f}s")
        return {
            "status": "DONE" if ok else "INCOMPLETE",
            "tiles_ok": ok_tiles,
            "tiles_expected": rows * cols,
            "elapsed_s": round(elapsed, 1),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "rc": rc,
        }
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - t0
        print(f"    TIMEOUT after {elapsed:.0f}s")
        return {
            "status": "TIMEOUT",
            "elapsed_s": round(elapsed, 1),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }


def main() -> int:
    d = json.loads(WISH.read_text(encoding="utf-8"))
    stitched = {r["id"]: r for r in d["tiers"]["stitched"]["regions"]}
    status = load_status()

    # Skip-list: any entry that is fully DONE (stitched output exists).
    todo = []
    for rid in PRIORITY:
        if rid not in stitched:
            print(f"[skip] {rid} not in wishlist")
            continue
        if is_done(rid):
            status[rid] = {"status": "DONE", "completed_at": "preexisting"}
            continue
        todo.append(rid)

    print(f"\nPlan: {len(todo)} mega-stacks to pull (skipping {len(PRIORITY) - len(todo)} already done)")
    print()

    save_status(status)
    completed = 0
    for i, rid in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {rid}")
        result = pull_one(rid, stitched[rid])
        status[rid] = result
        save_status(status)
        if result.get("status") == "DONE":
            completed += 1

    print(f"\n=== Done: {completed}/{len(todo)} mega-stacks completed ===")

    # Post-hook: refresh world3/data_catalog.json so downstream tools see
    # new mega-stacks. Skip on opt-out env var or zero new completions.
    import os
    if completed > 0 and not os.environ.get("WORLD3_NO_CATALOG_REFRESH"):
        refresh_master_catalog()

    return 0


def refresh_master_catalog() -> None:
    """Call build_master_catalog.py so world3/data_catalog.json reflects
    new mega-stacks. Added 2026-05-11 (Phase D.3)."""
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
