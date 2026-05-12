# World3 Rebuild Plan — 2026-05-11

> **Active rebuild plan.** Written 2026-05-11 after stock-take revealed
> doc-tree divergence + competing handoff docs + invented promotion-state
> vocabulary across orchestrator-side planning. Backup of pre-rebuild state
> at `D:/assets/_backup_world3_2026_05_11_pre_rebuild/`.

## Why rebuild (not just patch)

The audit pass found ~10 real divergences. Patching them one-by-one would
work but leaves the underlying problem: **the orchestrator-side doc tree
grew to 124 markdown files with no clear contract, and several "canonical"
docs invented vocabulary that doesn't match the actual code/schemas.**

A rebuild fixes the divergence pattern by:
1. Treating the worker-shipped code + manifests + scenes + captures as
   ground truth
2. Re-deriving the orchestrator-side plan + docs FROM that ground truth
3. Drastically reducing the doc surface (target: <30 active docs)
4. Establishing one canonical doc with explicit "if anything disagrees,
   this wins" authority
5. Aligning every doc's vocabulary with the actual schema (promotion
   states, knob-space, contract files)

This is not throwing away work. The worker's M1-M18 implementation,
manifests, scenes, captures, and audits are all kept verbatim. We're
rewriting the orchestrator-side planning layer that sits on top.

## What we keep (ground truth)

These survive untouched. The rebuild builds AROUND them, not over them.

### Code
- `world3/pipeline/` — 54 Python scripts (build_*, audit_*, derive_*, export_*, etc.)
- `world3/scripts/` — 35 Godot scripts (ChunkLoader, Terrain, IsoCam, TopDownCam, M12 parity runner, etc.)
- `world3/scenes/` — 157 Godot scenes (review scenes, capture scenes, source-stack tours)
- `world3/shaders/` — 4 .gdshader files (unified splat, terrain_blend, terrain_hex_detail, etc.)
- `pipelines/textures/` — 40 textures pipeline scripts (aaa_texture.py, flux_seamless.py, diversity_compare.py, bake_pbr.py, etc.)
- `pipelines/terrain/` — 11 terrain pipeline scripts (build_master_catalog.py, bulk_pull.py, pull_megastack_queue.py, fetch_regional_stac.py, landlab_smoke_test.py)

### Manifests + schemas (the actual contracts)
- `world3/jobs/production_promotion_candidates.json` — the M13 gate (authoritative)
- `world3/jobs/m14_texture_bakeoff_plan.json`
- `world3/jobs/m15_feature_scatter_policy.json`
- `world3/jobs/m17_procedural_neighbor_recipe.json`
- `world3/jobs/m17_rule_extraction_sources.json`
- `world3/jobs/m18_closure_review_manifest.json`
- `world3/jobs/m18_representative_slice_manifest.json`
- `world3/jobs/biome_kits.json`, `biome_transition_rules.json`, `regions.json`
- `world3/materials/catalog.json` — 31 materials + schema
- `world3/data_catalog.json` — needs regen (stale at 292 DEMs vs 657 on disk)

### Worker-shipped evidence docs (M-specific, kept verbatim)
- `WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md` (the formal audit)
- `WORLD3_M1_M18_HONEST_AUDIT_2026_05_10.md` (the pre-formal audit; kept as decision trail)
- `WORLD3_M1_M18_FULL_AUDIT_PLAN_2026_05_11.md`
- All `M*_*_PROOF_*.md` docs (M10/M11/M12/M14/M15/M16/M17/M18 evidence)
- All `M*_*_REVIEW_*.md` docs (per-bakeoff per-band reviews)
- All `M*_*_AUDIT_*.md` docs (per-M honest audits)
- `PRODUCTION_PROMOTION_AUDIT_2026_05_10.md`
- `M18_CLOSURE_AUDIT_2026_05_10.md`
- `GAMEPLAY_VIEW_QUALITY_PLAN_2026_05_09.md`
- `SOURCE_REPEAT_POLICY_2026_05_09.md`
- `SOURCE_STACK_VALID_AREA_POLICY_2026_05_08.md`
- `TERRAIN_SEAM_INTEGRATION_RESEARCH_2026_05_09.md`
- All OpenTopo worker-domain docs (`OPENTOPO_*.md`)

### Cross-pipeline ground truth
- `pipelines/textures/HANDOFF_FLUX2_BAKEOFF_2026_05_10.md`
- `pipelines/textures/WORKFLOW_GUIDE_FLUX2_2026_05_10.md`
- `pipelines/textures/DIVERSITY_COMPARE_2026_05_09.md`
- `pipelines/textures/FLUX2_KLEIN_9B_SETUP_2026_05_10.md`
- `pipelines/terrain/landlab_smoke_test.py` + README
- `docs/MASTER_DATA_CATALOG.md`
- `docs/plans/LONG_TERM_VISION.md`

### Source-stack + capture evidence
- `world3/textures/source_stack/*` — 24 region bundles (regen would lose specific bakes)
- `world3/docs/captures/` — 374 captures (regeneratable but expensive)

## What we rebuild (orchestrator-side planning layer)

These get rewritten from scratch, AFTER auditing against the kept ground truth:

### Drop (or archive)
- `ROADMAP.md` (current version, just rewritten today) — rewrite once with verified schema vocabulary
- `ORCHESTRATOR_HANDOFF_2026_05_11.md` (just written) — rewrite after rebuild
- `WORLD3_CONTRACT_2026_05_10.md` — re-derive from actual bundle layouts
- `WORLD3_COMPLETION_BAR_2026_05_10.md` — re-derive with actual gate state names
- `WORLD3_ARCHITECTURE_TEMP_2026_05_10.md` — re-validate modules against actual code
- `WORLD3_EXEC_SUMMARY_2026_05_10.md` — rewrite or retire
- `M_SEQUENCE_2026_05_10.md` — rewrite or retire
- `WORLD3_OPERABILITY_GAPS_2026_05_10.md` — re-validate
- 5 arc docs (`ATMOSPHERE_ARC`, `SKY_ARC`, `WATER_ARC`, `WEATHER_ARC`, `CONFORMANCE_ARC`) — defer entirely until needed; not active scope
- `M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md` — keep as committed-but-not-yet-started plan; update framing-correction at top
- `M25_M39_WATER_WEATHER_ROADMAP_2026_05_10.md` — already superseded; archive
- `ROADMAP_HISTORY_2026_05_10.md` — keep as historical archive
- `REBUILD_PLAN_2026_05_11.md` (this doc) — active plan during rebuild

### Retire entirely
- `PLAN.md` — stale (says "Current Iteration Plan: M1-M7")
- `NEXT_SESSION_PROMPT.md` — competing handoff doc
- `TEXTURE_PIPELINE_FIX_PLAN.md` — wrong location, 90% obsolete
- `DOCS_GUIDE.md` — claims 24 files when reality is 124; misleading
- `WORKFLOW_SNAPSHOT_2026_05_08.md` — superseded by audit + ROADMAP
- `M7_M12_NEAR_ROADMAP.md` — superseded; M7-M12 closed
- `M13_M18_POST_PARITY_ROADMAP_2026_05_10.md` — superseded; M13-M18 closed
- `WORKFLOW.md` — runbook from 2026-05-07; needs verification before retire (might still be accurate, just stale-feeling)

### Investigate before deciding
- `DECISIONS.md` — check if still maintained
- `README.md` — top-level world3 readme; should be one of the active docs

## What we cut

These get deleted (or kept in backup only). Reduce surface, not just reorganize.

- `M1_M7_*` series (8 files) — pre-M13 audits, evidence integrated into formal audit
- Phase A-F docs (`PHASE_F_*`, etc.) — Phase-era planning, integrated into ROADMAP_HISTORY
- `M2_TRANSITION_MATERIAL_PROTOTYPE.md` — implementation-era doc, integrated
- Other M1-M5 implementation-era docs once their evidence is in the audit report

Anything cut goes to `world3/docs/_archived_2026_05_11/` rather than being deleted, so git history is the safety net but the active tree stays clean.

## The target end-state

After rebuild, `world3/docs/` should have **roughly 30 active docs**:

### Active orchestrator-side (rewritten, ~6 docs)
1. **ROADMAP.md** — canonical roadmap. Current state, active milestone, gate truth, doc role map.
2. **CONTRACT.md** — output bundle spec, derived from actual bundle file layouts on disk.
3. **COMPLETION_BAR.md** — what "done" means; uses actual gate state names.
4. **HANDOFF.md** — cold-start prompt; points at ROADMAP.md as canonical.
5. **WORKFLOW.md** — living runbook (verify existing one against current reality; update or rewrite).
6. **README.md** — entry point for first-time readers, points everywhere else.

### Active worker-shipped audits (kept verbatim, ~5 docs)
- `WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md`
- `PRODUCTION_PROMOTION_AUDIT_2026_05_10.md`
- `M18_CLOSURE_AUDIT_2026_05_10.md`
- `M7_M12_CLOSURE_AUDIT_2026_05_10.md`
- `M1_M7_VISUAL_AUDIT_2026_05_08.md` (most recent M1-M7 audit only)

### Per-M evidence docs (kept; ~12 docs)
- `M10_*` (3 docs: terrain seam integration + ecotone + unlike-biome review)
- `M11_*` (3 docs: junction layer + fourway + case matrix)
- `M12_*` (2 docs: runtime parity proof + view-mode audit)
- `M14_*` (5 docs: close-play board + bakeoff reviews; consolidate where possible)
- `M15_*` (1 doc: feature scatter proof)
- `M16_*` (2 docs: gallery board + iso impostor research)
- `M17_*` (1 doc: rule extraction)
- `M18_*` (2 docs: closure audit + representative slice first pass)

### Policy + research kept (~5 docs)
- `GAMEPLAY_VIEW_QUALITY_PLAN_2026_05_09.md`
- `SOURCE_REPEAT_POLICY_2026_05_09.md`
- `SOURCE_STACK_VALID_AREA_POLICY_2026_05_08.md`
- `TERRAIN_SEAM_INTEGRATION_RESEARCH_2026_05_09.md`
- `DECISIONS.md` (verify it's current)

### Active plans (~2 docs)
- `M19_M24_HYBRID_PROCEDURAL_ROADMAP_2026_05_10.md` — M19+ committed scope
- `WORLD3_OPERABILITY_GAPS_2026_05_10.md` — O1-O3 promoted; rest queued

### Archive (`_archived_2026_05_11/`, ~80+ docs)
- All cut items above

### OpenTopo worker domain (untouched, kept where they are; ~10 docs)
- All `OPENTOPO_*.md`

That's ~30 active docs (~6 orchestrator + 5 audits + 12 evidence + 5 policy + 2 plans) plus the OpenTopo set the worker owns separately, plus an archive. Compared to today's 124, that's a 4× reduction with no information loss (archive preserves everything).

## What we expect world3 to be at end-of-rebuild

A **world-generation pipeline** that produces world-data bundles per a stable
contract. Specifically:

- **Active milestone is M19** (procedural neighbor placement quality)
- **Quality bar is "workflow evidence + visible improvement vs current"** —
  NOT AAA-grade. That's been a recurring over-scoping pattern; the rebuild
  locks it in.
- **Procedural is the placement engine** — heightmaps, biome labels, splat
  weights, scatter masks, transitions. Textures come from the textures
  pipeline + M1 catalog. Procedural zones consume catalog materials.
- **8 modules** (per architecture map): Terrain Foundation, Material Catalog,
  Transitions, Scatter, Water, Atmosphere, Sky, Weather. Validated against
  actual code at rebuild time.
- **One canonical roadmap** (`ROADMAP.md`) with explicit "this plus the
  latest committed audit wins if anything disagrees" authority.
- **Promotion gate uses actual schema state names**: `accepted_workflow`,
  `ready_for_live_review`, `sidecar_candidate`, `negative_evidence`,
  `production_candidate`, `production_promoted`. No invented vocabulary.
- **Data catalog regenerated** (657 DEMs reflected, not 292).
- **All orchestrator-side docs committed**. No untracked planning state.

## Sequencing (8 steps, user-gated)

The rebuild executes in ordered steps with explicit user gates between
phases. Each step is small (1-3 sessions) and reviewable.

### Step 1: Inventory + cuts (no user gate; safe)
- Move all "Retire entirely" + "Cut" docs to `world3/docs/_archived_2026_05_11/`
- Don't delete; preserve git history
- Result: doc count drops from 124 to ~40
- Cost: ~10 minutes

### Step 2: Regenerate authoritative state (no user gate; safe)
- Run `python pipelines/terrain/build_master_catalog.py` to refresh
  `data_catalog.json` against actual 657 DEMs
- Verify `production_promotion_candidates.json` schema; this is the
  vocabulary source of truth
- Verify materials/catalog.json
- Cost: ~10 minutes

### Step 3: Re-derive output contract from actual bundles **— USER GATE**
- Walk the 24 source-stack bundles + 8 promotion candidates
- Document the ACTUAL files each bundle contains, with actual sizes
  + formats + constraints
- Write a new `CONTRACT.md` describing reality, not aspiration
- Show user before committing
- Cost: ~1 session

### Step 4: Rewrite ROADMAP.md with verified vocabulary **— USER GATE**
- Use actual promotion state names from the schema
- Reference the actual audit verdict (M1-M18 workflow-closed / visually conditional)
- Active milestone = M19 with the framing correction (procedural = placement)
- Doc role map points at the ~30-doc target tree
- Show user before committing
- Cost: ~1 session

### Step 5: Write COMPLETION_BAR.md + HANDOFF.md + README.md **— USER GATE**
- COMPLETION_BAR uses actual gate names + actual measurable criteria
- HANDOFF is the cold-start prompt for a new orchestrator/agent
- README is the entry-point for first-time readers
- Show user before committing all three
- Cost: ~1 session

### Step 6: Verify WORKFLOW.md against current reality **— USER GATE**
- Read existing WORKFLOW.md (the 2026-05-07 living runbook)
- Walk through each step against current code
- Either update minimally or rewrite if too stale
- Show user before committing
- Cost: ~1 session

### Step 7: Update operability gaps + M19-M24 plan **— USER GATE**
- Both already exist; just need framing-correction propagation +
  vocabulary alignment
- Show user before committing
- Cost: ~30 minutes

### Step 8: Commit + verify end-state **— USER GATE**
- Single rebuild commit (or 2-3 small commits)
- Run a sanity check: can a cold-start agent read README → ROADMAP → 
  HANDOFF → relevant evidence doc and start work?
- Show user the final state for sign-off
- Cost: ~30 minutes

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| **Worker is mid-M19 work**; rebuild disrupts them | Sequence rebuild during quiet user-window; worker resumes M19 from clean state |
| **Documentation rewrite invents new wrong vocabulary** | Step 2 establishes schema as source of truth; every subsequent step references schema, not prior docs |
| **Cut decisions lose information** | Archive, don't delete. Everything moves to `_archived_2026_05_11/` which stays in git |
| **Backup is incomplete** | Verified: 254 MB backup, file counts match disk, git diff captured |
| **Rebuild itself drifts mid-flight** | This plan doc is the active source-of-truth during rebuild. User gates between steps catch drift |
| **External pipelines (textures, terrain) get disrupted** | Out of scope for this rebuild. Only world3 docs + planning layer change |

## Out of scope for this rebuild

- Worker's M14-M18 code shipped (we keep all of it)
- Textures pipeline (40 scripts, stable)
- Terrain pipeline (11 scripts, stable + Landlab smoke-tested)
- ComfyUI model installations (FLUX 2 9B + dev all on disk)
- DEM cache (657 files, regenerable but kept)
- OpenTopo worker domain docs
- Any actual generation/build work (M19, bakeoff, etc.)

This rebuild is **planning-layer only**. Code stays put.

## Authority

While the rebuild is in progress (Steps 1-8), THIS DOC is the canonical
authority. After rebuild closes, ROADMAP.md becomes canonical and this
doc moves to `_archived_2026_05_11/` as decision trail.

## Status

- [x] Backup made (254 MB at `D:/assets/_backup_world3_2026_05_11_pre_rebuild/`)
- [x] Plan written (this doc)
- [ ] Step 1: Inventory + cuts
- [ ] Step 2: Regenerate authoritative state
- [ ] Step 3: Re-derive CONTRACT.md (USER GATE)
- [ ] Step 4: Rewrite ROADMAP.md (USER GATE)
- [ ] Step 5: Write COMPLETION_BAR + HANDOFF + README (USER GATE)
- [ ] Step 6: Verify WORKFLOW.md (USER GATE)
- [ ] Step 7: Update operability + M19-M24 (USER GATE)
- [ ] Step 8: Final commit + sign-off (USER GATE)

## Cross-references

- Pre-rebuild backup: `D:/assets/_backup_world3_2026_05_11_pre_rebuild/`
- Stock-take findings: in chat history 2026-05-11 (also captured in the
  worker M1-M18 audit verdict + this plan's "Why rebuild" section)
- Audit verdict: `WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md` (commit c5b0cff)
