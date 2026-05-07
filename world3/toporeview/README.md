# OpenTopo Review Scenes

This folder contains standalone Godot review scenes for the OpenTopography
pilots.

## Scenes

```text
res://toporeview/phase1_mosaic_review.tscn
res://toporeview/phase2_fusion_review.tscn
res://toporeview/phase2_fusion_hd_review.tscn
res://toporeview/phase2_fusion_max_review.tscn
res://toporeview/phase2_fusion_ultra_rgb_review.tscn
```

Phase 1 shows the Grand Canyon `USGS10m` same-type mosaic. It starts on
`terrain_texture`, a synthetic review texture generated from elevation,
hillshade, slope, and roughness. It is useful for judging terrain form and
seams, but it is not real aerial imagery.

Phase 2 shows the Guadalupe Cypress fused stack with DTM terrain, RGB
orthophoto, NIR/false-color orthophoto, vegetation mask, canopy/CHM products,
point-cloud color mosaics, slope, roughness, and hillshade.

Phase 2 HD shows the same Guadalupe Cypress stack exported at 4096 for
close-range fidelity testing. It uses a 512-subdivision mesh by default.

Phase 2 MAX shows the same stack exported at 8192 with a 1024-subdivision mesh.
Phase 2 ULTRA RGB uses the 8192 heightmap with a separate 16K RGB orthophoto
stress layer.

## Controls

```text
RMB + mouse     look around
W / A / S / D   move
Space / Ctrl    move up / down
Shift           fast movement
L or Tab        cycle overlay layer
[ / ]           previous / next overlay layer
1               reset to isometric preset
2               reset to top-down preset
3               reset to low-angle preset
R               reset current camera preset
Z / X           decrease / increase vertical exaggeration
H               hide/show info text
```

The scenes use `toporeview/TopoReview.gd`, which loads a `heightmap.png`,
`meta.json`, and all PNG overlays in the configured `layers/` folder.

## Review Texture

Phase 1 texture command:

```powershell
python D:/assets/world3/pipeline/export_opentopo_review_texture.py `
  --layers-dir D:/assets/world3/toporeview/phase1_mosaic/layers `
  --output D:/assets/world3/toporeview/phase1_mosaic/layers/terrain_texture.png
```

## Data Copies

The review folder contains PNG copies of the current pilot review data so the
scenes can be opened directly from this folder. Source GeoTIFFs and full audit
outputs remain under `opentopo/`.

## HD Review

The 4096 Phase 2 HD scene exists here:

```text
res://toporeview/phase2_fusion_hd_review.tscn
```

Audit and rebuild commands:

```text
res://docs/OPENTOPO_PHASE2_HD_REVIEW.md
res://docs/OPENTOPO_PHASE2_MAX_REVIEW.md
```
