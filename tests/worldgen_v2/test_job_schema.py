import json
import pytest
from pipelines.worldgen_v2 import job_schema


def test_valid_job_loads():
    job = job_schema.load_dict({
        "id": "death_valley",
        "dem": {"source": "opentopography", "dataset": "COP30",
                 "bbox": [-117.0, 36.1, -116.6, 36.5]},
        "edit": {"style": "realistic", "strength": 1.0},
        "biomes": ["desert", "salt_flat", "rocky_highland", "sparse_pine"],
        "quality": "good",
        "cameras": ["character"],
    })
    assert job.id == "death_valley"
    assert job.dem.bbox == (-117.0, 36.1, -116.6, 36.5)
    assert job.quality == "good"


def test_unknown_quality_rejected():
    with pytest.raises(ValueError, match="quality"):
        job_schema.load_dict({
            "id": "x", "dem": {"source": "opentopography", "dataset": "COP30",
                "bbox": [0, 0, 1, 1]},
            "biomes": ["desert"] * 4, "cameras": ["character"], "quality": "ultra"})


def test_bbox_must_be_four_floats():
    with pytest.raises(ValueError, match="bbox"):
        job_schema.load_dict({
            "id": "x", "dem": {"source": "opentopography", "dataset": "COP30",
                "bbox": [0, 0, 1]},
            "biomes": ["desert"] * 4, "cameras": ["character"], "quality": "good"})


def test_biomes_must_be_exactly_four():
    with pytest.raises(ValueError, match="exactly 4"):
        job_schema.load_dict({
            "id": "x", "dem": {"source": "opentopography", "dataset": "COP30",
                "bbox": [0, 0, 1, 1]},
            "biomes": ["desert"] * 3, "cameras": ["character"], "quality": "good"})


def test_template_file_is_valid():
    from pipelines.worldgen_v2 import paths
    data = json.loads((paths.JOBS_DIR / "_template.json").read_text(encoding="utf-8"))
    job = job_schema.load_dict(data)
    assert job.id == "_template"


def test_death_valley_job_is_valid():
    from pipelines.worldgen_v2 import paths
    data = json.loads((paths.JOBS_DIR / "death_valley.json").read_text(encoding="utf-8"))
    job = job_schema.load_dict(data)
    assert job.id == "death_valley"
    assert job.dem.dataset == "COP30"
