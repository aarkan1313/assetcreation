# OpenTopography Guide

This project keeps OpenTopography discovery plans, downloaded rasters, point
cloud probes, and converted heightmaps under `world3/opentopo/`.

## Documentation Rule

Any OpenTopo tooling, pipeline step, storage convention, or Godot viewer behavior
must be documented in this file before it is treated as part of the workflow.
Keep `opentopo/STATUS.md` synchronized with what was actually fetched and
processed. Keep `OPENTOPO_DATA_TYPES.md` synchronized with what each data type
proved useful for.

## Secret

The API key is stored locally, but not tracked:

```text
D:/assets/world3/opentopo/config/opentopo.env
D:/assets/world3/opentopo/config/opentopo.ps1
```

Primary secret name:

```text
OPENTOPOGRAPHY_API_KEY
```

Compatibility alias:

```text
OPENTOPO_API_KEY
```

`pipeline/opentopo_fetch.py` auto-loads `opentopo.env` if the shell environment
does not already define either name.

For PowerShell commands outside that helper, load the key with:

```powershell
. D:/assets/world3/opentopo/config/opentopo.ps1
```

For the rest of the repo, the existing convention is User-scope
`OPENTOPOGRAPHY_API_KEY`:

```powershell
$env:OPENTOPOGRAPHY_API_KEY = [Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY", "User")
```

Inside this sandbox, User-scope registry writes may be blocked or written to an
elevated context. The reliable local workflow is:

```powershell
. D:/assets/world3/opentopo/config/opentopo.ps1
```

Then run repo tools in the same shell.

Do not copy the actual key value into tracked docs, scripts, scenes, or commit
messages.

## Important Files

```text
world3/opentopo/README.md              Acquisition plan and storage layout
world3/opentopo/STATUS.md              What has actually been fetched/converted
world3/opentopo/sample_plan.json       14-biome / 70-site sample matrix
world3/opentopo/data_type_matrix.json  Two-representative plan per data type
world3/docs/OPENTOPO_DATA_TYPES.md     Sequential usage guide by data type
world3/docs/OPENTOPO_TOOLING_KNOBS_GUIDE.md  Short control-panel guide for tools, knobs, and compression tiers
world3/docs/OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md  Stitching and layer-fusion plans
world3/docs/OPENTOPO_TEXTURE_SCENE_ROADMAP.md    Texture baking, real-place scenes, HD zoom plan
world3/docs/OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md  Real-source tileable ground texture workflow
world3/docs/OPENTOPO_PHASE2_HD_REVIEW.md         4096 Guadalupe Cypress HD review pass
world3/docs/OPENTOPO_PHASE2_MAX_REVIEW.md        8192 + 16K RGB Guadalupe Cypress max pass
world3/docs/OPENTOPO_RENDER_REPAIR_WORKFLOW.md   Source-first no-data/cliff repair workflow
world3/docs/OPENTOPO_LARGE_4CALL_PLAN.md         Next 4-call `USGS1m` scale plan
world3/docs/OPENTOPO_PHASE3_SMOKIES_4CALL_AUDIT.md  Completed Smokies 4-call `USGS1m` audit
world3/docs/OPENTOPO_MASTER_STACKS_AUDIT.md      Final Gloss/Zion master-stack audit and commands
world3/pipeline/opentopo_fetch.py      API/catalog/raster fetch helper
world3/pipeline/finish_opentopo_soft_materials.py  Finished Godot material pass for tileable real-ground composites
world3/pipeline/fetch_opentopo_tile_grid.py  Split one AOI into overlapping API tile pulls
world3/pipeline/build_opentopo_mosaic.py     Same-type raster tiles -> GeoTIFF mosaic + seam QA
world3/pipeline/build_opentopo_mosaic_streaming.py  Large same-CRS raster mosaic builder
world3/pipeline/validate_opentopo_mosaic.py  Re-read a mosaic and verify source/mosaic consistency
world3/pipeline/validate_opentopo_mosaic_streaming.py  Large mosaic validator
world3/pipeline/build_world.py         GeoTIFF -> Godot heightmap converter
world3/pipeline/extract_opentopo_layers.py  Extract DSM-DTM and GEDI layers
world3/pipeline/build_opentopo_dtm_dsm_stack.py  Matched DTM+DSM -> no-color Godot stack with surface/material masks
world3/pipeline/inspect_laz_headers.py      Inspect LAZ capabilities
world3/pipeline/process_laz_samples.py      Stream LAZ and create DTM/DSM/color/QA rasters
world3/pipeline/export_opentopo_texture.py  GeoTIFF -> aligned Godot PNG layer
world3/pipeline/export_opentopo_mosaic.py   Many single-band GeoTIFFs -> one aligned PNG layer
world3/pipeline/export_opentopo_rgb_mosaic.py  Many RGB GeoTIFFs -> one aligned RGB PNG layer
world3/pipeline/export_opentopo_vegetation_mask.py  NIR/false-color ortho -> vegetation signal PNG
world3/pipeline/export_opentopo_review_texture.py  Aligned diagnostic layers -> synthetic review RGB
world3/pipeline/export_heightmap_review_layers.py  Heightmap/meta -> diagnostic review layers
world3/pipeline/build_opentopo_stack_manifest.py  Fused stack manifest + layer-size validation
world3/pipeline/build_opentopo_render_albedo.py   Source-first render albedo from real orthophoto
world3/pipeline/build_opentopo_textured_master_stack.py  DEM+orthophoto -> textured master stack and review package
world3/pipeline/build_opentopo_tileable_texture.py Real-source crop/material pilot builder
world3/scripts/OpenTopoSampleViewer.gd      Godot sample/layer browser
world3/toporeview/phase1_mosaic_review.tscn Phase 1 same-type mosaic review scene
world3/toporeview/phase2_fusion_review.tscn Phase 2 fused-stack review scene
world3/toporeview/phase2_fusion_hd_review.tscn Phase 2 4096 HD fused-stack review scene
world3/toporeview/phase2_fusion_max_review.tscn Phase 2 8192 max fused-stack review scene
world3/toporeview/phase2_fusion_ultra_rgb_review.tscn Phase 2 16K RGB stress scene
world3/toporeview/phase3_smokies_4call_review.tscn Phase 3 large 4-call `USGS1m` review scene
world3/toporeview/bc_coast_dtm_dsm_review.tscn BC Coast DTM/DSM no-color stack review scene
world3/toporeview/gloss_mountain_textured_master_review.tscn Final real-textured master scene
world3/toporeview/zion_usgs10m_master_4call_review.tscn Final large no-texture master scene
world3/toporeview/tileable_texture_review.tscn OpenTopo repeated-plane texture review scene
world3/toporeview/capture_phase*.tscn    Real Godot viewport capture wrappers
world3/toporeview/TopoReviewCapture.gd   Deterministic camera capture helper
world3/docs/captures/opentopo/           Real Godot screenshots and QA sheets
```

## Storage

```text
world3/opentopo/
  config/                  ignored local secrets
  catalog/                 ignored live catalog results
  raw/globaldem/           ignored raw GeoTIFFs from globaldem
  raw/usgsdem/             ignored raw GeoTIFFs from usgsdem
  raw/pointcloud/          ignored LAZ/LAS/tile-index data
  raw/dataspace/           ignored direct OpenTopography Dataspace rasters
  processed/heightmaps/    ignored Godot-ready heightmap bundles
  processed/mosaics/       ignored same-type stitched raster stacks
  processed/stacks/        ignored cross-type fused raster stacks
  processed/master_stacks/  ignored full source-aligned authoring stacks
  processed/pointcloud/    ignored LAZ-derived DTM/DSM/color/canopy products
  processed/comparison/    ignored audit reports
  sample_plan.json         tracked biome/site plan
```

## Current Master Stack Quickstart

Use these two scenes as the current primary OpenTopo master-stack review set:

```text
res://toporeview/gloss_mountain_textured_master_review.tscn
res://toporeview/zion_usgs10m_master_4call_review.tscn
```

Use these captures as the current validation images:

```text
D:/assets/world3/docs/captures/opentopo/godot_gloss_mountain_textured_master.png
D:/assets/world3/docs/captures/opentopo/godot_zion_usgs10m_master_4call.png
D:/assets/world3/docs/captures/opentopo/opentopo_master_stack_final_comparison.png
```

Rebuild and audit commands are recorded in:

```text
D:/assets/world3/docs/OPENTOPO_MASTER_STACKS_AUDIT.md
```

Gloss Mountain is the current real-textured stack. Zion is the current large
no-texture stack. Chuculay and Rainier are retained as rejected/superseded QA
attempts because their valid-source coverage was too sparse for the primary
master-stack target.

## Discovery

Catalog discovery does not need the API key:

```powershell
python D:/assets/world3/pipeline/opentopo_fetch.py --priority 1 --catalog
```

Dry-run the calibration wave:

```powershell
python D:/assets/world3/pipeline/opentopo_fetch.py --priority 1 --catalog --global COP30,NASADEM --dry-run
```

## Raster Pulls

Pull one site:

```powershell
python D:/assets/world3/pipeline/opentopo_fetch.py --site-id des_mojave_usa --global COP30,NASADEM
```

Pull the priority-1 calibration wave:

```powershell
python D:/assets/world3/pipeline/opentopo_fetch.py --priority 1 --global COP30,NASADEM
```

Fallback through public OpenTopo COG/VRT storage when the API is blocked:

```powershell
python D:/assets/world3/pipeline/opentopo_fetch.py --priority 1 --cog COP30,NASADEM,SRTMGL1
```

For US high-resolution rasters:

```powershell
python D:/assets/world3/pipeline/opentopo_fetch.py --site-id des_mojave_usa --km 10 --usgs USGS10m,USGS1m
```

Use small bounds for `USGS1m`; OpenTopography caps it at 250 km2 per job.
The tile-grid fetcher supports `--max-tile-area-km2 250` so a dry run can fail
early before downloading an over-limit `USGS1m` request.

Known-good OT+ verification pull:

```powershell
python D:/assets/world3/pipeline/opentopo_fetch.py --site-id tbm_appalachians_usa --km 2 --usgs USGS10m,USGS1m
```

Current large-area plan:

```text
world3/docs/OPENTOPO_LARGE_4CALL_PLAN.md
```

## Same-Type Tile Mosaics

Use this when one desired AOI is larger than the practical/API size for one
request, but all tiles are the same product.

The raw tile fetcher writes immutable source tiles plus `tile_grid_manifest.json`
under:

```text
world3/opentopo/raw/<family>/<stack_id>/
```

The mosaic builder writes the stitched terrain and QA products under:

```text
world3/opentopo/processed/mosaics/<stack_id>/
```

Dry-run an overlapping tile grid before downloading:

```powershell
python D:/assets/world3/pipeline/fetch_opentopo_tile_grid.py `
  --stack-id grand_canyon_usgs10m_pilot `
  --family usgsdem --dataset USGS10m `
  --center-lon -112.1129 --center-lat 36.1069 `
  --width-km 40 --height-km 40 `
  --tiles-x 2 --tiles-y 2 --overlap-km 2 `
  --dry-run
```

Only use the `250` guard for `USGS1m` or other products with comparable small
job caps. Large lower-resolution products have different area limits.

Fetch the tiles:

```powershell
python D:/assets/world3/pipeline/fetch_opentopo_tile_grid.py `
  --stack-id grand_canyon_usgs10m_pilot `
  --family usgsdem --dataset USGS10m `
  --center-lon -112.1129 --center-lat 36.1069 `
  --width-km 40 --height-km 40 `
  --tiles-x 2 --tiles-y 2 --overlap-km 2
```

Build the mosaic:

```powershell
python D:/assets/world3/pipeline/build_opentopo_mosaic.py `
  --input-dir D:/assets/world3/opentopo/raw/usgsdem/grand_canyon_usgs10m_pilot `
  --glob "USGS10m_*.tif" `
  --output-dir D:/assets/world3/opentopo/processed/mosaics/grand_canyon_usgs10m_pilot `
  --name grand_canyon_usgs10m_pilot `
  --target-crs EPSG:32612 `
  --target-cell-size-m 10 `
  --reducer mean `
  --resampling bilinear `
  --heightmap-size 1024 `
  --material rock_light
```

Mosaic outputs:

```text
mosaic.tif                 stitched float32 terrain
coverage_count.tif         number of source tiles per output pixel
seam_delta.tif             max-min elevation delta in overlap pixels
tile_footprints.geojson    source tile bounds
mosaic_report.json         numeric audit and output inventory
stack_manifest.json        grid/layer manifest for future stack loaders
heightmap.png              Godot-ready 16-bit square heightmap
meta.json                  terrain metadata for the heightmap
qa/*.png                   quick visual QA previews
```

Pilot audit:

```text
world3/docs/OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md
```

Validate a mosaic against its raw source tiles:

```powershell
python D:/assets/world3/pipeline/validate_opentopo_mosaic.py `
  --mosaic-dir D:/assets/world3/opentopo/processed/mosaics/grand_canyon_usgs10m_pilot `
  --raw-dir D:/assets/world3/opentopo/raw/usgsdem/grand_canyon_usgs10m_pilot `
  --glob "USGS10m_*.tif"
```

For large same-CRS mosaics such as the Smokies `USGS1m` 4-call run, use the
streaming builder/validator instead of the all-in-memory builder:

```powershell
python D:/assets/world3/pipeline/build_opentopo_mosaic_streaming.py `
  --input-dir D:/assets/world3/opentopo/raw/usgsdem/smokies_usgs1m_4call `
  --glob "USGS1m_*.tif" `
  --output-dir D:/assets/world3/opentopo/processed/mosaics/smokies_usgs1m_4call `
  --name smokies_usgs1m_4call `
  --target-crs EPSG:26917 `
  --target-cell-size-m 1 `
  --reducer first `
  --resampling bilinear `
  --heightmap-size 8192 `
  --preview-size 2048 `
  --mem-limit 512

python D:/assets/world3/pipeline/validate_opentopo_mosaic_streaming.py `
  --mosaic-dir D:/assets/world3/opentopo/processed/mosaics/smokies_usgs1m_4call `
  --raw-dir D:/assets/world3/opentopo/raw/usgsdem/smokies_usgs1m_4call `
  --glob "USGS1m_*.tif" `
  --max-seam-p99 0.05 `
  --max-unique-p99 0.05
```

## Dataspace Direct Downloads

Some OpenTopography Dataspace products are direct files rather than API jobs.
Record the dataset page in `opentopo/catalog/`, download raw files into
`opentopo/raw/dataspace/<source>/` or `opentopo/raw/pointcloud/<source>/`, and
then update `opentopo/STATUS.md`.

Guadalupe Cypress source page:

```text
https://portal.opentopography.org/dataspace/dataset?opentopoID=OTDS.122024.32611.1
```

Raw file destinations used for the color/vegetation sample:

```text
D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/
D:/assets/world3/opentopo/raw/pointcloud/Guadalupe_Cypress/
```

Direct file URL pattern:

```text
https://opentopography.s3.sdsc.edu/dataspace/<opentopoID>/<folder>/<filename>
```

Example:

```powershell
curl.exe -L --fail --continue-at - `
  --output D:/assets/world3/opentopo/raw/pointcloud/Guadalupe_Cypress/2016_rgb_pc_r1.laz `
  https://opentopography.s3.sdsc.edu/dataspace/OTDS.122024.32611.1/pointcloud/2016_rgb_pc_r1.laz
```

Generate the local sample comparison report:

```powershell
python D:/assets/world3/pipeline/audit_opentopo_samples.py
```

Extract higher-level layers:

```powershell
python D:/assets/world3/pipeline/extract_opentopo_layers.py
python D:/assets/world3/pipeline/inspect_laz_headers.py
```

Process LAZ point clouds:

```powershell
python -m pip install laspy lazrs pyproj pillow
python D:/assets/world3/pipeline/process_laz_samples.py --cell-size 2 --sample-count 5000 --max-canopy-height 120
```

The processor writes `dtm_ground.tif`, `dsm_surface.tif`,
`surface_minus_ground_raw.tif`, `chm_vegetation.tif`, `points_sample.csv`, and
`summary.json` for each `.laz` file. Treat `surface_minus_ground_raw.tif` as a QA
layer; use `chm_vegetation.tif` only when `summary.json` reports valid cells.

For large point clouds, process one source folder at a time:

```powershell
python D:/assets/world3/pipeline/process_laz_samples.py `
  --source Guadalupe_Cypress `
  --cell-size 1 `
  --sample-count 8000 `
  --max-canopy-height 120 `
  --chunk-size 1000000
```

If RGB exists in the LAS/LAZ file, the processor also writes:

```text
rgb_topdown.tif
rgb_topdown.png
```

If a matching raw Dataspace DTM exists under
`opentopo/raw/dataspace/<source>/`, it also writes:

```text
surface_minus_external_dtm.tif
surface_minus_external_dtm_preview.png
canopy_like_external_dtm.tif
canopy_like_external_dtm_preview.png
```

## Convert To Godot Heightmaps

Convert a raw GeoTIFF:

```powershell
python D:/assets/world3/pipeline/build_world.py `
  D:/assets/world3/opentopo/raw/globaldem/des_mojave_usa/COP30_*.tif `
  D:/assets/world3/opentopo/processed/heightmaps/des_mojave_usa/COP30 `
  --size 1024 --material rock_dark
```

Each converted bundle contains:

```text
heightmap.png
meta.json
```

The Godot terrain script reads those two files.

Convert Cypress DTM and aligned color/canopy layers:

```powershell
python D:/assets/world3/pipeline/build_world.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/DTM_RGB_2016.tif `
  D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016 `
  --size 1024 --material forest_floor

python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_rgb_orto_COF.tif `
  D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/orthophoto_rgb.png `
  --mode rgb --size 1024 `
  --match-meta D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/meta.json

python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/2016_rgb_pc_r1/canopy_like_external_dtm.tif `
  D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/canopy_height_mask.png `
  --mode gray --size 1024 --min-value 0 --max-value 35 `
  --match-meta D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/meta.json
```

`export_opentopo_texture.py` writes square PNG texture channels plus a small
JSON sidecar. Use `--match-meta` when a layer should align to an existing
`build_world.py` terrain package.

Build a no-color DTM/DSM stack when matched bare-earth and surface rasters
exist but real orthophoto color does not:

```powershell
python D:/assets/world3/pipeline/build_opentopo_dtm_dsm_stack.py `
  --dtm D:/assets/world3/opentopo/raw/cog/tcf_bc_coast_canada/CA_MRDEM_DTM_m123.1398_p49.9096_m122.8602_p50.0904.tif `
  --dsm D:/assets/world3/opentopo/raw/cog/tcf_bc_coast_canada/CA_MRDEM_DSM_m123.1398_p49.9096_m122.8602_p50.0904.tif `
  --output-dir D:/assets/world3/opentopo/processed/heightmaps/tcf_bc_coast_dtm_dsm_stack `
  --name "BC Coast DTM DSM No-Color Stack" `
  --size 4096 --surface-max-m 45
```

This writes `heightmap.png`, `meta.json`, `stack_manifest.json`, and aligned
layers including `terrain_texture`, `surface_height`, `forest_surface_mask`,
`rock_slope_mask`, `wetness_valley_mask`, `material_mask_rgba`, and QA masks.
It is a practical starting point for a no-orthophoto megastack.

After processing all Guadalupe LAZ regions, build one max-combined canopy layer:

```powershell
$canopy = Get-ChildItem `
  D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress `
  -Recurse -Filter canopy_like_external_dtm.tif

python D:/assets/world3/pipeline/export_opentopo_mosaic.py `
  $canopy.FullName `
  --output D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/canopy_height_mosaic.png `
  --size 1024 --min-value 0 --max-value 60 --reducer max `
  --match-meta D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/meta.json
```

`scenes/opentopo_samples.tscn` starts on the Cypress sample when available. If a
sample folder contains `layers/*.png`, `OpenTopoSampleViewer.gd` applies those
layers as terrain overlays. Press `L` to cycle the overlay layer while the scene
is running.

## Mosaic And Fusion Workflows

The two next workflows are documented in
`world3/docs/OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md`:

- Same-type mosaics: split a large AOI into multiple requests, pull the same
  product for each tile, stitch into one seamless terrain package, and run seam
  QA.
- Cross-type fused stacks: choose one canonical grid, then align DTM/DSM/CHM,
  orthophoto, NIR, LAZ-derived products, GEDI, slope, roughness, and hillshade
  into one stack with a manifest.

Do not build tooling for either workflow without updating that doc and this
guide.

Current cross-type fusion pilot:

```text
D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/
D:/assets/world3/docs/OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md
```

The fused stack uses one `meta.json` as the canonical grid, then exports
orthophoto RGB, NIR/false color, NIR-derived vegetation signal, LAZ-derived
canopy/CHM, point-cloud RGB top-down mosaics, slope, roughness, and hillshade
into `layers/*.png`.

No-data policy:

- Keep broad crops even when they contain small source gaps.
- Preserve no-data and record valid-pixel counts.
- Future procedural/generative fill must write separate filled masks and never
  pretend filled pixels are original source measurements.

## Godot Topo Review Scenes

Open these in Godot for interactive review:

```text
res://toporeview/phase1_mosaic_review.tscn
res://toporeview/phase2_fusion_review.tscn
res://toporeview/phase2_fusion_hd_review.tscn
res://toporeview/phase2_fusion_max_review.tscn
res://toporeview/phase2_fusion_ultra_rgb_review.tscn
res://toporeview/phase3_smokies_4call_review.tscn
```

The shared controller is:

```text
res://toporeview/TopoReview.gd
```

Real viewport capture workflow:

```powershell
$args = @("--path", "D:/assets/world3", "res://toporeview/capture_phase1_mosaic.tscn")
$p = Start-Process -FilePath "C:/Godot/Godot_v4.5-stable_win64.exe" -ArgumentList $args -Wait -PassThru
"EXIT=$($p.ExitCode)"
```

Use normal Godot and pass the capture scene as the trailing argument. This
produces real in-engine viewport screenshots through `scripts/HeadlessCapture.gd`.
Do not use the older waited `--headless --scene ... --quit-after ...` command as
scene validation; that local Windows runner path can hit access violation
`-1073741819` even when the real capture scene works.

Current OpenTopo real Godot captures:

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

The older `opentopo_phase_*` comparison sheets in the same folder are static
data-layer QA references. They are useful, but they are not substitutes for
real Godot screenshots.

Render repair policy:

- Geometry can be repaired for a render-safe heightmap.
- Real orthophoto color remains the default albedo source.
- `render_albedo` is source-first; it does not procedurally repaint repaired
  DEM areas.
- Any future generated or stylized material must be tracked separately from
  source data.

Repair workflow:

```text
world3/docs/OPENTOPO_RENDER_REPAIR_WORKFLOW.md
```

Close-up Phase 2 finding:

- 1024/256 mesh is too soft at ground distance.
- 4096/512 improves orthophoto readability but still needs better geometry and
  material treatment.
- 8192/1024 is visibly sharper, but terrain triangles/normals become obvious.
  The next fidelity step should be chunked terrain plus real data projection
  from DSM/LAZ/color sources where available.

Controls are documented in:

```text
res://toporeview/README.md
```

Phase 1 starts on `terrain_texture`, a synthetic review texture generated from
the aligned elevation, hillshade, slope, and roughness PNG layers. It is a
diagnostic visualization for canyon form and seams, not real orthophoto color.
Regenerate it with:

```powershell
python D:/assets/world3/pipeline/export_opentopo_review_texture.py `
  --layers-dir D:/assets/world3/toporeview/phase1_mosaic/layers `
  --output D:/assets/world3/toporeview/phase1_mosaic/layers/terrain_texture.png
```

The first Phase 2 HD review pass is documented in:

```text
world3/docs/OPENTOPO_PHASE2_HD_REVIEW.md
world3/docs/OPENTOPO_PHASE2_MAX_REVIEW.md
```

## Current Data Notes

The API key path is working for small `globaldem` and `usgsdem` checks. Keep
large pulls staged because OT+ products still have area limits and account quota
behavior.

Valid converted samples currently exist under:

```text
D:/assets/world3/opentopo/processed/heightmaps/
```
