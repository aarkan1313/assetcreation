"""Tests for pipeline.quality_tiers."""
from __future__ import annotations
import pytest

from quality_tiers import (
    QualityTiersError,
    get_config_path,
    load_config,
    resolve,
    KNOWN_KEYS,
)


def test_load_config_returns_expected_shape():
    cfg = load_config()
    assert cfg["schema_version"] == 1
    assert cfg["default_tier"] == "high"
    assert set(cfg["tiers"].keys()) == {"low", "medium", "high", "ultra"}


def test_every_tier_has_every_known_key():
    cfg = load_config()
    for tier_name, tier_dict in cfg["tiers"].items():
        missing = [k for k in KNOWN_KEYS if k not in tier_dict]
        assert not missing, f"tier {tier_name!r} missing keys: {missing!r}"


def test_resolve_high_is_default():
    out = resolve()
    assert out["_tier"] == "high"
    assert out["ring_grid_n"] == 128
    assert out["ring_count"] == 4


def test_resolve_explicit_tier():
    out = resolve("low")
    assert out["_tier"] == "low"
    assert out["ring_grid_n"] == 64
    assert out["ring_count"] == 3
    out2 = resolve("ultra")
    assert out2["_tier"] == "ultra"
    assert out2["ring_grid_n"] == 256


def test_resolve_unknown_tier_raises():
    with pytest.raises(QualityTiersError, match="bogus"):
        resolve("bogus")


def test_resolved_dict_is_independent_copy():
    """Mutating one resolve() result must not poison subsequent calls."""
    a = resolve("high")
    a["ring_grid_n"] = -999
    b = resolve("high")
    assert b["ring_grid_n"] == 128


def test_get_config_path_is_a_real_file():
    p = get_config_path()
    assert p.exists(), f"config not found at {p}"


def test_resolve_values_sane():
    """Sanity ranges so a typo in the JSON doesn't ship silently."""
    for name in ["low", "medium", "high", "ultra"]:
        cfg = resolve(name)
        assert 2 <= cfg["ring_count"] <= 6
        assert 32 <= cfg["ring_grid_n"] <= 512
        assert 0.25 <= cfg["ring_grid_step_base_m"] <= 16.0
        assert cfg["heightmap_format_inner"] in {"RF", "RH"}
        assert cfg["heightmap_format_outer"] in {"RF", "RH"}
        assert 0 <= cfg["collision_rings"] <= cfg["ring_count"]
        assert 256 <= cfg["splat_texture_array_size"] <= 8192
        assert cfg["shadow_quality"] in {"off", "low", "high"}
        assert 0.01 <= cfg["update_interval_s"] <= 1.0
