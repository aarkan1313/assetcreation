"""Tests for build_tile_splats (mode=hard)."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from PIL import Image
import pytest

import build_tile_splats as bts


def make_world(tmp_path: Path) -> Path:
    bundle = tmp_path / "scale_demo"
    bundle.mkdir()
    layout = {
        (0, 0): "wetland", (1, 0): "desert",
        (0, 1): "forest",  (1, 1): "alpine",
    }
    for (tx, tz), biome in layout.items():
        td = bundle / "tiles" / f"tile_{tx}_{tz}"
        td.mkdir(parents=True)
        meta = {"tile_x": tx, "tile_z": tz, "tile_size_m": 256.0, "biome": biome}
        (td / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return bundle


def fake_manifest():
    return {
        "schema_version": 1,
        "tiers": {
            "standard": {"resolution": 1024, "layers": [
                {"biome": "forest",  "slot": "mid",    "layer": 0, "maps": {}},
                {"biome": "alpine",  "slot": "ground", "layer": 1, "maps": {}},
                {"biome": "alpine",  "slot": "mid",    "layer": 2, "maps": {}},
                {"biome": "alpine",  "slot": "rock",   "layer": 3, "maps": {}},
                {"biome": "desert",  "slot": "ground", "layer": 4, "maps": {}},
                {"biome": "desert",  "slot": "mid",    "layer": 5, "maps": {}},
                {"biome": "desert",  "slot": "rock",   "layer": 6, "maps": {}},
                {"biome": "wetland", "slot": "ground", "layer": 7, "maps": {}},
                {"biome": "wetland", "slot": "mid",    "layer": 8, "maps": {}},
                {"biome": "wetland", "slot": "rock",   "layer": 9, "maps": {}},
            ]},
            "hero":     {"resolution": 4096, "layers": [
                {"biome": "forest", "slot": "ground", "layer": 0, "maps": {}},
                {"biome": "forest", "slot": "rock",   "layer": 1, "maps": {}},
            ]},
        },
    }


def test_hard_mode_writes_per_tile_splat_and_meta(tmp_path: Path):
    bundle = make_world(tmp_path)
    bts.build_splats(
        bundle_dir=bundle, manifest=fake_manifest(),
        mode="hard", splat_size=8, feather_width_m=0.0,
    )
    for tx, tz in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        splat_path = bundle / "tiles" / f"tile_{tx}_{tz}" / "splat.png"
        meta_path  = bundle / "tiles" / f"tile_{tx}_{tz}" / "splat_meta.json"
        assert splat_path.is_file()
        assert meta_path.is_file()
        with Image.open(splat_path) as im:
            assert im.size == (8, 8)
            assert im.mode == "RGBA"


def test_hard_mode_splat_is_pure_first_channel(tmp_path: Path):
    bundle = make_world(tmp_path)
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="hard", splat_size=8, feather_width_m=0.0)
    splat_path = bundle / "tiles" / "tile_0_0" / "splat.png"
    arr = np.asarray(Image.open(splat_path).convert("RGBA"))
    assert (arr[..., 0] == 255).all()
    assert (arr[..., 1] == 0).all()
    assert (arr[..., 2] == 0).all()
    assert (arr[..., 3] == 0).all()


def test_hard_mode_splat_meta_has_per_slot_tier_layer(tmp_path: Path):
    """Each channel's record must carry (tier, layer) for ground/mid/rock."""
    bundle = make_world(tmp_path)
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="hard", splat_size=8, feather_width_m=0.0)
    # tile_0_0 = wetland — standard ground/mid/rock at layers 7/8/9.
    meta = json.loads((bundle / "tiles" / "tile_0_0" / "splat_meta.json").read_text())
    assert len(meta["channels"]) == 4
    c0 = meta["channels"][0]
    assert c0["biome"] == "wetland"
    assert c0["ground"] == {"tier": "standard", "layer": 7}
    assert c0["mid"]    == {"tier": "standard", "layer": 8}
    assert c0["rock"]   == {"tier": "standard", "layer": 9}
    # Channels 1..3 empty.
    for i in range(1, 4):
        assert meta["channels"][i]["biome"] is None
        assert meta["channels"][i]["ground"] is None
        assert meta["channels"][i]["mid"] is None
        assert meta["channels"][i]["rock"] is None


def test_hard_mode_forest_spans_tiers(tmp_path: Path):
    """Forest's ground+rock are hero, mid is standard. Verify meta encodes it."""
    bundle = make_world(tmp_path)
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="hard", splat_size=8, feather_width_m=0.0)
    # tile_0_1 = forest.
    meta = json.loads((bundle / "tiles" / "tile_0_1" / "splat_meta.json").read_text())
    c0 = meta["channels"][0]
    assert c0["biome"] == "forest"
    assert c0["ground"] == {"tier": "hero",     "layer": 0}
    assert c0["mid"]    == {"tier": "standard", "layer": 0}
    assert c0["rock"]   == {"tier": "hero",     "layer": 1}


def test_hard_mode_handles_unknown_biome(tmp_path: Path):
    bundle = make_world(tmp_path)
    bad_meta = bundle / "tiles" / "tile_0_0" / "meta.json"
    data = json.loads(bad_meta.read_text())
    data["biome"] = "tropical"
    bad_meta.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(bts.SplatError, match="tropical"):
        bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                         mode="hard", splat_size=8, feather_width_m=0.0)
