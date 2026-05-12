# OpenTopo Master Stacks Audit

Date: 2026-05-07

This pass built two brand-new OpenTopography master stacks for game review:

- A real-textured stack: Gloss Mountain State Park, Oklahoma.
- A large no-texture stack: Zion area, Utah, split into four API calls.

The deliverable is not just PNG screenshots. Each final stack has raw source
files, lossless or near-lossless processed GeoTIFF masters, Godot review layers,
real Godot capture scenes, and QA notes.

## Final Outputs

Primary Godot scenes:

```text
D:/assets/world3/toporeview/gloss_mountain_textured_master_review.tscn
D:/assets/world3/toporeview/zion_usgs10m_master_4call_review.tscn
```

Capture wrappers:

```text
D:/assets/world3/toporeview/capture_gloss_mountain_textured_master.tscn
D:/assets/world3/toporeview/capture_zion_usgs10m_master_4call.tscn
```

Real Godot captures:

```text
D:/assets/world3/docs/captures/opentopo/godot_gloss_mountain_textured_master.png
D:/assets/world3/docs/captures/opentopo/godot_zion_usgs10m_master_4call.png
D:/assets/world3/docs/captures/opentopo/opentopo_master_stack_final_comparison.png
```

Processed master roots:

```text
D:/assets/world3/opentopo/processed/master_stacks/gloss_mountain_textured_master/
D:/assets/world3/opentopo/processed/master_stacks/zion_usgs10m_master_4call/
```

## Textured Master: Gloss Mountain

Source dataset:

```text
Survey of Gloss Mountain State Park, Oklahoma, November 7 2021
OpenTopo ID: OTDS.072022.32615.1
License: CC BY 4.0
Products used: DSM + orthomosaic
```

Raw files:

```text
D:/assets/world3/opentopo/raw/dataspace/Gloss_Mountain_2021/Gloss_Mountain_DEM.tif
D:/assets/world3/opentopo/raw/dataspace/Gloss_Mountain_2021/Gloss_Mountain_Orthomosaic.tif
```

Why this is the final textured candidate:

- It has real color, real topography, and a visually strong mesa/eroded-slope
  form.
- The source DEM and orthomosaic overlap well enough after cropping.
- It is a practical game-scale area: about `0.62 x 1.08 km` in the review
  scene, not just a tiny texture sample.

Build command:

```powershell
python D:/assets/world3/pipeline/build_opentopo_textured_master_stack.py `
  --dem D:/assets/world3/opentopo/raw/dataspace/Gloss_Mountain_2021/Gloss_Mountain_DEM.tif `
  --orthophoto D:/assets/world3/opentopo/raw/dataspace/Gloss_Mountain_2021/Gloss_Mountain_Orthomosaic.tif `
  --output-dir D:/assets/world3/opentopo/processed/master_stacks/gloss_mountain_textured_master `
  --name "Gloss Mountain Textured Master Stack" `
  --review-max-dim 8192 `
  --material real_mesa_orthophoto `
  --crop-to-valid-dem `
  --crop-margin-px 16
```

Key stats:

```text
CRS: EPSG:32615
Review size: 4718 x 8192 px
World size: 619.4 x 1075.4 m
Elevation: 393.84-477.62 m
Valid DEM inside cropped stack: 84.44 percent
Orthophoto coverage inside cropped stack: 84.49 percent
Render fill mask: documented in render_fill_mask.png
Cliff/steep-risk review pixels: 15.70 percent
```

Layer meaning:

```text
render_albedo.png          Real orthophoto with documented edge/gap extension
orthophoto_rgb.png         Raw aligned orthophoto reference, unfilled
source_valid_mask.png      Valid DEM source pixels
texture_coverage_mask.png  Valid orthophoto source pixels
render_fill_mask.png       Pixels where render_albedo extended nearby source color
cliff_mask.png             Steep top-down texture stretch risk
hillshade/slope/roughness  Terrain diagnostics
```

Important limitation: this is photogrammetry/DSM, not a clean bare-earth DTM.
It is excellent as a visual game-area test and baked ground source, but exposed
vertical edges still need mesh-side treatment, skirts, chunk clipping, or a
proper masked terrain mesh before it is production terrain.

## No-Texture Master: Zion 4-Call USGS10m

Source:

```text
OpenTopo API: /usgsdem
Dataset: USGS10m
Center: lon -112.95, lat 37.30
Requested AOI: 36 x 36 km
Tile grid: 2 x 2
Overlap: 1 km
Per tile area: 342.25 km2
```

Raw files:

```text
D:/assets/world3/opentopo/raw/usgsdem/zion_usgs10m_master_4call/
```

Fetch command:

```powershell
python D:/assets/world3/pipeline/fetch_opentopo_tile_grid.py `
  --stack-id zion_usgs10m_master_4call `
  --family usgsdem `
  --dataset USGS10m `
  --center-lon -112.95 `
  --center-lat 37.30 `
  --width-km 36 `
  --height-km 36 `
  --tiles-x 2 `
  --tiles-y 2 `
  --overlap-km 1 `
  --max-tile-area-km2 350 `
  --timeout 600
```

Mosaic command:

```powershell
python D:/assets/world3/pipeline/build_opentopo_mosaic.py `
  --input-dir D:/assets/world3/opentopo/raw/usgsdem/zion_usgs10m_master_4call `
  --glob "USGS10m_*.tif" `
  --output-dir D:/assets/world3/opentopo/processed/master_stacks/zion_usgs10m_master_4call `
  --name "Zion USGS10m No-Texture Master Stack" `
  --target-crs EPSG:32612 `
  --target-cell-size-m 10 `
  --reducer mean `
  --resampling bilinear `
  --heightmap-size 8192 `
  --material sandstone_no_texture
```

Review layer command:

```powershell
python D:/assets/world3/pipeline/export_heightmap_review_layers.py `
  --heightmap D:/assets/world3/opentopo/processed/master_stacks/zion_usgs10m_master_4call/heightmap.png `
  --meta D:/assets/world3/opentopo/processed/master_stacks/zion_usgs10m_master_4call/meta.json `
  --output-dir D:/assets/world3/opentopo/processed/master_stacks/zion_usgs10m_master_4call/layers `
  --terrain-style sandstone `
  --coverage-raster D:/assets/world3/opentopo/processed/master_stacks/zion_usgs10m_master_4call/coverage_count.tif `
  --seam-raster D:/assets/world3/opentopo/processed/master_stacks/zion_usgs10m_master_4call/seam_delta.tif
```

Key stats:

```text
Target CRS: EPSG:32612
Target grid: 3680 x 3688 at 10 m
World size: 36.80 x 36.88 km
Elevation: 1080.22-2856.74 m
Valid pixels: 13,027,232
Overlap pixels: 708,388
Seam p50: 0.033 m
Seam p95: 0.439 m
Seam p99: 1.400 m
Seam > 5 m: 0.084 percent of overlap pixels
```

Layer meaning:

```text
terrain_texture.png        Procedural sandstone review material, not real color
hillshade.png              Landform visualization
elevation_gray.png         Normalized elevation
coverage_count.png         Tile contribution count
seam_delta.png             Absolute overlap disagreement
slope_deg.png              Slope mask
roughness.png              Local terrain roughness
```

This is the stronger no-texture game candidate than the attempted Rainier 1 m
stack because it has broad, clean coverage and no giant no-data plate.

## Rejected Or Superseded Attempts

Chuculay, Chile:

```text
D:/assets/world3/opentopo/raw/dataspace/Chuculay_Chile_2018/
D:/assets/world3/opentopo/processed/master_stacks/chuculay_textured_master/
D:/assets/world3/toporeview/chuculay_textured_master_review.tscn
```

Reason: real orthophoto looked interesting, but the valid DEM footprint was too
strip-like for a primary master. After valid-footprint crop, only about
`50 percent` of the review rectangle was source-valid elevation. Keep it as a
stress case for masked terrain and cliff repair, not as the recommended
textured master.

Mount Rainier USGS1m:

```text
D:/assets/world3/opentopo/raw/usgsdem/rainier_usgs1m_master_4call/
D:/assets/world3/opentopo/processed/master_stacks/rainier_usgs1m_south_master/
D:/assets/world3/toporeview/rainier_usgs1m_south_master_review.tscn
```

Reason: two of four API tiles returned no raster, and the two successful tiles
still produced only about `7.4 percent` valid terrain on the target grid. Keep
it as a no-data failure case and API coverage lesson.

## Pipeline Changes Made

New script:

```text
D:/assets/world3/pipeline/build_opentopo_textured_master_stack.py
```

Updated scripts:

```text
D:/assets/world3/pipeline/build_opentopo_mosaic.py
D:/assets/world3/pipeline/export_heightmap_review_layers.py
```

New knobs:

```text
--crop-to-valid-dem
--crop-margin-px
--texture-fill-distance-px
--terrain-style sandstone
--coverage-raster
--seam-raster
```

Rules learned:

- A big bounding box is not a big usable terrain if the valid-source mask is
  sparse.
- Always inspect valid-source percent before declaring a master stack good.
- Keep raw orthophoto and raw masks. Use `render_albedo` as the render-facing
  repaired layer, not as the sole source of truth.
- For no-texture stacks, broad clean coverage beats high nominal resolution
  with sparse no-data.
