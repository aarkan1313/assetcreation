"""Tests for build_world_splat (world-spanning sampler2DArray splat)."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from PIL import Image
import pytest

import build_world_splat as bws
import biome_catalog as bc


def make_world(tmp_path: Path) -> Path:
    """4x4 world. Layout: NW alpine, NE rocky, S desert, SW wetland."""
    bundle = tmp_path / "scale_demo"
    bundle.mkdir()
    (bundle / "meta.json").write_text(json.dumps({
        "world_size_m": 1024.0, "grid_n": 4, "tile_size_m": 256.0,
    }), encoding="utf-8")
    # rows are by tile_z (south->north as tz increases)
    layout = {
        (0, 0): "wetland", (1, 0): "wetland", (2, 0): "desert",  (3, 0): "desert",
        (0, 1): "forest",  (1, 1): "forest",  (2, 1): "desert",  (3, 1): "desert",
        (0, 2): "alpine",  (1, 2): "forest",  (2, 2): "forest",  (3, 2): "rocky",
        (0, 3): "alpine",  (1, 3): "alpine",  (2, 3): "rocky",   (3, 3): "rocky",
    }
    for (tx, tz), b in layout.items():
        td = bundle / "tiles" / f"tile_{tx}_{tz}"
        td.mkdir(parents=True)
        (td / "meta.json").write_text(json.dumps(
            {"tile_x": tx, "tile_z": tz, "tile_size_m": 256.0, "biome": b}
        ), encoding="utf-8")
    return bundle


def make_catalog(tmp_path: Path) -> bc.Catalog:
    data = {
        "schema_version": 1,
        "tiers": [{"name": "standard", "resolution": 1024}],
        "slots": ["ground", "mid", "rock"],
        "maps":  ["albedo", "normal", "roughness", "ao"],
        "biomes": [
            {"name": n, "kit_dir": f"materials/biome_{n}",
             "slots": {
                 "ground": {"source": "g", "tier": "standard"},
                 "mid":    {"source": "m", "tier": "standard"},
                 "rock":   {"source": "r", "tier": "standard"},
             }} for n in ("forest", "alpine", "desert", "rocky", "wetland")
        ],
    }
    p = tmp_path / "catalog.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return bc.load_catalog(p)


def test_world_splat_emits_one_layer_per_catalog_biome(tmp_path: Path):
    bundle = make_world(tmp_path)
    cat = make_catalog(tmp_path)
    m = bws.build_world_splat(
        bundle_dir=bundle, catalog=cat,
        splat_res=64, feather_width_m=32.0,
        smooth_sigma_px=0.0,  # disable smoothing for deterministic tests
    )
    assert len(m["layers"]) == 5
    biomes = [layer["biome"] for layer in m["layers"]]
    assert sorted(biomes) == sorted(["forest", "alpine", "desert", "rocky", "wetland"])
    for layer in m["layers"]:
        p = bundle / "world_splat" / layer["file"]
        assert p.is_file()
        with Image.open(p) as im:
            assert im.size == (64, 64)
            assert im.mode == "L"


def test_world_splat_weights_sum_to_one(tmp_path: Path):
    bundle = make_world(tmp_path)
    cat = make_catalog(tmp_path)
    m = bws.build_world_splat(
        bundle_dir=bundle, catalog=cat,
        splat_res=64, feather_width_m=32.0,
        smooth_sigma_px=0.0,
    )
    # Read all layers, sum, expect ~255 per pixel (==1.0 after /255).
    stack = []
    for layer in m["layers"]:
        a = np.asarray(
            Image.open(bundle / "world_splat" / layer["file"]).convert("L"),
            dtype=np.int32,
        )
        stack.append(a)
    sums = np.stack(stack, axis=-1).sum(axis=-1)
    # Quantization to uint8 + per-pixel normalize gives ~255 ±1 per pixel.
    assert sums.min() >= 253, f"min sum {sums.min()}"
    assert sums.max() <= 257, f"max sum {sums.max()}"


def test_world_splat_interior_is_pure(tmp_path: Path):
    """Deep inside a biome region, that biome's weight should be ~255
    and all others ~0."""
    bundle = make_world(tmp_path)
    cat = make_catalog(tmp_path)
    m = bws.build_world_splat(
        bundle_dir=bundle, catalog=cat,
        splat_res=64, feather_width_m=16.0,  # narrow so interior is far from boundary
        smooth_sigma_px=0.0,
    )
    # tile_0_3 = alpine (NW corner). At splat_res=64 grid_n=4, that's
    # rows 0..15 (north strip, west 16 cols). Pixel (4, 4) is deep inside.
    layers_by_biome = {layer["biome"]: layer["file"] for layer in m["layers"]}
    alpine = np.asarray(Image.open(bundle / "world_splat" / layers_by_biome["alpine"]).convert("L"))
    forest = np.asarray(Image.open(bundle / "world_splat" / layers_by_biome["forest"]).convert("L"))
    desert = np.asarray(Image.open(bundle / "world_splat" / layers_by_biome["desert"]).convert("L"))
    # Pixel deep inside alpine region — far from any boundary.
    assert alpine[4, 4] > 240, f"alpine interior should be ~255 got {alpine[4, 4]}"
    assert forest[4, 4] < 20, f"non-alpine should be ~0 at alpine interior got {forest[4, 4]}"
    assert desert[4, 4] < 20


def test_world_splat_boundary_is_smooth_and_continuous(tmp_path: Path):
    """At the boundary between two regions of different biomes, the
    weights should ramp smoothly over multiple pixels (no hard step).
    This is the regression test for the hard-line bug: with the gaussian
    smoothing pass enabled, a single boundary pixel's adjacent neighbour
    must differ by less than the feather can produce without smoothing.
    """
    bundle = make_world(tmp_path)
    cat = make_catalog(tmp_path)
    m = bws.build_world_splat(
        bundle_dir=bundle, catalog=cat,
        splat_res=64, feather_width_m=48.0,
        smooth_sigma_px=1.5,
    )
    # West tile is tile_0_2 = alpine. East neighbor tile_1_2 = forest.
    # Boundary in pixel space is at col 16 (16 px per tile).
    layers_by_biome = {layer["biome"]: layer["file"] for layer in m["layers"]}
    alpine = np.asarray(Image.open(bundle / "world_splat" / layers_by_biome["alpine"]).convert("L"), dtype=np.int32)
    forest = np.asarray(Image.open(bundle / "world_splat" / layers_by_biome["forest"]).convert("L"), dtype=np.int32)
    # Row 24 sits in the middle of tile_z=2 (rows 16..31). Sample a strip
    # crossing the alpine|forest boundary at col 16.
    row = 24
    strip_alpine = alpine[row, 10:24]
    # Per-pixel delta along the strip should be modest — no single jump
    # bigger than ~60/255. (Half the original 127-jump hard-line bug.)
    deltas = np.abs(np.diff(strip_alpine))
    assert int(deltas.max()) <= 60, (
        f"max per-pixel alpine delta along strip is {int(deltas.max())} "
        f"(should be <=60 with smoothing). Strip = {strip_alpine.tolist()}")
    # Ramp spans multiple pixels (signal that we're not still at a hard step):
    # find pixels with alpine in [60, 200] — should be at least 4 of them.
    ramp_zone = ((strip_alpine >= 30) & (strip_alpine <= 225)).sum()
    assert ramp_zone >= 4, (
        f"only {ramp_zone} ramp pixels in alpine strip; transition too sharp. "
        f"Strip = {strip_alpine.tolist()}")


def test_world_splat_unknown_biome_in_tile_raises(tmp_path: Path):
    bundle = make_world(tmp_path)
    cat = make_catalog(tmp_path)
    # Corrupt one tile.
    p = bundle / "tiles" / "tile_0_0" / "meta.json"
    d = json.loads(p.read_text())
    d["biome"] = "tropical"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(bws.WorldSplatError, match="tropical"):
        bws.build_world_splat(
            bundle_dir=bundle, catalog=cat,
            splat_res=64, feather_width_m=32.0, smooth_sigma_px=0.0,
        )
