# Phase F.5 — Catalog requisition (demand + runner)

> Given a world plan, derive which materials it needs that the catalog
> doesn't have at acceptable gate state, and dispatch the texture
> pipeline to close those gaps. F.5a derives demand; F.5b runs it.
> Runner is dry-run by default so an LLM can drive it without burning
> ComfyUI cycles unsupervised — `--run` is user-gated.

## Verdict

**F.5 ships the catalog-demand pipeline.** The user-stated north star
("we get our textures that we like made and audited, then they get
ran through the seam thingys") now has a real machinery for *deciding
what to make*. F.5a reads a plan + the F.4 audit and produces a
prioritized work queue. F.5b takes the queue and dispatches commands
to the right driver. Real generation runs on `--run`; default is
preview-only.

## What shipped

### F.5a — Demand deriver

**`world3/pipeline/derive_catalog_demand.py`** — argparse CLI taking
a plan. Walks the plan to find every referenced material
(`primary_material_id`, `source.material_id`, per-tile
`source_override.material_id`). For each:

- **have**: in catalog AND `provenance.passed_gate=true`
- **need**: not in catalog at all
- **below_promotion_bar**: in catalog but `passed_gate=false`, OR on
  disk but no catalog entry

Then reads `world3/jobs/transition_audits/<plan_id>.json` (F.4 audit)
if present and consumes failing/warning pair verdicts to drive
additional work_queue entries.

Output: `world3/jobs/catalog_demand/<plan_id>.json` with `have`,
`need`, `below_promotion_bar`, `transition_audit` summary, and the
prioritized `work_queue`.

Work queue prioritization (lower number = higher priority):

| Priority | Action | Reason |
|---|---|---|
| -1 | `fix_catalog` | material missing entirely — must be generated before plan works |
| 0 | `palette_lock` | cross-material palette work (cheapest fix for failing transition pairs) |
| 1 | `regenerate` | rebuild material (luminance/frequency mismatch) |
| 2 | `shader_blend_band` | runtime mitigation — NOT queued (surfaced but skipped) |

`shader_blend_band` items appear in F.4 audit results but the
deriver explicitly excludes them from the catalog work queue
(they are G.3 / G.5 shader work, not catalog work).

### F.5b — Requisition runner

**`world3/pipeline/run_catalog_requisition.py`** — argparse CLI taking
a demand JSON. For each work_queue item, builds the matching command:

| Action | Driver |
|---|---|
| `regenerate` / `fix_catalog` | `pipelines/textures/aaa_texture.py` with prompt + seed from catalog provenance |
| `palette_lock` | `pipelines/textures/palette_lock.py --kit <pair_name> --anchor <material>` |
| `shader_blend_band` | no-op (skipped with reason logged) |

**Default mode is DRY-RUN.** Pass `--run` to actually execute
subprocesses. This is intentional — F.5b is the LLM-drivable harness;
real catalog requisition is user-gated because ComfyUI runs can be
expensive.

Flags:
- `--run` — execute dispatched commands; without it, only previews
- `--only-action <id>` — filter to one action class
- `--max-items N` — cap dispatched items (smoke check)

Run records land in `world3/jobs/catalog_requisition_records/<plan_id>_<ts>.json`
with cmd, exit code, elapsed time, stdout/stderr tails per item.

## Validation

### F.5a on 5×5 starter plan

```
$ python world3/pipeline/derive_catalog_demand.py \
    world3/jobs/examples/world_plan_starter_5biome_procedural.json

Catalog: 31 materials total
Plan references: 5 unique materials across 5 biome bindings

--- Buckets ---
  have  (3): ['desert_canyon_rock', 'rock_dark', 'tundra_moss']
  need  (0): []
  below (2): ['grassland_grass', 'temperate_forest_grass']

--- Work queue (6 items) ---
  [palette_lock      ] desert_canyon_rock      [pair ['alpine', 'desert']]
  [palette_lock      ] rock_dark               [pair ['alpine', 'desert']]
  [regenerate        ] grassland_grass
  [regenerate        ] rock_dark               [pair ['tundra', 'alpine']]
  [regenerate        ] temperate_forest_grass
  [regenerate        ] tundra_moss             [pair ['tundra', 'alpine']]

  transition audit: pass=0 warn=1 fail=7
```

Findings:
- 3 / 5 plan materials clear gate (`have`)
- 2 are below gate (`grassland_grass`, `temperate_forest_grass` — the catalog flagged these `passed_gate=false`)
- Work queue prioritizes palette_lock (cheap fix for alpine-desert warn) before regenerate
- F.4's 3 `shader_blend_band` fails correctly excluded from catalog work queue
- Dedupe collapses redundant (material, action) pairs

### F.5a on 2×2 (single biome, no transition pairs)

```
  have  (1): ['tundra_moss']
  need  (0): []
  below (0): []
  Work queue (0 items) ---
  transition audit: pass=0 warn=0 fail=0
```

Correct no-op.

### F.5b dry-run on 5×5 demand

```
$ python world3/pipeline/run_catalog_requisition.py \
    world3/jobs/catalog_demand/starter_5biome_procedural.json

Mode: DRY-RUN (not executing)

  [plan ] palette_lock       desert_canyon_rock
           cmd: python pipelines/textures/palette_lock.py --kit alpine_desert --anchor desert_canyon_rock
  [plan ] palette_lock       rock_dark
           cmd: python pipelines/textures/palette_lock.py --kit alpine_desert --anchor rock_dark
  [plan ] regenerate         grassland_grass
           cmd: python pipelines/textures/aaa_texture.py --prompt 'tall savanna grass, golden-yellow, ...' --id grassland_grass --category Ground --quality default --seed 42
  [plan ] regenerate         rock_dark
           cmd: python pipelines/textures/aaa_texture.py --prompt 'dark grey volcanic rock surface, ...' --id rock_dark --category Ground --quality default --seed 42
  ... (4 more)

  dispatched: 6
  record:     world3\jobs\catalog_requisition_records\starter_5biome_procedural_20260511T144901Z.json
```

All commands include the original prompt + seed pulled from
`catalog.json` → `provenance.prompt` / `seed_base`. An LLM reviewing
the dry-run output sees exactly what would be generated.

### Filter test

```
$ python world3/pipeline/run_catalog_requisition.py <demand> --only-action palette_lock
  dispatched: 2  (only palette_lock items)
```

## Six-box LLM-drivability check

| Box | F.5a | F.5b |
|---|---|---|
| Schema | ⚠️ Implicit in script (output JSON shape) — deferred per F.4 precedent | Same — implicit in record JSON |
| Validator | N/A — derives from validated plan + validated audit | N/A — driver |
| Example | ✅ `world3/jobs/catalog_demand/starter_5biome_procedural.json` + 2x2 | ✅ `world3/jobs/catalog_requisition_records/starter_5biome_procedural_*.json` |
| Audit | ✅ deriver IS the audit | ✅ run records are the audit |
| Closure doc | ✅ this doc | ✅ this doc |
| Stages.json | N/A — these are world-plan-level tools | N/A |

Schema formalization is deferred as in F.4 (one consumer = ad-hoc OK).

## What's NOT in F.5

- **Real-run smoke.** F.5b has never executed `aaa_texture.py` or
  `palette_lock.py` in this session — only dry-run dispatched.
  When the user is ready to do a catalog remediation pass, run
  `--run --max-items 1` first as a sanity check.
- **Kit-aware palette_lock orchestration.** `palette_lock.py` operates
  on a kit (multiple materials). F.5b builds a per-pair kit name
  (`<biome_a>_<biome_b>`) and passes one anchor per command — this
  is a serviceable approximation but real palette_lock typically
  wants a multi-material kit definition. Refine when running first
  real palette_lock; defer until a real run gives feedback.
- **Per-mode quality bar awareness.** F.5a checks bundle-wide
  `passed_gate`. Per-mode gate (walk/iso/topdown) lands in G.5,
  at which point F.5a can recompute demand against the finer-grained
  state.
- **Texture pipeline status query.** F.5b doesn't ask
  `pipelines/textures/preflight.py` whether ComfyUI is up before
  dispatching. Worth wiring into `--run` before any real
  catalog remediation pass; deferred until F.5b runs for real.
- **Stages.json wiring.** F.5 is plan-level work, not per-bundle
  stage work — same reasoning as F.3 / F.4. Top-level entry point
  in F.8 will compose F.4 → F.5a → F.5b → F.3 → F.6 as a single
  command.

## Cross-references

- Parent phase: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Previous: [F4_TRANSITION_PAIR_AUDIT_2026_05_11.md](F4_TRANSITION_PAIR_AUDIT_2026_05_11.md)
- Reads: world plan, `world3/materials/catalog.json`, `world3/jobs/transition_audits/<plan_id>.json`
- Emits: `world3/jobs/catalog_demand/<plan_id>.json`, `world3/jobs/catalog_requisition_records/<plan_id>_<ts>.json`
- Drives: `pipelines/textures/aaa_texture.py`, `pipelines/textures/palette_lock.py`

## Status

- [x] `derive_catalog_demand.py` (F.5a)
- [x] `run_catalog_requisition.py` (F.5b)
- [x] Dry-run smoke on 5×5 + 2×2 plans
- [x] Filter (`--only-action`) + cap (`--max-items`) flags
- [x] Run records written under `world3/jobs/catalog_requisition_records/`
- [x] F.4 audit consumption (failing pairs drive work queue)
- [x] Closure doc (this doc)

**Phase F.5 SHIP.** Catalog demand machinery live; real generation
pass is a user-gated `--run` away.
