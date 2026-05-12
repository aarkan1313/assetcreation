# Phase F / M3 Chunk-Size Sweep

Date: 2026-05-08

## Verdict

Use **256 m** as the current base runtime chunk size for the synchronous
`walk.tscn` streaming path.

Why: at the current 8 m mesh spacing and 3x3 loaded neighborhood, 256 m is
the only tested size that keeps worst-case synchronous chunk update latency
near a single 60 Hz frame. 512 m and 1024 m are viable only after background
mesh builds, chunk pooling, or coarser far-LOD tiers.

This locks the **base chunk format**, not the eventual far-field LOD system:

- Base chunk size: `256 m`
- Mesh spacing: `8 m`
- Subdivisions per base chunk: `32`
- Loaded neighborhood for the sweep: 3x3 chunks around the target
- Height source: `res://heightmap/heightmap.png`, tiled as a synthetic
  infinite field
- Border normals: sampled from global source positions one mesh step outside
  the chunk footprint

## Evidence

Raw metrics: `world3/docs/captures/phase_f/chunk_sweep/chunk_sweep_metrics.json`

| Chunk size | Subdivisions | Peak chunks | Frame mean | Frame p95 | Frame p99 | Worst load | Peak video mem | Seam capture |
|------------|--------------|-------------|------------|-----------|-----------|------------|----------------|--------------|
| 256 m | 32 | 9 | 4.42 ms | 17.11 ms | 20.05 ms | 19.37 ms | 122.99 MB | `chunk_256m_seam.png` |
| 512 m | 64 | 9 | 7.01 ms | 65.48 ms | 72.10 ms | 71.44 ms | 125.22 MB | `chunk_512m_seam.png` |
| 1024 m | 128 | 9 | 17.25 ms | 260.86 ms | 263.28 ms | 262.63 ms | 130.89 MB | `chunk_1024m_seam.png` |

## Visual-Facing Seam Review

2026-05-08 update: the original M3 seam captures remain technical diagnostics.
After the M4 source-stack context repair, M3 also has a visual-facing 256 m seam
capture:

- `world3/docs/captures/phase_f/chunk_sweep/chunk_256m_source_stack_visual_seam.png`
- `world3/scenes/capture_phase_f/chunk_256m_source_stack_visual_seam.tscn`

This uses the same 256 m chunk / 8 m mesh spacing contract, but displays it
through source-stack terrain instead of the old debug/prototype material view.
See `world3/docs/M3_SOURCE_STACK_SEAM_REVIEW_2026_05_08.md`.

## Interpretation

The sweep keeps vertex spacing constant at 8 m, so larger chunks do more work
per synchronous build:

- 256 m builds 33x33 vertices per chunk.
- 512 m builds 65x65 vertices per chunk.
- 1024 m builds 129x129 vertices per chunk.

All three sizes held the same 3x3 loaded neighborhood and stayed in a narrow
video-memory band. The differentiator is load latency, not steady memory.

256 m does churn more often in world distance, but at walk-mode speeds this is
manageable and leaves headroom for the M5 integration. 512 m can become the
mid/far terrain tile once mesh generation is async or moved to an offline cache.
1024 m should be treated as far-LOD or prebuilt-region scale, not a synchronous
near-field streaming chunk.

## Implementation

- `world3/scripts/ChunkLoader.gd` builds streamed chunks around an XZ target.
- `world3/scripts/ChunkSweepRunner.gd` runs the 256/512/1024 m sweep and writes
  metrics plus seam captures.
- `world3/scenes/capture_phase_f/chunk_size_sweep.tscn` is the executable
  sweep scene.
- Captures live under `world3/docs/captures/phase_f/chunk_sweep/`.

## Normal-Seam Fix

The F.3 stitch test showed a faint shading seam because `Terrain.gd` computed
border normals from one-sided finite differences inside each chunk. The M3
loader fixes this for the chunked path by sampling heights from the global
height source at `x +/- mesh_step` and `z +/- mesh_step`, even when that sample
falls outside the current chunk footprint.

That means neighboring chunks compute the same normal at shared border vertices.

## Follow-up

M5 prototype-final has wired `ChunkLoader.gd` into `walk.tscn` with:

- `chunk_size_m = 256`
- `chunk_resolution_m = 8`
- `view_radius_chunks = 1` initially
- collision still deferred; the legacy single terrain remains hidden as the
  collision source while streamed chunks provide the visible terrain

If walk speed or camera horizon pushes the 3x3 256 m neighborhood too small,
increase radius before increasing base chunk size. Increase chunk size only
after async build/cache exists.

Final M5 evidence is in `world3/docs/M5_WALK_SPLAT_STREAMING.md` and
`world3/docs/M1_M5_FINAL_AUDIT_2026_05_08.md`.
