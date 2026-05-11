# world3 — Long Arc

> **Single canonical view of where world3 is going.** Phases B-E shipped.
> Phase F is active. Phases G, H, I are charted but unstarted. This
> doc replaces the scatter of M19-M24 / O1-O3 / A1-A5 / Track-A/B/C /
> ARC-DOC plans that accreted before the 2026-05-11 unification.
>
> **If any other doc disagrees with this one about phase ordering,
> scope, or active state, this doc wins.** Supporting per-phase
> charters live alongside; legacy roadmap-shaped docs were either
> absorbed (M19-M24 → F.4 + G.M-arc; O1-O3 → E.1-E.3) or retired with
> a redirect header.

## The arc, in one diagram

```
┌────────────────────────────────────────────────────────────────┐
│  HISTORY                                                       │
│  Phases A-E rebuild (2026-05-07 → 2026-05-11)                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                │
│  A: Texture pipeline overhaul                          ✅ DONE │
│  B: Cold-validation chains 1/2/3                       ✅ DONE │
│  C: Procedural-vs-texture framing correction           ✅ DONE │
│  D: Infrastructure fixes (macro tune, catalog refresh) ✅ DONE │
│  E: Orchestrator MVP + capture driver + style packs    ✅ DONE │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  ACTIVE (2026-05-11+)                                          │
│  Phase F — Pipeline buildout                                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                │
│  F.1: Close orchestrator gaps (seam + cache + real-DEM smoke) ✅
│  F.2: world_plan.json schema + validator                      ✅
│  F.3: plan → bundles iterator + world_map.json                ✅
│  F.4: catalog-time transition pair audit                      ✅
│  F.5: catalog demand deriver + requisition runner             ✅
│  F.6: in-context material re-audit                            ✅
│  F.7: multi-bundle streaming director (architecture)          ✅
│  F.3.1: edge-constraint plan iterator + procedural builder   ✅
│  F.3.4: m11_bundle_lib refactor                              ✅
│  F.3.5: fourway parity (lib + CLI + ~70% visual)             ✅
│  F.3.6: visual tuning + 5-biome rebuild + multi-domain       🔨
│  F.8: pipeline guide + world3_make_world.py top-level entry   ✅
│                                                                │
│  Exit: one command produces a ~5km, 5-biome, tile-able,        │
│  walkable world. Pipelines, not content.                       │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  QUEUED (charter exists, unstarted)                            │
│  Phase G — Polish + consumer integration                       │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                │
│  G.1: LOD-aware capture + zoom-level emission                  │
│  G.2: 2.5D perspective + new .tres variant                     │
│  G.3: Handcraft override path (patch bundles)                  │
│  G.4: Consumer integration kit (bundles → external runtime)    │
│  G.5: Per-mode quality bars measured at gate time              │
│  G.6: Real-DEM patch seeding (absorbs M22 scope)               │
│                                                                │
│  Exit: pipelines from F survive consumer use + polish gaps     │
│  closed against the completion bar.                            │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  QUEUED (charter exists, unstarted)                            │
│  Phase H — Content production hooks + catalog scaleup          │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                │
│  H.1: Catalog scaleup beyond 5-biome starter                   │
│  H.2: Erosion sim integration (absorbs M20 scope)              │
│  H.3: Spectral analysis for procedural-from-real-corpus        │
│       (absorbs M19 scope as catalog work, not pipeline work)   │
│  H.4: POI / landmark layer (absorbs G7 from operability gaps)  │
│  H.5: Water + atmosphere + sky + weather (absorbs ARC docs)    │
│  H.6: Conformance suite renders every bundle automatically     │
│                                                                │
│  Exit: catalog covers full intended biome range + the          │
│  completion bar's six conditions are met.                      │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  TERMINAL                                                      │
│  Phase I — Completion (the bar)                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                │
│  All six conditions from WORLD3_COMPLETION_BAR met.            │
│  world3 stops being a pipeline-under-construction and becomes  │
│  a content-production tool that ships worlds.                  │
└────────────────────────────────────────────────────────────────┘
```

## Why phases, not Ms, not Os, not Tracks

The codebase accumulated multiple parallel numbering schemes that all
claimed to describe "what comes next":

- **M1-M18** — milestones the pre-rebuild worker actually shipped
- **M19-M24** — hybrid procedural roadmap (M19-M24_HYBRID_PROCEDURAL_ROADMAP)
- **O1-O3** — orchestration arc (WORLD3_OPERABILITY_GAPS, partially shipped as E.1-E.3)
- **A1-A5** — earlier texture-pipeline arcs (TEXTURE_PIPELINE_FIX_PLAN era, retired)
- **Track A/B/C** — even earlier arc labels (WORLD3_STATE_2026_05_08, mostly retired)
- **ARC docs** — Atmosphere / Sky / Water / Weather / Conformance (long-term scope, archived 2026-05-11)
- **Phase A-F** — the texture-pipeline phase A-F sequence, now retired in favor of new B-E rebuild + F-I forward arc

Result: nobody (including the orchestrator) could keep them all straight.
2026-05-11 unification: **only phases own forward arc**. M-numbers
retained ONLY for completed history. New work happens in phases.

If you read a doc that talks about "active M19" or "queued O3" or
"Track B next," check this doc and the per-phase charter. Those names
are history, not roadmap.

## Status table (canonical)

| Phase | Scope | Status | Charter doc |
|-------|-------|--------|-------------|
| A | Texture pipeline overhaul | ✅ Done 2026-05-07 | (archived; see DECISIONS.md) |
| B | Cold-validation chains 1/2/3 | ✅ Done 2026-05-11 | [REBUILD_PLAN_PHASES_B_E_2026_05_11.md](REBUILD_PLAN_PHASES_B_E_2026_05_11.md) + B1/B2/B3 docs |
| C | Procedural-vs-texture framing | ✅ Done 2026-05-11 | [PHASE_C_DIAGNOSIS_2026_05_11.md](PHASE_C_DIAGNOSIS_2026_05_11.md) |
| D | Infrastructure fixes | ✅ Done 2026-05-11 | [D1_BUILD_MACRO_TUNE_2026_05_11.md](D1_BUILD_MACRO_TUNE_2026_05_11.md), [D3_D5_INFRASTRUCTURE_FIXES_2026_05_11.md](D3_D5_INFRASTRUCTURE_FIXES_2026_05_11.md), [D6_VALIDATION_PASS_2026_05_11.md](D6_VALIDATION_PASS_2026_05_11.md) |
| E | Orchestrator MVP + capture driver + style packs | ✅ Done 2026-05-11 | [E1_E3_ORCHESTRATOR_MVP_2026_05_11.md](E1_E3_ORCHESTRATOR_MVP_2026_05_11.md), [E4_ORCHESTRATOR_CAPTURE_DRIVER_2026_05_11.md](E4_ORCHESTRATOR_CAPTURE_DRIVER_2026_05_11.md), [E5_STYLE_PACK_MECHANISM_2026_05_11.md](E5_STYLE_PACK_MECHANISM_2026_05_11.md), [E6_DOCS_HANDOFF_2026_05_11.md](E6_DOCS_HANDOFF_2026_05_11.md), [E7_FINAL_VALIDATION_2026_05_11.md](E7_FINAL_VALIDATION_2026_05_11.md) |
| **F** | **Pipeline buildout (plan → tiled world)** | **🔨 Active** | [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md) |
| G | Polish + consumer integration | 📋 Charter exists | [PHASE_G_CHARTER_2026_05_11.md](PHASE_G_CHARTER_2026_05_11.md) |
| H | Content production + catalog scaleup | 📋 Charter exists | [PHASE_H_CHARTER_2026_05_11.md](PHASE_H_CHARTER_2026_05_11.md) |
| I | Completion (the bar) | 📋 Bar defined | [WORLD3_COMPLETION_BAR_2026_05_10.md](WORLD3_COMPLETION_BAR_2026_05_10.md) |

## How legacy plans were absorbed

This is the **anti-duplication ledger** — if you read one of the
retired roadmaps, this table tells you where its work went.

| Legacy item | Was scoped as | Absorbed by | Status |
|-------------|---------------|-------------|--------|
| M19 — Corpus statistical analysis | Procedural-from-real spectral fitting | F.4 (transition audit) + H.3 (full corpus analysis as catalog work) | Split |
| M20 — Erosion sim backbone | Landlab fluvial + diffusion | H.2 (content production phase) | Deferred |
| M21 — Procedural neighbor streaming contract | Bundle interop for streaming | F.7 (multi-bundle streaming director) | Absorbed |
| M22 — Real-DEM patch seeding | Hand-pick DEMs for plot points | G.6 (handcraft override path) | Absorbed |
| M23 — Infinite streaming director | The actual streamer | F.7 (multi-bundle streaming director) | Absorbed |
| M24 — Style lane + playable infinite slice | Style packs + playable proof | E.5 (style packs) + F.7 (playable slice) | Done in E + F |
| O1 — Region request schema | One-config-per-bundle | E.1 (region request schema) | Done |
| O2 — Pipeline runner | "world3 make-region" | E.3 (world3_make.py) | Done |
| O3 — Stage manifest | inputs/outputs declared | E.2 (stages.json) | Done |
| O4 — Smoke test | Auto-region regen | E.7 (final validation on unseen region) | Done |
| G1-G12 (operability gaps) | 12 numbered gaps | Mostly absorbed into E.1-E.3 + F.2-F.8 | See below |
| Track A1-A5 / Track B / Track C | Old arc labels | Retired entirely; work either landed or queued under phase letters | Retired |
| ARC: Atmosphere / Sky / Water / Weather / Conformance | Long-term scope | H.5 + H.6 (content production phase) | Deferred |
| FUTURE_WORLD_SOURCES (NLCD, bathy, planetary, fantasy) | Alternative data sources | H.1 (catalog scaleup) | Deferred |
| FUTURE_PROCEDURAL_STRUCTURES (trees, crystals, scree, etc.) | Structure-generator families | H.4 (POI/landmark layer) | Deferred |

### Operability gaps detail (G1-G12 → phase mapping)

| Gap | What | Absorbed by |
|-----|------|-------------|
| G1 | No single "make a region" entry point | E.3 (world3_make.py) |
| G2 | No config schema for "what region do I want?" | E.1 (region_request_schema.json) |
| G3 | Style packs named but never specified | E.5 (style pack mechanism) |
| G4 | View-mode switching is per-M | E.4 (parameterized capture driver) |
| G5 | (DISMISSED 2026-05-10) | — |
| G6 | No regional/continental composition layer | F.2 + F.3 (world_plan + iterator) |
| G7 | No POI/landmark layer | H.4 (deferred) |
| G8 | No iteration speed loop | F.4 + F.6 (audit-driven iteration) |
| G9 | No consumer-side integration kit | G.4 (consumer kit) |
| G10 | Per-mode quality bars aren't measured | G.5 (per-mode quality measurement) |
| G11 | LLM/agent-driven workflow not sketched | E.6 + F charter's LLM-drivability gate |
| G12 | No "make me 10 regions overnight" batch path | F.3 + F.7 (plan-to-bundles + streaming) |

If a legacy doc still claims an item is "active" or "queued," **this
doc overrides it**. Legacy docs have been (or will be) headered with
a redirect.

## What each phase costs (rough)

These are honest estimates after Phase B-E shipped in ~1 session per
sub-phase. Phase F sub-phases were sized to match that cadence; later
phases are less certain because they involve content + consumer-side
unknowns.

| Phase | Sub-phases | Estimated sessions |
|-------|-----------|--------------------|
| F | 8 (F.1-F.8) | ~12 (F.7 is 4-6, others ~1 each) |
| G | 6 (G.1-G.6) | ~8-10 |
| H | 6 (H.1-H.6) | Open-ended (depends on catalog ambition) |
| I | Sign-off only | ~1 |

So F + G + I is **roughly 22-25 sessions of pipeline work** to reach
a state where world3 ships worlds, with H being optional/ongoing
content work that doesn't gate completion.

## Cross-cutting rules (apply to every phase)

These were locked during Phase B-E and explicitly carry forward.

1. **Pipelines, not content** until at least mid-H. Every artifact
   lands as a script or schema, never authored art. Authored art
   happens in H.1+ once the pipeline is proven.
2. **Five-biome starter** through F and most of G. Catalog grows in H.
3. **Scale is the perennial enemy.** Every artifact carries explicit
   `world_size_*_m` / `elevation_range_m` / `tile_size_m` /
   `zoom_level_m`. Every script validates them. No implicit units.
4. **Catalog quality is gate-state, not vibes.** M13 promotion gate
   is sacred. Plans can only use materials at `production_candidate`
   or higher.
5. **Transition quality lives at catalog time, not at runtime.**
   F.4 catches blend failures before bundles are built.
6. **LLM-drivability is a hard gate.** Every sub-phase must ship with:
   schema + validator + example + audit script + closure doc + stages.json
   entry (if pipeline work). See F charter's LLM-drivability section
   for the exact checklist.
7. **Phase charters own scope.** No doc outside a phase charter can
   add scope to that phase. If a new idea appears, it lands in the
   relevant queued register and gets considered for a future phase.
8. **One canonical roadmap.** This doc + per-phase charters are
   authority. Legacy roadmap docs are history.

## Adapting the roadmap

Roadmaps change. When they do:

- A new sub-phase landing → update the per-phase charter, NOT this doc
  (this doc's status table updates only when a whole phase closes)
- Scope moving between phases → update both phase charters + the
  anti-duplication ledger above
- A whole phase changing shape → write a new long-arc doc dated, archive
  the old one, update ROADMAP.md to point at the new one

The goal is that "what comes next" never requires reading more than
two docs: this one + the active phase's charter.

## Cross-references

- Quick start: [README.md](README.md) (Phase E quick-start table)
- Cold-start handoff: [ORCHESTRATOR_HANDOFF_2026_05_11.md](ORCHESTRATOR_HANDOFF_2026_05_11.md)
- Output contract bundles emit: [WORLD3_CONTRACT_2026_05_10.md](WORLD3_CONTRACT_2026_05_10.md)
- Completion bar: [WORLD3_COMPLETION_BAR_2026_05_10.md](WORLD3_COMPLETION_BAR_2026_05_10.md)
- Decision log: [DECISIONS.md](DECISIONS.md)
