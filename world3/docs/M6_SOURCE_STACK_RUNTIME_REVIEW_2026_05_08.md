# M6 Source-Stack Runtime Review

Date: 2026-05-08

## Purpose

This reruns the M6 collision/runtime-hardening lane over the repaired M4/M5
source-stack context. The original M6 evidence is still the runtime-cache and
collision proof, but it inherited the old prototype visual context.

This pass keeps M6 focused on runtime behavior:

- 256 m chunks
- 8 m mesh spacing
- source-stack terrain material
- 25 loaded chunks in a 5x5 inspection neighborhood
- streamed collision chunks enabled
- scripted 256 m movement

## Capture And Metrics

- `docs/captures/m6/walk_source_stack_collision.png`
- `docs/captures/m6/walk_source_stack_collision_metrics.json`
- scene: `scenes/capture_phase_m5/walk_source_stack.tscn`
- runner: `scripts/M5WalkStreamRunner.gd`

Metrics from this run:

- Peak loaded chunks: `25`
- Chunks built: `30`
- Chunks removed: `5`
- Collision chunks built: `30`
- Collision total: `78.812 ms`
- Collision max: `3.244 ms`
- Frame p95: `4.32 ms`
- Worst update: `43.332 ms`

## Read

The visual frame is intentionally the same inspection-camera source-stack review
used by M5. M6 is not an art milestone; it proves the repaired context can still
run with collision chunks and measurable runtime behavior.

The worst update spike is higher than the no-collision M5 visual rerender
because this run rebuilds collision chunks after reset. That is acceptable as a
diagnostic, but async/background build remains the future runtime polish path.

## Next Refinement

1. Keep M6 acceptance tied to cache/collision/performance contracts.
2. Add async/background collision and mesh build once interaction polish starts.
3. Re-run this check after M7 boundary masks are combined with collision.
