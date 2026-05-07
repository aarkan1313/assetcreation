# Pipeline Directory

Live status of every pipeline, tool, and workflow in `D:\assets\`. Updated 2026-05-07 (post Phase 11 props + Phase 12 audio + docs/audits/AUDIT_2026_05_07.md reconciliation).

**Reframe (2026-05-06 PM):** the assets being produced today are mostly throwaway proofs of pipeline correctness — except possibly the characters. The point is **figuring out which pipelines work**, not building a content library. Real production content gets authored later, against pipelines that already proved themselves. Quality bar still high; volume bar dropped to "enough to prove the pipeline."

**Phase 11 props deep-dive complete (2026-05-06 PM).** HY3D-2.1 + Trellis2 both proven end-to-end on RTX 5090 / cu130, with a 4×4 quality sweep on the same Egyptian-obelisk concept. **Trellis2 is now the default AI route for props.** HY3D kept as ComfyUI-integration fallback for biome scatter authoring. **Postprocess orchestrator landed** (`pipelines/props/postprocess_ai_route.py`) — one command takes any AI-route GLB through preprocess → LOD chain → CoACD collision → PBR bind → validate → Godot export. Verified end-to-end on `obelisk_egyptian_a04`. Phase 11C scene-integration (drop into a real Godot biome scene) deferred — gated on worldgen v2 stabilizing. See `world/props/ai_routes/AB_hy3d_vs_trellis2_2026_05_06.md`.

**Phase 12 audio deep-dive complete (2026-05-06 PM).** Stable Audio Open 1.0 (1.21B) flipped from dry-run-silent to **real GPU bake on all 10 biomes**: 142 WAVs / 56 MB at 44.1 kHz mono, LUFS-normalized (-28 dBFS bed_drone, -30 dBFS bed_air, -22 dBFS wildlife peak, -20 dBFS distant_event peak). 740s wall-clock (12 min) for the full factory pack. 2 patches: local-path loader + large-only recipe. See `docs/handoffs/HANDOFF_phase12_audio_2026_05_06.md`.

**Worldgen status note:** worldgen v1 broke late on 2026-05-06; rebuild active at `pipelines/worldgen_v2/` (milestone 1 = terrain only, scatter/props/2D/iso renderers/multi-DEM stitching deliberately excluded for the rebuild). Outputs land at `D:\assets\worldgen2\`. See `pipelines/worldgen_v2/README.md` and `docs/superpowers/specs/2026-05-06-worldgen-v2-design.md`. Scene integration for both Phase 11 props and Phase 12 audio is gated on v2 reaching a usable scene-target state.

**Doc cleanup (2026-05-06 PM):** archived 13 superseded handoffs + 2 old audits + 1 orphan research blob to `_archive/`. Root has the current handoffs + reference/index docs + `docs/audits/AUDIT_2026_05_07.md`. See [DOCS_INDEX.md](DOCS_INDEX.md) for the canonical map.

**At a glance:**
- **22+ working pipelines.** Phase 11 (props) + Phase 12 (audio) deep-dives complete; both at A grade. Props v2+ → v3 with AI routes, Audio v3 → real Stable Audio bake, UI v3 (D), VFX v2 (C2), Game Data v2 (F2 + AB1), Phase 9 (open-weights/ComfyUI foundation).
- **VFX v2 critical bug found and fixed mid-flight** — exporters were copying frames per-effect × per-target across runs, exploding to **586,545 files / ~580 GB**. Rewrite eliminated copies (artifacts referenced at catalog paths via `res://vfx/<kind>/<id>/...`). Now ~78 MB total VFX disk, **57 effects total** (46 under `vfx/catalog/` + 11 migrated under `vfx/migrated_from_spell_lab/`). Bug-found-and-fixed pattern matches docs/audits/REVIEW.md discipline.
- AAA texture pipeline: seam grade A / 0.00037 (`biome_mana_crystal`). **35 dirs in `world/textures/library/`**, of which 21 have `aaa_pipeline.json` markers. Audit-flagged ambiguity; current AAA-pipeline-stamped count is 21.
- **One-command region pipeline** (`region_pipeline.py`) chains real DEM → fantasy edit → biome paint → splat → AAA texture bind → MultiMesh scatter → 3 Godot scenes. **10 biomes** (lava/ice/mana/grass/forest/desert/tundra/swamp/charred/underwater). **NOTE:** worldgen v1 broke 2026-05-06; rebuild lives at `pipelines/worldgen_v2/` (milestone 1, terrain-only). region_pipeline.py is v1 and may not produce usable output until v2 stabilizes.
- **Declarative region configs** (`region.config.v1`) at `art_lab/biomes/regions/*.region.json`. `region_pipeline_from_config.py` walks one or many configs, validates schema, and dispatches. Pattern modeled on `meshy/batch_pipeline.py`. See [art_lab/biomes/regions/README.md](art_lab/biomes/regions/README.md).
- **4 swap-points** in the worldgen v1 pipeline (Phase 1, 2026-05-06): shader registry, splat mode, terrain extents (`--use-real-extents`), per-region JSON config. See [_archive/handoffs_2026_05_06/HANDOFF_2026_05_06_PM5_worldgen_swappoints.md](_archive/handoffs_2026_05_06/HANDOFF_2026_05_06_PM5_worldgen_swappoints.md). v2 may carry these forward or replace them.
- **Data infra live on OT+**: 172 named regions + 300 unknowns + **222 cached DEMs**. (D: drive at 100% earlier on 2026-05-06; pruner remains Tier 2 polish.)
- **Cross-pipeline link validator** (`pipelines/_meta/link_validator.py`): MISSING: 0; indexes **51 props**, 135 icons, 57 vfx effects, 39 sfx. After library-only filter (55 entries): UNUSED 91 icons / 47 vfx / 31 sfx genuinely unbound. Next sweep target = wire game_data references or expand the library-only allowlist.
- **Audio ambience: 142 real Stable Audio Open WAVs across 10 biomes / 56 MB.** Replaces the dry-run silence. `dry_run=false` confirmed in `audio/ambience/ambience_summary.json`.
- **Phase 11C scene-integration NOT yet wired**: hero prop is at `world/props/library/obelisk_egyptian_a04/` and Godot-importable but not yet instanced into a biome scene. Gated on worldgen v2 producing a usable scene target.
- **Cross-pipeline seams partly proven**: `stage_biome_scatter.py` v3 prop_pool path landed (Phase 10A), spawn-on-terrain raycast landed, scene_prop scatter path still pending. One-button "biome + props + ambience + VFX + HUD" demo NOT yet built — that's the canonical proof-of-factory demo still owed.
- **The honest drag now**: worldgen v2 stabilization (gates Phase 11C and the seams demo); scene_prop scatter path; one-button composition demo; Phase 12 ambience re-export to Godot import format (`audio/godot/` currently has stale v3 audio); pipelines not yet built (cinematics / quest schema / save-load / localization / performance budgets / cross-pipeline gallery); remaining GPU flips (FLUX/LoRA, Hunyuan3D-Omni, Taichi/Warp/PhiFlow, F5-TTS, vLLM, Wan, YuE — Stable Audio Open and Trellis2 done in Phase 11/12).

**Quick links:**
- Region from preset (one command): `pipelines/terrain/region_pipeline.py --preset bryce_hoodoo --style spired --strength 1.5 --biomes mana_crystal,mana_crystal,grassland,grassland --id spire_garden --project <godot_project>`
- AAA texture: `pipelines/textures/aaa_texture.py --prompt "..." --id <name> --quality default`
- Terrain bundle (raw): `pipelines/terrain/terrain_bundle.py --id <name> --biome mountains`
- World map (political): `art_lab/maps/generators/generate_world_map.py --id <name> --size 1024`
- Bulk DEM pull: `pipelines/terrain/bulk_pull.py --tier premium`
- Cross-pipeline link check: `python pipelines/_meta/link_validator.py` (game_data ↔ ui/vfx/audio/props reference resolver)

**Legend:**
- ✅ tested working — produced a real output we kept
- 🟢 installed + smoke verified — code paths exercised but no production output yet
- 🟡 partial — env up, hits a known blocker, fixable
- 🟥 broken / blocked on user input
- ⏸️ stubbed / awaiting research
- ⏹️ deferred / superseded

Cross-refs: [TOOLS_INDEX.md](TOOLS_INDEX.md) | [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md) | [docs/plans/ROADMAP.md](docs/plans/ROADMAP.md) | [docs/audits/REVIEW.md](docs/audits/REVIEW.md) | [docs/plans/RESEARCH_HANDOFF.md](docs/plans/RESEARCH_HANDOFF.md) | [docs/audits/AUDIT_2026_05_07.md](docs/audits/AUDIT_2026_05_07.md)

---

## 1. Character pipeline (mature)

| Stage | Tool | Status | Output |
|---|---|---|---|
| Image → 3D | Meshy API | ✅ | 33 GLBs in `meshy/output/` |
| Mesh preprocess | Blender headless via [preprocess.py](meshy/preprocess.py) | ✅ | `meshy/preprocessed/` (33 cleaned) |
| Mixamo prep | [glb_to_fbx.py](meshy/glb_to_fbx.py) | ✅ | `meshy/mixamo_ready/` |
| Auto-rig (humanoid) | Mixamo (web upload) | ✅ verified workflow | manual |
| Auto-rig (creatures) | [SkinTokens](animators/SkinTokens/) | ✅ | giraffe + goblin + witch rigged |
| Auto-rig (fast) | [RigAnything](animators/RigAnything/) | ✅ | goblin + witch in ~5s each |
| Auto-rig (skeleton-only) | [MagicArticulate](animators/MagicArticulate/) | ✅ | sm_120 flash_attn 2.8.3 source-built |
| Auto-rig (Mixamo alt) | [Mesh2Motion](animators/mesh2motion-app/) | 🟢 installed, manual UI | localhost:5173 |
| Auto-rig (procedural) | [SKAVA](_archive/orphan_root_2026_05_06/skava_auto_rigger__init__.py) | ⏸️ untested (archived 2026-05-06) | — |
| Animate from text | [AnimateAnyMesh](animators/AnimateAnyMesh/) | ✅ | 16-frame shape-key FBX (dragon flies) |
| Animate (text + Mixamo rig) | [hy-motion-fbx-exporter](animators/hy-motion-fbx-exporter/) | 🟡 weights deferred | env ready |
| Backup image-to-3D | [Trellis2](animators/Trellis2/) | 🟢 imports verified, no actual gen | for when Meshy credits run out |
| Sprite bake | [bake.py](meshy/bake.py) → Blender | ✅ | N angles × M frames PNG |
| Atlas pack | [pack_sheet.py](meshy/pack_sheet.py) | ✅ | atlas + JSON |
| Pixel-art filter | [pixel_art.py](meshy/pixel_art.py) | ✅ | shared-palette quantize |
| Batch orchestration | [batch_pipeline.py](meshy/batch_pipeline.py) | ✅ | 30/30 preprocess in 406s |
| Render previews | [render_preview.py](meshy/render_preview.py), [render_rig.py](meshy/render_rig.py) | ✅ | 4-view + bone overlay |

**Verdict:** mature, full chain proven on multiple assets.

---

## 2. Terrain pipeline

| Tool | Status | Output | Notes |
|---|---|---|---|
| [generate_heightmap.py](pipelines/terrain/generate_heightmap.py) v1 | ✅ | single PNG | FBM + biome shaping + thermal erode |
| [terrain_bundle.py](pipelines/terrain/terrain_bundle.py) v2 | ✅ | full Godot folder | smoketest_a (256, mountains) verified |
| [fastnoise_height.py](pipelines/terrain/fastnoise_height.py) | ✅ | bundle | OpenSimplex2/Cellular/Perlin × FBm/Ridged/PingPong; fastnoise_ridged tested |
| [import_dem.py](pipelines/terrain/import_dem.py) | ✅ | bundle | Mapzen tile (881-2613m alpine) verified |
| OpenTopography (`import_dem.py --source opentopo`) | ✅ | bundle | API key set in Windows User env. **13 presets** verified — utah_canyon, colorado_alpine, appalachian, alps_dolomites, iceland_volcanic, sahara_dunes, **norwegian_fjord, nz_glacier, bryce_hoodoo, scottish_highlands, patagonian_spires, moroccan_atlas, japanese_alps**. Auto-selects AW3D30 dataset for high-latitude presets (>60° N/S). Override with `--dataset SRTMGL3\|AW3D30\|COP30\|COP90\|EU_DTM`. |
| [worldengine_to_bundle.py](pipelines/terrain/worldengine_to_bundle.py) | ✅ | bundle | worldengine_a (256x256 world) verified |
| [particle_erosion.py](pipelines/terrain/particle_erosion.py) | ✅ | refined height | 5k droplets on smoketest_a verified |
| Landlab hydraulic erosion (in `terrain_bundle.py`) | ✅ | bundle | smoketest_hydraulic (50 steps) verified |
| [mesa_terrain.py](pipelines/terrain/mesa_terrain.py) | ✅ **PROVEN** | optical + DEM + bundle | mesa_smoketest + mesa_badlands verified, ~7 it/s on 5090 |

**Verdict:** ALL terrain tools online. Six independent input modes (synthetic/noise/DEM/world/AI/erosion), one bundle contract, one Godot exporter target.

**Future research G prescribes:** add Mapgen4 + Mapshaper for **map screen** (different problem from heightmaps — political/labels/factions overlay). See section 8.

---

## 3. Texture pipeline — AAA self-generated stack

**Master orchestrator** chains every stage with a quality gate.

```
prompt
  → variant generation (N seeds × seamless FLUX = N candidates)
  → pick best by seam score
  → de-lighting pass (LAB-space large-blur subtract)
  → StableMaterials single-image PBR (real diffusion estimation; derive_pbr_v2 fallback)
  → seam repair on derived maps (PatchMatch, all-maps synced)
  → texture QA (seam grade + sphere/plane preview + sanity)
  → Blender Cycles render (lit sphere + tiled plane at grazing angle)
  → quality gate: default seam ≤ 0.010, strict seam ≤ 0.005
  → catalog manifest + provenance
```

| Tool | Status | Notes |
|---|---|---|
| [kit_generator.py](pipelines/textures/kit_generator.py) | ✅ **6 textures in 3.5 min** | builtin biomes: highland_ruins, frozen_volcanic, desert_temple, forest_floor; or custom JSON recipe; auto palette-lock + HDRI render + optional pyramid |
| [aaa_texture.py](pipelines/textures/aaa_texture.py) | ✅ **working with real PBR** | `default` and `strict` route through StableMaterials (real diffusion model). `fast` uses derive_pbr_v2 heuristic. Verified cobblestone seam grade B (0.00329). |
| [detail_pyramid.py](pipelines/textures/detail_pyramid.py) | ✅ | macro+detail pair generator; saves `detail_pair.json` linking macro to detail; pairs with `macro_detail_v1.gdshader` |
| [flux_seamless.py](pipelines/textures/flux_seamless.py) | ✅ | offset-shift + img2img heal; 3× seam improvement |
| [variant_select.py](pipelines/textures/variant_select.py) | ✅ | N seeds, pick best by seam score |
| [delight.py](pipelines/textures/delight.py) | ✅ | LAB large-blur, removes baked shadows from albedo |
| [ma_image2pbr.py](pipelines/textures/ma_image2pbr.py) | 🟥 **broken on 2D textures** | MA model needs multi-view 3D mesh consolidation; on a single flat image it outputs near-uniform grey. Replaced by `stablematerials_image2pbr.py` for 2D, `material_anything_adapter.py` for 3D meshes. |
| [stablematerials_image2pbr.py](pipelines/textures/stablematerials_image2pbr.py) | ✅ **Real single-image-to-PBR** | `gvecchio/StableMaterials` (OpenRAIL, ungated). LCM 4-step or standard 50-step. Outputs tileable basecolor/normal/height/roughness/metallic + derived AO. Default backend for `aaa_texture.py --quality default/strict`. |
| [flux_upscale.py](pipelines/textures/flux_upscale.py) | ✅ 2K verified | 1K → 2K → 4K via low-denoise FLUX heal; preserves tiling |
| [palette_lock.py](pipelines/textures/palette_lock.py) | ✅ | LAB hist-match new textures to anchor → biome-coherent kits |
| [blender_preview.py](pipelines/textures/blender_preview.py) | ✅ | Cycles render: lit sphere + tiled plane + side-by-side combo. **HDRI** (8 envs: studio, courtyard, forest, sunrise, sunset, city, interior, night). |
| [seam_repair.py](pipelines/textures/seam_repair.py) | ✅ | PatchMatch synced across all maps |
| [texture_qa.py](pipelines/textures/texture_qa.py) | ✅ | seam A/B/C/D grade, value-range sanity |
| [pack_terrain3d.py](pipelines/textures/pack_terrain3d.py) | ✅ | RGBA channel pack for Terrain3D |
| [comfy_generate.py](pipelines/textures/comfy_generate.py) | ✅ | single-shot FLUX.2 + heuristic PBR (legacy/fast path) |
| [derive_pbr_v2.py](pipelines/textures/derive_pbr_v2.py) | ✅ | heuristic PBR (used by `--quality fast`) |
| [process_texture.py](pipelines/textures/process_texture.py), [make_test_texture.py](pipelines/textures/make_test_texture.py) | ⏸️ | v1 legacy |
| [ambientcg_fetch.py](pipelines/textures/ambientcg_fetch.py), [polyhaven_fetch.py](pipelines/textures/polyhaven_fetch.py) | ⏸️ | CC0 ingesters; **deprecated** per user — we self-generate |
| [patina_adapter.py](pipelines/textures/patina_adapter.py) | 🟥 needs `FAL_KEY` | optional cloud alternative |
| [material_anything_adapter.py](pipelines/textures/material_anything_adapter.py) | 🟡 **runs but low quality** | Mesh-driven full MA pipeline (10 viewpoints over ~10 min on 5090). Verified end-to-end on Meshy goblin: produces 11 final UV maps, mesh imports cleanly, but albedo is bleached and prompt has weak effect. Useful only as a baseline texture for hand-painting, not as final PBR. |
| [render_ma_mesh.py](pipelines/textures/render_ma_mesh.py) | ✅ | Blender Cycles render of MA's textured-mesh output under HDRI for visual QA. |

**Quality presets:**
- `--quality fast` — 2 variants, derive_pbr_v2, seam C+ accepted
- `--quality default` — 4 variants, StableMaterials standard mode, seam B+ required (≤ 0.010)
- `--quality strict` — 6 variants, StableMaterials standard mode, seam A required (≤ 0.005)

(Earlier MA-i2p paths were broken: MA needs 3D mesh consolidation across N viewpoints. Single 2D textures collapse to flat grey. `fast` uses the deterministic `derive_pbr_v2` heuristic; `default`/`strict` use StableMaterials with a heuristic fallback.)

**Run:**
```powershell
python pipelines\textures\aaa_texture.py --prompt "weathered cobblestone street, mossy gaps" --id cobblestone_aaa --category Bricks --quality default
```

**Verdict:** Self-generated AAA-grade textures from prompt alone. No CC0 library dependency.

---

## 4. Godot exporter (cross-cutting)

| Asset type | Source | Status |
|---|---|---|
| pbr_material | `world/textures/library/<id>/` | ✅ Rock035 packaged |
| terrain | `pipelines/terrain/output/<id>/` | ✅ smoketest_a packaged |
| sprite_sheet | character atlas folder | 🟢 stub written, no real test |
| rigged_glb | rigged GLB | 🟢 stub written, no real test |

`pipelines/godot_export/export_godot.py` — 4 asset types, drops to `D:/assets/godot_pack/<cat>/<id>/`.

---

## 5. Animator/Generator inventory

| Tool | Env | Status |
|---|---|---|
| Meshy API | `meshy/config.json` | ✅ ~30 credits left |
| Trellis2 | `animators/Trellis2/venv` | 🟢 imports OK |
| AnimateAnyMesh | WSL conda `animateanymesh` | ✅ |
| SkinTokens | `animators/SkinTokens/.venv` | ✅ |
| RigAnything | WSL conda `riganything` | ✅ |
| MagicArticulate | WSL conda `magicarti-flash` | ✅ flash_attn 2.8.3 sm_120 |
| hy-motion | `animators/hy-motion-fbx-exporter/.venv` | 🟡 weights deferred |
| Mesh2Motion | Node 24 web app | 🟢 installed, manual UI |
| **MESA** (terrain AI) | `animators/mesa-env/venv` + `animators/mesa-repo/` | ✅ **WORKING** |
| **ComfyUI** | `animators/ComfyUI/venv` | ✅ **WORKING** as universal headless host foundation: FLUX.2-klein-4B texture path already live; Phase 9 `pipelines/_meta/comfy_runner.py` now plans/submits/polls/downloads generic workflows. Current custom nodes are minimal (`websocket_image_save.py` only), so Hunyuan3D/F5/Wan/IP-Adapter/BiRefNet/Depth workflows are dry-run-ready until node packs are installed. |
| **Material Anything** | WSL conda `materialanything` | ✅ **WORKING** — full mesh-driven PBR generation verified (rusty robot demo, 430 files, 151 MB output) |
| Anytop | cloned only | ⏸️ |
| SKAVA | Blender addon | ⏸️ |

---

## 6. Formerly-vapor pipelines — built 2026-05-06 PM

| Pipeline | Local state | Demo | Handoff | Research |
|---|---|---|---|---|
| **Game Data** | ✅ working v1.5+ — Pydantic schemas + synth/OpenAI/Claude gen + balance-target constrained generation + kill-dummy sim + migrations + DuckDB reports + Yarn link validation + local-LLM dry-run adapter + Godot `.tres` codegen | 5 items + 3 abilities + 2 factions + 2 NPCs + 2 lore terms; 14 `.tres` files; round-trip 14/14 passed; DuckDB rows items=5 abilities=3 faction_links=4; link validator missing refs=0 | [docs/handoffs/HANDOFF_game_data_v2_2026_05_06.md](docs/handoffs/HANDOFF_game_data_v2_2026_05_06.md) + [docs/handoffs/HANDOFF_audit_expand_2026_05_06.md](docs/handoffs/HANDOFF_audit_expand_2026_05_06.md) | ✅ research/F_game_data.md + research/F2_game_data_balance_sim.md |
| **Audio** | ✅ **v3 SOTA push complete** — v2 spine (synth_sfx + process_audio + audio_qa + eleven_sfx + local_audio_open + biome_ambience + ambience_pack + cc0_ingest + synth_sfx_extended + pyloudnorm) + phase-aware `loop_detect.py` (xcorr + phase-coherence + env metric; SSD legacy preserved) + `ffmpeg_decode.py` optional helper (Freesound MP3 + ambience >47s, gated on host ffmpeg) + `openai_tts.py` adapter (plan-only default; `--run` requires `OPENAI_API_KEY` + `--max-cost-usd` cap; 9 voices, gpt-4o-mini-tts default) + 6 new biome recipes (forest/desert/tundra/swamp/charred_wasteland/underwater = full **10 registered biomes covered**) + `gallery.py` static HTML browser (autoplay + spectrogram modal + LUFS column + filter/sort) + `lint_audio.py` strict-audio gating wrapper (unused / mismatch / bus-sanity / ambience-coverage; mirrors UI v3's `lint_icons` pattern) + `suggest_sfx_for_record.py` cosine-tag matcher (record→sfx top-K + sfx_id_patch.jsonl) + HRTF Godot wrapper recipe (`hrtf_resonance.json` + `SpatialEmitter.gd` fallback + `HRTFVerify.gd` headless smoke) + `adaptive_music.py` orchestrator scaffold (4 example tracks × placeholder stems × `track.tscn` × `AdaptiveMusicTrack.gd` controller with intensity/state/crossfade) + `AmbienceDensityAutoload.gd` per-zone density wire + `zone_overrides.json` schema (9 example zones across all 10 biomes) + `LUFS_AUTHORING_GUIDE.md` single source of truth + audio tool decision tree in pipelines/audio/README.md. | **39 sounds / 112 variants** + **10 biomes / 142 ambience stems** + **4 music tracks scaffolded** (15 placeholder stems); gallery.html ≈ 80 KB indexes 264 rows; lint_audio coverage=10/10 ✓ (registry → recipe → pack); sfx suggester 4 strong matches on existing dataset + surfaces real catalogue gap (no frost/cold school sfx); 10/10 pipelines/audio/*.py py_compile clean; link_validator MISSING=none ✓. | [docs/handoffs/HANDOFF_phase12_audio_2026_05_06.md](docs/handoffs/HANDOFF_phase12_audio_2026_05_06.md) (latest, real Stable Audio bake) + [_archive/handoffs_2026_05_06/HANDOFF_audio_v3_2026_05_06.md](_archive/handoffs_2026_05_06/HANDOFF_audio_v3_2026_05_06.md) (v3 forensics, archived) + older v1/v2 in archive | ✅ research/E_audio.md + research/E2_audio_local_ambience.md |
| **UI / Icons** | ✅ **v3 SOTA push complete** — v2 spine + `freelib_curated_slugs.txt` 190-slug game-icons.net allowlist + `--filter-by-list` flag + new `--source mit-iso-libs` lane (Lucide ISC / Phosphor MIT / Tabler MIT, 24/19/22 curated UI primitives via jsDelivr CDN templates) + `pixellab_icons.py` PixelLab cloud adapter (plan-only by default; gated on PIXELLAB_API_KEY + `--max-cost-usd` cap) + `suggest_icon_for_record.py` cosine-on-token-sets matcher (record→icon top-K + suggestions.md + icon_id_patch.jsonl) + `lint_icons.py` strict-icons gating wrapper around link_validator (unused / missing-tags / record↔icon mismatch / RTL flag review; `--strict` exits 1) + 24 HUD test fixtures via `--fixtures` (4 factions × 6 scenarios) + 4 new ornament drawers (chains/runes/vines/fangs; doubles ornament library to 8) + `lora_train.py` plan-only kohya-ss/sd-scripts scaffold (license-correct dataset prep + train_command.sh) + `vtracer_roundtrip.py` raster→SVG round-trip (`--annotate-manifest` writes svg_traced paths) + `ui/palettes/PALETTE_AUTHOR_GUIDE.md` + UI tool decision tree in pipelines/ui/README.md. | **135 icons** (37 synth + 98 freelib via curated allowlist) + atlas + **20 9-slice elements** (4 bases × 4 palettes; 8 ornaments available) + Theme.tres wiring 60 ext_resources + **4 HUD .tscn** + **28 HUD previews** (4 default + 24 fixtures) + LoRA training scaffold + 17/17 pipelines/ui/*.py py_compile clean; link_validator MISSING=none ✓; lint_icons --strict exits 1 (catalogue ahead of game_data wiring, working as intended). | [docs/handoffs/HANDOFF_ui_v3_2026_05_06.md](docs/handoffs/HANDOFF_ui_v3_2026_05_06.md) (latest) + older v1/v2 in `_archive/handoffs_2026_05_06/` | ✅ research/D_ui.md |
| **VFX** | ✅ **v2 SOTA push complete** — v1 spine (Effect schema + 3 CPU bakers + 2D Godot exporter + spell-lab importer + gallery) + `export_godot_3d.py` (4 export targets: 3d_billboard / decal / mesh_trail / fog_volume) + `baker_volumetric_fog.py` (numpy noise → Texture3D-via-slice-atlas + 7 biome presets) + `MeshTrail3D.gd` runtime (RibbonTrail/TubeTrail wrapper) + `AudioCueBus.gd` autoload (frame_changed → cue_hit signal driven by `manifest.extras.audio_cues`) + `author_grid.py` 24-cell element×archetype generator + `author_damage.py` 12-effect damage/impact catalogue + gallery v2 (filters/search/autoplay) + no-copy exporters (refs frames at catalog paths via `res://`) | **57 effects** (24 element×archetype + 12 damage/impact + 7 biome haze + 3 v1 demo + 11 spell-lab migrated); **39 2D + 43 3D Godot scenes** emitted into per-effect `godot/` subdirs; link_validator MISSING=none ✓ | [docs/handoffs/HANDOFF_vfx_v2_2026_05_06.md](docs/handoffs/HANDOFF_vfx_v2_2026_05_06.md) (latest) + v1 in `_archive/handoffs_2026_05_06/` | ✅ research/C_vfx.md + research/I_vfx_lab_local_audit_and_migration_plan.md + research/C2_vfx_3d_volumetric.md |
| **Props** | ✅ **v3 (Phase 11 deep-dive complete)** — v2 spine (13 procedural recipes; `variation_sweep.py`; `lod_chain.py` 4-tier DECIMATE COLLAPSE; CoACD collision; Godot HLOD; billboard + kit atlases; biome_scatter_rules v3; AAA-PBR binding) **PLUS** Phase 11 AI-route layer: HY3D-2.1 (kijai+visualbruno wrappers, ComfyUI workflow) + Trellis2 (microsoft/TRELLIS.2-4B) both proven end-to-end on cu130 with PBR textures embedded. New shared infra: `ai_route_dispatch.py` (Trellis2-default) + `trellis2_batch.py` (model-load-once batch runner) + wired `trellis2_route.py` + `TRELLIS2_PATCHES.md`. 4×4 quality sweep on Egyptian obelisk — Trellis2 wins visually at every config. | 50 v2 prop records; 4 hero-prop runs (HY3D placeholder/real, Trellis2 real, sweep configs); A/B doc; 8-cell compare sheet at `D:\tmp\sweep_compare_sheet.png`; Trellis2 mid run = 8s postprocess + 23s mesh gen → 194k faces / 2048² PBR | [docs/handoffs/HANDOFF_phase11_props_2026_05_06.md](docs/handoffs/HANDOFF_phase11_props_2026_05_06.md) (latest, AI routes + sweep + dispatcher) + [AB_hy3d_vs_trellis2_2026_05_06.md](world/props/ai_routes/AB_hy3d_vs_trellis2_2026_05_06.md) + [_archive/handoffs_2026_05_06/HANDOFF_props_v2_2026_05_06.md](_archive/handoffs_2026_05_06/HANDOFF_props_v2_2026_05_06.md) (v2 archived) + [TRELLIS2_PATCHES.md](pipelines/props/TRELLIS2_PATCHES.md) | ✅ research/J_props_3d_decoration_pipeline.md + research/J2_props_variation_lod.md |
| **World Art Lab** (G expansion) | ✅ built: shaders, maps, biomes, prop prep (separate work, see § 8a-c) | (existing) | (existing) | ✅ research/G/H/I/J |

**Phase 9 open-weights / ComfyUI lane (2026-05-06):** ✅ dry-run integration foundation shipped. `pipelines/_meta/comfy_runner.py` plus 9 workflow JSONs now support generic Comfy plan/submit/poll/download flows. New/extended lanes: Hunyuan3D props, FLUX/IP-Adapter icons, F5/Kokoro TTS, Wan video + flipbook, vLLM/xgrammar game data, HF surveyor, BiRefNet matting, DepthAnything/GeoWizard depth-normal, HAT-L upscale helper, and YuE pilot. Verification: 12 Phase 9 scripts py_compile clean; all lanes produced dry-run artifacts; no ComfyUI/GPU/cloud call was made. Handoff: [docs/handoffs/HANDOFF_phase9_2026_05_06.md](docs/handoffs/HANDOFF_phase9_2026_05_06.md).

GPU backends for VFX (Taichi / Warp / PhiFlow / LiquidFun) are documented in [pipelines/vfx/GPU_BACKENDS_PLAN.md](pipelines/vfx/GPU_BACKENDS_PLAN.md) — install plan only; not run today because the 5090 is busy with the texture stack.

---

## 7. Research reports

| File | Status |
|---|---|
| [research/A_terrain.md](research/A_terrain.md) | ✅ reviewed, drove terrain v2 buildout |
| [research/B_textures.md](research/B_textures.md) | ✅ reviewed, drove texture pipeline buildout |
| [research/C_vfx.md](research/C_vfx.md) | ✅ reviewed — VFX bake lab plan |
| research/D_ui.md | ⏸️ not back |
| [research/proceduralize_dem.md](research/proceduralize_dem.md) | ✅ **stretch-goal brief** — 4 approaches to learning procedural terrain from the cached real-DEM corpus (statistical fingerprinting, patch quilting, diffusion fine-tune, physics simulation). Parked until catalogue hits ~600 regions. |
| [research/E_audio.md](research/E_audio.md) | ✅ reviewed — ElevenLabs SFX + Kenney + processing spine |
| [research/F_game_data.md](research/F_game_data.md) | ✅ reviewed — Pydantic content compiler |
| [research/G_deep_dive_world_textures_decor_shader.md](research/G_deep_dive_world_textures_decor_shader.md) | ✅ reviewed, drove tonight's Art Lab buildout |
| [research/H_shader_generation_review_pipeline.md](research/H_shader_generation_review_pipeline.md) | ✅ second pass — shader creation/review loop and legacy cauldron integration |
| [research/I_vfx_lab_local_audit_and_migration_plan.md](research/I_vfx_lab_local_audit_and_migration_plan.md) | ✅ second pass — content-first VFX Lab migration from old SpellLab artifacts |
| [research/J_props_3d_decoration_pipeline.md](research/J_props_3d_decoration_pipeline.md) | ✅ second pass — prop kit factory, procedural Blender assets, AI/CC0 ingestion, Godot scatter export |
| [research/deep_report_6_intake_review.md](research/deep_report_6_intake_review.md) | ✅ intake — image-to-handwritten-shader RAG/corpus/Slang/security plan |

### Research takeaways (one line each)

- **C (VFX):** keep Taichi + LiquidFun + PhiFlow + Newton/Warp as primaries; VFX should be a *bake lab* (offline → flipbook/particles/fragments), not a runtime physics rig. SpellLab v2 = canonical artifact contract + replaceable backends.
- **E (audio):** ElevenLabs SFX API (cloud) + Stable Audio Open (local) + Kenney/Sonniss CC0 + ffmpeg/pyloudnorm/librosa processing spine. Same pattern as textures: source/generate → process → QA → Godot export.
- **F (game data):** Pydantic schemas as source of truth → provider-native structured outputs (OpenAI/Claude) wrapped by Instructor → deterministic validation + DuckDB balance reports → Godot `Resource` C# codegen + `.tres` export. JSON is for manufacturing, `.tres` is for shipping.
- **H (shaders):** the best practical path is not a magic AI shader product; it is a constrained shader-template/DSL library, automated non-OCR render scoring, reference matching, and LLM-driven parameter/code mutation.
- **I (VFX local audit):** keep `D:\spell lab` as a research/artifact source, but migrate to a content-first VFX factory where `effect.json` bakes to flipbooks, particle payloads, shader hints, previews, and Godot exports.
- **J (props):** props need a local-first kit factory, not a one-GLB generator. Start with Blender procedural scatter assets, normalize all sources, then test local/open 3D models for medium/hero props; Meshy/cloud APIs are optional baselines only.
- **Deep report 6:** useful for long-term image→handwritten-shader R&D: license-clean corpus, normalized AST/IR, Slang-centered future export, benchmark subsets, and sandbox/security policy. Do not pivot the current Godot template workflow.

---

## 8. Magic / World Art Lab — built from G's prescription

Located at `art_lab/`. Three pillars done tonight:

### 8a. Shader Lab — `art_lab/shaders/` ✅

| Item | Status |
|---|---|
| 5 first-party Godot 4.5 templates: `ring_field_2d`, `beam_lightning_2d`, `dissolve_fire_2d`, `shield_ripple_2d`, `portal_swirl_2d` | ✅ written |
| `shader_compile_preview.py` parameter-driven generator | ✅ smoke tested |
| 5 sample request JSONs (one per template) | ✅ |
| Preview rendering via Godot CLI | ⏸️ needs Godot binary path |

Run: `python art_lab\tools\shader_compile_preview.py --request art_lab\shaders\generated\examples\arcane_shield_ring.request.json`

### 8b. World Map Lab — `art_lab/maps/` ✅

| Item | Status |
|---|---|
| `generate_world_map.py` — pure-Python procedural | ✅ smoke tested |
| Output contract per G: layers/{height,biome,water,rivers,roads,regions,settlements,landmarks,labels,fog_mask} + 5 previews + Godot scene | ✅ all 18 files |
| `mythos_a` test map: 12 settlements, 6 landmarks, 134 rivers, 14 roads, 3 factions | ✅ |
| Mapgen4 / Mapshaper adapters (browser/Node-based for SOTA polish) | ⏸️ |

Run: `python art_lab\maps\generators\generate_world_map.py --id <name> --size 1024 --seed 7`

### 8c. Biome Decoration Lab — `art_lab/biomes/` ✅

| Item | Status |
|---|---|
| Kit JSON schema + 1 reference kit (`mossy_highland_ruins`) | ✅ |
| `dress_biome.py` placement compiler with mask-based blue-noise sampling | ✅ smoke tested |
| Constraints: slope, wetness, shade, landmark proximity, road avoidance, biome | ✅ |
| Per-asset masks, scatter.csv, decals.csv, top-down preview | ✅ |
| Smoke test: 9,818 scatter + 603 decal instances on `smoketest_a` terrain | ✅ |
| Prop Kit Lab prep (`art_lab/props`) | 🟢 local-first contract, 13 recipes, 76 variants planned, 26 CPU decals generated |
| Blender procedural prop generation (rocks, grass cards, ruin blocks) | 🟢 script scaffold + dry-run tested; real Blender smoke pending GPU |
| Real Godot MultiMesh importer plugin | ⏸️ next slice |

Run: `python art_lab\biomes\tools\dress_biome.py --kit mossy_highland_ruins --terrain smoketest_a --map mythos_a --id mossy_x_mythos`

---

### 8f. Region pipeline + data ingestion ✅ NEW (2026-05-06)

End-to-end orchestrator and data infrastructure for pulling real-world DEMs and turning them into playable Godot scenes.

| Item | Status |
|---|---|
| `pipelines/terrain/region_pipeline.py` — one-command DEM-to-Godot orchestrator (DEM → fantasy edit → biome → splat → AAA → scatter → 3 scenes) | ✅ verified end-to-end on Bryce/spired |
| `pipelines/terrain/dem_fantasy_edit.py` — 7 styles: realistic, exaggerated, terraced, sharpened, spired, floating, mythic | ✅ all 7 verified |
| `pipelines/terrain/bulk_pull.py` — walks `data_wishlist.json`, calls `import_dem.py` per region | ✅ tested with --tier standard --limit 1 |
| `pipelines/terrain/mystery_sampler.py` — generates N random worldwide bboxes from interesting strips | ✅ generated 300 mystery regions |
| `pipelines/terrain/source_dems/` — persistent TIFF cache (cache hits make re-runs near-instant) | ✅ 74 TIFFs / ~2.8 GB at audit snapshot |
| `pipelines/terrain/catalog_search.py` — `/otCatalog` client. Lists all available datasets per bbox (no quota cost). Confirms availability before fetch. | ✅ verified on Bryce + Milford Sound |
| `import_dem.py` — full dataset coverage: 23 datasets across `/globaldem` + `/usgsdem` + new `pgc_stac` + `linz_stac` endpoints (regional rasters now wired). Pre-flight bbox-area check. PIL decompression-bomb cap raised to 1B pixels. NoData sentinel sanitization. **Verified working**: COP30, AW3D30, GEBCOIceTopo, USGS10m, **USGS1m (Half Dome — OT+ tier)**, SRTM15Plus, CA_MRDEM_DTM, **ArcticDEM10m (Disko Bay)**, **REMA10m (Mt Erebus)**, **LINZ1m_DTM (Milford Sound, end-to-end Godot scene built)**. | ✅ |
| `fetch_regional_stac.py` — STAC + S3 fetchers for ArcticDEM/REMA (PGC, `s3://pgc-opendata-dems/`) and LINZ NZ 1m (`s3://nz-elevation/`). Bypasses OpenTopography's `/rasterSubmit` job-queue (which requires browser session auth) by reading COGs directly with rasterio windowed-read + reproject to EPSG:4326. Disk-caches the LINZ catalog walk (~50 sec cold, instant warm) and per-collection item-bbox indexes. **2026-05-06: this is THE answer to the long-standing "regional-raster endpoint" gap.** | ✅ |
| `bulk_pull.py` — rate-limit aware. Default quota 400/24h (OT+ tier). Tracks daily call count in `~/.opentopo_calls.jsonl`. Auto-throttles. | ✅ |
| `tile_stitch.py` — multi-tile DEM composer with NoData sanitization + percentile clamp (fixes -3.4e38 sentinels blowing up min/max normalization). Verified **9-tile yosemite_full_1m → 4096×4096 stitched output** (894-3396m elevation range matches real Yosemite geography; marquee scene built end-to-end at --size 2048). | ✅ |
| `bulk_build_scenes.py` — walks data_wishlist.json showcase tier, runs `region_pipeline --skip-dem` for every cached USGS1m region. **Built 13 scenes 2026-05-06**: bryce, grand_canyon, crater_lake, mt_st_helens, shiprock, devils_tower, haleakala, sedona, moab, white_sands, kilauea, carlsbad, rocky_mtn — 0 failures. | ✅ |
| `screenshot_scenes.py` (in `pipelines/godot_export/`) — headless Godot CLI render of any biome scene to PNG. Transactional patch-render-restore via the existing `snap.gd`. Used to mass-screenshot all 16 worldview + character cam pairs. | ✅ |
| `stage_biome_terrain.py` — `--cam {worldview, character}` flag (worldview frames the whole TERRAIN_SIZE_M, character is fixed 50m ARPG frame). **Phase 1 swap-points**: `--shader-preset {topdown, triplanar, hextile, heightblend}` resolves a preset from `godot_pack/shaders/shader_registry.json`; `--use-real-extents` reads terrain dims from `world.json`'s `dem_meta`. Worldview camera + fog density auto-scale with `TERRAIN_SIZE_M`. Anchored character cam uses densest-non-sentinel biome cluster centroid (no more "iso shows only fog"). Cam-aware fog density (~3× weaker for character cam). | ✅ |
| `region_pipeline_from_config.py` — walks `region.config.v1` JSONs, dispatches to `region_pipeline.py`. Use `--config FILE` for one region, `--batch GLOB...` for many, `--template ID` to emit a fresh template, `--dry-run` to print resolved CLI without running. Schema captures every choice (DEM source, fantasy style, biomes, splat mode, shader preset, terrain extents, scatter cap, camera framing, project, quality). | ✅ verified e2e on death_valley_basin |
| `godot_pack/shaders/shader_registry.json` — preset registry: topdown/triplanar shipped, hextile/heightblend reserved (fall back to topdown if .gdshader file missing). | ✅ |
| `art_lab/biomes/regions/*.region.json` — concrete regions; first example: `death_valley_basin.region.json`. Schema doc at `art_lab/biomes/regions/README.md`. | ✅ |
| **OT+ Pro tier** — confirmed active 2026-05-06. All Access (USGS 1m unlocked, all federated point clouds visible). 400/24h API quota, 350M point-cloud caps. $30/mo. Verified end-to-end with Half Dome 1m pull. | ✅ |
| [docs/reference/OPENTOPO_API.md](docs/reference/OPENTOPO_API.md) — full API surface reference (3944 datasets, on-demand processing tools, OT+ tier matrix, known gotchas) | ✅ |
| `art_lab/biomes/data_wishlist.json` — 172 named regions across stitched/highres_open/showcase/premium/standard/bathymetric tiers | ✅ |
| `art_lab/biomes/data_wishlist_mystery.json` — 300 procedural unknown regions | ✅ |
| `art_lab/biomes/world_catalogue.json` — 10 curated (preset × style × biome) starter combinations | ✅ |
| `import_dem.py` — bumped default to COP30 (was SRTMGL3, 90m → 30m), added `--bathymetry` (GEBCO seafloor merge), `--res` for high-res pulls, persistent TIFF cache | ✅ |

Run:
```powershell
# One-command: any preset + any style + any biome mix
python pipelines\terrain\region_pipeline.py --preset bryce_hoodoo --style spired --strength 1.5 --biomes mana_crystal,grassland,grassland,grassland --id spire_v1 --project C:\Users\josep\test\new-game-project --size 1024

# Bulk-pull cached source DEMs (resumable, cache-aware)
python pipelines\terrain\bulk_pull.py --tier premium

# Apply a fantasy style to any heightmap
python pipelines\terrain\dem_fantasy_edit.py --in <bundle>/height_16.png --out fantasy.png --style mythic --strength 1.2
```

---

### 8e. Biome ↔ AAA-texture binding ✅ NEW (2026-05-06)

Closes the loop between the world-gen output (biome_labels) and the AAA texture library: each biome maps to a stable PBR texture set, and the splat compiler writes a fixed-channel RGBA mask the terrain shader can hard-bind.

| Item | Status |
|---|---|
| `art_lab/biomes/biome_texture_registry.json` (single source of truth: biome_id → set_id + splat_channel + prompt_seed + tiling_meters) | ✅ |
| `pipelines/terrain/biome_splat.py` — biome_labels.png → biome_splat_rgba.png. Channels assigned by world.json position (any 4 biomes coexist). `--splat-mode {gaussian, soft, hard, height_blend}`: gaussian (1.6 px feather, default), soft (3.2 px), hard (no blur), height_blend (RESERVED, currently behaves like hard). | ✅ |
| `pipelines/textures/biome_texture_bind.py` — auto-generates any missing AAA texture sets via `aaa_texture.py`, emits `biome_pbr_pack.json` | ✅ |
| `pipelines/godot_export/stage_biome_terrain.py` — copies height + splat + 4 PBR sets into a Godot project, writes `.tres` ShaderMaterial + `.tscn` test scene. `--walkable` adds HeightMapShape3D collision + CharacterBody3D player (WASD+jump+mouse-look). `--cameras` writes two extra scenes (`biome_<id>_topdown.tscn` ortho top-down, `biome_<id>_iso.tscn` 45°/30° iso ortho) for A/B 2D-vs-2.5D look comparison. Auto-includes `biome_scatter_<id>.tscn` if present. | ✅ |
| `pipelines/godot_export/stage_biome_scatter.py` — reads biome_labels + heightmap + vegetation_density + water_mask from a world, blue-noise-samples per-biome scatter rules (`art_lab/biomes/biome_scatter_rules.json`), emits one `MultiMeshInstance3D` per asset type with placeholder primitive meshes (Box/Cylinder + tinted StandardMaterial3D). Writes a self-contained `biome_scatter_<id>.tscn` the main scene instances as a child. Verified 10063 instances across 13 asset types on `qa_fjord_4biome`. | ✅ |
| `art_lab/biomes/biome_scatter_rules.json` — per-biome asset list (id, placeholder_mesh, color, density_per_m2, slope/vegetation gates, scale range). Drives `stage_biome_scatter.py`. Real GLB props can swap in by extending the schema. | ✅ |
| `godot_pack/shaders/biome_terrain.gdshader` — 4-layer biome blender, vertex-stage heightmap displacement, **triplanar projection** (`triplanar_strength` + `triplanar_sharpness` uniforms) so cliffs/canyon walls don't stretch, per-biome tiling. Canonical source; stager copies into project. | ✅ |

Run:
```powershell
python pipelines\terrain\biome_splat.py --world world\worlds\qa_fjord_4biome
python pipelines\textures\biome_texture_bind.py --world world\worlds\qa_fjord_4biome --quality default
python pipelines\godot_export\stage_biome_terrain.py `
  --world world\worlds\qa_fjord_4biome `
  --project C:\Users\josep\test\new-game-project
```

---

## 8d. Future Art Lab buildouts (per G)

Per `G_deep_dive`, these are **not yet started** but are the next-week priorities:

### Magic/World Art Lab — `art_lab/`
1. **Godot shader template harness** — first-party `.gdshader` library + LLM JSON DSL + preview/bake. 5 templates: ring, beam, dissolve, shield ripple, portal swirl.
2. **Material Maker 1.6 adapter** — install + CLI export wrapper.
3. **Shadertoy/GodotShaders reference importer** — 10 CC0/MIT examples ingested with license tracking.
4. **Mapgen4 + Mapshaper world map slice** — 2048px region with rivers/biomes/12 settlements/3 factions/labels/SVG/PNG/GeoJSON.
5. **Blender Geometry Nodes biome kit** — mossy highland: 6 rocks, 4 grass cards, 3 ruin blocks, 5 decals, placement masks.
6. **Terrain3D 4.5 compatibility check** + ProtonScatter fallback.
7. **Recraft API adapter** for UI icons.

### Hard "no" list (G's recommendations):
- ❌ "AI shader generator" as core dep — no real Godot-compatible product exists (Refract is hosted-only)
- ❌ Blind Shadertoy copy-paste (license/perf risk)
- ❌ Unity Shader Graph / Unreal materials as canonical authoring
- ❌ GUI-only fantasy map tools as source of truth
- ❌ Raw AI 3D props in scatter fields (always clean/scale/LOD/thumbnail)
- ❌ GPL ingestion for runtime tools
- ❌ Houdini/HEGo first-week (too heavy)

---

## 9. Active blockers (need user)

| Blocker | What's needed |
|---|---|
| ~~FLUX schnell weights~~ | ✅ resolved — FLUX.2-klein-4B (Apache 2.0, ungated) installed |
| PATINA test | `FAL_KEY` env var (~$0.05 per call) |
| OpenTopography real DEMs | `OPENTOPOGRAPHY_API_KEY` env var (free) |
| Recraft API icons | Account + API key when we want UI generation |

---

## 10. Active blockers (technical, fixable) — ALL RESOLVED

| Blocker | Status |
|---|---|
| Material Anything torch ABI mismatch | ✅ resolved via atomic torch 2.9.1+cu130 / torchvision 0.24.1 install |
| Material Anything xformers conflict | ✅ uninstalled |
| MA bpy missing | ⚠️ only needed for optional `render_video_bpy_4s.py`; not on PBR critical path |
| MA cupy missing | ✅ installed cupy-cuda13x |
| MA pkg_resources missing | ✅ downgraded setuptools to 79 |
| MA nvcc missing | ✅ installed cuda-toolkit 13.2 in env |
| MA kaolin source build | ✅ kaolin 0.18 built and verified on CUDA |
| MA pytorch3d CUDA + pulsar link | ✅ rebuilt 0.7.9 with pulsar removed (same recipe as AAM) |
| MA diffusers/transformers/hf-hub API drift | ✅ pinned diffusers 0.28.2, transformers 4.46.3, hf-hub 0.25.2 |
| MA SD2 inpainting gated | ✅ used sd2-community mirror, patched lib/diffusion_helper.py to local path |
| MA ControlNet depth weight | ✅ downloaded 5.4 GB from lllyasviel/ControlNet |
| MA project_mask_image undefined | ✅ patched scripts/generate_texture_pbr_3d.py line 442 |

---

## 11. What "tested" means here

- ✅ = produced a real output file we kept on disk
- 🟢 = code import + boot verified, no production output
- 🟡 = stack reaches the model/inference but errors out at a known point

The character pipeline, terrain/region pipeline, biome texture binding, and Godot terrain staging all have chained end-to-end evidence on disk. Textures have QA manifests and preview renders for the kept library sets. Material Anything is not on the 2D texture critical path: the mesh-driven adapter runs but produces low-quality output, and `ma_image2pbr.py` remains broken for flat 2D textures.
