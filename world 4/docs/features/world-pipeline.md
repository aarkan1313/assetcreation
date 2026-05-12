# Feature — World Pipeline (DEM → Godot)

> How to take a real-world DEM and render it as a walkable Godot world.
> This is the W4 pipeline as it actually works today. If the code drifts
> from this doc, the code wins — file an update.
>
> For artifact-debug lookup see `../reference/PITFALLS.md`.
> For pipeline commands see `../reference/ORCHESTRATOR_GUIDE.md`.

## What this feature is

W4 turns a USGS1m LiDAR DEM into a textured 3D world that you can walk
through in Godot. The pipeline is two halves:

1. **Python pipeline** (`pipeline/`) — DEM crop, gaussian smooth, tile
   slice, material binding. Outputs Godot-loadable bundles.
2. **Godot runtime** (`the world 4/`) — `ScaleWorld` + `TileTerrain`
   load the bundle, build meshes at runtime, render with a custom
   shader.

There are currently two bundle flavors:

- **Anchor** (`worlds/anchor/`): one 256×256m world, single mesh, lit
  PBR shader. Locked as the regression baseline. See `../strategy/ANCHOR.md`.
- **Scale demo** (`worlds/scale_demo/`): one 1024×1024m world sliced
  into 4×4 = 16 tiles, multi-mesh, unshaded shader with manual lighting,
  radius-paged loader. See `../build-notes/SCALE_BUILD_NOTES.md`.

This doc describes the scale_demo pipeline since it's the more capable
one. The anchor pipeline is similar but simpler.

## End-to-end flow

```
USGS1m DEM tile (D:/assets/dems/<...>.tif)
  │
  │  pipeline/pick_dem_crop_scale.py
  │  - Scans DEM for best 1024×1024m subregion by relief + slope variance
  │  - (Optional) FFT anisotropy penalty rejects strongly-striated crops
  │  - Writes 16-bit PNG + meta JSON
  ↓
worlds/scale_demo/_source_1024.png + _source_1024_meta.json
  │
  │  pipeline/slice_to_tiles.py
  │  - Gaussian smooth (sigma=1 px) suppresses LiDAR scan-line noise
  │  - Writes the post-smooth source as world_heightmap.png
  │  - Slices into 4×4 tile heightmaps + per-tile meta
  ↓
worlds/scale_demo/world_heightmap.png       (1024×1024 px)
worlds/scale_demo/tiles/tile_X_Z/heightmap.png + meta.json  (× 16)
worlds/scale_demo/meta.json                 (world-level)
  │
  │  pipeline/write_material_tres_scale_v1.py
  │  - Emits ShaderMaterial bound to terrain_scale_v1.gdshader
  │  - 3 slots × 4 PBR maps = 12 texture references
  ↓
worlds/scale_demo/material_scale_v1.tres
  │
  │  Godot --import refreshes resource cache
  │  Open scenes/scale_demo.tscn → F6
  ↓
ScaleWorld (root)
  ↓ on _ready, loads world meta + world_heightmap.png into PackedFloat32Array
  ↓ spawns TileTerrain children based on load_mode
TileTerrain × 9 (radius mode) or × 16 (load-all)
  ↓ each builds an ArrayMesh from heights, attaches scale_v1 material
3D camera rig (walk / iso / topdown) sees the rendered world
```

## Key data invariants (broken these → bugs)

These are the load-bearing contracts. Code expects them.

1. **All tiles share `elevation_min_m` and `elevation_range_m` from the
   world meta.** Adjacent-tile heights are continuous because they all
   quantize against the same range. Violating this gives cliff-seams
   at every tile border (the W3 wall).

2. **World is centered on origin.** Each tile's `world_origin_x_m` =
   `tile_x * tile_size - world_size/2`. World X range is
   `-world_size/2 .. +world_size/2`. The terrain shader reads
   `v_world_pos.xz` for UV; this assumption makes textures continuous
   across tile borders without per-tile UV adjustment.

3. **`world_heightmap.png` is the post-smoothing source, NOT a
   re-quantize of the tiles.** ScaleWorld loads this for cross-tile
   sampling in normal computation (so finite-difference normals at
   tile edges read into neighbor data instead of clamping).

4. **Tile heightmaps are lossless slices of `world_heightmap.png`.**
   The slicer asserts this (merge-back diff == 0). If you smooth one
   and not the other, edges drift.

5. **Shader is `unshaded` for any world larger than anchor.** Godot's
   PBR pipeline produces pure-black mesh quads at scale (root cause
   not pinned, but bisected and reproducible). See PITFALLS #3.

## Tunable knobs (and what they cost)

These live in pipeline scripts and the scene config:

### `pipeline/slice_to_tiles.py`
- `SMOOTH_SIGMA_PX` (default 1.0) — gaussian blur applied before
  slicing. 0 = raw DEM (will show LiDAR scan-line bands as moving
  artifacts). 1 = recommended default. 3+ = aggressive smoothing,
  destroys real features. See PITFALLS #2.

### `pipeline/pick_dem_crop_scale.py`
- `ALLOW_RIDGED_OVERRIDE` (default False) — pin the crop at the
  known-striated region (1280, 5888) for reproducing PITFALLS #4.
  Set to True only for diagnostic work.
- `RIDGE_PENALTY_WEIGHT` (default 1500) — FFT-based anisotropy penalty
  in the crop scorer. Built when we thought directional ridging was a
  bug; turned out to be unnecessary at current scale. Kept as a lever
  for future DEMs with strong geological grain. Currently scoped out.

### `scripts/TileTerrain.gd` exports
- `resolution_m` (default 1.0) — meters per mesh quad. 0.5 = 4× verts
  per tile, finer geometry but proportionally slower build.
- `normal_stencil` (default 8) — finite-difference width for vertex
  normals in mesh vertices. Default 1 causes fingerprint banding;
  8 is correlation-smooth. See PITFALLS #4.
- `generate_tangents` (default false) — set true if you're swapping
  back to a lit PBR shader (anchor v2 style). Costs ~120 ms/tile.

### `scripts/ScaleWorld.gd` exports
- `load_mode` — `LOAD_ALL` (spawn all tiles at scene start) or `RADIUS`
  (page tiles around camera). RADIUS is currently default since the
  build cost dropped to ~77 ms/tile.
- `view_radius_tiles` (default 1) — 1 means 3×3 = 9 tiles loaded.
  Bump to 2 for 5×5 = 25 tiles if loading edge is visible.
- `tile_resolution_m` — passes through to TileTerrain. Same as the
  TileTerrain knob.
- `material_override_path` — swap the per-tile material at scene config
  time. Use for diagnostics (e.g. `material_minimal.tres`).

## Per-tile build cost (as of 2026-05-11, sync path)

Measured on the diagnostic crop (1280, 5888, 522 m relief). 1 m mesh,
normal stencil 8, `generate_tangents = false`. Tile = 256×256 quads,
66 K vertices.

| Phase | Cost | What it is |
|---|---|---|
| Heightmap decode | ~3 ms | Image.load → PackedFloat32Array conversion |
| p1 — wide-bordered height cache | ~41 ms | 75 K `_sample_height` calls into a (nx+1+2·pad)² grid |
| p2 — verts+UVs+normals | ~12 ms | 66 K vertex iterations; normals look up cached neighbors directly |
| Index pass | ~7 ms | 132 K triangle indices |
| `ArrayMesh.add_surface_from_arrays` | ~4 ms | C++ work in Godot |
| Material apply | ~0 ms | Single `load()` of a `.tres` reference |
| **Total** | **~77 ms** | First tile pays an extra ~95 ms scene-graph attach; subsequent tiles ~0 ms attach |

Per-tile cost was ~325 ms before two free wins on 2026-05-11:
- Cached-neighbor normals (p2: 156 ms → 12 ms)
- Skip `SurfaceTool.generate_tangents()` for unshaded path (~120 ms → 0)

**Initial scene load (9 tiles, radius mode):** ~700 ms freeze.
**Boundary cross (3 new tiles, amortized 1/frame):** three ~77 ms
stutters across 3 frames. Felt as a brief judder, not a freeze.
**Cache-hit re-attach (walking back into a recently-unloaded tile):**
~0 ms. The mesh is kept in memory, just removed from the scene tree.

## What's not in this feature yet

These are deferred — see `../ROADMAP.md` and the "Axis 1 (Scale)
follow-ups" section of `../strategy/WISHLIST.md`:

- **LOD rings.** Outer rings could use cheaper mesh density (or wider
  stencil) without the player noticing.
- **Real-game world sizes (4 km+ / 256+ tiles).** Demo proves the
  mechanism on 1024 m / 16 tiles. Bigger worlds need bigger view radius
  and probably LOD to be playable.
- **Predictive spawn / hysteresis.** Currently tiles spawn the frame
  after the camera enters a new tile cell. Pre-warming based on camera
  velocity could eliminate even the brief judder.

## Async build (landed 2026-05-11)

Tile vertex/normal/index math runs on a `WorkerThreadPool` task off the
main thread. Only the final `ArrayMesh.add_surface_from_arrays` +
material apply + `add_child` happens on the main thread (~4 ms per tile).

TileTerrain knob: `async_build = true` (default).

Autowalker numbers (200 s / 4 legs × 600 m / 4 boundary-cross cycles):

| Metric | Sync | Async |
|---|---|---|
| FPS avg | 239.5 | 239.7 |
| FPS min | 90 | 90 |
| Peak frame ms (0.5 s window) | 95.83 | 16.66 |
| Hitches > 33 ms | 7 | 2 |
| Total stall (ms over 200 s) | 732 | 283 |

The 2 remaining hitches are likely camera-mode-swap / async-finalize
collisions (multiple tiles finishing on the same frame). Not enough to
chase further at current scope.

## Where the code lives

```
world 4/
├── pipeline/
│   ├── pick_dem_crop_scale.py     (crop scout)
│   ├── slice_to_tiles.py          (smooth + slice + world heightmap)
│   └── write_material_tres_scale_v1.py
└── the world 4/
    ├── shaders/
    │   ├── terrain_scale_v1.gdshader      (unshaded, manual lighting)
    │   └── terrain_anchor_v2.gdshader     (lit PBR, anchor only)
    ├── scripts/
    │   ├── ScaleWorld.gd          (multi-tile world root + paging)
    │   ├── TileTerrain.gd         (per-tile mesh builder)
    │   └── AnchorCameraRig.gd     (3-camera rig, duck-typed)
    ├── scenes/
    │   ├── scale_demo.tscn
    │   └── capture_scale_*.tscn   (headless capture wrappers)
    └── worlds/scale_demo/         (built artifacts)
```
