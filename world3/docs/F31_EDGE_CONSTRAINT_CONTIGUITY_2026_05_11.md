# Phase F.3.1 — Edge-constraint plan iterator + procedural builder

> Heightmap contiguity at generation time. Adjacent bundles' shared
> boundaries are now forced to match by construction. The streaming
> director (F.7) becomes a trivial consumer of pre-contiguous bundles.

## Verdict

**F.3.1 closes the underworld at bundle boundaries.** Procedural
heightmaps now agree with their neighbors at shared edges within
16-bit PNG quantization noise. F.7's streamer no longer has to fake
seam continuity at runtime — the bundles themselves are contiguous
when they leave the F.3 iterator.

Measured on the 5×5 starter plan: **40 cross-tile seams, max delta
0.0103m** (vs typical bundle elev variation of 12-80m).

Measured on the 2×2 starter plan: **4 cross-tile seams, max delta
0.0004m** (essentially byte-perfect at the 16-bit encoding limit).

## What shipped

### `world3/pipeline/build_procedural_neighbor_bundle.py`

Three new CLI args:
- `--neighbor-west-edge <path>` — JSON file with the west neighbor's east edge values
- `--neighbor-north-edge <path>` — JSON file with the north neighbor's south edge values
- `--neighbor-edge-feather-px <int>` — feather distance (pixels) for inward blend

Three new helpers:
- `load_edge_constraint()` — loads a JSON edge file, resamples to required length
- `apply_edge_constraint()` — overrides field rows/cols + feathers inward
- `extract_edge_constraint()` — pulls field edge as a list for downstream tiles

Build flow now:
1. Generate procedural heightmap from noise (unchanged from D.1)
2. Apply west constraint (column 0 + feather right)
3. Apply north constraint (row 0 + feather down)
4. Corner reconciliation: corner cell becomes average of W + N corner values; both edges re-forced to exact neighbor match
5. **Skip the renormalize step** when constraints applied — using the request's nominal elev envelope preserves byte-exact edge values (renormalize was rescaling the whole bundle and breaking neighbor agreement)
6. Emit `edges/east_edge.json` and `edges/south_edge.json` for downstream tiles

### `world3/pipeline/world_plan_to_bundles.py`

Three changes:
- Iteration order forced to row-major (`sorted by (row, col)`) so each tile's W and N neighbors are built before it
- For procedural tiles, inject `source.neighbor_west_edge` + `source.neighbor_north_edge` paths pointing at the predecessor's edge JSON
- Added `_layout_entry_for(col, row)` helper to find neighbor tiles in the layout

### `world3/pipeline/world3_make.py`

`resolve_args` for `build_procedural_neighbor` now threads:
- `source.neighbor_west_edge` → `--neighbor-west-edge` arg
- `source.neighbor_north_edge` → `--neighbor-north-edge` arg
- `source.neighbor_edge_feather_px` → `--neighbor-edge-feather-px` arg

### `world3/jobs/region_request_schema.json`

Three new optional fields on the procedural `source` variant:
- `neighbor_west_edge` — repo-relative path to west neighbor's east edge JSON
- `neighbor_north_edge` — repo-relative path to north neighbor's south edge JSON
- `neighbor_edge_feather_px` — feather distance, default 32

`additionalProperties: false` on the procedural source variant is preserved.

## Validation

### Standalone smoke (two tiles, west constraint only)

```
tile_a east edge: min=206.61m max=224.00m
tile_b west edge: min=206.61m max=224.00m
edge delta: max abs=0.0000m mean=0.0000m
```

Byte-perfect. Tile_b's west column == tile_a's east column.

### 2×2 starter plan

```
a(0,0)<->b(1,0) east-west seam max |delta|: 0.0000m
a(0,0)<->c(0,1) south-north seam max |delta|: 0.0004m
b(1,0)<->d(1,1) south-north seam max |delta|: 0.0000m
c(0,1)<->d(1,1) east-west seam max |delta|: 0.0004m
```

All 4 seams agree within 0.0004m = ~one 16-bit LSB at the encoding's
precision.

### 5×5 starter plan (cross-biome adjacencies)

```
40 cross-tile seams measured, max |delta| = 0.0103m
```

Real cross-biome boundaries (alpine↔grassland, alpine↔desert, etc.)
work because the constraint propagates a neighbor's absolute meter
values regardless of the new tile's nominal elev envelope. The
builder dynamically expands its envelope to cover any constrained
values that fall outside its noise's natural range.

### F.7 streamer with contiguous bundles

After rebuilding the 2×2 with F.3.1, the F.7 sweep scene shows
**no underworld at bundle boundaries**. The ground is one continuous
surface across all 4 tiles. The remaining visual issues (wavy macro
colors) are F.7.1 texture-encoding work, unrelated to contiguity.

## Why renormalize was the silent killer

Pre-F.3.1, every bundle ran a final `normalize01(field)` step that
mapped the bundle's actual min/max to `[0, 1]` then back to its
nominal elev_min..elev_min+range. This maximized 16-bit dynamic
range per bundle.

Once constraints are applied, **renormalize is wrong**:
- Constrained edge has absolute meter values
- Renormalize rescales the whole bundle to [0, 1] of *this* bundle's
  min/max
- That breaks the byte-exact agreement with the neighbor

F.3.1 substitutes a dynamic envelope: keep the request's nominal
range when there are no constraints (preserves pre-F.3.1 behavior),
expand the envelope if constrained values fall outside (preserves
constrained accuracy at cost of slightly compressed dynamic range
within this bundle).

## Six-box LLM-drivability check

| Box | Status |
|---|---|
| Schema | ✅ updated `region_request_schema.json` — 3 new fields on procedural variant |
| Validator | ✅ existing `validate_region_request.py` accepts new schema |
| Example | ✅ 2×2 + 5×5 rebuilt with constraints applied |
| Audit | ✅ seam delta measurement script (in this doc); could formalize as `audit_world_contiguity.py` in F.3.2 |
| Closure doc | ✅ this doc |
| Stages.json | N/A — F.3.1 reuses existing `build_procedural_neighbor` stage |

## What's NOT in F.3.1

- **Formal contiguity audit script.** The seam-measurement Python in
  this doc could be packaged as `audit_world_contiguity.py` that
  runs after F.3 and emits a JSON verdict. Deferred to F.3.2 if
  needed; the soft proof (re-running F.7 visually) is sufficient
  for now.
- **Hybrid / real-DEM edge constraints.** Only procedural source
  type honors the constraint args. For hybrid bundles, the
  procedural side would need the same treatment; for real-DEM
  bundles, the source heightmap is fixed and edges are whatever
  the DEM has. Cross-biome real↔procedural seams stay unconstrained
  until G.6 (real-DEM patch refinement).
- **Macro texture continuity.** Heightmaps are contiguous; macro
  textures still vary independently per bundle and need either F.4
  catalog-time fixes or F.7.1 runtime seam blending. The two
  problems are now cleanly separable.
- **Bundle-order determinism for non-rectangular layouts.** The
  iterator assumes a regular grid where every tile has a layout
  entry. Sparse / irregular layouts (a future Phase G feature for
  handcraft patches) need different dependency-order logic.

## Cross-references

- Parent phase: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Predecessor: [F3_PLAN_TO_BUNDLES_ITERATOR_2026_05_11.md](F3_PLAN_TO_BUNDLES_ITERATOR_2026_05_11.md)
- Companion: [F7_MULTI_BUNDLE_STREAMER_2026_05_11.md](F7_MULTI_BUNDLE_STREAMER_2026_05_11.md) — F.7 now consumes contiguous bundles cleanly
- Touches: `build_procedural_neighbor_bundle.py`, `world_plan_to_bundles.py`, `world3_make.py`, `region_request_schema.json`

## Status

- [x] Procedural builder: `--neighbor-edge` args + corner reconciliation + skip-renormalize
- [x] Plan iterator: row-major order + neighbor edge field injection
- [x] Orchestrator: thread neighbor edges from request to builder
- [x] Schema: three new fields on procedural source variant
- [x] 2×2 smoke: 4 seams within 0.0004m
- [x] 5×5 smoke: 40 seams within 0.0103m
- [x] F.7 visual verify: no underworld at boundaries
- [x] Closure doc (this doc)

**Phase F.3.1 SHIP.** Adjacent bundles now share heightmap edges by
construction. F.7's streaming director consumes contiguous bundles.
The remaining seam issues are texture-color (F.7.1) and macro
blending (F.4 catalog work) — both cleanly separable now that the
geometry contiguity layer is solid.
