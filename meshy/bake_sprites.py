"""Headless Blender: animated mesh -> per-angle, per-frame PNG sprites.

Run via project wrapper:
    python D:\\assets\\meshy\\bake.py <input.fbx|glb> [options]

Or directly via Blender:
    blender.exe -b -P bake_sprites.py -- <input> <out_dir> \
        [--angles 8] [--frames 16] [--res 512] [--ortho] \
        [--padding 1.15] [--frame-start 1] [--frame-step 1] [--alpha]

Output structure:
    out_dir/
      angle_000/
        frame_0000.png
        frame_0001.png
        ...
      angle_045/
        ...
      manifest.json   (frame metadata: angles, frame count, resolution, source)
"""
import json
import math
import sys
from pathlib import Path

import bpy
import mathutils


# --- Args ---------------------------------------------------------------------
def parse_args():
    if "--" not in sys.argv:
        raise SystemExit("missing `--` separator before script args")
    args = sys.argv[sys.argv.index("--") + 1:]
    opts = {
        "input": None,
        "out_dir": None,
        "angles": 8,
        "frames": 16,
        "res": 512,
        "ortho": False,
        "padding": 1.15,
        "frame_start": 1,
        "frame_step": 1,
        "alpha": True,
        "elevation": 0.0,  # camera tilt above horizon, in degrees (0 = side, 30 = 3/4 view)
    }
    positional = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--angles":
            opts["angles"] = int(args[i + 1]); i += 2
        elif a == "--frames":
            opts["frames"] = int(args[i + 1]); i += 2
        elif a == "--res":
            opts["res"] = int(args[i + 1]); i += 2
        elif a == "--ortho":
            opts["ortho"] = True; i += 1
        elif a == "--padding":
            opts["padding"] = float(args[i + 1]); i += 2
        elif a == "--frame-start":
            opts["frame_start"] = int(args[i + 1]); i += 2
        elif a == "--frame-step":
            opts["frame_step"] = int(args[i + 1]); i += 2
        elif a == "--no-alpha":
            opts["alpha"] = False; i += 1
        elif a == "--elevation":
            opts["elevation"] = float(args[i + 1]); i += 2
        elif a.startswith("--"):
            raise SystemExit(f"unknown option: {a}")
        else:
            positional.append(a); i += 1
    if len(positional) < 2:
        raise SystemExit("usage: ... -- <input> <out_dir> [options]")
    opts["input"] = Path(positional[0])
    opts["out_dir"] = Path(positional[1])
    return opts


# --- Helpers -----------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_mesh(path: Path):
    ext = path.suffix.lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        raise SystemExit(f"unsupported input format: {ext}")
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def get_animation_frame_range():
    """Return (start, end) frame range from any animated objects in the scene."""
    start = None
    end = None
    for obj in bpy.context.scene.objects:
        if obj.animation_data and obj.animation_data.action:
            fr = obj.animation_data.action.frame_range
            s, e = int(fr[0]), int(fr[1])
            start = s if start is None else min(start, s)
            end = e if end is None else max(end, e)
        # Shape key animations
        if obj.type == "MESH" and obj.data.shape_keys and obj.data.shape_keys.animation_data \
                and obj.data.shape_keys.animation_data.action:
            fr = obj.data.shape_keys.animation_data.action.frame_range
            s, e = int(fr[0]), int(fr[1])
            start = s if start is None else min(start, s)
            end = e if end is None else max(end, e)
    return start, end


def world_bbox(meshes: list):
    """Combined world-space AABB of all mesh objects."""
    mins = mathutils.Vector((math.inf,) * 3)
    maxs = mathutils.Vector((-math.inf,) * 3)
    for m in meshes:
        for c in m.bound_box:
            wc = m.matrix_world @ mathutils.Vector(c)
            mins = mathutils.Vector((min(mins[i], wc[i]) for i in range(3)))
            maxs = mathutils.Vector((max(maxs[i], wc[i]) for i in range(3)))
    return mins, maxs


def setup_world():
    """White background, neutral 3-point-ish lighting."""
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1, 1, 1, 1)
    bg.inputs[1].default_value = 1.0

    # Key sun (front-top)
    key = bpy.data.lights.new(name="Key", type="SUN")
    key.energy = 3.0
    ko = bpy.data.objects.new("Key", key)
    ko.rotation_euler = (math.radians(50), math.radians(20), math.radians(30))
    bpy.context.collection.objects.link(ko)

    # Fill from opposite side (softens shadows)
    fill = bpy.data.lights.new(name="Fill", type="SUN")
    fill.energy = 1.5
    fo = bpy.data.objects.new("Fill", fill)
    fo.rotation_euler = (math.radians(60), math.radians(-30), math.radians(-150))
    bpy.context.collection.objects.link(fo)


def setup_camera(ortho: bool):
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 50
    if ortho:
        cam_data.type = "ORTHO"
    cam_obj = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    return cam_obj


def position_camera(cam_obj, center, radius_xy: float, radius_z: float, height_z: float, angle_deg: float, ortho: bool):
    """Position cam at given azimuth + height, aimed at center.
    Distance accounts for both horizontal extent (radius_xy) and vertical extent
    (radius_z) so tall thin meshes (witches, towers) frame correctly.
    """
    angle = math.radians(angle_deg)
    # For ortho, the ortho_scale is set elsewhere — distance just needs to be
    # outside the mesh. For perspective at 50mm/horizontal-FOV ~40°, we need
    # distance ≈ effective_radius / tan(20°) ≈ radius * 2.75 to fit comfortably.
    effective_radius = max(radius_xy, radius_z * 0.6)
    distance = effective_radius * (2.0 if ortho else 2.75)
    cam_obj.location = (
        center.x + math.sin(angle) * distance,
        center.y - math.cos(angle) * distance,
        center.z + height_z,
    )
    direction = mathutils.Vector(center) - mathutils.Vector(cam_obj.location)
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def configure_render(scene, res: int, alpha: bool):
    # Use EEVEE Next if available, else legacy EEVEE
    available = [e.identifier for e in scene.render.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in available else "BLENDER_EEVEE"
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.image_settings.file_format = "PNG"
    if alpha:
        scene.render.film_transparent = True
        scene.render.image_settings.color_mode = "RGBA"
    else:
        scene.render.film_transparent = False
        scene.render.image_settings.color_mode = "RGB"


# --- Main --------------------------------------------------------------------
def main():
    opts = parse_args()
    print(f"input:  {opts['input']}")
    print(f"out_dir: {opts['out_dir']}")
    print(f"options: angles={opts['angles']} frames={opts['frames']} res={opts['res']} "
          f"ortho={opts['ortho']} alpha={opts['alpha']} elevation={opts['elevation']}")

    if not opts["input"].exists():
        raise SystemExit(f"input not found: {opts['input']}")

    reset_scene()
    meshes = import_mesh(opts["input"])
    if not meshes:
        raise SystemExit("no meshes imported")

    # Determine animation frame range
    src_start, src_end = get_animation_frame_range()
    if src_start is None:
        # Static input — render N copies of the same frame doesn't make sense; render 1 frame
        print("input has no animation; rendering 1 frame per angle")
        opts["frames"] = 1
        src_start = src_end = 1
    else:
        # Distribute requested frames over the animation range
        total = src_end - src_start + 1
        if opts["frames"] >= total:
            print(f"requested {opts['frames']} frames, source has {total}; using all source frames")
            opts["frames"] = total
        print(f"source animation: frames {src_start}..{src_end} ({total} frames)")

    # Build the explicit list of source frames to sample
    if opts["frames"] == 1:
        sample_frames = [src_start]
    else:
        # evenly distribute, including endpoints
        sample_frames = [
            src_start + int(round((src_end - src_start) * i / (opts["frames"] - 1)))
            for i in range(opts["frames"])
        ]

    # Bbox to determine framing
    mins, maxs = world_bbox(meshes)
    # NOTE: animation-driven bbox can grow during animation.
    # For shape-key animation we should sample bbox at multiple frames.
    # Sample at start + middle + end to get a conservative bbox.
    expanded_mins = mathutils.Vector(mins)
    expanded_maxs = mathutils.Vector(maxs)
    for fr in (sample_frames[0], sample_frames[len(sample_frames) // 2], sample_frames[-1]):
        bpy.context.scene.frame_set(fr)
        bpy.context.view_layer.update()
        m, M = world_bbox(meshes)
        for i in range(3):
            expanded_mins[i] = min(expanded_mins[i], m[i])
            expanded_maxs[i] = max(expanded_maxs[i], M[i])
    mins, maxs = expanded_mins, expanded_maxs

    center = (mins + maxs) * 0.5
    size = maxs - mins
    # Use the largest horizontal extent for camera distance, and vertical for height
    radius_xy = max(size.x, size.y) * 0.5 * opts["padding"]
    radius_z = size.z * 0.5 * opts["padding"]

    setup_world()
    cam_obj = setup_camera(opts["ortho"])
    if opts["ortho"]:
        # Ortho scale = full mesh size + padding
        cam_obj.data.ortho_scale = max(size.x, size.y, size.z) * opts["padding"] * 1.05

    # Camera elevation: how high above horizon
    height_z = radius_z * 0.0 + math.sin(math.radians(opts["elevation"])) * radius_xy * 2.0

    scene = bpy.context.scene
    configure_render(scene, opts["res"], opts["alpha"])

    # Render loop
    opts["out_dir"].mkdir(parents=True, exist_ok=True)
    angle_step = 360.0 / opts["angles"]
    rendered = []

    for ai in range(opts["angles"]):
        angle_deg = ai * angle_step
        angle_dir = opts["out_dir"] / f"angle_{int(angle_deg):03d}"
        angle_dir.mkdir(parents=True, exist_ok=True)
        position_camera(cam_obj, center, radius_xy, radius_z, height_z, angle_deg, opts["ortho"])

        for fi, src_frame in enumerate(sample_frames):
            bpy.context.scene.frame_set(src_frame)
            bpy.context.view_layer.update()
            out_file = angle_dir / f"frame_{fi:04d}.png"
            scene.render.filepath = str(out_file)
            bpy.ops.render.render(write_still=True)
            rendered.append({"angle": int(angle_deg), "frame_index": fi, "src_frame": src_frame, "file": str(out_file.relative_to(opts["out_dir"]))})

    manifest = {
        "source": str(opts["input"]),
        "angles": opts["angles"],
        "frames": opts["frames"],
        "resolution": opts["res"],
        "alpha": opts["alpha"],
        "ortho": opts["ortho"],
        "elevation": opts["elevation"],
        "src_animation": {"start": src_start, "end": src_end, "sampled": sample_frames},
        "renders": rendered,
    }
    (opts["out_dir"] / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"rendered {len(rendered)} frames in {opts['out_dir']}")


if __name__ == "__main__":
    main()
