# world3 — Roadmap (thin pointer)

> **Canonical roadmap moved 2026-05-11 to
> [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md).**
> That doc owns phase ordering, scope, and active state. This file
> is retained as a thin pointer + historical content; the long-arc
> doc wins on any disagreement.

## Where to look

| Question | Read |
|---|---|
| Where is world3 going overall? | [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md) |
| What's being built right now? | [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md) |
| What comes after F? | [PHASE_G_CHARTER_2026_05_11.md](PHASE_G_CHARTER_2026_05_11.md) |
| What comes after G? | [PHASE_H_CHARTER_2026_05_11.md](PHASE_H_CHARTER_2026_05_11.md) |
| What does "done" mean? | [WORLD3_COMPLETION_BAR_2026_05_10.md](WORLD3_COMPLETION_BAR_2026_05_10.md) (= Phase I) |
| Cold-start handoff for a new agent | [ORCHESTRATOR_HANDOFF_2026_05_11.md](ORCHESTRATOR_HANDOFF_2026_05_11.md) |
| Phase E orchestrator quick-start | [README.md](README.md) (Phase E quick-start table) |
| Phase B-E rebuild evidence | E1_E3 / E4 / E5 / E6 / E7 closure docs |

## Status snapshot

- ✅ Phases A-E: done 2026-05-11
- 🔨 Phase F: active (8 sub-phases, ~12 sessions)
- 📋 Phase G: charter shipped (6 sub-phases)
- 📋 Phase H: charter shipped (6 sub-phases)
- 📋 Phase I: bar defined ([COMPLETION_BAR](WORLD3_COMPLETION_BAR_2026_05_10.md))

---

## Legacy content (pre-2026-05-11 unification)

Everything below is historical. Refer to the long-arc doc above for
current scope. The legacy content is kept as institutional context
on how the roadmap evolved.

---

## Current state

| | |
|---|---|
| **Active scope** | **Phase F — Pipeline buildout** (charter shipped 2026-05-11). See [`PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md`](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md). |
| **Phase B-E status** | Shipped. Orchestrator works end-to-end on unseen content with byte-identical reproduction. See [`E7_FINAL_VALIDATION_2026_05_11.md`](E7_FINAL_VALIDATION_2026_05_11.md). |
| **Audit verdict** | M1-M18 workflow-closed, visually conditional. D.1 macro fix landed through M18 cascade 2026-05-11. |
| **Production-promoted artifacts** | 0 of 8 candidates (M13 gate healthy) |
| **Strongest visuals** | M11 three-way + four-way junctions, M12 runtime parity, M16 gallery board |
| **M19 status** | Deferred behind Phase F. F.4 transition-pair audit + F.6 in-context audit absorb most of what M19 was scoped for. |
| **Quality bar** | Workflow evidence + visible improvement vs current. **Not** "AAA-grade" (that was orchestrator over-scoping per the audit). |

---

## What world3 is

A world-generation pipeline. Emits world-data bundles per [`WORLD3_CONTRACT_2026_05_10.md`](WORLD3_CONTRACT_2026_05_10.md). Consumers (games, tools) render them. Review scenes in `world3/scenes/` are validation harnesses, not gameplay.

Knob-space (per [`WORLD3_STATE_2026_05_08.md`](WORLD3_STATE_2026_05_08.md) §1): source × view × style × granularity. Bundles emit through the M13 production-promotion gate.

Definition of "done" lives in [`WORLD3_COMPLETION_BAR_2026_05_10.md`](WORLD3_COMPLETION_BAR_2026_05_10.md) — six conditions.

---

## Active work — M19 + Orchestration O1-O3

### Framing correction (2026-05-11)

**Procedural is the placement engine, not the texture generator.**

The M18 procedural neighbor side currently reads as smooth tan/sand
because the implementation treated the procedural side as having to
*generate* its own ground appearance. That was a misread of project
intent. The correct framing:

- **Textures come from the textures pipeline** — `pipelines/textures/`,
  `aaa_texture.py`, the FLUX 2 9B + dev bakeoff currently staged, the
  M14 close-play quality work, the M1 material catalog. These are
  the "floor / ground textures" — the actual visual appearance.
- **Procedural is the world-building system** — how heightmaps are
  generated (FastNoise spectral fitting + Landlab erosion + real-DEM
  patch seeding), where biomes are placed, where transitions sit,
  where scatter clusters fall, how regions stitch into worlds. The
  M19-M24 hybrid procedural infrastructure.
- **Procedural zones *use* catalog textures** through the same
  splat-shader pipeline as real-source regions. They don't invent
  textures.

User clarification (2026-05-11): *"the procedural thing was supposed
to be how the world is built, how textures are placed, heightmap, all
that stuff."* The "good textures to be our floor/ground textures" come
from the texture pipeline — not from procedural generation.

This reframes every "procedural quality" concern below. M19 isn't
about generating better-looking procedural ground. It's about
generating better placement (height, biome label, splat weights,
scatter masks) that lets the *existing* catalog materials read
correctly on procedural terrain.

### M19 — Procedural placement quality (current)

Goal: fix the M18 procedural neighbor side so it places catalog
materials correctly across heightmap topology, biome labels, splat
weights, transitions, and scatter masks. Win condition: the procedural
side looks like material-bearing terrain (using existing catalog
textures) under the same auditing lane.

**Critical reframe**: this is *not* about generating new textures or
new ground appearance. The procedural side should consume catalog
materials (via the M4 unified splat shader) the same way real-source
regions do. The current smooth-tan-sand veto is a symptom of the
procedural side either:
- (a) emitting splat weights that bias toward a single broad material, or
- (b) emitting a heightmap topology too smooth for the splat shader's
  slope/height rules to pick varied materials, or
- (c) bypassing the catalog and substituting a flat synthesized
  texture.

The M19 audit (which the worker will do as part of the entry plan)
identifies which of these is true and addresses placement, not texture
generation.

Sequence (per [`M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md`](M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md)):

| M | Scope |
|---|---|
| **M19** | Corpus statistical analysis — per-biome FastNoise parameter distributions from cached DEM mega-stacks |
| M20 | Erosion sim backbone — Landlab fluvial + diffusion per-biome calibrated baker |
| M21 | Procedural neighbor streaming contract — eroded chunks through ChunkLoader/seam integration |
| M22 | Real-DEM patch seeding — splice real DEM fragments into procedural fields, erode to harmonize |
| M23 | Infinite streaming director — per-chunk decision (cached / pre-baked / on-demand) |
| M24 | Style packs + playable infinite slice |

M19 entry plan to be written before implementation (per audit recommendation).

### Orchestration O1-O3 (parallel with M19, promoted from queued)

The audit identified pipeline throughput as the next strategic friction. O1-O3 promote from queued to committed scope to run alongside M19. O4-O10 remain queued; only promote if they directly unblock an M19-M24 deliverable.

| O | Scope | Gating |
|---|---|---|
| O1 | `region_request.json` declarative config schema | Can start immediately |
| O2 | `world3 make-region <config>` pipeline runner | Wants O1 first |
| O3 | `stages.json` manifest with inputs/outputs | Concurrent with M19 |

Per [`WORLD3_OPERABILITY_GAPS_2026_05_10.md`](WORLD3_OPERABILITY_GAPS_2026_05_10.md). O4-O10 (preview/bake split, all-modes render driver, batch generator, world composition, style pack contract, etc.) stay queued.

---

## Long-term plan (post-M24)

Five arcs run in dependency order. Each arc has right-sized Ms (1-3 sessions each, single concrete deliverable) in its arc doc.

| Order | Arc | Why this slot | Doc |
|---|---|---|---|
| 1st post-M24 | **Atmosphere** | Foundational shared infrastructure for Sky + Weather | [`ATMOSPHERE_ARC_2026_05_10.md`](ATMOSPHERE_ARC_2026_05_10.md) (A1-A5) |
| 2nd | **Sky** | Cheap, isolated, early visible momentum; depends only on Atmosphere | [`SKY_ARC_2026_05_10.md`](SKY_ARC_2026_05_10.md) (S1-S5) |
| 3rd | **Water** | Depends on Terrain (erosion) + Atmosphere (mist coupling) | [`WATER_ARC_2026_05_10.md`](WATER_ARC_2026_05_10.md) (W1-W6) |
| 4th | **Weather** | Heaviest arc; couples to all three above; opt-in via single switch | [`WEATHER_ARC_2026_05_10.md`](WEATHER_ARC_2026_05_10.md) (WX-1 to WX-13) |
| Last | **Conformance close** | Formalizes per-release validation | [`CONFORMANCE_ARC_2026_05_10.md`](CONFORMANCE_ARC_2026_05_10.md) (C1-C4) |

**Quality bar note (2026-05-11)**: the Weather arc was originally scoped as "AAA-grade environment art with full reference shaders." The audit clarified the project-wide quality bar is "workflow evidence + visible improvement vs current." Weather arc scope may need to soften at M24 reaudit — flagged as known re-decision point.

At end-of-sequence, world3 hits all six completion-bar conditions.

Sequential M ordering: [`M_SEQUENCE_2026_05_10.md`](M_SEQUENCE_2026_05_10.md) (supporting timeline, not roadmap authority).

---

## Module architecture

Eight content modules + one infrastructure module, per [`WORLD3_ARCHITECTURE_TEMP_2026_05_10.md`](WORLD3_ARCHITECTURE_TEMP_2026_05_10.md):

1. **Terrain Foundation** — heightmap, mesh, chunks, streaming, procedural
2. **Material Catalog** — kits, per-mode variants, splat shader binding
3. **Transitions & Junctions** — biome bridges, ecotones, corners
4. **Scatter & Features** — vegetation, rocks, debris, wind response
5. **Water** — rivers, lakes, ocean, ice, flow direction
6. **Atmosphere** — color LUT, scattering, fog/haze/dust/mist
7. **Sky** — stars, milky way, sun/moon, aurora
8. **Weather** — clouds, precip, surface response, state machine
9. **Conformance & Gates** (cross-cutting) — M13 gate, contract validation

Architecture doc is marked temporary; expected to evolve as later arcs land.

---

## Queued options

Not committed; held in registers. Pull from here when active milestone closes and direction needs setting.

| Register | Contents |
|---|---|
| [`FUTURE_WORLD_SOURCES_2026_05_08.md`](FUTURE_WORLD_SOURCES_2026_05_08.md) | Track A (heightmap sources: NLCD, bathymetry, planetary, sketch, fantasy generators, photo+depth, gaussian splat), Track B (interiors — different pipeline shape), Track D (astronomical sources: D1 + D3 already promoted) |
| [`FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md`](FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md) | Track C (11 procedural structure generator families G1-G11; consumer-side) |
| [`WORLD3_OPERABILITY_GAPS_2026_05_10.md`](WORLD3_OPERABILITY_GAPS_2026_05_10.md) | 11 operability gaps; Orchestration O4-O10 queued |

Promotion rule: a queued item moves into the canonical M-chain only when it (a) directly unblocks committed scope or (b) the user explicitly promotes it after a closure audit.

---

## Doc role map

This roadmap is the canonical entry-point. Every other doc has a defined supporting role.

| Doc | Role | Authority on... |
|---|---|---|
| **ROADMAP.md** (this doc) | **Canonical roadmap** | Current state, active milestone, M-chain ordering, gate truth |
| **ORCHESTRATOR_HANDOFF_2026_05_11.md** | **Cold-start prompt** | Self-contained reading guide for a new orchestrator/agent with no context |
| `WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md` | Audit verdict | M1-M18 ground truth (referenced by this doc) |
| `WORLD3_CONTRACT_2026_05_10.md` | Output contract | What bundles emit; file layout; coupling rules |
| `WORLD3_COMPLETION_BAR_2026_05_10.md` | Completion definition | What "done" means; six conditions |
| `WORLD3_ARCHITECTURE_TEMP_2026_05_10.md` | Module map | 8 modules + dependency graph + couplings (temporary; reaudit at arc transitions) |
| `M_SEQUENCE_2026_05_10.md` | Sequential timeline (supplementary) | Flat M order across arcs; **not** active-state authority |
| `WORLD3_EXEC_SUMMARY_2026_05_10.md` | One-page brief (supplementary) | Reading entry-point for cold sessions; **not** roadmap authority |
| `WORLD3_STATE_2026_05_08.md` | Orchestrator state inventory | Worker boundaries, knob-space, existing infrastructure |
| Per-arc docs (Atmosphere/Sky/Water/Weather/Conformance) | Arc scope specs | Arc-internal M scope + exit criteria; **not** active-state authority |
| `M13_M18_POST_PARITY_ROADMAP_2026_05_10.md` | Range-historical | M13-M18 scope (preserved; M14-M18 conditional per audit) |
| `M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md` | Range-historical, active scope | M19-M24 hybrid procedural plan |
| `M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md` | **Superseded** | Old flat range framing; arc docs are canonical |
| `WORLD3_OPERABILITY_GAPS_2026_05_10.md` | Gaps register | 11 gaps; O1-O3 promoted to active per this doc |
| `ROADMAP_HISTORY_2026_05_10.md` | Historical archive | Phase A-F history, pre-arc Track summaries; preserved for context |
| `FUTURE_WORLD_SOURCES_2026_05_08.md` | Queued options | Tracks A, B, D |
| `FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md` | Queued options | Track C |

If you read this doc and need more depth on a specific area, navigate to the doc named above.

---

## Operating principles

- **Honest, not optimistic.** The audit is the model. State of every M is whatever the evidence shows.
- **One canonical authority.** This doc plus the latest committed audit. Other docs feed in or are explicitly demoted.
- **Right-sized Ms.** Each M is 1-3 sessions, single concrete deliverable, reviewable in isolation. If a planned M needs "+" or "and" in its scope, split it.
- **Workflow evidence is the bar.** Not AAA-grade. Visible improvement vs current is enough for most Ms. Polish per-module post-completion, not blocking-completion.
- **M13 gate is sacred.** Every artifact has an explicit promotion state from the schema in `world3/jobs/production_promotion_candidates.json`: `accepted_workflow`, `ready_for_live_review`, `sidecar_candidate`, `negative_evidence`, `production_candidate`, `production_promoted`. Per-band status uses `pass / conditional / fail / not_reviewed / not_applicable`. No silent promotion.
- **Scope discipline.** New ideas land in queued registers, not directly into Ms. Promotions happen at closure audits, not in-flight.
- **Document as we go.** Audit reports, decision logs, lessons. The history archive (`ROADMAP_HISTORY_2026_05_10.md`) is the institutional memory.

---

## Change log

- **2026-05-11**: Rewrote as canonical roadmap. Demoted M_SEQUENCE + WORLD3_EXEC_SUMMARY to supporting roles. Archived Phase A-F history to `ROADMAP_HISTORY_2026_05_10.md`. Adopted "workflow evidence + visible improvement" as the project-wide quality bar (audit clarification). Promoted Orchestration O1-O3 to active scope alongside M19. Set M19 as the active milestone per audit recommendation.
- **2026-05-10**: Promoted weather from stretch to committed. Restructured long-term plan into arc-named docs. Added operability gaps register.
- **2026-05-09**: Methodology correction — repeated-source tiling demoted to diagnostic only. M10 terrain seam integration is the production-facing path.
- **2026-05-08**: Operating-model + sequence revision. Phase F absorbed into M1-M6.
- **2026-05-07**: v1 → v2 reframe. v1 archived in `ROADMAP_v1_archived.md`.
