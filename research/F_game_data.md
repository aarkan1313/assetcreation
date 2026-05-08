# Assignment F - Game Data / Lore Pipeline

Date: 2026-05-06  
Scope: structured game data for items, abilities, NPCs, factions, lore documents, dialogue hooks, schema validation, LLM-assisted generation, and Godot 4.5 / C# import.

## Executive Recommendation

Treat game data as a **content compiler**, not a folder of prompt-generated JSON. The best 2026 stack is:

1. **Schema spine:** Python [Pydantic v2](https://docs.pydantic.dev/dev/concepts/json_schema/) models as the source of truth, exporting JSON Schema 2020-12 for tooling and validation. This gives one typed model for validation, generation, tests, docs, and Godot export.
2. **Structured generation:** provider-native structured outputs first: [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs), [Claude Structured Outputs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs), and Gemini structured output where useful. Wrap those calls with [Instructor](https://github.com/567-labs/instructor) or PydanticAI when we want retry/validation/evals across providers.
3. **Validation and balance layer:** deterministic Python checks before any LLM judge: IDs, enums, references, duplicate names, stat budgets, rarity curves, unlock prerequisites, tag consistency, and localization keys. Use LLM review only after hard validation passes.
4. **Godot export:** generate typed Godot `Resource` classes and `.tres` resources, not just runtime-parsed JSON. Godot resources are built for data containers, inspector editing, automatic serialization, `.tres` version control, and C# `[GlobalClass]` / `[Export]` workflows ([Godot resources](https://docs.godotengine.org/en/4.5/getting_started/step_by_step/resources.html)).
5. **Lore/dialogue:** store canon in Markdown/YAML frontmatter plus structured extracted records. Use [Yarn Spinner for Godot](https://yarnspinner.dev/docs/godot/) for branch dialogue when the game needs dialogue scripting; use generated JSON/YAML for encyclopedic lore, items, factions, and ability data.

The starter kit should be: **Pydantic + JSON Schema + Instructor/PydanticAI + Godot Resource exporter + DuckDB/SQLite validation dashboard**. This is not glamorous, but it is the safest path to "generate 50 items with stats matching the design doc" without poisoning the game with plausible-looking bad data.

## Current Local State

`D:\assets\game_data\` is empty. The roadmap calls for JSON schemas for items/abilities/NPCs/factions, a validator, and a Godot `Resource` exporter. That is exactly the right first slice.

Recommended folder shape:

```text
game_data\
  schemas\                 # Pydantic source + exported JSON Schema
  source\
    lore\                  # markdown canon docs
    seeds\                 # name fragments, weapon types, tag vocab
  generated\
    items.jsonl
    abilities.jsonl
    npcs.jsonl
    factions.jsonl
  validated\
    items.jsonl
    abilities.jsonl
  reports\
    balance_items.html
    validation_errors.md
  godot\
    resources\
    scripts\
```

Each content record should include `id`, `display_name`, `category`, `tags`, `source`, `schema_version`, `provenance`, `balance_notes`, and `localization_key`. Generated content should never overwrite validated/shipping content directly.

## Tool Survey

| Tool / method | Role | License / interface | Why it matters | Caveat |
|---|---|---|---|---|
| [Pydantic v2](https://docs.pydantic.dev/dev/concepts/json_schema/) | Python schema and validation | MIT; Python | Best source-of-truth layer: typed models, validators, JSON Schema export | Need custom validators for design rules |
| [JSON Schema 2020-12](https://json-schema.org/specification) | Cross-tool schema standard | Open spec | Works with OpenAI/Claude/Gemini, editors, Ajv, docs, validators | Expresses structure better than game balance semantics |
| [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs) | AI data generation | API | Provider-enforced JSON Schema; good for item/NPC/faction batches | Schema validity is not design quality |
| [Claude Structured Outputs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) | AI data generation/review | API beta; Pydantic/Zod helper support | Strong for structured extraction from lore docs and editorial review | Beta headers/model availability need tracking |
| Gemini structured output | AI data generation | API | Good second provider for comparison and ensemble validation | Keep provider adapter replaceable |
| [Instructor](https://github.com/567-labs/instructor) | Multi-provider structured generation wrapper | MIT; Python | Pydantic-first, retries validation failures, simple provider switching | Another dependency; provider-native APIs still matter |
| [PydanticAI](https://github.com/pydantic/pydantic-ai) | Agent/evals framework | MIT; Python | Typed agents, tools, traces, evals; current 2026 project with fast releases | Heavier than needed for the first generator |
| [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output) | Agent wrapper | MIT; Python/JS | Useful if the pipeline later needs broad agent orchestration | Bigger framework surface than this task needs |
| [LlamaIndex structured extraction](https://docs.llamaindex.ai/en/stable/understanding/extraction/) | Lore doc extraction / RAG | MIT; Python | Good for "lore document to NPC/faction/item fields" | Overkill until there is a real lore corpus |
| [DuckDB](https://duckdb.org/docs/stable/clients/python/overview) | Balance analysis | MIT; Python/CLI | Reads JSON/CSV/Parquet directly; fast ad-hoc reports | Analysis tool, not canonical store |
| SQLite / SQLAlchemy | Local catalog DB | Public domain/MIT-style ecosystem | Durable index and references if JSONL grows large | Adds migrations; start with JSONL unless queries hurt |
| [Godot Resources](https://docs.godotengine.org/en/4.5/getting_started/step_by_step/resources.html) | Runtime/editor data | Engine feature | Typed data, inspector editing, `.tres` serialization, ResourceLoader/ResourceSaver | Need exporter scripts and generated classes |
| [Godot EditorImportPlugin](https://docs.godotengine.org/en/4.5/classes/class_editorimportplugin.html) | Import JSON/YAML as resources | Engine feature | Lets source data import as first-class resources in editor | More Godot-side tooling; Python exporter is simpler first |
| [Yarn Spinner for Godot](https://yarnspinner.dev/docs/godot/) | Branch dialogue | MIT ecosystem | Official Godot support, C# and GDScript, validation, localization | For dialogue, not general item/stat data |
| [GodotInk](https://store.godotengine.org/asset/paulloz/godot-ink/) | Ink narrative integration | MIT | Strong if narrative scripting is Ink-centric | More specialized than Yarn for this project |
| [Dialogic](https://github.com/dialogic-godot/dialogic) | Visual dialogue editor | MIT | Nice Godot-native UI for visual dialogue authoring | Less schema-first; not ideal as canonical data backbone |
| [names.io](https://github.com/Debdut/names.io) / [Syllabore](https://libraries.io/nuget/Syllabore) / [fantasyname](https://github.com/skeeto/fantasyname) | Name seeds | Apache-2.0 / MIT / Unlicense | Offline generation and large name pools | Check cultural fit; avoid random incoherent naming |

## What Is Actually SOTA In 2026

For structured game data, "SOTA" means **constrained generation plus deterministic validation**, not the largest model. OpenAI, Claude, Gemini, LangChain, Instructor, PydanticAI, and LlamaIndex all now support structured output workflows, but these only guarantee shape. They do not guarantee that an uncommon sword has the right DPS curve, that a faction's ideology is coherent, or that a quest prerequisite exists.

The production-grade pattern is:

1. define schema,
2. generate candidate rows,
3. validate hard constraints,
4. run balance/math reports,
5. run semantic/editorial checks,
6. promote accepted records,
7. export engine resources.

Use provider-native structured output where possible because constrained decoding reduces malformed JSON. Use Pydantic as the post-generation authority because Pydantic can enforce field constraints and model-level rules. Use LLM-as-reviewer only for soft quality: "is this faction too similar to another one?", "does this item description match the ice biome?", "does this NPC contradict the canon?"

For lore extraction, LlamaIndex-style structured extraction is useful once there are many Markdown documents. For now, a simpler pattern is enough: keep human-readable canon docs, then extract/update structured `Faction`, `NPC`, `Location`, `Term`, and `TimelineEvent` records from those docs using a Pydantic model.

For Godot, Resources are better than raw JSON at runtime. Godot docs explicitly position custom Resources as data containers with defined properties, inspector editing, and version-control-friendly `.tres` files. The pipeline should keep JSONL/YAML as source/manufacturing format and export `.tres` as the engine-facing format.

## Recommended Pipeline

### Stage 1: Define Schemas

Create Pydantic models:

- `Item`: weapon, armor, consumable, crafting material, quest item.
- `Ability`: active/passive, tags, costs, cooldown, scaling, VFX/audio links.
- `NPC`: identity, faction, role, biome, dialogue entry, relationship tags.
- `Faction`: ideology, territory, allies/enemies, palette/sigil/icon prompt.
- `LoreTerm`: glossary entry, canonical spelling, aliases, source docs.
- `EncounterTable`: biome, level range, weighted spawns, reward tags.

Generate JSON Schema from those models for LLM calls and editor validation. Add custom Pydantic validators for:

- stable IDs: lowercase snake/kebab only;
- no duplicate display names in category;
- rarity budget ranges;
- item stat budget;
- ability cooldown/cost/damage relationship;
- references exist;
- localization keys exist;
- tags come from controlled vocabularies.

### Stage 2: Generate Candidates

The LLM should generate **small batches**: 10-25 records at a time, not 500. Each run gets:

- design brief,
- schema,
- current accepted IDs/names,
- tag vocab,
- balance targets,
- examples of accepted records,
- explicit "do not modify accepted content" instruction.

Candidate output goes to `game_data/generated/*.jsonl`, not shipping content.

### Stage 3: Validate and Balance

Run deterministic validators first. Then use DuckDB to produce simple reports:

- item power by level/rarity/category;
- ability damage-per-second/cooldown/mana curves;
- faction coverage by biome;
- NPC role distribution;
- duplicate or near-duplicate names;
- missing VFX/audio/icon references.

Only then run an LLM judge for semantic review. The judge should return structured issues, not prose:

```json
{
  "record_id": "frostglass_dagger",
  "severity": "warning",
  "issue": "Description implies ice damage but damage_type is piercing only.",
  "suggested_fix": "Add secondary ice tag or revise description."
}
```

### Stage 4: Export to Godot

Generate:

- C# `Resource` classes using `[GlobalClass]` and `[Export]` fields for main content types.
- `.tres` files for accepted records.
- optional index resources like `ItemDatabase.tres`.
- CSV/translation key files for localization.
- a validation report Godot can show in-editor.

Keep the Python schema and generated C# in sync through codegen. Do not hand-edit generated C# unless it is moved into a stable runtime API layer.

### Stage 5: Dialogue and Lore

Use Markdown for canon and design notes. Use Yarn Spinner for playable branch dialogue. Connect records by IDs:

- `npc.dialogue_start_node`
- `faction.lore_terms`
- `ability.vfx_id`
- `ability.audio_cue`
- `item.icon_id`

Yarn/Ink dialogue files should reference structured IDs, and validators should verify those references.

## Test Plan

Run five initial tests:

1. **Generate 50 weapons:** 5 rarities, 10 weapon families. Pass if every item validates, power curve is monotonic enough, names are unique, and Godot exports load.
2. **Generate 30 abilities:** fire/ice/lightning/earth tags. Pass if costs/cooldowns/damage stay inside budget and VFX/audio references are either valid or explicitly TODO.
3. **Lore extraction:** write one Markdown faction brief, extract `Faction`, `NPC`, and `LoreTerm` records. Pass if fields are faithful to source and cite source file/section.
4. **Dialogue link test:** create 3 NPC records with Yarn start nodes. Pass if all nodes exist and missing nodes produce validator errors.
5. **Mutation test:** intentionally break references, stat budget, duplicate names, invalid tags, and localization keys. Pass if validator catches all failures before export.

Estimated setup:

- Pydantic schemas and first validator: 4-8 hours.
- Structured generation adapter: 3-6 hours.
- Balance reports: 4-8 hours.
- Godot C# Resource/codegen exporter: 6-12 hours.
- Lore extraction and dialogue link validation: 4-10 hours.

## Honest Tradeoffs

- JSON Schema is necessary but not sufficient. It catches malformed shape, not bad design.
- LLMs are good at breadth and naming; deterministic validators are better at truth.
- Godot Resources are better runtime data, but JSONL is better manufacturing data. Use both.
- Provider-native structured output is more reliable than prompt-only JSON, but refusals, max-token truncation, and semantic errors still require handling.
- Full RAG/lore graph tooling is premature until there is a real lore corpus.
- Seed-name libraries help, but pure random names can make a world feel incoherent. Prefer faction/biome-specific syllable templates plus curated exceptions.

## Starter Kit

Start with:

1. **Pydantic v2 models** for `Item`, `Ability`, `NPC`, `Faction`, and `LoreTerm`.
2. **Instructor or direct OpenAI/Claude structured outputs** for candidate generation into JSONL.
3. **Python validator + DuckDB reports** for schema, references, and balance.
4. **Godot Resource exporter** producing C# `[GlobalClass]` resource scripts and `.tres` content.

Add Yarn Spinner once NPC dialogue exists. Add LlamaIndex only when lore docs grow large enough that retrieval and structured extraction need indexing.

## Sources

- OpenAI Structured Outputs / Responses: https://platform.openai.com/docs/guides/structured-outputs, https://platform.openai.com/docs/api-reference/responses/retrieve
- Claude Structured Outputs: https://docs.claude.com/en/docs/build-with-claude/structured-outputs
- Pydantic / JSON Schema / Ajv: https://docs.pydantic.dev/dev/concepts/json_schema/, https://json-schema.org/specification, https://ajv.js.org/
- Instructor / PydanticAI / LangChain structured output: https://github.com/567-labs/instructor, https://github.com/pydantic/pydantic-ai, https://docs.langchain.com/oss/python/langchain/structured-output
- LlamaIndex structured extraction: https://docs.llamaindex.ai/en/stable/understanding/extraction/, https://docs.llamaindex.ai/en/stable/module_guides/querying/structured_outputs/
- Godot resources/import/export: https://docs.godotengine.org/en/4.5/getting_started/step_by_step/resources.html, https://docs.godotengine.org/en/4.5/classes/class_resourcesaver.html, https://docs.godotengine.org/en/4.5/classes/class_editorimportplugin.html
- Yarn Spinner / dialogue options: https://yarnspinner.dev/docs/godot/, https://github.com/YarnSpinnerTool/YarnSpinner-Godot, https://store.godotengine.org/asset/paulloz/godot-ink/, https://github.com/dialogic-godot/dialogic
- DuckDB / SQLAlchemy: https://duckdb.org/docs/stable/clients/python/overview, https://duckdb.org/docs/current/data/overview.html, https://www.sqlalchemy.org/
- Seed/name resources: https://github.com/Debdut/names.io, https://libraries.io/nuget/Syllabore, https://github.com/skeeto/fantasyname, https://www.behindthename.com/info/licensing
