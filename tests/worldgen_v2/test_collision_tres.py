import json
import numpy as np
from PIL import Image
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job, DemSpec, EditSpec
from pipelines.worldgen_v2.godot_writers import collision_tres


def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path / "wgout")
    out = paths.job_output_dir("ct_test")
    h = np.zeros((128, 128), dtype=np.uint16)
    h[:] = 65535
    Image.fromarray(h, mode="I;16").save(out / "height_16.png")
    meta = {"bbox": [0, 0, 1, 1], "span_x_m": 1000.0, "span_z_m": 1000.0,
            "elev_min_m": 100.0, "elev_max_m": 2100.0, "source": "x", "fetched_at": "x"}
    (out / "dem_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    job = Job(id="ct_test",
              dem=DemSpec(source="opentopography", dataset="COP30", bbox=(0, 0, 1, 1)),
              edit=EditSpec(style="realistic", strength=1.0),
              biomes=("desert", "salt_flat", "rocky_highland", "sparse_pine"),
              quality="draft", cameras=("character",))
    return job, tmp_path / "godot_project"


def test_collision_tres_uses_diorama_height_range(tmp_path, monkeypatch):
    """map_data values are scaled to the diorama render_height_m (default 64m),
    not the absolute DEM elevation range. This matches the visual mesh, which
    also renders at diorama scale, not real km-scale."""
    job, godot_root = _seed(tmp_path, monkeypatch)
    target = collision_tres.write(job, godot_root)
    text = target.read_text(encoding="utf-8")
    # All-max heightmap → every map_data value should be ~64.0 (draft preset
    # default render_height_m). NOT 2000 (would mean km-scale).
    assert "64.0" in text
    assert "2100.0," not in text
    assert "2000.0," not in text
    assert "map_width = 128" in text
    assert "map_depth = 128" in text


def test_collision_tres_resolution_matches_quality_preset(tmp_path, monkeypatch):
    job, godot_root = _seed(tmp_path, monkeypatch)
    target = collision_tres.write(job, godot_root)
    text = target.read_text(encoding="utf-8")
    assert "map_width = 128" in text
