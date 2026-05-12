# Axis 1 (Scale) — Plan

> One-page plan for expanding W4 from a single 256m tile to a streaming 4×4
> grid of 256m tiles over a 1024m × 1024m DEM region. Reuse v2 shader and
> materials unchanged. Anchor demo stays untouched as the regression
> baseline.

Date: 2026-05-11
Axis: 1 (Scale), per `AXES.md`
Anchor baseline: must keep passing 6/6 done-criteria after this lands.

## Goal

Walk the camera across a 1024m × 1024m world made of 16 tiles. Tiles
load/unload around the camera. No visible seams at tile boundaries (one
continuous DEM, sliced — not stitched). Same look as the anchor at any
single point.

## Non-goals (explicit)

- Async/threaded mesh build (no off-thread loading; main-thread fine for v1)
- Biome variation (all tiles use the same 3-slot material)
- Procedural source (real DEM only)
- New shader (v2 unchanged)
- LOD (one mesh density, same as anchor)
- Touching `anchor.tscn` / `worlds/anchor/` / v2 shader / v2 materials

## Decisions (defaults confirmed)

- **Streaming target:** static-radius paging around camera (load tiles
  within radius R, unload outside). Async/threading punted.
- **DEM region:** re-scan the same Blue Ridge tile for the best 1024m
  subregion (independent of anchor's 256m crop).
- **Scene + bundle:** new `scale_demo.tscn` + `worlds/scale_demo/`. Anchor
  untouched.
- **Tile size:** 256m (matches anchor; same vertex density per tile).
- **Grid:** 4×4 = 16 tiles, 1024m × 1024m total.
- **Mesh density:** 1m per vertex (same as anchor) → 256×256 quads per tile.

## Architecture sketch

```
worlds/scale_demo/
  meta.json                          (world: 1024m, tiles: 4×4, elev range)
  tiles/
    tile_0_0/ heightmap.png + meta.json
    tile_0_1/ heightmap.png + meta.json
    ... (16 tiles)
  material.tres                      (shared, reused across all tiles)
```

```
the world 4/
  scenes/scale_demo.tscn             (new — uses same camera rig + water)
  scripts/
    ScaleWorld.gd                    (loads world meta, instantiates ChunkLoader)
    ChunkLoader.gd                   (radius-based tile paging around camera)
    TileTerrain.gd                   (refactored AnchorTerrain — builds one tile)
  shaders/terrain_anchor_v2.gdshader (UNCHANGED, reused)
  materials/anchor_v2/               (UNCHANGED, reused)
```

The key change vs. anchor: `AnchorTerrain.gd` is single-mesh-for-world. We
refactor it into `TileTerrain.gd` that builds one mesh for one tile, given
its `tile_x, tile_z` index and the world's shared meta (elev range, tile
size). It loads its own tile heightmap, builds the mesh translated to its
world-XZ origin, applies the shared material. The shader's world-relative
UV math has to work across all tiles — see Risk #1 below.

## Checkpoints

Each checkpoint is a stopping point with an editor screenshot review.
Don't proceed past one until the screenshot looks correct.

### CP1 — Pipeline: crop a 1024m DEM region, slice to 16 tiles

**Deliverable:** `worlds/scale_demo/tiles/tile_{i}_{j}/{heightmap.png,meta.json}`
for all 16 tiles, plus `worlds/scale_demo/meta.json` (world-level meta).
Plus a `material.tres` referencing the existing anchor_v2 materials.

**Scripts:**
- `pipeline/pick_dem_crop_scale.py` (new) — re-scan Blue Ridge tile for
  best 1024×1024m region, save 1024×1024 px heightmap + meta to a
  scratch path
- `pipeline/slice_to_tiles.py` (new) — read the 1024×1024 heightmap,
  slice into 16 × 256×256 heightmaps, save per-tile. **Critical:**
  share the world elev_min/elev_range across all tiles. Each tile's
  meta references the world meta, doesn't compute its own.
- `pipeline/write_material_tres_scale.py` (new, ~10 lines, basically a
  symlink to v2's writer with output path changed) — emit a
  `worlds/scale_demo/material.tres`. Reuses anchor_v2 materials.

**Validation:**
- Re-merge the 16 tile heightmaps back into 1024×1024, compare to the
  source 1024 crop pixel-for-pixel. Zero diff = slicing is lossless.
- All 16 tile metas share the same elev_min / elev_range.

**Exit:** files exist, validation passes, no Godot involvement yet.

### CP2 — Static load-all: 16 tiles loaded at scene start, no paging

**Deliverable:** `scale_demo.tscn` opens, instantiates all 16 tiles at
once via `ScaleWorld.gd`, applies the shared material, camera rig works,
walk camera can move across the whole 1024m world.

**Files:**
- `scripts/TileTerrain.gd` — copy of AnchorTerrain.gd, parameterized by
  `tile_x, tile_z` and the world meta. Builds mesh at world XZ origin
  `(tile_x * 256 - 512, 0, tile_z * 256 - 512)` (centered).
- `scripts/ScaleWorld.gd` — load world meta, spawn 16 TileTerrain nodes.
- `scenes/scale_demo.tscn` — clone of anchor.tscn structure: ScaleWorld
  root, AnchorCameraRig, AnchorWater (sized to whole 1024m world for
  now). Same lighting/sky.

**Validation:**
- Live editor view: walk from tile (0,0) to (3,3), look at all 4 corners
- **The critical seam check:** look at every internal tile boundary in
  walk view from ~5m height — heights must be continuous, no
  cracks/cliffs. Texture must read continuous (no abrupt shifts).
- Capture iso + topdown for the whole world.

**Risk #1 — World-relative UV:** The v2 shader uses UV0 = world-relative
(0..1 across the bundle). If each tile sends `0..1` in its own UV0, the
texture will reset at every tile boundary → visible seams. Fix: each
tile's UV0 must be `(tile_x + local_u) / 4, (tile_z + local_v) / 4` so
UV0 spans 0..1 *across the whole 1024m world*, not per-tile. Or:
re-think what world_uv_scale means with multi-tile and verify it tiles
seamlessly. **Verify before instantiating all 16.** Build just 2
adjacent tiles first as a sub-checkpoint and check the seam.

**Exit:** 16 tiles render, no seams in walk view, anchor demo still passes
6/6 when its scene is opened.

### CP3 — Radius paging: tiles load/unload around camera

**Deliverable:** `ChunkLoader.gd` replaces `ScaleWorld.gd`'s spawn-all
behavior. Loads tiles within radius R of camera, unloads outside.

**Behavior:**
- `loaded_tiles: Dictionary[Vector2i, TileTerrain]`
- Every frame (or every N ms): compute camera tile, compute set of
  needed tiles in radius, diff against loaded, spawn missing, free
  excess.
- Start with R = 1 tile (3×3 = 9 tiles loaded around camera).

**Validation:**
- Walk from one corner of the world to the other. Tiles spawn/free
  visibly in the editor scene tree.
- Profile: no obvious frame hitches at tile boundary crossings (this
  is a soft check; severe hitches → bump to async later but not now).
- No memory leak after many crossings (check via Godot's monitor or
  just running for a minute and watching scene tree).

**Risk #2 — Hitch on tile spawn:** building a 256×256 mesh on the main
thread *might* hitch noticeably. If it's bad, the fallback is to
pre-build all 16 meshes at scene load (back to CP2) and only toggle
their `visible` property by radius. That keeps the streaming
*interface* in place without the async work.

**Exit:** walk across the full world, tiles load/unload, no seams as new
tiles enter view, anchor demo still passes 6/6.

### CP4 — Polish + regression check

**Deliverable:** anchor demo runs unchanged. Scale demo runs cleanly.
Both documented.

- Run `anchor.tscn` → capture walk/iso/topdown → diff against pre-scale
  captures (the locked baseline). Must be visually identical.
- Update `ORCHESTRATOR_GUIDE.md` with the scale_demo pipeline commands.
- Add a `SCALE_BUILD_NOTES.md` in the style of `ANCHOR_BUILD_NOTES.md`
  capturing what was actually built + lessons learned.
- Update `AXES.md` Axis 1 section: "Current state" → "First expansion
  landed: 4×4 streaming at 256m tile, 1024m world." Note next
  experiments (larger world, async loading, etc.).

**Exit:** anchor + scale both work, docs reflect reality.

## Methodology (lessons from anchor session)

- **One change per iteration.** No batching shader + script + material
  changes in one go.
- **`--headless --import` after every shader/texture/script edit.**
- **Editor screenshot is the truth, not headless capture.**
- **Source data > shader params.** If a tile looks wrong, check the
  heightmap and the slicing before tuning the shader.
- **The anchor demo is untouched.** If at any point a change to v2
  shader/materials/AnchorTerrain.gd starts looking necessary, stop —
  that's a scope creep that violates the "anchor as regression baseline"
  rule.

## Time estimate

- CP1 (pipeline + slicing + validation): ~1 hour
- CP2 (load-all 16 tiles, fix UV math, seam check): ~2 hours
- CP3 (radius paging): ~1-2 hours
- CP4 (polish + docs): ~30 min

Total: ~half-session to a session, matches the user's estimate.

## What we'll have learned at the end

- Whether per-tile mesh-build hitches on the main thread (informs
  whether async is needed)
- Whether the v2 world-relative UV math survives multi-tile (informs
  whether axis 6 textures has a tile-boundary problem)
- Whether the slice-from-one-DEM approach is enough or we'll want
  streaming from a larger source (informs axis 3 source kernelization)
- Concrete numbers: vertex count per tile, mesh build time, paging
  latency, draw call count at view radius 1
