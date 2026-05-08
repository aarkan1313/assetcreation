# OpenTopo Tileable Real Texture Workflow

This workflow turns real OpenTopography layers into reusable ground textures.
It is separate from real-place scene building.

The rule is simple:

- A **real-place stack** preserves geography and should be chunked, not tiled.
- A **tileable real texture** uses real pixels as source material but is no
  longer an exact map after crop repair, blending, or wrap correction.
- A **stylized/fantasy texture** is an art derivative. It can be pixelated,
  filtered, palette-shifted, or generated, but it must not be labeled as source
  repair.

## Why This Is Worth Doing

The Phase 2 Guadalupe Cypress orthophoto looks excellent from above because it
is literally real ground. That makes it useful in two ways:

1. As a large real-place map/scene when paired with the DTM, canopy, NIR, and
   point-cloud layers.
2. As source material for reusable ground textures such as dry wash, scrub,
   rocky slope, exposed soil, chaparral floor, and bright rock.

Those are different products. Tiling makes a material reusable, but it destroys
exact geography.

## Product Types

### 1. Source Crop

Purpose: preserve source pixels and provenance.

Use when:

- Reviewing the real location.
- Comparing OpenTopo layers.
- Building a real-place terrain scene.
- Feeding a later tileable/stylized pass.

Expected files:

```text
source/albedo.png
source/height.png
source/slope.png
source/roughness.png
source/vegetation_mask.png
source/meta.json
```

Do not force this to tile. If it needs to cover a large area, chunk it.

### 2. Tileable Real Texture

Purpose: create a seamless reusable game texture from real pixels.

Allowed operations:

- Crop selection.
- Downsample/resample.
- Wrap-offset seam repair.
- Real-pixel clone/patch repair.
- Crossfade between overlapping real crops of the same material.
- Derive normals/roughness/height from DEM, hillshade, slope, or image detail.

Disallowed as source repair:

- Procedural repainting over real color.
- AI-generated replacement color.
- Hand-painted material fills presented as measured data.

Expected files:

```text
tileable_real/albedo.png
tileable_real/normal.png
tileable_real/height.png
tileable_real/roughness.png
tileable_real/masks.png
tileable_real/tile_2x2.png
tileable_real/meta.json
```

### 3. Stylized Or Fantasy Texture

Purpose: use the real crop as inspiration for art.

Allowed operations:

- Palette reduction.
- Pixelation.
- Posterization.
- Painterly filtering.
- Fantasy color grading.
- Shader-driven material reinterpretation.
- AI/img2img/upscale/downscale experiments, if explicitly marked.

Expected files:

```text
stylized_<method>/albedo.png
stylized_<method>/normal.png
stylized_<method>/height.png
stylized_<method>/roughness.png
stylized_<method>/tile_2x2.png
stylized_<method>/meta.json
```

The sidecar must say this is an art derivative, not a measured map.

## Inputs

For Phase 2 Guadalupe Cypress, the strongest input set is:

```text
D:/assets/world3/toporeview/phase2_fusion_max/layers/render_albedo.png
D:/assets/world3/toporeview/phase2_fusion_max/layers/orthophoto_rgb.png
D:/assets/world3/toporeview/phase2_fusion_max/layers/orthophoto_nir_false.png
D:/assets/world3/toporeview/phase2_fusion_max/layers/vegetation_ndvi_like.png
D:/assets/world3/toporeview/phase2_fusion_max/layers/canopy_height_mosaic.png
D:/assets/world3/toporeview/phase2_fusion_max/layers/chm_vegetation_mosaic.png
D:/assets/world3/toporeview/phase2_fusion_max/layers/hillshade.png
D:/assets/world3/toporeview/phase2_fusion_max/layers/slope_deg.png
D:/assets/world3/toporeview/phase2_fusion_max/layers/roughness.png
D:/assets/world3/toporeview/phase2_fusion_max/heightmap.png
D:/assets/world3/toporeview/phase2_fusion_max/meta.json
```

Use `render_albedo.png` for render-facing color because it follows the
source-first albedo policy. Keep `orthophoto_rgb.png` available as a source
comparison layer.

## Crop Selection

Good tile crops are visually representative but not too unique.

Prefer:

- Evenly lit ground.
- Repeated local structure.
- No large one-off landmarks.
- No hard map edges.
- Minimal cast shadows unless the desired material includes them.
- One dominant material per crop.

Avoid:

- Roads, buildings, vehicles, labels, survey artifacts.
- Large diagonal washes that will obviously repeat.
- Huge isolated bushes unless the crop is meant to become a vegetation patch.
- Cliffs or steep side faces if only top-down orthophoto is available.

Suggested Phase 2 crop classes:

- `dry_wash`
- `scrub_sparse`
- `scrub_dense`
- `rocky_slope`
- `bare_soil`
- `bright_rock`
- `chaparral_floor`

Suggested ground sizes:

| Crop Size | Use |
|---:|---|
| 16 m | close detail, small stones, soil texture |
| 32 m | walking-scale ground material |
| 64 m | broad ground texture with vegetation speckle |
| 128 m | macro albedo, terrain color variation |

## Making A Texture Tileable

Use the least destructive method that passes QA.

### Method A: Direct Crop

Export a square crop and tile it `2 x 2`.

Use when:

- The source is naturally uniform.
- Edge mismatch is small.
- Repetition is not visible at expected camera range.

This is the baseline, not the final assumption.

### Method B: Offset Seam Repair

1. Roll the crop by half its width and height so the wrap seams meet in the
   center.
2. Repair the central cross using only real pixels from the same crop or sibling
   crops of the same material.
3. Roll the crop back.
4. Generate `tile_2x2.png`.

This keeps the texture source-real while removing the obvious border seam.

### Method C: Overlap Crossfade

Use two or more overlapping crops of the same material. Blend them with broad,
soft masks so no single landmark repeats too obviously.

This is useful for orthophoto crops because real terrain often has memorable
rocks, bushes, or drainages that become obvious when repeated.

### Method D: Macro/Micro Split

Make two products:

- A larger real macro albedo from a broad crop.
- A smaller tileable detail texture from a more uniform crop.

In the shader, use the macro texture at low frequency and the tileable detail
texture at high frequency.

This is probably the best game-rendering path: the broad color stays real, but
the close-range detail repeats less obviously.

### Method E: Anti-Tiling Shader Or Multi-Tile Set

A single real orthophoto crop can pass seam QA and still look bad when repeated:
unique shrubs, rocks, washes, and shadows reveal the square period.

For shipping terrain, prefer one of these:

- Hex/stochastic sampling in the shader using the tileable-real crop.
- A multi-tile/Wang-style set of sibling real crops from the same material class.
- Macro/micro blend: full-map macro atlas at low frequency, anti-tiled material
  detail at high frequency.

The current Godot review scene includes a `hex anti-tile` column because this is
the first method that visibly breaks the square grid.

Current review workflow:

1. Generate source, tileable-real, and stylized texture products.
2. Open `res://toporeview/tileable_texture_review.tscn` to compare all columns.
3. Open `res://toporeview/tileable_hex_column_16x16.tscn` to inspect only the
   `hex anti-tile` column at `16x` repeat.
4. Treat the hex column as the practical render preview. Treat plain repeat as
   a harsh QA view, not the desired shipping material.

Visual result as of 2026-05-07: the hex column looks much better than plain
repeat, but some tile-to-tile lines and repeated motifs are still visible. That
is expected because the shader is still reusing one source tile per material.
The next quality jump requires unlike real tiles, not heavier repair of one
tile.

Important scale note: the current crops also contain noisy real-world patterns
that can read strangely depending on camera distance. A crop can be seamless and
still look unnatural if shrubs, rocks, drainage marks, compression noise, or
orthophoto speckle are repeated at the wrong size. This is a scale-calibration
problem, not just a seam problem.

For production materials, split the source into frequency bands:

- `macro`: broad real color from the full map or large crops, used at low
  frequency.
- `meso`: unlike real tile variants, selected by the shader per cell.
- `micro`: close-detail normal/roughness/noise cleaned for walking-scale view.

Do not let one orthophoto crop carry all three jobs. That is what creates the
"real but weird" read.

### Method F: Unlike Real Multi-Tile Atlas

Purpose: keep the material source-real while avoiding the "same square forever"
look.

Build several sibling crops for each material class:

```text
dry_wash/
  variant_00/
  variant_01/
  variant_02/
  ...
scrub_sparse/
  variant_00/
  variant_01/
  ...
```

Each variant should be real-pixel tileable by itself, color-normalized to the
class, and paired with matching height/normal/roughness. The renderer should
choose a different variant per stochastic/hex cell or per terrain patch.

Recommended first target:

- `8` variants per material class.
- `64 m` crop size first, then `32 m` for close detail.
- `1024` or `2048` output per variant depending source-native crop quality.
- One `Texture2DArray` or atlas per map type: albedo, normal, roughness,
  height.
- Random variant selection by cell ID in the hex shader.
- Soft color/value normalization so adjacent variants belong to the same
  material family without looking cloned.

QA gates for the atlas:

- Every individual variant passes edge seam checks.
- A `16 x 16` Godot view does not show a square period.
- Adjacent unlike variants do not create obvious color blocks.
- Close view still reads as real ground, not blurred repair.
- Mid and far view do not show a noisy repeated pattern field.
- The chosen ground scale is plausible: shrubs stay shrubs, pebbles stay
  pebbles, and orthophoto speckle does not become fake terrain detail.
- Metadata records source crop bounds for every variant.

This is the preferred long-term path for real orthophoto ground materials. It
does not procedurally match photorealism; it uses more real ground.

First implemented slice:

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

Generated review assets:

```text
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants/manifest.json
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants/dry_wash_064m_variant_sheet.png
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants/dry_wash_064m_variant_grid_16x16.png
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants/dry_wash_064m_soft_composite/tileable_soft/albedo.png
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants/dry_wash_064m_soft_composite/tileable_soft/normal.png
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants/dry_wash_064m_soft_composite/tileable_soft/roughness.png
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants/dry_wash_064m_soft_composite/tileable_soft/height.png
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants/dry_wash_064m_soft_composite/tileable_soft/tile_2x2.png
res://toporeview/tileable_variant_atlas_review.tscn
res://toporeview/capture_tileable_variant_atlas_review.tscn
D:/assets/world3/docs/captures/opentopo/godot_tileable_variant_atlas_review.png
```

Finding: unlike variants help the "same square forever" problem, but naive
per-cell switching creates visible patch boundaries. RGB mean/std normalization
(`tileable_real_norm`) reduces the checkerboard read but does not fully solve
it. The current soft-composite step blends between unlike variants softly
instead of switching hard at cell borders.

Current solid path: the builder also writes a `4096` `tileable_soft` composite.
It blends normalized real variants with periodic soft masks and wrap-safe
offsets, then derives normal from the blended height. This produces a single
tileable PBR set, not a hard grid.

Expanded six-class batch command pattern:

```powershell
$classes = @("bare_soil", "bright_rock", "dry_wash", "rocky_slope", "scrub_dense", "scrub_sparse")
foreach ($class in $classes) {
  python D:/assets/world3/pipeline/build_opentopo_texture_variant_atlas.py `
    --stack-dir D:/assets/world3/toporeview/phase2_fusion_max `
    --output-dir "D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_variants_$class" `
    --material-class $class `
    --crop-size-m 64 `
    --variants 12 `
    --output-size 1024 `
    --min-distance-m 90 `
    --color-normalize-strength 0.85 `
    --composite-size 4096 `
    --composite-cells 8 `
    --composite-sharpness 9
}
```

Latest six-class soft-composite metrics:

| Class | Variants | Composite | Edge MSE Mean | Output Root |
|---|---:|---:|---:|---|
| `bare_soil` | 12 | 4096 | `0.000011675` | `opentopo/processed/textures/Guadalupe_Cypress_variants_bare_soil/` |
| `bright_rock` | 12 | 4096 | `0.000012058` | `opentopo/processed/textures/Guadalupe_Cypress_variants_bright_rock/` |
| `dry_wash` | 12 | 4096 | `0.000013659` | `opentopo/processed/textures/Guadalupe_Cypress_variants_dry_wash/` |
| `rocky_slope` | 12 | 4096 | `0.000017213` | `opentopo/processed/textures/Guadalupe_Cypress_variants_rocky_slope/` |
| `scrub_dense` | 12 | 4096 | `0.000018498` | `opentopo/processed/textures/Guadalupe_Cypress_variants_scrub_dense/` |
| `scrub_sparse` | 12 | 4096 | `0.000008059` | `opentopo/processed/textures/Guadalupe_Cypress_variants_scrub_sparse/` |

Representative dry-wash edge metrics:

```json
{
  "edge_mse_left_right": 0.0000204846,
  "edge_mse_top_bottom": 0.0000068343,
  "edge_mse_mean": 0.0000136595
}
```

Review assets:

```text
res://toporeview/tileable_variant_atlas_review.tscn
res://toporeview/tileable_soft_composite_gallery.tscn
D:/assets/world3/docs/captures/opentopo/godot_tileable_variant_atlas_review.png
D:/assets/world3/docs/captures/opentopo/godot_tileable_soft_composite_gallery.png
D:/assets/world3/docs/captures/opentopo/opentopo_soft_composite_2x2_material_sheet.png
```

Use the soft composite as the first practical texture product. Keep the hard
mixed grid as a QA/failure view. Remaining issue: some source-real patterns
still repeat as recognizable motifs at the wrong scale, so production use still
needs macro/meso/micro separation and source selection by intended camera
distance.

## Height And Normal Map Tiling

Height is more sensitive than albedo because edge discontinuity creates visible
lighting seams.

Preferred order:

1. Crop source height/slope/roughness aligned to the albedo crop.
2. Remove large-scale grade if this is a reusable material, not a real-place
   chunk.
3. Apply the same wrap seam repair to height.
4. Derive normals from the repaired height.
5. Validate albedo, height, normal, and roughness together in `2 x 2`.

For a real-place chunk, do not remove grade or force tileability. Preserve the
DEM and solve continuity with chunk seams.

## Downscale And Pixelation Experiments

These are valid, but they are art derivatives.

Recommended order for pixelated/fantasy outputs:

1. Choose a source crop.
2. Make the crop tileable at source or working resolution.
3. Downscale or pixelate.
4. Re-check tileability at the final resolution.
5. Generate normals/roughness from the final or intermediate height depending
   on the desired look.

Useful techniques:

- Nearest-neighbor pixelation.
- Palette quantization.
- Ordered dithering.
- Posterized slope shading.
- Biome palette remap.
- NDVI-driven vegetation color masks.
- Height/slope-driven rock and wash masks.

Do not overwrite the source-real product with a stylized product. Store it as a
separate sibling output.

## QA Gates

Every tileable output should have:

- `tile_2x2.png` for human review.
- Edge-continuity score for albedo and height.
- Center-seam visibility check after tiling.
- Repetition review at expected camera heights.
- Scale/frequency review at close, mid, and far camera distances.
- Godot plane/material preview.
- `16x` focused hex-column review for the current material class.
- Multi-variant atlas review once unlike-tile support exists.
- Color-normalized atlas review (`tileable_real_norm`) before judging variant
  mixing.
- Soft composite `tile_2x2` review before calling the product seamless.
- Sidecar metadata listing source crop, ground size, operations, and whether it
  is source-real or stylized.

Minimum sidecar fields:

```json
{
  "source_policy": "source_crop | tileable_real | stylized_derivative",
  "source_stack": "phase2_fusion_max",
  "crop_class": "dry_wash",
  "ground_size_m": 32,
  "output_size_px": 2048,
  "meters_per_pixel": 0.015625,
  "operations": ["offset_seam_repair", "real_pixel_patch"],
  "procedural_color_used": false,
  "ai_generated_color_used": false,
  "geography_preserved": false
}
```

## Implemented Tooling

The first script is:

```text
D:/assets/world3/pipeline/build_opentopo_tileable_texture.py
```

Responsibilities:

1. Read a fused stack manifest.
2. Export named crops at real ground sizes.
3. Produce `source/`, `tileable_real/`, and optional `stylized_*` outputs.
4. Run tileability QA.
5. Write provenance sidecars.
6. Build a comparison sheet.

Suggested output layout:

```text
D:/assets/world3/opentopo/processed/textures/
  Guadalupe_Cypress/
    dry_wash_032m/
      source/
      tileable_real/
      stylized_pixel/
      manifest.json
    rocky_slope_032m/
      source/
      tileable_real/
      manifest.json
```

The current unlike-variant script is:

```text
D:/assets/world3/pipeline/build_opentopo_texture_variant_atlas.py
```

Responsibilities:

1. Select several sibling real crops for one material class.
2. Reject crops too close to the source image edge or too near an existing
   selected variant.
3. Repair each crop independently with the single-crop pipeline.
4. Build hard-mixed variant QA images.
5. Build one periodic soft-composite `tileable_soft` PBR product.
6. Write a manifest with source crop positions, output paths, and edge metrics.

Use `make_image_comparison_sheet.py` to build labeled material sheets from the
generated `tile_2x2.png` files.

## First Pilot

Status: first Guadalupe Cypress pilot complete. Detailed audit:

```text
D:/assets/world3/docs/OPENTOPO_TILEABLE_TEXTURE_PILOT_AUDIT.md
```

Pilot command:

```powershell
python D:/assets/world3/pipeline/build_opentopo_tileable_texture.py `
  --stack-dir D:/assets/world3/toporeview/phase2_fusion_max `
  --output-dir D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress `
  --crop-sizes-m 32,64 `
  --output-size 1024 `
  --macro-output-size 4096
```

The pilot uses Guadalupe Cypress because we already have a fused stack and real
orthophoto. It:

1. Picks six crop classes: dry wash, sparse scrub, dense scrub, rocky slope,
   bare soil, bright rock.
2. Exports `32 m` and `64 m` versions.
3. Produces direct source crops.
4. Applies offset seam repair to all crops.
5. Generates albedo/height/normal/roughness.
6. Builds a Godot material comparison scene with source repeat, plain tileable,
   hex anti-tile, and stylized columns:
   `res://toporeview/tileable_texture_review.tscn`.
7. Adds a focused 16x third-column review scene:
   `res://toporeview/tileable_hex_column_16x16.tscn`.
8. Exports the full Phase 2 map as a `4096` macro atlas, not forced seamless.

Success means the texture looks good in a repeated/anti-tiled plane render, not
just as a single top-down crop. Plain square repeat is an intermediate QA view,
not the target renderer. Current verdict: single-tile hex anti-tiling is useful,
but it is now superseded by the unlike-variant `tileable_soft` composite for
seam-free source-real material candidates.
