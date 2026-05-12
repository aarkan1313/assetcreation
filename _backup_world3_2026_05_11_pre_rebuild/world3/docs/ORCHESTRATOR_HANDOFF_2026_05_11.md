# Orchestrator Handoff — 2026-05-11

> **Cold-start prompt for a new orchestrator picking up world3 work.**
> If you are an LLM/agent reading this, this doc plus the linked docs
> are all you need to start. You have no prior context. Read in
> order below.

## What world3 is

A **world-generation pipeline**. Not a game. Not a runtime. It emits
world-data bundles per a defined output contract; downstream consumers
(games, tools) render them.

The Godot scenes under `world3/scenes/` are **validation harnesses**,
not gameplay. They prove the bundles render correctly.

Repo: `D:/assets/world3/`. Project context: `D:/assets/`.

## The current situation in three sentences

1. M1-M18 audit just completed (commit `c5b0cff`, 2026-05-11): the
   pipeline is **workflow-closed but visually conditional**. M11/M12/M16
   are the strongest visuals. 0 of 8 candidates are production-promoted.
2. The biggest visible weakness is the M18 procedural neighbor side
   reading as broad smooth tan/sand. **M19 is the active milestone**
   to fix this.
3. A critical framing correction landed 2026-05-11: **procedural is
   the placement engine, not the texture generator.** Textures come
   from the texture pipeline (FLUX 2 / catalog); procedural emits
   heightmap + biome labels + splat weights that the catalog renders.
   Read this carefully before doing anything else.

## Read these in order

1. **`ROADMAP.md`** — canonical roadmap. Top of doc has current state,
   active milestone, gate truth, quality bar. Doc role map shows what
   every other doc is for.
2. **`WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md`** — audit verdict for
   M1-M18 with specific captures and findings. Most evidence-grounded
   doc in the project.
3. **`WORLD3_CONTRACT_2026_05_10.md`** — what bundles emit. The output
   contract every consumer reads against.
4. **`WORLD3_COMPLETION_BAR_2026_05_10.md`** — six conditions for
   "done." Long-term target.
5. **`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`** — active scope
   (M19 next). Has the 2026-05-11 framing correction at top.
6. **`WORLD3_OPERABILITY_GAPS_2026_05_10.md`** — Orchestration arc
   sketch. O1-O3 promoted to active alongside M19.

Skim, don't deep-read:

7. **`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`** — module map. Temporary;
   reaudit at arc transitions.
8. **`WORLD3_STATE_2026_05_08.md`** — orchestrator state inventory
   (worker boundaries, knob-space, existing infrastructure).
9. Per-arc docs: `ATMOSPHERE_ARC_2026_05_10.md`, `SKY_ARC_2026_05_10.md`,
   `WATER_ARC_2026_05_10.md`, `WEATHER_ARC_2026_05_10.md`,
   `CONFORMANCE_ARC_2026_05_10.md` — long-term arc scope. Don't read
   until M19-M24 closes.

History (read only if needed):
10. **`ROADMAP_HISTORY_2026_05_10.md`** — Phase A-F decision trail,
    pre-arc Track summaries. Institutional memory.
11. **`WORLD3_EXEC_SUMMARY_2026_05_10.md`** — one-page brief. May lag
    canonical state.
12. **`M_SEQUENCE_2026_05_10.md`** — supplementary flat M timeline. Not
    active-state authority.

## The framing correction in detail

User clarification 2026-05-11 after live-reviewing the M18 procedural
side:

> "we made the good textures to be our floor/ground textures, the
> procedural thing was supposed to be how the world is built, how
> textures are placed, heightmap, all that stuff."

Concretely:

- **Textures come from the textures pipeline.** `pipelines/textures/`,
  `aaa_texture.py`, FLUX 2 (the 9B + dev bakeoff currently staged in
  `pipelines/textures/HANDOFF_FLUX2_BAKEOFF_2026_05_10.md`), the M1
  material catalog, the M14 close-play quality work. These ARE the
  "good textures." They land in `world3/materials/catalog.json` and
  bind through the M4 unified splat shader.

- **Procedural is the world-building system.** M19 spectral fitting +
  M20 erosion + M21 streaming + M22 patch seeding + M23 director + M24
  style packs. The output is **placement data**: heightmap, biome
  label, splat weights, scatter masks, transitions. It is NOT a
  texture generator.

- **Procedural zones consume catalog materials** via the same M4 splat
  shader that real-source regions use. The procedural side emits "this
  pixel gets this weight of material X and that weight of material Y";
  the catalog supplies the actual texture.

The M18 procedural side currently reads as smooth tan/sand because
the implementation deviated from this principle. M19's first job is
the audit that determines whether the procedural placement is wrong
(splat weights biased, heightmap too smooth) or whether catalog
binding was bypassed entirely.

## Active milestone — M19

**Goal**: fix the M18 procedural neighbor side so it places catalog
materials correctly across heightmap topology, biome labels, splat
weights, transitions, and scatter masks.

**Win condition**: procedural neighbor reads as material-bearing
terrain using existing catalog textures, under the same M13 auditing
lane.

**First step**: M19 entry plan doc (~1 session). Should cover:
- What the M18 procedural side weakness looks like at each band
  (close/medium/iso/topdown) — informed by reading the audit
- Whether the weakness is splat-weight bias, topology smoothness,
  catalog-bypass, or some combination
- Which M19-M24 sub-Ms attack which part
- Whether the FLUX 2 bakeoff (currently staged but not run) needs to
  happen first to ensure catalog texture quality is solid for the
  catalog binding to read well

M19 sequence (per `M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`):

| M | Scope |
|---|---|
| **M19** | Corpus statistical analysis — per-biome FastNoise parameter distributions |
| M20 | Erosion sim backbone — Landlab fluvial + diffusion |
| M21 | Procedural neighbor streaming contract |
| M22 | Real-DEM patch seeding |
| M23 | Infinite streaming director |
| M24 | Style packs + playable infinite slice |

Tooling already in place:
- Landlab 2.11.0 installed + smoke-tested in `pipelines/terrain/.venv/`
  (`pipelines/terrain/landlab_smoke_test.py`)
- Cached DEM corpus (~659 TIFs, 4 master stacks at last check)
- FLUX 2 9B + dev bakeoff staged in
  `pipelines/textures/HANDOFF_FLUX2_BAKEOFF_2026_05_10.md` (not yet
  run — winner selection pending)

## Parallel: Orchestration O1-O3

Promoted from queued (`WORLD3_OPERABILITY_GAPS_2026_05_10.md`) to
active alongside M19. Pipeline throughput is the next strategic
friction; these make M19+ work faster.

- **O1**: `region_request.json` declarative config schema
- **O2**: `world3 make-region <config>` pipeline runner
- **O3**: `stages.json` manifest with inputs/outputs

O1 can start immediately. O2 wants O1 first. O3 is concurrent with
M19. O4-O10 stay queued.

## Quality bar

**"Workflow evidence + visible improvement vs current."**

NOT "AAA-grade." That was orchestrator over-scoping per the 2026-05-11
audit. If anything in the docs reads as a perfectionist gate, the
audit has overridden it.

Practical translation: each M lands when it produces workflow evidence
that visibly improves on what was there before, passes the M13 gate
review, and integrates with the bundle contract. Polish per-module
post-completion, not blocking-completion.

## M13 promotion gate (sacred — do not relax)

`world3/jobs/production_promotion_candidates.json` +
`world3/pipeline/audit_production_promotion_candidates.py`.

Every artifact has explicit status: `workflow_evidence`,
`sidecar_candidate`, `conditional`, `workflow_ready_not_production`,
`production_candidate`, `production_promoted`, `negative_evidence`.

No silent promotion. New artifacts enter as `workflow_evidence`; user
review + close/medium/iso/topdown band evidence required to advance.

## Operating principles

1. **Honest, not optimistic.** State of every M is whatever the evidence shows.
2. **One canonical authority.** `ROADMAP.md` + the latest committed audit. Other docs feed in or are explicitly demoted.
3. **Right-sized Ms.** Each M = 1-3 sessions, single concrete deliverable, reviewable in isolation. No "+" or "and" in M scope; split if needed.
4. **Workflow evidence is the bar.** Not perfection.
5. **M13 gate is sacred.** No silent promotion.
6. **Scope discipline.** New ideas land in queued registers
   (`FUTURE_WORLD_SOURCES_2026_05_08.md`,
   `FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md`,
   `WORLD3_OPERABILITY_GAPS_2026_05_10.md`), not directly into Ms.
7. **Procedural ≠ texture generator.** Procedural emits placement
   data; catalog supplies textures. See "framing correction" section.

## Worker / orchestrator boundary

The single-stream model from `WORLD3_STATE_2026_05_08.md` describes
the orchestrator/worker split for the OpenTopo data lane. For M19+
work, you (orchestrator) and whichever worker picks up M19
implementation form the same pattern: orchestrator owns roadmap +
cross-cutting decisions; worker owns M-specific implementation +
audit. Reconciliation conversations happen at M-closure points.

## Cross-pipeline dependencies world3 actually needs

- **`pipelines/textures/`** — provides material catalog (M14 active;
  FLUX 2 bakeoff staged)
- **`pipelines/terrain/`** — provides DEM cache + tooling (mature) +
  Landlab erosion (smoke-tested)
- **`world3/pipeline/`** — runtime glue, audit scripts, build_master_*
  tools

Everything else (props, characters, VFX, UI, audio, game data) is
**consumer-side**, NOT a world3 dependency.

## Out-of-scope for world3

- Gameplay, audio, animation, real-time game logic
- A specific game built on world3 (world3 is a pipeline; the game is
  a separate consumer)
- Real-time procedural generation at game-time (we pre-bake bundles)
- Track B interiors (separate pipeline shape)
- Track C structure generators (consumer-side)
- Track A4/A5/A6/A8 queued items (revisit at arc transitions, not
  in-flight)

## What you should NOT do

- Re-open M18 to chase procedural visual quality. M18 closed correctly
  as workflow evidence; the procedural-side weakness is M19's job.
- Bundle scope additions into M19. Discipline rule.
- Try to hit "AAA-grade." Workflow evidence + visible improvement is
  the bar.
- Promote anything past M13 gate's `workflow_evidence` tier without
  explicit user review.
- Have procedural Ms generate textures. Procedural emits placement
  data; catalog supplies textures.

## What you should do

1. Read the docs in the order at top.
2. Don't engage with M19 implementation until the M19 entry plan is
   written + reviewed.
3. Maintain the canonical roadmap discipline — `ROADMAP.md` is the
   one source of truth.
4. Surface anything that needs user decision rather than guessing.
5. Ask the user before making large doc changes — the doc surface
   was just stabilized; preserving the canonical-roadmap discipline
   matters.

## Current pending items (handoff snapshot)

| Item | State | Owner |
|---|---|---|
| Live review of M18 procedural scene | Done 2026-05-11 by previous worker; veto confirmed | — |
| Framing correction (procedural ≠ texture generator) | Landed in ROADMAP.md + M19-M24 plan + exec summary + architecture map | — |
| M19 entry plan | Pending; user requested ~1 session before implementation | New worker |
| FLUX 2 9B + dev bakeoff | Staged but not run; winner pending | Textures lane |
| M14 close-play quality | Conditional; depends on bakeoff outcome | Textures lane |
| O1-O3 promotion to active scope | Recorded in ROADMAP.md | Active alongside M19 |
| Stale `M14 active` language across some docs | Contained with "not authority" headers; canonical ROADMAP says M19 | — |
| Track A8 gaussian splat | Added to queued register 2026-05-11 | Queued |

## Change log

- **2026-05-11**: Initial handoff doc. Captures the M1-M18 audit
  verdict, the canonical-roadmap discipline, the procedural-vs-texture
  framing correction, the M19 active milestone, and the O1-O3
  promotion.
