"""Noise-stack kernel — multi-octave gradient noise.

The math:
- For each octave i in 0..octaves-1:
    freq = base_frequency_per_m * lacunarity^i
    amp = persistence^i
    n_i = gradient_noise_2d(world_x * freq, world_z * freq, seed)
- height_signed = sum(n_i * amp) / sum(amp)        # in -1..1
- height = elevation_base_m + height_signed * elevation_amplitude_m

`gradient_noise_2d` is a hand-rolled deterministic hash + gradient
look-up implementation that the GDScript port mirrors bit-for-bit
(modulo float precision). See `_gradient_noise_2d` for the exact
operations.

The seed used for `_gradient_noise_2d` is `world_seed + seed_offset`
(from params). This lets two biomes using NoiseStackKernel with the
same world_seed produce different patterns by changing seed_offset.
"""
from __future__ import annotations

import math

from kernels.base import Kernel


REQUIRED_PARAMS = (
    "elevation_base_m",
    "elevation_amplitude_m",
    "octaves",
    "lacunarity",
    "persistence",
    "base_frequency_per_m",
    "seed_offset",
)


def _hash2(ix: int, iz: int, seed: int) -> int:
    """Deterministic integer hash of (ix, iz, seed) -> 32-bit int.

    Uses the same magic constants and mix steps as the GDScript port
    will so the two implementations agree.
    """
    h = (seed * 374761393) & 0xFFFFFFFF
    h = (h + ix * 668265263) & 0xFFFFFFFF
    h = (h + iz * 2147483647) & 0xFFFFFFFF
    h = h ^ (h >> 13)
    h = (h * 1274126177) & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return h


def _gradient(ix: int, iz: int, seed: int) -> tuple[float, float]:
    """Return a deterministic 2D unit vector for grid cell (ix, iz)."""
    h = _hash2(ix, iz, seed)
    angle = (h / 0xFFFFFFFF) * 2.0 * math.pi
    return (math.cos(angle), math.sin(angle))


def _fade(t: float) -> float:
    """Quintic smoothstep used by Perlin: 6t^5 - 15t^4 + 10t^3."""
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _gradient_noise_2d(x: float, z: float, seed: int) -> float:
    """Perlin-style gradient noise at continuous (x, z) for given seed.

    Output is in approximately [-1, 1]. Continuous + differentiable.
    """
    ix = int(math.floor(x))
    iz = int(math.floor(z))
    fx = x - ix
    fz = z - iz

    g00 = _gradient(ix,     iz,     seed)
    g10 = _gradient(ix + 1, iz,     seed)
    g01 = _gradient(ix,     iz + 1, seed)
    g11 = _gradient(ix + 1, iz + 1, seed)

    d00 = (fx,       fz)
    d10 = (fx - 1.0, fz)
    d01 = (fx,       fz - 1.0)
    d11 = (fx - 1.0, fz - 1.0)

    n00 = g00[0] * d00[0] + g00[1] * d00[1]
    n10 = g10[0] * d10[0] + g10[1] * d10[1]
    n01 = g01[0] * d01[0] + g01[1] * d01[1]
    n11 = g11[0] * d11[0] + g11[1] * d11[1]

    u = _fade(fx)
    v = _fade(fz)
    nx0 = n00 * (1.0 - u) + n10 * u
    nx1 = n01 * (1.0 - u) + n11 * u
    return nx0 * (1.0 - v) + nx1 * v


class NoiseStackKernel(Kernel):
    """Multi-octave fBm over `_gradient_noise_2d`."""

    kind = "noise_stack"

    def _validate(self, params: dict) -> None:
        missing = [p for p in REQUIRED_PARAMS if p not in params]
        if missing:
            raise KeyError(f"NoiseStackKernel missing params: {missing!r}")

    def height(self, world_x: float, world_z: float, world_seed: int,
               params: dict) -> float:
        self._validate(params)
        seed = int(world_seed) + int(params["seed_offset"])
        octaves = int(params["octaves"])
        lacunarity = float(params["lacunarity"])
        persistence = float(params["persistence"])
        base_freq = float(params["base_frequency_per_m"])
        base_m = float(params["elevation_base_m"])
        amp_m = float(params["elevation_amplitude_m"])

        total = 0.0
        amp = 1.0
        freq = base_freq
        norm = 0.0
        for _ in range(octaves):
            total += _gradient_noise_2d(world_x * freq, world_z * freq, seed) * amp
            norm += amp
            amp *= persistence
            freq *= lacunarity
        if norm > 0.0:
            total /= norm
        return base_m + total * amp_m

    def biome_weight(self, biome_name: str, world_x: float, world_z: float,
                     world_seed: int, params: dict) -> float:
        # NoiseStackKernel doesn't itself drive biome assignment — the
        # composer's biome map (a separate noise field, see
        # kernel_composer.py) determines biome boundaries. Future
        # kernels (e.g. ErosionBakedKernel) may return slope- or
        # height-derived weights to bias biome placement.
        return 1.0
