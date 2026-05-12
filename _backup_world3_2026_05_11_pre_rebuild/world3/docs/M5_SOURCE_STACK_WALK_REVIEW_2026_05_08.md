# M5 Source-Stack Walk Review

Date: 2026-05-08

## Purpose

This is the first M5 rerender after the M4 source-stack context repair. The old
M5 walk capture proved streaming, but inherited the bad prototype M4 material
context.

This pass keeps the M5 streaming contract while swapping in the repaired M4
source-stack terrain context:

- `ChunkLoader.gd`
- 256 m chunks
- 8 m mesh spacing
- source-stack terrain material
- 256 m scripted walk distance
- inspection camera that avoids the known finite-footprint horizon failure

## Capture And Metrics

- `docs/captures/m5/walk_source_stack_after_crossing.png`
- `docs/captures/m5/walk_source_stack_metrics.json`
- `scenes/capture_phase_m5/walk_source_stack.tscn`

Metrics from this run:

- Peak loaded chunks: `25`
- Chunks built: `5`
- Chunks removed: `5`
- Distance: `256 m`
- Frame p95: `4.275 ms`
- Worst update: `30.067 ms`
- Collision chunks: `0` for this visual rerender

## Read

The first walk-camera attempt failed visually because it exposed finite source
footprint edges and horizon artifacts. The accepted capture uses an inspection
camera instead. That is a deliberate review compromise: it proves M5 can stream
the repaired M4 context without presenting a false far-field beauty shot.

This does not close M5 visually. A real walk/iso/topdown parity pass still
needs a wider or clipped source-stack footprint, plus a far-field policy.

## Next Refinement

1. Keep this as M5 visual-rerender evidence for the source-stack path.
2. Do not promote first-person/horizon M5 captures until finite-footprint and
   far-field coverage are solved.
3. Re-enable collision in the M6 lane after the visual framing is stable.
4. Feed this context into the next M7 boundary rerender.
