# OpenTopo Pilot 1 Audit: Grand Canyon USGS10m Mosaic

Date: 2026-05-07

Scope: Workflow 1 only. This validates same-type multi-tile stitching before
we start cross-type fusion.

## Goal

Build one larger terrain package from multiple OpenTopography requests of the
same product, then prove whether the stitch is usable for larger world builds.

Pilot choices:

- Site: Grand Canyon
- Center: `-112.1129, 36.1069`
- Product: `USGS10m`
- API family: `usgsdem`
- AOI: `40 km x 40 km`
- Tile grid: `2 x 2`
- Overlap: `2 km`
- Mosaic CRS: `EPSG:32612`
- Mosaic cell size: `10 m`
- Reducer: `mean`

## Commands

Dry-run tile plan:

```powershell
python D:/assets/world3/pipeline/fetch_opentopo_tile_grid.py `
  --stack-id grand_canyon_usgs10m_pilot `
  --family usgsdem --dataset USGS10m `
  --center-lon -112.1129 --center-lat 36.1069 `
  --width-km 40 --height-km 40 `
  --tiles-x 2 --tiles-y 2 --overlap-km 2 `
  --dry-run
```

Fetch raw tiles:

```powershell
python D:/assets/world3/pipeline/fetch_opentopo_tile_grid.py `
  --stack-id grand_canyon_usgs10m_pilot `
  --family usgsdem --dataset USGS10m `
  --center-lon -112.1129 --center-lat 36.1069 `
  --width-km 40 --height-km 40 `
  --tiles-x 2 --tiles-y 2 --overlap-km 2
```

Build mosaic:

```powershell
python D:/assets/world3/pipeline/build_opentopo_mosaic.py `
  --input-dir D:/assets/world3/opentopo/raw/usgsdem/grand_canyon_usgs10m_pilot `
  --glob "USGS10m_*.tif" `
  --output-dir D:/assets/world3/opentopo/processed/mosaics/grand_canyon_usgs10m_pilot `
  --name grand_canyon_usgs10m_pilot `
  --target-crs EPSG:32612 `
  --target-cell-size-m 10 `
  --reducer mean `
  --resampling bilinear `
  --heightmap-size 1024 `
  --material rock_light
```

## Outputs

Raw input:

```text
D:/assets/world3/opentopo/raw/usgsdem/grand_canyon_usgs10m_pilot/
  USGS10m_r00_c00_*.tif
  USGS10m_r00_c01_*.tif
  USGS10m_r01_c00_*.tif
  USGS10m_r01_c01_*.tif
  tile_grid_manifest.json
```

Processed mosaic:

```text
D:/assets/world3/opentopo/processed/mosaics/grand_canyon_usgs10m_pilot/
  mosaic.tif
  coverage_count.tif
  seam_delta.tif
  tile_footprints.geojson
  mosaic_report.json
  stack_manifest.json
  heightmap.png
  meta.json
  qa/
    mosaic_preview.png
    coverage_count_preview.png
    seam_delta_preview.png
    hillshade_preview.png
```

## Numeric Validation

Fetch status:

- 4 of 4 requested tiles returned valid GeoTIFFs.
- Source CRS: `EPSG:4269`.
- Each source tile is `2522 x 2051` pixels.

Mosaic grid:

- Target CRS: `EPSG:32612`.
- Target grid: `4050 x 4059`.
- Target bounds: `379530, 3976110, 420030, 4016700`.
- Valid pixels: `16,061,086`.
- Elevation range: `672.81 m` to `2705.65 m`.
- Mean elevation: `1810.68 m`.

Coverage:

- Overlap pixels: `1,571,430`.
- Max coverage count: `4`.
- Coverage preview shows the expected cross-shaped overlap from a `2 x 2`
  grid.

Seam delta:

- Mean: `0.126 m`.
- Median: `0.0028 m`.
- P95: `0.546 m`.
- P99: `1.425 m`.
- Max: `35.397 m`.

Threshold counts across overlap pixels:

| Threshold | Count | Percent |
|---|---:|---:|
| `> 0.5 m` | 90,290 | 5.746% |
| `> 1 m` | 29,567 | 1.882% |
| `> 2 m` | 8,046 | 0.512% |
| `> 5 m` | 627 | 0.0399% |
| `> 10 m` | 73 | 0.00465% |

Automated validation report:

```text
D:/assets/world3/opentopo/processed/mosaics/grand_canyon_usgs10m_pilot/validation_report.json
```

Automated checks:

- shape consistency: pass
- target CRS: pass
- no nodata inside coverage: pass
- report valid pixel count: pass
- seam P99 under `2 m`: pass
- unique-area source match: pass

Source-match result:

- Unique, non-overlap pixels match their reprojected source tile exactly:
  P99 absolute delta `0.0 m`.
- In overlap areas, the mosaic is the mean reducer output. Source-to-mosaic
  P99 absolute delta is `0.712 m`.

## Visual QA

`hillshade_preview.png` reads as one continuous canyon terrain surface. I did
not see obvious rectangular tile boundaries in the terrain relief.

`coverage_count_preview.png` shows the expected vertical and horizontal overlap
bands, with a four-tile overlap at the center.

`seam_delta_preview.png` shows seam disagreement only in overlap areas. The
largest visible disagreement is localized, mostly in steep or edge-adjacent
terrain. That matches the numeric distribution: the average and P95 seam deltas
are small, while the max is a localized outlier.

## Audit Verdict

Approved as the first same-type mosaic workflow. This is a valid base for
larger same-product mosaics and for the later cross-type fusion workflow.

What this product gives us:

- Bare terrain height.
- Godot-ready heightmap export.
- QA layers for stitch coverage and seam disagreement.

What it does not give us:

- Orthophoto color.
- Vegetation/canopy information.
- Point density or lidar classification.

Production notes before scaling up:

- Keep raw tiles immutable.
- Keep overlap enabled; it gives us measurable seam QA.
- Record vertical datum explicitly when metadata exposes it.
- Consider clipping an outer buffer after mosaicking if edge artifacts matter.
- For high-resolution `USGS1m`, use smaller windows and the same audit flow.
- Add the mosaic bundle to the Godot sample index only after deciding how
  `processed/mosaics` should coexist with `processed/heightmaps`.
- The GeoTIFF mosaic keeps the full `40500 m x 40590 m` grid. The exported
  Godot `heightmap.png` is square and records `world_size_m: 40500`, so use
  square AOIs or add rectangular terrain scaling before relying on exact
  horizontal distances in Godot.
