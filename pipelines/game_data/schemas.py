"""Pydantic v2 schemas - the single source of truth for game data.

These models are used by:
  - generate_records.py     (as response_format / structured-output schema)
  - validate_records.py     (validation + cross-reference linking + balance)
  - export_godot.py         (codegen of GDScript Resource classes + .tres)

Keep IDs stable, snake_case, lowercase. The id is the join key everywhere.

Five core record types per research/F_game_data.md:
  Item        - weapon/armor/consumable/material/quest
  Ability     - active/passive spell or skill
  NPC         - identity, faction, role, biome
  Faction     - ideology, territory, palette
  LoreTerm    - glossary entry, canonical spelling, aliases
"""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ID_PATTERN = r"^[a-z][a-z0-9_]{1,39}$"
LOC_KEY_PATTERN = r"^[A-Z][A-Z0-9_]{1,63}$"
HEX_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"

IdStr = Annotated[str, StringConstraints(pattern=ID_PATTERN)]
LocKey = Annotated[str, StringConstraints(pattern=LOC_KEY_PATTERN)]
HexColor = Annotated[str, StringConstraints(pattern=HEX_COLOR_PATTERN)]
Tag = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,31}$")]


SCHEMA_VERSION = "1.0.0"


class Provenance(BaseModel):
    """Where did this record come from? Generation audit trail."""
    model_config = ConfigDict(extra="forbid")

    source: Literal["llm", "human", "seed", "import", "synthetic"] = "synthetic"
    model: str | None = None
    seed: int | None = None
    prompt_id: str | None = None
    timestamp: str | None = None
    target_file_sha256: str | None = None
    constraint_technique: str | None = None
    constraint_pass: str | None = None
    sim_digest: str | None = None
    parent_id: str | None = None


class _Record(BaseModel):
    """Common fields. All five concrete types subclass this."""
    model_config = ConfigDict(extra="forbid")

    id: IdStr
    display_name: Annotated[str, StringConstraints(min_length=2, max_length=64)]
    schema_version: str = SCHEMA_VERSION
    tags: list[Tag] = Field(default_factory=list, max_length=12)
    localization_key: LocKey
    provenance: Provenance = Field(default_factory=Provenance)
    notes: Annotated[str, StringConstraints(max_length=512)] = ""

    @field_validator("tags")
    @classmethod
    def _unique_tags(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("tags must be unique")
        return v


# ---------- ITEM ----------

ItemCategory = Literal["weapon", "armor", "consumable", "material", "quest", "tool"]
DamageType = Literal["physical", "fire", "cold", "lightning", "poison", "arcane", "holy", "shadow"]
Rarity = Literal["common", "uncommon", "rare", "epic", "legendary"]


class ItemStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    damage: Annotated[int, Field(ge=0, le=999)] = 0
    armor: Annotated[int, Field(ge=0, le=999)] = 0
    weight: Annotated[float, Field(ge=0.0, le=999.0)] = 0.0
    durability: Annotated[int, Field(ge=0, le=9999)] = 100
    value_gold: Annotated[int, Field(ge=0, le=999_999)] = 0


class Item(_Record):
    category: ItemCategory
    rarity: Rarity = "common"
    damage_type: DamageType | None = None
    stats: ItemStats = Field(default_factory=ItemStats)
    icon_id: IdStr | None = None
    description: Annotated[str, StringConstraints(min_length=8, max_length=400)]
    stack_max: Annotated[int, Field(ge=1, le=9999)] = 1


# ---------- ABILITY ----------

AbilityKind = Literal["active", "passive", "channel", "toggle"]
AbilityShape = Literal["projectile", "self", "aura", "cone", "line", "point", "touch"]
AbilitySchool = Literal["physical", "elemental", "arcane", "nature", "shadow", "holy"]


class AbilityCost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mana: Annotated[int, Field(ge=0, le=9999)] = 0
    stamina: Annotated[int, Field(ge=0, le=9999)] = 0
    cooldown_sec: Annotated[float, Field(ge=0.0, le=600.0)] = 0.0


class AbilityEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    damage: Annotated[int, Field(ge=0, le=9999)] = 0
    damage_type: DamageType | None = None
    healing: Annotated[int, Field(ge=0, le=9999)] = 0
    radius_m: Annotated[float, Field(ge=0.0, le=100.0)] = 0.0
    duration_sec: Annotated[float, Field(ge=0.0, le=600.0)] = 0.0
    status_tags: list[Tag] = Field(default_factory=list, max_length=4)


class Ability(_Record):
    kind: AbilityKind
    school: AbilitySchool
    tier: Annotated[int, Field(ge=1, le=10)] = 1
    shape: AbilityShape
    cost: AbilityCost = Field(default_factory=AbilityCost)
    effect: AbilityEffect = Field(default_factory=AbilityEffect)
    icon_id: IdStr | None = None
    vfx_id: IdStr | None = None
    sfx_id: IdStr | None = None
    description: Annotated[str, StringConstraints(min_length=8, max_length=400)]


# ---------- NPC ----------

NpcRole = Literal["vendor", "questgiver", "enemy", "ally", "neutral", "boss"]


class NPC(_Record):
    role: NpcRole
    faction_id: IdStr | None = None
    biome: Tag | None = None
    level: Annotated[int, Field(ge=1, le=99)] = 1
    health: Annotated[int, Field(ge=1, le=99_999)] = 100
    abilities: list[IdStr] = Field(default_factory=list, max_length=8)
    dialogue_start: str | None = None
    description: Annotated[str, StringConstraints(min_length=8, max_length=400)]


# ---------- FACTION ----------


class Faction(_Record):
    ideology: Annotated[str, StringConstraints(min_length=4, max_length=64)]
    primary_color: HexColor
    secondary_color: HexColor
    territory: list[Tag] = Field(default_factory=list, max_length=8)
    allies: list[IdStr] = Field(default_factory=list, max_length=8)
    enemies: list[IdStr] = Field(default_factory=list, max_length=8)
    sigil_prompt: Annotated[str, StringConstraints(max_length=200)] = ""
    description: Annotated[str, StringConstraints(min_length=8, max_length=400)]


# ---------- LORE TERM ----------


class LoreTerm(_Record):
    canonical_spelling: Annotated[str, StringConstraints(min_length=2, max_length=64)]
    aliases: list[Annotated[str, StringConstraints(min_length=2, max_length=64)]] = Field(
        default_factory=list, max_length=8,
    )
    category: Literal["place", "person", "concept", "artifact", "event", "deity"]
    description: Annotated[str, StringConstraints(min_length=8, max_length=600)]
    source_doc: str | None = None


# ---------- registry ----------

RECORD_TYPES: dict[str, type[_Record]] = {
    "item": Item,
    "ability": Ability,
    "npc": NPC,
    "faction": Faction,
    "lore_term": LoreTerm,
}

# English plurals for filenames + folder names. Avoids "abilitys.jsonl".
_PLURALS = {
    "item": "items",
    "ability": "abilities",
    "npc": "npcs",
    "faction": "factions",
    "lore_term": "lore_terms",
}


def plural(record_type: str) -> str:
    return _PLURALS[record_type]


def get_model(record_type: str) -> type[_Record]:
    if record_type not in RECORD_TYPES:
        raise KeyError(f"unknown record_type {record_type!r}; expected one of {list(RECORD_TYPES)}")
    return RECORD_TYPES[record_type]


def all_record_types() -> list[str]:
    return list(RECORD_TYPES)


# IDs that pass ID_PATTERN regex but should never be allowed (collision with Godot keywords etc.)
RESERVED_IDS = frozenset({
    "node", "scene", "resource", "tres", "tscn", "extends", "var", "func",
    "class_name", "self", "true", "false", "null", "and", "or", "not",
    "if", "else", "elif", "while", "for", "in", "return", "break", "continue",
    "pass", "match", "signal", "static", "const", "enum", "export",
    "id", "name", "tags",  # collision with our own field names is OK at field level but not as id
})


def validate_id(value: str) -> bool:
    if not re.fullmatch(ID_PATTERN, value):
        return False
    if value in RESERVED_IDS:
        return False
    return True


if __name__ == "__main__":
    # smoke test
    import json

    item = Item(
        id="iron_sword",
        display_name="Iron Sword",
        category="weapon",
        rarity="common",
        damage_type="physical",
        localization_key="ITEM_IRON_SWORD",
        description="A simple iron blade. Reliable and balanced.",
        stats=ItemStats(damage=12, weight=3.5, durability=200, value_gold=50),
        icon_id="ico_sword_iron",
    )
    print(json.dumps(item.model_dump(), indent=2))
    print(f"\nschema:\n{json.dumps(Item.model_json_schema(), indent=2)[:400]}...")
