import numpy as np
from PIL import Image
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job, DemSpec, EditSpec
from pipelines.worldgen_v2.stages import compile_splat


def _seed_height(tmp_path, monkeypatch, h_u16):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    out = paths.job_output_dir("cs_test")
    Image.fromarray(h_u16, mode="I;16").save(out / "height_16_edited.png")
    return Job(
        id="cs_test",
        dem=DemSpec(source="opentopography", dataset="COP30", bbox=(0, 0, 1, 1)),
        edit=EditSpec(style="realistic", strength=1.0),
        biomes=("desert", "salt_flat", "rocky_highland", "sparse_pine"),
        quality="draft", cameras=("character",),
    )


def test_splat_has_4_channels_and_sums_close_to_255(tmp_path, monkeypatch):
    rng = np.random.default_rng(0)
    h = rng.integers(0, 65535, (128, 128), dtype=np.uint16)
    job = _seed_height(tmp_path, monkeypatch, h)
    compile_splat.run(job)
    splat = np.asarray(Image.open(paths.job_output_dir("cs_test") / "biome_splat_rgba.png"))
    assert splat.shape[2] == 4
    interior = splat[16:-16, 16:-16]
    sums = interior.sum(axis=2)
    # Float -> u8 rounding plus large-sigma blur edge effects: tolerate 5 LSB.
    assert np.all((sums >= 250) & (sums <= 260)), f"sum range {sums.min()}..{sums.max()}"


def test_low_flat_terrain_is_dominantly_salt_flat(tmp_path, monkeypatch):
    """A flat near-zero heightmap should produce mostly salt_flat (channel 1)."""
    h = np.zeros((128, 128), dtype=np.uint16)
    h[:] = 200  # ~0.3% of full range, low and flat
    job = _seed_height(tmp_path, monkeypatch, h)
    compile_splat.run(job)
    splat = np.asarray(Image.open(paths.job_output_dir("cs_test") / "biome_splat_rgba.png"))
    interior = splat[16:-16, 16:-16]
    means = interior.mean(axis=(0, 1))
    # salt_flat (index 1) should dominate
    assert means[1] > means[0]  # > desert
    assert means[1] > means[2]  # > rocky
    assert means[1] > means[3]  # > pine


def test_splat_actually_blends(tmp_path, monkeypatch):
    """Whole point of the rewrite: real blend coverage, not posterized."""
    rng = np.random.default_rng(7)
    h = rng.integers(0, 65535, (256, 256), dtype=np.uint16)
    # Smooth it so we have continuous height regions, not pure noise
    from scipy.ndimage import gaussian_filter
    h = gaussian_filter(h.astype(np.float32), sigma=8).astype(np.uint16)
    job = _seed_height(tmp_path, monkeypatch, h)
    compile_splat.run(job)
    splat = np.asarray(Image.open(paths.job_output_dir("cs_test") / "biome_splat_rgba.png"))
    # Count pixels that have a "blended" channel — between 30 and 220
    blend_pixels = ((splat > 30) & (splat < 220)).any(axis=2).mean()
    # The OLD code produced ~22% blend coverage. The new code should be
    # significantly higher because softmax + 12px blur produces real aprons.
    assert blend_pixels > 0.5, f"blend coverage only {blend_pixels*100:.1f}%, expected > 50%"
