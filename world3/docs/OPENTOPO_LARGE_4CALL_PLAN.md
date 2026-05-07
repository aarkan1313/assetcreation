# OpenTopo Large 4-Call Plan

Status: planned and preflighted after Phase 2 max validation.

Date: 2026-05-07

## Why This Exists

The next target is a large, stitched, high-quality terrain area that can later
receive color, canopy, and point-cloud-derived layers. This is deliberately
separate from the Guadalupe Cypress max test:

- Guadalupe Cypress proved cross-type fusion: DTM, RGB orthophoto, NIR,
  point-cloud color, canopy-like rasters, slope, roughness, and hillshade.
- The next 4-call run proves scale: the largest practical `USGS1m` stitched
  terrain mosaic we can make with four OpenTopography raster API calls.

Those are not the same constraint. Four raster API calls can maximize a height
mosaic. "All datasets" requires choosing an AOI where other products overlap
the mosaic and then pulling those products separately.

## Validation Baseline

Phase 2 max is validated before starting this larger run:

```text
D:/assets/world3/toporeview/phase2_fusion_max/stack_manifest.json
status: pass
layers: 10
heightmap: 8192 x 8192
world size: 1600 m

D:/assets/world3/toporeview/phase2_fusion_max_review.tscn
Godot headless load: pass

D:/assets/world3/toporeview/phase2_fusion_ultra_rgb_review.tscn
Godot headless load: pass
```

The 16K RGB stress layer is present:

```text
D:/assets/world3/toporeview/phase2_fusion_max/ultra_layers/orthophoto_rgb_16k.png
```

## Current Official Limits

OpenTopography's developer documentation lists the raster request caps:

```text
USGS30m: 225,000 km2 per request
USGS10m: 25,000 km2 per request
USGS1m: 250 km2 per request
```

OT+ / academic access also lists point-cloud processing limits:

```text
OT-hosted point cloud: 350 million points per job
USGS/NOAA point cloud: 250 million points per job
```

Important interpretation: the "350" number is point count, not meters.

Reference pages:

```text
https://opentopography.org/developers
https://opentopography.org/plus
https://www.opentopography.org/about/subscriptions
```

## Four-Call Geometry

For `USGS1m`, each API request must stay at or below 250 km2. The safe 2x2
layout is:

```text
AOI: 29 km x 29 km unique area
Tiles: 2 x 2
Overlap: 1 km total overlap across internal boundaries
Per call: 15 km x 15 km = 225 km2
Unique coverage: 841 km2
```

This leaves 25 km2 of headroom per request. It is intentionally conservative so
rounding, projection differences, and API interpretation do not push a tile
over the limit.

## Candidate Matrix

| Candidate | Center | Why It Is Good | Main Risk |
|---|---:|---|---|
| Southern Appalachians / Smokies | lon -83.50, lat 35.60 | We already proved `USGS1m` works here; forested mountain terrain; local catalog has USGS/NOAA point-cloud datasets nearby. | Color and canopy will require a second source pass, likely point-cloud-derived color/canopy plus external imagery if OpenTopo orthophoto is not present. |
| Mt. Rainier / Cascades | lon -121.80, lat 46.85 | Dramatic elevation, glaciers, forests, known point-cloud catalog hits. | We have not yet proved `USGS1m` at this exact AOI locally; snow/glacier coverage may complicate material interpretation. |
| Grand Canyon | lon -112.10, lat 36.10 | Visually dramatic and already has a successful `USGS10m` mosaic flow. | `USGS1m` coverage is less certain for the exact AOI; less useful for vegetation/canopy. |

Recommended first huge run: Southern Appalachians / Smokies. It is the lowest
risk because the repo already has a successful small `USGS1m` pull there.

## Preflight Command

The tile-grid fetcher now records per-tile width, height, and area. Use the
guard before downloading:

```powershell
python D:/assets/world3/pipeline/fetch_opentopo_tile_grid.py `
  --stack-id smokies_usgs1m_4call `
  --family usgsdem `
  --dataset USGS1m `
  --center-lon -83.50 `
  --center-lat 35.60 `
  --width-km 29 `
  --height-km 29 `
  --tiles-x 2 `
  --tiles-y 2 `
  --overlap-km 1 `
  --max-tile-area-km2 250 `
  --dry-run
```

Expected preflight:

```text
over_limit: []
tile count: 4
per tile: 15 km x 15 km
per tile area: 225 km2
```

## Fetch Command

When ready to spend the bandwidth/disk:

```powershell
python D:/assets/world3/pipeline/fetch_opentopo_tile_grid.py `
  --stack-id smokies_usgs1m_4call `
  --family usgsdem `
  --dataset USGS1m `
  --center-lon -83.50 `
  --center-lat 35.60 `
  --width-km 29 `
  --height-km 29 `
  --tiles-x 2 `
  --tiles-y 2 `
  --overlap-km 1 `
  --max-tile-area-km2 250 `
  --timeout 1200
```

Raw output:

```text
D:/assets/world3/opentopo/raw/usgsdem/smokies_usgs1m_4call/
```

## Processing Plan

1. Fetch four `USGS1m` tiles.
2. Build a same-type mosaic with `build_opentopo_mosaic.py`.
3. Validate source-to-mosaic consistency with `validate_opentopo_mosaic.py`.
4. Export a Godot heightmap and initial diagnostic texture layers.
5. Make a new `toporeview` scene for the 4-call mosaic.
6. Run headless Godot load validation.
7. Start the overlap pass:
   - USGS/NOAA/OpenTopo point-cloud coverage for canopy and surface detail.
   - Color imagery source for texture, preferring OpenTopo orthophoto when
     available and external NAIP-style imagery otherwise.
   - Derived layers: hillshade, slope, roughness, drainage/curvature masks,
     canopy height if point clouds overlap.

## Expected Data Shape

At 1 m resolution, the final unique mosaic is roughly:

```text
29,000 x 29,000 cells
841 million pixels
```

This is large. It is still below the user's stated 50 GB concern, but it is big
enough that processing may need chunked VRT/COG workflows instead of loading the
entire mosaic into memory.

If the full `USGS1m` mosaic is too heavy for Godot as one mesh, split the review
scene into chunks:

```text
near chunks: 2048 or 4096 textures
far terrain: downsampled mosaic
material overlays: streamed or baked per chunk
```

## Success Criteria

- Four raw GeoTIFFs downloaded with no non-GeoTIFF API errors.
- Every request window under 250 km2.
- Mosaic reports sane CRS, resolution, bounds, nodata, and overlap coverage.
- Seam QA shows no obvious border jumps.
- Godot review scene loads and can navigate the full terrain.
- Docs list raw paths, processed paths, exact commands, and validation results.
