# OpenTopo Phase 2 HD Review

Date: 2026-05-07

Status: first HD single-tile pass generated and validated.

## Purpose

The original Phase 2 Guadalupe Cypress review scene proved that a fused stack
could align DTM, orthophoto, NIR, point-cloud-derived canopy, hillshade, slope,
and roughness. It was intentionally lightweight:

```text
Texture size: 1024 x 1024
AOI:          1.6 km x 1.6 km
Texture scale: about 1.56 m/px
Mesh:         256 subdivisions
Mesh spacing: about 6.25 m/vertex
```

That looked good from high altitude but broke down close up. This HD pass keeps
the same AOI and stack idea, but exports source-aligned layers at 4096.

## Outputs

Godot scene:

```text
D:/assets/world3/toporeview/phase2_fusion_hd_review.tscn
```

Stack folder:

```text
D:/assets/world3/toporeview/phase2_fusion_hd/
```

Manifest:

```text
D:/assets/world3/toporeview/phase2_fusion_hd/stack_manifest.json
```

## Current HD Specs

```text
AOI:             1.6 km x 1.6 km
Heightmap:       4096 x 4096
Layer textures:  4096 x 4096
Texture scale:   about 0.3906 m/px
Scene mesh:      512 subdivisions
Mesh spacing:    about 3.125 m/vertex
CRS:             EPSG:32611
Elevation range: 931.06 m to 1201.28 m
```

Source-data ceiling for this AOI:

```text
RGB orthophoto: about 0.06627 m/px
NIR orthophoto: about 0.06486 m/px
DTM:            1.0 m cell size
```

Interpretation:

- Color detail is still below source-native. A chunked/native pass could go
  higher than 4096.
- Mesh detail is still lower than the 1 m DTM. A 1024-subdivision mesh would
  reach about 1.56 m/vertex, but may be heavier.
- True sub-meter geometry would need LAZ-derived surface detail, normal maps,
  or procedural micro-detail.

## Layers

All layers are aligned to the same `meta.json` bounds and validate at
`4096 x 4096`.

```text
orthophoto_rgb.png
orthophoto_nir_false.png
vegetation_ndvi_like.png
canopy_height_mosaic.png
chm_vegetation_mosaic.png
pointcloud_rgb_topdown_mosaic.png
pointcloud_nir_source_topdown_mosaic.png
hillshade.png
slope_deg.png
roughness.png
```

## Validation

```text
stack_manifest.json status: pass
Godot headless scene load: success
```

Validation command:

```powershell
python D:/assets/world3/pipeline/build_opentopo_stack_manifest.py `
  --stack-dir D:/assets/world3/toporeview/phase2_fusion_hd `
  --name guadalupe_cypress_phase2_hd_review `
  --site Guadalupe_Cypress `
  --description "4096 Phase 2 HD single-tile review stack for texture, scene, and zoom fidelity testing"

& "C:/Godot/Godot_v4.5-stable_win64.exe" `
  --headless --path "D:/assets/world3" `
  "res://toporeview/phase2_fusion_hd_review.tscn" --quit-after 3
```

## Rebuild Commands

Build the 4096 heightmap:

```powershell
python D:/assets/world3/pipeline/build_world.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/DTM_RGB_2016.tif `
  D:/assets/world3/toporeview/phase2_fusion_hd `
  --size 4096 --material forest_floor `
  --bbox 370200 3218600 371800 3220200
```

Export the orthophoto and terrain-derived core layers:

```powershell
python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_rgb_orto_COF.tif `
  D:/assets/world3/toporeview/phase2_fusion_hd/layers/orthophoto_rgb.png `
  --mode rgb --size 4096 `
  --match-meta D:/assets/world3/toporeview/phase2_fusion_hd/meta.json

python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_nir_orto_COG.tif `
  D:/assets/world3/toporeview/phase2_fusion_hd/layers/orthophoto_nir_false.png `
  --mode rgb --size 4096 `
  --match-meta D:/assets/world3/toporeview/phase2_fusion_hd/meta.json

python D:/assets/world3/pipeline/export_opentopo_vegetation_mask.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_nir_orto_COG.tif `
  D:/assets/world3/toporeview/phase2_fusion_hd/layers/vegetation_ndvi_like.png `
  --size 4096 `
  --match-meta D:/assets/world3/toporeview/phase2_fusion_hd/meta.json
```

Export hillshade/slope/roughness:

```powershell
python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/processed/derived/Guadalupe_Cypress/DTM_RGB_2016/hillshade.tif `
  D:/assets/world3/toporeview/phase2_fusion_hd/layers/hillshade.png `
  --mode gray --size 4096 --min-value 0 --max-value 255 `
  --match-meta D:/assets/world3/toporeview/phase2_fusion_hd/meta.json

python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/processed/derived/Guadalupe_Cypress/DTM_RGB_2016/slope_deg.tif `
  D:/assets/world3/toporeview/phase2_fusion_hd/layers/slope_deg.png `
  --mode gray --size 4096 --min-value 0 --max-value 75 `
  --match-meta D:/assets/world3/toporeview/phase2_fusion_hd/meta.json

python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/processed/derived/Guadalupe_Cypress/DTM_RGB_2016/roughness.tif `
  D:/assets/world3/toporeview/phase2_fusion_hd/layers/roughness.png `
  --mode gray --size 4096 --min-value 0 --max-value 50 `
  --match-meta D:/assets/world3/toporeview/phase2_fusion_hd/meta.json
```

Export point-cloud-derived mosaics:

```powershell
$canopy = Get-ChildItem `
  -LiteralPath D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress `
  -Recurse -Filter canopy_like_external_dtm.tif
python D:/assets/world3/pipeline/export_opentopo_mosaic.py @($canopy.FullName) `
  --output D:/assets/world3/toporeview/phase2_fusion_hd/layers/canopy_height_mosaic.png `
  --size 4096 --min-value 0 --max-value 60 --reducer max `
  --match-meta D:/assets/world3/toporeview/phase2_fusion_hd/meta.json

$chm = Get-ChildItem `
  -LiteralPath D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress `
  -Recurse -Filter chm_vegetation.tif
python D:/assets/world3/pipeline/export_opentopo_mosaic.py @($chm.FullName) `
  --output D:/assets/world3/toporeview/phase2_fusion_hd/layers/chm_vegetation_mosaic.png `
  --size 4096 --min-value 0 --max-value 35 --reducer max `
  --match-meta D:/assets/world3/toporeview/phase2_fusion_hd/meta.json
```

## Review Questions

Use this scene to answer:

- At what camera height does 4096 stop holding up?
- Does the 512-subdivision mesh visibly limit close-up quality?
- Does orthophoto need procedural detail blended under it for ground-level use?
- Which layers are useful as final visual layers, and which should only drive
  masks/material placement?

## Next

1. Capture fixed screenshots: overview, mid-altitude, close ground, steep slope,
   and vegetated patch.
2. If 4096 still fails too early, create an 8192 RGB-only stress export.
3. If texture holds but terrain geometry fails, test a 1024-subdivision scene.
4. Start baked ground texture crops from the 4096 orthophoto and masks.

