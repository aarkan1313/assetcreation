# Godot Exporter

Cross-cutting exporter that turns *any* pipeline's output folder into a
ready-to-import Godot 4.5 resource bundle.

## Asset types supported

| Type | Source | Output |
|---|---|---|
| `pbr_material` | `world/textures/library/<id>/` | `StandardMaterial3D` .tres + texture copies |
| `terrain` | `pipelines/terrain/output/<id>/` | `HeightMapShape3D` .tres + bundle copy |
| `sprite_sheet` | character pipeline atlas folder | `SpriteFrames` .tres stub + atlas copy |
| `rigged_glb` | rigged GLB (Mesh2Motion / Mixamo / RigAnything) | GLB copy + import notes |

## Usage

```powershell
python export_godot.py --type pbr_material --src D:/assets/world/textures/library/Rock035 --out D:/assets/godot_pack/materials/rock035
python export_godot.py --type terrain --src D:/assets/pipelines/terrain/output/smoketest_a --out D:/assets/godot_pack/terrain/smoketest_a
python export_godot.py --type sprite_sheet --src <character atlas folder> --out D:/assets/godot_pack/sprites/<id>
python export_godot.py --type rigged_glb --src <model.glb> --out D:/assets/godot_pack/characters/<id>
```

Output goes to `D:/assets/godot_pack/<category>/<id>/`. Each folder contains a
`godot_export.json` describing what was packaged.

## Limitations / Notes

- `sprite_sheet`: SpriteFrames stub created, but per-frame UV rects must still
  be sliced in the editor (or wired up via a follow-up pass once frames JSON
  schema is finalized).
- `terrain`: drops a `HeightMapShape3D` for collision; if you also want
  Terrain3D rendering, follow `terrain3d_import.json` hints in the bundle.
- `pbr_material`: defaults to `StandardMaterial3D`. ORM packing is supported
  by `pipelines/textures/pack_terrain3d.py`; an ORMMaterial3D template is in
  the script and can be wired in when needed.

## Future extensions (post-research)

- `vfx` — flipbook + SpriteFrames or AnimatedSprite3D
- `ui` — AtlasTexture region slicing
- `audio` — AudioStreamOgg / AudioStreamRandomizer
- `game_data` — bulk Resource pack
