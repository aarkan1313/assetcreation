# Prop Contract v1

Each prop variant is a durable library entry under:

```text
world/props/library/<prop_id>/
```

Required files for a generated mesh prop:

```text
prop.json
qa.json
model_lod0.glb
thumbnail.png
```

Preferred files:

```text
model_lod1.glb
model_lod2.glb
collision.glb
billboard.png
preview_turntable/
materials/
godot/<prop_id>.tscn
```

Required `prop.json` shape:

```json
{
  "schema": "prop_asset.v1",
  "id": "rock_cluster_small_01",
  "family": "rock_cluster_small",
  "kit": "mossy_highland_ruins",
  "source_method": "blender_procedural",
  "source_recipe": "art_lab/props/recipes/rock_cluster_small.recipe.json",
  "license": "project_generated",
  "render_class": "scatter_multimesh",
  "collision": "none",
  "origin": "bottom_center",
  "scale_m": [1.0, 0.45, 0.9],
  "footprint_radius_m": 0.65,
  "lods": [
    {"file": "model_lod0.glb", "max_distance_m": 25, "triangles": 1200}
  ],
  "thumbnail": "thumbnail.png",
  "placement_tags": ["rock", "mossy", "slope_ok"],
  "material_slots": ["basalt", "moss"],
  "qa": "qa.json"
}
```

Render classes:

- `scatter_multimesh`: many cheap, usually non-colliding instances.
- `scene_prop`: normal Godot scene prop, maybe colliding.
- `hero_prop`: unique/high-review prop.
- `decal`: flat projected or card texture.
- `billboard_only`: distant impostor/card.
- `terrain3d_instance`: Terrain3D instancer target if compatibility passes.

Collision policy:

- `none`: default for dense scatter.
- `simple`: generated box/capsule/convex proxy.
- `convex`: one or more convex hulls.
- `authored`: hand-authored collision for hero/interactable props.

CPU validators check the contract. Blender/GPU tools produce the actual GLB and
PNG files later.

