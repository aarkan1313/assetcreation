# OpenTopography Data Types

This is the living usage guide for the OpenTopography sample set in `world3`.
It should be updated whenever we extract a new layer, add a viewer mode, or
learn a practical limitation.

Current extracted reports:

```text
D:/assets/world3/opentopo/processed/comparison/sample_comparison.md
D:/assets/world3/opentopo/processed/comparison/sample_comparison.json
D:/assets/world3/opentopo/processed/comparison/laz_headers.json
D:/assets/world3/opentopo/processed/comparison/extracted_layers.json
D:/assets/world3/opentopo/processed/pointcloud/pointcloud_summary.json
D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/orthophotos/
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/
```

## 1. Global DSM / Surface Rasters

Representatives:

```text
COP30
AW3D30
```

What it is:

These are global 30 m-ish surface/elevation rasters. `COP30` is Copernicus DSM;
`AW3D30` is ALOS World 3D DSM. They are not color imagery. Each pixel stores one
height value.

What we extracted:

- Mojave `COP30`: 799 x 651 px, ~25-31 m cells, 660-1945 m.
- Mojave `AW3D30`: same shape/cell size, 661-1946 m.
- The two are very close over Mojave; `AW3D30` is mostly a cross-check rather
  than a different gameplay layer there.

Good for:

- Default worldwide terrain source.
- Biome breadth because it covers nearly everywhere.
- Medium-scale terrain shapes: basins, mountains, ridges, valleys.
- Base mesh when no local high-resolution DEM exists.

Weaknesses:

- Too coarse for walkable local detail.
- DSM can include surface artifacts; it is not guaranteed bare earth.
- No material, vegetation, or color information.

Usage in Godot:

- Convert to `heightmap.png` + `meta.json` with `build_world.py`.
- Good default for 20-80 km scenes.
- Use derived slope/roughness to drive material blending.

Next extraction:

- Compute `COP30 - AW3D30` difference maps to detect source disagreement and
  artifacts.

## 2. Global Terrain DEM Rasters

Representatives:

```text
NASADEM
SRTMGL1
```

What it is:

Global terrain-oriented 30 m DEM products derived from SRTM-family data. These
are heightmaps, not imagery.

What we extracted:

- Sierra Madre `NASADEM`: 714 x 651 px, ~28-31 m cells, 177-1436 m.
- Sierra Madre `SRTMGL1`: 714 x 651 px, ~28-31 m cells, 178-1438 m.
- They are nearly identical in this sample.

Good for:

- A second terrain baseline against `COP30`.
- Stable low/mid-latitude terrain mesh.
- Regions where DSM surface artifacts are distracting.

Weaknesses:

- SRTM/NASADEM coverage stops around high latitudes; Alaska/arctic samples
  returned all-nodata for NASADEM and SRTMGL1.
- Usually redundant if `COP30` looks good.

Usage in Godot:

- Use as an alternate heightmap source for comparison.
- Prefer `COP30` as default global coverage; keep NASADEM/SRTM as validation.

Next extraction:

- Build a per-site source-confidence report: if COP30/NASADEM/SRTM agree, use
  the smallest/cleanest file; if they diverge, flag the site for visual review.

## 3. USGS High-Resolution DEM Rasters

Representatives:

```text
USGS10m
USGS1m
```

What it is:

USGS 3DEP raster DEMs through the OpenTopography `usgsdem` API. `USGS1m` is the
high-value OT+ path for small U.S. areas.

What we extracted:

- California chaparral `USGS10m`: 235 x 195 px, ~8.5-10.3 m cells, 933-1462 m.
- California chaparral `USGS1m`: 1962 x 2046 px, 1 m cells, 937-1463 m.
- Appalachians also has a valid `USGS10m` + `USGS1m` pair.
- Mojave returned `USGS10m` but no raster for `USGS1m` at the tested box.

Good for:

- Best walkable terrain mesh source.
- High-detail cliffs, ridgelines, drainages, roads, terraces.
- Small hero locations and comparison shots.

Weaknesses:

- U.S.-only.
- `USGS1m` must use small AOIs; OpenTopography caps it at 250 km2 per job.
- For the planned 4-call scale test, use 2x2 tiles of 225 km2 each; see
  `OPENTOPO_LARGE_4CALL_PLAN.md`.
- Files grow quickly; 2 km x 2 km already produced ~12 MB compressed GeoTIFF.

Usage in Godot:

- Use `USGS1m` for detailed local scenes.
- Use `USGS10m` for broader playable areas where 1 m is too large.
- Do not fetch huge `USGS1m` boxes; tile or sample deliberately.

Next extraction:

- Generate matched `USGS1m - USGS10m` residual maps to quantify the detail we
  lose when downshifting to 10 m.

## 4. Bathymetry / Topobathy Rasters

Representatives:

```text
SRTM15Plus
GEBCOIceTopo
```

What it is:

Coarse global land + underwater elevation. These are still height rasters, but
they include negative elevation for underwater terrain.

What we extracted:

- Sundarbans `SRTM15Plus`: 186 x 174 px, ~430-464 m cells, -29 to 13 m.
- Sundarbans `GEBCOIceTopo`: same grid, -29 to 13 m.
- They were nearly identical in the sample.

Good for:

- World-map basemaps.
- Island chains, coastlines, deltas, continental shelves.
- Strategic overview maps rather than local walkable terrain.
- Sea-level masks and coastline extraction.

Weaknesses:

- Far too coarse for local gameplay terrain.
- Small local samples can look flat because the cell size is hundreds of meters.

Usage in Godot:

- Use for macro map or ocean-floor silhouette.
- Combine with a detailed land DEM for playable coastline scenes.

Next extraction:

- Generate water/land masks from `elevation <= 0`.
- Build coastline vectors/contours for map UI.

## 5. Paired DTM / DSM Rasters

Representatives:

```text
CA_MRDEM_DTM
CA_MRDEM_DSM
```

What it is:

Matched Canadian terrain and surface rasters. DTM is bare earth. DSM includes
surface features like vegetation/buildings. The difference is a surface-height
layer.

What we extracted:

Generated:

```text
D:/assets/world3/opentopo/processed/extracted/surface_height/bor_yukon_canada/dsm_minus_dtm.tif
D:/assets/world3/opentopo/processed/extracted/surface_height/tcf_bc_coast_canada/dsm_minus_dtm.tif
```

Results:

- Yukon surface height: max 18.2 m, mean 2.8 m, p95 7.5 m.
- BC Coast surface height: max 45.3 m, mean 8.2 m, p95 20.5 m.

Good for:

- Real vegetation/building/feature-height masks.
- Forest density, canopy height, obstruction, line-of-sight.
- Surface-vs-ground comparison for placement rules.

Weaknesses:

- Canada-specific in this source.
- 30 m cells: good for regional vegetation structure, not individual trees.

Usage in Godot:

- Use DTM as terrain mesh.
- Use `DSM - DTM` as a mask for vegetation spawn height/density.
- Use high surface-height areas to avoid placing roads/buildings unless the
  game intends forested/urban clutter.

Next extraction:

- Convert surface-height rasters into normalized biome masks and Godot textures.

## 6. GEDI L3 Metrics

Representatives:

```text
GEDI_L3_ELEV
GEDI_L3_RH100
```

What it is:

Coarse 1 km-ish gridded land surface metrics from GEDI lidar. This is not a
normal terrain mesh input. `RH100` is useful as vegetation/canopy structure.

What we extracted:

Generated:

```text
D:/assets/world3/opentopo/processed/extracted/gedi/tmf_amazon_brazil/rh100_height_metric.tif
D:/assets/world3/opentopo/processed/extracted/gedi/tgs_serengeti_tanzania/rh100_height_metric.tif
```

Results:

- Amazon `RH100`: mean 13.8 m, p95 27.3 m, max 36.4 m.
- Serengeti `RH100`: mean 4.8 m, p95 7.4 m, max 9.7 m.

Good for:

- Biome-scale vegetation height priors.
- Distinguishing rainforest/savanna/grassland structure.
- Procedural density parameters over large areas.

Weaknesses:

- Very coarse; not useful as a terrain mesh.
- Sparse/invalid pixels can exist depending on GEDI coverage.

Usage in Godot:

- Feed into biome material/scatter rules, not the heightmap mesh.
- Use as a high-level vegetation height/density texture after resampling.

Next extraction:

- Build a normalized `vegetation_density.png` per site from `RH100`.

## 7. Point Clouds / LAZ

Representatives:

```text
CA14_Lowe
WA12_Legg
Guadalupe_Cypress
```

What it is:

Compressed point clouds. Many are lidar; some, like the Guadalupe Cypress sample,
are photogrammetric/SfM products. Not a heightmap. Each point has XYZ plus
standard per-point attributes depending on point format.

What we extracted:

```text
D:/assets/world3/opentopo/processed/comparison/laz_headers.json
D:/assets/world3/opentopo/processed/pointcloud/pointcloud_summary.json
D:/assets/world3/opentopo/processed/pointcloud/CA14_Lowe/ot_335000_3809000/
D:/assets/world3/opentopo/processed/pointcloud/WA12_Legg/ot_583000_5176000/
D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/
```

Findings:

- `CA14_Lowe` and `WA12_Legg` are LAS 1.2, compressed LAZ, point format 1.
- `CA14_Lowe` and `WA12_Legg` include intensity, return info,
  classification, scan angle, point source, and GPS time.
- `CA14_Lowe` and `WA12_Legg` do not have RGB color or NIR.
- `CA14_Lowe`: 37,253 points, z range 205.6-288.9 m; 34,147 ground
  points and 3,106 unclassified points.
- `WA12_Legg`: 681,492 points, z range 630.4-1319.9 m; 94,026 ground,
  585,621 unclassified, 577 high-vegetation, and 1,268 low-point-noise points.
- `Guadalupe_Cypress`: all seven point-cloud regions are downloaded and
  processed, totaling 608,189,343 points. They are LAS point format 3 with RGB
  dimensions present.
- `Guadalupe_Cypress` RGB regions: 292,392,964 points across three files,
  including 15,490,124 high-vegetation points.
- `Guadalupe_Cypress` NIR-source regions: 315,796,379 points across four files,
  including 14,931,349 high-vegetation points.
- `Guadalupe_Cypress` external-DTM canopy-like maxima range from 25.1 m to
  55.5 m. Despite the NIR file names, the LAS dimensions are RGB, not a true
  LAS NIR dimension.
- Generated per sample: `dtm_ground.tif`, `dsm_surface.tif`,
  `surface_minus_ground_raw.tif`, `chm_vegetation.tif`, `points_sample.csv`,
  and `summary.json`.
- `CA14_Lowe` raw surface-minus-ground max is 5.9 m, mean 1.0 m. It has no
  vegetation-classified points, so `chm_vegetation.tif` has no valid cells.
- `WA12_Legg` raw surface-minus-ground max is 676.7 m, mean 29.4 m. That is a
  QA warning, not usable canopy height. After a 120 m canopy gate, all 184
  vegetation cells were rejected, so `chm_vegetation.tif` has no valid cells.
- `Guadalupe_Cypress` generated real color point-cloud previews:

```text
D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/2016_rgb_pc_r1/rgb_topdown.png
D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/2016_nir_pc_r1/rgb_topdown.png
```

- `Guadalupe_Cypress` also generated canopy-like surface-height previews using
  the supplied 1 m DTM as the ground reference:

```text
D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/2016_rgb_pc_r1/canopy_like_external_dtm_preview.png
D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/2016_nir_pc_r1/canopy_like_external_dtm_preview.png
```

Good for:

- Richest source for custom terrain processing.
- Filtering by classification: ground vs vegetation/buildings/noise where
  classification is reliable.
- Building custom DTM/DSM locally.
- Real color point-cloud previews when RGB exists.
- Canopy/surface-height extraction when a matching DTM exists.
- Auditing point returns, intensity, and classification quality before deriving
  gameplay masks.
- Point-cloud visualizations and QA.

Weaknesses:

- Needs LAZ tooling such as PDAL or `laspy[lazrs]` to read/decompress points.
- Huge datasets if we pull too many tiles.
- Many point clouds do not provide RGB; inspect the LAS point format before
  assuming color is present.
- Classification quality varies by dataset. A vegetation class can still contain
  bad heights or mismatched ground, so CHM needs sanity gates and visual review.
- External DTM subtraction can produce better canopy-like layers than relying
  only on within-cloud classification, but it still needs QA.

Usage in Godot:

- Use `dtm_ground.tif` or a supplied DTM as the terrain source after conversion
  to heightmap.
- Use `dsm_surface.tif` or `surface_minus_ground_raw.tif` as QA/debug layers,
  not automatic gameplay masks.
- Use `points_sample.csv` for a lightweight debug point-cloud view.
- Use `chm_vegetation.tif` only when it has valid cells after height gating.
- Use `rgb_topdown.png` as a real-world color reference or debug overlay.
- Use `canopy_like_external_dtm.tif` as a vegetation-height mask when it was
  generated from a trusted DTM.

Next extraction:

- Combine the two Cypress point-cloud canopy masks into one full-footprint
  vegetation-height mask and compare it against the NIR-source orthophoto.

## 8. Orthophotos / Color Imagery

Representatives:

```text
Guadalupe_Cypress 2016 RGB orthophoto
Guadalupe_Cypress 2016 NIR-source orthophoto
```

What it is:

These are real raster images, not heightmaps. The Cypress RGB orthophoto is
about 6.6 cm/pixel and the NIR-source orthophoto is about 6.5 cm/pixel. Both are
3-band `uint8` rasters in `EPSG:32611`.

What we extracted:

Raw files:

```text
D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_rgb_orto_COF.tif
D:/assets/world3/opentopo/raw/dataspace/Guadalupe_Cypress/2016_nir_orto_COG.tif
```

Preview files:

```text
D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/orthophotos/2016_rgb_orto_COF_preview.png
D:/assets/world3/opentopo/processed/pointcloud/Guadalupe_Cypress/orthophotos/2016_nir_orto_COG_preview.png
```

Good for:

- Real color reference for terrain materials.
- Vegetation/shrub patch masks.
- Roads, bare soil, rock color, and disturbed-ground reference.
- False-color/NIR-style vegetation emphasis.

Weaknesses:

- Orthophotos are flat imagery; they do not contain height by themselves.
- Large rasters need downsampling or tiled streaming before use in Godot.
- NIR-source products need interpretation; do not treat them as ordinary RGB
  albedo unless we explicitly want the false-color look.

Usage in Godot:

- Use downsampled orthophoto previews as debug/reference overlays.
- Use full-resolution orthos offline to derive material masks.
- Pair the orthophoto with the DTM/DSM/canopy-like rasters for real terrain
  plus real surface color.
- The first Godot-ready aligned texture exports are in:

```text
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/orthophoto_rgb.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/orthophoto_nir_false.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/canopy_height_mosaic.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/chm_vegetation_mosaic.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/canopy_height_mask.png
D:/assets/world3/opentopo/processed/heightmaps/guadalupe_cypress_dtm_2016/layers/canopy_height_mask_nir_source.png
```

## 9. Local Derived Rasters

Representatives:

```text
hillshade.tif
slope_deg.tif
roughness.tif
```

What it is:

Analysis layers derived locally from height rasters. These are not new
OpenTopography products, but they are essential for using elevation well.

What we extracted:

```text
D:/assets/world3/opentopo/processed/derived/tcf_pnw_cascades_usa/COP30/
D:/assets/world3/opentopo/processed/derived/tgr_great_plains_usa/COP30/
```

Results:

- Cascades rugged sample: max slope 73.4 degrees, max roughness 226.1 m.
- Great Plains flat sample: max slope 18.5 degrees, max roughness 16.3 m.

Good for:

- Material blending: grass vs rock vs scree.
- Road/path/building placement constraints.
- Cliff detection.
- Erosion/water-flow style heuristics.
- Map UI hillshades.

Weaknesses:

- Only as good as the input DEM resolution.
- Need smoothing or scale-aware thresholds to avoid noisy masks.

Usage in Godot:

- Convert derived rasters to grayscale/normalized textures.
- Use slope and roughness in terrain shader or spawn logic.

Next extraction:

- Create Godot-ready `slope.png`, `roughness.png`, and `hillshade.png` masks.

## Current Priorities

1. Use `toporeview/phase2_fusion_review.tscn` to compare the Cypress RGB
   orthophoto, NIR-source orthophoto, point-cloud color, canopy-height masks,
   hillshade, slope, and roughness.
2. Review `toporeview/phase2_fusion_hd_review.tscn`,
   `toporeview/phase2_fusion_max_review.tscn`, and
   `toporeview/phase2_fusion_ultra_rgb_review.tscn` at close range and capture
   fixed screenshots for the 4096, 8192, and 16K RGB passes.
3. Use orthophoto, NIR, slope, roughness, and canopy masks as source evidence
   for baked ground texture prototypes.

Related plan:

```text
D:/assets/world3/docs/OPENTOPO_TEXTURE_SCENE_ROADMAP.md
D:/assets/world3/docs/OPENTOPO_PHASE2_HD_REVIEW.md
D:/assets/world3/docs/OPENTOPO_PHASE2_MAX_REVIEW.md
```
