"""Blender 5.1 procedural prop generator. Runs as `blender --background --python <this>`.

13 kinds, each producing a single GLB plus a thumbnail PNG.

Per J2 SOTA spec: every factory accepts a `--params` JSON dict that overrides
recipe-internal knobs (displacement_magnitude, z_squash, subdivisions, color_variant,
etc). Unspecified params fall back to deterministic defaults seeded by --seed.

Kinds (v2):
  rock_small         displaced ico-sphere
  mushroom_lantern   stem cylinder + cap
  wooden_crate       beveled cube with planks
  barrel             curved-stave cylinder + iron bands
  lantern            base + glass column + capped roof
  signpost           pole + plank + nail studs
  treasure_chest     box body + lid + lock
  fence              two posts + 2 horizontal rails
  log                tapered cylinder + bark displacement
  stump              short trunk + ring detail
  tombstone          rounded slab base + cross indent
  bone_pile          5-7 ellipsoids stacked
  ruin_block         beveled cube + edge chip noise

Usage (called by proc_generate.py):
  blender --background --factory-startup --python proc_props.py -- \
    --kind rock_small --id rock_small_01 --out <dir> --seed 0 --target-tris 1500 \
    [--params '{"displacement_magnitude":0.25,"color_variant":"basalt_dark"}']
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--target-tris", type=int, default=1500)
    ap.add_argument("--params", default="{}", help="JSON dict of recipe overrides")
    return ap.parse_args(argv)


# ---------- helpers ---------------------------------------------------------

COLOR_PALETTES = {
    # rock palette
    "basalt_dark":    (0.18, 0.18, 0.20),
    "granite_grey":   (0.45, 0.44, 0.42),
    "sandstone_warm": (0.72, 0.58, 0.40),
    "obsidian":       (0.07, 0.06, 0.08),
    # wood palette
    "oak":            (0.45, 0.30, 0.18),
    "pine":           (0.62, 0.46, 0.28),
    "ash":            (0.50, 0.42, 0.30),
    "weathered_grey": (0.40, 0.38, 0.34),
    # metal palette
    "iron_black":     (0.10, 0.10, 0.11),
    "rusted_iron":    (0.42, 0.20, 0.10),
    "brass":          (0.78, 0.60, 0.20),
    # bone palette
    "bone_pale":      (0.86, 0.82, 0.74),
    "bone_aged":      (0.70, 0.65, 0.55),
    # cloth/canvas
    "linen":          (0.78, 0.72, 0.58),
    # vegetation
    "moss_green":     (0.20, 0.40, 0.18),
    "lichen_pale":    (0.55, 0.66, 0.42),
    # mushroom cap
    "amanita_red":    (0.78, 0.20, 0.22),
    "death_purple":   (0.40, 0.20, 0.55),
    "boletus_brown":  (0.55, 0.36, 0.20),
    # glass
    "glass_amber":    (0.90, 0.55, 0.18),
    "glass_blue":     (0.30, 0.55, 0.85),
}


def get_color(variant: str, default: str) -> tuple:
    return COLOR_PALETTES.get(variant, COLOR_PALETTES[default])


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def add_sun_and_camera() -> None:
    cam_data = bpy.data.cameras.new("Cam")
    cam_obj = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = Vector((2.0, -2.5, 1.6))
    cam_obj.rotation_euler = (math.radians(65), 0, math.radians(40))
    bpy.context.scene.camera = cam_obj
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 3.0
    sun_obj = bpy.data.objects.new("Sun", sun_data)
    sun_obj.rotation_euler = (math.radians(45), math.radians(20), 0)
    bpy.context.collection.objects.link(sun_obj)
    bpy.context.scene.world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world.use_nodes = True
    bg = bpy.context.scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.04, 0.05, 0.07, 1.0)
        bg.inputs[1].default_value = 0.4


def make_material(name: str, base_rgb: tuple, roughness: float = 0.8,
                  metallic: float = 0.0, emission: tuple | None = None) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*base_rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if emission and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 1.5
    return mat


def decimate(obj, target_tris: int) -> None:
    me = obj.data
    cur = len(me.polygons)
    if cur <= target_tris or cur == 0:
        return
    mod = obj.modifiers.new("Dec", "DECIMATE")
    mod.decimate_type = 'COLLAPSE'
    mod.use_collapse_triangulate = True
    mod.ratio = max(0.05, target_tris / max(cur, 1))
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Dec")


def jitter_verts(obj, seed: int, magnitude: float) -> None:
    rng = random.Random(seed)
    for v in obj.data.vertices:
        v.co += Vector((
            (rng.random() - 0.5) * magnitude,
            (rng.random() - 0.5) * magnitude,
            (rng.random() - 0.5) * magnitude,
        ))


def origin_to_bottom(obj, z: float = 0.0) -> None:
    bpy.context.scene.cursor.location = (0, 0, z)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')


def join_active(objs: list, name: str):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[-1]
    bpy.ops.object.join()
    out = bpy.context.active_object
    out.name = name
    return out


# ---------- factories -------------------------------------------------------

def make_rock_small(seed: int, target_tris: int, params: dict):
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=int(params.get("subdivisions", 4)), radius=0.5
    )
    obj = bpy.context.active_object
    obj.name = "Rock"
    jitter_verts(obj, seed, float(params.get("displacement_magnitude", 0.20)))
    obj.scale.z = float(params.get("z_squash", 0.55))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    decimate(obj, target_tris)
    color = get_color(params.get("color_variant", "granite_grey"), "granite_grey")
    obj.data.materials.append(make_material("rock", color, roughness=0.9))
    origin_to_bottom(obj, -0.3)
    return obj


def make_mushroom_lantern(seed: int, target_tris: int, params: dict):
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.10, depth=0.45,
                                         location=(0, 0, 0.225))
    stem = bpy.context.active_object
    stem.name = "Stem"
    stem.data.materials.append(make_material("mushroom_stem", (0.92, 0.86, 0.74), roughness=0.6))

    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12,
                                          radius=0.30, location=(0, 0, 0.50))
    cap = bpy.context.active_object
    cap.name = "Cap"
    cap_squash = float(params.get("cap_squash", 0.6))
    cap.scale = (1.2, 1.2, cap_squash)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.view_layer.objects.active = cap
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(cap.data)
    for v in [v for v in bm.verts if v.co.z < cap.location.z - 0.45]:
        bm.verts.remove(v)
    bmesh.update_edit_mesh(cap.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    jitter_verts(cap, seed, 0.025)
    cap_color = get_color(params.get("cap_color", "amanita_red"), "amanita_red")
    glow = float(params.get("emission_strength", 0.0))
    emission_rgb = cap_color if glow > 0 else None
    mat_cap = make_material("mushroom_cap", cap_color, roughness=0.5, emission=emission_rgb)
    if glow > 0 and "Emission Strength" in mat_cap.node_tree.nodes["Principled BSDF"].inputs:
        mat_cap.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = glow
    cap.data.materials.append(mat_cap)

    obj = join_active([stem, cap], "Mushroom")
    decimate(obj, target_tris)
    origin_to_bottom(obj, 0.0)
    return obj


def make_wooden_crate(seed: int, target_tris: int, params: dict):
    bpy.ops.mesh.primitive_cube_add(size=0.6, location=(0, 0, 0.3))
    obj = bpy.context.active_object
    obj.name = "Crate"
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = float(params.get("bevel_width", 0.025))
    mod.segments = int(params.get("bevel_segments", 2))
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Bevel")
    decimate(obj, target_tris)
    color = get_color(params.get("color_variant", "oak"), "oak")
    obj.data.materials.append(make_material("wood", color, roughness=0.85))
    origin_to_bottom(obj, 0.0)
    return obj


def make_barrel(seed: int, target_tris: int, params: dict):
    # cylinder with belly (bowed staves) approx via 2 cylinders + scale
    h = float(params.get("height", 0.85))
    r = float(params.get("radius", 0.30))
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=r, depth=h,
                                         location=(0, 0, h / 2))
    body = bpy.context.active_object
    body.name = "Barrel"
    # bow the middle outward
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(body.data)
    for v in bm.verts:
        f = 1.0 + 0.08 * math.sin(math.pi * (v.co.z / h + 0.5))
        v.co.x *= f
        v.co.y *= f
    bmesh.update_edit_mesh(body.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    body.data.materials.append(
        make_material("wood", get_color(params.get("color_variant", "oak"), "oak"),
                      roughness=0.85))
    # iron bands (3 thin tori)
    bands = []
    for z_frac in (0.15, 0.5, 0.85):
        bpy.ops.mesh.primitive_torus_add(major_radius=r * 1.04, minor_radius=0.012,
                                          location=(0, 0, h * z_frac),
                                          major_segments=16, minor_segments=6)
        b = bpy.context.active_object
        b.data.materials.append(make_material(
            f"iron_band{z_frac}", get_color("iron_black", "iron_black"),
            roughness=0.4, metallic=0.7))
        bands.append(b)
    obj = join_active([body, *bands], "Barrel")
    decimate(obj, target_tris)
    origin_to_bottom(obj, 0.0)
    return obj


def make_lantern(seed: int, target_tris: int, params: dict):
    # base disc
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.16, depth=0.05,
                                         location=(0, 0, 0.025))
    base = bpy.context.active_object
    base.data.materials.append(make_material(
        "iron", get_color("iron_black", "iron_black"), roughness=0.3, metallic=0.8))
    # glass column
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.10, depth=0.30,
                                         location=(0, 0, 0.20))
    glass = bpy.context.active_object
    glass_color = get_color(params.get("glass_color", "glass_amber"), "glass_amber")
    em = float(params.get("emission_strength", 4.0))
    mat_glass = make_material("glass", glass_color, roughness=0.1,
                              emission=glass_color)
    if em > 0:
        mat_glass.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = em
    glass.data.materials.append(mat_glass)
    # cap roof (cone)
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.15, depth=0.10,
                                     location=(0, 0, 0.40))
    roof = bpy.context.active_object
    roof.data.materials.append(make_material(
        "iron_roof", get_color("iron_black", "iron_black"), roughness=0.4, metallic=0.8))
    # top loop
    bpy.ops.mesh.primitive_torus_add(major_radius=0.04, minor_radius=0.008,
                                      location=(0, 0, 0.47),
                                      major_segments=8, minor_segments=4)
    loop = bpy.context.active_object
    loop.data.materials.append(make_material(
        "iron_loop", get_color("iron_black", "iron_black"), roughness=0.4, metallic=0.8))
    obj = join_active([base, glass, roof, loop], "Lantern")
    decimate(obj, target_tris)
    origin_to_bottom(obj, 0.0)
    return obj


def make_signpost(seed: int, target_tris: int, params: dict):
    pole_h = float(params.get("pole_height", 1.4))
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.05, depth=pole_h,
                                         location=(0, 0, pole_h / 2))
    pole = bpy.context.active_object
    pole.data.materials.append(make_material(
        "wood_pole", get_color(params.get("color_variant", "weathered_grey"), "weathered_grey"),
        roughness=0.9))
    # plank
    plank_z = pole_h * 0.85
    bpy.ops.mesh.primitive_cube_add(size=1.0,
                                     location=(0.25, 0, plank_z))
    plank = bpy.context.active_object
    plank.scale = (0.45, 0.04, 0.18)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    plank.data.materials.append(make_material(
        "wood_plank", get_color(params.get("color_variant", "weathered_grey"), "weathered_grey"),
        roughness=0.9))
    obj = join_active([pole, plank], "Signpost")
    decimate(obj, target_tris)
    origin_to_bottom(obj, 0.0)
    return obj


def make_treasure_chest(seed: int, target_tris: int, params: dict):
    # body
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.20))
    body = bpy.context.active_object
    body.scale = (0.45, 0.30, 0.20)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = body.modifiers.new("Bevel", "BEVEL")
    mod.width = 0.015
    mod.segments = 2
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier="Bevel")
    body.data.materials.append(make_material(
        "chest_wood", get_color(params.get("color_variant", "oak"), "oak"), roughness=0.85))
    # lid (half cylinder)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.30, depth=0.90,
                                         location=(0, 0, 0.40),
                                         rotation=(0, math.radians(90), 0))
    lid = bpy.context.active_object
    bpy.context.view_layer.objects.active = lid
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(lid.data)
    for v in [v for v in bm.verts if v.co.x < -0.001]:
        bm.verts.remove(v)
    bmesh.update_edit_mesh(lid.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    lid.scale = (0.5, 1.0, 0.65)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    lid.data.materials.append(make_material(
        "chest_lid", get_color(params.get("color_variant", "oak"), "oak"), roughness=0.85))
    # lock
    bpy.ops.mesh.primitive_cube_add(size=0.08, location=(0.30, 0, 0.30))
    lock = bpy.context.active_object
    lock.data.materials.append(make_material(
        "chest_lock", get_color("brass", "brass"), roughness=0.3, metallic=0.8))
    obj = join_active([body, lid, lock], "Chest")
    decimate(obj, target_tris)
    origin_to_bottom(obj, 0.0)
    return obj


def make_fence(seed: int, target_tris: int, params: dict):
    span = float(params.get("span", 1.6))
    post_h = float(params.get("post_height", 1.0))
    posts = []
    for x in (-span / 2, span / 2):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, 0, post_h / 2))
        p = bpy.context.active_object
        p.scale = (0.06, 0.06, post_h / 2)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        posts.append(p)
    rails = []
    for z in (post_h * 0.30, post_h * 0.75):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, z))
        r = bpy.context.active_object
        r.scale = (span / 2 + 0.06, 0.04, 0.04)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        rails.append(r)
    color = get_color(params.get("color_variant", "weathered_grey"), "weathered_grey")
    mat = make_material("fence_wood", color, roughness=0.95)
    for o in [*posts, *rails]:
        o.data.materials.append(mat)
    obj = join_active([*posts, *rails], "Fence")
    decimate(obj, target_tris)
    origin_to_bottom(obj, 0.0)
    return obj


def make_log(seed: int, target_tris: int, params: dict):
    length = float(params.get("length", 1.6))
    radius = float(params.get("radius", 0.18))
    bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=radius, depth=length,
                                         location=(0, 0, radius),
                                         rotation=(0, math.radians(90), 0))
    obj = bpy.context.active_object
    obj.name = "Log"
    # bark roughness
    jitter_verts(obj, seed, float(params.get("bark_jitter", 0.015)))
    color = get_color(params.get("color_variant", "ash"), "ash")
    obj.data.materials.append(make_material("log_bark", color, roughness=0.95))
    decimate(obj, target_tris)
    origin_to_bottom(obj, 0.0)
    return obj


def make_stump(seed: int, target_tris: int, params: dict):
    h = float(params.get("height", 0.40))
    r = float(params.get("radius", 0.30))
    bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=r, depth=h,
                                         location=(0, 0, h / 2))
    obj = bpy.context.active_object
    obj.name = "Stump"
    # taper top
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for v in bm.verts:
        if v.co.z > h * 0.4:
            v.co.x *= 0.92
            v.co.y *= 0.92
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    jitter_verts(obj, seed, 0.012)
    color = get_color(params.get("color_variant", "ash"), "ash")
    obj.data.materials.append(make_material("stump_bark", color, roughness=0.95))
    decimate(obj, target_tris)
    origin_to_bottom(obj, 0.0)
    return obj


def make_tombstone(seed: int, target_tris: int, params: dict):
    w = float(params.get("width", 0.50))
    h = float(params.get("height", 0.85))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, h / 2))
    obj = bpy.context.active_object
    obj.scale = (w / 2, 0.08, h / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # round top: shift top verts toward midpoint
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for v in bm.verts:
        if v.co.z > h * 0.35:
            d = abs(v.co.x) / (w / 2 + 1e-6)
            v.co.z -= d * d * 0.18
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = 0.015
    mod.segments = 2
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Bevel")
    jitter_verts(obj, seed, 0.008)
    color = get_color(params.get("color_variant", "weathered_grey"), "weathered_grey")
    obj.data.materials.append(make_material("stone", color, roughness=0.85))
    decimate(obj, target_tris)
    origin_to_bottom(obj, 0.0)
    return obj


def make_bone_pile(seed: int, target_tris: int, params: dict):
    rng = random.Random(seed)
    n = int(params.get("count", 6))
    parts = []
    color = get_color(params.get("color_variant", "bone_pale"), "bone_pale")
    mat = make_material("bone", color, roughness=0.7)
    for i in range(n):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.10,
                                              location=(rng.uniform(-0.20, 0.20),
                                                        rng.uniform(-0.20, 0.20),
                                                        rng.uniform(0.05, 0.25)))
        b = bpy.context.active_object
        # stretch into a long bone
        b.scale = (rng.uniform(0.7, 1.3),
                   rng.uniform(2.5, 4.0),
                   rng.uniform(0.6, 1.0))
        b.rotation_euler = (
            rng.uniform(0, math.pi),
            rng.uniform(0, math.pi),
            rng.uniform(0, math.pi),
        )
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        b.data.materials.append(mat)
        parts.append(b)
    obj = join_active(parts, "BonePile")
    decimate(obj, target_tris)
    origin_to_bottom(obj, 0.0)
    return obj


def make_ruin_block(seed: int, target_tris: int, params: dict):
    sx = float(params.get("size_x", 0.60))
    sy = float(params.get("size_y", 0.60))
    sz = float(params.get("size_z", 0.45))
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, sz / 2))
    obj = bpy.context.active_object
    obj.scale = (sx / 2, sy / 2, sz / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = float(params.get("bevel_width", 0.025))
    mod.segments = 2
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Bevel")
    # Edge chip noise: jitter only top/edge verts
    rng = random.Random(seed)
    me = obj.data
    chip = float(params.get("chip_magnitude", 0.04))
    for v in me.vertices:
        if v.co.z > sz * 0.30:
            v.co += Vector((
                (rng.random() - 0.5) * chip,
                (rng.random() - 0.5) * chip,
                (rng.random() - 0.5) * chip * 0.5,
            ))
    color = get_color(params.get("color_variant", "granite_grey"), "granite_grey")
    obj.data.materials.append(make_material("stone", color, roughness=0.9))
    decimate(obj, target_tris)
    origin_to_bottom(obj, 0.0)
    return obj


KIND_FACTORIES = {
    "rock_small":       make_rock_small,
    "mushroom_lantern": make_mushroom_lantern,
    "wooden_crate":     make_wooden_crate,
    "barrel":           make_barrel,
    "lantern":          make_lantern,
    "signpost":         make_signpost,
    "treasure_chest":   make_treasure_chest,
    "fence":            make_fence,
    "log":              make_log,
    "stump":            make_stump,
    "tombstone":        make_tombstone,
    "bone_pile":        make_bone_pile,
    "ruin_block":       make_ruin_block,
}


def render_thumbnail(out_path: Path) -> None:
    scene = bpy.context.scene
    available = [e.identifier for e in
                 bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in available else "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.filepath = str(out_path)
    scene.render.film_transparent = True
    bpy.ops.render.render(write_still=True)


def export_glb(out_path: Path, obj) -> None:
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.export_scene.gltf(
        filepath=str(out_path),
        use_selection=True,
        export_format='GLB',
        export_image_format='AUTO',
        export_yup=True,
    )


def main() -> int:
    args = parse_args()
    try:
        params = json.loads(args.params) if args.params else {}
    except json.JSONDecodeError as e:
        print(f"[proc_props] bad --params json: {e}", file=sys.stderr)
        return 1
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    clear_scene()
    add_sun_and_camera()
    fn = KIND_FACTORIES.get(args.kind)
    if fn is None:
        print(f"unknown kind {args.kind!r}; expected one of {list(KIND_FACTORIES)}",
              file=sys.stderr)
        return 1
    obj = fn(args.seed, args.target_tris, params)

    export_glb(out_dir / "model_lod0.glb", obj)
    try:
        render_thumbnail(out_dir / "thumbnail.png")
    except Exception as e:
        print(f"[proc_props] thumbnail render failed: {e}", file=sys.stderr)

    print(f"[proc_props] done -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
