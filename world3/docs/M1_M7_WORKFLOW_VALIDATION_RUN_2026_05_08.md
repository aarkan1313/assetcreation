# M1-M7 Workflow Validation Run

Date: 2026-05-08

## Purpose

This is the fresh sequential validation pass the user requested after the
source-stack remediation work. It reruns the established M1-M7 workflow using
the current contracts and writes one review folder:

- `docs/captures/m1_m7_validation_2026_05_08/`
- `docs/captures/m1_m7_validation_2026_05_08/m1_m7_validation_contact_sheet.png`
- `docs/captures/m1_m7_validation_2026_05_08/README.md`
- `docs/captures/m1_m7_validation_2026_05_08/manifest.json`

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

The strongest visual direction is the source-stack path. The M4-M6 runtime
captures still show the old procedural/debug splat context, so the roadmap
should continue with source-material cleanup, source-stack framing, and M5/M7
rerenders before visual closure.
