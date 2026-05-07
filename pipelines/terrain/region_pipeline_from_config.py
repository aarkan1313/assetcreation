"""Run region_pipeline.py from a per-region JSON config file.

Per the character-pipeline pattern (`meshy/batch_pipeline.py`), we want
swap-able tools at every layer driven by a declarative config. A single JSON
per region captures the full set of choices that go into building a Godot
scene. Multiple regions can be batched.

Schema (region.config.v1):
{
  "id": "death_valley_basin",                 # unique region identifier
  "source": {                                 # DEM source
    "kind": "opentopo" | "stitch" | "stac" | "synthetic",
    "preset": "bryce_hoodoo" | null,          # for kind=opentopo only
    "bbox":   [W, S, E, N] | null,
    "dataset": "USGS10m" | "COP30" | ...,     # see import_dem.DATASETS
    "bathymetry": false,                      # merge GEBCO seafloor under land
    "skip_dem": true                          # reuse existing output/<id>/
  },
  "style":   { "name": "mythic", "strength": 1.3 },   # dem_fantasy_edit
  "biomes":  ["forest", "grassland", ...],            # 4-tuple, in splat-channel order
  "splat":   { "mode": "gaussian" | "soft" | "hard" | "height_blend" },
  "shader":  {
      "preset": "topdown" | "triplanar" | "hextile" | "heightblend",
      "triplanar": null | float                       # override preset's triplanar_strength
  },
  "terrain": {
      "size_m": null | float,                         # override real-world span
      "height_m": null | float,                       # override real-world relief
      "mesh_subdiv": 256                              # 256 = 2m/quad, 512 = 1m/quad
  },
  "scatter": { "max_instances": 800 },
  "stage":   { "cam": "character" | "worldview", "walkable": true },
  "size": 1024,                                       # internal pipeline grid resolution
  "seed": 7,
  "project": "C:\\Users\\josep\\test\\new-game-project",
  "quality": "default" | "fast" | "strict"
}

Usage:
  # Single region:
  python region_pipeline_from_config.py --config art_lab/biomes/regions/death_valley.region.json

  # Batch:
  python region_pipeline_from_config.py --batch art_lab/biomes/regions/*.region.json

  # Generate a fresh template:
  python region_pipeline_from_config.py --template <id> > my_region.region.json
"""
from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r"D:\assets")
TERRAIN_DIR = REPO / "pipelines" / "terrain"
PROJECT_DEFAULT = r"C:\Users\josep\test\new-game-project"
SCHEMA_VERSION = 1


def template_for(region_id: str) -> dict:
    """Return a fresh region.config.v1 template populated with sensible defaults."""
    return {
        "_schema": "region.config.v1",
        "id": region_id,
        "source": {
            "kind": "opentopo",
            "preset": None,
            "bbox": None,
            "dataset": "COP30",
            "bathymetry": False,
            "skip_dem": False,
        },
        "style": {"name": "mythic", "strength": 1.3},
        "biomes": ["forest", "grassland", "mana_crystal", "ice_cavern"],
        "splat": {"mode": "gaussian"},
        "shader": {"preset": "topdown", "triplanar": None},
        "terrain": {"size_m": None, "height_m": None, "mesh_subdiv": 256},
        "scatter": {"max_instances": 800},
        "stage": {"cam": "character", "walkable": True},
        "size": 1024,
        "seed": 7,
        "project": PROJECT_DEFAULT,
        "quality": "default",
    }


def validate(cfg: dict) -> list[str]:
    """Return list of validation errors (empty list = valid)."""
    errors: list[str] = []
    if cfg.get("_schema") not in (None, "region.config.v1", f"region.config.v{SCHEMA_VERSION}"):
        errors.append(f"unknown _schema: {cfg.get('_schema')}")
    if not cfg.get("id") or not isinstance(cfg["id"], str):
        errors.append("'id' is required and must be a string")
    src = cfg.get("source") or {}
    if src.get("kind") not in ("opentopo", "stitch", "stac", "synthetic"):
        errors.append(f"source.kind must be one of opentopo/stitch/stac/synthetic; got {src.get('kind')!r}")
    if src.get("kind") == "opentopo" and not src.get("preset") and not src.get("bbox") and not src.get("skip_dem"):
        errors.append("source.kind=opentopo requires preset, bbox, or skip_dem=true")
    biomes = cfg.get("biomes") or []
    if len(biomes) != 4:
        errors.append(f"biomes must be a 4-tuple in splat-channel order (RGBA); got {len(biomes)}")
    splat = (cfg.get("splat") or {}).get("mode", "gaussian")
    if splat not in ("gaussian", "soft", "hard", "height_blend"):
        errors.append(f"splat.mode must be one of gaussian/soft/hard/height_blend; got {splat!r}")
    sh = (cfg.get("shader") or {}).get("preset", "topdown")
    if sh not in ("topdown", "triplanar", "hextile", "heightblend"):
        errors.append(f"shader.preset must be one of topdown/triplanar/hextile/heightblend; got {sh!r}")
    cam = (cfg.get("stage") or {}).get("cam", "character")
    if cam not in ("worldview", "character"):
        errors.append(f"stage.cam must be worldview or character; got {cam!r}")
    return errors


def build_argv(cfg: dict) -> list[str]:
    """Translate config to region_pipeline.py CLI args."""
    src = cfg.get("source") or {}
    style = cfg.get("style") or {}
    splat = cfg.get("splat") or {}
    shader = cfg.get("shader") or {}
    terrain = cfg.get("terrain") or {}
    scatter = cfg.get("scatter") or {}
    stage = cfg.get("stage") or {}

    argv = [
        sys.executable,
        str(TERRAIN_DIR / "region_pipeline.py"),
        "--id", cfg["id"],
        "--biomes", ",".join(cfg["biomes"]),
        "--project", str(cfg.get("project", PROJECT_DEFAULT)),
        "--size", str(cfg.get("size", 1024)),
        "--seed", str(cfg.get("seed", 7)),
        "--quality", cfg.get("quality", "default"),
        "--style", style.get("name", "mythic"),
        "--strength", str(style.get("strength", 1.0)),
        "--splat-mode", splat.get("mode", "gaussian"),
        "--shader-preset", shader.get("preset", "topdown"),
        "--cam", stage.get("cam", "character"),
        "--max-scatter", str(scatter.get("max_instances", 800)),
    ]
    if src.get("preset"):
        argv += ["--preset", src["preset"]]
    if src.get("bbox"):
        argv += ["--bbox", *[str(v) for v in src["bbox"]]]
    if src.get("dataset"):
        argv += ["--dataset", src["dataset"]]
    if src.get("bathymetry"):
        argv += ["--bathymetry"]
    if src.get("skip_dem"):
        argv += ["--skip-dem"]
    if terrain.get("size_m") is not None:
        argv += ["--terrain-size-m", str(terrain["size_m"])]
    if terrain.get("height_m") is not None:
        argv += ["--terrain-height-m", str(terrain["height_m"])]
    if terrain.get("use_real_extents"):
        argv += ["--use-real-extents"]
    return argv


def run_one(cfg_path: Path, dry_run: bool) -> int:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    errs = validate(cfg)
    if errs:
        print(f"[INVALID] {cfg_path}")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"\n========== {cfg_path.name} | id={cfg['id']} ==========")
    argv = build_argv(cfg)
    print("  $ " + " ".join(argv[1:]))
    if dry_run:
        return 0
    rc = subprocess.run(argv).returncode
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--config", type=Path, help="single region config JSON")
    g.add_argument("--batch", nargs="+", help="glob(s) of region config JSONs to run sequentially")
    g.add_argument("--template", help="emit a fresh template for the given id to stdout")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the resolved CLI for each config without running")
    args = ap.parse_args()

    if args.template:
        json.dump(template_for(args.template), sys.stdout, indent=2)
        print()
        return 0

    if args.config:
        return run_one(args.config, args.dry_run)

    # Batch mode: expand globs, validate all, then run.
    paths: list[Path] = []
    for pattern in args.batch:
        for p in glob.glob(pattern):
            paths.append(Path(p))
    if not paths:
        print(f"no configs matched: {args.batch}")
        return 1
    print(f"batch: {len(paths)} regions")
    failures = []
    for p in sorted(paths):
        rc = run_one(p, args.dry_run)
        if rc != 0:
            failures.append(p.name)
    print(f"\n=== batch done: {len(paths) - len(failures)}/{len(paths)} ok ===")
    if failures:
        for f in failures:
            print(f"  FAIL {f}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
