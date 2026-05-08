# M2 Boundary Transition Contract

Date: 2026-05-08

## Decision

Transition strips are **generated boundary assets referenced by biome/material
boundary rules**. They are not first-class base material catalog entries.

Machine contract:

```text
world3/jobs/biome_transition_rules.json
```

Regenerate current boundary assets from the contract with:

```powershell
python pipelines/textures/build_transition_strip.py --rules world3/jobs/biome_transition_rules.json
```

## Why

Base catalog entries represent reusable terrain material identities:
`desert_sand`, `grassland_grass`, `dry_wash`, and so on. A transition strip is
derivative of a pair plus a mask strategy. Promoting every pair to the material
catalog would create combinatorial catalog growth and blur the difference
between source material quality and boundary blending quality.

The cleaner split is:

- `world3/materials/catalog.json` owns source material identity, provenance,
  PBR maps, and validation state.
- `world3/jobs/biome_transition_rules.json` owns pair-specific boundary
  assets, review status, and M4 runtime intent.
- `world3/textures/transitions/index.json` owns generated outputs and score
  hints from the current build.

## Runtime Shape For M4

M4 should treat a boundary as three inputs:

- `material_a_weight`
- `material_b_weight`
- `boundary_weight`

The base material IDs still come from the catalog. The boundary rule provides
the generated strip manifest and the sampling contract:

- `u`: normalized signed distance across the biome/material boundary, 0..1
- `v`: world distance along the boundary divided by repeat scale

If the first M4 prototype does not have boundary-space UVs yet, it can still
use the score hints to tune normal two-material splat blending. The generated
strip then remains review/evidence rather than shader input.

## Rule Schema

Each rule contains:

- `id`: stable rule identity.
- `scope`: `biome_boundary`, `real_source_material_neighbor`, or a bridge role.
- `from_kit` / `to_kit`: biome-kit names when the boundary is kit-level.
- `from_material` / `to_material`: catalog IDs used by the generated strip.
- `transition_manifest`: generated manifest under `world3/textures/transitions/`.
- `prototype_width_repeats`: strip width in texture repeats.
- `runtime_width_m`: runtime boundary width, left `null` until M4 tests scale.
- `mask_strategy`: current mask family.
- `status`: review state.
- `m4_use`: why this pair exists in the next shader pass.

## Current Read

The four current rules cover:

- High-contrast generated biome boundary: `desert_sand` -> `grassland_grass`
- Same-source real-material control: `scrub_sparse` -> `dry_wash`
- Palette/normal stress pair: `tundra_moss` -> `temperate_forest_grass`
- Real/procedural bridge: `dry_wash` -> `desert_dry_brush`

This is enough to start M4 without pretending every transition is a production
candidate. The workflow contract is now stable; the assets can keep improving.
