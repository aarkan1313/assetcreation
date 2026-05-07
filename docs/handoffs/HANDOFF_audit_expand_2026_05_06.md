# Handoff - audit/expand pass for Props v2 + Game Data v1.5 (AB1, 2026-05-06)

Scope: push `../../pipelines/props/` and `../../pipelines/game_data/` toward the same depth standard as the character pipeline and world-gen. This pass included a read-only truth audit, then CPU-safe expansion work. No GPU model was loaded and no paid cloud endpoint was called.

Primary audit doc: [`../../_archive/audits_2026_05_06/AUDIT_props_gamedata_2026_05_06.md`](../../_archive/audits_2026_05_06/AUDIT_props_gamedata_2026_05_06.md) (archived)

---

## Props Pipeline

### Built

- `../../pipelines/props/pbr_material_bind.py`
  - CPU-only AAA-PBR material binding pass.
  - Walks `../../world/props/library/*/prop.json`.
  - Uses each prop's `material_slots` to bind existing texture sets from `../../world/textures/library`.
  - Writes `prop.json.pbr_material_bindings` and `../../world/props/kits/first_party_proc/pbr_bind_report.json`.
  - Default bindings include rock/stone -> `biome_lava_field`, mushroom_cap -> `biome_swamp`, mushroom_stem -> `biome_grassland`, wood/bark -> `forest_floor_oak_bark`, bone -> `biome_tundra`, metal -> `biome_charred_wasteland`, glass -> `biome_mana_crystal`.

- `../../pipelines/props/export_godot.py` update
  - Added `--all` compatibility.
  - Exports shared PBR material resources under `../../world/props/godot/_materials/<texture_set>/<texture_set>.tres`.
  - Copies referenced texture maps next to those materials.
  - Writes `../../world/props/godot/_shared/PropMaterialBinder.gd`.
  - Adds binder metadata to prop `.tscn` files so imported GLB surfaces can be overridden by the bound shared materials.

- `../../pipelines/props/trellis2_route.py`
  - Build-only local image-to-3D adapter.
  - CPU dry-run is the default; CUDA model path requires `--device cuda --run-model`.
  - Runtime command is supplied by `TRELLIS2_PROP_CMD` with placeholders `{image}`, `{out_glb}`, `{seed}`, `{target_tris}`.
  - Dry-run writes a `prop_asset.v1`-shaped manifest under `../../world/props/ai_routes/trellis2/<id>/`.

- `../../pipelines/props/meshy_route.py`
  - Meshy hero-prop adapter mirroring the procedural output shape.
  - Dry-run writes a `prop_asset.v1`-shaped manifest under `../../world/props/ai_routes/meshy/<id>/`.
  - Paid path refuses to run unless `MESHY_AUTH_FOR_THIS_BATCH=YES` is set for the current batch.

- `../../pipelines/props/README.md` and `../../pipelines/props/BLOCKERS_AI_ROUTE.md`
  - Added flip-on recipes for Trellis2 and Meshy.
  - Documented dry-run probes and shared postprocess chain: LOD -> collision -> billboard -> PBR bind -> Godot export -> validation.

### Tested

```powershell
python pipelines\props\pbr_material_bind.py --all
```

Result: `24/24` mesh props bound; report written to `../../world/props/kits/first_party_proc/pbr_bind_report.json`.

```powershell
python pipelines\props\export_godot.py --all
```

Result: `24` prop scenes exported, `63` LOD nodes, `6` collision-enabled props, shared `_materials/*` resources emitted. Spot check: `../../world/props/godot/rock_small_a01/rock_small_a01.tscn` references `PropMaterialBinder.gd` and `biome_lava_field.tres`.

```powershell
python pipelines\props\trellis2_route.py world\props\library\rock_small_a01\thumbnail.png --id trellis2_rock_small_probe --device cpu --dry-run
```

Result: dry-run manifest written under `../../world/props/ai_routes/trellis2/trellis2_rock_small_probe/`; no model import/load.

```powershell
python pipelines\props\meshy_route.py world\props\library\rock_small_a01\thumbnail.png --id meshy_rock_small_probe --dry-run
```

Result: dry-run manifest written under `../../world/props/ai_routes/meshy/meshy_rock_small_probe/`; no API call.

```powershell
python pipelines\props\validate_props.py
```

Result: `50/50 ok` across `../../world/props/library/*` (24 mesh props + 26 decal records).

### Stubbed

- Trellis2 route has the prop output contract, CLI, manifest schema, and command plumbing. It does not contain a hard-coded Trellis2 invocation because the local checkout's runnable entrypoint still needs to be selected when the GPU is free.
- Meshy route has the cloud gate and output contract. It does not spend credits or download a real GLB until the user authorizes a specific batch.
- PBR binding uses shared Godot `StandardMaterial3D` resources. It does not rewrite GLB materials or UVs. That is intentionally lower-risk than rebaking every source GLB during this pass.

### Blocked

- Real hero-prop quality remains blocked on either Meshy spend authorization or a GPU window for Trellis2.
- Scene-level scatter still needs the `stage_biome_scatter.py` v3 pickup so biome scenes instantiate prop GLBs instead of placeholder primitives. That file is outside this lane's ownership.

---

## Game Data Pipeline

### Built

- `../../pipelines/game_data/balance/duckdb_reports.py`
  - CPU-only DuckDB report generator.
  - Writes Markdown plus CSV slices under `../../game_data/reports/`.
  - Current slices: item value-vs-rarity, ability cost-vs-effect, faction ability crosstab.

- `../../pipelines/game_data/yarn_link.py`
  - CPU-only Yarn Spinner reference checker.
  - Parses `title:` nodes, `[[choice|target]]`, and `<<jump target>>`.
  - Checks `NPC.dialogue_start`, missing targets, and unreachable nodes.
  - Handles the current no-dialogue-source state as a warning, not a failure.

- `../../pipelines/game_data/local_llm_backend.py`
  - Build-only local constrained-generation backend.
  - CPU mode builds prompts, loads schema constraints, and validates parser shape with a deterministic sample.
  - CUDA path imports `outlines` only after `--device cuda --run-model`.

- `../../pipelines/game_data/README.md`
  - Added DuckDB, Yarn, and local-LLM recipes.
  - Clarified that synthetic content is demo-only and real TLTE seed content remains the content gap.

### Tested

```powershell
python pipelines\game_data\balance\duckdb_reports.py
```

Result: `../../game_data/reports/balance_duckdb_20260506_203714.md` plus three CSVs; rows: `items=5`, `abilities=3`, `faction_links=4`.

```powershell
python pipelines\game_data\yarn_link.py
```

Result: `../../game_data/reports/yarn_link_report.md`; `nodes=0`, `starts=0`, `missing=0`, with warning that `../../game_data/source/dialogue/` does not exist yet.

```powershell
python pipelines\game_data\local_llm_backend.py item --device cpu --max-records 1 --seed 77
python pipelines\game_data\local_llm_backend.py ability --device cpu --max-records 1 --seed 78
```

Result: dry-run reports in `../../game_data/reports/local_llm_backend_dryrun_item.json` and `../../game_data/reports/local_llm_backend_dryrun_ability.json`; `parser_ok=true`; no model import/load.

```powershell
python pipelines\game_data\validate_records.py --no-promote
python pipelines\game_data\roundtrip_test.py
```

Result: schema/link validation clean; `.tres` round-trip `14/14 passed`.

### Stubbed

- Local LLM generation path is adapter-complete but not model-complete. It needs a selected local model and `outlines` environment when GPU is free.
- Yarn validation has no real `.yarn` sources to walk yet. The tool is ready for the first dialogue file.
- C# Resource codegen was skipped. In-scope `project.godot` files under `D:\assets` did not contain `[dotnet]`, and the active project at `C:\Users\josep\test\new-game-project` was not touched per instruction.

### Blocked

- Real TLTE seed records are still the main content blocker. The schema/sim/reporting/export path is ready, but the current validated records are still synthetic demo vocabulary.
- Live cloud LLM calls were not run in this pass. Existing OpenAI/Claude paths remain env-gated.

---

## Cross-Pipeline / Meta

### Built

- `../../pipelines/_meta/link_validator.py`
  - Now loads prop IDs from `../../world/props/library/*/prop.json`.
  - Detects future `prop_id`, `*_prop_id`, and `prop_ids` references recursively in game_data records.
  - Fixed current Game Data reference counting for `npc.abilities[]` and `faction.allies[]` / `faction.enemies[]` while retaining legacy field names.

### Tested

```powershell
$env:PYTHONIOENCODING='utf-8'; python pipelines\_meta\link_validator.py
```

Result: `MISSING: none`, `assets prop: 50`, `references ability: 4`, `references prop: 0`.

```powershell
python -m py_compile pipelines\props\pbr_material_bind.py pipelines\props\export_godot.py pipelines\props\trellis2_route.py pipelines\props\meshy_route.py pipelines\_meta\link_validator.py pipelines\game_data\balance\duckdb_reports.py pipelines\game_data\yarn_link.py pipelines\game_data\local_llm_backend.py
```

Result: compile pass.

---

## Quality-Followup State

| Pipeline | Closed this pass | Still shallow vs character pipeline |
|---|---|---|
| Props | AAA-PBR material binding; Meshy route adapter; Trellis2 route adapter; prop-aware link validator coverage | No real hero-prop GLBs from Meshy/Trellis2 yet; procedural silhouettes remain lower-fidelity than character Meshy assets; world-scene scatter still uses placeholder primitives until `stage_biome_scatter.py` pickup lands |
| Game Data | DuckDB reporting; Yarn link validation; local-LLM constrained-gen adapter; current-field link counting fixed | Content is still synthetic; no TLTE canon/RAG seed; no live local-LLM or cloud-LLM content batch run; no real dialogue graph yet |

---

## GPU-Bound Ready Commands

Run only once the 5090 is free.

### Trellis2 Props

```powershell
$env:TRELLIS2_PROP_CMD = '<local Trellis2 command with {image} {out_glb} {seed} {target_tris}>'
python pipelines\props\trellis2_route.py world\props\input_images\altar.png --id altar_trellis2 --device cuda --run-model --publish
python pipelines\props\lod_chain.py altar_trellis2
python pipelines\props\collision_decompose.py altar_trellis2
python pipelines\props\billboard_bake.py altar_trellis2 --single
python pipelines\props\pbr_material_bind.py altar_trellis2
python pipelines\props\export_godot.py --id altar_trellis2
python pipelines\props\validate_props.py
```

Expected output: `../../world/props/library/altar_trellis2/model_lod0.glb`, `prop.json`, generated LODs/collision/billboard, and a Godot scene under `../../world/props/godot/altar_trellis2/`.

### Local LLM Game Data

```powershell
python pipelines\game_data\local_llm_backend.py item --device cuda --run-model --max-records 5 --out game_data\generated\items.local_llm.jsonl
python pipelines\game_data\validate_records.py
python pipelines\game_data\balance\duckdb_reports.py
python pipelines\game_data\export_godot.py
python pipelines\game_data\roundtrip_test.py
```

Expected output: model-generated JSONL candidates, validation report, updated DuckDB report, `.tres` resources, and `roundtrip 14/14` or higher depending on promoted record count.

---

## Cloud-Bound Ready Commands

Run only after explicit user authorization for the batch.

### Meshy Props

```powershell
$env:MESHY_AUTH_FOR_THIS_BATCH = 'YES'
python pipelines\props\meshy_route.py world\props\input_images\altar.png --id altar_meshy --publish --texture-prompt "weathered basalt altar, moss, engraved runes"
python pipelines\props\lod_chain.py altar_meshy
python pipelines\props\collision_decompose.py altar_meshy
python pipelines\props\billboard_bake.py altar_meshy --single
python pipelines\props\pbr_material_bind.py altar_meshy
python pipelines\props\export_godot.py --id altar_meshy
python pipelines\props\validate_props.py
```

Expected output: `../../world/props/library/altar_meshy/model_lod0.glb`, postprocessed LOD/collision/billboard/PBR files, and a Godot scene. Stop before the first command if the image batch or credit budget is unclear.

---

## Next Moves

1. Produce 3-5 real hero props through Meshy or Trellis2, then run the same visual review rigor used on character assets: silhouette, texture fidelity, LOD transitions, collision, Godot viewport check.
2. Modify `stage_biome_scatter.py` to consume `prop_pool` and emit per-prop MultiMesh instances from the real prop library.
3. Replace demo Game Data with a real TLTE seed pack: 30 items, 15 abilities, 8 NPCs, 4 factions, dialogue starts, and matching UI/VFX/audio references.
4. Run DuckDB reports and kill-dummy sims on that real pack, then decide whether GDScript `.tres` remains enough or C# Resource codegen is warranted.
