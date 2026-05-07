import json
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job, DemSpec, EditSpec
from pipelines.worldgen_v2.godot_writers import scene_tscn


def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path / "wgout")
    out = paths.job_output_dir("st_test")
    meta = {"bbox": [0, 0, 1, 1], "span_x_m": 1000.0, "span_z_m": 1000.0,
            "elev_min_m": 100.0, "elev_max_m": 2100.0, "source": "x", "fetched_at": "x"}
    (out / "dem_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    godot_root = tmp_path / "godot_project"
    (godot_root / "terrain" / "st_test").mkdir(parents=True)
    (godot_root / "terrain" / "st_test" / "terrain_st_test_material.tres").write_text("placeholder", encoding="utf-8")
    (godot_root / "terrain" / "st_test" / "terrain_st_test_collision.tres").write_text("placeholder", encoding="utf-8")
    job = Job(id="st_test",
              dem=DemSpec(source="opentopography", dataset="COP30", bbox=(0, 0, 1, 1)),
              edit=EditSpec(style="realistic", strength=1.0),
              biomes=("desert", "salt_flat", "rocky_highland", "sparse_pine"),
              quality="good", cameras=("character",))
    return job, godot_root


def test_scene_tscn_contains_all_required_nodes(tmp_path, monkeypatch):
    job, godot_root = _seed(tmp_path, monkeypatch)
    targets = scene_tscn.write(job, godot_root)
    assert len(targets) == 1
    text = targets[0].read_text(encoding="utf-8")
    for needle in [
        '[node name="Terrain"',
        'PlaneMesh',
        '[node name="Sun"',
        'DirectionalLight3D',
        '[node name="WorldEnvironment"',
        '[node name="TerrainBody"',
        'StaticBody3D',
        '[node name="FlyCam"',
        '[node name="Camera3D"',
        'FlyCam.gd',
    ]:
        assert needle in text, f"missing: {needle}"


def test_scene_tscn_camera_far_is_km_scale(tmp_path, monkeypatch):
    job, godot_root = _seed(tmp_path, monkeypatch)
    targets = scene_tscn.write(job, godot_root)
    text = targets[0].read_text(encoding="utf-8")
    # FlyCam camera far plane must clear the km-scale terrain
    assert "far = 150000.0" in text


def test_scene_tscn_terrain_size_uses_diorama_render_size(tmp_path, monkeypatch):
    """v2 renders at the v1 diorama scale (default 512m wide), not the raw
    DEM bbox span. PM5 handoff: 'For phase 2 work, ignore --use-real-extents
    and stay on legacy scale.'"""
    job, godot_root = _seed(tmp_path, monkeypatch)
    targets = scene_tscn.write(job, godot_root)
    text = targets[0].read_text(encoding="utf-8")
    assert "size = Vector2(512.0, 512.0)" in text


def test_scene_tscn_writes_one_file_per_camera(tmp_path, monkeypatch):
    job, godot_root = _seed(tmp_path, monkeypatch)
    job_two = job.__class__(**{**job.__dict__, "cameras": ("character", "topdown")})
    targets = scene_tscn.write(job_two, godot_root)
    assert len(targets) == 2
    names = {t.name for t in targets}
    assert "st_test_character.tscn" in names
    assert "st_test_topdown.tscn" in names
