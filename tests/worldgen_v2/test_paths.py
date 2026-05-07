from pathlib import Path
from pipelines.worldgen_v2 import paths


def test_root_is_pipeline_dir():
    assert paths.ROOT.name == "worldgen_v2"
    assert paths.ROOT.exists()


def test_job_output_dir_creates_subdir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    out = paths.job_output_dir("death_valley")
    assert out == tmp_path / "death_valley"
    assert out.is_dir()


def test_godot_project_default_points_to_worldgen2():
    assert paths.DEFAULT_GODOT_PROJECT == Path("D:/assets/worldgen2")
