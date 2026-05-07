"""Stage a biome world into a Godot 4.5 project for in-engine testing.

Reads `<world>/biome_pbr_pack.json` + heightmap/splat, copies textures into the
target project, and writes:
  - assets/biome_terrain_<world_id>/{height,splat,*.png}
  - biome_terrain_<world_id>.tres   (ShaderMaterial preconfigured)
  - biome_terrain_<world_id>.tscn   (MeshInstance3D + DirectionalLight + Camera)

With --walkable, additionally writes a HeightMapShape3D-driven StaticBody3D
matching the visual mesh extent + a CharacterBody3D with WASD+jump and a
third-person camera so you can actually traverse the terrain.

Usage:
  python stage_biome_terrain.py `
    --world D:/assets/world/worlds/qa_fjord_4biome `
    --project C:/Users/josep/test/new-game-project `
    --walkable
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
from pathlib import Path

import numpy as np
from PIL import Image

PBR_CHANNELS = ["albedo", "normal", "roughness"]
SHADERS_DIR = Path(r"D:\assets\godot_pack\shaders")
SHADER_REGISTRY = SHADERS_DIR / "shader_registry.json"
CANONICAL_SHADER = SHADERS_DIR / "biome_terrain.gdshader"
CANONICAL_WATER_SHADER = SHADERS_DIR / "biome_water.gdshader"


def resolve_shader_preset(preset: str) -> dict:
    """Return {shader_path, triplanar_strength, sharpness, name} for a named preset.

    Falls back to the registry's `default` if preset isn't found, and to the
    preset's own `fallback_preset` if its shader file doesn't exist on disk.
    """
    if not SHADER_REGISTRY.exists():
        return {
            "name": "default",
            "shader_path": CANONICAL_SHADER,
            "triplanar_strength": 0.0,
            "triplanar_sharpness": 8.0,
        }
    reg = json.loads(SHADER_REGISTRY.read_text(encoding="utf-8"))
    presets = reg.get("presets", {})
    name = preset if preset in presets else reg.get("default", "topdown")
    p = presets.get(name, {})
    shader_file = SHADERS_DIR / p.get("shader_file", "biome_terrain.gdshader")
    if not shader_file.exists() and p.get("fallback_preset"):
        # Recurse to fallback preset for missing implementations.
        return resolve_shader_preset(p["fallback_preset"])
    return {
        "name": name,
        "shader_path": shader_file,
        "triplanar_strength": float(p.get("triplanar_strength", 1.0)),
        "triplanar_sharpness": float(p.get("triplanar_sharpness", 8.0)),
        "description": p.get("description", ""),
    }
SEA_LEVEL_NORM = 0.32  # matches biome engine sea_level cutoff
DEFAULT_TERRAIN_HEIGHT_M = 64.0   # legacy default when no DEM metadata exists
DEFAULT_TERRAIN_SIZE_M = 512.0
COLLISION_RES = 128  # HeightMapShape3D grid size (collision is much coarser than visual)


def compute_terrain_dims(world: dict, override_size_m: float | None = None,
                         override_height_m: float | None = None,
                         use_real_extents: bool = False) -> tuple[float, float, float]:
    """Compute (terrain_size_m, terrain_height_m, sea_level_m) for this world.

    Priority:
      1. Explicit CLI overrides (--terrain-size-m / --terrain-height-m)
      2. If --use-real-extents AND world.json has dem_meta: real bbox/elev
      3. Defaults: 512m × 64m (legacy / scene-friendly compressed scale)

    Why default to 512m: the existing scatter rules, camera framing, fog, and
    texture tiling are all calibrated for the compressed 512m diorama scale.
    Real-world extents (e.g. 35km × 2km for death_valley) make for accurate
    science-data renders but break visible scatter density and texture tiling.
    Use --use-real-extents OR per-region overrides only when you've also
    re-tuned scatter density and tile_meters.
    """
    if override_size_m is not None:
        size_m = float(override_size_m)
    elif use_real_extents:
        dm = world.get("dem_meta") or {}
        if dm.get("span_x_m") and dm.get("span_z_m"):
            size_m = float(min(dm["span_x_m"], dm["span_z_m"]))
        else:
            size_m = DEFAULT_TERRAIN_SIZE_M
    else:
        size_m = DEFAULT_TERRAIN_SIZE_M

    if override_height_m is not None:
        height_m = float(override_height_m)
    elif use_real_extents:
        dm = world.get("dem_meta") or {}
        if dm.get("elev_range_m") and dm["elev_range_m"] > 1.0:
            # 5% headroom so fantasy_edit's vertical push doesn't clip.
            height_m = float(dm["elev_range_m"]) * 1.05
        else:
            height_m = DEFAULT_TERRAIN_HEIGHT_M
    else:
        height_m = DEFAULT_TERRAIN_HEIGHT_M

    sea_level_m = SEA_LEVEL_NORM * height_m
    return size_m, height_m, sea_level_m


def write_heightmap_shape_tres(
    world_dir: Path, out_path: Path, terrain_height_m: float, res: int
) -> tuple[int, int]:
    """Resample height_16.png to res×res floats in meters; write a HeightMapShape3D .tres."""
    im = Image.open(world_dir / "height_16.png")
    arr = np.asarray(im).astype(np.float32)
    if arr.max() > 1.0:
        arr /= 65535.0 if arr.max() > 256.0 else 255.0
    arr = np.clip(arr, 0.0, 1.0)
    # downsample to res×res via PIL bilinear
    h_im = Image.fromarray(arr, mode="F").resize((res, res), Image.BILINEAR)
    heights = np.asarray(h_im, dtype=np.float32) * terrain_height_m

    # HeightMapShape3D map_data is row-major width×depth; we'll feed it as
    # PackedFloat32Array literal text. Heights flatten in (z, x) order.
    flat = heights.flatten().tolist()
    # Godot text resources can take "PackedFloat32Array(0.0, 1.2, ...)" inline.
    body = ", ".join(f"{v:.4f}" for v in flat)

    out_path.write_text(
        '[gd_resource type="HeightMapShape3D" format=3]\n\n'
        '[resource]\n'
        f'map_width = {res}\n'
        f'map_depth = {res}\n'
        f'map_data = PackedFloat32Array({body})\n',
        encoding="utf-8",
    )
    return (res, res)


def write_arpg_script(test_dir: Path) -> None:
    """ARPG-style controller for ortho character cam:
       WASD moves the player camera-relative (W = away-from-camera in screen).
       No mouse-look — the camera is fixed offset, follows the player.
       Optional click-to-move: left-click sets a target the player walks to.
    """
    (test_dir / "biome_arpg_player.gd").write_text(
        '''extends CharacterBody3D

@export var speed: float = 12.0
@export var sprint_mul: float = 2.0
@export var jump_velocity: float = 8.0
# Set by stager: the world-space yaw that "up the screen" corresponds to.
# For the iso cam (camera at +X +Y +Z, looking at origin) screen-up = -X-Z direction.
@export var screen_up_yaw: float = 0.0  # radians; 0 = -Z is screen-up (topdown default)
@export var click_to_move: bool = true

var _click_target: Vector3 = Vector3.INF
var _has_click_target: bool = false

func _unhandled_input(event: InputEvent) -> void:
\tif click_to_move and event is InputEventMouseButton:
\t\tvar mb := event as InputEventMouseButton
\t\tif mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
\t\t\tvar cam := _find_active_camera()
\t\t\tif cam:
\t\t\t\tvar mp := mb.position
\t\t\t\tvar from := cam.project_ray_origin(mp)
\t\t\t\tvar dir := cam.project_ray_normal(mp)
\t\t\t\t# Intersect ray with the y = self.global_position.y plane.
\t\t\t\tvar t : float = (global_position.y - from.y) / max(dir.y, -1.0e-6)
\t\t\t\tif dir.y < -1.0e-6:
\t\t\t\t\tvar hit := from + dir * t
\t\t\t\t\thit.y = global_position.y
\t\t\t\t\t_click_target = hit
\t\t\t\t\t_has_click_target = true

func _find_active_camera() -> Camera3D:
\tvar root := get_tree().root
\treturn root.get_viewport().get_camera_3d()

func _physics_process(delta: float) -> void:
\tvelocity.y -= 24.0 * delta
\t# Camera-relative basis: yaw rotates around world Y so "screen up" is forward.
\tvar fwd := Vector3(-sin(screen_up_yaw), 0.0, -cos(screen_up_yaw))
\tvar right := Vector3(cos(screen_up_yaw), 0.0, -sin(screen_up_yaw))
\tvar dir := Vector3.ZERO
\tif Input.is_key_pressed(KEY_W): dir += fwd
\tif Input.is_key_pressed(KEY_S): dir -= fwd
\tif Input.is_key_pressed(KEY_D): dir += right
\tif Input.is_key_pressed(KEY_A): dir -= right
\t# Click-to-move: walks toward target unless overridden by WASD.
\tif dir.length() < 0.01 and _has_click_target:
\t\tvar to_target := _click_target - global_position
\t\tto_target.y = 0.0
\t\tif to_target.length() < 0.5:
\t\t\t_has_click_target = false
\t\telse:
\t\t\tdir = to_target.normalized()
\telse:
\t\t_has_click_target = false  # WASD overrides click target
\tif dir.length() > 0.0:
\t\tdir = dir.normalized()
\tvar s := speed * (sprint_mul if Input.is_key_pressed(KEY_SHIFT) else 1.0)
\tvelocity.x = dir.x * s
\tvelocity.z = dir.z * s
\tif is_on_floor() and Input.is_key_pressed(KEY_SPACE):
\t\tvelocity.y = jump_velocity
\tmove_and_slide()
''',
        encoding="utf-8",
    )


def write_character_script(test_dir: Path) -> None:
    """Simple WASD + jump CharacterBody3D with mouse-look camera."""
    (test_dir / "biome_player.gd").write_text(
        '''extends CharacterBody3D

@export var speed: float = 12.0
@export var sprint_mul: float = 2.5
@export var jump_velocity: float = 8.0
@export var mouse_sensitivity: float = 0.0025

var _yaw: float = 0.0
var _pitch: float = -0.35

func _ready() -> void:
\tInput.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _unhandled_input(event: InputEvent) -> void:
\tif event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
\t\t_yaw -= event.relative.x * mouse_sensitivity
\t\t_pitch -= event.relative.y * mouse_sensitivity
\t\t_pitch = clamp(_pitch, -1.4, 0.4)
\tif event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
\t\tInput.mouse_mode = Input.MOUSE_MODE_VISIBLE
\tif event is InputEventMouseButton and event.pressed:
\t\tInput.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _physics_process(delta: float) -> void:
\tvelocity.y -= 24.0 * delta
\tvar fwd := Vector3(-sin(_yaw), 0.0, -cos(_yaw))
\tvar right := Vector3(cos(_yaw), 0.0, -sin(_yaw))
\tvar dir := Vector3.ZERO
\tif Input.is_key_pressed(KEY_W): dir += fwd
\tif Input.is_key_pressed(KEY_S): dir -= fwd
\tif Input.is_key_pressed(KEY_D): dir += right
\tif Input.is_key_pressed(KEY_A): dir -= right
\tif dir.length() > 0.0:
\t\tdir = dir.normalized()
\tvar s := speed * (sprint_mul if Input.is_key_pressed(KEY_SHIFT) else 1.0)
\tvelocity.x = dir.x * s
\tvelocity.z = dir.z * s
\tif is_on_floor() and Input.is_key_pressed(KEY_SPACE):
\t\tvelocity.y = jump_velocity
\tmove_and_slide()
\tvar cam := $Cam as Camera3D
\tif cam:
\t\tcam.rotation = Vector3(_pitch, _yaw, 0.0)
''',
        encoding="utf-8",
    )


def stage(world_dir: Path, project_dir: Path, shader_rel: str, *, walkable: bool,
          mesh_subdiv: int = 256, triplanar_strength: float | None = None,
          shader_preset: str = "topdown",
          override_size_m: float | None = None,
          override_height_m: float | None = None,
          use_real_extents: bool = False) -> None:
    pack = json.loads((world_dir / "biome_pbr_pack.json").read_text(encoding="utf-8"))
    world = json.loads((world_dir / "world.json").read_text(encoding="utf-8"))
    world_id = world["id"]

    # Per-world terrain dimensions (real-world metres), with CLI overrides.
    TERRAIN_SIZE_M, TERRAIN_HEIGHT_M, SEA_LEVEL_M = compute_terrain_dims(
        world, override_size_m, override_height_m, use_real_extents=use_real_extents)
    if world.get("dem_meta"):
        print(f"  [terrain] from dem_meta: {TERRAIN_SIZE_M:.0f}m x {TERRAIN_SIZE_M:.0f}m, "
              f"height {TERRAIN_HEIGHT_M:.0f}m (elev_range "
              f"{world['dem_meta'].get('elev_range_m', 0):.0f}m + 5% headroom)")
    else:
        print(f"  [terrain] default: {TERRAIN_SIZE_M:.0f}m x {TERRAIN_SIZE_M:.0f}m, "
              f"height {TERRAIN_HEIGHT_M:.0f}m")

    # Resolve shader preset from registry; CLI --triplanar overrides preset default.
    preset = resolve_shader_preset(shader_preset)
    eff_triplanar = preset["triplanar_strength"] if triplanar_strength is None else float(triplanar_strength)
    eff_sharpness = preset["triplanar_sharpness"]
    print(f"  [shader] preset='{preset['name']}' file='{preset['shader_path'].name}' "
          f"triplanar_strength={eff_triplanar} sharpness={eff_sharpness}")

    test_dir = project_dir / "biome_terrain_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    out_root = test_dir / "assets" / world_id
    out_root.mkdir(parents=True, exist_ok=True)

    shader_dst = test_dir / "biome_terrain.gdshader"
    if preset["shader_path"].exists():
        shutil.copy2(preset["shader_path"], shader_dst)
    elif CANONICAL_SHADER.exists():
        shutil.copy2(CANONICAL_SHADER, shader_dst)
    elif not shader_dst.exists():
        raise SystemExit(f"shader missing at both {CANONICAL_SHADER} and {shader_dst}")

    water_shader_dst = test_dir / "biome_water.gdshader"
    if CANONICAL_WATER_SHADER.exists():
        shutil.copy2(CANONICAL_WATER_SHADER, water_shader_dst)

    # Always emit a water .tres next to the terrain .tres (cheap, harmless when
    # the world has no sea-level pixels — the plane just sits below terrain).
    water_tres_path = test_dir / f"biome_water_{world_id}.tres"
    water_tres_path.write_text(
        '[gd_resource type="ShaderMaterial" load_steps=2 format=3]\n\n'
        '[ext_resource type="Shader" path="res://biome_terrain_test/biome_water.gdshader" id="water_shader"]\n\n'
        '[resource]\n'
        'shader = ExtResource("water_shader")\n'
        'shader_parameter/shallow_color = Color(0.20, 0.55, 0.65, 1.0)\n'
        'shader_parameter/deep_color = Color(0.02, 0.08, 0.15, 1.0)\n'
        f'shader_parameter/depth_fade_m = 8.0\n'
        f'shader_parameter/shore_softness = 1.5\n'
        f'shader_parameter/wave_speed = 0.25\n'
        f'shader_parameter/wave_strength = 0.35\n'
        f'shader_parameter/wave_scale = 4.0\n'
        f'shader_parameter/metallic_amt = 0.05\n'
        f'shader_parameter/roughness_amt = 0.10\n'
        f'shader_parameter/fresnel_power = 4.0\n'
        f'shader_parameter/specular_amt = 0.65\n',
        encoding="utf-8",
    )

    shutil.copy2(world_dir / "height_16.png", out_root / "height_16.png")
    shutil.copy2(world_dir / "biome_splat_rgba.png", out_root / "biome_splat_rgba.png")

    channel_to_biome: dict[str, str] = {
        info["splat_channel"]: bid for bid, info in pack["biomes"].items()
    }

    tile_vec = [4.0, 4.0, 4.0, 3.0]
    channel_idx = {"R": 0, "G": 1, "B": 2, "A": 3}

    # If a world has fewer than 4 unique biomes, some channels are empty (splat=0).
    # The shader still expects all 4 channels to bind to real textures, so we
    # fall back to the first available biome's textures for empty channels —
    # since the splat is 0 there, those textures are never visually sampled.
    fallback_biome_id = next(iter(pack["biomes"].keys())) if pack["biomes"] else None
    fallback_info = pack["biomes"][fallback_biome_id] if fallback_biome_id else None

    for ch_letter in ["R", "G", "B", "A"]:
        bid = channel_to_biome.get(ch_letter)
        info = pack["biomes"].get(bid) if bid else fallback_info
        if not info:
            print(f"[warn] no biome to bind to channel {ch_letter}; aborting")
            continue
        # tile_meters is the real-world size of one texture tile in metres.
        # Keep it at the registry value (typically 4-8m): on the legacy 512m
        # diorama scale that's 64-128 repeats; on a 35km real-extents terrain
        # that's thousands of repeats at distance (mip-handled fine) but at
        # character-cam framing (~50m) the textures sample at their natural
        # detail. Previously this was scaled up by terrain_size/512, which
        # made each tile 420m on real-extents — so a 50m character cam saw
        # less than 1/8 of one tile and the surface read as a flat color.
        registry_tile = info.get("tiling_meters", 4.0)
        tile_vec[channel_idx[ch_letter]] = registry_tile
        for pbr in PBR_CHANNELS:
            src_path = Path(info["maps"].get(pbr, ""))
            if not src_path or not src_path.exists():
                print(f"[warn] missing {pbr} for channel {ch_letter}; staged scene may not load")
                continue
            dst = out_root / f"{ch_letter}_{pbr}.png"
            shutil.copy2(src_path, dst)

    res_root = f"res://biome_terrain_test/assets/{world_id}"
    shader_res = f"res://{shader_rel.replace(chr(92), '/')}"

    tres_path = project_dir / "biome_terrain_test" / f"biome_terrain_{world_id}.tres"
    tres_lines = [
        '[gd_resource type="ShaderMaterial" load_steps=14 format=3]',
        '',
        f'[ext_resource type="Shader" path="{shader_res}" id="shader"]',
        f'[ext_resource type="Texture2D" path="{res_root}/height_16.png" id="height"]',
        f'[ext_resource type="Texture2D" path="{res_root}/biome_splat_rgba.png" id="splat"]',
    ]
    eid = 1
    for ch in ["R", "G", "B", "A"]:
        for pbr in PBR_CHANNELS:
            p = f"{res_root}/{ch}_{pbr}.png"
            tres_lines.append(f'[ext_resource type="Texture2D" path="{p}" id="{ch}_{pbr}"]')
            eid += 1

    tres_lines += [
        '',
        '[resource]',
        'shader = ExtResource("shader")',
        'shader_parameter/heightmap = ExtResource("height")',
        'shader_parameter/splat = ExtResource("splat")',
    ]
    for ch in ["R", "G", "B", "A"]:
        tres_lines.append(f'shader_parameter/albedo_{ch} = ExtResource("{ch}_albedo")')
        tres_lines.append(f'shader_parameter/normal_{ch} = ExtResource("{ch}_normal")')
        tres_lines.append(f'shader_parameter/rough_{ch} = ExtResource("{ch}_roughness")')

    tres_lines += [
        f'shader_parameter/terrain_size_m = {TERRAIN_SIZE_M}',
        f'shader_parameter/terrain_height_m = {TERRAIN_HEIGHT_M}',
        f'shader_parameter/tile_meters = Vector4({tile_vec[0]}, {tile_vec[1]}, {tile_vec[2]}, {tile_vec[3]})',
        f'shader_parameter/triplanar_strength = {eff_triplanar}',
        f'shader_parameter/triplanar_sharpness = {eff_sharpness}',
        f'shader_parameter/metallic_const = 0.0',
        f'shader_parameter/ocean_color = Color(0.05, 0.10, 0.16, 1.0)',
        f'shader_parameter/ocean_roughness = 0.4',
        '',
    ]
    tres_path.write_text("\n".join(tres_lines), encoding="utf-8")

    test_dir = project_dir / "biome_terrain_test"

    # Auto-include the scatter scene if it exists alongside the world.
    scatter_scene = test_dir / f"biome_scatter_{world_id}.tscn"
    scatter_ext = ""
    scatter_node = ""
    extra_load_steps = 0
    if scatter_scene.exists():
        scatter_ext = (
            f'[ext_resource type="PackedScene" path="res://biome_terrain_test/biome_scatter_{world_id}.tscn" id="scatter"]\n'
        )
        scatter_node = (
            '\n[node name="Scatter" parent="." instance=ExtResource("scatter")]\n'
        )
        extra_load_steps = 1

    # WorldEnvironment with procedural sky + fog. Massively improves the look
    # vs. flat grey background. Every scene gets this.
    env_subres = (
        '\n[sub_resource type="ProceduralSkyMaterial" id="sky_mat"]\n'
        'sky_top_color = Color(0.32, 0.50, 0.82, 1.0)\n'
        'sky_horizon_color = Color(0.95, 0.82, 0.65, 1.0)\n'
        'sky_curve = 0.20\n'
        'sky_energy_multiplier = 1.1\n'
        'ground_bottom_color = Color(0.22, 0.25, 0.30, 1.0)\n'
        'ground_horizon_color = Color(0.65, 0.55, 0.45, 1.0)\n'
        'sun_angle_max = 30.0\n'
        'sun_curve = 0.10\n'
        '\n[sub_resource type="Sky" id="sky"]\n'
        'sky_material = SubResource("sky_mat")\n'
        '\n[sub_resource type="Environment" id="env"]\n'
        'background_mode = 2\n'
        'sky = SubResource("sky")\n'
        'ambient_light_source = 3\n'
        'ambient_light_energy = 1.0\n'
        'ambient_light_color = Color(0.80, 0.85, 0.95, 1.0)\n'
        'tonemap_mode = 2\n'
        'tonemap_exposure = 1.15\n'
        'tonemap_white = 6.0\n'
        'glow_enabled = true\n'
        'glow_intensity = 0.6\n'
        'glow_strength = 1.0\n'
        'glow_bloom = 0.15\n'
        'fog_enabled = true\n'
        'fog_light_color = Color(0.80, 0.85, 0.92, 1.0)\n'
        'fog_density = 0.0012\n'
        'fog_aerial_perspective = 0.45\n'
        'fog_sky_affect = 0.4\n'
        'fog_height = 30.0\n'
        'fog_height_density = 0.05\n'
    )
    env_node = (
        '\n[node name="WorldEnvironment" type="WorldEnvironment" parent="."]\n'
        'environment = SubResource("env")\n'
    )
    extra_load_steps += 3  # +3 sub_resources (ProceduralSkyMaterial, Sky, Environment)

    # Water plane at sea_level_m, covering the terrain footprint.
    # Separate ext_resource (water_mat) + sub_resource (water_plane) + node (Water).
    water_ext = (
        f'[ext_resource type="Material" path="res://biome_terrain_test/biome_water_{world_id}.tres" id="water_mat"]\n'
    )
    water_subres = (
        '\n[sub_resource type="PlaneMesh" id="water_plane"]\n'
        f'size = Vector2({TERRAIN_SIZE_M}, {TERRAIN_SIZE_M})\n'
        'subdivide_width = 1\n'
        'subdivide_depth = 1\n'
        'material = ExtResource("water_mat")\n'
    )
    water_node = (
        '\n[node name="Water" type="MeshInstance3D" parent="."]\n'
        f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, {SEA_LEVEL_M}, 0)\n'
        'mesh = SubResource("water_plane")\n'
        'cast_shadow = 0\n'
    )
    extra_load_steps += 2  # +1 ext_resource (water_mat), +1 sub_resource (water_plane)

    walkable_block = ""
    walkable_load_steps = 4 + extra_load_steps
    walkable_ext = ""
    if walkable:
        shape_path = test_dir / f"biome_collision_{world_id}.tres"
        write_heightmap_shape_tres(world_dir, shape_path,
                                   terrain_height_m=TERRAIN_HEIGHT_M,
                                   res=COLLISION_RES)
        write_character_script(test_dir)

        # Visual plane is TERRAIN_SIZE_M; HeightMapShape3D is COLLISION_RES-1 wide → scale to match.
        scale_xz = TERRAIN_SIZE_M / float(COLLISION_RES - 1)
        # Spawn ABOVE the actual ground at world center, not 80 m of free-fall.
        # Read center pixel of height_16.png (already 16-bit normalized) and
        # convert to meters. terrain_height_m=64 m max. Add 1.5 m clearance so
        # the capsule doesn't intersect the heightmap on the first frame.
        try:
            _h_im = Image.open(world_dir / "height_16.png")
            _h_arr = np.asarray(_h_im, dtype=np.float32)
            if _h_arr.ndim == 3:
                _h_arr = _h_arr[..., 0]
            _hmax = float(_h_arr.max())
            _norm = _h_arr / (65535.0 if _hmax > 256.0 else 255.0)
            _cy = _norm.shape[0] // 2
            _cx = _norm.shape[1] // 2
            ground_y = float(_norm[_cy, _cx]) * TERRAIN_HEIGHT_M
            spawn_y = ground_y + 1.5
        except Exception as _e:
            print(f"[warn] spawn-on-terrain raycast failed ({_e}); falling back to spawn_y=80")
            spawn_y = 80.0
        walkable_load_steps = 7 + extra_load_steps
        walkable_ext = (
            f'[ext_resource type="Shape3D" path="res://biome_terrain_test/biome_collision_{world_id}.tres" id="hshape"]\n'
            f'[ext_resource type="Script" path="res://biome_terrain_test/biome_player.gd" id="player_script"]\n'
        )
        walkable_subresources = (
            '\n[sub_resource type="CapsuleShape3D" id="capsule"]\n'
            'radius = 0.5\n'
            'height = 1.8\n'
        )
        walkable_nodes = (
            '\n[node name="TerrainBody" type="StaticBody3D" parent="."]\n'
            f'transform = Transform3D({scale_xz}, 0, 0, 0, 1, 0, 0, 0, {scale_xz}, 0, 0, 0)\n'
            '\n[node name="TerrainShape" type="CollisionShape3D" parent="TerrainBody"]\n'
            'shape = ExtResource("hshape")\n'
            '\n[node name="Player" type="CharacterBody3D" parent="."]\n'
            f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, {spawn_y}, 0)\n'
            'script = ExtResource("player_script")\n'
            '\n[node name="PlayerShape" type="CollisionShape3D" parent="Player"]\n'
            'shape = SubResource("capsule")\n'
            '\n[node name="Cam" type="Camera3D" parent="Player"]\n'
            'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1.6, 0)\n'
            'fov = 70.0\n'
            f'far = {max(8000.0, TERRAIN_SIZE_M * 4.0)}\n'
            'current = true\n'
        )

    tscn_path = test_dir / f"biome_terrain_{world_id}.tscn"
    walkable_subres = walkable_subresources if walkable else ""
    walkable_nodes_block = walkable_nodes if walkable else ""
    free_camera_block = '' if walkable else (
        '\n[node name="Camera" type="Camera3D" parent="."]\n'
        'transform = Transform3D(0.707, -0.5, 0.5, 0, 0.707, 0.707, -0.707, -0.5, 0.5, 0, 220, 280)\n'
        'fov = 55.0\n'
    )
    tscn_path.write_text(
        f'[gd_scene load_steps={walkable_load_steps} format=3]\n\n'
        f'[ext_resource type="Material" path="res://biome_terrain_test/biome_terrain_{world_id}.tres" id="mat"]\n'
        f'{walkable_ext}'
        f'{scatter_ext}'
        f'{water_ext}\n'
        '[sub_resource type="PlaneMesh" id="plane"]\n'
        f'size = Vector2({TERRAIN_SIZE_M}, {TERRAIN_SIZE_M})\n'
        f'subdivide_width = {mesh_subdiv}\n'
        f'subdivide_depth = {mesh_subdiv}\n'
        'material = ExtResource("mat")\n'
        f'{walkable_subres}'
        f'{water_subres}'
        f'{env_subres}\n'
        '[node name="BiomeTerrain" type="Node3D"]\n\n'
        '[node name="Terrain" type="MeshInstance3D" parent="."]\n'
        'mesh = SubResource("plane")\n\n'
        '[node name="Sun" type="DirectionalLight3D" parent="."]\n'
        'transform = Transform3D(0.866, -0.354, 0.354, 0, 0.707, 0.707, -0.5, -0.612, 0.612, 0, 80, 0)\n'
        'shadow_enabled = true\n'
        'light_energy = 0.9\n'
        'light_color = Color(1.0, 0.96, 0.88, 1.0)\n'
        + env_node
        + free_camera_block
        + water_node
        + walkable_nodes_block
        + scatter_node,
        encoding="utf-8",
    )

    print(f"staged world '{world_id}' into {project_dir}")
    print(f"  scene:    {tscn_path}")
    print(f"  material: {tres_path}")
    print(f"  assets:   {out_root}")
    if walkable:
        print(f"  walkable: ENABLED — HeightMapShape3D + CharacterBody3D added")
        print(f"            controls: WASD / Shift sprint / Space jump / mouse-look / Esc release mouse")
    print("\nIn Godot 4.5: open the project, then load the .tscn and press F6.")


def stage_comparison_scenes(world_dir: Path, project_dir: Path, *, mesh_subdiv: int = 256,
                            cam: str = "worldview",
                            anchor_label: int | None = None,
                            fog: bool = True,
                            glow: bool = True,
                            override_size_m: float | None = None,
                            override_height_m: float | None = None,
                            use_real_extents: bool = False) -> None:
    """Write two extra scenes that reuse the staged terrain + scatter from
    different camera projections so you can A/B the look:

      biome_<id>_topdown.tscn  — orthographic camera looking straight down
      biome_<id>_iso.tscn      — orthographic camera at 45°/30° (Diablo-style 2.5D)

    cam:
      "worldview"  — frames the whole 512m terrain (ortho size 540/720, far cam)
                     Reads as a satellite map / diorama. Good for previewing the
                     world layout, biome distribution, scatter patterns.
      "character"  — ARPG / Diablo-style framing (ortho size ~50m, near cam).
                     Shows ~50m of terrain on screen, scaled for a 1.8m player.
                     Adds a 1.8m capsule "PlayerMarker" at world center for
                     scale reference.

    Both expect biome_terrain_<id>.tres + biome_scatter_<id>.tscn to already exist.
    """
    world = json.loads((world_dir / "world.json").read_text(encoding="utf-8"))
    world_id = world["id"]

    # Per-world terrain dimensions, must match what stage() used.
    TERRAIN_SIZE_M, TERRAIN_HEIGHT_M, SEA_LEVEL_M = compute_terrain_dims(
        world, override_size_m, override_height_m, use_real_extents=use_real_extents)

    test_dir = project_dir / "biome_terrain_test"
    if not (test_dir / f"biome_terrain_{world_id}.tres").exists():
        raise SystemExit(f"main scene must be staged first (missing biome_terrain_{world_id}.tres)")

    # Camera-anchor location:
    #   X/Z anchor: centroid of the densest non-sentinel biome cluster from
    #     biome_labels.png. This keeps the framing on a region with actual
    #     scatter density rather than (0,0,0) which often lands on water /
    #     valley pit / NoData fill.
    #   Y anchor: terrain height at that anchor (sampled from the source
    #     heightmap), so the camera target sits on the actual surface.
    # Heightmap is 0..65535 → 0..1 → 0..TERRAIN_HEIGHT_M metres after the shader
    # vertex displacement.
    base_heightmap_path = Path(world.get("base_heightmap", ""))
    anchor_x_norm = 0.5  # 0..1 over the heightmap, default centre
    anchor_z_norm = 0.5

    biome_labels_path = world_dir / "biome_labels.png"
    if biome_labels_path.exists():
        labels = np.asarray(Image.open(biome_labels_path))
        if labels.ndim == 3:
            labels = labels[..., 0]
        # Sentinel / no-coverage is 255 (or any value >= 4 since slots are 0..3).
        valid_mask = labels < 4
        if valid_mask.any():
            # Pick the requested label, or the densest non-sentinel label.
            if anchor_label is not None and 0 <= anchor_label < 4:
                target_label = anchor_label
                ys, xs = np.where(labels == target_label)
                if not xs.size:
                    # Requested label has no pixels; fall back to densest.
                    counts = np.bincount(labels[valid_mask], minlength=4)
                    target_label = int(counts.argmax())
                    ys, xs = np.where(labels == target_label)
            else:
                counts = np.bincount(labels[valid_mask], minlength=4)
                target_label = int(counts.argmax())
                ys, xs = np.where(labels == target_label)
            if xs.size:
                # Centroid in pixel space → 0..1 normalized.
                cy_px = int(np.median(ys))
                cx_px = int(np.median(xs))
                anchor_z_norm = cy_px / labels.shape[0]
                anchor_x_norm = cx_px / labels.shape[1]
                print(f"  [cam] anchor on biome label {target_label}: "
                      f"x_norm={anchor_x_norm:.3f} z_norm={anchor_z_norm:.3f}")

    if base_heightmap_path.exists():
        h_arr = np.array(Image.open(base_heightmap_path))
        if h_arr.ndim == 3:
            h_arr = h_arr[..., 0]
        ay = int(anchor_z_norm * h_arr.shape[0])
        ax = int(anchor_x_norm * h_arr.shape[1])
        # Window-mean around the anchor to absorb pixel noise.
        win = 8
        y0, y1 = max(0, ay - win), min(h_arr.shape[0], ay + win + 1)
        x0, x1 = max(0, ax - win), min(h_arr.shape[1], ax + win + 1)
        anchor_norm = float(np.mean(h_arr[y0:y1, x0:x1])) / 65535.0
        centre_height_m = anchor_norm * TERRAIN_HEIGHT_M
    else:
        centre_height_m = 0.5 * TERRAIN_HEIGHT_M  # safe fallback

    # Convert anchor 0..1 → world metres (terrain centred on origin, span 512m).
    anchor_x_m = (anchor_x_norm - 0.5) * TERRAIN_SIZE_M
    # Image y axis is downward, world Z is forward; PlaneMesh is XZ so map
    # image-y → world-Z (positive Z = downward in image space).
    anchor_z_m = (anchor_z_norm - 0.5) * TERRAIN_SIZE_M

    has_scatter = (test_dir / f"biome_scatter_{world_id}.tscn").exists()
    scatter_ext = (
        f'[ext_resource type="PackedScene" path="res://biome_terrain_test/biome_scatter_{world_id}.tscn" id="scatter"]\n'
        if has_scatter else ""
    )
    scatter_node = '\n[node name="Scatter" parent="." instance=ExtResource("scatter")]\n' if has_scatter else ""

    has_water = (test_dir / f"biome_water_{world_id}.tres").exists()
    water_ext = (
        f'[ext_resource type="Material" path="res://biome_terrain_test/biome_water_{world_id}.tres" id="water_mat"]\n'
        if has_water else ""
    )
    water_subres = (
        '\n[sub_resource type="PlaneMesh" id="water_plane"]\n'
        f'size = Vector2({TERRAIN_SIZE_M}, {TERRAIN_SIZE_M})\n'
        'subdivide_width = 1\n'
        'subdivide_depth = 1\n'
        'material = ExtResource("water_mat")\n'
        if has_water else ""
    )
    water_node = (
        '\n[node name="Water" type="MeshInstance3D" parent="."]\n'
        f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, {SEA_LEVEL_M}, 0)\n'
        'mesh = SubResource("water_plane")\n'
        'cast_shadow = 0\n'
        if has_water else ""
    )

    n_load = 4 + (1 if has_scatter else 0) + (2 if has_water else 0) + 3  # +3 for env subresources

    # Fog tuning is cam-aware AND scale-aware:
    # - character cam frames ~50m → low density to keep colors readable
    # - worldview frames the whole TERRAIN_SIZE_M → density inversely scales
    #   so atmospheric perspective doesn't whiteout multi-km terrain
    if cam == "character":
        fog_density = 0.0004
        fog_aerial = 0.20
    else:
        # Scale fog density inversely with terrain size, calibrated for the
        # legacy 512m default to give 0.0012; for 35km terrain → 0.000017.
        fog_density = max(0.000005, 0.0012 * (512.0 / max(TERRAIN_SIZE_M, 1.0)))
        fog_aerial = 0.45

    env_subres_text = (
        '\n[sub_resource type="ProceduralSkyMaterial" id="sky_mat"]\n'
        'sky_top_color = Color(0.32, 0.50, 0.82, 1.0)\n'
        'sky_horizon_color = Color(0.95, 0.82, 0.65, 1.0)\n'
        'sky_curve = 0.20\n'
        'sky_energy_multiplier = 1.1\n'
        'ground_bottom_color = Color(0.22, 0.25, 0.30, 1.0)\n'
        'ground_horizon_color = Color(0.65, 0.55, 0.45, 1.0)\n'
        'sun_angle_max = 30.0\n'
        'sun_curve = 0.10\n'
        '\n[sub_resource type="Sky" id="sky"]\n'
        'sky_material = SubResource("sky_mat")\n'
        '\n[sub_resource type="Environment" id="env"]\n'
        'background_mode = 2\n'
        'sky = SubResource("sky")\n'
        'ambient_light_source = 3\n'
        'ambient_light_energy = 1.0\n'
        'ambient_light_color = Color(0.80, 0.85, 0.95, 1.0)\n'
        'tonemap_mode = 2\n'
        'tonemap_exposure = 1.15\n'
        'tonemap_white = 6.0\n'
        f'glow_enabled = {"true" if glow else "false"}\n'
        'glow_intensity = 0.6\n'
        'glow_strength = 1.0\n'
        'glow_bloom = 0.15\n'
        f'fog_enabled = {"true" if fog else "false"}\n'
        'fog_light_color = Color(0.80, 0.85, 0.92, 1.0)\n'
        f'fog_density = {fog_density}\n'
        f'fog_aerial_perspective = {fog_aerial}\n'
        'fog_sky_affect = 0.4\n'
        'fog_height = 30.0\n'
        'fog_height_density = 0.05\n'
    )
    env_node_text = (
        '\n[node name="WorldEnvironment" type="WorldEnvironment" parent="."]\n'
        'environment = SubResource("env")\n'
    )

    common_header = (
        f'[gd_scene load_steps={n_load} format=3]\n\n'
        f'[ext_resource type="Material" path="res://biome_terrain_test/biome_terrain_{world_id}.tres" id="mat"]\n'
        f'{scatter_ext}'
        f'{water_ext}'
        '\n[sub_resource type="PlaneMesh" id="plane"]\n'
        f'size = Vector2({TERRAIN_SIZE_M}, {TERRAIN_SIZE_M})\n'
        f'subdivide_width = {mesh_subdiv}\n'
        f'subdivide_depth = {mesh_subdiv}\n'
        'material = ExtResource("mat")\n'
        f'{water_subres}'
        f'{env_subres_text}'
    )
    common_world = (
        '\n[node name="BiomeTerrain" type="Node3D"]\n\n'
        '[node name="Terrain" type="MeshInstance3D" parent="."]\n'
        'mesh = SubResource("plane")\n\n'
        '[node name="Sun" type="DirectionalLight3D" parent="."]\n'
        'transform = Transform3D(0.866, -0.354, 0.354, 0, 0.707, 0.707, -0.5, -0.612, 0.612, 0, 80, 0)\n'
        'shadow_enabled = true\n'
        'light_energy = 0.9\n'
        'light_color = Color(1.0, 0.96, 0.88, 1.0)\n'
        + env_node_text
        + water_node
    )

    # Camera scaling presets. ortho_size is the screen-space height in world meters.
    if cam == "character":
        # Character cam stays at fixed metric scale regardless of terrain size —
        # a 1.8m player should always read as ~3-5% of frame height.
        # Keep iso_dist_xz / iso_height in a fixed ARPG ratio (~58° pitch) so
        # the basis math below works regardless of TERRAIN_HEIGHT_M.
        topdown_size = 48.0
        topdown_height = 80.0
        iso_size = 52.0
        iso_dist_xz = 35.0
        iso_height = 60.0
    else:
        # Worldview frames the WHOLE terrain regardless of scale.
        # Keep height proportional to dist_xz so basis pitch stays sensible.
        topdown_size = TERRAIN_SIZE_M * 1.05
        topdown_height = TERRAIN_SIZE_M * 0.8
        iso_size = TERRAIN_SIZE_M * 1.5
        iso_dist_xz = TERRAIN_SIZE_M * 0.5
        iso_height = TERRAIN_SIZE_M * 0.4   # gives ~58° pitch like character cam

    # In character cam, anchor the camera (X, Y, Z) to the densest-biome
    # centroid + sampled surface height so the frame is centred on real
    # terrain content, not (0, 0, 0).
    if cam == "character":
        target_x, target_y, target_z = anchor_x_m, centre_height_m, anchor_z_m
    else:
        # Worldview keeps the original (0, 0, 0) target — frames the whole 512m square.
        target_x, target_y, target_z = 0.0, 0.0, 0.0
    iso_cam_y = iso_height + target_y
    topdown_cam_y = topdown_height + target_y
    iso_cam_x = iso_dist_xz + target_x
    iso_cam_z = iso_dist_xz + target_z

    # Compute iso basis for camera at offset (iso_dist_xz, iso_height, iso_dist_xz)
    # looking at origin (its parent — the Player node — sits at the target).
    #
    # Conventions:
    #   - Camera looks down its local -Z (Godot/OpenGL).
    #   - Local +Y is screen-up, local +X is screen-right.
    #   - Godot's Transform3D text format stores basis as flat 9 floats:
    #         (X.x, X.y, X.z, Y.x, Y.y, Y.z, Z.x, Z.y, Z.z, origin...)
    #     where X/Y/Z are the camera's local axes expressed in world space.
    import math
    cam_pos = (iso_dist_xz, iso_height, iso_dist_xz)
    # Forward (camera local -Z) = (target - cam_pos), normalized.
    fwd = (-cam_pos[0], -cam_pos[1], -cam_pos[2])
    flen = math.sqrt(sum(c * c for c in fwd))
    fwd = (fwd[0] / flen, fwd[1] / flen, fwd[2] / flen)
    # Local Z axis = -forward (since forward = -Z).
    zax = (-fwd[0], -fwd[1], -fwd[2])
    # Local X axis (right) = normalize(forward × world_up). For world_up=(0,1,0):
    #   fwd × (0,1,0) = (fwd.z*1 - fwd.y*0, fwd.x*0 - fwd.z*0, fwd.x*0 - fwd.y*0... )
    # Doing it properly: a × b = (a.y*b.z - a.z*b.y, a.z*b.x - a.x*b.z, a.x*b.y - a.y*b.x)
    wu = (0.0, 1.0, 0.0)
    rx = fwd[1] * wu[2] - fwd[2] * wu[1]
    ry = fwd[2] * wu[0] - fwd[0] * wu[2]
    rz = fwd[0] * wu[1] - fwd[1] * wu[0]
    rlen = math.sqrt(rx * rx + ry * ry + rz * rz)
    xax = (rx / rlen, ry / rlen, rz / rlen)
    # Local Y axis (up) = Z × X
    yax = (
        zax[1] * xax[2] - zax[2] * xax[1],
        zax[2] * xax[0] - zax[0] * xax[2],
        zax[0] * xax[1] - zax[1] * xax[0],
    )
    iso_basis_inline = (
        f'{xax[0]:.4f}, {xax[1]:.4f}, {xax[2]:.4f}, '
        f'{yax[0]:.4f}, {yax[1]:.4f}, {yax[2]:.4f}, '
        f'{zax[0]:.4f}, {zax[1]:.4f}, {zax[2]:.4f}'
    )

    # Character cam: real CharacterBody3D player (WASD + click-to-move) with
    # camera as a child so it follows. Reuses the heightmap collision shape
    # written by stage() if available; otherwise the player just falls forever.
    player_subres = ""
    player_ext = ""
    player_topdown_node = ""
    player_iso_node = ""
    extra_load = 0

    if cam == "character":
        write_arpg_script(test_dir)
        # Spawn the player at the anchor (X, surface, Z); add 0.9 so capsule
        # bottom rests on terrain.
        spawn_y = centre_height_m + 0.9
        spawn_x = anchor_x_m
        spawn_z = anchor_z_m

        shape_path = test_dir / f"biome_collision_{world_id}.tres"
        if not shape_path.exists():
            # Build heightmap collision since perspective scene didn't (likely
            # --walkable was off). Cheap; CPU-only.
            try:
                write_heightmap_shape_tres(world_dir, shape_path,
                                           terrain_height_m=TERRAIN_HEIGHT_M,
                                           res=COLLISION_RES)
            except Exception as e:
                print(f"[warn] collision shape write failed ({e}); player will fall through")

        has_collision = shape_path.exists()
        scale_xz = TERRAIN_SIZE_M / float(COLLISION_RES - 1)

        player_subres = (
            '\n[sub_resource type="CapsuleShape3D" id="capsule_shape"]\n'
            'radius = 0.5\n'
            'height = 1.8\n'
            '\n[sub_resource type="CapsuleMesh" id="player_capsule"]\n'
            'radius = 0.4\n'
            'height = 1.8\n'
            '\n[sub_resource type="StandardMaterial3D" id="player_mat"]\n'
            'albedo_color = Color(1.0, 0.25, 0.25, 1.0)\n'
            'metallic = 0.0\n'
            'roughness = 0.6\n'
            'emission_enabled = true\n'
            'emission = Color(1.0, 0.20, 0.20, 1.0)\n'
            'emission_energy_multiplier = 0.4\n'
        )
        extra_load += 3  # capsule_shape + player_capsule + player_mat

        # Common ext_resources for the player + (optional) terrain collision.
        player_ext = (
            f'[ext_resource type="Script" path="res://biome_terrain_test/biome_arpg_player.gd" id="arpg_script"]\n'
        )
        extra_load += 1
        if has_collision:
            player_ext += (
                f'[ext_resource type="Shape3D" path="res://biome_terrain_test/biome_collision_{world_id}.tres" id="hshape"]\n'
            )
            extra_load += 1

        # Build the player + (optional) terrain collision body once; topdown
        # and iso reuse identical bodies, only camera differs (set per scene).
        terrain_body = ""
        if has_collision:
            terrain_body = (
                '\n[node name="TerrainBody" type="StaticBody3D" parent="."]\n'
                f'transform = Transform3D({scale_xz}, 0, 0, 0, 1, 0, 0, 0, {scale_xz}, 0, 0, 0)\n'
                '\n[node name="TerrainShape" type="CollisionShape3D" parent="TerrainBody"]\n'
                'shape = ExtResource("hshape")\n'
            )

        # screen_up_yaw: rotation around world Y so that -Z (player forward)
        # aligns with what the camera sees as "up the screen."
        # Topdown looks straight down with screen-up = world +Z (sin(0)=0,cos(0)=-1
        # in our convention) → yaw=0 means W moves toward -Z = up the screen.
        # Iso cam at +X+Z direction sees screen-up along (-X-Z)/sqrt2 → yaw=π/4
        # rotates W to that direction.
        topdown_yaw = 0.0
        iso_yaw = math.pi / 4.0  # 45°

        topdown_player = (
            terrain_body
            + '\n[node name="Player" type="CharacterBody3D" parent="."]\n'
            f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {spawn_x:.2f}, {spawn_y:.2f}, {spawn_z:.2f})\n'
            'script = ExtResource("arpg_script")\n'
            f'screen_up_yaw = {topdown_yaw}\n'
            '\n[node name="PlayerMesh" type="MeshInstance3D" parent="Player"]\n'
            'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)\n'
            'mesh = SubResource("player_capsule")\n'
            'material_override = SubResource("player_mat")\n'
            '\n[node name="PlayerShape" type="CollisionShape3D" parent="Player"]\n'
            'shape = SubResource("capsule_shape")\n'
            f'\n[node name="TopDownCam" type="Camera3D" parent="Player"]\n'
            'transform = Transform3D(1, 0, 0, 0, 0, 1, 0, 1, 0, '
            f'0, {topdown_height:.2f}, 0)\n'
            'projection = 1\n'
            f'size = {topdown_size}\n'
            'keep_aspect = 0\n'
            f'far = {max(8000.0, TERRAIN_SIZE_M * 4.0)}\n'
            'current = true\n'
        )

        iso_player = (
            terrain_body
            + '\n[node name="Player" type="CharacterBody3D" parent="."]\n'
            f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {spawn_x:.2f}, {spawn_y:.2f}, {spawn_z:.2f})\n'
            'script = ExtResource("arpg_script")\n'
            f'screen_up_yaw = {iso_yaw}\n'
            '\n[node name="PlayerMesh" type="MeshInstance3D" parent="Player"]\n'
            'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)\n'
            'mesh = SubResource("player_capsule")\n'
            'material_override = SubResource("player_mat")\n'
            '\n[node name="PlayerShape" type="CollisionShape3D" parent="Player"]\n'
            'shape = SubResource("capsule_shape")\n'
            f'\n[node name="IsoCam" type="Camera3D" parent="Player"]\n'
            f'transform = Transform3D({iso_basis_inline}, '
            f'{iso_dist_xz:.2f}, {iso_height:.2f}, {iso_dist_xz:.2f})\n'
            'projection = 1\n'
            f'size = {iso_size}\n'
            'keep_aspect = 0\n'
            f'far = {max(8000.0, TERRAIN_SIZE_M * 4.0)}\n'
            'current = true\n'
        )

        player_topdown_node = topdown_player
        player_iso_node = iso_player

    # Bump load_steps for character-cam additions.
    if cam == "character":
        common_header_local = common_header.replace(
            f'load_steps={n_load} format=3',
            f'load_steps={n_load + extra_load} format=3',
        ) + player_subres
        # Inject player ext_resource lines after [gd_scene ...] header line.
        common_header_local = common_header_local.replace(
            'format=3]\n\n', 'format=3]\n\n' + player_ext, 1,
        )
    else:
        common_header_local = common_header

    # Top-down 2D look: orthographic camera looking straight down from +Y.
    # Camera local -Z must point in -Y world direction (i.e. local Z = world +Y).
    # Basis (column-major) inline = (xx,xy,xz, yx,yy,yz, zx,zy,zz):
    #   X axis = (1, 0, 0)
    #   Y axis = (0, 0, 1)   (camera "up" in screen = world +Z)
    #   Z axis = (0, 1, 0)   (camera "back" = world +Y, so forward = -Y → looks down)
    if cam == "character":
        # Camera is a child of the Player node so it follows movement.
        topdown = (
            common_header_local
            + common_world
            + scatter_node
            + player_topdown_node
        )
        iso = (
            common_header_local
            + common_world
            + scatter_node
            + player_iso_node
        )
    else:
        # Worldview: static cameras at fixed offsets, no player.
        topdown = (
            common_header_local
            + common_world
            + '\n[node name="TopDownCam" type="Camera3D" parent="."]\n'
            f'transform = Transform3D(1, 0, 0, 0, 0, 1, 0, 1, 0, '
            f'{target_x:.2f}, {topdown_cam_y}, {target_z:.2f})\n'
            'projection = 1\n'
            f'size = {topdown_size}\n'
            'keep_aspect = 0\n'
            f'far = {max(8000.0, TERRAIN_SIZE_M * 4.0)}\n'
            'current = true\n'
            + scatter_node
        )
        iso = (
            common_header_local
            + common_world
            + '\n[node name="IsoCam" type="Camera3D" parent="."]\n'
            f'transform = Transform3D({iso_basis_inline}, '
            f'{iso_cam_x:.2f}, {iso_cam_y:.2f}, {iso_cam_z:.2f})\n'
            'projection = 1\n'
            f'size = {iso_size}\n'
            'keep_aspect = 0\n'
            f'far = {max(8000.0, TERRAIN_SIZE_M * 4.0)}\n'
            'current = true\n'
            + scatter_node
        )
    (test_dir / f"biome_{world_id}_topdown.tscn").write_text(topdown, encoding="utf-8")
    (test_dir / f"biome_{world_id}_iso.tscn").write_text(iso, encoding="utf-8")

    print(f"\nwrote comparison scenes:")
    print(f"  top-down 2D: biome_{world_id}_topdown.tscn")
    print(f"  2.5D iso:    biome_{world_id}_iso.tscn")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", type=Path, required=True)
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--shader", default="biome_terrain_test/biome_terrain.gdshader")
    ap.add_argument("--walkable", action="store_true",
                    help="add HeightMapShape3D + CharacterBody3D (WASD+jump+mouse-look)")
    ap.add_argument("--cameras", action="store_true",
                    help="also write biome_<id>_topdown.tscn (top-down 2D ortho) and "
                         "biome_<id>_iso.tscn (2.5D iso ortho) for A/B look comparison")
    ap.add_argument("--cam", choices=["worldview", "character"], default="worldview",
                    help="camera framing for --cameras scenes. worldview frames the whole "
                         "512m terrain (satellite/diorama view); character frames ~50m "
                         "(ARPG/Diablo-style) with a 1.8m capsule at world centre for scale.")
    ap.add_argument("--mesh-subdiv", type=int, default=256,
                    help="terrain mesh subdivisions (256 default = 2m/quad on 512m plane; "
                         "512 = 1m/quad matching USGS1m source detail; quality knob 'C').")
    ap.add_argument("--anchor-label", type=int, default=None, choices=[0,1,2,3],
                    help="force iso/topdown camera to anchor on biome label N (0..3). "
                         "Default picks densest non-sentinel cluster. Use to render multiple "
                         "viewpoints of the same scene without re-baking.")
    ap.add_argument("--no-fog", action="store_true",
                    help="disable WorldEnvironment fog (diagnostic).")
    ap.add_argument("--no-glow", action="store_true",
                    help="disable WorldEnvironment glow/bloom (diagnostic).")
    ap.add_argument("--terrain-size-m", type=float, default=None,
                    help="override real-world span (metres) of the staged terrain. "
                         "Default: read from world.json's dem_meta.span_x_m / span_z_m, "
                         "fall back to 512.")
    ap.add_argument("--terrain-height-m", type=float, default=None,
                    help="override real-world vertical relief (metres). "
                         "Default 64m (legacy). Use --use-real-extents for dem_meta-driven dims.")
    ap.add_argument("--use-real-extents", action="store_true",
                    help="read terrain size + height from world.json's dem_meta block "
                         "(real bbox span + elev range). WARNING: scatter density, "
                         "texture tiling, and camera framing are calibrated for the "
                         "default 512m diorama scale; expect visual issues on multi-km worlds "
                         "until those are also retuned.")
    ap.add_argument("--triplanar", type=float, default=None,
                    help="override terrain shader triplanar_strength (0..1). When omitted, "
                         "uses the value from --shader-preset. 0 = pure top-down UV (clean iso); "
                         "1 = slope-aware blend (cliff stretch reduced).")
    ap.add_argument("--shader-preset", default="topdown",
                    choices=["topdown", "triplanar", "hextile", "heightblend"],
                    help="terrain shader preset from godot_pack/shaders/shader_registry.json. "
                         "topdown=pure top-down (default, best for ARPG iso/topdown); "
                         "triplanar=slope-aware (best for first-person); "
                         "hextile=Mikkelsen 2022 (RESERVED, falls back to topdown if missing); "
                         "heightblend=height-based splat (RESERVED).")
    args = ap.parse_args()
    stage(args.world, args.project, args.shader, walkable=args.walkable,
          mesh_subdiv=args.mesh_subdiv, triplanar_strength=args.triplanar,
          shader_preset=args.shader_preset,
          override_size_m=args.terrain_size_m,
          override_height_m=args.terrain_height_m,
          use_real_extents=args.use_real_extents)
    if args.cameras:
        stage_comparison_scenes(args.world, args.project, cam=args.cam,
                                mesh_subdiv=args.mesh_subdiv,
                                anchor_label=args.anchor_label,
                                fog=not args.no_fog, glow=not args.no_glow,
                                override_size_m=args.terrain_size_m,
                                override_height_m=args.terrain_height_m,
                                use_real_extents=args.use_real_extents)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
