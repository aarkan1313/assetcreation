# World3 Project — Executive Summary (2026-05-10)

> ⚠️ **ONE-PAGE BRIEF — NOT THE CANONICAL ROADMAP.**
>
> **Canonical roadmap lives in [`ROADMAP.md`](ROADMAP.md).** If this
> brief disagrees with `ROADMAP.md` or the latest committed audit,
> the canonical roadmap wins. This brief may also lag — content here
> is correct at the time of last edit but not the current-state
> authority.
>
> Use this doc as a cold-start reading entry-point. Use ROADMAP.md
> for active state, M-chain ordering, and what to work on next.

Single-page orientation for anyone (or future-you) walking into the
world3 docs cold. Pairs the M-chain, the module architecture, and
the Tracks register into one readable snapshot.

## What world3 is

- A **world-generation pipeline**, not a game. Emits world-data bundles per a defined contract; consumers (games, tools) render them.
- Review scenes are validation harnesses, not gameplay.

## Current state

- **M1-M12 done** — terrain foundation, material catalog, transitions, junctions, splat shader, chunk streaming, source-stack contract, runtime parity across walk/iso/topdown
- **M13-M18 workflow-closed / visually conditional** (2026-05-11) — see [`WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md`](WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md). M18 procedural side reads as broad smooth tan/sand; no terrain content is production-promoted.
- **2026-05-11 framing correction**: procedural is the **placement engine** (heightmap, biome labels, splat weights, scatter masks), not the texture generator. Textures come from the textures pipeline (FLUX 2 + M14 + catalog). M19 fixes procedural placement so catalog materials read correctly on procedural terrain — not procedural texture quality. See ROADMAP.md "Framing correction" block.
- **M19 next** — replace the smooth procedural neighbor with material-identity-bearing close-range procedural terrain (per [`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md)). Promote Orchestration **O1-O3** in parallel.
- **M14 remains conditional** — FLUX 2 9B + dev bakeoff staged 2026-05-10; no winner selected yet.
- **M20-M39 planned** — full long-term arc through end-of-pipeline

## The eight content modules

| Module | Status | Scope |
|---|---|---|
| **Terrain Foundation** | M1-M12 done; M17/M18 workflow-closed; M19-M24 next | heightmap, mesh, chunks, streaming, procedural |
| **Material Catalog** | M1 + Phase E done; M14 conditional (FLUX 2 bakeoff staged) | kits, per-mode variants, splat shader binding |
| **Transitions & Junctions** | M2/M7/M10/M11 done | biome bridges, ecotones, corners |
| **Scatter & Features** | M11 workflow; M15 planned | vegetation, rocks, debris, wind response |
| **Atmosphere** | [Arc planned](ATMOSPHERE_ARC_2026_05_10.md): A1-A5 | color LUT, scattering, fog/haze/dust/mist — runs first post-M24 |
| **Sky** | [Arc planned](SKY_ARC_2026_05_10.md): S1-S5 | stars, milky way, sun/moon, aurora — runs second post-M24 |
| **Water** | [Arc planned](WATER_ARC_2026_05_10.md): W1-W6 | rivers, lakes, ocean, ice, flow direction — runs third post-M24 |
| **Weather** | [Arc planned](WEATHER_ARC_2026_05_10.md): WX-1 to WX-13 | clouds, precip, surface response, state machine — runs fourth post-M24 (largest arc) |
| **Conformance & Gates** (infra) | M13 active; [arc-close](CONFORMANCE_ARC_2026_05_10.md): C1-C4 | gate, contract validation, per-release reports |

Architecture map (temporary, reaudit at M18 close):
[`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`](WORLD3_ARCHITECTURE_TEMP_2026_05_10.md).

## Sky module (the part most likely to be forgotten)

Sky is a **new module surfaced in the architecture pass** — it was a
gap in prior planning. Static celestial content overhead, distinct
from Weather (dynamic) and Atmosphere (color/scattering).

What it produces:

- `sky/starfield.png` (or shader-input statistics) — real-derived but procedural star positions
- `sky/milky_way.json` — galactic-band orientation per region
- `sky/celestial_bodies.json` — sun, moon, planets, phases
- `sky/aurora_params.json` — polar regions only

How it gets generated: same "real data → statistical signature →
procedural derivative" pattern as M19-M24 terrain. Pull HYG / Gaia
catalog data; extract distributions (magnitude, spectral type, density
gradient across Milky Way band); generate **new** star fields with
matching statistics. Real but not Earth — constellations are
unrecognizable but the sky *feels* astronomically right.

**Track D3 (procedural night sky from stellar statistics) is promoted
as Sky's source.** Sky becomes the first downstream module to consume
astronomical data; sister to Weather/M33's nebula-statistics cloud
generator (also promoted from Track D1).

Per-mode behavior:
- **Walk** — full sky with stars + celestial bodies
- **Iso** — often clipped, fades to atmospheric color
- **Topdown** — no sky at all, skipped entirely

Opt-in: bundles without `sky/` directory = consumer renders flat
gradient sky (atmosphere only). With it = stars/sun/moon/milky way/aurora
populate. Within "sky enabled," per-mode opt-out remains valid
(topdown skips even when walk/iso include sky).

## Tracks A/B/C/D — queued options register

The Tracks live in two sibling docs alongside the M-chain. **Tracks
are queued options, not committed work.** Promotions happen when a
specific item gets pulled into the M-chain.

### Track A — alternative heightmap/world sources

In [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md).
Six items that plug into the existing terrain pipeline at the
`heightmap.png + meta.json` boundary:

- **A1 NLCD/Copernicus land-cover** — per-pixel biome ground truth; force-multiplier on the splat shader. HIGH VALUE.
- **A2 Bathymetry + coastal** — extends terrain to oceans/islands via GEBCO. **M27 (water track) will consume this.**
- **A3 Planetary DEMs (Mars/Moon/Mercury)** — alien geology; stress-tests Earth assumptions. **D5 (fantasy ground textures) depends on this.**
- **A4 Sketch-to-heightmap** — fantasy-axis source via user-drawn maps
- **A5 Fantasy world generators (Azgaar, WorldEngine)** — whole worlds with biomes/rivers/climate baked in
- **A6 Photo + depth estimation** — non-DEM imagery as terrain source

Status: all queued. A1 + A3 most likely to promote first; A2 effectively promoted-by-dependency through M27.

### Track B — explorable interiors / structures

In [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md)
Track B section. Six sub-categories from single-room caves through
full castle/dungeon networks. **Different pipeline shape from world3**
(layout generator + 3D extrusion + props + gameplay metadata, not
heightmap-based). Belongs adjacent to props/POI work but worth
pre-planning.

Status: **out of scope for world3 completion**. Lives as a separate
pipeline when pursued.

### Track C — procedural structure generators

In [`FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md`](FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md).
11 structure-generator families (G1-G11) for things that live ON
terrain but aren't covered by heightmap + texture:

- G1 branching (trees, rivers, lightning, vessels)
- G2 cellular/Voronoi (crystals, basalt, foam)
- G3 reaction-diffusion (animal markings, coral)
- G4 fractals (mountains, ferns, mandelbulb)
- G5 aggregates (scree, pebbles, rubble)
- G6 layered (rock strata, agate)
- G7 filaments (grass, hair, fabric)
- G8 folded surfaces (mountain folds, brain coral)
- G9 diffusion (frost, dust, lichen)
- G10 tilings (Penrose, Islamic, hex, brick)
- G11 wave patterns (Chladni, ripples, dunes)

Recommended Tier 1 targets: G1 trees + G7 grass + G5 scree (vegetation
is the single biggest visual delta from "terrain" to "place").

Status: **consumer-side**, not world3 emission. world3 emits scatter
masks; consumers call Track C generators on top of world3 bundles to
populate them.

### Track D — astronomical data sources

In [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md)
Track D section. Six items applying the "real data → procedural
derivative" pattern to astronomical sources:

- **D1 nebula-statistics → procedural cloud/VFX field generator** → **PROMOTED to M33** (weather-track cloud source)
- **D2 cosmic-web density → scatter mask generator** — queued; pairs with M15 if pursued
- **D3 procedural night sky from stellar statistics** → **PROMOTED to Sky module** as its source (M-sky-1 sketched, real M at M18 reaudit)
- **D4 spectral-type → blackbody color shader** — queued; consumer-side spell-glow utility
- **D5 real-DEM + nebula-statistics → fantasy ground textures** — queued; gated on M19-M22 + Track A3 planetary DEMs; would become the alien-real style pack in M24
- **D6 galactic-filament + constellation polygons → strategic-map decoration** — queued; consumer-side topdown flavor

**Two Track D items already promoted to scheduled work** (D1 → M33,
D3 → Sky module). D5 is the most likely next promotion (composes with
M19-M24 + A3). D2/D4/D6 stay queued; D4 and D6 are consumer-side and
may never need world3 promotion.

### View-mode applicability of Track D items

The astronomical-data pattern scales into every view mode, just
differently:

| Item | Walk | Iso | Topdown |
|---|---|---|---|
| D1 clouds → M33 | full volumetric | cast shadows + tint | tactical overlay |
| D2 scatter density | medium | high (cluster patterns visible) | high (density visible) |
| D3 sky → Sky module | full | clipped/faded | skip |
| D4 spell colors | full | full | full (icons) |
| D5 fantasy textures | full close-play | iso material | topdown blocks |
| D6 map decorations | n/a | n/a | high (sole purpose) |

## Key decisions made today

- **FLUX 2 9B + dev bakeoff staged.** All weights downloaded (klein-9B NVFP4/FP8/Q8 + dev NVFP4), harness wired in `diversity_compare.py`, handoff doc written. Bakeoff runs in the other ComfyUI session.
- **Cleanup**: deleted ~41 GB of sunset models (Qwen-Image, Chroma1-HD, byte-identical `clip/` duplicates). Disk 56 → 95 GB free.
- **Landlab installed + smoke-tested** in `pipelines/terrain/.venv` — ready for M20 erosion work.
- **Water promoted to committed scope** (M25-M30, post-M24).
- **Weather promoted to committed scope** (M31-M39, end-of-roadmap, full opt-in module with reference shaders). Bad weather is worse than no weather, so we ship the full system or skip it. Single-switch on/off.
- **Sky identified as a new module** — gap in prior planning. Track D3 promoted as its source. M-numbers assigned at M18 reaudit.
- **Track D1 promoted to M33** as the cloud-system source.
- **Atmosphere split** sketched as a natural separation from Weather (shared by Sky + Weather); formalization decided at M18 reaudit.
- **Track D added to the queued register** with view-mode applicability matrix.

## Hierarchy of plans (oriented for "how do I navigate this?")

- **Active work** → [`WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md`](WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md) (latest verdict) + [`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md) (M19 next). M14 close-play stays in flight via [`M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md`](M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md) + [`../../pipelines/textures/HANDOFF_FLUX2_BAKEOFF_2026_05_10.md`](../../pipelines/textures/HANDOFF_FLUX2_BAKEOFF_2026_05_10.md), but is no longer the lead.
- **What we do next, in order (primary orchestrator view)** → [`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md)
- **What world3 emits** → [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md)
- **What "done" means** → [`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md) (six conditions)
- **How it all fits together** → [`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`](WORLD3_ARCHITECTURE_TEMP_2026_05_10.md) (temporary snapshot, reaudit at M18)
- **Sequential M-chain (legacy view)** → [`ROADMAP.md`](ROADMAP.md) + [`PLAN.md`](PLAN.md)
- **Near-term per-range plans**:
  - [`M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`](M13_M18_POST_PARITY_ROADMAP_2026_05_10.md) — production gate, close-play, scatter, gallery, procedural neighbor, playable slice
  - [`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md) — hybrid procedural infinite world (real DEMs informing FastNoise + erosion + patch seeding + streaming director + style packs)
- **Long-term arc plans (post-M24)**:
  - [`ATMOSPHERE_ARC_2026_05_10.md`](ATMOSPHERE_ARC_2026_05_10.md) — A1-A5 (foundational; runs first)
  - [`SKY_ARC_2026_05_10.md`](SKY_ARC_2026_05_10.md) — S1-S5 (Track D3 source; runs second)
  - [`WATER_ARC_2026_05_10.md`](WATER_ARC_2026_05_10.md) — W1-W6 (runs third)
  - [`WEATHER_ARC_2026_05_10.md`](WEATHER_ARC_2026_05_10.md) — WX-1 to WX-13 (largest arc; Track D1 source; runs fourth)
  - [`CONFORMANCE_ARC_2026_05_10.md`](CONFORMANCE_ARC_2026_05_10.md) — C1-C4 (closes long-term plan)
- **Operability gaps + sketched Orchestration arc (reaudit-gated)**: [`WORLD3_OPERABILITY_GAPS_2026_05_10.md`](WORLD3_OPERABILITY_GAPS_2026_05_10.md) — 12 gaps against the "fast pipeline for making game worlds" goal; Orchestration arc sketched O1-O10; promotion deferred to M18 reaudit
- **Superseded (kept for reference)**: [`M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md`](M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md) — old water+weather framing; arc docs are now canonical
- **Queued options**:
  - [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md) — Tracks A (heightmap sources), B (interiors, separate pipeline), D (astronomical sources)
  - [`FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md`](FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md) — Track C (G1-G11 structure generators, consumer-side)

## Completion bar (six conditions)

world3 is "done" when:
1. **Contract stable** — output format locked, generator_version pinned
2. **Knob-space covered** — every cell of source × view × style × granularity emits valid bundles
3. **M13 gate clean** — every artifact has audited promotion state
4. **Water track ships** — rivers, lakes, ocean, ice, flow direction
5. **Weather system ships** — full opt-in module with reference shaders
6. **Conformance suite renders** — formalized per-release validation

**Note**: Sky is part of the architecture but not yet promoted to a
seventh completion-bar condition. M18 reaudit decides whether Sky
joins the bar formally or stays as an architecturally-recognized
module that ships within Atmosphere/Weather's quality umbrella.

## Realistic timeline

- M14-M18 closure: ~10-15 sessions
- M19-M24 hybrid procedural: ~10-15 sessions
- Atmosphere arc (A1-A5): ~5-15 sessions
- Sky arc (S1-S5): ~5-15 sessions
- Water arc (W1-W6): ~6-18 sessions
- Weather arc (WX-1 to WX-13): ~13-39 sessions (largest arc; reference shaders push upper bound)
- Conformance arc (C1-C4): ~4-12 sessions

**Total: ~53-129 sessions / 10-26 months at current cadence.** Same
scope as the prior M25-M39 framing; right-sized Ms increase the count
(33 post-M24 Ms vs the prior 15) but give smaller review points and
less risk per M.

## Cross-pipeline dependencies world3 actually needs

- **Textures pipeline** — provides material library (M14 conditional; FLUX 2 bakeoff staged 2026-05-10, no winner selected yet)
- **OpenTopo cache + tooling** — real source data (mature)
- Everything else (props, characters, VFX, UI, audio, game data) is **consumer-side**, not a world3 dependency

## Discipline lines

- **In scope for completing world3**:
  - M14-M39
  - Water track (M25-M30)
  - Weather full opt-in system (M31-M39)
  - Sky module (M-numbers TBD at M18 reaudit)
  - Conformance formalization
  - Track D1 (→ M33) + D3 (→ Sky)
- **Possibly in scope** (decide at M18 reaudit):
  - Atmosphere as its own M-arc (currently nested in Weather)
  - Track D5 (alien-real style pack) if M24 needs it
  - Per-mode 2D view-mode wiring if knob-space audit shows it matters
- **Out of scope for world3**:
  - Gameplay, audio, animation, day/night simulation, real-time weather logic
  - Track B interiors (separate pipeline)
  - Track C structure generators (consumer-side)
  - Track D2 / D4 / D6 (queued; consumer-side)
  - A specific game built on world3
- **Decision rule**: does X fill a knob-space cell that's uncovered AND blocks the M13 gate, or is X part of committed water/weather/sky scope? If yes → in scope. If no → queue it.

## M18 reaudit gate

When M18 closes:
- Reaudit [`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`](WORLD3_ARCHITECTURE_TEMP_2026_05_10.md) (it's marked temporary on purpose)
- Decide whether Atmosphere becomes its own M-arc
- Assign committed M-numbers to Sky module
- Verify coupling rules between modules are still right
- Update module → doc map for any new docs that landed
- Decide whether Sky becomes a 7th completion-bar condition

Halfway-done snapshot now → editing not authoring at M18.

## Change log

- **2026-05-10**: Initial executive summary. Captures eight content modules including Sky as new surfaced module, full Tracks A/B/C/D detail with promoted-vs-queued status, hierarchy of plans, completion bar, timeline, discipline lines, and M18 reaudit gate.
