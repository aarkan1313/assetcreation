# Axis 1 Path 2 — Stage 3 build notes

> Heightmap stack integration. Replaces the Stage 2 sine-wave debug
> displacement with real procedural terrain driven by `KernelComposer`,
> async via `WorkerThreadPool`, with `HeightMapShape3D` collision per
> ring. Tier-aware via the quality-tier system that landed in the same
> session.
>
> Shipped 2026-05-12 on `main`. Commits `3f174e3`…`135b52c`.

## What shipped

| Task | Component | Commit |
|---|---|---|
| 3.1 | `ClipmapRing` displacement-texture slot | `dbf9af0` |
| 3.2 | `terrain_world_v3.gdshader` — lit PBR + per-fragment normals | `3f174e3` |
| 3.3 | `ClipmapWorld` reads `QualityTiers` + wires `KernelComposer` | `a7fd98f` |
| 3.4 | `WorkerThreadPool` async regen with double-buffer + supersede | `41a915a` |
| 3.5 | `HeightMapShape3D` collision proxy per inner ring | `135b52c` |

**Worlds touched:** `the world 4/worlds/scale_v2/` got a 2-biome
`biome_catalog.json` (alpine + desert, both using `NoiseStackKernel`)
and a `material_world_v3.tres` bound to the v3 shader. `scale_demo` was
not touched — the two renderers (ScaleWorld / ClipmapWorld) coexist.

**Test count:** 54 → 54 (Stage 3 didn't add unit tests; all gates are
visual + parse-check). Stage 1's 17 kernel tests + Stage QT's 9 quality
tier tests cover the moving parts; Stage 3 itself is integration of
already-tested pieces plus visual sign-off via headless captures.

## Plan deviations + why

**Five deviations from `plans/AXIS1_PATH2_PLAN_2026_05_12.md`**, all
shipped knowingly:

### 1. Lit PBR instead of `unshaded` (Task 3.2)

Plan called for `render_mode unshaded` "for debug." Per project ethos
(quality > performance > anything), shipped lit from the start with
`cull_back + diffuse_burley + specular_schlick_ggx`. Stage 4's biome
PBR will slot in cleanly. Debug per-ring coloring lives behind a
`show_debug_color` uniform, off by default.

### 2. Per-fragment normals via finite differences (Task 3.2)

Plan implied per-vertex normals (the standard cheap path). Used
per-fragment central differences instead — smoother on outer rings
where vertex density is low. Costs a few extra texture taps per pixel;
fragment shader is otherwise cheap.

### 3. Half-texel UV offset (Task 3.2)

The original spec sample formula `(world_xz - origin) / extent` was
off by half a texel because `filter_linear` samples at texel centers.
Fixed via `(world_xz - origin) / (extent * n/(n-1))`. Without this,
adjacent rings disagree at their shared boundary by half a texel.

### 4. Tier-knobs read at `_ready` (Task 3.3)

Plan had `@export var ring_count` etc as the source. Changed to read
from `QualityTiers.get_current()` first; `@export` vars are
**overrides** for isolated testing only. This means changing the user's
quality tier in `ProjectSettings` actually changes ring count/grid
density at scene load without editing the scene file.

### 5. R16F outer-ring format intent preserved without implementation (Task 3.3+3.4)

The tier knob `heightmap_format_outer = "RH"` says outer rings should
store as `FORMAT_RH` (16-bit half-float) to save VRAM. GDScript has no
exposed `float32→float16` helper as of Godot 4.5; both inner and outer
rings currently store `FORMAT_RF` (32-bit). Tier knob preserved as
design intent; comment in code documents the gap. A native helper or
moving to a build-side pre-quantization would close it.

### 6. Bulk path now, not "later" (Task 3.3)

Plan's 3.3 used per-pixel `set_pixel()` (slow GDScript). Per ethos,
shipped bulk `PackedFloat32Array → Image.create_from_data` from the
start. Stage 3.4 wrapped the same code in a worker without rewriting.

### 7. Tier-aware collision (Task 3.5)

Plan added `HeightMapShape3D` to every ring. Changed to only the inner
`collision_rings` count (tier knob: 1 on low/medium, 2 on high/ultra).
Outer rings skip collision — player physics doesn't care about terrain
500m+ away.

## Architecture summary

```
┌─────────────────────────────┐
│ QualityTiers.get_current()  │ ← ProjectSettings("world/quality_tier")
└────────────┬────────────────┘
             ↓
┌─────────────────────────────┐
│ ClipmapWorld._ready         │
│ - reads tier knobs          │
│ - builds KernelComposer     │
│ - spawns N rings            │
│ - enables collision on K    │
└────────────┬────────────────┘
             ↓
┌─────────────────────────────┐    ┌──────────────────────────┐
│ ClipmapWorld._process       │ ←→ │ WorkerThreadPool         │
│ - polls finished tasks      │    │ - _worker_compute_heightm│
│ - snaps rings to camera     │    │   ap (off main)          │
│ - enqueues refresh on snap  │    │ - returns PackedFloat32  │
└────────────┬────────────────┘    │   to _ring_tasks         │
             ↓                     └──────────────────────────┘
┌─────────────────────────────┐
│ _finalize_ring_upload       │ (main thread)
│ - Image.create_from_data    │
│ - ImageTexture.create_from_ │
│   image                     │
│ - ring.set_displacement_    │
│   texture                   │
│ - ring.set_ring_uniforms    │
│ - ring.update_collision_    │
│   heightmap (if collision)  │
└─────────────────────────────┘
```

## Captures

- Walk view: `captures/axis1_clipmap_debug_2026_05_12.png`
- Topdown view: `captures/axis1_clipmap_debug_2026_05_12_topdown.png`

Both show 4 nested clipmap rings rendering procedural alpine/desert
terrain. Debug ring-color overlay enabled so partitions are visible.
Sun lighting visible on slopes. No gaps between rings; faint z-fight
pepper at ring overlaps (known — addressable by morph zones in a
future stage).

## Lessons + new pitfalls

### Pitfall — worker thread access to refcounted state during shutdown

When `HeadlessCapture.gd` called `quit()`, in-flight
`WorkerThreadPool` tasks were still running and tried to call
`_composer.sample_height` — `_composer` had been freed. Caused a
flurry of "null instance" errors during shutdown but no actual data
corruption (capture wrote before the errors).

Fix: `_exit_tree` drains pending tasks via
`wait_for_task_completion` before the scene frees, and a null-guard
at the top of `_compute_heightmap_floats` returns a zero-filled
buffer as defense-in-depth.

This is one I'll watch for in any future `WorkerThreadPool` use —
worker functions should null-guard their shared dependencies.

### Confirmed: `VERTEX.y += h` (not `=`)

Stage 2's shader fix carried forward to `terrain_world_v3.gdshader`.
Skirt verts arrive with `VERTEX.y = -skirt_depth_m`; the additive
form preserves them under the surface.

### Confirmed: `inner_grid_n` rounds DOWN

Stage 2's fix also carries forward. `((grid_n - 1) / 2) & ~1` gives
slightly-smaller-hole-than-inner-ring-outer-extent → guaranteed
overlap, no gap.

### Confirmed: half-texel UV offset matters

Without `extent_n = extent_m * n/(n-1)` correction, rings disagree
by half a texel at shared boundaries. Wasn't visible in the
Stage 3.3 walk capture but would show as a faint cliff at ring
boundaries during gameplay.

## Editor verification status

**Pending.** I need to ask the user to run:
```
"C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world 4/the world 4"
```
Open `scenes/clipmap_debug.tscn`, F6, WASD for 30 seconds. Watch for:
- Procedural terrain (not sine wave) ✓ expected
- No hitches when walking across a 2m ring-0 boundary ✓ expected (async)
- Lighting visible on slopes ✓ expected
- No cliffs at ring boundaries ✓ expected (half-texel fix)

For collision verification, drop a `CharacterBody3D` or `RigidBody3D`
test object into the scene and confirm it lands on terrain rather
than passing through.

## What's next

Stage 4 — Clipmap splat + biome rendering. Wires the world-splat
infrastructure (Axis 6 pattern) into the clipmap renderer. Each ring
samples a per-biome PBR Texture2DArray driven by a world-spanning
splat array. Replaces the debug ring-color overlay with real biome
shading.
