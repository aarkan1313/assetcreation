# Phase C — Diagnosis & Fix Sequencing

> Synthesis of Phase B findings (B.1 / B.2 / B.3) into bucketed gaps with
> concrete fix recommendations and an execution order for Phase D + E.

## Summary

Phase B tested three end-to-end chains cold from documented inputs:

- **Chain 1** (real DEM → bundle): byte-identical reproduction across 18 files
- **Chain 2** (textures): couldn't run cold; ComfyUI offline; 5 env gaps
- **Chain 3** (procedural neighbor): 3/4 byte-identical + **root cause for "smooth tan/sand" found**

**Total findings: 9** (0 Bucket A, 5 Bucket B, 2 Bucket C, 2 Bucket D)
- Bucket A — trivial config: 0
- Bucket B — manual-step gaps: 5 (all env/invocation; orchestrator territory)
- Bucket C — real code bugs: 2 (one big, one trivial)
- Bucket D — architectural gaps: 2 (no orchestrator, no batch wrapper)

**Verdict from Phase B**: world3 stays. No world4 case. Worker pipelines
are exemplary. Every gap is fixable in-place.

## Full bucketed findings register

### Bucket A — trivial config
*(none)*

### Bucket B — manual-step gaps (Phase D environment work + Phase E coverage)

| ID | Finding | From | Fix size |
|---|---|---|---|
| B-1 | `pipelines/textures/.venv` doesn't exist; texture pipeline runs on system Python 3.12 with no per-lane venv. Discipline asymmetric vs `pipelines/terrain/.venv`. | B.2 | half-session |
| B-2 | ComfyUI auto-start missing. `aaa_texture.py` assumes ComfyUI is at `127.0.0.1:8188`; no preflight, no start. Cold-start operators get generic "connection refused." | B.2 | small wrapper |
| B-3 | StableMaterials backend (`pbr=sm`, the **default** preset) requires `animators/mesa-env/venv` invocation pattern that isn't in `aaa_texture.py --help`. | B.2 | doc fix or auto-detect |
| B-4 | No preflight check for required model files (FLUX 2 klein, StableMaterials). Failures surface mid-flow in ComfyUI instead of upfront from the orchestrator. | B.2 | small preflight |
| B-5 | No documented "start ComfyUI; then run aaa_texture.py" sequence. Operator has to discover the dependency by reading the script. | B.2 | doc + sequence wrapper |

### Bucket C — real code bugs (Phase D direct fixes)

| ID | Finding | From | Fix size | Priority |
|---|---|---|---|---|
| **C-1** | **`build_macro()` parameter tune in `build_procedural_neighbor_bundle.py:96-124`.** The procedural macro collapses the catalog albedo to its median RGB color, then adds the texture back at only 42% strength under smooth value noise. **This is the documented root cause of the "broad smooth tan/sand" visual veto** that drove the entire M19 framing correction. | B.3 | 2-3 hours iter | **BIGGEST WIN** |
| C-2 | `res_path()` in `build_procedural_neighbor_bundle.py:52` crashes with `ValueError` if `--out` is outside `world3/`. `path.relative_to(ROOT)` not wrapped in try/except. Trivial. | B.3 | 5 minutes |

### Bucket D — architectural gaps (Phase E)

| ID | Finding | Source | Phase E item |
|---|---|---|---|
| D-1 | No top-level orchestrator that consumes a region request and resolves which scripts to invoke with what args. Operators currently hand-compose the chain. Both B.1 and B.3 demonstrate the pattern: manifest preserves perfect provenance; orchestrator should consume that automatically. | B.1, B.3 | E.1 schema + E.3 runner |
| D-2 | Texture-pipeline operations are per-material commands. No "given biome kit + view mode, generate all 5 materials and deploy" wrapper. | B.2 | E.3 + E.5 |

---

## Fix sequencing (Phase D order)

Phase D ships in **6 steps**. Order is "smallest visible win first" so user
sees improvement immediately while infrastructure work continues underneath.

### D.0 — Phase D pre-work (15 min)
Before any code change, regenerate `data_catalog.json` against the 657
DEMs actually on disk (currently stale at 292 since 2026-05-09).

```bash
python pipelines/terrain/build_master_catalog.py
```

Atomic; verifiable; unblocks future M19 corpus statistics work. Commit
the result.

### D.1 — `build_macro()` parameter tune (BIGGEST VISIBLE WIN) (2-3 hours)
Fixes Bucket C-1. The "smooth tan/sand" complaint goes away.

**Approach** (iterate to find good values):
1. Regenerate procedural macro with detail strength bumped from 0.42 → 0.85
2. Visual review against catalog `desert_canyon_rock/albedo.png`
3. If still too smooth: reduce smooth-noise contribution (`value` formula on line 119)
4. If detail too repeating: shrink tile repeat_px in `tiled_detail()` call
5. Repeat M18 representative-slice render with new macro
6. Confirm broad-smooth-tan veto cleared

Specific code changes (sketch):
```python
# Current (line 121):
color += detail_signal * 0.42

# Try first:
color += detail_signal * 0.85

# If too much, also reduce smooth-noise dominance (line 119):
# Current: value = 0.88 + low * 0.12 + med * 0.055 + fine * 0.018
# Try:     value = 0.92 + low * 0.06 + med * 0.025 + fine * 0.009
```

Validation: re-render `gloss_procedural_canyon_rock_proof` + the M18
representative slice scene. The procedural side should now look like
canyon rock, not smooth tan.

**Important caveat**: this changes the byte-content of all downstream
procedural bundles. Existing M10/M17/M18 captures are no longer
reproducible from the new code. **Update affected manifests + capture
references in the same commit so the M13 promotion gate stays consistent.**

### D.2 — `res_path()` crash fix (5 min)
Fixes Bucket C-2.

```python
def res_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(ROOT.resolve())
        return "res://" + rel.as_posix()
    except ValueError:
        return str(path.resolve())
```

Bundle with D.1 commit or separate; either is fine.

### D.3 — Catalog auto-regen hook (15 min)
Bucket B foundational fix. Add post-hook to `bulk_pull.py` and
`pull_megastack_queue.py` that calls `build_master_catalog.py` after
pulls. Prevents the "365 DEMs stale" problem from recurring.

### D.4 — Texture pipeline preflight (1-2 hours)
Fixes Bucket B-2, B-4. New script:

```
pipelines/textures/preflight.py
```

Behaviors:
1. Check ComfyUI is reachable at `127.0.0.1:8188`; if not, error with
   clear "start ComfyUI" instructions including a sample command
2. Check required model files on disk
3. Check StableMaterials venv exists (`animators/mesa-env/venv`)
4. Exit 0 if all good; exit non-zero with specific message if not

Then `aaa_texture.py` calls `preflight.py` as its first step. Operators
get clear errors before any work runs.

### D.5 — Texture pipeline venv + doc cleanup (half-session)
Fixes Bucket B-1, B-3, B-5.

Options:
- (a) Create `pipelines/textures/.venv` with numpy + PIL + requests
  pinned, document it
- (b) Document explicitly that `aaa_texture.py` uses system Python 3.12
  + list required packages
- (c) Both — venv for isolation + doc for clarity

Recommend (b) for now, defer (a) until a real isolation conflict
surfaces. The script's deps are minimal (numpy + PIL + requests) and
already on system Python. The heavy lifting happens in ComfyUI and
mesa-env, both of which already have their own envs.

Specific docs to update:
- `pipelines/textures/aaa_texture.py` docstring (add "Python env:" section)
- `pipelines/textures/README.md` (probably doesn't exist; create)
- `pipelines/textures/preflight.py --help` should mention env

### D.6 — Phase D validation pass (1 session)
Re-run B.1, B.3 cold-runs to confirm fixes didn't break determinism on
unchanged chains. Run B.2 cold-run end-to-end now that B.2 prereqs are
documented. Update validation docs.

---

## Phase E sequencing (after Phase D)

### E.1 — Region request schema (1 session)
Build `region_request.json` declarative config schema. Use the patterns
from existing manifests (`meta.json`, `aaa_pipeline.json`,
`stack_manifest.json`) so the schema is rooted in reality, not invented.

Concrete deliverables:
- `world3/jobs/region_request_schema.json` — JSON Schema
- `world3/jobs/examples/gloss_real.json` — example real-source request
  matching the existing Gloss Mountain bundle
- `world3/jobs/examples/desert_canyon_procedural.json` — example
  procedural request matching the existing M10 neighbor bundle
- `world3/jobs/examples/gloss_canyon_hybrid.json` — example hybrid
  request matching the M10 seam-integration proof
- Schema validation test script

The three examples are important: they prove the schema can represent
every chain currently in use.

### E.2 — Stages manifest (1 session)
`stages.json` declaring every pipeline step with inputs/outputs/dependencies.

Use Phase A inventory as the source. Every script in:
- `pipelines/terrain/` (data acquisition stages)
- `pipelines/textures/` (texture generation stages)
- `world3/pipeline/` (build + audit stages)

...gets a stage entry. Stages tagged with:
- `id` (stable identifier)
- `script` (relative path)
- `inputs` (required args from request, derived deps)
- `outputs` (files produced)
- `required_if` (condition that triggers inclusion)
- `prerequisites` (external services like ComfyUI)

Deliverables:
- `world3/jobs/stages.json`
- `world3/pipeline/audit_stages.py` — validates every declared stage
  exists + can run `--help` successfully

### E.3 — Orchestrator runner (`world3_make.py`) (2 sessions)

```bash
python world3/pipeline/world3_make.py jobs/examples/gloss_real.json
```

Behavior:
1. Validate request against schema
2. Compute required stages via `stages.json` + request
3. Build dependency graph
4. Execute stages in topological order, capturing per-stage output
5. Update bundle directory progressively
6. Write `run.json` provenance
7. On failure: report exact stage + args + log; resume support

Flags:
- `--dry-run` — print stage chain without executing
- `--from-stage <id>` — resume partial runs
- `--only-stages <list>` — run subset (for testing)

Deliverables:
- `world3/pipeline/world3_make.py`
- `world3/pipeline/world3_run_provenance.py`
- `world3/jobs/run_records/` directory for `run.json` provenance

### E.4 — All-modes render driver (1-2 sessions)
Today: 100+ per-M Godot scenes. After E.4: one parameterized scene that
loads any bundle path + renders close/medium/iso/topdown.

Deliverables:
- `world3/scenes/review/orchestrator_capture_driver.tscn`
- `world3/scripts/OrchestratorCaptureDriver.gd`
- CLI invocation that the orchestrator can call

### E.5 — Style pack mechanism (1 session)
Formalize the photoreal/painterly/topographic style swap. Phase E
per-mode `.tres` is the foundation; style packs are the layer above.

Deliverables:
- `world3/jobs/style_packs/photoreal.json`
- `world3/jobs/style_packs/painterly.json` (optional first cut)
- `world3/jobs/style_packs/topographic.json`
- Loader logic in `OrchestratorCaptureDriver.gd`

### E.6 — Documentation + handoff (1 session)
- Rewrite `WORKFLOW.md` around the orchestrator
- Update `ROADMAP.md` to reflect orchestrator as completed
- Update `ORCHESTRATOR_HANDOFF` with one-command "make a region" example
- Operator guide: "I want a region — here's how"

### E.7 — Final validation + sign-off (1 session)
- Run the orchestrator end-to-end on each example request
- Verify outputs match what hand-composing the chains produced
- Generate a region we've never seen before (not Gloss / Tetons /
  Guadalupe) as the real test
- Commit, update gate state, write completion doc

---

## What gets validated when

| Phase | Validation step |
|---|---|
| D.0 | `data_catalog.json` reflects 657 DEMs |
| D.1 | Procedural macro no longer reads as smooth tan; M18 visual veto cleared |
| D.2 | `--out` outside world3 doesn't crash |
| D.3 | After a fresh pull, catalog regen runs automatically |
| D.4 | `preflight.py` reports specific errors for each missing prereq |
| D.5 | `aaa_texture.py --help` documents env requirements |
| D.6 | All Phase B cold-runs pass with new code |
| E.1 | Schema validates the 3 example requests |
| E.2 | `audit_stages.py` confirms every script exists |
| E.3 | Orchestrator reproduces existing bundles from example requests |
| E.4 | Orchestrator captures all 4 bands from one command |
| E.5 | Same bundle renders correctly under 2-3 style packs |
| E.6 | Cold-start agent can read docs + run a region |
| E.7 | Orchestrator generates a region we've never seen |

---

## Risk register

| Risk | Phase | Mitigation |
|---|---|---|
| D.1 macro tune breaks downstream captures | D | Update M10/M17/M18 evidence captures in same commit as code change; M13 gate manifest entries reflect new bundle hashes |
| D.4 preflight is too brittle (false positives) | D | Start with warnings, escalate to errors only after confidence |
| E.1 schema misses a knob | E | Validate against all 3 example requests; iterate before locking |
| E.2 stages manifest goes stale | E | E.3 audit checks every declared stage at orchestrator startup |
| E.3 orchestrator gets too complex | E | Resist temptation to add features; ship minimal viable, iterate |
| ComfyUI required for E.7 integration test | E | Operator-controlled; document the prereq clearly |

---

## Estimated effort

| Phase | Subtasks | Effort |
|---|---|---|
| D.0 | catalog regen | 15 min |
| D.1 | macro tune + downstream cap updates | 2-3 hours |
| D.2 | res_path crash fix | 5 min |
| D.3 | catalog auto-regen hook | 15 min |
| D.4 | preflight script | 1-2 hours |
| D.5 | venv + doc cleanup | half session |
| D.6 | validation pass | 1 session |
| **D total** | | **~3-4 sessions** |
| E.1 | region request schema + 3 examples | 1 session |
| E.2 | stages manifest + audit | 1 session |
| E.3 | orchestrator runner + provenance | 2 sessions |
| E.4 | all-modes render driver | 1-2 sessions |
| E.5 | style pack mechanism | 1 session |
| E.6 | docs + handoff | 1 session |
| E.7 | final validation | 1 session |
| **E total** | | **~7-9 sessions** |

**Total D + E**: ~10-13 sessions. Less than the 12-19 sessions estimated
in the rebuild plan, because Phase B confirmed less is broken than
feared.

---

## What gets sequenced first

If user approves Phase D, here's the exact order:

```
D.0  catalog regen                        (15 min, atomic)
D.2  res_path crash fix                   (5 min, trivial; bundle with D.0?)
D.1  build_macro() tune                   (2-3 hours, BIGGEST visible win)
D.3  catalog auto-regen hook              (15 min)
D.4  preflight script                     (1-2 hours)
D.5  venv + docs                          (half session)
D.6  Phase D validation                   (1 session)
```

**Big win lands at D.1.** Everything before is small infrastructure;
everything after is environment polish.

After D.6, Phase E starts with the schema + examples (E.1).

---

## Cross-references

- Phase A inventory: [`WORKFLOW_INVENTORY_2026_05_11.md`](WORKFLOW_INVENTORY_2026_05_11.md)
- Phase B.1: [`B1_CHAIN1_VALIDATION_2026_05_11.md`](B1_CHAIN1_VALIDATION_2026_05_11.md)
- Phase B.2: [`B2_CHAIN2_VALIDATION_2026_05_11.md`](B2_CHAIN2_VALIDATION_2026_05_11.md)
- Phase B.3: [`B3_CHAIN3_VALIDATION_2026_05_11.md`](B3_CHAIN3_VALIDATION_2026_05_11.md)
- Phase plan: [`REBUILD_PLAN_PHASES_B_E_2026_05_11.md`](REBUILD_PLAN_PHASES_B_E_2026_05_11.md)
- Bug location: `world3/pipeline/build_procedural_neighbor_bundle.py:52, 96-124`
- M13 gate: `world3/jobs/production_promotion_candidates.json`
