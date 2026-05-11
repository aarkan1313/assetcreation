# world3 Pipeline Guide

> The canonical "how to use this" doc. Read this first if you want
> to build a world. Phase B-E built the foundation; Phase F made
> it real; this doc explains the operator surface that ships at end
> of F.8.

## The one command

```powershell
python world3/pipeline/world3_make_world.py world3/jobs/examples/world_plan_starter_5biome_procedural.json
```

This runs the full pipeline end-to-end: validate plan → audit transitions
→ derive catalog demand → emit per-tile bundles → re-audit in-context.
~30s for a 5×5 world (25 bundles + 5 in-context captures), ~9s for a 2×2.

## Mental model

```
WORLD PLAN  (you author this)
    │  describes: bounds, tile grid, biomes, allowed adjacencies, sources
    ▼
F.2 validate          schema + 7 semantic rules
    ▼
F.4 audit transitions  per-pair palette/luminance/freq/seam diagnostics
    │  output: world3/jobs/transition_audits/<plan_id>.json
    ▼
F.5a derive demand    have / need / below_promotion_bar + work_queue
    │  output: world3/jobs/catalog_demand/<plan_id>.json
    ▼
F.5b requisition       (optional, --auto-requisition) drives texture pipeline
    │
    ▼
F.3 emit + build       one region_request per tile + world_map.json
    │  output: world3/worlds/<plan_id>/{world_map.json, requests/, bundles/}
    ▼
F.6 in-context audit   re-capture each biome through orchestrator, score drift
    │  output: world3/jobs/in_context_audits/<plan_id>.json
    ▼
WORLD READY for F.7 streaming director (next phase)
```

Each stage has its own script and can run standalone for debug.
`world3_make_world.py` is the synthesis — it composes them with
sensible defaults.

## Authoring a world

### 1. Start from an example plan

```powershell
cp world3/jobs/examples/world_plan_starter_5biome_procedural.json world3/jobs/examples/my_world.json
```

Edit:
- `id` — must be lowercase, used as `world3/worlds/<id>/` dir name
- `bounds_m` — `[x_m, z_m]` in meters; must be divisible by `tile_size_m`
- `tile_size_m` — 256 starter (Phase F charter; may multi-scale later)
- `seed` — plan-level int, per-tile seeds derive from it deterministically
- `biomes[]` — declare each biome with `id`, `biome_kit`, `source`, `primary_material_id`
- `biome_layout[]` — explicit per-tile assignment `{tile_xy: [c,r], biome: "<id>"}`
  every tile in the grid must be assigned exactly once
- `adjacency_rules.allowed_pairs` — list of `[biome_a, biome_b]` pairs
  allowed to neighbor; any 4-connected adjacency in the layout not in
  this list is a validation error
- `perspectives` — subset of `walk|iso|topdown|25d`
- `style_pack` — default `"photoreal"`; must exist in `world3/jobs/style_packs/`

Two starter examples:
- `world_plan_starter_2x2_procedural.json` — 2×2 single biome (smallest)
- `world_plan_starter_5biome_procedural.json` — 5×5 all five starter biomes

### 2. Run the pipeline

```powershell
# full chain
python world3/pipeline/world3_make_world.py world3/jobs/examples/my_world.json

# fast iteration (skip the ~5s/biome Godot re-render loop)
python world3/pipeline/world3_make_world.py <plan> --skip-in-context

# resume mid-flow (e.g. you already built bundles, just want re-audit)
python world3/pipeline/world3_make_world.py <plan> --from-step 6

# single step
python world3/pipeline/world3_make_world.py <plan> --only-step 2

# strict: refuse to build if catalog has need/below items
python world3/pipeline/world3_make_world.py <plan> --strict-catalog

# USER-GATED: actually drive the texture pipeline to generate missing materials
python world3/pipeline/world3_make_world.py <plan> --auto-requisition
```

### 3. Read the audits

After a run, four JSON artifacts tell you the state of the world:

```
world3/jobs/transition_audits/<plan_id>.json    F.4: per-pair palette/freq/lum/seam scores + recommended_action
world3/jobs/catalog_demand/<plan_id>.json       F.5a: have/need/below + prioritized work_queue
world3/worlds/<plan_id>/world_map.json          F.3: world coord → bundle map
world3/jobs/in_context_audits/<plan_id>.json    F.6: catalog→runtime drift per biome
world3/jobs/world_build_summaries/<plan_id>_<ts>.json   F.8: step-by-step status
```

All are JSON, all have human-readable summaries when their script is
run directly. An LLM driving the pipeline can grep these for any
specific finding.

## Step-by-step reference

### Step 1 — validate plan (F.2)

`python world3/pipeline/validate_world_plan.py <plan>` (or `--schema-self-test`)

Enforces 7 semantic rules beyond schema. Failures are line-level:
"bounds not divisible by tile_size_m", "tile [3,4] outside grid",
"pair (alpine, tundra) not in allowed_pairs", etc.

### Step 2 — catalog-time transition audit (F.4)

`python world3/pipeline/audit_transition_pairs.py <plan>`

For each `allowed_pair`, loads both biomes' primary albedo, tiles to
512×1024, computes:
- `palette_delta_lab` — Lab distance of median colors
- `luminance_range_delta` — diff of p95-p5 luminance
- `high_freq_energy_ratio` — texture frequency mismatch
- `seam_band_internal_max_delta_rgb01` — simulated seam visible delta

Verdict per pair → `recommended_action`:
- `palette_lock` — cross-material palette work via `palette_lock.py`
- `regenerate` — material rebuild via `aaa_texture.py`
- `shader_blend_band` — runtime mitigation (not catalog work)
- `none` — pass

### Step 3 — derive catalog demand (F.5a)

`python world3/pipeline/derive_catalog_demand.py <plan>`

For every material referenced by the plan:
- `have` — exists in catalog AND `passed_gate=true`
- `need` — not in catalog at all
- `below_promotion_bar` — exists but `passed_gate=false`

Plus consumes the F.4 audit to add work_queue items for failing pairs.
Prioritization: `fix_catalog` > `palette_lock` > `regenerate` >
`shader_blend_band` (excluded).

### Step 4 — catalog requisition (F.5b) — USER-GATED

`python world3/pipeline/run_catalog_requisition.py <demand>` (dry-run by default)
`python world3/pipeline/run_catalog_requisition.py <demand> --run` (actually generate)

Reads the demand work_queue, builds commands for `aaa_texture.py` /
`palette_lock.py` with prompts + seeds pulled from
`world3/materials/catalog.json`. Run records under
`world3/jobs/catalog_requisition_records/`.

**Default is DRY-RUN.** Real generation requires `--run` flag —
intentional so LLM-driven catalog remediation needs explicit user gate.

### Step 5 — emit + build bundles (F.3)

`python world3/pipeline/world_plan_to_bundles.py <plan> --run`

For each tile in `biome_layout`:
- Derive per-tile seed: `sha256(plan_seed:col:row)` (deterministic)
- Emit `world3/worlds/<plan_id>/requests/<bundle_id>.json` (region request)
- Invoke `world3_make.py` to actually build the bundle

Writes `world3/worlds/<plan_id>/world_map.json` mapping world coords
to bundles. This is what the F.7 streaming director will read.

Without `--run`, only emits the requests + world_map (preview mode).

### Step 6 — in-context re-audit (F.6)

`python world3/pipeline/audit_materials_in_context.py <plan>`

For each biome:
- Find first tile in world_map using this biome
- Drive the E.4 orchestrator capture driver in iso mode
- Compute the same 3 metrics F.4 used (palette/lum/HF) on rendered patch
- Compare to catalog albedo metrics, flag drift

Each biome ends up with an iso capture under
`world3/docs/captures/review/in_context_<plan_id>_<biome>_iso.png`
plus per-biome drift verdict in the audit JSON.

## Schemas (the LLM-drivable surface)

Every layer has a JSON Schema + validator:

| Schema | Validator | What it describes |
|---|---|---|
| `region_request_schema.json` | `validate_region_request.py` | one bundle's intent |
| `stages.json` | `audit_stages.py` | the 12 pipeline stages |
| `style_pack_schema.json` | `validate_style_pack.py` | render-time visual overrides |
| `capture_request_schema.json` | (covered by E.8) | orchestrator capture driver request |
| `world_plan_schema.json` | `validate_world_plan.py` | multi-bundle world intent |
| `world_map_schema.json` | `validate_world_map.py` | emitted world coordinate map |

All schemas are JSON Schema 2020-12, in `world3/jobs/`.

## What ships at end of Phase F.8 (now)

- One command builds a tile-able multi-bundle world from a JSON plan
- Three independent audit JSONs surface catalog gaps, transition issues, and runtime drift
- All artifacts are deterministic; re-runs produce byte-identical bundles
- Every layer has a schema, validator, audit, closure doc — LLM-drivable
- Soft gates surface findings without blocking; strict mode + auto-requisition for hard runs

## What does NOT ship until F.7

- **Multi-bundle streaming at runtime.** The bundles are on disk and the
  world_map tells you which lives where; the GDScript ChunkLoader is
  still single-bundle. F.7 wires cross-bundle chunk handoff + direction-
  aware preload.
- **The "infinite tiled walkable world" experience.** Until F.7, you
  can render any individual bundle through the orchestrator capture
  driver, but you can't walk across bundle boundaries.

## What does NOT ship until Phase G+H

- LOD-aware emission for 3 zoom bands (G.1)
- 2.5D perspective + `terrain_blend_<kit>_25d.tres` variants (G.2)
- Handcraft override / patch bundles (G.3 + G.6)
- Per-mode quality bars at gate time (G.5)
- Catalog scaleup beyond 5-biome starter (H.1)
- Erosion sim, POI layer, water/atmo/sky/weather, conformance suite (H.2-H.6)

## Cross-references

- Long-arc roadmap: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Phase F charter (every sub-phase): [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Per-sub-phase closure docs: F1, F2, F3, F4, F5, F6, F8 (this doc + F8 closure)
- Bundle output contract: [WORLD3_CONTRACT_2026_05_10.md](WORLD3_CONTRACT_2026_05_10.md)
- Cold-start handoff: [ORCHESTRATOR_HANDOFF_2026_05_11.md](ORCHESTRATOR_HANDOFF_2026_05_11.md)
- Completion bar (Phase I): [WORLD3_COMPLETION_BAR_2026_05_10.md](WORLD3_COMPLETION_BAR_2026_05_10.md)
