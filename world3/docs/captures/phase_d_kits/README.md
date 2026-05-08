# Phase D Region Gallery — All 5 Kits Visible (2026-05-07)

Captures from `world3/scenes/region_gallery.tscn` covering 7 regions across
all 5 biome kits. Each region has `iso.png` + `topdown.png`.

## Kit binding fix (2026-05-07)

Phase D's first commit (`ca171e9`) updated `world3/jobs/biome_kits.json` to
the new `wgv3_tf_*` and `wgv3_gl_*` texture IDs but **did not** regenerate
the `terrain_blend_temperate_forest.tres` and `terrain_blend_grassland.tres`
materials. They still pointed to alpine-default texture slots. As a result
chaparral regions rendered with snow caps and grassland regions rendered as
alpine grass.

Fix: `pipelines/textures/deploy_kit_to_world3.py` deploys library textures
into per-kit slot dirs and rewrites the `.tres` to point at them.

## Region → Kit mapping in this set

| Region | Kit | iso.png reads as |
|--------|-----|------------------|
| `tcf_pnw_cascades_usa` | alpine | grass + rock + snow caps (correct) |
| `tbm_appalachians_usa` | alpine | grass + rock + snow caps (correct) |
| `des_mojave_usa` | desert | sand-tan everywhere (correct) |
| `tun_arctic_alaska` | tundra | muted moss + frost patches (correct) |
| `med_california_chaparral` | temperate_forest | brown/tan rocky chaparral, no snow (fixed) |
| `mgs_tibetan_plateau` | grassland | tall_grass yellow (fixed binding; tuning open) |
| `tgs_serengeti_tanzania` | grassland | tall_grass yellow (fixed binding; tuning open) |

## Quality observations

- **alpine, desert, tundra**: render as designed.
- **temperate_forest**: chaparral renders correctly — leaf litter / loamy
  soil / rock visible, no snow. This is the Phase D bug-fix payoff.
- **grassland**: kit-binding fixed but the rendered surface is a near-uniform
  tall_grass. Slope-threshold / height-band tuning didn't surface enough
  rock/dirt variation on Tibet (4500m plateau) or Serengeti (low relief).
  Open tuning task: lower `slope_threshold` or pull `h_grass_dirt` down so
  more rock/dirt shows through on slopes.

## Re-running

```powershell
# 1) Deploy any new kits (rebuilds .tres + copies textures into world3/textures/wgv3/)
python pipelines/textures/deploy_kit_to_world3.py --kit temperate_forest
python pipelines/textures/deploy_kit_to_world3.py --kit grassland

# 2) Have Godot re-import the new textures (one-time after deploy)
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet --headless --editor --import

# 3) Render gallery
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet res://scenes/region_gallery.tscn
```

Captures land in `D:/tmp/world3_screens/regions/<region_id>/{iso,topdown}.png`.
