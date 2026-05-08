# M4 Splat Shader Prototype

Date: 2026-05-08

## Status

Prototype pass 1 is complete. It proves the first M4 slice:

- one unified shader can render the existing five-slot terrain kit path;
- the same shader can consume an RGBA splat-weight texture for per-pixel
  material weights;
- the same shader can bind a finished OpenTopo material with the macro/detail
  controls from `terrain_hex_detail.gdshader`.

This is workflow-validation quality, not the final runtime contract.

Prototype pass 2 adds the chunk-facing contract:

- `world3/jobs/m4_chunk_material_contract.json`
- `world3/docs/M4_CHUNK_MATERIAL_CONTRACT.md`
- `ChunkLoader.gd` can bind a runtime splat weight texture through
  `splat_weights_path`
- `world3/scenes/capture_phase_m4/chunk_splat_stream_review.tscn`
- `world3/docs/captures/m4/chunk_splat_stream_review.png`

## Files

- Shader: `world3/shaders/terrain_splat_unified.gdshader`
- Builder: `world3/pipeline/build_m4_splat_prototype.py`
- Terrain review scene:
  `world3/scenes/capture_phase_m4/splat_shader_review.tscn`
- OpenTopo compatibility scene:
  `world3/scenes/capture_phase_m4/opentopo_unified_review.tscn`
- Chunk stream review scene:
  `world3/scenes/capture_phase_m4/chunk_splat_stream_review.tscn`
- Review scripts:
  - `world3/scripts/M4SplatShaderReview.gd`
  - `world3/scripts/M4OpenTopoUnifiedReview.gd`
  - `world3/scripts/M4ChunkSplatReview.gd`

Generated assets:

- `world3/textures/m4_splat/alpine_height_slope_weights_rgba.png`
- `world3/textures/m4_splat/alpine_height_slope_weights_debug.png`
- `world3/textures/wgv3/terrain_splat_alpine.tres`
- `world3/textures/wgv3/terrain_splat_alpine_fallback.tres`
- `world3/textures/wgv3/terrain_splat_scrub_sparse_single.tres`
- `world3/textures/wgv3/terrain_hex_detail_scrub_sparse_reference.tres`

Captures:

- `world3/docs/captures/m4/splat_shader_review.png`
- `world3/docs/captures/m4/opentopo_unified_review.png`
- `world3/docs/captures/m4/chunk_splat_stream_review.png`

## Splat Contract

The prototype uses the current five semantic kit slots:

1. `grass`
2. `dirt`
3. `rock_light`
4. `rock_dark`
5. `snow`

The splat texture stores the first four weights in RGBA. The fifth weight is
reconstructed in shader as:

```text
snow = max(1 - r - g - b - a, 0)
```

The generated Tetons/alpine test weights averaged:

| Slot | Mean weight |
|------|-------------|
| `grass` | 0.133 |
| `dirt` | 0.529 |
| `rock_light` | 0.099 |
| `rock_dark` | 0.223 |
| `snow` | 0.017 |

The weight texture is generated from the same height/slope rules used by
`terrain_blend.gdshader`, but offline against the heightmap. That is enough to
prove "chunk emits weights, shader resolves materials" before M5 wiring.

## Verification

Commands run:

```powershell
python -m py_compile world3/pipeline/build_m4_splat_prototype.py
python world3/pipeline/build_m4_splat_prototype.py
C:/Godot/Godot_v4.5-stable_win64.exe --path world3 --script res://scripts/_codex_render_runner.gd -- --scene res://scenes/capture_phase_m4/splat_shader_review.tscn --out res://docs/captures/m4/splat_shader_review.png --wait-frames 120 --width 1920 --height 1080
C:/Godot/Godot_v4.5-stable_win64.exe --path world3 --script res://scripts/_codex_render_runner.gd -- --scene res://scenes/capture_phase_m4/opentopo_unified_review.tscn --out res://docs/captures/m4/opentopo_unified_review.png --wait-frames 120 --width 1920 --height 1080
```

Capture stats:

| Capture | Mean RGB | RGB stddev | Read |
|---------|----------|------------|------|
| `splat_shader_review.png` | 139.51, 113.75, 89.14 | 59.44, 52.82, 45.80 | nonblank terrain A/B |
| `opentopo_unified_review.png` | 173.10, 183.81, 178.87 | 13.70, 15.93, 26.34 | nonblank OpenTopo A/B |
| `chunk_splat_stream_review.png` | 158.08, 189.62, 157.36 | 30.46, 39.66, 61.22 | nonblank ChunkLoader splat binding |

OpenTopo compatibility crop delta:

```text
mean absolute RGB delta ~= 5.3 / 255
```

This is close enough for a prototype equivalence check. Any remaining
difference belongs in shader tuning after the M5 runtime path exists.

## Known Limits

- The shader is fixed to the current five terrain slots. A production material
  table or texture-array path is still needed before arbitrary N-way catalog
  materials.
- The first splat map is height/slope-derived only. It does not yet use biome
  rules, canopy masks, soil classes, or M2 boundary strips.
- Boundary transition strips are not sampled in shader yet. M2 remains the
  boundary asset contract; M4 pass 1 only proves normal splat blending.
- Review scripts and `ChunkLoader.splat_weights_path` bind the fresh splat PNG
  dynamically because Godot runtime `.tres` loading does not see unimported new
  PNGs as `Texture2D` resources. M5 should either formalize the import step or
  keep generated splat maps on this runtime texture path.
- The terrain A/B capture is not expected to be pixel-identical. The right side
  is the offline splat-weight path and intentionally exposes the chunk-weight
  output instead of recomputing height/slope weights in-fragment.

## Next

M5 prototype-final has consumed this prototype:

- `walk.tscn` now uses `terrain_splat_alpine.tres` through `ChunkLoader.gd`;
- `ChunkLoader.gd` binds the generated splat PNG through `splat_weights_path`;
- chunk mesh UVs now use the same wrapped source fraction as height sampling,
  which fixed the first M5 smoke-test material split at chunk edges.

Next hardening:

- formalize generated weight-map import/cache if dynamic binding becomes
  fragile;
- add a boundary-weight lane that can later sample M2 transition strips once
  boundary-space UVs exist;
- keep the next hardening pass fixed at five slots until export-safe loading,
  streamed collision, and boundary-strip sampling are individually measured.
