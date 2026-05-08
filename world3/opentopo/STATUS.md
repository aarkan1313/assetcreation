# OpenTopography Status

Last updated: 2026-05-07

## API State

The `globaldem` / `usgsdem` API key path returned `401` after the first small
run, then later recovered. Diagnostics showed:

- no key: `401` with "API Key required"
- bad key: `401` with invalid-key message
- stored key: `200` GeoTIFF response for `globaldem`
- stored key: `200` GeoTIFF response for `usgsdem`

The public OpenTopography COG/VRT storage path works and was used for the broad
sample set.

Root cause/status:

- The request format was correct: `API_Key` query parameter.
- The repo convention is `OPENTOPOGRAPHY_API_KEY`; `OPENTOPO_API_KEY` is only a
  local alias. `world3/pipeline/opentopo_fetch.py` now supports both.
- The transient `401` was not reproducible after waiting; small diagnostic calls
  and a real `USGS10m` + `USGS1m` OT+ pull now work.
- Attempts to write User-scope env vars from the sandbox were blocked in the
  normal context. The ignored `opentopo/config/opentopo.env` and
  `opentopo/config/opentopo.ps1` files are the reliable in-repo setup path.

## Breadth Samples

Priority-1 biome breadth is covered with public COG rasters:

- 14 biome representative sites
- `COP30` for all 14
- `NASADEM` for 12 valid sites; Alaska boreal and arctic tundra returned
  all-nodata because NASADEM does not cover those high latitudes
- `SRTMGL1` for 12 valid sites; Alaska boreal and arctic tundra returned
  all-nodata because SRTM does not cover those high latitudes

Raw COG folder:

```text
D:/assets/world3/opentopo/raw/cog/
```

Converted heightmap folder:

```text
D:/assets/world3/opentopo/processed/heightmaps/
```

Current converted heightmap bundle count: 72.

## Data-Type Representatives

### Global DSM / Surface Raster

- `COP30`: full priority-1 biome breadth
- `AW3D30`: `des_mojave_usa`

### Global Terrain DEM Raster

- `NASADEM`: full valid priority-1 coverage where available
- `SRTMGL1`: full valid priority-1 coverage where available

### Bathymetry / Topobathy

- `man_sundarbans`: `SRTM15Plus`, `GEBCOIceTopo`, 80 km sample
- `fgs_pantanal_brazil`: `SRTM15Plus`, `GEBCOIceTopo`, 80 km sample

### Paired DTM / DSM

- `bor_yukon_canada`: `CA_MRDEM_DTM`, `CA_MRDEM_DSM`
- `tcf_bc_coast_canada`: `CA_MRDEM_DTM`, `CA_MRDEM_DSM`

BC Coast no-color Godot stack generated from `tcf_bc_coast_canada`:

```text
D:/assets/world3/opentopo/processed/heightmaps/tcf_bc_coast_dtm_dsm_stack/
D:/assets/world3/toporeview/bc_coast_dtm_dsm/
D:/assets/world3/toporeview/bc_coast_dtm_dsm_review.tscn
D:/assets/world3/docs/captures/opentopo/godot_bc_coast_dtm_dsm.png
D:/assets/world3/docs/captures/opentopo/opentopo_bc_coast_dtm_dsm_layer_sheet.png
```

Stack stats: 26.61 x 26.64 km, source 30 m cells, 4096 review export, DTM
297.4-2640.8 m, DSM-DTM surface height max 45.3 m and p95 20.5 m. This stack
has no real color; `terrain_texture.png` is a procedural layer driven by DTM,
DSM-DTM, slope, roughness, hillshade, and wetness.

### GEDI Raster Metrics

- `tmf_amazon_brazil`: `GEDI_L3_ELEV`, `GEDI_L3_RH100`, 80 km sample
- `tgs_serengeti_tanzania`: `GEDI_L3_ELEV`, `GEDI_L3_RH100`, 80 km sample

### Point Cloud / LAZ

Two small OpenTopo `pc-bulk` representatives were downloaded:

```text
D:/assets/world3/opentopo/raw/pointcloud/CA14_Lowe/CA14_Lowe_TileIndex.zip
D:/assets/world3/opentopo/raw/pointcloud/CA14_Lowe/ot_335000_3809000.laz
D:/assets/world3/opentopo/raw/pointcloud/WA12_Legg/WA12_Legg_TileIndex.zip
D:/assets/world3/opentopo/raw/pointcloud/WA12_Legg/ot_583000_5176000.laz
```

One richer color/vegetation representative was downloaded from OpenTopography
Dataspace:

```text
D:/assets/world3/opentopo/raw/pointcloud/Guadalupe_Cypress/2016_rgb_pc_r1.laz
D:/assets/world3/opentopo/raw/pointcloud/Guadalupe_Cypress/2016_rgb_pc_r2.laz
D:/assets/world3/opentopo/raw/pointcloud/Guadalupe_Cypress/2016_rgb_pc_r3.laz
D:/assets/world3/opentopo/raw/pointcloud/Guadalupe_Cypress/2016_nir_pc_r1.laz
D:/assets/world3/opentopo/raw/pointcloud/Guadalupe_Cypress/2016_nir_pc_r2.laz
D:/assets/world3/opentopo/raw/pointcloud/Guadalupe_Cypress/2016_nir_pc_r3.laz
D:/assets/world3/opentopo/raw/pointcloud/Guadalupe_Cypress/2016_nir_pc_r4.laz
D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/DTM_RGB_2016.tif
D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_rgb_orto_COF.tif
D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_nir_orto_COG.tif
```

Processed point-cloud outputs:

```text
D:/assets/world3/opentopo/processed/pointcloud/pointcloud_summary.json
D:/assets/world3/opentopo/processed/pointcloud/CA14_Lowe/ot_335000_3809000/
D:/assets/world3/opentopo/processed/pointcloud/WA12_Legg/ot_583000_5176000/
D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/
```

Each processed folder contains:

- `dtm_ground.tif`
- `dsm_surface.tif`
- `surface_minus_ground_raw.tif`
- `chm_vegetation.tif`
- `points_sample.csv`
- `summary.json`

Point-cloud findings:

- `CA14_Lowe` and `WA12_Legg` do not contain RGB or NIR color.
- `CA14_Lowe` has mostly ground returns. Raw surface-minus-ground max is
  5.9 m, but no vegetation classes exist, so CHM has no valid cells.
- `WA12_Legg` includes high-vegetation classes, but all vegetation cells were
  rejected by the 120 m canopy sanity gate. The raw surface-minus-ground max is
  676.7 m, which should be treated as a QA artifact, not vegetation height.
- `Guadalupe_Cypress` is the first good color/vegetation sample. All seven
  downloaded point clouds are LAS point format 3 with RGB dimensions.
- `2016_rgb_pc_r1.laz`: 61,703,019 points; 19,905,442 ground points;
  3,990,996 high-vegetation points; RGB top-down preview generated; external
  DTM canopy-like max 33.5 m.
- `2016_nir_pc_r1.laz`: 20,443,557 points; 13,058,771 ground points;
  279,133 high-vegetation points; stored as RGB dimensions despite the NIR file
  name; external DTM canopy-like max 55.5 m.
- Full Guadalupe point-cloud pull: 608,189,343 points across three RGB regions
  and four NIR-source regions. External-DTM canopy-like maxima range from
  25.1 m to 55.5 m across the processed regions.
- Orthophoto previews generated from the 6-7 cm RGB/NIR rasters:

```text
D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/orthophotos/2016_rgb_orto_COF_preview.png
D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/orthophotos/2016_nir_orto_COG_preview.png
```

Godot-ready Cypress terrain package:

```text
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/heightmap.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/meta.json
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/orthophoto_rgb.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/orthophoto_nir_false.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/pointcloud_rgb_topdown.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/pointcloud_nir_source_topdown.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/canopy_height_mosaic.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/chm_vegetation_mosaic.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/canopy_height_mask.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/canopy_height_mask_nir_source.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/chm_vegetation_mask.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/chm_vegetation_mask_nir_source.png
```

`heightmap.png` is a 1024 px terrain heightmap from the supplied DTM. The layer
PNGs were exported with `--match-meta` so they line up with the DTM bounds.
`canopy_height_mosaic.png` is the max-combined external-DTM canopy-like mask
from all seven point-cloud regions.
`scenes/opentopo_samples.tscn` now starts on this sample and can cycle available
layer overlays with `L`.

### Local Derived Rasters

Generated locally from `COP30`:

```text
D:/assets/world3/opentopo/processed/derived/tcf_pnw_cascades_usa/COP30/
D:/assets/world3/opentopo/processed/derived/tgr_great_plains_usa/COP30/
```

Each derived folder contains:

- `hillshade.tif`
- `slope_deg.tif`
- `roughness.tif`

### USGS API Verification

Verified after fixing the env alias:

```text
D:/assets/world3/opentopo/raw/usgsdem/tbm_appalachians_usa/USGS10m_m83.5110_p35.5910_m83.4890_p35.6090.tif
D:/assets/world3/opentopo/raw/usgsdem/tbm_appalachians_usa/USGS1m_m83.5110_p35.5910_m83.4890_p35.6090.tif
```

The `USGS1m` test returned a valid `1951 x 2058` GeoTIFF in `EPSG:26917`.

Second USGS high-resolution representative:

```text
D:/assets/world3/opentopo/raw/usgsdem/med_california_chaparral/USGS10m_m119.0109_p34.4910_m118.9891_p34.5090.tif
D:/assets/world3/opentopo/raw/usgsdem/med_california_chaparral/USGS1m_m119.0109_p34.4910_m118.9891_p34.5090.tif
```

The Mojave `USGS1m` attempt returned no raster for the tested 2 km box, but
`USGS10m` did succeed there.

## Same-Type Mosaic Pilot

Grand Canyon `USGS10m` mosaic pilot completed for Workflow 1.

Raw tile stack:

```text
D:/assets/world3/opentopo/raw/usgsdem/grand_canyon_usgs10m_pilot/
```

Processed mosaic stack:

```text
D:/assets/world3/opentopo/processed/mosaics/grand_canyon_usgs10m_pilot/
```

Generated files:

- `mosaic.tif`
- `coverage_count.tif`
- `seam_delta.tif`
- `tile_footprints.geojson`
- `mosaic_report.json`
- `stack_manifest.json`
- `heightmap.png`
- `meta.json`
- `qa/mosaic_preview.png`
- `qa/coverage_count_preview.png`
- `qa/seam_delta_preview.png`
- `qa/hillshade_preview.png`

Pilot configuration:

- AOI: `40 km x 40 km`
- Tiles: `2 x 2`
- Overlap: `2 km`
- Target CRS: `EPSG:32612`
- Target cell size: `10 m`
- Reducer: `mean`

Validation:

- 4 of 4 tiles fetched successfully.
- Mosaic grid: `4050 x 4059`.
- Valid pixels: `16,061,086`.
- Elevation range: `672.81 m` to `2705.65 m`.
- Overlap pixels: `1,571,430`.
- Seam delta mean: `0.126 m`.
- Seam delta P95: `0.546 m`.
- Seam delta P99: `1.425 m`.
- Seam delta max: `35.397 m`, localized rather than a continuous border.

Audit doc:

```text
D:/assets/world3/docs/OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md
```

Automated validation:

```text
D:/assets/world3/opentopo/processed/mosaics/grand_canyon_usgs10m_pilot/validation_report.json
```

Result: `pass_with_notes`.

- Shape consistency, CRS, no-data-inside-coverage, valid-pixel count, seam P99,
  and unique-area source matching all passed.
- Unique non-overlap source/mosaic P99 absolute delta: `0.0 m`.
- Overlap source/mosaic P99 absolute delta: `0.712 m`.
- Note: the GeoTIFF grid is slightly rectangular (`40500 m x 40590 m`) while
  the current Godot heightmap export is square.

## Cross-Type Fusion Pilot

Guadalupe Cypress fused stack completed for Workflow 2.

Primary review stack:

```text
D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/
```

Broader variants retained for later no-data fill experiments:

```text
D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_fused_pilot/
D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_core_fused_pilot/
D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_overlap_fused_pilot/
```

Review-stack configuration:

- Target CRS: `EPSG:32611`
- Bounds: `370200, 3218600, 371800, 3220200`
- AOI: `1600 m x 1600 m`
- Heightmap size: `1024 x 1024`
- Elevation range: `931 m` to `1201 m`

Generated review-stack layers:

- `orthophoto_rgb.png`
- `orthophoto_nir_false.png`
- `vegetation_ndvi_like.png`
- `canopy_height_mosaic.png`
- `chm_vegetation_mosaic.png`
- `pointcloud_rgb_topdown_mosaic.png`
- `pointcloud_nir_source_topdown_mosaic.png`
- `hillshade.png`
- `slope_deg.png`
- `roughness.png`

Validation:

- `stack_manifest.json` status: `pass`
- All listed layers are `1024 x 1024`.
- RGB orthophoto valid pixels: `1,048,576`.
- NIR/vegetation valid pixels: `1,000,762`.
- Canopy-height mosaic valid pixels: `987,137`.
- Point-cloud RGB mosaic valid pixels: `1,040,867`.

Audit doc:

```text
D:/assets/world3/docs/OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md
```

## Topo Review Scenes

Interactive Godot review scenes were added under:

```text
D:/assets/world3/toporeview/
```

Scenes:

```text
D:/assets/world3/toporeview/phase1_mosaic_review.tscn
D:/assets/world3/toporeview/phase2_fusion_review.tscn
D:/assets/world3/toporeview/phase2_fusion_hd_review.tscn
D:/assets/world3/toporeview/phase2_fusion_max_review.tscn
D:/assets/world3/toporeview/phase2_fusion_ultra_rgb_review.tscn
D:/assets/world3/toporeview/phase3_smokies_4call_review.tscn
```

Shared controller:

```text
D:/assets/world3/toporeview/TopoReview.gd
```

Both scenes include free-fly camera controls, camera presets, overlay cycling,
vertical exaggeration controls, and on-screen help.

Phase 1 now includes `terrain_texture.png`, a synthetic RGB review layer built
from aligned elevation, hillshade, slope, and roughness. It is useful for
terrain/seam inspection but is not real orthophoto imagery.

## OpenTopo Texture / Scene / HD Plan

Planning doc:

```text
D:/assets/world3/docs/OPENTOPO_TEXTURE_SCENE_ROADMAP.md
```

Current direction:

- Baked ground textures from orthophoto and derived terrain/vegetation masks.
- Fused real-place scenes/maps using the aligned Phase 2 stack pattern.
- High-detail zoom experiments, starting with a 4096 Phase 2 HD single-tile
  review scene and optional 8192 RGB stress test.
- Tileable real-ground texture workflow documented at
  `D:/assets/world3/docs/OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md`; source
  maps stay chunked real-place scenes, while reusable materials can be tiled,
  repaired, downscaled, or stylized with provenance.

Tileable texture pilot status:

```text
D:/assets/world3/docs/OPENTOPO_TILEABLE_TEXTURE_PILOT_AUDIT.md
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress/
D:/assets/world3/toporeview/tileable_texture_review.tscn
D:/assets/world3/toporeview/tileable_hex_column_16x16.tscn
D:/assets/world3/docs/captures/opentopo/godot_tileable_texture_review.png
```

The first pilot produced six crop classes at `32 m` and `64 m`, plus a `4096`
full-map macro atlas. The macro atlas keeps the broad real-ground view because
it looks good, but it is not forced seamless. Reusable material outputs are
stored separately as `source/`, `tileable_real/`, and `stylized_pixel/`.

Follow-up after visual review: plain square repeat is not good enough. The
builder uses source-pixel offset patch quilting for border repair, and the Godot
review scene added a `hex anti-tile` column. That broke up square repetition but
still reused one crop, so faint tile-to-tile lines remained. The current path is
the unlike-variant soft composite below. Additional visual note: several current
crops contain noisy real-world patterns that can read unnaturally depending on
scale, so production materials need source-native crops plus macro/meso/micro
separation, not a single orthophoto tile doing every job.

First unlike-tile slice completed:

```text
D:/assets/world3/pipeline/build_opentopo_texture_variant_atlas.py
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants/
D:/assets/world3/toporeview/tileable_variant_atlas_review.tscn
D:/assets/world3/docs/captures/opentopo/godot_tileable_variant_atlas_review.png
```

Result: `12` dry-wash sibling variants were generated and reviewed. RGB
normalization reduces the checkerboard, but hard per-cell switching still shows
patch boundaries. A `4096` `tileable_soft` composite now blends unlike variants
with periodic masks and wrap-safe offsets into a single seamless PBR product.
Latest dry-wash soft-composite edge MSE mean: `0.0000136595`.

Expanded current material batch:

```text
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants_bare_soil/
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants_bright_rock/
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants_dry_wash/
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants_rocky_slope/
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants_scrub_dense/
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants_scrub_sparse/
```

Each class has `12` source-real variants, a `4096` `tileable_soft` PBR output
(`albedo`, `height`, `normal`, `roughness`), and a generated `tile_2x2.png`.
Observed edge MSE means range from `0.000008059` to `0.000018498`, with no hard
tile boundary left in the soft-composite output. Review assets:

```text
D:/assets/world3/toporeview/tileable_soft_composite_gallery.tscn
D:/assets/world3/docs/captures/opentopo/godot_tileable_soft_composite_gallery.png
D:/assets/world3/docs/captures/opentopo/opentopo_soft_composite_2x2_material_sheet.png
```

Remaining texture risk: the seam problem is largely solved for this prototype,
but some real-world motifs still repeat visibly depending on scale. Production
materials should use this as a source-real meso layer, with macro color from the
full map and separate close detail/noise where needed.

Finished material pass completed:

```text
D:/assets/world3/pipeline/finish_opentopo_soft_materials.py
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_finished_materials_index.json
```

Each class now has a `finished_material/` sibling beside `tileable_soft/` with
balanced albedo, source-derived neutral detail maps, an `ao_white.png`, a
`material_hex_detail_finished.tres`, a `tile_2x2.png`, and a
`finish_manifest.json`. The finished pass keeps raw survey-derived color intact
as provenance, then creates a practical reusable Godot material candidate. Real
Godot captures:

```text
D:/assets/world3/toporeview/tileable_finished_material_review.tscn
D:/assets/world3/docs/captures/opentopo/godot_tileable_finished_material_review.png
D:/assets/world3/docs/captures/opentopo/godot_tileable_finished_material_close.png
D:/assets/world3/docs/captures/opentopo/opentopo_finished_material_2x2_sheet.png
```

Current verdict: this is the best reproducible endpoint for tileable real-ground
materials so far. Remaining judgment is art/scale selection per class, not a
known pipeline blocker.

Known Phase 2 detail facts:

```text
Current review: 1024 over 1.6 km = 1.56 m/px
RGB orthophoto source: about 0.066 m/px
NIR orthophoto source: about 0.065 m/px
DTM source: 1.0 m cell size
```

## Phase 2 HD Review Pass

Generated:

```text
D:/assets/world3/toporeview/phase2_fusion_hd/
D:/assets/world3/toporeview/phase2_fusion_hd_review.tscn
D:/assets/world3/docs/OPENTOPO_PHASE2_HD_REVIEW.md
```

Result:

```text
Heightmap: 4096 x 4096
Layers: 10 x 4096 aligned PNG layers
Texture scale: about 0.3906 m/px over 1.6 km
Scene mesh: 512 subdivisions, about 3.125 m/vertex
Manifest: pass
Real Godot capture: pass
Real close-up capture: pass
```

## Phase 2 Max Review Pass

Generated:

```text
D:/assets/world3/toporeview/phase2_fusion_max/
D:/assets/world3/toporeview/phase2_fusion_max_review.tscn
D:/assets/world3/toporeview/phase2_fusion_ultra_rgb_review.tscn
D:/assets/world3/docs/OPENTOPO_PHASE2_MAX_REVIEW.md
D:/assets/world3/docs/OPENTOPO_RENDER_REPAIR_WORKFLOW.md
```

Result:

```text
Full stack: 8192 x 8192 heightmap and 10 aligned layers
Texture scale: about 0.1953 m/px over 1.6 km
Scene mesh: 1024 subdivisions, about 1.5625 m/vertex
Compressed stack size: about 520 MB
Manifest: pass
Real Godot max capture: pass
Real Godot max close-up capture: pass
Render-safe geometry repair: pass
Source-first render_albedo: pass

Ultra RGB: 16384 x 16384 orthophoto stress layer
Ultra RGB scale: about 0.0977 m/px
Ultra RGB compressed file: about 252 MB
Ultra RGB capture: not rerun in this pass
```

## Phase 3 Large 4-Call USGS1m Mosaic

Generated:

```text
D:/assets/world3/docs/OPENTOPO_LARGE_4CALL_PLAN.md
D:/assets/world3/docs/OPENTOPO_PHASE3_SMOKIES_4CALL_AUDIT.md
D:/assets/world3/pipeline/fetch_opentopo_tile_grid.py
D:/assets/world3/pipeline/build_opentopo_mosaic_streaming.py
D:/assets/world3/pipeline/validate_opentopo_mosaic_streaming.py
D:/assets/world3/pipeline/export_heightmap_review_layers.py
```

Tooling update:

```text
fetch_opentopo_tile_grid.py now records per-tile width/height/area and supports
--max-tile-area-km2 for preflight guardrails.
```

Raw:

```text
D:/assets/world3/opentopo/raw/usgsdem/smokies_usgs1m_4call/
```

Processed:

```text
D:/assets/world3/opentopo/processed/mosaics/smokies_usgs1m_4call/
D:/assets/world3/toporeview/phase3_smokies_4call/
D:/assets/world3/toporeview/phase3_smokies_4call_review.tscn
```

Result:

```text
stack: smokies_usgs1m_4call
dataset: USGS1m
center: lon -83.50, lat 35.60
unique AOI: 29 km x 29 km
tiles: 2 x 2
overlap: 1 km
per request: 225 km2
preflight over_limit: []
target grid: 29005 x 29835 at 1 m
valid pixels: 845,312,752
elevation range: 358.2009-2025.1490 m
validation: pass_with_notes
seam p99: 0.0 m
source-window unique-area p99 delta: 0.00006103515625 m
```

Real Godot viewport captures:

```text
D:/assets/world3/docs/captures/opentopo/godot_phase1_mosaic.png
D:/assets/world3/docs/captures/opentopo/godot_phase2_fusion.png
D:/assets/world3/docs/captures/opentopo/godot_phase2_fusion_hd.png
D:/assets/world3/docs/captures/opentopo/godot_phase2_fusion_max.png
D:/assets/world3/docs/captures/opentopo/godot_phase3_smokies_4call.png
D:/assets/world3/docs/captures/opentopo/godot_real_render_phase_comparison.png
D:/assets/world3/docs/captures/opentopo/godot_phase2_close_baseline.png
D:/assets/world3/docs/captures/opentopo/godot_phase2_close_hd.png
D:/assets/world3/docs/captures/opentopo/godot_phase2_close_max.png
D:/assets/world3/docs/captures/opentopo/godot_phase2_close_resolution_comparison.png
```

Capture validation uses normal Godot with `res://toporeview/capture_phase*.tscn`
as the trailing scene argument. Older static comparison sheets remain useful
for layer QA, but are not real render captures.

Close-up Phase 2 conclusion: higher texture resolution helps, but MAX exposes
mesh/normal artifacts. The no-data curtain class should be fixed by geometry
repair and masks. Photoreal cliff/slope improvement should come from chunked
terrain and real DSM/LAZ/color projection where available, not procedural
repainting over orthophoto.

## Final Master Stack Pair: Gloss Mountain + Zion

Generated:

```text
D:/assets/world3/docs/OPENTOPO_MASTER_STACKS_AUDIT.md
D:/assets/world3/pipeline/build_opentopo_textured_master_stack.py
```

Updated:

```text
D:/assets/world3/pipeline/build_opentopo_mosaic.py
D:/assets/world3/pipeline/export_heightmap_review_layers.py
```

Primary textured stack:

```text
name: Gloss Mountain Textured Master Stack
source: OTDS.072022.32615.1
raw: D:/assets/world3/opentopo/raw/dataspace/Gloss_Mountain_2021/
processed: D:/assets/world3/opentopo/processed/master_stacks/gloss_mountain_textured_master/
scene: D:/assets/world3/toporeview/gloss_mountain_textured_master_review.tscn
capture: D:/assets/world3/docs/captures/opentopo/godot_gloss_mountain_textured_master.png
world size: 619.4 x 1075.4 m
elevation range: 393.84-477.62 m
valid DEM after crop: 84.44 percent
orthophoto coverage after crop: 84.49 percent
```

Primary no-texture stack:

```text
name: Zion USGS10m No-Texture Master Stack
dataset: USGS10m
raw: D:/assets/world3/opentopo/raw/usgsdem/zion_usgs10m_master_4call/
processed: D:/assets/world3/opentopo/processed/master_stacks/zion_usgs10m_master_4call/
scene: D:/assets/world3/toporeview/zion_usgs10m_master_4call_review.tscn
capture: D:/assets/world3/docs/captures/opentopo/godot_zion_usgs10m_master_4call.png
world size: 36.80 x 36.88 km
target grid: 3680 x 3688 at 10 m
elevation range: 1080.22-2856.74 m
seam p99: 1.400 m
```

Final comparison sheet:

```text
D:/assets/world3/docs/captures/opentopo/opentopo_master_stack_final_comparison.png
```

Rejected/superseded candidates retained for QA:

```text
Chuculay Chile: real texture, but source-valid DEM remained about 50 percent
inside the cropped review rectangle.

Rainier USGS1m: high nominal detail, but two of four API tiles returned no
raster and the partial mosaic had only about 7.4 percent valid terrain.
```

## Comparison Report

Generated local comparison:

```text
D:/assets/world3/opentopo/processed/comparison/sample_comparison.md
D:/assets/world3/opentopo/processed/comparison/sample_comparison.json
D:/assets/world3/opentopo/processed/comparison/laz_headers.json
D:/assets/world3/opentopo/processed/comparison/extracted_layers.json
```

Sequential usage guide:

```text
D:/assets/world3/docs/OPENTOPO_DATA_TYPES.md
```

## Empty / Invalid Raw Products

The following COG reads produced all-nodata rasters and should not be used:

```text
bor_alaska_interior/NASADEM
bor_alaska_interior/SRTMGL1
tun_arctic_alaska/NASADEM
tun_arctic_alaska/SRTMGL1
```
