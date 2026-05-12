# Master Data Catalog — 2026-05-09

**Single entry point** for "what data do we have, where does it live, and
what state is it in." Every other catalog/manifest in the repo plugs into
this doc.

The machine-readable counterpart is `world3/data_catalog.json` (regenerated
by `pipelines/terrain/build_master_catalog.py`). Re-run the script after
pulls/builds; this doc summarizes its output.

---

## 1. Total inventory at a glance

| Category | Count | Size | Path |
|----------|------:|------|------|
| **Raw DEM TIFs** (cached) | 292 | 19.2 GB | `dems/` |
| **Procedural texture sets** (PBR libraries) | 141 | ~1.5 GB | `world/textures/library/<id>/` |
| **Runtime-staged textures** (Godot-imported) | 27 dirs / 32 `.tres` | 154 MB | `world3/textures/wgv3/` |
| **OT heightmap bundles** (per-region heightmap+meta) | 19 regions | included in opentopo/ | `world3/opentopo/processed/heightmaps/` |
| **OT master stacks** (worker fused stacks) | 4 | included | `world3/opentopo/processed/master_stacks/` |
| **OT real-source textures** (worker materials) | 8 source classes | included | `world3/opentopo/processed/textures/` |
| **OT raw Dataspace projects** (DSM+ortho+LAZ bundles) | 3 | included | `world3/opentopo/raw/dataspace/` |
| **Processed terrain bundles** (stitched mega-stacks + single-region) | 211 | included | `pipelines/terrain/output/` |
| **OT API call ledger** (history) | 200+ calls | tiny | `~/.opentopo_calls.jsonl` |

**Total disk: world3 + dems + world ≈ 37 GB** of game-ready terrain & textures.

---

## 2. Raw DEM cache (`dems/`)

By dataset (run `python pipelines/terrain/build_master_catalog.py` to refresh):

| Dataset | Tiles | Size | Notes |
|---------|------:|-----:|-------|
| **USGS1m** (US LiDAR; OT+ Pro) | 56 | 16.3 GB | Big Bend 9/9, GSD 9/9, Yosemite 9/9, Bryce 4/4, Olympic 5/9, scattered hero shots |
| **COP30** (global 30m) | 156 | 3.0 GB | Bulk worldwide variety — the workhorse for biome breadth |
| **AW3D30** (alternate global 30m) | 32 | 154 MB | Cross-check + non-OT fallback |
| **USGS10m** (US 10m) | 15 | 108 MB | Mid-detail US; covers areas USGS1m doesn't (remote alpine) |
| **GEBCOIceTopo** (bathy 450m) | 18 | 9.5 MB | Ocean / coast; tiny because low-res |
| **ArcticDEM10m** (PGC polar) | 5 | 11.2 MB | Greenland, Iceland, Svalbard, Denali — via STAC bypass |
| **LINZ1m_DTM** (NZ LiDAR) | 5 | 15 MB | Milford, Mt Cook, etc. — via STAC bypass |
| **REMA10m** (PGC Antarctica) | 3 | 6.1 MB | Dry Valleys, Erebus, Taylor — via STAC bypass |
| **CA_MRDEM_DTM** (Canada DTM) | 1 | 3.6 MB | BC Coast |
| **SRTM15Plus** (global+bathy) | 1 | 3.1 MB | Backstop |

### Naming convention

`{DATASET}_{W:+.4f}_{S:+.4f}_{E:+.4f}_{N:+.4f}.tif`

Bbox in degrees. Cache hit lookup is exact-bbox-match; same bbox at
different dataset = different file.

### How to add more

- OT API datasets (COP30, AW3D30, USGS1m, USGS10m, GEBCOIceTopo):
  `pipelines/terrain/bulk_fetch_to_cache.py --tier <tier>` walks
  `art_lab/biomes/data_wishlist.json`.
- ArcticDEM / REMA / LINZ: `pipelines/terrain/fetch_regional_stac.py`
  uses providers' direct S3.
- Multi-tile stitched: `pipelines/terrain/tile_stitch.py`.
- Single bbox: `pipelines/terrain/import_dem.py` (raw cache only;
  the post-process bundle step depends on a since-archived
  `terrain_bundle` module — use `bulk_fetch_to_cache.py` instead).

---

## 3. Stitched mega-stacks (`pipelines/terrain/output/`)

Multi-tile composites. Each is `height_16.png` (4096×4096 16-bit) + 
`tile_grid.json` provenance.

| ID | Grid | Tiles ok | Notes |
|----|------|----------|-------|
| **`big_bend_1m_v2`** | 3×3 | 9/9 | Production-ready. 572-2215m. Desert+canyon+mountain. |
| **`great_sand_dunes_1m`** | 3×3 | 9/9 | **Highest relief.** 2291-4016m. Dunes → alpine in one block. |
| **`yosemite_full_1m`** | 3×3 | 9/9 | Full Yosemite Valley + Tuolumne ridges. |
| `bryce_extended_1m` | 2×2 | 4/4 | Full Bryce amphitheater. |
| `crater_lake_full_10m` | 2×2 | 4/4 | Full caldera + rim at 10m. |
| `death_valley_basin` | 2×2 | 4/4 | Below-sea basin + Telescope Peak. |
| `olympic_peninsula_1m` | 3×3 | 2/9 | Failed (1st attempt; superseded by v2). |
| `olympic_peninsula_1m_v2` | 3×3 | 5/9 | Partial — USGS1m gap in central alpine. |
| `yosemite_stitch_test` | 2×2 | 4/4 | Early test; superseded by full. |

**Verdict**: 5 production-quality mega-stacks at 1m or 10m (Big Bend, GSD,
Yosemite, Bryce, Crater Lake, Death Valley). Olympic is half-coverage.

---

## 4. OpenTopo master stacks (`world3/opentopo/processed/master_stacks/`)

Worker-built fused stacks (DEM + orthophoto + masks aligned). Production-
*facing* review scenes; not yet runtime-integrated.

| ID | Layers | Notes |
|----|-------:|-------|
| `gloss_mountain_textured_master` | 1+ | Real DSM + orthomosaic, 0.6×1.1km, OK |
| `zion_usgs10m_master_4call` | 4+ | 4-call USGS10m mosaic, 36.8×36.9km, no-color |
| `rainier_usgs1m_south_master` | 4+ | Mt Rainier south flank USGS1m |
| `chuculay_textured_master` | 1+ | Chuculay, Chile (worker test/superseded) |

These are the worker's high-quality reference stacks. Adding more is in
their domain.

---

## 5. OT real-source materials (`world3/opentopo/processed/textures/`)

Worker-extracted tileable PBR materials from real orthophoto crops.

Currently 8 source classes from one Dataspace project (Guadalupe Cypress):
`bare_soil`, `bright_rock`, `dry_wash`, `rocky_slope`, `scrub_dense`,
`scrub_sparse`, plus `Guadalupe_Cypress_finished_materials_index.json`.

Each class has `source/`, `tileable_real/`, `stylized_pixel/`, and (for
the 6 finished classes) `finished_material/material_hex_detail_finished.tres`
runtime files. Bound to `terrain_hex_detail.gdshader`.

---

## 6. Procedural texture library (`world/textures/library/`)

141 PBR sets generated by `pipelines/textures/aaa_texture.py`. Top
categories:

| Category | Count |
|----------|------:|
| Ground | 51 |
| Rock | 31 |
| Snow | 30 |
| Foliage | 10 |
| Sand | 4 |
| Bricks | 2 |
| Wood | 2 |

Each material is `library/<id>/<id>_<map>.png` with 6 PBR maps + 
`aaa_pipeline.json` log + QA contact sheet.

The flat one-line-per-material log lives at
`world/textures/catalog/materials.jsonl`.

---

## 7. Runtime-staged textures (`world3/textures/wgv3/`)

Godot-imported subset of the library — what's actually bound to runtime
materials.

- 27 slot-prefixed dirs (e.g. `alpine_grass/`, `temperate_forest_dirt/`,
  `grassland_rock_light/`)
- 32 `terrain_blend_*.tres` files (5 kits × 3 modes + base + transitions)
- Plus shaders + `terrain_hex_detail` finished `.tres` from worker

Connected to runtime via `world3/scenes/` mode scenes + `RegionGalleryCapture`.

---

## 8. The catalogs that ALREADY existed (now linked from this doc)

| Catalog | Role | Path |
|---------|------|------|
| **M1 material catalog** | Canonical material schema (31 entries; the "agreed" set) | `world3/materials/catalog.json` + `CATALOG.md` |
| **Library jsonl** | Flat per-material log of every generation | `world/textures/catalog/materials.jsonl` |
| **Regions** | 16 regions × kit assignment × bundle paths | `world3/jobs/regions.json` |
| **Biome kits** | 5 kits × 5 slots × height/slope rules | `world3/jobs/biome_kits.json` |
| **Transition rules** | Boundary contracts between material pairs | `world3/jobs/biome_transition_rules.json` |
| **DEM wishlist** | 205 DEM target bboxes (intent ledger) | `art_lab/biomes/data_wishlist.json` |
| **OT API ledger** | Every API call ever made (200+) | `~/.opentopo_calls.jsonl` |
| **OT raw catalog** | What OT advertised at the time of pull (per region) | `world3/opentopo/catalog/otcatalog_raw/` |
| **Comfy regen queue** | Materials queued for ComfyUI regeneration | `world3/jobs/comfy_texture_regen_candidates.json` |
| **Mega-stack docs** | Big Bend, Olympic, GSD, polar bypass | `world3/docs/MEGA_STACKS_2026_05_09.md` |
| **Data directory** | 50-region curated pull plan + cache cross-check | `world3/docs/OPENTOPO_DATA_DIRECTORY_2026_05_08.md` |

---

## 9. How to refresh this catalog

```powershell
python pipelines/terrain/build_master_catalog.py
```

Reads every directory above and rewrites `world3/data_catalog.json`. This
doc is the human-readable summary; update it when categories change shape
(e.g. new data type added, new tooling).

The script is read-only on data and idempotent.

---

## 10. What we DON'T have (gaps for future pulls)

This is what to consider next:

### Coverage gaps in the global DEM library

- **Africa**: only Serengeti, Madagascar, Ethiopian, Drakensberg, Okavango,
  Sahara erg, Namib dunes. Missing: Atlas mtns, Congo basin, Kalahari core,
  Ahaggar, Tibesti, Rift Valley lakes, Cape coast, Mt Kenya/Kilimanjaro
  triangle.
- **South America**: Amazon, Pantanal, Patagonia, Aconcagua, Atacama,
  Bolivian Altiplano. Missing: Cerrado, Pampas, Galápagos volcanic,
  Chocó rainforest, Guiana Shield, Cordillera Real, Iguazu basin.
- **South East Asia**: Borneo only. Missing: Indonesian volcanic chain
  beyond Bali/Lombok, Sumatra, Philippine archipelago detail, Mekong
  upper basin, Burmese highlands.
- **Australia**: Macdonnell ranges only. Missing: Great Dividing Range,
  Tasmanian highlands, Pinnacles desert, Kimberley plateau, Lake Eyre
  basin, Bungle Bungle range.
- **Russia / Central Asia**: Lena delta, Caucasus, Tien Shan. Missing:
  Altai, Pamirs, Kamchatka volcanic chain, Lake Baikal, Tundra of
  central Siberia, Urals.
- **Pacific**: Hawaiian + Maldives + Indonesia volcanic via bathy.
  Missing: Polynesian atolls (Tahiti, Bora Bora), Marquesas volcanic,
  Fiji, Galápagos.

### Biome categories under-represented

- **Mangrove forests**: zero. Sundarbans is in regions.json but only as
  a generic name; no mangrove-specific material kit.
- **Salt marsh / tidal flat**: zero.
- **Limestone karst / tower karst**: zero (Vietnam Halong Bay, Guilin).
- **Polar desert (vegetation-free dry)**: only Antarctic Dry Valleys.
- **Mediterranean shrub elsewhere**: only California chaparral.
- **Boreal lakes (Canadian Shield-type)**: zero specific.
- **Fjord-meets-ocean transition**: have Norwegian fjords + Milford
  Sound DEMs but no specific kit for fjord-floor / saltwater wall /
  hanging valley.

### What's NOT a coverage gap (we have plenty)

- US national parks (~10 covered at 1m).
- European Alps (Mont Blanc, Dolomites, Tetons-equivalent).
- Generic mountain terrain (we have a *lot* of alpine).
- Cold-temperate forest at coarse scale.

### Recommended next pulls (roughly tier-1 priorities)

1. **Mt Kilimanjaro + Mt Kenya** (Africa alpine + savanna transition).
2. **Atlas Mountains, Morocco** (Mediterranean alpine; under-represented).
3. **Halong Bay / Guilin karst** (limestone tower karst — totally new
   biome shape).
4. **Sundarbans mangrove** (currently only a generic point).
5. **Galápagos volcanic islands** (volcanic + ocean + endemic biome).
6. **Iguazu Falls basin** (waterfall river system).
7. **Tasmanian highlands + Cradle Mountain** (Southern Hemisphere
   alpine).
8. **Kamchatka volcanic chain** (active volcano belt).
9. **Pamirs** (high-altitude central Asia).
10. **Guiana Shield tepui plateau** (Mt Roraima — vertical-walled
    plateau, unique geology).

Pulls #1–4, 7 work straight through `bulk_fetch_to_cache.py` after
adding to wishlist. #5 (Galápagos) needs both COP30 and GEBCO bathy.
#6 (Iguazu) needs USGS-equivalent (likely COP30 only, no high-res).
#8–10 are COP30 territory.

---

## Change log

- **2026-05-09 initial**: drafted after session inventory revealed 5
  parallel catalog files, none covering the full library. This doc +
  `data_catalog.json` consolidate.
