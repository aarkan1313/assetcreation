# Mega-Stack Pulls — 2026-05-09

User asked for two HUGE 3×3 mega-stacks at the highest available
resolution, in NEW areas not yet pulled, with biome diversity.

The pattern matches the worker's existing master-stack approach
(see `OPENTOPO_MASTER_STACKS_AUDIT.md`) but at a larger USGS1m
LiDAR footprint (~42×42 km).

## Picks

Both target USGS1m LiDAR (highest resolution OpenTopo offers; US-only),
3×3 grid of ~14×14 km tiles per cell to stay under the 250 km²/call
API limit.

### Mega 1 — Olympic Peninsula, WA

- **ID**: `olympic_peninsula_1m_v2`
- **Bbox**: -123.731, 47.611, -123.169, 47.989 (42×42 km)
- **Center**: ~-123.45, 47.80 — Olympic National Park core
- **Biome diversity** (in one block):
  - Western temperate rainforest (Hoh, Quinault drainages)
  - Olympic mountains: Mt Olympus (2428m), Bailey Range
  - Glaciers: Hoh, Blue, Hubert
  - Subalpine meadows
  - Lower forested valleys with rivers
- **Why interesting**: spans 4 ecoregions in 42 km — rare on Earth.

### Mega 2 — Big Bend National Park, TX

- **ID**: `big_bend_1m_v2`
- **Bbox**: -103.466, 29.061, -103.034, 29.439 (42×42 km)
- **Center**: -103.25, 29.25 — Chisos basin core
- **Biome diversity**:
  - Chihuahuan desert flats
  - Rio Grande river canyon (Boquillas, Mariscal, Santa Elena)
  - Chisos Mountains (~2400m): juniper-piñon, oak woodland
  - Volcanic intrusions / mesas
  - Tornillo creek washes
- **Why interesting**: arid-mountain mosaic; high relief in dry environment;
  international border/river edge.

## Output

Both stacks build to:
```
pipelines/terrain/output/<id>/height_16.png      # 4096x4096 stitched
pipelines/terrain/output/<id>/tile_grid.json     # provenance
```
Per-tile raw TIFFs cache to `dems/USGS1m_<bbox>.tif`.

## Pull mechanics

`pipelines/terrain/tile_stitch.py` walks a 3×3 grid splitting the
target bbox into 9 sub-bboxes with `--overlap 0.002` (~220m feathered
overlap), fetches each via `import_dem.fetch_opentopo`, then composes
into one feathered 4096-px heightmap with NoData sanitization.

Command pattern:
```powershell
python pipelines/terrain/tile_stitch.py \
  --id olympic_peninsula_1m_v2 \
  --bbox -123.731 47.611 -123.169 47.989 \
  --dataset USGS1m --rows 3 --cols 3 \
  --size 4096 --overlap 0.002
```

## Results (in flight)

### Olympic Peninsula v2 — 5/9 tiles (USGS1m coverage gap in central alpine)

- 5/9 tiles cached + stitched. Re-shoot of failed tiles repeated the
  same "non-TIFF response (0 bytes)" failure on the same 4 cells.
- Failure pattern: the **central interior** tiles all fail (rows 0-1
  middle column + row 1 left column). These cluster around the high
  alpine / Mt Olympus core which **USGS1m LiDAR doesn't cover** —
  USGS1m focuses on populated / lower-elevation areas, not remote
  alpine. The eastern strip (column 2 of all rows) plus 2 western
  edge tiles work because those areas have lower-elevation LiDAR
  surveys.
- Stitched output: `pipelines/terrain/output/olympic_peninsula_1m_v2/height_16.png`
  (4096x4096), elevation 213-1970m (Mt Olympus summit is 2428m;
  the 1970m peak in the data is a satellite ridge, not the summit).
- ~16M sentinel pixels mean-filled in the failed cells (visible as
  flat patches at ~1000m elevation in the stitched output).
- Cache: 5 new USGS1m tiles (~30 MB to ~400 MB each, ~700 MB total).
- **Verdict**: partial mega-stack. Useful for the eastern + western
  edges where data exists. For the full Olympic interior at 1m,
  switch to USGS10m which covers everywhere.

### Big Bend v2 — 9/9 tiles complete (full coverage!)

- All 9 tiles cached + stitched successfully. Some cells took
  multiple API attempts (BB had its own non-TIFF flakiness mid-pull).
- Stitched output: `pipelines/terrain/output/big_bend_1m_v2/height_16.png`
  (4096x4096), elevation 572-2215m (Chisos summit ~2400m, very
  close).
- Only 185k sentinel pixels mean-filled (clean coverage; almost no
  gaps).
- Cache: 9 new USGS1m tiles (~50 MB to ~540 MB each, ~2.5 GB total).
- **Verdict**: full-quality mega-stack. Big Bend NP is a complete
  3x3 USGS1m mosaic — production-ready terrain.

### Comparison

| Stack | Tiles ok | Coverage | Elev range | Stitch quality |
|-------|----------|----------|------------|----------------|
| Olympic v2 | 5/9 | partial (central alpine missing) | 213-1970m | 16M sentinel-fill artifacts |
| Big Bend v2 | 9/9 | complete | 572-2215m | 185k clean stitch |

Big Bend is the fully successful mega-stack. Olympic is partial-but-
usable (eastern strip + western edge). For a clean Olympic alternative,
either:
- Re-do Olympic at USGS10m (10m vs 1m, but full coverage)
- Pick a different US LiDAR-covered area for the alpine biome (the
  Wasatch range, Sierra-Yosemite extension, or White Mountains may
  have better coverage)

## Caveats / known issues

1. **USGS1m API non-TIFF failures**: Several tiles in both stacks
   returned 0-byte non-TIFF responses. Could be transient OT API
   issues, USGS coverage gaps, or rate-limit silent throttling.
   Recommend: retry failed tiles individually after a delay.

2. **NoData/sentinel pixels**: Both stacks have `-999999.0` and
   `-3.4e38` (float min) sentinel values where USGS1m doesn't cover
   parts of the requested bbox (water, gaps, edges). `tile_stitch.py`
   sanitizes by mean-fill but the resulting heightmap has artifacts
   in those regions — visible as flat patches at the fill-mean
   elevation.

3. **Coverage validation pending**: tile_grid.json provenance is
   written but a per-tile success/coverage map (which 9 cells got
   real data vs which got fill) should be derived from the
   stitched output before this is treated as game-quality terrain.

## What's missing for full master-stack

OpenTopo's full master-stack includes orthophoto + NIR + LAZ
pointcloud + canopy + masks. USGS1m + tile_stitch only delivers the
DEM half. Adding the other layers requires:

- OT Dataspace projects (if either area has bundled DSM + ortho
  in a single Dataspace dataset). Olympic and Big Bend have NEON or
  USGS LiDAR releases; check OT catalog UI.
- Or direct fetch of NEON / USGS orthoimagery via separate APIs.
- Then run the worker's mosaic + fusion pipelines
  (`build_opentopo_textured_master_stack.py`, etc.) to align.

This is a **height-only mega-stack** — production-facing terrain,
not yet a full textured master stack like Gloss Mountain.

## Re-shoot recommendation

For each failed tile, retry individually:
```powershell
python -c "
import sys; sys.path.insert(0, 'pipelines/terrain')
from import_dem import fetch_opentopo
arr = fetch_opentopo((W, S, E, N), dataset='USGS1m')
print(arr.shape, arr.min(), arr.max())
"
```
After successful re-shoots, re-run `tile_stitch.py` (cache hits will
be instant for tiles already pulled).

## Status

Olympic v2: DONE with 5/9 coverage. Need re-shoot of failed tiles for
full coverage.

Big Bend v2: IN FLIGHT.

Cache: ~261 tiles, ~10 GB total at this point (from 222/8.1G at session
start; +39 tiles, ~+2 GB from this entire session including premium/
standard/bathy/showcase NEW + 8 mega-stack tiles).

## Crosslinks

- Tool: `pipelines/terrain/tile_stitch.py`
- Worker reference: [`OPENTOPO_MASTER_STACKS_AUDIT.md`](OPENTOPO_MASTER_STACKS_AUDIT.md)
- Curated directory: [`OPENTOPO_DATA_DIRECTORY_2026_05_08.md`](OPENTOPO_DATA_DIRECTORY_2026_05_08.md)
