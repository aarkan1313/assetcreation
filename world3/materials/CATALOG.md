# world3 Material Catalog

Date: 2026-05-08

This folder is the source of truth for terrain material identity. The
catalog is not a production-content promise; it is the pipeline contract used
to prove that procedural, real-source, and future fantasy materials can be
tracked, compared, transitioned, and rendered at AAA quality.

Machine-readable catalog:

```text
world3/materials/catalog.json
```

## Contract

Every terrain material entry must include:

- `id`: canonical material id. Runtime scenes, kit slots, transition tools,
  splat masks, and worker handoffs should use this id.
- `source`: `real`, `procedural`, or `fantasy`.
- `provenance`: generation prompt, source crop, source asset id, tool, and QA
  notes sufficient to reproduce or audit the asset.
- `scale_m_per_repeat`: the intended world-space repeat for current shader
  use. Today this is the terrain_blend iso/base repeat.
- `color_family`: coarse visual family for transition planning.
- `pbr_maps`: paths to the currently available albedo, normal, roughness,
  height, and AO maps. Use `null` for maps that do not exist in the deployed
  runtime folder yet.
- `shader_binding`: current shader family, either `terrain_blend` or
  `terrain_hex_detail`. M4 unifies these; the catalog records current reality.
- `validated_views`: close, mid, and far status using `ok`, `needs_review`, or
  `not_validated`.

Additional fields such as `asset_status`, `runtime_texture_dir`, and detailed
provenance are intentionally allowed. This project is a workflow creation set,
so traceability and QA state are part of the asset, not side paperwork.

## Naming

Canonical ids should describe the material class as used by the terrain
runtime, not necessarily the generator folder that produced it.

Example:

```text
canonical id:        grassland_grass
source_asset_id:     wgv3_gl_tall_grass
runtime texture dir: world3/textures/wgv3/grassland_grass
```

This keeps M2 transition pairs and M4 splat channels stable while preserving
the source generator provenance needed to regenerate the asset.

## Boundary Transition Assets

Transition strips are not base material catalog entries. They are generated
boundary assets derived from catalog material pairs and referenced by:

```text
world3/jobs/biome_transition_rules.json
```

This prevents the catalog from growing into every possible pair combination.
The catalog owns source material identity; the transition rules own pair
context, boundary intent, generated strip manifests, and M4 runtime use.

## Current Coverage

Committed in this draft:

- 25 procedural kit-slot materials from the five terrain_blend kits:
  alpine/base, desert, tundra, temperate_forest, and grassland.
- 6 real-source OpenTopo Guadalupe Cypress material classes:
  `bare_soil`, `bright_rock`, `dry_wash`, `rocky_slope`, `scrub_dense`,
  and `scrub_sparse`.
- `biome_kits.json` now references catalog-facing material ids for kit slots.
- The OpenTopo classes currently keep `shader_binding = terrain_hex_detail`
  until M4 unifies the shader stack.

## Scale Note

Current terrain_blend mode variants map to these repeats:

```text
walk:    2.5m
iso:     10m
topdown: 50m
```

The scalar `scale_m_per_repeat` in the catalog records the iso/base value so
M2 and M4 have one stable number to start from. If M4 moves to per-material or
per-mode UV policy, add explicit per-mode scale fields rather than changing
the meaning of this field.

## Validation Meaning

`asset_status = pipeline_validation` means the material exists to prove and
tune the workflow. It may become a production candidate later, but promotion
requires a separate review pass at the camera ranges and source/style mix used
by the target game.

## M1 Verification

2026-05-08 verification:

- Regenerated base kit materials with `world3/pipeline/build_kit_materials.py`.
- Regenerated per-mode materials with `pipelines/textures/emit_per_mode_materials.py`.
- Ran Godot import successfully.
- Rendered a Phase E alpine smoke capture.
- Regenerated the region gallery at `D:/tmp/world3_screens/regions/`.
- Checked nonblank output for grassland and temperate_forest regions, the kits
  whose slot ids changed from source-generator ids to catalog ids.

This closes the catalog as a stable M2/M4 input. It does not promote any
material to final production status.
