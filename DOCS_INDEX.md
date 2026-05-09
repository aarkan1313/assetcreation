# Docs Index

Canonical ownership map for the `D:\assets` documentation set. When docs disagree, update the owning doc first, then let the other docs link to it instead of repeating stale detail.

> **🚨 Worldgen nuked 2026-05-07.** v1 + v2 both archived to `_archive/worldgen_2026_05_07/` (incl. `worldgen2/` Godot project, `pipelines/worldgen_v2/` Python pipeline, all v1 scripts under `pipelines/terrain/`, all baked outputs in `world/worlds`/`world/regions`/`world/maps`/`world/terrain`/`world/scenes`, the 4 `wgv2_*` texture sets, and 2 worldgen handoff docs from `docs/handoffs/`). The OpenTopography DEM-fetch tooling under `pipelines/terrain/` is **kept** — 222 cached TIFFs (8.1 GB) live at top-level `dems/`. New worldgen pipeline TBD.

## Reference / index docs (stable, frequently updated)

| Doc | Owns | Does not own |
|---|---|---|
| [README.md](README.md) | Entry point, short current-state summary, first commands for common workflows. | Detailed status tables, long roadmaps, full tool inventory. |
| [DOCS_INDEX.md](DOCS_INDEX.md) | This ownership map and navigation rules. | Pipeline status truth. |
| [WORKFLOWS.md](WORKFLOWS.md) | **Master workflow list** — per-asset trees, tool branches, run order. The "if I want to make X, do these steps" doc. | Per-line tool descriptions. |
| [PIPELINE_DIRECTORY.md](PIPELINE_DIRECTORY.md) | Live status of every pipeline. Canonical truth table for "what works today." | Step-by-step recipes. |
| [TOOLS_INDEX.md](TOOLS_INDEX.md) | Script/tool/env inventory and quick "what tool for what job" lookup. | Priority decisions or historical handoffs. |
| [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md) | Copy-paste recipes for each lane. | Global status counts and backlog priority. |
| [docs/plans/ROADMAP.md](docs/plans/ROADMAP.md) | Current priorities, done-vs-next, deferred work. | Full API references or script-by-script inventory. |
| [docs/plans/EXPANSION_PLAN.md](docs/plans/EXPANSION_PLAN.md) | Living phased checklist + decision log. | Status counts (those live in PIPELINE_DIRECTORY). |
| [docs/audits/AUDIT_2026_05_07_post_nuke.md](docs/audits/AUDIT_2026_05_07_post_nuke.md) | **Latest audit** — truth-from-disk post-worldgen-nuke; 8 pipelines, gap analysis, ranked next moves. | Current implementation work. |
| [docs/VFX_LANES.md](docs/VFX_LANES.md) | **VFX lane disambiguation** — `pipelines/vfx/` vs `art_lab/shaders/` decision tree, tool tables, when not to merge. | New VFX research; lane-internal status. |
| [docs/tools/README.md](docs/tools/README.md) | **Tool docs index** — map of every per-tool/per-pipeline doc that lives next to its code. New entry point for "where's the doc for X?" | Tool doc content (lives next to code). |
| [docs/pipeline_reviews/README.md](docs/pipeline_reviews/README.md) | **Per-pipeline review index** — manual calibration pass 2026-05-07. Honest quality verdicts per lane. **Read before assuming anything works well.** | Live status (that's PIPELINE_DIRECTORY). |
| [animators/INSTALL_MATRIX.md](animators/INSTALL_MATRIX.md) | **Animator install recipes** — 13 tools install-validated for RTX 5090 / Win11 as of 2026-05-07. Exact pip commands, smoke tests, gotchas (kaolin wheel, bpy DLL load order, etc.). | Tool API/usage details. |
| [docs/audits/AUDIT_2026_05_07.md](docs/audits/AUDIT_2026_05_07.md) | Earlier 2026-05-07 audit (pre-nuke). Forensics. | — |
| [docs/audits/REVIEW.md](docs/audits/REVIEW.md) | Character-pipeline review. The depth standard. | Forward-looking work. |
| [docs/plans/LONG_TERM_VISION.md](docs/plans/LONG_TERM_VISION.md) | Multi-month directional intent for the asset factory. | Tactical priorities (those live in ROADMAP). |
| [docs/reference/CLOUD_KEYS.md](docs/reference/CLOUD_KEYS.md) | Index of every `*_API_KEY` env var, what activates it, and fallback behavior when missing. | Tool capability descriptions. |
| [docs/reference/OPENTOPO_API.md](docs/reference/OPENTOPO_API.md) | OpenTopography endpoint/dataset/rate-limit reference and known API gotchas. | Live asset-factory status count. |
| [_archive/worldgen_2026_05_07/docs/worldgen_v1/WORLDGEN_QUALITY.md](_archive/worldgen_2026_05_07/docs/worldgen_v1/WORLDGEN_QUALITY.md), [_archive/worldgen_2026_05_07/docs/worldgen_v1/WORLD_GEN_QA.md](_archive/worldgen_2026_05_07/docs/worldgen_v1/WORLD_GEN_QA.md), [_archive/worldgen_2026_05_07/docs/worldgen_v1/WORLDGEN_ARCHITECTURE.md](_archive/worldgen_2026_05_07/docs/worldgen_v1/WORLDGEN_ARCHITECTURE.md) | Worldgen **v1-era** lessons-learned (quality knobs, end-to-end QA matrix, architecture rewrite proposal). All three were archived on 2026-05-07 alongside the rest of worldgen v1/v2. Kept for forensics / lessons-learned only. | Current worldgen pipeline (TBD). |
| [docs/plans/RESEARCH_HANDOFF.md](docs/plans/RESEARCH_HANDOFF.md) | Assignment briefs for research agents. | Returned research conclusions. |
| [docs/plans/NEXT_STEPS_2026_05_07.md](docs/plans/NEXT_STEPS_2026_05_07.md) | Cross-cutting state from 2026-05-07 SOTA survey: per-brief outcomes, what got installed, code wirings done, queued installs, free-win action items, **Path 2 inpaint progress table (P0–P7).** | Per-pipeline detail (those live in pipeline_reviews). |
| [docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md](docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md) | **Per-instance mesh albedo inpaint** (faction emblems, damage states) — design + Architecture B confirmation + open-question resolutions + current Phase 1 status. | Live pipeline truth (PIPELINE_DIRECTORY owns that). |
| [research/](research/) | Returned research reports and intake reviews. Treat as evidence/reference, not live status. | Current implementation status. |

## Current pipeline handoffs (one per pipeline; latest version only)

These are point-in-time snapshots of the most recent build chat per pipeline. When a new version ships, the prior handoff moves to `_archive/handoffs_<date>/`.

When a pipeline gets a deep-dive (Phase 11+ pattern), the deep-dive handoff supersedes the prior version handoff. Both stay at root for a few days; the older one is archived after the next deep-dive lands.

| Handoff | Pipeline | Status |
|---|---|---|
| **[docs/handoffs/HANDOFF_world3_orchestrator_2026_05_08.md](docs/handoffs/HANDOFF_world3_orchestrator_2026_05_08.md)** | world3 (NEW orchestrator entry point) | **READ FIRST if you are picking up world3 as orchestrator. Single-page caught-up doc: what you own, what's been built, M1–M5, first move, sharp edges, doc-system map.** |
| **[world3/docs/WORLD3_STATE_2026_05_08.md](world3/docs/WORLD3_STATE_2026_05_08.md)** | world3 (orchestrator state) | Full orchestrator state doc — knob-space + inventory + gaps + M1–M5 detail + owner/worker boundary + handoff protocol + change log. Source of truth for direction. |
| [world3/docs/FUTURE_WORLD_SOURCES_2026_05_08.md](world3/docs/FUTURE_WORLD_SOURCES_2026_05_08.md) | world3 (post-M5 option register) | Track A — alternative world sources (NLCD land-cover, bathymetry, planetary DEMs, sketch-to-heightmap, fantasy world generators, photo+depth) + Track B — explorable interiors (castles, dungeons, building insides). Forward-looking; pick from after M1–M5 closes. |
| [world3/docs/FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md](world3/docs/FUTURE_PROCEDURAL_STRUCTURES_2026_05_08.md) | world3 (post-M5 option register) | Track C — procedural structure generators (trees, crystals, voronoi, fractals, scree, lattices — 11 families surveyed). Forward-looking; tier 1 starter is G1 trees + G7 grass + G5 scree. |
| [world3/docs/OPENTOPO_DATA_DIRECTORY_2026_05_08.md](world3/docs/OPENTOPO_DATA_DIRECTORY_2026_05_08.md) | world3 (data directory) | 50-region curation across 5 tiers targeting ~30 GB cache. Biome + continent + famous/non-famous balanced mix. Independent of M1–M5; worker handoff candidate. |
| **[docs/handoffs/HANDOFF_TEMPLATE_to_worker.md](docs/handoffs/HANDOFF_TEMPLATE_to_worker.md)** | world3 (template) | Handoff template for orchestrator → OpenTopo worker tasks. |
| **[docs/handoffs/HANDOFF_world3_phases_cde_2026_05_07.md](docs/handoffs/HANDOFF_world3_phases_cde_2026_05_07.md)** | world3 / textures | Phase C/D/E session arc (anchor framing + kit-binding fix + per-mode tuning). Superseded by state doc for direction; still the deep dive on what landed. |
| [docs/handoffs/HANDOFF_phase_c_anchor_framing_2026_05_07.md](docs/handoffs/HANDOFF_phase_c_anchor_framing_2026_05_07.md) | world3 / textures | Phase C-only handoff (mid-session); the C/D/E consolidated handoff above supersedes for orientation. |
| [docs/handoffs/HANDOFF_phase_d_complete_2026_05_07.md](docs/handoffs/HANDOFF_phase_d_complete_2026_05_07.md) | world3 / textures | Phase D handoff (kit generation, predates the kit-binding fix). |
| **[docs/handoffs/HANDOFF_2026_05_07_night_path2_parked.md](docs/handoffs/HANDOFF_2026_05_07_night_path2_parked.md)** | Cross-cutting | Latest — whole-project orientation + Path 2 parked + open backlog |
| **[docs/handoffs/HANDOFF_phase12_audio_2026_05_06.md](docs/handoffs/HANDOFF_phase12_audio_2026_05_06.md)** | Audio | **Latest — Phase 12 deep-dive (Stable Audio Open 1.0 real bake on 10 biomes / 142 stems)** |
| [_archive/handoffs_2026_05_06/HANDOFF_audio_v3_2026_05_06.md](_archive/handoffs_2026_05_06/HANDOFF_audio_v3_2026_05_06.md) | Audio | Superseded by Phase 12 (archived; A2 deferred fixes still relevant for tooling forensics) |
| [docs/handoffs/HANDOFF_ui_v3_2026_05_06.md](docs/handoffs/HANDOFF_ui_v3_2026_05_06.md) | UI / Icons | Latest — v3 (D + U2) |
| [docs/handoffs/HANDOFF_vfx_v2_2026_05_06.md](docs/handoffs/HANDOFF_vfx_v2_2026_05_06.md) | VFX / Spells | Latest — v2 (C2) |
| **[docs/handoffs/HANDOFF_phase11_props_2026_05_06.md](docs/handoffs/HANDOFF_phase11_props_2026_05_06.md)** | Props | **Latest — Phase 11 deep-dive (HY3D-2.1 + Trellis2 A/B + sweep + dispatcher + postprocess orchestrator + Phase 11C scene-integration deferred)** |
| [_archive/handoffs_2026_05_06/HANDOFF_props_v2_2026_05_06.md](_archive/handoffs_2026_05_06/HANDOFF_props_v2_2026_05_06.md) | Props | Superseded by Phase 11 (archived; v2 procedural + LOD + collision pipeline shape still in use) |
| [docs/handoffs/HANDOFF_game_data_v2_2026_05_06.md](docs/handoffs/HANDOFF_game_data_v2_2026_05_06.md) | Game Data | Latest — v2 (F2 + AB1); 14 records validate, real TLTE seed content still pending |
| [docs/handoffs/HANDOFF_phase9_2026_05_06.md](docs/handoffs/HANDOFF_phase9_2026_05_06.md) | Open-weights / ComfyUI | Latest — foundation (dry-run safe). Phase 11/12 used Comfy/Trellis paths in earnest, this is still the foundation snapshot. |
| [docs/handoffs/HANDOFF_audit_expand_2026_05_06.md](docs/handoffs/HANDOFF_audit_expand_2026_05_06.md) | Cross-cutting (AB1 round) | Historical — superseded by Phase 11 for props |
| [_archive/worldgen_2026_05_07/docs/handoffs/HANDOFF_PROMPT_worldgen.md](_archive/worldgen_2026_05_07/docs/handoffs/HANDOFF_PROMPT_worldgen.md) | Worldgen (archived) | Was the v2 rebuild prompt; archived 2026-05-07 with the rest of worldgen v1/v2. |
| [docs/audits/AUDIT_HANDOFF_PROMPT.md](docs/audits/AUDIT_HANDOFF_PROMPT.md) | Audit chat prompt | Reusable. Last audit output: `docs/audits/AUDIT_2026_05_07.md` |

## Archive (`_archive/`)

Superseded snapshots. Treat as historical context — never edit, never re-promote without a reason.

- `_archive/handoffs_2026_05_06/` — superseded handoff snapshots: older versions (`HANDOFF_audio_v3` superseded by Phase 12, `HANDOFF_props_v2` superseded by Phase 11), `PM*` generic dumps including `HANDOFF_2026_05_06_PM5_worldgen_swappoints.md` (worldgen v1 broke after that), `AB_RESULTS.md` scratch, `ART_LAB_HANDOFF_2026_05_06.md`.
- `_archive/audits_2026_05_06/` — `AUDIT_2026_05_06.md` (initial audit) and `AUDIT_props_gamedata_2026_05_06.md` (AB1 round audit). Findings rolled into ROADMAP / EXPANSION_PLAN; the audit docs are kept for forensics only.
- `_archive/orphan_research/` — research blobs that landed in `D:\assets\` but aren't on the factory's research track (e.g. one-off shader-generation report).

## Update Rules

- Put status changes in [PIPELINE_DIRECTORY.md](PIPELINE_DIRECTORY.md) first.
- Put new scripts and environment changes in [TOOLS_INDEX.md](TOOLS_INDEX.md).
- Put runnable recipes in [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md), with links back to tool/status docs instead of duplicating large status paragraphs.
- Put "what next" decisions in [docs/plans/ROADMAP.md](docs/plans/ROADMAP.md). Put per-phase living checklists in [docs/plans/EXPANSION_PLAN.md](docs/plans/EXPANSION_PLAN.md).
- Keep handoffs as historical context. Do not revise old handoffs to match current reality. When a new version ships, archive the prior version under `_archive/handoffs_<date>/`.
- Keep `research/*.md` immutable unless the task is explicitly to edit a research report.
- Keep `_archive/` immutable. If something in the archive turns out to be load-bearing, copy a forward-looking summary into the live doc rather than editing the archived file.
