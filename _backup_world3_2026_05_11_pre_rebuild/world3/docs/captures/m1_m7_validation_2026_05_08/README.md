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
| M2 | PASS / DEBUG REVIEW | Transition rules and hard-cut comparisons are reproducible; the review board stays diagnostic. |
| M3 | PASS / SOURCE-STACK BASELINE | Chunk sweep reruns and now has repaired source-stack seam evidence. |
| M4 | PIPELINE PASS / SOURCE-STACK BASELINE | Unified splat path runs over source-stack context; Comfy sidecar remains quarantined. |
| M5 | PIPELINE PASS / SOURCE-STACK BASELINE | Streaming walk runs over repaired source-stack context using inspection framing. |
| M6 | RUNTIME PASS / SOURCE-STACK BASELINE | Runtime cache and streamed collision run over the repaired source-stack context. |
| M7 | WORKFLOW PASS / SOURCE-STACK CONTROL | Boundary placement runs in source-stack context; same-source control and mask QA pass but final closure remains open. |

## Sequence

- **M1**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m1_catalog_validation.png
  Material catalog and biome-kit reference contract.
- **M2**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m2_transition_strip_review.png
  Catalog-driven transition strips beside hard-cut controls; debug review board.
- **M3**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m3_chunk_256m_seam.png
  256 m chunk seam capture from the chunk-size sweep.
- **M4**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m4_chunk_splat_stream_review.png
  Original streamed-chunk diagnostic for the unified splat material.
- **M5**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m5_walk_stream_after_crossing.png
  Original walk-streaming diagnostic; source-stack rerender is in the visual sheet.
- **M6**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m6_walk_stream_collision_cache.png
  Original runtime cache + streamed collision diagnostic.
- **M7**: `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m7_boundary_runtime_source_stack_control.png
  Original automatic boundary-mask diagnostic control.

## Main Visual Sheet

- `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m3_source_stack_visual_seam.png
  256 m chunk seam displayed through the repaired source-stack visual context.
- `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m4_source_stack_context_current_close.png
  256 m ChunkLoader path with source macro terrain and current grassland detail.
- `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m4_source_stack_context_comfy_v3_close.png
  Same M4 source-stack path with Comfy v3 sidecar detail; still quarantined.
- `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m5_source_stack_walk_after_crossing.png
  Walk streaming over the repaired M4 context using an inspection camera.
- `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m6_source_stack_collision.png
  Same source-stack walk context with streamed collision chunks enabled.
- `present` - world3/docs/captures/m1_m7_validation_2026_05_08/m7_boundary_runtime_source_stack_context.png
  Automatic boundary mask over a source-stack same-source control context.

## Read

This suite validates that the M1-M7 workflow can be rerun in order.
It is not a blanket visual promotion. The main sheet is the current
source-stack visual baseline and intentionally excludes finite-chunk,
topdown, and debug terrain captures that still read as prototype evidence.
Those remain in the engineering diagnostics sheet because they prove
plumbing, not art quality. M7 now has a cleaner same-source control
and same-source mask QA, but still needs cross-material stress with
its own metrics plus walk/iso/topdown parity before production-visual
closure.
