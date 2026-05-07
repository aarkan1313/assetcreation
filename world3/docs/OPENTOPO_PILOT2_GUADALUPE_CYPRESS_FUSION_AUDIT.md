# OpenTopo Pilot 2 Audit: Guadalupe Cypress Fused Stack

Date: 2026-05-07

Scope: Workflow 2. This validates cross-type layer fusion after the same-type
mosaic workflow passed.

## Goal

Build one aligned stack that combines terrain height, real color, vegetation
signal, point-cloud-derived canopy, point-cloud color, and terrain derivatives.

Chosen site: Guadalupe Cypress.

Why this site:

- Has a 1 m DTM in `EPSG:32611`.
- Has high-resolution RGB orthophoto.
- Has high-resolution NIR/false-color orthophoto.
- Has seven overlapping LAZ regions already processed into DTM/DSM/CHM,
  canopy-like rasters, and RGB top-down rasters.
- Visually interesting: dry mountainous terrain, drainage structure, shrub/tree
  patches, rocky slopes, and visible vegetation patterning.

## Review Stack

Primary review target:

```text
D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/
```

Grid:

- CRS: `EPSG:32611`
- Bounds: `370200, 3218600, 371800, 3220200`
- Size: `1600 m x 1600 m`
- Heightmap: `1024 x 1024`
- Elevation range: `931 m` to `1201 m`

This stricter crop was chosen after broader crops showed real source-footprint
gaps in the orthophoto/NIR/point-cloud products.

Broader variants kept for later no-data repair experiments:

```text
D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_fused_pilot/
D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_core_fused_pilot/
D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_overlap_fused_pilot/
```

Do not delete those just because they contain no-data strips. They are useful
for testing procedural or generative gap filling later.

## Generated Layers

All review-stack layers are `1024 x 1024` and validated by
`stack_manifest.json`.

| Layer | Role | Valid Pixels |
|---|---|---:|
| `heightmap.png` | base DTM terrain | 1,048,576 |
| `orthophoto_rgb.png` | real color/reference albedo | 1,048,576 |
| `orthophoto_nir_false.png` | NIR/false-color vegetation reference | 1,000,762 |
| `vegetation_ndvi_like.png` | NIR-derived vegetation signal | 1,000,762 |
| `canopy_height_mosaic.png` | LAZ-derived canopy-like height | 987,137 |
| `chm_vegetation_mosaic.png` | LAS class-based high vegetation CHM | 45,758 |
| `pointcloud_rgb_topdown_mosaic.png` | LAZ RGB top-down color | 1,040,867 |
| `pointcloud_nir_source_topdown_mosaic.png` | NIR-source LAZ top-down color | 981,711 |
| `hillshade.png` | terrain relief QA/reference | 1,048,576 |
| `slope_deg.png` | material-mask source | 1,048,576 |
| `roughness.png` | material-mask source | 1,048,576 |

QA contact sheet:

```text
D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/qa/contact_sheet.png
```

## Commands

Build cropped DTM heightmap:

```powershell
python D:/assets/world3/pipeline/build_world.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/DTM_RGB_2016.tif `
  D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot `
  --size 1024 --material forest_floor `
  --bbox 370200 3218600 371800 3220200 `
  --world-size-m 1600
```

Export orthophoto layers:

```powershell
python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_rgb_orto_COF.tif `
  D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/layers/orthophoto_rgb.png `
  --mode rgb --size 1024 `
  --match-meta D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/meta.json

python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_nir_orto_COG.tif `
  D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/layers/orthophoto_nir_false.png `
  --mode rgb --size 1024 `
  --match-meta D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/meta.json
```

Export NIR-derived vegetation signal:

```powershell
python D:/assets/world3/pipeline/export_opentopo_vegetation_mask.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_nir_orto_COG.tif `
  D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/layers/vegetation_ndvi_like.png `
  --size 1024 `
  --match-meta D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/meta.json
```

Export terrain derivatives:

```powershell
python D:/assets/world3/pipeline/derive_rasters.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/DTM_RGB_2016.tif `
  D:/assets/world3/opentopo/processed/derived/Guadalupe_Cypress/DTM_RGB_2016

python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/processed/derived/Guadalupe_Cypress/DTM_RGB_2016/slope_deg.tif `
  D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/layers/slope_deg.png `
  --mode gray --size 1024 --min-value 0 --max-value 75 `
  --match-meta D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/meta.json
```

Export point-cloud mosaics:

```powershell
$canopy = Get-ChildItem `
  D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress `
  -Recurse -Filter canopy_like_external_dtm.tif

python D:/assets/world3/pipeline/export_opentopo_mosaic.py `
  $canopy.FullName `
  --output D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/layers/canopy_height_mosaic.png `
  --size 1024 --min-value 0 --max-value 60 --reducer max `
  --match-meta D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/meta.json
```

Build manifest:

```powershell
python D:/assets/world3/pipeline/build_opentopo_stack_manifest.py `
  --stack-dir D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot `
  --name guadalupe_cypress_strict_fused_pilot `
  --site Guadalupe_Cypress
```

## Findings

What works:

- The base DTM, RGB orthophoto, NIR orthophoto, point-cloud top-down color,
  canopy-like layer, slope, roughness, and hillshade all align to one Godot
  grid.
- The RGB orthophoto is the best real albedo/reference layer.
- The NIR-derived vegetation signal is useful for vegetation masks and is
  visually consistent with tree/shrub clusters.
- The canopy-like layer catches taller vegetation clusters, especially on the
  right side of the crop.
- `chm_vegetation_mosaic.png` is sparse because it depends on LAS vegetation
  class labels. It is useful as a conservative high-confidence vegetation layer,
  not as the only vegetation signal.

What needs care:

- Some otherwise good larger crops contain orthophoto or point-cloud no-data
  strips. Keep them. Do not discard visually interesting sites because of
  limited gaps.
- Any future filled pixels must be tracked as filled/synthetic, not source.
- The `vegetation_ndvi_like.png` band mapping assumes NIR is band 1 and red is
  band 2. That assumption needs dataset-specific confirmation before treating
  it as a scientific NDVI product.

## No-Data Policy

Current rule:

- Preserve no-data as no-data.
- Record valid-pixel counts in layer sidecars and `stack_manifest.json`.
- Use clean crops for first-pass alignment validation.
- Keep broader crops for later fill experiments.

Future fill pipeline should support:

- Edge-aware raster inpainting for small orthophoto gaps.
- Terrain-aware procedural texture fill using slope/roughness/elevation masks.
- Canopy/vegetation fill from nearby NIR and point-cloud statistics.
- Optional generative fill for visual-only albedo, with a separate filled mask.
- `source_valid_mask.png` and `filled_mask.png` for every filled layer.

Never let filled pixels masquerade as measured source data.
