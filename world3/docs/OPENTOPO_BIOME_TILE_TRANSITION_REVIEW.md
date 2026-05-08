# OpenTopo Biome Tile Transition Review

Date: 2026-05-08

This pass adds a hard-adjacency review scene for unlike ground tiles. It compares
two families in the same Godot viewport:

- OpenTopo photoreal, source-real material candidates from Guadalupe Cypress.
- Regular generated `wgv3` biome-kit materials.

The goal is not to make the borders look good yet. The goal is to make bad
borders obvious before we build blend masks, transition strips, or runtime biome
shaders.

## Assets

Interactive scene:

```text
D:/assets/world3/toporeview/biome_tile_transition_review.tscn
```

Capture wrappers:

```text
D:/assets/world3/toporeview/capture_biome_tile_transition_review.tscn
D:/assets/world3/toporeview/capture_biome_tile_transition_opentopo.tscn
D:/assets/world3/toporeview/capture_biome_tile_transition_regular.tscn
```

Real Godot viewport captures:

```text
D:/assets/world3/docs/captures/opentopo/godot_biome_tile_transition_review.png
D:/assets/world3/docs/captures/opentopo/godot_biome_tile_transition_opentopo.png
D:/assets/world3/docs/captures/opentopo/godot_biome_tile_transition_regular.png
```

Primary script:

```text
D:/assets/world3/toporeview/BiomeTileTransitionReview.gd
```

## Inputs

OpenTopo material index:

```text
D:/assets/world3/opentopo/processed/textures/Guadalupe_Cypress_finished_materials_index.json
```

OpenTopo classes currently reviewed:

```text
scrub_sparse
scrub_dense
rocky_slope
dry_wash
bright_rock
bare_soil
```

Regular generated rows currently reviewed:

```text
Base / alpine:       snow, grass, dirt, rock_light, rock_dark
Desert:              desert_sand, desert_salt_pan, desert_dry_brush, desert_canyon_rock, desert_dark_rock
Grassland:           grassland_grass, grassland_dirt, grassland_rock_light, grassland_rock_dark, grassland_snow
Temperate forest:    temperate_forest_grass, temperate_forest_dirt, temperate_forest_rock_light, temperate_forest_rock_dark, temperate_forest_snow
Tundra:              tundra_moss, tundra_lichen, tundra_frost_rock, tundra_dark_rock, tundra_ice
Cross-biome chain:   tundra_ice, tundra_moss, snow, grassland_grass, temperate_forest_grass, forest_floor, desert_sand, desert_canyon_rock
```

## Controls

```text
RMB + mouse       look
W/A/S/D           move
Space / Ctrl      up / down
Shift             fast
1 or R            overview
2                 OpenTopo close strip
3                 regular biome-kit close rows
H                 show/hide HUD
```

## Capture Command

Use normal Godot with the capture scene as the trailing argument:

```powershell
$scenes = @(
  "res://toporeview/capture_biome_tile_transition_review.tscn",
  "res://toporeview/capture_biome_tile_transition_opentopo.tscn",
  "res://toporeview/capture_biome_tile_transition_regular.tscn"
)
foreach ($scene in $scenes) {
  $args = @("--path", "D:/assets/world3", $scene)
  $p = Start-Process -FilePath "C:/Godot/Godot_v4.5-stable_win64.exe" -ArgumentList $args -WindowStyle Hidden -Wait -PassThru
  "$scene EXIT=$($p.ExitCode)"
}
```

Validation on 2026-05-08: all three capture scenes exited `0` and wrote real
viewport PNGs.

## Findings

Hard adjacency is too harsh for final biome boundaries. That is expected and is
the reason this review exists.

OpenTopo photoreal materials are more naturally cohesive than the generated
sets because they come from one real place and one lighting/capture context.
Even so, hard cuts between `scrub_*`, `rocky_slope`, `dry_wash`, and
`bright_rock` read as artificial boundaries. They need transition masks, not
direct tile-to-tile placement.

The regular generated rows expose stronger style differences. Desert is the
most internally cohesive. Base/alpine has a large grass-to-rock style jump.
Grassland and tundra carry strong noisy motifs that can read as pattern fields
at the wrong scale. Temperate forest and tundra are especially sensitive to
scale because leafy/mossy details become too literal when enlarged.

The cross-biome chain is useful as a failure view. Tundra, snow, grassland,
forest, and desert can sit in one atlas, but hard borders between them should
not be considered a shippable transition. The runtime or preprocessing pipeline
needs explicit transition zones.

OpenTopo photoreal and regular generated textures should not be mixed raw in
one terrain without a style bridge. The safe options are:

- Use OpenTopo as real macro color/reference and generated materials as local
  detail.
- Color-grade generated kits toward the OpenTopo stack before adjacency review.
- Build source-real OpenTopo materials for the same biome family and avoid
  mixing source-real and generated rows at the same visual frequency.

## Recommended Transition Pipeline

Use four stages:

1. **Hard adjacency QA**: this scene. No blending, no gaps, no shader rescue.
2. **Palette/value normalization**: match brightness, saturation, and roughness
   family inside a kit before transition work.
3. **Transition bands**: generate or author 2-8 tile wide bands between unlike
   biome families using noisy masks, slope/wetness/elevation rules, and
   optional edge materials.
4. **Runtime blend shader**: blend macro color, meso tile variants, and micro
   detail separately. Do not expect one albedo tile to solve all scales.

The important production rule: unlike biome transitions should be geography or
mask driven. A desert-to-forest change should usually pass through scrub, dry
grass, exposed soil, or rocky transition material rather than touch directly.

## Current Status

Implemented:

- OpenTopo photoreal hard-adjacency strip.
- Regular biome-kit hard-adjacency rows.
- Cross-biome chain.
- Interactive Godot controls.
- Three real viewport captures.

Not implemented yet:

- Automated seam/contrast metric between unlike materials.
- Generated transition strips.
- Biome-boundary masks.
- Runtime shader blending for unlike biomes.
- Mixed OpenTopo/generated style bridge.

## Next Work

1. Add a transition-material builder that takes two material ids and writes a
   noisy blended strip or atlas.
2. Add numeric pair scoring: edge luminance delta, hue delta, roughness delta,
   and normal-energy delta.
3. Add lower regular close capture or scroll presets for all five rows and the
   cross-biome chain.
4. Test a real OpenTopo biome transition from a new AOI with color plus canopy
   or vegetation signal, then compare it against the generated kit transitions.
