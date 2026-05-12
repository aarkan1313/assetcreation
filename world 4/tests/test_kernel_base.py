"""Tests for pipeline.kernels.base."""
from __future__ import annotations
import pytest

from kernels.base import Kernel, KernelRegistry, KernelError


def test_abstract_kernel_cannot_instantiate():
    with pytest.raises(TypeError):
        Kernel()  # type: ignore[abstract]


def test_registry_register_and_get():
    reg = KernelRegistry()

    class FakeKernel(Kernel):
        kind = "fake"

        def height(self, world_x, world_z, world_seed, params):
            return 0.0

        def biome_weight(self, biome_name, world_x, world_z, world_seed, params):
            return 0.0

    reg.register(FakeKernel)
    got = reg.get("fake")
    assert isinstance(got, FakeKernel)


def test_registry_get_missing_raises():
    reg = KernelRegistry()
    with pytest.raises(KernelError, match="unknown kernel"):
        reg.get("nope")


def test_registry_register_duplicate_raises():
    reg = KernelRegistry()

    class A(Kernel):
        kind = "dup"

        def height(self, world_x, world_z, world_seed, params): return 0.0

        def biome_weight(self, biome_name, world_x, world_z, world_seed, params):
            return 0.0

    class B(Kernel):
        kind = "dup"

        def height(self, world_x, world_z, world_seed, params): return 1.0

        def biome_weight(self, biome_name, world_x, world_z, world_seed, params):
            return 1.0

    reg.register(A)
    with pytest.raises(KernelError, match="already registered"):
        reg.register(B)
