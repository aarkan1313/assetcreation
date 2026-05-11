# Phase F — Pipeline buildout (post-rebuild)

> Phase B-E ended with a working procedural-only orchestrator. Phase F
> turns that into a real world-generation pipeline: plan-driven catalog
> requisition, catalog-time transition audit, multi-bundle streaming
> director, and the connective tissue that lets one config produce a
> tile-able, walkable, ~5 km world. Pipelines first, content later.

## Operating principles for this phase

1. **Pipelines, not content.** Every step in F lands as a script or
   schema, never as authored art. We are building the machine; making
   things with the machine is a separate later phase.
2. **Five biomes, not the full catalog.** Starter set sized so one
   person can keep it in their head while we prove the spine works.
3. **Scale is the perennial enemy.** Every artifact carries explicit
   world-size + zoom-range fields; every script checks them; no script
   silently assumes a unit system. (User flag 2026-05-11: scale has
   broken every prior project.)
4. **Catalog quality is gate-state, not vibes.** Materials advance
   through M13 gate states. Plans can only use materials at
   `production_candidate` or higher.
5. **Transition quality lives at catalog time, not at runtime.** If
   two materials can't blend cleanly side-by-side, the catalog refuses
   to let them neighbor in a plan.
6. **LLM-drivability is a feature.** Every step has a JSON schema +
   validator + scriptable audit. An LLM with file access should be
   able to author and run each step without human intervention.

## The user-target this phase serves

From the 2026-05-11 conversation, exact target:

> We decide the world we want, biomes we want, what decorations we want,
> make a plan, create and audit the textures we will want, use the DEMs,
> photoreal stuff, run some scripts, have an infinite, tiled and good
> looking world, handcrafting is then done for special zones biomes,
> ideally with as minimal friction as possible.

Clarifications captured the same session:

- **"Infinite"** = ever-changing ~5 km playable area (size varies by
  resolution/perspective). Streaming director loads chunks ahead of
  travel, drops chunks behind, no permanent loaded state, preload
  buffer at game start.
- **Scale is hard.** Every prior project broke on scale; phase F bakes
  scale awareness into every layer.
- **Five biomes for starter.** Catalog grows later; pipeline ships at five.
- **Shader leverage is intentional.** Horizon Zero Dawn pattern referenced:
  one 512×512 dirt texture + shader machinery makes it look great.
  Per-biome material count is intentionally low-ish; shader detail does
  the rest.

## Phase F sequencing

Eight sub-phases, sized for one focused session each (F.5 is two, F.7 is the largest).

### F.1 — Close E-phase orchestrator gaps

**Goal:** Phase B-E ended with 3 placeholder stages and a real-DEM lane
that's never been run end-to-end through the orchestrator. Close those
before adding new layers on top.

**Scope:**
- Wire `build_seam_integration` stage's arg mapping (today validates
  schema but skips at runtime for hybrid requests)
- Wire `build_runtime_image_cache` stage's arg mapping
- End-to-end smoke test: run `world3_make.py` on `gloss_real.json`
  through the full real-DEM chain, verify byte-identical reproduction
- End-to-end hybrid smoke test on `gloss_canyon_hybrid.json`

**Exit:** All four example requests produce bundles via `world3_make.py`
without manual intervention. Run records in `world3/jobs/run_records/`
prove green-on-three-classes (procedural, real, hybrid).

**Why first:** F builds on the orchestrator. Leaving the orchestrator
with placeholder stages means F.2-F.7 hit them as latent bugs later.

### F.2 — World plan schema

**Goal:** A `world_plan.json` schema that owns "I want a world" intent,
independent of which bundles get built to satisfy it.

**Scope:**
- `world3/jobs/world_plan_schema.json` — JSON Schema 2020-12
- Fields:
  - `bounds`: world size in meters (e.g. 5000×5000)
  - `tile_size_m`: bundle grid resolution (decision: 256m starter)
  - `biomes`: array of biome ids drawn from the 5-biome starter set
  - `biome_layout`: how biomes are placed across the bounds
    (initially: explicit per-tile assignment; later: noise-driven)
  - `adjacency_rules`: which biome-pairs are allowed to neighbor
    (drives F.4 transition audit)
  - `perspectives`: which view modes the plan needs to support
    (walk / iso / topdown — drives capture stage selection)
  - `zoom_levels`: which zoom bands the plan needs (TBD, leave as
    array so F.6 can land non-breakingly)
  - `sources`: per-tile or per-biome data source (procedural / real-DEM
    region / hybrid — drives F.5 requisition)
- `world3/jobs/examples/world_plan_*.json` — at least 2 examples:
  - `world_plan_starter_5biome_procedural.json` — pure-procedural
    starter; smallest possible world that exercises every layer
  - `world_plan_starter_5biome_hybrid.json` — same biomes but with
    one real-DEM-source tile to prove the hybrid path
- `world3/pipeline/validate_world_plan.py` — validator with self-test

**Exit:** Both example plans validate clean. Schema rejects malformed
plans with line-level error messages.

**Why second:** Everything below F.2 reads from a world plan. Without
the schema, F.3+ would be designed against an implicit data shape.

### F.3 — Plan-to-bundle iterator

**Goal:** Convert a world plan into N region requests + a manifest of
how those bundles tile together (the seed of the streaming director's
world map).

**Scope:**
- `world3/pipeline/world_plan_to_bundles.py` — reads a world plan,
  emits one `region_request.json` per tile + a `world_map.json`:
  ```json
  {
    "world_id": "...",
    "bounds_m": [5000, 5000],
    "tile_size_m": 256,
    "tiles": [
      {"tile_xy": [0, 0], "world_xy_m": [0, 0],     "bundle_id": "...", "request_path": "..."},
      {"tile_xy": [0, 1], "world_xy_m": [0, 256],   "bundle_id": "...", "request_path": "..."},
      ...
    ]
  }
  ```
- Run the orchestrator over every emitted request via a batch wrapper
- World map written to `world3/worlds/<world_id>/world_map.json`

**Exit:** Running the iterator on the procedural starter plan produces
N bundles + a world map. Re-running is byte-identical (deterministic
seed derivation per tile from plan seed + tile xy).

**Why now:** This is where "one config → many bundles" becomes real.
Catalog requisition (F.5) needs the bundle set to know what materials
are demanded.

### F.4 — Catalog-time transition pair audit

**Goal:** Given a world plan's adjacency rules, audit *every allowed
biome-pair* for blend-quality at catalog time. Refuse to ship a plan
whose textures don't blend cleanly.

**Scope:**
- `world3/pipeline/audit_transition_pairs.py` — for each allowed
  adjacency pair in the plan:
  1. Load each biome's primary albedo from the catalog
  2. Run the existing seam-solver math (`build_terrain_seam_integration_proof.py`'s
     blend logic) on the two tiled albedos at standard band size
  3. Score: color delta across band, palette compatibility (CIE Lab
     distance), value-range mismatch, texture-frequency mismatch
- Output: `world3/jobs/transition_audit_<plan_id>.json` with per-pair
  scores + pass/fail against thresholds
- Failing pairs get either:
  - `recommended_action: "palette_lock"` — needs cross-material palette
    work via `pipelines/textures/palette_lock.py`
  - `recommended_action: "regenerate"` — material itself is the problem
  - `recommended_action: "shader_blend_band"` — runtime-mitigatable
- `world3/pipeline/world_plan_to_bundles.py` (F.3) reads the transition
  audit and refuses to emit bundles if any pair is failing

**Exit:** Audit runs over the starter plan in <30s. Produces a JSON
verdict per pair. Plans with failing pairs are blocked from F.3
unless `--force` is passed.

**Why now:** Catches catalog gaps *before* spending compute on N bundles
that will reveal the same gap N times in F.7 streaming.

### F.5 — Catalog requisition

**Goal:** Given a world plan + the current catalog state, derive
"which materials does this plan need that we don't have," and drive
the texture pipeline to generate them.

**Two sessions, in order:**

**F.5a — Demand deriver (1 session)**
- `world3/pipeline/derive_catalog_demand.py` — reads a plan, computes
  required material set (biomes × slot count per biome), checks the
  existing catalog (`world/textures/catalog/materials.jsonl`), emits
  a demand manifest:
  ```json
  {
    "plan_id": "...",
    "have": ["tundra_moss", "desert_canyon_rock", ...],
    "need": [{"id": "tundra_lichen_v2", "biome": "tundra", "slot": "secondary", "prompt_brief": "..."}, ...],
    "below_promotion_bar": ["...materials present but not at production_candidate..."]
  }
  ```
- Output drives the next step

**F.5b — Requisition runner (1 session)**
- `world3/pipeline/run_catalog_requisition.py` — reads the demand
  manifest, drives `pipelines/textures/aaa_texture.py` (or
  `palette_lock.py` for kit-coherent batches) for each needed
  material, advances M13 gate state as each lands
- Idempotent: re-running picks up where it left off

**Exit:** Running F.5 on a plan that has gaps produces those materials
without manual `aaa_texture.py` invocations. Running on a plan with
no gaps is a no-op.

**Why now:** Closes the loop from intent ("I want these biomes") to
catalog ("we have everything needed"). Without F.5 the user still
hand-drives texture authoring from doc-time decisions.

### F.6 — In-context re-audit

**Goal:** Once bundles exist, render each material in N biome-adjacent
contexts and score whether it still holds up under shader/lighting/blend.
Catches issues catalog-stage couldn't see.

**Scope:**
- `world3/pipeline/audit_materials_in_context.py` — for each material
  in the plan, capture it in:
  - Its own bundle's iso view (baseline)
  - Each adjacent biome's seam-band iso view (transition test)
- Scoring via OCR/structural metric on the captures + manual review
  flag
- Advances M13 gate state from `production_candidate` → `production_promoted`
  when in-context passes

**Exit:** Running F.6 over the starter world produces a per-material
verdict. Materials that fail in-context get demoted with a note
explaining why.

**Why now:** Lat last check before runtime. After F.6 we know the
catalog tiles cleanly *under shader+lighting*, not just on the static
seam-band metric.

### F.7 — Multi-bundle streaming director

**Goal:** ChunkLoader serves the right bundle's chunks for the player's
current world position, preloads ahead of travel direction, drops
behind. The actual "infinite tiled world" engine piece.

**Largest sub-phase. Estimate 4-6 sessions.** Split into clear
sub-deliverables:

**F.7a — World map → chunk service**
- `WorldMapService.gd` — reads `world_map.json`, maps `world_xy_m`
  → `(bundle_id, tile_xy)`, exposes "give me the bundle covering
  player position" API
- Unit-testable via simple GDScript scenes; no streaming involved yet

**F.7b — Cross-bundle ChunkLoader**
- ChunkLoader queries WorldMapService instead of hardcoding bundle
  paths
- Cross-bundle chunk handoff at bundle borders — uses the catalog-time
  audited seam math to blend
- Preserves single-bundle behavior when there's only one tile

**F.7c — Direction-aware preload**
- ChunkLoader observes player velocity, prefetches chunks ahead of
  travel direction, evicts chunks behind a configurable distance
- Preload buffer of N chunks initialized at game start

**F.7d — Real-world smoke**
- Walk a player across the 5-biome starter world, all four corners,
  capture before/during/after seams
- Verify no visual pops at bundle boundaries
- Verify memory stays bounded (no leak on prolonged streaming)

**Exit:** Player walks the starter world end-to-end, all seams clean,
memory bounded.

**Why last:** Everything above feeds this. Without F.1-F.6 the
streaming director would expose every catalog/transition gap as a
runtime artifact instead of catching them at build time.

### F.8 — Connective tissue

**Goal:** Land the workflow doc + handoff + LLM-drivability checklist
so the system is usable end-to-end without reading 8 closure docs.

**Scope:**
- `WORLD3_PIPELINE_GUIDE.md` — one canonical doc covering Phase F end-to-end
- Update `ORCHESTRATOR_HANDOFF` for the new shape
- LLM driveability checklist: every step has a JSON schema + validator
  + scriptable audit + closure doc
- `world3_make_world.py` — top-level entry point that takes a world
  plan and runs F.3 → F.4 → F.5 → F.6 (capture optional). One command
  end-to-end.

**Exit:** A fresh agent can read `WORLD3_PIPELINE_GUIDE.md` + the
schemas and produce a world from one command.

## Cross-cutting concerns

### Scale discipline

Every artifact in F carries explicit:
- `world_size_x_m` / `world_size_z_m` (no implicit "the bundle is 240m wide")
- `elevation_range_m` (no implicit altitude scale)
- `tile_size_m` at world-plan level (no implicit bundle-grid cell)
- `zoom_level_m` for any zoom-aware capture (no implicit camera distance)

Every script:
- Validates these on input, refuses to proceed if missing
- Emits these on output, never leaves consumers guessing
- Logs the actual values it used in run records

This is the single rule that addresses the user's flagged "scale has
broken every prior project."

### Catalog gate integration

M13 gate states are the authority for "is this material allowed in
a world plan." Plans can only reference materials at
`production_candidate` or higher. F.4 advances or demotes states based
on transition-pair results; F.6 advances or demotes based on in-context
results. M13 gate is sacred (per `ORCHESTRATOR_HANDOFF`); F respects it.

### Five-biome starter

Lock the starter at 5 biomes so the pipeline is provable without
catalog-scale work. Recommended starter (subject to user override):

1. **alpine** — has the most complete .tres set, well-tested
2. **desert** — has the most catalog materials including the M10
   procedural validation material
3. **tundra** — exercised by E.7
4. **grassland** — has palette-locked kit
5. **temperate_forest** — has palette-locked kit

These five cover the existing per-mode .tres infrastructure without
needing new deploy work. Other biomes (boreal, mangrove, etc.) are
queued for catalog-expansion later.

### LLM-drivability **hard gate**

Every Phase F sub-phase ships ONLY when **all six** boxes are checked.
This is a hard gate, not a recommendation. A sub-phase with five
checked boxes is not done.

- [ ] **JSON schema** with `$id`, types, descriptions — under `world3/jobs/` or `world3/schemas/`
- [ ] **Validator script** with `--schema-self-test` mode — under `world3/pipeline/validate_*.py`
- [ ] **At least 1 example file** under `world3/jobs/examples/` that validates clean
- [ ] **Closure doc** following the `<phase_id>_<topic>_<date>.md` pattern under `world3/docs/`
- [ ] **Stage entry in `stages.json`** if it's pipeline work that the orchestrator should drive
- [ ] **Audit script** under `world3/pipeline/audit_*.py` — `--help` clean and reports JSON with `--json`

Sub-phases that are pure infra (e.g. F.7a WorldMapService.gd) substitute
"unit test scene + smoke harness" for "schema + validator," but the
hard gate still applies to the six-box equivalent.

**Why hard, not soft:** Phase E.1-E.7 worked because every sub-phase
hit this bar. Phase E.5 was the weakest link (style pack lacked a
real validator + audit script), and that's already showing up as
friction. Phase F doesn't have the budget to repeat that mistake six
more times.

**Backfill obligation:** Style pack validator + audit script and
explicit capture-request schema doc land before F.1 starts. See
[E8_ORCHESTRATION_DEBT_BACKFILL_2026_05_11.md](E8_ORCHESTRATION_DEBT_BACKFILL_2026_05_11.md)
for the backfill closure.

## Pinned decisions from 2026-05-11 conversation

| Question | Decision |
|---|---|
| How big is "infinite"? | Ever-changing ~5 km area, sized per resolution/perspective. Streaming director loads ahead, drops behind, preload buffer. |
| Bundle/tile size? | **256 m starter.** Reusable for 3D/2.5D walk; topdown may want larger. Single value at plan level for now; can multi-scale later. |
| How many biomes at start? | **Five.** alpine, desert, tundra, grassland, temperate_forest. |
| Catalog quality bar for plan inclusion? | **`production_candidate` minimum.** F.4 transition audit + F.6 in-context audit drive promotion to `production_promoted`. |
| How many textures per biome? | Open. Shader leverage (Horizon Zero Dawn pattern) intentional. Per-biome material count: start with what we have; grow only when F.4 or F.6 says we need to. |
| Zoom levels per perspective? | TBD. F.2 schema reserves the field; F.6 wires the audit; full LOD work deferred until streaming works. |
| Real-DEM vs procedural mix? | Starter plan has both (procedural for the biome interiors, real-DEM as a hand-picked patch). |

## Out of scope for Phase F

- Authored art / hand-tuned biome content (post-F work)
- Game logic, UI, audio (consumer-side, not pipeline)
- LOD/impostor work beyond a placeholder zoom field (M16 territory)
- Procedural visual quality improvements beyond what D.1 fixed (M19+ territory)
- A specific game built on this pipeline (separate consumer)

## Status

- [x] F.1 — Close orchestrator gaps (seam integration + runtime cache + real-DEM smoke + hybrid smoke) — [F1_ORCHESTRATOR_GAPS_CLOSED_2026_05_11.md](F1_ORCHESTRATOR_GAPS_CLOSED_2026_05_11.md)
- [x] F.2 — World plan schema + 2 example plans + validator — [F2_WORLD_PLAN_SCHEMA_2026_05_11.md](F2_WORLD_PLAN_SCHEMA_2026_05_11.md)
- [x] F.3 — Plan-to-bundle iterator + world map output — [F3_PLAN_TO_BUNDLES_ITERATOR_2026_05_11.md](F3_PLAN_TO_BUNDLES_ITERATOR_2026_05_11.md)
- [x] F.4 — Catalog-time transition pair audit — [F4_TRANSITION_PAIR_AUDIT_2026_05_11.md](F4_TRANSITION_PAIR_AUDIT_2026_05_11.md)
- [x] F.5a — Catalog demand deriver — [F5_CATALOG_REQUISITION_2026_05_11.md](F5_CATALOG_REQUISITION_2026_05_11.md)
- [x] F.5b — Requisition runner (harness; real-run user-gated) — [F5_CATALOG_REQUISITION_2026_05_11.md](F5_CATALOG_REQUISITION_2026_05_11.md)
- [x] F.6 — In-context material re-audit — [F6_IN_CONTEXT_REAUDIT_2026_05_11.md](F6_IN_CONTEXT_REAUDIT_2026_05_11.md)
- [x] F.7a — WorldMapService.gd — [F7_MULTI_BUNDLE_STREAMER_2026_05_11.md](F7_MULTI_BUNDLE_STREAMER_2026_05_11.md)
- [x] F.7b — Cross-bundle ChunkLoader (MultiBundleStreamer.gd)
- [x] F.7c — Direction-aware preload
- [ ] F.7d — Real-world walk smoke (blocked on F.3.1 contiguity)
- [x] **F.3.1** — Edge-constraint plan iterator + procedural builder — [F31_EDGE_CONSTRAINT_CONTIGUITY_2026_05_11.md](F31_EDGE_CONSTRAINT_CONTIGUITY_2026_05_11.md)
- [x] **F.3.4** — M11 bundle library refactor (builder converged on M11 emit shape) — [F34_M11_LIB_REFACTOR_2026_05_11.md](F34_M11_LIB_REFACTOR_2026_05_11.md)
- [x] **F.3.5** — M11 parity refactor (fourway support in lib + CLI driver; ~70% visual parity, architecture converged) — [F35_M11_PARITY_REFACTOR_2026_05_11.md](F35_M11_PARITY_REFACTOR_2026_05_11.md)
- [ ] **F.3.6** — final visual tuning + 5-biome rebuild through new pipeline + multi-domain boundary tiles + F.7 revalidation
- [x] F.8 — Pipeline guide + top-level entry point — [F8_TOP_LEVEL_ENTRY_2026_05_11.md](F8_TOP_LEVEL_ENTRY_2026_05_11.md) + [WORLD3_PIPELINE_GUIDE.md](WORLD3_PIPELINE_GUIDE.md)

## What ships at end of Phase F

```
python world3/pipeline/world3_make_world.py world3/jobs/examples/world_plan_starter_5biome_procedural.json
```

Produces a ~5 km, 5-biome, tile-able world the player can walk across,
with the catalog audited at build-time for transition quality and
again at runtime in-context, all driven from one JSON config, all
deterministic, all reproducible.

That's the pipeline. Content is what comes after — and content built
on a real pipeline is much easier than content built on a script-soup.

**Phase F charter SHIPPED 2026-05-11.** Implementation begins at F.1.
