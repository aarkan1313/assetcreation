import numpy as np
import pytest
from PIL import Image
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job, DemSpec, EditSpec
from pipelines.worldgen_v2.stages import edit_dem


def _seed_job_with_height(tmp_path, monkeypatch, style):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    out = paths.job_output_dir("ed_test")
    arr = (np.linspace(0, 65535, 64 * 64).astype(np.uint16)).reshape(64, 64)
    Image.fromarray(arr, mode="I;16").save(out / "height_16.png")
    return Job(
        id="ed_test",
        dem=DemSpec(source="opentopography", dataset="COP30", bbox=(0, 0, 1, 1)),
        edit=EditSpec(style=style, strength=1.0),
        biomes=("desert", "salt_flat", "rocky_highland", "sparse_pine"),
        quality="draft",
        cameras=("character",),
    )


def test_realistic_style_is_passthrough(tmp_path, monkeypatch):
    job = _seed_job_with_height(tmp_path, monkeypatch, "realistic")
    edit_dem.run(job)
    out = paths.job_output_dir("ed_test")
    a = np.asarray(Image.open(out / "height_16.png"), dtype=np.uint16)
    b = np.asarray(Image.open(out / "height_16_edited.png"), dtype=np.uint16)
    assert np.array_equal(a, b)


def test_unimplemented_style_raises(tmp_path, monkeypatch):
    job = _seed_job_with_height(tmp_path, monkeypatch, "mythic")
    with pytest.raises(NotImplementedError, match="mythic"):
        edit_dem.run(job)
