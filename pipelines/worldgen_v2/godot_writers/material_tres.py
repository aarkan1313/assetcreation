"""Writer: terrain ShaderMaterial .tres referencing the shader + 6 textures."""
from __future__ import annotations
import json
from pathlib import Path
from pipelines.worldgen_v2 import paths, presets
from pipelines.worldgen_v2.job_schema import Job

SHADER_RES_PATH = "res://shaders/biome_terrain_topdown.gdshader"


def write(job: Job, godot_project: Path) -> Path:
    out = paths.job_output_dir(job.id)
    pack = json.loads((out / "pbr_pack.json").read_text(encoding="utf-8"))
    quality = presets.load_quality(job.quality)
    # Use the diorama render scale (matches scene_tscn). PM5: "For phase 2 work,
    # ignore --use-real-extents and stay on legacy scale."
    terrain_size_m = quality.render_size_m
    terrain_size_z_m = quality.render_size_m
    terrain_height_m = quality.render_height_m
    roughness = float(pack["channels"][0]["roughness"])

    def texres(stem: str) -> str:
        return f"res://terrain/{job.id}/{stem}"

    resources = [
        ("Shader", SHADER_RES_PATH),
        ("Texture2D", texres("height_16.png")),
        ("Texture2D", texres("biome_splat_rgba.png")),
        ("Texture2D", texres(pack["channels"][0]["albedo"])),
        ("Texture2D", texres(pack["channels"][1]["albedo"])),
        ("Texture2D", texres(pack["channels"][2]["albedo"])),
        ("Texture2D", texres(pack["channels"][3]["albedo"])),
    ]
    ext_lines = []
    for i, (typ, path) in enumerate(resources, start=1):
        ext_lines.append(f'[ext_resource type="{typ}" path="{path}" id="{i}"]')
    ext_block = "\n".join(ext_lines)

    body = (
        f'[resource]\n'
        f'shader = ExtResource("1")\n'
        f'shader_parameter/terrain_size_m = {terrain_size_m}\n'
        f'shader_parameter/terrain_size_z_m = {terrain_size_z_m}\n'
        f'shader_parameter/terrain_height_m = {terrain_height_m}\n'
        f'shader_parameter/tile_meters = Vector4(4.0, 4.0, 4.0, 3.0)\n'
        f'shader_parameter/roughness_value = {roughness}\n'
        f'shader_parameter/heightmap = ExtResource("2")\n'
        f'shader_parameter/splat = ExtResource("3")\n'
        f'shader_parameter/albedo_0 = ExtResource("4")\n'
        f'shader_parameter/albedo_1 = ExtResource("5")\n'
        f'shader_parameter/albedo_2 = ExtResource("6")\n'
        f'shader_parameter/albedo_3 = ExtResource("7")\n'
    )

    text = (
        f'[gd_resource type="ShaderMaterial" load_steps={len(resources)+1} format=3]\n\n'
        f'{ext_block}\n\n'
        f'{body}'
    )

    target = godot_project / "terrain" / job.id / f"terrain_{job.id}_material.tres"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"[material_tres] wrote {target}")
    return target
