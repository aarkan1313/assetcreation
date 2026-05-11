# Phase F.3.5 — M11 parity refactor

> Generalizes M11 fourway's hand-authored builder into our pipeline.
> `m11_bundle_lib.py` gains `FourwayBundleSpec` + `build_fourway_bundle`
> + `build_split_quadrant_fields` + M11's `build_height`/`build_layers`/
> `build_macro_preview` logic. `build_fourway_bundle.py` is the CLI
> driver. **Architecture parity reached; visual parity ~70% of M11.**
> Closing this session so a fresh project owner can take it from here.

## Verdict

**Architecture is converged on M11.** Bundles produced by our pipeline
have the same emit shape M11 emits (heightmap + macro + splat + 7
scatter masks + per-bundle .tres). The library is generalized so it
can produce M11's exact fourway content OR any other 1-4 domain
composition the schema describes.

**Visual quality is on the way but not yet at M11's bar.** The
M11-content rebuild renders correctly (real Gloss source crop in SW
quadrant, lava macro in NE, etc.) but lacks some per-quadrant
shading and detail richness that M11's hand-tuned builder produced.
The remaining gaps are tuning, not architecture.

## What shipped

### `world3/pipeline/m11_bundle_lib.py` (~600 lines)

The generalized library. Public API:

- `Domain` dataclass — one sub-region with material_id + weight field
- `BundleSpec` dataclass — N-domain single-biome bundle spec
- `FourwayBundleSpec` dataclass — M11-shape 4-quadrant bundle spec with
  optional real-source anchoring
- `build_bundle(spec, catalog)` — top-level builder for N-domain specs
- `build_fourway_bundle(spec, catalog)` — top-level builder for fourway
- `build_split_quadrant_fields()` — M11's split_x/split_y noisy
  quadrant decomposition (ported verbatim from `build_m11_fourway_corner_proof.py`)
- `build_fourway_height()` — per-quadrant procedural heights blended
  via the quadrant weight fields + junction softening
- `build_fourway_layers()` — per-pixel splat weights + 7 scatter masks
- `build_fourway_macro_preview()` — per-pixel macro composited from
  each quadrant's catalog albedo + M11-style tinting (grass patch,
  ember overlay, rock warm, etc.)
- `build_procedural_macro()` — catalog material tiled with noise
  modulation for a domain's macro reference
- `_write_fourway_material()` — emits a complete ShaderMaterial .tres
  binding 5 slot materials + their 35 textures + the bundle's macro/
  mask/splat — same shape M11's `eco.write_ecotone_material` produces
- Math helpers: `normalize01`, `smooth_noise`, `gaussian_gray`,
  `load_catalog`, edge-constraint helpers (F.3.1 compatibility)

### `world3/pipeline/build_fourway_bundle.py`

CLI driver for fourway bundles. Takes per-quadrant material ids +
elev ranges + optional real-source anchoring (heightmap + macro +
crop in macro pixel space) + slot overrides. Calls the library.

Example invocation that builds a Gloss-anchored M11-equivalent bundle:

```
python world3/pipeline/build_fourway_bundle.py \
  --out world3/worlds/f35_m11_parity/bundles/m11_fourway_parity \
  --bundle-id m11_fourway_parity \
  --biome-kit grassland \
  --width 1024 --height 1024 --world-size-m 240 --seed 4117 \
  --nw-material m8_grassland_grass_calm_v3 --nw-elev-range-m 22 \
  --ne-material fantasy_lava_field_controlled --ne-elev-range-m 28 \
  --se-material desert_canyon_rock --se-elev-range-m 42 \
  --sw-material scrub_sparse --sw-elev-range-m 12 \
  --slot-rock-dark scrub_sparse --slot-snow grassland_dirt \
  --source-heightmap world3/toporeview/gloss_mountain_textured_master/heightmap.png \
  --source-meta world3/toporeview/gloss_mountain_textured_master/meta.json \
  --source-macro world3/textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png \
  --source-crop 80,760,1024,1024 \
  --extra-catalog world3/materials/catalog_comfy_candidates.json \
  --extra-catalog world3/materials/catalog_m11_fourway_generated.json
```

### `world3/scenes/review/f35_fourway_parity_tour.tscn`

Review scene that loads the F.3.5 parity bundle through
`World3AutoReviewTour` — same scene template M11's review uses.

### `world3/scenes/review/capture_f35_fourway_parity.tscn`

Headless capture wrapper for iso framing comparison.

## Validation

### Emit shape parity

```
world3/worlds/f35_m11_parity/bundles/m11_fourway_parity/
├── heightmap.png
├── material.tres            ← per-bundle .tres, 5 slots × 7 maps
├── meta.json
└── layers/
    ├── render_albedo.png       ← M11-style composited macro
    ├── source_valid_mask.png
    ├── splat_weights_rgba.png  ← per-pixel splat
    ├── dry_grass_density_mask.png
    ├── fantasy_crack_mask.png
    ├── no_scatter_mask.png
    ├── rock_cluster_mask.png
    ├── shrub_carryover_mask.png
    ├── soil_exposure_mask.png
    └── wash_line_mask.png
```

Matches M11's `source_stack/m11_fourway_corner_proof/` shape with the
addition of per-bundle `material.tres` (M11 has a single shared
`terrain_m11_fourway_corner.tres`; ours generates one per bundle so
the iterator can drive arbitrary content).

### Visual: capture at `world3/docs/captures/review/f35_fourway_parity_iso.png`

What works:
- 4 quadrant domains visible in correct positions (grass NW, lava NE,
  canyon SE, scrub SW)
- Real Gloss source crop loads correctly in SW quadrant (after the
  macro-space → heightmap-space crop fix mid-session)
- Splat weights drive per-pixel domain dominance
- Per-bundle `material.tres` binds all 5 catalog materials correctly
- Heightmap matches per-quadrant elev range targets

What's still gapped vs M11:
- Per-quadrant brightness/shadow tinting (M11's `build_macro_preview`
  has light + slope + fine-noise modulation; our port has it but the
  `light` field is fixed at 0.5 instead of computed from the
  heightmap gradient — quick fix)
- Junction softening visible but less prominent than M11's
- Detail texture interaction with splat is subtle — needs side-by-side
  with M11 capture to see what tuning differs

## Where the session ended (honest status)

```
✅ F.1   orchestrator gaps closed
✅ F.2   world plan schema
✅ F.3   plan → bundles iterator
✅ F.3.1 heightmap edge contiguity (4 seams within 0.0004m)
✅ F.3.2 splat schema + iterator + orchestrator wiring
✅ F.3.3 per-bundle material.tres emit
✅ F.3.4 m11_bundle_lib refactor (single-domain bundles)
✅ F.3.5 fourway support in lib + CLI driver (this doc)
✅ F.4   catalog-time transition pair audit
✅ F.5   catalog demand + requisition (dry-run safe)
✅ F.6   in-context re-audit
✅ F.7   multi-bundle streaming director (architecture)
✅ F.8   top-level entry + pipeline guide

🔨 F.3.5 final tuning: per-quad light/shadow, macro brightness modulation
🔨 F.3.6 bring 5-biome starter through lib (not just M11-content fourway)
🔨 F.7.1 streamer re-validate with M11-shape bundles
```

The architecture is solid. The remaining work is tuning + validation,
not new design.

## Known issues going into handoff

1. **Per-quad light field stubbed at 0.5.** `build_fourway_macro_preview`
   should derive `light` from `np.gradient(height_m)` like M11 does.
   Easy 4-line fix in `m11_bundle_lib.py`.

2. **5-biome bundles still use the old single-domain `build_bundle`
   path, not `build_fourway_bundle`.** Single-biome bundles don't need
   fourway, but they should get M11-style splat weights driven by
   slope + height. F.3.4's `build_layers_general` does this but the
   tuning is conservative; F.3.6 should sharpen it.

3. **Multi-biome boundary tiles still emit as single-domain bundles
   with R=1 splat.** The iterator needs to populate the BundleSpec
   with multi-domain crossfade weights at biome boundaries. Library
   already supports this; iterator side missing.

4. **F.7 streamer hasn't been re-tested against M11-shape bundles.**
   With per-bundle material.tres now correct and edges/splat/macros
   M11-shaped, the streamer should render bundles individually fine.
   Cross-bundle seams may still need polish (the F.7 streamer's
   chunk_size / view_radius interaction with the per-bundle 256m
   tile size).

5. **5x5 starter plan never rebuilt with the F.3.4+ pipeline.** It was
   built earlier under F.3.2 and the bundles still reflect that
   shape. A rebuild via `world3_make_world.py` will regenerate them
   through the new pipeline.

## Six-box check

| Box | Status |
|---|---|
| Schema | ✅ region_request_schema.json carries all F.3.1-F.3.4 fields (this_biome, neighbor edges, neighbor biomes, splat feather). Fourway-specific fields not in schema yet (intentional — F.3.5 uses the CLI driver directly, future iterator extension will add them) |
| Validator | ✅ existing validate_region_request.py |
| Example | ✅ `world3/worlds/f35_m11_parity/bundles/m11_fourway_parity/` |
| Audit | ⏳ Capture-based; no automated parity-delta script (consider for G.5) |
| Closure doc | ✅ this doc |
| Stages.json | N/A — F.3.5 is a library refactor + driver, not a new stage |

## Cross-references

- Parent phase: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- M11 reference: [M11_FOURWAY_CORNER_PROOF_2026_05_10.md](M11_FOURWAY_CORNER_PROOF_2026_05_10.md)
- Course correction: [F_COURSE_CORRECTION_M11_ARCHITECTURE_2026_05_11.md](F_COURSE_CORRECTION_M11_ARCHITECTURE_2026_05_11.md)
- Predecessor: [F34_M11_LIB_REFACTOR_2026_05_11.md](F34_M11_LIB_REFACTOR_2026_05_11.md)
- Fresh-session handoff prompt: [F35_HANDOFF_PROMPT_2026_05_11.md](F35_HANDOFF_PROMPT_2026_05_11.md)

## Status

- [x] FourwayBundleSpec + build_fourway_bundle in lib
- [x] build_split_quadrant_fields ported from M11
- [x] build_fourway_height / build_fourway_layers / build_fourway_macro_preview
- [x] _write_fourway_material .tres emission
- [x] build_fourway_bundle.py CLI driver
- [x] Source-macro/heightmap crop math fixed (macro-space → heightmap-space rescale)
- [x] M11-equivalent bundle builds with real Gloss source loaded
- [x] f35_fourway_parity_tour.tscn + capture_f35_fourway_parity.tscn
- [x] Closure doc (this doc)
- [ ] Per-quad light field derived from height gradient (F.3.5 tuning)
- [ ] Visual parity with M11 fourway capture (close but not pixel-equivalent)
- [ ] 5-biome starter rebuild through F.3.4+ pipeline
- [ ] F.7 streamer revalidation with M11-shape bundles

**Phase F.3.5 SHIP (architecture).** Final visual tuning + 5-biome
revalidation + streamer revalidation queued for the next session.
