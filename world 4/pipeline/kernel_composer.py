"""KernelComposer — combines per-biome kernels into world-level functions.

Owns:
- the biome -> (kernel, params) mapping (parsed from biome_catalog.json)
- the biome-weight field (a per-biome noise function over world XZ)

API:
    sample_height(world_x, world_z, world_seed) -> float
    sample_biome_weights(world_x, world_z, world_seed) -> dict[biome, float]

The biome-weight field is a softmax over per-biome scalar fields:
each biome has a scalar field B_i(x, z) = gradient_noise_2d(x / scale,
z / scale, seed + i*1000). The weight for biome i at (x, z) is
  exp(B_i / temperature) / sum_j(exp(B_j / temperature))

This gives each biome a "territory" of approximate scale `biome_scale_m`
that varies smoothly. Temperature controls boundary sharpness;
v1 uses 0.5 (moderately sharp, smooth at boundaries).

Height at (x, z) is the weighted sum of each biome's kernel.height()
output, weighted by the biome weights. This produces a smooth
blend at biome boundaries — at a 50/50 alpine/desert boundary the
height is halfway between alpine's noise and desert's noise.
"""
from __future__ import annotations

import math

from kernels.base import Kernel, KernelRegistry
from kernels.noise_stack import _gradient_noise_2d


class ComposerError(RuntimeError):
    """Raised for composer-level catalog issues."""


BIOME_SEED_STRIDE = 1000

DEFAULT_BIOME_TEMPERATURE = 0.5


class _BiomeBinding:
    __slots__ = ("name", "kernel", "params", "biome_index")

    def __init__(self, name: str, kernel: Kernel, params: dict, biome_index: int):
        self.name = name
        self.kernel = kernel
        self.params = params
        self.biome_index = biome_index


class KernelComposer:
    """Combines per-biome kernels at world level."""

    def __init__(self, catalog: dict, registry: KernelRegistry,
                 biome_temperature: float = DEFAULT_BIOME_TEMPERATURE):
        self._biomes: list[_BiomeBinding] = []
        self._biome_scale_m = float(catalog.get("biome_scale_m", 1024.0))
        self._temperature = biome_temperature
        for i, b in enumerate(catalog["biomes"]):
            if "generator" not in b:
                raise ComposerError(f"biome {b['name']!r}: missing generator block")
            gen = b["generator"]
            kind = gen.get("kernel")
            if kind is None:
                raise ComposerError(f"biome {b['name']!r}: generator.kernel missing")
            try:
                kernel = registry.get(kind)
            except Exception as e:
                raise ComposerError(
                    f"biome {b['name']!r}: kernel {kind!r}: {e}") from e
            params = gen.get("params", {})
            self._biomes.append(_BiomeBinding(b["name"], kernel, params, i))

    def biome_names(self) -> list[str]:
        return [b.name for b in self._biomes]

    def _biome_scalar(self, biome_index: int, world_x: float, world_z: float,
                      world_seed: int) -> float:
        """Per-biome scalar field used for biome assignment. Each biome
        gets its own noise pattern over world XZ; softmax over these
        gives smooth biome boundaries."""
        seed = world_seed + biome_index * BIOME_SEED_STRIDE
        u = world_x / self._biome_scale_m
        v = world_z / self._biome_scale_m
        return _gradient_noise_2d(u, v, seed)

    def sample_biome_weights(self, world_x: float, world_z: float,
                             world_seed: int) -> dict[str, float]:
        scalars = [
            self._biome_scalar(b.biome_index, world_x, world_z, world_seed)
            for b in self._biomes
        ]
        mx = max(scalars)
        t = max(self._temperature, 1e-6)
        exps = [math.exp((s - mx) / t) for s in scalars]
        total = sum(exps)
        return {
            b.name: (e / total) for b, e in zip(self._biomes, exps)
        }

    def sample_height(self, world_x: float, world_z: float,
                      world_seed: int) -> float:
        weights = self.sample_biome_weights(world_x, world_z, world_seed)
        h = 0.0
        for b in self._biomes:
            w = weights[b.name]
            if w < 1e-6:
                continue
            h += w * b.kernel.height(world_x, world_z, world_seed, b.params)
        return h
