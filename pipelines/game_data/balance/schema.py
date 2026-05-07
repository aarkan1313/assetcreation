"""Pydantic model and helpers for `balance/targets.toml`."""
from __future__ import annotations

import hashlib
import sys
import tomllib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schemas import AbilitySchool, Rarity  # noqa: E402

DEFAULT_TARGETS = Path(__file__).resolve().parent / "targets.toml"


class Bounds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float
    max: float

    @model_validator(mode="after")
    def _ordered(self) -> "Bounds":
        if self.min > self.max:
            raise ValueError(f"bounds min {self.min} exceeds max {self.max}")
        return self

    def as_number_schema(self) -> dict[str, float]:
        return {"minimum": self.min, "maximum": self.max}


class WeaponBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rarity: Rarity
    damage: Bounds
    weight: Bounds
    value_gold: Bounds
    durability: Bounds | None = None


class ItemTargets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weapon: list[WeaponBucket]


class AbilityBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: Annotated[int, Field(ge=1, le=10)]
    mana: Bounds
    cooldown_sec: Bounds
    damage: Bounds


class SimGates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ttk_min_s: Annotated[float, Field(ge=0.0)] = 0.5
    ttk_max_s_by_rarity: dict[Rarity, Annotated[float, Field(gt=0.0)]]
    dps_z_max: float = 3.0
    dps_z_min: float = -2.0
    dominance_max: Annotated[int, Field(ge=0)] = 1


class SimTargets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gates: SimGates


class BalanceTargets(BaseModel):
    """Authoritative generation and simulation targets.

    The TOML file is intentionally human-authored. Tools read this model and
    derive slot plans and per-slot JSON Schema bounds from it; they never write
    back to the TOML.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    description: str
    rarity_histogram: dict[Rarity, Annotated[float, Field(ge=0.0, le=1.0)]]
    ability_school_floor: dict[AbilitySchool, Annotated[int, Field(ge=0)]]
    item: ItemTargets
    ability: list[AbilityBucket]
    sim: SimTargets

    @field_validator("rarity_histogram")
    @classmethod
    def _histogram_complete(cls, v: dict[str, float]) -> dict[str, float]:
        expected = {"common", "uncommon", "rare", "epic", "legendary"}
        missing = expected - set(v)
        if missing:
            raise ValueError(f"rarity_histogram missing {sorted(missing)}")
        total = sum(v.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"rarity_histogram must sum to 1.0, got {total:.4f}")
        return v

    @model_validator(mode="after")
    def _monotonic(self) -> "BalanceTargets":
        rarity_order = ["common", "uncommon", "rare", "epic", "legendary"]
        buckets = {b.rarity: b for b in self.item.weapon}
        missing = set(rarity_order) - set(buckets)
        if missing:
            raise ValueError(f"item.weapon missing rarity bucket(s): {sorted(missing)}")
        prev_max = -1.0
        for rarity in rarity_order:
            bucket = buckets[rarity]
            if bucket.damage.max < prev_max:
                raise ValueError(f"{rarity} weapon damage is not monotonic")
            prev_max = bucket.damage.max

        tiers = sorted(self.ability, key=lambda b: b.tier)
        seen_tiers = {b.tier for b in tiers}
        if not {1, 2, 3, 4, 5}.issubset(seen_tiers):
            raise ValueError("ability buckets must include tiers 1 through 5")
        prev_max = -1.0
        for bucket in tiers:
            if bucket.damage.max < prev_max:
                raise ValueError(f"tier {bucket.tier} ability damage is not monotonic")
            prev_max = bucket.damage.max
        return self

    def weapon_bucket(self, rarity: str) -> WeaponBucket:
        for bucket in self.item.weapon:
            if bucket.rarity == rarity:
                return bucket
        raise KeyError(f"no weapon bucket for rarity={rarity!r}")

    def ability_bucket(self, tier: int) -> AbilityBucket:
        eligible = [b for b in self.ability if b.tier <= tier]
        if not eligible:
            raise KeyError(f"no ability bucket at or below tier={tier}")
        return max(eligible, key=lambda b: b.tier)

    def rarity_sequence(self, count: int) -> list[Rarity]:
        raw = sorted(
            ((rarity, weight * count) for rarity, weight in self.rarity_histogram.items()),
            key=lambda item: item[1],
            reverse=True,
        )
        counts = {rarity: int(weighted) for rarity, weighted in raw}
        while sum(counts.values()) < count:
            rarity = max(raw, key=lambda item: item[1] - counts[item[0]])[0]
            counts[rarity] += 1
        out: list[Rarity] = []
        for rarity in ("common", "uncommon", "rare", "epic", "legendary"):
            out.extend([rarity] * counts.get(rarity, 0))
        return out[:count]

    def bounds_for_slot(self, record_type: str, slot: dict[str, object]) -> dict[str, Bounds]:
        if record_type == "item":
            rarity = str(slot.get("rarity", "common"))
            bucket = self.weapon_bucket(rarity)
            out = {
                "stats.damage": bucket.damage,
                "stats.weight": bucket.weight,
                "stats.value_gold": bucket.value_gold,
            }
            if bucket.durability is not None:
                out["stats.durability"] = bucket.durability
            return out
        if record_type == "ability":
            bucket = self.ability_bucket(int(slot.get("tier", 1)))
            return {
                "cost.mana": bucket.mana,
                "cost.cooldown_sec": bucket.cooldown_sec,
                "effect.damage": bucket.damage,
            }
        return {}


def load_targets(path: Path = DEFAULT_TARGETS) -> BalanceTargets:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return BalanceTargets.model_validate(data)


def sha256_file(path: Path = DEFAULT_TARGETS) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

