# World3 System Architecture — TEMPORARY SNAPSHOT 2026-05-10

> ⚠️ **TEMPORARY MAP. WILL BE REAUDITED AT M18 CLOSE.**
>
> This doc captures what we plan to build *as of 2026-05-10*, organized
> as a module graph rather than a sequential M-chain. It exists so
> future-you (or any session that opens this project later) can see
> how the parts fit together without reading 15 other docs first.
>
> **What it is**: a snapshot of current planning intent. Module names,
> module contents, the dependency graph, the coupling rules between
> modules, and a map from existing docs/M-numbers/Tracks back to modules.
>
> **What it is not**: a fixed design. A commitment that this is the
> final architecture. A replacement for the per-M roadmaps.
>
> **Reaudit gate**: when M18 closes, this doc gets a full re-pass with
> the benefit of M14-M18 hindsight. The reaudit may rename modules,
> split or merge them, reassign Ms, or invalidate parts of this
> snapshot entirely. That's expected.
>
> **Why halfway**: writing this map at M18 from scratch is harder than
> writing it now and editing it then. Halfway-done is cheaper than
> all-or-nothing.

---

## TL;DR — what world3 builds

world3 emits **world-data bundles**. The bundles describe a streamed,
biome-coherent slice of world space, suitable for any consumer game or
tool to render. The bundles are produced by **eight content modules**
and **one infrastructure module**, organized in a dependency graph
where lower-level modules feed upper-level ones.

The completion bar (per
[`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md))
says world3 is done when every module ships at workflow tier with
per-mode parity, the M13 gate is clean, and the conformance suite
validates every module across the knob-space.

---

## The eight content modules

Each module owns a part of the bundle. Each has its own opt-in
semantics where applicable, its own per-mode quality bars, its own
conformance scope.

```
┌──────────────────────────────────────────────────────────────────┐
│ Module 9: CONFORMANCE & GATES (cross-cutting)                    │
│  contract spec, M13 promotion gate, review scenes, audit tools   │
└──────────────────────────────────────────────────────────────────┘

┌─────────────┐                                    ┌──────────────┐
│ Module 7:   │  ◄── atmospheric color ◄────────►  │ Module 8:    │
│ SKY         │      sun/moon position             │ WEATHER      │
│             │                                    │              │
│ stars,      │                                    │ clouds,      │
│ milky way,  │                                    │ precip,      │
│ sun/moon    │                                    │ state machine│
│ disk,       │                                    │              │
│ aurora      │                                    │              │
└──────┬──────┘                                    └──────┬───────┘
       │                                                  │
       └─────────────►  Module 6: ATMOSPHERE  ◄───────────┘
                       (color LUT, scattering,
                        fog/haze/dust/mist)
                              │
                              ▼
                   ┌──────────────────────┐
                   │ Module 4: SCATTER &  │
                   │ FEATURES             │
                   │                      │
                   │ vegetation, rocks,   │
                   │ debris, wind response│
                   └──────────┬───────────┘
                              │
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Module 5:   │    │ Module 3:        │    │ Module 2:       │
│ WATER       │    │ TRANSITIONS &    │    │ MATERIAL CATALOG│
│             │    │ JUNCTIONS        │    │                 │
│ rivers,     │    │                  │    │ kits, per-mode  │
│ lakes,      │    │ biome bridges,   │    │ variants, splat │
│ ocean,      │    │ corners, ecotones│    │ shader binding  │
│ ice         │    │                  │    │                 │
└──────┬──────┘    └────────┬─────────┘    └────────┬────────┘
       │                    │                       │
       └────────────────────┴───────────────────────┘
                            │
                            ▼
                ┌────────────────────────┐
                │ Module 1: TERRAIN      │
                │ FOUNDATION             │
                │                        │
                │ heightmap, mesh,       │
                │ chunks, streaming,     │
                │ procedural generation, │
                │ source-stack contract  │
                └────────────────────────┘
```

**Reading the graph**:
- Arrows point from "depends on" to "depended upon" (top → bottom)
- Sky + Weather both depend on Atmosphere (they share color/scattering)
- Scatter depends on Atmosphere (wind sway visualization, lit/shadowed
  particle response)
- Water + Transitions + Materials all sit on Terrain Foundation
- Sky has *no* dependency on terrain — it's overhead, runs as a
  separate static layer
- Conformance + Gates is cross-cutting (every module validates through it)

---

## Module 1 — Terrain Foundation

**What it produces**: `height.png`, `height_meta.json`, `chunks/`,
`meta.json`, per-source provenance, biome labels, splat weights,
scatter masks (data layer only — textures live in Module 2).

**What it depends on**: nothing (it's the foundation).

**Framing note (2026-05-11)**: Terrain Foundation owns the
**placement layer** of the bundle — heightmap, biome labels, splat
weights, scatter masks, transitions, junctions. Procedural extensions
under M19-M24 generate this placement data. Textures themselves come
from **Module 2 (Material Catalog)** via the splat shader. Procedural
zones do not generate textures; they emit placement data that the
catalog renders.

**Status**:
- M1-M5: complete (catalog, transitions, chunk sweep, splat shader, walk streaming)
- M6: complete (runtime hardening, collision)
- M7: workflow complete, visual closure pending
- M19-M24: hybrid procedural extension planned

**Opt-in story**: not opt-in. Always present. Every bundle has terrain.

**Per-mode quality bar**: walk = close-play surface detail; iso = mid-scale ridge/valley readability; topdown = recognizable biome shape.

**Conformance**: every cell of the knob-space (source × view × style × granularity) must emit a valid terrain layer.

**Docs**:
- [`ROADMAP.md`](ROADMAP.md) M1-M5
- [`PLAN.md`](PLAN.md)
- [`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md)
- [`M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`](M13_M18_POST_PARITY_ROADMAP_2026_05_10.md) M17

---

## Module 2 — Material Catalog

**What it produces**: `world3/materials/catalog.json`, per-mode
`.tres` variants, splat manifest, material → shader binding.

**What it depends on**: nothing structural; consumes outputs from the
textures pipeline (`pipelines/textures/`).

**Status**:
- M1: complete (catalog spec)
- Phase E: complete (per-mode variants for 5 kits × 3 modes)
- M14: active (close-play texture quality for organic blockers)
- M35: future (wet/snow/ice/mud variants across full catalog — weather module dependency)

**Opt-in story**: catalog is always present. Per-mode variants always present. Per-state weather variants (M35) opt-in via weather module switch.

**Per-mode quality bar**: per Phase E — walk=detail, iso=midblend, topdown=color blocks.

**Conformance**: every catalog material renders correctly across all modes via the M12 parity contract.

**Docs**:
- [`ROADMAP.md`](ROADMAP.md) Phase A-E
- [`pipelines/textures/`](../../pipelines/textures/)
- [`pipelines/textures/WORKFLOW_GUIDE_FLUX2_2026_05_10.md`](../../pipelines/textures/WORKFLOW_GUIDE_FLUX2_2026_05_10.md)
- M14: [`M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md`](M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md)

---

## Module 3 — Transitions & Junctions

**What it produces**: `transitions/`, `junctions/`, `biome_label.json`, `biome_transition_rules.json` references.

**What it depends on**: Material Catalog (binds material pairs), Terrain Foundation (places strips at chunk boundaries).

**Status**:
- M2: prototype + tuning complete
- M7: runtime integration complete (workflow), visual closure pending
- M10: terrain seam integration accepted for several real-real + real-procedural pairs
- M11: three-way + four-way junction proofs accepted
- M-pending: unlike-biome ecotone (the rejected first attempt)

**Opt-in story**: not opt-in. Transitions are how biomes connect; can't disable without breaking biome adjacency.

**Per-mode quality bar**: walk = no visible hard cut; iso = readable ecotone; topdown = recognizable color blend.

**Conformance**: same-source mask QA passes (M7); cross-source proofs accepted (M10/M11).

**Docs**: M2, M7, M10, M11 docs.

---

## Module 4 — Scatter & Features

**What it produces**: `scatter_masks/`, `scatter_manifest.json`, feature-mask layers.

**What it depends on**: Terrain Foundation (chunks + heights), Material Catalog (per-scatter materials), Water module (water-aware rules), Atmosphere/Weather (wind response).

**Status**:
- M11: feature masks (workflow evidence)
- M15: future (production scatter + feature layers; small authored library; LOD policy by gameplay band)
- M29: future (water-aware scatter integration)
- M36: future (vegetation wind response — weather module)

**Opt-in story**: scatter is always present; per-feature scatter masks are optional per scatter manifest (a region might have no shrubs but always has *some* scatter mask file).

**Per-mode quality bar**: walk = individual instance quality; iso = cluster pattern readability; topdown = density gradient visibility.

**Conformance**: M15 promotion gate; per-(mode × biome) review of one representative scene.

**Docs**:
- [`M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`](M13_M18_POST_PARITY_ROADMAP_2026_05_10.md) M15
- [`M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md`](M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md) M29, M36
- Track C as the *consumer-side* scatter generator (not in scope for world3 emission)

---

## Module 5 — Water

**What it produces**: `water/water_height.png`, `water/water_type_mask.png`, `water/flow_direction.png`, `water/water_manifest.json`.

**What it depends on**: Terrain Foundation (drainage from erosion), Material Catalog (water material variants), Atmosphere (mist-over-water coupling).

**Status**: NOT STARTED. M25-M30 sketched.

**Opt-in story**: water directory present whenever there's any water in the region. Bundles without water = no `water/` directory. Consumer can render terrain without ever loading water if they choose.

**Per-mode quality bar**: walk = wet surfaces + reflective shader; iso = water-body shape + flow direction visible; topdown = water-type tactical color overlay.

**Conformance**: per-water-type validation scenes (river / lake / ocean / wetland / ice).

**Docs**: [`M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md`](M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md) M25-M30.

---

## Module 6 — Atmosphere

**What it produces**: `atmosphere/atmospheric_lut.png`,
`atmosphere/scattering_params.json`, `atmosphere/volumetrics.json`
(fog/haze/dust/mist).

**What it depends on**: nothing structural; pure physics + per-region climate hints from biome_label or weather/climate_class if weather module is enabled.

**Status**: NOT STARTED. Currently bundled inside the weather track (M32 atmospheric color + M37 volumetrics). **This snapshot splits atmosphere out as its own module** because both Sky and Weather depend on it. Reaudit will decide whether this split sticks.

**Opt-in story**: required if Sky OR Weather is opt-in enabled. If both disabled, atmosphere can be skipped entirely.

**Per-mode quality bar**: walk = full atmospheric scattering; iso = ambient tint shifts; topdown = atmospheric overlay color.

**Conformance**: per-(time-of-day × climate) atmospheric scenes.

**Docs**:
- Currently inside [`M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md`](M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md) M32, M37
- M18 reaudit decision: split into own M-arc OR keep nested in weather

**Coupling**:
- → **Sky**: atmospheric scattering colors the sky gradient between celestial bodies
- → **Weather**: atmospheric color shifts per weather state; volumetric fog runs in this module
- → **Materials**: ambient color affects rendered material brightness (consumer concern, but world3 emits the color reference)

---

## Module 7 — Sky (NEW; was a gap in prior planning)

**What it produces**: `sky/starfield.png` (or shader-input statistics),
`sky/milky_way.json` (band orientation + density), `sky/celestial_bodies.json`
(sun, moon, planets), `sky/aurora_params.json` (polar regions only).

**What it depends on**: Atmosphere (color shifts behind sky content), latitude + region orientation (where the celestial sphere sits).

**Status**: NOT STARTED. Was a gap surfaced when reviewing weather; now broken out as its own module. **Track D3 (procedural night sky from HYG statistics) is promoted to this module's source.**

Probable arc: 3-4 M-numbers. Sketched as `M_sky_*` placeholders pending the M18 reaudit:

| Sketch | Scope |
|---|---|
| M-sky-1 | Stellar statistics extraction from HYG/AT-HYG; per-region celestial-sphere orientation |
| M-sky-2 | Sun/moon disk + phase manifest; reference sky shader for celestial bodies |
| M-sky-3 | Milky way band texture + galactic-coordinate alignment per region |
| M-sky-4 | Aurora module for polar regions; conformance + opt-in verification |

**Opt-in story**: full opt-in. Bundles without `sky/` directory = consumer renders blank black-or-gradient sky (Atmosphere module handles the gradient). With `sky/` directory = stars, milky way, sun, moon, aurora all populate.

**Per-mode quality bar**: walk = full sky with stars + celestial bodies; iso = often clipped, skip or fade; topdown = no sky at all (skip entirely).

**Mode-specific opt-out**: even within "sky enabled" mode, sky can be disabled per view-mode. Topdown bundles don't include sky data even when the rest of the bundle has it.

**Conformance**: per-(time-of-day × latitude × hemisphere) walk-mode scenes; aurora-specific scenes for polar regions.

**Coupling**:
- ← Atmosphere: sky color gradient comes from atmosphere; sky content sits on top
- ← Weather: clouds occlude stars/sun/moon; storms hide sky entirely (consumer-side
  compositing decision driven by weather state)
- → no downward dependencies — sky doesn't affect terrain or scatter

**Docs**:
- This file (first time the module is named)
- Track D3 in [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md) (now scheduled, parallel to D1)
- M18 reaudit will commit specific M-numbers + contract spec

---

## Module 8 — Weather

**What it produces**: `weather/climate_class.json`,
`weather/cloud_distribution.json`, `weather/precipitation_manifest.json`,
`weather/surface_response.json`, `weather/wind_field.json`,
`weather/state_transitions.json`, `weather/reference_shaders/`,
`weather/conformance_scenes/`.

**What it depends on**: Atmosphere (color shifts per state), Sky (clouds occlude celestial bodies — coupling rule encoded in state_transitions.json), Materials (surface response variants), Scatter (vegetation response), Water (rain raises rivers, cold freezes lakes), Terrain (climate classification uses biome + latitude + elevation).

**Status**: NOT STARTED. M31-M39 sketched. **Notable correction in this snapshot**: M32 (atmospheric color) and M37 (atmospheric volumetrics) should be considered part of the **Atmosphere module**, not Weather — they're shared infrastructure used by both Sky and Weather. The M-numbers stay where they are; the *ownership* shifts to Atmosphere when M18 reaudit happens.

**Opt-in story**: full opt-in via single switch. Bundles without `weather/` = clear sky, no precipitation, no surface response. With `weather/` = full dynamic atmospheric system.

**Per-mode quality bar**: walk = full volumetrics + particles + surface response; iso = cast shadows + accumulated snow + atmospheric tint; topdown = weather-state icon overlay + biome tint shift.

**Conformance**: per-(mode × climate × state) scenes; weather-on/off equivalence test.

**Docs**: [`M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md`](M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md) M31, M33-M36, M38-M39 (M32 + M37 reassigned to Atmosphere at reaudit).

---

## Module 9 — Conformance & Gates

**What it produces**: the M13 promotion gate, conformance scene library, contract validation tools, audit reports.

**What it depends on**: every other module (it validates them all).

**Status**:
- M13: gate active (manifest + audit script + audit reports)
- Conformance scene library: review scenes exist; not formalized
- M18 work: formalize conformance suite as a per-release artifact
- M39 work: weather-on/off equivalence test added

**Opt-in story**: not opt-in. Always enforced. Every bundle goes through the gate before any artifact is "production promoted."

**Per-mode quality bar**: gate requires all four bands (close, medium, iso, topdown) of evidence for promotion.

**Docs**:
- [`M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`](M13_M18_POST_PARITY_ROADMAP_2026_05_10.md) M13
- [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md)
- [`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md)
- `world3/jobs/production_promotion_candidates.json`
- `world3/pipeline/audit_production_promotion_candidates.py`

---

## Coupling rules (the part the M-chain hides)

These are the **cross-module interactions** that have to work for the
system to read as coherent. Each is a rule the relevant modules must
honor.

| Coupling | Rule | Modules involved |
|---|---|---|
| Water × Scatter | No vegetation in or under water bodies. Riparian zones have denser scatter. | Water, Scatter |
| Water × Weather | Cold weather freezes lakes; storms raise river levels; rain produces mist over water. | Water, Weather, Atmosphere |
| Weather × Materials | Wet/snow/ice/mud material variants activate per weather state via surface_response thresholds. | Weather, Materials |
| Weather × Scatter | Wind sway driven by wind_field manifest; storms flatten grass. | Weather, Scatter |
| Weather × Sky | Clouds occlude celestial bodies; storms hide sky. **Compositing rule lives in weather/state_transitions.json**; consumer applies it. | Weather, Sky |
| Sky × Atmosphere | Sky content (stars, sun) sits on top of atmospheric color gradient. Sun/moon disk position drives the sun-aware portion of atmospheric scattering. | Sky, Atmosphere |
| Atmosphere × Materials | Ambient color from atmosphere affects material rendering brightness. **Consumer concern**; world3 emits the LUT, consumer applies the shading. | Atmosphere, Materials |
| Transitions × Biomes | Biome adjacency rules drive which transitions get generated. | Transitions, Terrain (via biome_label) |
| Procedural × Real | Hybrid regions blend real DEM patches with procedurally-eroded terrain; same-source-stack contract holds. | Terrain (procedural) |
| Conformance × everything | Every module's output flows through the M13 promotion gate. | Module 9, everything |

These couplings are what make the system feel coherent. Getting any of
them wrong is what makes it feel like glued-together parts. The M18
reaudit should verify each coupling is honored by the in-flight M
plans.

---

## Mapping existing artifacts to modules

For navigation. When you read a doc, this tells you which module it's
about.

| Doc / Track / Job | Primary module(s) | Notes |
|---|---|---|
| `ROADMAP.md`, `PLAN.md` | All | The sequential M-chain runs through every module |
| `WORLD3_CONTRACT_2026_05_10.md` | All (the spec) | Output contract spans every module |
| `WORLD3_COMPLETION_BAR_2026_05_10.md` | All | Completion conditions span every module |
| `WORLD3_STATE_2026_05_08.md` | All | Orchestrator state |
| `M13_M18_POST_PARITY_ROADMAP_2026_05_10.md` | Conformance (M13), Terrain (M14, M17), Materials (M14), Scatter (M15), Conformance (M16), Terrain (M18) | Most cross-module M-arc |
| `M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md` | Terrain (M19-M23), Materials (M24 style packs) | Procedural-foundation extension |
| `ATMOSPHERE_ARC_2026_05_10.md` | Atmosphere (A1-A5) | Foundational shared infrastructure for Sky + Weather |
| `SKY_ARC_2026_05_10.md` | Sky (S1-S5) | Track D3 promoted as source; runs after Atmosphere |
| `WATER_ARC_2026_05_10.md` | Water (W1-W6) | M20 erosion → drainage; bathymetry source |
| `WEATHER_ARC_2026_05_10.md` | Weather (WX-1 to WX-13) | Largest arc; Track D1 source for clouds |
| `CONFORMANCE_ARC_2026_05_10.md` | Conformance & Gates (C1-C4) | Closes long-term plan |
| `M_SEQUENCE_2026_05_10.md` | All | **Primary orchestrator view** — flat M timeline across all arcs |
| `M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md` | (superseded) | Old water+weather framing; arc docs are now canonical |
| `M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md` | Materials | Active work |
| `FUTURE_WORLD_SOURCES_2026_05_08.md` Track A | Terrain | Alternative source classes |
| Track B | (out of scope; separate pipeline) | Interiors, not world3 |
| `FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md` Track C | (out of scope; consumer-side) | Trees/scree generators called *on* world3 bundles |
| Track D1 | Weather → cloud generator | Promoted to M33 |
| Track D2 | Scatter (cosmic-web density) | Queued |
| **Track D3** | **Sky (NEW MODULE)** | Promoted from queued to this module's source |
| Track D4 | (consumer-side spell-color shader) | Queued; consumer concern |
| Track D5 | Terrain (procedural fantasy textures) + Materials | Queued; gated on M22 |
| Track D6 | (consumer-side map decoration) | Queued; consumer concern |
| `data_wishlist.json`, `MASTER_DATA_CATALOG.md` | Terrain (source data) | Real-DEM corpus |
| `M2_BOUNDARY_TRANSITION_CONTRACT.md` | Transitions | Stable contract |
| `M4_CHUNK_MATERIAL_CONTRACT.md` | Terrain + Materials | Splat-chunk binding |
| `M10_TERRAIN_SEAM_INTEGRATION_PROOF_*.md` | Transitions | Multi-source proofs |
| `M11_JUNCTION_*_PROOF_*.md` | Transitions | Three-way + four-way |
| `M12_RUNTIME_PARITY_PROOF_2026_05_10.md` | All (parity audit) | The "every module renders per-mode" proof |

---

## What this map adds that the per-doc files don't

1. **Names the modules.** Until now there were Ms and Tracks but no
   module-level vocabulary. "Weather" as a module is bigger than M31-M39;
   it's the conceptual unit those Ms ship pieces of.

2. **Shows the dependency graph.** The sequential M-chain reads as a
   timeline; the module graph reads as a system. Both are true; they
   answer different questions. "What do I work on next?" → M-chain.
   "How do the parts fit together?" → module graph.

3. **Surfaces the sky-vs-weather split.** Until this doc, sky-as-content
   was a gap nobody had named. Now it's a module with an explicit (if
   sketched) M-arc + Track D3 promoted to its source.

4. **Splits Atmosphere out from Weather.** M32 + M37 are currently
   inside the weather roadmap, but they're shared infrastructure
   between Sky and Weather. This snapshot calls that out; the M18
   reaudit decides whether to formalize the split (new M-arc for
   Atmosphere) or leave them nested in Weather.

5. **Documents coupling rules.** "Water × Weather" etc. aren't called
   out anywhere else as cross-cutting concerns. The M-chain hides them.

6. **Maps every existing doc back to a module.** Future-you reading any
   single doc can look up "what module does this belong to" and see how
   it fits the bigger picture.

---

## What this map does NOT do

- Does not redefine the M-chain. M14 is still active; M15-M39 still
  ship in order. The module map sits *above* the M-chain.
- Does not change the contract. Bundle layout per
  `WORLD3_CONTRACT_2026_05_10.md` is unchanged.
- Does not commit specific M-numbers to Sky. Sketched as
  `M-sky-1..M-sky-4`; M18 reaudit assigns real numbers.
- Does not commit to splitting Atmosphere out as its own M-arc.
  Sketched as the natural module boundary; M18 reaudit decides.
- Does not invalidate Tracks A/B/C/D. Tracks remain queued options.
  Promotions (D1 → M33, D3 → Sky module) are called out.
- Does not change the completion bar. Still six conditions.

---

## M18 reaudit checklist

When M18 closes, reread this doc and decide:

- [ ] Have any modules merged or split based on M14-M18 hindsight?
- [ ] Should Atmosphere become its own M-arc, or stay nested in Weather?
- [ ] Should Sky get committed M-numbers? Where in the sequence?
  (Probably parallel to Weather, but could be a separate arc.)
- [ ] Have any couplings turned out wrong / missed?
- [ ] Have any Tracks been promoted to scheduled work?
- [ ] Has the completion bar changed because of M14-M18 learnings?
- [ ] Update the module → doc map for any new docs that landed.

The reaudit is its own work item. It's not free — but it's much
cheaper than designing the architecture from scratch at M18 without
this snapshot to start from.

---

## Cross-references

- Output contract: [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md)
- Completion bar: [`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md)
- Current state: [`WORLD3_STATE_2026_05_08.md`](WORLD3_STATE_2026_05_08.md)
- Sequential M-chain: [`ROADMAP.md`](ROADMAP.md)
- Per-arc roadmaps:
  - [`M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`](M13_M18_POST_PARITY_ROADMAP_2026_05_10.md)
  - [`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md)
  - [`M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md`](M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md)
- Option registers:
  - [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md) — Tracks A, B, D
  - [`FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md`](FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md) — Track C
- Long-term direction: `../../docs/plans/LONG_TERM_VISION.md`

## Change log

- **2026-05-10**: Initial snapshot. Eight content modules + one
  infrastructure module identified. Sky surfaced as a new module
  (Track D3 promoted). Atmosphere sketched as a natural split from
  Weather (decision deferred to M18 reaudit). Coupling rules
  enumerated. Mapping from existing docs to modules. **Marked
  temporary; will be reaudited at M18.**
- **2026-05-10 (later)**: Long-term M-chain restructured. M25-M39
  flat range replaced with **arc-named docs** (Atmosphere / Sky /
  Water / Weather / Conformance) each with right-sized M-internal
  steps. Atmosphere split formalized in arc structure (decision still
  reaudit-gated, but the arc separation is in place). Module → doc
  map updated. Sequence timeline in
  [`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md) is now the
  primary orchestrator view.
