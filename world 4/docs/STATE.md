# W4 — current state snapshot

> **What we have right now.** Last updated: 2026-05-12 (post-Stage-3).
>
> For *what to do next* see `ROADMAP.md`. For *how to take over* see
> `HANDOFF.md`. This doc is "running inventory" — refresh whenever a
> stage or axis closes.

## Active work

**Axis 1 Path 2 — real-game scale + procedural amplification.** In
progress. Plan at `plans/AXIS1_PATH2_PLAN_2026_05_12.md`. Status:

- ✅ **Stage 1 — Kernel system foundation**: complete. 17/17 pytest
  passing. Python ↔ GDScript NoiseStackKernel cross-impl max delta
  4.5e-6 m. Preview CLI working (`pipeline/build_kernel_preview.py`).
- ✅ **Stage 2 — Clipmap geometry**: complete. 4 nested donut-mesh
  rings with skirts, camera-snap, sine-wave debug shader, walk +
  topdown headless captures (`captures/axis1_clipmap_debug_2026_05_12*`).
  Two plan-divergent fixes shipped: shader uses `VERTEX.y += h` (not
  `=`) to preserve skirt depth; `inner_grid_n` rounds DOWN so rings
  overlap (no gap). Editor verification still pending user.
- ✅ **Stage 3 — Heightmap stack integration**: complete pending
  editor verification. `terrain_world_v3.gdshader` (lit PBR + per-
  fragment normals + half-texel UV correction). `ClipmapWorld` reads
  `QualityTiers.get_current()` and drives `KernelComposer` via
  `WorkerThreadPool` (async double-buffer with task-supersede on
  rapid snap changes). `HeightMapShape3D` collision on the inner
  `collision_rings` (tier knob). All deviations from plan documented
  in `build-notes/AXIS1_PATH2_STAGE3_BUILD_NOTES_2026_05_12.md`.
- ⏳ **Stage 4 — Clipmap splat + biome rendering**: pending. Wires
  Axis 6 world-splat pattern into the clipmap renderer.

**Quality-tier system.** Shipped 2026-05-12. JSON source of truth at
`config/quality_tiers.json`. Python resolver at
`pipeline/quality_tiers.py`. GDScript resolver at
`scripts/QualityTiers.gd`. Cross-impl test pins both sides
(`tests/test_quality_tiers_cross_impl.py`). Default tier is `high`
(targeting 3060-class GPUs). Spec at
`superpowers/specs/2026-05-12-quality-tiers-design.md`, plan at
`superpowers/plans/2026-05-12-quality-tiers.md`. 54/54 W4 tests pass
across the whole suite.

## Worlds

| World | State | Notes |
|---|---|---|
| `anchor/` (256m × 256m) | **regression-locked** | Don't touch. `strategy/ANCHOR.md`. |
| `scale_demo/` (1024m × 1024m, 16 tiles) | **shipped** | Axis 1+2+4+6 work landed here. Tile-paging, 5 biomes, soft transitions, world-spanning splat. `build-notes/AXIS6_BUILD_NOTES_2026_05_12.md`. |
| `scale_v2/` (4 km × 4 km, clipmap rings) | **in progress** (Axis 1 Path 2 Stage 4 next) | `biome_catalog.json` (2 biomes via `NoiseStackKernel`), `material_world_v3.tres`. Stages 1+2+3 shipped. Real procedural terrain renders, async hitch-free, collision on inner rings. Pending: splat + biome PBR (Stage 4), world-bound + scale_v2.tscn (Stage 5). |

## Renderer architecture

**Two terrain renderers coexist; neither replaces the other yet:**

- **ScaleWorld + tile-paging** (`scripts/ScaleWorld.gd` +
  `terrain_world_v2.gdshader`): the shipped Axis 6 stack. World made
  of N×N tiles, world-spanning splat sampled at world XZ, per-biome
  PBR Texture2DArrays. **The 1024m scale_demo runs on this.**
- **ClipmapWorld + nested rings** (`scripts/ClipmapWorld.gd` +
  `terrain_world_v3.gdshader`): the new Axis 1 Path 2 stack. 4 ring
  meshes that translate with the camera. Kernel-driven heightmaps via
  `KernelComposer`, async via `WorkerThreadPool` with double-buffer.
  Tier-aware (reads `QualityTiers.get_current()`). Inner rings get
  `HeightMapShape3D` collision. **The 4 km scale_v2 runs on this.**

Long-term, the clipmap renderer is the "real-game" path. ScaleWorld
stays for legacy / small-world / 2D-bake cases.

## Code inventory (high-level)

| Module | Path | Purpose |
|---|---|---|
| Procedural kernels | `pipeline/kernels/`, `scripts/kernels/` | Pure-function height generators. `NoiseStackKernel` (fBm) is v1. `KernelComposer` blends per-biome kernels via softmax. Python + GDScript impls pinned bit-equivalent by cross-impl test. |
| Quality tiers | `pipeline/quality_tiers.py`, `scripts/QualityTiers.gd`, `config/quality_tiers.json` | Resolves `low`/`medium`/`high`/`ultra` → typed dict. Consumed by every perf-sensitive subsystem. Default `high`. |
| Clipmap renderer | `scripts/ClipmapWorld.gd`, `scripts/ClipmapRing.gd`, `shaders/clipmap_debug.gdshader`, `shaders/terrain_world_v3.gdshader` | Stages 1+2+3 shipped. Donut meshes + skirts, camera-snap, async displacement via WorkerThreadPool, lit PBR shader with per-fragment normals, HeightMapShape3D collision on inner rings. |
| ScaleWorld renderer | `scripts/ScaleWorld.gd`, `shaders/terrain_world_v2.gdshader` | Shipped Axis 6 stack. Tile-paging + world-splat. |
| Anchor renderer | `scripts/AnchorTerrain.gd`, `shaders/terrain_anchor_v2.gdshader` | Regression baseline. Locked. |
| Camera rig | `scripts/AnchorCameraRig.gd` | Walk / iso / topdown. Reused by every world. |
| Biome catalog | `pipeline/biome_catalog.py`, `the world 4/worlds/*/biome_catalog.json` | Per-world biome list + slot mapping. |
| Texture stack | `pipeline/aaa_texture.py`, `pipeline/generate_biome_kits.py`, `pipeline/build_biome_arrays.py` | ComfyUI-driven texture generation + Texture2DArray packing. |
| Splat builders | `pipeline/build_world_splat.py`, `pipeline/build_tile_splats.py` | World-spanning splat (current) + per-tile splat (legacy, kept for 2D bakes). |

Full one-line-per-tool index: `reference/TOOLS.md`.

## Test inventory

**54 pytest tests passing as of 2026-05-12.** Breakdown:

- Kernel system: 17 tests (`test_kernel_base`, `test_noise_stack_kernel`, `test_kernel_composer`, `test_kernel_cross_impl`).
- Quality tiers: 9 tests (`test_quality_tiers`, `test_quality_tiers_cross_impl`).
- Biome catalog: 5 tests (`test_biome_catalog`).
- Texture-array builders: 4 tests (`test_build_biome_arrays`).
- Splat builders: 19 tests (`test_build_tile_splats`, `test_build_world_splat`).

Run all: `cd "world 4" && python -m pytest tests/ -v`.

## Known pitfalls (≥ 1 per session)

See `reference/PITFALLS.md` for the canonical list with diagnosis +
fix per entry. Current count: **10 documented pitfall classes**:

- #1–#4: source-DEM + PBR-at-scale issues (anchor / scale_demo era)
- #5, #5b: Texture2DArray gotchas (Axis 6)
- #6: per-tile splat boundary discontinuity (Axis 6, drove world-splat pivot)
- #7: heightmap displacement clobbers skirt offset (Stage 2 — `+=` not `=`)
- #8: half-texel UV offset for heightmap sampling (Stage 3)
- #9: `inner_grid_n` rounded UP → gap (Stage 2 — round DOWN)
- #10: `WorkerThreadPool` outlives shared deps → shutdown crashes (Stage 3.4)

## What's documented now (and not)

✅ Workflows for: world building, fresh-session takeover, debugging
visual artifacts, headless captures, the orchestrator pipeline.
✅ Reference for: all CLI tools, all GDScript classes, all shaders,
all pitfalls.
✅ Strategy for: axes, biomes, anchor, wishlist.
❌ Not yet documented: clipmap renderer architecture as a feature
doc (only in build-notes once it ships), per-skill workflow recipes
in `workflows/`, contributor guide for adding a new kernel /
biome / pitfall entry.

The "❌ Not yet documented" items are tracked in `workflows/`
additions queued for after Axis 1 Path 2 ships.

## Update protocol

- Update this doc when **any of the following happens**: a stage
  closes, a test count changes meaningfully, a new top-level module
  lands (new resolver, new renderer, new pipeline), a known-pitfall
  gets fixed.
- Don't duplicate ROADMAP's ranking — link to it. STATE answers "what
  do we have", ROADMAP answers "what's next".
- Date in header is when the snapshot was taken. Old dates = stale
  doc; refresh before relying on it.
