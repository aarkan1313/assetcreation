# Phase F.7 — Multi-bundle streaming director

> Streaming architecture shipped. Heightmap contiguity deferred to
> F.3.1 because it's an F.3 bundle-generation contract bug, not a
> streaming bug.

## Verdict

**F.7 ships the streaming director architecture, NOT a visually
contiguous world.** All the runtime plumbing works:

- `WorldMapService.gd` loads `world_map.json` and answers
  "what tile is at world (x, z)?" / "what tiles are within radius?"
- `MultiBundleStreamer.gd` instantiates one ChunkLoader per nearby
  bundle, positioned at the bundle's center in world space
- Direction-aware preload (`bundle_keep_radius_m` + speed-biased
  `preload_ahead_m`)
- Drop-radius eviction (`bundle_drop_radius_m`)
- Per-loader chunk update with target clamped to bundle interior
- `clip_bounds_tolerance_m` field added to ChunkLoader so adjacent
  bundles' edge cells overlap by one mesh-step

What the streamer **doesn't** ship:

- **Contiguous geometry across bundle boundaries.** Each bundle's
  heightmap was generated independently with its own seed. Adjacent
  bundles disagree on what height the shared boundary should be at.
  Visible result: tiles float at different heights with underworld
  between them.
- **Per-biome source-stack material templates.** The streamer uses
  one source-stack template (`terrain_source_stack_gloss_scrub_source_stack.tres`)
  as a base for every bundle. Per-biome templates would let each
  biome's detail layers (rock, grass, snow) bind correctly.
- **Cross-bundle texture seam blending.** F.4's transition audit
  flagged 7/8 pairs as failing — the streamer faithfully renders
  those failures at runtime.

## Honest visual state

Capture: `world3/docs/captures/review/f7_multi_bundle_sweep_midpoint.png`

What you see:
- Four bundles, each rendered correctly *internally* (chunks build,
  meshes have surfaces, real textures sample)
- Visible discontinuities at all four bundle-meeting boundaries
- White / wrong-color regions where the source-stack template's
  defaults dominate over the (correctly-loaded but wrong-format)
  per-bundle macros

The streaming **architecture** is sound. The bundles **themselves**
weren't designed to be contiguous, which is the next problem.

## What shipped

### `world3/scripts/WorldMapService.gd`

Loads `world_map.json` once, exposes:
- `tile_xy_for_world_pos(x, z) -> Vector2i`
- `tile_for_world_pos(x, z) -> Dictionary`
- `tiles_in_radius(center, radius_m) -> Array`
- `all_tiles()`, `bounds_m()`, `tile_size_m()`, `plan_id()`

Validated: loads 2×2 starter (4 tiles) and 5×5 starter (25 tiles)
cleanly with correct bounds/grid metadata.

### `world3/scripts/MultiBundleStreamer.gd`

- Reads world map, instantiates per-bundle ChunkLoaders on demand
- Bundle loaders positioned at **bundle center** (not SW corner) so
  ChunkLoader's centered `[-half, +half]` source-bounds math works
- Each frame: query player position via `_target`, smooth velocity,
  compute lookahead-biased center, find tiles in keep-radius, drop
  bundles outside drop-radius, update each loaded loader with a
  bundle-interior-clamped local position
- Sample-height-global API for terrain-Y-aware cameras
- `_load_srgb_texture` helper for macro textures from bundles
  generated outside Godot's filesystem

### `world3/scripts/MultiBundleSweepDriver.gd` + `f7_multi_bundle_sweep.tscn`

Sweep driver: player anchor slides SW→NE across the world over
`sweep_duration_sec`. Camera offsets above terrain (samples real
elevation from the streamer). HUD shows tick / position / loaded
bundle count.

### `world3/scenes/review/capture_f7_multi_bundle_midpoint.tscn`

Headless wrapper for the F.7 capture proof.

### `world3/scripts/ChunkLoader.gd` — one new field

`@export var clip_bounds_tolerance_m: float = 0.0` — extends
`_inside_source_bounds` so per-bundle loaders' edge cells overlap by
a configured tolerance. Defaults to 0 (existing behavior unchanged
for single-bundle scenes).

## Why heightmap contiguity is the next problem (F.3.1 scope)

The visible underworld and the floating tiles are NOT runtime bugs.
They're a Phase F.3 contract gap.

When F.3's `world_plan_to_bundles.py` emits per-tile region requests,
each tile gets:

```json
{ "source": {"type": "procedural", "material_id": "...",
             "seed": derived_per_tile_from_plan_seed, ...} }
```

The `build_procedural_neighbor_bundle.py` builder reads the seed and
generates a 256m × 256m heightmap from noise. **No notion of
neighbors.** Bundle (0,0)'s right edge is whatever the noise produced
at that boundary; bundle (1,0)'s left edge is whatever the noise
produced from a *different* seed at *its* boundary. They don't
agree.

The fix is F.3.1: emit bundles in dependency order (NW first, then
each tile threading its W and N neighbor's edges as constraints),
and extend the procedural builder with `--neighbor-east-edge-png`
/ `--neighbor-south-edge-png` args that force matching boundary
samples.

Once F.3.1 ships:
- Bundle heightmaps match by construction
- Geometry is contiguous without runtime seam-blending
- F.7's streaming director becomes a trivial loader of pre-contiguous
  bundles — exactly the simple "load N, render N, evict the old N"
  it was supposed to be from the start

## What F.7's architecture WILL be good for

Once bundles are contiguous, F.7 already provides:

- O(loaded-bundles) load → drop dynamics
- Direction-aware preload (bundles in player's travel direction
  load earlier than bundles behind)
- World-coord → bundle lookup for game logic
- Per-bundle ChunkLoader isolation (so streaming a bundle in/out
  doesn't disrupt others' mesh state)
- Centered loader frame so adjacent bundles' chunk grids align
  by construction

The architecture is forward-correct. The bundles fed to it are
wrong. F.3.1 fixes the bundle generation.

## Six-box LLM-drivability check (partial)

| Box | Status |
|---|---|
| Schema | ✅ `world_map_schema.json` (from F.3) |
| Validator | ✅ `validate_world_map.py` (from F.3) |
| Example | ✅ 2×2 + 5×5 starters under `world3/worlds/` |
| Audit | ⏳ The capture is the audit — currently shows the contiguity gap, which is intentional diagnostic-of-the-real-problem |
| Closure doc | ✅ this doc |
| Stages.json | N/A — F.7 is runtime |

## What's deferred from F.7 (to F.7.1 or later)

1. **F.3.1 first.** Heightmap contiguity from bundle generation. Without
   this, no F.7 polish makes the world look right.
2. **Per-biome source-stack material templates.** Author a
   `terrain_source_stack_<kit>.tres` per biome (alpine / desert /
   tundra / grassland / temperate_forest) so the streamer picks the
   right template per bundle.
3. **Macro texture color encoding.** Currently using
   `Image.srgb_to_linear()` workaround on bundles produced outside
   the editor. Either pre-import bundles into Godot's filesystem
   before launch, or refine the runtime sRGB handling.
4. **Walk-mode player + collision.** F.7 sized as "streamer works";
   actual walkable player with collision streaming is consumer scope.
5. **Direction-aware preload stress test.** Logic implemented; needs
   a fast-moving player + telemetry to verify lookahead works.

## Cross-references

- Parent phase: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Next sub-phase: F.3.1 — edge-constraint plan iterator + procedural builder
- Reads: `world_map.json`
- Wraps: existing `ChunkLoader.gd`

## Status

- [x] WorldMapService.gd
- [x] MultiBundleStreamer.gd (data plane: spawn, drop, update, sample)
- [x] MultiBundleSweepDriver.gd + scene + capture wrapper
- [x] ChunkLoader.gd `clip_bounds_tolerance_m` field
- [x] 4 bundles spawn cleanly with per-bundle ChunkLoaders
- [x] Direction-aware preload + drop-radius eviction logic
- [x] Closure doc (this doc)
- [ ] **Visually contiguous world** ← F.3.1 work, not F.7
- [ ] Per-biome source-stack templates (F.7.1)
- [ ] Walk-mode player + collision (consumer scope)

**Phase F.7 SHIP (architecture).** The visual gap is F.3.1.
