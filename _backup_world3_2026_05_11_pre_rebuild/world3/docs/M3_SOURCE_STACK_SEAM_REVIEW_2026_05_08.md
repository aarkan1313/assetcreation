# M3 Source-Stack Seam Review

Date: 2026-05-08

## Purpose

M3's original chunk sweep is a technical validation: chunk sizes, seam behavior,
and synchronous runtime cost. Its old screenshot is not a visual target.

This pass adds a visual-facing M3 seam capture that uses the repaired M4
source-stack material context while preserving the M3 contract:

- 256 m chunks
- 8 m mesh spacing
- `ChunkLoader.gd`
- source-stack macro terrain
- unified shader material path

## Capture

- `docs/captures/phase_f/chunk_sweep/chunk_256m_source_stack_visual_seam.png`

Scene:

- `scenes/capture_phase_f/chunk_256m_source_stack_visual_seam.tscn`

## Read

This capture shows why M3 improves after M4 repair: the chunk seam evidence no
longer has to be viewed through the old debug/prototype material context. M3 is
still primarily an engineering gate, but it now has a visual-facing review image
that is compatible with the source-stack target.

This does not replace the original `chunk_sweep_metrics.json` or the old
256/512/1024 m comparison captures. Those remain the technical proof for chunk
size selection.

## Next Refinement

1. Add a seam-specific visual metric that compares color/normal discontinuity
   across chunk borders.
2. Re-run this view after M4 wider/topdown/iso framing is solved.
3. Keep M3 acceptance tied to seam/performance behavior, not beauty shots.
