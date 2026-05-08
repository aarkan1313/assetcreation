# M1-M5 Final Audit

Date: 2026-05-08

## Verdict

The M1-M5 workflow iteration is complete at **prototype final form**.

It proves the intended pipeline shape:

```text
catalog material IDs
-> generated transition boundary assets
-> locked 256 m chunk format
-> unified five-slot splat shader
-> walk.tscn streaming visual terrain
```

This is not production-final terrain. It is a working workflow spine with
review evidence, performance measurements, and explicit next hardening targets.

## Spec Audit

| Milestone | Spec Target | Status | Evidence |
|-----------|-------------|--------|----------|
| M1 | Single source of truth for procedural + OpenTopo materials | PASS | `world3/materials/catalog.json`, `world3/materials/CATALOG.md`, catalog-backed kit generation |
| M2 | 4-6 transition prototypes reading better than hard cuts | PASS | `world3/docs/M2_TRANSITION_MATERIAL_PROTOTYPE.md`, `world3/jobs/biome_transition_rules.json`, transition captures |
| M3 | Evidence-backed chunk-size lock | PASS | `world3/docs/PHASE_F_CHUNK_SIZE_SWEEP.md`; 256 m locked |
| M4 | Unified splat shader prototype consuming chunk weights | PASS | `world3/docs/M4_SPLAT_SHADER_PROTOTYPE.md`, `world3/docs/M4_CHUNK_MATERIAL_CONTRACT.md` |
| M5 | `walk.tscn` uses streaming chunks + splat shader, crosses boundaries, records budget | PASS FOR PROTOTYPE | `world3/docs/M5_WALK_SPLAT_STREAMING.md`, `world3/docs/M5_STREAMING_BUDGET.md`, M5 captures/metrics |

## M5 Final Evidence

Static walk capture:

```text
capture = world3/docs/captures/m5/walk_chunk_splat_smoke.png
size = 1920 x 1080
mean RGB = 153.59, 120.44, 98.58
stddev RGB = 15.87, 21.46, 26.71
```

Short crossing smoke:

```text
metrics = world3/docs/captures/m5/walk_stream_smoke_metrics.json
frames = 360
distance = 900 m
chunk path = [0,5] -> [0,9]
peak loaded chunks = 9
chunks built = 12
chunks removed = 12
worst chunk update = 18.816 ms
frame mean / p95 / p99 / max = 4.255 / 4.593 / 4.768 / 19.351 ms
```

Long-form sampled walk review:

```text
contact sheet = world3/docs/captures/m5/walk_long_contact_sheet.png
metrics = world3/docs/captures/m5/walk_long_metrics.json
frames = 1800
distance = 1536 m
chunk path = [0,5] -> [0,11]
peak loaded chunks = 9
chunks built = 18
chunks removed = 18
worst chunk update = 18.317 ms
frame mean / p95 / p99 / max = 4.152 / 4.582 / 4.661 / 19.076 ms
```

## What Improved During M5

- `walk.tscn` now starts near the terrain instead of high in the sky.
- Visible terrain is streamed through `ChunkLoader.gd` using
  `terrain_splat_alpine.tres`.
- Legacy single `Terrain.gd` is hidden and retained only for collision.
- Chunk UVs now match the height sampler's wrapped source fraction, which fixed
  the first smoke-test material split at chunk edges.
- `M5WalkStreamRunner.gd` now produces short/long crossing metrics, frame
  timing summaries, and sampled review frames.

## Known Production Gaps

These are real and should not be hidden:

- **Source material quality**: the grass/leaves texture is too noisy and too
  visibly green at close range. This is a material-generation QA issue, not a
  chunk/splat workflow failure.
- **Splat intelligence**: current weights are height/slope-derived only. They
  do not yet use biome adjacency, M2 transition strips, canopy masks, soil
  classes, or authored paint.
- **Runtime boundary strips**: M2 transition assets exist but are not sampled by
  the runtime shader yet.
- **Collision**: player collision still comes from the hidden full-region
  terrain, not streamed chunks.
- **Export safety**: heightmap and generated splat PNGs are loaded through
  runtime `Image.load_from_file()` in dev. Export-safe import/cache remains
  unsolved.
- **Synchronous loading**: 256 m chunks are acceptable for the prototype, but
  worst updates still exceed one 60 Hz frame. Production needs async build,
  prebuild/cache, or pooling.
- **Material indirection**: M4/M5 are fixed to five semantic terrain slots.
  Arbitrary catalog material tables and texture arrays are future work.

## Next Roadmap Move

The clean next phase is **M6: harden the streaming material runtime**.

Recommended order:

1. Export-safe generated image import/cache for height and splat maps.
2. Streamed collision chunks with separate budget measurements.
3. Runtime boundary-strip sampling for M2 transition assets.
4. Source-material QA pass for noisy grass/leaves before more visual breadth.

This order keeps the workflow honest: first make the runtime path robust, then
make boundaries richer, then improve source asset quality.
