# M11 Four-Way Corner Proof - 2026-05-10

## Status

Accepted M11 four-way/corner workflow proof.

Live validation result, 2026-05-10: accepted as "super solid" workflow evidence.

This extends the accepted three-way M11 contract to four explicit terrain
domains meeting in one generated corner. It is workflow evidence, not
production-final art.

## What Changed

Added `world3/pipeline/build_m11_fourway_corner_proof.py`.

The generator builds one continuous height/macro/splat surface from:

- Photoreal Gloss Mountain source scrub.
- `m8_grassland_grass_calm_v3` as the current "our texture" sidecar.
- A staged controlled fantasy lava/basalt material from
  `world/textures/library/biome_lava_field`.
- `desert_canyon_rock` plus the Zion master-stack macro reference as the fourth
  grounded terrain domain.

Runtime outputs:

- `world3/textures/source_stack/m11_fourway_corner_proof/`
- `world3/toporeview/m11_fourway_corner_proof/`
- `world3/textures/wgv3/fantasy_lava_field_controlled/`
- `world3/materials/catalog_m11_fourway_generated.json`
- `world3/textures/wgv3/terrain_m11_fourway_corner.tres`
- `world3/scenes/review/source_stack_m11_fourway_corner_tour.tscn`

Capture evidence:

- `world3/docs/captures/review/m11_fourway_corner_contact_sheet.png`
- `world3/docs/captures/review/source_stack_m11_fourway_corner_tour_topdown.png`
- `world3/docs/captures/review/source_stack_m11_fourway_corner_tour_iso.png`
- `world3/docs/captures/review/source_stack_m11_fourway_corner_tour_medium.png`
- `world3/docs/captures/review/source_stack_m11_fourway_corner_tour_close.png`

## Contract

The four-way splat RGBA contract is:

- R: grassland weight.
- G: fantasy lava/basalt weight.
- B: canyon rock weight.
- A: photoreal source scrub weight.

The generator also emits sidecar masks for review and future scatter:

- `grassland_domain.png`
- `fantasy_lava_domain.png`
- `canyon_domain.png`
- `source_scrub_domain.png`
- `junction_weight.png`
- `quad_core_weight.png`
- `cross_wash_weight.png`
- `shrub_carryover_mask.png`
- `dry_grass_density_mask.png`
- `soil_exposure_mask.png`
- `rock_cluster_mask.png`
- `fantasy_crack_mask.png`
- `wash_line_mask.png`
- `no_scatter_mask.png`

## Visual Read

Pass:

- No hard X-shaped strip in the current topdown/iso/3D captures.
- The center is a broad warped mixed-ownership field rather than four rectangles
  meeting at one pixel.
- Height joins are smooth enough for workflow evidence; junction gradient p95 is
  `0.317 m/px`.
- The fantasy quadrant remains readable without using neon mana/ice material.

Known limitations:

- The fantasy lava domain is intentionally controlled, but still darker than the
  other three domains. This is accepted as a stress case, not a promotion.
- The grassland material is still sidecar quality and needs the planned
  FLUX/Aura/SD batch-review workflow before canonical promotion.
- The proof uses one representative four-way layout, not a complete junction
  library or automatic biome-neighbor solver.
- Scatter masks exist, but scatter meshes are still placeholder assets and
  default off in the tour.

## Metrics

`m11_fourway_corner_metrics.json` records:

- Height range: `53.82 m`.
- Junction coverage over 0.25: `65.97%`.
- Quad-core coverage over 0.25: `11.36%`.
- Minimum dominant domain coverage: `16.39%`.
- Splat sum max error: `2.38e-7`.
- Mean weights: grass `0.236`, fantasy `0.280`, canyon `0.230`, source `0.254`.
- Macro guidance weight mean: `0.760`.

## Commands

Regenerate:

```powershell
python world3/pipeline/build_m11_fourway_corner_proof.py
```

Import new material PNGs after regeneration:

```powershell
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --quiet --headless --editor --import
```

Capture with the visible renderer:

```powershell
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m11_fourway_corner_topdown.tscn'
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m11_fourway_corner_iso.tscn'
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m11_fourway_corner_medium.tscn'
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m11_fourway_corner_close.tscn'
```

Do not use `--headless` for screenshot captures; use it only for import.

## Next

This closes the first four-way M11 proof. The remaining M11 work is the junction
case matrix in `M11_JUNCTION_CASE_MATRIX_2026_05_10.md`; then roadmap work moves
to M12 view-mode parity.
