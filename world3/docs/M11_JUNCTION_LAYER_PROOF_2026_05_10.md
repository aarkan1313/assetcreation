# M11 Junction Layer Proof - 2026-05-10

## Status

Accepted as first M11 workflow evidence for three-way terrain junctions.

This is not production-final AAA terrain. It proves the junction method: three
terrain domains can meet through generated domain fields, runtime splat weights,
macro guidance, and feature/scatter masks without a hard visual corner.

## What Changed

M11 adds `world3/pipeline/build_m11_junction_layer_proof.py`.

The generator builds a source/grassland/canyon Y junction from:

- Gloss Mountain real-source scrub crop.
- `m8_grassland_grass_calm_v3` as grassland sidecar material.
- `desert_canyon_rock` as canyon PBR slot.
- Zion master-stack terrain texture as the canyon macro reference.

The runtime output is:

- `world3/textures/source_stack/m11_three_way_junction_proof/`
- `world3/toporeview/m11_three_way_junction_proof/`
- `world3/textures/wgv3/terrain_m11_three_way_junction.tres`
- `world3/scenes/review/source_stack_m11_junction_tour.tscn`

Capture evidence:

- `world3/docs/captures/review/m11_junction_layer_contact_sheet.png`
- `world3/docs/captures/review/source_stack_m11_junction_tour_topdown.png`
- `world3/docs/captures/review/source_stack_m11_junction_tour_iso.png`
- `world3/docs/captures/review/source_stack_m11_junction_tour_medium.png`
- `world3/docs/captures/review/source_stack_m11_junction_tour_close.png`

## Contract

The splat RGBA contract is:

- R: grassland weight
- G: junction soil weight
- B: canyon rock weight
- A: source scrub weight

The sidecar masks are:

- `source_scrub_domain.png`
- `grassland_domain.png`
- `canyon_domain.png`
- `junction_weight.png`
- `triple_core_weight.png`
- `shrub_carryover_mask.png`
- `dry_grass_density_mask.png`
- `soil_exposure_mask.png`
- `rock_cluster_mask.png`
- `wash_line_mask.png`
- `no_scatter_mask.png`

Scatter remains a workflow sidecar, not final art. The M11 tour defaults
scatter off because the placeholder low-poly scatter can distract from terrain
quality; press `S` to inspect scatter and `M` to inspect masks.

## Metrics

`m11_junction_layer_metrics.json` records:

- Height range: 53.51 m.
- Junction coverage over 0.25: 26.02%.
- Triple-core coverage over 0.25: 2.48%.
- Minimum dominant domain coverage: 31.27%.
- Splat sum max error: 2.38e-7.
- Mean weights: source 0.334, grass 0.315, soil 0.036, canyon 0.315.
- Macro guidance weight mean: 0.746.

The low soil mean is intentional. The earlier draft over-relied on neutral soil
and read as a muddy beige strip. The accepted version keeps the soil core as a
blend/support layer while preserving grass/canyon/source ownership.

## Visual Read

Pass:

- No hard visual corner at the three-way junction.
- Source scrub, grassland, and canyon branches are distinguishable in topdown,
  iso, medium, and close review.
- The canyon branch now survives gameplay distance because it uses the Zion
  master-stack macro reference instead of a flat procedural tan macro.
- Scatter/mask data exists and is deterministic, but does not pollute default
  validation captures.

Known limitations:

- Canyon branch macro is strong enough for workflow evidence, but the underlying
  canyon geometry is still a proof heightfield, not a production landform.
- Grassland material remains sidecar quality and needs the planned ComfyUI
  FLUX/Aura/SD bakeoff before promotion.
- Placeholder scatter assets are not production assets.
- M11 currently proves a representative Y junction, not the full corner library.

## Commands

Regenerate:

```powershell
python world3/pipeline/build_m11_junction_layer_proof.py
```

Capture with the visible renderer:

```powershell
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m11_junction_topdown.tscn'
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m11_junction_iso.tscn'
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m11_junction_medium.tscn'
& 'C:/Godot/Godot_v4.5-stable_win64.exe' --path 'D:/assets/world3' --single-window --disable-crash-handler --quit-after 240 --scene 'res://scenes/review/capture_source_stack_m11_junction_close.tscn'
```

Do not use `--headless` for screenshot captures in this project. Godot's dummy
display returns a null viewport texture for `HeadlessCapture.gd`.

## Next

M11 is ready to move from "first representative Y junction" to:

1. Four-way/corner junction proof using the same contract.
2. Debug view that overlays domain ownership, splat ownership, and mask layers in
   the live scene.
3. Replacement scatter asset pass after authored scrub/grass/rock assets exist.
4. M12 view-mode parity once M11 corner cases have at least one accepted proof.
