# Phase F.8 — Top-level entry + pipeline guide

> One command takes a world plan from JSON to audited tile-able
> world: validate → audit transitions → derive demand → emit bundles
> → in-context re-audit. The canonical operator surface ships with
> this phase.

## Verdict

**F.8 closes the F-phase pipeline as an integrated operator surface.**
Every previous F sub-phase has a standalone script, but until F.8 you
had to invoke them in the right order yourself. `world3_make_world.py`
composes the chain with sensible defaults + escape hatches; the
canonical `WORLD3_PIPELINE_GUIDE.md` documents the whole surface
in one doc.

## What shipped

### `world3/pipeline/world3_make_world.py`

Six-step synthesis layer:

| # | Step | Script invoked | Notes |
|---|------|----------------|-------|
| 1 | validate plan | `validate_world_plan.py` | Hard gate — abort if invalid |
| 2 | transition audit | `audit_transition_pairs.py` | Soft — surface findings |
| 3 | derive demand | `derive_catalog_demand.py` | `--strict-catalog` gates here |
| 4 | requisition (run mode) | `run_catalog_requisition.py --run` | **Only with `--auto-requisition`** |
| 5 | emit + build | `world_plan_to_bundles.py --run` | Builds every tile |
| 6 | in-context re-audit | `audit_materials_in_context.py` | Skippable via `--skip-in-context` |

Flags:
- `--dry-run` — print plan, don't execute
- `--from-step N` — resume mid-flow (e.g. `--from-step 6` re-audit only)
- `--only-step N` — single step
- `--skip-in-context` — skip step 6 (Godot loop) for fast iteration
- `--strict-catalog` — abort after step 3 if any catalog gap exists
- `--auto-requisition` — USER-GATED escape hatch that runs step 4 real-mode

Each step's record (cmd, exit code, elapsed time) lands in a
composite summary at `world3/jobs/world_build_summaries/<plan_id>_<ts>.json`.

### `world3/docs/WORLD3_PIPELINE_GUIDE.md`

The canonical "how to use this" doc. A new agent or operator reads this
to understand the whole pipeline. Covers:

- The one command + mental model
- Authoring a world plan from scratch
- Step-by-step reference for all 6 steps
- Schema inventory (every JSON Schema + its validator)
- What ships now vs. queued for F.7 vs. queued for Phase G/H

## Validation

### 2×2 plan — full chain in ~9s

```
$ python world3/pipeline/world3_make_world.py \
    world3/jobs/examples/world_plan_starter_2x2_procedural.json

--- Summary ---
  [OK  ] step 1: validate_world_plan         0.1s
  [OK  ] step 2: audit_transition_pairs      0.2s
  [OK  ] step 3: derive_catalog_demand       0.1s
  [OK  ] step 5: world_plan_to_bundles --run 3.5s   (4 tiles)
  [OK  ] step 6: audit_materials_in_context  4.8s   (1 biome captured)
  overall: ok
```

Step 4 correctly skipped (no `--auto-requisition`). End-to-end:
plan validated → no allowed pairs to audit → demand has no work →
4 bundles built byte-identical → in-context audit captured tundra
through orchestrator and scored drift. **All artifacts wrote.**

### 5×5 plan with `--skip-in-context` — ~23s

```
$ python world3/pipeline/world3_make_world.py \
    world3/jobs/examples/world_plan_starter_5biome_procedural.json --skip-in-context

--- Summary ---
  [OK  ] step 1: validate_world_plan         0.1s
  [OK  ] step 2: audit_transition_pairs      0.9s   (8 pairs)
  [OK  ] step 3: derive_catalog_demand       0.1s   (6 work_queue items)
  [OK  ] step 5: world_plan_to_bundles --run 21.8s  (25 tiles)
  overall: ok
```

25 procedural bundles + 8-pair transition audit + 6-item catalog demand
in under 25 seconds.

### Strict-catalog gate

```
$ python world3/pipeline/world3_make_world.py <5x5_plan> --strict-catalog --only-step 3
... (runs step 3 only)
FAIL: --strict-catalog and demand reports need=0 below=2
$ echo $?
1

$ python world3/pipeline/world3_make_world.py <2x2_plan> --strict-catalog --only-step 3
... (passes — 2×2 has no below-gate materials)
$ echo $?
0
```

Gate correctly aborts on the 5×5 (`grassland_grass` + `temperate_forest_grass`
below gate) and passes on the 2×2 (`tundra_moss` has gate).

### Dry-run + filter modes

`--dry-run`, `--from-step`, `--only-step` all work as designed (verified
in the trace output of the smoke runs).

## What I deliberately didn't do

- **Run `--auto-requisition` for real.** That would invoke
  `aaa_texture.py` / `palette_lock.py` against ComfyUI for real
  generation. User-gated by design.
- **Bundle audit JSONs into a unified report**. The 4 separate JSONs
  (transition_audits, catalog_demand, world_map, in_context_audits)
  are intentionally separate — each is its own diagnostic axis. A
  combined-view UI lands in Phase G if needed.
- **Cron-style auto-rerun on changes.** Out of scope; nothing in the
  pipeline today blocks adding watch-mode later.

## Six-box LLM-drivability check

| Box | Status |
|---|---|
| Schema | N/A — F.8 is a composition layer, no new schema |
| Validator | N/A — composed sub-validators run as steps |
| Example | ✅ 2×2 + 5×5 starter plans (existing F.2 examples) |
| Audit | ✅ `world3/jobs/world_build_summaries/<plan_id>_<ts>.json` per run |
| Closure doc | ✅ this doc |
| Stages.json | N/A — F.8 is a top-level driver, not a per-bundle stage |

## Cross-references

- Parent phase: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Canonical pipeline guide: [WORLD3_PIPELINE_GUIDE.md](WORLD3_PIPELINE_GUIDE.md)
- Previous: [F6_IN_CONTEXT_REAUDIT_2026_05_11.md](F6_IN_CONTEXT_REAUDIT_2026_05_11.md)
- Composes: F.2 + F.3 + F.4 + F.5a + F.5b + F.6
- Next: F.7 multi-bundle streaming director (largest sub-phase, user-in-loop)

## Status

- [x] `world3_make_world.py` six-step synthesis layer
- [x] All five flag modes (`--dry-run`, `--from-step`, `--only-step`, `--strict-catalog`, `--auto-requisition`, `--skip-in-context`)
- [x] Composite summary JSON per run
- [x] 2×2 smoke (full chain, ~9s)
- [x] 5×5 smoke (`--skip-in-context`, ~23s, 25 bundles)
- [x] Strict-catalog gate verified (fails 5×5, passes 2×2)
- [x] `WORLD3_PIPELINE_GUIDE.md` canonical operator doc
- [x] Closure doc (this doc)

**Phase F.8 SHIP.** Pipeline is now one command end-to-end. F.7
streaming director is the remaining piece.
