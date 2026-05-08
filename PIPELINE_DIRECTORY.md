# Pipeline Directory

Live status of every pipeline in `D:\assets\`. Updated 2026-05-07 (post-worldgen nuke). Truth-from-disk; for full audit see [docs/audits/AUDIT_2026_05_07_post_nuke.md](docs/audits/AUDIT_2026_05_07_post_nuke.md).

## At a glance

| Pipeline | Status | Output count | Entry point |
|---|---|---|---|
| **Characters** | ✅ mature | 33 GLBs | `meshy/batch_pipeline.py` |
| **Props** | ✅ mature (Phase 11); **research-calibrated 2026-05-07** ([brief #03](docs/research_briefs/2026_05_07_sota_survey/03_props_image_to_3d.response.md)) — Trellis2 default validated, no generator swap | 52 entries (24 mesh + 28 decals) | `pipelines/props/postprocess_ai_route.py` |
| **Audio** | 🟡 pipeline mature, content archived 2026-05-07; **research-calibrated 2026-05-07** ([brief #06](docs/research_briefs/2026_05_07_sota_survey/06_audio.response.md)) — noise/static was workflow not model; 6 additive upgrades queued (CLAP/PyMusicLooper QA, AudioGen/ACE-Step/Chatterbox alongside existing tools) | (output archived; pipelines intact) | `pipelines/audio/biome_ambience.py` |
| **UI / Icons** | ✅ working; **research-calibrated 2026-05-07** ([brief #07](docs/research_briefs/2026_05_07_sota_survey/07_ui_icons.response.md)) — two version bumps unblock cloud lane (Recraft V3→V4 Pro Vector; FLUX-schnell→FLUX.2 Klein 4B Apache 2.0); LoRA via AI-Toolkit on Blackwell is biggest unlock; no 2026 AI HUD generator exists | atlas + 14 HUD mockups | `pipelines/ui/synth_icons.py` |
| **VFX (3D bake)** | ✅ working; **research-calibrated 2026-05-07** ([brief #04](docs/research_briefs/2026_05_07_sota_survey/04_vfx_3d_bake.response.md)) — GPU plan reduced to Warp-primary / PhiFlow-watch; build LLM `effect_from_description.py` *before* GPU port | 46 effect.json | `pipelines/vfx/bake.py` |
| **VFX (shaders)** | ✅ working; **research-calibrated 2026-05-07** ([brief #05](docs/research_briefs/2026_05_07_sota_survey/05_vfx_shaders.response.md)) — framework already 2026 SOTA-shaped (AI Co-Artist, ShadAR); 3 additive upgrades queued (DreamSim+LPIPS scoring side-by-side, 3 imported templates, first real batch on `occult_portal`) | 6 templates + N batches | `art_lab/tools/shader_evolve.py` |
| **Game Data** | ✅ working; **research-calibrated 2026-05-07** ([brief #08](docs/research_briefs/2026_05_07_sota_survey/08_game_data_balance.response.md)) — infrastructure validated as best-in-project; "run the plumbed cascade" is biggest unlock (cloud parked); 5 additive tools queued (pymoo Pareto, fastjsonschema, DSPy+GEPA, schema-diff CI, incremental linker) | schemas + records + reports | `pipelines/game_data/generate_records.py` |
| **Textures + world3** | ✅ Phases A–E + F.1/F.3 done; **operating model switched 2026-05-08 to orchestrator/worker; current iteration is M1–M5** ([state doc](world3/docs/WORLD3_STATE_2026_05_08.md)) | 31+ sets; 5 biome kits all purpose-built and bound to per-mode .tres (walk/iso/topdown); `wgv3_rock_dark` has 2K/1K/512 mip ladder; 6 OpenTopo finished real-source materials | `pipelines/textures/aaa_texture.py` (canonical; `--ladder` for hero-quality) |
| **DEM Fetch** | ✅ working | 222 TIFFs / 8.1 GB | `pipelines/terrain/import_dem.py` + `bulk_pull.py` |
| **Character Inpaint** | 🟡 pipeline mechanically correct (2026-05-07 night), FLUX prompt quality is the open gap — see [Path 2 design](docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md) | 1 test variant GLB (`goblin_p_ashen_v5.glb`) | `pipelines/character_inpaint/inpaint_variants.py` |
| **Scene composition** | ❌ **gone** (worldgen archived) | — | — — — *to be rebuilt* |

For canonical run-order recipes, see [WORKFLOWS.md](WORKFLOWS.md).

## Recent activity

- **2026-05-08** — operating-model switch: world3 main chat is orchestrator, OpenTopo chat is worker. State doc at `world3/docs/WORLD3_STATE_2026_05_08.md`. Iteration replaces "Phase F end-to-end" with M1–M5 (material catalog → transition prototype → chunk-size sweep → splat shader → wire to walk.tscn). Handoff template at `docs/handoffs/HANDOFF_TEMPLATE_to_worker.md`.
- **2026-05-07 (night)** — Phase C/D/E complete:
  - C: anchor-mode framing on `IsoCam.gd` / `TopDownCam.gd` + new `PlayerAnchor.gd` + 4 zoom-level captures (40m/300m/50m/10km) under `world3/docs/captures/phase_c/`.
  - D fix: kit-binding bug surfaced during region gallery rerun — `terrain_blend_temperate_forest.tres` and `terrain_blend_grassland.tres` still pointed at alpine textures. Fixed via new `pipelines/textures/deploy_kit_to_world3.py`.
  - E: per-mode `.tres` variants for all 5 kits via `pipelines/textures/emit_per_mode_materials.py`. Wired into `walk.tscn` / `iso.tscn` / `topdown.tscn` and `RegionGalleryCapture.gd`. Captures at `world3/docs/captures/phase_e/` (alpine sanity) and `phase_e_gallery/` (7 regions x iso+topdown).
- **2026-05-07 (evening)** — Phase B complete (B.1–B.5): SR→bake→mip→per-tier QA pipeline wired into `aaa_texture.py --ladder`. Phase D textures generated: temperate_forest + grassland kits (10 new wgv3_tf_*/wgv3_gl_* textures); `biome_kits.json` updated.
- **2026-05-07** — worldgen v1 + v2 archived to `_archive/worldgen_2026_05_07/`. DEMs relocated to top-level `dems/`. Three pillar docs (this one, TOOLS_INDEX, PIPELINE_GUIDE) rewritten — pre-nuke versions preserved at `_archive/docs_pre_nuke_2026_05_07/`.
- **2026-05-07** — fresh `world3/` Godot project user-created as a clean scene-composition target.
- **2026-05-06 PM** — Phase 12 audio deep-dive complete. Stable Audio Open 1.0 baked all 10 biomes, 142 WAVs / 56 MB.
- **2026-05-06 PM** — Phase 11 props deep-dive complete. Trellis2 default; HY3D-2.1 fallback. 4×4 quality sweep on Egyptian obelisk; postprocess orchestrator landed.

## Per-pipeline detail

### Characters (`meshy/` + `animators/`)

- **Entry:** `meshy/batch_pipeline.py` orchestrates image → 3D → preprocess → bake → atlas.
- **Riggers:** SkinTokens, RigAnything, Mesh2Motion, Anytop, MagicArticulate, AnimateAnyMesh + Mixamo (web).
- **Output:** 33 GLBs in `meshy/output/`. Includes assassin, bog_corpse, bone_construct, bone_priest, centipede, crab, crystal_cluster, dark_knight, eye_horror, …
- **Quality reference:** [docs/audits/REVIEW.md](docs/audits/REVIEW.md) — character-pipeline review with bugs found + fixed + tool comparison. This is the depth standard.
- **Latest handoff:** [docs/handoffs/HANDOFF_audit_expand_2026_05_06.md](docs/handoffs/HANDOFF_audit_expand_2026_05_06.md) (cross-cutting; props + game_data context).

### Props (`pipelines/props/` + `world/props/`)

- **Entry:** `pipelines/props/postprocess_ai_route.py` — 7-stage orchestrator: stage_into_library → preprocess → LOD chain → CoACD collision → billboard bake → PBR bind → validate → Godot export.
- **AI routes:** Trellis2 (default, microsoft/TRELLIS.2-4B local) + HY3D-2.1 (fallback, ComfyUI). Dispatcher: `ai_route_dispatch.py`. Batch runner: `trellis2_batch.py`.
- **Output:** 52 entries in `world/props/library/` (24 mesh + 28 decals — barrel_smoke, bone_pile_a01-03, cracked_stone_03_01-06, fence_a01, log_a01-02, moss_patch_01_01-06, rock_*, mushroom_*, tombstone_*, plus obelisk_egyptian_a04 hero from Phase 11).
- **Validation:** 9 timestamped `validation_*.md` reports in `world/props/`.
- **Latest handoff:** [docs/handoffs/HANDOFF_phase11_props_2026_05_06.md](docs/handoffs/HANDOFF_phase11_props_2026_05_06.md). Patches: [pipelines/props/TRELLIS2_PATCHES.md](pipelines/props/TRELLIS2_PATCHES.md). A/B doc: [world/props/ai_routes/AB_hy3d_vs_trellis2_2026_05_06.md](world/props/ai_routes/AB_hy3d_vs_trellis2_2026_05_06.md).

### Audio (`pipelines/audio/` + `audio/`)

- **Ambience:** `biome_ambience.py` + `local_audio_open.py` (Stable Audio Open 1.0 GPU bake).
- **SFX:** `synth_sfx.py` (procedural baseline) + `eleven_sfx.py` (ElevenLabs) + `cc0_ingest.py`.
- **Music:** `local_music_yue.py` (parked, weights-pending) + `adaptive_music.py`.
- **Speech:** `local_tts_f5.py` + `openai_tts.py`.
- **Output:** **archived 2026-05-07** to `_archive/audio_phase12_bake_2026_05_07/` (189 MB) — manual review found procedural/unprompted-cloud bake was placeholder-tier. Pipeline tools untouched; content gets re-baked when there's specific game-design intent. See [`docs/pipeline_reviews/03_audio.md`](docs/pipeline_reviews/03_audio.md).
- **QA:** `audio_qa.py` + `lint_audio.py` + LUFS-targeted normalization per `pipelines/audio/LUFS_AUTHORING_GUIDE.md`.
- **Latest handoff:** [docs/handoffs/HANDOFF_phase12_audio_2026_05_06.md](docs/handoffs/HANDOFF_phase12_audio_2026_05_06.md). Output archived 2026-05-07.

### UI / Icons (`pipelines/ui/` + `ui/`)

- **Procedural baseline:** `synth_icons.py` (always available, no API).
- **Cloud routes:** `openai_icons.py` (gpt-image-1), `recraft_icons.py` (Recraft V3), `pixellab_icons.py`.
- **Local diffusion:** `local_diffusion_icons.py` (FLUX-schnell adapter, plumbed; activated by ComfyUI).
- **Mockups:** `hud_mockup.py` — 14 generated faction HUD previews (ashen_pact + ember_legion × 7 states each).
- **Atlas:** `pack_atlas.py` → `ui/atlas.png` + `ui/atlas.json`.
- **Validation:** `lint_icons.py` + `icon_validator.py`.
- **9-slice + SVG:** `nine_slice.py` + `vtracer_roundtrip.py` + `freelib_ingest.py` (CC0 SVG library).
- **Latest handoff:** [docs/handoffs/HANDOFF_ui_v3_2026_05_06.md](docs/handoffs/HANDOFF_ui_v3_2026_05_06.md).

### VFX — 3D bakers (`pipelines/vfx/` + `vfx/`)

- **Entry:** `bake.py` routes `effect.json` → `baker_particle_cpu.py` (numpy SoA) / `baker_fracture2d.py` (Voronoi shards) / `baker_smoke_field.py` (semi-Lagrangian 2D smoke) / `baker_volumetric_fog.py` (3D fog atlas).
- **Authoring:** `author_grid.py` (24-cell element × archetype) + `author_damage.py` (12-effect damage/impact) + `import_spell_lab.py`.
- **Godot export:** `export_godot.py` (2D flipbook) + `export_godot_3d.py` (4 targets: 3d_billboard / decal / mesh_trail / fog_volume).
- **Runtime helpers:** `vfx/runtime/MeshTrail3D.gd` + `vfx/runtime/AudioCueBus.gd`.
- **Output:** 46 `effect.json` entries across 6 categories (28 spells, plus ambient/destruction/environment/projectiles/blood/dust). 39 2D + 43 3D Godot scenes.
- **GPU plan:** `pipelines/vfx/GPU_BACKENDS_PLAN.md` (Taichi/Warp/PhiFlow/LiquidFun) — deferred Phase 13.
- **Latest handoff:** [docs/handoffs/HANDOFF_vfx_v2_2026_05_06.md](docs/handoffs/HANDOFF_vfx_v2_2026_05_06.md).

### VFX — Shader workflow (`art_lab/`)

- **Distinct from `pipelines/vfx/`:** generates `.gdshader` files via LLM-driven evolve / score / promote.
- **Entry:** `art_lab/tools/shader_evolve.py` — generates N candidates from a template; `shader_promote.py` shortlists best by reference-score; `shader_godot_render.py` renders previews; `shader_batch_review.py` builds review pages.
- **Templates:** 6 first-party Godot 4.5 shaders — beam_lightning_2d, dissolve_fire_2d, portal_swirl_2d, ring_field_2d, shield_ripple_2d, macro_detail_v1 (terrain).
- **Catalogs:** `art_lab/shaders/batches/` (5 evolution batches), `art_lab/shaders/review_queues/` (promoted shortlists), `art_lab/shaders/reference_sets/` (curated targets), `art_lab/shaders/index.html` (dashboard via `shader_lab_index.py`).
- **Status / next-work:** [art_lab/SHADER_WORKFLOW_STATUS.md](art_lab/SHADER_WORKFLOW_STATUS.md) + [art_lab/SHADER_RESEARCH_INTEGRATION_PLAN.md](art_lab/SHADER_RESEARCH_INTEGRATION_PLAN.md).
- **Decision matrix:** see [WORKFLOWS.md](WORKFLOWS.md) — "VFX: which lane?"

### Game Data (`pipelines/game_data/` + `game_data/`)

- **Entry:** `generate_records.py` — schema-constrained record generation. Backends: OpenAI (gpt-image-1 sibling for text), Anthropic Claude (tool-schema), synthetic (always available), local vLLM (`local_llm_backend.py`, `--device cuda`).
- **Schema lifecycle:** `dump_schemas.py` → `schemas.py` → `validate_records.py` → `roundtrip_test.py` (.tres ↔ JSON).
- **Balance:** `pipelines/game_data/balance/` — DuckDB reports (item value-vs-rarity, ability cost-vs-effect, faction crosstab) + `kill_dummy_sim.py`.
- **Yarn validation:** `yarn_link.py` walks `[[choice|target]]` + `<<jump target>>`; ready when first `.yarn` file lands.
- **Output:** generated/ + validated/ + godot/ + reports/ + schemas/ + source/.
- **Latest handoff:** [docs/handoffs/HANDOFF_game_data_v2_2026_05_06.md](docs/handoffs/HANDOFF_game_data_v2_2026_05_06.md).

### Textures (`pipelines/textures/` + `world/textures/library/`)

- **Canonical entry:** `aaa_texture.py` — full pipeline: prompt → CHORD/SM PBR → seam repair → QA → gate → *(with `--ladder`)* SR 4× → bake → mip 2K/1K/512 → per-tier QA → catalog. See `pipelines/textures/PIPELINE.md`.
- **Kit generation:** `palette_lock.py` — generates N textures palette-locked to an anchor. `biome_consistency.py` — color-family validation before/after palette lock.
- **SR / upscaling:** `sr_upscale.py` (Real-ESRGAN x4plus via ComfyUI, offset+heal trick). `bake_pbr.py` (re-derive normal/AO/roughness from upscaled height at full res). `mip_ladder.py` (2K→2K/1K/512 with per-map correct filtering).
- **QA:** `texture_qa.py` — edge/junction/periodic/richness checks; `--ladder` mode runs per-tier + cross-tier contact sheet.
- **PBR backends:** `derive_pbr_v2` (heuristic, default), `sm` (StableMaterials), `chord` (CHORD), `chord_sm_rough` (CHORD + SM roughness hybrid — best for Rock-class hero materials).
- **Output state:** base library (31+ sets in `world/textures/library/`); 10 new wgv3_tf_*/wgv3_gl_* kit textures added Phase D. `wgv3_rock_dark` has full 2K/1K/512 mip ladder at grade B.
- **Biome kits:** `world3/jobs/biome_kits.json` — all 5 kits (alpine/desert/tundra/temperate_forest/grassland) now have purpose-built texture IDs. Previously temperate_forest + grassland reused alpine slots.
- **R&D log:** `pipelines/textures/TEXTURE_RND.md` — full experiment log. **Cookbook (Part 2)** has per-material prompts.
- **Per-mode tuning:** `pipelines/textures/emit_per_mode_materials.py` reads each kit's base `.tres` and emits walk/iso/topdown variants. `pipelines/textures/deploy_kit_to_world3.py` (re)builds kit `.tres` from `biome_kits.json`. Wiring in `walk.tscn` / `iso.tscn` / `topdown.tscn` and `RegionGalleryCapture.gd`.
- **Roadmap:** `world3/docs/ROADMAP.md` — Phases A–E all done as of 2026-05-07; Phase F (multi-tile / continuous world) is next, research+prototype phase.

### DEM Fetch (`pipelines/terrain/` + `dems/`)

- **OT REST:** `import_dem.py` (single-bbox, 23 datasets across `/globaldem` + `/usgsdem` + `pgc_stac` + `linz_stac`). Verified: COP30, AW3D30, GEBCOIceTopo, USGS10m, USGS1m, SRTM15Plus, CA_MRDEM_DTM, ArcticDEM10m, REMA10m, LINZ1m_DTM.
- **Wishlist-driven:** `bulk_pull.py` walks `art_lab/biomes/data_wishlist.json` (172 named regions across stitched/highres-open/showcase/premium/standard/bathymetric tiers); cache-aware + rate-limit-aware (`~/.opentopo_calls.jsonl`).
- **No-quota catalog:** `catalog_search.py` (OT `/otCatalog` lookup; confirms availability before fetch).
- **Regional STAC bypass:** `fetch_regional_stac.py` (ArcticDEM / REMA / LINZ — direct provider S3 bypassing OT `/globaldem`).
- **Multi-tile composer:** `tile_stitch.py` (e.g. full Yosemite at 1m as 9-tile composite).
- **Random sampler:** `mystery_sampler.py` (300 procedurally-sampled worldwide bboxes from interesting strips).
- **Output:** 222 cached TIFFs / 8.1 GB at `D:/assets/dems/`.
- **API reference:** [docs/reference/OPENTOPO_API.md](docs/reference/OPENTOPO_API.md).

### Character Inpaint (`pipelines/character_inpaint/`)

- **Entry:** `inpaint_variants.py` — 5-step orchestrator: render N orbit views (Blender headless) → mask each view → inpaint via ComfyUI/FLUX.1-Fill → back-project to UV atlas (nvdiffrast) → repack into output GLB.
- **Backends:** `--inpaint-backend {dry-run,flux-fill}` × `--project-backend {dry-run,nvdiffrast}`. Dry-run paths exist for pipeline smoke tests without GPU/ComfyUI.
- **Models (flux-fill backend):** `flux1-fill-dev-fp8.safetensors` (11.9 GB), `ae.safetensors` (FLUX 16-ch VAE, 319 MB), `clip_l.safetensors` + `t5xxl_fp8_e4m3fn.safetensors` (CLIP), optional `flux1-redux-dev.safetensors` (123 MB) + `sigclip_vision_patch14_384.safetensors` (816 MB) when `use_redux=True` (style-adapter mode, off by default — Redux can't reliably place specific logos).
- **Status (2026-05-07 night):** pipeline mechanically correct end-to-end. Five bugs found and fixed via visual inspection of intermediates: camera azimuth start, mask cy position, Redux vs prompt-only, FLUX result composite, back-projector azimuth match. Output `goblin_p_ashen_v5.glb` produced cleanly. **Open gap:** FLUX.1-Fill fills the masked chest with goblin skin continuation rather than a distinct insignia — strong surrounding context overwhelms the text prompt. Next: prompt engineering or ControlNet-reference approach.
- **Design doc:** [docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md](docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md).
- **Research brief:** [docs/research_briefs/2026_05_07_sota_survey/09_mesh_inpaint_per_instance.response.md](docs/research_briefs/2026_05_07_sota_survey/09_mesh_inpaint_per_instance.response.md) (Architecture B confirmed).
- **Phase 0 reference assets:** `pipelines/character_inpaint/phase_0_assets/` (insignia, UV layout extracts).

### Scene composition — ❌ gone

This is the open hole. Worldgen v1 + v2 are archived. Each pipeline above produces canonical assets in its own `library/`, but **nothing assembles them into a Godot scene**.

- `pipelines/godot_export/export_godot.py` still works for single-pipeline-to-Godot exports.
- `world3/` is the user's fresh Godot scene; experimental, not wired up.
- See [WORKFLOWS.md](WORKFLOWS.md) "Scene composition" for the open-question section.

## Cross-cutting tools

- **Link validator:** `pipelines/_meta/link_validator.py` — checks asset cross-references (effect → audio → icon → record).
- **HF surveyor:** `pipelines/_meta/hf_surveyor.py` — checks HuggingFace model availability.
- **Comfy runner:** `pipelines/_meta/comfy_runner.py` — generic ComfyUI workflow dispatcher.
- **Depth/normal:** `pipelines/_meta/depth_normal.py` — per-image depth + normal estimation.
- **Matting:** `pipelines/_meta/matting.py` — alpha extraction.
- **Upscale:** `pipelines/_meta/upscale.py` — Real-ESRGAN x4plus and SwinIR.

## Doc map

| Doc | Owns |
|---|---|
| [README.md](README.md) | Entry point + first commands. |
| [DOCS_INDEX.md](DOCS_INDEX.md) | Doc-ownership map. |
| **PIPELINE_DIRECTORY.md** *(this doc)* | Per-pipeline live status. |
| [WORKFLOWS.md](WORKFLOWS.md) | Per-asset run-order trees + tool branch decisions. |
| [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md) | Copy-paste recipes. |
| [TOOLS_INDEX.md](TOOLS_INDEX.md) | Tool inventory. |
| [docs/plans/ROADMAP.md](docs/plans/ROADMAP.md) | What's next. |
| [docs/audits/AUDIT_2026_05_07_post_nuke.md](docs/audits/AUDIT_2026_05_07_post_nuke.md) | Latest audit. |
| [docs/audits/REVIEW.md](docs/audits/REVIEW.md) | Character pipeline review (depth standard). |

## Archive

- `_archive/worldgen_2026_05_07/` — full worldgen v1 + v2 (Godot project, Python pipeline, scripts, baked outputs, broken textures, handoff docs, godot_pack worldgen artifacts, OCR session debris).
- `_archive/docs_pre_nuke_2026_05_07/` — pre-rewrite snapshots of PIPELINE_DIRECTORY/PIPELINE_GUIDE/TOOLS_INDEX. Forensics only.
- `_archive/audits_2026_05_06/`, `_archive/handoffs_2026_05_06/`, `_archive/orphan_research/`, `_archive/orphan_root_2026_05_06/` — older snapshots; never edit.
