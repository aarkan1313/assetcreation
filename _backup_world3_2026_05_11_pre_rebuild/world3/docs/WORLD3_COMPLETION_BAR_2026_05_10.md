# World3 Completion Bar — 2026-05-10

**Status**: durable framing doc. Defines what "world3 is complete"
means so every decision from M14 onward can be measured against a
fixed target.

This doc is paired with [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md),
which defines the output contract world3 promises to emit.

---

## The bar (one paragraph)

**world3 is complete when** the output contract (per
`WORLD3_CONTRACT_2026_05_10.md`) is stable and locked, the full
knob-space (source × view × style × granularity per
`WORLD3_STATE_2026_05_08.md` section 1) emits valid contract bundles
that pass the M13 production-promotion gate at all four gameplay bands
(close, medium, iso, topdown) for at least one biome per style pack,
the water track ships water masks + flow direction + type
classification, the weather system ships as a full opt-in module
(data + reference shaders, on/off at consumer's choice), and the
conformance suite (review scenes) renders every bundle correctly
without errors.

---

## What that breaks into

Six testable conditions. world3 is complete when **all six** are true.

### 1. The contract is stable

`WORLD3_CONTRACT_2026_05_10.md` defines all 13+ required files in the
bundle. world3 is at "stable" when:

- Every file has a producer (a script or pipeline step that emits it)
- Every file has a documented format with explicit guarantees
- A `generator_version` bump never silently changes the contract shape
- The contract changelog records every change
- No downstream consumer needs to special-case "this region is from M-X
  and looks different from M-Y"

This isn't aspirational — most of this is true today through M12.
The remaining work is documenting + locking it.

### 2. Knob-space coverage

From `WORLD3_STATE_2026_05_08.md` section 1, the world3 knob-space:

| Knob | Values |
|---|---|
| **Source** | real ⇄ procedural ⇄ fantasy |
| **View** | 2D ⇄ iso ⇄ walk (3D) |
| **Style** | photoreal ⇄ stylized ⇄ fantasy |
| **Granularity** | whole-region kit ⇄ kit-mix ⇄ per-pixel splat |

world3 is at "covered" when **every cell of this knob-space emits a
valid contract bundle** that passes the M13 gate at one biome per style.

Today's coverage (approximate):

| Cell | Status |
|---|---|
| real × walk × photoreal × per-pixel-splat | ✅ M5/M12 |
| real × iso × photoreal × per-pixel-splat | ✅ M12 parity |
| real × topdown × photoreal × per-pixel-splat | ✅ M12 parity |
| real × 2D × * | ⚠️ not wired (Phase E knob; not active) |
| procedural × walk × photoreal × per-pixel-splat | 🟡 M17 workflow proof; M19-M24 production |
| hybrid (real + procedural) × any | 🟡 M10/M21/M22/M23 |
| any × any × painterly/topographic | 🟡 M24 style packs |
| any × any × alien-real | 🟡 M24 + Track D5 |
| fantasy × any | ❌ no source pipeline yet (Track A4/A5/A6/D5) |

Coverage **does not** mean "every cell ships AAA quality." It means
"every cell emits a valid bundle that the gate accepts at workflow tier."
Quality lifts come in separate post-completion polish work.

### 3. M13 promotion gate accepts at all four bands

The M13 gate (`production_promotion_candidates.json` +
`audit_production_promotion_candidates.py`) enforces:

- Status states are auditable (workflow / sidecar / negative / candidate / promoted)
- Promotion requires close + medium + iso + topdown evidence
- No silent promotion through hand-edits to manifests

world3 is at "gate-clean" when:

- Every contract bundle in the production set has a defined gate state
- At least one biome per style pack has reached `production_candidate`
  status at all four bands
- The gate has no pending candidates older than the active M-iteration
  with stale evidence

This is M13 hygiene work, not new capability.

### 4. Water track ships

Per `WORLD3_CONTRACT_2026_05_10.md`, the water track adds:

- `water/water_height.png`
- `water/water_type_mask.png` (river / lake / ocean / wetland / ice)
- `water/flow_direction.png`
- `water/water_manifest.json`

world3 is at "water-complete" when:

- M20 erosion-derived drainage networks promote to water masks
- Lake/pond detection from depressions works
- Coastal extension works where biome_label says "coastal" and
  bathymetric source data is available
- Water-aware scatter rules (no shrubs in lake beds) are wired through
  the existing scatter mask manifest
- Per-mode water material variants render correctly through the
  conformance scenes

**Arc**: [`WATER_ARC_2026_05_10.md`](WATER_ARC_2026_05_10.md). Six
right-sized Ms (W1-W6). Committed scope. Runs after Sky arc in the
post-M24 sequence per [`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md).

### 5. Weather system ships as full opt-in module

Promoted from stretch to committed scope on 2026-05-10. **End-of-roadmap
work** — runs after the water track (M25-M30) closes.

Full system, not data-only. Bad weather is worse than no weather; if
we ship it, it has to meet the AAA-grade environment-art bar from
`LONG_TERM_VISION.md`. That means **the full system** — atmospheric
color, volumetric clouds, precipitation, surface response, vegetation
response, atmospheric volumetrics, state transitions, and reference
shader implementations — not just JSON manifests.

**On/off semantics**: weather must be a clean opt-in module the
consumer toggles. If disabled, world3 bundles work exactly as they do
pre-weather (clear-sky, no precipitation, no surface response,
default biome material variants). If enabled, the full system
activates from one configuration switch. No half-states.

Per `WORLD3_CONTRACT_2026_05_10.md`, the weather track adds:

- `weather/climate_class.json` — Köppen-Geiger zone + per-region patterns
- `weather/atmospheric_lut.png` — color tables per (climate × state × time)
- `weather/cloud_distribution.json` — per-climate cloud-type rules
- `weather/precipitation_manifest.json` — type frequencies + intensity curves
- `weather/surface_response.json` — wet/snow/ice/mud accumulation thresholds
- `weather/wind_field.json` — prevailing wind direction + magnitude distribution
- `weather/atmospheric_volumetrics.json` — fog/haze/dust/mist params
- `weather/state_transitions.json` — weather-state-machine manifest
- `weather/reference_shaders/` — opt-in reference impls for clouds, precipitation, surface response, fog
- `weather/conformance_scenes/` — per-mode × per-climate × per-state validation

world3 is at "weather-complete" when:

- Every climate class identifies cleanly from biome_label + latitude
- Reference cloud system uses Track D1 (nebula-statistics derived)
  cloud-class signatures
- Reference precipitation handles rain, snow, hail with per-mode LOD
- Surface response covers the full material catalog (wet/snow/ice
  variants per material)
- Vegetation response extends the scatter system without breaking
  current scatter conformance
- Weather state transitions are time-of-day-aware
- All conformance scenes render in both weather-on and weather-off
  modes
- Toggling weather off produces bundles identical (modulo `weather/`
  directory presence) to pre-weather bundles

**Arc**: [`WEATHER_ARC_2026_05_10.md`](WEATHER_ARC_2026_05_10.md).
Thirteen right-sized Ms (WX-1 through WX-13). Committed scope.
Largest single arc. Runs after Water arc per
[`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md). This is
explicitly **way-future work** — Atmosphere + Sky + Water all close
before Weather starts.

### 6. Conformance suite renders every bundle

The review scenes under `world3/scenes/review/` already validate
bundles in practice. Formalizing them is the M18 realignment work:

- A documented set of conformance scenes (close walk, medium walk, iso
  tactical, topdown, full-map review, water surface, scatter
  density, junction stress)
- A scripted runner that loads any bundle, renders all conformance
  scenes, and reports pass/fail
- Failure modes ("missing valid mask," "splat manifest references
  unknown catalog id," etc.) categorized + recovery documented
- A per-release artifact: "world3 v0.X.Y conformance report"

This is a real M-chunk of work (probably one of M-late) but it's the
thing that lets future-you (and any downstream consumer) **trust** that
world3 builds work.

---

## What "complete" does NOT mean

These are explicitly **post-completion polish**, not blockers for the
completion bar:

- AAA visual quality at every cell of the knob-space. (Workflow
  acceptance != AAA. Polish is per-cell, separate from completion.)
- Every biome on Earth covered. (One per style pack is the bar.)
- Every conceivable fantasy biome generated. (One stylized + one
  fantasy biome per style pack is the bar.)
- Day/night cycle simulation, dynamic lighting at runtime, audio.
  (Consumer side. Weather is in scope but ships static-with-reference;
  the rest are out of scope entirely.)
- Animated water surface, swimmable water physics, surface-tension
  shaders. (Consumer side; world3 emits static water data.)
- Real-time weather simulation logic at game-time (the consumer ticks
  the state machine; world3 emits the static rules + reference visual
  impls only).
- Real-time procedural generation at game-time. (Pre-baked bundles
  only; M23 streaming director loads pre-baked tiles.)
- A specific game built on world3. (world3 is a pipeline; the game is
  a separate consumer that builds on world3's bundles.)

---

## Why this bar is achievable

Today's progress vs the bar:

| Condition | Today's state | Gap |
|---|---|---|
| 1. Contract stable | ~85% (today's contract doc captures it) | Document changelog + lock generator_version |
| 2. Knob-space coverage | ~50% (real × walk/iso/topdown × photoreal works) | M14-M24 adds procedural + style packs + fantasy |
| 3. M13 gate clean | active (M14 candidates in flight) | M14-M18 closure |
| 4. Water track ships | 0% (not started) | [Water arc](WATER_ARC_2026_05_10.md) W1-W6 (~6 right-sized Ms) |
| 5. Weather system ships | 0% (not started) | [Weather arc](WEATHER_ARC_2026_05_10.md) WX-1 to WX-13 (~13 right-sized Ms) |
| 6. Conformance suite | review scenes exist; not formalized | [Conformance arc](CONFORMANCE_ARC_2026_05_10.md) C1-C4 |

(Also part of the long-term plan but not separate completion conditions:
[Atmosphere arc](ATMOSPHERE_ARC_2026_05_10.md) A1-A5 and
[Sky arc](SKY_ARC_2026_05_10.md) S1-S5 — both shared infrastructure
between Sky and Weather, run before Water + Weather per the dependency
graph.)

Realistic timeline if pursued at the current cadence (M14 currently
in progress, each M historically ~1-3 sessions):

- M14-M18 closure: ~10-15 sessions
- M19-M24 hybrid procedural: ~10-15 sessions (per that plan)
- Atmosphere arc (A1-A5): ~5-15 sessions
- Sky arc (S1-S5): ~5-15 sessions
- Water arc (W1-W6): ~6-18 sessions
- Weather arc (WX-1 to WX-13): ~13-39 sessions (largest single arc)
- Conformance arc (C1-C4): ~4-12 sessions

**Total**: roughly 53-129 working sessions from today's M14 start.
~10-26 calendar months of part-time work. Right-sized Ms increase
the *count* but not the *total scope* vs the prior M25-M39 framing;
smaller chunks just mean more review points + less risk per M +
easier handoff between sessions.

Primary orchestrator view: [`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md).

This is **achievable** at the current rate; the discipline question is
**not adding scope** along the way (other than what's committed: water,
weather). Tracks A/B/D options stay queued unless a specific item is
required for a knob-space cell, with the exception of **Track D1
(nebula-statistics cloud generator) which is promoted to M33** since it
becomes the cloud-system source.

---

## The "stop adding scope" line

After M18 closes the temptation is to add 50 more cool things. The
completion bar draws a hard line:

**In scope for completing world3** (changes the bar):

- M14-M18 closure (active)
- M19-M24 hybrid procedural (planned)
- Water track ~M25-M30 (committed)
- Weather system ~M31-M39 (committed; end-of-roadmap; full system
  with reference shaders; opt-in via single switch)
- Conformance suite formalization (M18-realignment work; extended
  by weather conformance work in M39)
- Track D1 nebula-statistics cloud generator (**promoted to M33** as
  the cloud-system source)
- Track D5 alien-real style pack **only if** the M24 style-pack work
  needs it (otherwise stays queued)
- Per-mode 2D view-mode wiring **if** the knob-space audit shows it
  matters

**Out of scope for completing world3** (deferred to post-completion
polish or a separate pipeline):

- Track A1-A6 (NLCD, bathymetry, planetary DEMs, sketch-to-heightmap,
  fantasy generators, photo+depth) — queued options, not blockers.
  Pick one or two if they fill a knob-space cell, defer the rest.
- Track B interiors — separate pipeline shape, not world3's job
- Track C structure generators — separate pipeline; consumers (game,
  prop pipeline) call these on top of world3 bundles
- Track D2-D4, D6 — scatter-density / spectral-color / map-decoration
  signals are consumer-side on top of world3 bundles
- Animation, audio, real-time gameplay systems
- Per-region biome polish beyond one biome per style pack
- Real-time generation at game-time
- Day/night cycle simulation (weather emits time-aware data; the
  consumer ticks the clock)

**Decision rule when faced with "should we add X?"** — does X land in
a knob-space cell that's currently uncovered AND blocks the M13 gate
from accepting bundles for that cell, OR is X part of the committed
water/weather scope? If yes, in scope. If no, queue it.

---

## What's stable enough to commit today

Without waiting for M18 realignment, the following are stable enough
to commit:

1. **The contract doc** (`WORLD3_CONTRACT_2026_05_10.md`) — captures
   M1-M12 reality; future-you knows what world3 emits.
2. **The completion bar** (this doc) — captures what done means; M18
   realignment becomes "audit against the bar" not "define the bar."
3. **Water track is in scope** — sketched M25-M30, committed post-M24.
4. **Weather system is in scope** — sketched M31-M39 in
   [`M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md`](M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md);
   end-of-roadmap work; full system with reference shaders; opt-in
   via single switch. Quality bar: matches AAA environment art per
   `LONG_TERM_VISION.md` — bad weather is worse than no weather, so
   if we ship it, it has to look right.
5. **Track D1 (nebula-statistics cloud generator) is promoted** to
   M33 as the cloud-system source.

That's enough to anchor the next 10-18 months of work without further
scope drift.

---

## Cross-references

- Output contract: [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md)
- Knob-space definition: [`WORLD3_STATE_2026_05_08.md`](WORLD3_STATE_2026_05_08.md) section 1
- Current M chain: [`ROADMAP.md`](ROADMAP.md)
- Post-parity M chain: [`M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`](M13_M18_POST_PARITY_ROADMAP_2026_05_10.md)
- Hybrid procedural: [`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md)
- Long-term direction: `../../docs/plans/LONG_TERM_VISION.md`
- Queued options: [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md),
  [`FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md`](FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md)

## Change log

- **2026-05-10**: Initial bar. Five completion conditions. Water
  committed, weather stretch. "Stop adding scope" line documented.
- **2026-05-10 (later)**: Promoted weather from stretch to **committed
  scope**, full system (M31-M39), end-of-roadmap (post-M30 water).
  Reference shader implementations included — bad weather is worse
  than no weather, so we ship the full system or skip it. Opt-in
  semantics: single switch turns the whole module on or off cleanly;
  bundles without weather behave exactly as pre-weather bundles.
  Track D1 (nebula-statistics cloud generator) promoted from queued
  option to M33 source. Sixth completion condition added; timeline
  shifted to 55-80 sessions / 10-18 months.
- **2026-05-10 (latest)**: Long-term M-chain restructured. M25-M39
  flat range replaced with five **arc-named docs**: Atmosphere, Sky,
  Water, Weather, Conformance. Each arc has right-sized M-internal
  steps (1-3 sessions per M, single concrete deliverable). Atmosphere
  + Sky arcs run before Water + Weather per dependency graph.
  Primary orchestrator view: [`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md).
  Timeline expanded to 53-129 sessions / 10-26 months total — same
  scope, more review points.
