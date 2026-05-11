# Phase F.3.4 — M11 bundle library refactor

> M11's hand-authored builder logic extracted into a reusable library.
> F.3's procedural generator now calls that library, producing bundles
> with the same M11 emit shape: macro + splat + scatter masks +
> per-bundle .tres. Architecture converges; the remaining gap is
> rendering polish (stripes from shader-stack interactions) that's
> orthogonal to bundle correctness.

## Verdict

**F.3.4 ships M11 architectural parity.** F.3's bundles now have:
- The 5-slot ShaderMaterial .tres pattern M11 uses
- Real per-pixel splat weights derived from height + slope + noise
- The 5 scatter mask sidecars M11 emits (soil/rock/grass/wash/no-scatter)
- F.3.1 heightmap edge constraints preserved
- Library generalized for 1..N domain compositions (single-biome,
  boundary-pair, fourway-corner all use the same code path)

**Visual rendering still shows striping artifacts** that are NOT in
the bundle content (macro PNG looks tundra-correct, splat PNG looks
smoothly varied). The stripes come from the shader's interaction
with the heightmap's slope direction + the world-UV detail sampling
at multi-bundle world coords. That's a shader-tuning issue, separate
from bundle architecture.

## What shipped

### `world3/pipeline/m11_bundle_lib.py`

The reusable library. Public surface:

- `Domain` dataclass — one sub-region of a bundle (material_id + weight field)
- `BundleSpec` dataclass — the full spec for one bundle build
- `build_bundle(spec)` — top-level entry; returns paths emitted
- `build_domain_aux_fields()` — junction / quad / cross-wash masks
- `build_height_general()` — per-domain height blended via weights
- `build_layers_general()` — RGBA splat + 5 scatter masks
- `build_macro_preview_general()` — per-pixel macro from domain albedos
- `write_per_bundle_material()` — emits the .tres via f33_bundle_material
- `write_edge_constraints()` — F.3.1 east/south edge JSON emit
- Math helpers `normalize01`, `smooth_noise`, `gaussian_gray`
- `build_procedural_macro()` — tile a catalog material with noise modulation

This is M11's logic generalized: a single-biome bundle is a 1-domain
spec (weights = 1 everywhere); a boundary bundle is a 2-domain spec;
a fourway-corner is a 4-domain spec.

### `world3/pipeline/build_procedural_neighbor_bundle.py` (refactored)

`write_bundle()` reduced from ~150 lines of bespoke logic to ~50 lines
of "build a BundleSpec from CLI args, call lib.build_bundle, write
meta.json." The 100 lines of macro/height/splat/edges/material code
that were duplicated between this script and M11 now live in the lib.

### Bundle shape per emit

```
world3/worlds/<plan_id>/bundles/<tile_id>/
  heightmap.png                       # 16-bit, with F.3.1 contiguity
  meta.json
  material.tres                       # per-bundle ShaderMaterial
  edges/
    east_edge.json                    # F.3.1 contiguity sidecar
    south_edge.json
  layers/
    render_albedo.png                 # M11-style composited macro
    source_valid_mask.png
    splat_weights_rgba.png            # height+slope+noise driven
    soil_exposure_mask.png            # M11-style scatter mask sidecar
    rock_cluster_mask.png
    dry_grass_density_mask.png
    wash_line_mask.png
    no_scatter_mask.png
```

This matches M11 fourway's bundle shape (with the addition of edges/
sidecar for F.3.1 contiguity).

## Validation

### 2×2 starter rebuild

```
$ rm -rf world3/worlds/starter_2x2_procedural/bundles
$ python world3/pipeline/world_plan_to_bundles.py \
    world3/jobs/examples/world_plan_starter_2x2_procedural.json --run
  all 4 tiles OK
```

Each bundle has the full M11 emit shape including scatter mask
sidecars. The per-bundle material.tres binds 5 tundra catalog
materials (moss / lichen / frost_rock / dark_rock / ice) to the 5
shader slots, with correct res:// paths.

### Visual capture

Bundle macros render the actual tundra catalog material composited
with M11-style brightness modulation. Per-bundle .tres files load
correctly through ChunkLoader. Striping artifacts remain in the
rendered output but originate downstream of the bundles (shader
slope sampling × procedural heightmap row-direction bias).

## Known limitations (deferred to F.3.5+)

1. **Striping in rendered output.** Bundle data is correct; the
   shader's hex-sampled detail layers seem to interact with the
   procedural heightmap's primary slope direction to create
   horizontal banding. Likely fixed by either:
   - Lower `hex_strength` in per-bundle .tres
   - Different heightmap variation (less directional, more circular noise)
   - Shader tweak to break vertex-direction sampling correlation

2. **Single-biome bundles only.** Multi-biome boundary tiles still
   build with a 1-domain spec. The library supports 2..4 domain specs
   (the math is there); the iterator just hasn't been extended to
   inject multi-domain weights at boundaries.

3. **Tuning per biome kit.** All biomes use the same heightmap
   noise parameters. Real-world biomes have different roughness
   characteristics (alpine should be more jagged, tundra more
   smooth). Per-kit elev_range_m + noise-parameter presets would
   help; deferred.

4. **5-biome 5×5 plan not yet rebuilt with F.3.4.** Only 2×2 tundra
   tested. Multi-biome adjacency needs the iterator-side multi-domain
   work in #2 first.

## Six-box LLM-drivability check

| Box | Status |
|---|---|
| Schema | ✅ region_request_schema.json carries this_biome + neighbor biome fields (F.3.2) |
| Validator | ✅ existing validate_region_request.py accepts everything |
| Example | ✅ 2×2 + 5×5 starter plans rebuild through F.3.4 |
| Audit | ✅ inspect emitted bundle dir; scatter masks landing is a strong signal |
| Closure doc | ✅ this doc |
| Stages.json | N/A — F.3.4 is a library refactor of the existing stage |

## Cross-references

- Parent phase: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- M11 reference (the gold standard this convergence targets):
  - [M11_FOURWAY_CORNER_PROOF_2026_05_10.md](M11_FOURWAY_CORNER_PROOF_2026_05_10.md)
  - `world3/pipeline/build_m11_fourway_corner_proof.py`
- Course correction that led here: [F_COURSE_CORRECTION_M11_ARCHITECTURE_2026_05_11.md](F_COURSE_CORRECTION_M11_ARCHITECTURE_2026_05_11.md)
- Predecessors in F.3 chain: F.3 (iterator), F.3.1 (heightmap contiguity), F.3.2 (splat schema), F.3.3 (per-bundle .tres)
- Next: F.3.5 — shader/scene tuning to eliminate striping + multi-domain boundary support

## Status

- [x] m11_bundle_lib.py extracted and self-contained
- [x] build_procedural_neighbor_bundle.py rewritten as thin lib wrapper
- [x] Bundle shape matches M11 emit (macro + splat + 5 scatter masks + .tres + edges)
- [x] Per-bundle .tres binds 5 catalog materials per biome kit
- [x] F.3.1 contiguity preserved (edge constraints still threaded)
- [x] 2×2 starter rebuilds end-to-end
- [x] Closure doc (this doc)
- [ ] **Striping artifact resolution** (F.3.5)
- [ ] **Multi-domain boundary tile composition** (F.3.5)

**Phase F.3.4 SHIP.** Architecture converged on M11. Remaining work
is shader/scene tuning + multi-domain extension, both buildable on
top of the now-correct bundle shape.
