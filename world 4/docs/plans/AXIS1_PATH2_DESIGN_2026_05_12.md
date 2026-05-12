# Axis 1 Path 2 — Real-Game Scale + Procedural Amplification Design

> Date: 2026-05-12. The scale_demo today is 1024m × 1024m, 16 tiles,
> sliced from one real DEM, all tiles fully resident, biomes
> hand-authored per tile. This design takes W4 to **4096m × 4096m
> (256 tiles)** with **clipmap LOD rendering, a kernel-based
> procedural generator system, and clipmap-resolution procedural
> splat** — all architected so the world bound is one config value
> and removing it later → infinite worlds with no refactor.
>
> Path 2 in the ROADMAP strategy. Sets the foundation that Path 3
> (DEM-informed kernel composition + erosion + river networks)
> builds on as additional kernels and policies — not as
> architectural changes.
>
> Implementation plan and per-stage PRs will be drafted from this
> doc in a separate writing-plans pass.

## Goals

### Primary
A 4 km × 4 km W4 world that:
- Renders smoothly with clipmap LOD (no fixed per-tile mesh budget;
  density falls off continuously with distance from camera).
- Generates terrain procedurally via a **kernel composition system**
  in which biomes declare which kernel(s) produce their geometry +
  biome boundary fields. v1 ships one kernel (a tileable noise
  stack); future kernels (erosion-baked, DEM-patch, river-network)
  slot in without architectural change.
- Samples its biome splat **at clipmap resolution** — high-res near
  camera, lower-res far away — to match the geometry's LOD curve.
- Has **no empty / grey / null regions visible in any direction**.
  The world always extends to the horizon with coherent terrain +
  biomes that look like continuations of what's around the camera.

### Strategic
- **Bounded-for-v1, renderer architected for infinite.** The world
  rect is one config value on `ClipmapWorld`, not baked into
  shaders or the kernel system. Setting it to `Vector2.ZERO`
  disables the clamp and the renderer keeps working. See "What
  'infinite-ready' means" below for what genuinely-infinite worlds
  ALSO need on top of the renderer (these are separate sub-projects;
  this spec ships the renderer piece).
- **DEM-informed procedural is the long-term endpoint.** Real DEMs
  feed in as a *DEM kernel* (Path 3) alongside noise / erosion /
  river kernels. The biome catalog selects which kernel(s) drive
  geometry per biome — no hardcoded "real or procedural" branch.
- **AAA-equivalent renderer architecture.** Clipmap geometry +
  clipmap splat is the Witcher 3 / Horizon / Hellblade pattern.
  Building it once means future quality / performance work happens
  inside a sane foundation.
- **Doesn't break anchor or current scale_demo.** Anchor (256m,
  locked baseline) is untouched. The existing 1024m scale_demo
  bundle stays as a working reference on the legacy pipeline path
  during the migration; new "scale_v2" bundle is the v1 target.

### What "infinite-ready" means (and what it doesn't)

The renderer (clipmap geometry + heightmap stack + splat array + the
kernel system) is bound-agnostic. Setting `world_bound_m =
Vector2.ZERO` disables the clamp at the kernel-sampling layer and
the rings keep producing terrain wherever the camera goes.

What's NOT shipped here but is needed for actually-infinite worlds:

- **Camera-relative world origin (precision).** float32 mantissa is
  24 bits, so per-millimeter precision degrades past ~16 km from
  origin. An infinite world needs the camera (or a "world origin"
  reference point) to shift periodically so the camera stays near
  the origin. Real game engines call this "origin rebasing." This
  spec doesn't ship it; for the bounded 4 km v1 it's irrelevant.
- **Chunk persistence policy.** If the player drops something in
  the world and walks away, does it survive? "Pure-function
  procedural" + "no persistence" means yes for terrain (regenerable)
  but no for state. Out of scope.
- **Collision proxy paging.** v1 has one `HeightMapShape3D` per
  ring × 4 rings. Genuinely infinite worlds may need a collision
  proxy that streams chunks the way rendering does. Same
  architectural pattern, more bookkeeping. Out of scope.
- **Long-distance LOD / fog / horizon impostors.** v1's 4 rings
  cover out to 2 km. Past that the world ends (wall + skirt).
  Genuinely infinite worlds want fog-out or distant impostors to
  hide where rendering stops.

Each of these is its own sub-project. The choice to call this spec
"infinite-ready" means **the renderer + kernel system don't need
re-architecting** when the above ship. They become additive layers.

## Non-goals (out of scope for v1)

- True infinite (chunk persistence, infinite seed memory). Slot pool
  for chunks comes later. v1 generates all 16×16 tiles at scene
  init or via clipmap visibility, no eviction policy.
- Erosion kernel (Path 3). Architecture supports it; v1 ships
  noise-stack only.
- Real DEM kernel (Path 3). Architecture supports it; v1 doesn't
  ship a real-DEM-conditioned biome variant.
- River network / hydrology systems (Path 3+).
- Object scatter (Axis 5).
- Iso/topdown per-biome shading (Axis 4 ↔ 2 cross-cut; still
  single-material in v1).
- Multi-seed worlds (one world_seed for v1; full seed system later).

## Constraints

- Godot 4.5. Vertex shader displacement + clipmap LOD geometry must
  work in Forward+ Vulkan (the editor's renderer; PITFALLS #3 says
  unshaded only at world scale, so the displacement work happens
  in a unshaded shader's vertex stage).
- Coexists with existing `terrain_world_v2.gdshader` lighting model
  (unshaded manual lambertian + ambient).
- Coexists with the Axis 6 world-splat path (the existing splat
  becomes a special case — "one resident clipmap level covering
  the world rect").

## Success criteria

1. **Visible world extends to horizon in all 4 directions** with
   coherent terrain + biomes. No grey, no null, no skybox-popped
   transition at world boundaries.
2. **Walk view at 4 km world scale stays at 60+ FPS** on a 5090
   Laptop. Headroom for decoration / VFX / gameplay later.
3. **Adding a new kernel** = declare matching `Kernel` subclasses in
   Python (`pipeline/kernels/`) and GDScript (`scripts/kernels/`) +
   register them + reference the new kernel's `kind` in
   `biome_catalog.json`. **The terrain shader does NOT change.**
   Kernels run on CPU (worker thread) and produce displacement +
   splat *textures*; the shader only ever samples textures. New
   kernel = new texture-producer, not new shader code.
4. **The renderer is world-bound-agnostic.** Setting
   `world_bound_m = Vector2.ZERO` in the scene file disables the
   clamp, and the clipmap rings keep evaluating the kernel composer
   without an architectural change. Note: this is not the same as
   "fully infinite worlds work for free" — see "What 'infinite-
   ready' means" below for the additional sub-projects that
   genuinely-infinite needs (camera-relative coordinates, chunk
   persistence policy, etc.). The renderer is one of those
   sub-projects; this spec ships it.
5. **Per-tile generation is deterministic + pure**:
   `(world_seed, tx, tz) → heightmap` is a function. Walking away
   and returning lands at the same world. No persistence required
   because generation is reproducible.
6. **Splat resolution falls off with distance**: per-fragment
   biome blend stays crisp at camera distance, smooths out far
   away. Memory cost bounded by clipmap rings, not world size.
7. **Anchor + existing scale_demo remain visually identical** to
   their 2026-05-12 baselines (regression).

## Architecture

Five components, each with one job. They communicate through narrow
interfaces so the long-term kernel + scale extensions slot in
without touching the others.

### 1. Kernel system (procedural terrain generation)

A **`Kernel`** is a pure-function terrain generator. Given a world
position and a parameter set, it produces height + biome weight
fields.

```
Kernel interface (Python pipeline + GDScript runtime mirror):

    height(world_xz: Vector2, world_seed: int, params: dict) -> float
    biome_weight(biome_name: str, world_xz: Vector2,
                 world_seed: int, params: dict) -> float
```

- Pure: same inputs → same outputs. No global state.
- World-space: takes `(x_m, z_m)` directly. No tile / chunk concept
  at this layer.
- **Runs on CPU only (worker thread).** Kernels produce displacement
  + splat *textures* via per-pixel sample loops. The shader never
  calls into a kernel — it only samples the resulting textures.
  This is why "adding a new kernel = no shader change" holds: a new
  kernel adds a new Python + GDScript class that produces texture
  data; the shader's contract (sample a Texture2DArray, blend by
  weight) is unaffected. Future GPU-resident kernels could exist
  but aren't part of this spec.
- Expected per-pixel cost: NoiseStackKernel at 4 octaves ≈ 4 µs in
  GDScript per `height()` call. A 256² grid = 65 536 calls = ~260 ms
  in single-thread GDScript. This is the budget the worker
  amortizes off the main thread (see "Async upload via double-buffer"
  in component 3).
- v1 ships **`NoiseStackKernel`** only — multi-octave fBm with
  per-biome parameter sets. Future: `ErosionBakedKernel`,
  `DEMPatchKernel`, `RiverNetworkKernel`,
  `KernelCompositeKernel` (recursive — kernels of kernels). All are
  additive Python + GDScript subclasses; the shader doesn't change.

A **`KernelComposer`** combines kernels at the world level:

```
KernelComposer interface:

    sample_height(world_xz, world_seed) -> float
    sample_biome_weights(world_xz, world_seed) -> dict[biome, float]
```

- Owns the biome → kernel mapping from `biome_catalog.json`.
- Smooths biome boundary regions by sampling each neighbor's kernel
  and weighting by biome weight at this position.
- v1's composer is **`StraightforwardComposer`** — one kernel per
  biome, biome weights from a global noise-based biome map,
  height = weighted sum of contributing biomes' kernels.
- Path 3's composer is **`KernelCompositeComposer`** — kernels can
  reference other kernels (e.g., erosion on top of noise).

#### Why this abstraction is the right thing to lock in now

The brainstorm rejected "noise stack v1, kernels later" specifically
because the kernel **registry + composer + biome→kernel mapping** IS
the architecture we want long-term. Locking it in now means future
kernels are additive subclasses, not refactors. Building noise-stack
WITHOUT this abstraction would mean rebuilding the entire pipeline
when erosion / DEM-patch lands.

### 2. Clipmap LOD rendering

The world is rendered as **N nested clipmap rings**, each a fixed
square grid of vertices that translates with the camera each frame.

```
Ring layout (top-down view):

    ┌─────────────────────────────┐
    │ Ring 3 (sparse, 16m verts)  │
    │   ┌───────────────────┐     │
    │   │ Ring 2 (8m verts) │     │
    │   │   ┌─────────────┐ │     │
    │   │   │ Ring 1 (4m) │ │     │
    │   │   │   ┌───────┐ │ │     │
    │   │   │   │Ring 0 │ │ │     │
    │   │   │   │ (2m)  │ │ │     │
    │   │   │   └───────┘ │ │     │
    │   │   └─────────────┘ │     │
    │   └───────────────────┘     │
    └─────────────────────────────┘
```

- **Ring 0** (camera-relative): 256 × 256 verts at 2m spacing →
  512m × 512m of high-detail terrain around the camera. ~131k tris.
- **Ring 1**: 256 × 256 verts at 4m spacing → 1024m × 1024m. ~131k
  tris. Renders ONLY the region outside ring 0.
- **Ring 2**: 256 × 256 verts at 8m spacing → 2048m × 2048m. Outside
  ring 1.
- **Ring 3**: 256 × 256 verts at 16m spacing → 4096m × 4096m. Covers
  the v1 world.

Each ring is **one MeshInstance3D** with a procedurally generated
mesh that's a "donut" (outer square minus inner square). Heightmap
displacement happens in the vertex shader from a sampled
displacement texture (the same clipmap-resolution heightmap stack
the splat uses; see Component 4).

Rings translate with the camera at integer multiples of their grid
spacing (to keep vertex positions aligned with the world grid and
avoid temporal flicker). Camera moves 2m → ring 0 translates 2m.
Camera moves 4m → ring 1 translates 4m. Etc.

#### Ring boundary stitching (REQUIRED — cracks are visible without it)

Naive clipmap rings produce **visible cracks at ring boundaries**:
ring 0's outer edge has a vertex every 2m, ring 1's inner edge has
one every 4m, so half of ring 0's edge vertices sit between ring 1's
edge vertices. After heightmap displacement these adjacent edges
disagree on Y by the difference between the heightmap sampled at the
finer rate vs the coarser rate.

The standard fixes, ordered by how we ship them:

1. **Vertical skirts (v1 — what this plan implements).** Ring N's
   inner edge has a downward-extruded skirt (~10 m below the
   displaced surface) that hides the gap. The skirt is shaded the
   same as the rest of the terrain. Cheap (a few hundred extra
   verts per ring) and visually clean — viewers don't see the
   transition unless they get inside the skirt geometry. Standard
   in every shipping clipmap implementation (Terragen, Cesium,
   Unreal's older LandscapeProxy).
2. **Stitch strips (alt, more complex).** A "transition mesh"
   between rings that has triangles fan-filling between the two
   resolutions exactly. No skirt geometry, no overshoot below the
   surface. More complex mesh construction. Not chosen for v1.
3. **Geomorphing (polish — Stage 6+).** Verts in the ring's outer
   edge band continuously slide their displaced position to match
   the next-ring-out's heightmap interpolation as the camera
   approaches the ring transition. Eliminates the small popping
   you can see when a ring re-snaps. Optional polish; not v1.

Component 2's mesh builder MUST emit the skirt geometry on every
ring's inner edge (and on ring 0's outer edge if we want symmetric
coverage). The skirt verts are placed at the inner-edge XZ
positions with a Y offset of `-skirt_depth_m` (default 10m).
Heightmap displacement still applies — the skirt slides downward
relative to whatever the surface elevation is.

Outermost ring's OUTER edge gets a skirt too, hiding the
"world rim" — players never see grey beyond the bound.

#### Why clipmaps (with proper stitching) over per-tile LOD rings:

- Constant tri budget regardless of world size (rings 0-3 = ~525k
  tris always, whether the world is 4 km or 40 km).
- Standard AAA pattern (Witcher 3, Horizon, Hellblade).
- Pairs naturally with clipmap splat (component 4).
- Per-fragment cost in the shader is the same as today.

(Per-tile LOD rings ALSO have boundary cracks; skirts or stitching
are equally required there. So this isn't a clipmap-specific cost
— but the plan's draft language implied clipmaps avoid it "by
construction," which was wrong.)

**Counter — per-tile LOD rings**: simpler to reason about, fits the
current per-tile mesh model, but each ring-boundary transition is
visible as a vertex density step. Not chosen.

#### Mesh generation method

CPU-built per-ring donut meshes. **Tessellation shaders are NOT
used.** Godot 4.5's spatial shader pipeline exposes vertex,
fragment, and light stages — no tessellation stage. (The earlier
draft of this spec listed tessellation as "use if Godot supports
it" — Godot 4.5 doesn't.) CPU-built meshes are fine: each ring is
~131k tris built once on scene init, no re-build needed since rings
translate with the camera rather than re-tessellating.

### 3. Heightmap displacement stack

The world's heightmap is **sampled at clipmap resolution** — one
displacement texture per ring, low-res far away, high-res near.

For each ring, a **`Texture2DArray` (one layer per ring) or a single
`Texture2D` per ring** stores the heightmap at the ring's grid
resolution. The mesh's vertex shader displaces by the value at the
vertex's world XZ.

Heightmap textures are **regenerated per ring as the camera moves**:
- Ring 0 (256² @ 2m) covers a 512m square that translates with the
  camera. Whenever the camera crosses a 2m boundary, the ring
  re-evaluates the kernel composer along its grid and writes a new
  heightmap texture.
- Ring N's update frequency = `2^N × camera_movement_threshold`.
  Coarse rings update rarely; fine rings update often.
- Per-frame budget: at typical walking speeds (5 m/s) ring 0
  updates once every ~0.4s, rings 1-3 less often. Amortizable.

#### Async upload via double-buffer (REQUIRED — main-thread RenderingServer ownership)

Godot's `RenderingServer` runs on the main thread; `ImageTexture`
creation, updates, and shader_parameter binding MUST happen on the
main thread. This is the same constraint that drives TileTerrain's
existing `WorkerThreadPool.add_task` + `_finalize()` pattern.

Per-ring update flow:

1. **Worker (off-thread)**: thread pool task receives the ring's
   target grid position. Allocates a flat `PackedFloat32Array` of
   `grid_n²` floats. Iterates the grid, calling
   `KernelComposer.sample_height(world_x, world_z, world_seed)` for
   each cell. Returns the packed array to the main thread via the
   task's result.
2. **Main thread `_finalize_ring_update()`**: receives the packed
   array, builds an `Image.create_from_data(grid_n, grid_n,
   false, Image.FORMAT_RF, bytes)` (one alloc), creates an
   `ImageTexture.create_from_image(img)` (one alloc), calls
   `MaterialInstance3D.set_shader_parameter("displacement", tex)`.

Double-buffering: each ring keeps `_current_displacement` (bound to
the material) and `_pending_displacement` (the next one being
prepared). The pending replaces the current atomically on the main
thread when the worker finishes. No frame ever sees a half-updated
texture; no shader parameter is set from a worker thread.

Budget: at 256² grid the worker does 65 536 composer.sample_height
calls. For NoiseStackKernel at 4 octaves that's ~262k Perlin lookups
per ring update. Walltime estimate: 50-200 ms in single-thread
GDScript, less if we port to C/GDExtension later. The async pattern
keeps the main thread free during that time; the ring just keeps
displaying its previous heightmap until the new one is ready.

#### Normals from the displacement texture (not from mesh)

The vertex shader reads the displacement texture, then samples the
SAME texture again at `±1 texel` in each axis to derive the
finite-difference normal in world space. The mesh's authored normals
(all `(0, 1, 0)`) are NOT used by lighting — the shader writes
`NORMAL = derived_n` in the vertex stage so the fragment stage's
`NORMAL` is the surface normal of the displaced geometry.

This is a deviation from `terrain_world_v2.gdshader`, which forwards
mesh-built normals because TileTerrain.gd computes them on the CPU
from the shared `world_height_data` (PITFALLS #4 mitigation). The v3
shader derives normals on the GPU from the displacement texture
instead. The cross-tile normal-discontinuity bug PITFALLS #4 was
about is impossible here for a different reason: each ring covers a
continuous region with one displacement texture, no cross-tile
sampling needed.

The finite-difference stencil width is one texel = `ring_extent_m /
grid_n` meters. At ring 0 (2m/texel) that's 2m, matching scale_demo's
current `normal_stencil`. Pass `stencil_texels: int = 1` as a shader
uniform so we can widen the stencil for less detailed normals on
flatter biomes (cosmetic tunable, default 1).

#### Collision proxy

GPU vertex displacement gives the player no collision geometry —
the CPU-side mesh is flat. Physics queries (camera ground-snap,
character controller, gameplay raycasts) need either a CPU
heightfield or an explicit collision proxy.

v1 ships **one `HeightMapShape3D` per ring**, sized to match the
ring's geometry. The shape's heightmap is the same
`PackedFloat32Array` the worker generated for the displacement
texture — the ring keeps the array around after building the texture
and feeds it to a `CollisionShape3D` child. Updates ride along with
the displacement update: when a ring's heightmap regenerates, so
does its `HeightMapShape3D.map_data`.

`HeightMapShape3D.update` IS main-thread (per Godot 4.5 PhysicsServer
ownership). Same double-buffer pattern as the displacement texture:
worker computes the array, main thread swaps it onto the
`HeightMapShape3D` in `_finalize_ring_update()`.

Per-ring memory cost: 256² × 4 bytes = 256 KB per ring × 4 rings =
1 MB total. Trivial.

Camera + character controllers use the existing physics collision
detection — no special path. The clipmap rings move with the camera,
so collision rings move with the camera too; the player is always
on the densest ring's collision shape.

#### Why not just keep the existing CPU-mesh-with-vertex-array pattern?

That's what the spec rejects in this section. The "build per-tile
CPU mesh, set per-vertex Y from heightmap" pattern (today's
TileTerrain.gd) works for scale_demo's 16 tiles but doesn't extend
to 256-tile worlds. Each tile mesh is 65k verts; at 256 tiles that's
16M verts, all sitting in RAM whether rendered or not. The
GPU-displaced clipmap stores ~525k verts total regardless of world
size, with the heightmap data living in compact textures.

#### Heightmap precision

**Use `Image.FORMAT_RF` (R32 float).** This is what the displacement
texture stores per pixel.

Why not R16F (`FORMAT_RH`): IEEE half-float has 11 bits of mantissa.
At absolute altitudes of hundreds of meters (typical W4 terrain at
500-1000m), the per-sample precision degrades to decimeters,
producing visible quantization staircase on slopes. The original
draft of this spec called this format "±32 km at cm precision" —
that's wrong; half-float doesn't deliver that.

Why not normalized R16 (uint16 + min/range decode): works
mathematically (16-bit-int precision per sample, decoded via two
uniform floats), but adds an unpack op in the vertex shader for
every clipmap vertex with no real upside. The memory difference
between R32F and R16-normalized is small at clipmap sizes:

- R32F: 4 rings × 256² × 4 bytes = **1 MB total**
- R16-normalized: 4 rings × 256² × 2 bytes = 0.5 MB

R32F's 0.5 MB extra is trivial; the simpler shader path wins.

Per-pixel precision at R32F: full 24-bit mantissa of float32 → ~6
decimal digits of precision. At a 1024m max elevation this is
sub-millimeter accuracy per sample.

### 4. Clipmap procedural splat

The biome splat from Axis 6 generalizes: **one splat layer-array per
ring**, resolution matches the ring's geometry resolution.

For each ring:
- `Texture2DArray` with N layers (one per biome, same as Axis 6).
- Sampled in the shader at world XZ (the world UV becomes ring UV
  per the ring's bounds).
- Resolution matches the ring's grid resolution (256² at ring 0
  covering 512m = 2m/pixel splat; 256² at ring 3 covering 4096m =
  16m/pixel splat).

Splat textures are generated by **sampling the `KernelComposer`'s
`sample_biome_weights` at the ring's grid positions**. Same
double-buffer + main-thread-upload pattern as the heightmap stack:
worker computes N flat `PackedByteArray`s (one per biome, R8
weights), main thread builds N `Image.create_from_data` + one
`Texture2DArray.create_from_images([imgs])` + one
`set_shader_parameter("ring_splat", arr)`.

`create_from_images` forces uniform-format layers; we
`img.convert(Image.FORMAT_RGBA8)` + `img.clear_mipmaps()` before
the call (PITFALLS #5). Cost per ring update: ~5× the heightmap
cost (one composer call per pixel produces both height + N biome
weights, so the sample loop is shared — we just emit N+1 arrays
instead of 1).

The splat update is tied to the heightmap update — they happen
together in one worker task per ring per snap.

**Shader picks the right ring's splat** based on world distance from
camera — same selection that picks the right geometry ring. Fragments
in the ring-0 zone read ring-0 splat (crispest biome boundaries);
fragments at the far horizon read ring-3 splat (still coherent biome
boundaries, just lower-res).

#### Why this is the right architecture

- **Memory bounded by ring count, not world size**: 4 rings × 256²
  × 5 biomes. Splat textures pack into RGBA8 (forced by Godot 4.5's
  `Texture2DArray.create_from_images` uniform-format requirement, see
  PITFALLS #5) — so 4 rings × 256² × 5 layers × 4 bytes/layer =
  **5 MB total**. Constant whether world is 4 km or ∞ km. (We could
  pack 4 biomes per RGBA8 layer to amortize the per-layer cost, but
  with N≤16 biomes the savings don't justify the encoding/decoding
  complexity.)
- **Splat fidelity matches what the eye can see**: high-res where the
  camera is, low-res where it isn't. AAA standard.
- **Same KernelComposer is the source for heightmap + splat**: no
  duplication of the "where are biomes" data. Both come from the
  same `sample_biome_weights` calls.

### 5. World seed + bound config

A single `world_seed: int` drives all kernel evaluation. Same seed
→ same world forever.

A single `world_bound: Vector2 | null` controls v1's clamp:
- `world_bound = Vector2(4096, 4096)` for v1 → world rect
  `[-2048..2048]` in XZ. Outside this rect: kernels return a fixed
  "wall" height (or kernels are not evaluated and rings just stop
  at the edge).
- `world_bound = null` for infinite → kernels evaluated forever.

The bound is a runtime concern (ScaleWorld + camera rig + a thin
"is this position in bounds" check). It's NOT baked into shaders or
pipeline. Removing it = setting it to null + verifying camera /
clipmap behaviour at extreme distances.

## Data flow

```
biome_catalog.json (gains `generator` field per biome)
        │
        ▼
KernelRegistry (NoiseStackKernel registered; Path 3 adds more)
        │
        ▼
KernelComposer (binds catalog biomes → kernels, owns world_seed)
        │
        ▼
Per-ring heightmap + splat textures (regenerated as camera moves)
        │
        ▼
Clipmap geometry (4 rings of MeshInstance3D, translate with camera)
        │
        ▼
terrain_world_v3.gdshader (samples displacement + splat by ring,
                            biome blend identical to Axis 6's v2)
        │
        ▼
Rendered world (4 km, 60+ FPS, no horizon void)
```

## Catalog schema additions

Each biome in `biome_catalog.json` gains a `generator` block:

```json
{
  "name": "alpine",
  "kit_dir": "materials/biome_alpine",
  "slots": { "ground": {...}, "mid": {...}, "rock": {...} },
  "generator": {
    "kernel": "noise_stack",
    "params": {
      "elevation_base_m": 800.0,
      "elevation_amplitude_m": 600.0,
      "octaves": 5,
      "lacunarity": 2.0,
      "persistence": 0.5,
      "ridge_sharpness": 1.4,
      "seed_offset": 1
    }
  }
}
```

- `kernel`: registered kernel name. `noise_stack` is the only v1
  value. Future: `erosion_baked`, `dem_patch`, `kernel_composite`.
- `params`: kernel-specific; documented in each kernel class.
- `seed_offset`: per-biome offset added to `world_seed` so two
  biomes using the same kernel produce different noise.

Biomes without a `generator` block fall back to a default
`noise_stack` config with flat-ish parameters — useful for
prototyping new biomes before tuning.

## Renderer + scene additions

### New shader: `terrain_world_v3.gdshader`

Inherits `terrain_world_v2`'s lighting model + biome blend logic.
Adds:

- Per-ring uniform `clipmap_ring: int` (0-3) so the shader knows
  which ring it's part of. Drives splat & heightmap layer
  selection.
- `displacement: sampler2DArray` (4 layers, one per ring).
- `splat_array` already in v2; now per-ring (multiple arrays bound
  via an array uniform) or a single array indexed by ring layer
  count.
- Vertex shader displaces from `displacement[clipmap_ring]` at
  vertex world XZ → world UV → texelfetch.

### New runtime: `ClipmapWorld.gd`

Replaces `ScaleWorld.gd` for the new world bundle. Responsibilities:

- Load biome catalog + initialize kernel registry + composer.
- Create N MeshInstance3D children (one per ring) with procedurally
  built donut meshes.
- Per-frame: track camera, decide which rings need texture update,
  enqueue async kernel evaluation, write results to ring textures.
- Translate ring meshes to stay camera-relative.
- Apply the same `terrain_world_v3` material to all rings (per-ring
  uniforms differ via `MaterialInstance3D.material_override`
  duplicates or shader parameter overrides per MeshInstance3D).

`ScaleWorld.gd` (the existing 1024m world) stays unchanged. The new
4 km world is a new bundle (`worlds/scale_v2/`) with its own scene.

### Pipeline scripts

- **`pipeline/kernels/noise_stack.py`** — Python impl of
  `NoiseStackKernel`. Used by pipeline preview tools + (optionally)
  cached splat / heightmap baking for the bounded v1 case.
- **`pipeline/kernels/base.py`** — `Kernel` abstract base + registry
  + composer.
- **`pipeline/build_kernel_preview.py`** — debug tool: render the
  composer's height + biome fields to a flat PNG at a chosen
  resolution. Use during biome tuning before launching Godot.
- **`scripts/kernels/NoiseStackKernel.gd`** — GDScript impl, mirrors
  the Python one for runtime. (Or GDExtension if perf demands; v1
  starts in GDScript and we measure.)

The Python + GDScript kernel impls must agree on outputs given the
same params + seed. **A test compares Python `NoiseStackKernel` to
GDScript `NoiseStackKernel`** for a fixed parameter set + seed at
sample points and asserts max error < epsilon.

## Performance targets

| Metric | Target | Notes |
|---|---|---|
| Walk view FPS at 4 km world | ≥ 60 | 5090 Laptop, Forward+ Vulkan |
| Frame-time variance | ≤ 5ms | Ring updates must amortize, no hitches |
| Tri count, total | ~500k-700k | Fixed by clipmap ring sizes, world-size-independent |
| Heightmap regen latency per ring | < 50ms | Ring 0 fast for responsiveness |
| Splat regen latency per ring | < 30ms | Same constraint, less data |
| Memory cost: clipmap stack | < 50 MB total | 4 rings × heightmap + splat |
| Determinism | identical bit-for-bit | Same seed + position = same heightmap, every load |

## Sub-stages (each independently testable)

### Stage 1 — Kernel system foundation
- `Kernel` interface + registry (Python + GDScript).
- `NoiseStackKernel` (Python + GDScript impls + cross-impl test).
- `KernelComposer` (straightforward composer).
- `build_kernel_preview.py` to render kernel output as a PNG.

**Exit**: Python and GDScript impls agree numerically. Preview PNG
of the noise field is reasonable.

### Stage 2 — Clipmap geometry
- Procedural donut mesh builder (per-ring grid → triangle list).
- N ring MeshInstance3D children + camera-relative translation
  logic.
- Vertex shader displacement from a debug heightmap texture (not
  the kernel composer yet — a sine-wave or noise PNG just to prove
  the geometry path).

**Exit**: 4 ring meshes render correctly, translate with camera, no
seams between rings. Frame rate ≥ 60 FPS.

### Stage 3 — Heightmap stack integration
- Wire `KernelComposer` to ring heightmap regeneration.
- Async ring updates as camera moves.
- Ring boundary continuity (rings 0 and 1 read the same height at
  their shared edge — no cliff between rings).

**Exit**: world's actual terrain renders correctly from the kernel
composer, regenerates as camera moves, no visible ring-boundary
seams.

### Stage 4 — Clipmap splat
- Splat texture stack (per-ring `Texture2DArray`).
- Wire `sample_biome_weights` to splat regeneration.
- Update `terrain_world_v3.gdshader` to sample splat by ring.

**Exit**: biomes render correctly across the world, splat sharpness
matches geometry sharpness at every distance.

### Stage 5 — World bound + new scene
- `ClipmapWorld.gd` exports `world_seed: int` + `world_bound:
  Vector2`.
- New `worlds/scale_v2/` bundle + `scenes/scale_v2.tscn`.
- `biome_catalog.json` for the new world: 5 biomes (same set as
  today) with `generator` blocks tuned per biome.

**Exit**: 4 km × 4 km world walkable, 60 FPS, terrain matches the
hand-tuned biome generator params.

### Stage 6 — Capture + verify + docs
- Walk + iso + topdown captures.
- Regression: open old scale_demo + anchor scenes, verify
  unchanged.
- Build-note + ROADMAP/AXES updates.
- Memory entry.

**Exit**: spec + plan + captures shipped. Path 3 is now "implement
another Kernel," not "rewrite anything."

## Open design questions (resolved during implementation)

- **Ring count**: 4 is a starting guess. May want 5-6 for
  high-altitude views (camera looking out 4+ km). Tune in Stage 2.
- **Skirt depth**: 10m is the starting value. Steep terrain may need
  more; we'll see in Stage 2's editor verification. Cosmetic-only.
- **Per-biome generator param tuning**: the noise stack has many
  knobs. Per-biome param tuning is its own iteration loop;
  `build_kernel_preview.py` exists to support it.
- **Cross-biome boundary blending in the kernel composer**: at
  boundary zones, do we sample BOTH biomes' kernels and blend, or
  pick the dominant biome and use its kernel? Current plan: blend
  by biome weights (continuous, no boundary cliff). Alternative:
  pick dominant (sharper biomes but cliff risk). Decide in Stage 1
  by comparison.

## Long-term path (Path 3, post-this-spec)

Adding kernels is additive. Roadmap once Path 2 ships:

- **`ErosionBakedKernel`**: pre-compute eroded heightmaps offline
  (hydraulic + thermal) per biome at multiple scales, sample at
  runtime. Adds river networks, talus slopes, realistic ridges.
- **`DEMPatchKernel`**: extract patches from real DEMs into a
  library, sample tileably at runtime. The "DEM-informed
  procedural" endpoint.
- **`KernelCompositeKernel`**: kernels that reference other kernels
  (noise base + erosion overlay + DEM patches in specific regions).
  Lets a single biome blend multiple sources.
- **`RiverNetworkKernel`**: graph-based river generation across the
  world, modifies the heightmap to carve valleys.

Each is one or two sessions. Path 2's `Kernel` interface +
`KernelComposer` make these additive, not refactor-inducing.

## What this design rejects (and why)

- **Per-tile LOD rings (the simple alternative)**: visible vertex
  density steps at ring boundaries. Doesn't scale to infinite
  worlds without re-architecting. Rejected in favour of clipmaps.
- **Pre-baked heightmaps for the bounded v1 world**: would mean
  v1's pipeline is "bake to disk once" but Path 3 needs runtime
  evaluation for DEM kernels in arbitrary world positions. Building
  runtime evaluation now means Path 3 is additive.
- **Single noise-stack-only generator without the kernel
  interface**: would require a full rewrite when erosion / DEM
  kernels land. Building the interface in v1 is one extra
  abstraction layer and pays for itself the moment a second kernel
  exists.
- **"Build A, then refactor to B" approach**: explicit user
  preference for long-term-best defaults (see memory
  `feedback_best_long_term_default.md`). Building A is throwaway
  work; building B from day 1 takes the same total work over the
  project's lifetime.

## Files this design will produce

### Created (estimated)
- `pipeline/kernels/__init__.py`
- `pipeline/kernels/base.py`
- `pipeline/kernels/noise_stack.py`
- `pipeline/kernel_composer.py`
- `pipeline/build_kernel_preview.py`
- `tests/test_noise_stack_kernel.py`
- `tests/test_kernel_composer.py`
- `tests/test_kernel_cross_impl.py`
- `the world 4/scripts/kernels/Kernel.gd` (interface)
- `the world 4/scripts/kernels/NoiseStackKernel.gd`
- `the world 4/scripts/kernels/KernelComposer.gd`
- `the world 4/scripts/ClipmapWorld.gd`
- `the world 4/shaders/terrain_world_v3.gdshader`
- `the world 4/worlds/scale_v2/biome_catalog.json`
- `the world 4/worlds/scale_v2/meta.json`
- `the world 4/scenes/scale_v2.tscn`
- `the world 4/scenes/capture_scale_v2_walk.tscn` + iso + topdown
- `docs/build-notes/AXIS1_PATH2_BUILD_NOTES_<YYYY_MM_DD>.md` (executor fills in the date when the work ships)

### Modified
- `the world 4/scripts/AnchorCameraRig.gd` — add support for
  ClipmapWorld in addition to ScaleWorld.
- `docs/strategy/AXES.md` — Axis 1 current-state update.
- `docs/ROADMAP.md` — shipped row + rerank.
- `docs/reference/TOOLS.md` — kernel system + clipmap docs.
- `docs/reference/PITFALLS.md` — any new gotchas during the build.

### Untouched
- `worlds/scale_demo/` (the existing 1024m world). Stays as legacy
  reference on the world-splat path during the migration. Can be
  deprecated once scale_v2 is the canonical demo.
- `worlds/anchor/` (locked regression baseline).
- `terrain_world_v2.gdshader` (still used by scale_demo).
- `terrain_anchor_v2.gdshader` (locked).

## Estimated cost

| Stage | Estimate |
|---|---|
| Stage 1 (kernel system) | 1-2 sessions |
| Stage 2 (clipmap geometry) | 1-2 sessions |
| Stage 3 (heightmap stack) | 1 session |
| Stage 4 (clipmap splat) | 1 session |
| Stage 5 (world bound + new scene) | 0.5 session |
| Stage 6 (capture + docs) | 0.5 session |
| **Total** | **~5-7 sessions** |

The 5-7 session estimate is for v1 (4 km, noise-stack only). Each
Path 3 kernel adds ~1-2 sessions on top.

## Why this is worth 5-7 sessions

Axis 1's first expansion (the 1024m scale_demo) took ~5 sessions
including all the pitfalls hit (black quads → unshaded shader,
contour bands → normal stencil, scanlines → gaussian smooth). Path
2 is roughly an order of magnitude more capability for 1-2× the
time. And Path 3 inherits all of it.

Compared to the cheaper alternatives (per-tile LOD + noise-only
generator, which I'd estimate at 2-3 sessions): the cheaper path
costs ~2 sessions of work that gets thrown away the first time
erosion or DEM kernels land. Net: building the right architecture
from day 1 saves time over the project's lifetime.
