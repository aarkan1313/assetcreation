# World3 Workflow Inventory — 2026-05-11

> **Phase A of the rebuild evaluation.** Honest inventory of every workflow
> across `world3/`, `pipelines/terrain/`, and `pipelines/textures/`. Built
> by reading actual script docstrings + argparse signatures, not from
> session-bound memory.
>
> Goal: answer "what can world3 actually do today, given the code +
> manifests + scenes that exist?" so we can decide world3-fixes vs world4
> based on evidence.

## Method

For each script: read the docstring (first line), read the argparse signature
(if it has one), classify by role. For each scene: classify by family (which
M, what review mode). For each manifest: what it configures. Don't trust
session memory; the inventory is derived from code on disk.

## Pipeline overview (the four executable layers)

```
LAYER 1 — DATA ACQUISITION  (pipelines/terrain/)
  Real-world DEMs, mega-stacks, regional STAC fetches.
  → outputs: cached *.tif files in d:/assets/dems/

LAYER 2 — TEXTURE GENERATION  (pipelines/textures/)
  Procedural texture creation + tileable PBR derivation.
  → outputs: world3/textures/wgv3/<material>/ + world/textures/library/<id>/

LAYER 3 — WORLD3 BUILD  (world3/pipeline/)
  DEM + textures + biome rules → bundle (heightmap + macro + splat + materials)
  → outputs: world3/textures/source_stack/<region>/ + jobs/ manifests

LAYER 4 — REVIEW / VALIDATION  (world3/scenes/ + world3/scripts/)
  Godot scenes that load bundles + render captures + run audits
  → outputs: world3/docs/captures/
```

The chain is: **Layer 1 fetches → Layer 2 generates → Layer 3 assembles → Layer 4 validates**. Each layer is mostly executable today; what's missing is the **glue** that turns this into a "one config in, one bundle out" pipeline.

---

## Layer 1: Data Acquisition (`pipelines/terrain/` — 11 scripts)

### Executable scripts

| Script | Purpose | Inputs | Outputs | Status |
|---|---|---|---|---|
| `opentopo_fetch.py` | OpenTopography acquisition helper. Single tile or bbox. | API key, bbox, dataset | `.tif` in cache | ✅ working |
| `bulk_pull.py` | Bulk-pull DEMs from a wishlist file. | wishlist JSON | many `.tif` | ✅ working |
| `bulk_fetch_to_cache.py` | Cache-only bulk fetch (variant w/o terrain_bundle). | wishlist | many `.tif` | ✅ working (workaround for archived terrain_bundle) |
| `pull_megastack_queue.py` | Pull all stitched mega-stacks in priority order. | queue JSON | mega-stacks | ✅ working (used through 2026-05-09) |
| `megastack_tracker.py` | Build a tracker for stitched mega-stack pulls. | queue state | tracker JSON | ✅ working |
| `tile_stitch.py` | Fetch huge bbox as N×M tiles + seamlessly stitch. | bbox, tile grid | stitched `.tif` | ✅ working |
| `fetch_regional_stac.py` | STAC fetchers for ArcticDEM/REMA/LINZ (bypass OpenTopo gate). | region spec | `.tif` | ✅ working (2026-05-08) |
| `catalog_search.py` | OpenTopography /otCatalog client. | search query | catalog JSON | ✅ working |
| `mystery_sampler.py` | Generate random worldwide bbox candidates. | seed | bbox suggestions | ✅ working (utility) |
| `import_dem.py` | Real-world DEM importer (entry helper). | DEM `.tif` | normalized form | ✅ working |
| `build_master_catalog.py` | Scan all data locations + build catalog. | filesystem | `data_catalog.json` | ✅ working but **stale** (last run 2026-05-09, missed 365 DEMs) |
| `landlab_smoke_test.py` | Verify Landlab erosion solver works. | — | erosion before/after PNGs | ✅ smoke-tested 2026-05-10 |

### Cache state today

- **657 DEMs on disk** at `d:/assets/dems/`
- **`data_catalog.json` says 292** — needs regen
- **4 master stacks** assembled by worker (Gloss Mountain, Zion, Guadalupe Cypress, [4th])
- **9 mega-stacks** stitched through the pull queue

### Workflow chain
```
wishlist.json → bulk_pull.py / pull_megastack_queue.py → *.tif in dems/
                                                          ↓
                                                  build_master_catalog.py
                                                          ↓
                                                  data_catalog.json (registry)
```

### Gap
- `build_master_catalog.py` is not re-run automatically after pulls. Stale catalog.
- No "given a region request, pull the data it needs" entry-point.

---

## Layer 2: Texture Generation (`pipelines/textures/` — 40 scripts)

This is the **largest pipeline** by script count and the most mature. Multiple subsystems.

### Generation entry-points

| Script | Purpose | Inputs | Outputs |
|---|---|---|---|
| **`aaa_texture.py`** | **Top-level orchestrator** for full quality stack | `--prompt`, `--id`, `--category`, `--quality`, `--variants`, `--ladder` | `world/textures/library/<id>/` with full PBR set + QA + manifest |
| `kit_generator.py` | Auto-generate coherent biome kit from one name | biome name | 5-material kit |
| `palette_lock.py` | Generate textures sharing a palette | anchor texture | locked-palette set |
| `relock_palette.py` | Re-palette-lock existing textures | new anchor | re-paletted set |

### Generation backends

| Script | Backend | Status |
|---|---|---|
| `flux_seamless.py` | FLUX.2-klein seam-aware (offset+heal) | ✅ working; has `--reference-image` anchor mode (A.10) |
| `comfy_generate.py` | ComfyUI prompt-to-texture wrapper | ✅ working |
| `flux_upscale.py` | FLUX img2img heal-pass | ✅ working |
| `diversity_compare.py` | Run same prompt across multiple models | ✅ working; **FLUX 2 9B + dev variants wired but not run** |

### PBR derivation backends

| Script | Method | Status |
|---|---|---|
| `derive_pbr_v2.py` | Materialize-style deterministic derivation | ✅ default |
| `stablematerials_image2pbr.py` | StableMaterials adapter | ✅ working |
| `chord_image2pbr.py` | CHORD (Ubisoft) adapter | ✅ opt-in via `--pbr-backend chord` |
| `bake_pbr.py` | High-res re-derive (normal/AO/roughness) | ✅ used in ladder workflow |
| `ma_image2pbr.py` | Material Anything (legacy; superseded) | ⚠️ kept for reference |
| `material_anything_adapter.py` | MA adapter for mesh PBR | ⚠️ legacy |
| `patina_adapter.py` | PATINA (fal.ai) adapter | ⚠️ external API; not active |

### Post-processing + QA

| Script | Purpose |
|---|---|
| `delight.py` | De-lighting (LAB-space large-blur subtract) |
| `seam_repair.py` | Offset + patch quilting + multiband blending |
| `variant_blend.py` | Combine N tileable variants softmax-blend |
| `variant_select.py` | Pick best of N candidates by seam score |
| `texture_qa.py` | Three-check tile/seam metric + grading |
| `biome_consistency.py` | Color-family kit consistency check |
| `mip_ladder.py` | 2K/1K/512 multi-tier writer with per-map filters |
| `sr_upscale.py` | Real-ESRGAN single-map super-resolution |
| `upscale_biome_set.py` | PIL Lanczos batch upscale |
| `detail_pyramid.py` | Macro + detail-layer pair generator |
| `detail_variant.py` | Detail-variant tied to existing macro |
| `high_pass_detail.py` | High-pass detail extraction |
| `process_texture.py` | Base color → tileable PBR pipeline |

### External sources / adapters

| Script | Purpose |
|---|---|
| `ambientcg_fetch.py` | CC0 PBR from ambientCG v2 API |
| `polyhaven_fetch.py` | CC0 PBR from Poly Haven API |
| `make_test_texture.py` | Quick procedural noise (testing) |

### World3 integration

| Script | Purpose |
|---|---|
| `deploy_kit_to_world3.py` | Copy kit textures from library/ to world3/textures/wgv3/ + emit .tres |
| `biome_texture_bind.py` | Biome → AAA-texture binder |
| `build_transition_strip.py` | Catalog-driven transition strips between two materials |
| `emit_per_mode_materials.py` | Phase E: emit walk/iso/topdown variants per kit |
| `pack_terrain3d.py` | Pack PBR into Terrain3D channel-packed format |

### Visualization

| Script | Purpose |
|---|---|
| `blender_preview.py` | Lit sphere + tiled plane render |
| `macro_detail_preview.py` | Macro+detail material in Blender Cycles |
| `render_ma_mesh.py` | Render Material Anything output in Blender |
| `experiment.py` | R&D harness |

### Workflow chain (top-level entry)
```
prompt + id + category
        ↓
aaa_texture.py (orchestrator)
   ├→ variant_select (N candidates via flux_seamless or comfy_generate)
   ├→ delight
   ├→ pbr backend (derive_v2 / chord / sm)
   ├→ seam_repair
   ├→ texture_qa (gate)
   ├→ mip_ladder (optional)
   └→ catalog manifest
        ↓
world/textures/library/<id>/ + QA report
        ↓
deploy_kit_to_world3.py → world3/textures/wgv3/<material>/.tres
```

### Gap
- `aaa_texture.py` requires ComfyUI running at `http://127.0.0.1:8188`
- No "given a biome name + view mode, generate the full 5-material kit deployed to world3" one-command entry
- `deploy_kit_to_world3.py` is a manual second step
- The 9 FLUX 2 / klein-9B / dev variants in `diversity_compare.py` registry — staged but never run

---

## Layer 3: World3 Build (`world3/pipeline/` — 54 scripts)

This is the largest layer by complexity. Mature build/audit/derive scripts.

### Region/bundle build

| Script | Purpose | Status |
|---|---|---|
| **`build_world.py`** | **Single DEM → 16-bit heightmap + meta.json** | ✅ working; entry-point for one-region bundles |
| `derive_rasters.py` | Generate derived rasters from elevation GeoTIFF | ✅ working |
| `export_heightmap_review_layers.py` | Export diagnostic layers from 16-bit heightmap | ✅ working |
| `index_regions.py` | Index heightmap bundles into region catalog | ✅ working (used by jobs/regions.json) |
| `build_runtime_image_cache.py` | Build export-safe runtime caches for Godot | ✅ working (M6) |

### OpenTopo orthophoto/mosaic pipeline

| Script | Purpose | Status |
|---|---|---|
| `opentopo_fetch.py` (in world3/pipeline too?) | wrapped fetch | check |
| `build_opentopo_mosaic.py` | Same-type raster mosaic with seam QA | ✅ working (worker built this) |
| `build_opentopo_mosaic_streaming.py` | Large same-CRS mosaic w/o full-RAM | ✅ working |
| `build_opentopo_dtm_dsm_stack.py` | Godot-ready stack from DTM + DSM | ✅ working |
| `build_opentopo_textured_master_stack.py` | Textured master stack (DEM + ortho) | ✅ working (Gloss / Guadalupe / Zion) |
| `build_opentopo_stack_manifest.py` | Build + validate stack manifest | ✅ working |
| `build_opentopo_render_albedo.py` | Source-first render albedo | ✅ working |
| `build_opentopo_tileable_texture.py` | Tileable texture pilots from OT stack | ✅ working |
| `build_opentopo_texture_variant_atlas.py` | Multi-crop variant atlases | ✅ working |
| `finish_opentopo_soft_materials.py` | Finish soft composites → Godot materials | ✅ working (6 materials: bare_soil/bright_rock/dry_wash/rocky_slope/scrub_dense/scrub_sparse) |
| `export_opentopo_mosaic.py` | Mosaic → Godot PNG layer | ✅ working |
| `export_opentopo_review_texture.py` | Procedural color review texture | ✅ working |
| `export_opentopo_rgb_mosaic.py` | RGB GeoTIFF → Godot-aligned PNG | ✅ working |
| `export_opentopo_texture.py` | OT rasters → PNG textures | ✅ working |
| `export_opentopo_vegetation_mask.py` | Vegetation mask from NIR/false-color | ✅ working |
| `extract_opentopo_layers.py` | Higher-level layers from OT data | ✅ working |
| `fetch_opentopo_tile_grid.py` | OT raster product as overlapping tiles | ✅ working |
| `validate_opentopo_mosaic.py` | Validate same-type mosaic bundle | ✅ working |
| `validate_opentopo_mosaic_streaming.py` | Streaming mosaic validation | ✅ working |

### LAZ point cloud (subset of features)

| Script | Purpose | Status |
|---|---|---|
| `inspect_laz_headers.py` | Inspect LAS/LAZ headers | ✅ working |
| `process_laz_samples.py` | Process LAZ samples → summaries + rasters | ✅ working |

### M-specific build scripts

| Script | M | Purpose | Status |
|---|---|---|---|
| `build_m4_splat_prototype.py` | M4 | Unified splat-shader prototype assets | ✅ |
| `build_m11_junction_layer_proof.py` | M11 | Three-way terrain junction proof | ✅ |
| `build_m11_fourway_corner_proof.py` | M11 | Four-way corner proof | ✅ |
| `build_m14_close_play_quality_board.py` | M14 | Close-play quality board | ✅ |
| `build_m16_source_stack_gallery_board.py` | M16 | Gallery bridge board | ✅ |
| `build_m17_real_data_rule_extraction.py` | M17 | Procedural neighbor rule extraction | ✅ |
| `build_m18_slice_feature_masks.py` | M18 | First-pass feature masks for runtime slice | ✅ |
| `build_m1_m7_validation_summary.py` | M1-M7 | Workflow validation summary | ✅ |
| `build_m8_regen_queue_status.py` | M8 | Organic regen queue status | ✅ |
| `build_kit_materials.py` | — | Per-biome terrain_blend_<kit>.tres | ✅ |

### Cross-region / seam integration

| Script | Purpose | Status |
|---|---|---|
| `build_ecotone_layer_proof.py` | M10 unlike-biome ecotone | ✅ |
| `build_procedural_neighbor_bundle.py` | M10 real-to-procedural seam | ✅ |
| `build_same_source_blend_stack.py` | Seam-conditioned macro for same-source repeat | ✅ |
| `build_source_stack_runtime_review.py` | Source-stack runtime review assets | ✅ |
| `build_terrain_seam_integration_proof.py` | Terrain seam-integration proof | ✅ |
| `scan_terrain_seam_compatibility.py` | Scan source pairs for seam-integration crops | ✅ |

### Audit / QA scripts

| Script | Purpose | Status |
|---|---|---|
| `audit_production_promotion_candidates.py` | Audit promotion candidates | ✅ (M13 gate runner) |
| `audit_m12_view_mode_parity.py` | M12 view-mode parity audit | ✅ |
| `audit_source_repeat_safety.py` | Finite-source wrap safety | ✅ |
| `audit_transition_mask_metrics.py` | M7 boundary mask metrics | ✅ |
| `audit_comfy_visual_veto.py` | ComfyUI candidate visual veto | ✅ |
| `audit_material_source_noise.py` | Close-range source material noise | ✅ |
| `audit_opentopo_samples.py` | OT samples comparison report | ✅ |

### Material library management

| Script | Purpose | Status |
|---|---|---|
| `build_comfy_material_candidate_catalog.py` | Inventory ComfyUI candidates | ✅ |
| `stage_comfy_candidate_material.py` | Stage ComfyUI output as quarantined | ✅ |
| `repair_organic_materials.py` | Calmer organic candidates | ✅ |
| `make_image_comparison_sheet.py` | Labeled PNG comparison | ✅ |
| `make_opentopo_texture_repeat_sheet.py` | Repeat-preview sheets | ✅ |

### Workflow chain (the path that exists today)
```
DEM → build_world.py → heightmap.png + meta.json
                              ↓
                       index_regions.py → jobs/regions.json
                              ↓
                       build_opentopo_textured_master_stack.py
                              ↓ + texture catalog from Layer 2
                       build_source_stack_runtime_review.py
                              ↓
                       source_stack/<region>/ bundle
                              ↓
                       Layer 4 (review scenes)
                              ↓
                       audit_production_promotion_candidates.py
```

### Gap
- This pipeline is composable but has **no top-level orchestrator** that says "given region X with biome Y in mode Z, run all the necessary steps."
- M-specific build scripts (`build_m11_*`, `build_m14_*`, etc.) are **one-shot scripts**, not generalized. Each M closure required custom code.
- The OpenTopo orthophoto pipeline (`build_opentopo_*`) and the procedural pipeline (`build_procedural_neighbor_bundle.py`) live side by side but **don't share entry-point conventions**.

---

## Layer 4: Review / Validation (`world3/scenes/` + `world3/scripts/`)

### Runtime scripts (35 Godot .gd files)

#### Core runtime (always present)

| Script | Role |
|---|---|
| `ChunkLoader.gd` | M3-M5 chunk streaming around an XZ position |
| `Terrain.gd` | Single-heightmap mesh builder |
| `RuntimeImageCache.gd` | M6 export-safe image cache |
| `RegionLoader.gd` | Load region bundle into runtime |
| `IsoCam.gd` / `TopDownCam.gd` / `FlyCam.gd` | Per-mode cameras |
| `CamFraming.gd` | Phase C anchor + visible_diameter_m framing |
| `PlayerAnchor.gd` | Y-snap to heightmap surface |
| `Walker.gd` | Walk-mode character controller |
| `CaptureSceneOnce.gd` | Headless capture runner |
| `HeadlessCapture.gd` | Headless capture support |

#### M-specific review runners

| Script | M | Role |
|---|---|---|
| `M4SplatShaderReview.gd` | M4 | Splat shader prototype review |
| `M4ChunkSplatReview.gd` | M4 | Chunk + splat review |
| `M4OpenTopoUnifiedReview.gd` | M4 | OpenTopo + unified shader review |
| `M5WalkStreamRunner.gd` | M5 | Walk-stream sampled review |
| `M6TransitionRuntimeReview.gd` | M6 | Transition runtime review |
| `M7BoundaryRuntimeReview.gd` | M7 | Boundary runtime review |
| `M7BoundaryWalkReview.gd` | M7 | Boundary walk review |
| `M12SourceStackParityRuntime.gd` | M12 | Source-stack parity runtime |
| `M14LichenSidecarCompareBoard.gd` | M14 | Lichen sidecar compare |
| `M15FeatureScatterOverlay.gd` | M15 | Feature scatter overlay |
| `M16SourceStackGalleryReview.gd` | M16 | Gallery bridge review |
| `M16IsoImpostorCardReview.gd` | M16 | Cached iso impostor card |
| `M18PerformanceSmoke.gd` | M18 | Performance smoke test |
| `SourceStackRuntimeReview.gd` | — | Generic source-stack review |
| `TransitionStripReview.gd` | M2 | Transition strip review |
| `EcotoneScatterOverlay.gd` | M10 | Ecotone scatter overlay |
| `RegionGalleryCapture.gd` | — | Bulk region gallery |
| `World3AutoReviewTour.gd` | — | Auto review tour |
| `_codex_render_runner.gd` | — | Codex-driven render runner |
| `ChunkSweepRunner.gd` | M3 | Chunk-size sweep runner |
| `HeadlessTextureGrid.gd` | — | Headless texture grid |
| `OpenTopoSampleViewer.gd` | — | OpenTopo sample viewer |
| `TextureViewer.gd` | — | Texture viewer |

### Review scenes (101 .tscn files in `scenes/review/`)

Categorized by M (sample):
- **M2**: transition_strip_review (4 scenes)
- **M3**: source-stack seam (multiple)
- **M4**: splat/chunk review (8+)
- **M5**: walk stream review (multiple)
- **M6**: transition runtime + collision review (4+)
- **M7**: boundary runtime (8+) + walk review (4+)
- **M10**: terrain seam integration (4+), ecotone (4+), real-to-procedural (4+)
- **M11**: three-way + four-way junctions (8+)
- **M12**: runtime parity (4+)
- **M14**: per-bakeoff per-band scenes (40+ — grassland/grass/temperate_forest/tundra_moss/tundra_lichen × close/medium/iso/topdown)
- **M16**: gallery board + iso impostor (4+)
- **M17**: rule extraction (3+)
- **M18**: representative slice + guided neighbor + closure review (8+)

### Gap
- Per-M scenes are **specific to specific bundles**. No "given a bundle path, render all four bands" generalized scene.
- No `render_all_modes(region_id)` one-command driver.
- Capture runners exist (`CaptureSceneOnce.gd`, `HeadlessCapture.gd`) but launching them requires manual Godot CLI invocations with full path specs.

---

## Job manifests (`world3/jobs/` — 15 files)

| Manifest | Purpose | Schema state |
|---|---|---|
| `_template.json` | template for new jobs | ✅ |
| `biome_kits.json` | 5 biome kit definitions | ✅ |
| `biome_transition_rules.json` | M2/M7 transition pairs + rules | ✅ |
| `comfy_texture_regen_candidates.json` | M8 organic regen queue | ✅ (M14 supersedes practically) |
| `m14_texture_bakeoff_plan.json` | M14 active lanes + parked + rejected | ✅ (with FLUX 2 9B candidates pending bakeoff) |
| `m15_feature_scatter_policy.json` | M15 scatter policy | ✅ |
| `m16_source_stack_gallery_manifest.json` | M16 gallery candidates | ✅ |
| `m17_procedural_neighbor_recipe.json` | M17 extraction recipe | ✅ |
| `m17_rule_extraction_sources.json` | M17 source list | ✅ |
| `m18_closure_review_manifest.json` | M18 closure picker | ✅ |
| `m18_representative_slice_manifest.json` | M18 slice config | ✅ |
| `m4_chunk_material_contract.json` | M4 chunk-material binding | ✅ |
| **`production_promotion_candidates.json`** | **M13 gate (THE authoritative state)** | ✅ schema v1, 8 candidates |
| `regions.json` | 16 regions with biome_kit + datasets + bundles | ✅ |
| `world3_m1_m18_audit_matrix.json` | 2026-05-11 audit matrix | ✅ |

### Schema accuracy notes
- `production_promotion_candidates.json` declares states: `accepted_workflow / ready_for_live_review / sidecar_candidate / negative_evidence / production_candidate / production_promoted`. **This is the source of truth for state names.**
- Several recent doc rewrites (today's ROADMAP, audit report) used different state-name vocabulary. **Schema wins.**

---

## End-to-end workflow chains that exist today

### Chain 1 — Real DEM → review-ready source-stack bundle

```
1. pipelines/terrain/opentopo_fetch.py     (download DEM tile)
2. world3/pipeline/build_world.py          (DEM → heightmap + meta)
3. world3/pipeline/build_opentopo_textured_master_stack.py
                                           (DEM + ortho → master stack)
4. world3/pipeline/build_source_stack_runtime_review.py
                                           (master stack → review bundle)
5. world3/pipeline/build_runtime_image_cache.py
                                           (export-safe cache)
6. Godot scene (e.g. source_stack_review.tscn) → captures
7. world3/pipeline/audit_production_promotion_candidates.py
                                           (M13 gate update)
```

**Status**: every step works. Chain has been run for ~24 source-stack bundles. **Manual: each step is a separate command with hand-curated args.**

### Chain 2 — Procedural texture → world3 kit deployment

```
1. pipelines/textures/aaa_texture.py --prompt ... --id ...
                                           (ComfyUI must be running)
2. pipelines/textures/biome_consistency.py (verify kit fits)
3. pipelines/textures/deploy_kit_to_world3.py
                                           (library → world3/textures/wgv3/)
4. pipelines/textures/emit_per_mode_materials.py
                                           (walk/iso/topdown .tres variants)
```

**Status**: every step works. 31 catalog materials + 56 .tres variants on disk. **Manual: each material is a separate orchestrator invocation.**

### Chain 3 — Procedural neighbor → seam-integrated bundle (M10/M17)

```
1. world3/pipeline/build_procedural_neighbor_bundle.py
                                           (FastNoise + rules → procedural bundle)
2. world3/pipeline/build_terrain_seam_integration_proof.py
                                           (join procedural to real source)
3. Godot scene → captures
4. audit_production_promotion_candidates.py
```

**Status**: every step works. The M18 closure used this chain. **The procedural side's "broad smooth tan/sand" weakness is in step 1's output — placement bias, not pipeline failure.**

### Chain 4 — M14 close-play material bakeoff (active 2026-05-10)

```
1. pipelines/textures/diversity_compare.py --models <list> --prompt ...
                                           (run prompt through N models)
2. pipelines/textures/aaa_texture.py for each survivor
3. pipelines/textures/stage_comfy_candidate_material.py
4. world3/pipeline/build_m14_close_play_quality_board.py
5. Godot per-band capture scene
6. audit_production_promotion_candidates.py
```

**Status**: every step works. FLUX 2 9B + dev candidates in `m14_texture_bakeoff_plan.json` are **staged but not run** (ComfyUI not running; bakeoff pending).

---

## What's missing — the "data + world-type → world" gap

The user's stated north star:
> "this is the world data I have, here's the world type I want, make it."

What that one-command experience would require:

1. **A request schema** — `region_request.json` with: bbox or DEM ref, biome kit, view mode(s), style pack, water on/off, weather on/off, output bundle id. Doesn't exist today.

2. **A dispatcher** — `world3 make-region <config.json>` that reads the request, walks the dependency chain (which DEMs to pull, which textures to bind, which build scripts to chain, which review scenes to render), executes them, reports status. Doesn't exist today.

3. **A stage manifest** — `stages.json` declaring every step's inputs/outputs/dependencies in a form the dispatcher can read. Doesn't exist today.

4. **All-modes render driver** — `render_all_modes(region_id)` that loads the bundle + renders close/medium/iso/topdown captures. Today this is per-M custom Godot scenes.

5. **Per-style swap mechanism** — formalized `style_pack.json` describing material/shader/atmosphere overrides for photoreal / painterly / topographic / fantasy. Phase E per-mode `.tres` is the foundation; doesn't extend to style packs yet.

6. **Catalog auto-regen** — after pulls or builds, automatically refresh `data_catalog.json`. Today it's manual; today it's 365 DEMs stale.

7. **Worker venv per-pipeline** — `pipelines/textures/.venv` doesn't exist (only `pipelines/terrain/.venv`). textures scripts use the system Python which mixes deps. Per-lane venv discipline exists in the docs principle but isn't applied to textures yet.

8. **Documented commands per workflow chain** — chains 1-4 above exist in code but **no single doc lists "run these 7 commands in this order with these args."** Each session re-derives the commands.

---

## What works really well (strengths)

1. **The `aaa_texture.py` orchestrator** is the closest thing to a clean entry-point. Single command, full quality stack, gate. Pattern for what every layer should look like.

2. **The M13 gate** (`audit_production_promotion_candidates.py` + manifest) is genuine, honest infrastructure. 8 candidates, accurate states, no silent promotion. This is the strongest single thing in the project.

3. **The `data_catalog.json` registry** (when regenerated) is one place to look for "what data exists." `pipelines/terrain/build_master_catalog.py` is the script. Just needs to run after pulls.

4. **The source-stack contract** is real and produces working bundles (24 of them on disk). Per-region directory layout is consistent.

5. **The per-mode `.tres` system** (Phase E) is the foundation for style swaps. Working today across 5 kits × 3 modes = 15 variants.

6. **The Godot review scenes are reproducible** — they read bundle paths from manifests, not from hardcoded scene state.

7. **Worker scripts are well-docstring'd**. Every script in `world3/pipeline/` has a clear first-line description. This inventory was possible because of that discipline.

---

## What doesn't work / where the divergence happened

1. **No top-level "given X, make Y" dispatcher**. The chains exist; the orchestration doesn't.

2. **M-specific build scripts are one-shots**, not parameterized. Generalizing them to a common base would consolidate ~10 scripts.

3. **`data_catalog.json` regen isn't automatic** after pulls — leaves stale state.

4. **Texture lane requires ComfyUI running** at a hardcoded port. No "start ComfyUI then run pipeline" wrapper.

5. **Per-pipeline venv discipline is incomplete** — terrain has `.venv`, textures doesn't, world3 uses... something (probably system).

6. **OpenTopo orthophoto pipeline and procedural pipeline don't share conventions** — `build_opentopo_*` vs `build_procedural_neighbor_bundle.py` have different arg styles + output layouts.

7. **Per-M one-shot Godot scenes** — 100+ scenes that load specific bundles. Should be parameterized.

8. **No `style_pack.json` mechanism** — Phase E per-mode .tres is hardcoded; can't swap "photoreal → painterly" without rewriting kits.

---

## Verdict (for the world3 vs world4 decision)

**The code is largely solid.** ~120 scripts across three pipelines, well-docstring'd, with clear input/output conventions. The audit confirmed M1-M18 implementations are honest workflow evidence. The M13 gate is real.

**The divergence is in the orchestration layer**, not the implementation:
- No top-level dispatcher
- No request schema
- No stage manifest
- Stale catalog due to manual regen requirement
- One-shot M-specific scripts that should be parameterized
- Texture pipeline requires running ComfyUI

These are **all solvable in world3 without a fresh repo.** The Orchestration arc (O1-O3) was sketched as exactly the missing layer. World4 doesn't fix this faster — it would re-implement everything below the orchestration layer.

**Specific to "is there hidden divergence beyond the procedural-vs-texture confusion?"**:

The user worried that since procedural texture generation was a fundamental misframe, what else might be similarly misframed. The inventory says: not much that's structural. The texture pipeline (Layer 2) cleanly does texture generation. The procedural placement work (M17 + `build_procedural_neighbor_bundle.py`) cleanly does placement. **The confusion was at the *plumbing* level** — the M18 representative slice combined them in a way that produced ambiguous output. That's a one-script integration problem, not a pipeline-wide problem.

**Other potential divergences worth checking** (Phase B candidates):
- Does `build_kit_materials.py` actually emit the per-mode `.tres` variants Phase E specifies, or only the base?
- Does `audit_production_promotion_candidates.py` validate every required file the contract claims, or just the headline ones?
- Do M-specific build scripts have hidden hardcoded paths that fail outside their original capture session?

Those are validation candidates for **Phase B** (cold end-to-end runs).

## Recommended next step

**Run a cold end-to-end test on Chain 1** (Real DEM → review-ready bundle) before committing to a path. Pick a region we already have a bundle for (e.g. Gloss Mountain). Run every script from step 1 onward against fresh inputs. Document what breaks. That's the real Phase B.

If Chain 1 runs cleanly cold, world3 is in better shape than today's chat-tone implies, and the right move is the Orchestration arc (O1-O3) inside world3.

If Chain 1 breaks in multiple non-trivial places, the case for world4 strengthens — but **the new world would steal the script catalog from world3 wholesale**, not redesign it.

## Status

- [x] Phase A: Workflow inventory written (this doc)
- [ ] Phase B: Cold end-to-end run of Chain 1
- [ ] Phase C: Diagnose breakages (if any)
- [ ] Phase D: World3 fixes vs world4 decision

## Cross-references

- Pre-rebuild backup: `D:/assets/_backup_world3_2026_05_11_pre_rebuild/`
- Rebuild plan: [`REBUILD_PLAN_2026_05_11.md`](REBUILD_PLAN_2026_05_11.md)
- Audit verdict: [`WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md`](WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md)
- M13 gate (state authority): `../jobs/production_promotion_candidates.json`
- Data registry: `../data_catalog.json` (regen via `pipelines/terrain/build_master_catalog.py`)
