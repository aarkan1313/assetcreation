"""Tests for pipeline.kernels.noise_stack."""
from __future__ import annotations
import math
import pytest

from kernels.noise_stack import NoiseStackKernel


def default_params() -> dict:
    return {
        "elevation_base_m": 500.0,
        "elevation_amplitude_m": 200.0,
        "octaves": 4,
        "lacunarity": 2.0,
        "persistence": 0.5,
        "base_frequency_per_m": 1.0 / 256.0,
        "seed_offset": 0,
    }


def test_height_is_pure_function():
    k = NoiseStackKernel()
    p = default_params()
    a = k.height(100.0, 200.0, 42, p)
    b = k.height(100.0, 200.0, 42, p)
    assert a == b


def test_height_changes_with_position():
    k = NoiseStackKernel()
    p = default_params()
    samples = [k.height(float(x), 0.0, 42, p) for x in range(0, 1024, 64)]
    assert len(set(samples)) > 1


def test_height_stays_within_envelope():
    k = NoiseStackKernel()
    p = default_params()
    heights = [
        k.height(float(x * 17), float(z * 23), 42, p)
        for x in range(50) for z in range(50)
    ]
    base = p["elevation_base_m"]
    amp = p["elevation_amplitude_m"]
    assert all(base - 2 * amp < h < base + 2 * amp for h in heights), \
        f"heights outside envelope: min={min(heights)} max={max(heights)}"


def test_seed_offset_shifts_pattern():
    k = NoiseStackKernel()
    p_a = default_params()
    p_b = dict(p_a, seed_offset=1)
    same = sum(
        1 for x in range(64)
        if math.isclose(
            k.height(float(x), 0.0, 42, p_a),
            k.height(float(x), 0.0, 42, p_b),
            abs_tol=1e-6,
        )
    )
    assert same < 5


def test_biome_weight_is_pure_function():
    k = NoiseStackKernel()
    p = default_params()
    assert k.biome_weight("alpine", 100.0, 200.0, 42, p) == 1.0
    assert k.biome_weight("desert", 0.0, 0.0, 99, p) == 1.0


def test_kind_class_attr():
    assert NoiseStackKernel.kind == "noise_stack"


def test_missing_param_raises():
    k = NoiseStackKernel()
    with pytest.raises(KeyError, match="elevation_base_m"):
        k.height(0.0, 0.0, 42, {})
