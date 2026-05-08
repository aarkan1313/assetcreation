# Research Brief — Game Data / Balance Pipeline (2026 SOTA)

## Goal

Identify 2026-current SOTA tools for **game-data record generation + balance analysis**. Current pipeline has best-in-project infrastructure (provenance, validators, DuckDB balance reports, Yarn dialogue link checking) but only 14 toy records and no real balance work yet.

## Hardware target

- RTX 5090 Laptop (24 GB VRAM, Blackwell sm_120, CUDA 12.8+ / torch >=2.7)
- Windows 11; Python 3.11/3.12 venvs preferred
- Cloud LLM routes preferred for record generation (OpenAI, Anthropic — already plumbed)
- Local vLLM also plumbed

## Context

The project has a complete game-data pipeline with the best infrastructure in the project:

**5 schemas:** ability, faction, item, lore_term, npc. Required fields enforce id + display_name + localization_key + provenance.

**Provenance tracking:** every record has `provenance: {source, model, seed, timestamp, target_file_sha256, constraint_technique, constraint_pass, sim_digest, parent_id}`. Better than 90% of game data pipelines.

**Backend cascade for generation** (`generate_records.py`): OpenAI → Anthropic → synthetic → local vLLM (xgrammar-constrained). All plumbed; only synthetic has been used.

**Validation chain:** `validate_records.py` (schema + cross-ref) → `roundtrip_test.py` (.tres ↔ JSON, 14/14 passing).

**Cross-reference linking:** abilities reference vfx_id / sfx_id / icon_id; NPCs reference faction_id / biome / dialogue_start. Linker validates.

**Balance reports** (`pipelines/game_data/balance/duckdb_reports.py`): per-rarity item value/damage stats, per-school ability cost/effect stats, faction-ability crosstabs. **Real BI tooling on top of game data**, not just markdown summaries.

**Yarn validator** (`yarn_link.py`): walks `[[choice|target]]` + `<<jump target>>` references. Ready when first .yarn file lands.

**Current state:** **14 toy records** (5 items + 3 abilities + 2 npcs + 2 factions + 2 lore_terms). All `source: "synthetic"`. Cloud LLM routes never run with real keys. Two factions are functionally identical (both "verdant", both "balance" ideology). Names are clearly templated ("Iron Mace", "Frost Spear", "Shadow Aura T1").

**User flagged this as a long-term focus area:** "Balance review and setup will be huge and a long-term goal to get right."

## Specific questions

1. **2026 SOTA for game-data record generation.** We have OpenAI / Anthropic / vLLM-with-xgrammar plumbed. Is there a 2026 advance — better LLM for game content (DeepSeek? Llama 4? a fine-tuned game-content model?), better constraint techniques (newer than xgrammar?), better seed-content workflow (give the LLM 5 hand-authored examples → expand to 50)?

2. **ML-driven game balance.** Our DuckDB reports are conventional BI. Is there a 2026 tool for **automated balance analysis** — given a corpus of ability/item/npc records, find balance problems automatically? E.g., "your tier 3 fire abilities have 2× the average cost-to-effect ratio of your tier 3 ice abilities; either overpriced fire or underpriced ice." Game-balance-specific ML?

3. **Combat simulation tools.** Our `pipelines/game_data/sim/kill_dummy_sim.py` exists (a dummy combat simulator for ability balance testing). Is there a 2026 standard for **agent-based combat simulation** at the game-data design stage? RL-driven, "play out N battles with this ability set, find dominant strategies / unwinnable matchups"?

4. **Dialogue tooling beyond Yarn.** Yarn (Yarn Spinner) is what we plumbed for. Is there a 2026 standard that's better for game dialogue — specifically: structure validation + branching coverage + LLM-assisted authoring? Ink, Twine, Articy, something new?

5. **Lore database tools.** `source/lore/` is empty. Is there a 2026 game-lore-specific tool for building canonical world-bible databases — entity relationships, timeline coherence, contradictions detection, vector-search across lore? Or do people just use Notion / Obsidian and import?

6. **Localization + i18n.** Every record has `localization_key`. We don't have a localization workflow. What's the 2026 standard for game localization — gettext-based, custom JSON pipelines, ML-translation-augmented authoring?

7. **Schema migration tools.** We have `migrate_records.py` + `migrations/` directory. Is the manual schema migration approach still 2026-current, or has there been progress in **automated schema-evolution + record-migration** tooling for game data?

8. **Cross-reference integrity at scale.** With 14 records, our linker is fast. At 500+ records, linking gets expensive. What's 2026 best practice for fast cross-ref validation at scale — DuckDB graph queries, dedicated tools, etc.?

## Format of response

Per question:
1. Top 2-3 tool/approach recommendations with one-paragraph why
2. Cost & maturity (cloud LLM costs at production scale; tool maintenance state)
3. License + cost notes
4. Maturity check
5. **Honest comparison** — does the new tool actually beat what we have (DuckDB + Yarn + LLM-cascade), or is it lateral?

## Out of scope

- Game design itself (we're not asking what makes games balanced)
- Specific games' balance (no comparing our items to D&D 5e or WoW)
- General-purpose data tools (we want game-data-specific)

## After response returns

Update `docs/pipeline_reviews/04_game_data.md` and `pipelines/game_data/README.md`. The user wants to:
- Plan the long-term balance-review effort
- Identify what tooling would unlock real-N record generation (50+ items, 30+ abilities, etc.)
- Decide cloud vs local LLM for generation (cost + quality tradeoff)
