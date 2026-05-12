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
            "standard": {"resolution": 1024, "slot_pool": list(range(10)), "layers": [
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
            "hero": {"resolution": 4096, "slot_pool": [0, 1], "layers": [
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


def test_hard_mode_splat_meta_has_per_slot_tier_slot(tmp_path: Path):
    """Each channel's record must carry (tier, slot) for ground/mid/rock.
    `slot` is a slot-pool index — in v1 the pool is identity so the
    numbers match the raw layer indices, but the field name reflects
    the indirection."""
    bundle = make_world(tmp_path)
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="hard", splat_size=8, feather_width_m=0.0)
    meta = json.loads((bundle / "tiles" / "tile_0_0" / "splat_meta.json").read_text())
    assert len(meta["channels"]) == 4
    c0 = meta["channels"][0]
    assert c0["biome"] == "wetland"
    assert c0["ground"] == {"tier": "standard", "slot": 7}
    assert c0["mid"]    == {"tier": "standard", "slot": 8}
    assert c0["rock"]   == {"tier": "standard", "slot": 9}
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
    meta = json.loads((bundle / "tiles" / "tile_0_1" / "splat_meta.json").read_text())
    c0 = meta["channels"][0]
    assert c0["biome"] == "forest"
    assert c0["ground"] == {"tier": "hero",     "slot": 0}
    assert c0["mid"]    == {"tier": "standard", "slot": 0}
    assert c0["rock"]   == {"tier": "hero",     "slot": 1}


def test_hard_mode_non_identity_pool(tmp_path: Path):
    """When the manifest's slot_pool is NOT identity (streaming-style),
    the emitted slot index reflects the pool position, not the raw
    layer. Simulates a streaming setup where biome layers have been
    paged into different array slots."""
    bundle = make_world(tmp_path)
    m = fake_manifest()
    # Reverse the standard tier's slot_pool. Now pool[0] = layer 9,
    # pool[1] = layer 8, ..., pool[9] = layer 0. wetland.ground (raw
    # layer 7) sits at pool position 2.
    m["tiers"]["standard"]["slot_pool"] = list(reversed(range(10)))
    bts.build_splats(bundle_dir=bundle, manifest=m,
                     mode="hard", splat_size=8, feather_width_m=0.0)
    meta = json.loads((bundle / "tiles" / "tile_0_0" / "splat_meta.json").read_text())
    c0 = meta["channels"][0]
    assert c0["biome"] == "wetland"
    # Raw layers 7/8/9 reversed -> pool positions 2/1/0.
    assert c0["ground"] == {"tier": "standard", "slot": 2}
    assert c0["mid"]    == {"tier": "standard", "slot": 1}
    assert c0["rock"]   == {"tier": "standard", "slot": 0}


def test_hard_mode_handles_unknown_biome(tmp_path: Path):
    bundle = make_world(tmp_path)
    bad_meta = bundle / "tiles" / "tile_0_0" / "meta.json"
    data = json.loads(bad_meta.read_text())
    data["biome"] = "tropical"
    bad_meta.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(bts.SplatError, match="tropical"):
        bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                         mode="hard", splat_size=8, feather_width_m=0.0)


# ---- feather mode ----

def test_feather_mode_writes_per_tile_splat_and_meta(tmp_path: Path):
    bundle = make_world(tmp_path)
    bts.build_splats(
        bundle_dir=bundle, manifest=fake_manifest(),
        mode="feather", splat_size=16, feather_width_m=64.0,
    )
    for tx, tz in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        splat_path = bundle / "tiles" / f"tile_{tx}_{tz}" / "splat.png"
        meta_path = bundle / "tiles" / f"tile_{tx}_{tz}" / "splat_meta.json"
        assert splat_path.is_file()
        assert meta_path.is_file()


def test_feather_mode_ramps_at_boundary(tmp_path: Path):
    """A tile with a different-biome east neighbor should have a smooth
    ramp on its easternmost feather strip from this-biome (ch0) to the
    east-neighbor's channel."""
    bundle = make_world(tmp_path)
    # 4 tiles: (0,0)=wetland with neighbors (1,0)=desert (E), (0,1)=forest (N).
    # NESW iteration order means channels become: [wetland, forest, desert, _].
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="feather", splat_size=16, feather_width_m=64.0)
    splat = np.asarray(
        Image.open(bundle / "tiles" / "tile_0_0" / "splat.png").convert("RGBA"))
    meta = json.loads(
        (bundle / "tiles" / "tile_0_0" / "splat_meta.json").read_text())
    # Find which channel holds the east neighbor (desert).
    east_ch = next(i for i, c in enumerate(meta["channels"])
                   if c["biome"] == "desert")
    # splat_size=16, tile_size_m=256 -> 16m/pixel. feather_width_m=64m = 4
    # pixels of ramp. Use mid row (row 8) so the north ramp (forest) is
    # already 0 at this row (it dies off after 4 rows from the north edge).
    mid_row = 8
    # Mid-tile column (col 4): pure this-biome (wetland).
    assert splat[mid_row, 4, 0] > 240, "mid-tile column should be ~255 in ch0"
    assert splat[mid_row, 4, east_ch] < 20, "mid-tile column should be ~0 in east neighbor ch"
    # East edge (col 15): east neighbor should have meaningful weight.
    assert splat[mid_row, 15, east_ch] >= 100, \
        f"easternmost column row 8 should have substantial east-neighbor weight (got {splat[mid_row, 15, east_ch]})"
    # Ramp monotonicity: east neighbor weight non-decreasing as we move east.
    east_strip = splat[mid_row, 12:16, east_ch].astype(np.int32)
    assert (np.diff(east_strip) >= 0).all(), \
        f"east-neighbor weight should be monotonically non-decreasing on east strip, got {east_strip}"


def test_feather_mode_channels_list_neighbor_biomes(tmp_path: Path):
    """splat_meta.json must list this-biome in channel 0 and each unique
    different-biome neighbor in channels 1..3."""
    bundle = make_world(tmp_path)
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="feather", splat_size=16, feather_width_m=64.0)
    # tile_0_0 = wetland. East = desert (different), north = forest (different).
    # No other neighbors (south/west off-world). So channels: wetland, desert,
    # forest, (empty).
    meta = json.loads(
        (bundle / "tiles" / "tile_0_0" / "splat_meta.json").read_text())
    assert meta["channels"][0]["biome"] == "wetland"
    biomes_in_meta = sorted([
        meta["channels"][i]["biome"] for i in range(4)
        if meta["channels"][i]["biome"] is not None
    ])
    assert biomes_in_meta == ["desert", "forest", "wetland"]


def test_feather_mode_interior_tile_unchanged(tmp_path: Path):
    """A tile whose neighbors all match its biome should have a pure
    hard splat (every pixel = (255, 0, 0, 0)) — no boundary to feather."""
    bundle = tmp_path / "scale_demo"
    bundle.mkdir()
    for tx in range(3):
        for tz in range(3):
            td = bundle / "tiles" / f"tile_{tx}_{tz}"
            td.mkdir(parents=True)
            (td / "meta.json").write_text(json.dumps({
                "tile_x": tx, "tile_z": tz, "tile_size_m": 256.0,
                "biome": "alpine",
            }), encoding="utf-8")
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="feather", splat_size=8, feather_width_m=32.0)
    splat = np.asarray(
        Image.open(bundle / "tiles" / "tile_1_1" / "splat.png").convert("RGBA"))
    assert (splat[..., 0] == 255).all(), "interior tile must be pure ch0"
    assert (splat[..., 1] == 0).all()
    assert (splat[..., 2] == 0).all()
    assert (splat[..., 3] == 0).all()


def test_feather_mode_weight_sum_normalised(tmp_path: Path):
    """At every pixel, the four channel weights should sum to ~255
    (255 = weight 1.0 after dividing by 255 in the shader)."""
    bundle = make_world(tmp_path)
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="feather", splat_size=16, feather_width_m=64.0)
    splat = np.asarray(
        Image.open(bundle / "tiles" / "tile_0_0" / "splat.png").convert("RGBA")
    ).astype(np.int32)
    sums = splat.sum(axis=-1)
    # Allow small rounding error from float->uint8 quantization (±2).
    assert sums.min() >= 253, f"min sum {sums.min()} should be ~255"
    assert sums.max() <= 257, f"max sum {sums.max()} should be ~255"
