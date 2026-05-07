"""Writer: HeightMapShape3D .tres with map_data = real elevations in metres.
Closes the v1 fall-through bug where collision encoded 64m max instead of real range."""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
from PIL import Image
from pipelines.worldgen_v2 import paths, presets, dem_math
from pipelines.worldgen_v2.job_schema import Job


def write(job: Job, godot_project: Path) -> Path:
    out = paths.job_output_dir(job.id)
    meta = json.loads((out / "dem_meta.json").read_text(encoding="utf-8"))
    quality = presets.load_quality(job.quality)
    res = quality.collision_res

    h_u16 = np.asarray(Image.open(out / "height_16.png"), dtype=np.uint16)
    h_norm = h_u16.astype(np.float32) / 65535.0
    # Match the diorama render scale used by scene_tscn / material_tres.
    terrain_height_m = quality.render_height_m
    h_relative = h_norm * terrain_height_m

    h_resampled = dem_math.resample_to_size(h_relative, res)
    flat = h_resampled.ravel()
    data_str = ", ".join(f"{v:.4f}" for v in flat)

    # cell_size puts the XZ scale INSIDE the shape, so the parent StaticBody3D
    # can stay at identity transform. Avoids Godot's 'non-uniform scale' warning.
    cell_x = quality.render_size_m / max(res - 1, 1)
    cell_z = quality.render_size_m / max(res - 1, 1)

    text = (
        '[gd_resource type="HeightMapShape3D" format=3]\n\n'
        '[resource]\n'
        f'map_width = {res}\n'
        f'map_depth = {res}\n'
        f'cell_size = Vector2({cell_x}, {cell_z})\n'
        f'map_data = PackedFloat32Array({data_str})\n'
    )

    target = godot_project / "terrain" / job.id / f"terrain_{job.id}_collision.tres"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"[collision_tres] wrote {target} ({res}x{res}, scene Y 0..{terrain_height_m:.1f}m, "
          f"footprint {quality.render_size_m:.0f}x{quality.render_size_m:.0f}m)")
    return target
