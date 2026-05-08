"""Render N orbit views of a GLB inside Blender headless mode.

Usage (called by render_views_runner.py):
  blender --background --factory-startup --python render_views.py -- \
    --glb <path> \
    --out-dir <path> \
    --n-views 6 \
    --resolution 512 \
    --camera-distance 2.5 \
    --elevation-deg 15.0

Outputs: <out-dir>/view_00.png, view_01.png, ... (RGBA PNG, square resolution)
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
import mathutils


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    ap = argparse.ArgumentParser(description="Render GLB orbit views")
    ap.add_argument("--glb", required=True, help="Input GLB path")
    ap.add_argument("--out-dir", required=True, help="Output directory for PNG renders")
    ap.add_argument("--n-views", type=int, default=6, help="Number of orbit views")
    ap.add_argument("--resolution", type=int, default=512, help="Square render resolution (px)")
    ap.add_argument("--camera-distance", type=float, default=2.5, help="Distance from origin (m)")
    ap.add_argument("--elevation-deg", type=float, default=15.0, help="Camera elevation above equator (deg)")
    ap.add_argument("--front-azimuth-deg", type=float, default=270.0,
                    help="Azimuth (deg) that faces the character's front. Default 270 = camera along -Y axis.")
    return ap.parse_args(argv)


def clear_scene() -> None:
    """Delete all default objects (cube, lamp, camera, etc.)."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    # Also purge orphan data blocks
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)
    for block in list(bpy.data.cameras):
        bpy.data.cameras.remove(block)
    for block in list(bpy.data.lights):
        bpy.data.lights.remove(block)


def import_glb(glb_path: Path) -> list[bpy.types.Object]:
    """Import GLB and return list of imported mesh objects."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    imported = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in imported if o.type == 'MESH']
    if not meshes:
        raise RuntimeError(f"No mesh objects imported from {glb_path}")
    return meshes


def get_bounds_center_and_half_diagonal(objects: list[bpy.types.Object]) -> tuple[mathutils.Vector, float]:
    """Return world-space bounding box center and half-diagonal of all objects combined."""
    corners = []
    for obj in objects:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            corners.append(world_corner)
    if not corners:
        return mathutils.Vector((0, 0, 0)), 1.0

    xs = [v.x for v in corners]
    ys = [v.y for v in corners]
    zs = [v.z for v in corners]
    center = mathutils.Vector((
        (min(xs) + max(xs)) / 2,
        (min(ys) + max(ys)) / 2,
        (min(zs) + max(zs)) / 2,
    ))
    half_diag = math.sqrt(
        ((max(xs) - min(xs)) / 2) ** 2 +
        ((max(ys) - min(ys)) / 2) ** 2 +
        ((max(zs) - min(zs)) / 2) ** 2
    )
    return center, max(half_diag, 1e-6)


def normalize_mesh(objects: list[bpy.types.Object]) -> mathutils.Vector:
    """
    Scale and translate all objects so the combined bounding box fits within
    a +-1.0 unit cube centered at the origin.
    Returns the bounding-box center used (pre-normalization) for camera targeting.
    """
    center, half_diag = get_bounds_center_and_half_diagonal(objects)

    # Translate so center lands at origin
    for obj in objects:
        obj.location -= center

    # Scale so the longest half-diagonal == 1.0 (fits within unit cube)
    scale_factor = 1.0 / half_diag
    for obj in objects:
        obj.scale *= scale_factor

    # Apply transforms so the camera math is clean
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)

    return center  # original center (pre-shift), not needed downstream but useful for debug


def add_world_lighting() -> None:
    """Add a simple sky/sun setup so EEVEE renders something visible."""
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True  # ensures node_tree is a proper ShaderNodeTree
    nt = world.node_tree
    nt.nodes.clear()

    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.8, 0.85, 1.0, 1.0)
    bg.inputs['Strength'].default_value = 1.5

    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])

    # Key light (sun)
    sun_data = bpy.data.lights.new("Sun", type='SUN')
    sun_data.energy = 3.0
    sun_obj = bpy.data.objects.new("Sun", sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(45), math.radians(0), math.radians(45))

    # Fill light
    fill_data = bpy.data.lights.new("Fill", type='AREA')
    fill_data.energy = 200.0
    fill_data.size = 4.0
    fill_obj = bpy.data.objects.new("Fill", fill_data)
    bpy.context.collection.objects.link(fill_obj)
    fill_obj.location = (-2, -2, 3)


def setup_render(resolution: int) -> None:
    """Configure scene render settings for EEVEE-Next, RGBA PNG."""
    scene = bpy.context.scene
    # Blender 5.x: 'BLENDER_EEVEE' is the enum value (the engine is still
    # internally EEVEE Next in 5.1, but the enum string remains 'BLENDER_EEVEE').
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.film_transparent = True


def add_camera() -> bpy.types.Object:
    """Add a new camera to the scene and return it."""
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.lens = 50  # 50mm focal length, sensible default
    cam_obj = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    return cam_obj


def point_camera_at(cam_obj: bpy.types.Object, target: mathutils.Vector) -> None:
    """Rotate camera so -Z axis points at target (standard Blender camera convention)."""
    direction = target - cam_obj.location
    # Blender cameras look along -Z; track_axis='-Z', up_axis='Y'
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()


def camera_position(azimuth_deg: float, elevation_deg: float, distance: float) -> mathutils.Vector:
    """Convert spherical coords (azimuth around Z, elevation above XY plane) to cartesian."""
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    x = distance * math.cos(el) * math.cos(az)
    y = distance * math.cos(el) * math.sin(az)
    z = distance * math.sin(el)
    return mathutils.Vector((x, y, z))


def render_view(cam_obj: bpy.types.Object, out_path: Path, target: mathutils.Vector,
                azimuth_deg: float, elevation_deg: float, distance: float) -> None:
    """Position camera and render one view."""
    cam_obj.location = camera_position(azimuth_deg, elevation_deg, distance)
    point_camera_at(cam_obj, target)

    scene = bpy.context.scene
    scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)


def main() -> int:
    args = parse_args()
    glb_path = Path(args.glb)
    out_dir = Path(args.out_dir)
    n_views: int = args.n_views
    resolution: int = args.resolution
    camera_distance: float = args.camera_distance
    elevation_deg: float = args.elevation_deg
    front_azimuth_deg: float = args.front_azimuth_deg

    if not glb_path.exists():
        print(f"[render_views] ERROR: GLB not found: {glb_path}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[render_views] Clearing scene")
    clear_scene()

    print(f"[render_views] Importing {glb_path}")
    meshes = import_glb(glb_path)
    print(f"[render_views] Imported {len(meshes)} mesh object(s)")

    print("[render_views] Normalizing mesh to +-1.0 unit cube")
    normalize_mesh(meshes)

    # After normalization, the bounding box center is at origin
    target = mathutils.Vector((0.0, 0.0, 0.0))

    print("[render_views] Setting up lighting")
    add_world_lighting()

    print("[render_views] Configuring render settings")
    setup_render(resolution)

    cam_obj = add_camera()

    # Orbit starting from front_azimuth_deg so view_00 is always a front-facing shot.
    azimuths = [(front_azimuth_deg + 360.0 * i / n_views) % 360.0 for i in range(n_views)]

    for i, az in enumerate(azimuths):
        out_path = out_dir / f"view_{i:02d}.png"
        print(f"[render_views] Rendering view {i:02d} (az={az:.1f}deg) -> {out_path}")
        render_view(cam_obj, out_path, target, az, elevation_deg, camera_distance)

    print(f"[render_views] Done. {n_views} views written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
