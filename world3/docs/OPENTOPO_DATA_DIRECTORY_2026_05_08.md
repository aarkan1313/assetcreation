# OpenTopo Data Directory + Curation Plan — 2026-05-08

**Goal**: a curated ~30 GB DEM library spanning a healthy mix of
biomes, continents, and famous + non-famous locations. No buildings
(per user 2026-05-08). Mostly natural-terrain study material, used
to feed the world3 pipeline (terrain → kit → splat → chunks).

This doc is BOTH a directory of what we have AND a curation plan for
what to pull next.

---

## Existing infrastructure (don't rebuild)

| Asset | Path | Status |
|-------|------|--------|
| Wishlist (172 regions × 6 tiers) | `art_lab/biomes/data_wishlist.json` | Mature; ~50 GB at full pull |
| Bulk fetcher | `pipelines/terrain/bulk_pull.py` | Walks the wishlist; cache-aware; rate-limit-aware |
| Single-bbox fetcher | `pipelines/terrain/import_dem.py` | One-shot; 23 datasets supported |
| Tile-stitch | `pipelines/terrain/tile_stitch.py` | Multi-call composites for huge regions |
| Catalog search (no-quota) | `pipelines/terrain/catalog_search.py` | Confirms availability before fetch |
| Regional STAC bypass | `pipelines/terrain/fetch_regional_stac.py` | LINZ/Arctic/REMA via providers |
| Mystery sampler | `pipelines/terrain/mystery_sampler.py` | 300 procedural worldwide bboxes |
| Call ledger | `~/.opentopo_calls.jsonl` | 200 historical calls logged |
| Cache | `dems/` | 222 TIFFs / 8.1 GB |

**The wishlist + bulk_pull is the spine.** This doc curates what to
pull; the existing tools execute the pulls.

---

## What's in the cache today (8.1 GB / 222 tiles)

By dataset:

| Dataset | Count | Notes |
|---------|------:|-------|
| COP30 (30m global) | 131 | Bulk standard-tier coverage |
| AW3D30 (30m global) | 29 | Alternate 30m |
| USGS1m (US LiDAR) | 28 | Showcase tier — high detail |
| GEBCOIceTopo (450m) | 14 | Bathymetric |
| USGS10m (US 10m) | 13 | Mid-detail US |
| Other (SRTM15Plus / REMA / LINZ / ArcticDEM / CA_MRDEM) | 6 | Sparse spot pulls |

**Coverage observation**: heavy on COP30 + US LiDAR. Sparse on
LINZ/Arctic/REMA — those are gated either by the OT API's
`/globaldem` endpoint rejecting some datasets or by Pro tier.

---

## Wishlist coverage analysis

172 regions across 6 tiers:

| Tier | Count | Default dataset | Use |
|------|------:|-----------------|-----|
| stitched | 10 | USGS1m | Multi-tile huge regions (Yosemite full, Bryce, etc.) |
| highres_open | 15 | COP30 | LINZ/Arctic/REMA (mostly blocked via API) + USGS10m |
| showcase | 20 | USGS1m | Single-bbox high-detail flagship |
| premium | 50 | COP30 | Large-bbox standard 30m |
| standard | 62 | COP30 | Medium-bbox standard 30m |
| bathymetric | 15 | COP30 | GEBCOIceTopo seafloor |

### Top tags in wishlist (current bias)

```
alpine        19    (heavy mountain emphasis)
glacier       11
volcano       10
high-altitude  9
fjord          6
caldera        5
spire          5
volcanic-island 5
canyon         4
rainforest     4
glacial        4
monolith       4
```

### Continent coverage (rough lat/lon bucketing)

```
north_america   32
asia            29
europe          21
africa          20
arctic          19
south_america   17
oceania         15
antarctica       4
```

### Coverage gaps in the current wishlist

The wishlist tilts **dramatic / vertical / alpine**. Underweight in:

- **Flat biomes**: savanna, plains, prairies, steppes, tundra-flat,
  river-deltas. World3 has a `grassland` kit; we have only one
  region tagged for it (Tibetan Plateau).
- **Coastal mixed**: barrier islands, estuaries, coral atolls, reefs.
  Bathymetric tier covers seafloor but not the land-meets-sea edge.
- **Forested low-relief**: taiga, boreal forest, temperate rainforest
  flat areas. World3 has a `temperate_forest` kit; one wishlist hit
  (Olympic Peninsula).
- **Wetlands**: mangroves, peat bogs, swamps. Visually distinct,
  not represented.
- **Drylands non-canyon**: dune fields (Sahara, Namib), badlands
  (variations), salt-pan flats. We have a few canyons + Death
  Valley basin; missing pure dunes.
- **Africa beyond canyon/desert**: Serengeti is in `regions.json`
  but not in the wishlist. Madagascar, Ethiopian highlands, Atlas
  mountains all absent.
- **South-east Asia mixed**: Indonesia volcanic chains, Borneo
  rainforest, Philippines reefs.

These gaps are why grassland/temperate-forest regions get assigned
generic OpenTopo bboxes when they're rendered — the wishlist doesn't
have a curated entry for them.

---

## Storage plan: ~30 GB target across a healthy mix

Free on `D:\` as of 2026-05-08: **191 GB** (81% used). 30 GB target
is comfortable.

Allocate roughly:

| Category | Budget | Purpose |
|----------|------:|---------|
| Showcase (USGS1m, single-bbox) | 4 GB | High-detail famous landmarks for hero captures |
| Stitched (USGS1m, multi-tile) | 6 GB | Full-region coverage of Yosemite/Bryce/Grand Canyon-class |
| Premium (COP30 large-bbox) | 8 GB | Bulk continent-scale variety |
| Standard (COP30 medium) | 5 GB | Medium-scale specific places |
| Bathymetric (GEBCO) | 2 GB | Coastal + seafloor for any aquatic kit work |
| Highres-open (USGS10m + Arctic/REMA/LINZ where reachable) | 3 GB | Mid-detail polar + NZ |
| Mystery (procedural worldwide) | 2 GB | "What does an unknown place look like" sampler |

**Total: ~30 GB**, leaving ~160 GB free on D for working files.

---

## Curated directory: 50 priority pulls (mix-balanced)

This is the **selection** to curate from the 172-region wishlist
plus gap-fills (entries marked NEW need to be added to the wishlist).

Goal: a **healthy mix** — not all alpine, not all famous. Mostly
famous (~60%) so the renders read as recognizable, with ~40% lesser-
known places to test that the pipeline doesn't only work on
photogenic outliers.

### Tier 1 — flagship hero captures (8 regions, ~6 GB)

Already-pulled or wishlist-priority:

| Region | Tier | Dataset | Status | Why |
|--------|------|---------|--------|-----|
| Yosemite Valley | showcase | USGS1m | partial | Granite cathedrals — hero alpine |
| Grand Canyon inner | showcase | USGS1m | wishlist | Vertical-mile canyon — hero canyon |
| Bryce Hoodoos | showcase | USGS1m | partial | Spire/pinnacle — hero spired |
| Death Valley basin | stitched | USGS10m | wishlist | Below-sea + salt-flat — hero arid |
| Mt St Helens crater | showcase | USGS1m | wishlist | Active volcano — hero volcanic |
| Crater Lake | showcase | USGS1m | wishlist | Caldera — hero circular |
| Tetons (existing scene) | premium | COP30 | DONE | Already integrated into world3 demos |
| Half Dome | showcase | USGS1m | DONE | Verified test pull |

### Tier 2 — biome variety (15 regions, ~10 GB)

Filling biome-coverage gaps. Mix of famous + non-famous.

| Region | Biome category | Dataset | Tier | Status |
|--------|----------------|---------|------|--------|
| Serengeti plains (Tanzania) | savanna/grassland | COP30 | premium | NEW — gap fill |
| Tibetan plateau (high steppe) | high-altitude grassland | COP30 | premium | exists in regions.json |
| Great Plains (Nebraska/Kansas) | temperate grassland | COP30 | standard | NEW — gap fill |
| Pantanal (Brazil) | wetland/floodplain | COP30 | standard | NEW — gap fill |
| Okavango Delta (Botswana) | inland delta | COP30 | premium | NEW |
| Namib dunes | dune field | COP30 | premium | wishlist |
| Sahara erg (Algeria/Libya) | dune field | COP30 | premium | wishlist |
| Alaskan boreal interior | taiga | COP30 | standard | NEW |
| Yukon boreal | taiga | COP30 | standard | NEW |
| Olympic Peninsula | temperate rainforest | USGS10m + COP30 | stitched | wishlist |
| Madagascar central | tropical highlands | COP30 | premium | NEW |
| Ethiopian highlands | high-altitude grassland | COP30 | premium | NEW |
| California chaparral | mediterranean shrub | COP30 | premium | exists in regions.json |
| Borneo rainforest | tropical rainforest | COP30 | standard | NEW |
| Patagonian steppe (Argentina) | cold dry grassland | COP30 | premium | NEW |

### Tier 3 — extreme + unusual (10 regions, ~6 GB)

Stress-test material the pipeline can show off. Polar, mars-analog,
volcanic islands, fjords, high-altitude.

| Region | Why interesting | Dataset | Status |
|--------|-----------------|---------|--------|
| Norwegian fjord network (full) | dramatic glacial carving | AW3D30 | wishlist (stitched) |
| Iceland Eyjafjallajökull | active volcano | ArcticDEM10m | wishlist |
| Greenland Disko Bay edge | tundra+ice transition | ArcticDEM10m | wishlist |
| Antarctica Dry Valleys | Mars analog | REMA10m | wishlist |
| New Zealand Milford Sound | fjord at LiDAR | LINZ1m_DTM | wishlist |
| Mt Cook / Aoraki | NZ alpine | LINZ1m_DTM | wishlist |
| Aconcagua massif | high-altitude S. America | COP30 | wishlist (stitched) |
| Annapurna circuit | Himalayan high-altitude | COP30 | NEW |
| Mt Fuji | symmetric stratovolcano | AW3D30 | NEW |
| Atacama plateau | high desert | COP30 | NEW |

### Tier 4 — coastal + bathymetric (8 regions, ~3 GB)

Land-meets-sea edge cases. For any future aquatic kit work
(Track A bathymetry from `FUTURE_WORLD_SOURCES`).

| Region | Type | Dataset | Status |
|--------|------|---------|--------|
| Maldives atoll | coral atoll | GEBCOIceTopo + COP30 | NEW |
| Great Barrier Reef shelf | reef shelf | GEBCOIceTopo | wishlist |
| Norwegian fjord coast (with bathy) | fjord+sea | AW3D30 + GEBCO | NEW (composite) |
| Hawaiian archipelago | volcanic islands | AW3D30 + GEBCO | wishlist |
| Bay of Fundy | macro-tide coast | COP30 + GEBCO | NEW |
| Outer Banks NC | barrier island | USGS10m + GEBCO | NEW |
| Indonesia volcanic chain (Bali/Lombok) | volcanic island chain | COP30 + GEBCO | NEW |
| California Big Sur coast | cliff coast | USGS10m + GEBCO | NEW |

### Tier 5 — non-famous variety (9 regions, ~5 GB)

Lesser-known places to validate the pipeline doesn't only work on
hero locations.

| Region | Country | Why | Dataset |
|--------|---------|-----|---------|
| Drakensberg escarpment | South Africa | Lesser-known cliff/savanna mix | COP30 |
| Bolivian Altiplano (general) | Bolivia | Salt-flat ↔ mountain | COP30 |
| Lena River delta | Russia | Arctic delta | COP30 |
| Mekong delta | Vietnam | Tropical delta | COP30 |
| Caucasus mountains | Georgia/Russia | Lesser-known alpine | COP30 |
| Tien Shan (Kyrgyzstan) | Kyrgyzstan | Asian alpine, off-radar | COP30 |
| Japanese Alps | Japan | Lesser-known mountain | AW3D30 |
| Australian outback (MacDonnell ranges) | Australia | Arid mountain | COP30 |
| Faroe Islands | Faroe | Volcanic North Atlantic | AW3D30 |

---

## How to execute the pull

### Step 1 — gap-fill the wishlist

For NEW entries above, append to `art_lab/biomes/data_wishlist.json`
in the appropriate tier. Each entry needs `id`, `bbox`,
`dataset`, `tags`, `fantasy_styles`, `tagline`. Use existing
entries as template.

(Done in a separate commit that precedes the pull.)

### Step 2 — pull by tier

```powershell
# Bulk-pull priority tiers (uses OT+ quota; budget ~400/24h on Pro)
$env:OPENTOPOGRAPHY_API_KEY = [Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY", "User")

# 1 — Plan first (no quota)
python pipelines/terrain/bulk_pull.py --tier showcase --dry-run
python pipelines/terrain/bulk_pull.py --tier premium --dry-run
python pipelines/terrain/bulk_pull.py --tier standard --dry-run

# 2 — Execute (cache-aware, resumable)
python pipelines/terrain/bulk_pull.py --tier showcase
python pipelines/terrain/bulk_pull.py --tier premium
python pipelines/terrain/bulk_pull.py --tier standard
python pipelines/terrain/bulk_pull.py --tier highres_open
python pipelines/terrain/bulk_pull.py --tier bathymetric

# 3 — Stitched (per-region, more careful)
python pipelines/terrain/tile_stitch.py --id yosemite_full_1m ...
# (see the tagline + bbox + rows/cols in each stitched entry)
```

### Step 3 — verify

After pull, verify against the directory:

```powershell
# How big is the cache now?
du -sh dems/

# What did we get?
ls dems/ | sed 's/_[+-].*//' | sort | uniq -c
```

Expected ~30 GB total cache after Tier 1–4 pulls.

### Step 4 — index for world3 consumption

Each pulled DEM should produce a `regions.json` entry in world3 so
it's pickable for kit binding + region gallery. If 50 new pulls
land, the regions.json gets ~50 new entries. This is a separate
step from the raw pull; deferred until first M5+ session that wants
to use specific regions.

---

## Quality / coverage rule of thumb

After pull, the dataset breakdown should look roughly like:

```
COP30 (global 30m)        ~150-180 tiles  (bulk variety)
USGS1m (US LiDAR)         ~30-40 tiles    (showcase HD)
USGS10m (US 10m)          ~15-25 tiles    (mid-detail US)
AW3D30 (alternate 30m)    ~30-40 tiles    (non-US 30m)
GEBCOIceTopo (bathy 450m) ~15-20 tiles    (coast+seafloor)
ArcticDEM10m / REMA10m / LINZ1m_DTM  ~5-10 each   (where reachable)
SRTM15Plus / others       ~5 tiles        (sanity backstop)
```

If COP30 is dominating >85% of the cache, the mix isn't diverse
enough — pull more US-LiDAR + bathy.

---

## What this enables

- **OpenTopo worker handoffs** can reference a known curated set
  ("apply M2 transition on regions X, Y, Z") instead of vague
  "real DEM."
- **Region gallery captures** (Phase D / E) get more biome variety
  for free — current 7-region gallery becomes a 30-50 region gallery
  trivially.
- **Test bench for M3 chunk-size sweep** — swept against multiple
  DEM types (alpine vs flat savanna vs canyon) instead of just
  Tetons. Catches biome-specific failures.
- **NLCD-pairing readiness** (post-M5 Track A): each US region in
  the cache pairs with NLCD coverage. Ready for splat-mask
  experiments without an extra fetch.
- **Future bathymetry work**: Tier 4 coastal regions are the
  starter set when we want to extend "terrain" to "world."

---

## Open decisions

- **Pull cadence**: one big session vs. several smaller sessions?
  Recommend several smaller — easier to spot rate-limit issues +
  the call ledger captures progress.
- **NLCD-paired regions**: should US regions in Tier 1–2 also pull
  matching NLCD land-cover during the same session? Or defer until
  Track A actually starts? **Recommend defer** — keep this directory
  scoped to terrain only; NLCD is a parallel layer.
- **Worker handoff for the pull?** OpenTopo chat owns real-data
  sourcing per the operating model. Pulling 30 GB is squarely in
  their domain. **Recommend handoff once this directory is approved
  by the user.**

---

## Status

- **Doc**: drafted 2026-05-08, awaiting user review.
- **NEW wishlist entries**: not yet added.
- **Pulls**: not yet executed.

This doc is the **plan + directory**. Pulls happen via the existing
bulk_pull tooling once the user approves the curation.

---

## Crosslinks

- Wishlist source: [`art_lab/biomes/data_wishlist.json`](../../art_lab/biomes/data_wishlist.json)
- Bulk fetcher: `pipelines/terrain/bulk_pull.py`
- Cache: `D:/assets/dems/`
- Worker runbook: [`OPENTOPO_GUIDE.md`](OPENTOPO_GUIDE.md),
  [`OPENTOPO_DATA_TYPES.md`](OPENTOPO_DATA_TYPES.md)
- Future bathymetry context: [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md)

---

## Change log

- **2026-05-08**: Initial directory + curation plan. 50 priority
  regions across 5 tiers covering biome + continent + famous/non-
  famous mix targeting ~30 GB cache total.
