# Biome Decoration Kits

Per `research/G_deep_dive_world_textures_decor_shader.md`, this is the
prop/scatter/decal layer that makes a biome feel inhabited rather than
just textured ground.

## Pattern

```
biomes/
├── kits/<biome_id>.json         declares materials, decals, scatter rules, shader hints
├── tools/dress_biome.py         compiles a kit + terrain bundle + map → placement plan
└── output/<id>/                 per-run outputs
    ├── dressing.json            canonical manifest
    ├── placements/
    │   ├── scatter.csv          per-instance: asset, x, y, z, scale, rotation
    │   └── decals.csv           per-decal: id, x, y, size
    ├── masks/                   per-rule mask PNGs (QA + visualization)
    │   ├── wetness.png shade.png landmarks.png roads.png
    │   └── scatter_<asset>.png  one per scatter rule
    ├── preview_dressed.png      top-down density visualization
    └── godot/
        ├── scatter.tres         (stub) MultiMesh data resource for Godot
        └── placement_recipe.json LLM-readable summary
```

## Run

```powershell
# Dress a terrain bundle with a biome kit, optionally using a world map for
# landmark/road awareness:
python art_lab\biomes\tools\dress_biome.py `
  --kit mossy_highland_ruins `
  --terrain smoketest_a `
  --map mythos_a `
  --id mossy_x_mythos `
  --m-per-pixel 0.5
```

`--m-per-pixel` controls density math. 0.5 means each pixel = 0.5 m so a
512×512 terrain = 256m × 256m of world.

## Kit JSON shape

See `kits/mossy_highland_ruins.json` for a working example. Each kit has:

- **materials** — surface PBR sets (referenced by id from `world/textures/library/`)
- **decals** — id, size, density rules (`max_per_m2`, `wetness_min`, etc.)
- **scatter** — asset, density, slope/wetness/shade/road/landmark constraints, scale randomization
- **shader_rules** — wind sway, wetness darkening, snow cap, etc.

## What this gives the LLM

- A reproducible "fill this terrain with appropriate flora and props" function
- Per-asset masks I can visually inspect to debug placement
- A CSV the user can import into Godot's MultiMeshInstance3D
- A recipe file that describes what's been placed in plain language

## What's missing (next slice)

- **Actual prop GLBs.** The scatter.csv references asset names; we still
  need to *generate* those models. G recommends Blender Geometry Nodes for
  rocks/grass/cards. Current local-first prep lives in `art_lab/props/`; Blender
  procedural generation is the backbone, and Meshy/cloud APIs are optional
  baselines only.
- **Real Godot importer plugin.** scatter.tres is currently a stub. A small
  plugin should read scatter.csv and build proper MultiMesh transforms.
- **ProtonScatter handoff.** For interior scenes (caves, ruins),
  ProtonScatter is the better Godot target than terrain-scale MultiMesh.

## Status

- ✅ Kit schema + 1 reference kit (mossy_highland_ruins)
- ✅ Dressing compiler with mask-based placement (slope, wetness, shade, landmarks, roads)
- ✅ Blue-noise sampling per rule
- ✅ CSV outputs + per-rule mask PNGs
- ✅ Top-down preview
- ⏸️ Prop GLB generation (Blender Geometry Nodes)
- ⏸️ Godot MultiMesh importer plugin
- ⏸️ More kits (forest, desert, snow, swamp, urban-ruin)
