# OpenTopo Phase 2 Max Review

Date: 2026-05-07

Status: max single-tile pass generated and data-validated.

## Purpose

This pass pushes the Guadalupe Cypress Phase 2 fused stack as far as practical
before chunking/streaming becomes the correct architecture.

It contains two levels:

1. A full 8192 aligned fused stack with all ten Phase 2 layers.
2. A separate 16K RGB-only orthophoto stress layer.

The 16K layer is intentionally stored outside `layers/` so it does not break the
8192 stack manifest. It is a single-texture stress test, not the normal stack
format.

## Outputs

Full 8192 max scene:

```text
D:/assets/world3/toporeview/phase2_fusion_max_review.tscn
```

8192 stack folder:

```text
D:/assets/world3/toporeview/phase2_fusion_max/
```

16K RGB stress scene:

```text
D:/assets/world3/toporeview/phase2_fusion_ultra_rgb_review.tscn
```

16K RGB layer:

```text
D:/assets/world3/toporeview/phase2_fusion_max/ultra_layers/orthophoto_rgb_16k.png
```

## 8192 Full Stack Specs

```text
AOI:             1.6 km x 1.6 km
Heightmap:       8192 x 8192
Layer textures:  8192 x 8192
Texture scale:   about 0.1953 m/px
Scene mesh:      1024 subdivisions
Mesh spacing:    about 1.5625 m/vertex
CRS:             EPSG:32611
Elevation range: 931.06 m to 1201.28 m
Compressed size: about 520 MB including heightmap/layers/sidecars
```

Validated 8192 layers:

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

Validation:

```text
stack_manifest.json status: pass
layers: 10
heightmap size: 8192 x 8192
Real Godot capture: pass
Real close-up capture: pass
Render-safe geometry repair: pass
Source-first render_albedo: pass
```

## 16K RGB Stress Specs

```text
RGB texture:     16384 x 16384
Texture scale:   about 0.0977 m/px
Compressed file: about 252 MB
Layer role:      RGB orthophoto stress/reference only
Godot scene:     phase2_fusion_ultra_rgb_review.tscn
Capture status:  not rerun in this pass
```

Source-data ceiling:

```text
RGB orthophoto source: about 0.06627 m/px
NIR orthophoto source: about 0.06486 m/px
DTM source:            1.0 m cell size
```

Interpretation:

- 8192 is still not source-native color, but it is a serious single-tile
  close-range test.
- 16K gets close to source-native RGB, but it is too large to treat as a normal
  multi-layer scene format.
- Full source-native over the whole 1.6 km AOI would be roughly 24K pixels wide.
  That belongs in a chunked/streamed workflow.

Real close-up result:

The 8192 texture is clearly sharper than the 1024 and 4096 captures, but it also
reveals mesh/normal artifacts at close range. The correct next step is not just
larger single-image exports; it is chunked terrain plus real DSM/LAZ/color
projection where available.

No-data/cliff repair policy:

```text
D:/assets/world3/docs/OPENTOPO_RENDER_REPAIR_WORKFLOW.md
```

`render_albedo.png` is now source-first. It preserves the real orthophoto and
does not procedurally repaint repaired DEM areas.

## Rebuild Commands

Build the 8192 heightmap:

```powershell
python D:/assets/world3/pipeline/build_world.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/DTM_RGB_2016.tif `
  D:/assets/world3/toporeview/phase2_fusion_max `
  --size 8192 --material forest_floor `
  --bbox 370200 3218600 371800 3220200
```

Export the 8192 RGB orthophoto:

```powershell
python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_rgb_orto_COF.tif `
  D:/assets/world3/toporeview/phase2_fusion_max/layers/orthophoto_rgb.png `
  --mode rgb --size 8192 `
  --match-meta D:/assets/world3/toporeview/phase2_fusion_max/meta.json
```

Export the 16K RGB stress layer:

```powershell
python D:/assets/world3/pipeline/export_opentopo_texture.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_rgb_orto_COF.tif `
  D:/assets/world3/toporeview/phase2_fusion_max/ultra_layers/orthophoto_rgb_16k.png `
  --mode rgb --size 16384 `
  --match-meta D:/assets/world3/toporeview/phase2_fusion_max/meta.json
```

Build/validate the 8192 manifest:

```powershell
python D:/assets/world3/pipeline/build_opentopo_stack_manifest.py `
  --stack-dir D:/assets/world3/toporeview/phase2_fusion_max `
  --name guadalupe_cypress_phase2_max_review `
  --site Guadalupe_Cypress `
  --description "8192 Phase 2 max single-tile review stack for upper-bound texture and zoom testing"
```

Godot capture note:

Real viewport capture was validated with normal Godot and the capture scene as
the trailing argument:

```text
res://toporeview/capture_phase2_fusion_max.tscn
res://toporeview/capture_phase2_close_max.tscn
D:/assets/world3/docs/captures/opentopo/godot_phase2_fusion_max.png
D:/assets/world3/docs/captures/opentopo/godot_phase2_close_max.png
D:/assets/world3/docs/captures/opentopo/godot_phase2_close_resolution_comparison.png
```

The older waited `--headless --scene ... --quit-after ...` path can hit a local
Windows access violation across multiple review scenes. Do not use that path as
scene validation.

## Review Questions

Use this pass to decide:

- Does 8192 solve close-up texture blur enough to proceed with real scenes?
- Does the 1024-subdivision mesh now become the limiting factor?
- Does 16K RGB materially beat 8192 in Godot, or is it overkill for the full
  AOI?
- Should the next real investment be chunked terrain, baked real-ground
  textures, or point-cloud/color projection for steep surfaces?

## Decision Boundary

If 8192/16K still fails at desired close range, do not keep increasing one
texture. Move to chunks:

- 256 m to 400 m chunks.
- 2048 or 4096 per chunk.
- Nearby chunks high-res; far chunks downsampled.
- Real orthophoto/reference layer plus source-derived detail maps close up.
- If stylized/fantasy materials are used, keep them separate from source-first
  repair outputs.
