"""Tests for build_biome_arrays.build_manifest (the Python half)."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

import build_biome_arrays as bba
import biome_catalog as bc


def make_pbr_kit(root: Path, *, size: int = 8) -> None:
    """Create dummy 4-map PBR files in `root` so on-disk checks pass."""
    from PIL import Image
    root.mkdir(parents=True, exist_ok=True)
    for name in ("albedo", "normal", "roughness", "ao"):
        Image.new("RGB", (size, size), (128, 128, 128)).save(root / f"{name}.png")


def write_catalog(tmp_path: Path, w4_root: Path) -> Path:
    data = {
        "schema_version": 1,
        "tiers": [
            {"name": "standard", "resolution": 8},
            {"name": "hero",     "resolution": 16},
        ],
        "slots": ["ground", "mid", "rock"],
        "maps":  ["albedo", "normal", "roughness", "ao"],
        "biomes": [
            {
                "name": "forest", "kit_dir": "kitA",
                "slots": {
                    "ground": {"source": "g", "tier": "hero"},
                    "mid":    {"source": "m", "tier": "standard"},
                    "rock":   {"source": "r", "tier": "hero"},
                },
            },
            {
                "name": "alpine", "kit_dir": "kitB",
                "slots": {
                    "ground": {"source": "g", "tier": "standard"},
                    "mid":    {"source": "m", "tier": "standard"},
                    "rock":   {"source": "r", "tier": "standard"},
                },
            },
        ],
    }
    p = tmp_path / "biome_catalog.json"
    p.write_text(json.dumps(data), encoding="utf-8", newline="\n")
    make_pbr_kit(w4_root / "kitA" / "g", size=16)
    make_pbr_kit(w4_root / "kitA" / "m", size=8)
    make_pbr_kit(w4_root / "kitA" / "r", size=16)
    make_pbr_kit(w4_root / "kitB" / "g", size=8)
    make_pbr_kit(w4_root / "kitB" / "m", size=8)
    make_pbr_kit(w4_root / "kitB" / "r", size=8)
    return p


def test_manifest_lists_layers_per_tier(tmp_path: Path):
    w4 = tmp_path / "w4"
    catalog_path = write_catalog(tmp_path, w4)
    cat = bc.load_catalog(catalog_path)
    m = bba.build_manifest(cat, w4_root=w4)
    assert sorted(m["tiers"].keys()) == ["hero", "standard"]
    # standard tier: forest/mid (0), alpine/ground (1), alpine/mid (2), alpine/rock (3)
    std = m["tiers"]["standard"]
    assert [r["layer"] for r in std["layers"]] == [0, 1, 2, 3]
    assert [r["biome"] for r in std["layers"]] == ["forest", "alpine", "alpine", "alpine"]
    # hero tier: forest/ground (0), forest/rock (1)
    hero = m["tiers"]["hero"]
    assert [r["layer"] for r in hero["layers"]] == [0, 1]
    assert hero["resolution"] == 16


def test_manifest_oversize_raises(tmp_path: Path):
    """A source PNG larger than the tier's resolution should raise — that
    indicates a misconfigured catalog (high-res file in a low-res tier)."""
    w4 = tmp_path / "w4"
    catalog_path = write_catalog(tmp_path, w4)
    from PIL import Image
    bad = w4 / "kitB" / "g" / "albedo.png"  # kitB's slots are standard (res=8)
    Image.new("RGB", (32, 32), (0, 0, 0)).save(bad)
    cat = bc.load_catalog(catalog_path)
    with pytest.raises(bba.BuildError, match="larger than tier"):
        bba.build_manifest(cat, w4_root=w4)


def test_manifest_undersize_auto_upsamples(tmp_path: Path):
    """A source PNG smaller than the tier's resolution should be LANCZOS-
    upsampled to match. The manifest references the upsampled sibling."""
    w4 = tmp_path / "w4"
    catalog_path = write_catalog(tmp_path, w4)
    from PIL import Image
    # kitA/g/ao is hero tier (res=16). Replace with a 4x4 to force upsample.
    small = w4 / "kitA" / "g" / "ao.png"
    Image.new("L", (4, 4), 128).save(small)
    cat = bc.load_catalog(catalog_path)
    m = bba.build_manifest(cat, w4_root=w4)
    hero_layers = m["tiers"]["hero"]["layers"]
    # Find the kitA/g entry.
    ground = next(r for r in hero_layers if r["biome"] == "forest" and r["slot"] == "ground")
    ao_rel = ground["maps"]["ao"]
    assert "__upsampled16" in ao_rel
    upsampled = w4 / ao_rel
    assert upsampled.is_file()
    with Image.open(upsampled) as im:
        assert im.size == (16, 16)


def test_manifest_missing_map_raises(tmp_path: Path):
    w4 = tmp_path / "w4"
    catalog_path = write_catalog(tmp_path, w4)
    (w4 / "kitA" / "g" / "ao.png").unlink()
    cat = bc.load_catalog(catalog_path)
    with pytest.raises(bba.BuildError, match="missing.*ao.png"):
        bba.build_manifest(cat, w4_root=w4)


def test_write_manifest_roundtrip(tmp_path: Path):
    w4 = tmp_path / "w4"
    catalog_path = write_catalog(tmp_path, w4)
    cat = bc.load_catalog(catalog_path)
    m = bba.build_manifest(cat, w4_root=w4)
    out = tmp_path / "layer_manifest.json"
    bba.write_manifest(m, out)
    reloaded = json.loads(out.read_text(encoding="utf-8"))
    assert reloaded == m
