"""Tiny deterministic combat sim for game-data balance gates.

This is intentionally not the full game. It is a fixed 60 Hz / 30 s harness
that instantiates one generated weapon or active ability against a TrainingDummy
with armor plus eight damage-type resistances. It rejects only degenerate
records: dummy survived, TTK below the floor, no damage, or player death.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schemas import Ability, Item  # noqa: E402

TICK_HZ = 60
SIM_SECONDS = 30
MAX_TICKS = TICK_HZ * SIM_SECONDS


@dataclass
class TrainingDummy:
    hp: float = 200.0
    armor: int = 2
    resist: dict[str, float] = field(default_factory=lambda: {
        "physical": 0.0,
        "fire": 0.15,
        "cold": 0.15,
        "lightning": 0.15,
        "poison": 0.10,
        "arcane": 0.10,
        "holy": 0.10,
        "shadow": 0.10,
    })
    retaliate_dps: float = 5.0


@dataclass
class Player:
    hp: float = 200.0
    mana: float = 100.0
    mana_regen_per_s: float = 5.0
    stamina: float = 100.0


@dataclass
class Loadout:
    weapon: Item | None = None
    ability: Ability | None = None
    swing_period_s: float = 1.2


@dataclass
class SimResult:
    ttk_s: float
    dps: float
    mps: float
    player_died: bool
    ability_uses: int
    weapon_swings: int
    digest: str
    verdict: str


def _apply_damage(dmg: float, dtype: str | None, dummy: TrainingDummy) -> float:
    dtype = dtype or "physical"
    after_armor = max(0.0, dmg - dummy.armor) if dtype == "physical" else dmg
    return after_armor * (1.0 - dummy.resist.get(dtype, 0.0))


def simulate(
    loadout: Loadout,
    dummy: TrainingDummy | None = None,
    player: Player | None = None,
    *,
    seed: int = 0,
    ttk_min_s: float = 0.5,
) -> SimResult:
    rng = random.Random(seed)
    dummy = dummy or TrainingDummy()
    player = player or Player()
    dummy_hp = dummy.hp
    p_hp = player.hp
    p_mana = player.mana
    next_swing_tick = 0
    next_cd_ready_tick = 0
    swings = uses = 0
    total_dmg = total_mana_spent = 0.0
    cd_ticks = max(1, int(((loadout.ability.cost.cooldown_sec if loadout.ability else 0.0)) * TICK_HZ))
    swing_ticks = max(1, int(loadout.swing_period_s * TICK_HZ))
    elapsed_s = 0.0

    for tick in range(MAX_TICKS):
        elapsed_s = (tick + 1) / TICK_HZ
        if loadout.weapon and tick >= next_swing_tick and dummy_hp > 0:
            jitter = 1.0 + rng.uniform(-0.015, 0.015)
            dmg = _apply_damage(loadout.weapon.stats.damage * jitter, loadout.weapon.damage_type, dummy)
            dummy_hp -= dmg
            total_dmg += dmg
            swings += 1
            next_swing_tick = tick + swing_ticks

        if loadout.ability and tick >= next_cd_ready_tick and dummy_hp > 0:
            need = loadout.ability.cost.mana
            if p_mana >= need:
                p_mana -= need
                total_mana_spent += need
                dmg = _apply_damage(loadout.ability.effect.damage, loadout.ability.effect.damage_type, dummy)
                dummy_hp -= dmg
                total_dmg += dmg
                uses += 1
                next_cd_ready_tick = tick + cd_ticks

        p_mana = min(player.mana, p_mana + player.mana_regen_per_s / TICK_HZ)
        p_hp -= dummy.retaliate_dps / TICK_HZ
        if dummy_hp <= 0 or p_hp <= 0:
            break

    ttk = elapsed_s if dummy_hp <= 0 else math.inf
    dps = total_dmg / elapsed_s if elapsed_s > 0 else 0.0
    mps = total_mana_spent / elapsed_s if elapsed_s > 0 else 0.0
    digest_payload = {
        "ability_uses": uses,
        "dps": round(dps, 4),
        "dummy_hp_remaining": round(max(0.0, dummy_hp), 4),
        "player_died": p_hp <= 0,
        "ttk_s": "inf" if math.isinf(ttk) else round(ttk, 4),
        "weapon_swings": swings,
    }
    digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True).encode()).hexdigest()[:16]
    verdict = verdict_for(ttk, dps, p_hp <= 0, ttk_min_s=ttk_min_s)
    return SimResult(ttk, dps, mps, p_hp <= 0, uses, swings, digest, verdict)


def verdict_for(ttk: float, dps: float, player_died: bool, *, ttk_min_s: float = 0.5) -> str:
    if player_died:
        return "reject:player_died"
    if dps <= 0.1:
        return "reject:no_damage"
    if math.isinf(ttk):
        return "reject:dummy_survived"
    if ttk < ttk_min_s:
        return "reject:ttk_too_low"
    return "pass"


def loadout_for(record_type: str, record: dict[str, Any]) -> Loadout:
    if record_type == "item":
        item = Item.model_validate(record)
        return Loadout(weapon=item if item.category == "weapon" else None)
    if record_type == "ability":
        ability = Ability.model_validate(record)
        return Loadout(ability=ability if ability.kind == "active" else None)
    raise ValueError(f"kill_dummy only supports item and ability records, got {record_type!r}")


def simulate_record(record_type: str, record: dict[str, Any], *, seed: int = 0, ttk_min_s: float = 0.5) -> SimResult:
    return simulate(loadout_for(record_type, record), seed=seed, ttk_min_s=ttk_min_s)


def _load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    return [payload]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("record_type", choices=("item", "ability"))
    ap.add_argument("path", type=Path, help="JSON or JSONL record path")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true", help="Emit JSONL metrics")
    args = ap.parse_args()

    failed = 0
    for rec in _load_records(args.path):
        result = simulate_record(args.record_type, rec, seed=args.seed)
        row = {"id": rec.get("id"), **asdict(result)}
        if args.json:
            print(json.dumps(row, ensure_ascii=False))
        else:
            print(f"{row['id']}: {result.verdict} ttk={result.ttk_s:.2f} dps={result.dps:.2f} digest={result.digest}")
        if result.verdict != "pass":
            failed += 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
