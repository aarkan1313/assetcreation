# M1-M7 Workflow Validation Run

Date: 2026-05-08

## Purpose

This is the fresh sequential validation pass the user requested after the
source-stack remediation work. It reruns the established M1-M7 workflow using
the current contracts and writes one review folder:

- `docs/captures/m1_m7_validation_2026_05_08/`
- `docs/captures/m1_m7_validation_2026_05_08/m1_m7_validation_contact_sheet.png`
- `docs/captures/m1_m7_validation_2026_05_08/m1_m7_engineering_diagnostics_contact_sheet.png`
- `docs/captures/m1_m7_validation_2026_05_08/README.md`
- `docs/captures/m1_m7_validation_2026_05_08/manifest.json`
- `M1_M7_REFINEMENT_MAP_2026_05_08.md`

## Sequence Run

1. M1 catalog validation card.
2. M2 transition-strip Godot review capture.
3. M3 chunk-size sweep rerun; 256 m seam capture copied into the suite.
4. M4 chunk splat stream capture.
5. M5 walk streaming runner capture and metrics.
6. M6 cache/collision walk runner capture and metrics.
7. M7 source-stack boundary control capture.

## Verdict

| Milestone | Status | Read |
|-----------|--------|------|
| M1 | PASS | Catalog has 31 materials, 5 biome kits, and no missing kit references. |
| M2 | PASS / REVIEW | Transition workflow is demonstrable, but the view is still a debug comparison board. |
| M3 | PASS | Chunk sweep reruns and preserves 256 m seam evidence. |
| M4 | PIPELINE PASS / VISUAL REWORK | Unified splat shader works, but current material context still reads debug/prototype. |
| M5 | PIPELINE PASS / VISUAL REWORK | Streaming chunks and metrics work; visible terrain remains below the 70 percent target. |
| M6 | PIPELINE PASS / VISUAL REWORK | Runtime cache/collision path works; visual context is still inherited from M5. |
| M7 | WORKFLOW PASS / VISUAL REWORK | Boundary placement runs over source-stack terrain, but the control capture remains diagnostic. |

## Important Read

This suite validates that the M1-M7 workflow can be rerun in order. It does not
promote M4-M7 to final visual quality.

The user rejected the diagnostic M3/M4-style finite chunk views as visual
evidence. That read is correct: they are engineering diagnostics, not quality
targets. The main visual contact sheet now only carries close-view source-stack
baseline candidates. The bad prototype/debug terrain captures remain in the
engineering diagnostics sheet so we can prove workflow plumbing without
confusing it with art approval.

The strongest visual direction is still the source-stack path, but M4/M5/M7
need rerenders after source-material cleanup and source-stack framing before
visual closure. Use `M1_M7_REFINEMENT_MAP_2026_05_08.md` to refine each
milestone instead of blindly advancing the roadmap.

M4 update: `M4_SOURCE_STACK_CONTEXT_REVIEW_2026_05_08.md` adds the first
acceptable close-view M4 context using 256 m chunks, 8 m mesh spacing, and the
unified shader over source-stack terrain. The main visual contact sheet now
uses those M4 source-stack captures. Wider/topdown/iso M4 review remains open.

M3/M5 update: M3 now has a source-stack visual seam capture
(`M3_SOURCE_STACK_SEAM_REVIEW_2026_05_08.md`), and M5 has a source-stack
inspection walk rerender (`M5_SOURCE_STACK_WALK_REVIEW_2026_05_08.md`). The
old M3/M5 captures remain technical diagnostics.

M6/M7 update: M6 now has a source-stack collision rerender
(`M6_SOURCE_STACK_RUNTIME_REVIEW_2026_05_08.md`), and M7 has a cleaner
source-stack same-source boundary context
(`M7_SOURCE_STACK_BOUNDARY_REVIEW_2026_05_08.md`). M7 is improved but not
visually closed. Same-source mask metrics now pass
(`M7_TRANSITION_MASK_METRICS_2026_05_08.md`); cross-material stress and view
parity remain open.
