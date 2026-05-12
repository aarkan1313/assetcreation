# OpenTopo Tileable Texture Pilot Audit

Date: 2026-05-07

## Scope

Built the first reusable ground-texture pilot from the Phase 2 Guadalupe Cypress
fused stack.

This is not a new data pull. It uses the existing 8192 Phase 2 stack:

```text
D:/assets/world3/toporeview/phase2_fusion_max/
```

The pilot keeps three products separate:

- `source/`: repeated source crop, geography preserved inside the crop.
- `tileable_real/`: source-real crop with offset seam repair from the same real
  pixels; no procedural or AI color.
- `stylized_pixel/`: art derivative made from the tileable-real crop.

It also exports the full Phase 2 top-down view as a macro atlas because the full
map reads well as broad real-ground color.

## Tooling

New script:

```text
D:/assets/world3/pipeline/build_opentopo_tileable_texture.py
```

Command used:

```powershell
python D:/assets/world3/pipeline/build_opentopo_tileable_texture.py `
  --stack-dir D:/assets/world3/toporeview/phase2_fusion_max `
  --output-dir D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress `
  --crop-sizes-m 32,64 `
  --output-size 1024 `
  --macro-output-size 4096
```

The script:

1. Reads the fused stack and `meta.json`.
2. Selects representative crop centers using RGB, vegetation, slope, roughness,
   source-valid, and fill masks.
3. Exports six crop classes at `32 m` and `64 m`.
4. Writes `source/`, `tileable_real/`, and `stylized_pixel/` outputs.
5. Builds albedo, local height, normal, roughness, masks, `tile_2x2`, and
   provenance sidecars.
6. Exports a `4096` full-map macro atlas.
7. Builds a comparison sheet.

## Outputs

Root:

```text
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress/
```

Generated crop classes:

```text
dry_wash_032m
dry_wash_064m
scrub_sparse_032m
scrub_sparse_064m
scrub_dense_032m
scrub_dense_064m
rocky_slope_032m
rocky_slope_064m
bare_soil_032m
bare_soil_064m
bright_rock_032m
bright_rock_064m
full_map_macro_1600m
```

Generated summary images:

```text
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress/comparison_sheet.png
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress/full_map_macro_1600m/source/albedo.png
```

## Godot Review

New interactive scene:

```text
res://toporeview/tileable_texture_review.tscn
res://toporeview/tileable_hex_column_16x16.tscn
```

Capture wrapper:

```text
res://toporeview/capture_tileable_texture_review.tscn
```

Real viewport capture:

```text
D:/assets/world3/docs/captures/opentopo/godot_tileable_texture_review.png
```

The scene shows the `64 m` crops as repeated planes. Columns are:

```text
source repeated | plain tileable | hex anti-tile | stylized pixel
```

`tileable_hex_column_16x16.tscn` isolates the third column, `hex anti-tile`, at
`16x` repeat for interactive review. This is the current best practical view of
the real-ground tile workflow because it shows the actual shader path rather
than a static image sheet.

## Findings

- The full Phase 2 map works very well as a macro atlas. It should be treated as
  broad color/reference, not a seamless material.
- Small real crops are immediately useful as texture source, especially scrub,
  rocky slope, bright rock, and bare soil.
- Direct source crops often repeat visibly because real orthophotos contain
  memorable shrubs, rocks, and drainage shapes.
- The first plain repeated pass was not acceptable as a shipping material:
  visible square repetition remained even when the edge seam was softened.
- The plain tileable output now uses source-pixel offset patch quilting instead
  of blur-band repair. This improves border continuity without procedural or AI
  repainting, but it still does not solve repeated landmarks by itself.
- The practical render fix is the hex anti-tiling material path. It samples the
  same real tile through rotated/jittered hex cells and breaks the visible square
  period in Godot.
- The `16x` third-column review looks much better than plain square repeat, but
  some tile-to-tile lines remain. This is now documented as a limitation of
  using one real crop repeatedly, not as a failure of border seam repair.
- Several current crops also have noisy real-world patterns that read oddly at
  some scales. The issue is scale/frequency calibration: orthophoto speckle,
  shrubs, rocks, and drainage marks should not all become one repeated ground
  material layer.
- The stylized pixel derivative is useful as a proof of separation, not yet as a
  final art style.

## QA Notes

Texture QA on the `64 m` `tileable_real` outputs now says the edge seams mostly
pass numerically:

| Crop | Grade | Edge MSE | Junction | Period |
|---|---:|---:|---:|---:|
| bare_soil_064m | A | 0.0014 | 0.98 | 9.6 |
| bright_rock_064m | A | 0.0040 | 0.70 | 6.3 |
| dry_wash_064m | A | 0.0018 | 1.17 | 7.8 |
| rocky_slope_064m | A | 0.0025 | 1.16 | 13.6 |
| scrub_dense_064m | A | 0.0016 | 0.92 | 10.0 |
| scrub_sparse_064m | B | 0.0015 | 1.33 | 22.9 |

Important: seam QA is not enough. It can say the border wraps, while the human
eye still sees the crop repeat as a square. Shipping terrain should use either
hex/stochastic anti-tiling, a multi-tile set, or a macro/micro material stack.

## Current Limitations

- The pilot uses the 8192 review export, about `0.195 m/px`, not the native
  orthophoto ceiling of about `0.066 m/px`.
- `32 m` crops have only about `164` source pixels before upsampling. They are
  useful for workflow testing but too thin for final close-detail textures.
- `64 m` crops have about `328` source pixels before upsampling. They are better
  for this first pass.
- Some material classes are too visually busy to act as single repeated tiles.
  They need either cleaner source-native crops, variant atlases, or macro/meso/
  micro splitting.
- Height/normal outputs are local material maps derived from the review
  heightmap, not terrain-grade DEM tiles.
- Godot prints warnings when loading fresh PNGs directly as image files. This is
  intentional for review because it bypasses import-cache timing.

## Next Improvements

1. Add source-native orthophoto crop mode so `32 m` and `64 m` textures use the
   original COG resolution instead of the 8192 review export.
2. Add stronger QA metrics for repeated landmark visibility. Current seam QA
   passes borders but does not fully capture visible square repetition.
3. Build a multi-tile or atlas variant set per material class so the renderer can
   pick among several real crops instead of repeating one crop forever.
4. Add a macro/micro terrain material: full-map macro atlas at low frequency,
   tileable-real crop at high frequency.
5. Add close, mid, and overhead Godot capture presets for the texture review
   scene.
6. Add a focused unlike-tile Godot review: `16 x 16` cells, one material class,
   variant ID chosen per hex/stochastic cell, with all variants sourced from the
   same real orthophoto stack.
7. Add scale/frequency QA: close, mid, and far camera views for each material so
   noisy crops are rejected even when seam metrics pass.
8. Split materials into macro/meso/micro layers: broad real map color, unlike
   real crop variants, and cleaned close-detail normal/roughness.

## Variant Atlas Slice

Implemented first unlike-tile prototype for `dry_wash`:

```text
D:/assets/world3/pipeline/build_opentopo_texture_variant_atlas.py
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants/
D:/assets/world3/toporeview/tileable_variant_atlas_review.tscn
D:/assets/world3/docs/captures/opentopo/godot_tileable_variant_atlas_review.png
```

Command:

```powershell
python D:/assets/world3/pipeline/build_opentopo_texture_variant_atlas.py `
  --stack-dir D:/assets/world3/toporeview/phase2_fusion_max `
  --output-dir D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants `
  --material-class dry_wash `
  --crop-size-m 64 `
  --variants 12 `
  --output-size 1024 `
  --min-distance-m 90 `
  --color-normalize-strength 0.85 `
  --composite-size 4096 `
  --composite-cells 8 `
  --composite-sharpness 9
```

Result:

- `12` sibling `dry_wash` variants generated.
- Each variant has `source`, `tileable_real`, `tileable_real_norm`, and
  `stylized_pixel` outputs.
- Static `16 x 16` grid and real Godot capture were generated.
- Normalized variants reduce color checkerboarding, but hard per-cell switching
  still reads as block boundaries in the mixed grid.
- A `4096` `tileable_soft` composite now blends variants with periodic masks and
  wrap-safe offsets. This is the current best seamless texture product.
- Latest soft-composite edge MSE mean: `0.0000136595`.

Expanded batch:

| Class | Variants | Composite | Edge MSE Mean |
|---|---:|---:|---:|
| `bare_soil` | 12 | 4096 | `0.000011675` |
| `bright_rock` | 12 | 4096 | `0.000012058` |
| `dry_wash` | 12 | 4096 | `0.000013659` |
| `rocky_slope` | 12 | 4096 | `0.000017213` |
| `scrub_dense` | 12 | 4096 | `0.000018498` |
| `scrub_sparse` | 12 | 4096 | `0.000008059` |

Additional review assets:

```text
res://toporeview/tileable_soft_composite_gallery.tscn
res://toporeview/capture_tileable_soft_composite_gallery.tscn
D:/assets/world3/docs/captures/opentopo/godot_tileable_soft_composite_gallery.png
D:/assets/world3/docs/captures/opentopo/opentopo_soft_composite_2x2_material_sheet.png
```

Finished material pass:

```text
D:/assets/world3/pipeline/finish_opentopo_soft_materials.py
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_finished_materials_index.json
res://toporeview/tileable_finished_material_review.tscn
D:/assets/world3/docs/captures/opentopo/godot_tileable_finished_material_review.png
D:/assets/world3/docs/captures/opentopo/godot_tileable_finished_material_close.png
D:/assets/world3/docs/captures/opentopo/opentopo_finished_material_2x2_sheet.png
```

This pass writes `finished_material` siblings for all six classes. Each pack has
balanced albedo, neutral source-derived detail maps, a Godot
`terrain_hex_detail` material, and a manifest. Balanced edge MSE remains low:
`0.000011632` to `0.000023212`.

Verdict: unlike real variants are the right direction. Hard "one full tile per
cell" switching is a QA view, not the final material. The current practical
pipeline is the soft composite: a single tileable PBR set made from multiple
real variants. It fixes hard seams, but it does not magically remove all
recognizable source motifs. The finishing pass is the current practical answer:
attenuate low-frequency repetition, use neutral source-derived close detail, and
let the existing hex/detail shader handle runtime repetition.

## Verdict

The workflow is viable, but plain square tiling is not. The full map should
become a macro texture/reference layer, while selected crops become reusable
ground materials through unlike real variants and soft composites. The quality
jump came from source-native crops, real-pixel patch synthesis, and unlike real
tile variants, not procedural repainting. The remaining work is scale
calibration: some real pixels are too noisy or too specific to repeat directly
as a general-purpose ground layer.
