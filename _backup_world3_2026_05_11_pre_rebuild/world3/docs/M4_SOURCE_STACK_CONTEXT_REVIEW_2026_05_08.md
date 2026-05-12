# M4 Source-Stack Context Review

Date: 2026-05-08

## Purpose

This is the first M4 visual repair slice after the M1-M7 validation review
showed that the old M4 chunk/splat captures were unacceptable as visual
evidence.

The old M4 evidence still proves shader/chunk plumbing. This pass replaces the
visual target with a source-stack context that keeps the M4 runtime contract:

- `ChunkLoader.gd`
- 256 m chunks
- 8 m mesh spacing
- `terrain_splat_unified.gdshader`
- source macro albedo with `source_macro_valid_mask`
- low-strength tileable detail material

## Captures

- `docs/captures/m4/source_stack_context_current_close.png`
- `docs/captures/m4/source_stack_context_comfy_v3_close.png`
- `docs/captures/m4/source_stack_context_review.png`

Scenes:

- `scenes/capture_phase_m4/source_stack_context_current_close.tscn`
- `scenes/capture_phase_m4/source_stack_context_comfy_v3_close.tscn`

## Read

This is a clear improvement over the old M4 diagnostic captures:

- No blue finite-chunk background in the review frame.
- No obvious rectangular material regions from the old height/slope splat map.
- The M4 path is now shown through the source-stack macro terrain that matches
  the current visual target.
- The Comfy v3 sidecar remains calmer than the current grassland detail, but it
  is still not promoted.

This does not close M4 visually yet. It is close-view only. M4 still needs a
wider-footprint strategy for topdown/iso review that does not expose the finite
source-stack boundary as a beauty shot.

## Next Refinement

1. Build a wider or masked source-stack review footprint so topdown/iso can be
   evaluated without blue/debug boundaries.
2. Feed this M4 material context into M5 walk streaming.
3. Re-run M7 boundary placement over the same repaired M4/M5 context.
4. Keep the old M4 splat/chunk captures in diagnostics only.
