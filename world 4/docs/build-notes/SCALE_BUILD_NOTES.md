# Scale Demo Build Notes

> Captured 2026-05-11 after the first end-to-end run of the scale_demo
> (Axis 1 — Scale, first expansion). Companion to `ANCHOR_BUILD_NOTES.md`.
> The anchor doc describes the *target* of the anchor; this doc captures
> what we actually built for scale_demo: decisions made, what worked,
> what didn't, lessons learned.
>
> For the four artifact bugs we hit during the build, the canonical
> reference is now `PITFALLS.md`. This doc points there rather than
> duplicating.

## What got built

End-to-end pipeline + Godot runtime:

```
USGS1m DEM tile (Blue Ridge, VA, ~1m native)
  ↓ pick_dem_crop_scale.py (1024m × 1024m crop)
_source_1024.png (16-bit, 1024×1024 px) + _source_1024_meta.json
  ↓ slice_to_tiles.py (gaussian smooth, slice into 4×4 tiles)
worlds/scale_demo/tiles/tile_X_Z/heightmap.png + meta.json (×16)
worlds/scale_demo/world_heightmap.png  (the post-smooth source, used
                                         for cross-tile sampling)
worlds/scale_demo/meta.json  (world-level)
  ↓ write_material_tres_scale_v1.py
worlds/scale_demo/material_scale_v1.tres
  ↓ Godot scene scale_demo.tscn
    ScaleWorld root (loads world meta, pages tiles)
      ↳ TileTerrain children (one per loaded tile)
        ↳ MeshInstance3D with terrain_scale_v1 shader
3-camera view of the rendered 1024m world, with radius-paging
```

## Decisions made during build

- **DEM source:** same USGS1m_-78.3520_+38.5147_-78.1980_+38.6500.tif
  as anchor. Cropped 1024m × 1024m region for scale_demo (vs anchor's
  256m × 256m).
- **Crop strategy:** scan whole tile in `crop_px/4` steps, score by
  `relief + 0.5 * std`. Pinned current crop at `(1280, 5888)`,
  522m relief — chosen as a diagnostic case because it surfaces the
  contour-band bug (Pitfall #4). Cleaner crops exist elsewhere in the
  tile; an FFT anisotropy-penalty scorer in the same file can auto-pick
  them but isn't needed at current scale.
- **Tile layout:** 4×4 = 16 tiles, 256m each, 1024m × 1024m world.
- **Mesh density:** 1 vertex per meter (`resolution_m = 1.0`). Same as
  anchor. 257×257 = 66K verts per tile, 1.06M verts at full load.
- **Normal stencil:** `normal_stencil = 8` (sample ±8m for finite-
  difference). Default 1 produces visible contour bands; 8 removes them
  via adjacent-normal correlation. See Pitfall #4 in PITFALLS.md.
- **Heightmap smoothing:** sigma=1.0 px gaussian applied at slice time
  to suppress LiDAR scan-line noise. See Pitfall #2.
- **Shader:** `terrain_scale_v1.gdshader` — fresh write, `unshaded`,
  with manual lambertian + ambient math in shader code. Bypasses
  Godot's PBR pipeline entirely. See Pitfall #3.
- **Cross-tile normal sampling:** ScaleWorld loads the full
  world_heightmap.png into a shared PackedFloat32Array. TileTerrain
  samples it using world coordinates so finite-difference normals at
  tile boundaries naturally read into the neighbor tile's data.
  Eliminates the white-seam-at-tile-edge artifact.
- **Ghost-border height cache:** TileTerrain's `_build_mesh` computes
  heights at a (nx+3) × (nz+3) grid (1-vertex border outside the tile).
  Combined with cross-tile sampling, edge vertex normals are centered
  finite differences — same shape as interior normals.
- **Radius paging:** ScaleWorld in `LoadMode.RADIUS` keeps a 3×3 window
  of tiles loaded around the camera. Repage check runs every 0.25s and
  only diffs when the camera crosses a tile boundary. New tile spawns
  drain one per frame to amortize the ~325ms-per-tile build cost.

## What worked first try

- **Cross-tile UV continuity.** The v2/v1 shader computes UVs from
  `v_world_pos.xz`, not from mesh UV0. Each tile's mesh just needs to be
  positioned correctly in world space and textures tile seamlessly
  across borders. The "Risk #1" called out in the plan turned out to
  be no risk at all.
- **Lossless slicing.** Merge-back diff = 0 after gaussian smooth +
  slice. Verified in the slicer itself.
- **The duck-typing change to AnchorCameraRig.** Replacing the
  hard-coded `as AnchorTerrain` cast with a `has_method` check let the
  same rig serve both anchor and scale demos without scene changes.
  Anchor regression still passes 6/6.
- **PackedFloat32Array heightmap cache.** Decoding the heightmap PNG
  once at load time and reading via array index is ~30× faster than
  `Image.get_pixel()` per sample. Build time dropped from ~1s+ per tile
  to ~200ms before we added the wider normal stencil. (Stencil widening
  brought it back to ~325ms because each vertex normal now does 4 extra
  `_sample_height` calls at ±8m offsets.)

## What didn't work the first time (now fixed)

These are documented in detail in PITFALLS.md. Brief summary of how each
surfaced during the scale_demo build:

1. **Speckle noise from texture content (Pitfall #1)** — already known
   from anchor session, didn't bite us again because the v2/v1 shaders
   have the luma_floor + ao_floor + NaN guard infrastructure built in.
2. **LiDAR scan-line bands (Pitfall #2)** — bands that moved with the
   player. Fixed by adding `SMOOTH_SIGMA_PX = 1.0` gaussian to the
   slicer.
3. **Stationary pure-black mesh quads (Pitfall #3)** — appeared when
   first running scale_demo with the anchor's lit PBR shader. Bisect
   showed Godot's PBR pipeline produces black on certain fragments at
   large world coordinates × steep normal magnitudes, even with no sun
   and uniform ambient. Fix: switch terrain to an `unshaded` shader
   with manual lighting (`terrain_scale_v1.gdshader`).
4. **Contour-aligned fingerprint bands (Pitfall #4)** — bands that
   stayed in place as the player walked. Initially mis-diagnosed as
   source-DEM striation (the
   `TERRACING_BUG_LESSON_2026_05_11.md` doc explains that path). Real
   root cause: normal-stencil too narrow vs heightmap pixel scale.
   With stencil=1m on a 1m mesh, adjacent vertices share only 1/2
   stencil samples → independent normals → bands. With stencil=8m
   they share 15/16 → smooth lambertian. Fix: widen
   `normal_stencil` to 8.

## Radius paging — what's there and what's deferred

**Implemented in CP3:**
- 3×3 window (`view_radius_tiles = 1`) of loaded tiles around camera
- 0.25s repage check interval (not every frame)
- Boundary-cross detection by quantizing camera world XZ to tile index
- Camera resolution via Viewport.get_camera_3d() so the AnchorCameraRig
  walk/iso/topdown swap automatically triggers a repage
- Initial scene-load: full 9-tile spawn drains synchronously (~3s)
- Subsequent boundary crossings: one tile per frame from a FIFO queue
  → ~325ms × 3 stutters across 3 frames instead of one 1s freeze

**Deferred to WISHLIST.md "Axis 1 (Scale) follow-ups":**
- Real-game world sizes (4km+, 256+ tiles)
- LOD rings (different mesh density per ring around camera)
- Async/threaded tile mesh build (`WorkerThreadPool` job)
- View-radius vs visible-distance asymmetry handling

CP3 ships a working radius-paging *mechanism*; real-game scale is a
separate problem.

## Files created (CP1-CP3 scope)

### `D:\assets\world 4\pipeline\`

- `pick_dem_crop_scale.py` — DEM scout + crop for 1024m region (with
  optional FFT-anisotropy penalty + `ALLOW_RIDGED_OVERRIDE` for
  diagnostic pinning)
- `slice_to_tiles.py` — gaussian smooth + 4×4 slice + world_heightmap.png
  + per-tile meta
- `write_material_tres_scale_v1.py` — emit material_scale_v1.tres bound
  to the new unshaded shader

### `D:\assets\world 4\the world 4\`

- `shaders/terrain_scale_v1.gdshader` (~110 lines)
- `shaders/terrain_anchor_v2_minimal.gdshader` (~25 lines) — diagnostic
- `scripts/ScaleWorld.gd` (~225 lines)
- `scripts/TileTerrain.gd` (~280 lines)
- `scenes/scale_demo.tscn`
- `scenes/capture_scale_walk.tscn`, `capture_scale_iso.tscn`,
  `capture_scale_topdown.tscn` (capture wrappers)
- `worlds/scale_demo/` — 16 tile bundles + world_heightmap.png +
  meta.json + material_scale_v1.tres + diagnostic .tres files

### `D:\assets\world 4\docs\`

- `AXIS1_SCALE_PLAN_2026_05_11.md` — the prospective plan (CP1-CP4)
- `PITFALLS.md` — canonical reference for the 4 artifact bugs
- `SCALE_BUILD_NOTES.md` — this doc
- Historical docs (kept on disk, redirect headers to PITFALLS.md):
  - `AUDIT_HANDOFF_BLACK_ARTIFACTS_2026_05_11.md`
  - `BLACK_PATCH_BUG_LESSONS_2026_05_11.md`
  - `TERRACING_BUG_LESSON_2026_05_11.md`

## Done criteria (from AXIS1_SCALE_PLAN_2026_05_11.md)

1. ✅ **CP1** — pipeline produces 16 lossless tiles + shared meta + material
2. ✅ **CP2** — all 16 tiles render with no seams (visual continuity
   verified by user via editor screenshots)
3. ✅ **CP3** — radius paging works; tiles spawn/free around camera with
   1-tile-per-frame amortization; visible hitch when crossing boundaries
   is reduced but not eliminated (acceptable per user; documented as a
   wishlist follow-up)
4. ✅ **CP4** — anchor demo regression passes (verified 2026-05-11 via
   captures, all 3 views render identically to pre-scale baseline)

Anchor demo continues to pass its own 6/6 done-criteria. Scale demo
passes its plan's exit criterion.

## Addendum 2026-05-11 — perf pass + async + view modes

After CP4 closed, three follow-on chunks landed in the same session:

### Perf pass — 4× faster tile build
Profiled `_build_mesh`. Per-tile cost was 325ms split: 41ms height
cache / 156ms vert+normal pass / 7ms index / 123ms SurfaceTool tangents.
Two free wins:

1. **Skip `SurfaceTool.generate_tangents()`** on the unshaded scale_v1
   path. Tangents only matter for normal-mapped lit shaders. Saved
   ~120ms/tile.
2. **Cached-neighbor normals.** Widen the pass-1 height cache to include
   the `±normal_stencil` border. Pass 2 then reads normal neighbors
   from the cache instead of calling `_sample_height` 4× per vertex.
   Vert+normal pass dropped 156ms → 12ms.

New per-tile cost: ~77ms. Build time at 16 tiles dropped from ~5.2s
total to ~1.3s.

### Persistent unloaded-tile cache
When a tile leaves the radius, detach + hide instead of `queue_free`.
Cache hit on re-entry takes ~0ms (no rebuild). Memory cost is bounded
by total world tile count (~33MB at 16 tiles max). On `_exit_tree`,
cached nodes are explicitly `queue_free`'d to avoid leaks at scene exit.

### Async tile build via WorkerThreadPool
`TileTerrain._ready` queues a `WorkerThreadPool.add_task(_build_arrays_threaded)`
instead of building synchronously. `_process` polls
`is_task_completed`, then runs the main-thread finalize (build
ArrayMesh + attach to scene tree, ~4ms).

`_sample_height` reads two `PackedFloat32Array`s that are populated
before the task is queued and never mutated after — safe to read from
worker threads.

`_exit_tree` blocks on any pending task to avoid freeing the instance
while the worker is reading it.

### Numbers (AutoWalker, 200s of walking, 4 legs × 600m)

| Metric | Sync (pre-perf) | Sync (post-perf) | Async |
|---|---|---|---|
| Per-tile build wall-clock | 325ms | 77ms | 77ms |
| Per-tile build main-thread | 325ms | 77ms | ~4ms |
| Peak frame ms (0.5s window) | 95.83 | ~95 | 16.66 |
| Hitches > 33ms over 200s | 7 | 7 | 2 |
| FPS min | 90 | 90 | 90 |
| FPS avg | 239.5 | 239.7 | 239.7 |

### View modes (Axis 4 first expansion)

Three view shaders for scale_demo, swapped at runtime by
`AnchorCameraRig._set_mode → ScaleWorld.set_view_mode`:

- `terrain_scale_v1.gdshader` — walk view (existing)
- `terrain_view_iso.gdshader` — flatter lambertian + form-light term
- `terrain_view_topdown.gdshader` — cartographic hillshade + sepia

Per-view radius override (`view_radius_walk`/`_iso`/`_topdown`) so
iso/topdown automatically bump to whole-world while walk uses the
narrow streaming radius. Each mode swap forces a repage + drain.

WASD pans the iso + topdown cameras (no rotation, no zoom for iso;
WASD + scroll-wheel zoom for topdown). HUD updated with per-mode hints.

### Tooling shipped

- `scripts/PerfHud.gd` — top-right overlay with FPS / frame ms / peak
  ms / vertex count / tile count.
- `scripts/AutoWalker.gd` + `scenes/autotest_scale_walk.tscn` —
  scriptable walk path that prints a stats summary on completion.
  Lets us measure perf changes numerically instead of eyeballing.

## What we learned about the architecture

- **The PITFALLS.md approach (consolidating root causes by symptom)
  works.** Three predecessor docs (audit handoff, black-patch lessons,
  terracing lesson) each captured one bug in detail, but trying to
  remember which doc had what cost time. PITFALLS.md with a
  symptom-matrix at the top dispatches future debug sessions in
  seconds.
- **Lit PBR vs unshaded is a real fork in the road for terrain at scale.**
  Anchor uses lit PBR successfully; scale_demo had to switch to
  unshaded because of Pitfall #3. Going forward, any heightmap terrain
  larger than the anchor's size should default to unshaded + manual
  lighting, not lit PBR.
- **Methodology beats velocity when debugging visual artifacts.** Strict
  one-change-per-iteration cracked Pitfalls #3 and #4 in much less time
  than the multi-knob approach from the original anchor session. The
  audit doc warned the previous agent about this; we re-learned it
  empirically.
- **"Source-DEM is striated" was an honest diagnosis that turned out
  not to be the dominant cause.** Per-meter slope magnitude tests
  showed ~0.37m per meter at every stencil width — the terrain is
  rough at every scale, not "smooth signal + high-frequency noise."
  The bands came from adjacent-vertex normal independence at narrow
  stencil, not source data. Documented properly in PITFALLS.md #4.

## Follow-up: biome kits shipped 2026-05-12

The texture-generation half of Axis 2 landed in a follow-up session:
- 48 new texture maps for 4 new biomes (alpine, desert, rocky highlands,
  wetland) generated via ComfyUI FLUX2-klein 9B + aaa_texture.py at 1024².
- 4 new biome `.tres` files at
  `worlds/scale_demo/biomes/material_<biome>.tres`.
- Per-biome walk captures in `captures/biome_<biome>_walk_2026_05_12.png`.
- See `BIOME_KITS_BUILD_NOTES_2026_05_12.md` for the full session writeup.

The per-tile biome assignment (ScaleWorld + tile meta.json reading the
biome label and applying the matching material) is still pending. Hard
borders first; the Axis 6 transition workflow lights up once those seams
are visible.

## What unlocks now

Per `AXES.md`:

- **Axis 2 (Biome)** — viable now that the scale axis has tiles. Per-tile
  biome assignment becomes meaningful.
- **Axis 3 (Source)** — orthogonal, can do any time.
- **Axis 4 (View)** — anchor still uses one shader for all 3 cameras.
  The scale_v1 manual-lighting pattern is a natural starting point
  for per-view shader profiles (the math is all in-shader and easy to
  tune).
- **Axis 6 (Textures)** — still needs the blending/transition workflow
  worked out for multi-biome. Becomes more interesting once Axis 2
  lights up.

## What does NOT unlock yet

- Multi-biome (axis 2) — has a path forward but needs the textures
  workflow (axis 6) too, since biome boundaries are texture-domain.
- Decoration (axis 5) — explicit end-game per ANCHOR.md.
- LLM-drivability — still a cross-cutting wishlist concern.
