# Tools Index — D:\assets

Master index of every tool, script, and AI model. Updated 2026-05-07 (post-worldgen nuke; pre-nuke version at `_archive/docs_pre_nuke_2026_05_07/TOOLS_INDEX.md`).

Hit Ctrl-F for a tool you remember by name.

- 📚 [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md) — copy-paste recipes
- 📋 [PIPELINE_DIRECTORY.md](PIPELINE_DIRECTORY.md) — per-pipeline live status
- 🌳 [WORKFLOWS.md](WORKFLOWS.md) — per-asset run-order trees + tool branch decisions
- 📂 [docs/tools/README.md](docs/tools/README.md) — index of every per-tool / per-pipeline in-tree doc
- 🛠 [animators/INSTALL_MATRIX.md](animators/INSTALL_MATRIX.md) — install recipes for the 13 animator tools (RTX 5090 / Win11)
- 🛣 [docs/plans/ROADMAP.md](docs/plans/ROADMAP.md) — what's verified, what's missing, recommended next
- 🔍 [docs/audits/AUDIT_2026_05_07_post_nuke.md](docs/audits/AUDIT_2026_05_07_post_nuke.md) — latest audit
- 🔬 [docs/plans/RESEARCH_HANDOFF.md](docs/plans/RESEARCH_HANDOFF.md) — research briefs

## Top-level tree

```
D:\assets\
├── meshy/               Character pipeline (Meshy API + preprocess + bake + atlas)
├── animators/           AI rigging / animation / 3D-gen tools (per-tool venvs)
├── pipelines/           All non-character pipelines
│   ├── _meta/           Cross-cutting helpers (link_validator, hf_surveyor, comfy_runner, depth_normal, matting, upscale)
│   ├── audio/           Ambience + SFX + music + speech bakers
│   ├── character_inpaint/ Per-instance mesh albedo inpaint (faction emblems, damage states) — Architecture B (camera-projection)
│   ├── game_data/       Schema-constrained record generation, balance sim, Yarn validator
│   ├── godot_export/    export_godot.py (cross-pipeline) + screenshot_scenes.py
│   ├── props/           Procedural + Trellis2/HY3D AI routes + 7-stage postprocess orchestrator
│   ├── terrain/         OpenTopography DEM fetch + tile stitch (worldgen archived)
│   ├── textures/        AAA-PBR + FLUX seamless + Material Anything + StableMaterials + QA + seam repair
│   ├── ui/              Procedural + cloud icon gen + atlas + 9-slice + HUD mockups
│   ├── vfx/             3D bakers (particle/fracture/smoke/fog) + effect.json schema + Godot exporter
│   └── video/           Comfy video + flipbook extract
├── world/               Outputs: textures/library + props/library
├── audio/               Output: ambience + sfx + music + tts
├── ui/                  Output: atlas + hud + 9slice + svg cache
├── vfx/                 Output: 46 effect.json catalog + Godot scenes + runtime helpers
├── game_data/           Output: schemas + records + reports + validated/godot
├── meshy/               Char outputs (33 GLBs in output/)
├── characters/          Reserved future
├── dems/                222 OT TIFFs / 8.1 GB (relocated 2026-05-07)
├── godot_pack/          Drop-in Godot resources (materials, props, shaders)
├── art_lab/             Shader workflow (templates, batches, evolve/promote/score), biomes, maps, props recipes
├── images/              Concept image stash
├── research/            24 research reports A–K
├── tests/               (ad-hoc; worldgen_v2/ tests await archival)
├── docs/                handoffs/, plans/, audits/, reference/, superpowers/
├── _archive/            Frozen historical (worldgen_2026_05_07/, docs_pre_nuke_2026_05_07/, …)
└── world3/              User-active fresh Godot project
```

## Pipeline tools — by lane

### Characters

| Tool | What |
|---|---|
| [meshy/batch_pipeline.py](meshy/batch_pipeline.py) | Master orchestrator: image → 3D → preprocess → bake → atlas |
| [meshy/meshy_image_to_3d.py](meshy/meshy_image_to_3d.py) | Meshy API client |
| [meshy/preprocess.py](meshy/preprocess.py), [meshy/preprocess_mesh.py](meshy/preprocess_mesh.py) | Geometry cleanup |
| [meshy/bake.py](meshy/bake.py), [meshy/bake_sprites.py](meshy/bake_sprites.py) | 2D sprite bake from 3D |
| [meshy/pack_sheet.py](meshy/pack_sheet.py) | Sprite-sheet packer |
| [meshy/glb_to_fbx.py](meshy/glb_to_fbx.py), [meshy/glb_to_fbx_blender.py](meshy/glb_to_fbx_blender.py) | Format conversion (Mixamo prep) |
| [meshy/pixel_art.py](meshy/pixel_art.py) | Pixel-art bake variant |
| [meshy/batch_animate.py](meshy/batch_animate.py) | Per-rigger animation batch driver |
| [meshy/batch_preprocess.py](meshy/batch_preprocess.py) | Preprocess batch driver |
| [animators/SkinTokens/](animators/SkinTokens/) | Radial-skinning rigger |
| [animators/RigAnything/](animators/RigAnything/) | LLM-instructed rigger |
| [animators/mesh2motion-app/](animators/mesh2motion-app/) | Self-hosted Mixamo-alt (Node + browser; humanoid + fox + bird + dragon) |
| [animators/Anytop/](animators/Anytop/) | Animation tool |
| [animators/MagicArticulate/](animators/MagicArticulate/) | Articulation tool |
| [animators/AnimateAnyMesh/](animators/AnimateAnyMesh/) | Generic mesh animator |
| [animators/hy-motion-fbx-exporter/](animators/hy-motion-fbx-exporter/) | Hunyuan motion → FBX exporter |
| [_archive/orphan_root_2026_05_06/skava_auto_rigger__init__.py](_archive/orphan_root_2026_05_06/skava_auto_rigger__init__.py) | SKAVA Auto-Rigger Blender addon (archived 2026-05-06; marker-based heuristic) |

### Props

| Tool | What |
|---|---|
| [pipelines/props/postprocess_ai_route.py](pipelines/props/postprocess_ai_route.py) | **7-stage orchestrator** (entry point) |
| [pipelines/props/ai_route_dispatch.py](pipelines/props/ai_route_dispatch.py) | Picks Trellis2 vs HY3D per render_class |
| [pipelines/props/trellis2_batch.py](pipelines/props/trellis2_batch.py) | Model-load-once batch runner |
| [pipelines/props/trellis2_route.py](pipelines/props/trellis2_route.py) | Single-prop Trellis2 invocation |
| [pipelines/props/hunyuan3d_route.py](pipelines/props/hunyuan3d_route.py) | HY3D-2.1 ComfyUI route (kijai+visualbruno) |
| [pipelines/props/meshy_route.py](pipelines/props/meshy_route.py) | Cloud Meshy route (gated) |
| [pipelines/props/proc_generate.py](pipelines/props/proc_generate.py) | Procedural recipe runner |
| [pipelines/props/generate_props.py](pipelines/props/generate_props.py) | Top-level props generator |
| [pipelines/props/concept_gen.py](pipelines/props/concept_gen.py), [pipelines/props/concept_placeholder.py](pipelines/props/concept_placeholder.py) | Concept image gen |
| [pipelines/props/lod_chain.py](pipelines/props/lod_chain.py) | 4-tier DECIMATE COLLAPSE LOD |
| [pipelines/props/collision_decompose.py](pipelines/props/collision_decompose.py) | CoACD convex collision |
| [pipelines/props/billboard_bake.py](pipelines/props/billboard_bake.py) | Far-LOD billboard atlas |
| [pipelines/props/material_lod.py](pipelines/props/material_lod.py) | LOD-aware materials |
| [pipelines/props/pbr_material_bind.py](pipelines/props/pbr_material_bind.py) | Bind PBR sets to prop slots |
| [pipelines/props/variation_sweep.py](pipelines/props/variation_sweep.py) | Parametric variation generator |
| [pipelines/props/validate_props.py](pipelines/props/validate_props.py) | Schema validator |
| [pipelines/props/export_godot.py](pipelines/props/export_godot.py) | Godot scene + LOD nodes |
| [pipelines/props/TRELLIS2_PATCHES.md](pipelines/props/TRELLIS2_PATCHES.md) | Forensics notes |

### Audio

| Tool | What |
|---|---|
| [pipelines/audio/biome_ambience.py](pipelines/audio/biome_ambience.py) | **Biome ambience baker** (entry) |
| [pipelines/audio/local_audio_open.py](pipelines/audio/local_audio_open.py) | Stable Audio Open 1.0 (1.21B) GPU bake |
| [pipelines/audio/ambience_pack.py](pipelines/audio/ambience_pack.py) | Pack ambience for Godot import |
| [pipelines/audio/synth_sfx.py](pipelines/audio/synth_sfx.py), [pipelines/audio/synth_sfx_extended.py](pipelines/audio/synth_sfx_extended.py) | Procedural SFX baseline |
| [pipelines/audio/eleven_sfx.py](pipelines/audio/eleven_sfx.py) | ElevenLabs SFX cloud route |
| [pipelines/audio/cc0_ingest.py](pipelines/audio/cc0_ingest.py) | CC0 freesound ingestion |
| [pipelines/audio/local_music_yue.py](pipelines/audio/local_music_yue.py) | YuE local music (parked) |
| [pipelines/audio/adaptive_music.py](pipelines/audio/adaptive_music.py) | Adaptive music stems |
| [pipelines/audio/local_tts_f5.py](pipelines/audio/local_tts_f5.py) | F5-TTS local |
| [pipelines/audio/openai_tts.py](pipelines/audio/openai_tts.py) | OpenAI TTS cloud |
| [pipelines/audio/audio_qa.py](pipelines/audio/audio_qa.py) | LUFS / loudness QA |
| [pipelines/audio/lint_audio.py](pipelines/audio/lint_audio.py) | Catalog linter |
| [pipelines/audio/loop_detect.py](pipelines/audio/loop_detect.py) | Loop-point detection |
| [pipelines/audio/process_audio.py](pipelines/audio/process_audio.py), [pipelines/audio/ffmpeg_decode.py](pipelines/audio/ffmpeg_decode.py) | DSP utilities |
| [pipelines/audio/build_demo.py](pipelines/audio/build_demo.py), [pipelines/audio/gallery.py](pipelines/audio/gallery.py) | Preview rendering |
| [pipelines/audio/export_godot.py](pipelines/audio/export_godot.py) | Godot import resources |
| [pipelines/audio/suggest_sfx_for_record.py](pipelines/audio/suggest_sfx_for_record.py) | Per-record SFX picker |
| [pipelines/audio/recipes/](pipelines/audio/recipes/) | Bake recipe JSONs (biome_ambience, biome_ambience_large_only) |

### UI

| Tool | What |
|---|---|
| [pipelines/ui/synth_icons.py](pipelines/ui/synth_icons.py) | **Procedural icon baseline** (always available) |
| [pipelines/ui/openai_icons.py](pipelines/ui/openai_icons.py) | gpt-image-1 cloud route |
| [pipelines/ui/recraft_icons.py](pipelines/ui/recraft_icons.py) | Recraft V3 cloud route |
| [pipelines/ui/pixellab_icons.py](pipelines/ui/pixellab_icons.py) | PixelLab cloud route |
| [pipelines/ui/local_diffusion_icons.py](pipelines/ui/local_diffusion_icons.py) | FLUX-schnell local adapter |
| [pipelines/ui/lora_train.py](pipelines/ui/lora_train.py) | LoRA training (unused; ready) |
| [pipelines/ui/freelib_ingest.py](pipelines/ui/freelib_ingest.py) | CC0 SVG library ingestion |
| [pipelines/ui/hud_mockup.py](pipelines/ui/hud_mockup.py) | Faction HUD mockup composer |
| [pipelines/ui/pack_atlas.py](pipelines/ui/pack_atlas.py) | atlas.png + atlas.json packer |
| [pipelines/ui/nine_slice.py](pipelines/ui/nine_slice.py) | 9-slice frame slicer |
| [pipelines/ui/vtracer_roundtrip.py](pipelines/ui/vtracer_roundtrip.py) | PNG ↔ SVG via vtracer |
| [pipelines/ui/frame_compose.py](pipelines/ui/frame_compose.py) | Multi-frame composition |
| [pipelines/ui/preview_grid.py](pipelines/ui/preview_grid.py) | Preview grid renderer |
| [pipelines/ui/lint_icons.py](pipelines/ui/lint_icons.py), [pipelines/ui/icon_validator.py](pipelines/ui/icon_validator.py) | QA |
| [pipelines/ui/suggest_icon_for_record.py](pipelines/ui/suggest_icon_for_record.py) | Per-record icon picker |
| [pipelines/ui/export_godot.py](pipelines/ui/export_godot.py) | Godot resource export |

### VFX (3D bakers)

| Tool | What |
|---|---|
| [pipelines/vfx/bake.py](pipelines/vfx/bake.py) | **Effect-router** (entry; effect.json → backend) |
| [pipelines/vfx/baker_particle_cpu.py](pipelines/vfx/baker_particle_cpu.py) | numpy SoA particles + emitter + gravity + drag |
| [pipelines/vfx/baker_fracture2d.py](pipelines/vfx/baker_fracture2d.py) | Voronoi shards + analytical motion |
| [pipelines/vfx/baker_smoke_field.py](pipelines/vfx/baker_smoke_field.py) | Semi-Lagrangian advection 2D smoke |
| [pipelines/vfx/baker_volumetric_fog.py](pipelines/vfx/baker_volumetric_fog.py) | numpy 3D noise → Texture3D-via-slice-atlas |
| [pipelines/vfx/author_grid.py](pipelines/vfx/author_grid.py) | 24-cell element × archetype generator |
| [pipelines/vfx/author_damage.py](pipelines/vfx/author_damage.py) | 12-effect damage/impact catalogue |
| [pipelines/vfx/import_spell_lab.py](pipelines/vfx/import_spell_lab.py) | Migrate legacy spell-lab artifacts |
| [pipelines/vfx/export_godot.py](pipelines/vfx/export_godot.py) | 2D flipbook + manifest |
| [pipelines/vfx/export_godot_3d.py](pipelines/vfx/export_godot_3d.py) | 4 targets: 3d_billboard / decal / mesh_trail / fog_volume |
| [pipelines/vfx/gallery.py](pipelines/vfx/gallery.py) | HTML gallery |
| [pipelines/vfx/schemas.py](pipelines/vfx/schemas.py) | effect.json schema |
| [vfx/runtime/MeshTrail3D.gd](vfx/runtime/MeshTrail3D.gd) | RibbonTrail/TubeTrail Godot wrapper |
| [vfx/runtime/AudioCueBus.gd](vfx/runtime/AudioCueBus.gd) | Frame-synced audio cue autoload |
| [pipelines/vfx/GPU_BACKENDS_PLAN.md](pipelines/vfx/GPU_BACKENDS_PLAN.md) | Phase 13 plan (Taichi/Warp/PhiFlow) |

### VFX (shader workflow)

| Tool | What |
|---|---|
| [art_lab/tools/shader_evolve.py](art_lab/tools/shader_evolve.py) | **Generate N candidates** from a template |
| [art_lab/tools/shader_compile_preview.py](art_lab/tools/shader_compile_preview.py) | Compile + preview |
| [art_lab/tools/shader_godot_render.py](art_lab/tools/shader_godot_render.py) | Render preview via Godot headless |
| [art_lab/tools/shader_reference_score.py](art_lab/tools/shader_reference_score.py) | Score against reference set |
| [art_lab/tools/shader_promote.py](art_lab/tools/shader_promote.py) | Shortlist best for human review |
| [art_lab/tools/shader_batch_review.py](art_lab/tools/shader_batch_review.py) | Build review pages |
| [art_lab/tools/shader_lab_index.py](art_lab/tools/shader_lab_index.py) | Static dashboard generator |
| [art_lab/shaders/templates/](art_lab/shaders/templates/) | 6 templates: beam_lightning_2d, dissolve_fire_2d, portal_swirl_2d, ring_field_2d, shield_ripple_2d, macro_detail_v1 |
| [art_lab/shaders/batches/](art_lab/shaders/batches/) | Evolution batches |
| [art_lab/shaders/review_queues/](art_lab/shaders/review_queues/) | Promoted shortlists |
| [art_lab/shaders/reference_sets/](art_lab/shaders/reference_sets/) | Curated targets |

### Game Data

| Tool | What |
|---|---|
| [pipelines/game_data/generate_records.py](pipelines/game_data/generate_records.py) | **Schema-constrained record generation** (entry; OpenAI / Anthropic / synthetic / vLLM) |
| [pipelines/game_data/local_llm_backend.py](pipelines/game_data/local_llm_backend.py) | Local vLLM with `guided_json` + xgrammar |
| [pipelines/game_data/constrained_generate.py](pipelines/game_data/constrained_generate.py) | Constrained generation core |
| [pipelines/game_data/schemas.py](pipelines/game_data/schemas.py) | Authoritative schemas |
| [pipelines/game_data/dump_schemas.py](pipelines/game_data/dump_schemas.py) | Schema dumper |
| [pipelines/game_data/validate_records.py](pipelines/game_data/validate_records.py) | Validator |
| [pipelines/game_data/roundtrip_test.py](pipelines/game_data/roundtrip_test.py) | .tres ↔ JSON round-trip |
| [pipelines/game_data/migrate_records.py](pipelines/game_data/migrate_records.py) | Schema migrations |
| [pipelines/game_data/balance/](pipelines/game_data/balance/) | DuckDB reports + kill-dummy sim |
| [pipelines/game_data/yarn_link.py](pipelines/game_data/yarn_link.py) | Yarn dialogue link validator |
| [pipelines/game_data/sim/](pipelines/game_data/sim/) | Simulation harnesses |
| [pipelines/game_data/migrations/](pipelines/game_data/migrations/) | Schema migration history |
| [pipelines/game_data/export_godot.py](pipelines/game_data/export_godot.py) | .tres / .gd export |

### Textures

| Tool | What |
|---|---|
| [pipelines/textures/aaa_texture.py](pipelines/textures/aaa_texture.py) | **Canonical entry**: prompt → StableMaterials PBR → seam repair → derive_pbr → QA |
| [pipelines/textures/flux_seamless.py](pipelines/textures/flux_seamless.py) | FLUX 2 + offset+heal trick (4-pass tileable albedo) |
| [pipelines/textures/stablematerials_image2pbr.py](pipelines/textures/stablematerials_image2pbr.py) | StableMaterials route (single-image PBR) |
| [pipelines/textures/material_anything_adapter.py](pipelines/textures/material_anything_adapter.py), [pipelines/textures/ma_image2pbr.py](pipelines/textures/ma_image2pbr.py) | Material Anything route |
| [pipelines/textures/derive_pbr_v2.py](pipelines/textures/derive_pbr_v2.py) | Albedo-only → height/normal/AO/roughness |
| [pipelines/textures/seam_repair.py](pipelines/textures/seam_repair.py) | Standalone seam fix |
| [pipelines/textures/texture_qa.py](pipelines/textures/texture_qa.py) | Edge-MSE seam scorer (writes qa/seam_score.json + grade A/B/C) |
| [pipelines/textures/blender_preview.py](pipelines/textures/blender_preview.py) | Render plane/sphere/combo preview |
| [pipelines/textures/macro_detail_preview.py](pipelines/textures/macro_detail_preview.py) | Iso macro+detail preview |
| [pipelines/textures/detail_pyramid.py](pipelines/textures/detail_pyramid.py) | Multi-scale detail pyramid |
| [pipelines/textures/palette_lock.py](pipelines/textures/palette_lock.py), [pipelines/textures/patina_adapter.py](pipelines/textures/patina_adapter.py), [pipelines/textures/process_texture.py](pipelines/textures/process_texture.py) | Color/style processors |
| [pipelines/textures/biome_texture_bind.py](pipelines/textures/biome_texture_bind.py) | Bind biome → PBR set (was used by worldgen; still useful for prop binding) |
| [pipelines/textures/kit_generator.py](pipelines/textures/kit_generator.py) | Kit generator |
| [pipelines/textures/comfy_generate.py](pipelines/textures/comfy_generate.py) | Generic Comfy texture gen |
| [pipelines/textures/delight.py](pipelines/textures/delight.py) | De-light pre-pass |
| [pipelines/textures/flux_upscale.py](pipelines/textures/flux_upscale.py) | FLUX upscale |
| [pipelines/textures/upscale_biome_set.py](pipelines/textures/upscale_biome_set.py) | Upscale all maps in a set |
| [pipelines/textures/render_ma_mesh.py](pipelines/textures/render_ma_mesh.py) | Material Anything mesh-driven render |
| [pipelines/textures/pack_terrain3d.py](pipelines/textures/pack_terrain3d.py) | Terrain3D-format packer |
| [pipelines/textures/polyhaven_fetch.py](pipelines/textures/polyhaven_fetch.py), [pipelines/textures/ambientcg_fetch.py](pipelines/textures/ambientcg_fetch.py) | Third-party PBR ingestion |
| [pipelines/textures/variant_select.py](pipelines/textures/variant_select.py) | Variant picker |
| [pipelines/textures/make_test_texture.py](pipelines/textures/make_test_texture.py) | Solid test pattern |
| [pipelines/textures/deploy_kit_to_world3.py](pipelines/textures/deploy_kit_to_world3.py) | Phase D: read `world3/jobs/biome_kits.json` and (re)build kit `terrain_blend_<kit>.tres` files; copy library textures into per-kit slot dirs in `world3/textures/wgv3/<kit>_<slot>/` |
| [pipelines/textures/emit_per_mode_materials.py](pipelines/textures/emit_per_mode_materials.py) | Phase E: read each kit's base `terrain_blend_<kit>.tres` and emit walk/iso/topdown variants with per-mode shader-param overrides (UV scale, normal strength, macro tint, blend sharpness, band softness) |

### DEM Fetch (post-worldgen)

| Tool | What |
|---|---|
| [pipelines/terrain/import_dem.py](pipelines/terrain/import_dem.py) | **Single-bbox DEM fetch** (entry; 23 datasets) |
| [pipelines/terrain/bulk_pull.py](pipelines/terrain/bulk_pull.py) | Wishlist-driven cache puller (rate-limit-aware) |
| [pipelines/terrain/catalog_search.py](pipelines/terrain/catalog_search.py) | OT `/otCatalog` search (no quota cost) |
| [pipelines/terrain/fetch_regional_stac.py](pipelines/terrain/fetch_regional_stac.py) | ArcticDEM / REMA / LINZ S3 STAC bypass |
| [pipelines/terrain/tile_stitch.py](pipelines/terrain/tile_stitch.py) | Multi-tile DEM composer |
| [pipelines/terrain/mystery_sampler.py](pipelines/terrain/mystery_sampler.py) | Random worldwide bbox sampler |
| [art_lab/biomes/data_wishlist.json](art_lab/biomes/data_wishlist.json) | 172-region master target list |
| [art_lab/biomes/data_wishlist_mystery.json](art_lab/biomes/data_wishlist_mystery.json) | 300 procedural mystery bboxes |
| [dems/](dems/) | **Persistent TIFF cache** (222 / 8.1 GB; relocated 2026-05-07 from `pipelines/terrain/source_dems/`) |

### Character Inpaint (per-instance albedo variants)

| Tool | What |
|---|---|
| [pipelines/character_inpaint/inpaint_variants.py](pipelines/character_inpaint/inpaint_variants.py) | **Master orchestrator** (entry): GLB → render N orbit views (Blender) → inpaint each (FLUX.1-Fill or dry-run) → back-project to UV (nvdiffrast or dry-run) → repack into output GLB |
| [pipelines/character_inpaint/render_views_runner.py](pipelines/character_inpaint/render_views_runner.py) | Thin wrapper invoking Blender headless to render N orbit views |
| [pipelines/character_inpaint/blender_scripts/render_views.py](pipelines/character_inpaint/blender_scripts/render_views.py) | Blender-side render script (runs in Blender's Python) |
| [pipelines/character_inpaint/comfy_inpaint.py](pipelines/character_inpaint/comfy_inpaint.py) | ComfyUI HTTP client; FLUX.1-Fill workflow builder; dry-run PIL composite fallback |
| [pipelines/character_inpaint/back_project.py](pipelines/character_inpaint/back_project.py) | nvdiffrast-based view → UV atlas back-projector; dry-run = passthrough |
| [pipelines/character_inpaint/glb_repack.py](pipelines/character_inpaint/glb_repack.py) | Replaces a GLB's albedo texture with a new one, preserving geometry/skinning |
| [pipelines/character_inpaint/PHASE_0_WALKTHROUGH.md](pipelines/character_inpaint/PHASE_0_WALKTHROUGH.md) | Original Phase 0 PoC walkthrough (Architecture A — superseded by Architecture B per brief #09) |
| [pipelines/character_inpaint/phase_0_assets/](pipelines/character_inpaint/phase_0_assets/) | Reference inputs (insignia, UV layout extracts) |

Status notes: pipeline mechanically correct end-to-end; FLUX prompt quality is the open gap. Design doc: [docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md](docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md). Run via the pipeline venv at `pipelines/character_inpaint/.venv/`.

### Cross-cutting (`pipelines/_meta/`)

| Tool | What |
|---|---|
| [pipelines/_meta/link_validator.py](pipelines/_meta/link_validator.py) | Asset-cross-reference validator (effect → audio → icon → record) |
| [pipelines/_meta/hf_surveyor.py](pipelines/_meta/hf_surveyor.py) | HuggingFace model availability check |
| [pipelines/_meta/comfy_runner.py](pipelines/_meta/comfy_runner.py) | Generic ComfyUI workflow dispatcher |
| [pipelines/_meta/depth_normal.py](pipelines/_meta/depth_normal.py) | Per-image depth + normal estimation |
| [pipelines/_meta/matting.py](pipelines/_meta/matting.py) | Alpha extraction |
| [pipelines/_meta/upscale.py](pipelines/_meta/upscale.py) | Real-ESRGAN x4plus + SwinIR |
| [pipelines/_meta/library_only.json](pipelines/_meta/library_only.json) | Link-validator filter |

### Godot export

| Tool | What |
|---|---|
| [pipelines/godot_export/export_godot.py](pipelines/godot_export/export_godot.py) | Cross-pipeline exporter (any pipeline output → Godot resources) |
| [pipelines/godot_export/screenshot_scenes.py](pipelines/godot_export/screenshot_scenes.py) | Headless Godot screenshot driver |

### Video

| Tool | What |
|---|---|
| [pipelines/video/comfy_video.py](pipelines/video/comfy_video.py) | ComfyUI video gen |
| [pipelines/video/flipbook_extract.py](pipelines/video/flipbook_extract.py) | Frame extract from video |

## Output trees

```
world/
  textures/library/<set_id>/
    <set_id>_albedo.png + _normal.png + _roughness.png + _metallic.png + _ao.png + _height.png
    aaa_pipeline.json (provenance)
    qa/seam_score.json + tile_2x2.png + plane_preview.png + sphere_preview.png

  props/library/<prop_id>/
    prop.json (manifest)
    thumbnail.png
    decal.png (or decal/mesh GLBs)
    qa.json
  props/ai_routes/{trellis2,hunyuan3d,meshy}/<prop_id>/

audio/
  ambience/<biome>/<layer_kind>__<seed>.wav
  sfx/<category>/<id>.wav
  music/<id>/{ogg,wav,stems/}
  sfx_manifest.json + ambience_summary.json

vfx/
  catalog/{ambient,destruction,environment,projectiles,spells}/<effect_id>/
    effect.json + manifest.json + frames/ + flipbook.png + extras (particles.json | field.json | fragments.json)
    godot/ (scene/material/texture references)

ui/
  atlas.png + atlas.json
  hud_preview_<faction>_<state>.png
  9slice/<frame_id>/
  freelib_svg_cache/
  godot/

game_data/
  generated/<schema>/*.json
  validated/<schema>/*.json
  schemas/*.json
  reports/*.md + *.csv
  godot/*.tres

meshy/output/<character>/
  <character>.glb (rigged)
  preprocessed/, previews/, mixamo_ready/

dems/
  <DATASET>_<W>_<S>_<E>_<N>.tif
```

## Cloud env-var reference

See [docs/reference/CLOUD_KEYS.md](docs/reference/CLOUD_KEYS.md) for the full table — every `*_API_KEY` we read, what it activates, and the fallback.

## OpenTopography reference

See [docs/reference/OPENTOPO_API.md](docs/reference/OPENTOPO_API.md) for endpoint/dataset/rate-limit details.

## Archive

- `_archive/worldgen_2026_05_07/` — full worldgen v1 + v2.
- `_archive/docs_pre_nuke_2026_05_07/` — pre-rewrite snapshots of these 3 pillar docs.
- `_archive/handoffs_2026_05_06/`, `_archive/audits_2026_05_06/`, `_archive/orphan_*/` — older snapshots.
