# M5 Walk Splat Streaming

Date: 2026-05-08

## Status

M5 is complete at prototype final form. `walk.tscn` now uses the M3
`ChunkLoader.gd` visual stream with the M4 fixed five-slot splat material, and
the workflow has both short crossing and long-form sampled walk evidence.

This is not production-final terrain. The final M1-M5 audit is
`world3/docs/M1_M5_FINAL_AUDIT_2026_05_08.md`; the streaming budget is
`world3/docs/M5_STREAMING_BUDGET.md`.

M6 update: the current `walk.tscn` now uses export-safe runtime height/splat
caches and streamed chunk collision. The M5 notes below remain the historical
prototype closure; current runtime hardening evidence lives in
`world3/docs/M6_RUNTIME_HARDENING.md`.

2026-05-08 visual-remediation update: the original M5 walk capture remains
streaming proof only. The first source-stack visual rerender lives in
`world3/docs/M5_SOURCE_STACK_WALK_REVIEW_2026_05_08.md` and uses
`world3/scenes/capture_phase_m5/walk_source_stack.tscn`.

## Scene Contract

`world3/scenes/walk.tscn` now uses two terrain paths:

- Hidden legacy `Terrain.gd`: historical fallback. In M6 it is deferred and no
  longer builds the full hidden terrain/collision on scene start.
- Visible `ChunkLoader.gd`: 256 m streamed chunks using the unified splat
  material and, in M6, streamed chunk collision.

Current `ChunkLoader` parameters:

```text
terrain_material = res://textures/wgv3/terrain_splat_alpine.tres
splat_weights_path = res://textures/m4_splat/alpine_height_slope_weights_rgba.png
splat_weights_cache_path = res://runtime_cache/alpine_splat_rgba8.json
heightmap_cache_path = res://runtime_cache/heightmap_rf32.json
chunk_size_m = 256
chunk_resolution_m = 8
view_radius_chunks = 1
target_path = ../Player
build_collision_chunks = true
```

The player spawn is lowered to a terrain-visible altitude near the sampled
height at the current start position so interactive use and smoke captures
start on the actual terrain instead of high in the sky.

## Chunk Material UV Fix

The first M5 smoke render exposed a hard material boundary at a chunk edge. The
cause was a coordinate-contract mismatch:

- height sampling uses `_wrapped_fraction(global_x + source_half_extent)`;
- chunk UVs were using raw `global_x / source_size`.

`ChunkLoader.gd` now writes mesh UVs with the same wrapped source fraction used
for height sampling:

```gdscript
uvs[i] = Vector2(
    _wrapped_fraction(global_x, _source_size_x_m),
    _wrapped_fraction(global_z, _source_size_z_m)
)
```

That removed the artificial vertical split in the walk capture. Remaining
large material changes are prototype splat-map content, not chunk-boundary UV
breakage.

## Verification

Static walk smoke capture:

```powershell
C:/Godot/Godot_v4.5-stable_win64.exe --path world3 --script res://scripts/_codex_render_runner.gd -- --scene res://scenes/walk.tscn --out res://docs/captures/m5/walk_chunk_splat_smoke.png --wait-frames 120 --width 1920 --height 1080
```

Result:

```text
capture = world3/docs/captures/m5/walk_chunk_splat_smoke.png
size = 1920 x 1080
mean RGB = 153.59, 120.44, 98.58
stddev RGB = 15.87, 21.46, 26.71
```

Scripted chunk-crossing smoke:

```powershell
C:/Godot/Godot_v4.5-stable_win64.exe --path world3 --script res://scripts/M5WalkStreamRunner.gd -- --out res://docs/captures/m5/walk_stream_after_crossing.png --metrics res://docs/captures/m5/walk_stream_smoke_metrics.json --frames 360 --width 1920 --height 1080
```

Result:

```text
capture = world3/docs/captures/m5/walk_stream_after_crossing.png
metrics = world3/docs/captures/m5/walk_stream_smoke_metrics.json
distance = 900 m along +Z
chunk path = [0,5] -> [0,9]
peak loaded chunks = 9
chunks built = 12
chunks removed = 12
worst synchronous update = 18.816 ms
frame mean / p95 / p99 / max = 4.255 / 4.593 / 4.768 / 19.351 ms
```

Long-form sampled walk review:

```powershell
C:/Godot/Godot_v4.5-stable_win64.exe --path world3 --script res://scripts/M5WalkStreamRunner.gd -- --out res://docs/captures/m5/walk_long_after_crossing.png --metrics res://docs/captures/m5/walk_long_metrics.json --sample-dir res://docs/captures/m5/walk_long_frames --sample-every-frames 300 --frames 1800 --distance-z 1536 --width 1920 --height 1080
```

Result:

```text
contact sheet = world3/docs/captures/m5/walk_long_contact_sheet.png
metrics = world3/docs/captures/m5/walk_long_metrics.json
distance = 1536 m along +Z
chunk path = [0,5] -> [0,11]
peak loaded chunks = 9
chunks built = 18
chunks removed = 18
worst synchronous update = 18.317 ms
frame mean / p95 / p99 / max = 4.152 / 4.582 / 4.661 / 19.076 ms
```

The capture is nonblank and shows no obvious chunk-edge split. The worst update
time is in the same envelope as the M3 256 m sweep and is acceptable for this
prototype because the current loader is still synchronous.

Historical M5 expected warnings:

```text
Loaded resource as image file, this will not work on export
```

These were from runtime `Image.load_from_file()` for the heightmap and fresh
splat PNG. M6 replaced the primary walk/runtime path with `RuntimeImageCache.gd`
and generated cache manifests; see `M6_RUNTIME_HARDENING.md`.

## Remaining Production Work

- Keep `M5_STREAMING_BUDGET.md` and `M6_RUNTIME_HARDENING.md` updated as chunk
  radius, collision, or async loading changes.
- Move from manual transition-strip shader knobs to generated per-chunk
  boundary masks.
- Regenerate/filter flagged organic source materials before production
  close-range promotion.
