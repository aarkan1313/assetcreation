# F.3.5 Handoff Prompt — Fresh Project Owner Takeover

> **Read this first.** You are taking over the world3 project mid-flow.
> This doc is the entire context dump for a fresh agent (or person)
> to pick up where the previous session ended on 2026-05-11.
>
> Read this doc, then `WORLD3_LONG_ARC_2026_05_11.md`, then
> `F35_M11_PARITY_REFACTOR_2026_05_11.md`. That's the spine.
>
> **Handoff revision: git commit `0d76446`.** Run `git show 0d76446
> --stat` to see exactly what this session shipped. There are also
> ~150 other uncommitted changes from earlier sessions sitting in the
> working tree — those are intentional, left for the user to triage.

## What world3 is

A world-generation pipeline. Emits world-data bundles per
[WORLD3_CONTRACT_2026_05_10.md](WORLD3_CONTRACT_2026_05_10.md).
Consumers (games, tools) render them. Godot scenes under
`world3/scenes/` are **validation harnesses**, not gameplay.

The current target: from one `world_plan.json` config, generate a
~5 km tile-able multi-biome world that streams in chunks at runtime.
Each tile must look as good as the existing M11 fourway scene (the
quality bar) without manual per-tile authoring.

## Where you are in the journey

Phase B-E rebuild shipped 2026-05-11. Phase F is in flight: 8 main
sub-phases (F.1-F.8) all shipped, plus 5 follow-ups (F.3.1 contiguity,
F.3.2 splat schema, F.3.3 per-bundle .tres, F.3.4 M11 lib refactor,
F.3.5 fourway support).

**The architectural pivot mid-session was learning that M11
fourway's hand-authored builder was the right shape all along.**
Our pipeline was building parallel-but-skinnier bundles. F.3.4 and
F.3.5 ported M11's logic into our library so F.3 generates
M11-shaped bundles by construction.

**Where the visual gap stands:** Architecture is converged on M11.
Bundles emit the same artifact shape M11 emits. The library can
produce single-biome bundles, multi-biome boundary bundles (schema
ready, iterator side TBD), and M11-style fourway corner bundles.
Visual quality is ~70% of M11's bar — pure tuning + integration
work remaining, no new design needed.

## The one command, today

```
python world3/pipeline/world3_make_world.py world3/jobs/examples/world_plan_starter_2x2_procedural.json
```

This does the whole chain: validate plan → audit transitions →
derive demand → emit bundles → in-context re-audit. ~9s for the
2×2 tundra plan. For a single bundle that recreates M11's exact
fourway content with real Gloss source:

```
python world3/pipeline/build_fourway_bundle.py \
  --out world3/worlds/f35_m11_parity/bundles/m11_fourway_parity \
  --bundle-id m11_fourway_parity \
  --biome-kit grassland \
  --width 1024 --height 1024 --world-size-m 240 --seed 4117 \
  --nw-material m8_grassland_grass_calm_v3 --nw-elev-range-m 22 \
  --ne-material fantasy_lava_field_controlled --ne-elev-range-m 28 \
  --se-material desert_canyon_rock --se-elev-range-m 42 \
  --sw-material scrub_sparse --sw-elev-range-m 12 \
  --slot-rock-dark scrub_sparse --slot-snow grassland_dirt \
  --source-heightmap world3/toporeview/gloss_mountain_textured_master/heightmap.png \
  --source-meta world3/toporeview/gloss_mountain_textured_master/meta.json \
  --source-macro world3/textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png \
  --source-crop 80,760,1024,1024 \
  --extra-catalog world3/materials/catalog_comfy_candidates.json \
  --extra-catalog world3/materials/catalog_m11_fourway_generated.json
```

After Godot --import, view via `res://scenes/review/f35_fourway_parity_tour.tscn`.

## Mental model

```
WORLD PLAN  (user authors)
    │  bounds + tiles + biomes + adjacencies + perspectives + sources
    ▼
F.2 validate_world_plan.py
    ▼
F.4 audit_transition_pairs.py   ← does the catalog support these biome pairs?
    ▼
F.5a derive_catalog_demand.py   ← what materials are needed/missing/below-gate?
    ▼
F.5b run_catalog_requisition.py (--run is user-gated)  ← generate missing mats
    ▼
F.3 world_plan_to_bundles.py    ← emit per-tile region_request.json + world_map.json
   │ runs world3_make.py per tile, which runs the procedural builder
   ▼
   build_procedural_neighbor_bundle.py (thin wrapper around m11_bundle_lib)
     OR build_fourway_bundle.py (fourway corner bundles)
   emits: heightmap + macro + splat + scatter masks + per-bundle material.tres
    ▼
F.6 audit_materials_in_context.py  ← rendered vs catalog drift per biome
    ▼
F.7 multi-bundle streaming director (MultiBundleStreamer.gd + WorldMapService.gd)
    ▼
Walkable world
```

## Critical files (where to look first)

### Schemas
- `world3/jobs/region_request_schema.json` — per-bundle request
- `world3/jobs/world_plan_schema.json` — world plan
- `world3/jobs/world_map_schema.json` — emitted world map
- `world3/jobs/style_packs/style_pack_schema.json` — render style overrides
- `world3/jobs/capture_request_schema.json` — Godot capture request

### Validators (every schema has one)
- `world3/pipeline/validate_region_request.py`
- `world3/pipeline/validate_world_plan.py`
- `world3/pipeline/validate_world_map.py`
- `world3/pipeline/validate_style_pack.py`

### Generators
- `world3/pipeline/m11_bundle_lib.py` — **the core library**, 600 lines, contains all the bundle-shape logic
- `world3/pipeline/build_procedural_neighbor_bundle.py` — thin wrapper for single-biome bundles
- `world3/pipeline/build_fourway_bundle.py` — driver for M11-shape fourway bundles
- `world3/pipeline/f33_bundle_material.py` — per-bundle .tres emit helper

### Orchestrator + top-level
- `world3/pipeline/world3_make.py` — single-bundle orchestrator (`world3_make.py <request.json>`)
- `world3/pipeline/world3_make_world.py` — full-pipeline driver (`world3_make_world.py <plan.json>`)
- `world3/pipeline/world_plan_to_bundles.py` — F.3 plan→bundles iterator

### Audits
- `world3/pipeline/audit_transition_pairs.py` — F.4 catalog-time
- `world3/pipeline/audit_materials_in_context.py` — F.6 runtime
- `world3/pipeline/derive_catalog_demand.py` — F.5a demand deriver
- `world3/pipeline/run_catalog_requisition.py` — F.5b dispatcher (DRY-RUN default)

### Streamer (F.7)
- `world3/scripts/WorldMapService.gd` — world_map.json reader
- `world3/scripts/MultiBundleStreamer.gd` — multi-bundle ChunkLoader manager
- `world3/scripts/MultiBundleSweepDriver.gd` — review sweep scene
- `world3/scenes/review/f7_multi_bundle_sweep.tscn` — F.7 sweep scene

### Reference (the gold standard)
- `world3/pipeline/build_m11_fourway_corner_proof.py` — original M11 builder
- `world3/scenes/review/source_stack_m11_fourway_corner_tour.tscn` — M11 review scene

### Per-phase closure docs (read in order)
1. `E1_E3_ORCHESTRATOR_MVP_2026_05_11.md` — orchestrator MVP
2. `E4_ORCHESTRATOR_CAPTURE_DRIVER_2026_05_11.md` — capture driver
3. `E5_STYLE_PACK_MECHANISM_2026_05_11.md` — style packs
4. `E6_DOCS_HANDOFF_2026_05_11.md` — docs reconciliation
5. `E7_FINAL_VALIDATION_2026_05_11.md` — Phase B-E sign-off
6. `E8_ORCHESTRATION_DEBT_BACKFILL_2026_05_11.md` — pre-F backfill
7. `F1_ORCHESTRATOR_GAPS_CLOSED_2026_05_11.md`
8. `F2_WORLD_PLAN_SCHEMA_2026_05_11.md`
9. `F3_PLAN_TO_BUNDLES_ITERATOR_2026_05_11.md`
10. `F31_EDGE_CONSTRAINT_CONTIGUITY_2026_05_11.md`
11. `F4_TRANSITION_PAIR_AUDIT_2026_05_11.md`
12. `F5_CATALOG_REQUISITION_2026_05_11.md`
13. `F6_IN_CONTEXT_REAUDIT_2026_05_11.md`
14. `F7_MULTI_BUNDLE_STREAMER_2026_05_11.md`
15. `F8_TOP_LEVEL_ENTRY_2026_05_11.md`
16. `F_COURSE_CORRECTION_M11_ARCHITECTURE_2026_05_11.md` ← the mid-session pivot
17. `F34_M11_LIB_REFACTOR_2026_05_11.md`
18. `F35_M11_PARITY_REFACTOR_2026_05_11.md` ← where this session ended

### Canonical operator docs
- `world3/docs/WORLD3_LONG_ARC_2026_05_11.md` — the spine; phase ordering authority
- `world3/docs/PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md` — Phase F charter
- `world3/docs/WORLD3_PIPELINE_GUIDE.md` — how to use this
- `world3/docs/WORKFLOW.md` — operational guide

## What I'd do next, in priority order

### Immediate (visual-quality closure)

1. **Fix the per-quad light field in `m11_bundle_lib.py`.** The
   `build_fourway_macro_preview` function uses `light = 0.5` (flat).
   M11 derives it from `np.gradient(height_m)`. Pass `height_m`
   through to `build_fourway_macro_preview` and compute light there.
   File: `world3/pipeline/m11_bundle_lib.py`. ~10 minutes.

2. **Side-by-side capture against M11.** Use both:
   - `world3/scenes/review/source_stack_m11_fourway_corner_tour.tscn` (M11)
   - `world3/scenes/review/f35_fourway_parity_tour.tscn` (ours)
   Compare at matching iso framing. The gap should narrow significantly
   after fix #1.

3. **Tune `build_fourway_layers` weight formulas** until splat-driven
   slot dominance matches M11's pattern. M11 has specific multipliers
   (e.g. `canyon_weight = ... + slope * 0.34 + rock_cluster * 0.42`)
   that we ported correctly but may want re-tuning if our generalized
   library produces slightly different domain weights.

### Medium-term (extend to 5-biome starter)

4. **Have `build_procedural_neighbor_bundle.py` (single-biome path)
   produce as much visual richness as the fourway path.** Currently
   single-biome bundles use `build_bundle()` which has the M11 scatter
   masks but the splat-weight formulas in `build_layers_general` are
   conservative. Compare splat-weight pattern between single-biome
   and fourway, sharpen if needed.

5. **Rebuild the 5-biome starter plan through `world3_make_world.py`**
   to see how 5 different biomes' single-biome bundles look under
   the F.3.4+ pipeline. Test:
   ```
   rm -rf world3/worlds/starter_5biome_procedural/bundles
   python world3/pipeline/world3_make_world.py \
     world3/jobs/examples/world_plan_starter_5biome_procedural.json \
     --skip-in-context
   ```
   Then run `audit_materials_in_context.py` on it to see per-biome
   drift verdicts.

### Larger (streamer revalidation + multi-biome boundaries)

6. **Multi-biome boundary tile composition.** When a tile's east or
   south neighbor is a different biome, the iterator should emit a
   `FourwayBundleSpec` (or extended `BundleSpec`) with crossfade
   weights at the relevant edges. The library supports it; iterator
   doesn't yet inject the multi-domain weights. See
   `world_plan_to_bundles.py:_layout_entry_for` — extend the
   `source["this_biome"]` logic to include west/north neighbor
   biomes too, and have the procedural builder accept 2-4 domain
   specs.

7. **Re-validate F.7 streamer with M11-shape bundles.** The streamer
   now loads per-bundle `material.tres` directly (F.3.3 changes).
   With the F.3.5 bundles now correctly M11-shaped, the streamer
   should render them cleanly. Test:
   ```
   $GODOT --rendering-driver opengl3 --path "D:/assets/world3" \
     --single-window --disable-crash-handler \
     "res://scenes/review/f7_multi_bundle_sweep.tscn"
   ```

### After Phase F closes (Phase G and beyond)

Per `PHASE_G_CHARTER_2026_05_11.md`:
- G.1 LOD-aware capture
- G.2 2.5D perspective
- G.3 Handcraft override path (patch bundles)
- G.4 Consumer integration kit
- G.5 Per-mode quality bars at gate time
- G.6 Real-DEM patch seeding refinement

## Pinned decisions (don't re-litigate)

These were settled by the user 2026-05-11; respect them:

1. **5 km world, 256 m tile size, 5 starter biomes** (alpine, desert,
   tundra, grassland, temperate_forest)
2. **Pipelines, not content** until at least mid-Phase H — every
   deliverable lands as a script/schema, never authored art
3. **Scale is the perennial enemy** — every artifact carries explicit
   `world_size_*_m` / `elevation_range_m` / `tile_size_m` /
   `zoom_level_m`. No implicit units.
4. **Catalog quality is gate-state, not vibes.** M13 promotion gate
   is sacred.
5. **Transition quality lives at catalog time** (F.4), not runtime
6. **M11 fourway is the visual quality bar** — bundles produced by
   our pipeline must clear what M13 gate says about M11 fourway
7. **LLM-drivability is a hard gate** — every sub-phase ships with
   schema + validator + example + audit + closure doc + stages.json
   entry
8. **One canonical roadmap** — `WORLD3_LONG_ARC_2026_05_11.md` wins
   on phase ordering. Legacy M19+/O1+ are history, mapped via the
   anti-duplication ledger inside that doc.

## How to drive the user

The user wants **autonomous execution with course corrections**. They:
- Want me/you to keep going without checking in for routine decisions
- Will say "course correct to X" when they spot something off
- Trust you to make reasonable assumptions
- Want WORKFLOW.md / README.md updated as you go (not just closure docs)
- Want the F charter and long-arc kept current in real time
- Want operator-facing docs to stay current (not buried in closure docs)
- Do NOT want destructive operations without explicit confirmation
- Use Auto Mode — keep momentum, don't pause to ask permission for
  reasonable next steps

When the user gives a one-liner like "ok keep going" or "lets do it",
that's permission to drive the next obvious deliverable end-to-end
including doc updates + closure + memory.

When they push back ("looks bad", "why aren't we doing X"), take it
seriously — they have context you don't. The big mid-session pivot
("why aren't we just doing what M11 did?") was the right call from
them, not from me.

## Tool conventions

- **Godot binary**: `C:/Godot/Godot_v4.5-stable_win64.exe` (NOT the
  mono build at `C:/Users/josep/Downloads/...`). Mono build silently
  fails. Always use `--rendering-driver opengl3 --single-window
  --disable-crash-handler --log-file <path>`.
- **Headless import**: `C:/Godot/Godot_v4.5-stable_win64.exe --headless
  --path "D:/assets/world3" --import` — needed after bundles are
  built outside the editor's filesystem watch.
- **Capture scenes**: use the regular binary with `opengl3` driver and
  the headless capture script — never `--headless` alone, which
  returns a null viewport.
- **Memory location**:
  `C:/Users/josep/.claude/projects/d--assets/memory/MEMORY.md` and
  individual `<topic>.md` files. Index in MEMORY.md.
- **Python**: Python 3.12 on Windows, jsonschema installed. Use
  `python` not `python3`.

## Quick verification commands

```
# Validate every schema's self-test
python world3/pipeline/validate_region_request.py --schema-self-test
python world3/pipeline/validate_world_plan.py --schema-self-test
python world3/pipeline/validate_world_map.py --schema-self-test
python world3/pipeline/validate_style_pack.py --schema-self-test
python world3/pipeline/audit_stages.py

# Build a small world end-to-end
python world3/pipeline/world3_make_world.py \
  world3/jobs/examples/world_plan_starter_2x2_procedural.json \
  --skip-in-context

# Build a single M11-parity fourway
# (full command in F35_M11_PARITY_REFACTOR_2026_05_11.md)
```

## When you're ready to start

1. Read `WORLD3_LONG_ARC_2026_05_11.md` — phase ordering
2. Read `F35_M11_PARITY_REFACTOR_2026_05_11.md` — current state
3. Read `m11_bundle_lib.py` source — understand the central library
4. Run the verification commands above to confirm the environment
5. Either pick up at "Immediate" item 1 above (per-quad light field)
   or ask the user which path they want first

## Goodbye

The work is in good shape. The architecture is right. The library is
clean. The audits are honest. The remaining gaps are tunable, not
fundamental.

Don't be afraid to step back if something feels wrong — the M11 pivot
mid-session was a 3-hour course correction that the previous sessions
should have caught earlier. Trust the user when they push back.
