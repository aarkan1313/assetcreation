# M2 Transition Material Prototype

Date: 2026-05-08

## Status

Prototype pass 3 is complete: deterministic transition strips now build from
catalog material IDs and produce PBR outputs, hard-cut comparison captures,
numeric score hints, rule-level tuning, and a clean Godot review scene.
User visual review on 2026-05-08: transitions read as promising/good; the
remaining concern is source texture noise in grass/leaves, not the transition
workflow.

M2 workflow exit is met. The asset-contract decision is closed: transition
strips are generated boundary assets referenced by
`world3/jobs/biome_transition_rules.json`, not base material catalog entries.
The remaining normal-energy mismatch on two stress pairs is a known M4 shader
and source-material risk, not a blocker for starting M4.

## Tool

`pipelines/textures/build_transition_strip.py`

Inputs:

- `world3/materials/catalog.json`
- Optional rule file: `world3/jobs/biome_transition_rules.json`
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

Each manifest now also carries score hints:

- source hue/value/saturation deltas
- roughness mean absolute delta
- normal energy and normal mean absolute deltas
- visible-frequency mismatch
- hard-edge vs transition-center albedo delta improvement

These are review signals, not automatic pass/fail gates.

Rule files can provide per-pair tuning:

- transition width in texture repeats
- mask noise strength
- albedo mean/std matching
- transition-local albedo frequency dampening
- roughness mean/std matching
- normal-energy dampening

## Godot Review Scene

- Scene: `world3/scenes/capture_phase_m2/transition_strip_review.tscn`
- Script: `world3/scripts/TransitionStripReview.gd`
- Capture: `world3/docs/captures/transitions/godot_transition_strip_review.png`

The scene reads `world3/textures/transitions/index.json`, shows each hard cut
beside its generated transition strip, and displays the manifest score summary.
It is separate from the dirty OpenTopo review harness so the commit boundary
stays clean.

## Generated Pairs

| Pair | Role | Preview | Hard-edge albedo delta |
|------|------|---------|------------------------|
| `desert_sand` -> `grassland_grass` | Cross-biome, high style delta | `desert_sand__grassland_grass_hard_vs_transition.png` | 0.139652 |
| `scrub_sparse` -> `dry_wash` | OpenTopo neighbor pair | `scrub_sparse__dry_wash_hard_vs_transition.png` | 0.033954 |
| `tundra_moss` -> `temperate_forest_grass` | Cross-biome moderate | `tundra_moss__temperate_forest_grass_hard_vs_transition.png` | 0.287778 |
| `dry_wash` -> `desert_dry_brush` | Real -> procedural style bridge | `dry_wash__desert_dry_brush_hard_vs_transition.png` | 0.135151 |

Index: `world3/textures/transitions/index.json`
Rule contract: `world3/jobs/biome_transition_rules.json`
Contract note: `world3/docs/M2_BOUNDARY_TRANSITION_CONTRACT.md`

## Tuned Score Read

| Pair | Width | Hard edge | Tuned center | Improvement | Raw -> tuned key deltas | Remaining hints |
|------|-------|-----------|--------------|-------------|-------------------------|-----------------|
| `desert_sand` -> `grassland_grass` | 8 | 0.139652 | 0.022570 | 83.8% | freq 0.099164 -> 0.034751; rough 0.336034 -> 0.151638 | none |
| `scrub_sparse` -> `dry_wash` | 6 | 0.033954 | 0.008808 | 74.1% | unchanged control pair | none |
| `tundra_moss` -> `temperate_forest_grass` | 8 | 0.287778 | 0.032655 | 88.7% | rough 0.494944 -> 0.148489; normal 0.611044 -> 0.383937 | normal energy |
| `dry_wash` -> `desert_dry_brush` | 8 | 0.135151 | 0.014219 | 89.5% | rough 0.861734 -> 0.129260; normal 0.544815 -> 0.319896 | normal energy |

Read: the transition strips reduce the immediate center discontinuity on all
four pairs, including the hard stress cases. The tuned pass clears the
roughness/frequency flags on all but the deliberately untouched control pair.
Normal-energy mismatch remains visible on the two hardest cross-source pairs;
that should feed M4 shader design and source-material QA rather than be hidden.

## Read

All four generated strips are visibly better than hard cuts as texture-sheet
prototypes. The noisy feathered band removes the instant seam and gives the
shader/M4 path real assets to consume. The transition method passes the current
workflow-read check.

Quality caveats:

- Cross-source transitions still need style normalization. `dry_wash` ->
  `desert_dry_brush` is usable as a workflow proof, but a production candidate
  would need color/roughness grading.
- `tundra_moss` -> `temperate_forest_grass` exposes the largest value/style
  gap. It is a good stress pair for M4, not a solved art direction.
- Grass/leaves in the generated source textures are too noisy for production
  at current review scale. Treat that as a material-generation/prompt/QA issue,
  not a transition workflow failure.
- The current transition mask is a texture-space prototype. Runtime geography
  should eventually drive mask placement using slope, wetness, elevation,
  biome distance fields, and authored exceptions.

## M4 Handoff

- Use `world3/jobs/biome_transition_rules.json` as the boundary input contract.
- Keep `raw_scores` in manifests as source-material QA signals.
- Use tuned `scores` as the transition-asset read.
- M4 pass 1/2 followed this: normal splat blending and the chunk material
  contract landed first. Explicit boundary asset sampling remains reserved for
  when boundary-space UVs exist.
