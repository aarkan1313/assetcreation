# M1-M7 Workflow Validation Run

Date: 2026-05-08

This is a sequential validation pass over the established M1-M7 workflow
using the current source-stack valid-mask and M7 source-stack control state.
It deliberately separates credible visual baseline candidates from
engineering diagnostics that prove workflow plumbing.

## Summary

- M1 catalog status: `PASS`
- Catalog material count: `31`
- Biome kit count: `5`
- Visual validation sheet: `m1_m7_validation_contact_sheet.png`
- Engineering diagnostics sheet: `m1_m7_engineering_diagnostics_contact_sheet.png`
- Refinement map: `../../M1_M7_REFINEMENT_MAP_2026_05_08.md`

## Milestone Verdicts

| Milestone | Status | Read |
|-----------|--------|------|
| M1 | PASS | Catalog and biome-kit material references resolve. |
| M2 | PASS / REVIEW | Transition workflow is demonstrable, but the view is still a debug comparison board. |
| M3 | PASS | Chunk sweep reruns and preserves 256 m seam evidence. |
| M4 | PIPELINE PASS / VISUAL REWORK | Unified splat shader works, but the current material context is still debug-looking. |
| M5 | PIPELINE PASS / VISUAL REWORK | Streaming chunks and metrics work; the visible terrain remains below the 70 percent visual target. |
| M6 | PIPELINE PASS / VISUAL REWORK | Runtime cache/collision path works; visual context is still inherited from M5. |
| M7 | WORKFLOW PASS / VISUAL REWORK | Boundary placement runs over source-stack terrain, but the control capture remains diagnostic. |

## Sequence

- **M1**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m1_catalog_validation.png
  Material catalog and biome-kit reference contract.
- **M2**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m2_transition_strip_review.png
  Catalog-driven transition strips beside hard-cut controls; debug review board.
- **M3**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m3_chunk_256m_seam.png
  256 m chunk seam capture from the chunk-size sweep.
- **M4**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m4_chunk_splat_stream_review.png
  Streamed chunk set consuming the unified splat material; visual context still needs repair.
- **M5**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m5_walk_stream_after_crossing.png
  Walk scene crosses streamed chunks; terrain read remains below visual target.
- **M6**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m6_walk_stream_collision_cache.png
  Runtime cache + streamed collision validate, but inherit the M5 visual context.
- **M7**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m7_boundary_runtime_source_stack_control.png
  Automatic boundary path over valid-mask source-stack terrain; diagnostic control.

## Main Visual Sheet

- `present` - world3/docs/captures/m1_m7_validation_2026_05_08/source_stack_grassland_current_close.png
  Current best terrain direction: source macro terrain plus low-strength detail.
- `present` - world3/docs/captures/m1_m7_validation_2026_05_08/source_stack_grassland_comfy_v3_detail_stress_close.png
  Comfy sidecar is calmer than current grassland detail, but not promoted.

## Read

This suite validates that the M1-M7 workflow can be rerun in order.
It is not a blanket visual promotion. The main sheet is now visual-focused
and intentionally excludes finite-chunk/topdown/debug terrain captures that
still read as bad prototype evidence. Those remain in the engineering
diagnostics sheet because they prove plumbing, not art quality. M7 remains
workflow-pass / visual-rework until source-material cleanup, source-stack
framing, and M5/M7 rerenders close.
