# Audit — Post-Worldgen-Nuke Stocktake (2026-05-07)

Truth-from-disk audit. **Docs are not trusted** — every count and claim below
came from walking the file tree on 2026-05-07 PM, after the worldgen v1+v2 nuke.

## TL;DR

- **8 working asset pipelines** (characters, props, audio, ui, vfx, game_data, textures, dems-fetch). All ship real outputs. None are vapor.
- **Worldgen is gone.** Anything that "composed pipelines into a Godot scene" is gone with it. The 8 lanes produce assets but *nothing assembles them*.
- **Two duplicated layers** discovered: VFX exists at both `pipelines/vfx/` (3D bakers + canonical effect.json) and `art_lab/shaders/` (2D shader-evolve-and-promote workflow). They are different pipelines with the same goal — produce VFX. Worth deciding on one.
- **Texture quality is the open quality gap.** 10/24 graded sets are A, 11 are B, 3 are C; 7 sets have no QA at all. The `flux_seamless.py` "shift+heal" tiling repair exists but isn't on by default for biome textures.
- **Docs are still bad post-nuke.** PIPELINE_DIRECTORY/TOOLS_INDEX have 19 known-broken links to archived terrain scripts. The high-level docs got banners, but the inventory tables inside them are still worldgen-stained.
- **Leftover crumbs from the nuke:** `tests/worldgen_v2/` (dead tests), `pipelines/godot_export/stage_biome_*` (worldgen scene-composers), `godot_pack/terrain/` + `godot_pack/shaders/biome_*` (worldgen baked artifacts). All should follow the rest of v1/v2 into the archive.

## What's at the root

| Path | Status | Notes |
|---|---|---|
| `pipelines/` | ✅ live | 8 sub-pipelines (audio, game_data, godot_export, props, terrain, textures, ui, vfx, video) plus `_meta` |
| `world/` | ✅ live | Trimmed post-nuke. Holds 31 texture sets + 52 prop entries. `worlds/`, `regions/`, `maps/`, `terrain/`, `scenes/` archived. |
| `dems/` | ✅ live | 222 OpenTopo TIFFs / 8.1 GB. Relocated from `pipelines/terrain/source_dems/` 2026-05-07. |
| `audio/` | 🟡 emptied 2026-05-07 | Output archived to `_archive/audio_phase12_bake_2026_05_07/` (189 MB) after manual review found content was noise-tier. Pipeline retained. |
| `vfx/` | ✅ live | 46 effect.json entries across 6 categories (ambient/destruction/environment/projectiles/spells + 28 spells). |
| `ui/` | ✅ live | atlas.png + atlas.json + per-faction HUD previews + 9slice + 14 generated mockups. |
| `meshy/` | ✅ live | 33 character GLBs in `output/`. |
| `animators/` | ✅ live | 12 AI rigging/animation tools, each with own venv where applicable. ComfyUI + ComfyUI_HY3D + Trellis2 are the GPU lanes. |
| `art_lab/` | 🟡 **needs decision** | Houses `shaders/` (2D shader-evolve-promote workflow with 6 templates), `biomes/` (registry data + tools), `maps/generators/` (world-map generator), `props/` (procedural recipes), `tools/` (shader-batch tools). **`shaders/` overlaps with `pipelines/vfx/`** — see [VFX duplication](#vfx-duplication) below. |
| `game_data/` | ✅ live | Generated records, schemas, validated outputs, balance reports, source docs. |
| `godot_pack/` | 🟡 partial | Drop-in Godot resources: `materials/`, `props/`, `shaders/`, `terrain/`. Last two are worldgen leftovers (see [Crumbs](#leftover-crumbs)). |
| `images/` | ✅ live | Concept image stash. Includes `phase11_hero_obelisk_concept_2026_05_06.png`. |
| `research/` | ✅ live | 24 research reports A–K. |
| `tests/` | 🟡 stale | Only contents are `tests/worldgen_v2/` — left over from nuke. |
| `docs/` | 🟡 still drifting | post-nuke banners added but inventory tables still worldgen-stained. |
| `world3/` | 🟢 user-active | Fresh Godot project for new pipeline. *Not audited* per user. |
| `original_workflow_godot/` | ❓ unclear | Test Godot project from worldgen-debug session. References archived `worldgen2/`. |
| `godot llm ocr.md` | ❓ floating | Notes from the OCR-debug worldgen session. References archived `worldgen2/`. |
| `_archive/` | ✅ frozen | Includes 4 cohorts: orphan_research, audits_2026_05_06, handoffs_2026_05_06, orphan_root_2026_05_06, worldgen_2026_05_07. |

## Per-pipeline status

### Characters (✅ mature — no work needed now)

- **Entry:** `meshy/batch_pipeline.py` (image → 3D → preprocess → bake → atlas).
- **Output:** 33 GLBs in `meshy/output/` (assassin, bog_corpse, bone_construct, … 33 total).
- **Riggers:** 5 in `animators/` (SkinTokens, RigAnything, Mesh2Motion, Anytop, MagicArticulate, AnimateAnyMesh + Mixamo).
- **Quality bar:** REVIEW.md from 2026-05-05 documents bugs found + fixed + tradeoffs. This is the depth standard.
- **Verdict:** Don't touch. This is the only pipeline that produces shippable content.

### Props (✅ mature post-Phase 11)

- **Entry:** `pipelines/props/postprocess_ai_route.py` (orchestrates 7 stages: stage_into_library → preprocess → LOD chain → CoACD collision → billboard bake → PBR bind → validate → Godot export).
- **AI routes:** Trellis2 default, HY3D-2.1 fallback. `ai_route_dispatch.py` picks; `trellis2_batch.py` runs N concepts in one model load.
- **Output:** 52 props in `world/props/library/` (24 v2 procedural + 28 cracked-stone/moss/bone/log/fence variants + obelisk_egyptian_a04 hero).
- **Validation runs:** 9 timestamped `validation_*.md` reports from 2026-05-06/07.
- **Verdict:** Solid. Phase 11C (drop into a real biome scene) is gated on whatever replaces worldgen.

### Audio (✅ mature post-Phase 12)

- **Entry:** `pipelines/audio/biome_ambience.py` (ambience), `synth_sfx.py` / `eleven_sfx.py` (SFX), `local_audio_open.py` (Stable Audio Open 1.0 GPU bake), `local_tts_f5.py`, `local_music_yue.py` (parked).
- **Output:** Archived 2026-05-07 to `_archive/audio_phase12_bake_2026_05_07/`. See [`docs/pipeline_reviews/03_audio.md`](../pipeline_reviews/03_audio.md).
- **Verdict:** Solid. Listen-test + Godot re-export are the only loose ends.

### UI / Icons (✅ working)

- **Entry:** `pipelines/ui/synth_icons.py` (procedural baseline), `openai_icons.py` / `recraft_icons.py` (cloud), `local_diffusion_icons.py` (FLUX-schnell, plumbed but waiting on GPU).
- **Output:** atlas.png + atlas.json + 14 per-faction HUD mockups + 9-slice frames + svg cache.
- **Verdict:** Done for now. lora_train.py exists but unused.

### VFX (✅ working — but duplicated, see below)

- **Entry:** `pipelines/vfx/bake.py` routes effect.json → `baker_particle_cpu.py` / `baker_fracture2d.py` / `baker_smoke_field.py` / `baker_volumetric_fog.py` (3D fog).
- **Output:** 46 effect.json entries across 6 categories (28 spells, plus ambient/destruction/environment/projectiles/blood/dust).
- **GPU plan:** `GPU_BACKENDS_PLAN.md` lists Taichi/Warp/PhiFlow/LiquidFun for later.
- **Verdict:** CPU bakers cover most cases. GPU upgrade is the deferred Phase 13 candidate.

### Game Data (✅ working)

- **Entry:** `pipelines/game_data/generate_records.py` (LLM-driven, OpenAI/Claude/synthetic), `validate_records.py`, `roundtrip_test.py`, `balance/` (DuckDB reports + sim).
- **Output:** schemas + generated/validated records + reports + Yarn link validator.
- **Verdict:** Adapter layer ready. Real TLTE seed records still gated on game-design intent.

### Textures (🟡 — quality gap)

- **Entries (overlapping):**
  - `aaa_texture.py` — full pipeline: prompt → StableMaterials PBR → seam repair → derive_pbr → QA. **Produces A-grade biome sets.**
  - `flux_seamless.py` — FLUX 2 with offset+heal trick (4-pass tiling repair). **A-grade source for non-PBR albedo.**
  - `material_anything_adapter.py` / `ma_image2pbr.py` — Material Anything route.
  - `stablematerials_image2pbr.py` — StableMaterials route.
  - `polyhaven_fetch.py` / `ambientcg_fetch.py` — third-party PBR ingestion.
  - `seam_repair.py` — standalone seam fix.
  - `texture_qa.py` — edge-MSE seam scorer.
  - `derive_pbr_v2.py` — albedo → height/normal/AO/roughness when only albedo exists.
- **Output state (`world/textures/library/`, 31 sets):**
  - **A grade:** 10 sets (all `biome_*` synthesized via aaa_texture)
  - **B grade:** 11 sets (cobblestone variants, forest_floor_*, Rock035)
  - **C grade:** 3 sets (forest_floor_loam, cobblestone_klein, forest_floor_rotten_log)
  - **No QA at all:** 7 sets (cobblestone_sm, cobblestone_sm_std, goblin_bronze, mossy_basalt_test, rock035_derived, rocks_ground_06, v2_test_saltflat)
- **Verdict:** Multiple working tools but no clear front door. Tileability QA isn't on by default. Worldgen v2 used `flux_seamless.py` but bypassed the QA + seam_repair postprocess, so its 4 outputs were B/C grade.

### DEM Fetch (✅ working — kept after worldgen nuke)

- **Entries:** `import_dem.py` (single-bbox), `bulk_pull.py` (wishlist-driven), `catalog_search.py` (no-quota OT catalog), `fetch_regional_stac.py` (ArcticDEM/REMA/LINZ S3 bypass), `tile_stitch.py` (multi-tile composer), `mystery_sampler.py` (random worldwide).
- **Output:** 222 cached TIFFs / 8.1 GB at `D:/assets/dems/`.
- **Verdict:** This is the only worldgen-adjacent thing that survived. It works.

## VFX duplication

Two VFX pipelines on disk, doing different things at different layers:

| Aspect | `pipelines/vfx/` | `art_lab/shaders/` |
|---|---|---|
| **Goal** | Bake content (particles, fracture, smoke, fog) into Godot-importable manifests + frames | Generate + evolve + score Godot shaders (.gdshader files) |
| **Authoring artifact** | `effect.json` | `.gdshader` template + JSON prompt |
| **Tools** | `bake.py` + 4 bakers + `export_godot.py` + `gallery.py` + `import_spell_lab.py` | `shader_compile_preview.py`, `shader_evolve.py`, `shader_promote.py`, `shader_reference_score.py`, `shader_godot_render.py`, `shader_batch_review.py` |
| **Templates / catalog** | 46 effect.json entries → frames + extras | 6 first-party shader templates (beam_lightning_2d, dissolve_fire_2d, portal_swirl_2d, ring_field_2d, shield_ripple_2d, macro_detail_v1) + 5 evolution batches |
| **Godot integration** | flipbook + manifest + extras → scene runtime (MeshTrail3D, AudioCueBus) | direct .gdshader, used as material |

**Both are real.** Neither is vapor. They overlap in name only — they're solving different problems. But:

- A new user cannot tell which to use for "I want a fire spell."
- `art_lab/shaders/templates/macro_detail_v1.gdshader` is a *terrain* shader, not VFX. It's only here because `art_lab/` was the historical "anything Godot-shader" lane.
- Several research reports (C, C2, H) and several plan docs (`SHADER_WORKFLOW_STATUS.md`, `SHADER_RESEARCH_INTEGRATION_PLAN.md`) live under `art_lab/`, so consolidating is non-trivial.

**Suggestion:** when you next want VFX work, decide which lane the task is. "Make a fire spell ground decal" → `pipelines/vfx/` (bake content). "Iterate on portal_swirl shader until it looks like reference" → `art_lab/shaders/` (shader-evolve workflow). Don't merge them.

## Cross-pipeline composition gap

This is the biggest hole post-nuke:

- Each pipeline produces a `library/` of canonical outputs.
- `pipelines/godot_export/export_godot.py` turns one pipeline's library into Godot resources.
- **Nothing composes a *scene* from multiple libraries.** `stage_biome_terrain.py` and `stage_biome_scatter.py` (in `pipelines/godot_export/`) were the worldgen scene-composers — they're still there but they referenced now-archived terrain bundles + biome registry, so they're broken.
- `world3/` is your fresh Godot scene. It currently has its own `pipeline/`, `heightmap/`, `textures/`, `shaders/` subdirs — looks like an embedded mini-pipeline.

**The decision tree for whatever replaces worldgen:**

1. Does the new pipeline live under `pipelines/<name>/` (factory style — emits to `world/` + Godot resources, then `world3/` imports as needed)?
2. Or does it live under `world3/pipeline/` (game-project style — owned by the Godot project, emits in-place)?

The factory style fits the existing architecture. The game-project style fits "I'm building one specific game now and don't need re-use." Both are defensible.

## Workflow-quality scoring

For each pipeline, does it have a real one-command path? `--dry-run`? Clear failure mode?

| Pipeline | One-command | --dry-run | Clear failure | Notes |
|---|---|---|---|---|
| Characters | ✅ `batch_pipeline.py` | partial | ✅ | Mature, REVIEW.md captures bugs |
| Props | ✅ `postprocess_ai_route.py` | ✅ | ✅ | Phase 11 added orchestrator |
| Audio | ✅ `biome_ambience.py` | ✅ | ✅ | Local-path fallback for gated repo |
| UI | ✅ `synth_icons.py` | partial | ✅ | Cloud routes have env-gate fallbacks |
| VFX (bake) | ✅ `bake.py` | partial | ✅ | CPU; GPU still deferred |
| VFX (shaders) | ✅ `shader_evolve.py` | n/a | ⚠️ | Heavy LLM dependency; less mechanical |
| Game Data | ✅ `generate_records.py` | ✅ | ✅ | LLM backend cascades |
| Textures | ⚠️ unclear | partial | ⚠️ | Multiple front doors; no canonical recipe |
| DEMs | ✅ `import_dem.py` / `bulk_pull.py` | ✅ | ✅ | Cache-aware, quota-aware |

**Outliers:**
- **Textures** — multiple working tools but a new user wouldn't know which to call. Needs a canonical recipe.
- **VFX shaders** — workflow is "LLM iterates on prompts" rather than mechanical. Hard to give it a one-command verdict.

## Audit corrections (2026-05-07 post-cleanup pass)

- **224 `audio/sfx/*_qa/` subdirs are NOT empty scratch** — earlier audit was wrong. Each holds `qa.json + spectrogram.png + waveform.png` produced by `pipelines/audio/audio_qa.py` (verified at line 139: `out_dir or in_path.parent / f"{in_path.stem}_qa"`). 7.2 MB total. They're the QA companion to each `<id>.wav`. **Do not delete.**
- **Texture worker activity:** went from 7 ungraded sets to 1 (only `goblin_bronze`, a non-biome character texture). 21 sets now have full PBR pipeline (was unclear yesterday).

## Leftover crumbs

Things still on disk that are dead post-nuke:

1. **`tests/worldgen_v2/`** — pytest suite for the archived pipeline. Move to `_archive/worldgen_2026_05_07/tests/` or delete.
2. **`pipelines/godot_export/stage_biome_terrain.py`** + **`stage_biome_scatter.py`** — worldgen scene-composers. Reference now-archived registry data.
3. **`godot_pack/terrain/qa_alpine_hydraulic`** + **`smoketest_a`** — worldgen-baked terrain artifacts.
4. **`godot_pack/shaders/biome_terrain.gdshader`** + **`biome_water.gdshader`** + **`shader_registry.json`** — worldgen shaders. May still be useful as templates if the new pipeline needs them.
5. **`pipelines/_meta/library_only.json`** — was the link_validator filter for old library structure. May still be relevant.
6. **`docs/handoffs/HANDOFF_audit_expand_2026_05_06.md`** — references worldgen v1 file paths but is a *cross-cutting* handoff, not a worldgen one. Pre-nuke historical, fine to keep.
7. **`original_workflow_godot/`** + **`godot llm ocr.md`** at root — leftovers from the worldgen-debug OCR session. Either archive or leave; they don't hurt anything.

## Recommended next moves (ranked)

In rough order of leverage. Pick whichever matches your appetite.

1. **Decide on the new "scene composition" pipeline.** This is the highest-leverage decision. Two paths: factory-style (under `pipelines/<name>/`, emits to `world/` + godot_pack) or game-project-style (under `world3/pipeline/`, emits in-place). Both are 1-2 days of work to spec. **Until this is decided, the 8 working pipelines produce orphan assets.**

2. **Texture pipeline canonical recipe.** Pick one front door (probably `aaa_texture.py` for new content, `flux_seamless.py` for albedo-only retiles) and document the recipe. Run `texture_qa.py` on the 7 ungraded sets so we know where we stand. ~1 hour.

3. **Sweep the worldgen crumbs** (item 1-4 in [Leftover crumbs](#leftover-crumbs)). 10 minutes.

4. **Real doc reconciliation.** PIPELINE_DIRECTORY and TOOLS_INDEX still have worldgen-stained inventory rows below the banner. Either rewrite the tables or add a much louder banner. 30 min for the rewrite.

5. **Decide on VFX duplication.** Don't merge — but write a short page that says "for X use lane A, for Y use lane B." 15 min.

6. **Phase 13 GPU VFX bakers** (Taichi/Warp/PhiFlow). The plan exists in `pipelines/vfx/GPU_BACKENDS_PLAN.md`. Half day. Only do this if you actually want better fluid/smoke; otherwise CPU is fine.

7. **Listen-test Phase 12 audio + re-export to Godot import format.** Small closeout. 30 min.

## What I did NOT audit

- `art_lab/biomes/`, `art_lab/maps/`, `art_lab/props/` — light touch, since they're declarative data + tools that the user said leave alone.
- `world3/` — fresh, user-active.
- `_archive/` — frozen by rule.
- Third-party `animators/` venvs — they exist and the relevant ones (ComfyUI, Trellis2, ComfyUI_HY3D) are working per Phase 11 forensics.
- Cross-doc link integrity beyond the 19 known archived-target broken links in PIPELINE_DIRECTORY/TOOLS_INDEX.
