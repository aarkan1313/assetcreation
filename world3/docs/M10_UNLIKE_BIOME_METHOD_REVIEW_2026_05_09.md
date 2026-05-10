# M10 Unlike-Biome Method Review

Date: 2026-05-09

## Status

The first Gloss-to-grassland unlike-biome attempt is **not accepted** as M10
visual evidence.

It is useful negative evidence:

- height and mesh continuity can be preserved;
- the current macro bridge can avoid walls and boxes;
- but the visual result reads as a muted brown/green strip, not a real biome
  transition.

Do not promote `source_stack_unlike_biome_tour.tscn` until the workflow is
rebuilt around layer/mask/ecotone data.

## Root Cause

The current seam solver is still mostly a source-to-source bridge. That works
for same-family or compatible arid terrain because the target is continuity.
Unlike-biome terrain has a different target: a believable ecotone.

The failed result came from treating the problem as:

```text
left macro color + right macro color + smoothing = transition
```

That averages biome identity away. A convincing unlike-biome transition needs:

- preserved palette on both sides;
- an irregular boundary, not a uniform strip;
- material weights, not only final RGB;
- slope/height/drainage-aware placement;
- feature carryover such as scrub islands, soil exposure, wash traces, rock,
  dry grass, and vegetation density;
- later scatter masks for shrubs/grass/rocks, even if no meshes are spawned yet.

## Research Notes

Houdini heightfields model terrain as stacked data layers. Height and masks are
separate fields, and terrain operations are controlled through masks. This maps
directly to what world3 needs: height, biome/material weights, erosion masks,
flow/debris/sediment, vegetation density, and source validity should remain
separate until runtime or bake output.

Houdini texture-layer workflows also treat terrain texturing as layer/mask
composition. Layers such as debris, flow, sediment, water, and bedrock can drive
different visual channels. That argues against baking the whole ecotone into one
flattened macro image too early.

Unreal landscape materials use layer blending and height/weight inputs for
terrain material composition. The useful lesson is not "copy Unreal", but that
engine-facing terrain should carry material-layer weights and valid fallback
weights, not an all-or-nothing bitmap.

AutoBiomes is the closest research match for this stage. It treats multi-biome
terrain as a pipeline: biome distribution, border distortion, biome-specific DEM
detail blending, and asset placement. Its biome transition section is especially
relevant: biome borders are distorted with fractal noise, then biome-specific
DEM/detail weights are blended with a kernel. That is closer to what we need
than our current straight integration band.

WorldBrush is also relevant because it learns and applies distributions of
world features such as vegetation, rocks, and grass, constrained by terrain
properties. This supports treating biome transitions as feature-distribution
problems, not just color interpolation.

## Revised Workflow

### U0 - Compatibility Class

Classify the transition before solving:

- same-source diagnostic;
- compatible real-to-real;
- real-to-procedural same biome;
- unlike-biome/ecotone;
- hard biome break where a cliff, river, road, ridge, shore, canyon wall, or
  authored feature should separate the regions.

Unlike-biome transitions should not use the same macro bridge defaults as
real-to-real seams.

### U1 - Ecotone Field

Generate a world-space ecotone field:

- noisy, row-varying boundary center;
- variable transition width;
- islands/fingers from both sides;
- feature masks derived from slope, curvature, height, source vegetation, and
  source soil/rock exposure;
- no forced global color match unless it is a compatible same-biome case.

Output required:

- `biome_a_weight`;
- `biome_b_weight`;
- `ecotone_weight`;
- optional `feature_carryover_mask`;
- optional `vegetation_density_mask`;
- optional `soil_exposure_mask`.

### U2 - Height And Landform

Height must remain solved separately from color:

- preserve edge continuity;
- avoid ramps that read as a strip;
- blend or synthesize biome-specific detail only where the ecotone field allows
  it;
- optionally run erosion/noise/detail after the combined field, not before.

### U3 - Material Weights

Emit material weights, not just an RGB macro:

- source scrub/soil/rock weights;
- grassland/hardpan/straw weights;
- ecotone dust/soil weights;
- normalized weights with no all-zero material region.

The final macro preview can still be baked for review, but it must be derived
from the material weights and masks, not used as the only transition data.

### U4 - Feature And Scatter Masks

Even before full scatter systems, the proof should produce masks for:

- shrub/tree carryover;
- dry grass/straw density;
- exposed soil;
- rock clusters;
- wash/drainage lines;
- no-scatter zones near sharp slopes or invalid source data.

This is essential for AAA direction because a biome transition without object
distribution will always look like a painted texture.

### U5 - Runtime Review

The review scene should be able to toggle:

- baked macro preview;
- material-weight debug;
- ecotone field debug;
- vegetation/scatter mask debug;
- height-only lighting;
- topdown, iso, medium, close camera bands.

### U6 - Acceptance Gate

Unlike-biome evidence fails if:

- it reads as one uniform blended strip;
- either biome loses its palette identity;
- the transition is a straight vertical/horizontal band;
- grass/scrub/rock features stop exactly at the band edge;
- close view has no material/detail variation;
- medium/iso view shows a synthetic stripe.

Unlike-biome evidence can pass as workflow evidence if:

- height is continuous;
- both biome identities remain readable;
- the boundary is irregular and feature-driven;
- material weights exist and can be inspected;
- at least one feature/scatter mask exists even if meshes are deferred.

## 2026-05-09 Runtime Layer Proof Update

The first layer-based correction now exists:

- `world3/pipeline/build_ecotone_layer_proof.py`
- `world3/scenes/review/source_stack_ecotone_layer_tour.tscn`
- `world3/docs/M10_ECOTONE_LAYER_PROOF_2026_05_09.md`

This is materially different from the rejected RGB strip attempt. It emits
runtime splat weights, biome/ecotone fields, feature masks, a continuous
heightmap, and a masked source-photo payload. The generated material relies on
the existing `terrain_splat_unified.gdshader` splat path, and generated PNGs are
loaded through `RuntimeImageCache` instead of `.tres` `ExtResource` references.

Current read after the macro-guided runtime layer pass: accepted as M10
unlike-biome workflow evidence, not production-final visual closure. The latest
captures remove the hard straight-line failure, keep both biome identities
readable, suppress the repeated grass-tile problem, and use runtime splat
weights plus macro guidance rather than an RGB strip alone. Remaining work is
explicit debug views, scatter mask population, better grassland source
candidates, and a fuller gameplay-zoom quality pass.

## Immediate Decision

Pause M10 unlike-biome promotion.

Keep the original RGB-strip attempt as local negative evidence only. Promote the
new ecotone-layer proof as workflow evidence, with production caveats active.

## Sources

- Houdini heightfield terrain docs:
  https://www.sidefx.com/docs/houdini/model/heightfields
- Houdini texture layers:
  https://www.sidefx.com/docs/houdini/heightfields/texturelayers.html
- Unreal Landscape Material Expressions:
  https://dev.epicgames.com/documentation/en-us/unreal-engine/landscape-material-expressions-in-unreal-engine
- Unreal Layered Materials:
  https://dev.epicgames.com/documentation/en-us/unreal-engine/layering-materials-in-unreal-engine
- AutoBiomes: procedural generation of multi-biome landscapes:
  https://link.springer.com/article/10.1007/s00371-020-01920-7
- WorldBrush: Interactive Example-Based Synthesis of Procedural Virtual Worlds:
  https://www.cs.purdue.edu/cgvlab/www/publications/Emilien15ToG/
