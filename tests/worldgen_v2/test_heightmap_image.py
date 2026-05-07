import numpy as np
from PIL import Image
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job, DemSpec, EditSpec
from pipelines.worldgen_v2.godot_writers import heightmap_image


def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path / "wgout")
    out = paths.job_output_dir("hi_test")
    Image.fromarray(np.zeros((128, 128), dtype=np.uint16), mode="I;16").save(out / "height_16.png")
    Image.fromarray(np.zeros((128, 128, 4), dtype=np.uint8), mode="RGBA").save(out / "biome_splat_rgba.png")
    for i, b in enumerate(("desert", "salt_flat", "rocky_highland", "sparse_pine")):
        Image.fromarray(np.zeros((64, 64, 3), dtype=np.uint8), mode="RGB").save(out / f"albedo_{i}_{b}.png")
    job = Job(id="hi_test",
              dem=DemSpec(source="opentopography", dataset="COP30", bbox=(0, 0, 1, 1)),
              edit=EditSpec(style="realistic", strength=1.0),
              biomes=("desert", "salt_flat", "rocky_highland", "sparse_pine"),
              quality="draft", cameras=("character",))
    return job, tmp_path / "godot_project"


def test_writer_copies_files_and_marks_data_textures_lossless(tmp_path, monkeypatch):
    job, godot_root = _seed(tmp_path, monkeypatch)
    heightmap_image.write(job, godot_root)
    terrain_dir = godot_root / "terrain" / "hi_test"
    expected = ["height_16.png", "biome_splat_rgba.png",
                "albedo_0_desert.png", "albedo_1_salt_flat.png",
                "albedo_2_rocky_highland.png", "albedo_3_sparse_pine.png"]
    for f in expected:
        assert (terrain_dir / f).exists(), f"missing {f}"

    for f in ("height_16.png", "biome_splat_rgba.png"):
        sidecar = terrain_dir / f"{f}.import"
        text = sidecar.read_text(encoding="utf-8")
        assert "compress/mode=0" in text
        assert "mipmaps/generate=false" in text
        assert "detect_3d/compress_to=0" in text

    for f in ("albedo_0_desert.png", "albedo_1_salt_flat.png",
              "albedo_2_rocky_highland.png", "albedo_3_sparse_pine.png"):
        assert not (terrain_dir / f"{f}.import").exists(), f"unexpected sidecar for albedo {f}"


def test_writer_clears_stale_godot_import_cache_for_data_textures(tmp_path, monkeypatch):
    job, godot_root = _seed(tmp_path, monkeypatch)
    imported = godot_root / ".godot" / "imported"
    imported.mkdir(parents=True)
    stale_height = imported / "height_16.png-oldhash.s3tc.ctex"
    stale_splat = imported / "biome_splat_rgba.png-oldhash.s3tc.ctex"
    stale_albedo = imported / "albedo_0_desert.png-oldhash.s3tc.ctex"
    stale_height.write_bytes(b"x")
    stale_splat.write_bytes(b"x")
    stale_albedo.write_bytes(b"x")

    heightmap_image.write(job, godot_root)

    assert not stale_height.exists()
    assert not stale_splat.exists()
    assert stale_albedo.exists()
