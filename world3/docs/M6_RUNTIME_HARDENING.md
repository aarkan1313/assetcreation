# M6 Runtime Hardening

Date: 2026-05-08

M6 hardens the M5 streamed walk prototype into a more export-aware runtime
contract. This is still workflow-validation content, but it closes four
practical gaps that would otherwise become production blockers.

## What Landed

### Export-safe runtime image cache

Generated runtime caches now live under:

- `world3/runtime_cache/heightmap_rf32.json`
- `world3/runtime_cache/heightmap_rf32.bin`
- `world3/runtime_cache/alpine_splat_rgba8.json`
- `world3/runtime_cache/alpine_splat_rgba8.bin`

Builder:

```powershell
python world3/pipeline/build_runtime_image_cache.py
```

Runtime loader:

- `world3/scripts/RuntimeImageCache.gd`

The loader reads a JSON manifest plus raw bytes through `FileAccess`, then
creates `Image` / `ImageTexture` objects at runtime. This replaces direct
`Image.load_from_file()` for the primary heightmap/splat path used by
`Terrain.gd`, `PlayerAnchor.gd`, and `ChunkLoader.gd`.

### Streamed collision chunks

`ChunkLoader.gd` can now build a `StaticBody3D` + trimesh collision shape per
loaded visual chunk:

- `build_collision_chunks`
- `collision_layer`
- `collision_mask`

Metrics are tracked on the loader:

- `collision_chunks_built`
- `collision_build_usec_total`
- `collision_build_usec_max`

`walk.tscn` now uses streamed chunk collision by default. The legacy hidden
`Terrain.gd` remains in the scene but is deferred and no longer builds the
full hidden terrain/collision on scene start.

### Runtime transition-strip shader hook

`terrain_splat_unified.gdshader` now has an opt-in boundary-strip sampler:

- `use_transition_strip`
- `transition_albedo`
- `transition_rough`
- `transition_ao`
- `transition_center_u`
- `transition_width_u`
- `transition_repeat_v`
- `transition_strength`

The hook is disabled by default, so the normal M5 walk material path is
unchanged. The M6 review scene enables it explicitly:

- `world3/scenes/capture_phase_m6/transition_runtime_review.tscn`
- `world3/scripts/M6TransitionRuntimeReview.gd`

This is a shader/runtime proof, not the final biome-mask solution. It proves
the M2 transition assets can be sampled by the streamed terrain shader; the
next layer is automatic boundary-mask placement from biome/chunk rules.

### Source-material noise QA

User review correctly called out that the grass/leaves are too noisy for
production close-up use. M6 adds a source-material audit instead of treating
that as a transition failure.

Tool:

```powershell
python world3/pipeline/audit_material_source_noise.py
```

Outputs:

- `world3/docs/M6_SOURCE_MATERIAL_NOISE_AUDIT.md`
- `world3/docs/M6_SOURCE_MATERIAL_NOISE_AUDIT.json`

Result: 10 of 17 audited green/organic materials flagged, including
`grassland_grass`, `grass`, `temperate_forest_grass`, `tundra_moss`, and
`tundra_lichen`.

## Verification

Godot import:

```powershell
C:/Godot/Godot_v4.5-stable_win64.exe --path world3 --quiet --headless --editor --import
```

Walk stream + collision/cache capture:

```powershell
C:/Godot/Godot_v4.5-stable_win64.exe --path world3 --script res://scripts/M5WalkStreamRunner.gd -- --out res://docs/captures/m6/walk_stream_collision_cache.png --metrics res://docs/captures/m6/walk_stream_collision_cache_metrics.json --frames 360 --distance-z 900 --clearance-m 48 --build-collision true --rebuild-after-reset true --width 1920 --height 1080
```

Metrics:

| Metric | Value |
|--------|-------|
| Frames | 360 |
| Distance | 900 m |
| Peak loaded chunks | 9 |
| Chunks built / removed | 21 / 12 |
| Collision chunks built | 21 |
| Collision build total | 60.433 ms |
| Collision build max | 5.033 ms |
| Worst update | 28.675 ms |
| Frame mean | 4.315 ms |
| Frame p95 / p99 | 4.594 ms / 5.221 ms |
| Frame max | 29.29 ms |

Capture:

- `world3/docs/captures/m6/walk_stream_collision_cache.png`
- `world3/docs/captures/m6/walk_stream_collision_cache_metrics.json`

Runtime transition-strip capture:

```powershell
C:/Godot/Godot_v4.5-stable_win64.exe --path world3 --script res://scripts/_codex_render_runner.gd -- --scene res://scenes/capture_phase_m6/transition_runtime_review.tscn --out res://docs/captures/m6/transition_runtime_review.png --wait-frames 120 --width 1920 --height 1080
```

Capture:

- `world3/docs/captures/m6/transition_runtime_review.png`

## Audit

M6 closes the M5 hardening targets:

- Export-safe primary height/splat loading: done for `walk.tscn` and the main
  runtime scripts.
- Streamed collision: done, measured, and enabled in `walk.tscn`.
- Runtime transition-strip sampling: shader hook and review scene done.
- Grass/leaves source QA: done, with a machine-readable flagged-material list.

Remaining hard truths:

- Transition-strip placement is manual/prototype. It needs biome boundary masks
  generated per chunk before it is production behavior.
- Collision is built synchronously with chunk meshes. The measured spike is
  acceptable for this prototype, but async/background build is the next runtime
  improvement.
- Some legacy review-only scripts still use direct image loading. The primary
  walk/runtime path is fixed; old capture utilities can be migrated as touched.
- The close-range material weak link is now documented as source QA. The next
  quality win is regenerating or filtering flagged organic materials, not adding
  more shader complexity.
