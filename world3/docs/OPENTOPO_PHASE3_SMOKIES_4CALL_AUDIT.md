# OpenTopo Phase 3 Audit: Smokies USGS1m 4-Call Mosaic

Status: completed and data-validated.

Date: 2026-05-07

## Goal

Build the largest practical high-resolution stitched height mosaic we can make
with four OpenTopography raster API calls, then make it viewable in Godot.

This phase proves the scale workflow. It does not yet prove color/canopy fusion
over the full area; that is the next overlap pass.

## Target

```text
Name: smokies_usgs1m_4call
Area: Southern Appalachians / Smokies
Center: lon -83.50, lat 35.60
Dataset: USGS1m
API family: usgsdem
Tiles: 2 x 2
Requested unique AOI: 29 km x 29 km
Overlap: 1 km
Per request: 15 km x 15 km = 225 km2
Limit guard: 250 km2
Preflight over_limit: []
```

The 250 km2 cap is the OpenTopography `USGS1m` request cap. The "350" number
from earlier is a point-cloud processing limit in millions of points, not a
distance or raster width.

## Raw Fetch

Command:

```powershell
python D:/assets/world3/pipeline/fetch_opentopo_tile_grid.py `
  --stack-id smokies_usgs1m_4call `
  --family usgsdem `
  --dataset USGS1m `
  --center-lon -83.50 `
  --center-lat 35.60 `
  --width-km 29 `
  --height-km 29 `
  --tiles-x 2 `
  --tiles-y 2 `
  --overlap-km 1 `
  --max-tile-area-km2 250 `
  --timeout 1200
```

Raw output:

```text
D:/assets/world3/opentopo/raw/usgsdem/smokies_usgs1m_4call/
```

Files:

```text
USGS1m_r00_c00_m83.6602_p35.4689_m83.4945_p35.6045.tif  700,053,936 bytes
USGS1m_r00_c01_m83.5055_p35.4689_m83.3398_p35.6045.tif  704,445,854 bytes
USGS1m_r01_c00_m83.6602_p35.5955_m83.4945_p35.7311.tif  701,245,023 bytes
USGS1m_r01_c01_m83.5055_p35.5955_m83.3398_p35.7311.tif  702,401,714 bytes
tile_grid_manifest.json
```

All four raw tiles are:

```text
CRS: EPSG:26917
Resolution: 1 m
Data type: float32
NoData: -999999.0
```

## Streaming Mosaic

The original all-in-memory mosaic builder is not appropriate for this scale.
The 1 m target grid has about 865 million cells, and the old reducer keeps many
full-size arrays in memory. For this run, the pipeline uses:

```text
D:/assets/world3/pipeline/build_opentopo_mosaic_streaming.py
D:/assets/world3/pipeline/validate_opentopo_mosaic_streaming.py
```

Build command:

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
```

Processed output:

```text
D:/assets/world3/opentopo/processed/mosaics/smokies_usgs1m_4call/
```

Key products:

```text
mosaic.tif              1,975,792,241 bytes
coverage_count.tif         5,087,126 bytes
seam_delta.tif             6,924,657 bytes
heightmap.png             79,399,544 bytes
meta.json
mosaic_report.json
validation_report.json
stack_manifest.json
tile_footprints.geojson
qa/
```

## Mosaic Metrics

```text
Target grid: 29005 x 29835
Cell size: 1 m
Projected size: 29.005 km x 29.835 km
Valid pixels: 845,312,752
Elevation range: 358.2009 m to 2025.1490 m
Mean elevation: 1059.9961 m
Overlap pixels: 56,463,759
```

The final footprint is slightly taller than the requested 29 km because the API
returned projected tile bounds that snap to the 1 m target grid.

## Validation

Command:

```powershell
python D:/assets/world3/pipeline/validate_opentopo_mosaic_streaming.py `
  --mosaic-dir D:/assets/world3/opentopo/processed/mosaics/smokies_usgs1m_4call `
  --raw-dir D:/assets/world3/opentopo/raw/usgsdem/smokies_usgs1m_4call `
  --glob "USGS1m_*.tif" `
  --max-seam-p99 0.05 `
  --max-unique-p99 0.05
```

Result:

```text
status: pass_with_notes
shape_consistency: pass
target_crs: pass
nodata_inside_coverage: pass
report_valid_pixel_count: pass
seam_p99_limit: pass
unique_area_source_match: pass
```

Important validation numbers:

```text
seam p99: 0.0 m
source-window unique-area p99 delta: 0.00006103515625 m
```

Notes:

- The grid is rectangular. `Terrain.gd` now honors optional
  `world_size_x_m` / `world_size_z_m` metadata so the review scene does not
  squash it into a square.
- The validator does not prove vertical datum provenance. Keep that as a source
  metadata task for any downstream scientific use.

## Godot Review

View scene:

```text
res://toporeview/phase3_smokies_4call_review.tscn
D:/assets/world3/toporeview/phase3_smokies_4call_review.tscn
```

Review assets:

```text
D:/assets/world3/toporeview/phase3_smokies_4call/
```

Layers:

```text
terrain_texture.png   procedural Appalachian diagnostic texture, not real imagery
hillshade.png
elevation_gray.png
coverage_count.png
seam_delta.png
slope_deg.png
roughness.png
```

Layer export command:

```powershell
python D:/assets/world3/pipeline/export_heightmap_review_layers.py `
  --heightmap D:/assets/world3/toporeview/phase3_smokies_4call/heightmap.png `
  --meta D:/assets/world3/toporeview/phase3_smokies_4call/meta.json `
  --output-dir D:/assets/world3/toporeview/phase3_smokies_4call/layers `
  --terrain-style appalachian
```

The procedural texture was visually checked directly as a PNG, then validated
as a real Godot viewport capture.

Godot capture command:

```powershell
$p = Start-Process -FilePath "C:/Godot/Godot_v4.5-stable_win64.exe" `
  -ArgumentList @(
    "--path", "D:/assets/world3",
    "res://toporeview/capture_phase3_smokies_4call.tscn"
  ) `
  -Wait `
  -PassThru
```

Result: pass, exit code `0`.

Output:

```text
D:/assets/world3/docs/captures/opentopo/godot_phase3_smokies_4call.png
```

The older waited `--headless --scene ... --quit-after ...` path can hit Windows
access violation `-1073741819` across Phase 1, Phase 2, and Phase 3. Do not use
that path as scene validation. Use the capture wrapper or interactive Godot
review.

## What This Proves

- Four `USGS1m` API calls can produce a large high-resolution stitched terrain.
- The tile-area guard correctly kept every request below the 250 km2 cap.
- The streaming builder avoids the all-in-memory failure mode.
- Seam QA is clean for this area.
- The output is already useful for high-level terrain review and material-mask
  generation.

## What This Does Not Prove Yet

- It does not include real orthophoto color over the whole 29 km x 29.8 km area.
- It does not include canopy height over the whole area.
- It does not include full point-cloud fusion yet.
- It does not solve close-up Godot fidelity for a 29 km single mesh. The 8192
  heightmap is about 3.5 m/px in the review export, and the 1024-subdivision
  mesh is an overview mesh. Real close-up fidelity needs chunking.

## Next Pass

Start overlap/fusion over the Smokies footprint:

1. Query point-cloud coverage for the same bounds.
2. Pull one or two representative point-cloud windows first, not the entire
   29 km area.
3. Derive canopy/surface-color rasters where point clouds overlap.
4. Add real color imagery if OpenTopo orthophoto is unavailable for the full
   AOI.
5. Convert the big scene to chunks for close-up review.
