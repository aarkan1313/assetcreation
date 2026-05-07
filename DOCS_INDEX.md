# Docs Index

Canonical ownership map for the `D:\assets` documentation set. When docs disagree, update the owning doc first, then let the other docs link to it instead of repeating stale detail.

## Reference / index docs (stable, frequently updated)

| Doc | Owns | Does not own |
|---|---|---|
| [README.md](README.md) | Entry point, short current-state summary, first commands for common workflows. | Detailed status tables, long roadmaps, full tool inventory. |
| [DOCS_INDEX.md](DOCS_INDEX.md) | This ownership map and navigation rules. | Pipeline status truth. |
| [PIPELINE_DIRECTORY.md](PIPELINE_DIRECTORY.md) | Live status of every pipeline and each status-marker claim. Canonical truth table for "what works today." | Step-by-step recipes. |
| [TOOLS_INDEX.md](TOOLS_INDEX.md) | Script/tool/env inventory, where files live, and quick "what tool for what job" lookup. | Priority decisions or historical handoffs. |
| [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md) | Copy-paste workflow recipes and expected output contracts. | Global status counts and backlog priority. |
| [docs/plans/ROADMAP.md](docs/plans/ROADMAP.md) | Current priorities, done-vs-next reconciliation, pipeline maturity scorecard, and deferred work. | Full API references or script-by-script inventory. |
| [docs/plans/EXPANSION_PLAN.md](docs/plans/EXPANSION_PLAN.md) | Living phased checklist (Phases 0–12), per-pipeline punch lists, decision log. | Status counts (those live in PIPELINE_DIRECTORY). |
| [docs/audits/AUDIT_2026_05_07.md](docs/audits/AUDIT_2026_05_07.md) | Most recent project-state audit — drift flags between docs and disk, recommended next moves. | Current implementation work. |
| [docs/audits/REVIEW.md](docs/audits/REVIEW.md) | Bug-find / fix post-mortems with REVIEW-discipline format. | Forward-looking work. |
| [docs/plans/LONG_TERM_VISION.md](docs/plans/LONG_TERM_VISION.md) | Multi-month directional intent for the asset factory. | Tactical priorities (those live in ROADMAP). |
| [docs/reference/CLOUD_KEYS.md](docs/reference/CLOUD_KEYS.md) | Index of every `*_API_KEY` env var, what activates it, and fallback behavior when missing. | Tool capability descriptions. |
| [docs/reference/OPENTOPO_API.md](docs/reference/OPENTOPO_API.md) | OpenTopography endpoint/dataset/rate-limit reference and known API gotchas. | Live asset-factory status count. |
| [docs/worldgen_v1/WORLDGEN_QUALITY.md](docs/worldgen_v1/WORLDGEN_QUALITY.md), [docs/worldgen_v1/WORLD_GEN_QA.md](docs/worldgen_v1/WORLD_GEN_QA.md), [docs/worldgen_v1/WORLDGEN_ARCHITECTURE.md](docs/worldgen_v1/WORLDGEN_ARCHITECTURE.md) | Worldgen **v1-era** lessons-learned (quality knobs, end-to-end QA matrix, architecture rewrite proposal). All three carry a "Status 2026-05-07: v1-era" banner and were moved to `docs/worldgen_v1/` on 2026-05-06 to declutter root. v2 live source is `pipelines/worldgen_v2/README.md`. | Current v2 implementation status. |
| [docs/plans/RESEARCH_HANDOFF.md](docs/plans/RESEARCH_HANDOFF.md) | Assignment briefs for research agents. | Returned research conclusions. |
| [research/](research/) | Returned research reports and intake reviews. Treat as evidence/reference, not live status. | Current implementation status. |

## Current pipeline handoffs (one per pipeline; latest version only)

These are point-in-time snapshots of the most recent build chat per pipeline. When a new version ships, the prior handoff moves to `_archive/handoffs_<date>/`.

When a pipeline gets a deep-dive (Phase 11+ pattern), the deep-dive handoff supersedes the prior version handoff. Both stay at root for a few days; the older one is archived after the next deep-dive lands.

| Handoff | Pipeline | Status |
|---|---|---|
| **[docs/handoffs/HANDOFF_phase12_audio_2026_05_06.md](docs/handoffs/HANDOFF_phase12_audio_2026_05_06.md)** | Audio | **Latest — Phase 12 deep-dive (Stable Audio Open 1.0 real bake on 10 biomes / 142 stems)** |
| [_archive/handoffs_2026_05_06/HANDOFF_audio_v3_2026_05_06.md](_archive/handoffs_2026_05_06/HANDOFF_audio_v3_2026_05_06.md) | Audio | Superseded by Phase 12 (archived; A2 deferred fixes still relevant for tooling forensics) |
| [docs/handoffs/HANDOFF_ui_v3_2026_05_06.md](docs/handoffs/HANDOFF_ui_v3_2026_05_06.md) | UI / Icons | Latest — v3 (D + U2) |
| [docs/handoffs/HANDOFF_vfx_v2_2026_05_06.md](docs/handoffs/HANDOFF_vfx_v2_2026_05_06.md) | VFX / Spells | Latest — v2 (C2) |
| **[docs/handoffs/HANDOFF_phase11_props_2026_05_06.md](docs/handoffs/HANDOFF_phase11_props_2026_05_06.md)** | Props | **Latest — Phase 11 deep-dive (HY3D-2.1 + Trellis2 A/B + sweep + dispatcher + postprocess orchestrator + Phase 11C scene-integration deferred)** |
| [_archive/handoffs_2026_05_06/HANDOFF_props_v2_2026_05_06.md](_archive/handoffs_2026_05_06/HANDOFF_props_v2_2026_05_06.md) | Props | Superseded by Phase 11 (archived; v2 procedural + LOD + collision pipeline shape still in use) |
| [docs/handoffs/HANDOFF_game_data_v2_2026_05_06.md](docs/handoffs/HANDOFF_game_data_v2_2026_05_06.md) | Game Data | Latest — v2 (F2 + AB1); 14 records validate, real TLTE seed content still pending |
| [docs/handoffs/HANDOFF_phase9_2026_05_06.md](docs/handoffs/HANDOFF_phase9_2026_05_06.md) | Open-weights / ComfyUI | Latest — foundation (dry-run safe). Phase 11/12 used Comfy/Trellis paths in earnest, this is still the foundation snapshot. |
| [docs/handoffs/HANDOFF_audit_expand_2026_05_06.md](docs/handoffs/HANDOFF_audit_expand_2026_05_06.md) | Cross-cutting (AB1 round) | Historical — superseded by Phase 11 for props |
| [docs/handoffs/HANDOFF_PROMPT_worldgen.md](docs/handoffs/HANDOFF_PROMPT_worldgen.md) | Worldgen v2 (active) | Active rebuild prompt. See also `pipelines/worldgen_v2/README.md` and `docs/superpowers/specs/2026-05-06-worldgen-v2-design.md`. |
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
