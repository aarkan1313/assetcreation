# Mega-Stack Pull Queue — 2026-05-09

User asked for "all we can, largest size, ideally chunks of 9 at a time /
a large contiguous area for each pull. We can use lower res 30m and 10m
too — they look just as good at iso/topdown."

This is the tracker for the **63-mega-stack pull queue** kicked off
2026-05-09 ~04:51 EDT.

## Queue size + breakdown

74 total stitched mega-stack entries in `art_lab/biomes/data_wishlist.json`.

| Status at queue start | Count |
|-----------------------|------:|
| Already DONE (pre-existing stitched output) | 1 (ethiopian_simiens — others have stitched but not in priority list) |
| In priority queue | 63 |

### Priority order

1. **USGS1m hi-res** (16 entries, US 1m LiDAR, 42×42 km each):
   sequoia, shenandoah, great_basin, haleakala, north_cascades,
   lassen, adirondacks, guadalupe_peak, kilauea, smoky_mtns_north,
   rocky_mtn_estes, wind_river, yellowstone_grand, glacier_park,
   white_mtns, olympic_lower

2. **NZ LINZ1m** (3 entries, 42×42 km each):
   nz_aoraki, nz_milford, nz_taranaki

3. **Foreign biome-gap COP30** (12 entries, 70×70 km tiles = 210×210 km
   regions): kilimanjaro_kenya, atlas_morocco, tasmanian, kamchatka,
   pamirs, mt_roraima, iguazu, great_dividing_au, halong_bay, guilin,
   sundarbans, galapagos_isabela

4. **US 10m regional** (8 entries, 50×50 km tiles = 150×150 km):
   sierra_nevada, wasatch, olympic_full, white_mtns_full, cascade_volcanic,
   san_juan_co, ozarks, blue_ridge

5. **Large 30m regional** (17 entries, 165×165 km tiles = 500×500 km):
   alps_central, andes_southern, himalaya_central, japan_alps,
   kilimanjaro_region, saharan_atlas_region, patagonia_glacier,
   scottish_highlands, iceland_central, alaska_range, siberian_baikal,
   nz_south_alps, ethiopian_simiens, pyrenees, carpathians, kunlun,
   altai

6. **AW3D30 alternates** (3 entries):
   norwegian_fjord, philippines_volcanic, indonesia_volcano_chain

7. **GEBCO bathymetric** (5 entries):
   hawaiian_chain, great_barrier_reef, maldives, indonesia_sunda,
   galapagos_bathy

## How to monitor

Live status JSON: `D:/d/tmp/bulk_pull_logs/megastack_status.json`
(written by the runner after each entry completes)

Per-entry logs: `D:/d/tmp/bulk_pull_logs/megastack_<id>.log`

Runner log: `/d/tmp/bulk_pull_logs/megastack_runner.log`

Snapshot one-liner:

```powershell
python -c "import json; d=json.load(open('D:/d/tmp/bulk_pull_logs/megastack_status.json')); print(f'DONE={sum(1 for v in d.values() if v.get(\"status\")==\"DONE\")} INCOMPLETE={sum(1 for v in d.values() if v.get(\"status\")==\"INCOMPLETE\")}/{len(d)}')"
```

## Tools

- **Driver**: `pipelines/terrain/pull_megastack_queue.py` —
  walks priority list, calls tile_stitch.py per entry, writes status
  JSON. Idempotent: skips entries whose stitched output already
  exists.

- **Tracker**: `pipelines/terrain/megastack_tracker.py` — scans
  the wishlist + cache + output dirs and prints DONE/PARTIAL/NEW
  status per entry. Run anytime.

## Expected duration

Rough math:
- USGS1m: ~9 tiles × ~30-90s each = 5-15 min/stack. 19 stacks at ~1m
  resolution = 95-285 minutes (~2-5 hours).
- USGS10m: ~9 tiles × ~10s each = 1-2 min/stack. 8 stacks = ~15 min.
- COP30/AW3D30: ~9 tiles × ~5s each + 0.5s throttle = ~1 min/stack.
  20 stacks = ~20 min.
- GEBCO: trivially fast (~10s/stack). 5 stacks = ~1 min.

Total: ~3-6 hours of API time, depending on how many failed tile
retries we hit. Some 1m stacks will fail entirely on coverage gaps
(remote alpine — same pattern as Olympic).

## Coverage caveats observed

- **USGS1m has gaps in remote alpine**: Olympic interior (5/9), and
  initial test on Sequoia (0/9 — likely all-alpine bbox) confirmed
  this. Solution: pair each USGS1m stack with a USGS10m fallback at
  larger area. Several 10m stacks in this queue serve that purpose.
- Some `non-TIFF` failures are transient API hiccups; some are real
  coverage gaps. The runner doesn't distinguish.

## Outcome categories (post-run)

When the queue finishes, each entry will be one of:

- **DONE 9/9**: full success, production-ready stitched output.
- **DONE partial (e.g. 5/9)**: stitched output exists but with
  sentinel-fill in failed cells. Useful for the cells that worked.
- **INCOMPLETE 0/9**: API rejected the entire bbox (coverage gap or
  rate limit). No stitched output.
- **TIMEOUT**: the runner gave up after 40 min on one entry.

A post-run analysis pass will tally results, identify patterns, and
suggest re-shoots / fallback datasets for incomplete stacks.

## Status as of 04:55 EDT

- 1 DONE (ethiopian_simiens, preexisting)
- 1 INCOMPLETE (sequoia_high_country_1m — 0/9, alpine coverage gap)
- 1 in flight (shenandoah_full_1m, 2/9 cached so far)
- 60 queued
