# Atmosphere Arc

Date: 2026-05-10

The Atmosphere module owns sky-gradient color, scattering, time-of-day
color shifts, and atmospheric volumetrics (fog/haze/dust/mist). It's
**shared infrastructure** consumed by both the Sky arc and the Weather
arc — building it first means Sky and Weather build on a stable base
rather than grafting atmospheric concerns onto themselves.

This arc runs **first** in the post-M24 sequence per
[`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md).

## What it produces

Files added to the bundle (per `WORLD3_CONTRACT_2026_05_10.md`):

```
<region_id>/
└── atmosphere/
    ├── climate_class.json        ← Köppen-Geiger zone + region patterns
    ├── atmospheric_lut.png       ← color tables, (state × time-of-day × view-dir)
    ├── scattering_params.json    ← per-climate scattering coefficients
    ├── volumetrics.json          ← fog/haze/dust/mist params per state
    └── reference_shaders/
        ├── atmospheric_color.gdshader
        └── volumetric_fog.gdshader
```

## What it depends on

- **Terrain Foundation**: `biome_label.json`, `height_meta.json` (latitude + elevation for climate classification)
- **Material Catalog**: ambient color from atmosphere affects rendered material brightness (coupling only; no atmospheric data flows into materials directly)
- Nothing else.

## What depends on it

- **Sky arc**: sky content sits on top of atmospheric color gradient
- **Weather arc**: weather state shifts atmospheric color; volumetric fog runs in this module

## Right-sized Ms

Each M is **1-3 sessions**, **one concrete deliverable**, **reviewable in isolation**.

### A1 — Climate classification

**Goal**: per-region Köppen-Geiger climate zone + typical-weather manifest.

Inputs:
- Real climate data (Köppen-Geiger global maps, NOAA reanalysis grids — both freely available)
- `biome_label.json` + latitude + elevation from `height_meta.json`

Deliverables:
- `pipelines/atmosphere/classify_climate.py` — maps region → Köppen zone
- `atmosphere/climate_class.json` per region with Köppen code, precipitation type frequencies, temperature ranges, season patterns

Exit:
- Cached test regions (Big Bend, Olympic, Yosemite, Yellowstone, Sierra) match published Köppen-Geiger maps
- Procedural regions get plausible classification from biome rules

### A2 — Atmospheric color LUT (data only)

**Goal**: per-(climate × state × time-of-day × view-direction) color tables. Data layer only; no shader.

Inputs:
- A1 climate classes
- Atmospheric scattering models (Hosek-Wilkie or simplified blackbody-driven)

Deliverables:
- `pipelines/atmosphere/atmospheric_lut_gen.py` — generates 3D LUT
- `atmosphere/atmospheric_lut.png` — sky/sun/ambient RGB lookup
- `atmosphere/scattering_params.json` — per-climate Rayleigh + Mie coefficients

Exit:
- LUT values match published atmospheric-scattering references at known sun angles
- Per-climate variation visible in the LUT (clear vs hazy vs polluted air)

### A3 — Reference atmospheric color shader

**Goal**: reference Godot shader that consumes A2's LUT and produces correct sky color in walk mode.

Inputs:
- A2 LUT
- Per-mode color shift policies (walk = full sky; iso = ambient tint; topdown = overlay)

Deliverables:
- `atmosphere/reference_shaders/atmospheric_color.gdshader`
- Per-mode reference scenes (`atmosphere_walk_test.tscn`, etc.)

Exit:
- Sky color shifts correctly across day/night cycle in walk mode
- Iso mode shows correct ambient tint without rendering full sky
- Topdown mode applies weather-tint overlay without breaking gameplay readability

### A4 — Atmospheric volumetrics data

**Goal**: per-(climate × state) fog/haze/dust/mist density distributions.

Inputs:
- A1 climate classes
- Mist-over-water coupling rules (deferred; consumed by Water arc when it lands)

Deliverables:
- `pipelines/atmosphere/volumetrics_gen.py`
- `atmosphere/volumetrics.json` — density + color + scale parameters per (climate × state)

Exit:
- Dawn-mist density appropriate per climate (foggy coasts, dry deserts)
- Dust-storm parameters present for desert climates
- Mist-over-water hooks reserved for Water arc consumer

### A5 — Reference volumetric fog shader + conformance

**Goal**: reference fog shader + atmosphere-arc conformance scenes.

Inputs:
- A2 LUT
- A4 volumetrics data
- A3 reference shader (composes with fog)

Deliverables:
- `atmosphere/reference_shaders/volumetric_fog.gdshader`
- Per-(climate × state × time-of-day) conformance scenes
- M13 promotion gate accepts atmosphere artifacts

Exit:
- All conformance scenes render correctly at walk + iso + topdown
- Atmosphere arc passes M13 promotion gate

## Exit criteria (whole arc)

- Every cached test region has valid `atmosphere/` directory in its bundle
- LUT + scattering params + volumetrics data + reference shaders all conform
- Sky arc and Weather arc can consume atmosphere outputs without modification
- All five Ms passed M13 gate

## Risks

- **R1 — Atmospheric scattering is well-trodden but easy to get subtly wrong.** Mitigation: validate against published references per A2 exit; rely on Hosek-Wilkie or similar peer-reviewed model, not roll-your-own.
- **R2 — Per-mode parity for fog is hard.** Topdown fog cannot occlude tactical info. Mitigation: per-mode fog rendering is always a tint or icon overlay in iso/topdown, never depth-occluding.
- **R3 — Coupling to Water arc (mist over water) is unresolved.** Mitigation: A4 leaves hooks; Water arc fills them when it lands.

## Estimated effort

5 Ms × 1-3 sessions each = ~5-15 sessions / ~1-3 months.

## Cross-references

- Output contract: [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md)
- Architecture: [`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`](WORLD3_ARCHITECTURE_TEMP_2026_05_10.md) Module 6
- M-sequence timeline: [`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md)
- Sister arc (Sky): [`SKY_ARC_2026_05_10.md`](SKY_ARC_2026_05_10.md)
- Sister arc (Weather): [`WEATHER_ARC_2026_05_10.md`](WEATHER_ARC_2026_05_10.md)
- Sister arc (Water): [`WATER_ARC_2026_05_10.md`](WATER_ARC_2026_05_10.md)
- Long-term direction: `../../docs/plans/LONG_TERM_VISION.md`
