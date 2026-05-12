# OpenTopo BC Coast DTM/DSM No-Color Stack Audit

Date: 2026-05-07

## Goal

Create a new map implementation from an OpenTopo data combo that does not
provide real color. This tests whether paired DTM/DSM rasters can produce a
useful terrain, surface-height, and material-mask stack without orthophoto
imagery.

## Source

```text
D:/assets/world3/opentopo/raw/cog/tcf_bc_coast_canada/CA_MRDEM_DTM_m123.1398_p49.9096_m122.8602_p50.0904.tif
D:/assets/world3/opentopo/raw/cog/tcf_bc_coast_canada/CA_MRDEM_DSM_m123.1398_p49.9096_m122.8602_p50.0904.tif
```

Source grid:

```text
CRS: EPSG:3979
Cell size: 30 m
Shape: 887 x 888
Footprint: 26.61 x 26.64 km
```

## Build Command

```powershell
python D:/assets/world3/pipeline/build_opentopo_dtm_dsm_stack.py `
  --dtm D:/assets/world3/opentopo/raw/cog/tcf_bc_coast_canada/CA_MRDEM_DTM_m123.1398_p49.9096_m122.8602_p50.0904.tif `
  --dsm D:/assets/world3/opentopo/raw/cog/tcf_bc_coast_canada/CA_MRDEM_DSM_m123.1398_p49.9096_m122.8602_p50.0904.tif `
  --output-dir D:/assets/world3/opentopo/processed/heightmaps/tcf_bc_coast_dtm_dsm_stack `
  --name "BC Coast DTM DSM No-Color Stack" `
  --size 4096 --surface-max-m 45
```

The Godot review package was copied to:

```text
D:/assets/world3/toporeview/bc_coast_dtm_dsm/
```

## Outputs

```text
D:/assets/world3/opentopo/processed/heightmaps/tcf_bc_coast_dtm_dsm_stack/heightmap.png
D:/assets/world3/opentopo/processed/heightmaps/tcf_bc_coast_dtm_dsm_stack/meta.json
D:/assets/world3/opentopo/processed/heightmaps/tcf_bc_coast_dtm_dsm_stack/stack_manifest.json
D:/assets/world3/opentopo/processed/heightmaps/tcf_bc_coast_dtm_dsm_stack/layers/
```

Layer set:

```text
terrain_texture.png
dtm_gray.png
dsm_gray.png
surface_height.png
forest_surface_mask.png
rock_slope_mask.png
wetness_valley_mask.png
material_mask_rgba.png
hillshade.png
elevation_gray.png
slope_deg.png
roughness.png
source_valid_mask.png
surface_valid_mask.png
```

Godot scene:

```text
res://toporeview/bc_coast_dtm_dsm_review.tscn
res://toporeview/capture_bc_coast_dtm_dsm.tscn
```

Captures:

```text
D:/assets/world3/docs/captures/opentopo/godot_bc_coast_dtm_dsm.png
D:/assets/world3/docs/captures/opentopo/opentopo_bc_coast_dtm_dsm_layer_sheet.png
```

## Validation Stats

From `stack_manifest.json`:

```text
DTM elevation:       297.445 m to 2640.762 m
DSM elevation:       308.681 m to 2657.512 m
Surface height:      0.000 m to 45.336 m
Surface p95:         20.523 m
Slope max:           68.887 degrees
Slope p95:           39.432 degrees
Valid DTM cells:     787,656
```

Godot capture succeeded with normal trailing-scene launch and wrote a
`1920 x 1080` real viewport screenshot.

## Findings

- This is a useful no-color stack. The terrain reads as real coastal mountain
  landform, and the synthetic texture is good enough for regional review.
- `DSM - DTM` gives a strong surface/canopy signal. It is not individual-tree
  detail, but it is good for regional forest density, obstruction, and material
  masking.
- The source is only 30 m, so close-up terrain will not compete with the 1 m
  Guadalupe or Smokies data. A 4096 export improves review smoothness and mask
  quality but does not create new source detail.
- This is a good candidate pattern for no-orthophoto megastacks: keep DTM as
  ground, DSM-DTM as surface/vegetation, then derive material masks and a
  procedural/fantasy texture.

## Compression Note

This stack currently exports review-ready PNGs. For a larger megastack, keep
the aligned master layers as lossless float32 tiled GeoTIFF or chunked Zarr
first, validate them, then export compressed Godot packs:

- 16-bit height PNG tiles.
- RGBA packed masks.
- compressed color/procedural albedo.
- lower-resolution overview maps for far views.

Do not make the review PNGs the only high-quality copy when the source stack
gets large.
