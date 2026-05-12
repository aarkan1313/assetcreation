# M25-M39 Water + Weather Roadmap

> ⚠️ **SUPERSEDED 2026-05-10**. This doc captured an earlier flat
> M25-M39 framing for water + weather. The long-term plan is now
> organized into **arc-named docs** with right-sized Ms inside.
>
> **Canonical replacements**:
> - [`ATMOSPHERE_ARC_2026_05_10.md`](ATMOSPHERE_ARC_2026_05_10.md) (A1-A5; was nested inside weather here)
> - [`SKY_ARC_2026_05_10.md`](SKY_ARC_2026_05_10.md) (S1-S5; new arc that fixed a gap this doc missed)
> - [`WATER_ARC_2026_05_10.md`](WATER_ARC_2026_05_10.md) (W1-W6; was M25-M30 here)
> - [`WEATHER_ARC_2026_05_10.md`](WEATHER_ARC_2026_05_10.md) (WX-1 to WX-13; was M31-M39 here, but split + atmosphere parts extracted)
> - [`CONFORMANCE_ARC_2026_05_10.md`](CONFORMANCE_ARC_2026_05_10.md) (C1-C4; closes the long-term plan)
>
> **Primary orchestrator view**: [`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md).
>
> This doc is **kept for historical reference**. Don't update it; go to
> the arc docs instead.

Date: 2026-05-10

This roadmap closes out the world3 long-term plan. Runs after M19-M24
(hybrid procedural infinite world) completes. Final two arcs:

- **M25-M30: Water track** — water masks, flow direction, type
  classification, lake/pond detection, coastal extension, water-aware
  scatter, water material variants
- **M31-M39: Weather system** — full opt-in atmospheric module
  (climate classification + atmospheric color + volumetric clouds +
  precipitation + surface response + vegetation response + atmospheric
  volumetrics + state transitions + conformance + integration)

At M39 close, world3 hits the completion bar per
[`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md).

## Framing

Both tracks **emit data to the world3 output contract**
([`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md)).
They are not runtime systems; they are world-data generators. The
consumer game (or any downstream tool) renders the data.

The weather track additionally **ships reference shader implementations**
because the alternative — JSON manifests without rendering proof — does
not meet the quality bar. Reference shaders enforce the quality bar at
the contract boundary.

## Sequencing rules

- M25-M30 (water) runs first; M31-M39 (weather) runs second.
- Weather couples to water (rain affects rivers; cold freezes lakes).
  Water track closes before weather starts so weather has stable
  water-state to reference.
- Both tracks honor existing M13 promotion-gate semantics.
- All new files emit to the contract bundle per
  `WORLD3_CONTRACT_2026_05_10.md`.
- Weather is **opt-in via a single switch**. When disabled, bundles
  validate against the pre-weather contract; when enabled, the full
  `weather/` directory populates.

---

# Water track (M25-M30)

## M25 - Water mask emission from erosion

**Goal**: M20 erosion-derived drainage networks promote to runtime
water masks.

Inputs:
- M20 Landlab erosion baked drainage maps per cached region
- M11 feature-mask runtime infrastructure
- Real-DEM hydrology data (USGS NHDPlus where available)

Deliverables:
- `pipelines/terrain/erosion_to_water_mask.py` — extracts drainage
  network polygons + flow magnitudes from M20 output
- `water/water_height.png` populated per-chunk for procedural regions
- `water/flow_direction.png` populated for river/channel pixels
- Per-region validation: river network topology matches real
  hydrology for cached real-DEM regions

Exit:
- At least 3 cached real-DEM regions have water masks that pass
  visual review against real-world river maps
- At least 1 procedural region has plausible water masks emerging
  from M20 erosion

## M26 - Lake / pond detection

**Goal**: closed depressions in heightmaps emit as lake water bodies.

Inputs:
- M20 erosion drainage + M22 patch-seeded terrain
- Real lake coverage data (USGS NHDPlus, OpenStreetMap)

Deliverables:
- `pipelines/terrain/detect_water_bodies.py` — closed-depression
  finder + depth threshold + minimum-area filter
- `water/water_type_mask.png` populated with type=2 (lake) regions
- Lake `water_height.png` reflects pooled-water surface, not terrain
- Per-region: number/area of lakes matches real-world reference for
  cached regions

Exit:
- Lakes correctly detected in test regions (e.g. Crater Lake,
  Yellowstone hotsprings, alpine tarns)
- No false positives on saddles / shallow basins that aren't actual
  water bodies

## M27 - Ocean / coastal extension

**Goal**: coastal regions emit ocean water where biome_label says
"coastal" and bathymetric source data is available.

Inputs:
- GEBCO bathymetry (Track A2 source — pulled if not already cached)
- Sea-level rules per region (typically 0m for present-day Earth)
- Coastline data (OpenStreetMap, USGS DEM coastline products)

Deliverables:
- `pipelines/terrain/extend_coastal.py` — extends terrain heightmap
  with bathymetry beyond shoreline; emits ocean water mask
- `water/water_type_mask.png` populated with type=3 (ocean) regions
- `water/water_manifest.json` includes salinity + temperature per ocean
  body

Exit:
- At least 2 cached coastal regions have correct ocean extension
  (e.g. Olympic Peninsula, Big Sur)
- Inland regions (no coast) correctly emit no ocean

## M28 - Water type classification + flow direction

**Goal**: full water_type_mask coverage (river/lake/ocean/wetland/ice);
flow_direction.png correctly encoded for all flowing water.

Inputs:
- M25/M26/M27 outputs
- Climate hints for ice extent (latitude + elevation; deferred to M31
  if Köppen-Geiger isn't yet ready)

Deliverables:
- `pipelines/terrain/classify_water.py` — produces unified type mask
- Flow direction encoded as 2-channel RG (cos/sin) for river/ocean
  pixels; static for lake/wetland
- `water/water_manifest.json` finalized with per-feature parameters

Exit:
- All water pixels in test regions classified correctly
- Flow vectors point downhill / follow real-world river directions

## M29 - Water + scatter integration

**Goal**: scatter masks respect water bodies (no shrubs in lake beds,
sparse vegetation near river channels, riparian-density rules).

Inputs:
- M15 scatter mask infrastructure
- M25-M28 water outputs

Deliverables:
- `pipelines/terrain/water_aware_scatter.py` — modifies scatter
  density masks based on water proximity
- `scatter_manifest.json` extensions: per-feature "water-affinity"
  (avoid, neutral, prefer)
- Riparian zone scatter overrides (denser grass + reeds near rivers)

Exit:
- Scatter conformance scenes show no vegetation in/under water bodies
- Riparian zones have visibly different scatter density than dryland
  in test scenes

## M30 - Water material variants + conformance

**Goal**: per-mode water material variants + water-track conformance.

Inputs:
- All M25-M29 outputs
- Per-mode `.tres` material variant system (Phase E)

Deliverables:
- `world3/materials/water_<type>_<mode>.tres` for each water type
  × each view mode (river/lake/ocean × walk/iso/topdown)
- Water-track conformance scenes (clear-water, muddy-water, ice,
  riparian, deep-ocean)
- M13 promotion gate accepts water-track artifacts

Exit:
- Water renders correctly at close walk, medium walk, iso, and topdown
- Water track is **water-complete** per
  `WORLD3_COMPLETION_BAR_2026_05_10.md` section 4
- All conformance scenes pass review

---

# Weather system (M31-M39)

## M31 - Climate classification

**Goal**: per-region Köppen-Geiger climate zone + typical-weather
manifest.

Inputs:
- Real climate data (Köppen-Geiger global maps, NOAA reanalysis grids)
- biome_label.json (existing world3 contract)
- Latitude + elevation from height_meta.json

Deliverables:
- `pipelines/weather/classify_climate.py` — maps region → Köppen
  zone using biome class + latitude + elevation
- `weather/climate_class.json` per region: Köppen code, precipitation
  type frequencies, temperature ranges, season patterns
- Reference data: every cached real-DEM region has correct Köppen
  classification

Exit:
- Cached test regions (Big Bend, Olympic, Yosemite, Yellowstone,
  Sierra) match published Köppen-Geiger maps
- Procedural regions get plausible classification from biome rules

## M32 - Atmospheric color model + reference sky shader

**Goal**: per-(climate × weather-state × time-of-day) atmospheric color
tables + reference sky shader that consumes them.

Inputs:
- Atmospheric scattering models (Hosek-Wilkie, Preetham, or simplified
  blackbody-driven version)
- Per-mode color shift policies (walk shows full sky; iso shows
  ambient/scattered light only; topdown shows tint overlay)

Deliverables:
- `pipelines/weather/atmospheric_lut_gen.py` — generates color LUTs
  from physical scattering model
- `weather/atmospheric_lut.png` — 3D LUT (time × state × view-direction
  → sky/sun/ambient RGB)
- `weather/reference_shaders/atmospheric_color.gdshader` — sky shader
  that samples the LUT
- Reference sky scene for each climate × state × time-of-day

Exit:
- Sky color shifts correctly across day/night cycle in walk mode
- Iso mode shows correct ambient tint without rendering full sky
- Topdown mode applies weather-tint overlay without breaking gameplay
  readability

## M33 - Volumetric cloud system (TRACK D1 PROMOTED HERE)

**Goal**: per-climate cloud-type distribution + reference volumetric
cloud shader. **Track D1 (nebula-statistics cloud generator) is the
source** — promoted from queued option to scheduled.

Inputs:
- Hubble/JWST nebula imagery corpus (per Track D1 spec)
- Cloud-class definitions (cumulus, stratus, cirrus, storm, fog-layer)
- Per-climate cloud-type frequency from M31

Deliverables:
- `pipelines/weather/nebula_to_cloud_signatures.py` — Track D1
  implementation: extracts cloud statistics from nebula imagery,
  fits to 6 cloud-type signatures, exports 3D volume textures or
  shader-input noise stacks
- `weather/cloud_distribution.json` — per-climate cloud-type weights
  + altitude bands + density rules
- `weather/reference_shaders/volumetric_clouds.gdshader` — volumetric
  cloud shader using the signature noise stacks
- Per-(climate × state) cloud reference scenes

Exit:
- Clouds render at walk-mode quality matching AAA bar
- Per-climate cloud distributions are visibly different (cumulus over
  grasslands, stratus over coastal, cirrus over alpine, storm clouds
  in stormy state)
- Track D1 deliverables ship as part of this M (no separate Track D
  work needed for clouds)

## M34 - Precipitation system

**Goal**: rain/snow/hail particle systems with per-climate rules +
per-mode LOD.

Inputs:
- Per-climate precipitation frequencies from M31
- Particle physics references (terminal velocity, drift, splash)

Deliverables:
- `pipelines/weather/precipitation_manifest_gen.py` — generates
  per-climate precipitation parameter tables
- `weather/precipitation_manifest.json` — type frequencies + intensity
  curves + particle counts per intensity + fall velocity per type
- `weather/reference_shaders/precipitation_particles.gd` — Godot
  particle system implementations for rain/snow/hail
- Per-mode LOD: walk uses full particle counts; iso uses reduced;
  topdown shows ambient streak overlay only

Exit:
- Rain looks like rain at all three view modes
- Snow drifts correctly with wind_field input
- Hail bounces realistically
- Per-climate precipitation type matches expected (no snow in tropical
  biomes; rain rare in deserts)

## M35 - Surface response

**Goal**: wet/snow/ice/mud material variants across the full catalog +
accumulation rules.

Inputs:
- M1 material catalog (full extent)
- Per-precipitation surface-response thresholds

Deliverables:
- `pipelines/weather/generate_surface_variants.py` — generates
  wet/snow/ice/mud variants for every catalog material
- `world3/materials/<id>_<state>.tres` for each (material × state)
- `weather/surface_response.json` — accumulation thresholds per
  material per state; per-mode visibility rules
- `weather/reference_shaders/surface_response/` — drop-in shaders for
  consumers; can be replaced
- Per-mode: walk shows puddles + ice patches; iso shows accumulated
  snow-line; topdown shows tint shifts

Exit:
- Every catalog material has at least wet + snow variants generated
- Surface response renders at walk-mode close-play quality
- Accumulation thresholds produce visible state transitions over time
  in conformance scenes

## M36 - Vegetation response

**Goal**: scatter masks gain wind-driven sway + storm flattening
parameters; reference vegetation shader extensions.

Inputs:
- M15 scatter system
- wind_field manifest from M-pending (or built during M36)
- Per-scatter-type vegetation response rules (grass flattens fully,
  trees sway, branches break in extreme storms)

Deliverables:
- `pipelines/weather/wind_field_gen.py` — per-climate prevailing-wind
  manifest
- `weather/wind_field.json` — prevailing wind direction + magnitude +
  storm overrides + per-state multipliers
- Per-scatter vegetation-response parameters in scatter_manifest.json
- `weather/reference_shaders/vegetation_response.gdshader` — adds
  wind-sway to scatter materials without breaking existing scatter
  conformance

Exit:
- Grass + leaves visibly sway with wind in walk mode
- Storms flatten grass to a degree appropriate to storm intensity
- Iso/topdown show wind direction subtly (e.g. directional brightness
  bias on scatter clusters)

## M37 - Atmospheric volumetrics

**Goal**: fog/haze/dust/mist per (climate × state); reference volumetric
fog shader.

Inputs:
- M31 climate classes
- Mist-over-water coupling rules (from water track)

Deliverables:
- `weather/atmospheric_volumetrics.json` — per-(climate × state)
  density + color + scale parameters; mist-over-water rules
- `weather/reference_shaders/atmospheric_volumetrics.gdshader` —
  reference volumetric fog implementation
- Per-mode: walk shows full volumetric; iso shows ambient haze tint;
  topdown shows atmospheric overlay

Exit:
- Dawn mist over water bodies looks right at walk
- Desert dust haze reads correctly in dust-storm state
- Fog density per climate is plausible (foggy coasts, dry deserts)

## M38 - Weather state transitions

**Goal**: Markov-style state machine manifest that consumer ticks at
game-time.

Inputs:
- All previous weather subsystems
- State-transition probabilities from real climate data

Deliverables:
- `pipelines/weather/state_transitions_gen.py` — generates per-climate
  state-machine: weather-state transition probabilities, time-of-day
  coupling, min/max durations per state
- `weather/state_transitions.json` — Markov-style transition matrix +
  duration parameters; time-of-day modifiers
- Documentation: how the consumer reads this and animates state
  changes

Exit:
- State transitions are climate-appropriate (deserts spend most time
  clear; coastal regions cycle through overcast/rain frequently;
  alpine winter favors snow + clear)
- Transition timescales are believable (storms last hours, clear-sky
  states last days)

## M39 - Conformance + opt-in integration verification

**Goal**: full weather-system conformance + verified on/off behavior.

Inputs:
- All M31-M38 deliverables
- Pre-weather conformance suite (from M18 work)

Deliverables:
- `weather/conformance_scenes/` populated with per-(mode × climate ×
  state) validation scenes
- `pipelines/weather/conformance_runner.py` — scripted validation that
  loads a bundle, toggles weather on/off, renders all conformance
  scenes, reports pass/fail
- **On/off verification**: scripted test that runs the same bundle
  through with-weather and without-weather pipelines and confirms
  the without-weather output is identical to a pre-weather bundle
  (modulo `weather/` directory presence)
- Documentation: how a consumer opts in to weather + how to disable
  it cleanly
- M13 promotion gate accepts the full weather system at all four bands

Exit:
- All conformance scenes pass at all four gameplay bands
- Weather on/off toggle works cleanly; off-state bundles are
  identical to pre-weather bundles
- Weather system is **weather-complete** per
  `WORLD3_COMPLETION_BAR_2026_05_10.md` section 5
- world3 hits **all six completion conditions**; pipeline is done

---

## Realistic timeline

Per `WORLD3_COMPLETION_BAR_2026_05_10.md`:

- Water track (M25-M30): ~10-15 sessions
- Weather system (M31-M39): ~18-30 sessions; M35 (surface response
  across the full material catalog) and M33 (volumetric cloud
  reference shader) are the heaviest single Ms

Total water + weather: ~28-45 sessions / ~5-9 months at current
cadence. End-of-roadmap work; runs after M19-M24 closes.

## Risks

- **R1 — Weather reference shaders are the largest visual-quality
  commitment world3 has made.** If quality slips here, "bad weather is
  worse than no weather" applies and we should skip rather than ship.
  Mitigation: per-M visual review against AAA bar; willingness to
  defer specific reference shaders (e.g. ship the manifests + a
  subset of shaders) if quality can't be met for all six subsystems.
- **R2 — Weather × water coupling rules are intricate.** Cold weather
  freezes lakes; rain raises river levels; ice forms on water
  surfaces; mist forms over water. These rules live in
  `state_transitions.json` but are easy to get wrong. Mitigation:
  M38 coupling rules get explicit conformance scenes.
- **R3 — Per-mode parity is harder for weather than terrain.**
  Topdown weather is a known gameplay-readability hazard; we cannot
  let storm volumetrics obscure tactical information. Mitigation: per
  weather subsystem, the topdown rendering is **always a tint or
  icon overlay**, never a depth-occluding effect.
- **R4 — Caption / animation drift.** Reference shaders may need
  per-Godot-version updates as the engine evolves. Mitigation:
  pin Godot version per release; update reference shaders only at
  pipeline version bumps.

## What this roadmap does NOT do

- No game built on world3. world3 emits the data + reference shaders;
  the consumer game does the integration + animation + sound.
- No real-time weather simulation. State transitions are
  consumer-ticked; world3 emits the rules.
- No interactive weather (player triggers a storm). That's game
  logic; consumer-side.
- No biome-altering weather over time (climate change simulation).
  Static climate per region.

## Cross-references

- Contract: [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md)
- Completion bar: [`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md)
- Sequential M-chain: [`ROADMAP.md`](ROADMAP.md)
- Hybrid procedural plan (upstream): [`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md)
- Post-parity plan: [`M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`](M13_M18_POST_PARITY_ROADMAP_2026_05_10.md)
- Track D source for clouds: [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md) Track D1
- Long-term vision: `../../docs/plans/LONG_TERM_VISION.md`

## Status

NOT STARTED. Gated by:

1. M19-M24 closure (hybrid procedural infinite world)
2. Per `WORLD3_COMPLETION_BAR_2026_05_10.md`, water track runs first;
   weather second.

End-of-roadmap work. When M39 closes, world3 hits the completion bar.
