# Archived 2026-05-11 — Decision Trail

These docs were moved out of the active `world3/docs/` tree on 2026-05-11
during a planning-layer cleanup. **They are kept here, not deleted.** Git
history is preserved. Use this archive when you need decision context
that the canonical active docs don't carry.

Reason for the cleanup: the active doc tree grew from ~24 docs (2026-05-07)
to 124 (2026-05-11), with overlapping planning docs that invented
inconsistent vocabulary and made the canonical roadmap hard to find. The
worker-shipped code/manifests/audits are all kept active. This archive
holds the orchestrator-side planning layer history + the per-M
implementation evidence that's now consolidated into the M1-M18 audit.

## Archive structure

### `retired_planning/` (8 docs)

Competing or stale orchestrator-side planning docs. None of these are
canonical anymore.

- `PLAN.md` — pre-2026-05-08 "M1-M7 current iteration plan." Superseded by
  ROADMAP.md.
- `NEXT_SESSION_PROMPT.md` — competing handoff doc from a previous session.
  Superseded by ORCHESTRATOR_HANDOFF_2026_05_11.md.
- `TEXTURE_PIPELINE_FIX_PLAN.md` — 2026-05-07 textures audit; lived in
  wrong location (about `pipelines/textures/`). Mostly overtaken by
  FLUX 2 work since.
- `DOCS_GUIDE.md` — orientation doc that claimed "~24 markdown files"
  when reality was 124. Misleading; ROADMAP.md's doc role map replaces it.
- `WORKFLOW_SNAPSHOT_2026_05_08.md` — superseded by audit + ROADMAP.
- `M7_M12_NEAR_ROADMAP.md` — superseded; M7-M12 closed and audited.
- `M13_M18_POST_PARITY_ROADMAP_2026_05_10.md` — superseded; M13-M18
  closed (workflow-closed / visually conditional per audit).
- `M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md` — old flat-range framing;
  superseded by the arc-named approach (which itself is now in
  `superseded_planning/` as the rebuild simplified the long-term plan).

### `phase_history/` (4 docs)

Phase A-F era planning, pre-M-numbered approach.

- `PHASE_F_CHUNK_SIZE_SWEEP.md`
- `PHASE_F_RESEARCH_2026_05_07.md`
- `PLAN_phaseA_archived.md`
- `ROADMAP_v1_archived.md`

Useful only for understanding why the M-chain replaced the Phase
approach (per the 2026-05-08 reframe).

### `m1_m9_implementation/` (26 docs)

Per-M implementation evidence from M1-M9 era. **Evidence consolidated
into `WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md`** (the formal audit) and
`WORLD3_M1_M18_HONEST_AUDIT_2026_05_10.md` (the pre-formal honest audit,
both still active). These per-M docs are kept for decision trail but
not active reading.

- M1-M5 audits + closure docs
- M2 transition prototype + boundary contract
- M3 source-stack seam review
- M4 splat shader prototype + chunk material contract
- M5 walk streaming + streaming budget
- M6 runtime hardening + source material noise audit
- M7 boundary runtime integration + transition mask metrics + source-stack
  boundary review
- M1-M7 visual audit series (plan, audit, vision gap, refinement map,
  remediation plan, workflow validation, organic texture repair)
- Source-stack runtime remediation
- Review scene auto-tour

### `m8_organic_cleanup/` (9 docs)

M8 organic source-material cleanup era. **Superseded by M14 close-play
quality work** which is still active in the tree.

- M8 ComfyUI candidate noise audit + terrain context review + texture regen pass
- M8 grass regen attempts review + visual veto audit
- M8 organic regen queue status

### `superseded_planning/` (9 docs)

Planning docs from 2026-05-10 that were superseded during the
2026-05-11 rebuild. Kept for decision trail of how the long-term plan
evolved.

- `WORLD3_EXEC_SUMMARY_2026_05_10.md` — one-page brief that drifted from
  canonical ROADMAP. Useful patterns are in ROADMAP.md now.
- `M_SEQUENCE_2026_05_10.md` — flat M timeline. Sequence is in
  ROADMAP.md now.
- `WORLD3_ARCHITECTURE_TEMP_2026_05_10.md` — 8-module architecture map.
  Kept here as historical reference; the modules are real but the
  canonical doc role is now smaller.
- `ATMOSPHERE_ARC_2026_05_10.md`, `SKY_ARC_2026_05_10.md`,
  `WATER_ARC_2026_05_10.md`, `WEATHER_ARC_2026_05_10.md`,
  `CONFORMANCE_ARC_2026_05_10.md` — five long-term arc docs. Deferred
  until needed; M19-M24 (hybrid procedural) is the next committed scope.
- `ROADMAP_HISTORY_2026_05_10.md` — historical archive of Phase A-F.
  Most useful content is now in `phase_history/` directly.

## When to come back here

- Looking for decision context that ROADMAP.md doesn't carry
- Understanding why a current approach exists (read the predecessor here)
- Tracing how the M-chain emerged from the Phase approach
- Recovering a specific M-implementation detail consolidated out of the audit

## When NOT to come here

- Looking for current state — use `world3/docs/ROADMAP.md`
- Looking for what to work on next — use `ROADMAP.md`
- Looking for the M13 promotion gate state — use
  `world3/jobs/production_promotion_candidates.json`
- Cold-starting on world3 — use `ORCHESTRATOR_HANDOFF_2026_05_11.md`

## How to restore

If anything in here needs to come back to active:

```
git mv world3/docs/_archived_2026_05_11/<subdir>/<file> world3/docs/<file>
```

Then update the relevant active doc to point at it.

## Pre-rebuild backup

A separate full-disk backup of the pre-rebuild state lives at:
`D:/assets/_backup_world3_2026_05_11_pre_rebuild/`

Includes git diff of all uncommitted dirty state at backup time. Use
that for worst-case "I need everything back exactly how it was" recovery.
