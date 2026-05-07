import json
import numpy as np
from PIL import Image
from pipelines.worldgen_v2 import paths
from pipelines.worldgen_v2.job_schema import Job, DemSpec, EditSpec
from pipelines.worldgen_v2.stages import stage_godot


def _seed_full(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path / "wgout")
    out = paths.job_output_dir("sg_test")
    Image.fromarray(np.zeros((128, 128), dtype=np.uint16), mode="I;16").save(out / "height_16.png")
    Image.fromarray(np.zeros((128, 128, 4), dtype=np.uint8), mode="RGBA").save(out / "biome_splat_rgba.png")
    for i, b in enumerate(("desert", "salt_flat", "rocky_highland", "sparse_pine")):
        Image.fromarray(np.zeros((64, 64, 3), dtype=np.uint8), mode="RGB").save(out / f"albedo_{i}_{b}.png")
    meta = {"bbox": [0, 0, 1, 1], "span_x_m": 1000.0, "span_z_m": 1000.0,
            "elev_min_m": 100.0, "elev_max_m": 2100.0, "source": "x", "fetched_at": "x"}
    (out / "dem_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    pack = {"channels": [{"biome": b, "channel_index": i, "albedo": f"albedo_{i}_{b}.png", "roughness": 0.9}
                          for i, b in enumerate(("desert", "salt_flat", "rocky_highland", "sparse_pine"))],
            "tex_size": 64}
    (out / "pbr_pack.json").write_text(json.dumps(pack), encoding="utf-8")
    job = Job(id="sg_test",
              dem=DemSpec(source="opentopography", dataset="COP30", bbox=(0, 0, 1, 1)),
              edit=EditSpec(style="realistic", strength=1.0),
              biomes=("desert", "salt_flat", "rocky_highland", "sparse_pine"),
              quality="good", cameras=("character",))
    return job, tmp_path / "godot_project"


def test_stage_godot_writes_all_artifacts(tmp_path, monkeypatch):
    job, godot_root = _seed_full(tmp_path, monkeypatch)
    godot_root.mkdir(parents=True, exist_ok=True)
    stage_godot.run(job, godot_project=godot_root)
    terrain_dir = godot_root / "terrain" / "sg_test"
    assert (terrain_dir / "height_16.png").exists()
    assert (terrain_dir / "biome_splat_rgba.png").exists()
    assert (terrain_dir / "terrain_sg_test_material.tres").exists()
    assert (terrain_dir / "terrain_sg_test_collision.tres").exists()
    assert (godot_root / "scenes" / "sg_test_character.tscn").exists()
