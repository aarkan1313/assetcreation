# World3 Output Contract — 2026-05-10

**Status**: spec doc, current as of 2026-05-10. Captures what world3
**already** emits (M1-M12 work) plus what it **will** emit (M13-M24 +
water-track additions). Single source of truth for the world3 output
contract so downstream consumers (games, tools, review harnesses) can
build against it.

This doc is paired with [`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md),
which defines what "world3 is complete" means.

---

## What world3 is

world3 is a **world-generation pipeline**. It ingests source data (real
DEMs, biome rules, material library, procedural seeds) and emits
world-data bundles with a documented contract that any downstream
consumer can render.

world3 is **not** a game, runtime, scene assembler, or game engine.
The Godot scenes under `world3/scenes/` are **review/validation
harnesses** — they prove the contract works, they don't define gameplay.

world3 has **one downstream-facing concern**: emit valid bundles that
match this contract.

---

## The output contract (bundle layout)

A world3 **region bundle** is a directory at a stable path. Every
region produced by world3 conforms to this shape:

```
<region_id>/
├── meta.json                          ← REQUIRED. region identity + provenance
├── height.png                         ← REQUIRED. 16-bit grayscale heightmap
├── height_meta.json                   ← REQUIRED. height domain + spacing
├── macro_color.png                    ← REQUIRED. macro albedo (source or synthesized)
├── source_macro_valid_mask.png        ← REQUIRED. valid-pixel mask for macro
├── splat_weights.png                  ← REQUIRED for splat-shader regions
├── splat_manifest.json                ← REQUIRED. material id → channel binding
├── biome_label.json                   ← REQUIRED. region biome assignment + transitions
├── transitions/                       ← OPTIONAL. per-pair transition strips
│   └── <kit_a>__<kit_b>.png
├── junctions/                         ← OPTIONAL. corner/three-way layers
│   └── <kit_a>__<kit_b>__<kit_c>.png
├── scatter_masks/                     ← OPTIONAL but populated by M15+
│   ├── <feature>.png                  ← e.g. shrub.png, grass.png, rock.png, wash.png
│   └── scatter_manifest.json
├── water/                             ← OPTIONAL but populated by water track
│   ├── water_height.png               ← per-pixel water surface elevation
│   ├── water_type_mask.png            ← river / lake / ocean / wetland classification
│   ├── flow_direction.png             ← 2-channel encoded flow vectors (rivers)
│   └── water_manifest.json            ← parameters: salinity, opacity, flow rate
├── weather/                           ← OPTIONAL; populated only if weather module is opt-in enabled
│   ├── climate_class.json             ← Köppen-Geiger + region patterns
│   ├── atmospheric_lut.png            ← color tables (climate × state × time)
│   ├── cloud_distribution.json        ← cloud-type rules (Track D1 source)
│   ├── precipitation_manifest.json    ← type frequencies + intensity curves
│   ├── surface_response.json          ← wet/snow/ice/mud accumulation
│   ├── wind_field.json                ← prevailing wind + magnitude
│   ├── atmospheric_volumetrics.json   ← fog/haze/dust/mist params
│   ├── state_transitions.json         ← weather-state-machine manifest
│   ├── reference_shaders/             ← drop-in opt-in visual impls
│   └── conformance_scenes/            ← per-(mode × climate × state) validation
└── chunks/                            ← OPTIONAL. pre-chunked variant for streaming
    └── <chunk_x>_<chunk_z>/
        ├── height.png
        ├── macro_color.png
        ├── splat_weights.png
        ├── (water/, scatter_masks/ if applicable)
        └── chunk_meta.json
```

### File-level guarantees

| File | Format | Constraints |
|---|---|---|
| `meta.json` | JSON | Must include `region_id`, `provenance` (real \| procedural \| hybrid), `bounds`, `biome_classes`, `style`, `generator_version` |
| `height.png` | 16-bit grayscale PNG | sRGB-disabled, linear encoding; height = pixel × (range / 65535) + min |
| `height_meta.json` | JSON | `width_m`, `height_m`, `mesh_spacing_m`, `elev_min`, `elev_range`, `crs` (optional) |
| `macro_color.png` | 8-bit sRGB RGB | matches height resolution OR a documented integer downsample |
| `source_macro_valid_mask.png` | 8-bit grayscale | 0 = invalid (no source coverage); 255 = valid; intermediate = blended boundary |
| `splat_weights.png` | 8-bit RGBA | each channel = weight of slot N; 5th slot derived as remainder |
| `splat_manifest.json` | JSON | maps channel index → catalog material id; declares which 5th-slot rule applies |
| `biome_label.json` | JSON | `primary_biome`, `transition_pairs[]`, `corner_triples[]`, references `world3/jobs/biome_transition_rules.json` |
| `transitions/<a>__<b>.png` | 8-bit RGBA | 2D blended strip per M2 contract; bound via `splat_manifest.json` |
| `junctions/<a>__<b>__<c>.png` | 8-bit RGBA | M11 three-way junction; bound the same way |
| `scatter_masks/<feature>.png` | 8-bit grayscale | density map; 0 = none, 255 = max-density placement |
| `scatter_manifest.json` | JSON | per-mask: `feature`, `material_role`, `geometry_class`, `density_units`, downstream-LOD policy |
| `water/water_height.png` | 16-bit grayscale | same encoding as `height.png`; "no water" pixels = 0; consumer must compare against terrain |
| `water/water_type_mask.png` | 8-bit indexed | 0=none, 1=river, 2=lake, 3=ocean, 4=wetland, 5=ice (extensible) |
| `water/flow_direction.png` | 8-bit RG | R=cos(angle)*128+128, G=sin(angle)*128+128; rivers/ocean only |
| `water/water_manifest.json` | JSON | per-feature: `type`, `bounds`, `flow_rate`, `salinity`, `optical_depth`, `temperature` |
| `chunks/<x>_<z>/chunk_meta.json` | JSON | `chunk_origin_m`, `chunk_size_m`, `parent_region_id`, downsample/repeat policy |

### Hard rules

1. **Every file in the bundle is reproducible** from inputs + `generator_version`.
   No hand edits survive a regen; if they do, they're sidecar candidates
   in a separate manifest, not in the bundle.
2. **All raster files share a coordinate frame** — same orientation
   (Z+ north or per `meta.json` declaration), same origin, integer
   relationship between resolutions.
3. **No fake fallback data**. If source coverage is missing for a region
   of macro_color, `source_macro_valid_mask` MUST reflect that. Consumer
   decides how to render invalid pixels (clip, fade, fill).
4. **Materials referenced by id**, not path. `splat_manifest.json` and
   `scatter_manifest.json` reference catalog ids from
   `world3/materials/catalog.json`. Consumer resolves to disk paths.
5. **Chunks are derivable from the un-chunked region.** Pre-chunked
   variants exist for streaming; they're not authoritative on their own.

### Versioning

`meta.json.generator_version` is the world3 git ref (short sha + tag
when applicable) that produced the bundle. Bumps are recorded in
`world3/docs/CONTRACT_CHANGELOG.md` (created when needed). Bundle
consumers pin against `generator_version` ranges.

---

## What the contract does NOT cover

These are explicitly **out of scope** for world3. They belong to the
consumer (game engine, tool, downstream pipeline):

- **Runtime** — meshing, GPU upload, shader instances, draw calls
- **Camera / view modes** — world3 provides per-mode `.tres` material
  variants (Phase E) but doesn't ship a camera
- **Game systems** — gameplay, AI, NPCs, dialogue, quests, inventory,
  save/load, UI, audio, time-of-day, lighting, weather (see note below
  on weather as stretch)
- **Animation** — characters, foliage sway, water surface waves; world3
  emits static data + parameter manifests
- **VFX / particles** — emitted from masks (scatter, water) but never
  composed by world3
- **Localization / text** — region names exist in `meta.json` as
  identifiers, not display strings
- **Networking, persistence, save game**
- **Audio mixing** — even ambient biome audio is consumer-side

If a consumer wants any of the above, it consumes the relevant world3
output (e.g. ambient audio uses `biome_label.json` + `scatter_manifest`
to drive its own logic) but the **integration glue is not world3's job**.

---

## What the contract DOES cover

Everything world3 emits at the boundary. The consumer's job is to load
this and render it; world3's job is to guarantee it's valid, complete,
and reproducible.

The contract evolves through M-numbered work:

| File / lane | First emitted | Stabilized at |
|---|---|---|
| `height.png` + `height_meta.json` | M1 | M12 (per source-stack policy) |
| `macro_color.png` + `source_macro_valid_mask.png` | M6 source-stack work | M12 |
| `splat_weights.png` + `splat_manifest.json` | M4 | M12 |
| `transitions/` | M2 prototype | M7 runtime integration |
| `junctions/` | M11 | M11 (workflow evidence accepted) |
| `biome_label.json` | M1 (catalog) | M7 (rules-driven) |
| `chunks/` | M3 sweep | M5 (256 m locked) |
| `scatter_masks/` | M10/M11 feature masks (workflow) | M15 (production scatter lane) |
| `water/` | M-track post-M24 (M25-M30) | M30 |
| `weather/` (opt-in) | M-track post-M30 (M31-M39) | M39 |
| `weather/reference_shaders/` (opt-in) | M32 onward | M39 |
| Per-mode `.tres` material variants | Phase E (current) | M12 (parity proof) |

---

## Water track (committed; M-numbers TBD post-M24)

Water is a real terrain-adjacent concern, not a runtime/gameplay concern,
so it belongs in world3's contract.

### Why water belongs in world3

1. Water surface is a **second heightfield** layered on the terrain
   heightfield. Same data shape as `height.png`; same chunking; same
   coordinate frame.
2. Water masks affect **scatter density** (no shrubs in lake beds, no
   trees in river channels). Already inside M15 territory.
3. Water type masks affect **biome labels and material selection**
   (riverbed = different material than dry channel). Splat-shader job.
4. Erosion (M20) **naturally produces drainage networks**. Going from
   "Landlab told us where water flows" to "world3 emits water masks
   matching those flows" is a small step, not a new pipeline.

### Out-of-scope for water track (still consumer-side)

- Animated waves / surface shader
- Player swimming / wading physics
- Water audio (splash, flow, lap)
- Reflections / refractions at runtime
- Flow simulation at game-time (we emit static flow direction; runtime
  may animate from that)

### Probable M-chain for water (sketched, not committed)

| M | Scope |
|---|---|
| M25 | Water mask emission from M20 erosion drainage networks (rivers, channels) |
| M26 | Lake / pond detection from terrain depressions + closed drainage |
| M27 | Ocean / coastal extension where biome_label says "coastal" + bathymetric source available |
| M28 | Water type classification + flow direction encoding |
| M29 | Water + scatter mask integration (no-vegetation rules in water bodies) |
| M30 | Water-source promotion gate (per M13) + per-mode water material variants |

This is a sketch. Actual M-numbers assigned when M24 closes and water
work is committed.

---

## Weather track (committed; END-OF-ROADMAP; M31-M39 sketched)

Weather is **committed scope** as of 2026-05-10. End-of-roadmap work —
runs after the water track (M25-M30) closes.

Full system, not data-only. Per `WORLD3_COMPLETION_BAR_2026_05_10.md`:
bad weather is worse than no weather. If we ship it, it has to meet
the AAA-grade environment-art bar from `LONG_TERM_VISION.md`. That
means all six interlocking subsystems (atmospheric color, volumetric
clouds, precipitation, surface response, vegetation response,
atmospheric volumetrics) **plus** reference shader implementations,
**plus** state transitions, **plus** conformance scenes per
(mode × climate × state).

### On/off semantics

The weather module is a clean opt-in. Single switch turns the whole
system on or off:

- **Weather disabled**: bundles look exactly like pre-weather bundles.
  No `weather/` directory present; no atmospheric color overrides;
  default biome material variants; no precipitation; no
  surface-response masks. Bundles validate against the pre-weather
  contract.
- **Weather enabled**: full system activates. `weather/` directory
  populated with all manifests + reference shaders + conformance
  outputs. Consumer reads from the manifests and animates per the
  state-transition rules.

No half-states. No "weather data without shaders" or "weather shaders
without data." If a consumer disables weather mid-stream, the bundles
remain valid pre-weather bundles.

### Why we ship reference shaders, not just data

A consumer game implementing weather from JSON manifests alone would
have to build atmospheric scattering, volumetric clouds, particle
systems, wet-surface shaders, vegetation sway shaders, fog shaders,
and state-transition logic from scratch. That's a quarter-year of
shader work the consumer has to do **just to use weather at all**.

By shipping reference implementations alongside the data, we:

1. Enforce the quality bar (the reference impls are tested + audited)
2. Let consumers drop in the full system in a single integration pass
3. Allow modular replacement (a consumer can swap our cloud shader
   for their own without rebuilding the data layer)

The reference shaders are **the proof the contract is real**. Without
them, "weather support" is a manifest format with no guarantee anyone
can actually render it.

### Bundle layout (weather enabled)

```
<region_id>/
└── weather/
    ├── climate_class.json           ← Köppen-Geiger zone + region patterns
    ├── atmospheric_lut.png          ← color tables, (climate × state × time)
    ├── cloud_distribution.json      ← per-climate cloud-type rules
    ├── precipitation_manifest.json  ← type frequencies + intensity curves
    ├── surface_response.json        ← wet/snow/ice/mud accumulation rules
    ├── wind_field.json              ← prevailing wind direction + magnitude
    ├── atmospheric_volumetrics.json ← fog/haze/dust/mist parameters
    ├── state_transitions.json       ← weather-state-machine manifest
    ├── reference_shaders/
    │   ├── atmospheric_color.gdshader
    │   ├── volumetric_clouds.gdshader
    │   ├── precipitation_particles.gd     ← particle systems, not shaders
    │   ├── surface_response/
    │   │   └── <material_id>_<state>.gdshader   ← per-material wet/snow/ice/mud variants
    │   ├── vegetation_response.gdshader
    │   └── atmospheric_volumetrics.gdshader
    └── conformance_scenes/
        └── <mode>_<climate>_<state>.tscn
```

### Per-file guarantees (weather)

| File | Format | Purpose |
|---|---|---|
| `climate_class.json` | JSON | Per-region: Köppen-Geiger zone, precipitation type frequencies, temperature ranges, season patterns |
| `atmospheric_lut.png` | 16-bit RGBA | 3D lookup: time-of-day × weather-state × view-direction → sky/sun/ambient colors |
| `cloud_distribution.json` | JSON | Per-climate cloud-type weights (cumulus, stratus, cirrus, storm); density distributions; altitude bands; uses Track D1 nebula-statistics generators as source |
| `precipitation_manifest.json` | JSON | Per-climate rules: precipitation type (rain/snow/hail/freezing-rain), intensity-vs-time curves, particle counts per intensity, fall velocity |
| `surface_response.json` | JSON | Wetness/snow-depth/ice-thickness/mud-saturation accumulation thresholds per material; per-mode visibility (close shows puddles, topdown shows snowline) |
| `wind_field.json` | JSON | Per-region prevailing direction + magnitude; storm-strength overrides; per-state wind multipliers |
| `atmospheric_volumetrics.json` | JSON | Fog/haze/dust/mist density distributions per state; mist-over-water rules where water track exists |
| `state_transitions.json` | JSON | Markov-style transition probabilities between weather states; time-of-day coupling; min/max state durations |
| `reference_shaders/*.gdshader` | Godot shader | Drop-in implementations; consumer can replace any with their own |
| `conformance_scenes/*.tscn` | Godot scene | Per-(mode × climate × state) validation scenes that prove the full system renders correctly |

### Hard rules (weather track)

1. **Toggling weather off produces bundles identical to pre-weather
   bundles** (modulo absence of `weather/` directory). Verified by
   conformance.
2. **Weather state machine is consumer-driven**, not world3-baked.
   world3 emits the rules; the consumer ticks the clock.
3. **Reference shaders are replaceable**, not required. A consumer can
   ship without the reference shaders and roll their own visuals from
   the data; world3 makes no promise about quality in that case.
4. **Per-mode parity holds** for weather just like terrain. Walk
   shows clouds + precipitation + surface response. Iso shows cast
   shadows + atmospheric color + accumulated snow lines. Topdown
   shows weather-state icon overlays + biome-tinted color shifts.
5. **Water track interaction**: weather affects water (rain raises
   river levels in `flow_direction` interpretation; cold weather
   ices over lakes via `water_type_mask` override). These coupling
   rules live in `state_transitions.json` and are evaluated by the
   consumer.

### Out-of-scope (weather track)

- **Real-time weather simulation logic at game-time**. Consumer ticks
  the state machine; world3 emits the rules.
- **Day/night cycle simulation**. `atmospheric_lut.png` is keyed by
  time-of-day but the clock itself is consumer-side.
- **Weather audio** (thunder, rain hiss, wind howl). Consumer-side;
  state_transitions.json provides the cue triggers.
- **Lightning strike simulation**, **tornado spawning**, **named
  storm events**. Game-specific; build on the manifests, don't bake
  in.

### M-chain sketch

Full breakdown in
[`M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md`](M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md).
Summary:

| M | Scope |
|---|---|
| M31 | Climate classification per region (Köppen-Geiger + biome_label) |
| M32 | Atmospheric color model + reference sky shader |
| M33 | Volumetric cloud system (uses Track D1 nebula-statistics source) |
| M34 | Precipitation system (rain/snow/hail) + per-mode LOD |
| M35 | Surface response (wet/snow/ice/mud) across material catalog |
| M36 | Vegetation response (wind sway, storm flattening) |
| M37 | Atmospheric volumetrics (fog/haze/dust/mist) |
| M38 | Weather state transitions + state machine manifest |
| M39 | Conformance + opt-in integration + weather-on/off verification |

---

## Conformance

A world3 build "conforms" if:

1. Running the full pipeline on a known input (e.g. a cached OpenTopo
   DEM + a biome assignment) produces a bundle matching this contract
2. The bundle loads through the world3 review scenes
   (`source_stack_*.tscn` family) without errors
3. The M13 production-promotion gate accepts the bundle's artifacts as
   `workflow_evidence` (or higher)
4. Per-mode material variants (`_walk.tres`, `_iso.tres`, `_topdown.tres`)
   render the bundle correctly across all three modes per the M12
   parity contract

**Conformance suite location**: review scenes already exist; formalizing
them into a per-release "conformance run" is part of M13 hygiene work
and probably an M-numbered task at the M18 realignment.

---

## Cross-references

- Completion bar: [`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md)
- Current state: [`WORLD3_STATE_2026_05_08.md`](WORLD3_STATE_2026_05_08.md)
- Sequential M-chain: [`ROADMAP.md`](ROADMAP.md)
- Post-parity plan: [`M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`](M13_M18_POST_PARITY_ROADMAP_2026_05_10.md)
- Hybrid procedural plan: [`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md)
- Material catalog: `world3/materials/catalog.json`
- Transition rules: `world3/jobs/biome_transition_rules.json`
- Data catalog: `../../docs/MASTER_DATA_CATALOG.md`
- Long-term direction: `../../docs/plans/LONG_TERM_VISION.md`

## Change log

- **2026-05-10**: Initial spec. Captures M1-M12 contract reality
  (height, macro, valid mask, splat, transitions, junctions, chunks,
  biome label, scatter masks) + committed water track additions + weather
  stretch.
- **2026-05-10 (later)**: Promoted weather from stretch to **committed
  scope, full system** (M31-M39). Adds 9 weather manifest files +
  reference shader directory + conformance scene directory. Opt-in
  module: single switch turns the whole `weather/` directory + system
  on or off; bundles validate against pre-weather contract when
  disabled. Track D1 (nebula-statistics cloud generator) promoted from
  queued option to M33 source.
