# M7 Source-Stack Boundary Review

Date: 2026-05-08

## Purpose

This is the M7 rerender over the repaired source-stack context. The earlier M7
captures proved automatic boundary-mask generation but still looked diagnostic
or exposed finite-footprint framing problems.

This pass keeps the M7 runtime contract:

- rule-driven transition selection from `biome_transition_rules.json`
- generated per-chunk transition masks
- `ChunkLoader.gd`
- `terrain_splat_unified.gdshader`
- source-stack macro terrain with valid-mask policy
- same-source control rule: `opentopo_scrub_sparse__dry_wash_neighbor`

## Capture

- `docs/captures/m7/boundary_runtime_source_stack_context.png`
- `docs/captures/m7/transition_mask_metrics_source_stack_context.json`
- `docs/captures/m7/transition_mask_metrics_source_stack_context.png`
- scene: `scenes/capture_phase_m7/boundary_runtime_source_stack_context.tscn`

## Read

This is a cleaner M7 visual control than the earlier source-stack control:

- No blue finite-chunk debug background.
- Uses a 5x5 loaded neighborhood.
- Uses a same-source transition rule, so the boundary is intentionally subtle.
- Stays in the source-stack visual lane instead of the old alpine/debug splat
  context.

This does not fully close M7. It proves the automatic boundary path can be
reviewed inside the repaired visual context. M7 still needs:

- a stronger but clean cross-material control pair;
- a walk/iso/topdown parity pass;
- transition-mask metrics rerun for each future cross-material stress scene;
- a far-field/finite-footprint policy before horizon views are promoted.

The same-source control now has a quantitative mask QA pass in
`M7_TRANSITION_MASK_METRICS_2026_05_08.md`: 25 loaded chunks, 5 boundary-mask
chunks, mean band coverage `0.280469`, and worst mean chunk-edge band delta
`0.047768`.

## Next Refinement

1. Use this as the M7 same-source control.
2. Add a second source-stack cross-material stress capture once the source
   materials stop sabotaging the read.
3. Reuse the mask metric audit for every M7 cross-material trial.
4. Combine M7 boundary masks with the M6 collision review.
