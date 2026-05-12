# Weather Arc

Date: 2026-05-10

The Weather module owns **dynamic atmospheric phenomena**: volumetric
clouds, precipitation, surface response (wet/snow/ice/mud), vegetation
response (wind sway, storm flattening), and the state-machine that
ticks all of it. Largest single arc in the long-term plan.

This arc runs **fourth** in the post-M24 sequence per
[`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md) — after
Atmosphere + Sky + Water. Weather couples to all three and benefits
most from them being solid first.

## On/off semantics

Weather is the **most opt-in module in world3**. Single switch turns
the whole `weather/` directory on or off:

- **Weather disabled**: bundles look exactly like pre-weather bundles. No `weather/` directory; no surface-response masks; default material variants. Validates against pre-weather contract.
- **Weather enabled**: full system activates. All manifests + reference shaders + conformance outputs populate.

No half-states. Bad weather is worse than no weather, so we ship the
full system or skip it.

## What it produces

Files added to the bundle (per `WORLD3_CONTRACT_2026_05_10.md`):

```
<region_id>/
└── weather/
    ├── cloud_distribution.json       ← per-climate cloud-type rules
    ├── precipitation_manifest.json   ← type frequencies + intensity curves
    ├── surface_response.json         ← wet/snow/ice/mud accumulation rules
    ├── wind_field.json               ← prevailing wind + magnitude
    ├── state_transitions.json        ← Markov-style state machine
    ├── reference_shaders/
    │   ├── volumetric_clouds.gdshader
    │   ├── precipitation_particles.gd        ← Godot particle systems
    │   ├── surface_response/
    │   │   └── <material_id>_<state>.gdshader  ← per-material variants
    │   └── vegetation_response.gdshader
    └── conformance_scenes/
        └── <mode>_<climate>_<state>.tscn
```

## What it depends on

- **Atmosphere arc**: atmospheric color shifts per weather state; climate classification
- **Sky arc**: clouds occlude celestial bodies (compositing rules in state_transitions.json)
- **Water arc**: rain raises rivers, cold freezes lakes, mist forms over water
- **Material Catalog**: surface response variants per material
- **Scatter & Features**: vegetation wind response

## What depends on it

- Nothing upstream — Weather is the top module in the dependency graph
- Consumer game (downstream) ticks the state machine at game-time

## Source: Track D1 promoted

**Track D1 (nebula-statistics → cloud field generator)** is promoted as
the volumetric cloud system source (WX-1). Real Hubble/JWST nebula
imagery → statistical signatures → procedural cloud-class generators.

## Right-sized Ms

Each M is **1-3 sessions**, **one concrete deliverable**. Previously
mega-scoped M33 + M35 are split into smaller pieces.

### WX-1 — Cloud-class statistics extraction (Track D1 source work)

**Goal**: extract per-cloud-type statistical signatures from nebula imagery corpus.

Inputs:
- Hubble/JWST nebula imagery (~5-10 GB curated corpus pulled from MAST)
- Cloud-class taxonomy (cumulus, stratus, cirrus, storm, fog-layer)

Deliverables:
- `pipelines/weather/nebula_to_cloud_signatures.py` — fits per-class statistics
- `pipelines/weather/cloud_class_signatures.json` — fitted per-class params (global priors)

Exit:
- Six cloud-class signatures fitted with visual review against reference imagery
- Signatures distinguishable to a trained eye (cumulus ≠ stratus ≠ cirrus)

### WX-2 — Per-climate cloud-type distribution generator

**Goal**: per-region cloud-type frequency rules.

Inputs:
- WX-1 signatures
- Atmosphere arc A1 climate classification

Deliverables:
- `pipelines/weather/cloud_distribution_gen.py`
- `weather/cloud_distribution.json` — per-climate cloud-type weights + altitude bands + density rules

Exit:
- Cumulus dominant over grasslands; stratus over coastal; cirrus over alpine; storm clouds in stormy state
- Per-climate distributions visibly different in review captures

### WX-3 — Reference volumetric cloud shader

**Goal**: reference volumetric cloud shader consuming WX-2 distributions.

Inputs:
- WX-2 distribution data
- Atmosphere arc atmospheric_lut for sky color behind clouds

Deliverables:
- `weather/reference_shaders/volumetric_clouds.gdshader`
- Per-(climate × state) cloud reference scenes
- Performance budget documented

Exit:
- Clouds render at walk-mode quality matching AAA bar per `LONG_TERM_VISION.md`
- Performance fits per-mode budget (walk full quality; iso reduced; topdown flat)

### WX-4 — Cloud × sky compositing rules

**Goal**: cloud-occlusion-of-celestial-bodies rules for consumer use.

Inputs:
- WX-3 cloud shader output
- Sky arc S2 starfield + S3 celestial bodies

Deliverables:
- Cloud × sky compositing rules in `state_transitions.json` (or sibling file)
- Reference compositing logic in `weather/reference_shaders/volumetric_clouds.gdshader`
- Consumer documentation: how to read cloud-occlusion data

Exit:
- Stars visibly occluded by cumulus in reference scenes
- Moon visible through thin cirrus; hidden behind storm clouds
- Compositing rule documented for consumer implementations

### WX-5 — Precipitation manifest generator

**Goal**: per-climate precipitation parameters (rain/snow/hail).

Inputs:
- Atmosphere arc A1 climate classification
- Real precipitation data (NOAA reanalysis, climatology references)

Deliverables:
- `pipelines/weather/precipitation_gen.py`
- `weather/precipitation_manifest.json` — type frequencies + intensity curves + particle counts + fall velocity

Exit:
- Tropical biomes: no snow, monsoon-frequency rain
- Alpine: high snow frequency, freezing-rain hybrids
- Desert: rare rain, no snow, sand-storm rules
- Manifest values match reference climatology for cached regions

### WX-6 — Reference precipitation particle systems

**Goal**: Godot particle systems for rain/snow/hail with per-mode LOD.

Inputs:
- WX-5 manifest
- Per-mode visibility rules (walk = full particles; iso = reduced; topdown = streak overlay)

Deliverables:
- `weather/reference_shaders/precipitation_particles.gd` — rain/snow/hail particle systems
- Per-mode LOD policy
- Per-state reference scenes

Exit:
- Rain looks like rain at all three view modes
- Snow drifts correctly with wind_field input
- Hail bounces realistically
- Per-mode performance fits budget

### WX-7 — Surface response: wet variants for catalog

**Goal**: generate wet material variants for every catalog material.

Inputs:
- Material Catalog (full extent)
- Wetness response model (surface roughness drops, specularity rises)

Deliverables:
- `pipelines/weather/generate_wet_variants.py`
- `world3/materials/<id>_wet.tres` for every catalog material
- `weather/reference_shaders/surface_response/<id>_wet.gdshader` for representative materials

Exit:
- Every catalog material has wet variant
- Wet variants visibly different from dry (puddles + sheen)
- Conformance scenes pass walk-mode close-play

### WX-8 — Surface response: snow + ice variants

**Goal**: generate snow + ice material variants for catalog.

Inputs:
- Material Catalog
- Snow accumulation model (surface texture replacement + albedo shift)

Deliverables:
- `pipelines/weather/generate_snow_variants.py`
- `world3/materials/<id>_snow.tres` and `<id>_ice.tres` for every catalog material
- `weather/reference_shaders/surface_response/<id>_snow.gdshader` for representative materials

Exit:
- Every catalog material has snow + ice variants
- Snow accumulation reads correctly per material (rough materials hold more snow)
- Ice variants only generated for surfaces near water bodies (per Water arc)

### WX-9 — Surface response: mud + accumulation thresholds

**Goal**: mud variants + accumulation threshold curves.

Inputs:
- Material Catalog (wet variants from WX-7)
- Mud model (wet + soft surface compaction)

Deliverables:
- `pipelines/weather/generate_mud_variants.py`
- `world3/materials/<id>_mud.tres` for applicable materials (organic soils, dirt, grass)
- `weather/surface_response.json` — accumulation thresholds per (material × state); per-mode visibility rules

Exit:
- Mud appears on organic soil materials but not on stone/sand
- Threshold curves produce visible state transitions over reference time-step
- Per-mode rules sensible (walk shows puddles; topdown shows tint shifts)

### WX-10 — Wind field + vegetation response data

**Goal**: per-region wind field + per-scatter vegetation response parameters.

Inputs:
- Atmosphere arc A1 climate classification
- M15 scatter system

Deliverables:
- `pipelines/weather/wind_field_gen.py`
- `weather/wind_field.json` — prevailing wind direction + magnitude + storm overrides
- Per-scatter vegetation-response params in `scatter_manifest.json`

Exit:
- Wind direction matches real-world prevailing winds for cached regions
- Storm-strength wind multipliers defined per state
- Per-scatter response rules (grass flattens, trees sway, branches break in extreme)

### WX-11 — Reference vegetation sway shader

**Goal**: vegetation sway shader extending scatter materials.

Inputs:
- WX-10 wind field
- M15 scatter system

Deliverables:
- `weather/reference_shaders/vegetation_response.gdshader` — adds wind-sway to scatter materials
- Per-(mode × scatter-type) reference scenes
- Existing scatter conformance suite passes with sway enabled

Exit:
- Grass + leaves visibly sway with wind in walk mode
- Storms flatten grass appropriately
- Iso/topdown show wind direction subtly (directional brightness bias on clusters)

### WX-12 — Weather state machine manifest

**Goal**: Markov-style state machine that consumer ticks at game-time.

Inputs:
- All prior weather subsystems
- Climate-class transition probabilities from real data

Deliverables:
- `pipelines/weather/state_transitions_gen.py`
- `weather/state_transitions.json` — Markov transition matrix + duration params + time-of-day modifiers
- Coupling rules (cloud × sky from WX-4; weather × water from Water arc)
- Consumer integration documentation

Exit:
- State transitions are climate-appropriate (deserts mostly clear; coastal cycle through overcast/rain; alpine winter favors snow + clear)
- Transition timescales believable (storms hours; clear-sky days)

### WX-13 — Weather conformance + on/off equivalence

**Goal**: full weather-arc conformance + verified on/off behavior.

Inputs:
- All WX-1 through WX-12 deliverables

Deliverables:
- `weather/conformance_scenes/` populated with per-(mode × climate × state) validation scenes
- `pipelines/weather/conformance_runner.py` — scripted validation
- **On/off equivalence test**: same bundle through with-weather and without-weather pipelines; without-weather output identical to pre-weather bundle
- Consumer documentation: how to opt in / how to disable cleanly
- M13 promotion gate accepts full weather system at all four bands

Exit:
- All conformance scenes pass at walk + medium + iso + topdown
- Weather on/off toggle works cleanly
- Off-state bundles bit-identical (modulo `weather/` directory presence) to pre-weather
- Weather arc passes M13 promotion gate

## Exit criteria (whole arc)

- Every cloud + precipitation + surface response + vegetation response + wind + state-transition module ships
- Reference shaders cover the full system at AAA quality bar
- Per-mode parity holds across walk + iso + topdown
- Weather × Sky + Weather × Water coupling rules verified
- All 13 WX-Ms passed M13 gate
- World3 hits the 5th completion-bar condition

## Risks

- **R1 — Reference shaders are the largest visual-quality commitment world3 has made.** If quality slips, "bad weather is worse than no weather" applies; defer specific reference shaders rather than ship sub-AAA. Mitigation: per-M visual review; willingness to ship some shaders behind a "weather minimal" flag if quality can't be met for all.
- **R2 — Weather × water coupling rules are intricate.** Easy to get wrong. Mitigation: WX-12 coupling rules get explicit conformance scenes (frozen lake, rain-swollen river, mist-over-water).
- **R3 — Per-mode parity is harder for weather than terrain.** Topdown cannot allow storm volumetrics to obscure tactical info. Mitigation: per weather subsystem, topdown rendering is **always a tint or icon overlay**, never depth-occluding.
- **R4 — Surface variant generation across the catalog is heavy.** WX-7/8/9 each touch every catalog material. Mitigation: batch processing in `aaa_texture.py`; can defer rarely-used materials.

## Estimated effort

13 Ms × 1-3 sessions each = ~13-39 sessions / ~3-9 months.

Largest single arc. Reference shader work + surface variant generation
across the full catalog push the upper bound.

## Cross-references

- Output contract: [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md)
- Architecture: [`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`](WORLD3_ARCHITECTURE_TEMP_2026_05_10.md) Module 8
- M-sequence timeline: [`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md)
- Source: Track D1 in [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md)
- Sister arcs: [`ATMOSPHERE_ARC_2026_05_10.md`](ATMOSPHERE_ARC_2026_05_10.md), [`SKY_ARC_2026_05_10.md`](SKY_ARC_2026_05_10.md), [`WATER_ARC_2026_05_10.md`](WATER_ARC_2026_05_10.md)
