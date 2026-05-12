"""Index the OpenTopography heightmap bundles into a region catalog.

Walks `world3/opentopo/processed/heightmaps/<site>/<dataset>/` looking for
bundles that have both `heightmap.png` and `meta.json`. Emits
`world3/jobs/regions.json` with one entry per (site, dataset) pair, plus
a per-site "preferred dataset" pick (default = first valid in priority
order: COP30 > NASADEM > SRTMGL1 > whatever).

The catalog is what the Godot region-picker scene reads.

Usage:
    python world3/pipeline/index_regions.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\assets\world3")
HEIGHTMAPS_ROOT = ROOT / "opentopo" / "processed" / "heightmaps"
JOBS_DIR = ROOT / "jobs"
BIOME_KITS_JSON = JOBS_DIR / "biome_kits.json"

# Priority for picking the "preferred" dataset per site.
DATASET_PRIORITY = ("COP30", "NASADEM", "SRTMGL1", "AW3D30",
                    "CA_MRDEM_DTM", "CA_MRDEM_DSM",
                    "SRTM15Plus", "GEBCOIceTopo",
                    "GEDI_L3_ELEV", "GEDI_L3_RH100", "USGS10m", "USGS1m")

# Best-effort landform tags. "biome" prefix codes used in the OpenTopo plan:
#   tcf=temperate conifer forest, bor=boreal, mgs=mountain grassland,
#   tgs=tropical grassland savanna, des=desert, fgs=flooded grassland,
#   man=mangrove, med=mediterranean, tbm=temperate broadleaf mixed,
#   tdf=tropical dry forest, tgr=temperate grassland, tmf=tropical
#   moist forest, tun=tundra
LANDFORM_HINTS = {
    "tcf_pnw_cascades_usa": "alpine",
    "tcf_bc_coast_canada": "fjord",
    "tcf_sierra_madre_mexico": "mountain",
    "bor_alaska_interior": "boreal_plain",
    "bor_yukon_canada": "boreal_basin",
    "des_mojave_usa": "desert",
    "fgs_pantanal_brazil": "flooded_basin",
    "man_sundarbans": "delta_coast",
    "med_california_chaparral": "mediterranean_hills",
    "mgs_tibetan_plateau": "high_plateau",
    "tbm_appalachians_usa": "rolling_mountain",
    "tdf_yucatan_mexico": "karst_lowland",
    "tgr_great_plains_usa": "grassland_plain",
    "tgs_serengeti_tanzania": "savanna",
    "tmf_amazon_brazil": "lowland_jungle",
    "tun_arctic_alaska": "tundra",
    "guadalupe_cypress_dtm_2016": "coastal_island",
}

# Default biome kit per landform tag. These reference texture-set IDs
# under world3/textures/wgv3/. (Currently we only have one biome kit
# fully staged; this gets richer as we generate more.)
DEFAULT_BIOME_KIT = {
    "grass": "grass",
    "dirt": "dirt",
    "rock_light": "rock_light",
    "rock_dark": "rock_dark",
    "snow": "snow",
}


def discover_bundles(root: Path) -> list[dict]:
    bundles = []
    if not root.is_dir():
        return bundles
    for site_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for ds_dir in sorted(p for p in site_dir.iterdir() if p.is_dir()):
            hp = ds_dir / "heightmap.png"
            mp = ds_dir / "meta.json"
            if not (hp.exists() and mp.exists()):
                continue
            try:
                meta = json.loads(mp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            # Skip degenerate (all-nodata) bundles. The other chat's STATUS
            # noted some NASADEM/SRTM coverage gaps in arctic latitudes.
            erange = float(meta.get("elevation_range_m", 0.0))
            if erange < 1.0:
                continue
            bundles.append({
                "site": site_dir.name,
                "dataset": ds_dir.name,
                "heightmap_path": str(hp).replace("\\", "/"),
                "meta_path": str(mp).replace("\\", "/"),
                "elevation_min_m": meta.get("elevation_min_m"),
                "elevation_max_m": meta.get("elevation_max_m"),
                "elevation_range_m": erange,
                "world_size_m": meta.get("world_size_m"),
                "source_crs": meta.get("source_crs"),
                "source_bounds": meta.get("source_bounds"),
            })
    return bundles


def choose_preferred(bundles_for_site: list[dict]) -> str:
    """Return the dataset name the picker should default to."""
    by_ds = {b["dataset"]: b for b in bundles_for_site}
    for cand in DATASET_PRIORITY:
        # Match either exact or with "_COG" suffix.
        for key in (cand, cand + "_COG"):
            if key in by_ds:
                return key
    # fallback: first dataset alphabetically
    return sorted(by_ds.keys())[0]


def load_region_to_kit() -> tuple[dict[str, str], str]:
    """Read biome_kits.json and return {region_id: kit_name} + default_kit."""
    if not BIOME_KITS_JSON.exists():
        return {}, "alpine"
    data = json.loads(BIOME_KITS_JSON.read_text(encoding="utf-8"))
    default_kit = data.get("default_kit", "alpine")
    region_to_kit: dict[str, str] = {}
    for kit_name, kit in (data.get("kits") or {}).items():
        for region_id in (kit.get("regions") or []):
            region_to_kit[region_id] = kit_name
    return region_to_kit, default_kit


def main():
    bundles = discover_bundles(HEIGHTMAPS_ROOT)
    if not bundles:
        print(f"no heightmap bundles found under {HEIGHTMAPS_ROOT}")
        return

    region_to_kit, default_kit = load_region_to_kit()

    by_site: dict[str, list[dict]] = {}
    for b in bundles:
        by_site.setdefault(b["site"], []).append(b)

    regions = []
    for site, site_bundles in sorted(by_site.items()):
        preferred = choose_preferred(site_bundles)
        kit_name = region_to_kit.get(site, default_kit)
        regions.append({
            "id": site,
            "landform": LANDFORM_HINTS.get(site, "unknown"),
            "biome_kit": kit_name,
            "biome_kit_material": f"res://textures/wgv3/terrain_blend_{kit_name}.tres",
            "preferred_dataset": preferred,
            "datasets": [b["dataset"] for b in site_bundles],
            "bundles": site_bundles,
        })

    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    out = JOBS_DIR / "regions.json"
    out.write_text(json.dumps(regions, indent=2), encoding="utf-8")
    print(f"wrote {len(regions)} regions ({len(bundles)} total bundles) -> {out}")
    for r in regions:
        print(f"  {r['id']:35s} ({r['landform']:18s}) "
              f"kit={r['biome_kit']:18s} "
              f"-> {r['preferred_dataset']:12s} ({len(r['datasets'])} datasets)")


if __name__ == "__main__":
    main()
