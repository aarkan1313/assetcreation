# Props Pipeline

**Status:** v2+ working. The local procedural route is production-usable for scatter and scene props; the new material-binding pass gives those props shared AAA PBR materials from `world/textures/library`. AI hero routes are scaffolded but runtime-gated.

## Files

| File | Role |
|---|---|
| [proc_generate.py](proc_generate.py) | Blender-headless procedural prop generator. 13 kinds; writes `prop_asset.v1`. |
| [variation_sweep.py](variation_sweep.py) | `prop_sweep.v1` batch runner for deterministic recipe variants. |
| [lod_chain.py](lod_chain.py) | LOD ladder authoring. Two methods (`--method decimate` default, `--method meshopt`); side-by-side via `--suffix _meshopt`. See "LOD method comparison" below. |
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

## LOD method comparison (decimate vs meshopt)

Per brief #03 SOTA survey 2026-05-07, **meshoptimizer** is recommended over Blender's DECIMATE COLLAPSE for silhouette quality at low LODs. We ship both side-by-side for A/B comparison; `decimate` remains the default so existing pipelines and Godot scenes don't change.

**Tool:** [tools/meshoptimizer/gltfpack.exe](../../tools/meshoptimizer/gltfpack.exe) (zeux/meshoptimizer v1.1, prebuilt Windows binary, ~1.4 MB).

**Run side-by-side on the same prop:**
```powershell
# Generates the canonical model_lod{N}.glb files (default behavior, unchanged)
python pipelines\props\lod_chain.py obelisk_egyptian_a04

# Generates model_lod{N}_meshopt.glb files alongside; preserves canonical lods array;
# adds prop.json `lods_meshopt` sibling field for the new run.
python pipelines\props\lod_chain.py obelisk_egyptian_a04 --method meshopt --suffix _meshopt
```

**Verified 2026-05-07** on `obelisk_egyptian_a04` (4-LOD hero ladder 1.0/0.65/0.35/0.15):

| LOD | Tris (decimate) | Tris (meshopt) | File size (decimate) | File size (meshopt) | Δ size |
|---|---|---|---|---|---|
| 0 | 100,000 | 100,000 | 11.72 MB | 11.72 MB | — (LOD0 is a copy) |
| 1 | 64,998 | 64,998 | 10.34 MB | 10.24 MB | **−100 KB** |
| 2 | 35,000 | 34,998 | 9.56 MB | 9.37 MB | **−192 KB** |
| 3 | 15,000 | 15,000 | 8.82 MB | 8.75 MB | **−66 KB** |

Both methods hit the requested triangle ratio essentially exactly; meshopt produces 1-2% smaller GLBs at matched tri counts (more efficient vertex/index packing). The brief's "real silhouette win" claim is about visual quality at low LODs and requires visual inspection — the file-size delta is incidental.

**Switching the default:** when ready, change `--method decimate` to `--method meshopt` in `postprocess_ai_route.py`'s `stage_lod_chain` invocation. Don't switch yet — visual A/B first.

