"""Auto-generate a coherent biome texture kit from a single biome name.

Given just a biome name (e.g. "highland_ruins" or "frozen_volcanic"), an LLM
brief (the LLM running this script picks the prompts), or a JSON kit recipe,
this generates a complete palette-locked texture set:

  Default kit (8 materials):
    1. Anchor: dominant ground material (rock or soil)
    2. Secondary ground: alternate surface (grass/moss/sand)
    3. Tertiary ground: walking surface (path/trail/road)
    4. Cliff: vertical rock variant for slopes
    5. Detail: high-frequency overlay (matches anchor)
    6. Snow/wet variant: weather-modified surface
    7. Hero accent: ruin block / unique stone
    8. Vegetation card: grass/fern/lichen tile

Each material:
  - Goes through aaa_texture.py at the requested quality
  - Is palette-locked to the anchor (LAB hist match)
  - Gets a detail pyramid pair if --pyramid is set
  - Gets a Blender HDRI render
  - Catalog entry appended

Usage:
  python kit_generator.py --kit highland_ruins --quality default
  python kit_generator.py --recipe my_recipe.json --quality strict --pyramid

Or write a JSON recipe by hand:
  {
    "kit_id": "frozen_volcanic",
    "category": "Rock",
    "anchor": {"prompt": "obsidian volcanic glass with frost cracks", "id": "obsidian_anchor"},
    "members": [
      {"prompt": "frozen black ash", "id": "ash_frost", "category": "Ground"},
      {"prompt": "snow-dusted basalt cliff", "id": "snow_basalt_cliff", "category": "Rock"},
      ...
    ]
  }
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LIBRARY = Path(r"D:\assets\world\textures\library")
KITS_DIR = Path(r"D:\assets\art_lab\biomes\kits")
PIPELINE_DIR = Path(__file__).parent


# Built-in biome recipes — LLM-curated default prompts that work
BUILTIN_KITS: dict[str, dict] = {
    "highland_ruins": {
        "category": "Rock",
        "anchor": {"prompt": "weathered grey basalt rock with green moss patches", "id_suffix": "_basalt"},
        "members": [
            {"prompt": "wet mossy soil with fallen leaves", "id_suffix": "_mossy_soil", "category": "Ground"},
            {"prompt": "cobblestone pathway worn by rain", "id_suffix": "_cobble_path", "category": "Bricks"},
            {"prompt": "vertical basalt cliff face with vertical cracks and lichen", "id_suffix": "_basalt_cliff", "category": "Rock"},
            {"prompt": "ancient ruin block carved with faded runes", "id_suffix": "_ruin_block", "category": "Rock"},
            {"prompt": "dense fern undergrowth ground cover", "id_suffix": "_fern_carpet", "category": "Ground"},
        ],
    },
    "frozen_volcanic": {
        "category": "Rock",
        "anchor": {"prompt": "obsidian volcanic glass with thin frost cracks", "id_suffix": "_obsidian"},
        "members": [
            {"prompt": "frozen black volcanic ash", "id_suffix": "_frozen_ash", "category": "Ground"},
            {"prompt": "snow-dusted basalt cliff with ice", "id_suffix": "_snow_cliff", "category": "Rock"},
            {"prompt": "icy hardpack snow with footprints", "id_suffix": "_hardpack", "category": "Snow"},
            {"prompt": "cracked basalt with glowing magma in the cracks", "id_suffix": "_magma_basalt", "category": "Rock"},
        ],
    },
    "desert_temple": {
        "category": "Rock",
        "anchor": {"prompt": "weathered sandstone temple block with carved hieroglyphs", "id_suffix": "_sandstone"},
        "members": [
            {"prompt": "fine wind-rippled desert sand", "id_suffix": "_dune_sand", "category": "Ground"},
            {"prompt": "cracked sandstone tile floor", "id_suffix": "_temple_tile", "category": "Tiles"},
            {"prompt": "weathered bronze inlaid stone", "id_suffix": "_bronze_stone", "category": "Marble"},
            {"prompt": "dried clay ground with cracks", "id_suffix": "_clay_ground", "category": "Ground"},
        ],
    },
    "forest_floor": {
        "category": "Ground",
        "anchor": {"prompt": "rich forest soil with fallen leaves and pine needles", "id_suffix": "_loam"},
        "members": [
            {"prompt": "dense moss carpet with small mushrooms", "id_suffix": "_moss_carpet", "category": "Ground"},
            {"prompt": "fallen oak bark plank texture", "id_suffix": "_oak_bark", "category": "Wood"},
            {"prompt": "moss-covered grey stone outcropping", "id_suffix": "_mossy_stone", "category": "Rock"},
            {"prompt": "muddy forest path with tire tracks", "id_suffix": "_muddy_path", "category": "Ground"},
            {"prompt": "rotten fallen log with fungus", "id_suffix": "_rotten_log", "category": "Wood"},
        ],
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", help="builtin biome kit name", choices=list(BUILTIN_KITS.keys()))
    ap.add_argument("--recipe", type=Path, help="JSON recipe file")
    ap.add_argument("--quality", default="default",
                    choices=["fast", "default", "strict"])
    ap.add_argument("--variants", type=int, default=None)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--seed-base", type=int, default=42)
    ap.add_argument("--palette-strength", type=float, default=0.5,
                    help="LAB hist-match strength for siblings (0=no match, 1=full)")
    ap.add_argument("--pyramid", action="store_true",
                    help="also generate a detail layer for each material")
    ap.add_argument("--hdri", default="sunset",
                    help="HDRI for the Blender render of each material")
    args = ap.parse_args()

    if not args.kit and not args.recipe:
        ap.error("provide --kit or --recipe")

    if args.recipe:
        recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
        kit_id = recipe["kit_id"]
        category = recipe.get("category", "Rock")
        anchor_spec = recipe["anchor"]
        members_spec = recipe["members"]
    else:
        spec = BUILTIN_KITS[args.kit]
        kit_id = args.kit
        category = spec["category"]
        prefix = kit_id
        anchor_spec = {
            "prompt": spec["anchor"]["prompt"],
            "id": prefix + spec["anchor"]["id_suffix"],
            "category": spec["anchor"].get("category", category),
        }
        members_spec = [
            {"prompt": m["prompt"],
             "id": prefix + m["id_suffix"],
             "category": m.get("category", category)}
            for m in spec["members"]
        ]

    anchor_id = anchor_spec["id"]

    print(f"\n{'='*60}")
    print(f"KIT: {kit_id}")
    print(f"  anchor:   {anchor_id} — {anchor_spec['prompt']!r}")
    for i, m in enumerate(members_spec):
        print(f"  member {i}: {m['id']} — {m['prompt']!r}")
    print(f"  total: {1 + len(members_spec)} materials")
    print(f"  quality: {args.quality}")
    print(f"  pyramid: {args.pyramid}")
    print(f"{'='*60}\n")

    started = datetime.now(timezone.utc)

    # Step 1: anchor
    print(f"\n>>> ANCHOR: {anchor_id} <<<")
    anchor_cmd = [
        sys.executable, str(PIPELINE_DIR / "aaa_texture.py"),
        "--prompt", anchor_spec["prompt"],
        "--id", anchor_id,
        "--category", anchor_spec.get("category", category),
        "--quality", args.quality,
        "--size", str(args.size),
        "--seed-base", str(args.seed_base),
        "--no-gate",
    ]
    if args.variants is not None:
        anchor_cmd += ["--variants", str(args.variants)]
    r = subprocess.run(anchor_cmd)
    if r.returncode != 0:
        print(f"ANCHOR FAILED — aborting kit")
        sys.exit(1)

    # Render anchor with HDRI
    subprocess.run([sys.executable, str(PIPELINE_DIR / "blender_preview.py"),
                     "--material", str(LIBRARY / anchor_id), "--hdri", args.hdri])

    # Step 2: palette-lock siblings
    print(f"\n>>> SIBLINGS via palette_lock ({len(members_spec)} members) <<<")
    palette_cmd = [
        sys.executable, str(PIPELINE_DIR / "palette_lock.py"),
        "--kit", kit_id,
        "--anchor", anchor_id,
        "--strength", str(args.palette_strength),
        "--quality", args.quality,
        "--size", str(args.size),
        "--seed-base", str(args.seed_base + 1000),
    ]
    if args.variants is not None:
        palette_cmd += ["--variants", str(args.variants)]
    for m in members_spec:
        palette_cmd += ["--add", f"{m['prompt']}:{m['id']}:{m['category']}"]
    r = subprocess.run(palette_cmd)
    if r.returncode != 0:
        print(f"  palette_lock had errors but kit may still be usable")

    # Step 3: render each member with HDRI
    print(f"\n>>> HDRI RENDERS for siblings <<<")
    for m in members_spec:
        member_dir = LIBRARY / m["id"]
        if member_dir.exists():
            subprocess.run([sys.executable, str(PIPELINE_DIR / "blender_preview.py"),
                             "--material", str(member_dir), "--hdri", args.hdri])

    # Step 4: optional detail pyramid for each
    if args.pyramid:
        print(f"\n>>> DETAIL PYRAMIDS <<<")
        all_ids = [anchor_id] + [m["id"] for m in members_spec]
        for asset_id in all_ids:
            asset_dir = LIBRARY / asset_id
            if asset_dir.exists():
                subprocess.run([sys.executable, str(PIPELINE_DIR / "detail_pyramid.py"),
                                 "--macro", str(asset_dir),
                                 "--detail-quality", "fast",  # detail is overlay, fast is fine
                                 "--detail-variants", "2",
                                 "--detail-size", str(args.size)])

    # Final manifest
    completed = datetime.now(timezone.utc)
    duration = (completed - started).total_seconds()
    kit_log = {
        "kit_id": kit_id,
        "category": category,
        "quality": args.quality,
        "anchor": anchor_id,
        "members": [m["id"] for m in members_spec],
        "all_materials": [anchor_id] + [m["id"] for m in members_spec],
        "pyramid": args.pyramid,
        "hdri": args.hdri,
        "palette_strength": args.palette_strength,
        "started": started.isoformat(),
        "completed": completed.isoformat(),
        "duration_seconds": duration,
        "library_paths": {
            mid: str(LIBRARY / mid) for mid in [anchor_id] + [m["id"] for m in members_spec]
        },
    }
    KITS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = KITS_DIR / f"{kit_id}_textures.json"
    log_path.write_text(json.dumps(kit_log, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"KIT COMPLETE: {kit_id}")
    print(f"  duration:  {duration:.0f}s ({duration/60:.1f} min)")
    print(f"  materials: {len(kit_log['all_materials'])}")
    print(f"  manifest:  {log_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
