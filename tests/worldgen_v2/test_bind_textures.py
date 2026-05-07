import json
import numpy as np
from PIL import Image
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job, DemSpec, EditSpec
from pipelines.worldgen_v2.stages import bind_textures


def _job(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    return Job(
        id="bt_test",
        dem=DemSpec(source="opentopography", dataset="COP30", bbox=(0, 0, 1, 1)),
        edit=EditSpec(style="realistic", strength=1.0),
        biomes=("desert", "salt_flat", "rocky_highland", "sparse_pine"),
        quality="draft", cameras=("character",),
    )


def test_bind_writes_4_albedos_and_pbr_pack_json(tmp_path, monkeypatch):
    job = _job(tmp_path, monkeypatch)
    bind_textures.run(job)
    out = paths.job_output_dir("bt_test")
    pack = json.loads((out / "pbr_pack.json").read_text(encoding="utf-8"))
    assert len(pack["channels"]) == 4
    for ch in pack["channels"]:
        assert ch["biome"] in {"desert", "salt_flat", "rocky_highland", "sparse_pine"}
        assert (out / ch["albedo"]).exists()


def test_albedo_has_expected_dominant_color(tmp_path, monkeypatch):
    job = _job(tmp_path, monkeypatch)
    bind_textures.run(job)
    out = paths.job_output_dir("bt_test")
    img = np.asarray(Image.open(out / "albedo_0_desert.png"))
    mean = img.mean(axis=(0, 1))
    assert abs(mean[0] - 194) < 25
    assert abs(mean[1] - 168) < 25
    assert abs(mean[2] - 120) < 25
