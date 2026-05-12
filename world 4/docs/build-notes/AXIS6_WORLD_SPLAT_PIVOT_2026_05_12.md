# Axis 6 World-Splat Pivot + Mesh Density Perf — 2026-05-12

> Architectural follow-up to `AXIS6_BUILD_NOTES_2026_05_12.md`.
> Per-tile splats had a hard-line bug visible in the live editor
> (Vulkan) but hidden in headless captures (OpenGL Compatibility) —
> the exact PITFALLS methodology trap of "trust the editor screenshot,
> not the headless one." Pivoted the splat architecture to a
> world-spanning `Texture2DArray` sampled at world XZ. While in the
> shader, also bumped `resolution_m` default 1m → 2m (-75% tri count,
> no visible quality loss).

## The bug (PITFALLS #6)

Editor screenshot at a forest↔alpine↔rocky↔desert junction showed
hard diagonal color lines at every tile boundary. Headless captures
of the same scene looked clean. Per-tile splats are independent
textures sampled in [0..1] over the tile; bilinear interpolation
can't cross between two tiles' splats. Even with pixel-center
continuity (`forest tile east edge col 63 = [128, 128, 0, 0]`
exactly matching `desert tile west edge col 0 = [128, 128, 0, 0]`),
fragments at intermediate world positions read different texels from
two different textures and got different colors. Hard line.

The half-pixel-offset mitigation I shipped first (`(px - 1) * m_per_px`
instead of `(px - 0.5) * m_per_px`) made the on-disk regression test
pass but didn't fix the bug — the discontinuity was at the GPU
sampler level, not in the splat data.

## The architecture pivot

**One world-spanning Texture2DArray, one layer per biome, R8 weight
per pixel.**

- Pipeline (`build_world_splat.py`): rasterize the per-tile biome map
  at world resolution (default 256² covering 1024m → 4m/pixel). For
  each biome, compute signed distance via EDT to the nearest pixel
  of any other biome. Weight = `0.5` at the boundary, `1.0` deep
  inside the biome, `0.0` deep outside, ramped via
  `feather_width_m`. Per-pixel normalize across all biome layers.
  Optional gaussian smooth (default σ=1.5px) to remove per-pixel
  sharpness.
- Shader (`terrain_world_v2.gdshader`): drop `splat: sampler2D` +
  per-tile uniforms. Add `world_splat: sampler2DArray` +
  `num_biomes: int` + fixed-size per-biome packed `(tier, layer)`
  arrays for ground/mid/rock (MAX_BIOMES=16, bumpable). Per fragment:
  for biome i in [0..num_biomes), read weight from `world_splat`
  layer i, early-out if w<1e-3, sample biome's PBR via the packed
  index arrays, weighted-sum. `world_origin_m` + `world_size_m`
  uniforms drive the world-XZ → splat UV map.
- ScaleWorld: builds the world splat array at scene init alongside
  the 8 PBR arrays. Sets ALL per-biome packed indices + world rect
  ONCE on the global material. Every tile uses the same global
  material — no per-tile duplication, no per-tile splat lookup.

## Why this also solves the N>4 biome problem

Single RGBA8 splat caps at 4 active biomes per fragment. A
Texture2DArray splat has one layer per biome with no channel cap.
Per-fragment perf stays low because the loop early-outs on
near-zero weights — typical fragments read 1-2 active layers (the
biome they're in + maybe one neighbor in the feather zone). For
scale_demo's 5 biomes: 5 splat texture reads per fragment, ~2 of
them non-zero away from boundaries.

Architecturally clean to 15-30 biomes per world without changes.
Beyond that, biome streaming becomes the practical limit (already
listed as a parked follow-up).

## Mesh density perf pass

Heightmap downsample analysis told us per-vertex error at lower
mesh density:

| Resolution | Mean error | Max error | Note |
|---|---|---|---|
| 1m/quad (original) | 0 | 0 | baseline |
| 2m/quad | 2.5cm | 1.3m | well below walk-view visibility |
| 4m/quad | 6.6cm | 4.2m | noticeable on cliff edges |
| 8m/quad | 16.9cm | 10m | distant-LOD only |

Bumped `resolution_m` default 1m → 2m across `TileTerrain.gd`,
`ScaleWorld.gd::tile_resolution_m`, and `scale_demo.tscn`. Effects:

- Tri count: 656k → **164k (-75%)** across 9 visible tiles.
- Per-tile build cost: async finalize ~5ms → ~1ms.
- Total wall-clock per tile: ~320ms → ~245ms.
- FPS: already maxed (240 FPS); no visible change, just headroom.

The real value is for future scaling. At 4-8 km worlds (256-1024
tiles), 1m/quad would mean 100M+ tris loaded; 2m/quad gets that to
~25M, which is more manageable while LOD-rings work is parked.

## Files touched

### Created
- `pipeline/build_world_splat.py` — world-splat pipeline (rasterize +
  signed distance + ramp + gaussian smooth + normalize). 5 tests.
- `tests/test_build_world_splat.py` — 5 tests including
  boundary-continuity regression test for PITFALLS #6.
- `worlds/scale_demo/world_splat/layer_*.png` × 5 + `manifest.json`.
- `captures/axis6_world_splat_walk_2026_05_12.png`,
  `axis6_world_splat_2m_walk_2026_05_12.png`.

### Modified
- `shaders/terrain_world_v2.gdshader` — drop per-tile uniforms, add
  `world_splat: sampler2DArray`, `num_biomes: int`, per-biome
  `biome_ground/mid/rock_packed[16]: int` arrays, `world_origin_m`
  + `world_size_m` uniforms.
- `scripts/ScaleWorld.gd::_build_v2_arrays_if_needed` — load
  `world_splat/manifest.json`, build a 9th `Texture2DArray` for the
  splat stack, set per-biome packed indices + world rect on the
  global material. `_make_v2_tile_material` simplified to "return
  the global material" — no per-tile duplication.
- `scripts/TileTerrain.gd::resolution_m` — default 1.0 → 2.0.
- `scripts/ScaleWorld.gd::tile_resolution_m` — default 1.0 → 2.0.
- `scenes/scale_demo.tscn::tile_resolution_m` — 1.0 → 2.0.
- `docs/reference/PITFALLS.md` — added #6 + #6b methodology note.
- `docs/reference/TOOLS.md` — updated Axis 6 pipeline subsection,
  shader row, ScaleWorld/TileTerrain rows, demoted
  `build_tile_splats.py` to legacy.
- `docs/ROADMAP.md` — new shipped row.
- `docs/strategy/AXES.md` — Axis 6 current-state rewritten.

### Removed (no longer wired, on disk as legacy)
- ScaleWorld no longer reads `tiles/*/splat.png` + `splat_meta.json`
  or calls `_make_v2_tile_material` with per-tile uniforms. Files
  remain for a follow-up cleanup.

## What this stage did NOT do

- **No legacy cleanup.** `build_tile_splats.py`,
  `tiles/*/splat.png`, `splat_meta.json`, the
  `_v2_pool_to_layer`/`_v2_read_slot_or_layer` helpers (already
  deleted in the world-splat refactor as orphaned) — broader cleanup
  pass is a separate follow-up.
- **No streaming.** Slot pool still identity; the world splat is
  built once at scene init and resident in VRAM. Plan for streaming
  when biome count exceeds ~30.
- **No LOD rings.** Mesh density is uniform across tiles. LOD is
  the right answer for 4-8 km worlds and is parked.
- **No iso/topdown per-biome shading.** Iso/topdown still single-
  material. Cross-cut Axis 4 ↔ 2 follow-up.

## Lesson reinforcement

Per PITFALLS #6b: **the editor screenshot caught a bug the headless
captures hid through three iterations of "regression test passes,
ship it."** Walking the editor through a biome boundary should be a
mandatory step before merging Axis-6-class changes. The headless
capture is a smoke test, not a sign-off.
