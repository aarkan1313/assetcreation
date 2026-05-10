# M10 Ecotone Layer Proof

Date: 2026-05-09

## Status

Accepted as M10 unlike-biome **workflow evidence** after the macro-guided
runtime layer pass.

Not production-final / AAA-closed. The remaining gaps are scatter/object
population, stronger real-source biome candidates, and a fuller gameplay-zoom
quality pass.

This pass responds to the failed unlike-biome strip attempt. The user correctly
flagged that the previous rendered result still read like a muted texture strip,
not a real biome transition. The correction is to move the proof from final RGB
blending toward runtime layer data.

## What Changed

Tool:

- `world3/pipeline/build_ecotone_layer_proof.py`

Runtime scene:

- `world3/scenes/review/source_stack_ecotone_layer_tour.tscn`
- `world3/scripts/EcotoneScatterOverlay.gd`

Key outputs:

- `world3/textures/source_stack/gloss_grassland_ecotone_layer_proof/layers/splat_weights_rgba.png`
- `world3/textures/source_stack/gloss_grassland_ecotone_layer_proof/layers/*_weight.png`
- `world3/textures/source_stack/gloss_grassland_ecotone_layer_proof/layers/*_mask.png`
- `world3/textures/source_stack/gloss_grassland_ecotone_layer_proof/source_macro_albedo.png`
- `world3/textures/source_stack/gloss_grassland_ecotone_layer_proof/source_macro_weight_mask.png`
- `world3/textures/source_stack/gloss_grassland_ecotone_layer_proof/layers/source_photo_payload.png`
- `world3/toporeview/gloss_grassland_ecotone_layer_proof/heightmap.png`
- `world3/textures/wgv3/terrain_ecotone_layer_gloss_grassland.tres`

The shader now receives runtime splat weights through `ChunkLoader` and
`terrain_splat_unified.gdshader` instead of relying only on a baked macro
preview.

## 2026-05-10 Scatter/Debug Pass

The existing feature masks are now used in the live review scene instead of
only appearing in the contact sheet.

Runtime additions:

- `EcotoneScatterOverlay.gd` samples masks in world space and places
  deterministic lightweight shrub, dry-grass, and rock instances.
- `S` toggles scatter visibility in the review scene.
- `M` toggles the mask-debug overlay.
- Topdown automatically hides 3D scatter so map/readability captures do not
  turn into speckle fields. Iso, medium, and close 3D keep scatter visible.

Current deterministic scatter counts:

- shrubs: `333`
- dry-grass clumps: `205`
- rocks: `30`

This is still prototype scatter. The important workflow step is that object
breakup now comes from the same masks emitted by the ecotone pipeline. It is
not hand-placed decoration and should be replaceable with higher-quality
vegetation/rock assets later.

## Difference From M2 Texture-To-Texture

M2 texture-to-texture transition:

- builds a generated transition strip from two source materials;
- uses a noisy 2D ramp in texture space;
- outputs final PBR strip maps;
- is useful for material-pair QA and simple boundary assets.

This M10 ecotone pass:

- builds a continuous height field for the joined terrain;
- emits biome A, biome B, and ecotone fields;
- emits normalized material weights for source scrub, grassland, ecotone soil,
  and rock exposure;
- emits future scatter masks for shrub carryover, grass density, soil exposure,
  rock clusters, wash lines, and no-scatter regions;
- binds material weights to the runtime splat shader;
- keeps the source macro as a masked source-photo payload, not as the final
  transition itself.

That is the correct workflow direction for terrain systems. It is workflow
evidence, not a finished production art result.

## Runtime Fixes Found

Generated PNGs should not be referenced directly as `ExtResource` entries in
the generated `.tres` material. Godot can fail to load brand-new PNGs that have
not gone through import metadata. The material now stores shader parameters and
existing imported material resources; generated macro/mask/splat textures are
bound at runtime with `RuntimeImageCache`.

The source macro payload is now separated from the derived macro preview:

- `source_macro_albedo.png`: layer-derived macro guidance used by the shader;
- `layers/source_photo_payload.png`: source-photo-only payload retained for
  audit/debug;
- `layers/derived_macro_preview.png`: the macro guidance preview saved beside
  the layer outputs.

The correction is deliberately not "no RGB macro." Terrain needs broad macro
landcover/photo guidance at topdown and iso distance. The important split is
that macro guidance is paired with runtime splat/material weights and masks, so
it does not become the only transition data.

The latest pass:

- reduces the ecotone width from the overly broad muddy band;
- increases irregular boundary jitter;
- uses macro guidance across the whole ecotone to suppress repeated grass-tile
  bands;
- sharpens runtime splat ownership;
- increases ecotone soil/rock participation enough to keep the boundary from
  becoming a plain 50/50 albedo average;
- centers capture progress so screenshots land in the representative middle of
  each camera sweep.

## Current Visual Read

Accepted workflow read:

- no height cliff;
- no invalid-data wall;
- runtime splat weights are actually bound;
- source macro is now broad guidance, not the sole transition contract;
- the hard straight-line failure is removed;
- the grassland side no longer reads primarily as repeated tile bands;
- feature masks now drive visible scatter in medium/close views;
- topdown remains clean because scatter is LOD-hidden there;
- topdown, iso, medium, and close captures preserve both biome identities;
- the transition reads as a believable proof-of-workflow ecotone, not merely a
  debug strip.

Still not production-final:

- scatter uses simple generated placeholder meshes, not authored production
  vegetation/rock assets;
- the right-side biome is still a procedural/Comfy material macro, not a true
  adjacent real-source terrain pull;
- the source-photo to PBR-material handoff is still visible in close play;
- close gameplay needs better detail/normal tuning and object breakup before
  AAA visual closure.

## Metrics

Latest generated metrics:

- height range: `74.45 m`
- boundary step p95: `0.030 m`
- ecotone coverage over `0.25`: `19.9%`
- boundary x std: `132.2 px`
- mean local width: `260.7 px`
- max material-weight sum error: `< 0.000001`
- source macro weight mean: `0.305`
- macro guidance weight mean: `0.740`

The geometry and data-layer metrics are sane. The latest visual pass is good
enough to promote as workflow evidence while keeping production caveats active.

## Next Work

1. Replace placeholder scatter meshes with authored vegetation/rock assets and
   add distance/scale bands for gameplay cameras.
2. Add a runtime/debug view for splat weights and biome weights, not only
   scatter masks.
3. Re-run with better grassland material candidates from the ComfyUI workflow.
4. Prefer real adjacent source data for production-like proofs whenever the data
   catalog has suitable neighboring tiles.
5. Carry the macro-guidance + runtime-splat split into M11 junctions instead of
   reverting to strip-only transition assets.

## Commands

Build:

```powershell
python world3/pipeline/build_ecotone_layer_proof.py
```

Review captures:

```powershell
$godot = 'C:/Godot/Godot_v4.5-stable_win64.exe'
$scenes = @(
  'res://scenes/review/capture_source_stack_ecotone_layer_topdown.tscn',
  'res://scenes/review/capture_source_stack_ecotone_layer_iso.tscn',
  'res://scenes/review/capture_source_stack_ecotone_layer_medium.tscn',
  'res://scenes/review/capture_source_stack_ecotone_layer_close.tscn'
)
foreach ($scene in $scenes) {
  $args = @('--path', 'D:/assets/world3', '--single-window', '--disable-crash-handler', '--scene', $scene)
  $p = Start-Process -FilePath $godot -ArgumentList $args -Wait -PassThru
  Write-Output "$scene exit=$($p.ExitCode)"
}
```
