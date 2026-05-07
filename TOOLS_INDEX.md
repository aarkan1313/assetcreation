# Tools Index — D:\assets

Master index of every tool, script, and AI model in this asset pipeline. Hit Ctrl-F for a tool you remember by name.

- 📚 [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md) — end-to-end walkthroughs (AAA textures, characters, terrain, world maps, biome dressing, shaders)
- 📋 [PIPELINE_DIRECTORY.md](PIPELINE_DIRECTORY.md) — live status table for every tool/pipeline
- 🛣 [docs/plans/ROADMAP.md](docs/plans/ROADMAP.md) — what's verified working, what's missing, recommended next steps
- 🔍 [docs/audits/REVIEW.md](docs/audits/REVIEW.md) — character pipeline review with bugs found and tool comparison
- 🔬 [docs/plans/RESEARCH_HANDOFF.md](docs/plans/RESEARCH_HANDOFF.md) — research briefs for terrain (A), textures (B), VFX (C), UI (D), audio (E), game data (F), G deep dive

---

## 1. Project layout

```
D:\assets\
├── README.md                   ← entry point + doc map
├── TOOLS_INDEX.md              ← this file
├── PIPELINE_DIRECTORY.md       ← live status table for every tool/pipeline
├── PIPELINE_GUIDE.md           ← end-to-end walkthroughs (AAA textures, terrain, maps, biomes, shaders, characters)
├── docs/plans/ROADMAP.md                  ← what's next + parity scorecard
├── docs/audits/REVIEW.md                   ← character pipeline post-mortem
├── docs/plans/RESEARCH_HANDOFF.md         ← briefs for sub-agents
├── _archive/orphan_root_2026_05_06/skava_auto_rigger__init__.py  ← SKAVA Auto-Rigger Blender addon (archived 2026-05-06)
├── images\                     ← reference images (with archived\ subfolder)
│
├── meshy\                      ← MATURE — character mesh pipeline
│   ├── config.json             Meshy API key + defaults
│   ├── generate.py / meshy_image_to_3d.py    Meshy API
│   ├── render_preview.py / render_rig.py     Blender visual previews
│   ├── preprocess.py / preprocess_mesh.py    cleanup + decimate + quad-remesh
│   ├── bake.py / bake_sprites.py             animated mesh → PNG frames
│   ├── pack_sheet.py                         frames → atlas
│   ├── pixel_art.py                          pixel-art filter (shared palette)
│   ├── glb_to_fbx.py                         Mixamo upload prep
│   ├── batch_*.py                            orchestration
│   ├── output\<name>\                        Meshy raw outputs
│   ├── preprocessed\<name>_p.glb             33 cleaned GLBs
│   ├── mixamo_ready\                         FBX exports for Mixamo
│   └── sprites\<name>\                       baked frames + atlas
│
├── animators\                  ← AI riggers, generators, motion synthesizers
│   ├── AnimateAnyMesh\         WSL conda — text + mesh → animated mesh
│   ├── SkinTokens\             Native venv — mesh → rigged GLB (2026 SOTA)
│   ├── RigAnything\            WSL conda — template-free rigger (~5 s)
│   ├── MagicArticulate\        WSL conda — skeleton predictor (sm_120 flash_attn)
│   ├── Trellis2\               Native venv — image → 3D (Meshy alternative)
│   ├── hy-motion-fbx-exporter\ Native venv — text → Mixamo FBX motion
│   ├── mesh2motion-app\        Node web app — Mixamo alternative
│   ├── ComfyUI\                ✅ FLUX.2-klein-4B + Phase 9 universal headless host foundation
│   ├── mesa-env\               ✅ MESA AI text→DEM (Diffusers stack)
│   ├── mesa-repo\              MESA paper code (PaulBorneP/MESA) + cached weights
│   ├── MaterialAnything\       cloned + 8.6 GB MA weights + 5.4 GB ControlNet + 25 GB SD2-inpaint
│   └── Anytop\                 cloned, not configured
│
├── pipelines\                  ← non-character pipelines
│   ├── terrain\                heightmaps + Godot-ready bundle (6 input modes)
│   │   ├── generate_heightmap.py        v1 single-PNG
│   │   ├── terrain_bundle.py            v2 full bundle (height/normal/splat/biome/veg/water/flow + Godot)
│   │   ├── fastnoise_height.py          FastNoiseLite SIMD noise → bundle
│   │   ├── import_dem.py                real-world DEM (OpenTopo / Mapzen, 23 datasets)
│   │   ├── dem_fantasy_edit.py          7 fantasy heightmap transforms
│   │   ├── region_pipeline.py           one-command DEM → biomes → textures → Godot scenes
│   │   ├── bulk_pull.py                 wishlist/cache-aware OpenTopo ingestion
│   │   ├── mystery_sampler.py           procedural unknown-region bbox sampler
│   │   ├── catalog_search.py            OpenTopo /otCatalog bbox search
│   │   ├── tile_stitch.py               multi-tile DEM composer
│   │   ├── biome_splat.py               biome labels → RGBA terrain splat
│   │   ├── worldengine_to_bundle.py     world-scale → bundle
│   │   ├── particle_erosion.py          droplet erosion (refines bundle in-place)
│   │   └── mesa_terrain.py              MESA AI text → DEM → bundle
│   ├── textures\               AAA self-generated PBR stack
│   │   ├── aaa_texture.py               MASTER ORCHESTRATOR (StableMaterials default/strict)
│   │   ├── kit_generator.py             one command → coherent biome kit
│   │   ├── flux_seamless.py             seam-aware FLUX.2-klein
│   │   ├── variant_select.py            N seeds, pick best
│   │   ├── delight.py                   strip baked shadows from albedo
│   │   ├── stablematerials_image2pbr.py real single-image PBR backend
│   │   ├── ma_image2pbr.py              broken for flat 2D textures; kept as reference
│   │   ├── flux_upscale.py              1K → 2K → 4K with seam preserved
│   │   ├── palette_lock.py              LAB hist-match siblings to anchor
│   │   ├── detail_pyramid.py            macro+detail layer pair generator
│   │   ├── macro_detail_preview.py      Blender preview for macro+detail shader pairs
│   │   ├── biome_texture_bind.py        biome registry → AAA PBR pack
│   │   ├── blender_preview.py           HDRI Cycles render (8 envs)
│   │   ├── seam_repair.py               PatchMatch synced across all maps
│   │   ├── texture_qa.py                seam grade + sanity
│   │   ├── pack_terrain3d.py            channel-pack for Terrain3D
│   │   ├── derive_pbr_v2.py             heuristic PBR (--quality fast)
│   │   ├── material_anything_adapter.py mesh-driven PBR (different use case)
│   │   ├── comfy_generate.py            single-shot FLUX.2 + heuristic PBR
│   │   ├── process_texture.py           v1 legacy
│   │   ├── make_test_texture.py         procedural FBM stone
│   │   ├── ambientcg_fetch.py           CC0 ingester (deprecated per direction)
│   │   ├── polyhaven_fetch.py           CC0 ingester (deprecated)
│   │   └── patina_adapter.py            cloud alternative (FAL_KEY)
│   ├── props\                  environment objects
│   │   ├── proc_generate.py / variation_sweep.py / lod_chain.py
│   │   ├── pbr_material_bind.py / export_godot.py
│   │   └── trellis2_route.py / meshy_route.py / hunyuan3d_route.py
│   ├── godot_export\           cross-cutting Godot exporter
│   │   ├── export_godot.py              4 asset types: pbr_material, terrain, sprite_sheet, rigged_glb
│   │   └── README.md
│   ├── vfx\                    ⏸️ C/I research received, not built
│   ├── ui\                     ⏸️ awaiting research/D_ui.md
│   ├── audio\                  ✅ procedural SFX v1 + QA + Godot randomizer export + Phase 9 TTS/music lanes
│   ├── video\                  ✅ Phase 9 Comfy Wan video planner + flipbook extractor
│   └── game_data\              ✅ schema/generate/validate/export/roundtrip/reports v1.5+
│
├── art_lab\                    ← Magic / World Art Lab (G deep dive)
│   ├── shaders\
│   │   ├── templates\          5 first-party Godot shaders + macro_detail_v1
│   │   ├── generated\          per-shader output dirs
│   │   ├── batches\            batch-explore review packets
│   │   ├── review_queues\      promoted shortlists for human review
│   │   ├── reference_sets\     curated images for style scoring
│   │   └── prompts\            LLM operator prompts
│   ├── tools\
│   │   ├── shader_compile_preview.py    single-shader generator
│   │   ├── shader_batch_review.py       batch + non-OCR scoring + HTML gallery
│   │   ├── shader_evolve.py             evolutionary search against reference images
│   │   ├── shader_promote.py            promote diverse review queues
│   │   ├── shader_reference_score.py    compare candidates to reference sets
│   │   ├── shader_godot_render.py       Godot CLI render wrapper
│   │   └── shader_lab_index.py          static shader dashboard
│   ├── legacy\               preserved Shader Cauldron HTML + notes
│   ├── maps\
│   │   ├── generators\generate_world_map.py    layered world map (rivers/roads/factions)
│   │   └── generated\
│   └── biomes\
│       ├── kits\                kit JSON definitions (mossy_highland_ruins.json)
│       ├── tools\dress_biome.py placement compiler (scatter + decals)
│       └── output\<id>\         per-run scatter.csv + masks + preview
│
├── world\                      ← world-asset outputs
│   ├── terrain\                terrain bundles
│   ├── textures\
│   │   ├── catalog\materials.jsonl   license/source/hash provenance
│   │   ├── library\<id>\             AAA texture sets (full PBR + qa/ + provenance)
│   │   ├── input_images\
│   │   └── output\                   legacy v1
│   ├── maps\<id>\              world map output (layers/, previews/, godot/)
│   ├── props\
│   └── scenes\                 reserved
│
├── godot_pack\                 ← exporter output, drop into Godot 4.5
│   ├── materials\<id>\         StandardMaterial3D .tres + textures
│   ├── terrain\<id>\           HeightMapShape3D .tres + bundle
│   ├── sprites\<id>\           SpriteFrames stub + atlas
│   └── characters\<id>\        rigged GLB
│
├── research\                   ← returned research reports
│   ├── A_terrain.md  B_textures.md  C_vfx.md  E_audio.md  F_game_data.md
│   └── G_deep_dive_world_textures_decor_shader.md
│
├── characters\                 reserved for character outputs
├── audio\                      generated SFX + manifest + Godot audio export
├── game_data\                  generated/validated JSONL + Godot `.tres` resources
├── ui\  vfx\                   reserved/stubbed
└── skills\                     deprecated; merging into vfx\

D:\spell lab\                   17 physics engines (separate research lab; SpellLab v2 rewrite scoped)
D:\wsl\                         ~15 reproducible build scripts for WSL conda envs
```

---

## 2. Local scripts

### Meshy / generation pipeline

| Script | Purpose |
|---|---|
| [meshy/generate.py](meshy/generate.py) | One-shot wrapper: submit image → Meshy → save GLB → render preview |
| [meshy/meshy_image_to_3d.py](meshy/meshy_image_to_3d.py) | Just the Meshy API submission/poll/download |
| [meshy/render_preview.py](meshy/render_preview.py) | Blender script: 4-view preview render of any GLB |
| [meshy/render_rig.py](meshy/render_rig.py) | Blender script: render rigged GLB with red skeleton overlay |

### Mesh preprocessing

| Script | Purpose |
|---|---|
| [meshy/preprocess.py](meshy/preprocess.py) | CLI wrapper |
| [meshy/preprocess_mesh.py](meshy/preprocess_mesh.py) | Blender script: import → clean → decimate → optionally quad-remesh → re-export |

Common flags: `--target-tris N` (default 30000), `--quad-remesh`, `--unwrap-uvs`, `--normalize-scale`, `--dry-run`.

### Sprite baking

| Script | Purpose |
|---|---|
| [meshy/bake.py](meshy/bake.py) | CLI wrapper |
| [meshy/bake_sprites.py](meshy/bake_sprites.py) | Blender script: animated mesh → N-angle × M-frame PNG sprites |
| [meshy/pack_sheet.py](meshy/pack_sheet.py) | PNG frames + manifest.json → atlas PNG + atlas JSON |
| [meshy/pixel_art.py](meshy/pixel_art.py) | Optional filter: pixelate / palette-quantize / outline / upscale |

### Batch / pipeline orchestration

| Script | Purpose |
|---|---|
| [meshy/batch_preprocess.py](meshy/batch_preprocess.py) | Preprocess every Meshy `<asset>/model.glb` into `preprocessed/<asset>_p.glb`. Skips already-done assets. |
| [meshy/batch_animate.py](meshy/batch_animate.py) | Run AnimateAnyMesh on multiple (mesh, prompt) jobs from a JSON file |
| [meshy/batch_pipeline.py](meshy/batch_pipeline.py) | End-to-end batch: animate → bake → pack → optional pixel-art |

### Mixamo prep

| Script | Purpose |
|---|---|
| [meshy/glb_to_fbx.py](meshy/glb_to_fbx.py) | CLI wrapper |
| [meshy/glb_to_fbx_blender.py](meshy/glb_to_fbx_blender.py) | Blender: convert preprocessed GLB → Mixamo-ready FBX (single mesh, 1.7m tall, feet at origin, embedded textures) |

### World pipelines (in `pipelines/`)

**Terrain** (`pipelines/terrain/`)

| Script | Purpose |
|---|---|
| [generate_heightmap.py](pipelines/terrain/generate_heightmap.py) | v1 — synthetic heightmap (FBM + biome shaping + thermal erosion). Single PNG output. |
| [terrain_bundle.py](pipelines/terrain/terrain_bundle.py) | v2 — full bundle (height/normal/splat/biome/veg/water/flow/previews + Godot folder). Hydraulic erosion via Landlab. |
| [fastnoise_height.py](pipelines/terrain/fastnoise_height.py) | FastNoiseLite-backed bundle: OpenSimplex2/Cellular/Perlin × FBm/Ridged/PingPong fractal types. |
| [import_dem.py](pipelines/terrain/import_dem.py) | OpenTopography (OT+ key) or Mapzen DEM → bundle. Real-world heightmaps with 13 named presets and 23 dataset entries across `/globaldem`, `/usgsdem`, and regional placeholders. Default dataset is COP30; verified pulls include COP30, AW3D30, GEBCOIceTopo, USGS10m, USGS1m, SRTM15Plus, and CA_MRDEM_DTM. |
| [dem_fantasy_edit.py](pipelines/terrain/dem_fantasy_edit.py) | Apply fantasy transforms (`realistic`, `exaggerated`, `terraced`, `sharpened`, `spired`, `floating`, `mythic`) to normalized heightmaps. |
| [region_pipeline.py](pipelines/terrain/region_pipeline.py) | One-command orchestrator: import DEM → optional fantasy edit → world biome engine → splat → texture bind → scatter → Godot terrain scenes. New 2026-05-06 flags: `--shader-preset`, `--splat-mode`, `--use-real-extents`, `--terrain-size-m`, `--terrain-height-m`. |
| [region_pipeline_from_config.py](pipelines/terrain/region_pipeline_from_config.py) | **`region.config.v1` walker.** Reads declarative `*.region.json` configs at `art_lab/biomes/regions/*.region.json` and dispatches to `region_pipeline.py`. Supports `--config`, `--batch <glob>`, `--template <id>`, `--dry-run`. Schema at [art_lab/biomes/regions/README.md](art_lab/biomes/regions/README.md). |
| [bulk_pull.py](pipelines/terrain/bulk_pull.py) | Walks `data_wishlist.json` or `data_wishlist_mystery.json`, respects cache, tracks `~/.opentopo_calls.jsonl`, and defaults to 400 calls/24h for OT+. |
| [mystery_sampler.py](pipelines/terrain/mystery_sampler.py) | Generates procedural "unknown" bbox targets for the mystery wishlist. |
| [catalog_search.py](pipelines/terrain/catalog_search.py) | `/otCatalog` client for finding available raster/point-cloud/community datasets by bbox. |
| [tile_stitch.py](pipelines/terrain/tile_stitch.py) | Splits large bboxes into N×M child pulls and feather-blends them into one 16-bit stitched DEM. |
| [biome_splat.py](pipelines/terrain/biome_splat.py) | Compiles `biome_labels.png` into registry-driven `biome_splat_rgba.png`. |
| [worldengine_to_bundle.py](pipelines/terrain/worldengine_to_bundle.py) | Wrap a WorldEngine output into the bundle contract. |
| [particle_erosion.py](pipelines/terrain/particle_erosion.py) | Droplet-based hydraulic erosion alternative to Landlab; sharper river carving. |
| [mesa_terrain.py](pipelines/terrain/mesa_terrain.py) | MESA AI (NewtNewt/MESA on HF) text → DEM. Uses dedicated venv `animators/mesa-env/`. **Adobe research license — non-commercial.** |

**Textures** (`pipelines/textures/`) — AAA self-generated stack

| Script | Purpose |
|---|---|
| [aaa_texture.py](pipelines/textures/aaa_texture.py) | **MASTER ORCHESTRATOR.** Chains variants → de-light → StableMaterials PBR (`default`/`strict`) or `derive_pbr_v2` (`fast`) → seam repair → QA → Blender preview → quality gate. Current on-disk best is grade A / 0.00037; `cobblestone_aaa` is grade B / 0.00329. |
| [flux_seamless.py](pipelines/textures/flux_seamless.py) | Seam-aware FLUX.2-klein: text2img → offset shift → img2img heal → reverse shift. 3× seam improvement vs raw klein. |
| [variant_select.py](pipelines/textures/variant_select.py) | Run flux_seamless N times with different seeds, pick lowest-seam-score winner. |
| [delight.py](pipelines/textures/delight.py) | LAB-space large-blur de-lighting; strips baked shadows/highlights from albedo for engine-friendly PBR. |
| [ma_image2pbr.py](pipelines/textures/ma_image2pbr.py) | 🟥 **broken on 2D textures** — MA's i2p needs multi-view 3D mesh consolidation, not a single flat image. Outputs near-uniform grey. Kept in tree for reference but **not used in AAA pipeline**. For mesh-driven PBR use `material_anything_adapter.py`. |
| [stablematerials_image2pbr.py](pipelines/textures/stablematerials_image2pbr.py) | ✅ **Real single-image-to-PBR.** Diffusion model (`gvecchio/StableMaterials`, OpenRAIL, ungated, ~8.3 GB) takes a flat texture image (or text prompt) and outputs tileable basecolor + normal + height + roughness + metallic + derived AO. Standard mode = 50 steps high quality, LCM = 4 steps fast (height contrast issue in LCM, prefer standard). Runs in `mesa-env`. |
| [render_ma_mesh.py](pipelines/textures/render_ma_mesh.py) | Blender Cycles render of a Material Anything mesh-driven output (final OBJ + UV-space PBR maps) under HDRI lighting. |
| [flux_upscale.py](pipelines/textures/flux_upscale.py) | 1K → 2K → 4K via low-denoise FLUX heal pass with offset-trick. Preserves tiling. Verified 2K seam 0.00028. |
| [palette_lock.py](pipelines/textures/palette_lock.py) | LAB histogram-match new textures to a kit anchor → biome-coherent palettes. |
| [blender_preview.py](pipelines/textures/blender_preview.py) | Headless Cycles render: lit sphere + tiled plane + side-by-side combo. **HDRI environment lighting** (8 options: studio, courtyard, forest, sunrise, sunset, city, interior, night). |
| [detail_pyramid.py](pipelines/textures/detail_pyramid.py) | Generate a macro+detail texture pair. AAA terrain uses both: macro for far view, detail for close. Outputs detail material + `detail_pair.json` linking them. |
| [macro_detail_preview.py](pipelines/textures/macro_detail_preview.py) | Blender/Cycles preview for macro+detail shader pairs. |
| [kit_generator.py](pipelines/textures/kit_generator.py) | **One-command biome kit.** Pick a builtin kit (highland_ruins, frozen_volcanic, desert_temple, forest_floor) or write a JSON recipe → 6-8 palette-locked AAA textures + HDRI renders + optional detail pyramids. |
| [seam_repair.py](pipelines/textures/seam_repair.py) | PatchMatch deterministic seam repair, applied synchronously to all maps in a set. |
| [texture_qa.py](pipelines/textures/texture_qa.py) | Seam grade (A/B/C/D), 2x2 tile preview, value-range sanity checks. |
| [pack_terrain3d.py](pipelines/textures/pack_terrain3d.py) | Channel-pack RGBA = albedo+height and RGBA = normal+roughness for Terrain3D. |
| [comfy_generate.py](pipelines/textures/comfy_generate.py) | Single-shot FLUX.2-klein + derive_pbr_v2 (legacy/fast path). |
| [derive_pbr_v2.py](pipelines/textures/derive_pbr_v2.py) | Heuristic PBR derivation. Used by `--quality fast` preset. |
| [material_anything_adapter.py](pipelines/textures/material_anything_adapter.py) | 🟡 **runs but low-quality output.** GLB/OBJ + prompt → 11 UV-space PBR maps in ~10 min on 5090. Pipeline mechanically works, but the model produces bleached albedo and flat roughness regardless of prompt — verified on Meshy goblin with "ancient bronze armor" prompt → got near-uniform white-grey. Kept for reference / experimentation only. |
| [process_texture.py](pipelines/textures/process_texture.py), [make_test_texture.py](pipelines/textures/make_test_texture.py) | v1 legacy. |
| [ambientcg_fetch.py](pipelines/textures/ambientcg_fetch.py), [polyhaven_fetch.py](pipelines/textures/polyhaven_fetch.py) | CC0 library ingesters. **Deprecated per user direction — we self-generate.** |
| [patina_adapter.py](pipelines/textures/patina_adapter.py) | PATINA on fal.ai (cloud alternative). Needs `FAL_KEY`. |

**AAA quality presets** (`aaa_texture.py --quality`):
- `fast` — 2 variants, `derive_pbr_v2` (heuristic, no model), seam C+ accepted (≤ 0.020)
- `default` — 4 variants, **StableMaterials standard 50-step** (real diffusion PBR), seam B+ required (≤ 0.010)
- `strict` — 6 variants, **StableMaterials standard 50-step**, seam A required (≤ 0.005)

`default` and `strict` route through `gvecchio/StableMaterials` for real diffusion-based PBR estimation (basecolor/normal/height/roughness/metallic). Falls back to `derive_pbr_v2` if SM fails. Verified seam grade B (0.00329) on cobblestone test.

**Props** (`pipelines/props/`)

| Script | Purpose |
|---|---|
| [generate_props.py](pipelines/props/generate_props.py) | Manifest-driven prop batch: image → Meshy → preprocess → game-ready GLB. **AI route blocked** today — see [BLOCKERS_AI_ROUTE.md](pipelines/props/BLOCKERS_AI_ROUTE.md). |
| [proc_generate.py](pipelines/props/proc_generate.py) | **CPU/Blender procedural route (v2).** Spawns Blender 5.1 headless. **13 demo kinds**: rock_small, mushroom_lantern, wooden_crate, barrel, lantern, signpost, treasure_chest, fence, log, stump, tombstone, bone_pile, ruin_block. Accepts `--params` JSON for parametric overrides. Writes canonical `prop_asset.v1`. No keys, no GPU. |
| [blender_scripts/proc_props.py](pipelines/props/blender_scripts/proc_props.py) | Blender script with 13 recipes (v2). Each factory takes a `params` dict (displacement_magnitude / z_squash / color_variant / cap_color / emission_strength / size_x / chip_magnitude etc). 21-entry color palette. Renders 256² Eevee-Next thumbnail + GLB. |
| [variation_sweep.py](pipelines/props/variation_sweep.py) | **(J2 MVP #1)** consumes `prop_sweep.v1` JSON: family + count + parametric `params` (float_range / int_range / int_choice / categorical / constant) + LOD ladder + collision policy. Spawns N proc_generate runs at deterministic seeds → lod_chain → collision_decompose. Provenance written to `prop.json.sweep_*`. Specs in `pipelines/props/sweeps/`. |
| [lod_chain.py](pipelines/props/lod_chain.py) + [blender_scripts/proc_lod.py](pipelines/props/blender_scripts/proc_lod.py) | **(J2 MVP #2)** Blender 5.x DECIMATE COLLAPSE (QEM, same algorithm as Unreal Auto-LOD), `bpy.ops.object.modifier_apply` (NOT broken-headless `bpy.ops.mesh.decimate`). Per-class ladders — scatter_multimesh 100/50/20/8%, scene_prop 100/50/20%, hero_prop 100/65/35/15%. Triangle-floor 32 skip. |
| [collision_decompose.py](pipelines/props/collision_decompose.py) | **(J2 MVP #3)** CoACD (SIGGRAPH 2022, ~30% better than archived V-HACD) → list of `ConvexPolygonShape3D` hulls. `pip install coacd trimesh pygltflib`. Per-class threshold: scene_prop 0.05/8 hulls; hero_prop 0.02/24. Hull tightening via `trimesh.convex_hull` after CoACD. Small-mesh (<200 faces) fallback to single trimesh hull. |
| [billboard_bake.py](pipelines/props/billboard_bake.py) + [blender_scripts/proc_billboard.py](pipelines/props/blender_scripts/proc_billboard.py) | **(J2 MVP #5)** orthographic Eevee-Next render of LOD0 from N yaw angles (default 8 × 256² = 2048×256 horizontal-strip atlas), or `--single` for cheap front-only. Updates `prop.json.billboard.{file,angles,tile_px,atlas_layout}`. |
| [material_lod.py](pipelines/props/material_lod.py) | **(J2 MVP #6)** kit atlas. Walks every prop with `kit=<name>`, extracts Principled-BSDF base colors via pygltflib, packs as 32×32 colored tiles into `world/props/kits/<kit>/kit_atlas_lod_far.png` (default 8×8 grid = 64 slots / 256² total) + manifest. PBR-bake-with-xatlas-rebind path is deferred. |
| [pbr_material_bind.py](pipelines/props/pbr_material_bind.py) | CPU AAA-PBR material swap. Binds `prop.json.material_slots` to existing `world/textures/library/<set_id>` texture sets and writes `pbr_material_bindings`; `--all` bound 24/24 mesh props in the audit-expand pass. |
| [trellis2_route.py](pipelines/props/trellis2_route.py) | Build-only local Trellis2 image-to-3D adapter. CPU dry-run emits `prop_asset.v1`; actual model load is gated behind `--device cuda --run-model` and `TRELLIS2_PROP_CMD`. |
| [meshy_route.py](pipelines/props/meshy_route.py) | Meshy hero-prop adapter. Dry-run safe; paid API path refuses to run unless `MESHY_AUTH_FOR_THIS_BATCH=YES` for the current batch. |
| [hunyuan3d_route.py](pipelines/props/hunyuan3d_route.py) | **Phase 9** Hunyuan3D-2.5 Comfy route. Dry-run emits `prop_asset.v1` + QA; real route uploads source image to Comfy, runs `hunyuan3d_25_image_to_glb.json`, and is gated behind `--device cuda --run-model`. |
| [validate_props.py](pipelines/props/validate_props.py) | Schema validator for `prop_asset.v1`. Confirms every LoD GLB + thumbnail + tags + footprint. Walks `world/props/library/*` (50/50 ok at 2026-05-06: 24 procedural + 26 art_lab decals). |
| [export_godot.py](pipelines/props/export_godot.py) | **(J2 MVP #4)** v2+ multi-LOD `.tscn` with explicit `VisibilityRange` (HLOD): per-LOD `MeshInstance3D`, cross-fade margins, `.glb.import` auto-LOD disabled, optional `Sprite3D` billboard tier, CoACD `StaticBody3D`, per-prop MultiMesh scaffold, and shared `_materials/*` PBR resources applied by `PropMaterialBinder.gd`. |
| [sweeps/](pipelines/props/sweeps/) | 8 `prop_sweep.v1` specs (rock×4, mushroom×2, log×2, ruin_block×4, tombstone×2, stump×2, bone_pile×3, fence×1) + `demo10.json` batch index. |

**Game Data** (`pipelines/game_data/`)

| Script | Purpose |
|---|---|
| [schemas.py](pipelines/game_data/schemas.py) | Pydantic v2 source-of-truth schemas for items, abilities, NPCs, factions, and lore terms; provenance includes v1.5 target/sim audit fields. |
| [generate_records.py](pipelines/game_data/generate_records.py) | Synthetic generator plus optional OpenAI and Claude structured-output paths; `--target-balance` delegates to constrained generation and writes candidate records under `game_data/generated/`. |
| [constrained_generate.py](pipelines/game_data/constrained_generate.py) | Balance-target orchestrator: slot plan, narrowed JSON Schema, real asset ID resolver, kill-dummy sim gate, 3x oversample fallback, and gated critique/revise. |
| [balance/targets.toml](pipelines/game_data/balance/targets.toml) | Human-authored v1.5 balance target file for rarity histogram, weapon/ability numeric bounds, school floors, and sim gates. |
| [balance/lint.py](pipelines/game_data/balance/lint.py) | Validates `targets.toml`, checks monotonic ranges, prints current validated range deltas, and reports the target SHA. |
| [balance/duckdb_reports.py](pipelines/game_data/balance/duckdb_reports.py) | DuckDB balance report generator: rarity-by-faction crosstabs, ability cost-vs-effect CSV, item value-vs-rarity CSV, plus Markdown summary under `game_data/reports/`. |
| [sim/kill_dummy.py](pipelines/game_data/sim/kill_dummy.py) | Deterministic 60 Hz / 30 s TrainingDummy combat sim for items and abilities; rejects dummy-survived, ttk<0.5s, no-damage, and player-died. |
| [yarn_link.py](pipelines/game_data/yarn_link.py) | Yarn Spinner link validator. Parses `title:` nodes, choices, jumps, checks `NPC.dialogue_start`, missing targets, and unreachable nodes. |
| [local_llm_backend.py](pipelines/game_data/local_llm_backend.py) | Build-only offline constrained-gen adapter. CPU mode verifies prompt/schema/parser shape and now emits a vLLM OpenAI-compatible `guided_json` + `guided_decoding_backend=xgrammar` request preview. Real vLLM/outlines paths are gated behind `--device cuda --run-model`. |
| [dump_schemas.py](pipelines/game_data/dump_schemas.py) | Dumps JSON Schema files for all record types into `game_data/schemas/`. |
| [migrate_records.py](pipelines/game_data/migrate_records.py) | Applies sequential `pipelines/game_data/migrations/*.py` record migrations to generated or validated JSONL. |
| [validate_records.py](pipelines/game_data/validate_records.py) | Schema/link/balance validation and promotion path into `game_data/validated/`; seed-42 demo validates with 0 schema/link errors. |
| [export_godot.py](pipelines/game_data/export_godot.py) | Converts validated JSONL records into Godot `.tres` resources and helper scripts under `game_data/godot/`; prunes stale resource files during export. |
| [roundtrip_test.py](pipelines/game_data/roundtrip_test.py) | Parses exported `.tres` resources back and verifies IDs/typed fields against validated JSONL; demo passed 14/14 resources. |

**Audio** (`pipelines/audio/`)

| Script | Purpose |
|---|---|
| [synth_sfx.py](pipelines/audio/synth_sfx.py) | Offline procedural SFX generator (v1 base). Six presets: `ui_click`, `ui_confirm`, `ui_back`, `sword_swing`, `fireball_cast`, `footstep`. Pure numpy + stdlib `wave`. Deterministic by seed. |
| [synth_sfx_extended.py](pipelines/audio/synth_sfx_extended.py) | v2 extended catalogue. 33 new presets on top of synth_sfx primitives → 39 sounds total / 112 variants. UI×7 (select / error / open_menu / close_menu / pickup / purchase / quest_complete) + spell-school×8 (fire / ice / lightning / arcane × cast / impact) + footstep×6 (grass / stone / wood / metal / water / snow) + impact×5 (flesh / wood / metal / stone / shield_block) + ambience-placeholder×7. `--build` synthesizes, processes, QAs, and Godot-exports the whole catalogue. |
| [eleven_sfx.py](pipelines/audio/eleven_sfx.py) | Optional cloud ElevenLabs SFX client; gated on `ELEVENLABS_API_KEY`. Hardcoded `pcm_44100` so we don't need ffmpeg/pydub. |
| [local_audio_open.py](pipelines/audio/local_audio_open.py) | v2 Stable Audio Open adapter. `generate(prompt, duration, *, model='small'\|'large', steps, seed, negative_prompt) -> (samples, sr)` mirroring `eleven_sfx.py` shape. Lazy diffusers `StableAudioPipeline` cache; bf16 + cu128 + sm_120 path. `--dry-run` writes silent placeholders so downstream stages run without GPU. Per-call `<stem>.cue.json` provenance. |
| [local_tts_f5.py](pipelines/audio/local_tts_f5.py) | **Phase 9** F5-TTS + Kokoro local TTS lane. Dry-run writes deterministic WAV + `.cue.json`; F5 real run routes through Comfy `f5tts_voice_clone.json`; Kokoro real run uses `KOKORO_TTS_CMD`. Both are gated behind `--device cuda --run-model`. |
| [local_music_yue.py](pipelines/audio/local_music_yue.py) | **Phase 9** YuE music pilot. Dry-run writes placeholder WAV + `.music.json`; real local run uses `YUE_MUSIC_CMD` and refuses the MusicGen/AudioCraft/AudioGen license-trap families by omission. |
| [process_audio.py](pipelines/audio/process_audio.py) | Trim + fade + LUFS-target normalization + true-peak limiter to -1 dBTP. v2 swap: `rms_lufs_proxy()` now uses `pyloudnorm.Meter` (BS.1770-4) for signals ≥400 ms, with RMS-dBFS fallback for shorter one-shots. |
| [audio_qa.py](pipelines/audio/audio_qa.py) | Waveform PNG (binned min/max) + spectrogram PNG (numpy STFT) + sanity (clipped, click-count, DC offset). |
| [loop_detect.py](pipelines/audio/loop_detect.py) | v3 phase-aware loop point search (default `--metric phase`: composite cross-correlation + phase-coherence at the dominant FFT bin + RMS-envelope delta) + crossfade synthesizer + seam-RMS + `long_loop_seam_rms()` 3-loop concat audit. SSD legacy preserved via `--metric ssd` for A/B regression tests. Tunable via env vars `LOOPDET_W_XC`/`W_PHASE`/`W_ENV`. |
| [ffmpeg_decode.py](pipelines/audio/ffmpeg_decode.py) | v3 optional helper for decoding compressed audio (MP3/OGG/FLAC/M4A/Opus) to mono float32 buffers via subprocess `ffmpeg`. PATH-resolved (`AUDIO_FFMPEG_BIN` overrides). `decode()` raises `FfmpegNotFound`; `decode_or_none()` returns None when ffmpeg is missing. Wired into `cc0_ingest.py` as tier-2 fallback after `soundfile`. |
| [openai_tts.py](pipelines/audio/openai_tts.py) | v3 OpenAI Text-to-Speech adapter. Plan-only by default (writes `audio/tts_plans/<id>.openai_tts_plan.json`); `--run` requires `OPENAI_API_KEY` AND `--max-cost-usd <cap>`. Models: `gpt-4o-mini-tts` (default), `tts-1`, `tts-1-hd`. 9 voices (alloy/ash/ballad/coral/echo/fable/nova/sage/shimmer/verse). `wav` output (no ffmpeg) or `pcm`. Single line via `--text`+`--id` or batch via `--batch <jsonl>`. |
| [export_godot.py](pipelines/audio/export_godot.py) | Per-sound `randomizer.tres` (`AudioStreamRandomizer` over N variants), per-WAV `.import`, `cue.json` provenance, `bus_layout.tres` (Master/SFX/UI/Voice/Ambience/Music). |
| [biome_ambience.py](pipelines/audio/biome_ambience.py) | v2 4-layer biome ambience runner (bed_drone -28 LUFS / bed_air -30 LUFS / wildlife_sparse Poisson λ≈0.05/s peak -22 LUFS / distant_event Poisson λ≈0.01/s peak -20 LUFS). Reads `recipes/biome_ambience.json`; backends `local_audio_open` / `library` / `synth`. Beds get loop_detect + crossfade. Per-biome `biome_ambience.json` + top-level `ambience_summary.json`. |
| [recipes/biome_ambience.json](pipelines/audio/recipes/biome_ambience.json) | v3 recipes for **all 10 registered biomes** (lava_field / ice_cavern / mana_crystal / grassland / forest / desert / tundra / swamp / charred_wasteland / underwater). Per-stem prompts hand-tuned with `negative: "music, melody, vocals, rhythm, drum, song, beat"` to keep Stable Audio Open off-melody. Per-biome reverb presets per E2 §3.3 + biome-appropriate Poisson lambdas (densest swamp 0.10/s, sparsest desert 0.025/s). |
| [ambience_pack.py](pipelines/audio/ambience_pack.py) | v2 Godot exporter for biome ambience. Per biome: bed_*.wav + .import (loop=1) + wildlife/distant subdirs + randomizer.tres + preset.tres (custom `BiomeAmbiencePreset` Resource). Top-level: `biome_ambience_registry.tres`, `bus_layout_ambience_overlay.tres` (adds Ambience + AmbienceReverb buses), `BiomeAmbienceController.{tscn,gd}` runtime (4-second crossfade Tween + Poisson timers + per-biome AudioEffectReverb tuning + 3D one-shot spawner). |
| [cc0_ingest.py](pipelines/audio/cc0_ingest.py) | v2 Sonniss + Freesound CC0 library ingester (extended in v3 with `ffmpeg_decode` fallback). `--sonniss DIR` walks a Sonniss bundle, normalizes to -23 LUFS into `audio/library/sonniss/<cat>/...`. `--freesound QUERY` hits API filtered to CC0 only. Heuristic biome-keyword tagging into `biome_candidates`. Unified `audio/library/manifest.json` consumed by `biome_ambience.py` when `backend: library`. |
| [build_demo.py](pipelines/audio/build_demo.py) | End-to-end v1 demo: 3 SFX × 3 variants, processed, QA'd, exported. RMS hits -16 dBFS exactly, peak ≤ -1 dBTP. Still passes after pyloudnorm swap. |
| [gallery.py](pipelines/audio/gallery.py) | v3 static HTML browser (`audio/gallery.html`). Three tabs (SFX / Ambience cards / Ambience stems), live filter, sortable headers, autoplay `<audio>` per row, click-to-zoom spectrogram modal, LUFS column color-coded vs target. Indexes `sfx_manifest.json` + `ambience_summary.json`. |
| [lint_audio.py](pipelines/audio/lint_audio.py) | v3 strict-audio gating linter. Wraps `pipelines/_meta/link_validator.py` (mirrors UI v3 `lint_icons.py` pattern; preserves lane isolation) and adds 4 audio-specific checks: (a) unused sfx, (b) ability↔sfx mismatch via NEGATIVE_TOKENS, (c) bus-assignment sanity, (d) ambience coverage (registry → recipe → pack flow). `--strict` exits 1 on a/b/c; `--warn-only` always 0; `--allow-unused` whitelist. |
| [suggest_sfx_for_record.py](pipelines/audio/suggest_sfx_for_record.py) | v3 cosine-on-token-sets matcher mirroring `pipelines/ui/suggest_icon_for_record.py`. Two lanes per ability (cast_sfx_id, impact_sfx_id), single lane for items/npcs. Bonuses +0.5 (school in id), +0.3 (lane in id), +0.2 (category match). Outputs `audio/suggestions.{json,md}` and (with `--apply`) `audio/sfx_id_patch.jsonl` (game_data team's pickup). |
| [adaptive_music.py](pipelines/audio/adaptive_music.py) | v3 adaptive music orchestrator scaffold. Reads music intent JSON (combat / exploration / bossfight / town pre-seeded) and emits `audio/music/<id>/intent.json` + `manifest.json` + N silent-placeholder stem WAVs + `audio/godot/music/<id>/track.tscn` + `AdaptiveMusicTrack.gd` controller (`set_intensity(0..1)` envelopes, `set_state(name)` lookup, `crossfade_to(other, seconds)` parallel tween). NO open-weights music model wired (license traps). |
| [recipes/hrtf_resonance.json](pipelines/audio/recipes/hrtf_resonance.json) | v3 wrapper recipe for the `godot-resonance-audio` GDExtension (Apache-2.0). Install steps, verify command, decision matrix per use case, fallback behavior. Companion: `audio/godot/spatial/SpatialEmitter.gd` abstraction class + `HRTFVerify.gd` headless smoke. |
| [LUFS_AUTHORING_GUIDE.md](pipelines/audio/LUFS_AUTHORING_GUIDE.md) | v3 single source of truth for loudness targets across the catalogue. 4 measurement units, canonical 21-row target table (UI / weapon / spell / voice / music / 4 ambience layers), per-tool defaults, diagnosing LUFS misses, audience-platform delivery targets. |

**UI / Icons** (`pipelines/ui/`)

| Script | Purpose |
|---|---|
| [synth_icons.py](pipelines/ui/synth_icons.py) | Pure-PIL procedural icon set. v2: 37 presets covering weapons (8), consumables/gems (4), spells one-per-`Ability.school` (8), buffs/chrome (9), plus the 8 v1 originals. Single palette across all → coherent set. 256 px transparent. |
| [openai_icons.py](pipelines/ui/openai_icons.py) | OpenAI `gpt-image-1` adapter, gated on `OPENAI_API_KEY`. Style brief baked in for set-consistency. b64 → PNG. |
| [recraft_icons.py](pipelines/ui/recraft_icons.py) | v2 Recraft V3 cloud adapter, gated on `RECRAFT_API_KEY`. Best-in-class 2026 set-style consistency via `--style-id <UUID>`; supports `--style icon|vector_illustration|...`, `--substyle`, `--svg` (vector lane rasterized through freelib chain). Mirrors `openai_icons.py` shape. |
| [local_diffusion_icons.py](pipelines/ui/local_diffusion_icons.py) | v2 FLUX.1 schnell (Apache-2.0, commercially shippable) adapter. Default mode `--plan` writes a deterministic diffusion plan JSON without GPU touch. `--run` lazy-imports diffusers + torch and executes; LoRA via `--lora` + `--lora-weight`. **Phase 9:** `--backend comfy` writes FLUX-schnell + IP-Adapter/InstantStyle workflow overrides and routes real runs through `comfy_runner.py`. **License gate** hard-refuses FLUX.1 [dev] / [Krea-dev] without `--i-know-its-non-commercial`. |
| [freelib_ingest.py](pipelines/ui/freelib_ingest.py) | v2/v3 free-icon-library ingester. **v3 sources**: `game-icons-net --zip <archive>` (with `--filter-by-list pipelines/ui/freelib_curated_slugs.txt` for the curated 190-slug allowlist) or `url-list` or **new `mit-iso-libs --library lucide\|phosphor\|tabler`** (built-in URL templates via jsDelivr CDN; 24/19/22 curated UI primitives per library). 3-tier SVG rasterizer (resvg-py → cairosvg → PIL silhouette). License-correct: every entry preserves author/license/URL; aggregate `ui/ATTRIBUTION.md` auto-written. |
| [freelib_curated_slugs.txt](pipelines/ui/freelib_curated_slugs.txt) | **v3** 190-slug allowlist for game-icons.net `--filter-by-list`. Categorized: weapons / armor / consumables / spell schools (fire/ice/lightning/nature/shadow/arcane/holy) / buffs / UI primitives / world+map. |
| [pixellab_icons.py](pipelines/ui/pixellab_icons.py) | **v3** PixelLab cloud adapter for native pixel-art icons (16/32/48/64 px). Mirrors `openai_icons.py` / `recraft_icons.py` shape. **Plan-only by default** (writes `ui/diffusion_plans/<id>.pixellab_plan.json`); `--run` requires `PIXELLAB_API_KEY` AND `--max-cost-usd <cap>` to gate spend. |
| [suggest_icon_for_record.py](pipelines/ui/suggest_icon_for_record.py) | **v3** tag-overlap matcher between game_data validated records and ui icons. Cosine on token sets + category/name bonuses. Outputs `ui/icons/suggestions.{json,md}` per-record top-K with reasons. `--apply` writes `icon_id_patch.jsonl` (game_data team's pickup; this tool does not mutate validated records). |
| [lint_icons.py](pipelines/ui/lint_icons.py) | **v3** strict-icons gating wrapper around `link_validator.py`. 4 checks: (a) unused icons, (b) missing semantic_tags, (c) record↔icon category mismatch (NEGATIVE_TOKENS heuristic), (d) RTL flag review for asymmetric icons. `--strict` exits 1; `--warn-only` always exits 0; `--allow-unused <ids>` whitelists intentionally-unused. |
| [lora_train.py](pipelines/ui/lora_train.py) | **v3** plan-only kohya-ss / sd-scripts dataset prep + train command writer. Reads icons under permissive licenses only (CC0 / MIT / ISC / Apache-2.0 / first-party / CC-BY with attribution). Writes `ui/lora/<run_id>/{dataset/, dataset.toml, train_lora.toml, train_command.sh, metadata.json}`. Verify command: `bash ui/lora/<run_id>/train_command.sh` on the 5090 when free. |
| [vtracer_roundtrip.py](pipelines/ui/vtracer_roundtrip.py) | **v3** raster→SVG round-trip via `vtracer` (BSD-3). Per icon: PNG → SVG → re-rasterize via freelib chain → `<id>_round_trip.png` for visual diff. `--plan-only` works without vtracer installed; `--annotate-manifest` writes `svg_traced` paths back into `ui/icons/manifest.json` so Recraft / frame_compose can find vector forms by id. |
| [nine_slice.py](pipelines/ui/nine_slice.py) | Synthesize panel/button/frame/healthbar 9-slice elements + alpha-bbox margin detector for arbitrary input PNGs. Writes `<id>.json` margin sidecars. |
| [frame_compose.py](pipelines/ui/frame_compose.py) | v2/v3 faction-themed 9-slice variant composer. Base (panel/button/frame/healthbar) × ornament × palette JSON → N visual variants. **v3**: 8 corner ornaments (filigree / brackets / gem / scrollwork / **chains / runes / vines / fangs**) + 3 edge styles (none/beads/ridge) + `RECRAFT_REPLACEMENT_HINTS` doc-stub for future cloud-vector ornament swap. `--sweep` runs all bases × all palettes deterministically. Default 4 faction palettes. |
| [pack_atlas.py](pipelines/ui/pack_atlas.py) | Greedy shelf atlas packer (descending-height shelf), POT dimensions, configurable padding. |
| [export_godot.py](pipelines/ui/export_godot.py) | Per-icon `AtlasTexture.tres`, per-9slice `StyleBoxTexture.tres` (one per faction variant when present), unified `Theme.tres` wiring `Button.styles.*` + `Panel.styles.panel` + `IconSet/icons/<id>` lookup type. |
| [hud_mockup.py](pipelines/ui/hud_mockup.py) | v2/v3 real Godot 4.5 HUD `.tscn` generator. Per faction emits `hud_<faction>.tscn` + PIL preview. **v3 `--scenario`** picks one of {default / full_hp / low_hp / combat_active / inventory_full / dialog_open / level_up}; `--fixtures` emits the full 4 factions × 6 scenarios = 24 spot-check PNG grid (skipping .tscn for non-default scenarios). |
| [preview_grid.py](pipelines/ui/preview_grid.py) | Single-PNG preview at 32/64/128 px per icon + 9-slice strip. |

**Video** (`pipelines/video/`)

| Script | Purpose |
|---|---|
| [comfy_video.py](pipelines/video/comfy_video.py) | **Phase 9** Wan/Comfy video planner. Dry-run writes `video_plan.json` + runner plan; real run is gated behind `--device cuda --run-model` and routes through `wan_t2v_5s_720p.json`. |
| [flipbook_extract.py](pipelines/video/flipbook_extract.py) | CPU image-sequence-to-flipbook extractor for Comfy/Wan outputs. `--dry-run` writes a manifest without Pillow/frame requirements. |

**VFX** (`pipelines/vfx/`)

| Script | Purpose |
|---|---|
| [schemas.py](pipelines/vfx/schemas.py) | Pydantic `Effect` (effect.json contract) + `BakeManifest` + `EffectVisual3D`. v2 adds `export_target` (2d/3d_billboard/decal/fog_volume/mesh_trail), element/archetype/tags taxonomy, new `Backend` literals (volumetric_fog/runtime_trail/decal_flipbook/vat + deferred GPU bakers). |
| [baker_particle_cpu.py](pipelines/vfx/baker_particle_cpu.py) | numpy SoA particle baker. Burst/stream emitter, gravity, drag, palette over life, Gaussian splat render, additive + alpha blend. |
| [baker_fracture2d.py](pipelines/vfx/baker_fracture2d.py) | First-party 2D fracture: Voronoi seeds → Sutherland-Hodgman half-plane clip → shards → analytical motion + spin. Outputs `fragments.json` + `bodies.json`. |
| [baker_smoke_field.py](pipelines/vfx/baker_smoke_field.py) | Semi-Lagrangian numpy fluid solver. 64×64 density+velocity grid, buoyancy, viscosity, dissipation. Real fluid sim, deterministic. |
| [baker_volumetric_fog.py](pipelines/vfx/baker_volumetric_fog.py) | **v2** numpy 3D Worley/value noise → density volume → packed slice atlas (`density.png`) + `shader_type fog;` shader (`fog.gdshader`) + `FogMaterial.tres`. `--emit-biome-presets` emits 7 biome haze stubs (lava_field / ice_cavern / mana_crystal / grassland / ruins / swamp / ash_waste). |
| [bake.py](pipelines/vfx/bake.py) | Orchestrator: routes `effect.json` to backend baker. `--all` walks `vfx/catalog/`. v2 adds volumetric_fog / decal_flipbook / runtime_trail / external / vat / GPU-deferred routing + `_hoist_audio_cues()` (manifest.extras.audio_cues for `AudioCueBus`). |
| [export_godot.py](pipelines/vfx/export_godot.py) | 2D `SpriteFrames.tres` + `<id>.tscn` (AnimatedSprite2D, autoplay). **No file copies** (post-2026-05-06 rewrite): emits into `vfx/catalog/<kind>/<id>/godot/` referencing frames at `res://vfx/<kind>/<id>/frames/...`. |
| [export_godot_3d.py](pipelines/vfx/export_godot_3d.py) | **v2 NEW** four 3D export targets: `3d_billboard` (MeshInstance3D + QuadMesh + ShaderMaterial with explicit TIME-driven UV math), `decal` (Decal + ShaderMaterial overlay quad), `mesh_trail` (RibbonTrailMesh/TubeTrailMesh + MeshTrail3D.gd script), `fog_volume` (FogVolume + FogMaterial). No file copies. |
| [author_grid.py](pipelines/vfx/author_grid.py) | **v2 NEW** generator for the 24-cell element × archetype effect grid (fire/ice/lightning/earth/arcane/shadow × projectile/burst/aura/impact). Per-element 4-stop palette, tuned size/speed multipliers, `_audio_cues` for AudioCueBus, archetype-specific export_target. |
| [author_damage.py](pipelines/vfx/author_damage.py) | **v2 NEW** 12-effect damage/impact catalogue (3 blood + 3 sparks + 3 dust + 3 debris). |
| [import_spell_lab.py](pipelines/vfx/import_spell_lab.py) | Migrate 11 mapped artifacts from `D:\spell lab\spell-sandbox\artifacts\` into the new catalog shape with `backend: external`. |
| [gallery.py](pipelines/vfx/gallery.py) | Static HTML gallery v2: filters (element/archetype/backend/export_target), live tag/id search, autoplay sprite-atlas previews via CSS @keyframes steps(), color-coded element pills, fog-volume tile gradient placeholders. |
| [GPU_BACKENDS_PLAN.md](pipelines/vfx/GPU_BACKENDS_PLAN.md) | Adoption plan for Taichi / Warp / PhiFlow / LiquidFun when GPU is free. Same baker shape; one new file each. |
| [vfx/runtime/MeshTrail3D.gd](vfx/runtime/MeshTrail3D.gd) | **v2 NEW** Godot 4.5 GDScript `class_name MeshTrail3D extends MeshInstance3D`. Wraps RibbonTrailMesh/TubeTrailMesh, EMA velocity smoothing for direction-reversal pop fix, idle-fade auto-free, static `spawn_burst()` convenience. |
| [vfx/runtime/AudioCueBus.gd](vfx/runtime/AudioCueBus.gd) | **v2 NEW** Godot 4.5 GDScript autoload. Watches `AnimatedSprite{2D,3D}.frame_changed`, fires `cue_hit(name, effect_id)` signal at frame thresholds derived from `manifest.extras.audio_cues` × fps. Per C2 §4: runtime, not bake-time (FFT-bake doesn't survive variable playback). |

**Godot Exporter** (`pipelines/godot_export/`)

| Script | Purpose |
|---|---|
| [export_godot.py](pipelines/godot_export/export_godot.py) | Cross-cutting: turn pbr_material / terrain / sprite_sheet / rigged_glb output into a `D:/assets/godot_pack/<cat>/<id>/` folder ready for Godot 4.5 import. |

**Magic / World Art Lab** (`art_lab/`) — first-party shaders + maps + biome dressing

| Script / asset | Purpose |
|---|---|
| [art_lab/shaders/templates/*.gdshader](art_lab/shaders/templates/) | 5 `canvas_item` Godot 4.5 shader templates: ring_field_2d, beam_lightning_2d, dissolve_fire_2d, shield_ripple_2d, portal_swirl_2d. Plus 1 `spatial`: **macro_detail_v1** (RNM macro+detail blend with distance fade — pairs with `detail_pyramid.py`). |
| [art_lab/tools/shader_compile_preview.py](art_lab/tools/shader_compile_preview.py) | Single-shader generator: request JSON → `.gdshader` + `.tscn` + `project.godot` + provenance + optional Godot preview render. |
| [art_lab/tools/shader_batch_review.py](art_lab/tools/shader_batch_review.py) | **Batch explorer + review harness.** Generates many param variants, scores from pixels (coverage, contrast, colorfulness, edge energy, motion, role fit), writes HTML gallery + LLM review packet. CPU proxy renderer for when Godot unavailable. |
| [art_lab/tools/shader_evolve.py](art_lab/tools/shader_evolve.py) | Evolves shader parameter populations toward curated reference images while keeping the normal role/quality gate. |
| [art_lab/tools/shader_promote.py](art_lab/tools/shader_promote.py) | Promotes high-scoring candidates from batches into small, diverse human review queues with mutation commands. |
| [art_lab/tools/shader_reference_score.py](art_lab/tools/shader_reference_score.py) | Scores candidates against curated reference image folders; writes `reference_scores.json` and `reference_review.md`. |
| [art_lab/tools/shader_godot_render.py](art_lab/tools/shader_godot_render.py) | Runs candidate projects through Godot CLI when `GODOT_EXE` or `--godot-exe` is available; writes Godot frames/preview/flipbook. |
| [art_lab/tools/shader_lab_index.py](art_lab/tools/shader_lab_index.py) | Builds `art_lab/shaders/index.html`, a static dashboard over batches, review queues, references, templates, and legacy notes. |
| [art_lab/legacy/FOUND_OLD_SHADER_WORKFLOW.md](art_lab/legacy/FOUND_OLD_SHADER_WORKFLOW.md) | Inventory of the recovered `shader-cauldron-v6.html` workflow and related older shader projects. |
| [art_lab/maps/generators/generate_world_map.py](art_lab/maps/generators/generate_world_map.py) | Pure-Python procedural map: layered height/biome/water/rivers/roads/regions/settlements/landmarks/labels GeoJSON+JSON+PNG + 5 previews + Godot scene. Verified `mythos_a` (12 settlements, 134 rivers, 3 factions). |
| [art_lab/biomes/kits/](art_lab/biomes/kits/) | Biome kit JSON definitions (materials, decals, scatter rules, shader hints). Reference: `mossy_highland_ruins.json`. |
| [art_lab/biomes/tools/dress_biome.py](art_lab/biomes/tools/dress_biome.py) | Placement compiler: kit + terrain bundle + map → blue-noise scatter CSV + decal CSV + per-asset masks + top-down preview + Godot recipe. Verified 9,818 scatter + 603 decals on smoketest_a. |
| [art_lab/biomes/tools/world_biome_engine.py](art_lab/biomes/tools/world_biome_engine.py) | **Coherent multi-biome world generator.** Reads `world_kits/*.json`, places biomes by Poisson + priority, computes influence (Voronoi + altitude/slope affinity), **snaps boundaries to terrain features** (rivers / ridges / altitude bands), per-biome heightmap shaping with feature carving (lava cracks, ice spires, crystal spikes, glassy smoothing). Base heightmap = synthetic continental (continent + ridge + fine FBM stack) by default, **or pass `--base-heightmap path/to/height_16.png` to use any real terrain bundle's DEM** (e.g. an OpenTopography Utah canyon → 4 biomes painted on top). Emits 3-tier views (world / regional / local) + full Godot bundle. Verified on synthetic continent + Utah Vermilion Cliffs + Norwegian Hardanger fjord. |
| [art_lab/biomes/tools/region_zoom.py](art_lab/biomes/tools/region_zoom.py) | **World chunk → playable terrain.** Crop a bbox of any world, upsample to target resolution with fresh mid + fine FBM detail, re-carve biome features at playable scale, emit a full bundle at `world/regions/<id>/`. The bridge between world-overview and "player walks here." |
| [art_lab/biomes/world_kits/*.json](art_lab/biomes/world_kits/) | World biome identity kits: `lava_field.json`, `ice_cavern.json`, `mana_crystal.json`, `grassland.json`. Schema: [BIOME_KIT_SCHEMA.md](art_lab/biomes/BIOME_KIT_SCHEMA.md). |
| [art_lab/biomes/BIOME_KIT_SCHEMA.md](art_lab/biomes/BIOME_KIT_SCHEMA.md) | Schema doc: how a kit drives world/regional/local rendering + per-pair transition specs. |
| [art_lab/biomes/biome_texture_registry.json](art_lab/biomes/biome_texture_registry.json) | **Biome → AAA-texture binding registry.** Single source of truth: each biome_id → set_id (lives under `world/textures/library/<set_id>`) + splat_channel (R/G/B/A) + prompt_seed (auto-regenerates missing sets via `aaa_texture.py`) + tiling_meters. |
| [art_lab/biomes/biome_scatter_rules.json](art_lab/biomes/biome_scatter_rules.json) | Per-biome scatter ruleset for `stage_biome_scatter.py`. mesh kinds: `box`, `cyl`, `cone`, `sphere`, `prism`. Optional emission/metallic/roughness/y_offset_m fields. |
| [art_lab/biomes/world_catalogue.json](art_lab/biomes/world_catalogue.json) | Curated **(preset × style × biome-mix)** combinations known to look good. 10 starter regions covering fjord/volcano/spire/canyon/highland/tepui/atlas/dunes/alps/glacier. |
| [art_lab/biomes/data_wishlist.json](art_lab/biomes/data_wishlist.json) | **Master DEM target list.** 172 named regions across stitched/highres_open/showcase/premium/standard/bathymetric tiers. Each tagged with bbox + dataset + fantasy-style hints. Walked by `bulk_pull.py`. |
| [art_lab/biomes/data_wishlist_mystery.json](art_lab/biomes/data_wishlist_mystery.json) | 300 procedurally-sampled "unknown" bboxes across worldwide interesting strips. Generated by `mystery_sampler.py`. |
| [pipelines/terrain/source_dems/](pipelines/terrain/source_dems/) | **Persistent TIFF cache.** Raw OpenTopography downloads. Re-runs hit the cache; no API credit re-spend. Audit snapshot: 74 TIFFs / ~2.8 GB. Filename pattern: `<DATASET>_<W>_<S>_<E>_<N>.tif`. |
| [pipelines/terrain/dem_fantasy_edit.py](pipelines/terrain/dem_fantasy_edit.py) | Apply a fantasy-style transform to a heightmap PNG. Styles: `realistic, exaggerated, terraced, sharpened, spired, floating, mythic`. Operates on normalized 0..1 heightmaps; slots between `import_dem.py` and the biome engine. |
| [pipelines/terrain/region_pipeline.py](pipelines/terrain/region_pipeline.py) | **One-command DEM-to-Godot orchestrator.** Chains import_dem → fantasy_edit → biome_engine → splat → texture_bind → scatter → stage_biome_terrain. Single command from a preset to 3 ready-to-play Godot scenes. |
| [pipelines/terrain/bulk_pull.py](pipelines/terrain/bulk_pull.py) | Walks `data_wishlist.json` and runs `import_dem.py` per region. Filters by `--tier`, optional `--dry-run`. Resumable via the TIFF cache. |
| [pipelines/terrain/mystery_sampler.py](pipelines/terrain/mystery_sampler.py) | Procedurally samples N random bboxes from "interesting" worldwide strips (Andes, Himalayas, Scandinavia, etc) for the mystery tier of the wishlist. |
| [pipelines/terrain/catalog_search.py](pipelines/terrain/catalog_search.py) | **OpenTopography catalog search** by bbox via `/otCatalog`. Lists all datasets available for any region (raster + point cloud + community). Confirms availability before fetch; no API quota cost. |
| [pipelines/terrain/tile_stitch.py](pipelines/terrain/tile_stitch.py) | **Tile-stitch huge DEM regions.** Splits a target bbox into N×M overlapping tiles (each within the dataset's per-call km² limit), pulls each via `import_dem.py`, blends seams with linear feather, writes a single stitched 16-bit PNG. Use this for full-Yosemite-at-1m or full-fjordland scale. |
| [docs/reference/OPENTOPO_API.md](docs/reference/OPENTOPO_API.md) | **Full OpenTopography API reference.** Captures all endpoints (`/globaldem`, `/usgsdem`, `/otCatalog`), all datasets (Swagger-documented + 3944-total catalog), bbox limits, rate limits, on-demand processing tools, and known gotchas (regional rasters returning 400 from /globaldem). |
| [pipelines/_meta/link_validator.py](pipelines/_meta/link_validator.py) | **Cross-pipeline link validator.** Walks `game_data/validated/*.jsonl` and asserts every `icon_id` / `vfx_id` / `sfx_id` / `faction_id` / `ability` / future `prop_id` reference resolves to a real asset in the corresponding pipeline, including `world/props/library/*/prop.json`. Reports missing refs + unused assets. Run after any regen. `--strict` makes unused-asset warnings into failures. Returns exit 0/1. |
| [pipelines/_meta/comfy_runner.py](pipelines/_meta/comfy_runner.py) | **Phase 9 ComfyUI runner.** Dry-run by default; applies dotted workflow overrides, submits `/prompt` only with `--run`, polls `/history/<id>`, downloads `/view` outputs, and can validate `/object_info` node classes. |
| [pipelines/_meta/comfy_workflows/](pipelines/_meta/comfy_workflows/) | **Phase 9 workflow library.** Starter workflows plus Hunyuan3D, FLUX/IP-Adapter icons, F5-TTS, Wan, BiRefNet, DepthAnything/GeoWizard, and HAT-L upscale JSONs. |
| [pipelines/_meta/hf_surveyor.py](pipelines/_meta/hf_surveyor.py) | **Phase 9 HF surveyor.** Writes weekly model reports with commercial-license accept/reject filtering; `--dry-run` verifies without network. |
| [pipelines/_meta/matting.py](pipelines/_meta/matting.py) | **Phase 9 BiRefNet matting helper.** Comfy dry-run planner; real run waits on node pack + GPU. |
| [pipelines/_meta/depth_normal.py](pipelines/_meta/depth_normal.py) | **Phase 9 DepthAnything/GeoWizard helper.** Comfy dry-run planner for depth + normal outputs. |
| [pipelines/_meta/upscale.py](pipelines/_meta/upscale.py) | **Phase 9 HAT-L upscale microtool.** Comfy dry-run planner, kept in `_meta` so texture-lane retrofit can consume it later. |
| [docs/reference/CLOUD_KEYS.md](docs/reference/CLOUD_KEYS.md) | Consolidated env-var index — every `*_API_KEY` we read, what tool activates, fallback when missing. |
| [docs/plans/EXPANSION_PLAN.md](docs/plans/EXPANSION_PLAN.md) | Living checklist — phased plan to take pipelines D-J from v1 to SOTA. Tracks Round 2 research returns + dependent build items. |
| [pipelines/terrain/biome_splat.py](pipelines/terrain/biome_splat.py) | Compiles `biome_labels.png` → `biome_splat_rgba.png` using the registry's channel assignment. Soft Gaussian smoothing for shader-friendly transitions. Writes `biome_splat.json` manifest. |
| [pipelines/textures/biome_texture_bind.py](pipelines/textures/biome_texture_bind.py) | **Biome → AAA-texture binder.** For a world output dir, ensures every biome's AAA texture set exists in the library (auto-generates missing sets via `aaa_texture.py` using `prompt_seed`). Emits `biome_pbr_pack.json` next to the world — single file the Godot terrain shader reads to wire all 4 layers. |
| [pipelines/godot_export/stage_biome_terrain.py](pipelines/godot_export/stage_biome_terrain.py) | **Stages a biome world into a Godot 4.5 project.** Copies the canonical shader (`godot_pack/shaders/biome_terrain.gdshader`) + height + biome splat + 4 PBR sets, writes a preconfigured `ShaderMaterial` `.tres` (with triplanar uniforms) + a ready-to-play `.tscn` (PlaneMesh with vertex displacement, DirectionalLight, Camera). |
| [godot_pack/shaders/biome_terrain.gdshader](godot_pack/shaders/biome_terrain.gdshader) | **Canonical biome terrain shader** (Godot 4.5 spatial). Vertex-stage displacement from heightmap with analytic neighbour-gradient normal. Fragment-stage 4-layer biome blend with triplanar projection (`triplanar_strength` 0..1, `triplanar_sharpness` 1..16) so steep slopes sample from the side. Per-biome tiling rates, DirectX→GL normal flip on unpack. |
| [pipelines/godot_export/stage_biome_scatter.py](pipelines/godot_export/stage_biome_scatter.py) | **Biome scatter compiler.** Per-biome scatter rules → blue-noise-sampled MultiMesh placements with placeholder primitives (Box/Cylinder + tinted material). Reads biome_labels + heightmap + vegetation_density + water_mask. Emits self-contained `biome_scatter_<world_id>.tscn`. Scales from a few hundred to 10k+ instances. Auto-included by `stage_biome_terrain.py` if present. |
| [art_lab/biomes/biome_scatter_rules.json](art_lab/biomes/biome_scatter_rules.json) | Per-biome asset list (placeholder mesh kind, color, density_per_m²) driving `stage_biome_scatter.py`. |

**Prop Kit Lab** (`art_lab/props/`)

| Script | Purpose |
|---|---|
| [prop_plan_kit.py](art_lab/props/tools/prop_plan_kit.py) | Build CPU-only prop kit plans and work queues from kit + recipe contracts. |
| [prop_validate.py](art_lab/props/tools/prop_validate.py) | Validate prop kit recipes and optional generated prop assets. |
| [prop_make_decal.py](art_lab/props/tools/prop_make_decal.py) | CPU decal generator for `texture_decal_v1` recipes; 26 decal variants exist from the prep run. |
| [prop_make_blender.py](art_lab/props/tools/prop_make_blender.py) | Blender procedural generator scaffold for rocks, foliage cards, mushrooms, logs, and ruins; dry-run verified, real Blender smoke still pending. |
| [prop_run_queue.py](art_lab/props/tools/prop_run_queue.py) | Safe queue runner for CPU decal tasks. |
| [prop_gallery.py](art_lab/props/tools/prop_gallery.py) | Static HTML gallery for a prop kit plan. |

See `art_lab/README.md` and `art_lab/biomes/README.md` for details.

**Status of the formerly-vapor categories (2026-05-06 update):**

- ✅ `pipelines/game_data/` — Pydantic schemas + synth/OpenAI/Claude generation + balance-constrained target mode + kill-dummy sim + migrations + DuckDB balance reports + Yarn link validator + local-LLM dry-run adapter + Godot `.tres` codegen. Round-trip 14/14 passed and link-validator missing refs=0 (5 items + 3 abilities + 2 factions + 2 NPCs + 2 lore terms). HANDOFF: `docs/handoffs/HANDOFF_game_data_v2_2026_05_06.md` + `docs/handoffs/HANDOFF_audit_expand_2026_05_06.md`.
- ✅ `pipelines/audio/` — synth + ElevenLabs adapter + process spine + QA + Godot AudioStreamRandomizer. 9-variant SFX bank shipped (UI click, sword swing, fireball cast). HANDOFF: `HANDOFF_audio_2026_05_06.md`.
- ✅ `pipelines/ui/` — synth + OpenAI Images adapter + 9-slice + atlas + Godot Theme. 8-icon set + 4 9-slice elements + atlas + theme.tres. HANDOFF: `HANDOFF_ui_2026_05_06.md`.
- ✅ `pipelines/vfx/` — three CPU bakers (particle, fracture2d, smoke field) + Godot SpriteFrames exporter + spell-lab importer + gallery. 3 demo spells + 11 migrated legacy artifacts. HANDOFF: `HANDOFF_vfx_2026_05_06.md`. GPU backends planned in `GPU_BACKENDS_PLAN.md`.
- ✅ `pipelines/props/` — **v2+ SOTA push** (J2 + audit-expand). 13 procedural recipes, parametric variation_sweep, 4-tier LOD chain via DECIMATE COLLAPSE, CoACD convex collision, Godot 4.5 HLOD via VisibilityRange, billboard atlas, kit material atlas, biome_scatter_rules v3, AAA-PBR binding, and gated Meshy/Trellis2 adapters. 50 prop records validate (24 mesh props + 26 decals), 24 mesh props PBR-bound, 63 Godot LOD nodes, 6 with collision, 9 with billboards. HANDOFF: `HANDOFF_props_v2_2026_05_06.md` + `docs/handoffs/HANDOFF_audit_expand_2026_05_06.md`. Runtime AI route remains blocked on GPU/spend authorization; documented in `BLOCKERS_AI_ROUTE.md`.

See [docs/plans/ROADMAP.md](docs/plans/ROADMAP.md) parity scorecard for what's missing per pipeline.

Common flags for `bake.py`: `--angles N`, `--frames N`, `--res N`, `--ortho`, `--elevation D`, `--no-alpha`.

### Custom Blender addons

| File | Purpose |
|---|---|
| [_archive/orphan_root_2026_05_06/skava_auto_rigger__init__.py](_archive/orphan_root_2026_05_06/skava_auto_rigger__init__.py) | **SKAVA Auto-Rigger** — heuristic marker-based Blender addon for humanoid / quadruped / simple skeletons. Manual fallback when ML riggers misbehave. *Archived 2026-05-06* (was at repo root by accident; preserved if needed). |

---

## 3. AI tools (in animators/)

### Image-to-3D

| Tool | Status | Env | Notes |
|---|---|---|---|
| Meshy API (cloud) | ✅ | API key in `meshy/config.json` | Default. ~30 credits remaining. |
| [Trellis2](animators/Trellis2/) | ✅ | `Trellis2\venv\` (Windows) | Microsoft 4B model. Backup for when Meshy credits run out. ~20 GB weights. |

### Auto-rigging (mesh → rigged mesh)

| Tool | Status | Env | Strengths |
|---|---|---|---|
| [SkinTokens](animators/SkinTokens/) | ✅ verified | `SkinTokens\.venv\` (Windows) | 2026 SOTA. Skeleton + skin weights in one pass. ~22 s/mesh. |
| [RigAnything](animators/RigAnything/) | ✅ verified | WSL conda `riganything` | Fastest (~5 s). Template-free for diverse topology (creatures, marine life). 40 bones. |
| [MagicArticulate](animators/MagicArticulate/) | ✅ verified | WSL conda `magicarti-flash` | Skeleton-only (no skinning). 52 bones with finger detail. Requires source-built `flash_attn` for sm_120. |
| **Mixamo** (web) | ✅ verified prep | n/a — adobe.com | 2500+ humanoid animations, manual web upload. Best for hand-picked humanoids. |
| **[Mesh2Motion](animators/mesh2motion-app/)** | ✅ installed, manual UI | Node 24 + browser at `http://localhost:5173` | Self-hosted Mixamo alt. Humanoid + fox + bird + dragon. Run via `start.ps1`. |
| [SKAVA](_archive/orphan_root_2026_05_06/skava_auto_rigger__init__.py) | ⏸️ untested (archived) | Blender addon | Marker-based heuristic, deterministic. Guaranteed to produce *some* rig. |

### Animation / motion

| Tool | Status | Env | Input | Output |
|---|---|---|---|---|
| [AnimateAnyMesh](animators/AnimateAnyMesh/) | ✅ verified | WSL conda `animateanymesh` | static mesh + text | 16-frame shape-key animated FBX |
| [hy-motion-fbx-exporter](animators/hy-motion-fbx-exporter/) | ⏸️ weights deferred | `hy-motion-fbx-exporter\.venv\` | text + Mixamo FBX | retargeted animated FBX |
| Anytop | ❌ not installed | n/a | skeleton sequence | n/a |

---

## 4. Environments inventory

| Env name | Location | Python | Torch | Purpose |
|---|---|---|---|---|
| `animateanymesh` | WSL `/opt/miniconda3/envs/` | 3.11 | 2.9.1+cu130 | AnimateAnyMesh, custom-built pytorch3d 0.7.9 (no pulsar), bpy 4.5 |
| `riganything` | WSL `/opt/miniconda3/envs/` | 3.11 | 2.9.1+cu130 | RigAnything |
| `magicarti` | WSL `/opt/miniconda3/envs/` | 3.10 | 2.9.1+cu130 | MagicArticulate base (no flash_attn) — kept clean as fallback |
| `magicarti-flash` | WSL `/opt/miniconda3/envs/` | 3.10 | 2.9.1+cu130 | MagicArticulate + source-built flash_attn 2.8.3 with sm_120 kernels |
| `SkinTokens/.venv` | `D:\assets\animators\SkinTokens\` | 3.11 | 2.7.0+cu128 | SkinTokens (came with the repo) |
| `Trellis2/venv` | `D:\assets\animators\Trellis2\` | 3.11 | 2.8.0+cu128 | Trellis2 (came with the repo) |
| `hy-motion-fbx-exporter/.venv` | `D:\assets\animators\hy-motion-fbx-exporter\` | 3.12 | 2.x+cu124 | hy-motion CLI |
| `mesa-env/venv` | `D:\assets\animators\mesa-env\` | 3.12 | 2.11.0+cu130 | **✅ MESA WORKING** (NewtNewt/MESA + cloned `mesa-repo` for custom UNetDEMConditionModel). Diffusers 0.38. ~7 it/s on 5090. |
| `ComfyUI/venv` | `D:\assets\animators\ComfyUI\` | 3.12 | 2.11.0+cu130 | **✅ FLUX.2-klein-4B + Phase 9 universal host foundation.** Server runs at http://127.0.0.1:8188. Current custom nodes are minimal (`websocket_image_save.py` only); Phase 9 workflow lanes are dry-run-ready until Hunyuan3D/IP-Adapter/F5/Wan/BiRefNet/Depth nodes are installed. |
| `materialanything` | WSL `/opt/miniconda3/envs/` | 3.10 | 2.9.1+cu130 | **🟡 Material Anything mesh path runs but is low-quality.** kaolin 0.18 source-built, pytorch3d 0.7.9 with pulsar removed, 8.6 GB MA weights + 5.4 GB ControlNet depth + 25 GB SD2-inpainting mirror. Use `material_anything_adapter.py` only as an experimental mesh-texture baseline; `ma_image2pbr.py` is broken for flat 2D textures. |
| Windows system Python 3.12 | `C:\Program Files\Python312\` | 3.12 | 2.11.0+cpu (acquired by diffusers install) | Wrapper scripts (preprocess, bake, pack). CPU-only torch is harmless here. |

---

## 5. Hardware

- **GPU**: RTX 5090 Laptop, sm_120 (Blackwell), 24 GB VRAM
- **Driver**: 592.01 / CUDA 13.1 runtime (backward-compatible with cu128/cu130 toolkits)
- **Disk**: D: (~140 GB free, where everything lives) + C: (smaller, holds default HuggingFace cache)
- **WSL2**: Ubuntu 24.04 LTS at `D:\wsl\ubuntu24\ext4.vhdx`

---

## 6. Build scripts (for reproducibility)

All in `D:\wsl\`:

| Script | What it does |
|---|---|
| `install-conda.sh` | Miniconda inside WSL at `/opt/miniconda3` |
| `install-aam.sh` | Set up AnimateAnyMesh env |
| `install-pytorch3d-v4.sh` | Build pytorch3d 0.7.9 from source w/ pulsar removed |
| `stub-pulsar.sh` | Strip remaining pulsar refs in installed pytorch3d |
| `download-checkpoints.sh` | Pull AnimateAnyMesh weights from Google Drive |
| `install-magicart.sh` | Set up MagicArticulate env |
| `install-riganything.sh` | Set up RigAnything env |
| `download-rigger-weights.sh` | Pull MagicArticulate + RigAnything HF weights |
| `clone-magicart-env.sh` | Clone `magicarti` → `magicarti-flash` for isolated flash_attn |
| `build-flash-attn.sh` | Source-build flash_attn 2.8.3 with sm_120 kernels (~60 min) |

---

## 7. Quick reference — what tool for what job

| You want to... | Use this |
|---|---|
| Generate a 3D mesh from an image | `meshy/generate.py` (cloud) or Trellis2 (local) |
| Clean / decimate / fix a high-poly mesh | `meshy/preprocess.py` |
| Prep a mesh for **Mixamo upload** | `meshy/glb_to_fbx.py` |
| **Auto-rig a humanoid with motion library** | Mixamo (web, free, requires manual upload) |
| Auto-rig anything (creatures, quadrupeds, etc.) | RigAnything (fast) > SkinTokens (best) > MagicArticulate (skeleton only) |
| Animate a static mesh from text | AnimateAnyMesh |
| Generate custom AI motion for a Mixamo-rigged char | hy-motion-fbx-exporter |
| Run multiple animations on multiple meshes | `meshy/batch_animate.py` (just AAM) or `meshy/batch_pipeline.py` (full chain) |
| Render an animated mesh to PNG sprite frames | `meshy/bake.py` |
| Pack frames into a sprite sheet | `meshy/pack_sheet.py` |
| Convert sprites to pixel-art style | `meshy/pixel_art.py` |
| Render a still preview of any GLB | `meshy/render_preview.py` |
| Render a rigged GLB with bones visible | `meshy/render_rig.py` |
| **Generate a coherent biome texture kit** (one command) | `pipelines/textures/kit_generator.py --kit highland_ruins --quality default --pyramid` |
| **Generate an AAA texture from a prompt** (one command) | `pipelines/textures/aaa_texture.py --prompt "..." --id <name> --category <cat> --quality default` |
| Add a detail layer to an existing material | `pipelines/textures/detail_pyramid.py --macro world/textures/library/<id>` |
| Render a material with HDRI lighting | `pipelines/textures/blender_preview.py --material <dir> --hdri sunset` |
| Generate just the FLUX albedo (seam-aware) | `pipelines/textures/flux_seamless.py --prompt "..." --id <name>` |
| Run N variants and pick best | `pipelines/textures/variant_select.py --prompt "..." --id <name> --variants 4` |
| Strip baked shadows from albedo (de-light) | `pipelines/textures/delight.py --material <dir> --strength 0.6` |
| Real PBR estimation from albedo | `pipelines/textures/stablematerials_image2pbr.py --input albedo.png --out <dir> --id <name> --mode standard` |
| Upscale 1K → 2K/4K with seam preserved | `pipelines/textures/flux_upscale.py --material <dir> --target 2048` |
| Lock new texture to a kit's palette | `pipelines/textures/palette_lock.py --kit <name> --anchor <id> --add "prompt:id:cat"` |
| Real Cycles PBR render (lit sphere + tile plane) | `pipelines/textures/blender_preview.py --material <dir>` |
| Score a texture's seams + sanity | `pipelines/textures/texture_qa.py --material <dir>` |
| Fix tileable seams deterministically | `pipelines/textures/seam_repair.py --material <dir>` |
| Pack a material for Terrain3D channel format | `pipelines/textures/pack_terrain3d.py --material <dir>` |
| Process v1 (heuristic, legacy) | `pipelines/textures/process_texture.py` |
| Generate a heightmap (v1, single PNG) | `pipelines/terrain/generate_heightmap.py` |
| Generate a full terrain bundle (v2) | `pipelines/terrain/terrain_bundle.py --id <name> --biome <preset>` |
| Import a real-world DEM | `pipelines/terrain/import_dem.py --source mapzen --mapzen-tile Z X Y --id <name>` |
| Build a world-scale map | `worldengine world -s SEED -n NAME --gs -r` then `worldengine_to_bundle.py --we-dir <dir> --id <name>` |
| Generate text → DEM heightmap with AI | `pipelines/terrain/mesa_terrain.py --prompt "..." --id <name>` (mesa-env) |
| Apply hydraulic erosion to terrain | `terrain_bundle.py --erosion-mode hydraulic` (Landlab) |
| Apply particle/droplet erosion | `pipelines/terrain/particle_erosion.py --bundle <dir>` |
| Generate a procedural Godot shader from a request JSON | `art_lab/tools/shader_compile_preview.py --request <name>.request.json` |
| Batch-explore + score N shader variants | `art_lab/tools/shader_batch_review.py --batch-id <name> --count 80 --intent "..."` |
| Evolve shader variants toward references | `art_lab/tools/shader_evolve.py --reference art_lab/shaders/reference_sets/<name> --batch-id <name> --population 36 --generations 5` |
| Generate a layered world map (rivers/factions/labels) | `art_lab/maps/generators/generate_world_map.py --id <name> --size 1024 --seed 7` |
| Compile a biome dressing kit | `art_lab/biomes/tools/dress_biome.py --kit <kit_id> --terrain <terrain_id> --map <map_id> --id <out_id>` |
| **Generate a coherent multi-biome world** (synthetic) | `art_lab/biomes/tools/world_biome_engine.py --id <name> --biomes lava_field,ice_cavern,mana_crystal,grassland --size 1024 --seed 7` |
| **Multi-biome world on a real DEM** | `art_lab/biomes/tools/world_biome_engine.py --id <name> --biomes ... --base-heightmap pipelines/terrain/output/<dem_id>/height_16.png --size 1024` |
| Zoom into a world chunk for playable terrain | `art_lab/biomes/tools/region_zoom.py --world <world_id> --bbox X0 Y0 X1 Y1 --id <region_id> --size 1024` |
| **Bind biomes to AAA texture sets** (auto-generates missing) | `pipelines/textures/biome_texture_bind.py --world world/worlds/<id> --quality default` |
| **Build the biome splat for a world** | `pipelines/terrain/biome_splat.py --world world/worlds/<id>` |
| **Stage a biome world into a Godot 4.5 project** | `pipelines/godot_export/stage_biome_terrain.py --world world/worlds/<id> --project <godot_project_path>` |
| **Stage walkable test scene** (HeightMapShape3D + CharacterBody3D) | `pipelines/godot_export/stage_biome_terrain.py --world world/worlds/<id> --project <godot_project_path> --walkable` |
| **Stage 2D vs 2.5D comparison scenes** (top-down ortho + iso ortho) | `pipelines/godot_export/stage_biome_terrain.py --world world/worlds/<id> --project <godot_project_path> --cameras` |
| **Build biome scatter (10k+ MultiMesh instances)** | `pipelines/godot_export/stage_biome_scatter.py --world world/worlds/<id> --project <godot_project_path> --max-instances 800` |
| **One-command region (DEM → biome → AAA → scatter → 3 Godot scenes)** | `pipelines/terrain/region_pipeline.py --preset bryce_hoodoo --style spired --strength 1.5 --biomes mana_crystal,grassland,grassland,grassland --id spire_v1 --project <project>` |
| **Apply fantasy edit to a heightmap** | `pipelines/terrain/dem_fantasy_edit.py --in <bundle>/height_16.png --out <out>.png --style mythic --strength 1.2` |
| **Bulk-pull DEMs from wishlist** (walks data_wishlist.json) | `pipelines/terrain/bulk_pull.py --tier premium --limit 5` (drop --limit for all). Tracks daily quota in `~/.opentopo_calls.jsonl`. |
| **Generate 300 random unknown regions** | `pipelines/terrain/mystery_sampler.py --count 300 --seed 42 --out art_lab/biomes/data_wishlist_mystery.json` |
| **Search OT catalog for a bbox** | `pipelines/terrain/catalog_search.py --bbox -112.20 37.55 -112.00 37.75` (no API quota cost; lists all available datasets) |
| **Pull US 10m LiDAR-grade** | `pipelines/terrain/import_dem.py --id <name> --bbox W S E N --dataset USGS10m --size 1024` (verified working 2026-05-06 on Yosemite) |
| **Pull US 1m LiDAR (OT+ tier)** | `pipelines/terrain/import_dem.py --id <name> --bbox W S E N --dataset USGS1m --size 1024` (verified Half Dome — 1712×1717 px of 1m granite) |
| **Tile-stitch a huge DEM** | `pipelines/terrain/tile_stitch.py --id <name> --bbox W S E N --dataset USGS1m --rows 3 --cols 3 --size 4096` (verified Yosemite 2×2 USGS10m, seamless) |
| Auto-PBR-texture a 3D mesh (mesh-driven MA) | `pipelines/textures/material_anything_adapter.py --mesh <glb> --prompt "..." --id <name>` |
| Export anything to Godot 4.5 | `pipelines/godot_export/export_godot.py --type {pbr_material,terrain,sprite_sheet,rigged_glb} --src <dir> --out <dir>` |
| Batch-generate environment props | `pipelines/props/generate_props.py` |
