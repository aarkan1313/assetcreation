# Worldgen v2 — Design Spec

**Date:** 2026-05-06
**Status:** Draft, awaiting user review
**Owner:** worldgen lane
**Supersedes:** `pipelines/terrain/` (v1, retained read-only for reference)

---

## Goal

Rebuild the world-generation pipeline from the ground up at `pipelines/worldgen_v2/`, outputting to a fresh Godot 4.5 project at `D:/assets/worldgen2/`. v1 became unrecoverable (cascading regressions, no git history). v2 is a clean codebase modeled on `meshy/batch_pipeline.py`'s swappable-tools pattern.

**Immediate target:** one OpenTopography DEM → one good-looking, walkable Godot 3D scene. No v1 code is reused. No backward compatibility.

**One thing kept from v1:** the OpenTopography API surface knowledge (auth via `OPENTOPOGRAPHY_API_KEY` env var, dataset identifiers like `COP30` / `SRTMGL1` / `AW3D30` / `USGS1m` / `GEBCO`, bbox call format, OT+ Pro tier capabilities). v2 writes a fresh client; it just doesn't need to re-derive what we already know about the API.

**Long-term target (out of scope for this spec):** procedural open world with handcrafted DEM zones; multi-output (true 2D / iso / 3D) from one canonical world representation.

## Non-goals (v2 first cut)

- Procedural FastNoise terrain. DEM-driven only for now.
- Multi-DEM stitching. One DEM = one world.
- Streamed open-world chunks. Single mesh, no LOD.
- Scatter / props. Build chat G's lane; v2 leaves an empty scatter slot.
- 2D and isometric *renderers*. Camera presets exist (iso/topdown/character/worldview) but the only output format is a 3D Godot scene.
- Hand-edited heightmap overrides.
- Ports of v1 features that aren't on this list.

## Design constraints (lessons from v1)

1. **One writer, one file.** v1's `stage_biome_terrain.py` wrote .tscn + .tres + collision + cameras in one function; when something regressed, you couldn't isolate which output broke. v2 splits writers so each can be re-run independently.
2. **Real extents are the only mode.** v1's legacy 512×64 diorama scale shipped 23 working scenes but produced wrong-feeling worlds. v2 uses real DEM extents (km-scale) by default; the open `--use-real-extents` bug from v1 PM5 is solved by designing the writers around km-scale from day one.
3. **Quality knobs are presets, not flags.** v1 scattered `--size`, `--mesh-subdiv`, `--triplanar`, `--shader-preset` across multiple CLIs. v2 has `--quality {draft,good,max}` and the orchestrator sets all knob values consistently.
4. **No shared shaders or textures with v1.** v2 has its own copies in `pipelines/worldgen_v2/shaders/` and `pipelines/worldgen_v2/textures/`. v1 can be deleted later without breaking v2.

## Pipeline shape

```
pipelines/worldgen_v2/
  batch_pipeline.py             # orchestrator (entry point)
  jobs/
    death_valley.json           # one job recipe per region
    _template.json
  stages/
    fetch_dem.py                # OpenTopography client → height_16.png + dem_meta.json
    edit_dem.py                 # optional fantasy/style pass (mythic, terraced, etc.)
    paint_biomes.py             # heightmap+slope+elevation → biome mask PNG
    compile_splat.py            # biome mask → 4-channel RGBA splat PNG
    bind_textures.py            # resolve biomes → PBR sets, copy/import to Godot
    stage_godot.py              # orchestrate the writers below
  godot_writers/
    heightmap_image.py          # height_16.png + .import sidecar
    terrain_mesh.py             # PlaneMesh subdiv config
    material_tres.py            # biome_terrain.tres + uniform binding
    collision_tres.py           # HeightMapShape3D with real elev range
    environment_tscn.py         # WorldEnvironment + Sun + Sky + Fog
    camera_tscn.py              # iso / topdown / character / worldview
    scene_tscn.py               # assembles writers above into one .tscn
  shaders/
    biome_terrain_topdown.gdshader     # default — knob D settled answer
    # biome_terrain_hextile.gdshader   # knob E — Mikkelsen; deferred to v2.1
  presets/
    quality.json                # draft / good / max
    cameras.json                # per-mode tuning (near, far, fov, position basis)
    biomes.json                 # biome → texture-set mapping
  textures/                     # local biome PBR sets, no D:\assets\world deps
    desert/, tundra/, swamp/, charred_wasteland/, ...
  output/                       # job artifacts (per-job subdir)
    death_valley/
      height_16.png
      dem_meta.json
      biome_mask.png
      biome_splat_rgba.png
      world.json
  README.md
```

## Data contract — what flows between stages

Each stage reads files written by upstream stages from the job's `output/<job_id>/` directory. No stage holds in-memory state across runs; everything is on disk so any stage can be re-run independently.

| Stage | Reads | Writes |
|---|---|---|
| `fetch_dem` | `jobs/<id>.json` (bbox, dataset) | `height_16.png` (16-bit grayscale), `dem_meta.json` (bbox, span_x_m, span_z_m, elev_min_m, elev_max_m, source) |
| `edit_dem` | `height_16.png`, `dem_meta.json` | `height_16_edited.png` (overwrites for downstream simplicity) |
| `paint_biomes` | `height_16.png`, `dem_meta.json`, job's biome rules | `biome_mask.png` (8-bit indexed, palette = biome IDs) |
| `compile_splat` | `biome_mask.png` | `biome_splat_rgba.png` (4 biomes max per scene, one per channel) |
| `bind_textures` | `biome_mask.png`, `presets/biomes.json` | `pbr_pack.json` (paths to albedo/normal/roughness/ao per channel), texture files copied into Godot project |
| `stage_godot` | all of the above | `<godot_project>/scenes/<id>.tscn` + `.tres` + `.import` files |

`dem_meta.json` schema:
```json
{
  "bbox": [west, south, east, north],
  "span_x_m": 35886.0,
  "span_z_m": 44430.0,
  "elev_min_m": 657.6,
  "elev_max_m": 2712.6,
  "source": "OT/COP30",
  "fetched_at": "2026-05-06T20:53:00Z"
}
```

`jobs/<id>.json` schema (v1 minimal):
```json
{
  "id": "death_valley",
  "dem": {
    "source": "opentopography",
    "dataset": "COP30",
    "bbox": [-117.0, 36.1, -116.6, 36.5]
  },
  "edit": { "style": "realistic", "strength": 1.0 },
  "biomes": ["desert", "salt_flat", "rocky_highland", "sparse_pine"],
  "quality": "good",
  "cameras": ["character"],
  "output_godot_project": "D:/assets/worldgen2"
}
```

## Quality presets (knobs A/B/C/D from `docs/worldgen_v1/WORLDGEN_QUALITY.md`)

`presets/quality.json`:
```json
{
  "draft":  { "dem_size": 1024, "mesh_subdiv": 256, "collision_res": 128, "shader": "topdown", "triplanar_strength": 0.0 },
  "good":   { "dem_size": 2048, "mesh_subdiv": 512, "collision_res": 256, "shader": "topdown", "triplanar_strength": 0.0 },
  "max":    { "dem_size": 4096, "mesh_subdiv": 1024, "collision_res": 512, "shader": "topdown", "triplanar_strength": 0.0 }
}
```

The orchestrator passes the resolved preset to every stage and writer. There is no per-stage knob override in the first cut.

## Camera presets

`presets/cameras.json` — one entry per camera mode. Every preset sets `near` and `far` correctly for km-scale terrain (v1's regression where `far=4000` clipped 35km terrain is closed by making `far` a per-preset value, not a Godot default).

```json
{
  "character": { "fov": 70, "near": 0.1, "far": 50000, "y_offset_m": 1.7 },
  "iso":       { "ortho_size_m": 80, "near": 0.1, "far": 80000, "elevation_deg": 30, "azimuth_deg": 45 },
  "topdown":   { "ortho_size_m": 80, "near": 0.1, "far": 80000, "elevation_deg": 90 },
  "worldview": { "ortho_size_m": 50000, "near": 0.1, "far": 100000, "elevation_deg": 60 }
}
```

## Godot writer responsibilities (one job each)

| Writer | Output file | Single responsibility |
|---|---|---|
| `heightmap_image.py` | `terrain_<id>_height.png` + `.import` | Copy 16-bit heightmap into Godot project, write `.import` sidecar so Godot loads it as ImageTexture (not normal map). |
| `terrain_mesh.py` | (inline node in `.tscn`) | Emit a `MeshInstance3D` node string with `PlaneMesh { size, subdiv }` from quality preset and `dem_meta.span_x_m/span_z_m`. |
| `material_tres.py` | `terrain_<id>_material.tres` | Build `ShaderMaterial` resource with shader path + every uniform bound (heightmap, splat, 4× biome PBR sets, terrain_size_m, terrain_height_m, sea_level_m, triplanar_strength). |
| `collision_tres.py` | `terrain_<id>_collision.tres` | Build `HeightMapShape3D` with `map_data` PackedFloat32Array sampled from heightmap, scaled to real elev range (closes v1's "fall through ground" — the heightmap collision was baked at 64m max instead of 2055m). |
| `environment_tscn.py` | (inline node in `.tscn`) | WorldEnvironment + DirectionalLight3D + ProceduralSkyMaterial + Fog density auto-scaled to terrain size. |
| `camera_tscn.py` | (inline node in `.tscn`) | One Camera3D per requested camera mode, with transform + near/far from preset. |
| `scene_tscn.py` | `<id>_<camera>.tscn` | Assemble all writers above into one `.tscn` file. The ONLY writer that touches the final scene file. |

This split is the core of "find regressions fast." If textures go black, you re-run `material_tres.py` only. If the player falls through, you re-run `collision_tres.py` only. If lighting is dead, you re-run `environment_tscn.py` only.

## Error handling

- **Stages fail loud and stop the orchestrator.** No silent fallback to placeholders. v1's "scatter prop missing → use placeholder" pattern hid real bugs; v2 surfaces them.
- **Stages are idempotent.** Re-running a stage overwrites its outputs cleanly. No "skip if exists" flag in v1's first cut.
- **Job validation runs first.** `batch_pipeline.py` validates every `jobs/<id>.json` against the schema before running any stage. Bad bbox / unknown dataset / unknown biome → fail before the OpenTopography call.

## Testing

For the first milestone, "tested" means:
1. **Smoke run on `death_valley`:** orchestrator runs end-to-end, every stage produces its expected outputs, the resulting `.tscn` opens in Godot 4.5 without errors, and the `character` camera scene renders a recognizable terrain (not black, not empty).
2. **Single-stage re-run works:** delete `terrain_death_valley_material.tres`, re-run `stage_godot.py`, verify the file regenerates and the scene still renders.
3. **Quality preset swap works:** run the same job with `"quality": "draft"` then `"quality": "good"`, verify the second produces a denser mesh and bigger heightmap.

No automated test suite in the first cut. Manual Godot-eye verification per the above. Automated screenshot regression tests can come in v2.1.

## First milestone — definition of done

A user runs:
```powershell
python pipelines\worldgen_v2\batch_pipeline.py jobs\death_valley.json
```
and gets:
- A new `D:/assets/worldgen2/scenes/death_valley_character.tscn` that opens in Godot 4.5.
- Pressing F5 in Godot loads the scene with: terrain mesh visible (not black), Sun lighting (not flat), correctly textured biomes (4 distinct biome materials visible), player capsule that stands on the ground (not falling through), and the camera sees out to the horizon (no premature far-clip).
- Re-running the orchestrator is idempotent and produces the same result.

That's "good-looking map" v2 milestone 1. After it lands, the iteration knobs in `docs/worldgen_v1/WORLDGEN_QUALITY.md` (knob E hex-tile shader, B real-ESRGAN texture upscale, etc.) become the v2.1+ work — but not before milestone 1 is solid.

## What v2 is *not* yet (deferred to later phases, listed for clarity)

- **2D / iso renderers.** Pipeline shape leaves room (a future `render_2d.py` and `render_iso.py` stage could read the same `world.json` + `biome_mask.png` and produce PNG/tile outputs) but v2 first cut is 3D only.
- **Procedural FastNoise terrain.** A future `fetch_dem.py` swap to a `synth_dem.py` stage with the same `dem_meta.json` output contract.
- **Multi-DEM stitching.** A future `stitch_dems.py` stage upstream of `paint_biomes`.
- **Hand-edited overrides.** A future `edit_overrides.py` stage that lets a user paint a PNG mask and have downstream stages respect it.
- **Scatter / props.** Build chat G's lane; v2 leaves a `scatter_<id>.tscn` slot in the scene that can be filled later.

These are intentionally not in the first-cut codebase. They're noted so future maintainers know where they'll plug in.

## Risks and open questions

- **OpenTopography API key handling.** v1 used `$env:OPENTOPOGRAPHY_API_KEY` from a User-scope env var. v2 will do the same; documented in README. No secret committed.
- **Disk pressure.** D: was at 100% on 2026-05-06; per `d_drive_space_constraint.md`, check free space before bulk pulls. v2 first cut is one DEM (~50 MB), no risk; future bulk modes need a check.
- **Biome painting algorithm.** v2's `paint_biomes.py` is fresh code. v1's `world_biome_engine.py` was sophisticated (terrain-feature aware, 4 biomes, scatter rules). v2's first cut will be a much simpler height/slope rule (e.g. low-flat→salt_flat, mid-flat→desert, mid-steep→rocky_highland, high→sparse_pine). Aesthetic tuning happens during milestone 1's Godot-eye review loop.
- **Texture set sourcing.** v2 needs at least 4 PBR sets in `pipelines/worldgen_v2/textures/` for milestone 1. **No copies from `D:/assets/world/textures/`** — per the "only OpenTopography stays" rule, v2 sources its own textures from scratch. Options for the first cut, in order of cheapness: (a) free PBR set downloads from a permissive source (e.g. ambientCG/CC0Textures) bundled into v2's repo; (b) procedural placeholder textures generated in-pipeline (flat color + tiled noise) — adequate to verify the staging layer renders without taking a dependency on real PBR. Recommendation for milestone 1: start with (b) so the staging layer is testable end-to-end without any external download, then move to (a) once the pipeline shape is proven. Real AAA textures are a v2.1+ concern.
