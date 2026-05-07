"""Godot 4.5 exporter for props (v2 — HLOD + CoACD collision + multimesh templates).

For each validated prop in `world/props/library/<id>/`, emits:

  godot/<id>/<id>.tscn               multi-LOD scene with explicit VisibilityRange
                                     (HLOD); meshes/generate_lods DISABLED on
                                     hand-authored chains.
  godot/<id>/<id>_multimesh.tscn     scatter template — N MultiMeshInstance3D
                                     nodes (one per LOD), each with its own
                                     VisibilityRange and an empty MultiMesh
                                     resource the placement compiler fills.
  godot/<id>/model_lodN.glb          copies of every LOD GLB
  godot/<id>/model_lodN.glb.import   per-GLB import metadata
  godot/<id>/billboard.png           if present
  godot/<id>/prop.json               provenance copy

Per J2 §3.2-§3.3:
  - VisibilityRange ranges come from prop.json.lods[i].max_distance_m.
  - Adjacent LODs have small overlap windows for fade_mode=1 (cross-fade).
  - generate_lods disabled per .glb.import to avoid double-LOD work.
  - When prop.json has `collision_file`: read collision.json, emit one
    StaticBody3D + N CollisionShape3D + N ConvexPolygonShape3D sub-resources.
  - Billboard is the final tier when present (Sprite3D with billboard=1).

CLI:
  python export_godot.py --all
  python export_godot.py --id barrel_a01
  python export_godot.py --all --hlod --multimesh-template
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ASSETS = Path(r"D:\assets")
LIBRARY = Path(r"D:\assets\world\props\library")
GODOT_OUT = Path(r"D:\assets\world\props\godot")
TEXTURE_LIBRARY = Path(r"D:\assets\world\textures\library")

# Cross-fade margin in meters between adjacent LODs.
FADE_MARGIN_M = 3.0
# Billboard is visible from the last LOD's max distance out to this far cap.
BILLBOARD_FAR_M = 400.0

SHARED_BINDER_SCRIPT = '''extends Node

@export var material_overrides: Array[Material] = []

func _ready() -> void:
\t_apply_materials(self)

func _apply_materials(node: Node) -> void:
\tif node is MeshInstance3D and material_overrides.size() > 0:
\t\tvar mesh_instance := node as MeshInstance3D
\t\tvar surface_count := 0
\t\tif mesh_instance.mesh != null:
\t\t\tsurface_count = mesh_instance.mesh.get_surface_count()
\t\tfor i in range(surface_count):
\t\t\tvar mat_index = min(i, material_overrides.size() - 1)
\t\t\tmesh_instance.set_surface_override_material(i, material_overrides[mat_index])
\tfor child in node.get_children():
\t\t_apply_materials(child)
'''


def make_glb_import(godot_glb_path: str, generate_lods: bool) -> str:
    """Per-GLB .import. We disable Godot auto-LOD whenever we ship a hand-
    authored chain — the auto-LOD work is wasted on these meshes.
    """
    return (
        '[remap]\n\n'
        'importer="scene"\n'
        'importer_version=1\n'
        'type="PackedScene"\n'
        f'path="res://.godot/imported/{Path(godot_glb_path).stem}-import.scn"\n'
        '[deps]\n\n'
        f'source_file="res://{godot_glb_path}"\n'
        f'dest_files=["res://.godot/imported/{Path(godot_glb_path).stem}-import.scn"]\n'
        '[params]\n\n'
        'nodes/root_type=""\n'
        'nodes/root_name=""\n'
        'nodes/apply_root_scale=true\n'
        'nodes/root_scale=1.0\n'
        'nodes/import_as_skeleton_bones=false\n'
        'nodes/use_node_type_suffixes=true\n'
        'meshes/ensure_tangents=true\n'
        f'meshes/generate_lods={"true" if generate_lods else "false"}\n'
        'meshes/create_shadow_meshes=true\n'
        'meshes/light_baking=1\n'
        'meshes/lightmap_texel_size=0.2\n'
        'meshes/force_disable_compression=false\n'
        'animation/import=true\n'
    )


def _find_texture_map(texture_set: str, suffix: str) -> Path | None:
    path = TEXTURE_LIBRARY / texture_set / f"{texture_set}_{suffix}.png"
    return path if path.exists() else None


def _material_tres(texture_set: str, rel_paths: dict[str, str]) -> str:
    ext: list[str] = []
    ids: dict[str, int] = {}
    for suffix in ("albedo", "normal", "roughness", "metallic", "ao"):
        if suffix in rel_paths:
            ids[suffix] = len(ext) + 1
            ext.append(f'[ext_resource type="Texture2D" path="res://{rel_paths[suffix]}" id="{ids[suffix]}"]')

    out = [f'[gd_resource type="StandardMaterial3D" load_steps={1 + len(ext)} format=3]', '']
    out.extend(ext)
    out.extend(['', '[resource]', f'resource_name = "{texture_set}"'])
    if "albedo" in ids:
        out.append(f'albedo_texture = ExtResource("{ids["albedo"]}")')
    if "normal" in ids:
        out.append('normal_enabled = true')
        out.append(f'normal_texture = ExtResource("{ids["normal"]}")')
    if "roughness" in ids:
        out.append(f'roughness_texture = ExtResource("{ids["roughness"]}")')
    if "metallic" in ids:
        out.append(f'metallic_texture = ExtResource("{ids["metallic"]}")')
    if "ao" in ids:
        out.append('ao_enabled = true')
        out.append(f'ao_texture = ExtResource("{ids["ao"]}")')
    out.append('roughness = 0.85')
    return "\n".join(out) + "\n"


def ensure_shared_assets(godot_root: Path, texture_sets: set[str]) -> dict[str, str]:
    """Copy shared material assets under res://props/_materials/.

    Returns {texture_set: godot_material_path}.
    """
    shared = godot_root / "_shared"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "PropMaterialBinder.gd").write_text(SHARED_BINDER_SCRIPT, encoding="utf-8")

    material_paths: dict[str, str] = {}
    for texture_set in sorted(texture_sets):
        out_dir = godot_root / "_materials" / texture_set
        out_dir.mkdir(parents=True, exist_ok=True)
        rel_paths: dict[str, str] = {}
        for suffix in ("albedo", "normal", "roughness", "metallic", "ao", "height"):
            src = _find_texture_map(texture_set, suffix)
            if not src:
                continue
            dst = out_dir / src.name
            shutil.copyfile(src, dst)
            rel_paths[suffix] = f"props/_materials/{texture_set}/{src.name}"
        if rel_paths:
            material_tres = out_dir / f"{texture_set}.tres"
            material_tres.write_text(_material_tres(texture_set, rel_paths), encoding="utf-8")
            material_paths[texture_set] = f"props/_materials/{texture_set}/{texture_set}.tres"
    return material_paths


def _packed_vec3(verts: list) -> str:
    flat = ", ".join(f"{x:.6g}" for v in verts for x in v)
    return f"PackedVector3Array({flat})"


# --------- multi-LOD scene emit --------------------------------------------

def make_multilod_tscn(prop_id: str,
                        lods: list[dict],
                        glb_godot_paths: list[str],
                        billboard_godot_path: str | None,
                        collision: dict | None,
                        material_godot_paths: list[str] | None = None) -> str:
    """Multi-LOD Node3D scene with explicit VisibilityRange per child.

    Layout:
      <prop_id> (Node3D)
        LOD0 [MeshInstance3D-instance from GLB]   visibility 0..d0
        LOD1                                       visibility d0..d1
        ...
        Billboard (Sprite3D)                       visibility d_last..400
        StaticBody3D                               (if collision.json)
          CollisionShape3D × N
    """
    n = len(lods)
    material_godot_paths = material_godot_paths or []
    # ext-resources: one per LOD GLB + billboard + binder script/materials.
    ext = []
    for i, godot_path in enumerate(glb_godot_paths):
        ext.append(f'[ext_resource type="PackedScene" path="res://{godot_path}" id="{i + 1}"]')
    bb_id = None
    if billboard_godot_path:
        bb_id = len(ext) + 1
        ext.append(f'[ext_resource type="Texture2D" path="res://{billboard_godot_path}" id="{bb_id}"]')
    binder_id = None
    material_ids: list[int] = []
    if material_godot_paths:
        binder_id = len(ext) + 1
        ext.append(f'[ext_resource type="Script" path="res://props/_shared/PropMaterialBinder.gd" id="{binder_id}"]')
        for mat_path in material_godot_paths:
            mid = len(ext) + 1
            ext.append(f'[ext_resource type="Material" path="res://{mat_path}" id="{mid}"]')
            material_ids.append(mid)

    # Sub-resources for collision hulls.
    sub = []
    if collision and collision.get("hulls"):
        for h in collision["hulls"]:
            idx = h["index"]
            verts = h["vertices"]
            sub.append(f'[sub_resource type="ConvexPolygonShape3D" id="hull_{idx}"]')
            sub.append(f'points = {_packed_vec3(verts)}')
            sub.append("")

    load_steps = 1 + len(ext) + (len(collision["hulls"]) if collision else 0)
    out = [f'[gd_scene load_steps={load_steps} format=3]', '']
    out.extend(ext)
    out.append('')
    out.extend(sub)
    out.append(f'[node name="{prop_id}" type="Node3D"]')
    if binder_id is not None:
        out.append(f'script = ExtResource("{binder_id}")')
        mat_refs = ", ".join(f'ExtResource("{mid}")' for mid in material_ids)
        out.append(f'material_overrides = [{mat_refs}]')
    out.append('')

    # Per-LOD nodes.
    for i, lod in enumerate(lods):
        d_end = float(lod["max_distance_m"])
        d_begin = 0.0 if i == 0 else float(lods[i - 1]["max_distance_m"])
        node_name = f"LOD{i}"
        out.append(f'[node name="{node_name}" parent="." instance=ExtResource("{i + 1}")]')
        if i > 0:
            out.append(f'visibility_range_begin = {d_begin:.2f}')
            out.append(f'visibility_range_begin_margin = {FADE_MARGIN_M:.2f}')
        out.append(f'visibility_range_end = {d_end:.2f}')
        out.append(f'visibility_range_end_margin = {FADE_MARGIN_M:.2f}')
        out.append('visibility_range_fade_mode = 1')
        out.append('')

    # Billboard tier.
    if bb_id is not None and lods:
        d_begin = float(lods[-1]["max_distance_m"])
        out.append('[node name="Billboard" type="Sprite3D" parent="."]')
        out.append(f'texture = ExtResource("{bb_id}")')
        out.append(f'visibility_range_begin = {d_begin:.2f}')
        out.append(f'visibility_range_end = {BILLBOARD_FAR_M:.2f}')
        out.append('visibility_range_fade_mode = 1')
        out.append('billboard = 1')
        out.append('shaded = false')
        out.append('')

    # Collision.
    if collision and collision.get("hulls"):
        out.append('[node name="StaticBody3D" type="StaticBody3D" parent="."]')
        out.append('')
        for h in collision["hulls"]:
            idx = h["index"]
            out.append(f'[node name="CollisionShape3D_{idx}" type="CollisionShape3D" parent="StaticBody3D"]')
            out.append(f'shape = SubResource("hull_{idx}")')
            out.append('')

    return "\n".join(out) + "\n"


# --------- multimesh template emit -----------------------------------------

def make_multimesh_template_tscn(prop_id: str,
                                  lods: list[dict],
                                  glb_godot_paths: list[str]) -> str:
    """Empty-transforms scaffold for scatter compilers.

    One MultiMeshInstance3D per LOD; each has its own VisibilityRange. The
    placement compiler fills the MultiMesh transforms array later.
    The MeshInstance3D's mesh resource is sourced by extracting the imported
    GLB's first surface — we expose this via inline @export-style references
    that the compiler swaps for real `MultiMesh` resources.
    """
    ext = []
    for i, godot_path in enumerate(glb_godot_paths):
        ext.append(f'[ext_resource type="PackedScene" path="res://{godot_path}" id="{i + 1}"]')

    load_steps = 1 + len(ext)
    out = [f'[gd_scene load_steps={load_steps} format=3]', '']
    out.extend(ext)
    out.append('')
    out.append(f'[node name="{prop_id}_multimesh" type="Node3D"]')
    out.append('')

    for i, lod in enumerate(lods):
        d_end = float(lod["max_distance_m"])
        d_begin = 0.0 if i == 0 else float(lods[i - 1]["max_distance_m"])
        # We use a Node3D placeholder + a child reference to the GLB's first
        # mesh; the placement compiler replaces this node with a real
        # MultiMeshInstance3D + populated MultiMesh.
        out.append(f'[node name="MM_LOD{i}" type="MultiMeshInstance3D" parent="."]')
        out.append(f'# placement compiler should set: multimesh = MultiMesh<Mesh from ExtResource("{i + 1}")>')
        if i > 0:
            out.append(f'visibility_range_begin = {d_begin:.2f}')
        out.append(f'visibility_range_end = {d_end:.2f}')
        out.append('visibility_range_fade_mode = 0  # MultiMesh fade not supported in 4.5')
        out.append('')

    return "\n".join(out) + "\n"


# --------- per-prop export -------------------------------------------------

def export_prop(prop_dir: Path, godot_root: Path,
                emit_multimesh: bool = True,
                material_paths: dict[str, str] | None = None) -> dict | None:
    pj = prop_dir / "prop.json"
    if not pj.exists():
        return None
    data = json.loads(pj.read_text(encoding="utf-8"))
    pid = data["id"]
    lods = data.get("lods", [])
    if not lods:
        return None
    out_dir = godot_root / pid
    out_dir.mkdir(parents=True, exist_ok=True)

    glb_godot_paths: list[str] = []
    for lod in lods:
        f = lod["file"]
        src = prop_dir / f
        if not src.exists():
            continue
        dst = out_dir / f
        shutil.copyfile(src, dst)
        godot_path = f"props/{pid}/{f}"
        (out_dir / f"{f}.import").write_text(
            make_glb_import(godot_path, generate_lods=False),
            encoding="utf-8",
        )
        glb_godot_paths.append(godot_path)

    # Filter lods to those whose GLB files actually exist.
    lods_present = [lod for lod in lods if (out_dir / lod["file"]).exists()]
    if len(lods_present) != len(glb_godot_paths):
        # paths and lods must align; rebuild from intersection
        glb_godot_paths = [f"props/{pid}/{lod['file']}" for lod in lods_present]

    # Billboard
    bb_godot = None
    if (prop_dir / "billboard.png").exists():
        shutil.copyfile(prop_dir / "billboard.png", out_dir / "billboard.png")
        bb_godot = f"props/{pid}/billboard.png"

    # Thumbnail
    if (prop_dir / "thumbnail.png").exists():
        shutil.copyfile(prop_dir / "thumbnail.png", out_dir / "thumbnail.png")

    # Collision
    collision_data = None
    coll_path = prop_dir / (data.get("collision_file") or "collision.json")
    if data.get("collision_file") and coll_path.exists():
        try:
            collision_data = json.loads(coll_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[export_godot] {pid}: collision parse failed: {e}")

    shutil.copyfile(pj, out_dir / "prop.json")

    # PBR material bindings are authored by pbr_material_bind.py and exported
    # as shared StandardMaterial3D resources under props/_materials.
    material_godot_paths: list[str] = []
    material_paths = material_paths or {}
    binding = data.get("pbr_material_bindings") or {}
    for slot in binding.get("slots", []):
        tex = slot.get("texture_set")
        if tex and tex in material_paths:
            material_godot_paths.append(material_paths[tex])

    # Single-instance LOD scene
    tscn = make_multilod_tscn(pid, lods_present, glb_godot_paths,
                               bb_godot, collision_data, material_godot_paths)
    (out_dir / f"{pid}.tscn").write_text(tscn, encoding="utf-8")

    # Multimesh template (only useful for scatter render_class)
    if emit_multimesh and data.get("render_class") == "scatter_multimesh":
        mm = make_multimesh_template_tscn(pid, lods_present, glb_godot_paths)
        (out_dir / f"{pid}_multimesh.tscn").write_text(mm, encoding="utf-8")

    return {
        "id": pid,
        "scene": str(out_dir / f"{pid}.tscn"),
        "lod_count": len(lods_present),
        "has_collision": bool(collision_data and collision_data.get("hulls")),
        "has_billboard": bb_godot is not None,
        "render_class": data.get("render_class"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--library", type=Path, default=LIBRARY)
    ap.add_argument("--out", type=Path, default=GODOT_OUT)
    ap.add_argument("--id", default=None,
                    help="Export only this prop id (default: all)")
    ap.add_argument("--all", action="store_true",
                    help="Compatibility no-op; exporting all is the default.")
    ap.add_argument("--no-multimesh", action="store_true",
                    help="Skip emitting _multimesh.tscn templates")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    emit_mm = not args.no_multimesh

    texture_sets: set[str] = set()
    prop_dirs = []
    if args.id:
        prop_dirs = [args.library / args.id]
    else:
        prop_dirs = [d for d in sorted(args.library.iterdir()) if d.is_dir()]
    for d in prop_dirs:
        pj = d / "prop.json"
        if not pj.exists():
            continue
        try:
            pdata = json.loads(pj.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for slot in (pdata.get("pbr_material_bindings") or {}).get("slots", []):
            tex = slot.get("texture_set")
            if tex:
                texture_sets.add(tex)
    material_paths = ensure_shared_assets(args.out, texture_sets) if texture_sets else {}

    if args.id:
        info = export_prop(args.library / args.id, args.out, emit_mm, material_paths)
        if info:
            print(f"[export_godot] {info['id']} -> {info['scene']}  "
                  f"lods={info['lod_count']} coll={info['has_collision']} "
                  f"billboard={info['has_billboard']}")
        return 0

    n = 0
    n_coll = 0
    n_lod = 0
    for d in prop_dirs:
        if not d.is_dir():
            continue
        info = export_prop(d, args.out, emit_mm, material_paths)
        if info:
            print(f"[export_godot] {info['id']} -> {info['scene']}  "
                  f"lods={info['lod_count']} coll={info['has_collision']} "
                  f"billboard={info['has_billboard']}")
            n += 1
            if info["has_collision"]:
                n_coll += 1
            n_lod += info["lod_count"]
    (args.out / "README.txt").write_text(
        "# props drop-in for Godot 4.5 (v2 HLOD)\n"
        "Copy this folder to res://props/. Each prop is a packed .tscn that\n"
        "instances its model_lodN.glb chain with explicit VisibilityRange (HLOD).\n"
        "Auto-LOD is DISABLED per .glb.import — the chain is the chain.\n\n"
        "    var s := preload('res://props/barrel_a01/barrel_a01.tscn')\n"
        "    add_child(s.instantiate())\n\n"
        "Scatter (MultiMesh) templates: <id>_multimesh.tscn for scatter_multimesh\n"
        "props. Each template has one MultiMeshInstance3D per LOD with its own\n"
        "VisibilityRange; the placement compiler fills the transform array.\n",
        encoding="utf-8",
    )
    print(f"[export_godot] exported {n} props ({n_lod} LODs total, "
          f"{n_coll} with convex collision) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
