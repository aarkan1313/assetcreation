# Props Pipeline

**Status:** v2+ working. The local procedural route is production-usable for scatter and scene props; the new material-binding pass gives those props shared AAA PBR materials from `world/textures/library`. AI hero routes are scaffolded but runtime-gated.

## Files

| File | Role |
|---|---|
| [proc_generate.py](proc_generate.py) | Blender-headless procedural prop generator. 13 kinds; writes `prop_asset.v1`. |
| [variation_sweep.py](variation_sweep.py) | `prop_sweep.v1` batch runner for deterministic recipe variants. |
| [lod_chain.py](lod_chain.py) | Blender DECIMATE COLLAPSE LOD ladder authoring. |
| [collision_decompose.py](collision_decompose.py) | CoACD convex hull decomposition for scene/hero props. |
| [billboard_bake.py](billboard_bake.py) | Sprite3D billboard/impostor bake. |
| [material_lod.py](material_lod.py) | Far-distance color atlas for procedural kit LODs. |
| [pbr_material_bind.py](pbr_material_bind.py) | CPU AAA-PBR binding: maps prop material slots to existing texture sets. |
| [export_godot.py](export_godot.py) | Godot 4.5 HLOD scene export, collision, MultiMesh templates, and PBR material binder resources. |
| [trellis2_route.py](trellis2_route.py) | Build-only local Trellis2 image-to-3D route. CPU dry-run by default; CUDA gated. |
| [meshy_route.py](meshy_route.py) | Meshy hero-prop route. Dry-run by default; paid cloud call gated by env authorization. |
| [validate_props.py](validate_props.py) | Prop contract validator over `world/props/library/*`. |
| [BLOCKERS_AI_ROUTE.md](BLOCKERS_AI_ROUTE.md) | AI route blockers and enable steps. |

## Quickstart

```powershell
# Validate current library
python pipelines\props\validate_props.py

# Bind existing AAA texture sets to all mesh props
python pipelines\props\pbr_material_bind.py --all

# Export self-contained Godot props folder with HLOD + PBR binder
python pipelines\props\export_godot.py --all
```

Drop `world/props/godot/` into Godot at `res://props/`. Each prop scene loads its LOD GLBs and applies `res://props/_materials/<texture_set>/<texture_set>.tres` through `res://props/_shared/PropMaterialBinder.gd`.

## AI Route Flip-On

Trellis2 local route, once the GPU is free:

```powershell
$env:TRELLIS2_PROP_CMD = '<local Trellis2 command with {image} {out_glb} {seed} {target_tris}>'
python pipelines\props\trellis2_route.py world\props\input_images\altar.png --id altar_trellis2 --device cuda --run-model --publish
python pipelines\props\lod_chain.py altar_trellis2
python pipelines\props\collision_decompose.py altar_trellis2
python pipelines\props\billboard_bake.py altar_trellis2 --single
python pipelines\props\export_godot.py --id altar_trellis2
```

Meshy cloud route, once the user authorizes spend for a specific batch:

```powershell
$env:MESHY_AUTH_FOR_THIS_BATCH = 'YES'
python pipelines\props\meshy_route.py world\props\input_images\altar.png --id altar_meshy --publish --texture-prompt "weathered basalt altar, moss, engraved runes"
python pipelines\props\lod_chain.py altar_meshy
python pipelines\props\collision_decompose.py altar_meshy
python pipelines\props\billboard_bake.py altar_meshy --single
python pipelines\props\export_godot.py --id altar_meshy
```

Dry-run checks do not load GPU models or call paid APIs:

```powershell
python pipelines\props\trellis2_route.py world\props\library\rock_small_a01\thumbnail.png --id trellis2_probe --device cpu --dry-run
python pipelines\props\meshy_route.py world\props\library\rock_small_a01\thumbnail.png --id meshy_probe --dry-run
```

## Current Limits

- Procedural geometry is still lower-fidelity than character Meshy GLBs; PBR binding improves material quality but not silhouette complexity.
- Trellis2 and Meshy routes are adapters only until the GPU is free / cloud spend is authorized.
- Biome scatter v3 has real `prop_pool` data, but the world-scene scatter compiler still needs to instantiate these GLBs instead of placeholder primitives.

