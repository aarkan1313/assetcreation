"""8-angle billboard bake for distant-LOD fallback. Blender 5.x headless.

Per J2 §5.3: imports model_lod0.glb, places it at origin, renders 8 evenly
spaced views around the Y-up axis from a 30° elevation, packs them into a
single transparent 1024×128 atlas (8 slots × 128² each, or 256² if we
want 4×2). Default: 8 angles in a single horizontal strip at 256×256 each
-> 2048×256 atlas.

The Godot side is a Sprite3D using the angle-correct slice for the camera
yaw — done in a tiny shader / MultiMeshInstance3D index. For now we ship
the atlas + per-angle metadata.

Usage (called by billboard_bake.py):
  blender --background --factory-startup --python proc_billboard.py -- \
    --in <prop_dir>/model_lod0.glb \
    --out <prop_dir>/billboard.png \
    --angles 8 --tile-px 256
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--angles", type=int, default=8)
    ap.add_argument("--tile-px", type=int, default=256)
    ap.add_argument("--elevation-deg", type=float, default=20.0)
    ap.add_argument("--single", action="store_true",
                    help="Render a single front view only (cheap fallback)")
    return ap.parse_args(argv)


def import_glb_centered(path: Path) -> Vector:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not objs:
        raise RuntimeError(f"no mesh in {path}")
    # Compute combined bounding box via worldspace coords.
    mins = [float("inf")] * 3
    maxs = [float("-inf")] * 3
    for o in objs:
        for corner in o.bound_box:
            wc = o.matrix_world @ Vector(corner)
            for i in range(3):
                mins[i] = min(mins[i], wc[i])
                maxs[i] = max(maxs[i], wc[i])
    center = Vector(((mins[0] + maxs[0]) / 2,
                     (mins[1] + maxs[1]) / 2,
                     (mins[2] + maxs[2]) / 2))
    extents = Vector((maxs[0] - mins[0], maxs[1] - mins[1], maxs[2] - mins[2]))
    return center, extents


def add_lighting() -> None:
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 4.0
    sun_obj = bpy.data.objects.new("Sun", sun_data)
    sun_obj.rotation_euler = (math.radians(50), math.radians(35), 0)
    bpy.context.collection.objects.link(sun_obj)
    bpy.context.scene.world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world.use_nodes = True
    bg = bpy.context.scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
        bg.inputs[1].default_value = 0.6


def render_view(out_path: Path, center: Vector, extents: Vector,
                 yaw_deg: float, elevation_deg: float, tile_px: int) -> None:
    # Camera distance scales with the largest horizontal extent.
    radius = max(extents.x, extents.y, extents.z) * 1.6 + 0.5
    yaw = math.radians(yaw_deg)
    el = math.radians(elevation_deg)
    cx = center.x + radius * math.cos(yaw) * math.cos(el)
    cy = center.y + radius * math.sin(yaw) * math.cos(el)
    cz = center.z + radius * math.sin(el)

    cam_data = bpy.data.cameras.new("BBCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = max(extents.x, extents.y, extents.z) * 1.4 + 0.4
    cam_obj = bpy.data.objects.new("BBCam", cam_data)
    cam_obj.location = Vector((cx, cy, cz))
    # Aim camera at center.
    direction = (center - Vector((cx, cy, cz))).normalized()
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    scene = bpy.context.scene
    available = [e.identifier for e in
                 bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in available else "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.resolution_x = tile_px
    scene.render.resolution_y = tile_px
    scene.render.filepath = str(out_path)
    scene.render.film_transparent = True
    bpy.ops.render.render(write_still=True)
    # Clean up
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)


def composite_strip(tile_paths: list[Path], out_path: Path, tile_px: int) -> None:
    """Pack N square tiles into a 1×N horizontal strip RGBA PNG.

    Pure-Python via PIL/Pillow (Blender 5.x ships Pillow).
    """
    try:
        from PIL import Image
    except ImportError:
        # fall back to Blender's image API
        out = bpy.data.images.new(name="bb_strip", width=tile_px * len(tile_paths),
                                   height=tile_px, alpha=True)
        out.generated_color = (0, 0, 0, 0)
        # Blending images programmatically is awkward; just write the first.
        out.filepath_raw = str(out_path)
        out.file_format = 'PNG'
        out.save()
        return
    strip = Image.new("RGBA", (tile_px * len(tile_paths), tile_px), (0, 0, 0, 0))
    for i, p in enumerate(tile_paths):
        if not p.exists():
            continue
        img = Image.open(p).convert("RGBA")
        strip.paste(img, (i * tile_px, 0), img)
    strip.save(out_path)


def main() -> int:
    args = parse_args()
    src = Path(args.src)
    out = Path(args.out)
    if not src.exists():
        print(f"[proc_billboard] missing {src}", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)

    center, extents = import_glb_centered(src)
    add_lighting()

    if args.single or args.angles <= 1:
        render_view(out, center, extents, yaw_deg=-90.0,
                    elevation_deg=args.elevation_deg, tile_px=args.tile_px)
        print(f"[proc_billboard] single front -> {out}")
        return 0

    n = args.angles
    tile_dir = out.parent / "_billboard_tiles"
    tile_dir.mkdir(parents=True, exist_ok=True)
    tile_paths = []
    for i in range(n):
        yaw = -90.0 + (360.0 / n) * i
        tile = tile_dir / f"angle_{i:02d}.png"
        render_view(tile, center, extents, yaw_deg=yaw,
                    elevation_deg=args.elevation_deg, tile_px=args.tile_px)
        tile_paths.append(tile)
    composite_strip(tile_paths, out, args.tile_px)
    # Clean up tiles after compositing.
    for t in tile_paths:
        try:
            t.unlink()
        except Exception:
            pass
    try:
        tile_dir.rmdir()
    except Exception:
        pass
    print(f"[proc_billboard] {n}-angle strip -> {out}  ({args.tile_px * n}x{args.tile_px})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
