# World3 Rebuild — Phases B-E Plan

> **Active execution plan.** Builds on Phase A (workflow inventory in
> `WORKFLOW_INVENTORY_2026_05_11.md`). Four sequential phases, each with
> user-review gates, ending in a clean orchestration layer that delivers
> the "data + world-type → world" experience.

## Goal (the north star, locked in)

> "this is the world data I have, here's the world type I want, make it"
>
> — user 2026-05-11

After this rebuild, generating a region should be **one command from a
config file**, not 7-10 hand-curated invocations. The catalog should
auto-update. The textures should bind automatically. The captures should
render automatically. The promotion gate should track results
automatically.

## Phase progression

```
Phase A (DONE)         ↓
Phase B (cold validate)
                       ↓
Phase C (diagnose)     ↓
Phase D (fix gaps)     ↓
Phase E (orchestrator) ↓
                       READY
```

Each phase has a single gate to the next: user reviews outputs, says
"continue" or "pivot." No phase starts until the prior phase ships.

## Phase B — Cold validation of existing chains

**Goal**: prove each documented chain actually works end-to-end from
cold-start, before we build orchestration on top. If chains are broken,
we fix them in Phase D. If they work, we know orchestration is safe.

**Why cold matters**: we have evidence chains have worked at some point
(24 bundles exist). We need to know whether they still work today,
without any "well, the last session had ComfyUI running already" caveats.

### B.1 — Chain 1: Real DEM → review-ready bundle

The most-trafficked chain. The one the worker ran for 24 bundles.

**Test**: re-generate a known bundle from scratch on a fresh shell.

Concrete steps:
1. Pick a region we have a bundle for (suggest: Gloss Mountain — it's in
   the M10/M11/M12 evidence)
2. Find the source DEM in `dems/`
3. Run each script in Chain 1 in order, with the args the existing
   bundle used (recover from `meta.json` if needed)
4. Diff the new bundle against the existing bundle byte-by-byte (or
   image-similarity if PNGs)
5. Record every failure, missing arg, hardcoded path, undocumented
   dependency in `B1_CHAIN1_VALIDATION_2026_05_11.md`

**Pass criteria**: new bundle reproduces existing bundle within tolerance
(exact for JSON, perceptually identical for PNGs).

**Estimated effort**: 1-2 sessions.

### B.2 — Chain 2: Procedural texture → kit deployment

Texture pipeline. Requires ComfyUI running.

**Test**: regenerate one existing material from scratch.

Concrete steps:
1. Pick a known shipped material (suggest: `wgv3_desert_canyon_rock` —
   well-validated through Phase A polish)
2. Start ComfyUI manually
3. Run `aaa_texture.py --prompt <recovered> --id desert_canyon_rock_test
   --category Rock --quality default`
4. Diff against existing material
5. Run `deploy_kit_to_world3.py` for one full kit
6. Verify `.tres` variants emit correctly
7. Record failures in `B2_CHAIN2_VALIDATION_2026_05_11.md`

**Pass criteria**: regenerated material matches existing seam grade /
QA verdict. Deploy produces the same .tres files.

**Estimated effort**: 1 session.

### B.3 — Chain 3: Procedural neighbor → seam-integrated bundle

The chain with the procedural-vs-texture confusion. Most important to
validate.

**Test**: regenerate the M10 real-to-procedural Gloss-canyon-rock proof.

Concrete steps:
1. Read `build_procedural_neighbor_bundle.py` args from M10 evidence
2. Re-run with same args
3. Inspect output — does the procedural side emit the expected
   placement data (height, biome label, splat weights, scatter masks)?
4. Re-run `build_terrain_seam_integration_proof.py` against the new
   procedural bundle + Gloss Mountain source
5. Render the existing review scene against the regenerated bundle
6. Visual diff captures
7. Record failures in `B3_CHAIN3_VALIDATION_2026_05_11.md`

**Pass criteria**: regenerated bundle produces captures within visual
tolerance of original.

**Special focus**: did `build_procedural_neighbor_bundle.py` *actually*
emit smooth tan/sand (placement bug) or did it emit varied splat weights
that something downstream collapsed (downstream bug)? This phase
diagnoses the procedural-vs-texture confusion definitively.

**Estimated effort**: 1-2 sessions.

### B.4 — Chain 4: M14 close-play bakeoff (deferred)

Lowest priority for cold validation because:
- FLUX 2 9B + dev candidates were staged but never run
- Running them requires both ComfyUI active AND the bakeoff hardware
  config we already documented
- The chain itself has working precedent through 2026-05-10 bakeoff
  reviews
- Cold-validating it now would consume hours of compute for relatively
  low diagnostic signal

**Decision**: skip Chain 4 cold validation in Phase B. Validate by
running the actual bakeoff later (after the orchestrator exists, run
the staged FLUX 2 9B comparison as the orchestrator's first real
batch).

### B.5 — Phase B review gate

**User reviews**:
- B1/B2/B3 validation docs
- Lists of every breakage per chain
- Decision: do chains work? Are breakages structural or trivial?

**Output**: agreement on which fixes belong in Phase D + whether any
chain is so broken it requires architectural work (rare).

---

## Phase C — Diagnose

**Goal**: categorize every Phase B finding into one of four buckets, so
Phase D fixes can be sequenced.

### Bucket A: trivial config (env vars, paths, missing deps)

Examples: "script expects ComfyUI URL in env", "script hardcodes
`D:/assets/world3/...` paths". Fix: minimal arg/env work, no rewrite.

### Bucket B: manual-step gaps (could be one script)

Examples: "must run `build_master_catalog.py` after pulls", "must
manually start ComfyUI", "must copy file from X to Y between steps".
Fix: short shell wrapper or Python coordinator.

### Bucket C: real code bugs

Examples: "script crashes on regions with no orthophoto coverage",
"splat weights emit as 0,0,0,0 when biome label is missing". Fix:
focused per-script patches.

### Bucket D: architectural gaps

Examples: "no way to chain steps from a config", "scripts don't share
arg conventions". Fix: new orchestration layer (Phase E).

**Estimated effort**: 1 session.

### Phase C review gate

**User reviews**: the categorized list. Decides what's in Phase D scope.

---

## Phase D — Fix gaps

**Goal**: actually patch what Phase B found, scoped per Phase C buckets.

### D.1 — Trivial config fixes
Bucket A items, batched into one or two small commits.

### D.2 — Manual-step gaps → coordinator scripts
Bucket B items, each gets a small Python coordinator (`pull_and_catalog.py`,
`comfy_session_start.py`, etc.). Not the full orchestrator yet — just the
"these two commands always run together" pairings.

### D.3 — Real code bugs
Bucket C items, per-script patches. Run validation again to confirm.

### D.4 — Catalog auto-regen
Specific deferred fix from Phase A stock-take: catalog needs to refresh
itself after pulls/builds. Add a post-hook to `bulk_pull.py` and
`pull_megastack_queue.py` that calls `build_master_catalog.py`.

### D.5 — Per-lane venv discipline
Set up `pipelines/textures/.venv` (matches the `pipelines/terrain/.venv`
pattern). Document required packages. Note: this may not actually be
needed if ComfyUI provides the Python env for textures.

### Phase D review gate

**User reviews**: chains run cold again, all green. Manual-step counts
dropped. Ready for orchestration.

---

## Phase E — Orchestration layer (the "data + world-type → world" command)

**Goal**: build the top-level orchestrator that delivers the user's
stated workflow.

### E.1 — Request schema (`region_request.json`)

Define what "I want a region" looks like as a declarative config.

```json
{
  "id": "alpine_test_region",
  "source": {
    "type": "real" | "procedural" | "hybrid",
    "dem_ref": "dems/Tetons.tif",          // for real
    "bbox": [...],                          // for procedural
    "patch_seed_refs": [...]                // for hybrid
  },
  "world_type": {
    "biome_kit": "alpine",
    "style_pack": "photoreal" | "painterly" | "topographic",
    "view_modes": ["walk", "iso", "topdown"]
  },
  "options": {
    "water": false,
    "weather": false,
    "scatter_density": "default"
  },
  "output": {
    "bundle_dir": "textures/source_stack/<id>/",
    "render_captures": true,
    "promotion_gate_entry": true
  }
}
```

Concrete deliverables:
- `world3/jobs/region_request_schema.json` — JSON Schema with validation
- `world3/jobs/examples/*.json` — 3-5 example requests
- Documentation: what each knob does, default values

### E.2 — Stages manifest (`stages.json`)

Declare every pipeline step's inputs/outputs/dependencies in a form the
orchestrator can read.

```json
{
  "stages": [
    {
      "id": "fetch_dem",
      "script": "pipelines/terrain/opentopo_fetch.py",
      "inputs": ["bbox", "dataset"],
      "outputs": ["dem_tif"],
      "required_if": "source.type in [real, hybrid]"
    },
    {
      "id": "build_heightmap",
      "script": "world3/pipeline/build_world.py",
      "inputs": ["dem_tif", "size"],
      "outputs": ["heightmap_png", "meta_json"],
      "required_if": "always"
    },
    ...
  ]
}
```

Concrete deliverables:
- `world3/jobs/stages.json` — manifest covering every workflow step
- `world3/pipeline/audit_stages.py` — verify each declared script exists
  and the args line up

### E.3 — Orchestrator (`world3_make.py`)

The actual dispatcher.

```bash
python world3/pipeline/world3_make.py jobs/examples/alpine_test_region.json
```

Behavior:
1. Validate request against schema
2. Resolve which stages are required given request
3. Build dependency graph from stages.json
4. Execute stages in order, capturing stdout/stderr per stage
5. Update bundle directory progressively
6. Run final captures + promotion gate entry
7. Write `run.json` provenance record

Concrete deliverables:
- `world3/pipeline/world3_make.py`
- `world3/pipeline/world3_run_provenance.py` — write per-run records
- `--dry-run` mode that prints the chain without executing
- `--from-stage <id>` for resuming partial runs

### E.4 — All-modes render driver

Today: 100+ per-M Godot scenes load specific bundles. After E.4: one
scene reads bundle path + mode list, renders all requested modes.

Concrete deliverables:
- `world3/scenes/review/orchestrator_capture_driver.tscn`
- `world3/scripts/OrchestratorCaptureDriver.gd` — loads bundle path
  from CLI arg, renders close/medium/iso/topdown
- Per-mode capture template (already exists in Phase E `.tres` system)

### E.5 — Style pack mechanism

Today: Phase E per-mode `.tres` is hardcoded per kit. After E.5: one
`style_pack.json` swaps shader params + material overrides without
touching kits.

Concrete deliverables:
- `world3/jobs/style_packs/photoreal.json`
- `world3/jobs/style_packs/painterly.json`
- `world3/jobs/style_packs/topographic.json`
- Loader logic in `OrchestratorCaptureDriver.gd`

### E.6 — Catalog auto-regen + provenance

Concrete deliverables:
- Post-hook on pulls calls `build_master_catalog.py` (was Phase D.4 if
  not done there)
- `world3_make.py` emits `run.json` per bundle with:
  - request config
  - stage timings
  - output file manifest
  - validation results
  - gate state at end

### E.7 — Documentation + handoff
- `WORKFLOW.md` rewritten to point at orchestrator as the primary entry
- One-page operator guide: "I want a region — here's what to put in the
  request and how to run it"
- `ROADMAP.md` updated to reflect orchestrator as completed
- `ORCHESTRATOR_HANDOFF` updated

### Phase E review gate

**User reviews**: actually run the orchestrator end-to-end. Generate a
region from a request file. Watch captures land. Watch gate state
update. Sign off.

---

## Sequencing + dependencies

```
Phase B  ─────────────►  Phase C  ─────►  Phase D  ─────►  Phase E
(cold validate)         (diagnose)        (fix)            (orchestrate)
   │                                                          │
   │                                                          ▼
   └── any chain catastrophically broken ─────► world4 conversation
                                                (only if Phase B reveals
                                                 architectural rot)
```

The world3-vs-world4 decision sits explicitly between B and C. If B
shows the chains are fundamentally broken (e.g. 5+ structural bugs per
chain), we revisit world4. If B shows the chains mostly work with config
gaps and manual-step gaps, we proceed to C → D → E.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Cold validation reveals dozens of breakages | Phase C buckets handle that; user can pause for triage between B and C |
| ComfyUI doesn't start cleanly for Chain 2/4 cold tests | Phase B.2 documents this as Bucket B (manual-step gap); Phase D.2 wraps the start |
| Phase E orchestrator takes longer than estimated | E.1-E.3 are the minimum viable; E.4-E.7 can ship incrementally |
| User changes north star mid-rebuild | Re-anchor against `WORKFLOW_INVENTORY_2026_05_11.md`'s evidence + this plan; resist re-scoping |
| World4 emerges as right answer | Phase B captures evidence; world4 inherits validated script catalog |

## Out of scope for this rebuild

- Worker's M14-M18 code (kept, validated, not rewritten)
- M19 generation work (deferred until orchestrator exists; M19 becomes
  the orchestrator's first real run)
- ComfyUI workflows themselves (already documented; kept as-is)
- DEM cache management beyond catalog regen (already mature)
- Atmosphere/Sky/Water/Weather arcs (already deferred via archive)

## Estimated total effort

| Phase | Effort | Ends with |
|---|---|---|
| B | 3-5 sessions | 3 validation docs + breakage inventory |
| C | 1 session | bucketed gap list |
| D | 3-5 sessions | green chains + coordinator scripts |
| E | 5-8 sessions | orchestrator + docs + one example region generation |

**Total**: 12-19 sessions / ~2-4 weeks at current cadence. Comparable to
the M14-M18 worker arc that just shipped.

## Status

- [x] Phase A: workflow inventory (`WORKFLOW_INVENTORY_2026_05_11.md`)
- [ ] Phase B.1: Chain 1 cold validation (Real DEM → bundle)
- [ ] Phase B.2: Chain 2 cold validation (texture → kit)
- [ ] Phase B.3: Chain 3 cold validation (procedural neighbor → seam)
- [ ] Phase B.5: review gate
- [ ] Phase C: diagnose
- [ ] Phase D: fix
- [ ] Phase E: orchestrator

## Cross-references

- Phase A inventory: [`WORKFLOW_INVENTORY_2026_05_11.md`](WORKFLOW_INVENTORY_2026_05_11.md)
- Pre-rebuild backup: `D:/assets/_backup_world3_2026_05_11_pre_rebuild/`
- Audit verdict: [`WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md`](WORLD3_M1_M18_AUDIT_REPORT_2026_05_11.md)
- M13 gate (state authority): `../jobs/production_promotion_candidates.json`
- Original rebuild plan (now superseded by this phase plan): [`REBUILD_PLAN_2026_05_11.md`](REBUILD_PLAN_2026_05_11.md)
