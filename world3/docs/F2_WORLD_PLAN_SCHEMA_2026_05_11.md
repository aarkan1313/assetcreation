# Phase F.2 — World plan schema

> Top-level intent for a multi-bundle world is now a validated JSON
> shape. A plan declares bounds, tile grid, biomes, allowed
> adjacencies, per-biome sources, perspectives, and zoom levels.
> Two example plans ship — the smallest possible (2×2 single biome)
> and the Phase F starter (5×5 all five biomes, 6 cross-biome
> adjacency rules). The validator catches schema errors AND seven
> distinct semantic error classes.

## Verdict

**F.2 ships the "I want a world" schema layer.** Everything downstream
in Phase F (F.3 plan→bundles iterator, F.4 transition audit, F.5
catalog requisition, F.6 in-context audit, F.7 streaming director)
reads from this schema. Pure JSON work — no subprocess wiring, no
Godot, no runtime changes.

## What shipped

### Schema

**`world3/jobs/world_plan_schema.json`** — JSON Schema draft 2020-12.
Required fields:

- `schema_version` — const 1
- `id` — lowercase identifier, used for `world3/worlds/<id>/` output dir
- `bounds_m` — `[x_m, z_m]` world size in meters
- `tile_size_m` — square tile size (256m starter per Phase F charter)
- `seed` — plan-level seed; per-tile seeds derive deterministically in F.3
- `biomes[]` — array of `{id, biome_kit, source, primary_material_id}`
- `biome_layout[]` — explicit per-tile assignment `{tile_xy, biome, source_override?}`
- `adjacency_rules` — `{allowed_pairs[], self_neighbor_allowed}`
- `perspectives[]` — subset of `walk|iso|topdown|25d`

Optional:
- `description` — human-readable provenance
- `zoom_levels[]` — array of `{id: close|mid|far, distance_m}`, default empty (Phase G.1 wires real LOD)
- `style_pack` — default `photoreal`

### Validator

**`world3/pipeline/validate_world_plan.py`** — argparse CLI with
positional plans + `--schema-self-test`. Beyond schema conformance,
enforces six semantic rules:

1. `bounds_m` must be integer-multiple of `tile_size_m` on both axes
2. `biome_layout` must cover every tile in the grid exactly once
3. No duplicate `tile_xy` entries
4. Every biome referenced in layout must be declared in `biomes[]`
5. Every 4-connected adjacency in the layout must be in
   `adjacency_rules.allowed_pairs` (or be a self-neighbor when
   allowed)
6. `style_pack` file must exist under `world3/jobs/style_packs/<id>.json`

Plus a soft warning for `biome_kit` values outside the Phase F starter
roster (alpine, desert, tundra, grassland, temperate_forest).

### Example plans

**`world3/jobs/examples/world_plan_starter_2x2_procedural.json`** — smallest
possible: 2×2 tundra tiles at 256m, single biome, self-neighbor only.
Proves the minimum viable surface.

**`world3/jobs/examples/world_plan_starter_5biome_procedural.json`** —
Phase F starter: 5×5 (1280m × 1280m), all 5 starter biomes laid out in
concentric bands with 8 declared adjacency pairs:
- tundra↔grassland, tundra↔alpine
- alpine↔grassland, alpine↔temperate_forest, alpine↔desert
- temperate_forest↔desert, temperate_forest↔tundra
- desert↔grassland

The 5×5 plan exercises every semantic check at non-trivial scale.

## Validation

### Happy path

```
$ python world3/pipeline/validate_world_plan.py --schema-self-test
  [OK  ] jobs\examples\world_plan_starter_2x2_procedural.json
  [OK  ] jobs\examples\world_plan_starter_5biome_procedural.json

=== World plan self-test PASSED (2 plans) ===
```

### Negative cases (7 caught)

Generated under `D:/tmp/world_plan_neg/`:

| Case | Mutation | Caught as |
|------|----------|-----------|
| case1 | `bounds_m = [500.0, 512.0]` | `bounds_m[0]=500.0 not divisible by tile_size_m=256.0` |
| case2 | Removed last tile from layout | `biome_layout: missing 1 tiles, e.g. [(1, 1)]` |
| case3 | Reduced allowed_pairs to one pair | `adjacency: 13 forbidden adjacent pairs (4-connected)` with line-level enumeration |
| case4 | `style_pack = "nonexistent_pack"` | `style_pack 'nonexistent_pack' not found at jobs\style_packs\nonexistent_pack.json` |
| case5 | Layout tile uses biome id `"imaginary"` | `biome_layout: tile [0, 0] references undeclared biome 'imaginary'` |
| case6 | `schema_version = 99` | `schema: schema_version: 1 was expected` |
| case7 | Duplicated `[0, 0]` in layout | `biome_layout: tile [0, 0] declared more than once` |

All seven error classes produce actionable line-level messages.

## Six-box LLM-drivability check

- ✅ **Schema** — `world_plan_schema.json`
- ✅ **Validator** — `validate_world_plan.py --schema-self-test`
- ✅ **Example** — 2 plans under `world3/jobs/examples/world_plan_*.json`
- ✅ **Audit** — validator IS the audit at the plan level. F.4 will add
  the deeper transition-pair audit; that's a different concern.
- ✅ **Closure doc** — this doc
- ✅ **Stages.json entry** — N/A here (this layer doesn't run as an
  orchestrator stage; it's read by F.3 which will be the stage).

## What's NOT in F.2

- **Plan-to-bundles iterator.** That's F.3. F.2 just defines what a
  plan looks like.
- **Transition-pair audit at catalog time.** That's F.4. F.2's adjacency
  rules are *declarative* only — the validator checks the layout
  doesn't violate them; F.4 audits whether the materials actually
  blend cleanly when those adjacencies happen at render time.
- **Per-tile sources, source overrides.** Schema supports `source_override`
  on layout entries, but no example exercises it. Trivial extension
  when needed.
- **Noise-driven layout generators.** Schema is explicit-layout only.
  Future generators emit the same shape; the schema is layout-source-agnostic.
- **Hybrid example plan.** Schema supports `source.type = "hybrid"` via
  the same shape as `region_request.json`, but the example plans are
  procedural-only. A hybrid example plan would need a real-DEM bundle
  reference per-biome; deferred until G.6 (real-DEM patch refinement)
  is closer.

## Cross-references

- Parent phase: [PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md](PHASE_F_PIPELINE_BUILDOUT_2026_05_11.md)
- Long-arc: [WORLD3_LONG_ARC_2026_05_11.md](WORLD3_LONG_ARC_2026_05_11.md)
- Previous sub-phase: [F1_ORCHESTRATOR_GAPS_CLOSED_2026_05_11.md](F1_ORCHESTRATOR_GAPS_CLOSED_2026_05_11.md)
- Reads from: `world3/jobs/region_request_schema.json` (source shape),
  `world3/jobs/style_packs/*.json` (style pack lookup)

## Status

- [x] `world_plan_schema.json` shipped
- [x] `validate_world_plan.py` with `--schema-self-test`
- [x] Two example plans (2×2 single-biome, 5×5 all-five-biomes)
- [x] Self-test PASSED on both examples
- [x] 7 negative cases caught with line-level messages
- [x] Closure doc (this doc)

**Phase F.2 SHIP.** Plan schema ready. F.3 (plan → bundles iterator)
is next.
