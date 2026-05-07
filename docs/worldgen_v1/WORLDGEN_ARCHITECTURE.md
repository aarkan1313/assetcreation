# Worldgen Pipeline — Audit + Rewrite Proposal

> **Status (2026-05-07):** ✅ **rewrite proposal accepted and acted on.** Worldgen v1 broke late 2026-05-06; v2 rebuild active at `pipelines/worldgen_v2/`. v2 milestone 1 deliberately scoped down (terrain-only — no scatter / no real PBR sets / no 2D-iso / no multi-DEM stitch). The "swap-points" + per-region JSON config patterns this doc proposed are partly carried forward into v2's design at `docs/superpowers/specs/2026-05-06-worldgen-v2-design.md`. Keep this doc as historical context for the rationale; v2 README is the live source of truth.

Status as of 2026-05-06 evening. Reviews the current world-gen pipeline against
the character pipeline pattern (reference for swap-able tools) and proposes
where to refactor for production-quality flexibility.

## Pipeline contract today

```
[ DEM SOURCE ]                       (swap-point: 6 sources today)
  ├─ import_dem.py    → /globaldem, /usgsdem (OT)
  ├─ fetch_regional_stac.py → ArcticDEM/REMA via PGC, LINZ via NZ S3
  ├─ tile_stitch.py   → stitch N×M tiles for big regions
  ├─ mesa_terrain.py  → AI text-to-DEM (MESA)
  ├─ fastnoise_height.py → procedural OpenSimplex/Cellular
  └─ worldengine_to_bundle.py → WorldEngine simulation
                                ↓
                          height_16.png (16-bit grayscale, world space)
                                ↓
[ STYLE EDIT ]                       (1 swap-point, 7 styles)
  └─ dem_fantasy_edit.py → realistic / exaggerated / terraced / sharpened
                            spired / floating / mythic
                                ↓
                          height_16_fantasy_<style>.png
                                ↓
[ BIOME PAINT ]                      (1 implementation, locked)
  └─ art_lab/biomes/tools/world_biome_engine.py
       reads: biome_scatter_rules.json, biome_texture_registry.json,
              world_kits/<biome>.json
       writes: biome.png, biome_labels.png, world.json
                                ↓
[ SPLAT COMPILE ]                    (1 implementation, locked)
  └─ biome_splat.py
       writes: biome_splat_rgba.png, biome_splat.json
                                ↓
[ TEXTURE BIND ]                     (delegates AAA gen, swap-point INSIDE)
  └─ biome_texture_bind.py
       checks: world/textures/library/<set_id>/*.png exists
       on-miss: aaa_texture.py orchestrator (swap-point: see below)
       writes: world/worlds/<id>/biome_pbr_pack.json
                                ↓
[ TEXTURE GEN — FOR MISSING SETS ]   (swap-point: 5 backends today)
  └─ aaa_texture.py orchestrator
       chains: variant_select → delight → PBR estimate → seam_repair → QA → gate
       PBR backends:
         ├─ stablematerials_image2pbr.py (default)
         ├─ derive_pbr_v2.py            (CPU fallback)
         ├─ ma_image2pbr.py             (Material Anything, broken for 2D)
         ├─ patina_adapter.py           (Patina LoRA)
         └─ comfy_generate.py           (FLUX.2 / FLUX.1 schnell)
                                ↓
[ SCATTER ]                          (1 implementation, locked)
  └─ stage_biome_scatter.py
       reads: biome_scatter_rules.json (owned by Build chat G)
       writes: biome_scatter_<id>.tscn + .bin sidecar
                                ↓
[ STAGE GODOT SCENE ]                (1 implementation, hardcoded shader)
  └─ stage_biome_terrain.py
       hardcoded: godot_pack/shaders/biome_terrain.gdshader (one shader)
       writes: 3 .tscn files (perspective + iso + topdown), .tres material,
               heightmap collision
                                ↓
[ GODOT PROJECT ] (live in C:\Users\josep\test\new-game-project)
```

## What's already swap-able (good — keep this)

| Layer | Swap implementations | Picked by |
|---|---|---|
| DEM source | OT global, OT USGS, PGC STAC, LINZ STAC, MESA AI, FastNoise, WorldEngine, tile_stitch | `--source` / `--dataset` / `--preset` / dedicated tool |
| DEM fantasy edit | 7 styles | `--style` |
| AAA texture PBR backend | StableMaterials, derive_pbr_v2, MaterialAnything, Patina, FLUX | `--backend` (currently default-only wired) |
| Texture quality gate | grade A/B thresholds | `--quality fast/default/strict` |
| Scatter prop pool | rules JSON owned externally (Build chat G) | per-asset entry in `biome_scatter_rules.json` |
| Camera framing | worldview vs character | `--cam` |

## What's locked-in today (the rewrite targets)

### 1. Single terrain shader, hardcoded to one path

`stage_biome_terrain.py:31` — `CANONICAL_SHADER = Path(r"D:\assets\godot_pack\shaders\biome_terrain.gdshader")`. There is no `--shader` swap. The terrain shader does everything: vertex displacement + 4-channel splat blend + triplanar/top-down projection + ocean fallback.

**Why this is a problem.** The 2026-05-06 quality investigation showed multiple desirable shading techniques (Mikkelsen hex-tiling, height-blend splat, parallax occlusion, slope-aware projection) that would each call for a different shader. Right now we'd have to fork the file in place and lose backward-compat.

**Rewrite:** registry of named shaders + per-scene `--shader-preset <name>`:

```
godot_pack/shaders/
  biome_terrain_topdown.gdshader     # current pure top-down (default for character cam)
  biome_terrain_triplanar.gdshader   # current triplanar (best for first-person)
  biome_terrain_hextile.gdshader     # Mikkelsen hex-tile (NEW, fixes cliff stretch)
  biome_terrain_heightblend.gdshader # Height-based splat blend (NEW, sharp boundaries)
  biome_terrain_pom.gdshader         # Parallax occlusion (NEW, hero-rock detail)
```

Each shader exports the same uniforms (`heightmap`, `splat`, `albedo_R..A` etc.) so `stage_biome_terrain.py` is shader-agnostic. CLI becomes `--shader-preset hextile`, defaults to `topdown`.

### 2. Single biome compositor, locked algorithm

`art_lab/biomes/tools/world_biome_engine.py` is the only paint implementation. It uses:
- Voronoi-region biome seeds with terrain-aware bias (slope, altitude_band, river anchors)
- `transitions.blend_neighbours.width_px` controls feathering
- Output: 8-bit `biome_labels.png` + 16-bit `biome.png`

There is no swap for "paint biomes via OpenSimplex blobs", "paint via climate-zone simulation", "paint via authored splat", etc. If we want to test e.g. real-world biome data (BiomeXYZ from satellite), we'd have to fork this script.

**Rewrite:** make `world_biome_engine.py` one of N painters, each writes the same `biome_labels.png` + `world.json` contract:

```
pipelines/biome_paint/
  voronoi_painter.py         # current world_biome_engine.py
  noise_painter.py           # OpenSimplex blobs, no terrain awareness
  climate_painter.py         # use heightmap altitude bands + latitude → biome
  satellite_painter.py       # take a real ESA/NASA biome map TIFF as input
  authored_painter.py        # take a hand-painted biome_labels.png in
```

CLI: `--painter voronoi|noise|climate|satellite|authored`, default `voronoi`.

### 3. Hardcoded splat compiler

`biome_splat.py` has one algorithm: pick first 4 biomes, assign by scene position, gaussian-blur 1.6px. The 2026-05-06 research recommended **height-based splat blending** (use height as alpha → softmax across layers) for crisp pebble-into-sand transitions.

**Rewrite:** make splat strategy a `--splat-mode {gaussian, height_blend, hard, weighted_voronoi}` flag. Same I/O contract.

### 4. Scatter implementation locked

`stage_biome_scatter.py` outputs MultiMeshInstance3D + .bin sidecar. There is no path to:
- Output as GPU compute scatter (HZD-style)
- Output as Godot 4.5 GeometryInstance3D + LOD chains
- Output via Terrain3D's native scatter

**Rewrite (deferred):** scatter strategy flag, but Build chat G owns this lane and has its own roadmap. Don't preempt.

### 5. Hardcoded `TERRAIN_SIZE_M=512` + `TERRAIN_HEIGHT_M=64`

Constants at the top of `stage_biome_terrain.py`. Means every world is 512m × 512m at 64m max relief. For a real region (yosemite_full_1m spans 30km × 30km, range goes 894m → 3396m = 2502m relief), our staged Godot scene compresses 30km into 512m and 2.5km of relief into 64m. The actual data is way more dramatic than what we render.

**Rewrite:** make these per-world from `world.json` metadata. Pull from the source DEM bbox's km² extent + percentile elevation range. CLI override: `--terrain-size-m 1024 --terrain-height-m 256` for marquee scenes.

This single change might be the biggest visual upgrade — the death_valley_basin scene currently shows a ~2km vertical relief in 64m of mesh height, so cliffs are 25× shallower than they should be.

### 6. Single Godot project target

`stage_biome_terrain.py` writes into `<project>/biome_terrain_test/`. There is no scene-template system. If we want a different visual style (cel-shaded, voxel, painterly), we have to fork the .tscn template strings in the script.

**Rewrite (later):** scene template registry with named templates and per-template stagers. Out of scope for the immediate rewrite.

## Reference: how character pipeline does it

From `D:\assets\meshy\batch_pipeline.py` and `D:\assets\animators\README.md`:

1. **Per-job JSON config**, not per-script CLI. Every job is a dict with mesh, prompt, optional bake/pack/pixel_art settings. The orchestrator reads the JSON and dispatches to the right tool with the right args.
2. **Swap-able tools at every layer.** Image-to-3D: Meshy or Trellis2. Rigging: SkinTokens, RigAnything, MagicArticulate, Mesh2Motion. Animation: AnimateAnyMesh or hy-motion-fbx-exporter. All output GLB/FBX so the bake/pack pipeline doesn't care which path produced the input.
3. **Shared output format.** Every rigging tool emits a GLB with skeleton + skin weights; every animator emits FBX with motion. The orchestrator stages them identically.
4. **Status table in README.md** with verified-working/installed/deferred per tool.

Our world-gen pipeline currently has step 2 partially (DEM sources, AAA backends) but is missing 1 (per-region JSON config, the wishlist sort of does it but not all params), 3 (shader/scene templates aren't normalized), and 4 (no status table in worldgen-specific README — we have ROADMAP but it's mixed).

## Proposed refactor scope (ordered by impact)

### Phase 1 — Core swap-points (1-2 days)
1. **Per-region JSON config** like character `jobs.json`. One file per scene with: bbox, dataset, style, biomes, painter, splat_mode, shader_preset, cam, terrain_size_m, terrain_height_m, project. `region_pipeline.py` becomes a JSON walker, not a CLI parser. Existing CLI stays as a wrapper that emits the JSON.
2. **Shader registry** at `godot_pack/shaders/`. Wire `--shader-preset {topdown,triplanar,hextile,heightblend}`. Implement `topdown` and `triplanar` immediately (split the current shader). Defer `hextile` + `heightblend` to phase 2.
3. **Per-world TERRAIN_SIZE_M / TERRAIN_HEIGHT_M** from world.json. Compute from DEM bbox + elevation percentiles. Single biggest visible quality gain across all 23 staged scenes.
4. **Splat mode flag** with `gaussian` (current) and `hard` (no blur) initially.

### Phase 2 — Quality wins from research (2-3 days)
5. Implement `biome_terrain_hextile.gdshader` (Mikkelsen 2022). Public Godot 4 GLSL port available. Fixes cliff stretch.
6. Implement `biome_terrain_heightblend.gdshader` (height-based splat blend). Drops the gaussian splat blur dependency, gains crisp boundaries.
7. **BC7 / BC5 reimport** for albedos / normals via `.import` file overrides. Free quality.
8. Real-ESRGAN x4plus offline upscale pipeline replacing the PIL Lanczos in `upscale_biome_set.py`. ComfyUI workflow.

### Phase 3 — Painter swap-out (deferred until needed)
9. Painter registry. Voronoi (current) + climate (altitude+latitude → biome) initially. Satellite painter for real ESA/NASA data later.

### Phase 4 — Status / docs hygiene (small but important)
10. `pipelines/terrain/README.md` with the swap-point table from this doc. Same shape as `animators/README.md`. Easy onboarding for a future Build chat to extend.
11. Per-region `<region_id>.region.json` config files in `art_lab/biomes/regions/`. Replaces the implicit CLI invocations scattered across our test commands.

## Don't-touch list (other lanes own these)

- `pipelines/props/` (Build chat G)
- `biome_scatter_rules.json` (Build chat G — but the SCATTER stage that reads it is in our lane and already swap-able internally)
- `world/props/library/` (Build chat G)
- `pipelines/audio/`, `pipelines/ui/`, `pipelines/vfx/`, `pipelines/game_data/` (other Build chats)

## Phase 1 STATUS — landed 2026-05-06

All four steps shipped. Pipeline now has 4 new orthogonal swap-points + a
declarative config layer.

### 1.1 — Per-region JSON config + walker

`pipelines/terrain/region_pipeline_from_config.py` reads `*.region.json`
files conforming to **schema `region.config.v1`** and dispatches to
`region_pipeline.py` with the right CLI args. Schema captures every choice:
DEM source, fantasy style, biomes, splat mode, shader preset, terrain
extents, scatter caps, camera framing, project path, quality gate.

CLI:
```powershell
# Single region
python pipelines\terrain\region_pipeline_from_config.py --config art_lab\biomes\regions\death_valley_basin.region.json
# Batch
python pipelines\terrain\region_pipeline_from_config.py --batch art_lab\biomes\regions\*.region.json
# Generate fresh template
python pipelines\terrain\region_pipeline_from_config.py --template my_id > art_lab\biomes\regions\my_id.region.json
```

First example region: `art_lab/biomes/regions/death_valley_basin.region.json`.

### 1.2 — Shader registry

`godot_pack/shaders/shader_registry.json` maps `--shader-preset NAME` to
`{shader_file, triplanar_strength, triplanar_sharpness, description}`.
Presets:
- `topdown` (default) — pure top-down UV; cleanest for ARPG iso/topdown
- `triplanar` — slope-aware (top + cliff blend); better for first-person
- `hextile` (RESERVED, falls back to topdown) — Mikkelsen 2022 stochastic tiling
- `heightblend` (RESERVED) — height-based splat blend

Stage code resolves the preset, copies the right `.gdshader` into the
project, and writes the right uniform values into `.tres`. CLI override
`--triplanar 0.0|1.0` works on top of the preset's default.

### 1.3 — Per-world terrain extents

`stage_biome_terrain.py:compute_terrain_dims()` reads `world.json`'s
`dem_meta` block (which `world_biome_engine.py` now populates from the
upstream DEM tool's `terrain.json` or `tile_grid.json`) and computes real
metric span + relief. CLI:
- `--use-real-extents` — opt-in: use real bbox span + elev range from dem_meta
- `--terrain-size-m N` / `--terrain-height-m N` — explicit override

Default stays at the legacy 512m × 64m diorama scale because scatter density,
texture tiling, and camera framing are all calibrated for it. Use
`--use-real-extents` only when you've also retuned those (e.g. via region
config overrides for `terrain.size_m` + `terrain.mesh_subdiv` + tile_meters).

Worldview camera framing now scales with terrain size automatically; fog
density inversely scales with terrain size to avoid multi-km whiteout.

### 1.4 — Splat-mode flag

`biome_splat.py --splat-mode {gaussian, soft, hard, height_blend}` sets
the boundary blend strategy. Wired through `region_pipeline.py` and
`region.config.v1`. `height_blend` is reserved (currently behaves like
`hard` for forward-compatibility with the future heightblend shader).

### Test status

End-to-end verified on `death_valley_basin` via the new config walker.
Legacy 512m default produces the same output as before our refactor; new
`--use-real-extents` flag correctly produces 35.9km × 2055m terrain (with
expected visual issues that need scatter density / tile_meters retuning).

## Phase 2 — research-driven quality wins (next)

Now that the swap-points exist, drop-in quality wins from the 2026-05-06
research survey:

1. **Implement `biome_terrain_hextile.gdshader`** — Mikkelsen 2022 stochastic
   hex-tiling. Public Godot 4 GLSL port available. Fixes both visible texture
   repeats AND cliff stretch in one shader. ~half day.
2. **Implement `biome_terrain_heightblend.gdshader`** — height-based splat
   blending using packed alpha-as-height. Drops the gaussian splat blur,
   produces crisp pebble-into-sand transitions. ~half day.
3. **BC7 / BC5 reimport** for albedos / normals via `.import` file overrides.
   ~1h.
4. **Real-ESRGAN x4plus offline pipeline** replacing PIL Lanczos. ComfyUI
   workflow. ~half day setup + per-set runtime.

## Phase 3+ (deferred)

- Painter swap (Voronoi, climate, satellite, authored)
- Scatter strategy (currently locked, Build chat G owns)
- Scene template registry (cel-shaded, voxel, painterly)
