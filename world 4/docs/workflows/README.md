# W4 workflows

> Recipes for recurring tasks. Each doc walks through "what to do" with
> exact commands and expected output. If you find yourself doing the
> same thing twice, write a workflow doc and link it here.

## Workflows

| Workflow | When to use it |
|---|---|
| [`adding-a-feature.md`](adding-a-feature.md) | Adding any non-trivial feature (spec → plan → execute) |
| [`verifying-visual-change.md`](verifying-visual-change.md) | After any change that affects rendering — captures + editor verification |
| [`working-with-quality-tiers.md`](working-with-quality-tiers.md) | Consuming `QualityTiers` knobs in a new subsystem |
| [`debugging-terrain-artifacts.md`](debugging-terrain-artifacts.md) | When a visual bug appears — symptom → diagnosis → fix |

## Workflow conventions

- **One workflow per recurring task pattern.** Don't subdivide too early.
- **Exact commands always.** No "run the tests" without showing how.
- **Cross-link** instead of duplicating. If a workflow needs the orchestrator pipeline, link to `reference/ORCHESTRATOR_GUIDE.md`.
- **Update protocol**: when a workflow's steps drift from current practice (you found yourself doing the same thing but differently), update the doc in the same commit.

## Workflows queued (not yet written)

These are patterns we'd like to formalize but don't have enough repetitions yet:

- `adding-a-kernel.md` — Python impl + GDScript port + cross-impl test pattern. Will exist once we add the second kernel (erosion / DEM-patch / river-network — see `plans/AXIS1_PATH2_PLAN_2026_05_12.md` Stage 1+).
- `adding-a-biome.md` — Texture generation + catalog update + manifest rebuild. Today this lives across multiple build-notes; should be consolidated.
- `adding-a-world.md` — Bundle directory layout for `worlds/<name>/`. Currently 3 worlds (`anchor`, `scale_demo`, `scale_v2`) but each has a different layout; a future cleanup pass.
- `running-the-pipeline-on-a-new-dem.md` — DEM source → tile build → biome assignment. Currently covered by `reference/ORCHESTRATOR_GUIDE.md` but that doc predates the kernel system.
