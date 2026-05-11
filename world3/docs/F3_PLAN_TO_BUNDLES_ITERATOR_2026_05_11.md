# Phase F.3 — Plan-to-bundles iterator

> A validated world plan now expands into N per-tile region requests
> + a `world_map.json` that the F.7 streaming director will read.
> The iterator can optionally drive the orchestrator end-to-end so
> the entire chain `plan → requests → bundles` runs from one command.
> Smoked clean on 4-tile and 25-tile worlds; byte-identical
> reproduction proved across independent runs on both.

## Verdict

**F.3 ships the multi-bundle expansion layer.** From this point on,
"a world" is a real thing on disk: a world_map plus a tree of
bundles indexed by world coordinate, all reproducible from one plan
JSON.

## What shipped

### Iterator

**`world3/pipeline/world_plan_to_bundles.py`** — argparse CLI taking
a world plan path. Validates the plan via `validate_world_plan.py`
(re-uses the F.2 semantic ruleset, no duplication), then for each
tile in `biome_layout`:

1. Derives per-tile seed: `int(sha256(plan_seed:col:row)[:4]) & 0x7FFFFFFF`.
   Deterministic across runs and machines (no Python `hash()` salt).
2. Resolves the tile's source: `source_override` on the layout entry
   wins, else falls back to the biome's `source` from `biomes[]`.
3. Emits a region_request.json under
   `world3/worlds/<plan_id>/requests/<bundle_id>.json` with the
   tile's seed substituted into the source dict.
4. Records a tile entry for `world_map.json`.

After all tiles, writes `world3/worlds/<plan_id>/world_map.json`.

Flags:
- `--dry-run` — validate + preview without writing files
- `--run` — after emitting, invoke `world3_make.py` on each request
  in order; aborts on first failure
- `--only-stages` — pass-through to `world3_make.py` when `--run`

### World map schema

**`world3/jobs/world_map_schema.json`** — JSON Schema 2020-12 for the
emitted `world_map.json`. Required:

- `schema_version`, `plan_id`, `bounds_m`, `tile_size_m`, `seed`, `tiles[]`

Each tile entry:
- `tile_xy` — `[col, row]` from the plan
- `world_xy_m` — `[col*tile_size_m, row*tile_size_m]` SW corner
- `biome`, `source_type`
- `bundle_id` — `<plan_id>__tile_<col>_<row>`
- `request_path` — relative path to the emitted region request
- `bundle_dir` — relative path the orchestrator will produce into
- `tile_seed` — deterministic per-tile seed

Optional plan-level metadata: `grid` (=`[cols, rows]`), `perspectives`,
`style_pack`, `generated_at` ISO timestamp.

### World map validator

**`world3/pipeline/validate_world_map.py`** — argparse CLI with
positional maps + `--schema-self-test` (walks
`world3/worlds/*/world_map.json`). Beyond schema:

1. Every tile in the declared `grid` is present exactly once
2. No `tile_xy` out of bounds
3. No duplicate `tile_xy`
4. No duplicate `bundle_id` (would collide on disk)

## Validation

### 2×2 plan, full chain

```
$ python world3/pipeline/world_plan_to_bundles.py \
    world3/jobs/examples/world_plan_starter_2x2_procedural.json --run

--- Validating plan ---     [OK]
--- Emitting tile requests ---
  [tile [0,0]] biome=tundra -> ...requests/starter_2x2_procedural__tile_0_0.json
  [tile [1,0]] biome=tundra -> ...
  [tile [0,1]] biome=tundra -> ...
  [tile [1,1]] biome=tundra -> ...
  wrote 4 request files
--- World map ---
  world3\worlds\starter_2x2_procedural\world_map.json
--- Running orchestrator on 4 tiles ---
  [run] tile [0,0] ... === world3 orchestrator DONE ===
  [run] tile [1,0] ... === world3 orchestrator DONE ===
  [run] tile [0,1] ... === world3 orchestrator DONE ===
  [run] tile [1,1] ... === world3 orchestrator DONE ===
  all 4 tiles OK
=== world_plan_to_bundles DONE ===
```

Output:
```
world3/worlds/starter_2x2_procedural/
  world_map.json
  requests/
    starter_2x2_procedural__tile_{0,1}_{0,1}.json  (4 files)
  bundles/
    starter_2x2_procedural__tile_{0,1}_{0,1}/      (4 bundles)
```

World map validates: `=== World map self-test PASSED (1 maps) ===`.

**Byte-identical reproduction across two independent runs** — all four
heightmap hashes match:
```
3b9636bfff2a14e83607959911d74461 *tile_0_0/heightmap.png
8900fa7e67012845111c0640a3e0bdcb *tile_0_1/heightmap.png
eac44791fd58bf64756ada000bb1bc09 *tile_1_0/heightmap.png
55f58fac3308758fbe10c9a80fd84002 *tile_1_1/heightmap.png
```

### 5×5 plan, 25 tiles

```
$ python world3/pipeline/world_plan_to_bundles.py \
    world3/jobs/examples/world_plan_starter_5biome_procedural.json --run

...
  all 25 tiles OK
=== world_plan_to_bundles DONE ===
```

- 25 request files emitted
- 25 unique `tile_seed` values (no hash collisions)
- 25 bundles built end-to-end through `world3_make.py`
- Biome distribution: tundra=3, grassland=8, alpine=4, temperate_forest=6, desert=4 (sums to 25, matches plan)
- Sample hashes show distinct heightmaps per biome:
  - tundra @ (0,4): `95af67c3970533fa23f1570275fa9217`
  - alpine @ (2,2): `c9739231d52797470372ef10e227286a`
  - desert @ (4,0): `a925425ccb47f5d67a2bf762e65a7d43`
- Byte-identical across runs: alpine tile (2,2) reproduces
  `c9739231d52797470372ef10e227286a` on rerun

### Round-trip schema check

The iterator's emitted request files validate clean against the
existing `region_request_schema.json`:

```
$ python world3/pipeline/validate_region_request.py \
    world3/worlds/starter_5biome_procedural/requests/starter_5biome_procedural__tile_2_2.json
  [OK  ] ...starter_5biome_procedural__tile_2_2.json
```

That's the cross-schema sanity check — F.3 emits requests that F.2's
upstream schema (region request) accepts. Closed loop.

## Six-box LLM-drivability check

| Box | Status |
|---|---|
| Schema | ✅ `world_map_schema.json` |
| Validator | ✅ `validate_world_map.py --schema-self-test` |
| Example | ✅ Two emitted world maps under `world3/worlds/*/world_map.json` |
| Audit | ✅ validator IS the audit at this layer |
| Closure doc | ✅ this doc |
| Stages.json | N/A — F.3 is a top-level driver, not a per-bundle stage |

## What's NOT in F.3

- **Hybrid / real-DEM iteration.** The iterator handles `source.type =
  "hybrid"` and `"real"` mechanically (passes them through to
  region requests), but no example plan exercises this. F.4 + G.6
  will likely need such an example.
- **Adjacency-aware bundle dependencies.** The orchestrator runs
  bundles in `biome_layout` declaration order, not adjacency order.
  Fine for procedural-only (each bundle is independent). When
  hybrid plans land in G.6, the iterator will need a topological
  pass so a real-source-side bundle is built before its hybrid
  neighbor.
- **Resume / incremental builds.** Re-running with `--run` rebuilds
  every tile. Deterministic content means re-runs are wasted work
  for unchanged tiles; an incremental mode could short-circuit on
  matching tile_seed + source hash. Deferred — at 25 procedural
  tiles in ~15s the savings don't matter yet.
- **Parallel orchestrator execution.** Tiles run sequentially. Trivial
  to parallelize at the subprocess layer; not needed at current
  scale.
- **Transition-pair audit before emit.** That's exactly F.4 — auditing
  whether the catalog materials behind the plan's adjacency rules
  actually blend cleanly *before* spending compute on N bundles.
  Today the iterator emits regardless; F.4 will gate emission.

## Cross-references

- Parent phase: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Previous: [F2_WORLD_PLAN_SCHEMA_2026_05_11.md](F2_WORLD_PLAN_SCHEMA_2026_05_11.md)
- Reads: `world3/jobs/world_plan_schema.json`, `world3/jobs/region_request_schema.json`
- Emits: `world_map.json` per `world_map_schema.json`, plus per-tile region requests
- Drives: `world3/pipeline/world3_make.py`

## Status

- [x] `world_plan_to_bundles.py` iterator
- [x] `world_map_schema.json`
- [x] `validate_world_map.py` with --schema-self-test
- [x] 2×2 smoke (4 tiles emit + run + byte-identical across runs)
- [x] 5×5 smoke (25 tiles emit + run + byte-identical across runs)
- [x] Round-trip schema check (emitted requests validate clean)
- [x] Closure doc (this doc)

**Phase F.3 SHIP.** Plans expand into worlds. F.4 (catalog-time
transition audit) is next.
