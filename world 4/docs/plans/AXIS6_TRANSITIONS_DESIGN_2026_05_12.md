# Axis 6 — Biome Transitions Design

> Date: 2026-05-12. Author: collaborative brainstorm.
>
> Successor to `AXIS6_TEXTURE_VARIETY_2026_05_11.md`. That doc covered
> the *creation* of biome textures (now shipped). This doc covers the
> *transition* problem — how adjacent biomes blend at tile boundaries.
>
> The hard-border failure mode is visible in
> `captures/biomes_wired_walk_2026_05_12.png` and
> `captures/biomes_wired_topdown_2026_05_12.png`.
>
> Implementation plan and per-step PRs will be drafted from this doc in
> a separate writing-plans pass.

## Goals

### Primary
Soft, art-directable transitions between any pair of biomes on the W4
scale_demo (and any future W4 world built on the same engine).

### Strategic
- **Biome-count-agnostic.** Shader, pipeline, and runtime have no
  hardcoded knowledge of which biomes exist. Adding/removing a biome is
  data-only — drop a kit + register in the catalog.
- **Resolution-tier-agnostic.** v1 ships with two tiers (`standard`
  1024², `hero` 4096²); adding a third tier is a data-only change (new
  array uniform + slot pool, no shader logic).
- **Engine-bundle clean.** The biome system lifts out of W4 into other
  Godot 4.5 projects as a folder of scripts + shaders + a config schema,
  with no W4-specific dependencies.
- **Forward path to streaming.** Slot-pool abstraction in place from
  day 1; static residency in v1, eviction policy is a follow-up.
- **Doesn't break anchor or current scale_demo.** Regression baselines.

## Non-goals (out of scope for v1)

- Streaming eviction policy / async biome load — slot table is static
  at world-build time.
- Per-pair authored transitions — explicitly rejected; that's the
  combinatorial trap that ate W3 session-time.
- Procedural biome assignment from heightmap features — Axis 2
  follow-up, not transition-axis work.
- Per-view per-biome shading (iso/topdown lose biome distinction) —
  Axis 4 ↔ Axis 2 cross-cut, separate work.
- Object scatter / vegetation — Axis 5.

## Constraints

- **Godot 4.5.** No bindless textures (not exposed to shaders or
  GDScript without a custom GDExtension); we use texture arrays.
- **Texture arrays require uniform resolution + format per array.**
  Implication: multiple arrays at different resolutions, one per tier.
- **Coexists with `terrain_scale_v1.gdshader` unshaded lighting**
  (PITFALLS #3). The new shader keeps the manual-lighting model.
- **Coexists with cross-tile heightmap sampling for normals** in
  `TileTerrain.gd` (PITFALLS #4 mitigation).

## Resolution tiers (v1)

| Tier | Resolution | Used by (v1) |
|---|---|---|
| `standard` | 1024² | All 4 new biomes (alpine, desert, rocky, wetland) × 3 slots = 12. Forest's `tundra_lichen` (mid). |
| `hero` | 4096² | Forest's `scrub_dense` (ground) and `rocky_slope` (rock). The two W3 real-ortho textures that already exist at 4K. |

A biome registry maps each `(biome, slot)` → `(tier, layer)` pair. Stable
identifiers are biome name + slot name; tier + layer are implementation
detail.

## Success criteria

1. No hard tile-boundary seams visible in walk view of scale_demo.
2. Transition width is art-directable per biome pair (or globally)
   without recompiling.
3. Adding a biome = drop kit in `materials/biome_<name>/` + register in
   `biome_catalog.json` + regenerate splats. No shader edits, no
   GDScript edits.
4. Scales to ≥15 active biomes with no architectural changes.
5. Adding a new resolution tier = add one array uniform + one slot
   pool in the catalog. No shader logic changes.
6. Worst-case transition blending (4 biomes contributing to one
   fragment) costs ≤ 10% frame time vs current.
7. Anchor demo and scale_demo single-biome view remain visually
   identical to their 2026-05-11/12 baselines (regression check).

## Architecture

Five components, each with one job:

```
┌─────────────────────────┐
│ biome_catalog.json      │ ── declares biomes, slots, tiers
└──────────┬──────────────┘
           │
           ├──→ build_biome_arrays.py ──→ texture arrays (.tres) per tier per map type
           │                              (global resource, bound by ScaleWorld)
           │
           └──→ build_tile_splats.py  ──→ per-tile splat.png + slot-index manifest
                                          (16 splats for scale_demo)
                                                  │
                                                  ↓
                                          Godot --import
                                                  │
                                                  ↓
┌─────────────────────────┐         ┌──────────────────────────┐
│ ScaleWorld.gd           │ ──────→ │ unified terrain shader   │
│  (global material +     │         │  terrain_world_v2.       │
│   per-tile splat bind)  │         │  gdshader                │
└─────────────────────────┘         └──────────────────────────┘
```

### Components

#### 1. Biome catalog (`worlds/scale_demo/biome_catalog.json`)

The single source of truth for what biomes exist and how they're stored.

```json
{
  "schema_version": 1,
  "tiers": [
    {"name": "standard", "resolution": 1024},
    {"name": "hero",     "resolution": 4096}
  ],
  "slots": ["ground", "mid", "rock"],
  "maps":  ["albedo", "normal", "roughness", "ao"],
  "biomes": [
    {
      "name": "forest",
      "kit_dir": "materials/anchor_v2",
      "slots": {
        "ground": {"source": "scrub_dense",   "tier": "hero"},
        "mid":    {"source": "tundra_lichen", "tier": "standard"},
        "rock":   {"source": "rocky_slope",   "tier": "hero"}
      }
    },
    {
      "name": "alpine",
      "kit_dir": "materials/biome_alpine",
      "slots": {
        "ground": {"source": "ground", "tier": "standard"},
        "mid":    {"source": "mid",    "tier": "standard"},
        "rock":   {"source": "rock",   "tier": "standard"}
      }
    },
    {"name": "desert",  "kit_dir": "materials/biome_desert",  "slots": {"ground": {"source": "ground", "tier": "standard"}, "mid": {"source": "mid", "tier": "standard"}, "rock": {"source": "rock", "tier": "standard"}}},
    {"name": "rocky",   "kit_dir": "materials/biome_rocky",   "slots": {"ground": {"source": "ground", "tier": "standard"}, "mid": {"source": "mid", "tier": "standard"}, "rock": {"source": "rock", "tier": "standard"}}},
    {"name": "wetland", "kit_dir": "materials/biome_wetland", "slots": {"ground": {"source": "ground", "tier": "standard"}, "mid": {"source": "mid", "tier": "standard"}, "rock": {"source": "rock", "tier": "standard"}}}
  ]
}
```

**Why JSON:** human-readable, hand-editable, Godot can also parse it
directly if a future runtime needs catalog inspection. Schema version
field for future migration.

**Why `kit_dir` + per-slot `source`:** decouples "where the textures
live on disk" from "what the slot is called in the shader." Forest's
ground happens to be named `scrub_dense` (legacy), but the slot is
`ground` everywhere in the shader.

#### 2. Texture array builder (`pipeline/build_biome_arrays.py`)

Reads the catalog, packs PBR maps into per-tier per-map-type
`Texture2DArray` Godot resources.

Outputs (per tier × per map type = 2 tiers × 4 maps = 8 resources):
```
worlds/scale_demo/arrays/
  standard_albedo.tres     # Texture2DArray, 1024², N layers
  standard_normal.tres
  standard_roughness.tres
  standard_ao.tres
  hero_albedo.tres         # Texture2DArray, 4096², M layers
  hero_normal.tres
  hero_roughness.tres
  hero_ao.tres
  layer_manifest.json      # biome+slot -> (tier, layer) lookup
```

The manifest is consumed by the splat builder and by ScaleWorld at
load time.

**Implementation note:** Godot 4.5 supports `Texture2DArray` natively
(`Texture2DArray.create_from_images(Array[Image])`). The `.tres` files
reference the underlying PNGs and the import pipeline materializes the
array.

#### 3. Per-tile splat builder (`pipeline/build_tile_splats.py`)

For each tile, generates a low-res splat texture (64² is plenty —
matches typical splatmap practice) that encodes per-pixel weights for
up to 4 contributing biomes.

Splat format: **RGBA8, 4 channels = up to 4 contributing biome slots
per fragment**. The slot index for each channel is delivered as a
per-tile uniform (4 ints), not encoded in the splat itself — that keeps
the splat resolution-independent and avoids alpha-channel collision
with weight values.

Output:
```
worlds/scale_demo/tiles/tile_X_Z/
  meta.json               (existing — biome field already added)
  splat.png               (new — 64x64 RGBA, weights for 4 biome slots)
  splat_meta.json         (new — the 4 layer indices for this tile)
```

For v1, splat generation has three modes (CLI flag):

- `--mode hard` — every pixel is `(255, 0, 0, 0)`, splat_meta names just the tile's own biome. Visually identical to current state. **Used to verify the array+shader path doesn't regress.**
- `--mode feather <width_m>` — pixels within `width_m` of a tile edge that borders a different biome encode a smooth ramp between this tile's biome and the neighbor's. Default width: 32m.
- `--mode noise <width_m>` — like feather but with per-pixel noise jitter on the ramp, for organic boundary shapes.

The width is the transition-width art knob from the design.

#### 4. Unified terrain shader (`shaders/terrain_world_v2.gdshader`)

Replaces `terrain_scale_v1.gdshader`. Same lighting model (unshaded
manual lambertian + ambient). New parts:

```glsl
// Two tier-specific arrays per map type
uniform sampler2DArray standard_albedo : source_color;
uniform sampler2DArray standard_normal : hint_normal;
uniform sampler2DArray standard_roughness;
uniform sampler2DArray standard_ao : hint_default_white;
uniform sampler2DArray hero_albedo : source_color;
uniform sampler2DArray hero_normal : hint_normal;
uniform sampler2DArray hero_roughness;
uniform sampler2DArray hero_ao : hint_default_white;

// Per-tile uniforms (set by TileTerrain at material instantiation)
uniform sampler2D splat;                  // 64x64 RGBA, weights
uniform ivec4 splat_layer_indices;        // up to 4 (tier_id, layer_idx) pairs
                                          // packed: tier_id in bit 31 (0=standard, 1=hero),
                                          // layer_idx in bits 0-30
uniform vec4 splat_layer_slots;           // which slot (ground/mid/rock) each maps to
                                          // (0=ground, 1=mid, 2=rock as floats)

// Existing uniforms (lighting, slope, world_uv_scale, luma_floor, etc.)
// ... unchanged from terrain_scale_v1
```

Per fragment:
1. Sample splat at world position → 4 weights, summed to 1.0.
2. For each of the 4 channels with weight > epsilon:
   - Decode `(tier, layer)` from `splat_layer_indices[i]`.
   - Decode slot from `splat_layer_slots[i]`.
   - Sample appropriate array (tier-branched) at `(world_uv, layer)`.
   - Apply slope blend within the biome (existing ground/mid/rock logic).
3. Weighted sum of the 4 contributions.
4. Apply lighting (lambertian + ambient) as before.

**Why tier branching is OK on modern GPUs:** the branch is uniform per
draw call (all fragments in a tile read the same indices). GPUs handle
uniform branches free.

**Slot-pool indirection:** the indices are *layer indices into the
array*, not *biome IDs*. CPU-side, a biome name maps to a layer via
the layer_manifest. When streaming is added later, the manifest becomes
dynamic — biome → slot, where slot is a stable index in the array. v1
manifest is static (every biome has a fixed slot for the session).

#### 5. ScaleWorld + TileTerrain bindings

Changes:

- `ScaleWorld.gd`: load global terrain material with the 8 array
  resources bound. Drop `biome_materials: Dictionary` and the per-tile
  `material_<biome>.tres` selection — replaced by per-tile splat.
- `TileTerrain.gd`: at spawn, load this tile's `splat.png` + read
  `splat_meta.json` for the 4 (tier, layer, slot) tuples. Set as
  per-tile shader_parameter uniforms on a `MaterialInstance` derived
  from the global material. (Godot 4.5 supports
  `BaseMaterial3D.duplicate()` for cheap per-instance overrides.)
- `scale_demo.tscn`: replaces `biome_materials` dict with a single
  `global_terrain_material` reference.

The legacy `biome_materials` path stays in code as a fallback for
projects that don't use the array pipeline (zero-cost when unused).

## Data flow

```
biome_catalog.json
  ↓ build_biome_arrays.py
{standard,hero}_{albedo,normal,roughness,ao}.tres + layer_manifest.json
  ↓ build_tile_splats.py (reads catalog + per-tile biome assignment)
per-tile splat.png + splat_meta.json (×16)
  ↓ Godot --headless --import
ScaleWorld loads global material with 8 arrays
  ↓ per tile spawned
TileTerrain loads splat.png + splat_meta.json, sets per-tile shader uniforms
  ↓ frame render
fragment: splat → 4 weights → 4 (tier, layer, slot) reads → blend → lit
```

## Splat semantics — worked example

For scale_demo's 4×4 layout, tile `(2, 1)` is **desert**, neighbor
`(1, 1)` is **forest**. With `--mode feather 32m`:

- splat 64×64 covers 256m × 256m tile = 4m per splat pixel
- pixels in column 0..7 (leftmost ~32m of tile) ramp from
  `(forest_weight, desert_weight) = (1.0, 0.0)` at the very edge to
  `(0.0, 1.0)` 32m in
- pixels in column 8..63 are `(0.0, 1.0)` (pure desert)
- splat_layer_indices for this tile: `[forest_layer, desert_layer, 0, 0]`
- splat_layer_slots: `[0, 0, 0, 0]` (all are ground slot — the within-biome
  slope blend still applies on top)

For tile `(1, 1)` (forest, adjacent to alpine to the north and desert
to the east): two boundaries to feather. The corner pixel in the NE is
a 3-way blend. The 4-way corner case happens only at junctions where
four tiles meet — rare in practice.

## Scope & deliverables (sub-stages)

Each stage independently testable and ships visible output before the
next begins.

### Stage 5a — Catalog + tier-array infrastructure
**Deliverable:** scale_demo renders with the new shader and the new
array path, using `--mode hard` splats. Visually identical to current
state (regression check).

Steps:
- Write `biome_catalog.json` covering all 5 biomes.
- Write `pipeline/build_biome_arrays.py` — emits the 8 array .tres files.
- Write `pipeline/build_tile_splats.py --mode hard` — emits the 16
  splat.png files.
- Write `shaders/terrain_world_v2.gdshader` — new unified shader.
- Write `pipeline/write_global_terrain_material.py` — emits the single
  global material .tres that binds the 8 arrays + lighting uniforms.
- Patch `ScaleWorld.gd` + `TileTerrain.gd` for the new uniforms +
  splat binding.
- Capture walk + topdown, diff against current state.

Exit: no visible regression vs current hard-border state.

### Stage 5b — Splat-driven blends
**Deliverable:** scale_demo with `--mode feather 32m` splats. Soft
transitions visible at every biome boundary.

Steps:
- Implement `--mode feather <width_m>` in the splat builder.
- Regenerate the 16 splats with width=32m.
- Capture, eyeball, iterate width.

Exit: no hard tile-boundary seams.

### Stage 5c — Slot-pool indirection refactor
**Deliverable:** splats reference layer indices, not biome IDs. Verify
identical render output.

Pure refactor; sets up the streaming follow-up cleanly.

Steps:
- Add `slot_pool: Array[String]` to the layer_manifest (the active
  resident set; static in v1).
- Splat builder writes pool indices instead of layer indices.
- Shader unchanged (it always saw indices).
- ScaleWorld passes pool → manifest indirection at material setup.

Exit: identical visual output to 5b; code path is streaming-ready.

### Stage 5d — Two-tier verification
**Deliverable:** confirm hero-tier reads work for forest's
`scrub_dense` and `rocky_slope`. Close-up walk capture shows 4K detail.

Steps:
- Visual diff between standard-tier and hero-tier rendering of forest
  on a close-up walk capture.
- Profile shader: any branch-cost surprise?

Exit: hero-tier visibly higher detail than standard, no perf regression.

### Stage 5e — Portability documentation
**Deliverable:** a `README` showing how to lift the biome-transitions
system into another Godot project.

Steps:
- Document the file list: shaders, scripts, pipeline tools, catalog
  schema.
- Document the integration points: how the host project hands
  per-tile splats + global material to its terrain renderer.
- Document the "what you have to write yourself" interface (the host
  project decides how tiles are spawned and what camera they're seen
  from).

Exit: doc exists, internal review passes.

### Stage 5f — Build-note + roadmap update
**Deliverable:** `build-notes/AXIS6_BUILD_NOTES_2026_05_<DD>.md`,
ROADMAP.md shipped row, AXES.md Axis 6 state update, memory entry.

## Open design questions (resolve during implementation)

- **Mip filtering on splats** — should splats use point or bilinear
  filtering on the GPU? Bilinear smooths boundary ramps for free but
  can wash out noise patterns. Recommend bilinear with mipmaps off.
- **Within-biome slope blend interaction.** Today the shader does
  ground/mid/rock blending by slope. With per-fragment biome blends,
  the slope blend happens *per contributing biome*, then biomes are
  blended. Verify the ordering doesn't produce surprises (e.g., a
  steep alpine slope blending with a flat desert flat should pick
  alpine-rock + desert-ground, then weight).
- **Boundary alignment with heightmap features.** Should biome
  boundaries snap to ridgelines / valley centerlines? Out of scope for
  v1 (hand-coded layout), but worth noting for procedural-assignment
  follow-up.
- **Sampler limits across hardware.** 8 array samplers + 1 splat + 4
  existing fallback samplers ≤ 32 (every desktop GPU since 2010).
  Mobile/integrated may have lower limits; not v1 target.

## Estimated cost

| Stage | Estimate |
|---|---|
| 5a — Catalog + array infrastructure | 1-2 sessions |
| 5b — Splat-driven blends | 0.5 session |
| 5c — Slot-pool indirection | 0.5 session |
| 5d — Two-tier verification | 0.5 session |
| 5e — Portability doc | 0.5 session |
| 5f — Build-notes + roadmap | 0.25 session |
| **Total** | **~3-4 sessions** |

The big unknowns are in 5a (first time wiring Texture2DArray through
Godot 4.5's import pipeline) and 5b (tuning the transition look).
Everything after 5a is incremental on a working foundation.
