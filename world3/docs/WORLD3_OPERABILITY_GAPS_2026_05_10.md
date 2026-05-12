# World3 Operability Gaps + Sketched Orchestration Arc

> ⚠️ **SUPERSEDED 2026-05-11.** This doc identified 12 numbered
> operability gaps (G1-G12) and the O1-O3 orchestration arc.
> Both have been absorbed:
>
> - **O1-O3 + O4** (region request schema + pipeline runner + stage
>   manifest + smoke test) → **shipped as Phase E.1-E.3 + E.7**
> - **G1-G12** (the 12 gaps) → mapped into Phase F + G charter
>   sub-phases; see the anti-duplication ledger in
>   [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
>   for the full G-number-to-sub-phase mapping
>
> **Canonical roadmap**: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md).
> Do not start new work from this doc; reference the per-phase charters.

Date: 2026-05-10

> **Status**: gaps register, not committed scope. Sketched arc with
> right-sized Ms for future promotion. **Promotion deferred to M18
> reaudit.**
>
> **Why this exists**: the long-term plan (M-chain + arc docs + contract +
> completion bar) is correct for **what world3 emits**, but it doesn't
> commit to **how fast / operable / driven** the pipeline is. If the
> goal is a fast workflow for creating game worlds across 3D / 2.5D /
> topdown view modes, several real gaps exist. This doc names them so
> M18-you sees them and decides whether to promote the Orchestration
> arc into committed scope.

## The reframed goal (the part the bar didn't say out loud)

Current completion bar: "world3 emits valid bundles across the
knob-space, gate clean, water + weather + conformance ship."

What's actually wanted (per user 2026-05-10): **a pipeline that turns
a goal ("make me a 5km region in this biome at this style for these
view modes") into a shippable world bundle in hours, not weeks.**
Speed and operability are first-class.

A correct contract can still be slow + manual. The current docs don't
distinguish.

This matches the factory-operations vision in
`../../docs/plans/LONG_TERM_VISION.md`: "every pipeline becomes a
discoverable, configurable, end-to-end-validated unit, usable by
either human (GUI) or LLM (API)."

## The 12 operability gaps

### G1 — No single "make a region" entry point

Today, producing a region from a real DEM is ~8-12 manual steps (DEM
pull → import → catalog material → splat → transitions → scatter →
review → promote). No `world3 make-region <config>` runs the chain
end-to-end. **Without this, "fast" is impossible.**

### G2 — No config schema for "what region do I want?"

There's no declarative `region_request.json` describing: bounds,
biome, source class, style pack, view modes, water on/off, weather
on/off, sky on/off. Every region is hand-configured across Godot
scenes + jobs JSON. **Until this exists, world3 is a sequence of
decisions, not a workflow.**

### G3 — Style packs are named but never specified

M24 says "style packs swap shaders/materials on the same height/splat"
but nothing defines what a style pack *is* as a file/manifest. How
does photoreal differ from painterly differ from topographic?
Per-style material overrides live where? Style-aware shader
selection logic lives where? **"Switch to painterly mode" is an
unknown amount of work today.**

### G4 — View-mode switching is per-M, not pipeline-level

Phase E shipped per-mode `.tres` variants per kit. M12 proved parity
for one region. But there's no `render_all_modes(region_id)` that
captures walk + iso + topdown for any region as a single command.
Currently a manual per-scene check.

### G5 — ~~Fantasy source ingestion isn't planned anywhere~~ (DISMISSED 2026-05-10)

**Original concern was wrong.** Fantasy *geography* is already
planned through M19-M24 hybrid procedural + Track A3 planetary DEMs
(Mars/Moon as macro shapes) + Track D5 alien-real ground textures.
The pipeline generates real metric heightmaps with real drainage
networks from Mars+Earth corpus statistics, not from hand-drawn maps
or third-party world generators.

Fantasy *style* is the legitimate gap, and it's already captured as
**G3** (style packs unspecified) and **O10** (style pack contract).
Same Phase E per-mode `.tres` infrastructure handles photoreal vs
painterly vs alien-real via style packs.

So **"fantasy source" decomposes into two existing planned items
working together**: M19-M24 + Track A3 + Track D5 for geography,
plus O10 style pack contract for look. No separate Fantasy Sources
arc needed. Azgaar/WorldEngine ingest remains queued in Track A5 as
an alternate authoring path but is not required for the knob-space
`source=fantasy` cell to fill.

### G6 — No regional / continental composition layer

Bundles describe single regions. Nothing describes how regions
compose into a continent or world. A 50km × 50km playable area with
10 stitched biome regions is currently a hand-assembly job. M10/M11
prove the seams work; there's no driver that uses them.

### G7 — No POI / landmark layer

Hero locations (specific peaks, notable crags, ruined tower sites,
sacred groves) make worlds feel intentional. World3 emits homogenous
biome bundles with no per-region "this is the cool spot." Landmark
anchors in `meta.json` would be the lightweight version.

### G8 — No iteration speed loop

Generating a region today takes minutes-to-hours. There's no "preview
at low resolution → approve → bake at full resolution" path. For
fast workflow this is essential.

### G9 — No consumer-side integration kit

World3 emits bundles, but every downstream consumer (game, Godot
project, Blender import) reimplements the loader. No
`world3-godot-loader` plugin, no Blender importer, no Unity importer.
Even with documented bundle format, every consumer rebuilds. World3
should ship **one** reference loader (probably Godot) so consumers
have a working example to copy.

### G10 — Per-mode quality bars aren't measured

Phase E specifies per-mode tuning but no quantitative measure of
"this region passes walk-mode quality at close-play band." M14 uses
visual review; M13 gate uses status states. At scale (100s of
regions), visual review doesn't scale.

### G11 — LLM/agent-driven workflow isn't sketched

LONG_TERM_VISION wants LLM-driven operation. World3's tools work via
CLI but aren't standardized as a uniform API. Factory-ops vision
says every pipeline gets: `run.py` entry point, `config_schema.json`
declared knobs, `stages.json` discoverable steps, `smoke_test.py`
end-to-end shape verification, `run.json` per-run provenance.
World3 doesn't have this yet.

### G12 — No "make me 10 regions overnight" batch path

The mega-stack pull queue is a batch path for *data*. There's no
equivalent for *region bundles*. Overnight queue → wake up to 10
production-candidate bundles is the workflow goal.

## Pattern

Most of these aren't missing **content modules** (the eight content
modules cover what world3 *emits*). They're missing **operational
modules** — what makes the pipeline *runnable*, *fast*, and *driven
by config rather than hand-assembly*.

The architecture map has a 9th module (Conformance & Gates) for
validation. **The missing 10th module is Orchestration** — what
makes the pipeline operable.

## Sketched Orchestration arc

Right-sized Ms, each 1-3 sessions, single concrete deliverable.
**Promotion deferred to M18 reaudit** — these are not committed work
today.

### O1 — Region request schema

**Goal**: `region_request.json` declarative config for "what region do I want?"

Inputs: existing implicit knob choices across docs (source, view mode, style, granularity, biome, bounds, water/weather/sky toggles).

Deliverables:
- `world3/jobs/region_request_schema.json` — JSON schema with validation
- Reference example requests per knob-space cell
- Documentation: what each knob does + which arc owns it

Exit: a region can be fully described in one JSON file that the runner can consume.

### O2 — Pipeline runner

**Goal**: `world3 make-region <config>` end-to-end entry point.

Inputs: O1 request schema + existing per-stage scripts (`build_master_catalog.py`, `deploy_kit_to_world3.py`, etc.).

Deliverables:
- `world3/pipeline/run.py` — orchestrator that consumes O1 requests and runs the chain
- Stage outcome reporting (success/failure/skipped per stage)
- Idempotency: re-running with same config produces same bundle (per `generator_version`)

Exit: one command produces one bundle from one config; reproducible.

### O3 — Stage manifest

**Goal**: `stages.json` listing every pipeline step, inputs, outputs.

Inputs: existing pipeline scripts.

Deliverables:
- `world3/pipeline/stages.json` — every stage declared with `name`, `inputs`, `outputs`, `arc_owner`
- Stage dependency graph derivable from the manifest
- Validation: every stage referenced by O2 runner is in the manifest

Exit: stages are discoverable; LLM/agent can introspect what the pipeline does.

### O4 — Smoke test

**Goal**: `smoke_test.py` end-to-end shape verification of one canonical region.

Inputs: O1 + O2 + a reference `region_request.json` (e.g. Big Bend walk-mode photoreal).

Deliverables:
- `world3/pipeline/smoke_test.py` — runs the canonical region; validates contract; reports pass/fail
- Reference baseline outputs (expected hashes or visual diff thresholds)

Exit: every world3 commit can be smoke-tested in one command.

### O5 — Run provenance

**Goal**: `run.json` per-run record of what was generated, when, from what config.

Inputs: O2 runner.

Deliverables:
- Per-bundle `run.json` with: request config, generator version, stage timings, output file list, validation results
- Aggregation tool: list all runs, filter by config/result/version

Exit: every bundle is traceable to its inputs.

### O6 — All-modes render driver

**Goal**: `render_all_modes.py` captures walk/iso/topdown for any region as a single command.

Inputs: Phase E per-mode `.tres` variants, existing review scenes.

Deliverables:
- Driver script that loads a bundle + emits captures across all modes
- Per-mode capture templates (close walk, medium walk, iso tactical, topdown world map)
- Output format: contact sheet + per-capture metadata

Exit: any region can be reviewed across all three view modes in one command.

### O7 — Preview/bake split

**Goal**: low-res iteration + full-res bake.

Inputs: O2 runner.

Deliverables:
- Preview mode: smaller chunk size, reduced quality, faster generation (10-30s per region)
- Bake mode: full quality, full resolution
- Same `region_request.json` config drives both; preview is `--preview` flag

Exit: iteration loop is < 1 minute; bake is < 30 minutes.

### O8 — Batch region generator

**Goal**: overnight queue for batch region generation.

Inputs: O2 runner, list of region requests.

Deliverables:
- `world3/jobs/region_batch_<name>.json` — list of region requests
- Batch runner with progress reporting + failure recovery
- Resume-from-checkpoint support

Exit: "make me 10 regions overnight" works.

### O9 — World composition driver

**Goal**: `world_request.json` for multi-region stitched worlds.

Inputs: M10/M11 seam integration + junction work, O2 runner.

Deliverables:
- World request schema (multiple regions + adjacency rules + global biome map)
- Composition driver that generates regions, then stitches them per M10/M11
- Output: world bundle (collection of region bundles + adjacency manifest)

Exit: a 50km × 50km world with 10 stitched regions can be generated from one config.

### O10 — Style pack contract

**Goal**: formalize what "style pack" means as a file/manifest.

Inputs: M24 style pack concept, Phase E per-mode variants.

Deliverables:
- `world3/styles/<style>/style_pack.json` — per-style overrides for materials, shaders, scatter rules, atmosphere LUT
- Style-aware pipeline runner: `region_request.json` references style pack by id
- Reference style packs (photoreal, painterly, topographic) shipping
- Documentation: how to author a new style pack

Exit: style is a configurable knob; "switch to painterly" is one config change.

## Coupling with existing arcs

The Orchestration arc doesn't ship new content modules — it operates
on the existing ones. Coupling:

- **O2 runner** consumes every arc's per-stage scripts
- **O3 stage manifest** must include every arc's stages
- **O6 all-modes driver** uses Phase E + M12 per-mode contracts
- **O7 preview/bake** must respect every arc's quality budgets
- **O9 world composition** uses M10/M11 seam + junction work
- **O10 style packs** intersect with M24, Atmosphere arc LUTs, Material catalog

The arc runs **alongside** content arcs, not strictly after. Some O-Ms
benefit from running early (O1 schema, O2 runner) because they unlock
faster iteration for everything downstream. M18 reaudit decides
sequencing.

## On the other gaps (G5, G7, G9, G10)

Not all gaps fit cleanly inside the Orchestration arc.

**~~G5 — Fantasy source ingestion~~**: DISMISSED 2026-05-10.
Decomposes into existing planned work (M19-M24 + Track A3 + Track D5
for geography; O10 style pack contract for look). No separate arc
needed.

**G7 — POI / landmark layer**: lightweight; just data additions to
`meta.json`. Either inside Terrain Foundation evolution (as a new M)
or carved out as its own micro-arc (P1-P3 covering: landmark anchors,
named-region manifest, POI metadata schema).

**G9 — Consumer-side integration kit**: post-completion polish, not
in scope for the world3 completion bar. **But** a single reference
loader (Godot) should ship with world3 as part of the conformance
suite — review scenes are already that, in effect. Could be Conformance
arc C4 hygiene work.

**G10 — Per-mode quality metrics**: future tooling. Not blocking
completion bar but relevant for scaling. Could be a Conformance arc
addition (C5? quality metric pipeline).

## Effort estimate (if Orchestration arc promotes)

10 Ms × 1-3 sessions each = ~10-30 sessions / ~2-6 months.

Could run in parallel with content arcs to reduce wall time. O1-O3 are
high-leverage early items — once they exist, every downstream arc
benefits from the runnable pipeline.

## Decision at M18 reaudit

Three options:

1. **Promote full Orchestration arc** — committed scope, added to
   completion bar as condition 7 ("Pipeline operable via uniform
   config-driven runner")
2. **Promote subset** — O1/O2/O3 minimum so pipeline becomes runnable;
   defer O4-O10 to post-completion
3. **Defer entirely** — keep operability as queued register; complete
   world3 content-first, add orchestration after

My read at writing-time (2026-05-10): **option 2** is honest. O1-O3
make every other arc faster. O4-O10 are polish. M18-you decides with
M14-M18 hindsight.

## What this doc does NOT do

- Does not commit any of these gaps to scope today
- Does not change the M-chain
- Does not change the completion bar (six conditions stand)
- Does not promote Track A4/A5/A6 to scheduled work
- Does not add a Fantasy Sources arc to the architecture map (yet)

## Cross-references

- Long-term direction: `../../docs/plans/LONG_TERM_VISION.md`
- Architecture: [`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`](WORLD3_ARCHITECTURE_TEMP_2026_05_10.md)
- Completion bar: [`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md)
- Output contract: [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md)
- M sequence: [`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md)
- Executive summary: [`WORLD3_EXEC_SUMMARY_2026_05_10.md`](WORLD3_EXEC_SUMMARY_2026_05_10.md)
- Track register: [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md)

## Change log

- **2026-05-10**: Initial draft. 12 operability gaps named.
  Orchestration arc sketched with 10 right-sized Ms. Three M18-reaudit
  options recommended. Other-arc gaps (G5 fantasy, G7 POI, G9 consumer
  loader, G10 metrics) flagged separately.
- **2026-05-10 (later)**: G5 (fantasy source ingestion) **dismissed**.
  Was wrong concern — fantasy decomposes into existing planned work:
  M19-M24 + Track A3 planetary DEMs + Track D5 alien-real for
  geography; O10 style pack contract for look. No new arc needed.
  Net gap count: 11.
