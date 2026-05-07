"""Region pipeline — one command, full DEM-to-Godot flow.

Composes the entire chain from a single OpenTopography preset to a playable
Godot scene with biomes painted, AAA textures bound, water animated, scatter
populated, and three camera modes (walkable/topdown/iso).

Steps (each is its own existing tool, just chained here):
  1. import_dem.py             — pull real DEM from OpenTopography
  2. dem_fantasy_edit.py       — apply --style transformation (optional)
  3. world_biome_engine.py     — paint biomes on top with --base-heightmap
  4. biome_splat.py            — compile RGBA splat
  5. biome_texture_bind.py     — auto-generate any missing AAA texture sets
  6. stage_biome_scatter.py    — emit MultiMeshInstance3D scatter
  7. stage_biome_terrain.py    — emit Godot scenes (--walkable --cameras)

Usage:
  python region_pipeline.py `
    --preset bryce_hoodoo `
    --style spired `
    --strength 1.4 `
    --biomes lava_field,mana_crystal,grassland,grassland `
    --id bryce_v1 `
    --project C:\\Users\\josep\\test\\new-game-project `
    --size 1024 `
    --res 2048 `
    --bathymetry

What you get:
  pipelines/terrain/output/<id>/        (real DEM bundle)
  world/worlds/<id>/                    (biome-painted world + biome_pbr_pack.json)
  <project>/biome_terrain_test/         (3 .tscn files + scatter + collision)

Open <project> in Godot 4.5 and load any of the .tscn files.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(r"D:\assets")
TERRAIN_DIR = REPO / "pipelines" / "terrain"
TEXTURES_DIR = REPO / "pipelines" / "textures"
GODOT_DIR = REPO / "pipelines" / "godot_export"
BIOMES_DIR = REPO / "art_lab" / "biomes" / "tools"


def run(label: str, cmd: list[str]) -> None:
    print(f"\n========== {label} ==========")
    print("  $ " + " ".join(str(c) for c in cmd))
    rc = subprocess.run([sys.executable] + cmd).returncode
    if rc != 0:
        raise SystemExit(f"{label} failed (rc={rc})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", help="OpenTopography preset (e.g. bryce_hoodoo). "
                    "If omitted you must pass --bbox W S E N.")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"))
    ap.add_argument("--dataset", default=None,
                    help="OpenTopography dataset (default: per-preset, else COP30)")
    ap.add_argument("--bathymetry", action="store_true",
                    help="Merge GEBCO seafloor bathymetry under the land DEM")
    ap.add_argument("--style", default="realistic",
                    choices=["realistic", "exaggerated", "terraced", "sharpened",
                             "spired", "floating", "mythic"])
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--biomes", required=True,
                    help="comma-separated biome ids (e.g. lava_field,mana_crystal,grassland,grassland)")
    ap.add_argument("--id", required=True, help="region id used everywhere downstream")
    ap.add_argument("--project", type=Path, required=True,
                    help="target Godot 4.5 project root")
    ap.add_argument("--size", type=int, default=1024,
                    help="final render heightmap resolution")
    ap.add_argument("--res", type=int, default=None,
                    help="source DEM pull resolution (>= --size for high-detail bake)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--quality", default="default",
                    choices=["fast", "default", "strict"])
    ap.add_argument("--max-scatter", type=int, default=800)
    ap.add_argument("--skip-dem", action="store_true",
                    help="Reuse existing pipelines/terrain/output/<id> instead of refetching")
    ap.add_argument("--skip-fantasy", action="store_true",
                    help="Skip the fantasy-edit step even if --style is set")
    ap.add_argument("--splat-mode", default="gaussian",
                    choices=["gaussian", "soft", "hard", "height_blend"],
                    help="biome_splat boundary blend strategy (passed through).")
    ap.add_argument("--shader-preset", default="topdown",
                    choices=["topdown", "triplanar", "hextile", "heightblend"],
                    help="terrain shader preset (passed through to stage_biome_terrain).")
    ap.add_argument("--cam", default="character", choices=["worldview", "character"],
                    help="staged comparison-scene camera framing (default: character).")
    ap.add_argument("--terrain-size-m", type=float, default=None,
                    help="override real-world terrain span (metres); default reads dem_meta.")
    ap.add_argument("--terrain-height-m", type=float, default=None,
                    help="override real-world terrain relief (metres); default 64m.")
    ap.add_argument("--use-real-extents", action="store_true",
                    help="read terrain dimensions from world.json's dem_meta block "
                         "instead of legacy 512m × 64m diorama scale.")
    ap.add_argument("--sea-level", type=float, default=0.32,
                    help="normalized 0..1 cutoff below which biome painter labels "
                         "pixels as ocean. Default 0.32 (fantasy worlds). For real "
                         "DEMs without ocean (e.g. Death Valley), use 0.0 — otherwise "
                         "the basin floor is painted as ocean and renders black.")
    args = ap.parse_args()

    # 1. DEM pull
    dem_dir = TERRAIN_DIR / "output" / args.id
    if not args.skip_dem:
        cmd = [str(TERRAIN_DIR / "import_dem.py"), "--id", args.id, "--source", "opentopo",
               "--size", str(args.size)]
        if args.preset:
            cmd += ["--preset", args.preset]
        elif args.bbox:
            cmd += ["--bbox", *[str(v) for v in args.bbox]]
        else:
            raise SystemExit("Need --preset or --bbox")
        if args.dataset:
            cmd += ["--dataset", args.dataset]
        if args.bathymetry:
            cmd += ["--bathymetry"]
        if args.res:
            cmd += ["--res", str(args.res)]
        run("1. import_dem", cmd)

    height_path = dem_dir / "height_16.png"
    if not height_path.exists():
        raise SystemExit(f"expected {height_path} after import_dem; aborting")

    # 2. Fantasy edit (optional)
    base_for_biomes = height_path
    if args.style != "realistic" and not args.skip_fantasy:
        fantasy_path = dem_dir / f"height_16_fantasy_{args.style}.png"
        run("2. dem_fantasy_edit", [
            str(TERRAIN_DIR / "dem_fantasy_edit.py"),
            "--in", str(height_path), "--out", str(fantasy_path),
            "--style", args.style, "--strength", str(args.strength),
        ])
        base_for_biomes = fantasy_path

    # 3. Biome engine on top of (real or fantasy-edited) DEM
    run("3. world_biome_engine", [
        str(BIOMES_DIR / "world_biome_engine.py"),
        "--id", args.id,
        "--biomes", args.biomes,
        "--base-heightmap", str(base_for_biomes),
        "--size", str(args.size),
        "--seed", str(args.seed),
        "--sea-level", str(args.sea_level),
    ])

    world_dir = REPO / "world" / "worlds" / args.id
    if not (world_dir / "world.json").exists():
        raise SystemExit(f"expected {world_dir}/world.json after biome engine")

    # 4. Splat
    run("4. biome_splat", [
        str(TERRAIN_DIR / "biome_splat.py"), "--world", str(world_dir),
        "--splat-mode", args.splat_mode,
    ])

    # 5. Texture bind (auto-generates any missing AAA sets)
    run("5. biome_texture_bind", [
        str(TEXTURES_DIR / "biome_texture_bind.py"),
        "--world", str(world_dir), "--quality", args.quality,
    ])

    # 6. Scatter
    run("6. stage_biome_scatter", [
        str(GODOT_DIR / "stage_biome_scatter.py"),
        "--world", str(world_dir), "--project", str(args.project),
        "--max-instances", str(args.max_scatter),
    ])

    # 7. Stage the 3 scenes
    stage_cmd = [
        str(GODOT_DIR / "stage_biome_terrain.py"),
        "--world", str(world_dir), "--project", str(args.project),
        "--walkable", "--cameras",
        "--cam", args.cam,
        "--shader-preset", args.shader_preset,
    ]
    if args.terrain_size_m is not None:
        stage_cmd += ["--terrain-size-m", str(args.terrain_size_m)]
    if args.terrain_height_m is not None:
        stage_cmd += ["--terrain-height-m", str(args.terrain_height_m)]
    if args.use_real_extents:
        stage_cmd += ["--use-real-extents"]
    run("7. stage_biome_terrain", stage_cmd)

    print("\n=" * 1, "=" * 70, sep="")
    print(f"region '{args.id}' done.")
    print(f"  DEM:   {dem_dir}")
    print(f"  world: {world_dir}")
    print(f"  Godot: {args.project / 'biome_terrain_test'}")
    print(f"\nOpen {args.project} in Godot 4.5 and load any:")
    print(f"  biome_terrain_{args.id}.tscn         — walkable")
    print(f"  biome_{args.id}_topdown.tscn         — top-down 2D")
    print(f"  biome_{args.id}_iso.tscn             — 2.5D iso")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
