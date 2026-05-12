# Morph zones — build notes

> Eliminates the elevation cliff at clipmap ring boundaries via
> two-texture heightmap blending in the vertex shader. Shipped
> 2026-05-12 on `main`. Commits `ea98d43`…`152b36a`.

## What shipped

| Task | Component | Commit |
|---|---|---|
| 1 | `morph_band_fraction` quality-tier knob + 2 unit tests | `ea98d43` |
| 2 | Shader uniforms + helpers; half-texel UV fix (PITFALLS #8) | `7d932f0` |
| 3 | Shader: morph blend in `vertex()` and `compute_normal()` | `c41fcee` |
| 4 | `ClipmapRing.set_coarse_uniforms()` API | `fdac0a8` |
| 5 | `ClipmapWorld` plumbs coarse uniforms (spawn + finalize) | `a56dcea` |
| 6 | `material_world_v3.tres` defaults for new uniforms | `d3de521` |
| 7 | A/B captures + `debug_disable_morph` toggle | `152b36a` |
| 8 | PITFALLS #11 + STATE refresh + this build-note | (this commit) |

**Test count:** 54 → 56 (2 new quality-tier tests pinning the new
`morph_band_fraction` knob).

**Visual delta:** see `captures/axis1_clipmap_morph_off_*.png` vs
`captures/axis1_clipmap_morph_on_*.png` for the A/B. The foreground
ring cliffs in the morph-off topdown are gone in the morph-on
topdown.

## The morph factor

Each non-outermost ring computes a per-fragment morph factor `m`:

```
center = ring_origin_m + ring_extent_m * 0.5
d = max(|world_xz - center|)          # Chebyshev
R = ring_extent_m * 0.5
band = ring_extent_m * 0.5 * morph_band_fraction
m = clamp((d - (R - band)) / band, 0.0, 1.0)
```

- `m = 0` in the ring's safe interior (`d < R - band`)
- `m = 1` at the ring's outer edge (`d = R`)
- Linear ramp between (not smoothstep — cheaper, visually
  indistinguishable for this band size)

Both vertex height AND fragment normal blend the same way:

```glsl
h = mix(h_inner, h_outer, m);
// for normals: mix each finite-difference sample identically
```

## Architecture

```
Worker thread: _compute_heightmap_floats
                ↓ PackedFloat32Array
Main thread: _finalize_ring_upload(ring i)
                ├──> ring i: set_displacement_texture, set_ring_uniforms,
                │            update_collision_heightmap
                └──> ring (i - 1).set_coarse_uniforms(this ring's data, true)
                    (skipped if i == 0; no inner ring exists)

Outermost ring (i = ring_count - 1):
    set_coarse_uniforms(null, ZERO, 1.0, 1, 0.0, false)
    once at _spawn_rings; never touched again. morph_enabled = false
    short-circuits the blend.
```

## Plan deviations

**One deviation worth flagging** (Task 7): the spec assumed the
`.tres` `morph_enabled` flag would be a sufficient on/off switch for
A/B capture. It wasn't — `ClipmapWorld._finalize_ring_upload` calls
`set_coarse_uniforms(..., enable_morph=true)` after every regen,
overwriting the `.tres` default. The A/B captures were identical until
I noticed.

Fixed by adding a `debug_disable_morph: bool` `@export` on
`ClipmapWorld` that propagates to the `enable_morph` argument. Four
dedicated capture scenes (`capture_clipmap_morph_{off,on}{,_topdown}.tscn`)
set the override in-scene so the comparison is reproducible without
file edits between runs. Bonus: the debug flag lets future-you toggle
morph from the inspector instead of digging in the .tres.

## Lessons + new pitfalls

- **PITFALLS #11 added** — Clipmap without morph zones. Linked from
  the `morph_band_fraction` knob description for future readers.
- **PITFALLS #8 finally fixed** — the half-texel UV offset was
  documented but not actually applied in the v3 shader. Corrected
  while touching the sampler.

## What's still visible (out of scope for this stage)

The morph captures still show:

- **Far-distance ridges / parallel banding** on outer rings. This is
  Stage 3.6 Issue 2 from the systematic-debugging pass — aliasing of
  fine kernel detail into coarse outer-ring heightmaps. Likely mostly
  hidden once Stage 4's biome PBR textures cover the surface. If
  still visible after that, revisit.
- **Dark hex blobs at the horizon**. Stage 3.6 Issue 3 — most likely
  worker-latency UV-out-of-range sampling returning 0. Explicitly
  deferred until after Stage 4 textures: if real PBR textures hide
  them, they were never a bug; if not, real bug.

## What's next

Stage 4 — clipmap splat + biome rendering. With cliffs eliminated,
biome-blending artifacts can be debugged independently. The
infrastructure is ready: the catalog already has 2 biomes; Axis 6's
world-splat pattern wires straight into the clipmap renderer.
