# M4 Chunk Material Contract

Date: 2026-05-08

Machine contract:

```text
world3/jobs/m4_chunk_material_contract.json
```

## Decision

M4 pass 2 keeps the first streaming contract fixed to the current five
semantic terrain slots:

```text
grass, dirt, rock_light, rock_dark, snow
```

This is not the forever material system. It is the smallest contract that lets
M5 wire 256 m chunks to a per-pixel weight texture without also solving
texture arrays, material indirection, and boundary-space transition sampling in
the same step.

## Chunk Inputs

A streamed terrain chunk needs:

- height source: shared heightmap + meta, or a chunk-local height tile later;
- material table: five catalog material IDs in slot order;
- weight texture: RGBA map for the first four slots;
- shader material: `.tres` bound to `terrain_splat_unified.gdshader`;
- optional runtime texture path for fresh/generated splat PNGs.

The fifth slot is reconstructed in shader:

```text
snow = max(1 - r - g - b - a, 0)
```

Current prototype:

- material: `world3/textures/wgv3/terrain_splat_alpine.tres`
- weights: `world3/textures/m4_splat/alpine_height_slope_weights_rgba.png`
- review scene: `world3/scenes/capture_phase_m4/chunk_splat_stream_review.tscn`
- capture: `world3/docs/captures/m4/chunk_splat_stream_review.png`

## Runtime Binding

`ChunkLoader.gd` now has:

```gdscript
@export var splat_weights_path: String = ""
```

If the assigned `terrain_material` is a `ShaderMaterial`, `ChunkLoader` pushes:

- `elev_min_m`
- `elev_range_m`
- `splat_weights` loaded as an `ImageTexture` when `splat_weights_path` is set

The dynamic `ImageTexture` path is intentional for now. Godot runtime `.tres`
loading did not resolve a fresh unimported PNG as a `Texture2D` resource during
the M4 pass 1 render. M5 should either formalize an import/cache step or keep
runtime-generated weight maps on this dynamic binding path.

## Boundary Lane

Boundary transitions are reserved but not sampled yet. M2 remains the source
of truth:

```text
world3/jobs/biome_transition_rules.json
```

The eventual boundary shader inputs are:

- `material_a_weight`
- `material_b_weight`
- `boundary_weight`
- `boundary_signed_distance_u`
- `boundary_repeat_v`

Do not promote transition strips into the base material catalog. They remain
generated boundary assets referenced by rules.

## M5 Use

For the first `walk.tscn` integration, use:

- `chunk_size_m = 256`
- `chunk_resolution_m = 8`
- `view_radius_chunks = 1`
- `terrain_material = res://textures/wgv3/terrain_splat_alpine.tres`
- `splat_weights_path = res://textures/m4_splat/alpine_height_slope_weights_rgba.png`

That gives M5 a concrete streaming material contract while keeping the known
prototype limits visible.

M5 pass 1 applied this contract in `walk.tscn`. One contract bug surfaced and
was fixed: chunk mesh UVs must use the same wrapped source fraction as height
sampling, not raw `global_x / source_size`, or splat lookup creates artificial
material breaks at chunk edges. The pass 1 evidence is recorded in
`world3/docs/M5_WALK_SPLAT_STREAMING.md`.

## Verification

Rendered with:

```powershell
C:/Godot/Godot_v4.5-stable_win64.exe --path world3 --script res://scripts/_codex_render_runner.gd -- --scene res://scenes/capture_phase_m4/chunk_splat_stream_review.tscn --out res://docs/captures/m4/chunk_splat_stream_review.png --wait-frames 120 --width 1920 --height 1080
```

Capture stats:

```text
size = 1920 x 1080
mean RGB = 158.08, 189.62, 157.36
stddev RGB = 30.46, 39.66, 61.22
```

Read: nonblank 3x3 streamed chunk view using `terrain_splat_alpine.tres` and
`ChunkLoader.splat_weights_path`. The visible material-region blocking is
expected for this height/slope-derived prototype weight map and top-down debug
framing; it is not a final M5 art-quality read.
