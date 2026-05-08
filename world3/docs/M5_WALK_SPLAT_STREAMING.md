# M5 Walk Splat Streaming

Date: 2026-05-08

## Status

M5 pass 1 is wired and smoke-tested. `walk.tscn` now uses the M3
`ChunkLoader.gd` visual stream with the M4 fixed five-slot splat material.

This is not the final M5 exit yet. It proves the first playable scene wiring
and chunk-crossing behavior. The first budget note is in
`world3/docs/M5_STREAMING_BUDGET.md`. Remaining M5 work is the longer walk
demo, export-safe image import/cache, and the eventual collision migration from
the hidden single terrain to streamed chunks.

## Scene Contract

`world3/scenes/walk.tscn` now uses two terrain paths:

- Hidden legacy `Terrain.gd`: collision source only, still attached to
  `TerrainBody`.
- Visible `ChunkLoader.gd`: 256 m streamed chunks using the unified splat
  material.

Current `ChunkLoader` parameters:

```text
terrain_material = res://textures/wgv3/terrain_splat_alpine.tres
splat_weights_path = res://textures/m4_splat/alpine_height_slope_weights_rgba.png
chunk_size_m = 256
chunk_resolution_m = 8
view_radius_chunks = 1
target_path = ../Player
```

The player spawn was lowered to a terrain-visible altitude near the sampled
height at the current start position so headless smoke captures do not render
blank sky.

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
mean RGB = 157.27, 144.55, 137.60
stddev RGB = 40.57, 54.78, 67.94
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
worst synchronous update = 20.096 ms
```

The capture is nonblank and shows no obvious chunk-edge split. The worst update
time is in the same envelope as the M3 256 m sweep and is acceptable for this
prototype because the current loader is still synchronous.

Known expected warnings:

```text
Loaded resource as image file, this will not work on export
```

These are from runtime `Image.load_from_file()` for the heightmap and fresh
splat PNG. They are acceptable for dev smoke tests. Export-safe loading remains
an M5/M6 hardening item.

## Remaining M5 Work

- Run a longer player-facing walk capture once the user has visually checked
  the pass 1 scene.
- Keep `M5_STREAMING_BUDGET.md` updated as chunk radius, collision, or async
  loading changes.
- Decide whether the next hardening step is export-safe generated image import,
  chunk collision, or boundary-strip sampling.
- Keep M2 transition strips out of the runtime shader until boundary-space UVs
  and material-pair selection are explicit.
