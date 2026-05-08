# Pipeline Guide

Copy-paste recipes for the production-ready pipelines. For decision trees and per-asset run-order, see [WORKFLOWS.md](WORKFLOWS.md). For status, see [PIPELINE_DIRECTORY.md](PIPELINE_DIRECTORY.md). For tool inventory, see [TOOLS_INDEX.md](TOOLS_INDEX.md).

Updated 2026-05-07 (post-worldgen nuke; pre-nuke version at `_archive/docs_pre_nuke_2026_05_07/PIPELINE_GUIDE.md`).

## Pre-flight

Every new shell:

```powershell
# OT+ tier active 2026-05-06: All Access (USGS 1m unlocked), 400 calls/24h.
$env:OPENTOPOGRAPHY_API_KEY = [Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY", "User")
```

For other env vars (OPENAI_API_KEY, ANTHROPIC_API_KEY, RECRAFT_API_KEY, ELEVEN_API_KEY, MESHY_API_KEY, HF_TOKEN, …), see [docs/reference/CLOUD_KEYS.md](docs/reference/CLOUD_KEYS.md).

---

## Sections

- [DEM ingestion](#dem-ingestion)
- [Tile-stitched DEMs](#tile-stitched-dems)
- [AAA Texture Workflow](#aaa-texture-workflow)
- [Character Pipeline](#character-pipeline)
- [Character Inpaint Pipeline](#character-inpaint-pipeline)
- [Props Pipeline](#props-pipeline)
- [Audio Pipeline](#audio-pipeline)
- [UI / Icon Pipeline](#ui--icon-pipeline)
- [VFX (3D bake)](#vfx-3d-bake)
- [VFX (shader workflow)](#vfx-shader-workflow)
- [Game Data Pipeline](#game-data-pipeline)
- [Scene composition (open question)](#scene-composition)

---

## DEM ingestion

**Single bbox:**

```powershell
# US LiDAR-grade 10m (free tier)
python pipelines\terrain\import_dem.py --id yose_10m --source opentopo --bbox -119.65 37.70 -119.50 37.80 --dataset USGS10m --size 1024

# US 1m LiDAR (OT+ subscription, verified working)
python pipelines\terrain\import_dem.py --id half_dome_1m --source opentopo --bbox -119.540 37.740 -119.520 37.755 --dataset USGS1m --size 1024
```

**Search the catalog (no quota cost):**

```powershell
python pipelines\terrain\catalog_search.py --bbox -112.20 37.55 -112.00 37.75
```

**Bulk-pull from wishlist (resumable, cache-aware, rate-limit-aware):**

```powershell
python pipelines\terrain\bulk_pull.py --tier premium --dry-run    # plan
python pipelines\terrain\bulk_pull.py --tier premium              # do (default 400/24h OT+ quota)
```

**Regional STAC bypass (ArcticDEM / REMA / LINZ — direct provider S3):**

```powershell
python pipelines\terrain\fetch_regional_stac.py --id milford_1m --bbox 167.85 -44.70 167.95 -44.60 --provider linz
```

**Random sampler (300 procedural worldwide bboxes):**

```powershell
python pipelines\terrain\mystery_sampler.py --out art_lab\biomes\data_wishlist_mystery.json
```

Outputs: TIFFs cache to `D:/assets/dems/`. Bundles + heightmaps to `pipelines/terrain/output/<id>/`.

Quota tracking: `~/.opentopo_calls.jsonl`. Resumable next day. Cached TIFFs are free.

---

## Tile-stitched DEMs

For regions too big for a single API call (e.g. full Yosemite at 1m as 9-tile composite):

```powershell
python pipelines\terrain\tile_stitch.py `
  --id yosemite_full_1m `
  --bbox -119.75 37.65 -119.40 37.90 `
  --dataset USGS1m --rows 3 --cols 3 --size 4096
```

Outputs to `pipelines/terrain/output/<id>/height_16.png` plus `tile_grid.json` provenance.

---

## AAA Texture Workflow

**Canonical (full PBR pipeline):**

```powershell
python pipelines\textures\aaa_texture.py `
  --prompt "weathered cobblestone, mossy gaps" `
  --id cobble --category Bricks --quality default
```

This runs: prompt → StableMaterials PBR generation → seam repair → derive_pbr (fills missing maps) → texture_qa (writes `qa/seam_score.json` with grade A/B/C). Output: `world/textures/library/cobble/`.

**Albedo-only seamless (fast, no PBR):**

```powershell
python pipelines\textures\flux_seamless.py `
  --prompt "mossy basalt rock" --id basalt --size 1024 `
  --seed 7 --heal-strength 0.35
```

4-pass: text2img → circular shift → img2img heal → reverse shift. A-grade tileability for noise-like materials.

**QA an existing set:**

```powershell
python pipelines\textures\texture_qa.py --id <set_id>
# Or batch:
python pipelines\textures\texture_qa.py --all
```

**Repair seams on a borderline set:**

```powershell
python pipelines\textures\seam_repair.py --id <set_id>
```

**Render preview for visual A/B:**

```powershell
python pipelines\textures\blender_preview.py --id <set_id>
```

**Third-party PBR ingestion:**

```powershell
python pipelines\textures\polyhaven_fetch.py --asset cobblestone_floor_05 --id ph_cobble_05
python pipelines\textures\ambientcg_fetch.py --asset Rock035 --id Rock035
```

Output state today: 31 sets in `world/textures/library/`. Grades: 10 A / 11 B / 3 C / 7 ungraded.

---

## Character Pipeline

```powershell
python meshy\batch_pipeline.py --input meshy\input\<char>.png --id <name>
```

Chains: image → 3D (Meshy API) → preprocess → bake → atlas. Output: `meshy/output/<name>/<name>.glb`.

Per-rigger animation:

```powershell
# Mesh2Motion (self-hosted Mixamo-alt)
cd animators\mesh2motion-app
.\start.ps1
# Browser at http://localhost:5173

# SkinTokens / RigAnything / Anytop / MagicArticulate / AnimateAnyMesh
# Each has its own venv + README. See animators/<tool>/README.md.
```

Mixamo (web): manual upload at adobe.com/mixamo.

Quality reference: [docs/audits/REVIEW.md](docs/audits/REVIEW.md).

---

## Character Inpaint Pipeline

Per-instance mesh albedo inpaint (faction emblems, damage states, weathering). Architecture B (camera-projection): render N orbit views → 2D inpaint each view → back-project to UV atlas → repack into output GLB.

**Dry-run smoke test** (no GPU, no ComfyUI required — validates plumbing):

```powershell
cd D:\assets\pipelines\character_inpaint
.\.venv\Scripts\python.exe inpaint_variants.py `
  --glb d:\path\to\character.glb `
  --reference phase_0_assets\insignia_ashen_pact_brand.png `
  --out d:\tmp\character_variant.glb `
  --inpaint-backend dry-run --project-backend dry-run `
  --blender-exe "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
```

**Live run** (requires ComfyUI running at 127.0.0.1:8188 with FLUX.1-Fill models loaded):

```powershell
cd D:\assets\pipelines\character_inpaint
.\.venv\Scripts\python.exe inpaint_variants.py `
  --glb d:\path\to\character.glb `
  --reference phase_0_assets\insignia_ashen_pact_brand.png `
  --out d:\tmp\character_variant.glb `
  --inpaint-backend flux-fill --project-backend nvdiffrast `
  --positive-prompt "<descriptive prompt for the insignia>" `
  --comfy-url http://127.0.0.1:8188 `
  --blender-exe "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
```

**Required ComfyUI models** (in `D:\assets\animators\ComfyUI\models\`):

- `diffusion_models/flux1-fill-dev-fp8.safetensors` (11.9 GB)
- `vae/ae.safetensors` (319 MB FLUX 16-ch VAE — NOT flux2-vae)
- `clip/clip_l.safetensors` + `clip/t5xxl_fp8_e4m3fn.safetensors`

Optional Redux conditioning (off by default — Redux is a style adapter, doesn't reliably place specific logos): `style_models/flux1-redux-dev.safetensors` + `clip_vision/sigclip_vision_patch14_384.safetensors`. Pass `use_redux=True` programmatically (no CLI flag yet).

Status: pipeline runs end-to-end, **FLUX prompt quality is the open gap.** Design + open-question resolutions: [docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md](docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md).

---

## Props Pipeline

**Full one-command (AI route + 7-stage postprocess):**

```powershell
# Concept image → Trellis2 default → all postprocess stages → Godot export
python pipelines\props\postprocess_ai_route.py `
  --concept <path>.png --id <prop_id> --render-class hero
```

`--render-class`: `scatter` / `balanced` / `hero` / `hi_tex` (picks Trellis2 preset).

**Procedural recipe (no AI):**

```powershell
python pipelines\props\proc_generate.py --recipe pipelines\props\PROC_RECIPES.md
```

**Variation sweep on existing prop:**

```powershell
python pipelines\props\variation_sweep.py --id <prop_id> --variations 4
```

**Validate library:**

```powershell
python pipelines\props\validate_props.py --library world\props\library
```

Output: `world/props/library/<prop_id>/` — prop.json, thumbnail.png, decal/mesh, qa.json.

Patches reference: [pipelines/props/TRELLIS2_PATCHES.md](pipelines/props/TRELLIS2_PATCHES.md).

---

## Audio Pipeline

**Bake biome ambience (Stable Audio Open 1.0 GPU):**

```powershell
python pipelines\audio\biome_ambience.py `
  --recipe pipelines\audio\recipes\biome_ambience.json
```

10 biomes × 4 layers (bed_drone + bed_air + wildlife_sparse + distant_event), LUFS-normalized per `LUFS_AUTHORING_GUIDE.md`.

**Procedural SFX:**

```powershell
python pipelines\audio\synth_sfx.py --catalog pipelines\audio\recipes\sfx_grid.json
```

**ElevenLabs SFX (cloud):**

```powershell
python pipelines\audio\eleven_sfx.py --prompt "wood crack, sharp" --id wood_crack_a01
```

**TTS:**

```powershell
python pipelines\audio\local_tts_f5.py --text "Hail, traveler." --id npc_greet_a
python pipelines\audio\openai_tts.py --text "Hail, traveler." --voice alloy --id npc_greet_a
```

**Pack for Godot:**

```powershell
python pipelines\audio\ambience_pack.py --library audio\ambience
python pipelines\audio\export_godot.py --library audio
```

Outputs: `audio/{ambience,sfx,music,tts}/`. Manifests: `sfx_manifest.json`, `ambience_summary.json`.

LUFS targets: -28 dBFS bed_drone, -30 dBFS bed_air, -22 dBFS wildlife peak, -20 dBFS distant_event peak.

---

## UI / Icon Pipeline

**Procedural baseline (always available):**

```powershell
python pipelines\ui\synth_icons.py --catalog game_data\schemas\ability.json --out ui\synth
```

**Cloud routes (env-gated):**

```powershell
$env:OPENAI_API_KEY = [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "User")
python pipelines\ui\openai_icons.py --catalog game_data\schemas\ability.json --out ui\openai

$env:RECRAFT_API_KEY = [Environment]::GetEnvironmentVariable("RECRAFT_API_KEY", "User")
python pipelines\ui\recraft_icons.py --catalog game_data\schemas\ability.json --style icon --svg --out ui\recraft
```

**Local FLUX-schnell (GPU):**

```powershell
python pipelines\ui\local_diffusion_icons.py --backend comfy --catalog ... --out ui\flux
```

**HUD mockups:**

```powershell
python pipelines\ui\hud_mockup.py --faction ashen_pact --state low_hp
```

**Pack atlas:**

```powershell
python pipelines\ui\pack_atlas.py --in ui\openai --out ui\atlas.png --json ui\atlas.json
```

**9-slice frames:**

```powershell
python pipelines\ui\nine_slice.py --in <frame.png> --id frame_a
```

**Validate:**

```powershell
python pipelines\ui\lint_icons.py --library ui
python pipelines\ui\icon_validator.py --catalog game_data\schemas\ability.json
```

Outputs: `ui/atlas.png` + `ui/atlas.json` + `ui/9slice/` + `ui/hud_preview_*.png`.

---

## VFX (3D bake)

**Bake one effect:**

```powershell
python pipelines\vfx\bake.py --effect vfx\catalog\spells\fireball_projectile\effect.json
```

Routes to `baker_particle_cpu` / `baker_fracture2d` / `baker_smoke_field` / `baker_volumetric_fog` per effect kind.

**Generate full element × archetype catalogue:**

```powershell
python pipelines\vfx\author_grid.py --elements fire,ice,lightning,earth,arcane,shadow `
  --archetypes projectile,burst,aura,impact
```

**Damage/impact catalogue (12 effects):**

```powershell
python pipelines\vfx\author_damage.py
```

**Migrate legacy spell-lab:**

```powershell
python pipelines\vfx\import_spell_lab.py --in <legacy_path> --out vfx\catalog
```

**Export to Godot:**

```powershell
python pipelines\vfx\export_godot.py --catalog vfx\catalog --kind 2d
python pipelines\vfx\export_godot_3d.py --catalog vfx\catalog --target 3d_billboard
# Other targets: decal, mesh_trail, fog_volume
```

**Gallery:**

```powershell
python pipelines\vfx\gallery.py --catalog vfx\catalog --out vfx\index.html
```

Outputs: `vfx/catalog/<kind>/<id>/` — effect.json + manifest.json + frames/ + flipbook.png + extras (particles.json | field.json | fragments.json) + godot/.

Runtime helpers: `vfx/runtime/MeshTrail3D.gd` (RibbonTrail/TubeTrail wrapper) + `vfx/runtime/AudioCueBus.gd` (frame-synced cue autoload).

GPU plan (deferred): [pipelines/vfx/GPU_BACKENDS_PLAN.md](pipelines/vfx/GPU_BACKENDS_PLAN.md).

---

## VFX (shader workflow)

This is a **distinct lane** from `pipelines/vfx/`. Use this when iterating on a Godot `.gdshader` file (visual look) rather than baking content (frames + manifest).

**Generate N candidates from a template:**

```powershell
python art_lab\tools\shader_evolve.py `
  --template art_lab\shaders\templates\portal_swirl_2d.gdshader `
  --batch portal_swirl_v1 --n 12 --seed 7
```

**Render previews:**

```powershell
python art_lab\tools\shader_godot_render.py --batch portal_swirl_v1
```

**Score against reference set:**

```powershell
python art_lab\tools\shader_reference_score.py --batch portal_swirl_v1 `
  --reference art_lab\shaders\reference_sets\portal_blue.png
```

**Promote shortlist for human review:**

```powershell
python art_lab\tools\shader_promote.py --batch portal_swirl_v1 --top 4
```

**Build review pages:**

```powershell
python art_lab\tools\shader_batch_review.py --batch portal_swirl_v1
```

**Static dashboard:**

```powershell
python art_lab\tools\shader_lab_index.py
# Open art_lab/shaders/index.html
```

Templates: 6 in `art_lab/shaders/templates/` — beam_lightning_2d, dissolve_fire_2d, portal_swirl_2d, ring_field_2d, shield_ripple_2d, macro_detail_v1 (terrain).

Status / next-work: [art_lab/SHADER_WORKFLOW_STATUS.md](art_lab/SHADER_WORKFLOW_STATUS.md).

---

## Game Data Pipeline

**Generate records (LLM, fallback chain):**

```powershell
# Backend cascade: openai → anthropic → synthetic. --backend overrides.
python pipelines\game_data\generate_records.py --schema item --count 20

# Local vLLM (GPU)
python pipelines\game_data\local_llm_backend.py item --device cuda --run-model --max-records 20
```

**Validate:**

```powershell
python pipelines\game_data\validate_records.py
```

**Round-trip test (.tres ↔ JSON):**

```powershell
python pipelines\game_data\roundtrip_test.py
```

**Balance reports (DuckDB):**

```powershell
python pipelines\game_data\balance\duckdb_reports.py
```

**Yarn dialogue link validator:**

```powershell
python pipelines\game_data\yarn_link.py --source game_data\source\dialogue
```

**Export to Godot:**

```powershell
python pipelines\game_data\export_godot.py
```

Outputs: `game_data/{generated,validated,godot,reports,schemas,source}/`.

---

## Scene composition

**Open question** post-worldgen-nuke. Each pipeline above produces canonical assets in its own `library/`, but **nothing assembles them into a Godot scene**.

The fresh `world3/` Godot project is the user's clean scene-composition target. As of 2026-05-07 it has its own `pipeline/`, `heightmap/`, `textures/`, `shaders/` subdirs — a game-project-style embedded mini-pipeline.

The two architectural options for whatever fills this hole:

| Option | Where the new pipeline lives | Pro | Con |
|---|---|---|---|
| **Factory style** | `pipelines/<scene_compose>/` | Re-usable across multiple Godot projects; emits to `world/` + `godot_pack/`. Matches existing 8-lane shape. | Decoupling means more glue. |
| **Game-project style** | `world3/pipeline/` | Owned by one game; emits in-place; faster iteration. | Doesn't re-use across projects. |

Until decided, the 8 working pipelines emit orphan assets that don't combine. See [docs/audits/AUDIT_2026_05_07_post_nuke.md](docs/audits/AUDIT_2026_05_07_post_nuke.md) for the gap-analysis.

---

## Cross-cutting tools

```powershell
# Validate asset cross-references (effect → audio → icon → record)
python pipelines\_meta\link_validator.py

# Check HuggingFace model availability
python pipelines\_meta\hf_surveyor.py

# Generic ComfyUI workflow dispatcher
python pipelines\_meta\comfy_runner.py --workflow <path>.json

# Per-image depth + normal estimation
python pipelines\_meta\depth_normal.py --in <img>.png

# Alpha extraction
python pipelines\_meta\matting.py --in <img>.png

# Real-ESRGAN x4plus / SwinIR
python pipelines\_meta\upscale.py --in <img>.png --scale 4
```

## Cross-pipeline Godot export

```powershell
python pipelines\godot_export\export_godot.py --pipeline textures --in world\textures\library --project <godot_project>
python pipelines\godot_export\export_godot.py --pipeline props --in world\props\library --project <godot_project>
# etc — supports each pipeline's library shape

python pipelines\godot_export\screenshot_scenes.py --project <godot_project> --scenes <res://...>
```

## Reference docs

- [docs/reference/CLOUD_KEYS.md](docs/reference/CLOUD_KEYS.md) — every `*_API_KEY` and what it activates
- [docs/reference/OPENTOPO_API.md](docs/reference/OPENTOPO_API.md) — full OpenTopography reference
- [docs/audits/AUDIT_2026_05_07_post_nuke.md](docs/audits/AUDIT_2026_05_07_post_nuke.md) — latest audit
- [docs/audits/REVIEW.md](docs/audits/REVIEW.md) — character pipeline review (depth standard)
