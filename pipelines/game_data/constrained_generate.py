"""Balance-constrained generation orchestrator.

Wraps `generate_records.py` with a target TOML, per-slot JSON Schema
narrowing, deterministic kill-dummy simulation, oversample-and-discard fallback,
and a single critique/revise pass only when first-pass acceptance is below 60%.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import generate_records as gen  # noqa: E402
from balance.narrow_schema import narrow_schema  # noqa: E402
from balance.schema import DEFAULT_TARGETS, BalanceTargets, Bounds, load_targets, sha256_file  # noqa: E402
from schemas import AbilitySchool, RECORD_TYPES, Rarity, plural  # noqa: E402
from sim.kill_dummy import simulate_record  # noqa: E402

GAME_DATA = Path(r"D:\assets\game_data")
GENERATED = GAME_DATA / "generated"
REPO = Path(r"D:\assets")

DAMAGE_TYPES = {
    "physical": "physical",
    "elemental": "fire",
    "arcane": "arcane",
    "nature": "poison",
    "shadow": "shadow",
    "holy": "holy",
}


class AssetResolver:
    def __init__(self, repo: Path = REPO) -> None:
        self.icon_ids = self._icon_ids(repo)
        self.vfx_ids = self._vfx_ids(repo)
        self.sfx_ids = self._sfx_ids(repo)

    @staticmethod
    def _icon_ids(repo: Path) -> set[str]:
        path = repo / "ui" / "icons" / "manifest.json"
        if not path.exists():
            return set()
        return {entry["id"] for entry in json.loads(path.read_text(encoding="utf-8")).get("icons", [])}

    @staticmethod
    def _vfx_ids(repo: Path) -> set[str]:
        out: set[str] = set()
        for root in (repo / "vfx" / "catalog", repo / "vfx" / "migrated_from_spell_lab"):
            if not root.exists():
                continue
            for path in root.rglob("effect.json"):
                try:
                    eid = json.loads(path.read_text(encoding="utf-8")).get("id")
                except (OSError, json.JSONDecodeError):
                    continue
                if eid:
                    out.add(eid)
        return out

    @staticmethod
    def _sfx_ids(repo: Path) -> set[str]:
        path = repo / "audio" / "sfx_manifest.json"
        if not path.exists():
            return set()
        return {entry["id"] for entry in json.loads(path.read_text(encoding="utf-8")).get("sounds", [])}

    def icon_for_item(self, rec: dict[str, Any]) -> str | None:
        tags = set(rec.get("tags", []))
        category = rec.get("category")
        candidates = []
        if category == "weapon":
            candidates.extend(["ico_sword", "ico_shield"])
        if "shield" in tags or category == "armor":
            candidates.append("ico_shield")
        if category == "consumable":
            candidates.extend(["ico_potion_red", "ico_potion_blue"])
        if category == "material":
            candidates.extend(["ico_gem_blue", "ico_coin"])
        candidates.extend(["ico_scroll", "ico_coin"])
        return self._first(candidates, self.icon_ids)

    def icon_for_ability(self, rec: dict[str, Any]) -> str | None:
        school = rec.get("school")
        candidates = {
            "physical": ["ico_sword"],
            "elemental": ["ico_gem_blue", "ico_scroll"],
            "arcane": ["ico_gem_blue", "ico_scroll"],
            "nature": ["ico_potion_blue", "ico_scroll"],
            "shadow": ["ico_scroll", "ico_gem_blue"],
            "holy": ["ico_scroll", "ico_gem_blue"],
        }.get(school, ["ico_scroll"])
        return self._first(candidates + ["ico_scroll"], self.icon_ids)

    def vfx_for_ability(self, rec: dict[str, Any]) -> str | None:
        dtype = rec.get("effect", {}).get("damage_type")
        candidates = {
            "fire": ["fireball_projectile", "fireball_projectile_legacy"],
            "arcane": ["arcane_shock_ring_legacy", "warp_blackhole_particles"],
            "shadow": ["smoke_pulse", "smoke_rift_legacy"],
            "poison": ["smoke_pulse", "liquidfun_particle_splash"],
            "holy": ["rune_shatter_legacy", "arcane_shock_ring_legacy"],
            "physical": ["shield_break", "fracture2d_shard_baker"],
            "cold": ["smoke_pulse", "rune_shatter_legacy"],
            "lightning": ["arcane_shock_ring_legacy", "fireball_projectile"],
        }.get(dtype, ["smoke_pulse"])
        return self._first(candidates + ["smoke_pulse"], self.vfx_ids)

    def sfx_for_ability(self, rec: dict[str, Any]) -> str | None:
        dtype = rec.get("effect", {}).get("damage_type")
        candidates = ["sword_swing"] if dtype == "physical" else ["fireball_cast", "ui_click"]
        return self._first(candidates, self.sfx_ids)

    @staticmethod
    def _first(candidates: list[str], available: set[str]) -> str | None:
        for candidate in candidates:
            if candidate in available:
                return candidate
        return sorted(available)[0] if available else None


def _resolve_backend(backend: str) -> str:
    if backend != "auto":
        return backend
    ok, _ = gen._has_openai()
    if ok:
        return "openai"
    ok, _ = gen._has_claude()
    if ok:
        return "claude"
    return "synthetic"


def _mid(bounds: Bounds, integer: bool = False) -> int | float:
    value = (bounds.min + bounds.max) / 2.0
    return int(round(value)) if integer else round(value, 2)


def _clamp(value: float | int | None, bounds: Bounds, integer: bool = False) -> int | float:
    if value is None:
        return _mid(bounds, integer=integer)
    clamped = min(max(float(value), bounds.min), bounds.max)
    return int(round(clamped)) if integer else round(clamped, 2)


def _loc_key(record_type: str, rid: str) -> str:
    return f"{record_type.upper()}_{rid.upper()}"[:64]


def _ability_school_sequence(count: int, seed: int) -> list[AbilitySchool]:
    schools: list[AbilitySchool] = ["elemental", "arcane", "nature", "shadow", "holy", "physical"]
    rng = random.Random(seed)
    rng.shuffle(schools)
    return [schools[i % len(schools)] for i in range(count)]


def slot_plan(targets: BalanceTargets, record_type: str, count: int, seed: int) -> list[dict[str, object]]:
    if record_type == "item":
        return [{"category": "weapon", "rarity": rarity} for rarity in targets.rarity_sequence(count)]
    if record_type == "ability":
        tiers = [1, 2, 3, 4, 5]
        schools = _ability_school_sequence(count, seed)
        return [{"tier": tiers[i % len(tiers)], "school": schools[i]} for i in range(count)]
    return [{} for _ in range(count)]


def _slot_prompt(record_type: str, slot: dict[str, object], failure: str | None = None) -> str:
    bits = [f"Generate for fixed slot: {json.dumps(slot, sort_keys=True)}."]
    if record_type == "item":
        bits.append("The item must be a usable weapon and must have nonzero damage.")
    if record_type == "ability":
        bits.append("The ability must be active, damaging, and sustainable in a 30 second dummy test.")
    if failure:
        bits.append(f"Previous candidate failed deterministic sim with `{failure}`. Revise stats only enough to pass.")
    return "\n".join(bits)


def _call_cloud(
    backend: str,
    record_type: str,
    slot: dict[str, object],
    targets: BalanceTargets,
    count: int,
    seed: int,
    model_name: str,
    failure: str | None = None,
) -> list[dict[str, Any]]:
    cls = RECORD_TYPES[record_type]
    schema = narrow_schema(cls.model_json_schema(), targets, record_type, slot, strict=True)
    prompt = _slot_prompt(record_type, slot, failure=failure)
    if backend == "openai":
        return gen._gen_openai_batch(
            record_type, count, model_name, seed,
            schema_override=schema, prompt_extra=prompt, strict=True,
        )
    if backend == "claude":
        if model_name == "gpt-4o-mini":
            model_name = "claude-sonnet-4-20250514"
        return gen._gen_claude_batch(
            record_type, count, model_name, seed,
            schema_override=schema, prompt_extra=prompt,
        )
    raise ValueError(f"cloud backend expected, got {backend!r}")


def _raw_candidate(
    backend: str,
    record_type: str,
    slot: dict[str, object],
    targets: BalanceTargets,
    seed: int,
    model_name: str,
    failure: str | None = None,
) -> dict[str, Any]:
    if backend in ("openai", "claude"):
        return _call_cloud(backend, record_type, slot, targets, 1, seed, model_name, failure=failure)[0]
    return gen.generate(record_type, 1, backend="synthetic", seed=seed, model_name=model_name)[0]


def _coerce_record(
    record_type: str,
    raw: dict[str, Any],
    slot: dict[str, object],
    targets: BalanceTargets,
    resolver: AssetResolver,
    *,
    seed: int,
) -> dict[str, Any]:
    rec = json.loads(json.dumps(raw))
    rec.setdefault("schema_version", "1.0.0")
    rec.setdefault("tags", [])
    rec.setdefault("notes", "")
    rec.setdefault("provenance", {})
    bounds = targets.bounds_for_slot(record_type, slot)

    if record_type == "item":
        rarity = str(slot.get("rarity", "common"))
        dtype = ["physical", "fire", "cold", "arcane"][seed % 4]
        raw_category = rec.get("category")
        rec["category"] = "weapon"
        rec["rarity"] = rarity
        rec["damage_type"] = dtype
        rec["stack_max"] = 1
        rec.setdefault("stats", {})
        rec["stats"]["damage"] = _clamp(rec["stats"].get("damage"), bounds["stats.damage"], integer=True)
        rec["stats"]["weight"] = _clamp(rec["stats"].get("weight"), bounds["stats.weight"])
        rec["stats"]["value_gold"] = _clamp(rec["stats"].get("value_gold"), bounds["stats.value_gold"], integer=True)
        if "stats.durability" in bounds:
            rec["stats"]["durability"] = _clamp(
                rec["stats"].get("durability"), bounds["stats.durability"], integer=True,
            )
        rec["stats"]["armor"] = 0
        if not rec.get("display_name") or raw_category != "weapon":
            rec["id"] = f"{rarity}_{dtype}_blade_{seed % 10000}"
            rec["localization_key"] = _loc_key(record_type, rec["id"])
            rec["display_name"] = f"{rarity.title()} Training Blade"
            rec["description"] = f"A {rarity} {dtype} weapon tuned by the balance target."
            rec["tags"] = [dtype, rarity, "weapon"]
        else:
            rec["description"] = rec.get("description") or f"A {rarity} training weapon tuned by the balance target."
            rec["tags"] = sorted(set([dtype, "weapon"] + [t for t in rec.get("tags", []) if isinstance(t, str)]))[:12]
        rec["icon_id"] = resolver.icon_for_item(rec)

    if record_type == "ability":
        tier = int(slot.get("tier", 1))
        school = str(slot.get("school", "elemental"))
        dtype = DAMAGE_TYPES.get(school, "fire")
        rec["kind"] = "active"
        rec["tier"] = tier
        rec["school"] = school
        rec.setdefault("shape", "projectile")
        shape = str(rec.get("shape", "projectile"))
        rec["id"] = f"{school}_{shape}_t{tier}_{seed % 10000}"[:40].rstrip("_")
        rec["localization_key"] = _loc_key(record_type, rec["id"])
        rec["display_name"] = f"{school.title()} {shape.replace('_', ' ').title()} T{tier}"
        rec.setdefault("cost", {})
        rec.setdefault("effect", {})
        rec["cost"]["mana"] = int(bounds["cost.mana"].min)
        rec["cost"].setdefault("stamina", 0)
        rec["cost"]["cooldown_sec"] = float(bounds["cost.cooldown_sec"].min)
        rec["effect"]["damage"] = _mid(bounds["effect.damage"], integer=True)
        rec["effect"]["damage_type"] = dtype
        rec["effect"].setdefault("healing", 0)
        rec["effect"].setdefault("radius_m", 0.0)
        rec["effect"].setdefault("duration_sec", 0.0)
        rec["effect"]["status_tags"] = [f"{dtype}_touched"]
        rec["description"] = f"A tier {tier} {school} ability tuned by the balance target."
        rec["tags"] = list(dict.fromkeys([school, dtype, shape]))
        rec["icon_id"] = resolver.icon_for_ability(rec)
        rec["vfx_id"] = resolver.vfx_for_ability(rec)
        rec["sfx_id"] = resolver.sfx_for_ability(rec)

    if not rec.get("localization_key"):
        rec["localization_key"] = _loc_key(record_type, rec["id"])
    return rec


def _revise_for_failure(
    record_type: str,
    record: dict[str, Any],
    slot: dict[str, object],
    targets: BalanceTargets,
    failure: str,
) -> dict[str, Any]:
    rec = json.loads(json.dumps(record))
    bounds = targets.bounds_for_slot(record_type, slot)
    if failure == "reject:dummy_survived":
        if record_type == "item":
            rec["stats"]["damage"] = int(bounds["stats.damage"].max)
        if record_type == "ability":
            rec["effect"]["damage"] = int(bounds["effect.damage"].max)
            rec["cost"]["cooldown_sec"] = float(bounds["cost.cooldown_sec"].min)
            rec["cost"]["mana"] = int(bounds["cost.mana"].min)
    elif failure == "reject:ttk_too_low":
        if record_type == "item":
            rec["stats"]["damage"] = int(bounds["stats.damage"].min)
        if record_type == "ability":
            rec["effect"]["damage"] = int(bounds["effect.damage"].min)
            rec["cost"]["cooldown_sec"] = float(bounds["cost.cooldown_sec"].max)
    elif failure == "reject:no_damage":
        if record_type == "item":
            rec["stats"]["damage"] = max(1, int(bounds["stats.damage"].min))
        if record_type == "ability":
            rec["effect"]["damage"] = max(1, int(bounds["effect.damage"].min))
    return rec


def _dedupe_ids(records: list[dict[str, Any]], record_type: str) -> None:
    seen: dict[str, int] = {}
    seen_names: dict[str, int] = {}
    for rec in records:
        rid = rec["id"][:40]
        if rid in seen:
            seen[rid] += 1
            suffix = f"_{seen[rid]}"
            rid = (rid[: 40 - len(suffix)] + suffix).rstrip("_")
            rec["id"] = rid
            rec["localization_key"] = _loc_key(record_type, rid)
        else:
            seen[rid] = 0
        name = rec.get("display_name", "")
        if name in seen_names:
            seen_names[name] += 1
            suffix = f" {seen_names[name] + 1}"
            rec["display_name"] = (name[: 64 - len(suffix)] + suffix).strip()
        else:
            seen_names[name] = 0


def _stamp_provenance(
    record: dict[str, Any],
    *,
    backend: str,
    model_name: str,
    seed: int,
    target_hash: str,
    sim_digest: str,
    constraint_pass: str,
    parent_id: str | None = None,
) -> None:
    model = model_name
    if backend == "claude" and model == "gpt-4o-mini":
        model = "claude-sonnet-4-20250514"
    record["provenance"] = {
        **(record.get("provenance") or {}),
        "source": "synthetic" if backend == "synthetic" else "llm",
        "model": None if backend == "synthetic" else model,
        "seed": seed,
        "target_file_sha256": target_hash,
        "constraint_technique": (
            "openai_strict_schema" if backend == "openai"
            else "claude_tool_schema" if backend == "claude"
            else "synthetic_schema_bounds"
        ),
        "constraint_pass": constraint_pass,
        "sim_digest": sim_digest,
        "parent_id": parent_id,
    }


def generate_constrained(
    record_type: str,
    count: int,
    *,
    backend: str = "auto",
    seed: int = 0,
    model_name: str = "gpt-4o-mini",
    target_path: Path = DEFAULT_TARGETS,
    oversample_factor: float = 3.0,
) -> list[dict[str, Any]]:
    if record_type not in RECORD_TYPES:
        raise KeyError(f"unknown record_type {record_type}; expected one of {list(RECORD_TYPES)}")
    if record_type not in ("item", "ability"):
        return gen.generate(record_type, count, backend=backend, seed=seed, model_name=model_name)

    targets = load_targets(target_path)
    target_hash = sha256_file(target_path)
    backend_used = _resolve_backend(backend)
    resolver = AssetResolver()
    plan = slot_plan(targets, record_type, count, seed)
    accepted: list[dict[str, Any]] = []
    rejected: list[tuple[dict[str, Any], dict[str, object], str, int]] = []

    for idx, slot in enumerate(plan):
        raw = _raw_candidate(backend_used, record_type, slot, targets, seed + idx, model_name)
        rec = _coerce_record(record_type, raw, slot, targets, resolver, seed=seed + idx)
        result = simulate_record(record_type, rec, seed=seed + idx)
        if result.verdict == "pass":
            _stamp_provenance(
                rec, backend=backend_used, model_name=model_name, seed=seed + idx,
                target_hash=target_hash, sim_digest=result.digest, constraint_pass="first_pass",
            )
            accepted.append(RECORD_TYPES[record_type].model_validate(rec).model_dump())
        else:
            rejected.append((rec, slot, result.verdict, seed + idx))

    first_pass_rate = len(accepted) / max(1, count)
    max_attempts = max(0, math.ceil(count * oversample_factor) - count)
    attempt = 0
    while len(accepted) < count and attempt < max_attempts:
        slot = plan[(len(accepted) + attempt) % len(plan)]
        raw = _raw_candidate(backend_used, record_type, slot, targets, seed + 1000 + attempt, model_name)
        rec = _coerce_record(record_type, raw, slot, targets, resolver, seed=seed + 1000 + attempt)
        result = simulate_record(record_type, rec, seed=seed + 1000 + attempt)
        if result.verdict == "pass":
            _stamp_provenance(
                rec, backend=backend_used, model_name=model_name, seed=seed + 1000 + attempt,
                target_hash=target_hash, sim_digest=result.digest, constraint_pass="oversample",
            )
            accepted.append(RECORD_TYPES[record_type].model_validate(rec).model_dump())
        else:
            rejected.append((rec, slot, result.verdict, seed + 1000 + attempt))
        attempt += 1

    if first_pass_rate < 0.60 and len(accepted) < count:
        for rec, slot, failure, rec_seed in rejected:
            if len(accepted) >= count:
                break
            parent_id = rec.get("id")
            if backend_used in ("openai", "claude"):
                raw = _raw_candidate(backend_used, record_type, slot, targets, rec_seed + 5000, model_name, failure=failure)
                rec = _coerce_record(record_type, raw, slot, targets, resolver, seed=rec_seed + 5000)
            else:
                rec = _revise_for_failure(record_type, rec, slot, targets, failure)
            result = simulate_record(record_type, rec, seed=rec_seed + 5000)
            if result.verdict == "pass":
                _stamp_provenance(
                    rec, backend=backend_used, model_name=model_name, seed=rec_seed + 5000,
                    target_hash=target_hash, sim_digest=result.digest,
                    constraint_pass="critique_revise", parent_id=parent_id,
                )
                accepted.append(RECORD_TYPES[record_type].model_validate(rec).model_dump())

    _dedupe_ids(accepted, record_type)
    if len(accepted) < count:
        raise RuntimeError(
            f"constrained generation accepted {len(accepted)}/{count} {record_type} records "
            f"(first_pass={first_pass_rate:.0%})"
        )
    return accepted[:count]


def write_jsonl(path: Path, records: list[dict[str, Any]], *, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("record_type", choices=sorted(RECORD_TYPES))
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--backend", choices=("auto", "openai", "claude", "synthetic"), default="auto")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--target-balance", type=Path, default=DEFAULT_TARGETS)
    ap.add_argument("--oversample-factor", type=float, default=3.0)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()

    records = generate_constrained(
        args.record_type,
        args.count,
        backend=args.backend,
        seed=args.seed,
        model_name=args.model,
        target_path=args.target_balance,
        oversample_factor=args.oversample_factor,
    )
    out_path = args.out or (GENERATED / f"{plural(args.record_type)}.jsonl")
    write_jsonl(out_path, records, append=args.append)
    print(f"[constrained_generate] {len(records)} {args.record_type}(s) -> {out_path}")
    print(f"[constrained_generate] backend={_resolve_backend(args.backend)} target={args.target_balance}")
    for rec in records:
        prov = rec.get("provenance", {})
        print(f"  {rec['id']}: pass={prov.get('constraint_pass')} sim={prov.get('sim_digest')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
