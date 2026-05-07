# Procedural prop recipes

Three first-party kinds today. Each is a Blender 5.1 recipe in [`blender_scripts/proc_props.py`](blender_scripts/proc_props.py).

| kind | base primitive | post-ops | typical tris | use class |
|---|---|---|---|---|
| `rock_small` | ico-sphere subdiv 4 | per-vertex random offset → squash z=0.55 → decimate | 600-1500 | scatter_multimesh |
| `mushroom_lantern` | cylinder stem + uv-sphere cap | crop cap bottom half → light surface displace → join → decimate | 800-1500 | scatter_multimesh |
| `wooden_crate` | cube size 0.6 | bevel modifier 0.025 / 2 segments → decimate | 600-1200 | scene_prop (with collision) |

Run any of them:

```powershell
python pipelines\props\proc_generate.py rock_small        --id rock_small_01      --seed 7   --target-tris 600
python pipelines\props\proc_generate.py mushroom_lantern  --id mushroom_lantern_a --seed 11  --target-tris 800
python pipelines\props\proc_generate.py wooden_crate      --id crate_oak_01       --seed 0   --target-tris 800
```

Each writes `world/props/library/<id>/{model_lod0.glb, thumbnail.png, prop.json, qa.json}`.

## Adding new kinds

1. Implement `make_<kind>(seed, target_tris) -> bpy.types.Object` in `blender_scripts/proc_props.py`. Return a single object after `transform_apply()`.
2. Add the kind to the `KIND_FACTORIES` dict.
3. Add the kind to `KINDS` in `proc_generate.py` and add an entry in the `placement_tags` / `material_slots` tables there.

That's enough for the validator + Godot exporter to pick it up unchanged.

## Material handling

The Blender route bakes simple Principled BSDF materials with a `Base Color` and `Roughness` per submesh. They survive into the GLB. Godot 4.5 imports the GLB as a packed scene with the materials intact; the `<id>.tscn` instances that scene as a child of a `Node3D`.

To swap in AAA PBR materials later (using `pipelines/textures/aaa_texture.py` outputs), add a `materials/` folder in the prop dir and reference texture paths from `prop.json["material_slots"]`. The Godot importer can be extended to swap the GLB's materials for `StandardMaterial3D` resources at scene-build time. Out of scope for v1.

## Comparison to the AI route

| | procedural Blender | Meshy AI |
|---|---|---|
| Cost | 0 | ~1 credit/prop |
| Wall-clock | ~30 s/prop | ~60-180 s/prop |
| Variety | hand-coded kinds only | unconstrained |
| Visual quality | utility-low | hero-medium |
| Determinism | seed → identical mesh | non-deterministic |
| Required network | none | yes |
| GPU | no | server-side |

We pick procedural by default; AI is a finishing pass for hero props. Same `prop.json` shape both routes.
