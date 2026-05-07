"""V2 worldgen stager — minimal iso terrain test scene.

Goals over v1:
  - One .tscn with everything inlined; no separate materials/collision/water.
  - Terrain only: PlaneMesh + ShaderMaterial + DirectionalLight + WorldEnvironment + iso Camera3D.
  - No player, no water, no scatter, no comparison scenes, no real-extents toggle.
  - Camera transform is explicit and verified by the Godot Transform3D
    documentation, not heuristics.

Inputs:
  --world   D:/assets/world/worlds/<id>      a v1 world (uses height_16.png,
                                              biome_splat_rgba.png, biome_pbr_pack.json)
  --project C:/worldgen2/new-game-project    target Godot 4.5 project dir

Output:
  <project>/v2/<id>.tscn       single self-contained scene
  <project>/v2/biome_terrain.gdshader  copied from godot_pack/shaders/
  <project>/v2/<id>/*.png      world assets (height, splat, 4× albedo/normal/roughness)
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

SHADER_SRC = Path(r"D:/assets/godot_pack/shaders/biome_terrain.gdshader")
TERRAIN_SIZE_M = 512.0     # fixed; v2 is single-scale.
TERRAIN_HEIGHT_M = 64.0
MESH_SUBDIV = 512          # 1 m per quad on a 512 m plane; matches the 1024px heightmap.
ISO_ORTHO_SIZE = 800.0     # ortho frame height in metres; >> 512m mesh so it's always in frame.
ISO_PITCH_DEG = 35.0       # angle below horizontal — slightly steeper than 30 for less skew.
ISO_YAW_DEG = 45.0         # rotation around world Y from looking down -Z.
ISO_DISTANCE_M = 600.0     # from terrain centre, along the (yaw, pitch) ray.


def _write_lossless_import(png_path: Path, normal_map: bool) -> None:
    """Write a .import sidecar that forces Godot to import this PNG losslessly.

    Without this, Godot defaults to VRAM-compressed (S3TC/BPTC), which is fine
    for view textures (albedo) but corrupts data textures (splat, heightmap).
    Writing .import BEFORE the editor opens the project avoids the auto-import
    using its defaults; if the editor has already imported, deleting the existing
    .import + the .godot/imported/<hash>.* cached files would also work.
    """
    # compress/mode=0 = lossless (no VRAM compression)
    # mipmaps/generate=false avoids smearing across mip levels for data textures
    # detect_3d/compress_to=0 prevents Godot from auto-flipping to VRAM-compressed
    #   the moment the texture is first used in a 3D context.
    body = (
        '[remap]\n\n'
        'importer="texture"\n'
        'type="CompressedTexture2D"\n\n'
        '[deps]\n\n'
        f'source_file="res://{png_path.relative_to(png_path.parents[2]).as_posix()}"\n\n'
        '[params]\n\n'
        'compress/mode=0\n'
        'compress/high_quality=false\n'
        'compress/lossy_quality=0.7\n'
        'compress/hdr_compression=0\n'
        f'compress/normal_map={1 if normal_map else 0}\n'
        'compress/channel_pack=0\n'
        'mipmaps/generate=false\n'
        'mipmaps/limit=-1\n'
        'roughness/mode=0\n'
        'roughness/src_normal=""\n'
        'process/fix_alpha_border=true\n'
        'process/premult_alpha=false\n'
        'process/normal_map_invert_y=false\n'
        'process/hdr_as_srgb=false\n'
        'process/hdr_clamp_exposure=false\n'
        'process/size_limit=0\n'
        'detect_3d/compress_to=0\n'
    )
    sidecar = png_path.with_suffix(png_path.suffix + ".import")
    sidecar.write_text(body, encoding="utf-8")


def iso_camera_transform(distance_m: float, pitch_deg: float, yaw_deg: float) -> str:
    """Compute a Godot Transform3D for an iso camera at (yaw, pitch) looking at origin.

    Godot Transform3D text format = (X.x, X.y, X.z,  Y.x, Y.y, Y.z,  Z.x, Z.y, Z.z,  o.x, o.y, o.z)
    where X/Y/Z are the camera's local right/up/back axes expressed in world space.
    Camera looks down its local -Z, so back axis = (cam_pos - target) normalised.

    We build it by composing two rotations:
      1. Pitch the camera down by pitch_deg around its local right axis
         (after step 2 places it at (0, 0, dist)).
      2. Yaw around world Y by yaw_deg.
    Equivalently: place camera at world Y = sin(pitch)*dist, world XZ = cos(pitch)*dist,
    then rotate about world Y by yaw.
    """
    import math
    p = math.radians(pitch_deg)
    y = math.radians(yaw_deg)

    # Camera position. Start by placing it on the +Z axis tilted up by pitch,
    # then yaw around world Y. Distance is measured from origin.
    cam_y = math.sin(p) * distance_m
    horiz = math.cos(p) * distance_m
    cam_x = math.sin(y) * horiz
    cam_z = math.cos(y) * horiz

    # Build basis: camera looks at origin from cam_pos, world up = (0, 1, 0).
    # back  = normalize(cam_pos - target) = normalize(cam_pos)
    bx, by, bz = cam_x, cam_y, cam_z
    bl = math.sqrt(bx * bx + by * by + bz * bz)
    bx, by, bz = bx / bl, by / bl, bz / bl
    # right = normalize(world_up × back)
    # world_up × back = (1*bz - 0*by, 0*bx - 0*bz, 0*by - 1*bx) = (bz, 0, -bx)
    rx, ry, rz = bz, 0.0, -bx
    rl = math.sqrt(rx * rx + ry * ry + rz * rz)
    rx, ry, rz = rx / rl, ry / rl, rz / rl
    # up = back × right
    ux = by * rz - bz * ry
    uy = bz * rx - bx * rz
    uz = bx * ry - by * rx

    return (
        f"Transform3D({rx:.6f}, {ry:.6f}, {rz:.6f}, "
        f"{ux:.6f}, {uy:.6f}, {uz:.6f}, "
        f"{bx:.6f}, {by:.6f}, {bz:.6f}, "
        f"{cam_x:.4f}, {cam_y:.4f}, {cam_z:.4f})"
    )


def stage(world_dir: Path, project_dir: Path) -> Path:
    pack = json.loads((world_dir / "biome_pbr_pack.json").read_text(encoding="utf-8"))
    world = json.loads((world_dir / "world.json").read_text(encoding="utf-8"))
    world_id = world["id"]

    out_root = project_dir / "v2"
    out_root.mkdir(parents=True, exist_ok=True)
    asset_dir = out_root / world_id
    asset_dir.mkdir(parents=True, exist_ok=True)

    # Copy shader (single source of truth).
    shutil.copy2(SHADER_SRC, out_root / "biome_terrain.gdshader")

    # Copy heightmap + splat. These are DATA textures — they must be imported
    # losslessly. VRAM (S3TC/BPTC) compression on an RGBA splat introduces
    # block-quantisation artifacts that read as black speckles on biome
    # boundaries; on a 16-bit heightmap it collapses elevation steps to ~8 bits.
    shutil.copy2(world_dir / "height_16.png", asset_dir / "height.png")
    shutil.copy2(world_dir / "biome_splat_rgba.png", asset_dir / "splat.png")
    _write_lossless_import(asset_dir / "height.png", normal_map=False)
    _write_lossless_import(asset_dir / "splat.png", normal_map=False)

    # Copy 4 PBR sets bound to RGBA channels in declared order.
    channel_order = pack.get("channel_order", ["R", "G", "B", "A"])
    fallback = next(iter(pack["biomes"].values()))
    channel_to_biome: dict[str, dict] = {}
    for biome_id, info in pack["biomes"].items():
        ch = info.get("splat_channel")
        if ch in channel_order and ch not in channel_to_biome:
            channel_to_biome[ch] = info
    tile_vec = []
    for ch in channel_order:
        info = channel_to_biome.get(ch, fallback)
        for pbr in ("albedo", "normal", "roughness"):
            src = Path(info["maps"][pbr])
            shutil.copy2(src, asset_dir / f"{ch}_{pbr}.png")
        tile_vec.append(float(info.get("tiling_meters", 6.0)))

    # Build the .tscn. Inline all subresources; only ext_resources are PNGs and shader.
    res_root = f"res://v2/{world_id}"
    shader_path = "res://v2/biome_terrain.gdshader"

    ext_lines = [
        f'[ext_resource type="Shader" path="{shader_path}" id="shader"]',
        f'[ext_resource type="Texture2D" path="{res_root}/height.png" id="height"]',
        f'[ext_resource type="Texture2D" path="{res_root}/splat.png" id="splat"]',
    ]
    for ch in channel_order:
        for pbr in ("albedo", "normal", "roughness"):
            ext_lines.append(
                f'[ext_resource type="Texture2D" path="{res_root}/{ch}_{pbr}.png" id="{ch}_{pbr}"]'
            )

    # ShaderMaterial as a sub_resource (inline).
    mat_lines = [
        '[sub_resource type="ShaderMaterial" id="mat"]',
        'shader = ExtResource("shader")',
        'shader_parameter/heightmap = ExtResource("height")',
        'shader_parameter/splat = ExtResource("splat")',
    ]
    for ch in channel_order:
        mat_lines.append(f'shader_parameter/albedo_{ch} = ExtResource("{ch}_albedo")')
        mat_lines.append(f'shader_parameter/normal_{ch} = ExtResource("{ch}_normal")')
        mat_lines.append(f'shader_parameter/rough_{ch} = ExtResource("{ch}_roughness")')
    mat_lines += [
        f'shader_parameter/terrain_size_m = {TERRAIN_SIZE_M}',
        f'shader_parameter/terrain_height_m = {TERRAIN_HEIGHT_M}',
        f'shader_parameter/tile_meters = Vector4({tile_vec[0]}, {tile_vec[1]}, {tile_vec[2]}, {tile_vec[3]})',
        'shader_parameter/triplanar_strength = 0.0',
        'shader_parameter/triplanar_sharpness = 8.0',
        'shader_parameter/metallic_const = 0.0',
        'shader_parameter/ocean_color = Color(0.45, 0.42, 0.32, 1.0)',  # warm sandy fallback, NOT navy blue
        'shader_parameter/ocean_roughness = 0.7',
    ]

    plane_lines = [
        '[sub_resource type="PlaneMesh" id="plane"]',
        f'size = Vector2({TERRAIN_SIZE_M}, {TERRAIN_SIZE_M})',
        f'subdivide_width = {MESH_SUBDIV}',
        f'subdivide_depth = {MESH_SUBDIV}',
        'material = SubResource("mat")',
    ]

    sky_lines = [
        '[sub_resource type="ProceduralSkyMaterial" id="sky_mat"]',
        'sky_top_color = Color(0.32, 0.50, 0.82, 1.0)',
        'sky_horizon_color = Color(0.95, 0.82, 0.65, 1.0)',
        'ground_bottom_color = Color(0.22, 0.25, 0.30, 1.0)',
        'ground_horizon_color = Color(0.65, 0.55, 0.45, 1.0)',
        '',
        '[sub_resource type="Sky" id="sky"]',
        'sky_material = SubResource("sky_mat")',
        '',
        '[sub_resource type="Environment" id="env"]',
        'background_mode = 2',
        'sky = SubResource("sky")',
        'ambient_light_source = 3',
        # Bump ambient so shadow regions read as "in shade" not "void".
        'ambient_light_energy = 0.75',
        'ambient_light_color = Color(0.85, 0.88, 0.95, 1.0)',
        'tonemap_mode = 2',
        'tonemap_exposure = 1.0',
        # NO fog. Fog at iso ortho framing makes everything wash out.
        # NO glow either; can add back once base render is verified.
    ]

    cam_xform = iso_camera_transform(ISO_DISTANCE_M, ISO_PITCH_DEG, ISO_YAW_DEG)

    nodes = [
        '[node name="World" type="Node3D"]',
        '',
        '[node name="Terrain" type="MeshInstance3D" parent="."]',
        'mesh = SubResource("plane")',
        '',
        '[node name="Sun" type="DirectionalLight3D" parent="."]',
        # Sun ~50deg above horizon, yawed 30deg from -Z. Light direction (where
        # rays travel) = (0.321, -0.766, 0.557) — Y negative = shining downward,
        # which is what we want. This matrix was computed (sin(yaw)*cos(elev),
        # -sin(elev), cos(yaw)*cos(elev)) as the local -Z; verified that light
        # actually goes DOWN before being committed.
        'transform = Transform3D(-0.866025, 0.0, 0.5, 0.383022, 0.642788, 0.663414, -0.321394, 0.766044, -0.556670, 0, 200, 0)',
        'light_energy = 1.2',
        'light_color = Color(1.0, 0.96, 0.88, 1.0)',
        'shadow_enabled = true',
        # Cover the whole 512m terrain at iso framing. Default 100m caused the
        # far half of the basin to fail-out-to-pitch-black.
        'directional_shadow_max_distance = 1500.0',
        'directional_shadow_split_1 = 0.1',
        'directional_shadow_split_2 = 0.3',
        'directional_shadow_split_3 = 0.7',
        # Tame self-shadow acne on the high-density 1m-quad heightmap mesh.
        'shadow_bias = 0.05',
        'shadow_normal_bias = 2.0',
        'shadow_blur = 1.5',
        '',
        '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]',
        'environment = SubResource("env")',
        '',
        '[node name="IsoCam" type="Camera3D" parent="."]',
        f'transform = {cam_xform}',
        'projection = 1',
        f'size = {ISO_ORTHO_SIZE}',
        'keep_aspect = 1',  # 1=KEEP_HEIGHT — size is the screen-height in world m, regardless of aspect.
        'near = 0.1',
        'far = 5000.0',
        'current = true',
    ]

    n_subs = 5  # mat + plane + sky_mat + sky + env
    n_exts = len(ext_lines)
    header = f'[gd_scene load_steps={n_subs + n_exts} format=3]'

    tscn = "\n".join(
        [header, ""]
        + ext_lines
        + [""]
        + mat_lines
        + [""]
        + plane_lines
        + [""]
        + sky_lines
        + [""]
        + nodes
        + [""]
    )

    out_scene = out_root / f"{world_id}.tscn"
    out_scene.write_text(tscn, encoding="utf-8")
    return out_scene


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", type=Path, required=True)
    ap.add_argument("--project", type=Path, required=True)
    args = ap.parse_args()

    if not (args.world / "world.json").exists():
        raise SystemExit(f"world.json not found in {args.world}")
    if not (args.project / "project.godot").exists():
        raise SystemExit(f"project.godot not found in {args.project}")

    out = stage(args.world, args.project)
    print(f"v2 staged: {out}")
    print(f"  open in Godot 4.5: project = {args.project}")
    print(f"  scene = res://v2/{args.world.name}.tscn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
