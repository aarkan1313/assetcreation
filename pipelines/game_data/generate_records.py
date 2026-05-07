"""Candidate record generator.

Two backends, picked at runtime:

  1. **openai** - uses OpenAI's structured-output API (response_format=Pydantic).
     Activates when OPENAI_API_KEY is set in the user environment AND the
     `openai` package is importable. Recommended for real generation.

  2. **synthetic** - deterministic offline generator that samples from seed
     vocabularies. Always available. Produces real, validation-passing records
     so the rest of the pipeline can be exercised end-to-end without any keys.

CLI:
  python generate_records.py item --count 10 --seed 7
  python generate_records.py ability --count 5 --backend openai

Output goes to game_data/generated/<record_type>s.jsonl. One JSON per line,
each one a fully-validated Pydantic record.

Per F_game_data: small batches (10-25), never overwrite shipping content,
log provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from schemas import (  # noqa: E402
    Ability, AbilityCost, AbilityEffect,
    Faction, Item, ItemStats, LoreTerm, NPC, Provenance, RECORD_TYPES, plural,
)

GAME_DATA = Path(r"D:\assets\game_data")
GENERATED = GAME_DATA / "generated"
SEEDS = GAME_DATA / "source" / "seeds"


# -------- seed vocabularies (used by synthetic backend) --------

SEED_DATA: dict[str, dict[str, list[str]]] = {
    "weapons": {
        "adjective": ["iron", "steel", "rusted", "ember", "frost", "moonsilver",
                      "obsidian", "bronze", "thornwood", "stormcast"],
        "weapon": ["sword", "dagger", "spear", "axe", "mace", "bow", "staff",
                  "warhammer", "scimitar", "halberd"],
    },
    "armor": {
        "adjective": ["leather", "chain", "plate", "scale", "padded", "studded"],
        "armor": ["helm", "cuirass", "greaves", "gauntlets", "shield", "boots"],
    },
    "consumables": {
        "kind": ["potion", "elixir", "draught", "tonic", "philtre"],
        "effect": ["healing", "mana", "fire-resist", "speed", "stoneflesh"],
    },
    "abilities": {
        "verb": ["bolt", "burst", "lance", "ward", "pulse", "veil", "mend",
                 "shatter", "summon", "rebuke"],
        "element": ["frost", "fire", "arc", "shadow", "verdant", "radiant",
                    "void", "stone"],
    },
    "factions": {
        "name": ["Order", "Concord", "Hand", "Circle", "Pact", "Guild", "Conclave"],
        "epithet": ["Ashen", "Verdant", "Iron", "Silent", "Wandering", "Riven",
                    "Sunken", "Hollow"],
    },
    "npc_first": [
        "Mara", "Erdan", "Thorne", "Ysolde", "Brann", "Kira", "Sef", "Vellan",
        "Lira", "Orwin", "Caedis", "Pell", "Nessa", "Hakon", "Junie",
    ],
    "npc_last": [
        "Vex", "Halloran", "of-the-Pines", "Stormrest", "Ash", "Brightwater",
        "the-Grim", "Marchant", "Hollow", "Thrice-Born",
    ],
    "biomes": [
        "forest", "highland", "fen", "tundra", "desert", "coast", "ruin",
        "cavern", "marsh", "alpine",
    ],
    "lore_categories": ["place", "person", "concept", "artifact", "event", "deity"],
    "lore_places": [
        "Fenmoor", "Aldwyck", "Saltreach", "Greyspine", "Hollowfen",
        "the Riven Coast", "the Pale Reach",
    ],
    "lore_concepts": [
        "the Sundering", "the Long Hush", "the Verdant Pact",
        "the Ash Compact", "the Tidewatch",
    ],
}


def _save_seeds_to_disk() -> None:
    SEEDS.mkdir(parents=True, exist_ok=True)
    (SEEDS / "vocab.json").write_text(json.dumps(SEED_DATA, indent=2))


# -------- synthetic backend --------


def _stable_id(prefix: str, parts: list[str]) -> str:
    chunks = [p.lower().replace(" ", "_").replace("-", "") for p in parts]
    if prefix:
        chunks.insert(0, prefix)
    raw = "_".join(c for c in chunks if c)
    raw = "".join(c for c in raw if c.isalnum() or c == "_").lstrip("_")
    if not raw or not raw[0].isalpha():
        raw = "x_" + raw
    return raw[:40].rstrip("_")


def _loc_key(record_type: str, item_id: str) -> str:
    return f"{record_type.upper()}_{item_id.upper()}"


def _provenance(backend: str, seed: int, model: str | None = None) -> Provenance:
    return Provenance(
        source="synthetic" if backend == "synthetic" else "llm",
        model=model,
        seed=seed,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def _gen_synthetic_item(rng: random.Random, idx: int, seed: int) -> Item:
    pick = rng.choice(["weapon", "armor", "consumable", "material"])
    if pick == "weapon":
        adj = rng.choice(SEED_DATA["weapons"]["adjective"])
        wpn = rng.choice(SEED_DATA["weapons"]["weapon"])
        item_id = _stable_id("", [adj, wpn]) + f"_{idx}"
        dmg_type = rng.choice(["physical", "fire", "cold", "arcane"])
        stats = ItemStats(
            damage=rng.randint(5, 60),
            weight=round(rng.uniform(0.5, 8.0), 1),
            durability=rng.randint(80, 400),
            value_gold=rng.randint(10, 800),
        )
        return Item(
            id=item_id,
            display_name=f"{adj.capitalize()} {wpn.capitalize()}",
            category="weapon",
            rarity=rng.choice(["common", "common", "uncommon", "rare"]),
            damage_type=dmg_type,
            stats=stats,
            icon_id=f"ico_{wpn}_{adj}"[:40],
            description=f"A {adj} {wpn}. Forged for {rng.choice(['siege', 'duels', 'hunting', 'pilgrim guards'])}.",
            tags=[adj, wpn, "weapon"],
            localization_key=_loc_key("item", item_id),
            provenance=_provenance("synthetic", seed),
        )
    if pick == "armor":
        adj = rng.choice(SEED_DATA["armor"]["adjective"])
        piece = rng.choice(SEED_DATA["armor"]["armor"])
        item_id = _stable_id("", [adj, piece]) + f"_{idx}"
        stats = ItemStats(
            armor=rng.randint(2, 40),
            weight=round(rng.uniform(0.4, 12.0), 1),
            durability=rng.randint(80, 400),
            value_gold=rng.randint(15, 500),
        )
        return Item(
            id=item_id,
            display_name=f"{adj.capitalize()} {piece.capitalize()}",
            category="armor",
            rarity=rng.choice(["common", "common", "uncommon"]),
            stats=stats,
            icon_id=f"ico_{piece}_{adj}"[:40],
            description=f"A {adj} {piece}. Standard issue for the local watch.",
            tags=[adj, piece, "armor"],
            localization_key=_loc_key("item", item_id),
            provenance=_provenance("synthetic", seed),
        )
    if pick == "consumable":
        kind = rng.choice(SEED_DATA["consumables"]["kind"])
        eff = rng.choice(SEED_DATA["consumables"]["effect"])
        item_id = _stable_id("", [eff, kind]) + f"_{idx}"
        return Item(
            id=item_id,
            display_name=f"{eff.replace('-', ' ').capitalize()} {kind.capitalize()}",
            category="consumable",
            rarity=rng.choice(["common", "uncommon"]),
            stats=ItemStats(weight=0.2, durability=1, value_gold=rng.randint(5, 60)),
            icon_id=f"ico_{kind}_{eff}".replace("-", "_")[:40],
            description=f"A {kind} of {eff.replace('-', ' ')}. Single use.",
            tags=[kind, eff.replace("-", "_")],
            localization_key=_loc_key("item", item_id),
            stack_max=10,
            provenance=_provenance("synthetic", seed),
        )
    # material
    mats = ["iron_ore", "leather_scrap", "mana_dust", "linen_thread", "oak_plank"]
    mat = rng.choice(mats)
    item_id = f"{mat}_{idx}"
    return Item(
        id=item_id,
        display_name=mat.replace("_", " ").title(),
        category="material",
        rarity="common",
        stats=ItemStats(weight=round(rng.uniform(0.05, 1.0), 2), value_gold=rng.randint(1, 20)),
        icon_id=f"ico_mat_{mat}"[:40],
        description=f"A small quantity of {mat.replace('_', ' ')}. Used in crafting.",
        tags=["material"],
        localization_key=_loc_key("item", item_id),
        stack_max=99,
        provenance=_provenance("synthetic", seed),
    )


def _gen_synthetic_ability(rng: random.Random, idx: int, seed: int) -> Ability:
    verb = rng.choice(SEED_DATA["abilities"]["verb"])
    element = rng.choice(SEED_DATA["abilities"]["element"])
    item_id = _stable_id("", [element, verb]) + f"_{idx}"
    school_map = {
        "frost": "elemental", "fire": "elemental", "arc": "elemental",
        "shadow": "shadow", "verdant": "nature", "radiant": "holy",
        "void": "arcane", "stone": "elemental",
    }
    dmg_map = {
        "frost": "cold", "fire": "fire", "arc": "lightning",
        "shadow": "shadow", "verdant": "poison", "radiant": "holy",
        "void": "arcane", "stone": "physical",
    }
    shape = rng.choice(["projectile", "self", "aura", "cone", "point"])
    tier = rng.randint(1, 5)
    cost = AbilityCost(
        mana=tier * rng.randint(8, 20),
        cooldown_sec=round(rng.uniform(0.5, 8.0) * tier, 1),
    )
    eff = AbilityEffect(
        damage=tier * rng.randint(5, 15),
        damage_type=dmg_map[element],
        radius_m=round(rng.uniform(0.0, 6.0), 1) if shape in ("aura", "point", "cone") else 0.0,
        duration_sec=round(rng.uniform(0.0, 6.0), 1),
        status_tags=[f"{element}_touched"][:1],
    )
    return Ability(
        id=item_id,
        display_name=f"{element.capitalize()} {verb.capitalize()}",
        kind=rng.choice(["active", "active", "active", "passive"]),
        school=school_map[element],
        tier=tier,
        shape=shape,
        cost=cost,
        effect=eff,
        icon_id=f"ico_abil_{element}_{verb}"[:40],
        vfx_id=f"vfx_{element}_{shape}"[:40],
        sfx_id=f"sfx_{element}_{verb}"[:40],
        description=f"Channels {element} power as a {shape}. Tier {tier} {school_map[element]} ability.",
        tags=[element, school_map[element], shape],
        localization_key=_loc_key("ability", item_id),
        provenance=_provenance("synthetic", seed),
    )


def _gen_synthetic_npc(
    rng: random.Random, idx: int, seed: int, faction_pool: list[str], ability_pool: list[str]
) -> NPC:
    first = rng.choice(SEED_DATA["npc_first"])
    last = rng.choice(SEED_DATA["npc_last"])
    npc_id = _stable_id("", [first, last]) + f"_{idx}"
    role = rng.choice(["vendor", "questgiver", "enemy", "ally", "neutral"])
    level = rng.randint(1, 20)
    health = level * rng.randint(20, 60)
    abilities = rng.sample(ability_pool, k=min(2, len(ability_pool))) if ability_pool else []
    faction_id = rng.choice(faction_pool) if faction_pool and rng.random() > 0.3 else None
    return NPC(
        id=npc_id,
        display_name=f"{first} {last.replace('-', ' ').replace('of_the_', 'of the ').replace('the_', 'the ')}".strip(),
        role=role,
        faction_id=faction_id,
        biome=rng.choice(SEED_DATA["biomes"]),
        level=level,
        health=health,
        abilities=abilities,
        description=f"A level-{level} {role} found in the {rng.choice(SEED_DATA['biomes'])}.",
        tags=[role],
        localization_key=_loc_key("npc", npc_id),
        provenance=_provenance("synthetic", seed),
    )


def _gen_synthetic_faction(rng: random.Random, idx: int, seed: int) -> Faction:
    name = rng.choice(SEED_DATA["factions"]["name"])
    epithet = rng.choice(SEED_DATA["factions"]["epithet"])
    fac_id = _stable_id("", [epithet, name]) + f"_{idx}"
    palette = ["#3a4a2e", "#7c2c2c", "#2c3a7c", "#7c6e2c", "#2c7c6e", "#5a2c7c"]
    return Faction(
        id=fac_id,
        display_name=f"The {epithet} {name}",
        ideology=rng.choice(["balance", "expansion", "preservation", "vengeance", "trade"]),
        primary_color=rng.choice(palette),
        secondary_color=rng.choice(palette),
        territory=rng.sample(SEED_DATA["biomes"], k=2),
        sigil_prompt=f"a sigil of the {epithet.lower()} {name.lower()}, "
                     f"{rng.choice(['heraldic', 'monastic', 'martial'])} style",
        description=f"The {epithet} {name}: a {rng.choice(['minor', 'rising', 'ancient'])} order.",
        tags=[epithet.lower(), "faction"],
        localization_key=_loc_key("faction", fac_id),
        provenance=_provenance("synthetic", seed),
    )


def _gen_synthetic_lore(rng: random.Random, idx: int, seed: int) -> LoreTerm:
    cat = rng.choice(SEED_DATA["lore_categories"])
    if cat == "place":
        spelling = rng.choice(SEED_DATA["lore_places"])
    elif cat == "concept":
        spelling = rng.choice(SEED_DATA["lore_concepts"])
    else:
        spelling = f"{rng.choice(SEED_DATA['npc_first'])} the {rng.choice(['Wise', 'Cruel', 'Forgotten'])}"
    term_id = _stable_id("lore", [spelling]) + f"_{idx}"
    return LoreTerm(
        id=term_id,
        display_name=spelling,
        canonical_spelling=spelling,
        aliases=[],
        category=cat,
        description=f"{spelling} - a {cat} of regional importance. (placeholder lore body)",
        tags=[cat],
        localization_key=_loc_key("lore", term_id),
        provenance=_provenance("synthetic", seed),
    )


# -------- OpenAI backend (cloud, optional) --------


def _has_openai() -> tuple[bool, str | None]:
    """Return (available, reason_if_not). Checks env + import."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return False, "OPENAI_API_KEY not set"
    try:
        import openai  # noqa: F401
    except ImportError:
        return False, "openai package not installed (pip install openai)"
    return True, None


def _batch_schema(schema: dict[str, Any], count: int | None = None) -> dict[str, Any]:
    records_spec: dict[str, Any] = {"type": "array", "items": schema}
    if count is not None:
        records_spec["minItems"] = count
        records_spec["maxItems"] = count
    return {
        "type": "object",
        "properties": {"records": records_spec},
        "required": ["records"],
        "additionalProperties": False,
    }


def _generation_prompt(record_type: str, count: int, prompt_extra: str | None = None) -> str:
    prompt = (
        f"Generate exactly {count} unique {record_type} records for a fantasy "
        f"action-RPG game. Each record must satisfy the schema. Use varied "
        f"adjectives, schools, and elements. Make IDs lowercase snake_case "
        f"unique tokens. Generate descriptions of 1-2 sentences. Tag list "
        f"should match the record's category and theme."
    )
    if prompt_extra:
        prompt += "\n\nAdditional constraints:\n" + prompt_extra
    return prompt


def _gen_openai_batch(
    record_type: str,
    count: int,
    model_name: str,
    seed: int,
    schema_override: dict[str, Any] | None = None,
    prompt_extra: str | None = None,
    strict: bool = False,
) -> list[dict[str, Any]]:
    """Real OpenAI structured-output call. Returns raw dicts; caller validates."""
    from openai import OpenAI

    cls = RECORD_TYPES[record_type]
    schema = schema_override or cls.model_json_schema()
    client = OpenAI()

    prompt = _generation_prompt(record_type, count, prompt_extra=prompt_extra)

    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a game-data generator. "
                                          "Return ONLY a JSON object with key 'records' "
                                          "containing an array of records."},
            {"role": "user", "content": prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": f"{record_type}_batch",
                "schema": _batch_schema(schema, count=count),
                "strict": strict,
            },
        },
        seed=seed,
    )
    payload = json.loads(resp.choices[0].message.content)
    return payload["records"]


# -------- Anthropic / Claude backend (cloud, optional) --------


def _has_claude() -> tuple[bool, str | None]:
    """Return (available, reason_if_not). Checks env + import."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return False, "ANTHROPIC_API_KEY not set"
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "anthropic package not installed (pip install anthropic)"
    return True, None


def _gen_claude_batch(
    record_type: str,
    count: int,
    model_name: str,
    seed: int,
    schema_override: dict[str, Any] | None = None,
    prompt_extra: str | None = None,
) -> list[dict[str, Any]]:
    """Anthropic Messages API tool-use structured output. Returns raw dicts."""
    import anthropic

    cls = RECORD_TYPES[record_type]
    schema = schema_override or cls.model_json_schema()
    client = anthropic.Anthropic()
    prompt = _generation_prompt(record_type, count, prompt_extra=prompt_extra)
    prompt += f"\n\nSeed hint for deterministic variety: {seed}."

    resp = client.messages.create(
        model=model_name,
        max_tokens=4096,
        system="You are a game-data generator. Use the provided tool exactly once.",
        messages=[{"role": "user", "content": prompt}],
        tools=[{
            "name": "emit_records",
            "description": "Return generated game data records.",
            "input_schema": _batch_schema(schema, count=count),
        }],
        tool_choice={"type": "tool", "name": "emit_records"},
    )
    for block in resp.content:
        btype = getattr(block, "type", None)
        if btype == "tool_use":
            payload = getattr(block, "input", None)
            if isinstance(payload, dict) and "records" in payload:
                return payload["records"]
    raise RuntimeError("claude backend did not return emit_records tool output")


# -------- main entry --------


def generate(
    record_type: str,
    count: int,
    backend: str = "auto",
    seed: int = 0,
    model_name: str = "gpt-4o-mini",
) -> list[dict[str, Any]]:
    """Generate `count` records of `record_type` using the chosen backend.

    Returns a list of validated record dicts (model_dump()).
    Writes nothing to disk - caller decides where to save.
    """
    if record_type not in RECORD_TYPES:
        raise KeyError(f"unknown record_type {record_type}; expected one of {list(RECORD_TYPES)}")

    rng = random.Random(seed)

    if backend == "auto":
        ok, _reason = _has_openai()
        if ok:
            backend = "openai"
        else:
            ok, _reason = _has_claude()
            backend = "claude" if ok else "synthetic"

    if backend == "openai":
        ok, reason = _has_openai()
        if not ok:
            raise RuntimeError(f"openai backend unavailable: {reason}")
        raw_records = _gen_openai_batch(record_type, count, model_name, seed)
        cls = RECORD_TYPES[record_type]
        records = []
        for i, raw in enumerate(raw_records):
            # provenance fix-up - let our pipeline own this
            raw["provenance"] = _provenance("openai", seed, model_name).model_dump()
            obj = cls.model_validate(raw)
            records.append(obj.model_dump())
        return records

    if backend == "claude":
        ok, reason = _has_claude()
        if not ok:
            raise RuntimeError(f"claude backend unavailable: {reason}")
        if model_name == "gpt-4o-mini":
            model_name = "claude-sonnet-4-20250514"
        raw_records = _gen_claude_batch(record_type, count, model_name, seed)
        cls = RECORD_TYPES[record_type]
        records = []
        for raw in raw_records:
            raw["provenance"] = _provenance("claude", seed, model_name).model_dump()
            obj = cls.model_validate(raw)
            records.append(obj.model_dump())
        return records

    # synthetic backend - deterministic, no keys needed
    out: list[Any] = []
    if record_type == "item":
        out = [_gen_synthetic_item(rng, i, seed) for i in range(count)]
    elif record_type == "ability":
        out = [_gen_synthetic_ability(rng, i, seed) for i in range(count)]
    elif record_type == "faction":
        out = [_gen_synthetic_faction(rng, i, seed) for i in range(count)]
    elif record_type == "npc":
        # need faction + ability pools first
        faction_pool: list[str] = []
        ability_pool: list[str] = []
        for base in (GENERATED, GAME_DATA / "validated"):
            fac_path = base / f"{plural('faction')}.jsonl"
            ab_path = base / f"{plural('ability')}.jsonl"
            if not faction_pool and fac_path.exists():
                for line in fac_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        faction_pool.append(json.loads(line)["id"])
            if not ability_pool and ab_path.exists():
                for line in ab_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        ability_pool.append(json.loads(line)["id"])
        out = [_gen_synthetic_npc(rng, i, seed, faction_pool, ability_pool) for i in range(count)]
    elif record_type == "lore_term":
        out = [_gen_synthetic_lore(rng, i, seed) for i in range(count)]

    # dedupe by id - if collision, append hash suffix
    seen: dict[str, int] = {}
    deduped = []
    for rec in out:
        if rec.id in seen:
            seen[rec.id] += 1
            new_id = f"{rec.id}_{seen[rec.id]}"
            rec.id = new_id[:40]
            rec.localization_key = _loc_key(record_type, new_id)
        seen[rec.id] = seen.get(rec.id, 0)
        deduped.append(rec.model_dump())
    return deduped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("record_type", choices=sorted(RECORD_TYPES))
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--backend", choices=("auto", "openai", "claude", "synthetic"), default="auto")
    ap.add_argument("--model", default="gpt-4o-mini",
                    help="Provider model name (OpenAI or Claude cloud backends)")
    ap.add_argument("--target-balance", nargs="?", const=ROOT / "balance" / "targets.toml",
                    type=Path, default=None,
                    help="Use balance-constrained generation with optional TOML target file")
    ap.add_argument("--out", type=Path, default=None,
                    help="Output JSONL path (default: game_data/generated/<type>s.jsonl)")
    ap.add_argument("--append", action="store_true",
                    help="Append to existing JSONL instead of overwriting")
    args = ap.parse_args()

    _save_seeds_to_disk()

    if args.target_balance:
        from constrained_generate import generate_constrained

        records = generate_constrained(
            args.record_type,
            count=args.count,
            backend=args.backend,
            seed=args.seed,
            model_name=args.model,
            target_path=args.target_balance,
        )
    else:
        records = generate(
            args.record_type,
            count=args.count,
            backend=args.backend,
            seed=args.seed,
            model_name=args.model,
        )

    out_path = args.out or (GENERATED / f"{plural(args.record_type)}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.append else "w"
    with out_path.open(mode, encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    backend_used = (
        "openai" if args.backend == "openai"
        else "claude" if args.backend == "claude"
        else ("openai" if args.backend == "auto" and _has_openai()[0]
              else ("claude" if args.backend == "auto" and _has_claude()[0] else "synthetic"))
    )
    print(f"[generate_records] {len(records)} {args.record_type}(s) -> {out_path}")
    print(f"[generate_records] backend={backend_used} seed={args.seed}")


if __name__ == "__main__":
    main()
