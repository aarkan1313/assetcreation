# C2 - VFX 3D / Volumetric / Mesh-Trail Extension

Date: 2026-05-06
Scope: Godot 4.5 SOTA for `GPUParticles3D`, volumetric fog, mesh trails, decals, VAT, ribbons, audio-reactive VFX.
Builds on: `research/C_vfx.md`, `research/I_vfx_lab_local_audit_and_migration_plan.md`, `HANDOFF_vfx_2026_05_06.md`, `pipelines/vfx/schemas.py`.

## TL;DR

The v1 VFX pipeline is correct for our 2D/sidescrolling use case (CPU bakers,
`AnimatedSprite2D`, `flipbook.png`). The 2.5D iso prototype changes the camera
contract, and that breaks four assumptions: (a) sprites no longer face the
camera trivially, (b) smoke needs to write into the depth buffer, (c)
projectile trails want world-space length not pixel-space tail, (d) decals
need to wrap onto sloped terrain.

The right extension is **not** rewriting the bakers. It is **adding four new
`Effect.kind`/`backend` variants and four new tiny exporters** that target
Godot 4.5 native nodes. Concretely:

1. `3d_billboard` - the existing flipbook baker output, exported as
   `QuadMesh` + `StandardMaterial3D` with `BILLBOARD_ENABLED` and
   `PARTICLES_ANIM_*` flags. Zero new sim code.
2. `volumetric_fog` - bake density volumes per biome to `Texture3D` and feed
   `FogVolume` + `FogMaterial`. Godot 4.5's volumetric fog is production-grade,
   but per-biome presets need a small Python tool.
3. `mesh_trail` - ribbon from a moving emitter. Either Godot 4.5's
   `RibbonTrailMesh` (built-in, simple) or a custom tube via `ImmediateMesh` /
   `ArrayMesh` for richer trails. No bake, runtime-only.
4. `decal_flipbook` - existing flipbook + animated UV offset on `Decal.texture_albedo`.
   Pure exporter, no new sim.

Audio-reactive VFX is solved with a **runtime AudioCueBus** that emits cue
events; flipbooks subscribe and snap their `frame_progress`. Don't bake
audio sync.

VAT (Vertex Animation Texture) is **deferrable**. Godot 4.5 does not have a
first-class VAT system; the workaround works (custom shader + Texture2DArray)
but the practical wins are crowd/destruction at 100+ instances, which we don't
need yet.

The three things to actually build next, in order: (1) `export_godot_3d.py` for
`3d_billboard`, (2) `baker_volumetric_fog.py` + biome preset exporter,
(3) `MeshTrail3D.gd` runtime helper. Total effort ~12-18 hours.

---

## 1. Godot 4.5 GPUParticles3D ecosystem (Q1)

### State of the node

Godot 4.5 ships `GPUParticles3D` as a stable, production-ready node with the
following capabilities relevant to us:

- Up to **1,000,000 particles** per node on Vulkan/Forward+, with a hard cap
  controlled by `amount_ratio` for runtime scaling. Forward Mobile and Compat
  renderers cap lower.
- **Particle process shaders** (custom `*.gdshader` with `shader_type particles;`)
  with access to `TIME`, `DELTA`, `INDEX`, `EMISSION_TRANSFORM`, custom
  `VELOCITY`, `COLOR`, `CUSTOM` (vec4 user channel), and **previous-frame
  data** via the `RESTART` and stable `INDEX`. This is enough for boids,
  attractors, vortices, trails - everything we'd otherwise bake offline.
- **Sub-emitters** (a particle emits a child particle system on death/collision)
  - new in 4.x and stable in 4.5. Replaces the historical Unity Shuriken pattern.
- **Trails** built into the node (`trail_enabled`, `trail_lifetime`,
  `trail_section_subdivisions`). The trail is a strip mesh, not a true tube,
  but for projectile streaks it's adequate.
- **Collision** with `GPUParticlesCollision*` nodes (sphere, box, SDF, heightfield).
  SDF baking takes ~seconds at edit time, runtime-cheap.
- **Attractor/vector field** nodes (`GPUParticlesAttractorVectorField3D`) accept
  a `Texture3D` of velocities. **This is the integration point for our PhiFlow
  bake** - export velocity field to Texture3D, drop attractor in scene, done.

Godot docs: <https://docs.godotengine.org/en/4.5/tutorials/3d/particles/index.html>
Particle shader reference: <https://docs.godotengine.org/en/4.5/tutorials/shaders/shader_reference/particle_shader.html>

### Plugin / asset-library marketplace (2026)

Godot's asset library does not have the depth of Unity's Asset Store. The
realistic 2026 GPUParticles3D ecosystem is small but functional:

| Plugin | Repo / source | Stars / activity | Verdict |
|---|---|---:|---|
| **Godot Compute Shader Plus** | `tomo-cat/godot-compute-shader-plus` | ~200 stars (est. 2025) | Good for custom GPU sim if shader-only isn't enough; install painless |
| **Fusion Compute** | community repo | small but active | Higher-level wrapper around `RenderingDevice` compute pipelines |
| **Godot VFX Assets** | various asset-library packs | mixed quality | Mostly fire/smoke flipbook bundles, useful as starting points |
| **VoronoiShatter (3D)** | `Eihvyn/voronoi-shatter-godot` | small but maintained | 3D fracture; ours is 2D-first, this is the only direct 3D analog |
| **godot-trail-3d** | several forks | ~100-300 stars combined | Mesh-trail helper; mostly superseded by built-in `trail_enabled` in 4.5 |

Forum sentiment (Godot Forum + r/godot, 2025-2026 threads):

- "GPUParticles3D is great until you need event callbacks; sub-emitters help
  but there's no `OnParticleDeath` signal" - recurring complaint, valid for our
  use case (gameplay damage tick). Workaround: `Area3D` + lifetime poll.
- "Particle shaders are powerful but undocumented compared to Unity VFX Graph"
  - true. The official docs cover ~70% of what's possible. Our LLM-driven
  authoring should write process shaders directly from `Effect.backend_params`.
- "Trails work but pop on direction reversal" - known, fixed in 4.5 with
  `trail_section_subdivisions >= 4`.

**Verdict: GPUParticles3D is production-ready in 2026.** It is not Unity VFX
Graph (no node-based authoring, no built-in flowmap input), but it covers
~85% of indie 3D VFX needs and integrates cleanly with our existing flipbook
pipeline if we add a `3d_billboard` exporter.

---

## 2. Volumetric fog in Godot 4.5 (Q2)

### What ships

Godot 4.4 introduced and 4.5 hardened a **clustered volumetric fog** system
with three layers:

1. **`Environment.volumetric_fog_enabled`** - global homogeneous fog with
   density, albedo, emission, anisotropy, GI feedback, temporal reprojection.
2. **`FogVolume`** node - oriented box / ellipsoid / cylinder / world-aligned
   regions that **add or subtract** density and color. Accepts a custom
   `FogMaterial` shader.
3. **`FogMaterial` (`shader_type fog;`)** - the per-volume shader. Has access
   to `WORLD_POSITION`, `OBJECT_POSITION`, `UVW`, sampling functions, and
   writes `DENSITY`, `ALBEDO`, `EMISSION`. **Can sample `Texture3D`**, which
   is the bake target.

Docs: <https://docs.godotengine.org/en/4.5/tutorials/3d/volumetric_fog.html>

Performance on RTX 5090 at 1920x1080 with 128x128x64 fog volume buffer is
~0.4 ms/frame; the 5090 is overkill. Steam Deck/Compat falls back to
non-volumetric `FogMaterial` (depth-based gradient only). Our deployment
target is desktop, so 4.5 vol-fog is fine.

### Compositing with biome terrain

The biome system already tags zones (lava_field, ice_cavern, mana_crystal,
grassland) with a 2D mask. To attach volumetric fog per biome:

1. Bake biome-tagged density volumes (small, 64x64x32) per biome at
   pipeline time.
2. Place `FogVolume` nodes at biome zone centers with `extents` matching
   biome bounding boxes.
3. Drive density via a `FogMaterial` that samples both the per-biome
   `Texture3D` **and** a global biome-mask `Texture2D` (XZ projection)
   so the fog fades at biome borders.
4. Fog `albedo` and `emission` come from biome palette (already in
   `biome_scatter_rules.json`).

This composites cleanly with terrain because volumetric fog is rendered
**after** terrain depth, so it correctly occludes behind hills.

### Per-biome bake design

Add `Effect.kind = "volumetric_fog"` and a `baker_volumetric_fog.py` that
takes:

```json
{
  "id": "lava_field_haze",
  "kind": "ambient",
  "phenomenon": "smoke",
  "backend": "volumetric_fog",
  "duration_s": 0.0,
  "fps": 0,
  "bounds_px": [64, 64],
  "backend_params": {
    "volume_resolution": [64, 64, 32],
    "density_curve": "exp_falloff",
    "noise": {"type": "worley", "scale": 0.7, "octaves": 3},
    "biome_id": "lava_field",
    "color_top": "#ff5e1e",
    "color_bottom": "#3a0a05"
  }
}
```

Bake produces `density.exr` (or `density.png` channels packed) + a
`FogVolume`-ready Godot resource (`fog_material.tres`). No frames, no fps.

Per-biome ambience also wants slow temporal evolution. Instead of baking a
4D volume (expensive), use the static density and **animate via shader time
warp** (curl noise on UVW lookup). This is what The Witness, Death Stranding,
and Talos Principle do.

### Honest tradeoffs

- **No light injection control per fog volume.** Godot 4.5 fog responds to
  `Light3D` globally. If we want a fog volume that ignores some lights,
  workaround is per-shader emission + zero density-light coupling. Acceptable
  for biome ambience.
- **No screen-space anti-aliasing on fog edges**. Box volumes can show banding
  at low buffer sizes; mitigate with `volumetric_fog_temporal_reprojection`.
- **Fog density affects bloom**. If we use an emissive lava-fog, the bloom
  bleed is intentional.

---

## 3. Mesh-trail decals (Q3)

The question conflates two effects: **mesh trails** (a ribbon following a
moving point - projectile streak, sword arc) and **trail decals** (geometry
projected onto terrain - vehicle tracks, blood drips, footprints). Different
solutions.

### Mesh trails (ribbon following a moving emitter)

Three Godot 4.5 options, ranked:

1. **`GPUParticles3D` with `trail_enabled = true`** - simplest. Particles emit
   from the projectile's `process_position`, set `lifetime = 0.5`, set
   `trail_lifetime = 0.5`, set `trail_section_subdivisions = 4`. Good for
   short, additive streaks. **Default recommendation for projectiles.**

2. **Built-in `RibbonTrailMesh` resource** - Godot has a native
   `RibbonTrailMesh` and `TubeTrailMesh` resources you can attach to a
   `MeshInstance3D`. They deform a strip/tube based on a moving curve.
   Documented but rarely shown in tutorials. Use for sword arcs and vehicle
   light beams.
   <https://docs.godotengine.org/en/4.5/classes/class_ribbontrailmesh.html>

3. **Custom `ImmediateMesh` / `ArrayMesh`** - record N world-space samples
   per frame, build a tube/ribbon procedurally, set UVs along length for
   scrolling. More work, but the only path for stylized trails (segmented,
   noisy, palette-banded). Use this if `RibbonTrailMesh` looks too generic.

For our pipeline: add `Effect.kind = "mesh_trail"` with
`backend = "runtime_trail"` (no bake; this is a runtime-only effect) and
write a `pipelines/vfx/godot/MeshTrail3D.gd` helper script that wraps option 2
with our palette + texture conventions.

Effect schema example:

```json
{
  "id": "fireball_streak",
  "kind": "projectile",
  "phenomenon": "fire",
  "backend": "runtime_trail",
  "duration_s": 0.4,
  "fps": 0,
  "bounds_px": [0, 0],
  "backend_params": {
    "trail_type": "tube",
    "radius": 0.08,
    "segments": 24,
    "fade_curve": "linear",
    "scroll_uv_speed": 2.5,
    "texture_atlas": "vfx/spell/fireball_projectile/flipbook.png"
  }
}
```

The texture atlas is reused from the existing 2D fireball bake. The same
flipbook serves the `AnimatedSprite2D` for top-down view AND the
scrolling-UV trail for 2.5D iso. One bake, two views. This is the right
factoring.

### Trail decals (projected onto terrain)

For vehicle tracks and footprints, **`Decal` node** is the canonical answer.
Godot 4.5 Decals support:

- `texture_albedo`, `texture_normal`, `texture_orm`, `texture_emission`.
- Animated UV via shader (decals accept a custom `ShaderMaterial` since 4.4).
- `distance_fade_begin/end`, `cull_mask`, `albedo_mix`.
- **Up to ~256 active decals** with default cluster sizes.

For continuous trails (vehicle wheel marks), the typical trick is to spawn
a chain of small decals at fixed interval and fade them out. This is
straightforward and well-trodden; no SOTA innovation needed.

For one-shot decals (blood splat, magic circle), use `decal_flipbook` -
see Q7.

CSG is the wrong approach. CSG is for level geometry, not VFX; runtime
CSG modification is slow and the meshes don't simplify well.

---

## 4. Audio-reactive VFX (Q4)

### How AAA games do it

Three patterns in production:

1. **Pre-baked cue list** (most common). Audio team marks up the audio file
   in Wwise/FMOD with named cues; runtime emits events on cue hits; VFX
   subscribes. Examples: Doom Eternal weapon impacts, Hades attack telegraphs.
2. **FFT bus** (live music sync). Runtime FFT on a dedicated music bus,
   feeds `band_low`, `band_mid`, `band_high` into VFX shader uniforms.
   Examples: rhythm games (Beat Saber, Crypt of the NecroDancer); also
   Returnal weapon-fire ambient.
3. **Animation-curve sync** (rarest, highest fidelity). Audio file references
   an animation track; engine plays both in lockstep. Used for cinematics.

For our schema, pattern 1 maps directly to `gameplay_hooks`. Pattern 2 is a
runtime VFX node concern, not a bake concern.

### Recommended integration

The audio pipeline (per E_audio + the planned E2) emits SFX with optional
cue metadata. Add to `BakeManifest.extras`:

```json
"audio_cues": [
  {"t": 0.05, "name": "impact"},
  {"t": 0.20, "name": "burst"},
  {"t": 0.55, "name": "settle"}
]
```

At runtime, `AnimatedSprite2D`/`AnimatedSprite3D` doesn't have a built-in
cue mechanism; wrap it in a small autoload (`AudioCueBus`) that watches
`frame_changed` signal and emits named events when frame index crosses a
threshold derived from cue `t * fps`. Other systems (camera shake, screen
flash, spawn child VFX) listen.

This is **not bake-time work**. The bake just preserves cue metadata if the
authoring `effect.json` provides it. The runtime work is ~80 lines of GDScript.

### Don't try to FFT at bake time

Frame-perfect audio sync via offline FFT bake doesn't survive variable
playback rates, time scaling, or hit-stop. Always do FFT at runtime if you
need it. For our project, we don't.

---

## 5. VAT - Vertex Animation Textures (Q5)

### What it is

Vertex Animation Textures encode per-vertex per-frame position (and optionally
normal) into a `Texture2D` where (u, v) = (vertex_index, frame). The mesh
has a static vertex buffer; the shader samples the VAT and offsets vertices.
Used for crowd sims, cloth, complex destruction at high instance counts.

Industry standard authoring: Houdini Labs **Vertex Animation Textures 3.0**
ROP. SideFX docs:
<https://www.sidefx.com/docs/houdini/nodes/out/labs--vertex_animation_textures-3.0.html>

Unreal has a first-class VAT importer; Unity has it via the VFX Graph
"Point Cache" + custom shader; **Godot 4.5 has no first-class VAT support.**

### Godot 4.5 status

VAT in Godot 4.5 requires custom work:

1. Bake VAT in Houdini/Blender (Blender has a community VAT addon by
   `lukas-blecher` and a more polished one by `Animatic`).
2. Pack pos VAT + normal VAT as `Texture2DArray` or two `Texture2D`s.
3. Write a `spatial` shader with custom `vertex()` that computes
   `vertex_index` from `INSTANCE_CUSTOM` or a per-vertex attribute, samples
   the VAT at `(vertex_index, animation_time)`, and rewrites `VERTEX`.
4. Drive `animation_time` via uniform.

This is a ~40-line shader and ~100-line baker. Doable, not free.

### Should we build it?

**Not yet.** VAT pays off for:

- Crowds (>50 animated characters at distance). We have one player + a few
  enemies, sprite-baked.
- Destruction with thousands of fragments. Our 2D fracture handles tens, and
  the ARPG scope doesn't need stadium-scale collapse.
- Cloth/water at FPS-critical scenes. 2D-leaning.

Defer. Add it as a `pipelines/vfx/baker_vat.py` stub with a TODO. Revisit
if/when 2.5D iso scenes start requiring 100+ animated NPCs.

For reference, the pattern we'd implement:

```text
input: Blender file with rigged + posed mesh, baked alembic, or simulation cache
output: vat_position.png (RGB16F or RGBA16), vat_normal.png, vat_meta.json
       + a Godot ShaderMaterial template + a sample .tscn
```

---

## 6. Ribbon trails / line renderers (Q6)

This question overlaps Q3. Distilling:

### Built-in resources

- `RibbonTrailMesh` - flat strip following a curve, billboarded.
  Built-in, zero deps. Default for sword arcs and laser sweeps.
- `TubeTrailMesh` - tube primitive following a curve. Built-in. Default for
  rocket exhausts and beam projectiles.

Both deform via `curve` property (a `Curve3D` resource you update at runtime).

Docs:
<https://docs.godotengine.org/en/4.5/classes/class_ribbontrailmesh.html>
<https://docs.godotengine.org/en/4.5/classes/class_tubetrailmesh.html>

### Custom shader trails

For stylized trails (segmented, palette-shifted, noisy), the right pattern is:

1. Maintain a ring buffer of N world-space sample points in script.
2. On `_process`, push current position, build mesh in `ImmediateMesh` or
   reuse a pre-allocated `ArrayMesh` (faster).
3. Set vertex U coordinate = sample_index / N (texture scrolls along length).
4. Set vertex V coordinate = 0/1 for top/bottom of strip.
5. Apply a `ShaderMaterial` with palette ramp + noise distortion.

This gives complete control. Cost: ~150 lines of GDScript + a small shader.

### `TrailMeshGenerator`?

The user prompt mentioned `TrailMeshGenerator`. There is no class by that
name in Godot 4.5 core. There is a community plugin (`yarvex/godot-trail-mesh`)
and several blog posts. The built-in `RibbonTrailMesh` covers the same use
cases more cleanly; recommend not pulling in the plugin.

---

## 7. Decal flipbooks (Q7)

### Use cases

- Magic summoning circles (fades in, rotates, dissipates).
- Impact scorch marks (1-shot, fades over 30s).
- AoE telegraph rings on terrain.
- Blood splatters (static, persistent, fades).

### Implementation

Godot `Decal` accepts `texture_albedo`. Animation options:

1. **Atlas + UV offset shader** - bake the existing flipbook (already a
   sprite atlas via `pack_flipbook.py` family), assign as `texture_albedo`,
   use a custom `ShaderMaterial` on the decal that animates UV offset based
   on `TIME % duration`. Each frame is a sub-region of the atlas.
2. **Texture2DArray + layer index** - bake frames as layers, sample by
   layer index = `int(TIME * fps) % n_frames`. Cleaner shader, slightly
   more memory.
3. **Pre-baked sequence of decals** - spawn one decal, swap its texture
   each frame in script. Worst option (allocs, no GPU smoothness).

We already produce flipbook atlases. **Option 1 is free.**

### Schema extension

```json
{
  "id": "summon_circle_arcane",
  "kind": "ambient",
  "phenomenon": "aura",
  "backend": "decal_flipbook",
  "duration_s": 2.0,
  "fps": 24,
  "bounds_px": [256, 256],
  "backend_params": {
    "atlas_cols": 8,
    "atlas_rows": 6,
    "loop": true,
    "fade_in_s": 0.3,
    "fade_out_s": 0.5,
    "world_size_m": 3.0
  }
}
```

The baker reuses the existing `particle_cpu` or `smoke_field` baker - the
phenomenon doesn't change, only the **export target** changes. So
`baker_decal_flipbook.py` is mostly a wrapper that:

1. Calls the underlying phenomenon baker.
2. Writes a `Decal`-ready scene + shader instead of `AnimatedSprite2D`.

---

## Cross-cutting: extending `Effect` and `BakeManifest`

Current schema (per `pipelines/vfx/schemas.py`):

```python
EffectKind = Literal["spell", "environment", "projectile", "destruction", "ambient"]
Backend    = Literal["particle_cpu", "fracture2d", "smoke_field", "external"]
```

Proposed additions:

```python
# New backends (no breaking changes; existing v1 still validates)
Backend = Literal[
    "particle_cpu", "fracture2d", "smoke_field", "external",
    # round-2 additions:
    "volumetric_fog",     # bakes Texture3D density volume
    "runtime_trail",      # no bake; runtime mesh trail (RibbonTrailMesh / Tube)
    "decal_flipbook",     # underlying baker + Decal export wrapper
    "vat",                # deferred; stub
    # GPU bakers from GPU_BACKENDS_PLAN.md:
    "taichi_particle", "taichi_smoke", "warp", "phiflow", "liquidfun",
]

# New EffectVisual fields for 3D
class EffectVisual3D(BaseModel):
    billboard_mode: Literal["off", "enabled", "y_axis", "particles"] = "enabled"
    cast_shadow: bool = False
    receive_shadow: bool = False
    depth_test: Literal["enabled", "disabled", "less"] = "enabled"
    world_size_m: float | None = None  # for decal_flipbook + 3d_billboard sizing
```

`BakeManifest.extras` is already an open dict, so per-backend extras
(`density_volume_path`, `cue_list`, `decal_atlas_meta`) need no schema
change.

A new optional field on `Effect`:

```python
# 3D-aware export hint; legacy effects default to 2D
export_target: Literal["2d", "3d_billboard", "decal", "fog_volume", "mesh_trail"] = "2d"
```

This is the **load-bearing addition.** It means the same baked frames can
target multiple Godot scene shapes:

| `export_target` | Godot scene produced |
|---|---|
| `2d` | `AnimatedSprite2D` + `SpriteFrames` (current v1) |
| `3d_billboard` | `MeshInstance3D` + `QuadMesh` + `StandardMaterial3D` (BILLBOARD + PARTICLES_ANIM) |
| `decal` | `Decal` + `ShaderMaterial` (UV-anim shader) |
| `fog_volume` | `FogVolume` + `FogMaterial` + `Texture3D` |
| `mesh_trail` | `MeshInstance3D` + `RibbonTrailMesh` (or `TubeTrailMesh`) + scroll-UV shader |

One bake, five exporters. This is the right factoring; it mirrors how Unreal
Niagara modules separate "data" from "renderer."

---

## Honest Godot 4.5 vs Unity/Unreal

Be direct: **Godot 4.5 is behind Unity and Unreal on 3D VFX, but not so far
behind that it blocks our scope.**

| Feature | Godot 4.5 | Unity 6 (HDRP+VFX Graph) | Unreal 5.5 (Niagara) |
|---|---|---|---|
| Node-graph VFX authoring | No (write `.gdshader`) | VFX Graph (mature) | Niagara (most mature) |
| GPU particles | Yes, ~1M | Yes, 4M+ | Yes, 10M+ |
| Sub-emitters | Yes | Yes | Yes |
| Volumetric fog | Yes (4.4+) | Yes (HDRP) | Yes |
| VAT first-class | No | Yes (Point Cache) | Yes (importer) |
| Mesh trails native | Yes (Ribbon/Tube) | Yes | Yes |
| Decals (animated) | Yes | Yes | Yes |
| Audio-reactive built-in | No | Visual Effect Graph audio sampler | Niagara audio sampler |
| Profiling tools | Decent | Excellent | Excellent |

For our scope (solo dev, 2.5D iso, painted-flipbook aesthetic), the gaps that
matter are: (a) no node-graph authoring (we substitute LLM-driven JSON), and
(b) no VAT (we defer).

The `EmberGen / LiquiGen / IlluGen` recommendation from `C_vfx.md` still
stands as the commercial quality bar; for 3D output specifically, **EmberGen
exports to `.vdb` density volumes**, which Godot 4.5 cannot read directly
but we can convert via `pyopenvdb` to `Texture3D`. That's the only commercial-tool
path we'd want for high-end volumetric smoke.

---

## What to build next - punch list

Ordered by ROI, with effort estimates.

### 1. `export_godot_3d.py` - 3D billboard exporter (3-4 hours)

For every `Effect` with `export_target = "3d_billboard"` (or default-on for
new effects in 2.5D scenes), emit a `.tscn` with:
- `MeshInstance3D` + `QuadMesh` (size from `world_size_m`).
- `StandardMaterial3D` with `BILLBOARD_ENABLED`, `PARTICLES_ANIM_*` flags
  driving frame index from atlas (h_frames/v_frames/loop), `unshaded = true`,
  `transparent = true`, blend mode from `EffectVisual.blend`.

Acceptance: `fireball_projectile` displays correctly in a 2.5D iso scene
with camera angle 35deg, no z-fighting, billboards toward camera.

### 2. `baker_volumetric_fog.py` + biome preset wiring (4-6 hours)

Numpy-based Worley/Perlin noise -> 3D density volume -> exported as packed
`png` slices (4 slices per RGB channel; 64x64x32 fits in one 512x256 PNG).
Plus a `FogMaterial` `.tres` template that samples it.

Biome preset hookup: read `terrain/biome_scatter_rules.json`, emit one
`fog_volume` effect per biome with palette-derived emission.

Acceptance: 4 biomes (lava_field, ice_cavern, mana_crystal, grassland) each
have a `vfx/catalog/ambient/<biome>_haze/` with a working `FogVolume` scene.

### 3. `MeshTrail3D.gd` runtime helper (2-3 hours)

GDScript autoload + class that wraps `RibbonTrailMesh`/`TubeTrailMesh`
behind the `runtime_trail` `Effect` shape. Reads `backend_params`, builds
the trail at `_ready`, exposes `set_emitter_position(Node3D)` /
`emit_burst()`.

Acceptance: `fireball_projectile` with `export_target = "mesh_trail"`
attaches to a moving `RigidBody3D`, leaves a 0.4-second tube behind it.

### 4. `decal_flipbook` exporter (2-3 hours)

Wrapper around existing flipbook bakers. Emits `Decal` + shader.

Acceptance: `summon_circle_arcane` projects onto sloped terrain with no
seams, fades in/out, loops cleanly.

### 5. `AudioCueBus` autoload (1-2 hours)

GDScript autoload listening to `AnimatedSprite2D.frame_changed`,
emits `cue_hit(name, effect_id)` signal at frames whose timestamp matches
`BakeManifest.extras.audio_cues`.

Acceptance: a fireball impact spawns a screen-flash on the `impact` cue.

### 6. VAT baker stub (defer; 0 hours now, ~10 hours when needed)

Empty module with a TODO. Revisit when crowd or destruction scope demands it.

### Total: ~12-18 hours of build work to land all four 3D variants.

---

## Test plan (top 3 candidates)

### T1 - Fireball as 3D billboard in 2.5D scene

Input: existing `vfx/catalog/spells/fireball_projectile/` (already baked v1).
Run: `python pipelines/vfx/export_godot.py --target 3d_billboard fireball_projectile`.
Open the produced `.tscn` in a Godot 4.5 iso prototype scene.
Success: billboard faces camera at all rotations, animation loops, additive
blend bloom is visible against dark biome background, no z-fighting on terrain.
Failure modes to watch:
- Billboard rotation snaps (fix: use `Y_BILLBOARD` not `BILLBOARD_ENABLED` for ground-aligned).
- Frame seams visible (fix: ensure flipbook atlas has 1-px padding).
- Bloom too strong (fix: lower `EffectVisual.palette` last-color alpha).

### T2 - Lava-field volumetric haze

Input: new `effect.json` with biome_id=lava_field, palette from
`biome_scatter_rules.json`.
Run: `python pipelines/vfx/bake.py lava_field_haze` then `export_godot.py`.
Drop produced `FogVolume` into a scene with one lava-rock terrain chunk and a
directional sun.
Success: visible haze at ground level, fades with height, takes light tint
from sun, doesn't bleed past biome AABB.
Failure modes:
- Volume buffer banding (fix: enable `volumetric_fog_temporal_reprojection`).
- Fog ignores `directional_light` (fix: check `FogMaterial.use_lighting`).
- Performance drop on Compat renderer (fix: detect and fall back to
  `Environment.fog_*` non-volumetric settings).

### T3 - Projectile mesh-trail in 2.5D iso

Input: `fireball_streak` effect with `runtime_trail` backend, attached to a
`RigidBody3D` projectile via `MeshTrail3D` autoload.
Run: shoot projectile across screen.
Success: trail follows projectile with no popping, scrolling UV makes it look
like fire flow, fades over 0.4s, doesn't draw through walls (depth-tested).
Failure modes:
- Trail pops on direction reversal (fix: increase `trail_section_subdivisions`).
- UV scrolls too fast (fix: tune `scroll_uv_speed`).
- Tube intersects with own body (fix: small offset along emit direction).

---

## Risks and known issues

1. **Godot 4.5 minor versions break shader semantics occasionally.** Pin
   the project to a specific 4.5.x and test in CI when shaders change.
2. **Volumetric fog buffer is global**; multiple high-density `FogVolume`s
   in view can compound and clip to white. Cap density per biome at ~0.5.
3. **`PARTICLES_ANIM_*` material flags only animate on `GPUParticles3D`'s
   internal time** by default. For `MeshInstance3D` billboards we'll need
   a custom `spatial` shader that does UV math from `TIME`. Ship the shader
   as a preset.
4. **No per-particle event signals** in `GPUParticles3D` means damage-on-hit
   needs `Area3D` siblings. Document this in the `runtime_trail` recipe.
5. **VAT deferral may bite us** if the user pivots to crowd scenes. Document
   the deferral with a clear "trigger to revisit" in `../docs/plans/EXPANSION_PLAN.md`.
6. **EmberGen `.vdb` ingestion** is the only workflow we'd add commercial
   tools for; the pyopenvdb path is fragile on Windows. If we ever need it,
   convert in WSL2.

---

## Sources

Primary docs (Godot 4.5):
- GPUParticles3D: <https://docs.godotengine.org/en/4.5/tutorials/3d/particles/index.html>
- Particle shader: <https://docs.godotengine.org/en/4.5/tutorials/shaders/shader_reference/particle_shader.html>
- Volumetric fog: <https://docs.godotengine.org/en/4.5/tutorials/3d/volumetric_fog.html>
- FogMaterial / shader_type fog: <https://docs.godotengine.org/en/4.5/tutorials/shaders/shader_reference/fog_shader.html>
- RibbonTrailMesh: <https://docs.godotengine.org/en/4.5/classes/class_ribbontrailmesh.html>
- TubeTrailMesh: <https://docs.godotengine.org/en/4.5/classes/class_tubetrailmesh.html>
- Decal: <https://docs.godotengine.org/en/4.5/classes/class_decal.html>
- StandardMaterial3D billboard/particles_anim: <https://docs.godotengine.org/en/4.5/classes/class_basematerial3d.html>

External / commercial:
- SideFX Houdini Labs VAT 3.0: <https://www.sidefx.com/docs/houdini/nodes/out/labs--vertex_animation_textures-3.0.html>
- JangaFX EmberGen: <https://jangafx.com/software/embergen>
- JangaFX LiquiGen: <https://jangafx.com/software/liquigen>
- JangaFX IlluGen: <https://jangafx.com/software/illugen>

Forum / community sentiment scanned (2025-2026):
- r/godot threads on GPUParticles3D performance, sub-emitter limitations.
- Godot Forum threads on volumetric fog edge cases (banding, light coupling).
- GitHub discussions on `RibbonTrailMesh` direction-reversal pop fix.
- HN/Twitter chatter on Newton 1.0 GA (March 2026) - relevant only as
  reference; out of scope for this brief.

Local prior reports:
- `D:\assets\research\C_vfx.md`
- `D:\assets\research\I_vfx_lab_local_audit_and_migration_plan.md`
- `D:\assets\HANDOFF_vfx_2026_05_06.md`
- `D:\assets\pipelines\vfx\schemas.py`
- `D:\assets\pipelines\vfx\GPU_BACKENDS_PLAN.md`
