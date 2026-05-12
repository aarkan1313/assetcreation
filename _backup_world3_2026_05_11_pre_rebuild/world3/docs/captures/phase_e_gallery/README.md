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
| `mgs_tibetan_plateau` | grassland | uniform yellow grass (by design — see note) | uniform pale yellow |
| `tgs_serengeti_tanzania` | grassland | uniform yellow grass (by design) | uniform pale yellow |

### Grassland kit design note (2026-05-07)

The grassland kit's loose height bands (`h_grass_dirt=0.4`,
`h_dirt_rockdark=0.75`, `h_rockdark_snow=0.95`) and high
`slope_threshold=0.5` are intentional. Real Serengeti and Tibetan
plateau imagery is biologically near-uniform tall_grass with rare
rocky outcrops; tightening these bands triggers different slot
textures but they all read yellow-tan (tall_grass / dry_thatch /
hardpan_soil are all warm-toned), giving fake variation that doesn't
match real biome reference. We tested tighter bands (alpine-cadence
0.2/0.5/0.8 + slope 0.35); the result was *more* uniform-looking
because all 5 grassland slots share a yellow color family.

If a specific grassland landform needs visible rocky variation
(East African kopjes, Tibetan buttes), the right fix is **either**:
(1) a region-specific kit override, or (2) regenerating
`wgv3_gl_grass_rock` and `wgv3_gl_weathered_stone` with darker /
greyer prompts. Don't widen the kit's bands — that breaks the
biome's faithful reading on the four other grassland regions.

This is documented as decision-locked in `biome_kits.json` (grassland
`height_bands._comment` field).

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
