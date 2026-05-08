# M7 Boundary Runtime Integration

Date: 2026-05-08

## Status

M7 pass 1 is complete for workflow/runtime validation.

The streamed runtime can now place transition strips automatically from
`world3/jobs/biome_transition_rules.json`. This is not a production visual
promotion. The captures are evidence that the contract works; final visual
quality needs the M1-M7 visual audit before M8.

## What Changed

- `ChunkLoader.gd` can enable rule-driven transition boundaries.
- Runtime rules select:
  - `from_material` and `to_material` from `world3/materials/catalog.json`
  - transition strip textures from each rule's transition manifest
  - boundary width, repeat, strength, and noise tuning
- Chunks get local `UV2` coordinates for generated mask sampling.
- Boundary chunks receive a generated RGBA mask texture:
  - `R`: transition strength band
  - `G`: transition strip U across the boundary
  - `B`: transition strip V along the boundary
  - `A`: reserved/opaque
- `terrain_splat_unified.gdshader` now supports `use_transition_mask` in
  addition to the older manual `use_transition_strip` review path.
- `M5WalkStreamRunner.gd` records transition-mask build metrics.

## Evidence

Scenes:

- `world3/scenes/capture_phase_m7/boundary_runtime_review.tscn`
- `world3/scenes/capture_phase_m7/boundary_runtime_biome_stress.tscn`
- `world3/scenes/capture_phase_m7/boundary_walk_review.tscn`

Captures:

- `world3/docs/captures/m7/boundary_runtime_review.png`
- `world3/docs/captures/m7/boundary_runtime_biome_stress.png`
- `world3/docs/captures/m7/boundary_walk_after_crossing.png`
- `world3/docs/captures/m7/boundary_walk_metrics.json`

Verification:

- Godot import passed.
- Same-source control rule:
  `opentopo_scrub_sparse__dry_wash_neighbor`
- Biome stress rule:
  `biome_desert__grassland_base`
- Walk capture crossed `384 m` along +Z and moved from chunk `[0,6]` to
  `[0,7]`.
- Peak loaded chunks: `9`
- Chunks built / removed: `12 / 3`
- Collision chunks built: `12`
- Transition masks built: `6`
- Transition mask build total / max: `83.454 ms / 14.142 ms`
- Worst update: `26.599 ms`
- Frame mean / p95 / p99: `4.263 ms / 4.873 ms / 4.970 ms`

## Visual Read

The runtime contract works, but the visual result is mixed.

- The same-source control is calm and seam-soft, but subtle because the source
  materials are close relatives.
- The desert-to-grassland stress capture proves the cross-biome path, but it
  also confirms the known M6 issue: grassland/organic source texture noise is
  too strong for production close-range use.
- The walk capture is usable as engineering evidence, not a beauty shot.

Conclusion: M7 can close as a workflow milestone, but it should not be used to
claim final terrain-art quality. The next gate is a formal M1-M7 visual audit.

## Remaining Risks

- Boundary geometry is still a straight test boundary, not a biome-map-derived
  contour.
- Missing source AO maps fall back through the material's existing/default
  binding.
- Mask generation is synchronous and per-chunk. Current measured cost is
  acceptable for this pass, but M9 should revisit async/background work if
  interactive hitching appears.
- Corner/junction cases remain M11.
