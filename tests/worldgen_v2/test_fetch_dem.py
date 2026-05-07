import json
import numpy as np
from unittest.mock import patch
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job, DemSpec, EditSpec
from pipelines.worldgen_v2.stages import fetch_dem


def _job(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    return Job(
        id="dv_test",
        dem=DemSpec(source="opentopography", dataset="COP30",
                    bbox=(-117.0, 36.1, -116.6, 36.5)),
        edit=EditSpec(style="realistic", strength=1.0),
        biomes=("desert", "salt_flat", "rocky_highland", "sparse_pine"),
        quality="draft",
        cameras=("character",),
    )


def test_fetch_dem_writes_height_and_meta(tmp_path, monkeypatch):
    job = _job(tmp_path, monkeypatch)
    fake_arr = np.full((128, 128), 1500.0, dtype=np.float32)
    fake_arr[64:, :] = 2000.0  # half higher
    with patch("pipelines.worldgen_v2.stages.fetch_dem.ot_client.fetch_dem",
               return_value=fake_arr):
        fetch_dem.run(job)

    out = paths.job_output_dir("dv_test")
    h = out / "height_16.png"
    m = out / "dem_meta.json"
    assert h.exists()
    assert m.exists()
    meta = json.loads(m.read_text(encoding="utf-8"))
    assert meta["bbox"] == [-117.0, 36.1, -116.6, 36.5]
    assert meta["elev_min_m"] == 1500.0
    assert meta["elev_max_m"] == 2000.0
    assert meta["span_x_m"] > 0 and meta["span_z_m"] > 0
    assert meta["source"] == "OT/COP30"


def test_fetch_dem_resamples_to_quality_size(tmp_path, monkeypatch):
    job = _job(tmp_path, monkeypatch)
    fake_arr = np.zeros((512, 512), dtype=np.float32)
    with patch("pipelines.worldgen_v2.stages.fetch_dem.ot_client.fetch_dem",
               return_value=fake_arr):
        fetch_dem.run(job)
    from PIL import Image
    h = Image.open(paths.job_output_dir("dv_test") / "height_16.png")
    assert h.size == (1024, 1024)  # draft preset
