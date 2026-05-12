# Phase F.3 — 2x2 Stitch Test (2026-05-07)

Test scene: `world3/scenes/capture_phase_f/tetons_2x2_stitch.tscn` and
`tetons_2x2_stitch_topdown.tscn`. Four `Terrain.gd` instances, all
loading the same Tetons heightmap (4km × 4km), translated to ±2000m
on X/Z so the 4 tiles form an 8km × 8km grid.

## Captures

| File | Notes |
|------|-------|
| `tetons_2x2_iso.png` | Iso angle, anchor-mode framing at 10km diameter. Iso projection makes adjacent tiles look like 4 separate rendered chunks with sky between, but this is a perspective artifact — see topdown. |
| `tetons_2x2_topdown.png` | Straight-down framing at 9km diameter. The 4 tiles read as one continuous 8km square with no sky gaps. Confirms F.3's basic geometric stitch works. |

## F.3 verdict: PASS with one caveat

**Geometry stitches cleanly.** Each tile's mesh extends from local
`-half_x..+half_x` (i.e. ±2000m). After ±2000m XZ translation, tile
edges meet at the world-axis lines and share elevation values
(because they're sampling identical heightmap pixels at the seam).
The topdown render shows no sky-color gap between the 4 tiles.

**Caveat: per-chunk normal computation creates a faint seam.** Each
chunk's `Terrain.gd._build_mesh` computes normals via finite
differences from its own height grid. At the chunk's outer edge,
there's no "neighbor pixel" to sample from, so the normal is one-sided
— off by half a step compared to the same vertex on the adjacent
chunk computed from the other direction. Visible as a subtle shading
seam at chunk borders under directional light. Will need addressing
in F.4 (streaming prototype) by either:
1. Sampling 1-2 pixel overlap from the source heightmap when
   building each chunk's hgrid (so border vertices get full neighbor
   context).
2. Sharing edge vertices' normals across adjacent chunks
   post-build.

Option 1 is simpler and matches how Terrain3D handles this internally.

## What this validates for F.4 onwards

- **Architecture A from PHASE_F_RESEARCH** is viable. Hand-rolling
  chunk meshes from `Terrain.gd` works for the basic stitch case.
- **Memory profile** at 4 tiles × 256 subdivisions is well within
  budget (per-tile 3.6MB mesh + 60MB shared kit textures ≈ 75MB
  for the 4-tile scene).
- **Per-chunk material binding** works fine — all 4 tiles share the
  same `terrain_blend_alpine_topdown.tres` here, but Phase F.5+
  will exercise per-chunk-different materials for kit-boundary
  testing.

## Known limitations of this test

- Same heightmap 4× means the texture pattern is identical in each
  quadrant. A real DEM stitch would need to source different sub-rects
  from a larger heightmap or load 4 different per-region heightmaps.
- All 4 chunks built statically at scene load. F.4 will add load /
  unload as the walker moves.
- No collision shapes wired in this test (each chunk would need its
  own `HeightMapShape3D`; deferred to F.4 where streaming + collision
  matter together).

## Superseded F.4 streaming prototype note

Per PLAN.md: walker XZ enters a chunk's "warmup zone" → load chunk;
walker leaves "keepalive zone" → unload. Verify load/unload doesn't
stutter and frame budget stays within target. Chunk size 512m at
256 subdivisions per F.2 default.

This note is superseded by the M3 sweep below.

## M3 chunk-size sweep outcome

M3 added a parameterized streaming loader and sweep scene:

- `world3/scripts/ChunkLoader.gd`
- `world3/scripts/ChunkSweepRunner.gd`
- `world3/scenes/capture_phase_f/chunk_size_sweep.tscn`

Results live in `chunk_sweep/`:

| File | Notes |
|------|-------|
| `chunk_sweep/chunk_sweep_metrics.json` | Raw 256/512/1024 m sweep metrics. |
| `chunk_sweep/chunk_256m_seam.png` | Winning base chunk size seam capture. |
| `chunk_sweep/chunk_256m_source_stack_visual_seam.png` | Visual-facing 256 m seam capture using the repaired M4 source-stack context. |
| `chunk_sweep/chunk_512m_seam.png` | Larger chunk comparison; higher load spike. |
| `chunk_sweep/chunk_1024m_seam.png` | Far-LOD scale comparison; too heavy synchronously. |

Verdict: use 256 m as the current synchronous base chunk size. Details:
`world3/docs/PHASE_F_CHUNK_SIZE_SWEEP.md`.
