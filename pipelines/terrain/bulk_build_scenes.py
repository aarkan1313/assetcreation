"""Build Godot scenes for every cached region across all wishlist tiers.

Reads art_lab/biomes/data_wishlist.json (and optionally
data_wishlist_mystery.json), finds regions that already have a processed
height_16.png in pipelines/terrain/output/<id>/, then runs region_pipeline.py
--skip-dem for each, picking a fantasy style + biome quartet based on the
region's tags.

Available biomes (Phase B + C): grassland, mana_crystal, lava_field, ice_cavern,
forest, desert, tundra, swamp, charred_wasteland, underwater.

Usage:
  python pipelines/terrain/bulk_build_scenes.py --project <godot> --tier all
  python pipelines/terrain/bulk_build_scenes.py --project <godot> --tier bathymetric
  python pipelines/terrain/bulk_build_scenes.py --project <godot> --include-mystery
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TERRAIN_DIR = REPO / "pipelines" / "terrain"
WISHLIST = REPO / "art_lab" / "biomes" / "data_wishlist.json"
WISHLIST_MYSTERY = REPO / "art_lab" / "biomes" / "data_wishlist_mystery.json"


def biome_quartet_for(tags: list[str], tier: str = "") -> tuple[str, ...]:
    """Pick a 4-biome layout from tags. Phase C biomes available."""
    t = set(tags)
    # Bathymetric / submerged: underwater is the marquee biome
    if tier == "bathymetric" or t & {"submerged", "below-sea", "reef"}:
        return ("underwater", "swamp", "grassland", "forest")
    if t & {"volcano", "active-lava", "fresh-eruption", "lahar"}:
        return ("lava_field", "charred_wasteland", "grassland", "mana_crystal")
    if t & {"caldera", "salt-flat"}:
        return ("ice_cavern", "tundra", "grassland", "mana_crystal")
    if t & {"alpine", "high-altitude", "glacier", "icefield", "polar-glacier"}:
        return ("ice_cavern", "tundra", "grassland", "mana_crystal")
    if t & {"arctic", "tundra", "permafrost", "polar"}:
        return ("tundra", "ice_cavern", "swamp", "grassland")
    if t & {"dune", "gypsum", "sand", "arid"}:
        return ("desert", "charred_wasteland", "grassland", "mana_crystal")
    if t & {"rainforest", "wetland", "delta", "marsh"}:
        return ("forest", "swamp", "grassland", "underwater")
    if t & {"red-rock", "mesa", "pinnacle", "spire", "monolith", "volcanic-plug",
            "amphitheater", "fin", "arch", "spire-monolith"}:
        return ("desert", "mana_crystal", "grassland", "charred_wasteland")
    if t & {"canyon", "vertical-mile", "slot-canyon", "karst", "cave-country"}:
        return ("desert", "mana_crystal", "lava_field", "grassland")
    if t & {"forest", "temperate", "rolling"}:
        return ("forest", "grassland", "swamp", "mana_crystal")
    # Default mix that covers most procedural unknowns
    return ("forest", "grassland", "ice_cavern", "mana_crystal")


def style_for(fantasy_styles: list[str], tags: list[str]) -> tuple[str, float]:
    """Pick (style, strength). Prefer first fantasy_styles entry; tune strength."""
    style = (fantasy_styles or ["mythic"])[0]
    # Stronger pushes for already-dramatic terrain
    if set(tags) & {"pinnacle", "spire", "monolith", "volcanic-plug",
                    "amphitheater", "spire-monolith"}:
        return style, 1.5
    if set(tags) & {"alpine", "glacier", "high-altitude"}:
        return style, 1.3
    return style, 1.2


def run_region(region_id: str, style: str, strength: float, biomes: tuple[str, ...],
               project: Path, size: int) -> int:
    cmd = [
        sys.executable,
        str(TERRAIN_DIR / "region_pipeline.py"),
        "--id", region_id,
        "--style", style,
        "--strength", str(strength),
        "--biomes", ",".join(biomes),
        "--project", str(project),
        "--size", str(size),
        "--skip-dem",
    ]
    print(f"\n=== {region_id} | style={style} strength={strength} biomes={biomes} ===")
    print(" ", " ".join(cmd))
    proc = subprocess.run(cmd)
    return proc.returncode


def collect_regions(tier_filter: set[str], include_mystery: bool) -> list[tuple[dict, str]]:
    """Return [(region_dict, tier_name), ...] across selected wishlists/tiers."""
    out = []
    wishlist = json.loads(WISHLIST.read_text(encoding="utf-8"))
    for tier_name, tier_data in wishlist["tiers"].items():
        if not isinstance(tier_data, dict) or "regions" not in tier_data:
            continue
        if tier_filter and tier_name not in tier_filter:
            continue
        for r in tier_data["regions"]:
            out.append((r, tier_name))

    if include_mystery and WISHLIST_MYSTERY.exists():
        mystery = json.loads(WISHLIST_MYSTERY.read_text(encoding="utf-8"))
        # mystery file uses flat 'regions' shape, not nested under 'tiers'
        regions = mystery.get("regions", [])
        for r in regions:
            out.append((r, "mystery"))

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--only", default="",
                    help="comma-separated subset of region ids")
    ap.add_argument("--skip", default="",
                    help="comma-separated region ids to skip")
    ap.add_argument("--tier", default="showcase",
                    help='which tier(s) to build. Comma-separated, or "all". '
                         'Choices: showcase, premium, standard, bathymetric, '
                         'stitched, highres_open, all.')
    ap.add_argument("--include-mystery", action="store_true",
                    help="also build cached regions from data_wishlist_mystery.json")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap total scenes built")
    ap.add_argument("--cam", choices=["worldview", "character"], default="character",
                    help="camera framing for the staged ortho scenes (default: character)")
    args = ap.parse_args()

    skip = set(s.strip() for s in args.skip.split(",") if s.strip())
    only = set(s.strip() for s in args.only.split(",") if s.strip()) if args.only else None
    if args.tier.lower() == "all":
        tier_filter = set()  # no filter
    else:
        tier_filter = set(t.strip() for t in args.tier.split(",") if t.strip())

    candidates = collect_regions(tier_filter, args.include_mystery)
    print(f"considering {len(candidates)} regions across tiers: "
          f"{tier_filter or 'all'}{' + mystery' if args.include_mystery else ''}")

    # Filter to regions that have processed height_16.png on disk.
    targets: list[tuple[dict, str]] = []
    for r, tier_name in candidates:
        rid = r["id"]
        if only and rid not in only:
            continue
        if rid in skip:
            continue
        height = TERRAIN_DIR / "output" / rid / "height_16.png"
        if not height.exists():
            continue
        # Skip if already-staged scene exists (no need to rebuild unless --only).
        staged = (args.project / "biome_terrain_test" /
                  f"biome_terrain_{rid}.tscn")
        if staged.exists() and not only:
            continue
        targets.append((r, tier_name))

    if args.limit:
        targets = targets[: args.limit]

    print(f"\nbuilding {len(targets)} regions:")
    for r, tn in targets[:20]:
        print(f"  - [{tn:>12}] {r['id']}")
    if len(targets) > 20:
        print(f"  ... +{len(targets) - 20} more")

    successes: list[str] = []
    failures: list[str] = []
    for r, tier_name in targets:
        style, strength = style_for(r.get("fantasy_styles", []), r.get("tags", []))
        biomes = biome_quartet_for(r.get("tags", []), tier=tier_name)
        rc = run_region(r["id"], style, strength, biomes, args.project, args.size)
        if rc == 0:
            successes.append(r["id"])
        else:
            failures.append(r["id"])

    print(f"\n=== bulk build done: {len(successes)} ok, {len(failures)} failed ===")
    for s in successes:
        print(f"  ok  {s}")
    for f in failures:
        print(f"  FAIL {f}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
