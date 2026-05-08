# OpenTopo Render Repair Workflow

Status: active workflow, source-first policy.

Date: 2026-05-07

## Goal

Fix no-data cliffs, broken terrain edges, and bad close-range rendering in a
reproducible way without pretending generated pixels are source data.

## Policy

Render repair is split into two separate tracks:

1. Geometry repair may fill missing DEM cells for a render-safe heightmap.
2. Albedo repair must remain source-first. Do not procedurally repaint real
   orthophoto areas to hide geometry repair.

If a pixel is generated, filled, synthesized, or extended, it must be tracked by
a mask or sidecar. Source rasters stay untouched.

## Current Pipeline

### 1. Build Render-Safe Heightmap

Tool:

```text
D:/assets/world3/pipeline/build_world.py
```

Current behavior:

- Reads source DEM/DTM and computes `source_valid_mask` before repair.
- Fills no-data cells for render use with `rasterio.fill.fillnodata`.
- Falls back to nearest valid source elevation if fill produces invalid values.
- Smooths repaired pixels only; original valid source elevations are restored
  after each smoothing pass.
- Writes a 16-bit `heightmap.png` plus metadata.

Generated repair layers:

```text
layers/source_valid_mask.png
layers/render_fill_mask.png
layers/render_fill_buffer.png
layers/cliff_mask.png
```

Important metadata:

```text
meta.json -> nodata_repair
meta.json -> render_masks
```

### 2. Build Source-First Render Albedo

Tool:

```text
D:/assets/world3/pipeline/build_opentopo_render_albedo.py
```

Current behavior:

- Preserves `orthophoto_rgb.png` as the visual source.
- Does not blend procedural color into repaired DEM areas.
- Optionally repairs explicit color gaps by extending nearby real orthophoto
  pixels.
- Writes sidecar policy fields so downstream users can tell whether color was
  modified.

Current sidecar policy:

```json
{
  "method": "source_orthophoto_first",
  "policy": {
    "geometry_repair_affects_albedo": false,
    "procedural_color_used": false,
    "source_texture_preserved": true
  }
}
```

### 3. Review In Godot

Current Phase 2 scenes start on:

```text
render_albedo
```

Layer order includes the repair QA masks so the same scene can inspect source
validity and repaired pixels:

```text
render_albedo
orthophoto_rgb
...
cliff_mask
source_valid_mask
render_fill_mask
render_fill_buffer
```

## What This Fixes

- Prevents no-data pixels from becoming artificial low-elevation pits.
- Prevents meshes from stretching down into dark vertical curtains.
- Preserves real orthophoto color where the orthophoto exists.
- Makes repair areas auditable.

## What This Does Not Fix Yet

Top-down orthophoto still cannot describe vertical or near-vertical side faces.
If a true cliff is viewed from the side, the texture will still smear because
the source imagery is nadir/top-down.

Do not solve that by painting fake procedural cliffs over real imagery.

## Better Long-Term Fix

The correct long-term cliff solution is data-driven:

1. Build chunked terrain so local mesh density can match source resolution.
2. Use DSM/LAZ point clouds for surface geometry where available.
3. Use RGB/NIR point-cloud color or another real imagery source for steep
   surfaces.
4. Project real source color into a terrain atlas or per-vertex/splat layer.
5. Use masks to mark where no real side-facing color exists.

If real side-facing data does not exist, the engine can still use a stylized or
fantasy material, but it must be clearly marked as an art material, not a
photoreal source repair.

## Current Phase 2 Numbers

For the Guadalupe Cypress 1.6 km review crop:

```text
source_invalid_pixels: 152,818 of 2,560,000 source DTM cells
source_invalid_fraction: about 6.0%
render_albedo gap_pixels: 0 for current orthophoto exports
```

This means the visible edge problem came from DEM no-data, not missing
orthophoto color. The heightmap should be repaired; the orthophoto should be
preserved.

## Rebuild Commands

Phase 2 MAX heightmap and masks:

```powershell
python D:/assets/world3/pipeline/build_world.py `
  D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/DTM_RGB_2016.tif `
  D:/assets/world3/toporeview/phase2_fusion_max `
  --size 8192 --material forest_floor `
  --bbox 370200 3218600 371800 3220200
```

Phase 2 MAX source-first albedo:

```powershell
python D:/assets/world3/pipeline/build_opentopo_render_albedo.py `
  --layers-dir D:/assets/world3/toporeview/phase2_fusion_max/layers `
  --output D:/assets/world3/toporeview/phase2_fusion_max/layers/render_albedo.png
```

Manifest:

```powershell
python D:/assets/world3/pipeline/build_opentopo_stack_manifest.py `
  --stack-dir D:/assets/world3/toporeview/phase2_fusion_max `
  --name guadalupe_cypress_phase2_max_review `
  --site Guadalupe_Cypress `
  --description "8192 Phase 2 max fused review stack with render-safe geometry and source-first albedo"
```

## Tiling Direction

The same source-first policy applies if we turn top-down terrain into ground
texture tiles:

- Use real orthophoto/height/slope as source.
- Make tileable crops by overlap/crossfade or real-pixel edge extension.
- Track any fantasy, pixelation, stylization, or AI/generated pass as an art
  derivative separate from source data.

The concrete workflow lives in
`D:/assets/world3/docs/OPENTOPO_TILEABLE_REAL_TEXTURE_WORKFLOW.md`.
