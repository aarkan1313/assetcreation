# Phase F course correction — M11 fourway architecture

> User flagged 2026-05-11: "I know for a fact in M1-M18 we had a lava
> field + phototopo + normal texture meeting in a 4-way and it
> matched up and looked good." That's correct, and reading
> `build_m11_fourway_corner_proof.py` reveals the **architecture
> Phase F has been getting wrong**.

## The lesson

M11 fourway built **one bundle containing four materials**, blended
via a per-pixel splat-weight image. F.7 has been doing the opposite —
one biome per bundle, then gluing bundles together at runtime — and
that's why my multi-bundle world looked like garbage compared to a
single M11 fourway scene that already shipped weeks ago.

## How M11 fourway actually works

`world3/pipeline/build_m11_fourway_corner_proof.py` produces:

- **One bundle** at `world3/toporeview/m11_fourway_corner_proof/`
  with a single `heightmap.png`, a single macro `render_albedo.png`,
  and a single splat-weights image `layers/splat_weights_rgba.png`
  where the four channels carry per-material weights
- **One shader material** `terrain_m11_fourway_corner.tres` (built
  on `terrain_splat_unified.gdshader`) with all four textures bound
  to the shader's `grass / dirt / rock_light / rock_dark` slots
- **A scatter mask sidecar** with per-domain weight fields

The shader at runtime samples the splat-weights image per pixel,
multiplies each channel by its bound material, and produces a
seamless blend across the bundle interior. Where two materials
meet, the splat weights crossfade smoothly. No bundle boundaries
exist between materials because **all four materials live in one
bundle**.

## How my Phase F has been doing it

`world_plan_to_bundles.py` emits **one bundle per tile**, each tile
bound to **one biome** with one primary material. Adjacent tiles
have independent ShaderMaterial instances and the only "blend"
between them is whatever happens at runtime where their meshes
meet — which is nothing, hence the hard seams.

This was a reasonable first design but it misses the M11 lesson:
**a single Godot shader material can carry many textures + a splat
weight image, and that's where seam-blending naturally lives**.

## The right architecture for Phase F

There are two valid paths and they aren't mutually exclusive:

### Path A: "Bundle is multi-material" (M11 pattern, scaled up)

A bundle's region rect can contain N biomes. Build a single
splat-weights image where channel weights encode which material
dominates at each pixel. One shader material per bundle binds N
material slots + the splat weights. Bundles can be large (e.g. a
full 5 km × 5 km world is one bundle).

**Pros**: Seam blending is per-pixel and free at runtime. Already
proven by M11. One bundle = the entire visible world.

**Cons**: Huge memory footprint at high resolution. Loses the "tile
in / tile out" streaming property. Limited to the shader's bound-slot
count (4 in M11; could be ~8 in a custom shader).

### Path B: "Tile grid with shared shader" (proper streaming)

Keep one bundle per tile, BUT every tile uses **the same shader
material instance** (or a small number of biome-kit-level material
instances). Per-tile differences live in textures the shader samples
by world position — heightmap, macro, splat weights — not in
per-tile ShaderMaterial duplicates.

The key insight: the shader's `splat_weights` texture can be
*sampled by world UV*, meaning each tile contributes its slice of
the splat-weights data. At a tile boundary, the splat weights
crossfade between this tile's primary biome and the neighbor's
primary biome (because the iterator wrote them to crossfade in the
boundary band, similar to F.3.1's heightmap edge constraints).

**Pros**: Keeps streaming. Per-tile compute stays bounded. Seam
blending happens via shader interpolation across world-UV. Adds an
F.3.2 "build per-tile splat weights with neighbor crossfade" step.

**Cons**: More work. Requires teaching `build_procedural_neighbor_bundle.py`
to emit a splat-weights image instead of just an albedo, AND
teaching the iterator to crossfade splat weights at boundaries
like it crossfades heightmaps in F.3.1.

## My recommendation

**Path B with M11 as the reference**. The pattern matches everything
we've built in Phase F already:

- F.3 plan → bundles iterator stays
- F.3.1 heightmap edge constraints stay
- **F.3.2 (new)**: per-bundle splat weights, with neighbor crossfade
  at boundaries — same pattern as F.3.1 but for splat channels
  instead of height
- F.7 streamer stays (still loads multiple bundles), but bundles now
  have shared shader material so adjacent bundles blend seamlessly
- F.7.1 followups (per-biome material templates, sRGB texture binding)
  become trivial because all bundles share one material per biome-kit

## What needs to change in code

1. **`build_procedural_neighbor_bundle.py`** — emit a `splat_weights_rgba.png`
   where channels encode this bundle's biome assignment. For a
   pure single-biome bundle, channel 0 = 1.0 everywhere. For a
   boundary bundle (crossfade with east neighbor), channel 0 fades
   from 1.0 at west to 0.0 at east; channel 1 (neighbor's biome)
   fades inversely.

2. **`world_plan_to_bundles.py`** — when iterating, look at each
   tile's W/N/E/S neighbors' biomes. Inject the boundary crossfade
   recipe into each tile's source args. Each tile knows which 1-4
   biome materials it needs to bind.

3. **Per-biome-kit shared shader material template** — pre-author
   `terrain_starter_<kit>.tres` (one per biome kit) that uses
   `terrain_splat_unified.gdshader` with the kit's primary +
   secondary materials bound. The streamer picks the right one per
   bundle. Multi-biome boundary bundles get a per-biome-pair
   variant: `terrain_starter_<kit_a>__<kit_b>.tres`.

4. **`MultiBundleStreamer.gd`** — instead of duplicating ShaderMaterial
   per bundle and binding macro/mask textures, just point each
   ChunkLoader at the right shared material instance and let the
   shader's world-UV splat sampling handle it.

## What this means for the work already shipped

Most of F-phase is fine:
- F.1, F.2, F.3, F.4, F.5, F.6, F.8 → unaffected
- **F.3.1 heightmap edge constraints**: still correct, still needed
- **F.7 streaming director**: architecture is right, but the bundles
  it consumes need F.3.2 to be visually correct

The wasted-work item: my **per-bundle ShaderMaterial duplication +
runtime texture binding** logic in `MultiBundleStreamer.gd` (the
`_load_srgb_texture` path, the manual macro/mask shader param sets)
becomes unnecessary once bundles share a material. That's maybe 100
lines that get deleted in F.3.2.

The valuable insight earned: **the underworld + wavy-color disaster
is what told us we were doing it wrong**. Better to find this now
at F.7 than after building Phase G on top of it.

## Status

This is a course correction, not a phase. The work plan becomes:

- [x] Identify the M11 lesson (this doc)
- [ ] F.3.2 — Per-bundle splat weights with neighbor crossfade
- [ ] F.7 re-validate with proper shared materials
- [ ] F.7.1 retired (its problems become moot)

## Cross-references

- M11 fourway reference: [M11_FOURWAY_CORNER_PROOF_2026_05_10.md](M11_FOURWAY_CORNER_PROOF_2026_05_10.md)
- M11 builder: `world3/pipeline/build_m11_fourway_corner_proof.py`
- M11 material: `world3/textures/wgv3/terrain_m11_fourway_corner.tres`
- Shader: `world3/shaders/terrain_splat_unified.gdshader`
- Phase F charter: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
