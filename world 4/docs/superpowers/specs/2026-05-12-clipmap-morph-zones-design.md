# Clipmap morph zones — design

Status: approved 2026-05-12, ready to plan.

## Why

Stage 3 of Axis 1 Path 2 shipped a working clipmap renderer: 4 nested
rings, each with its own kernel-derived heightmap texture, displaced
in the vertex shader. The user's first editor F6 shows the textbook
clipmap-without-morph artifact: a visible **elevation cliff** at every
ring boundary where the inner-ring heightmap (fine grid) disagrees
with the outer-ring heightmap (coarse grid) for the same world XZ.

This is not a bug — it's a missing feature. Clipmap rendering needs
morph zones (geomorphing) to converge adjacent rings smoothly at their
shared edge. Standard since GPU Gems 2.

Per project ethos (Quality ≥ Performance > anything > time), morph
zones land **before Stage 4 biome textures** so biome blending isn't
co-debugging with ring-mismatch artifacts.

## Scope

In: the math + shader changes that smooth adjacent-ring elevations in
a configurable boundary band; the per-ring shader-uniform plumbing in
`ClipmapWorld` and `ClipmapRing` to make this work; a quality-tier
knob exposing the morph-band width.

Out: morph for biome assignment (Stage 4 splat handles that with its
own blending), morph for collision (collision lives on inner rings
only, no boundary to morph), per-vertex LOD popping mitigation (a
related but separate technique — vertex skirts already buy us
horizon-edge resilience).

## Approach: heightmap morph (two-texture blend in vertex shader)

For each ring `i` other than the outermost, the vertex shader:

1. Samples this ring's heightmap at the vertex's world XZ → `h_inner`.
2. Samples the **next coarser ring's** heightmap (ring `i+1`) at the
   same world XZ → `h_outer`.
3. Computes a morph factor `m ∈ [0, 1]` that's 0 in the ring's
   interior and ramps to 1 inside a thin band near the ring's outer
   edge.
4. Uses `mix(h_inner, h_outer, m)` as the displacement.

At the precise ring boundary, `m = 1` → the inner ring's vertex
displaces using the outer ring's heightmap, which is exactly what the
outer ring renders at the same world XZ. The cliff converges to zero.

The outermost ring has no `h_outer` to blend toward; it uses
`h_inner` only.

### The morph factor

Let `d` be the Chebyshev distance from the ring's snap center to the
vertex (in world meters):

```
d = max(|world_xz.x - ring_center.x|, |world_xz.y - ring_center.y|)
```

Each ring has an outer half-extent `R = (grid_n - 1) * grid_step / 2`.
Define the morph band as the band `[R - W, R]` where `W` is the band
width in meters. Then:

```
m = clamp((d - (R - W)) / W, 0.0, 1.0)
```

Vertices inside the safe zone (`d < R - W`) get `m = 0` (no morph,
full inner heightmap). Vertices at the very edge (`d = R`) get
`m = 1` (full outer heightmap).

We use linear (not smoothstep). Reasons: morph zones are visually
subtle to begin with; the linear taper costs one mul-add vs
smoothstep's two mul-adds + cube; the visible difference between
linear and smoothstep is minor compared to the difference between
morphed and unmorphed. If during sign-off we observe visible faceting
at the morph band edges we'll swap to smoothstep — but starting
linear.

### Band width `W`

Wide enough that the morph is gradual but narrow enough not to lose
detail across most of the ring. Standard practice: roughly **5–15%
of the ring's outer extent**. For a ring with `R = 254m`, that's
12–38m. We tier this:

| Tier | `morph_band_fraction` |
|---|---|
| Low | 0.20 (wider = more averaging = cheaper to render acceptably) |
| Medium | 0.12 |
| High | 0.10 |
| Ultra | 0.08 (narrowest = most detail visible) |

Each ring's actual band width in meters is `R * morph_band_fraction`.

## Implementation

### Plumbing

`ClipmapRing.gd` already accepts a per-ring shader material with
displacement texture + ring uniforms. The morph addition needs each
non-outermost ring to also bind:

- `coarse_displacement` (sampler2D) — the next-coarser ring's heightmap
- `coarse_origin_m` (vec2) — that ring's world-XZ origin
- `coarse_extent_m` (float) — that ring's extent in meters
- `coarse_texel_n` (int) — that ring's texel resolution
- `morph_band_m` (float) — this ring's morph band width in meters

`ClipmapWorld.gd` needs to track which texture belongs to which ring
and update the coarse-side uniforms each time the **coarse ring's**
heightmap changes (not just this ring's). When ring `i+1` regenerates,
ring `i`'s coarse-side uniforms must also update.

Easiest: in `_finalize_ring_upload(ring)`, also push this ring's
texture+origin+extent as the *coarse* inputs of `ring_index - 1` (if
it exists). One ring upload triggers up to two ring material updates.

### Shader changes (`terrain_world_v3.gdshader`)

New uniforms:

```glsl
uniform sampler2D coarse_displacement : filter_linear, repeat_disable, hint_default_black;
uniform vec2 coarse_origin_m = vec2(0.0, 0.0);
uniform float coarse_extent_m = 1024.0;
uniform int coarse_texel_n = 128;
uniform float morph_band_m = 25.0;

uniform bool morph_enabled = true; // toggle for debug A/B
```

New helper:

```glsl
float sample_coarse_height(vec2 world_xz) {
    float n = float(coarse_texel_n);
    float extent_n = coarse_extent_m * n / max(n - 1.0, 1.0);
    vec2 uv = (world_xz - coarse_origin_m) / extent_n + (0.5 / n);
    float h = texture(coarse_displacement, uv).r;
    return (isnan(h) || isinf(h)) ? 0.0 : h;
}

float compute_morph_factor(vec2 world_xz) {
    // Chebyshev distance from this ring's snap center. ring_origin_m
    // is the ring's lower-left in world XZ; the ring center is
    // origin + extent/2.
    vec2 center = ring_origin_m + vec2(ring_extent_m * 0.5);
    vec2 d_xz = abs(world_xz - center);
    float d = max(d_xz.x, d_xz.y);
    float R = ring_extent_m * 0.5;
    return clamp((d - (R - morph_band_m)) / max(morph_band_m, 1e-6), 0.0, 1.0);
}
```

`vertex()` becomes:

```glsl
void vertex() {
    vec3 model_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    float h_inner = sample_height(model_world.xz);
    float h;
    if (morph_enabled) {
        float h_outer = sample_coarse_height(model_world.xz);
        float m = compute_morph_factor(model_world.xz);
        h = mix(h_inner, h_outer, m);
    } else {
        h = h_inner;
    }
    VERTEX.y += h;
    v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}
```

The fragment-shader normal computation (`compute_normal`) also needs
to morph, otherwise the surface lights match the inner heightmap even
as it geometrically morphs toward the outer. For Stage 4 readiness,
do the same morph blend in `compute_normal` — sample both
heightmaps' normals (finite-difference each) and blend by the same
factor.

Half-texel UV correction (PITFALLS #8): use
`(world_xz - origin) / extent_n + (0.5 / n)` for both samplers. The
v3 shader is *missing* the `+ 0.5/n` term currently — fix
opportunistically since we're touching the sampler anyway.

### Quality tier knob

Add `morph_band_fraction` to `config/quality_tiers.json` per the
table above. Update `KNOWN_KEYS` in `pipeline/quality_tiers.py` and
`tests/test_quality_tiers.py`'s `test_resolve_values_sane` to pin the
range `[0.0, 0.5]`. The new knob is a float; no GDScript int-coercion
needed.

`ClipmapWorld._spawn_rings` consumes the knob: each ring's
`morph_band_m = (grid_n - 1) * grid_step_m / 2 * morph_band_fraction`.

### Edge cases

- **Outermost ring**: no coarse texture to morph toward. Set
  `morph_enabled = false` on the outermost ring's per-ring material
  duplicate, or bind a transparent dummy texture and a `morph_band_m
  = 0` to bypass via the clamp.
- **Innermost ring**: gets the morph, but its outer boundary is the
  inner-edge of ring 1. The morph blends ring 0's fine heightmap
  toward ring 1's coarser heightmap. Correct behavior.
- **Async lag**: if ring `i+1` regenerates AFTER ring `i` has bound
  `i+1`'s old texture as `coarse_displacement`, the morph blends
  against stale data for one or two frames until `i`'s coarse uniforms
  refresh. Acceptable — visible only as a tiny smear at boundaries
  for a sub-second window.
- **Skirts**: skirt vertices live just inside the ring's outer edge
  (or inner edge on the inner skirt). Outer-edge skirts get morphed
  to coarse heightmap — desirable, hides the world rim. Inner-edge
  skirts are inside the morph-safe zone, get the inner heightmap
  only — also desirable.

## Validation

- Visual: walk + topdown captures of `scenes/clipmap_debug.tscn`
  with morph on/off (via `morph_enabled` uniform). Cliff should be
  gone with morph on, present with morph off. A/B captures committed
  to `captures/`.
- Test: a Python test that resolves each tier and asserts the
  `morph_band_fraction` knob lands in `[0.0, 0.5]` (extending
  `test_resolve_values_sane`).
- No new pytest unit needed for the shader math — it's pure GLSL
  with no Godot-side branching. Visual sign-off is the gate.

## Implementation order (handed off to writing-plans)

1. Add `morph_band_fraction` to JSON tier config (Low/Medium/High/Ultra).
   Update `KNOWN_KEYS`, sanity test.
2. Shader: add the morph uniforms + `sample_coarse_height` helper +
   `compute_morph_factor`. Update `vertex()` and `compute_normal()` to
   blend inner/coarse. Fix the half-texel offset (PITFALLS #8) while
   touching the sampler.
3. `ClipmapRing.set_ring_uniforms` extended to also accept the coarse
   inputs (or new `set_coarse_uniforms`).
4. `ClipmapWorld._finalize_ring_upload` pushes this ring's data as the
   coarse-inputs of ring (i-1).
5. `ClipmapWorld._spawn_rings` reads `morph_band_fraction` from tier;
   sets `morph_band_m` on each ring; disables morph on the outermost
   ring; binds an empty/dummy coarse texture on the outermost ring.
6. Walk + topdown A/B captures. PITFALLS update for the new
   "missing morph zone" entry.
7. Build-note + STATE refresh.
