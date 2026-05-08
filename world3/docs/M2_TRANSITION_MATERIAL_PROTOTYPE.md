# M2 Transition Material Prototype

Date: 2026-05-08

## Status

Prototype pass 1 is complete: deterministic transition strips now build from
catalog material IDs and produce PBR outputs plus hard-cut comparison captures.

Full M2 is still **in progress** because the Godot `biome_tile_transition_review`
harness is currently part of the preexisting OpenTopo worker dirt. This pass
does not commit that harness. It gives M4 concrete transition assets and keeps
the commit boundary clean.

## Tool

`pipelines/textures/build_transition_strip.py`

Inputs:

- `world3/materials/catalog.json`
- Pair list as catalog IDs, e.g. `desert_sand:grassland_grass`

Outputs per pair:

- `world3/textures/transitions/<a>__<b>/albedo.png`
- `normal.png`
- `roughness.png`
- `height.png`
- `ao.png`
- `mask.png`
- `manifest.json`
- `world3/docs/captures/transitions/<a>__<b>_hard_vs_transition.png`

The builder uses a deterministic noisy ramp mask across a 6-tile strip. It
blends albedo, roughness, height, and AO linearly, and blends normals by
renormalizing the vector mix.

## Generated Pairs

| Pair | Role | Preview | Hard-edge albedo delta |
|------|------|---------|------------------------|
| `desert_sand` -> `grassland_grass` | Cross-biome, high style delta | `desert_sand__grassland_grass_hard_vs_transition.png` | 0.139652 |
| `scrub_sparse` -> `dry_wash` | OpenTopo neighbor pair | `scrub_sparse__dry_wash_hard_vs_transition.png` | 0.033954 |
| `tundra_moss` -> `temperate_forest_grass` | Cross-biome moderate | `tundra_moss__temperate_forest_grass_hard_vs_transition.png` | 0.287778 |
| `dry_wash` -> `desert_dry_brush` | Real -> procedural style bridge | `dry_wash__desert_dry_brush_hard_vs_transition.png` | 0.135151 |

Index: `world3/textures/transitions/index.json`

## Read

All four generated strips are visibly better than hard cuts as texture-sheet
prototypes. The noisy feathered band removes the instant seam and gives the
shader/M4 path real assets to consume.

Quality caveats:

- Cross-source transitions still need style normalization. `dry_wash` ->
  `desert_dry_brush` is usable as a workflow proof, but a production candidate
  would need color/roughness grading.
- `tundra_moss` -> `temperate_forest_grass` exposes the largest value/style
  gap. It is a good stress pair for M4, not a solved art direction.
- The current transition mask is a texture-space prototype. Runtime geography
  should eventually drive mask placement using slope, wetness, elevation,
  biome distance fields, and authored exceptions.

## Remaining M2 Work

- Integrate the generated strips into a Godot review scene without sweeping in
  unrelated OpenTopo worker files.
- Add numeric pair scoring beyond hard-edge albedo delta: hue delta, roughness
  delta, normal energy, and visible-frequency mismatch.
- Decide whether transition materials become first-class catalog entries or
  remain generated boundary assets referenced by biome-boundary rules.
