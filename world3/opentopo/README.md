# OpenTopography Acquisition Plan

This folder is for the OpenTopography sampling campaign feeding the `world3`
viewer. Keep API keys out of tracked files; use `OPENTOPOGRAPHY_API_KEY` in the
environment. `OPENTOPO_API_KEY` is also supported as a local alias.

See `world3/docs/OPENTOPO_GUIDE.md` for the local secret file path and API
commands.

## Goal

Build a representative terrain dataset across world biomes, elevations, and
source types, then compare what each data product actually gives us in Godot.

The full target matrix is 14 terrestrial biome groups x 5 locations = 70
sampling sites. The first pass should be a smaller calibration wave before we
download the full set.

## Storage Layout

```text
world3/opentopo/
  README.md
  sample_plan.json
  catalog/
    otcatalog_raw/
    site_catalog_summary.json
  raw/
    globaldem/
    usgsdem/
    pointcloud/
    dataspace/
    bulk/
  processed/
    heightmaps/
    mosaics/
    stacks/
    pointcloud/
    comparison/
    derived/
    extracted/
  viewer_sets/
    calibration/
    full_biome_matrix/
```

## Acquisition Stages

1. Calibration wave: pull one site per biome at roughly 20 km x 20 km.
2. Data-type comparison: for selected sites, pull several raster sources over
   the same bounds and compare elevation ranges, artifacts, and shape detail.
3. High-resolution probe: use `otCatalog` to find point-cloud or 1 m DEM
   availability for sites in the US, Canada, New Zealand, polar regions, and
   coastal zones.
4. Viewer integration: convert rasters to 16-bit heightmaps and metadata using
   `pipeline/build_world.py`; convert point clouds to sampled CSV, DTM/DSM,
   color, and canopy rasters using `pipeline/process_laz_samples.py`.
5. Texture-layer export: convert useful rasters to Godot-aligned PNG layers
   using `pipeline/export_opentopo_texture.py`; combine related masks with
   `pipeline/export_opentopo_mosaic.py`.
6. Same-type mosaics: split large AOIs into overlapping API windows, then stitch
   them under `processed/mosaics/<stack_id>/` using seam QA.
7. Full matrix: expand to all 70 sites once the viewer and storage naming are
   stable.

## Data Types To Pull

Raster height products:

- `DTM` / `DEM`: bare-earth terrain height. Best source for playable terrain.
- `DSM`: surface height including trees/buildings. Best for canopy/city mass.
- `CHM`: canopy/feature height above ground, normally `DSM - DTM`.
- `bathymetry/topobathy`: land plus underwater/coastal elevation.
- derived rasters: hillshade, slope, aspect, roughness, contours.

Point-cloud products:

- `LAZ` / `LAS`: real lidar point data, not a heightmap. Contains x/y/z and
  possible attributes such as classification, intensity, return number, GPS
  time, and color depending on the dataset.
- tile indexes: shapefiles identifying LAZ tile footprints and download URLs.

## First Pull Set

For the first pass, use the `priority: 1` entries in `sample_plan.json`.

For every priority-1 site:

- Pull `COP30` as the default 30 m global DSM/height source.
- Pull `NASADEM` or `SRTMGL1` as an alternate global terrain source where valid.
- Pull `SRTM15Plus` or `GEBCOIceTopo` for coastal, island, mangrove, and
  bathymetry-heavy sites.
- Query `otCatalog` with `include_federated=true` to discover point-cloud,
  USGS, NOAA, or OT-hosted coverage.

For US priority-1 sites, also pull:

- `USGS10m` over the same bounds.
- `USGS1m` only after checking size; OpenTopography's limit is 250 km2 per job.
  Use `pipeline/fetch_opentopo_tile_grid.py --max-tile-area-km2 250` for
  four-call scale tests.

## Naming

Use stable IDs from `sample_plan.json`:

```text
raw/globaldem/{site_id}/{demtype}_{bbox_slug}.tif
raw/usgsdem/{site_id}/{datasetName}_{bbox_slug}.tif
processed/heightmaps/{site_id}/{source}/heightmap.png
processed/heightmaps/{site_id}/{source}/meta.json
processed/heightmaps/{site_id}/{source}/layers/{layer_name}.png
processed/pointcloud/{source}/{laz_stem}/{product}.tif
processed/mosaics/{stack_id}/mosaic.tif
processed/mosaics/{stack_id}/mosaic_report.json
processed/stacks/{stack_id}/heightmap.png
processed/stacks/{stack_id}/layers/{layer_name}.png
processed/stacks/{stack_id}/stack_manifest.json
processed/comparison/{site_id}/summary.json
```

## Workflow Documentation

When adding or changing any acquisition or processing step, update:

- `world3/docs/OPENTOPO_GUIDE.md` for commands and tool behavior.
- `world3/docs/OPENTOPO_DATA_TYPES.md` for what the product is good for.
- `world3/docs/OPENTOPO_MOSAIC_FUSION_WORKFLOWS.md` for tile stitching and
  cross-type stack design.
- `world3/opentopo/STATUS.md` for what was actually downloaded or generated.
