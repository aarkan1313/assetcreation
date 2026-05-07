import json
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job, DemSpec, EditSpec
from pipelines.worldgen_v2.godot_writers import material_tres


def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path / "wgout")
    out = paths.job_output_dir("mt_test")
    meta = {"bbox": [0, 0, 1, 1], "span_x_m": 35886.0, "span_z_m": 44430.0,
            "elev_min_m": 657.6, "elev_max_m": 2712.6, "source": "OT/COP30",
            "fetched_at": "2026-05-06T00:00:00Z"}
    (out / "dem_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    pack = {"channels": [{"biome": b, "channel_index": i, "albedo": f"albedo_{i}_{b}.png", "roughness": 0.9}
                          for i, b in enumerate(("desert", "salt_flat", "rocky_highland", "sparse_pine"))],
            "tex_size": 512}
    (out / "pbr_pack.json").write_text(json.dumps(pack), encoding="utf-8")
    job = Job(id="mt_test",
              dem=DemSpec(source="opentopography", dataset="COP30", bbox=(0, 0, 1, 1)),
              edit=EditSpec(style="realistic", strength=1.0),
              biomes=("desert", "salt_flat", "rocky_highland", "sparse_pine"),
              quality="good", cameras=("character",))
    return job, tmp_path / "godot_project"


def test_material_tres_references_shader_and_textures(tmp_path, monkeypatch):
    job, godot_root = _seed(tmp_path, monkeypatch)
    target = material_tres.write(job, godot_root)
    text = target.read_text(encoding="utf-8")
    assert 'biome_terrain_topdown.gdshader' in text
    assert 'res://terrain/mt_test/height_16.png' in text
    assert 'res://terrain/mt_test/biome_splat_rgba.png' in text
    assert 'shader_parameter/terrain_size_m' in text
    # Diorama render scale: 512m wide / 64m relief by default.
    assert '512' in text
    assert '64' in text
    assert 'shader_parameter/albedo_0' in text


def test_material_tres_writes_to_godot_project_terrain_dir(tmp_path, monkeypatch):
    job, godot_root = _seed(tmp_path, monkeypatch)
    target = material_tres.write(job, godot_root)
    assert target == godot_root / "terrain" / "mt_test" / "terrain_mt_test_material.tres"
