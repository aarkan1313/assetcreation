# Game Data Pipeline

**Status:** ✅ Working v1.5 end-to-end (offline-first; cloud LLM optional via OPENAI_API_KEY or ANTHROPIC_API_KEY).

The "content compiler" prescribed by `research/F_game_data.md`:

```
Pydantic schemas (source of truth)
   ↓
generate_records.py  ─── synthetic backend (offline, deterministic)
   │                     OR openai/claude backend (structured outputs)
   │                     OR --target-balance constrained mode
   ▼
generated/<type>.jsonl
   ↓
validate_records.py  ─── schema check + cross-reference linker + balance report
   ▼
validated/<type>.jsonl   +   reports/validation_<ts>.md
   ↓
export_godot.py      ─── codegens GDScript Resource classes + one .tres per record
   ▼
godot/scripts/<type>_record.gd
godot/resources/<type>/<id>.tres
```

## Files

| File | Role |
|---|---|
| [schemas.py](schemas.py) | Pydantic v2 models for `Item`, `Ability`, `NPC`, `Faction`, `LoreTerm`. Single source of truth, including v1.5 provenance audit fields. |
| [generate_records.py](generate_records.py) | Candidate generator. Backends: synthetic (offline), openai, claude, and `--target-balance` constrained mode. |
| [constrained_generate.py](constrained_generate.py) | Balance-target orchestrator with narrowed JSON Schema, sim gate, oversample fallback, and gated critique/revise. |
| [balance/targets.toml](balance/targets.toml) | Human-authored target ranges for rarity histogram, weapon/ability bounds, school floors, and sim gates. |
| [balance/lint.py](balance/lint.py) | Validates the target file and prints current accepted range deltas. |
| [balance/duckdb_reports.py](balance/duckdb_reports.py) | DuckDB balance report: item value-vs-rarity, ability cost-vs-effect, and faction ability crosstab CSVs. |
| [sim/kill_dummy.py](sim/kill_dummy.py) | Deterministic 60 Hz / 30 s dummy combat sim for item and ability records. |
| [yarn_link.py](yarn_link.py) | Yarn Spinner node parser/link validator for `NPC.dialogue_start`. |
| [local_llm_backend.py](local_llm_backend.py) | Build-only local LLM constrained-gen adapter. CPU dry-run validates prompt/parser; CUDA model load is explicit. |
| [dump_schemas.py](dump_schemas.py) | Dumps JSON Schema files for all record types into `game_data/schemas/`. |
| [migrate_records.py](migrate_records.py) | Applies sequential JSONL migrations from `migrations/`. |
| [validate_records.py](validate_records.py) | Schema validation + cross-ref linker + balance report. Promotes valid records to `validated/`. |
| [export_godot.py](export_godot.py) | Emits GDScript Resource classes and `.tres` files for Godot 4.5, pruning stale resources during export. |
| [roundtrip_test.py](roundtrip_test.py) | Smoke test: jsonl → tres → parse-back-to-Pydantic; per-field equality. |

## Quickstart

```powershell
# 1. Generate (default: synthetic, deterministic)
python pipelines\game_data\generate_records.py item     --count 5 --seed 42 --target-balance
python pipelines\game_data\generate_records.py ability  --count 3 --seed 42 --target-balance
python pipelines\game_data\generate_records.py faction  --count 2 --seed 42
python pipelines\game_data\validate_records.py
python pipelines\game_data\generate_records.py npc      --count 2 --seed 42  # needs factions+abilities
python pipelines\game_data\generate_records.py lore_term --count 2 --seed 42

# 2. Validate + balance report (writes validated/*.jsonl + reports/validation_<ts>.md)
python pipelines\game_data\validate_records.py

# 3. Export to Godot
python pipelines\game_data\export_godot.py

# 4. Sanity check round-trip
python pipelines\game_data\roundtrip_test.py
```

Drop `D:\assets\game_data\godot\` into a Godot 4.5 project at `res://game_data/` and any record loads as a typed Resource:

```gdscript
var rec: ItemRecord = load("res://game_data/resources/items/iron_sword_0.tres")
print(rec.display_name, " dmg=", rec.stats.damage)
```

## Balance-Constrained Generation

```powershell
python pipelines\game_data\balance\lint.py
python pipelines\game_data\balance\duckdb_reports.py
python pipelines\game_data\generate_records.py item --count 10 --target-balance --backend auto
python pipelines\game_data\sim\kill_dummy.py item game_data\validated\items.jsonl
```

`--target-balance` plans rarity/tier slots from `balance/targets.toml`, narrows numeric JSON Schema bounds per slot, validates each candidate through `sim/kill_dummy.py`, oversamples up to 3x when needed, and uses a critique/revise pass only when first-pass acceptance falls below 60%.

## Cloud LLM generation

Set `OPENAI_API_KEY` + `pip install openai`, or `ANTHROPIC_API_KEY` + `pip install anthropic`. Then:

```powershell
python pipelines\game_data\generate_records.py item --count 25 --backend openai --model gpt-4o-mini --seed 7
python pipelines\game_data\generate_records.py ability --count 10 --backend claude --target-balance --seed 7
```

OpenAI uses `response_format=json_schema`; Claude uses Messages tool-use with an `input_schema`. We still re-validate through Pydantic and the deterministic sim before saving.

## Local LLM Backend

The offline LLM lane is wired but GPU-gated. CPU mode checks the prompt builder and structured parser without importing a model:

```powershell
python pipelines\game_data\local_llm_backend.py item --device cpu --max-records 1
python pipelines\game_data\local_llm_backend.py ability --device cpu --max-records 1
```

When the GPU is free and the local model is available:

```powershell
python pipelines\game_data\local_llm_backend.py item --device cuda --run-model --max-records 5 --out game_data\generated\items.local_llm.jsonl
python pipelines\game_data\validate_records.py
python pipelines\game_data\export_godot.py
```

The CUDA path imports `outlines` only after `--device cuda --run-model`, so dry-run use is safe during GPU contention.

## Dialogue / Yarn Link

Put `.yarn` files under `game_data/source/dialogue/`, then set `NPC.dialogue_start` to a Yarn `title:` node and run:

```powershell
python pipelines\game_data\yarn_link.py
```

The report catches missing NPC start nodes, missing option/jump targets, and unreachable nodes.

## Output contract

| Path | Contents |
|---|---|
| `D:\assets\game_data\schemas\` | JSON Schema dumps for editor tooling |
| `D:\assets\game_data\source\seeds\vocab.json` | regenerated each run; the synthetic vocab |
| `D:\assets\game_data\source\lore\` | (reserved) Markdown canon docs for future LlamaIndex extraction |
| `D:\assets\game_data\generated\<type>.jsonl` | candidate records, one per line |
| `D:\assets\game_data\validated\<type>.jsonl` | schema-clean records (the linker's `link_errors` are warnings, not promotion blockers — see report) |
| `D:\assets\game_data\reports\validation_<ts>.md` | latest validation + balance report |
| `D:\assets\game_data\reports\balance_duckdb_<ts>.md` | DuckDB balance slices plus CSVs for plotting |
| `D:\assets\game_data\reports\yarn_link_report.md` | Yarn node reachability/link report |
| `D:\assets\game_data\godot\scripts\<type>_record.gd` | GDScript Resource class |
| `D:\assets\game_data\godot\resources\<type>\<id>.tres` | one resource file per record |
| `D:\assets\game_data\godot\README.txt` | drop-in instructions for the Godot project |

## Validation rules

The link checker enforces:

- `npc.faction_id` must exist as a `faction.id` (or be null)
- `npc.abilities[]` must each exist as an `ability.id`
- `faction.allies[]` and `faction.enemies[]` must each exist as a `faction.id`
- a faction id cannot appear in both `allies` and `enemies` of the same faction
- duplicate `display_name` within a record type → flagged
- weapon `damage` and armor must fit the rarity stat budget (loose: common ≤60, legendary ≤260)
- ability `effect.damage` must be ≤ `tier × 25`
- damaging ability with zero mana cost AND zero cooldown → flagged

Schema fields are enforced at validation time via Pydantic constraints (id pattern, color hex, locale-key pattern, value ranges).

## Why GDScript .tres instead of CSV/JSON?

Per F_game_data and Godot 4.5 docs: Resources give us inspector editing, `[GlobalClass]` codegen-friendly typed access, ResourceLoader caching, and `.tres` is text-mergeable. JSONL stays as the manufacturing format; `.tres` is the shipping format.

A C# variant of `export_godot.py` is straightforward to add later if the project standardizes on Mono. Today's choice (GDScript) matches the existing `godot_pack/shaders/*.gdshader` convention.

## Known limits

- Synthetic backend is deterministic and intentionally generic — the goal is "validation-passing demo records", not "shipping content." Use real TLTE seed docs plus OpenAI/Claude/local-LLM constrained generation for content candidates, then revalidate.
- The `.tres` parser in `roundtrip_test.py` only handles literals we emit; it is not a general Godot parser.
- Lore document → structured extraction (LlamaIndex / RAG) is the next step but parked until a real lore corpus exists.
- Yarn link validation exists, but there are no source `.yarn` dialogue files yet; the current report is a structural smoke test.
- Real TLTE seed content is still deferred to user-authored system/content decisions; v1.5 ships the balance/sim plumbing and refreshed demo records.

## Roundtrip-tested

```
[roundtrip] 14/14 passed
```

5 items + 3 abilities + 2 factions + 2 NPCs + 2 lore terms generate, validate, export to .tres, and parse back to Pydantic with full per-field equality.
