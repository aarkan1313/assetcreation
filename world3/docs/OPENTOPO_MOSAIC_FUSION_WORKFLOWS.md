# OpenTopo Mosaic And Fusion Workflows

This document covers two related but different workflows:

1. Same-type mosaics: pull multiple tiles of the same product over one large
   area and stitch them into one seamless terrain package.
2. Cross-type fusion: align height, color, point-cloud, canopy, GEDI, and
   derived layers into one compatible data stack for Godot.

The rule for both workflows is the same: pick a canonical grid first, then make
every source conform to it. If the CRS, bounds, resolution, vertical datum, or
timestamp do not line up, the source is a candidate layer, not a trusted layer.

## Core Grid Contract

Every stitched or fused dataset should produce a `stack_manifest.json` with:

```json
{
  "name": "grand_canyon_pilot",
  "target_crs": "EPSG:26912",
  "target_bounds": {
    "left": 0,
    "bottom": 0,
    "right": 0,
    "top": 0
  },
  "target_cell_size_m": 1.0,
  "target_width": 0,
  "target_height": 0,
  "vertical_datum": "unknown",
  "base_height_layer": "dtm",
  "layers": []
}
```

Required grid choices:

- CRS: projected CRS in meters for local work, not lat/lon pixels.
- Bounds: one exact rectangle. All rasters are clipped to it.
- Cell size: one target resolution. Use 1 m for small high-res pilots, 10 m or
  30 m for large regions.
- Origin/alignment: all rasters must share the same transform, not just similar
  bounds.
- Vertical datum: record it even if unknown. Never silently mix ellipsoid,
  NAVD88, EGM96, or local datums as if they are identical.
- Timestamp: record capture dates. Vegetation and flood/coastal data can change
  quickly.

## Workflow A: Same-Type Multi-Tile Mosaic

Use this when one area is too large for a single OpenTopography job or one
download file.

Example target:

```text
Grand Canyon high-resolution terrain pilot
Product: USGS10m first, then USGS1m in smaller windows
Goal: one seamless DTM/DEM heightmap package
```

Steps:

1. Define the AOI and target grid.
2. Split the AOI into request windows below API/product limits.
3. Pull the same product for every window.
4. Reproject each tile to the target CRS if needed.
5. Warp each tile onto the exact target grid.
6. Mosaic with a defined overlap rule.
7. Run seam QA.
8. Export one heightmap plus optional debug seam layers.

Overlap rules:

| Product | Default Rule | Why |
|---|---|---|
| DEM/DTM | weighted mean or first-valid after QA | Avoid small edge jumps |
| DSM | max or weighted mean depending on source | Preserve surface objects when valid |
| CHM/canopy | max | Preserve tallest vegetation |
| Orthophoto | feathered RGB blend | Avoid visible tile seams |
| Classification masks | priority or nearest | Do not average class IDs |
| Confidence/coverage | max or count | Show where multiple sources agree |

Seam QA outputs:

```text
seam_delta.tif
seam_delta_preview.png
coverage_count.tif
tile_footprints.geojson
mosaic_report.json
```

Failure signs:

- Tile borders visible in hillshade.
- Overlap elevation jumps larger than source error tolerance.
- Different vertical datum between tiles.
- Mismatched nodata values becoming real terrain.
- Blurry orthophoto seams from repeated reprojection.

Implementation direction:

- Use `rasterio.merge` or explicit window writes for rasters.
- Use VRTs for large intermediate mosaics where possible.
- Keep raw tile files immutable under `opentopo/raw/...`.
- Write mosaics under `opentopo/processed/mosaics/<stack_id>/`.

## Workflow B: Cross-Type Fused Stack

Use this when multiple products overlap and we want one beautiful, layered map.

Example target:

```text
Guadalupe Cypress fused stack
Base height: supplied DTM
Color: RGB orthophoto
Vegetation signal: NIR-source orthophoto + LAZ-derived canopy mosaic
Point-cloud products: RGB topdown, DTM/DSM/CHM, class masks
Derived layers: slope, roughness, hillshade
```

Steps:

1. Pick the base height layer. Usually DTM/DEM.
2. Build the canonical grid from that layer.
3. Convert base height to `heightmap.png` and `meta.json`.
4. Warp every compatible raster to the same grid.
5. Rasterize point clouds into DTM, DSM, CHM, RGB, density, and class masks.
6. Normalize derived layers into Godot-ready `layers/*.png`.
7. Write `stack_manifest.json`.
8. Load the stack in Godot and toggle layers for visual QA.

Layer roles:

| Data Type | Stack Role | Good For | Not Good For |
|---|---|---|---|
| DTM/DEM | Base geometry | Playable ground, collision, slope | Color, trees, buildings |
| DSM | Surface geometry/debug | Tree/building mass, surface height | Player ground unless intentionally above canopy |
| CHM / DSM-DTM | Height mask | Vegetation height, spawn density, canopy volume | Ground elevation |
| Orthophoto RGB | Color/reference layer | Real albedo reference, roads, exposed soil, vegetation patches | Height |
| NIR/false color ortho | Vegetation signal | Plant health/vegetation masks, stylized debug | Natural color albedo |
| LAZ/LAS | Raw evidence | Custom DTM/DSM, class masks, color, density | Direct Godot terrain without rasterization |
| GEDI | Coarse vegetation metric | Regional canopy/biomass hints | Fine local tree placement |
| Hillshade | QA/reference | Reading terrain relief | Game albedo |
| Slope | Derived mask | Rock/grass/scree blending, traversal | Raw visual color |
| Roughness | Derived mask | Boulder/noise/detail zones | Absolute elevation |
| Intensity | Sensor/debug layer | Lidar material hints when valid | Reliable color |
| Point density | Confidence layer | Where LAZ products are trustworthy | Visual texture |

## Orthophoto vs Fantasy Textures

Orthophoto does not prevent fantasy styling. It gives us options:

| Mode | What We Render | When To Use |
|---|---|---|
| Realistic survey | Orthophoto as albedo | Inspection, real-place reconstructions |
| Hybrid grounded fantasy | Orthophoto drives masks; custom textures render final terrain | Best default for game maps |
| Full fantasy | Ignore orthophoto color, keep derived masks and terrain structure | Stylized worlds |
| Debug | Orthophoto/canopy/slope toggles in viewer | QA and data understanding |

Best game path:

1. Use DTM for terrain geometry.
2. Use orthophoto only to derive material masks: vegetation, roads, bare soil,
   rock, water, disturbed ground.
3. Use slope/roughness/elevation to refine those masks.
4. Use custom shaders and PBR textures for final rendering.
5. Keep orthophoto as a toggleable debug/reference overlay.

This gives us real-world placement logic without locking the final look to
photographic imagery.

## Compatibility Matrix

Before fusing two layers, check:

| Check | Required For | Notes |
|---|---|---|
| CRS | All layers | Reproject to target CRS once |
| Transform/grid alignment | All rasters | Similar bounds are not enough |
| Resolution | All rasters | Downsample high-res sources for Godot packages |
| Vertical datum | Height layers | Critical for DEM/DSM/CHM subtraction |
| Capture date | Vegetation/coastal/urban | Old orthos plus new lidar can disagree |
| Nodata semantics | All rasters | Convert to one mask convention |
| Classification schema | LAZ/LAS | LAS class IDs vary in reliability |
| Band meaning | Orthos/NIR/GEDI | Do not assume RGB, NIR, or RH metrics without metadata |
| Coverage footprint | All layers | Every layer needs a valid-pixel mask |
| License/source | All layers | Record source page and license in manifest |

## Proposed Pilot 1: Large Same-Type Mosaic

Start conservative:

```text
Site: Grand Canyon or another large canyon/desert area
Product: USGS10m DEM first
AOI: large enough to require multiple pulls
Output: one stitched DTM heightmap, seam QA, coverage mask
```

Why USGS10m first:

- Big enough to test stitching.
- Small enough to iterate quickly.
- Cleaner than starting with many 1 m jobs.

Then repeat with USGS1m over a smaller sub-area once the mosaic logic is proven.

## Pilot 1 Result: Grand Canyon USGS10m

Status: executed and approved for same-type mosaic workflow validation.

Run summary:

```text
Stack ID: grand_canyon_usgs10m_pilot
Product: USGS10m via usgsdem
AOI: 40 km x 40 km
Tiles: 2 x 2
Overlap: 2 km
Target CRS: EPSG:32612
Target cell size: 10 m
Reducer: mean
```

Output:

```text
D:/assets/world3/opentopo/processed/mosaics/grand_canyon_usgs10m_pilot/
```

Validation highlights:

- 4 of 4 source tiles downloaded as valid GeoTIFFs.
- Mosaic grid: `4050 x 4059`, `16,061,086` valid pixels.
- Elevation range: `672.81 m` to `2705.65 m`.
- Overlap pixels: `1,571,430`, with max coverage count `4`.
- Seam delta mean: `0.126 m`.
- Seam delta P95: `0.546 m`.
- Seam delta P99: `1.425 m`.
- Only `0.00465%` of overlap pixels exceed `10 m`; these are localized
  outliers, not a general tile-border failure.
- Hillshade visual QA did not show obvious rectangular tile seams.

Audit doc:

```text
world3/docs/OPENTOPO_PILOT1_GRAND_CANYON_USGS10M_AUDIT.md
```

Verdict:

- Good enough to scale same-type mosaics.
- Still height-only data; no color, canopy, or lidar classification.
- Use this mosaic as a base-height candidate when Workflow B starts.

## Proposed Pilot 2: Cross-Type Fused Stack

Start with Guadalupe Cypress because the raw data is already local:

```text
Base: DTM_RGB_2016.tif
Color: 2016_rgb_orto_COF.tif
Vegetation signal: 2016_nir_orto_COG.tif
Point cloud: seven LAZ regions
Canopy: canopy_height_mosaic.png / chm_vegetation_mosaic.png
Viewer: opentopo_samples.tscn
```

Next missing layers:

- `slope.png`
- `roughness.png`
- `hillshade.png`
- `coverage_count.png`
- `point_density.png`
- `vegetation_mask_from_nir.png`
- `material_mask.png`

## Pilot 2 Result: Guadalupe Cypress Fused Stack

Status: executed and validated for first cross-type fusion workflow.

Primary review stack:

```text
D:/assets/world3/opentopo/processed/stacks/guadalupe_cypress_strict_fused_pilot/
```

Run summary:

```text
Site: Guadalupe Cypress
Bounds: 370200, 3218600, 371800, 3220200
CRS: EPSG:32611
AOI: 1.6 km x 1.6 km
Output size: 1024 x 1024
Base height: DTM_RGB_2016.tif
```

Aligned layers:

- `orthophoto_rgb.png`
- `orthophoto_nir_false.png`
- `vegetation_ndvi_like.png`
- `canopy_height_mosaic.png`
- `chm_vegetation_mosaic.png`
- `pointcloud_rgb_topdown_mosaic.png`
- `pointcloud_nir_source_topdown_mosaic.png`
- `hillshade.png`
- `slope_deg.png`
- `roughness.png`

Audit doc:

```text
world3/docs/OPENTOPO_PILOT2_GUADALUPE_CYPRESS_FUSION_AUDIT.md
```

Verdict:

- The cross-type grid approach works.
- RGB orthophoto is a strong real-color/reference layer.
- NIR-derived vegetation and LAZ canopy products give useful vegetation signals.
- Larger crops with no-data strips are still valuable and should be retained for
  future fill workflows.

## Texture, Scene, And High-Detail Branch

The mosaic/fusion work now supports three follow-on workflows:

1. Baked ground textures: use orthophoto and derived masks as source evidence
   for reusable seamless PBR materials.
2. Fused real-place scenes/maps: preserve an actual AOI as a layered Godot
   terrain stack.
3. High-detail zoom/chunked delivery: push texture/mesh resolution, then split
   scenes into chunks when single-texture delivery runs out of memory or
   fidelity.

Detailed plan:

```text
world3/docs/OPENTOPO_TEXTURE_SCENE_ROADMAP.md
```

First HD pass:

```text
world3/docs/OPENTOPO_PHASE2_HD_REVIEW.md
world3/toporeview/phase2_fusion_hd_review.tscn
world3/docs/OPENTOPO_PHASE2_MAX_REVIEW.md
world3/toporeview/phase2_fusion_max_review.tscn
world3/toporeview/phase2_fusion_ultra_rgb_review.tscn
```

Important distinction:

- Workflow 2 decides which measured/derived layers belong together.
- Workflow 3 decides how to render those layers close up.
- Workflow 1 extracts reusable materials from the same source evidence.

## Large 4-Call Mosaic Result

The scale test is a completed 2x2 `USGS1m` mosaic with four API calls. The first
target is Southern Appalachians / Smokies because the repo already had a
known-good `USGS1m` pull there and the local catalog reports nearby USGS/NOAA
point-cloud datasets.

The planned grid is:

```text
stack: smokies_usgs1m_4call
dataset: USGS1m
center: lon -83.50, lat 35.60
unique AOI: 29 km x 29 km
tiles: 2 x 2
overlap: 1 km
per request: 15 km x 15 km = 225 km2
result grid: 29005 x 29835 at 1 m
validation: pass_with_notes
seam p99: 0.0 m
```

Runbook:

```text
world3/docs/OPENTOPO_LARGE_4CALL_PLAN.md
world3/docs/OPENTOPO_PHASE3_SMOKIES_4CALL_AUDIT.md
```

## No-Data And Fill Policy

Small no-data gaps should not disqualify otherwise good sites. The workflow
should treat gap filling as a separate, explicit layer-generation step.

Current rule:

- Preserve source no-data.
- Store valid-pixel counts in sidecars and manifests.
- Keep broader stacks for future fill experiments.
- Use cleaner crops only for first-pass alignment validation.

Future fill modes:

| Fill Mode | Good For | Must Track |
|---|---|---|
| Neighbor inpaint | tiny orthophoto cracks or edge slivers | `filled_mask.png` |
| Source-pixel inpaint/extension | tiny orthophoto cracks or edge slivers | source mask + fill provenance |
| Art-material fill | non-photoreal game albedo/material gaps | separate art mask + provenance |
| Vegetation-stat fill | missing canopy/vegetation hints | source-valid vegetation mask |
| Generative image fill | visual-only color gaps | synthetic/fill provenance |

Filled pixels are visual/modeling aids, not measured source data.

## Tooling To Build Next

New scripts should be documented in `OPENTOPO_GUIDE.md` when created.

Planned tools:

```text
pipeline/build_opentopo_mosaic.py
  Same-type raster tiles -> one seamless GeoTIFF + seam QA.

pipeline/fetch_opentopo_tile_grid.py
  One AOI -> overlapping OpenTopography API requests for same-type mosaics.

pipeline/validate_opentopo_mosaic.py
  Same-type mosaic -> automated source/mosaic consistency report.

pipeline/export_opentopo_rgb_mosaic.py
  Multiple RGB point-cloud/ortho rasters -> one aligned RGB PNG.

pipeline/export_opentopo_vegetation_mask.py
  NIR/false-color orthophoto -> aligned vegetation signal PNG.

pipeline/build_opentopo_stack_manifest.py
  Fused Godot stack folder -> manifest and size validation.

pipeline/build_opentopo_stack.py
  DTM/DSM/ortho/pointcloud-derived rasters -> aligned stack manifest and layers.

pipeline/derive_opentopo_masks.py
  Orthophoto/NIR/slope/roughness/canopy -> material and vegetation masks.
```

Expected stack output:

```text
opentopo/processed/stacks/<stack_id>/
  stack_manifest.json
  heightmap.png
  meta.json
  layers/
    orthophoto_rgb.png
    orthophoto_nir_false.png
    canopy_height.png
    slope.png
    roughness.png
    hillshade.png
    point_density.png
    material_mask.png
  qa/
    coverage_count.png
    seam_delta.png
    alignment_report.json
```
