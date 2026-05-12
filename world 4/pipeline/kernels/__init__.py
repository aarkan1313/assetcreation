"""W4 procedural terrain kernel system.

A `Kernel` is a pure function of (world_seed, world_xz, params) that
produces a heightmap value + per-biome weight value. `KernelComposer`
combines kernels via the biome catalog's per-biome `generator` block.

Built-in kernels are registered in BUILTIN_REGISTRY by
build_builtin_registry(). Called lazily so base-class tests don't
depend on concrete kernel implementations existing yet.
"""
from __future__ import annotations

from kernels.base import Kernel, KernelRegistry, KernelError


def build_builtin_registry() -> KernelRegistry:
    """Construct the registry of built-in kernels. Lazy import to
    avoid circular dependency during testing of the base classes."""
    from kernels.noise_stack import NoiseStackKernel  # noqa: WPS433
    reg = KernelRegistry()
    reg.register(NoiseStackKernel)
    return reg


__all__ = [
    "Kernel",
    "KernelRegistry",
    "KernelError",
    "build_builtin_registry",
]
