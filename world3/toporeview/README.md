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
res://toporeview/phase3_smokies_4call_review.tscn
res://toporeview/tileable_texture_review.tscn
res://toporeview/tileable_hex_column_16x16.tscn
res://toporeview/tileable_variant_atlas_review.tscn
res://toporeview/tileable_soft_composite_gallery.tscn
```

Phase 1 shows the Grand Canyon `USGS10m` same-type mosaic. It starts on
`terrain_texture`, a synthetic review texture generated from elevation,
hillshade, slope, and roughness. It is useful for judging terrain form and
seams, but it is not real aerial imagery.

Phase 2 shows the Guadalupe Cypress fused stack with DTM terrain, RGB
orthophoto, NIR/false-color orthophoto, vegetation mask, canopy/CHM products,
point-cloud color mosaics, slope, roughness, and hillshade.
The Phase 2 scenes start on `render_albedo`, a source-first real orthophoto
layer. Geometry repair masks are available as QA overlays.

Phase 2 HD shows the same Guadalupe Cypress stack exported at 4096 for
close-range fidelity testing. It uses a 512-subdivision mesh by default.

Phase 2 MAX shows the same stack exported at 8192 with a 1024-subdivision mesh.
Phase 2 ULTRA RGB uses the 8192 heightmap with a separate 16K RGB orthophoto
stress layer.

Phase 3 shows the Smokies `USGS1m` 4-call mosaic: 29.005 km x 29.835 km at
1 m source resolution, exported as an 8192 Godot heightmap with diagnostic
layers. It starts on `terrain_texture`, a procedural Appalachian review texture,
not real aerial imagery.

The tileable texture review shows Guadalupe Cypress `64 m` real-ground crops as
repeated planes. Columns are source repeated, plain tileable, hex anti-tile, and
a stylized pixel derivative. Plain repeat is intentionally harsh; the hex column
tests the anti-square-grid renderer. The full-map macro atlas is exported
separately and is not forced seamless.

`tileable_hex_column_16x16.tscn` shows only the third column, `hex anti-tile`, at
`16x` repeat. Use it for the earlier single-crop material review. The result is
good enough to continue, but remaining faint cell lines should be treated as the
motivation for the current soft-composite path: unlike real tile variants per
material class.

`tileable_variant_atlas_review.tscn` compares one repeated variant against a
mixed `16 x 16` grid of unlike `dry_wash` variants, plus a soft seamless
composite on the right. It uses `tileable_real_norm` for the hard-mixed variants
and `tileable_soft` for the final panel. The hard grid is a QA/failure view; the
soft composite is the current usable tileable product.

`tileable_soft_composite_gallery.tscn` shows the current six `4096`
source-real soft composites at `2x` repeat: `bare_soil`, `bright_rock`,
`dry_wash`, `rocky_slope`, `scrub_dense`, and `scrub_sparse`. Use it to compare
the material classes after the hard tile-to-tile seams have been removed.

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

## Real Godot Captures

Capture wrappers:

```text
res://toporeview/capture_phase1_mosaic.tscn
res://toporeview/capture_phase2_fusion.tscn
res://toporeview/capture_phase2_fusion_hd.tscn
res://toporeview/capture_phase2_fusion_max.tscn
res://toporeview/capture_phase3_smokies_4call.tscn
res://toporeview/capture_phase2_close_baseline.tscn
res://toporeview/capture_phase2_close_hd.tscn
res://toporeview/capture_phase2_close_max.tscn
res://toporeview/capture_tileable_texture_review.tscn
res://toporeview/capture_tileable_hex_column_16x16.tscn
res://toporeview/capture_tileable_variant_atlas_review.tscn
res://toporeview/capture_tileable_soft_composite_gallery.tscn
```

Run them through normal Godot with the capture scene as the trailing argument:

```powershell
$args = @("--path", "D:/assets/world3", "res://toporeview/capture_phase2_fusion_max.tscn")
$p = Start-Process -FilePath "C:/Godot/Godot_v4.5-stable_win64.exe" -ArgumentList $args -Wait -PassThru
"EXIT=$($p.ExitCode)"
```

Current real viewport outputs:

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
D:/assets/world3/docs/captures/opentopo/godot_tileable_variant_atlas_review.png
D:/assets/world3/docs/captures/opentopo/godot_tileable_soft_composite_gallery.png
D:/assets/world3/docs/captures/opentopo/opentopo_soft_composite_2x2_material_sheet.png
```

The older waited `--headless --scene ... --quit-after ...` path can hit a local
Windows access violation across multiple scenes. Do not use it as scene
validation; use real capture scenes or interactive Godot review.

`TopoReviewCapture.gd` is for deterministic comparison shots. It sets the same
camera pose across review scenes before saving the viewport.

Render repair policy is documented in:

```text
res://docs/OPENTOPO_RENDER_REPAIR_WORKFLOW.md
```

## Review Texture

Phase 1 texture command:

```powershell
python D:/assets/world3/pipeline/export_opentopo_review_texture.py `
  --layers-dir D:/assets/world3/toporeview/phase1_mosaic/layers `
  --output D:/assets/world3/toporeview/phase1_mosaic/layers/terrain_texture.png
```

Phase 3 texture/layer command:

```powershell
python D:/assets/world3/pipeline/export_heightmap_review_layers.py `
  --heightmap D:/assets/world3/toporeview/phase3_smokies_4call/heightmap.png `
  --meta D:/assets/world3/toporeview/phase3_smokies_4call/meta.json `
  --output-dir D:/assets/world3/toporeview/phase3_smokies_4call/layers `
  --terrain-style appalachian
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
res://docs/OPENTOPO_PHASE3_SMOKIES_4CALL_AUDIT.md
```
