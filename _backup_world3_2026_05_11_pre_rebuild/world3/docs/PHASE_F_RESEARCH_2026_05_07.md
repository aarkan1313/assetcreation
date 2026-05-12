# Phase F — Multi-tile / Continuous World: Research Findings (2026-05-07)

This is the F.1 deliverable: survey of approaches to continuous-world
streaming in Godot 4.5 with the constraints world3 has today.

## Constraints we're inheriting from B/C/D/E

- **Heightmap as PNG + meta.json** is our terrain source format.
  `world3/scripts/Terrain.gd` builds a 256-subdiv plane mesh from one
  heightmap on `_ready` and writes the elev_min/range to the bound
  ShaderMaterial.
- **Per-mode `terrain_blend_<kit>_<mode>.tres`** is bound by the
  active scene (walk/iso/topdown). Phase E. Any Phase F approach
  must keep this material model — we don't want to throw away the
  Phase E tuning work.
- **Per-region kit binding** via `RegionGalleryCapture.gd` swap-on-load.
  Phase D. A continuous-world approach has to handle the case where
  walking across a chunk boundary crosses a kit boundary (e.g.
  alpine → tundra at a snowline).
- **OpenTopo as DEM source.** ~16 regions × 4-20km. Each region is
  one heightmap today.

## Three architectural options

### A. Roll our own chunk streamer on top of `Terrain.gd`

Extend `Terrain.gd` to accept an XZ offset + a heightmap region
(image rect inside the source PNG). Spawn N×N `Terrain` MeshInstance3D
nodes, one per chunk, each rendering a sub-rect of a larger heightmap.

**Pros:**
- Reuses everything we built (Terrain.gd, materials, shader, meta.json).
- No new plugin install, no GDExtension build.
- Per-chunk material binding lines up with the Phase D/E pattern.

**Cons:**
- We hand-roll LOD, frustum culling, mesh memory. None of this is
  trivial; getting the seam-stitching at chunk boundaries right
  (matched normals, no z-fighting, matching tessellation) is fiddly.
- 256 subdivisions × N×N chunks = quadratic vertex cost. Phase F.5
  will measure but at 4×4 chunks that's already 1M vertices.
- Walk-mode framerate target unmet without LOD.

**Effort:** Maybe 2-3 sessions to a working prototype + LOD sketch.

### B. Adopt Terrain3D plugin as runtime target

Terrain3D (TokisanGames, MIT, v1.0.1 Jun 2025, GDExtension):
- Clipmap-LOD terrain rendering.
- Imports heightmap PNG + control map + splatmap directly.
- Up to 32 texture sets per terrain.
- Built-in foliage instancing.
- Documented Godot 4.5 support (need to check current release).

**Pros:**
- LOD, clipmap streaming, foliage already solved.
- Production-tested by other Godot 4 projects.
- Designed for the heightmap+splat workflow we already produce.

**Cons:**
- New plugin in the project; one more thing to keep up to date.
- Our `terrain_blend.gdshader` is custom and uses height-band + slope
  masks rather than splatmaps. Two sub-options to bridge:
  - **B1**: Generate splatmaps offline from height-band thresholds
    (one-time per region) and feed Terrain3D's splat-driven shader.
    Loses our shader's runtime height-band tuning but gains LOD.
  - **B2**: Replace Terrain3D's shader with our `terrain_blend.gdshader`
    via material override. Documented but harder to verify until
    we try it.
- Terrain3D doesn't speak our `meta.json` directly; would need an
  adapter that reads our heightmap + writes Terrain3D's expected
  format on demand.

**Effort:** Probably 1-2 sessions to import a single Tetons region as
a Terrain3D scene and verify it looks like our current iso/topdown
captures. Plus 1 session to wire kit binding.

### C. HTerrain plugin (older, Godot 4 still supported)

Less work than B but Terrain3D explicitly outclasses HTerrain on
LOD + scaling per the prior research. Skip in favor of B.

## Recommendation

**Start with Option A for F.3 (the 2x2 stitch test) — it's quick to
prototype and tells us whether stitching works in our current
pattern.** If A reveals fundamental seam/LOD issues that won't go
away, transition to Option B for F.4+.

Rationale:
- F.3's 2x2 Tetons grid is a small enough test that rolling our own
  is fine. We're testing whether `Terrain.gd` with XZ offsets stitch
  cleanly, not whether we can scale to 100×100 chunks.
- If A passes, F.4 (streaming prototype) inherits everything we
  already wrote. We get to keep the Phase E material tuning.
- If A fails (seam discontinuities, framerate, memory), F.4 becomes
  "swap to Terrain3D" with the work in F.3 informing what an adapter
  needs to do.
- B is a bigger commitment. Don't make it before A's verdict.

## Memory budget upper bound (back-of-envelope)

Per chunk at 256 subdivisions:
- Vertices: 257² × 3 floats × 4 bytes = ~792 KB position data.
- Normals: same = ~792 KB.
- UVs: 257² × 2 floats × 4 = ~528 KB.
- Indices: 256² × 6 × 4 = ~1.5 MB.
- Total mesh: ~3.6 MB per chunk.
- Material textures (5 PBR sets × 3 maps × 1K res × 4 bytes): ~60 MB
  but shared across chunks of the same kit, so amortized.
- HeightMapShape3D collision: another 257² × 4 = ~264 KB.

Budget at 4×4 grid (16 chunks) of one kit: ~58 MB mesh + 60 MB shared
textures = ~120 MB. Comfortably fits in any GPU. At 8×8 = ~230 MB
mesh + textures shared.

The bottleneck is *vertex count for rendering* (16 × 65k = ~1M verts
in view), not memory. Solves itself with LOD or chunk subdivision
reduction at distance.

## What this means for F.2 (chunk-size decision)

Two viable defaults:
- **256m chunk @ 256 subdivisions → 1m sample spacing.** Walk-mode
  detail. 9 chunks for a 768m visibility circle.
- **512m chunk @ 256 subdivisions → 2m sample spacing.** Iso/topdown
  detail. 4 chunks for the same visibility circle.

A region (4-20km today) is not a chunk — it's the boundary of one
DEM. A region splits into chunks at build time when we adopt
streaming. The current per-region heightmap PNGs stay; we just sample
sub-rects.

Recommendation: **start with 512m @ 256 subdiv** (iso/topdown
default), revisit if walk-mode needs finer detail. Iso-mode 300m
diameter (Phase C lock) fits in one chunk, simplifying gallery
captures.

## Decision (to lock in F.6)

After F.3 + F.4 evidence:
- If Option A scales cleanly, Phase F closes with an "extended
  Terrain.gd + chunk streamer + LOD-by-distance" implementation.
- If Option A surfaces hard problems, Phase F closes with a
  "Terrain3D-as-runtime + adapter pipeline that reads our region
  heightmaps" implementation.

Either way: chunk size 512m, sub-rect sampled from per-region
heightmap, kit-aware material binding inherited from Phase D/E,
walker-XZ-driven streaming.

## Open questions for the user

- **Cross-kit chunk boundaries.** A walker crossing from alpine into
  tundra: hard cut at chunk boundary, or shader-blend across? Phase F
  could demo either; default is hard cut (matches how regions work
  today).
- **DEM seam handling for real cross-region walks.** Two adjacent
  regions don't share elevation reference. Building a smooth
  transition requires either DEM-level pre-mosaic (the OpenTopo
  branch is already doing this, owned by other chat) or per-region
  walls / loading-screens. Default for F: same-region only; cross-
  region is a follow-up.

## References pulled forward

- `research/A_terrain.md` — full terrain research doc; Terrain3D
  identified as engine target.
- `world3/scripts/Terrain.gd` — current single-heightmap mesh builder.
- `world3/scripts/RegionGalleryCapture.gd` — region-load + per-mode
  material swap pattern; extends naturally to chunk-load.
- `world3/jobs/regions.json` — 16 regions × bundle paths.
- ROADMAP.md "Phase F" section — checklist + exit criteria.
