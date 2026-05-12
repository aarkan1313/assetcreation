# M5 Streaming Budget

Date: 2026-05-08

## Current Budget

This budget applies to the wired M5 prototype-final `walk.tscn` path:

```text
base chunk size = 256 m
mesh spacing = 8 m
subdivisions per chunk = 32
loaded radius = 1 chunk
loaded visual neighborhood = 3 x 3 = 9 chunks
vertices per visual chunk = 33 x 33 = 1,089
triangles per visual chunk = 32 x 32 x 2 = 2,048
total near-field visual triangles = 18,432
```

The hidden legacy `Terrain.gd` still builds the single full-region mesh and
collision shape. That is a temporary M5 bridge, not part of the final streaming
budget.

## Measured Evidence

M3 synthetic sweep at the same 256 m / 8 m / 3x3 settings:

```text
frame mean = 4.42 ms
frame p95 = 17.11 ms
frame p99 = 20.05 ms
worst load = 19.37 ms
peak video memory = 122.99 MB
```

M5 scripted walk-scene crossing:

```text
distance = 900 m along +Z
chunk path = [0,5] -> [0,9]
peak loaded chunks = 9
chunks built = 12
chunks removed = 12
worst synchronous update = 18.816 ms
frame mean / p95 / p99 / max = 4.255 / 4.593 / 4.768 / 19.351 ms
```

M5 long-form sampled walk review:

```text
distance = 1536 m along +Z
chunk path = [0,5] -> [0,11]
peak loaded chunks = 9
chunks built = 18
chunks removed = 18
worst synchronous update = 18.317 ms
frame mean / p95 / p99 / max = 4.152 / 4.582 / 4.661 / 19.076 ms
```

## Interpretation

The current synchronous loader is acceptable for prototype review, but it is
not a production streaming budget yet. The worst update is still over one
60 Hz frame (16.67 ms), while p99 measured frame time in the scripted review is
under 5 ms because chunk rebuild spikes are infrequent. This confirms that
256 m is the right synchronous base size for now, and that the next performance
work should target rebuild spikes rather than steady-state rendering.

The visible mesh budget is modest. The risk is not steady-state triangle count;
it is synchronous chunk construction and, later, collision/scatter/material
work arriving on the same frame.

## Rules For Next Iteration

- Keep 256 m as the base walk chunk size.
- Keep `chunk_resolution_m = 8` until the visual stream needs more close-range
  terrain geometry.
- Increase `view_radius_chunks` before increasing base chunk size if the horizon
  feels too short.
- Do not move to 512 m base chunks until mesh generation is async, prebuilt, or
  pooled.
- Treat streamed collision as a separate budget line; do not hide its cost in
  the visual chunk budget.

## Production Hardening Targets

1. Background mesh generation or a chunk mesh cache.
2. Chunk pooling to avoid allocation churn.
3. Streamed collision chunks with their own update cadence.
4. Export-safe heightmap and splat-map loading.
5. Far-field LOD tiles, likely 512 m or larger, after near-field streaming is
   stable.
