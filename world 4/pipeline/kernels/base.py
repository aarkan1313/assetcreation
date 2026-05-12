"""Kernel interface + registry.

A `Kernel` is a pure function of (world_seed, world_xz, params) that
returns a heightmap value (meters) and per-biome weight values
(0..1, dimensionless). Subclasses MUST define class attribute `kind`
(matches biome_catalog.json's `generator.kernel` field) and implement
`height` + `biome_weight`.

All kernel methods must be pure: same inputs -> same outputs. No I/O,
no mutable global state, no time-dependent behavior.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Type


class KernelError(RuntimeError):
    """Raised for kernel-system misuse (unknown kernel, registry clashes)."""


class Kernel(ABC):
    """Abstract base for terrain kernels.

    Subclasses must set the class attribute `kind` to a unique short
    string (e.g. "noise_stack") and implement `height()` +
    `biome_weight()`. The `kind` value is what `biome_catalog.json`'s
    `generator.kernel` field references.
    """

    kind: str = ""  # subclasses override

    @abstractmethod
    def height(self, world_x: float, world_z: float, world_seed: int,
               params: dict) -> float:
        """Return the terrain height (meters) at world position
        (world_x, world_z) for the given kernel params + world seed."""

    @abstractmethod
    def biome_weight(self, biome_name: str, world_x: float, world_z: float,
                     world_seed: int, params: dict) -> float:
        """Return the unnormalized biome weight (0..1, dimensionless)
        for `biome_name` at world position (world_x, world_z). The
        composer normalizes across biomes — this method just returns
        the raw weight."""


class KernelRegistry:
    """Registry of kernel kinds to instances.

    Each registered subclass is instantiated once and held as a
    singleton. Subclasses must be stateless (kernels are pure functions
    of their args; instance state would break the purity contract).
    """

    def __init__(self) -> None:
        self._kernels: dict[str, Kernel] = {}

    def register(self, kernel_cls: Type[Kernel]) -> None:
        kind = kernel_cls.kind
        if not kind:
            raise KernelError(
                f"kernel class {kernel_cls.__name__} must set class attr `kind`")
        if kind in self._kernels:
            raise KernelError(f"kernel {kind!r} already registered")
        self._kernels[kind] = kernel_cls()

    def get(self, kind: str) -> Kernel:
        if kind not in self._kernels:
            raise KernelError(f"unknown kernel {kind!r}")
        return self._kernels[kind]

    def all_kinds(self) -> list[str]:
        return sorted(self._kernels.keys())
