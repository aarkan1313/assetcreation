# OpenTopography API — Full Reference

Captured 2026-05-06 from the official Swagger doc. Source of truth for what we *could* fetch, what limits apply, and what tiers unlock what.

> This is a living reference; if OpenTopo changes their API, update this file. Our pipeline reads dataset names + limits from this doc, not from training data.

---

## Endpoints

### `/globaldem` — Global topography & bathymetry (most-used)

Parameters: `demtype`, `south`, `north`, `west`, `east`, `outputFormat`, `API_Key`.

Available datasets:

| `demtype` | Description | Resolution | Coverage | bbox limit (km²) | Notes |
|---|---|---|---|---|---|
| `SRTMGL3` | SRTM Global 90m | 90m | 60S–60N | 4,050,000 | Fastest, lowest res |
| `SRTMGL1` | SRTM Global 30m | 30m | 60S–60N | 450,000 | 30m SRTM, some voids |
| `SRTMGL1_E` | SRTM 30m Ellipsoidal | 30m | 60S–60N | 450,000 | Ellipsoidal heights — *not for game terrain*, use SRTMGL1 instead |
| `AW3D30` | ALOS World 3D 30m | 30m | 82S–82N | 450,000 | Best high-latitude coverage |
| `AW3D30_E` | ALOS 30m Ellipsoidal | 30m | 82S–82N | 450,000 | Same caveat as SRTMGL1_E |
| `COP30` | Copernicus DSM 30m | 30m | 90S–90N | 450,000 | **Default** — cleanest 30m global |
| `COP90` | Copernicus DSM 90m | 90m | 90S–90N | 4,050,000 | Larger area, 90m |
| `NASADEM` | SRTM reprocessed | 30m | 60S–60N | 450,000 | Fewer voids than SRTMGL1 |
| `EU_DTM` | Europe DTM | 30m | Europe only | 450,000 | Best European resolution |
| `SRTM15Plus` | Global Bathy+Topo SRTM15+ V2.1 | 500m | Global ocean+land | **125,000,000** | Whole-region bathymetric basemap |
| `GEBCOIceTopo` | GEBCO 2023 ice surface | 500m | Global | 125,000,000 | Land + ice (ice-surface elevation) |
| `GEBCOSubIceTopo` | GEBCO 2023 sub-ice bedrock | 500m | Global | 125,000,000 | Bedrock under ice (Antarctica, Greenland) |
| `GEDI_L3` | DTM 1000m | 1km | Global | **500,000,000** | Canopy-corrected, very low-res; whole-continent bboxes |
| `CA_MRDEM_DSM` | Canada MRDEM Surface | 30m | Canada | 450,000 | Canadian DSM (with trees) |
| `CA_MRDEM_DTM` | Canada MRDEM Terrain | 30m | Canada | 450,000 | Canadian DTM (bare earth) |

Output formats: `GTiff` (default, recommended), `AAIGrid` (text), `HFA` (Erdas .img).

### `/usgsdem` — USGS 3DEP Raster (US only, much higher resolution)

Parameters: `datasetName`, `south`, `north`, `west`, `east`, `outputFormat`, `API_Key`.

| `datasetName` | Description | Resolution | bbox limit (km²) | Access |
|---|---|---|---|---|
| `USGS30m` | 1 arc-second DEM | 30m | 225,000 | Open |
| `USGS10m` | 1/3 arc-second DEM | ~10m | 25,000 | Open |
| `USGS1m` | 1m LiDAR-derived DEM | **1m** | **250** | **OT+ subscription, Academic, or Enterprise** |

Notes:
- `USGS10m` is the high-res option available on the free tier (no Pro needed).
- `USGS1m` is **unlocked by OT+ subscription** (verified 2026-05-06 — Half Dome pulled at 1712×1717 px of bare-earth granite). Also unlocked by Academic verification (.edu) or Enterprise key. Free non-academic tier does NOT include 1m. **Earlier doc text saying "OT+ does NOT unlock 1m" was wrong** — corrected per the official OT+ tier matrix.
- Service relies on USGS infrastructure — sometimes flaky.

### `/otCatalog` — Bbox-based dataset search

Parameters: `productFormat` (PointCloud or Raster), `minx`, `miny`, `maxx`, `maxy` (or `polygon` WKT), `detail`, `outputFormat`, `include_federated`.

Use case: "What datasets are available for this bbox?" Returns list of all hosted topography datasets covering the area — including **point clouds, federated USGS 3DEP catalog**, and custom regional datasets we wouldn't know about by name.

Example: search Bryce Canyon bbox → returns SRTMGL1, COP30, AW3D30, NASADEM, USGS30m, USGS10m, USGS1m (OT+ unlocks API access), plus any LiDAR point cloud campaigns covering that area.

This is how we discover what we *could* download for any location, instead of guessing dataset names.

### Other access methods (not yet wired in our pipeline)

- **STAC Catalog** — SpatioTemporal Asset Catalog, machine-readable index of all OpenTopo raster DEMs. Notebooks at OT's GitHub. Useful if we wanted to walk the entire raster catalog without per-region API calls.
- **CSW endpoint** — `https://portal.opentopography.org/geoportal/csw` — OGC standard catalog browsing. Returns metadata as XML/RSS/etc. Not needed for our use case.
- **GMRT** — Global Multi-Resolution Topography, separate service at `gmrt.org`. Multi-resolution DEM; we don't need to wire this since GEBCO covers the same use case for us.
- **NASA ICESat-2** — laser altimetry data via OpenAltimetry. Different problem space (sea ice height, etc).

---

## The full data catalog (3944 datasets total)

The Swagger API doc only lists `/globaldem` and `/usgsdem` datasets. The real OpenTopo catalog is much bigger. Per the OT data-catalog page (`portal.opentopography.org/dataCatalog`):

### Global & Regional DEM (20 datasets)

These are the 1-button-download global/regional rasters. The Swagger spec covers most but **misses several major ones** that are also `/globaldem`-fetchable with the right `demtype`:

| Catalog Name | API name (likely) | Resolution | Coverage | Notes |
|---|---|---|---|---|
| New Zealand Lidar 1 Meter DEM | `LINZ1m_DTM` / `LINZ1m_DSM` | **1m** | Full New Zealand | Open via nz-elevation S3, NOT via /globaldem. See `fetch_regional_stac.py`. |
| Reference Elevation Model of Antarctica (REMA) | `REMA10m` / `REMA32m` | 10m / 32m | Antarctica | Open via PGC STAC + s3://pgc-opendata-dems/. NOT via /globaldem. |
| ArcticDEM | `ArcticDEM10m` / `ArcticDEM32m` | 10m / 32m | Arctic (>50°N) | Open via PGC STAC. NOT via /globaldem. (No-underscore names matter.) |
| Medium Resolution DEM of Canada | `CA_MRDEM_DSM` / `CA_MRDEM_DTM` | 30m | Canada | DSM (with vegetation) and DTM (bare earth) |
| GEBCO Global Bathymetry | `GEBCOIceTopo`, `GEBCOSubIceTopo` | 500m | Global | Already in our pipeline |
| GEDI L3 Gridded Land Surface Metrics | `GEDI_L3` | 1km | Global | Canopy-corrected DTM |
| USGS 1 arc-second DEM | `USGS30m` | 30m | USA | `/usgsdem` endpoint |
| USGS 1/3 arc-second DEM | `USGS10m` | 10m | USA | `/usgsdem` endpoint |
| Continental Europe DTM | `EU_DTM` | 30m | Europe | We have it |
| Copernicus 30m DSM | `COP30` | 30m | Global 90S-90N | Default global |
| Copernicus 90m DSM | `COP90` | 90m | Global 90S-90N | Bigger bbox limit |
| SRTM (GL1, GL3, +Ellipsoidal variants) | `SRTMGL1`, `SRTMGL3`, etc | 30m / 90m | 60S-60N | Legacy |
| ALOS World 3D | `AW3D30`, `AW3D30_E` | 30m | 82S-82N | High-latitude friendly |
| NASADEM | `NASADEM` | 30m | 60S-60N | SRTM reprocessed |
| SRTM15+ V2.1 | `SRTM15Plus` | 500m | Global, ocean+land | Massive bbox limit |

**The ones we wired up that don't need OT at all:**
- **LINZ1m** (NZ 1m DEM/DSM) — open via `s3://nz-elevation/` (CC-BY-4.0)
- **ArcticDEM** (2m / 10m / 32m) — open via `s3://pgc-opendata-dems/arcticdem/`
- **REMA** (2m / 10m / 32m) — open via `s3://pgc-opendata-dems/rema/`

### Regional rasters: SOLVED 2026-05-06 — bypass OpenTopography entirely

Tested 2026-05-06: `LINZ1m_DTM`, `ArcticDEM10m`, `REMA10m` all return **400 from `/API/globaldem`** regardless of name spelling, EPSG hint, or whether the bbox is in lat/lon or projected coords. The OpenTopography `/rasterSubmit` POST endpoint (the form action on `/arcticDem` etc) requires browser session auth — it's a job-queue UI, not a programmatic API.

**The actual path:** OT mirrors these but the original providers all publish them as Cloud-Optimized GeoTIFFs (COGs) on public AWS S3 with STAC indexes. No API key, no quota, no auth — and we range-read just the bbox we want.

| Dataset | STAC | S3 Bucket | Native EPSG |
|---|---|---|---|
| ArcticDEM 2m / 10m / 32m | `https://stac.pgc.umn.edu/api/v1/` | `s3://pgc-opendata-dems/arcticdem/mosaics/` (us-west-2) | 3413 (Polar North) |
| REMA 2m / 10m / 32m | `https://stac.pgc.umn.edu/api/v1/` | `s3://pgc-opendata-dems/rema/mosaics/` (us-west-2) | 3031 (Polar South) |
| EarthDEM 2m strips | `https://stac.pgc.umn.edu/api/v1/` | `s3://pgc-opendata-dems/earthdem/` (us-west-2) | varies |
| LINZ NZ 1m DEM/DSM | static catalog at `https://nz-elevation.s3-ap-southeast-2.amazonaws.com/catalog.json` | `s3://nz-elevation/` (ap-southeast-2) | 2193 (NZTM) |

**Implementation:** [`../../pipelines/terrain/fetch_regional_stac.py`](../../pipelines/terrain/fetch_regional_stac.py) implements `fetch_pgc()` (ArcticDEM/REMA via STAC bbox-search → multi-tile rasterio merge → reproject to 4326) and `fetch_linz()` (static catalog walk → bbox-intersect filter → COG mosaic). [`import_dem.py`](../../pipelines/terrain/import_dem.py) routes `pgc_stac` and `linz_stac` endpoint datasets through it. **Use the no-underscore names** (`ArcticDEM10m`, `REMA10m`) per the OT catalog's `alternateName`; the underscore variants from older code (`ArcticDEM_10m`) are gone.

How the discovery happened: inspecting the JS form action on `/arcticDem` page (`<form action="/rasterSubmit">`) revealed it was a UI POST flow needing session auth. The page's "Bulk download registry" link pointed to `https://registry.opendata.aws/pgc-arcticdem/`, which led to the S3 bucket. The PGC STAC API (`https://stac.pgc.umn.edu/api/v1/`) is what their dynamic data-catalog UI hits behind the scenes. LINZ's NZ Elevation has its own static STAC catalog at the bucket root.

**Practical implication:** the wishlist `highres_open` tier (LINZ1m, ArcticDEM10m, REMA10m) is fully usable now. No Pro tier required for any of them.

### High Resolution Topography (3656 datasets)

These are individual LiDAR campaigns and surveys — **point clouds plus derived rasters**, indexed by location and date. Not accessible via simple `demtype` parameter; you go through the catalog search or the data-catalog UI to find a specific campaign, then fetch via different API patterns.

Sub-categories from the screenshot:
- **OpenTopography hosted** (498) — surveys uploaded to and hosted by OT directly
- **Point Cloud USGS 3DEP** (2233) — federated USGS 3DEP catalog
- **NOAA Coastal Lidar** (925) — every US-coast LiDAR campaign ever flown

Examples:
- "UAV Lidar Survey of Volcan Mountain Wilderness Preserve, CA 2024"
- "Riverside County Flood Control Apple Fire Lidar 2020"
- "Lithologic Controls on Slot Canyon Formation, AZ 2025"
- "Mt Saint Helens Crater 2003 / 2017 / 2024" (multiple time slices for differencing)

These come as `.las` / `.laz` point clouds plus pre-rasterized DEMs. To use them in our pipeline:
1. Catalog search by bbox → identify dataset ID
2. Get raster via "Get Raster Data" button (server-side derived)
3. Optionally, get point cloud → run our own DEM gen at custom resolution

### Community Contributed (268 datasets)

Third-party uploads, pointing back to external hosts. OpenTopo provides metadata + a "Get Data" link but doesn't host the bytes. Quality varies widely. Examples:

- "Backpack LiDAR scans from a sand-covered lava margin at Holuhraun (Iceland)"
- "High-Resolution SfM Topography of Stromboli volcano (Italy), 26-27 May 2021"
- "Mobile lidar scans in the Mariposa Grove of Giant Sequoias, California"
- "Digital Elevation Model of Crater Elegante, Sonora, Mexico, November 2022"

These are the **most fantasy-friendly** because they're often unique, niche, well-photographed locations with strong narrative hooks.

---

## On-demand processing tools (server-side)

OpenTopo offers these as web tools but several have programmatic equivalents (per the API spec there's no documented endpoint for most — they're UI-driven workflows). Wiring these as automation would require web scraping or contacting OpenTopo for endpoint access.

| Tool | What it does | Our equivalent | Should we wire? |
|---|---|---|---|
| Point Cloud Selection & Filtering | Crop point clouds by bbox + classifications, output LAS/LAZ/ASCII | none | **Yes, eventually** — unlocks 2233+925 federated point clouds |
| Raster Selection | Crop a hosted DEM to bbox | this is `/globaldem` | already covered |
| DEM Generation | TIN or grid-mean rasterization from point clouds | none | **Yes** — derive custom-res DEMs from LiDAR |
| Topographic Hillshades | Server hillshade with custom illumination/color/KMZ | `terrain_bundle.py` (local) | local is fine |
| Contour Lines | TIN-derived smoothed contour vectors | none | **Yes for 2D map overlays / minimap features** |
| 3D Point Cloud Visualization | Browser viewer | none | for exploration only |
| Vertical Differencing | Diff two DEMs to detect change | none | **Cool for "scarred earth" fantasy variants** |
| 3D Differencing | Detect horizontal + vertical change | none | similar |
| Hydrology Tools (TauDEM) | Flow paths, watersheds, hydrologically conditioned DEMs | `flow_accumulation_d8` in `terrain_bundle.py` | local is simpler |
| Canopy Height Model | DSM minus DTM = tree heights | none | **Yes** — drive forest density per-region from real data |

### High-leverage server tools we should chase later

In rough priority order:

1. **Point cloud → custom DEM** — server-side via the DEM Generation tool, or local with PDAL after downloading the point cloud. Lets us re-rasterize at any resolution we want.
2. **Canopy height model** — real per-region forest density input. Replaces our heuristic vegetation_density mask with actual tree-height data.
3. **Vertical Differencing** — a secret weapon for fantasy: pull a region "before" and "after" some catastrophe (Mt St Helens 1980, post-wildfire, etc), use the diff as a "carnage" overlay for a battlefield biome.
4. **Contour vectors** — for map screens / minimaps, vector contours look better than raster hillshades.

---

## Underused datasets we already have access to

Verified working but underused in the wishlist:

### `SRTM15Plus` is the world-map dataset
A single pull at this resolution returns **the entire ocean basin + landmass for any region** in one TIFF. The Hawaiian chain test pulled 700km × 450km in 3.1MB, with full 10km vertical relief from abyssal seafloor to summit. Use cases:

- **World-overview maps** for the strategic UI screen — instead of generating fake continents with FBM noise, pull SRTM15Plus for any real region and use it directly as the map backdrop.
- **Continental-shelf basemaps** for "the world is an island chain" fantasy settings.
- **Foundation for cross-DEM blending** — pull macro shape from SRTM15Plus, detail from COP30 over the focus area, composite.

### `CA_MRDEM_DTM/DSM` covers Canada
Canadian Rockies, Yukon, Arctic Canada — all 30m, no high-latitude coverage gaps (since AW3D30 stops at 82°N anyway). Should be the default for any Canada bbox.

### `EU_DTM` is the right default for Europe
30m and Europe-specific, often cleaner than COP30 over the same areas. Auto-pick for European presets.

### Ellipsoidal variants
`SRTMGL1_E` and `AW3D30_E` are **ellipsoidal-height** variants. For game terrain you almost always want the **orthometric** (default; height above mean sea level), not ellipsoidal (height above WGS84 ellipsoid). Ellipsoidal has a geoid offset that varies by location and adds ~100m of meaningless visual noise. **Don't use the `_E` variants.**

### `GEDI_L3` for biome heuristic input
1km canopy-corrected DTM over the entire globe, 500M km² per call. Use cases:
- Pull a whole continent at 1km, use as biome-density prior for procedural generation.
- Calibrate our synthetic biome rules against real biome distributions.

---

## Rate limits + tier matrix

Per the official OT+ tier table (captured 2026-05-06 when our Pro confirmed):

| Feature | Guest | Free Registered (non-academic) | **OT+ Subscriber (us)** | Academic |
|---|---|---|---|---|
| Portal data access | Limited (OT global 10m+) | Limited (OT global 10m+) | **All datasets (OT + USGS 3DEP + NOAA)** | All datasets |
| Portal point-cloud size/job | 50M pts | 250M pts | **350M pts (250M for USGS/NOAA)** | 350M / 250M |
| On-Demand processing tools | Limited | All | **All** | All |
| **API data access** | None | Global 30m + USGS 10m/30m | **All Global + All USGS (incl. 1m)** | Same |
| **API processing limits** | N/A | 50/24h global, 50/24h USGS | **200/24h global, 200/24h USGS** | Same |
| Cost | — | Free | **$30/mo or $330/yr** | Free with .edu / verification |

Source: `opentopography.org/about/services` (the OT+ marketing page).

**We are on OT+ as of 2026-05-06.** API key unchanged at the user's `OPENTOPOGRAPHY_API_KEY` env var. Tier was activated by the OT team after payment processed.

### What changed when Pro went live

- **USGS1m is unlocked** for API calls. Verified via a Half Dome pull (8.5 MB, 1712×1717 pixels of 1m bare-earth granite, 1250–2694m elevation).
- **Daily quota jumped from 50/24h → 400/24h total** (200 global + 200 USGS, separate buckets).
- **All federated point cloud datasets** accessible (USGS 3DEP, NOAA Coastal LiDAR campaigns visible in the catalog).
- **All on-demand processing tools** unlocked (DEM gen, hillshade, contour, vertical differencing, hydrology, canopy height) — these are portal-UI driven; programmatic endpoints not yet known.

### Implications for our pipeline

- The full 130-region wishlist + 300-region mystery sample = 430 calls = **~2 days at the new quota** instead of 9 at free tier.
- The `showcase` tier of `data_wishlist.json` is now actionable. ~10 GB of 1m LiDAR ready to pull.
- `bulk_pull.py --quota 400` is the new default ceiling.

Strategy:
1. **Cache + resume.** Already implemented. A failed/skipped pull doesn't waste a credit.
2. **`--throttle-sec 2` between calls** (already implemented) so we don't burst.
3. **Daily counter in `~/.opentopo_calls.jsonl`** (already implemented) tracks our burn rate.
4. **Distinct quota buckets** — strictly speaking we have 200/24h of `/globaldem` AND 200/24h of `/usgsdem`. Our current counter is total-only; could split if we ever hit it.

---

## Bbox area limits — critical pre-flight check

The API **rejects** requests where the bbox covers more area than the dataset's limit. This is per-request, not aggregate. We should validate bbox area before submitting.

Quick area math: at the equator, 1 degree of longitude × 1 degree of latitude ≈ 12,300 km². Toward the poles, longitude shrinks by `cos(lat)`.

```python
def bbox_area_km2(bbox):
    w, s, e, n = bbox
    lat_mid = (s + n) / 2
    width_km  = (e - w) * 111.32 * cos(radians(lat_mid))
    height_km = (n - s) * 110.57
    return width_km * height_km
```

For our wishlist, the largest bbox is `fjordland_west` (5–7°E, 60–61.5°N) = 2°×1.5° at lat 60.75 → ~133km × 167km = 22,200 km². Well under 450,000 km² 30m limit. **All current wishlist entries are safe.**

But for any future "give me the whole Andes" request, we'd need to tile it.

---

## Bbox tiling for huge regions

Two patterns:

1. **Single dataset, multiple tiles.** Split a giant bbox into N smaller bboxes that each fit under the limit. Fetch each. Stitch with overlap. Useful for high-res over large area.

2. **Multi-resolution composite.** Fetch low-res (`SRTM15Plus` / `GEDI_L3`) for the wide background and high-res (`COP30` / `USGS10m`) for the focus area. Composite. Useful for "world map with playable region inset."

We don't need either yet — current scope tops out at ~30km × 30km regions per source DEM. But if we ever wanted a 200km × 200km playable Norway, this is the path.

---

## Pricing & licensing

- All listed datasets are open / permissive license. See OpenTopo's data licenses page for per-dataset specifics (most are CC-BY or public domain).
- API keys must be unique per user. **Don't share, don't embed in client-side software.** For commercial integration into a shipping product, you need an Enterprise key.
- Game-asset use is fine — we're using the data as one input to derived assets, not redistributing the source DEMs.

---

## What our pipeline currently uses

As of 2026-05-06 (post-data-infra):

**Verified working (real bytes pulled):**
- `COP30` — default global 30m
- `AW3D30` — high-latitude 30m (auto-selected for Norway, Iceland, Patagonia, Scotland presets)
- `SRTMGL3` — legacy 90m
- `GEBCOIceTopo` — bathymetry merge via `--bathymetry`
- `USGS10m` — US 10m via `/usgsdem` (Yosemite test, 5.4MB, 1190–2770m)
- `USGS1m` — **US 1m LiDAR via OT+ subscription** (Half Dome test, 8.5MB, 1712×1717, 1250–2694m). One 0.02° × 0.015° bbox at 1m gives 1700² pixels of carved granite detail.
- `SRTM15Plus` — global 500m bathy+topo combined (Hawaiian chain test, 3.1MB, -5793 to +4163m → 10km of vertical relief in one image)
- `CA_MRDEM_DTM` — Canadian 30m DTM (Banff test, 3.6MB, 1511–3296m)

**Documented but not yet pulled (presumed working since they're in /globaldem enum):**
SRTMGL1, SRTMGL1_E, AW3D30_E, COP90, NASADEM, EU_DTM, GEDI_L3, GEBCOSubIceTopo, CA_MRDEM_DSM, USGS30m

**Verified via STAC bypass (not OT — see "Regional rasters: SOLVED" above):**
- `ArcticDEM10m` — Disko Bay smoke test, 1 PGC tile, 0–913m, 512×512 EPSG:4326 GeoTIFF
- `REMA10m` — Mt Erebus smoke test, 2-tile rio_merge, 0–3732m, 512×512
- `LINZ1m_DTM/DSM` — wired but live-test pending (LINZ catalog walk is slow; ~104 collection.json + per-region item.json fetches)

**Pipeline behavior:**
- **Default dataset:** COP30 (was SRTMGL3, bumped on 2026-05-06)
- **Auto-pick AW3D30** for high-latitude presets where SRTMGL3 has coverage gaps
- **Bathymetry merge:** GEBCOIceTopo via `--bathymetry` flag
- **High-res pulls:** `--res N` saves the full-resolution heightmap as a sidecar before downsampling for renderable mesh
- **TIFF cache:** persistent at `D:\assets\pipelines\terrain\source_dems\`. Re-runs hit cache, no API credit re-spend
- **Pre-flight bbox area check:** rejects requests over the dataset's per-call km² limit, suggests a coarser dataset
- **Rate limit awareness:** `bulk_pull.py` tracks `~/.opentopo_calls.jsonl` and stops at quota

Datasets we **do not** currently use that are interesting:

- `USGS10m` — high-res US, free-tier accessible. Already wired and pulled.
- `USGS1m` — game-changer for showcase regions. **Unlocked by OT+ (active since 2026-05-06).** Already wired and pulled — 14 of 20 showcase regions cached + a 9-tile yosemite_full_1m stitch.
- `SRTM15Plus` — global topo+bathy combined at 500m; great for full-world basemaps.
- `GEDI_L3` — canopy-corrected 1km, useful for whole-continent reference.
- `CA_MRDEM_DSM/DTM` — Canadian high-quality 30m, useful for Rockies + Arctic regions.
- `/otCatalog` search — we'd be smarter about pulls if we queried this first to see what's actually available per bbox.

---

## Roadmap items for our pipeline

- [ ] Add all listed datasets to `import_dem.py` DATASETS dict (currently has 9, missing SRTMGL1_E, AW3D30_E, SRTM15Plus, GEDI_L3, CA_MRDEM_DSM, CA_MRDEM_DTM).
- [ ] Add `/usgsdem` endpoint as a separate `fetch_opentopo_usgs()` function.
- [ ] Add `/otCatalog` client as `../../pipelines/terrain/catalog_search.py`.
- [ ] Pre-flight `bbox_area_km2()` check in `import_dem.py`; reject (with a helpful message) if over the dataset's limit, recommend tiling or switching to `COP90` / `SRTM15Plus`.
- [ ] Add `--throttle-per-hour N` to `bulk_pull.py`.
- [ ] Add daily call counter in `~/.opentopo_calls.jsonl` so we can warn before quota.
- [ ] Update `data_wishlist.json` showcase tier to use `USGS10m` + `USGS1m` (with explicit `dataset` key per region).
