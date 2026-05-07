"""Blender procedural prop generator.

Run inside Blender for real output:

  blender -b --python art_lab/props/tools/prop_make_blender.py -- \
    --recipe art_lab/props/recipes/rock_cluster_small.recipe.json \
    --variant-id rock_cluster_small_01 \
    --out world/props/library/rock_cluster_small_01

Run with normal Python for a CPU-only dry-run:

  python art_lab/props/tools/prop_make_blender.py --recipe ... --variant-id ... --out ... --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path


ASSET_ROOT = Path(__file__).resolve().parents[3]


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", type=Path, required=True)
    ap.add_argument("--variant-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-render-thumbnail", action="store_true")
    return ap.parse_args(argv)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ASSET_ROOT).as_posix()
    except ValueError:
        return str(path)


def stable_seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ASSET_ROOT / path


def hex_to_rgba(hex_color: str) -> tuple[float, float, float, float]:
    s = hex_color.strip().lstrip("#")
    if len(s) != 6:
        return (0.5, 0.5, 0.5, 1.0)
    return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0, 1.0)


def average_range(values: dict, axis: str, default: float = 1.0) -> float:
    r = values.get(axis, [default, default])
    return (float(r[0]) + float(r[1])) / 2.0


def average_scale(recipe: dict) -> list[float]:
    scale = recipe.get("scale_m", {})
    return [round(average_range(scale, axis), 3) for axis in ["x", "y", "z"]]


def average_radius(recipe: dict) -> float:
    radius = recipe.get("placement", {}).get("footprint_radius_m", 0.5)
    if isinstance(radius, list):
        return round((float(radius[0]) + float(radius[1])) / 2.0, 3)
    return round(float(radius), 3)


def dry_run(args: argparse.Namespace, recipe: dict) -> int:
    out = resolve_path(args.out)
    plan = {
        "variant_id": args.variant_id,
        "recipe": rel(resolve_path(args.recipe)),
        "out": rel(out),
        "generator": recipe.get("generator"),
        "family": recipe.get("family"),
        "would_write": ["model_lod0.glb", "thumbnail.png", "prop.json", "qa.json"],
        "note": "dry-run only; run through blender -b without --dry-run for real generation",
    }
    print(json.dumps(plan, indent=2))
    return 0


def require_bpy():
    try:
        import bpy  # type: ignore
        return bpy
    except Exception as exc:
        raise SystemExit(f"Blender Python is required for generation. Use --dry-run outside Blender. Import error: {exc}")


def clear_scene(bpy) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def make_materials(bpy, recipe: dict) -> dict:
    mats = {}
    for mat_def in recipe.get("materials", []):
        name = mat_def.get("slot", "material")
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            color = hex_to_rgba(mat_def.get("color", "#808080"))
            if "Base Color" in bsdf.inputs:
                bsdf.inputs["Base Color"].default_value = color
            if "Roughness" in bsdf.inputs:
                bsdf.inputs["Roughness"].default_value = float(mat_def.get("roughness", 0.85))
        mats[name] = mat
    if not mats:
        mat = bpy.data.materials.new("default")
        mats["default"] = mat
    return mats


def assign_mat(obj, mat) -> None:
    obj.data.materials.append(mat)


def add_cube(bpy, name: str, loc: tuple[float, float, float], scale: tuple[float, float, float], mat) -> object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    assign_mat(obj, mat)
    bevel = obj.modifiers.new("soft_chips", "BEVEL")
    bevel.width = min(scale) * 0.08
    bevel.segments = 1
    obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    return obj


def add_ico(bpy, name: str, loc: tuple[float, float, float], scale: tuple[float, float, float], mat) -> object:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    assign_mat(obj, mat)
    disp = obj.modifiers.new("stone_noise", "DISPLACE")
    tex = bpy.data.textures.new(f"{name}_noise", "VORONOI")
    tex.noise_scale = 1.2
    tex.intensity = 0.35
    disp.texture = tex
    disp.strength = 0.08
    obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    return obj


def add_cylinder(bpy, name: str, loc: tuple[float, float, float], radius: float, depth: float, mat, vertices: int = 12) -> object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    obj = bpy.context.object
    obj.name = name
    assign_mat(obj, mat)
    obj.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    return obj


def add_card(bpy, name: str, loc: tuple[float, float, float], width: float, height: float, yaw: float, mat) -> object:
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=loc, rotation=(math.radians(72), 0, yaw))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (width, height, 1.0)
    assign_mat(obj, mat)
    return obj


def gen_rocks(bpy, rng: random.Random, recipe: dict, mats: dict) -> None:
    scale = recipe.get("scale_m", {})
    sx = average_range(scale, "x")
    sy = average_range(scale, "y")
    sz = average_range(scale, "z")
    rock_mat = mats.get("basalt") or mats.get("basalt_stone") or next(iter(mats.values()))
    moss_mat = mats.get("moss") or rock_mat
    count = rng.randint(3, 7)
    for i in range(count):
        rx = rng.uniform(0.18, 0.42) * sx
        ry = rng.uniform(0.12, 0.35) * sy
        rz = rng.uniform(0.18, 0.42) * sz
        x = rng.uniform(-0.35, 0.35) * sx
        y = rng.uniform(-0.30, 0.30) * sz
        z = ry
        add_ico(bpy, f"rock_{i+1}", (x, y, z), (rx, rz, ry), rock_mat)
    for i in range(max(1, count // 2)):
        add_ico(
            bpy,
            f"moss_lump_{i+1}",
            (rng.uniform(-0.35, 0.35) * sx, rng.uniform(-0.30, 0.30) * sz, rng.uniform(0.18, 0.55) * sy),
            (rng.uniform(0.08, 0.20) * sx, rng.uniform(0.08, 0.18) * sz, rng.uniform(0.02, 0.06) * sy),
            moss_mat,
        )


def gen_foliage(bpy, rng: random.Random, recipe: dict, mats: dict) -> None:
    scale = recipe.get("scale_m", {})
    sx = average_range(scale, "x")
    sy = average_range(scale, "y")
    leaf_mat = next(iter(mats.values()))
    cards = rng.randint(8, 16)
    for i in range(cards):
        angle = math.tau * i / cards + rng.uniform(-0.15, 0.15)
        radius = rng.uniform(0.05, 0.22) * sx
        width = rng.uniform(0.05, 0.12) * sx
        height = rng.uniform(0.18, 0.42) * sy
        add_card(bpy, f"leaf_card_{i+1}", (math.cos(angle) * radius, math.sin(angle) * radius, height * 0.45), width, height, angle, leaf_mat)


def gen_mushrooms(bpy, rng: random.Random, recipe: dict, mats: dict) -> None:
    cap_mat = mats.get("cap") or next(iter(mats.values()))
    stem_mat = mats.get("stem") or cap_mat
    count = rng.randint(5, 12)
    for i in range(count):
        x = rng.uniform(-0.28, 0.28)
        y = rng.uniform(-0.28, 0.28)
        h = rng.uniform(0.10, 0.38)
        r = rng.uniform(0.025, 0.055)
        add_cylinder(bpy, f"stem_{i+1}", (x, y, h / 2), r, h, stem_mat, vertices=8)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=rng.uniform(0.055, 0.12), location=(x, y, h))
        cap = bpy.context.object
        cap.name = f"cap_{i+1}"
        cap.scale.z = rng.uniform(0.25, 0.45)
        assign_mat(cap, cap_mat)


def gen_log(bpy, rng: random.Random, recipe: dict, mats: dict) -> None:
    scale = recipe.get("scale_m", {})
    length = average_range(scale, "x")
    radius = max(0.08, average_range(scale, "y") * 0.45)
    bark = mats.get("wet_bark") or next(iter(mats.values()))
    obj = add_cylinder(bpy, "fallen_log", (0, 0, radius), radius, length, bark, vertices=18)
    obj.rotation_euler[1] = math.radians(90)
    obj.rotation_euler[2] = rng.uniform(-0.15, 0.15)
    moss = mats.get("moss")
    if moss:
        for i in range(3):
            add_ico(bpy, f"log_moss_{i+1}", (rng.uniform(-length * 0.35, length * 0.35), rng.uniform(-0.08, 0.08), radius * 1.65), (0.18, 0.08, 0.035), moss)


def gen_ruins(bpy, rng: random.Random, recipe: dict, mats: dict) -> None:
    family = recipe.get("family", "")
    stone = mats.get("basalt_stone") or mats.get("basalt") or next(iter(mats.values()))
    moss = mats.get("moss") or stone
    scale = recipe.get("scale_m", {})
    sx = average_range(scale, "x")
    sy = average_range(scale, "y")
    sz = average_range(scale, "z")
    if "pillar" in family:
        radius = min(sx, sz) * 0.35
        height = sy
        obj = add_cylinder(bpy, "broken_pillar", (0, 0, height / 2), radius, height, stone, vertices=10)
        obj.rotation_euler[0] = rng.uniform(-0.10, 0.10)
        obj.rotation_euler[1] = rng.uniform(-0.16, 0.16)
        add_cube(bpy, "broken_cap", (0, 0, height + 0.08), (radius * 1.25, radius * 1.25, 0.08), stone)
    else:
        pieces = rng.randint(1, 3)
        for i in range(pieces):
            add_cube(
                bpy,
                f"ruin_block_{i+1}",
                (rng.uniform(-0.18, 0.18) * sx, rng.uniform(-0.14, 0.14) * sz, sy * 0.25),
                (rng.uniform(0.25, 0.55) * sx, rng.uniform(0.20, 0.45) * sz, rng.uniform(0.15, 0.40) * sy),
                stone,
            )
    add_ico(bpy, "ruin_moss", (0, 0, sy * 0.55), (sx * 0.16, sz * 0.12, sy * 0.035), moss)


def generate_geometry(bpy, rng: random.Random, recipe: dict, mats: dict) -> None:
    generator = recipe.get("generator")
    if generator == "blender_rock_cluster_v1":
        gen_rocks(bpy, rng, recipe, mats)
    elif generator == "blender_foliage_cards_v1":
        gen_foliage(bpy, rng, recipe, mats)
    elif generator == "blender_mushroom_cluster_v1":
        gen_mushrooms(bpy, rng, recipe, mats)
    elif generator == "blender_log_v1":
        gen_log(bpy, rng, recipe, mats)
    elif generator == "blender_ruins_v1":
        gen_ruins(bpy, rng, recipe, mats)
    else:
        raise SystemExit(f"unsupported Blender generator: {generator}")


def setup_render(bpy, out_dir: Path) -> None:
    bpy.ops.object.light_add(type="AREA", location=(0, -3, 4))
    light = bpy.context.object
    light.name = "thumbnail_key"
    light.data.energy = 500
    light.data.size = 4
    bpy.ops.object.camera_add(location=(2.8, -4.0, 2.3), rotation=(math.radians(62), 0, math.radians(35)))
    bpy.context.scene.camera = bpy.context.object
    bpy.context.scene.render.resolution_x = 512
    bpy.context.scene.render.resolution_y = 512
    try:
        bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
    except Exception:
        pass
    bpy.context.scene.render.filepath = str(out_dir / "thumbnail.png")


def triangle_count(bpy) -> int:
    total = 0
    for obj in bpy.context.scene.objects:
        if getattr(obj, "type", None) == "MESH":
            total += len(obj.data.polygons)
    return total


def export_glb(bpy, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(out_dir / "model_lod0.glb"), export_format="GLB")


def write_manifests(recipe_path: Path, recipe: dict, variant_id: str, out_dir: Path, tris: int) -> None:
    placement = recipe.get("placement", {})
    budget = int(recipe.get("budgets", {}).get("lod0_tris_max", 999999))
    qa = {
        "schema": "prop_qa.v1",
        "id": variant_id,
        "passed": tris <= budget,
        "metrics": {
            "triangles_estimate": tris,
            "lod0_tris_max": budget
        },
        "warnings": [] if tris <= budget else ["triangle estimate exceeds lod0 budget"]
    }
    write_json(out_dir / "qa.json", qa)
    prop = {
        "schema": "prop_asset.v1",
        "id": variant_id,
        "family": recipe["family"],
        "kit": recipe["kit"],
        "source_method": "blender_procedural",
        "source_recipe": rel(recipe_path),
        "license": "project_generated",
        "render_class": placement.get("render_class", "scatter_multimesh"),
        "collision": placement.get("collision", "none"),
        "origin": placement.get("origin", "bottom_center"),
        "scale_m": average_scale(recipe),
        "footprint_radius_m": average_radius(recipe),
        "lods": [{"file": "model_lod0.glb", "max_distance_m": 30, "triangles": tris}],
        "thumbnail": "thumbnail.png",
        "placement_tags": placement.get("placement_tags", []),
        "material_slots": [m.get("slot") for m in recipe.get("materials", []) if isinstance(m, dict)],
        "qa": "qa.json"
    }
    write_json(out_dir / "prop.json", prop)


def main() -> int:
    args = parse_args()
    recipe_path = resolve_path(args.recipe)
    out_dir = resolve_path(args.out)
    recipe = load_json(recipe_path)
    if args.dry_run:
        return dry_run(args, recipe)

    bpy = require_bpy()
    rng = random.Random(args.seed if args.seed is not None else stable_seed(f"{recipe_path}:{args.variant_id}"))
    clear_scene(bpy)
    mats = make_materials(bpy, recipe)
    generate_geometry(bpy, rng, recipe, mats)
    tris = triangle_count(bpy)
    export_glb(bpy, out_dir)
    if not args.no_render_thumbnail:
        setup_render(bpy, out_dir)
        bpy.ops.render.render(write_still=True)
    write_manifests(recipe_path, recipe, args.variant_id, out_dir, tris)
    print(json.dumps({"id": args.variant_id, "out": rel(out_dir), "triangles": tris}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

