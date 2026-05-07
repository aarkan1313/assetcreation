# Worldgen v2

Clean ground-up rebuild of the world generator. Modeled on `meshy/batch_pipeline.py`.

Spec: [`docs/superpowers/specs/2026-05-06-worldgen-v2-design.md`](../../docs/superpowers/specs/2026-05-06-worldgen-v2-design.md)
Plan: [`docs/superpowers/plans/2026-05-06-worldgen-v2.md`](../../docs/superpowers/plans/2026-05-06-worldgen-v2.md)

## Quickstart

```powershell
# 1. Pre-flight (every shell)
$env:OPENTOPOGRAPHY_API_KEY = [Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY","User")
$env:PYTHONIOENCODING = "utf-8"

# 2. Run a job
python -m pipelines.worldgen_v2.batch_pipeline pipelines/worldgen_v2/jobs/death_valley.json

# 3. Open the scene
# Godot 4.5 -> open D:/assets/worldgen2/project.godot -> open scenes/death_valley_character.tscn -> F5
```

## Pipeline stages

1. `fetch_dem` — pull a GeoTIFF from OpenTopography, resample to quality preset, write `height_16.png` + `dem_meta.json`.
2. `edit_dem` — fantasy/style pass (milestone 1: `realistic` only).
3. `paint_biomes` — height/slope rule -> 4-biome mask PNG.
4. `compile_splat` — mask -> RGBA one-hot splat.
5. `bind_textures` — generate 4 procedural placeholder albedos + `pbr_pack.json`.
6. `stage_godot` — copy textures + write `material.tres`, `collision.tres`, `<id>_<cam>.tscn`.

## Quality presets

- `draft` — 1024 DEM / 256 mesh subdiv / 128 collision (fast iteration).
- `good` — 2048 / 512 / 256 (default).
- `max` — 4096 / 1024 / 512 (marquee scenes).

## Re-running a single stage

Each stage is idempotent and reads only from disk. To re-run just the material:

```powershell
python -c "from pipelines.worldgen_v2 import batch_pipeline; from pipelines.worldgen_v2.godot_writers import material_tres; from pathlib import Path; job = batch_pipeline.load_job(Path('pipelines/worldgen_v2/jobs/death_valley.json')); material_tres.write(job, Path('D:/assets/worldgen2'))"
```

Same pattern for `collision_tres`, `scene_tscn`, `heightmap_image`. If textures regress, you only re-run that one writer instead of the whole pipeline.

## Tests

```powershell
cd D:/assets/tests/worldgen_v2
python -m pytest . -v
```

45 unit tests, ~1 second.

## What's NOT in milestone 1

Scatter / props, real PBR sets (placeholders only), 2D and iso renderers, procedural FastNoise terrain, multi-DEM stitching, hand-edited overrides. See spec for the deferred list.
