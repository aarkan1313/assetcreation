# Handoff — game_data pipeline v1.5 (2026-05-06)

Built per `../../research/F2_game_data_balance_sim.md` on top of `HANDOFF_game_data_2026_05_06.md`.

## Built

- `../../pipelines/game_data/balance/targets.toml` — human-authored balance target file: rarity histogram, weapon buckets, ability tier buckets, school floors, and sim gates.
- `../../pipelines/game_data/balance/schema.py` — Pydantic `BalanceTargets` parser with histogram completeness, monotonic weapon/ability range checks, per-slot bounds lookup, and target SHA helper.
- `../../pipelines/game_data/balance/lint.py` — CLI target linter that prints target SHA plus current accepted weapon/ability range deltas.
- `../../pipelines/game_data/balance/narrow_schema.py` — JSON Schema narrowing helpers: inline local `$ref`s, set per-slot consts, apply numeric min/max bounds, and force `additionalProperties: false` for strict provider modes.
- `../../pipelines/game_data/sim/kill_dummy.py` — deterministic 60 Hz / 30 s TrainingDummy sim with armor + 8 resists. Rejects `dummy_survived`, `ttk_too_low`, `no_damage`, and `player_died`.
- `../../pipelines/game_data/constrained_generate.py` — v1.5 orchestrator: target slot plan, schema narrowing, provider call or synthetic candidate, asset-ID resolver, sim gate, 3x oversample fallback, and critique/revise only when first-pass acceptance is below 60%.
- `../../pipelines/game_data/generate_records.py` updates:
  - `--backend claude` via Anthropic Messages tool-use `input_schema`.
  - `--backend auto` falls back `openai -> claude -> synthetic`.
  - `--target-balance [targets.toml]` delegates to the constrained orchestrator.
  - synthetic NPC generation now prefers freshly generated faction/ability pools before validated pools.
- `../../pipelines/game_data/schemas.py` provenance extension: `target_file_sha256`, `constraint_technique`, `constraint_pass`, `sim_digest`, `parent_id`.
- `../../pipelines/game_data/dump_schemas.py` — writes all five JSON Schema files under `../../game_data/schemas/`.
- `../../pipelines/game_data/migrations/` + `migrate_records.py` — sequential migration runner; first migration backfills v1.5 provenance keys.
- `../../pipelines/game_data/export_godot.py` — now prunes stale `.tres` files per record type during export, so `../../game_data/godot/resources/` reflects the current validated set exactly.

## Regenerated Outputs

- `../../game_data/generated/*.jsonl`
- `../../game_data/validated/*.jsonl`
- `../../game_data/schemas/{item,ability,npc,faction,lore_term}.schema.json`
- `../../game_data/godot/scripts/*.gd`
- `../../game_data/godot/resources/*/*.tres`

Current demo shape remains 14 records:

```text
items.jsonl       5
abilities.jsonl   3
factions.jsonl    2
npcs.jsonl        2
lore_terms.jsonl  2
```

The regenerated item/ability records now use real existing UI/VFX/audio IDs, so cross-pipeline link validation reports zero missing references.

## Tested

```powershell
python -m py_compile pipelines/game_data/schemas.py pipelines/game_data/generate_records.py pipelines/game_data/constrained_generate.py pipelines/game_data/export_godot.py pipelines/game_data/dump_schemas.py pipelines/game_data/migrate_records.py pipelines/game_data/balance/schema.py pipelines/game_data/balance/lint.py pipelines/game_data/balance/narrow_schema.py pipelines/game_data/sim/kill_dummy.py pipelines/game_data/migrations/001_add_v15_provenance_fields.py
python pipelines/game_data/balance/lint.py
python pipelines/game_data/generate_records.py item --count 5 --seed 42 --backend synthetic --target-balance
python pipelines/game_data/generate_records.py ability --count 3 --seed 42 --backend synthetic --target-balance
python pipelines/game_data/generate_records.py faction --count 2 --seed 42 --backend synthetic
python pipelines/game_data/generate_records.py npc --count 2 --seed 42 --backend synthetic
python pipelines/game_data/generate_records.py lore_term --count 2 --seed 42 --backend synthetic
python pipelines/game_data/validate_records.py
python pipelines/game_data/dump_schemas.py
python pipelines/game_data/migrate_records.py --dir game_data/validated
python pipelines/game_data/export_godot.py
python pipelines/game_data/roundtrip_test.py
$env:PYTHONIOENCODING='utf-8'; python pipelines/_meta/link_validator.py
python pipelines/game_data/sim/kill_dummy.py item game_data/validated/items.jsonl
python pipelines/game_data/sim/kill_dummy.py ability game_data/validated/abilities.jsonl
```

Results:

```text
[validate_records] schema_errors=0 link_errors=0
[export_godot] wrote 14 .tres files
[roundtrip] 14/14 passed
game_data/godot/resources/*.tres count: 14
link_validator: MISSING none, OK
kill_dummy items: 5/5 pass
kill_dummy abilities: 3/3 pass
```

Auto fallback was checked with both cloud env vars cleared:

```powershell
$env:OPENAI_API_KEY=''; $env:ANTHROPIC_API_KEY=''
python pipelines/game_data/generate_records.py item --count 1 --seed 5 --backend auto --target-balance --out game_data/generated/_test_auto_fallback_items.jsonl
# backend=synthetic
```

The temporary `_test_*.jsonl` files were removed after smoke testing.

## Stubbed / Deferred

- Real TLTE seed content remains deferred. The v1.5 plumbing is ready, but user-authored TLTE systems/content should drive the real 30 items + 15 abilities + 8 NPCs.
- DuckDB balance reports and deeper provenance audit remain the full F2 follow-up item.
- C# Resource codegen remains deferred until TLTE confirms C# usage.
- Yarn Spinner dialogue validation and LlamaIndex lore extraction remain parked until dialogue/lore source files exist.

## Blocked

- Claude backend is implemented and import/env gated, but no live Anthropic call was run in this build because `ANTHROPIC_API_KEY` is planned rather than required. `--backend auto` falls through cleanly when it is missing.
- OpenAI strict cloud calls were not run during verification; synthetic constrained mode exercised the same schema narrowing, sim gate, asset resolver, provenance, and export path without network.
