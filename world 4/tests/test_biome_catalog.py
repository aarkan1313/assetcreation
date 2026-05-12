"""Tests for pipeline.biome_catalog (catalog loader/validator)."""
from __future__ import annotations
import json
import pytest
from pathlib import Path

import biome_catalog as bc


def write_catalog(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "biome_catalog.json"
    p.write_text(json.dumps(data), encoding="utf-8", newline="\n")
    return p


def minimal_catalog() -> dict:
    return {
        "schema_version": 1,
        "tiers": [{"name": "standard", "resolution": 1024}],
        "slots": ["ground", "mid", "rock"],
        "maps":  ["albedo", "normal", "roughness", "ao"],
        "biomes": [{
            "name": "forest",
            "kit_dir": "materials/anchor_v2",
            "slots": {
                "ground": {"source": "scrub_dense",   "tier": "standard"},
                "mid":    {"source": "tundra_lichen", "tier": "standard"},
                "rock":   {"source": "rocky_slope",   "tier": "standard"},
            },
        }],
    }


def test_load_minimal(tmp_path: Path):
    p = write_catalog(tmp_path, minimal_catalog())
    cat = bc.load_catalog(p)
    assert cat.biome_names() == ["forest"]
    assert cat.tier_names() == ["standard"]


def test_layer_index_is_stable(tmp_path: Path):
    data = minimal_catalog()
    data["biomes"].append({
        "name": "alpine",
        "kit_dir": "materials/biome_alpine",
        "slots": {
            "ground": {"source": "ground", "tier": "standard"},
            "mid":    {"source": "mid",    "tier": "standard"},
            "rock":   {"source": "rock",   "tier": "standard"},
        },
    })
    p = write_catalog(tmp_path, data)
    cat = bc.load_catalog(p)
    assert cat.layer_index("forest", "mid", "standard") == 1
    assert cat.layer_index("alpine", "ground", "standard") == 3


def test_rejects_unknown_tier(tmp_path: Path):
    data = minimal_catalog()
    data["biomes"][0]["slots"]["ground"]["tier"] = "bogus"
    p = write_catalog(tmp_path, data)
    with pytest.raises(bc.CatalogError, match="unknown tier"):
        bc.load_catalog(p)


def test_rejects_missing_slot(tmp_path: Path):
    data = minimal_catalog()
    del data["biomes"][0]["slots"]["mid"]
    p = write_catalog(tmp_path, data)
    with pytest.raises(bc.CatalogError, match="missing slot"):
        bc.load_catalog(p)


def test_slot_kit_path(tmp_path: Path):
    p = write_catalog(tmp_path, minimal_catalog())
    cat = bc.load_catalog(p)
    assert cat.slot_kit_path("forest", "mid") == "materials/anchor_v2/tundra_lichen"
