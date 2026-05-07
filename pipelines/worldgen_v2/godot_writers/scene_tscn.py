"""Writer: assemble the final .tscn — terrain mesh + environment + camera.

One file per camera mode listed in `job.cameras`. Cameras supported:
  - "character" — FlyCam.gd noclip rig (Node3D + Camera3D child, WASD+mouse)
  - "iso"       — orthographic camera at elevation_deg/azimuth_deg, no controls
  - "topdown"   — orthographic straight-down (special case of iso, az=0)
  - "worldview" — orthographic high-up overview

The terrain/env/sun/collision block is identical across cameras; only the
camera node tail differs.
"""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np
from pipelines.worldgen_v2 import paths, presets
from pipelines.worldgen_v2.job_schema import Job


def _scene_body(job: Job, span_x_m: float, span_z_m: float, subdiv: int,
                mat_path: str, col_path: str) -> str:
    """Common prefix: ext_resources + sub_resources + Scene root + WorldEnvironment
    + Sun + Terrain + TerrainBody/Shape. Camera + extras get appended after."""
    return (
        '[sub_resource type="PlaneMesh" id="PlaneMesh_terrain"]\n'
        f'size = Vector2({span_x_m}, {span_z_m})\n'
        f'subdivide_width = {subdiv}\n'
        f'subdivide_depth = {subdiv}\n'
        'material = ExtResource("1")\n\n'
        '[sub_resource type="ProceduralSkyMaterial" id="Sky_proc"]\n'
        'sky_top_color = Color(0.35, 0.55, 0.90, 1)\n'
        'sky_horizon_color = Color(0.85, 0.80, 0.70, 1)\n'
        'ground_bottom_color = Color(0.45, 0.40, 0.35, 1)\n'
        'ground_horizon_color = Color(0.65, 0.58, 0.50, 1)\n'
        'sun_angle_max = 10.0\n'
        'sun_curve = 0.05\n\n'
        '[sub_resource type="Sky" id="Sky_res"]\n'
        'sky_material = SubResource("Sky_proc")\n\n'
        '[sub_resource type="Environment" id="Env_res"]\n'
        'background_mode = 2\n'
        'sky = SubResource("Sky_res")\n'
        'tonemap_mode = 2\n'
        'ambient_light_source = 3\n'
        'ambient_light_sky_contribution = 0.6\n'
        'ambient_light_energy = 1.0\n\n'
        '[node name="Scene" type="Node3D"]\n\n'
        '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]\n'
        'environment = SubResource("Env_res")\n\n'
        '[node name="Sun" type="DirectionalLight3D" parent="."]\n'
        'transform = Transform3D(0.866,0,0.5, 0.354,0.707,-0.612, -0.354,0.707,0.612, 0,0,0)\n'
        'light_energy = 2.0\n'
        'shadow_enabled = false\n\n'
        '[node name="Terrain" type="MeshInstance3D" parent="."]\n'
        'mesh = SubResource("PlaneMesh_terrain")\n'
        # extra_cull_margin: PlaneMesh AABB is computed from the un-displaced
        # flat mesh; displaced vertices need to be considered for visibility.
        'extra_cull_margin = 16384.0\n'
        'lod_bias = 128.0\n'
        'gi_mode = 0\n\n'
        '[node name="TerrainBody" type="StaticBody3D" parent="."]\n\n'
        '[node name="TerrainShape" type="CollisionShape3D" parent="TerrainBody"]\n'
        'shape = ExtResource("2")\n\n'
    )


def _flycam_tail(terrain_height_m: float, terrain_size_m: float) -> str:
    """FlyCam: noclip Node3D + child Camera3D driven by FlyCam.gd."""
    fly_y = terrain_height_m * 1.5 + 30.0  # ~125m for 64m terrain
    fly_z = -terrain_size_m * 0.6           # ~300m back for 512m terrain
    pitch_rad = math.radians(-30)
    cos_p = math.cos(pitch_rad)
    sin_p = math.sin(pitch_rad)
    return (
        '[node name="FlyCam" type="Node3D" parent="."]\n'
        f'transform = Transform3D(1,0,0, 0,1,0, 0,0,1, 0,{fly_y},{fly_z})\n'
        'script = ExtResource("3")\n\n'
        '[node name="Camera3D" type="Camera3D" parent="FlyCam"]\n'
        f'transform = Transform3D(1,0,0, 0,{cos_p},{sin_p}, 0,{-sin_p},{cos_p}, 0,0,0)\n'
        'fov = 70.0\n'
        'near = 0.5\n'
        'far = 150000.0\n'
        'current = true\n'
    )


def _ortho_camera_tail(cam_name: str, cam, terrain_size_m: float,
                       terrain_height_m: float, ext_resource_id: str) -> str:
    """Orthographic camera (iso/topdown/worldview).

    Position is set explicitly; orientation is set by IsoCam.gd's `look_at` at
    scene load. The Python-precomputed basis approach was math-correct but
    produced no rendering — Godot's runtime look_at is the proven path.
    """
    target_y = terrain_height_m * 0.5
    if cam_name == "topdown":
        cam_pos = (0.0, terrain_size_m, 0.001)  # tiny z offset to avoid degenerate look_at
        ortho_size = terrain_size_m * 1.05
    elif cam_name == "worldview":
        # High-up overview. Big ortho_size to frame the whole diorama plus margin.
        cam_pos = (terrain_size_m * 0.7, terrain_size_m * 0.9, terrain_size_m * 0.7)
        ortho_size = terrain_size_m * 1.5
    else:  # iso (Diablo-style)
        # 30deg pitch, 45deg azimuth, framed tight on the diorama.
        cam_pos = (terrain_size_m * 0.5, terrain_size_m * 0.4, terrain_size_m * 0.5)
        ortho_size = terrain_size_m * 0.85

    name = f"{cam_name.title()}Cam"
    return (
        f'[node name="{name}" type="Camera3D" parent="."]\n'
        f'transform = Transform3D(1,0,0, 0,1,0, 0,0,1, {cam_pos[0]},{cam_pos[1]},{cam_pos[2]})\n'
        f'script = ExtResource("{ext_resource_id}")\n'
        f'target = Vector3(0, {target_y}, 0)\n'
        'projection = 1\n'  # 1 = ORTHOGONAL
        f'size = {ortho_size}\n'
        f'near = {cam.near}\n'
        f'far = {cam.far}\n'
        'current = true\n'
    )


def _build_one(job: Job, godot_project: Path, cam_name: str) -> Path:
    out = paths.job_output_dir(job.id)
    quality = presets.load_quality(job.quality)
    # v1 diorama scale (default 512m wide, 64m relief). DEM data is real-world
    # topology; only the visual rendering is scaled. PM5: "stay on legacy scale".
    span_x_m = quality.render_size_m
    span_z_m = quality.render_size_m
    terrain_size_m = span_x_m
    terrain_height_m = quality.render_height_m
    subdiv = quality.mesh_subdiv

    mat_path = f"res://terrain/{job.id}/terrain_{job.id}_material.tres"
    col_path = f"res://terrain/{job.id}/terrain_{job.id}_collision.tres"

    body = _scene_body(job, span_x_m, span_z_m, subdiv, mat_path, col_path)

    # Per-camera tail + ext_resource list. FlyCam needs the script ext_resource;
    # ortho cameras don't.
    if cam_name == "character":
        ext_block = (
            f'[ext_resource type="Material" path="{mat_path}" id="1"]\n'
            f'[ext_resource type="Shape3D" path="{col_path}" id="2"]\n'
            f'[ext_resource type="Script" path="res://scripts/FlyCam.gd" id="3"]\n\n'
        )
        tail = _flycam_tail(terrain_height_m, terrain_size_m)
        load_steps = 8
    elif cam_name in ("iso", "topdown", "worldview"):
        cam = presets.load_camera(cam_name)
        ext_block = (
            f'[ext_resource type="Material" path="{mat_path}" id="1"]\n'
            f'[ext_resource type="Shape3D" path="{col_path}" id="2"]\n'
            f'[ext_resource type="Script" path="res://scripts/IsoCam.gd" id="3"]\n\n'
        )
        tail = _ortho_camera_tail(cam_name, cam, terrain_size_m, terrain_height_m,
                                   ext_resource_id="3")
        load_steps = 8
    else:
        raise ValueError(f"unknown camera name: {cam_name!r}")

    text = f'[gd_scene load_steps={load_steps} format=3]\n\n{ext_block}{body}{tail}'

    scenes_dir = godot_project / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    target = scenes_dir / f"{job.id}_{cam_name}.tscn"
    target.write_text(text, encoding="utf-8")
    print(f"[scene_tscn] wrote {target}")
    return target


def write(job: Job, godot_project: Path) -> list[Path]:
    return [_build_one(job, godot_project, cam) for cam in job.cameras]
