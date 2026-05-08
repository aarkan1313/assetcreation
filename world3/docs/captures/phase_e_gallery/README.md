# Phase E — Region Gallery with Per-Mode Material Swap (2026-05-07)

This supersedes `world3/docs/captures/phase_d_kits/`. Same regions, same
kits, but `RegionGalleryCapture.gd` now binds the iso-tuned material
(`terrain_blend_<kit>_iso.tres`) for the iso shot and the topdown-tuned
material (`terrain_blend_<kit>_topdown.tres`) for the topdown shot.

The visible difference: topdown captures use the topdown-tuned shader
params (low normal_strength, high macro_value, low world_uv_scale, soft
band transitions) so terrain reads as color-blocked regions instead of
detailed surface relief. Iso captures retain the original mid-detail
look.

## Per-region readings

| Region | Kit | iso | topdown |
|--------|-----|-----|---------|
| `tcf_pnw_cascades_usa` | alpine | grass + rock + snow caps, sharp normals | green/brown/white color-blocked terrain, muted normals |
| `tbm_appalachians_usa` | alpine | similar | similar (forested ridges read as grass blocks) |
| `des_mojave_usa` | desert | sand-tan with directional shadows | smoothed sand color, lower contrast |
| `tun_arctic_alaska` | tundra | moss + frost patches | flatter green/white blocks |
| `med_california_chaparral` | temperate_forest | brown rocky chaparral | flat brown color blocks |
| `mgs_tibetan_plateau` | grassland | uniform yellow grass | uniform pale yellow |
| `tgs_serengeti_tanzania` | grassland | uniform yellow grass | uniform pale yellow |

## Implementation note: elev_min/range push

When `RegionGalleryCapture` swaps `material_override` between iso/topdown
shots, the new ShaderMaterial doesn't have `elev_min_m` / `elev_range_m`
set (those were pushed into the prior material by `Terrain.rebuild()`).
The gallery now reads the bundle's `meta.json` upfront and re-pushes those
uniforms into each newly-bound material in `_bind_material()`. Without
this fix, the height-band thresholds would compute against `[0..1]` instead
of real elevation in meters, and the topdown's lower `h_band_softness`
would push the snow band off-screen entirely.

## Re-running

```powershell
# 1) Emit / refresh per-mode .tres if shader-param tuning changed
python pipelines/textures/emit_per_mode_materials.py

# 2) Godot import
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet --headless --editor --import

# 3) Gallery
& "C:/Godot/Godot_v4.5-stable_win64.exe" --path world3 --quiet res://scenes/region_gallery.tscn

# Output lands in D:/tmp/world3_screens/regions/<region>/{iso,topdown}.png
```
