# Clipmap splat + biome rendering — design

Status: approved 2026-05-12, ready to plan.

## Why

Stage 3 + Stage 3.6 of Axis 1 Path 2 shipped a working clipmap
renderer: kernel-driven heightmaps, async regen, morph zones, lit
PBR. But every fragment still uses a single flat `base_albedo` — no
biomes are visually distinguishable. The user's editor verification
captures show smooth procedural terrain with one brown color.

Stage 4 wires per-biome PBR shading into the clipmap renderer:
each fragment samples the per-biome ground/mid/rock material maps
weighted by biome presence at that world XZ, so alpine reads as
rocky+icy, desert as sandy, forest as soil+vegetation, etc.

The challenge versus Axis 6's existing splat pipeline (which works
on scale_demo's 1024m bounded world): the clipmap renderer's world
is **unbounded by design** (4 km initial, designed to grow without
a rebuild). The Axis 6 pattern of "pre-bake a fixed-size splat PNG
covering the whole world" doesn't fit. Stage 4 builds the splat
**procedurally per-ring**, mirroring the heightmap async pipeline.

Per project ethos (Quality ≥ Performance > anything > time-to-ship),
this is the long-term-correct architecture even if it costs more
sessions than a baked-splat approach. The baked path stays in
ScaleWorld for legacy / 2D-bake / scale_demo cases.

## Scope

In:
- Per-ring splat **`sampler2DArray`** generated procedurally via
  `KernelComposer.sample_biome_weights` on `WorkerThreadPool`, one
  R8 layer per "active biome in this ring" (mirrors Axis 6's
  `terrain_world_v2.gdshader` splat-array pattern; not RGBA-packed,
  not channel-packed). Layer count = `active_biomes_n` (varies per
  ring, ≤ `max_biomes_per_ring`).
- CPU-side **biome culler** that picks which biomes occupy slots in
  a given ring, with **hysteresis** to avoid biome-list churn on
  small camera moves.
- Per-ring **biome PBR Texture2DArrays** — ground/mid/rock × all
  active biomes for this ring, sourced from
  `worlds/scale_v2/materials/biome_<name>/`.
- Shader changes: `terrain_world_v3.gdshader` samples splat array +
  per-biome PBR arrays, accumulates weighted albedo/normal/roughness.
- `MAX_BIOMES_PER_RING` as a quality-tier knob (Low 4 / Medium 6 /
  High 10 / Ultra 16).
- Morph zones extended to splat: the splat sample at a fragment in
  ring `i` blends toward ring `i+1`'s splat sample at the same world
  XZ inside the morph band, identical to the heightmap morph.

Out:
- Reusing Axis 6's `build_world_splat.py` baked-PNG pipeline (kept
  as-is for `scale_demo`; clipmap renderer has its own runtime
  generator).
- Biome streaming with LRU eviction across multiple worlds — single
  active world is enough for now.
- 4-way junction "select N of M overlapping biomes" sophistication
  beyond the cap. v1 picks top-weighted N inside the ring's bbox.
- Per-biome slope-blended ground/mid/rock — the slope-blend pattern
  exists in `terrain_world_v2.gdshader`; porting it is Stage 4.2.
  Stage 4.1 ships just ground-albedo + per-biome blending.

## Architecture

### Data flow

```
KernelComposer (knows all world biomes — no cap)
        │
        │ sample_biome_weights(x, z, seed)
        ▼
Worker thread (per ring regen, same pipeline as heightmap):
  1. Sample composer at every ring vertex → biome weight matrix
  2. Cull to top N biomes in this ring's bbox (hysteresis)
  3. Build N-layer splat float buffer (n × n × N)
        │
        │ PackedByteArray
        ▼
Main thread: _finalize_ring_upload
  1. Build splat Texture2DArray (Image.create_from_data per layer)
  2. Set per-ring shader uniforms:
     - splat_array (sampler2DArray)
     - active_biomes_n (int)
     - biome_pbr_slot[N]: which biome occupies each splat layer
  3. Bind per-biome PBR Texture2DArrays (ground albedo for v1) for
     every biome currently used by ANY ring (shared across rings).
        │
        ▼
Fragment shader:
  for i in 0..active_biomes_n:
      w = texture(splat_array, vec3(uv, i)).r
      albedo += w * texture(pbr_ground_array, vec3(uv_local, biome_pbr_slot[i])).rgb
  ALBEDO = albedo
```

### CPU-side biome culler

```python
def biomes_intersecting_ring(composer, ring_bbox_m, threshold, sticky_set):
    """Return the set of biome names with weight > threshold anywhere
    inside ring_bbox_m, biased to keep biomes in `sticky_set` if their
    weight is still > sticky_threshold (hysteresis).
    """
```

GDScript-side equivalent runs on the worker. Threshold + sticky
threshold are tier-tunable but start at 0.05 / 0.01 — biomes have
to drop below 1% influence to leave the ring's active set after
joining.

Hysteresis matters because: at high player speed, a ring that
catches a biome's edge for one frame would otherwise churn the
biome-slot dictionary, forcing splat rebuilds. Stickiness lets the
biome ride along for a few extra frames as it fades out — covers
the regen latency.

### Per-ring biome slot mapping

Each ring carries a `biome_slot_to_name: Array[String]` of length
`active_biomes_n`. Slot N of the splat array is biome
`biome_slot_to_name[N]`. The shader uniform
`biome_pbr_slot: Array[int]` maps splat slot N → PBR
Texture2DArray layer for that biome's ground material.

Why two indirection levels (slot → pbr_slot)?

- **Splat slot** is dense (0..active_biomes_n-1, per ring).
- **PBR slot** is global (0..total_biomes_in_world-1, shared across
  rings, in Texture2DArray layer order).

This lets ring 0 use biomes {alpine, desert, forest} in splat slots
{0,1,2} while ring 2 uses {forest, alpine, tundra, marsh} in splat
slots {0,1,2,3} — they both reference biome PBR data from the same
shared global PBR arrays.

### Per-biome PBR Texture2DArrays (one global stack per slot type)

For v1, just `pbr_ground_albedo_array` (one global Texture2DArray
with all loaded biomes as layers). v2 adds `_normal`, `_roughness`,
`_ao`. v3 adds mid + rock variants for the slope-blend.

ClipmapWorld at `_ready`:
- Scan `worlds/scale_v2/materials/` for biome subfolders that exist.
- Load each biome's `ground/albedo.png` into a fresh Texture2DArray
  layer.
- Record biome name → PBR layer index in `_biome_pbr_slot`.

Biomes referenced in the catalog but missing from disk get a
fallback debug color. Loud warning printed.

### Morph zone for splat

Same shape as heightmap morph. In the fragment shader:

```glsl
vec3 sample_albedo_at_ring(uv_world, ring_pbr_slots, this_ring_splat) {
    vec3 albedo = vec3(0);
    for (int i = 0; i < active_biomes_n; i++) {
        float w = texture(this_ring_splat, vec3(uv_world, i)).r;
        int pbr_layer = ring_pbr_slots[i];
        albedo += w * texture(pbr_ground_array, vec3(uv_local, pbr_layer)).rgb;
    }
    return albedo;
}

void fragment() {
    vec3 a_inner = sample_albedo_at_ring(...this ring's data...);
    if (morph_enabled) {
        vec3 a_outer = sample_albedo_at_ring(...coarse ring's data...);
        float m = compute_morph_factor(world_xz);
        ALBEDO = mix(a_inner, a_outer, m);
    } else {
        ALBEDO = a_inner;
    }
}
```

This is a real perf cost (2× the loop). The morph band is small (~10%
of ring extent), so it could be gated by an early-out `if m == 0`.
Will measure; default off-by-default for outer rings where the morph
band would barely show.

### Quality tier knobs (new this stage)

| Knob | Low | Medium | High | Ultra |
|---|---|---|---|---|
| `max_biomes_per_ring` | 4 | 6 | 10 | 16 |
| `splat_resolution_per_ring_m` | 4.0 | 2.0 | 1.0 | 0.5 |

(The second knob already exists from Stage 3 quality tiers but
finally gets consumed in Stage 4.)

## Implementation breakdown

Five sub-stages, each shippable independently:

**Stage 4.1 — Single-biome shading proof.**
Sample splat array + one biome's albedo. No biome blending yet. Just
prove the texture-array binding path works. Hardcode ring 0 to
biome "alpine" — render it correctly textured.

**Stage 4.2 — Biome culler + multi-biome shader loop.**
CPU culler picks top-N biomes; shader loop iterates and blends.
2-biome catalog (alpine + desert) renders with visible boundary
blending.

**Stage 4.3 — Morph zone for splat.**
Extends the heightmap morph pattern to splat. Adjacent rings agree
on biome blending at boundaries.

**Stage 4.4 — Hysteresis on culler.**
Sticky biome set. Test by walking fast across biome boundaries.

**Stage 4.5 — Per-biome PBR generation for scale_v2.**
Run the existing `pipeline/generate_biome_kits.py` on the scale_v2
biomes (alpine + desert). Shipped images get loaded by ClipmapWorld
at startup. (Defer mid+rock + slope-blend to a follow-up stage.)

## Validation

- Walk + topdown A/B captures at every sub-stage.
- Editor verification (PITFALLS #6b): user walks for 30s, reports
  what they see vs the captures.
- Headless test for the biome culler (`tests/test_biome_culler.py`)
  — given a `ring_bbox` + a known composer setup, asserts the right
  biomes are picked.
- Tier-knob tests for `max_biomes_per_ring` (extends existing tier
  test suite).
- No regression on quality-tier cross-impl test.

## Risks + mitigations

**Risk: splat regen hitches.** Each splat regen is one async worker
task + one main-thread Texture2DArray upload. Texture2DArrays
upload slower than 2D textures. Mitigation: profile at sub-stage 4.2;
if it hitches, drop splat resolution per ring or precompute the
slot weights at coarser resolution than the heightmap.

**Risk: GPU sampler count cap.** Some older GPUs limit total
sampler bindings per shader. Each per-biome PBR Texture2DArray is
one binding, but a 16-biome ring has 1 splat array + 1 ground PBR
array = 2 bindings (since PBR arrays are global, not per-biome).
Safe everywhere.

**Risk: missing biome textures.** Catalog references a biome whose
`materials/biome_<name>/ground/albedo.png` doesn't exist on disk.
Mitigation: ClipmapWorld scans at startup and falls back to a debug
color, prints a loud warning. Tier-knob: in dev mode, a missing
biome is a hard error; in release, falls back silently.

## Open questions resolved

- **Procedural per-ring vs pre-baked world splat**: per-ring (C). The
  world is unbounded by design.
- **Per-ring biome count**: tier-knob (`max_biomes_per_ring`), CPU
  culler picks which biomes occupy slots. Total world biomes
  unlimited.
- **Hysteresis**: yes, with sticky_threshold = 0.01 / threshold =
  0.05. Avoids churn on fast player movement.
- **Per-biome PBR slope blend (mid/rock)**: deferred to Stage 4.6
  or later. v1 ships ground-albedo only.

## Sub-stage ship order — separate plans per

Stage 4 is too large for one plan. This spec is the **architectural
contract** — the data flow, the morph extension, the tier knob, the
on-disk layout. Each sub-stage gets its own plan when its turn comes:

1. **Stage 4.1** (single biome rendering) → captures. **Next.**
2. **Stage 4.2** (multi-biome with culler) → captures + tests.
3. **Stage 4.5** (PBR generation for scale_v2's 2 biomes) — can run
   in parallel with 4.3-4.4 since it's a separate pipeline.
4. **Stage 4.3** (splat morph) → captures.
5. **Stage 4.4** (hysteresis) → behavior verified with fast-walk test.

Each sub-stage produces a working, editor-verifiable build. After
this spec is approved, the very next document is the **Stage 4.1
plan** alone — not a single mega-plan covering all five.
