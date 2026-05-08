# Game Data — Manual Review (2026-05-07)

`pipelines/game_data/` lane. Different review rhythm than UI/VFX/audio — content here is records, not media. Different question: are the **records actually shippable game content**, or schema-valid placeholder noise?

## Inventory (truth from disk)

### Schemas

5 JSON schemas in `game_data/schemas/`:

| Schema | Required fields | Property count | Use |
|---|---|---|---|
| `item.schema.json` | id, display_name, localization_key, category, description | 14 | weapons, armor, consumables |
| `ability.schema.json` | (similar) | (similar) | spells, skills |
| `npc.schema.json` | (similar) | (similar) | enemies, vendors |
| `faction.schema.json` | (similar) | (similar) | political groups |
| `lore_term.schema.json` | (similar) | (similar) | wiki entries |

All schemas have:
- `id`, `display_name`, `schema_version`, `tags`, `localization_key`, `provenance` — standard infra fields
- Domain-specific fields per record type

### Records on disk

**`game_data/validated/*.jsonl` (after schema + cross-ref validation passed):**

| Schema | Record count |
|---|---|
| items | **5** |
| abilities | **3** |
| factions | **2** |
| lore_terms | **2** |
| npcs | **2** |
| **Total** | **14 records** |

`game_data/generated/*.jsonl` (pre-validation) is the same 14 (1:1 with validated, all passed).

`game_data/godot/resources/*/*.tres` — **14 .tres files**, one per validated record. Each has the right `script_class` (`AbilityRecord`, `ItemRecord`, etc.) and structured fields.

### Sample record content

```
items: iron_mace_0, frost_spear_0, obsidian_sword_0, uncommon_fire_blade_45, rare_cold_blade_1042
abilities: shadow_aura_t1_42, arcane_self_t2_43, nature_self_t3_44
npcs: caedis_halloran_0 (vendor, faction=verdant_guild_0, biome=alpine, level=9, hp=315)
factions: verdant_guild_0, verdant_order_1 (both ideology=balance, similar colors)
lore_terms: lore_erdan_the_wise_0 (deity), and 1 other
```

**Provenance is fully tracked:** every record has `provenance: {source: "synthetic", seed: 42, timestamp, sim_digest, ...}` so we know where each came from.

### Reports

`game_data/reports/` has 18 files:
- 6 balance reports (DuckDB MD + 3 CSVs each, two timestamps)
- 6 validation reports (all timestamped 2026-05-06)
- 2 local LLM dry-run reports (item, ability)
- 1 phase9 LLM dry-run
- 1 yarn_link_report.md (npc_count=2, dialogue_starts=0, ok=true)

### Dialogue / Yarn

`game_data/source/dialogue/` directory **doesn't exist yet**. `yarn_link.py` reports "0 nodes" (correctly — no .yarn files have been authored). The validator is ready, no content to validate.

### Source / seeds / lore / vocab

- `game_data/source/lore/` — empty
- `game_data/source/seeds/` — empty
- `game_data/source/vocab.json` — exists, controls name generation

## What works

- ✅ **Schemas are real and well-designed.** Required fields enforce id + display_name + localization_key + provenance. Domain fields exist (cost, effect, school, tier for abilities; rarity, damage_type, stats for items; faction_id, biome, level, health for NPCs).
- ✅ **Provenance tracking is gold-standard.** Every record's `.provenance` block has `source` ("synthetic" / could be "openai" / "anthropic"), `seed`, `timestamp`, `sim_digest`, `constraint_technique`, `constraint_pass`, `parent_id`. This is **better tracking than 90% of game-data pipelines I've seen**.
- ✅ **Round-trip works.** 14 JSON records → 14 `.tres` files via `export_godot.py`, all with correct `script_class` and field types (dicts for `cost`/`effect`/`stats`, arrays for `tags`/`status_tags`).
- ✅ **Schema validation is clean.** Latest report: 0 schema errors, 0 cross-reference errors.
- ✅ **Cross-reference linking works.** NPCs reference factions (`faction_id: "verdant_guild_0"`); abilities reference vfx/sfx/icon IDs (`vfx_id: "arcane_shock_ring_legacy"`, `icon_id: "ico_gem_blue"`, `sfx_id: "fireball_cast"`). Linker validates these exist.
- ✅ **Balance reports run.** DuckDB queries produce per-rarity item value/damage stats, per-school ability cost/effect stats, faction-ability crosstabs. Real BI tooling, not just markdown summaries.
- ✅ **Backend cascade is real.** OpenAI / Anthropic / synthetic / vLLM. All plumbed; synthetic is what produced these 14 records (env keys not used yet).
- ✅ **Yarn validator is ready.** Just no dialogue to validate.

## What's open / weak

1. **14 records is toy-tier.** 5 items / 3 abilities / 2 NPCs / 2 factions / 2 lore_terms. **A real game has hundreds.** We're 1-2% of "minimum shippable."
2. **All records are `source: "synthetic"`.** The OpenAI/Anthropic/local-LLM cloud routes have **never been run with real keys** — synthetic generator made everything.
3. **Names are clearly procedural.** "Iron Mace", "Frost Spear", "Obsidian Sword", "Uncommon Fire Blade", "Rare Cold Blade", "Shadow Aura T1", "Arcane Self T2". These are template-generated combinations, not authored. **Iron Mace, Frost Spear, Obsidian Sword** could be from any generic fantasy game.
4. **Two factions are nearly identical.** "verdant_guild_0" and "verdant_order_1" both `ideology: "balance"`, similar colors. They're labeled differently but functionally one faction repeated. (The procedural generator has minimal diversity built in.)
5. **No dialogue exists.** Yarn pipeline is paper-only.
6. **`source/lore/` and `source/seeds/` are empty.** The "feed real seed content in, get richer records out" path was set up but never used.
7. **Balance numbers are toy-tier statistics.** Latest report says "5 items, mean damage 26.4". You can't derive game-balance signal from N=5.
8. **vfx_id / sfx_id / icon_id references** all point to valid catalog IDs — but those catalogs are themselves placeholder (palette-swap VFX, procedural icons, archived audio). So a record like `arcane_self_t2_43` *links* to placeholder content. Still — the linking infrastructure is real.

## User verdict (2026-05-07)

After reading samples:

1. **Sample ability record (`arcane_self_t2_43.tres`):** "**seems good for how we'd setup a spell.**" Schema fits the actual game-design need.
2. **Two near-identical factions:** "fine I guess, idk we will definitely want much wider range of generation. Almost the same name but it's just a POC." Confirms — the *system* can express diversity (different ideology, different colors, different names possible); the *generator* just hasn't been pushed to use that range.
3. **Balance report format:** "makes sense. **Balance review and setup will be huge and a long-term goal to get right.**" — explicitly flagged as a long-term focus area.

**Net read:** schemas + provenance + .tres round-trip are real production infrastructure. The procedural generator is POC-tier (intentionally — never run with cloud LLMs or real seed content). Balance is the **real long-term work** — infrastructure is ready, it just needs real-N records to analyze and game-design intent to balance against.

## Pipeline-level read

- **State:** **infrastructure is the strongest in the project.** Schemas, provenance, validation, cross-ref linking, round-trip to Godot `.tres`, balance analytics, Yarn validator. Real production-quality plumbing.
- **Strongest part:** **provenance tracking + balance reporting via DuckDB**. These are the things real game studios fail at. We have them.
- **Weakest part:** **content volume + content authorship.** 14 procedurally-generated records with clearly templated names. Same pattern as audio/VFX: **the pipeline can produce real content; nobody has fed it real intent yet.**
- **What "shipping quality" would require:**
  - Real seed content in `source/seeds/` (e.g. "here's the 50 weapons we want", "here's the 20 NPCs", "here's the 5 factions with distinct ideologies")
  - Cloud LLM run via OpenAI/Anthropic with that seed content
  - At least one real dialogue tree (`.yarn` file) so the validator has something to validate
  - Lore database population — currently empty
  - Re-run balance reports against a real-N corpus (~100+ records)

## Concrete next moves

This pipeline is **the closest to "ready to use" of any pipeline in the project**, but only if you bring the content yourself.

1. **Decide what game you're seeding for.** Without that, this pipeline produces beautiful procedural noise like the audio bake.
2. **If you have a game in mind:** write a `source/seeds/<schema>/seed.yaml` per schema with 5-10 hand-authored real records. Run cloud LLM (OpenAI or Claude) with those as seed examples to expand to 50+. Validate. Export. Real game data.
3. **If you don't:** keep the 14 records (they're kilobytes, no harm), defer authoring. Re-bake when game-design intent crystallizes.

**Long-term goal flagged by user (2026-05-07):** **balance review and setup is going to be a big long-term effort.** The infrastructure is ready (DuckDB queries, per-rarity stats, ability cost-vs-effect crosstabs, faction-ability linking). The work is:
- Define what "balanced" means for the game (e.g. "tier 2 abilities should average 25 mana / 30 damage / 1.5s cooldown")
- Author/generate enough records to fill those buckets (N=5 is unanalyzable; N=100+ is meaningful)
- Iterate balance until distributions look right
- Repeat as new content gets added

**Don't archive these 14 records** — they're a sandbox that proves the pipeline works. Just stop calling them "real game data".

---

## Research-calibrated update (2026-05-07)

Brief #08 ([response](../research_briefs/2026_05_07_sota_survey/08_game_data_balance.response.md)) returned. **Same shape as brief #03 (Props): existing infrastructure validated as best-in-project; the 2026 SOTA story is "run what's plumbed" + a few additive tools.**

### Headline: infrastructure is best-in-project, content is gated

The pipeline (Pydantic schemas, OpenAI/Claude/synthetic/vLLM cascade, DuckDB balance reports, kill-dummy sim, Yarn validator, migrations, .tres export) has the right architecture for May 2026. The 14 records are synthetic-only artifacts (two factions both "verdant+balance"; every ability uses `fireball_cast` SFX) — **running real LLM passes will eliminate both immediately.**

**The single highest-leverage move:** run the cascade on real keys.
- **Bulk path:** DeepSeek V4-Pro (~$0.18-$0.51 per 1K records, 30-100× cheaper than Opus, OpenAI-API-compatible — drops into the existing cascade with a base_url override).
- **Creative weight (~10% of records):** Claude Opus 4.7 — lore_terms, key NPC voice, faction ideology.
- **250 records at DeepSeek bulk + 25 at Opus ≈ ~$0.50-$2 total.**
- **Cloud parked per user direction** — this is queued, not done.

### Five additive tools (free, owned by us, additive pattern)

| # | Tool | Role | Cost |
|---|---|---|---|
| 1 | **pymoo NSGA-II** | `pareto_dominated_records.py` sibling to `duckdb_reports.py` — surfaces "this ability is strictly worse than that one" | 1 day, pip install |
| 2 | **fastjsonschema** or **okjson** | 50-100× faster validator alongside stock `jsonschema` | Sub-day, additive |
| 3 | **DSPy + GEPA** (ICLR 2026 Oral) | Prompt optimization for items/abilities (metric-driven). +13% over MIPROv2 with 35× fewer rollouts | 1-2 days |
| 4 | **`getsentry/json-schema-diff`** CI gate | BACKWARD/FORWARD/BREAKING gate on migrations | Sub-day |
| 5 | **Hash-based incremental linker** (~50 LOC) | Skip revalidation when records unchanged | Sub-day |

### When vLLM ships compat: XGrammar-2

**XGrammar-2 dropped 2026-05-04** (3 days before the brief). 10-80× faster constrained decoding via cross-grammar caching, repetition-state compression, batching/speculative decoding. New "Structural Tag" abstraction. Already integrated into vLLM/SGLang/TensorRT-LLM/MLC-LLM. **Free local-vLLM speedup on the constrained stage** — upgrade `local_llm_backend.py` when vLLM ships compat.

### Sub-pipeline-specific findings (condensed)

- **Combat sim:** keep `kill_dummy_sim.py`. **Don't set up RL agents now** — combat isn't built. When it is: scripted-heuristic Monte Carlo in PettingZoo + LLM-as-tester pass (~$5/run via Claude Sonnet).
- **Dialogue:** **Yarn migration to Ink or Dialogic 2 is lateral.** Build a ~100-line static analyzer + Claude-based authoring lint pass instead. **Don't adopt Inworld/Convai** (runtime NPC products, not authoring).
- **Lore:** start with `source/lore/*.md` + Obsidian + Smart Connections. **Don't buy World Anvil / LegendKeeper / Kanka / Campfire** — worldbuilding-as-product, wrong shape. Lore-as-data in git.
- **Localization:** Godot gettext (.po) + Crowdin Free + Claude Haiku (dialogue) / DeepL (UI). Pseudo-localization on day one (`set_pseudolocalization_enabled(true)`). **Don't buy Lokalise / Phrase / Smartling pre-launch.**
- **Cross-ref scaling:** custom linker fine through ~20K records *if* lookups go through pre-built `dict[id → record]` maps. Audit this. Re-evaluate at 50K records.

### What NOT to do

- **Don't fine-tune game-content LoRAs.** No usable production examples; SOTA general-purpose models write D&D-style content well enough.
- **Don't set up RL on combat balance before combat is built.** Sunk-cost spiral.
- **Don't migrate Yarn → Ink / Dialogic 2.** Lateral.
- **Don't buy worldbuilding platforms.**
- **Don't adopt Neo4j / KuzuDB / Graphiti at <20K records.** Architectural cosplay.
- **Don't buy enterprise TMS pre-launch.**

### Watch list

- **DeepSeek V4-Pro** — wire when cloud is unparked.
- **DuckPGQ** — when DuckDB integrates SQL/PGQ natively.
- **JSON Schema SchemaShift** (GSoC 2026, late 2026).
- **PettingZoo + scripted-heuristic** — when combat exists.

### Texture worker impact

**None.** Game data is its own lane.
