# Decimate vs meshopt LOD A/B — obelisk_egyptian_a04

**Free-win backlog item #4 (per brief #03, 2026-05-07).** Brief #03 wired `meshoptimizer` (`gltfpack v1.1` at `tools/meshoptimizer/`) alongside the existing Blender DECIMATE COLLAPSE path in `pipelines/props/lod_chain.py --method {decimate,meshopt}`. Outputs landed in `world/props/library/obelisk_egyptian_a04/` with the `_meshopt` suffix preserving the decimate baseline for A/B inspection.

This doc records the **quantitative side** of the A/B (file size + tri counts). The **visual side** — does meshopt preserve silhouette and surface detail as well as decimate at matched tri counts? — needs eyes-on inspection in Blender or Godot. **Visual judgment is queued for the next session you're at the keyboard.**

## Quantitative comparison

Source path: [world/props/library/obelisk_egyptian_a04/](../../world/props/library/obelisk_egyptian_a04/)

Method: parsed each GLB header + JSON chunk; tri count is the sum of `indices.count // 3` across all triangle-mode primitives.

| LOD | decimate KB | meshopt KB | size delta | decimate tris | meshopt tris | tri delta |
|---:|---:|---:|---|---:|---:|---|
| 0 | 11450.2 | 11450.2 | +0.00 (+0.0%) | 100000 | 100000 | +0 (+0.0%) |
| 1 | 10100.8 | 10003.1 | −97.64 (−1.0%) | 64998 | 64998 | +0 (+0.0%) |
| 2 |  9337.7 |  9150.8 | −186.92 (−2.0%) | 35000 | 34998 | −2 (−0.0%) |
| 3 |  8613.4 |  8549.4 | −64.03 (−0.7%) | 15000 | 15000 | +0 (+0.0%) |

## Reading

- **LOD0 identical.** Both methods pass the full 100k-tri base mesh through unchanged — there's no simplification target at LOD0.
- **LOD1-3 size advantage to meshopt: 0.7-2.0%.** Modest but consistent. The win is **vertex quantization + index compression**, not topology — the tri counts are within ±2 across every LOD, so visual silhouette should be at least equivalent.
- **Tri-count fidelity is essentially identical.** Both methods hit the same simplification ratios (LOD1 ~65%, LOD2 ~35%, LOD3 ~15%). The wired pipeline meets target counts on both methods.
- **Compression is the lever, not topology.** This matches the `gltfpack` design — it's a runtime/storage optimizer, not a remesher. If we want a topology change (better silhouette preservation, less surface-detail loss), that's a different tool (e.g. quadric error metrics with surface-aware constraints — Knodt 2026 watch list).

## What the visual A/B is checking for

1. **Silhouette preservation** at LOD2 + LOD3 (the simplified ones). Decimate-collapse is well-known to produce occasional silhouette pinches; meshopt's simplifier is a different algorithm and may behave differently.
2. **Surface artifact bands.** Carved geometric features (the obelisk has hieroglyph-like surface detail per the Phase 11 hero pass) are where the two methods diverge in practice.
3. **UV preservation.** Both methods can break UV continuity at simplification seams; visual inspection at LOD2+ catches this.

## How to do the visual pass (for the next time you sit with this)

Quick path in Godot:

1. Drop `world/props/library/obelisk_egyptian_a04/` into a Godot scene
2. Place two GroundPlane'd instances side-by-side: one referencing `model_lod{0..3}.glb`, one referencing `model_lod{0..3}_meshopt.glb`
3. Step through LOD distances and screenshot the comparison at each LOD

Quick path in Blender:

1. `bpy_blender --python -c "import bpy; bpy.ops.import_scene.gltf(filepath=...)"` to load both into a single scene
2. Offset one set on the X axis by ~5 m
3. Visually compare, paying attention to LOD2 (35k tris) and LOD3 (15k tris) where simplification artifacts dominate

## Decision gate

If meshopt is **visually equivalent or better** at LOD2+: promote `--method meshopt` to default in `lod_chain.py` for new bakes. Existing decimate outputs stay (preserved by `--suffix` convention).

If meshopt is **visually worse** at LOD2+: keep decimate as default; meshopt remains opt-in for cases where storage size matters more than detail (e.g. deep-LOD2.5D distance imposters).

If they're **approximately equivalent**: keep decimate as default for stability (we have more tooling around DECIMATE COLLAPSE; meshopt's silent storage-size win at LOD1-3 is a "use it on shipping builds" lever, not a default-flip).

Either way, the side-by-side files live forever under the `_meshopt` suffix — **the wiring is non-destructive,** so this decision can be revisited any time without re-running the bake.

## Next time you visually compare

Mark the result inline below. Decision is yours.

- [ ] LOD2 silhouette: decimate / meshopt / equivalent
- [ ] LOD3 silhouette: decimate / meshopt / equivalent
- [ ] Surface detail (hieroglyph carving): decimate / meshopt / equivalent
- [ ] Default-method recommendation: keep decimate / promote meshopt / keep both opt-in

---

_Generated 2026-05-07 evening as part of the orchestrator handoff free-wins backlog (item #4)._
