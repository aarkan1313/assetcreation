"""Biome catalog loader/validator for the W4 transitions pipeline.

The catalog declares every biome that exists in a world, which slots
each biome has, and which tier (resolution class) each slot lives in.
It is the single source of truth consumed by build_biome_arrays.py,
build_tile_splats.py, and ScaleWorld at runtime.

Layer index policy:
- Within a tier, layers are laid out in (biome, slot) iteration order
  from the catalog's biome list. Biome A's slots come before biome B's.
- A given (biome, slot) pair has a stable layer index within its tier.
- Layer index is None if the (biome, slot) is not in the requested tier.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Tier:
    name: str
    resolution: int


@dataclass(frozen=True)
class SlotEntry:
    source: str
    tier: str


@dataclass(frozen=True)
class Biome:
    name: str
    kit_dir: str
    slots: dict[str, SlotEntry]


@dataclass(frozen=True)
class Catalog:
    schema_version: int
    tiers: list[Tier]
    slot_names: list[str]
    map_names: list[str]
    biomes: list[Biome]

    def biome_names(self) -> list[str]:
        return [b.name for b in self.biomes]

    def tier_names(self) -> list[str]:
        return [t.name for t in self.tiers]

    def tier_by_name(self, name: str) -> Tier:
        for t in self.tiers:
            if t.name == name:
                return t
        raise CatalogError(f"unknown tier: {name}")

    def biome_by_name(self, name: str) -> Biome:
        for b in self.biomes:
            if b.name == name:
                return b
        raise CatalogError(f"unknown biome: {name}")

    def layer_index(self, biome_name: str, slot_name: str, tier_name: str) -> int | None:
        idx = 0
        for b in self.biomes:
            for s_name in self.slot_names:
                if s_name not in b.slots:
                    continue
                s = b.slots[s_name]
                if s.tier != tier_name:
                    continue
                if b.name == biome_name and s_name == slot_name:
                    return idx
                idx += 1
        return None

    def slot_kit_path(self, biome_name: str, slot_name: str) -> str:
        b = self.biome_by_name(biome_name)
        if slot_name not in b.slots:
            raise CatalogError(f"biome {biome_name!r} has no slot {slot_name!r}")
        return f"{b.kit_dir}/{b.slots[slot_name].source}"

    def all_slot_records(self) -> list[tuple[str, str, str, int]]:
        out = []
        for tier in self.tiers:
            idx = 0
            for b in self.biomes:
                for s_name in self.slot_names:
                    if s_name not in b.slots:
                        continue
                    s = b.slots[s_name]
                    if s.tier != tier.name:
                        continue
                    out.append((b.name, s_name, tier.name, idx))
                    idx += 1
        return out


def load_catalog(path: Path | str) -> Catalog:
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    return _parse(data, source=str(path))


def _parse(data: dict, source: str = "<dict>") -> Catalog:
    try:
        tiers = [Tier(name=t["name"], resolution=int(t["resolution"]))
                 for t in data["tiers"]]
        tier_names = {t.name for t in tiers}
        slot_names = list(data["slots"])
        map_names = list(data["maps"])
        biomes = []
        for bdata in data["biomes"]:
            slots: dict[str, SlotEntry] = {}
            for slot_name in slot_names:
                if slot_name not in bdata["slots"]:
                    raise CatalogError(
                        f"biome {bdata['name']!r} missing slot {slot_name!r}")
                s = bdata["slots"][slot_name]
                if s["tier"] not in tier_names:
                    raise CatalogError(
                        f"biome {bdata['name']!r} slot {slot_name!r}: "
                        f"unknown tier {s['tier']!r}")
                slots[slot_name] = SlotEntry(source=s["source"], tier=s["tier"])
            biomes.append(Biome(name=bdata["name"], kit_dir=bdata["kit_dir"],
                                slots=slots))
        return Catalog(
            schema_version=int(data["schema_version"]),
            tiers=tiers, slot_names=slot_names, map_names=map_names,
            biomes=biomes,
        )
    except KeyError as e:
        raise CatalogError(f"{source}: missing required key {e}") from e
