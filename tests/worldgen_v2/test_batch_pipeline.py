import json
import numpy as np
from unittest.mock import patch
from pipelines.worldgen_v2 import paths, batch_pipeline


def test_load_job_file(tmp_path):
    p = tmp_path / "j.json"
    p.write_text(json.dumps({
        "id": "tt", "dem": {"source": "opentopography", "dataset": "COP30", "bbox": [0, 0, 1, 1]},
        "biomes": ["desert", "salt_flat", "rocky_highland", "sparse_pine"],
        "quality": "draft", "cameras": ["character"]
    }), encoding="utf-8")
    job = batch_pipeline.load_job(p)
    assert job.id == "tt"


def test_run_calls_all_six_stages(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path / "wgout")
    p = tmp_path / "j.json"
    p.write_text(json.dumps({
        "id": "tt", "dem": {"source": "opentopography", "dataset": "COP30", "bbox": [0, 0, 1, 1]},
        "biomes": ["desert", "salt_flat", "rocky_highland", "sparse_pine"],
        "quality": "draft", "cameras": ["character"]
    }), encoding="utf-8")
    godot_root = tmp_path / "godot_project"
    godot_root.mkdir()
    fake_arr = np.full((128, 128), 1500.0, dtype=np.float32)
    with patch("pipelines.worldgen_v2.stages.fetch_dem.ot_client.fetch_dem",
               return_value=fake_arr):
        batch_pipeline.run_one(p, godot_project=godot_root)
    out = paths.job_output_dir("tt")
    for f in ["height_16.png", "height_16_edited.png", "biome_mask.png",
              "biome_splat_rgba.png", "pbr_pack.json", "dem_meta.json"]:
        assert (out / f).exists(), f"missing {f}"
    assert (godot_root / "scenes" / "tt_character.tscn").exists()
