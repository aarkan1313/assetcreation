import numpy as np
from PIL import Image
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job, DemSpec, EditSpec
from pipelines.worldgen_v2.stages import paint_biomes


def _seed(tmp_path, monkeypatch, height_arr_u16):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    out = paths.job_output_dir("pb_test")
    Image.fromarray(height_arr_u16, mode="I;16").save(out / "height_16_edited.png")
    return Job(
        id="pb_test",
        dem=DemSpec(source="opentopography", dataset="COP30", bbox=(0, 0, 1, 1)),
        edit=EditSpec(style="realistic", strength=1.0),
        biomes=("desert", "salt_flat", "rocky_highland", "sparse_pine"),
        quality="draft", cameras=("character",),
    )


def test_very_low_flat_region_is_salt_flat(tmp_path, monkeypatch):
    # Salt flat threshold is h < 0.05 with slope < 0.15 — needs the absolute
    # bottom of the elevation range AND essentially no gradient.
    h = np.zeros((64, 64), dtype=np.uint16)
    h[:] = 1_000  # ~1.5% of 65535 — well within the salt_flat band
    job = _seed(tmp_path, monkeypatch, h)
    paint_biomes.run(job)
    mask = np.asarray(Image.open(paths.job_output_dir("pb_test") / "biome_mask.png"))
    assert (mask == 1).mean() > 0.9


def test_steep_terrain_is_rocky_highland(tmp_path, monkeypatch):
    # Random noise → uniformly-distributed slope; p99 normalizes meaningfully
    # so that a high fraction of pixels passes slope >= 0.4.
    rng = np.random.default_rng(42)
    h = rng.integers(0, 65535, (64, 64), dtype=np.uint16)
    job = _seed(tmp_path, monkeypatch, h)
    paint_biomes.run(job)
    mask = np.asarray(Image.open(paths.job_output_dir("pb_test") / "biome_mask.png"))
    interior = mask[2:-2, 2:-2]
    # On uniform random noise the slope distribution is broad; >50% of interior
    # pixels should land in the rocky_highland (steep) bucket.
    assert (interior == 2).mean() > 0.5


def test_output_values_are_in_0_to_3(tmp_path, monkeypatch):
    rng = np.random.default_rng(0)
    h = rng.integers(0, 65535, (64, 64), dtype=np.uint16)
    job = _seed(tmp_path, monkeypatch, h)
    paint_biomes.run(job)
    mask = np.asarray(Image.open(paths.job_output_dir("pb_test") / "biome_mask.png"))
    assert mask.min() >= 0 and mask.max() <= 3
