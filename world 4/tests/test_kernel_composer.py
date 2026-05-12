"""Tests for pipeline.kernel_composer."""
from __future__ import annotations
import pytest

from kernels import build_builtin_registry
from kernel_composer import KernelComposer, ComposerError


def fake_catalog() -> dict:
    return {
        "schema_version": 1,
        "tiers": [{"name": "standard", "resolution": 1024}],
        "slots": ["ground", "mid", "rock"],
        "maps": ["albedo", "normal", "roughness", "ao"],
        "biome_scale_m": 1024.0,  # biome regions ~1km across
        "biomes": [
            {
                "name": "alpine",
                "kit_dir": "materials/biome_alpine",
                "slots": {
                    "ground": {"source": "ground", "tier": "standard"},
                    "mid": {"source": "mid", "tier": "standard"},
                    "rock": {"source": "rock", "tier": "standard"},
                },
                "generator": {
                    "kernel": "noise_stack",
                    "params": {
                        "elevation_base_m": 800.0,
                        "elevation_amplitude_m": 400.0,
                        "octaves": 4,
                        "lacunarity": 2.0,
                        "persistence": 0.5,
                        "base_frequency_per_m": 1.0 / 256.0,
                        "seed_offset": 0,
                    },
                },
            },
            {
                "name": "desert",
                "kit_dir": "materials/biome_desert",
                "slots": {
                    "ground": {"source": "ground", "tier": "standard"},
                    "mid": {"source": "mid", "tier": "standard"},
                    "rock": {"source": "rock", "tier": "standard"},
                },
                "generator": {
                    "kernel": "noise_stack",
                    "params": {
                        "elevation_base_m": 200.0,
                        "elevation_amplitude_m": 80.0,
                        "octaves": 3,
                        "lacunarity": 2.0,
                        "persistence": 0.5,
                        "base_frequency_per_m": 1.0 / 256.0,
                        "seed_offset": 1,
                    },
                },
            },
        ],
    }


def test_sample_biome_weights_sums_to_one():
    cat = fake_catalog()
    comp = KernelComposer(catalog=cat, registry=build_builtin_registry())
    seed = 42
    for x, z in [(0, 0), (500, 200), (-1000, 800), (3142, -2718)]:
        weights = comp.sample_biome_weights(float(x), float(z), seed)
        assert set(weights.keys()) == {"alpine", "desert"}
        s = sum(weights.values())
        assert abs(s - 1.0) < 1e-6, f"weights sum {s} at ({x},{z})"


def test_sample_biome_weights_is_pure():
    cat = fake_catalog()
    comp = KernelComposer(catalog=cat, registry=build_builtin_registry())
    a = comp.sample_biome_weights(100.0, 200.0, 42)
    b = comp.sample_biome_weights(100.0, 200.0, 42)
    assert a == b


def test_sample_height_is_weighted_blend():
    """At a position where alpine dominates, sample_height should be
    close to alpine's NoiseStackKernel output; at a position where
    desert dominates, close to desert's output."""
    cat = fake_catalog()
    comp = KernelComposer(catalog=cat, registry=build_builtin_registry())
    seed = 42
    alpine_pos = None
    desert_pos = None
    # 0.9 threshold: with temperature 0.5 and gradient-noise scalars in
    # ~[-1, 1], the softmax peak runs ~0.91 — 0.95 would be unreachable
    # over a 2-biome 4km sweep. 0.9 still means strongly-dominant.
    for x in range(-2000, 2001, 50):
        for z in range(-2000, 2001, 50):
            w = comp.sample_biome_weights(float(x), float(z), seed)
            if w["alpine"] > 0.9 and alpine_pos is None:
                alpine_pos = (float(x), float(z))
            if w["desert"] > 0.9 and desert_pos is None:
                desert_pos = (float(x), float(z))
            if alpine_pos and desert_pos:
                break
        if alpine_pos and desert_pos:
            break
    assert alpine_pos is not None, "no near-pure alpine position found"
    assert desert_pos is not None, "no near-pure desert position found"
    h_alpine = comp.sample_height(*alpine_pos, seed)
    h_desert = comp.sample_height(*desert_pos, seed)
    # Alpine base 800m, desert base 200m. At >95% weight positions the
    # height should be near each biome's base envelope.
    assert h_alpine > 400.0, f"alpine-dominant height {h_alpine} too low"
    assert h_desert < 500.0, f"desert-dominant height {h_desert} too high"


def test_unknown_kernel_in_catalog_raises():
    cat = fake_catalog()
    cat["biomes"][0]["generator"]["kernel"] = "bogus"
    with pytest.raises(ComposerError, match="bogus"):
        KernelComposer(catalog=cat, registry=build_builtin_registry())


def test_missing_generator_block_raises():
    cat = fake_catalog()
    del cat["biomes"][1]["generator"]
    with pytest.raises(ComposerError, match="missing generator"):
        KernelComposer(catalog=cat, registry=build_builtin_registry())
