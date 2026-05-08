# Next Steps After 2026-05-07 SOTA Survey

All 8 research briefs returned, sifted, and integrated into pipeline reviews + ROADMAP. This doc is the cross-cutting view: **what got done today, what's queued, what's user-gated, and where to point next.**

For per-pipeline detail: [docs/pipeline_reviews/](../pipeline_reviews/) and [ROADMAP.md](ROADMAP.md). For raw research: [docs/research_briefs/2026_05_07_sota_survey/](../research_briefs/2026_05_07_sota_survey/).

## Today's outcome (one line per brief)

| Brief | Headline | Net change | Status |
|---|---|---|---|
| #01 Characters | AnimateAnyMesh demoted; canonical chain decided; Puppeteer installed; AniMo skipped (training-only repo) | Major | ✅ done |
| #02 Textures | CHORD (Ubisoft, Dec 2025) is consequential drop we missed; MA reclassified; hero_mesh sibling lane planned | Major (worker-owned) | ✅ doc + handoff written |
| #03 Props | Trellis2 default validated; meshoptimizer side-by-side wired; Rodin parked; foliage = separate lane | Small wins | ✅ done |
| #04 VFX 3D bake | GPU plan reduced to Warp-primary, PhiFlow-watch (Taichi/LiquidFun dropped); LLM authoring tool comes BEFORE GPU port | Plan simplified | ✅ docs + plan banner |
| #05 VFX shaders | Framework already 2026 SOTA-shaped; dreamsim+lpips scoring wired side-by-side; art_lab venv stood up | Small wins | ✅ done |
| #06 Audio | Noise/static was workflow not model; CLAP+PyMusicLooper QA wired; audio venv stood up; 5 model installs queued | Major QA fix | ✅ done |
| #07 UI / Icons | LoRA training is biggest unlock; FLUX.2 Klein 4B + Recraft V4 plumbed; Iconoir added | Plumbing additions | ✅ done |
| #08 Game Data | Infrastructure validated as best-in-project; "run the cascade" is biggest unlock; 5 additive tools queued | Reassuring | ✅ docs + game_data venv |

## What got installed today

| Venv | Tools | Purpose | Brief |
|---|---|---|---|
| `animators/Puppeteer/.venv` | torch 2.7+cu128 + xformers + flash-attn + pytorch3d + torch-scatter + bpy 4.4 | Rig + skin + FBX export pipeline | #01 |
| `art_lab/.venv` | torch 2.7+cu128 + dreamsim + lpips | Perceptual scoring backends for shader_reference_score.py | #05 |
| `pipelines/audio/.venv` | torch 2.7+cu128 + laion-clap + pymusiclooper + librosa | Audio QA: CLAP score + loop seam validator | #06 |
| `pipelines/game_data/.venv` | pymoo + fastjsonschema + duckdb | Pareto dominance + faster validator | #08 |
| Tool binary (no venv) | `tools/meshoptimizer/gltfpack.exe` v1.1 | LOD chain method = `meshopt` | #03 |

**Architecture:** one isolated venv per pipeline lane prevents the `accelerate==0.28.0 vs modern peft` kind of conflicts we hit. Same pattern across all 4 venvs.

## Code wiring done (additive, A/B-comparable)

| File | Change | Status |
|---|---|---|
| `pipelines/props/lod_chain.py` | `--method {decimate,meshopt}` flag, `--suffix _meshopt` for parallel A/B | ✅ verified on obelisk |
| `pipelines/props/blender_scripts/proc_lod.py` | `--suffix` plumbed | ✅ |
| `art_lab/tools/shader_reference_score.py` | `--scorer {edge_mse,dreamsim,lpips,all}` flag with lazy-imports | ✅ verified on smoke batch |
| `pipelines/audio/audio_qa.py` | `--clap-prompt <text>` + `--loop-check` flags, lazy imports | ✅ verified +0.407 / -0.117 discrimination |
| `pipelines/ui/freelib_ingest.py` | Iconoir added as 4th `mit-iso-libs` library | ✅ syntax-checked |
| `pipelines/ui/local_diffusion_icons.py` | FLUX.2 Klein 4B + FLUX.2 dev added; commercial-safe set updated | ✅ syntax-checked |
| `pipelines/ui/recraft_icons.py` | `--model {recraftv3,recraftv4,recraftv4-pro-vector}` flag | ✅ syntax-checked |
| `pipelines/vfx/GPU_BACKENDS_PLAN.md` | Superseded banner: Warp-primary, PhiFlow-watch | ✅ |

## Queued installs (not done — gated on user direction or sequencing)

### Cloud-gated (per user "no cloud right now")
- **Rodin Gen-2** — props hero quad route (#03)
- **Stable Audio 2.5** — reference-conditioned ambience (#06; LoRA on Open 1.0 is local alternative)
- **Recraft V4 Pro Vector run** — 6 hero icons ~$2 spend (#07)
- **DeepSeek V4-Pro** — bulk record generator (#08; cascade plumbing exists, just runs synthetic)
- **Claude Opus 4.7 / Haiku** — creative-weight records, dialogue translate (#08)

### User-time-gated (manual curation, design decisions)
- **AI-Toolkit by Ostris** — faction LoRA trainer (#07; gated on 20 reference images per faction)
- **LoRA fine-tune Stable Audio Open** — per-biome reference clips (#06; gated on CC0 reference library run)
- **First real shader batch on `occult_portal`** — has reference image, just needs to be aimed (#05)

### Sequencing-gated (something else has to land first)
- **NVIDIA Warp install + Warp-port `particle_cpu`** — gated on `effect_from_description.py` LLM tool being built first (#04)
- **`effect_from_description.py`** — sub-day LLM scaffold; the actual #4 priority item (#04)
- **Chatterbox-Multilingual TTS** — wire alongside `local_tts_f5.py` when NPC voice work begins (#06)
- **ACE-Step v1.5 music** — wire alongside `local_music_yue.py` when music work begins (#06)
- **AudioGen / MAGNeT** — alongside `synth_sfx.py` (#06; uses existing audio venv)
- **PettingZoo + scripted-heuristic** — when combat exists (#08)
- **XGrammar-2 upgrade** — when vLLM ships compat (#08)

### Worker-owned (texture worker decides timing)
- **CHORD** — replaces `derive_pbr_v2.py` as PBR estimator (#02; brief #02 is highest-leverage swap in entire texture lane)
- **Hunyuan3D-Paint 2.1** — for hero_mesh sibling lane (#02; ~1-2 day Blackwell port)
- **IP-Adapter on `flux_seamless.py`** — reference-photo conditioning (#02)

## Free-win action items (no cloud, no curation, not gated)

In rough priority order. **Today's progress marked.**

| # | Action | Brief | Effort | Status |
|---|---|---|---|---|
| 1 | Build `pareto_dominated_records.py` on top of pymoo NSGA-II (sibling to `duckdb_reports.py`) | #08 | 1 day | ✅ **done 2026-05-07 evening** — verified on 14 records, sparse cohorts mean nothing dominated yet (real value at #08's recommended 250-record scale) |
| 2 | Add `fastjsonschema` as additive option in `validate_records.py` (existing pydantic stays) | #08 | sub-day | ✅ **done 2026-05-07 evening** — `--validator {pydantic,fastjsonschema,both}` flag wired; pydantic also installed in `pipelines/game_data/.venv` so all 3 backends run from one interpreter; smoke-tested on 14 records (zero schema-validity disagreements between backends, fastjsonschema **1.89x** faster on this dataset; brief #08's 5-50x speedup framing is for the 250-record scale). Negative test: malformed records rejected by both backends. |
| 3 | Build `effect_from_description.py` LLM authoring tool — addresses "18 palette-swap recolors" at right layer | #04 | sub-day | ✅ **done 2026-05-07 evening** — at [`pipelines/vfx/effect_from_description.py`](../../pipelines/vfx/effect_from_description.py). Mirrors `pipelines/game_data/local_llm_backend.py` shape: `--backend {dry-run,vllm}`, OpenAI-compat HTTP, `guided_json` w/ Effect-schema enforcement, validates LLM output against Pydantic `Effect` model before write. Dry-run smoke test on `giant_fire_slam_wave` produced schema-valid effect.json. Cloud backends (Claude, DeepSeek) NOT wired per cloud-parked direction; sibling backend is a 1-file addition when cloud comes back. |
| 4 | Add Schneider-Vos cloud noise upgrade to `baker_volumetric_fog.py` | #04 | sub-day | pending |
| 5 | Add `audio_clip` field to VFX `manifest.json` schema | #04 | sub-day | pending |
| 6 | Add `getsentry/json-schema-diff` CI gate for migrations | #08 | sub-day | pending |
| 7 | Hash-based incremental linker (~50 LOC) for `pipelines/game_data/` | #08 | sub-day | pending |
| 8 | Import 3 curated shader templates (Hollow Pixel hit_flash, gdquest projectile_trail, godotshaders ground_glow) with license sidecars | #05 | sub-day | pending |
| 9 | Stand up `art_lab/library/<category>/<name>/manifest.json` convention + promote-from-review-queue helper | #05 | sub-day | pending |
| 10 | 100-line Yarn static analyzer (unreachable nodes, dead-ends, undefined var refs) on `yarn_link.py` | #08 | 1 day | pending |
| 11 | DSPy + GEPA scaffold for items/abilities (metric: schema valid + Pareto-non-dominated + embedding distance) | #08 | 1-2 days | pending |
| 12 | Visual A/B inspection of decimate vs meshopt LODs on obelisk (already-baked outputs exist; just look) | #03 | 30 min | 🟡 **quantitative side done 2026-05-07 evening** — at [`docs/plans/LOD_COMPARISON_OBELISK_2026_05_07.md`](LOD_COMPARISON_OBELISK_2026_05_07.md). meshopt is **0.7-2.0% smaller at matched tri counts** for LOD1-3 (LOD0 identical). Tri counts within ±2 verts across all LODs — both methods hit the same simplification ratios; meshopt's win is vertex quantization + index compression, not topology. **Visual eyeball pass still pending** (needs Blender/Godot side-by-side; queued for next time at the keyboard). |

## Path 2 — per-instance mesh albedo inpaint (post-brief-sweep gap)

**Highest-value cross-pipeline gap surfaced 2026-05-07 evening.** Not covered by any of the 8 SOTA briefs we ran. User direction: this is the priority direction.

| # | Action | Effort | Status |
|---|---|---|---|
| P0 | Brief #09 written for research-agent dispatch | sub-day | ✅ **done** — at [`docs/research_briefs/2026_05_07_sota_survey/09_mesh_inpaint_per_instance.md`](../research_briefs/2026_05_07_sota_survey/09_mesh_inpaint_per_instance.md), ready for user to dispatch |
| P1 | Initial design doc (architectural shape + open Qs) | sub-day | ✅ **done** — at [`docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md`](PATH_2_INPAINT_DESIGN_2026_05_07.md) |
| P2 | Phase 0 proof-of-concept (one-shot ComfyUI inpaint on goblin chest) | 1 day | **Skipped** — brief #09 returned and ruled out Architecture A (UV-space) for the entire asset class before Phase 0 ran. UV fragmentation is universal across all Trellis2/Meshy outputs. Phase 0 inputs are preserved in `pipelines/character_inpaint/phase_0_assets/` for reference. |
| P3 | Refine design from brief #09 response | sub-day | ✅ **done 2026-05-07 evening** — design doc updated at [`docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md`](PATH_2_INPAINT_DESIGN_2026_05_07.md). Architecture B confirmed. nvdiffrast as back-projector. Pipeline shape defined. All 7 open questions answered. |
| P4 | Stand up `pipelines/character_inpaint/.venv` + Phase 1 batch CLI (`inpaint_variants.py`) | 2-3 days | ✅ **done 2026-05-07 evening** — 6-module pipeline built + dry-run smoke test passed (goblin_p × ashen_pact_brand, 6 views, all 5 steps clean). Modules: `render_views_runner.py`, `comfy_inpaint.py`, `back_project.py`, `glb_repack.py`, `inpaint_variants.py`. Backend: `--inpaint-backend dry-run --project-backend dry-run` validated; `flux-fill` + `nvdiffrast` backends coded, gated on FLUX.1-Fill download (~16 GB) and nvdiffrast GPU test. |
| P4b | Download FLUX.1-Fill + Redux models → run live GPU pipeline end-to-end | 1 day | ✅ **done 2026-05-07 night** — Models: `flux1-fill-dev-fp8.safetensors` (11.9 GB), `flux1-redux-dev.safetensors` (123 MB, replaces XLabs IP-Adapter — incompatible with Fill), `sigclip_vision_patch14_384.safetensors` (816 MB SigLIP — Redux requires this, not CLIP ViT-G), `ae.safetensors` (319 MB FLUX VAE — Fill needs 16-ch VAE not flux2-vae 64-ch). Blender 5.1 headless confirmed. Full run produced `goblin_p_ashen_live.glb` (3.2 MB). Pipeline executes without errors. |
| P5 | Visual quality check — faction mark legible on output GLB? | sub-day | ⚠️ **PIPELINE CORRECT, FLUX QUALITY OPEN** — four root-cause bugs diagnosed and fixed 2026-05-07 night: **(1)** camera orbit started at 0° (side view) → fixed to 270° (front-facing); **(2)** mask at 66% down (hip) → fixed to 45% down (sternum); **(3)** Redux is a style adapter not a logo compositor → `use_redux=False` default, prompt-only mode; **(4)** FLUX output composited back incorrectly (whole image replaced, not masked composite + raw RGBA blit including transparent BG) → fixed mask composite in `_flux_fill`. Back-projector azimuth mismatch also fixed (was 0-based, now 270-based to match renderer). Output GLB `goblin_p_ashen_v5.glb` produced. **Remaining issue:** FLUX.1-Fill fills the mask with "more goblin skin texture" — strong surrounding context overwhelms the text prompt. Insignia not visibly distinct. Needs: stronger prompt engineering (CFG guidance trick, negative prompt, more explicit shape desc) or ControlNet reference approach. |
| P6 | Phase 2: replace nvdiffrast with Hunyuan3D-Paint projection module if smearing unacceptable | 1-2 days | Deferred — gated on P5 quality eval |
| P7 | Phase 3: Grounded-SAM-2 mask gen + damage-state parameterization | sub-day each | Deferred — Phase 1 uses hand-authored view masks |

## Things to actively NOT do (decided by 2026 SOTA, not us)

These are the "don't build that, the brief said no" entries. Putting them here so future agents don't re-investigate:

- **Don't fine-tune game-content LoRAs** (#08) — niche doesn't exist usably; SOTA general models write D&D-style content well enough.
- **Don't set up RL on combat balance before combat is built** (#08) — sunk-cost spiral.
- **Don't migrate Yarn → Ink / Dialogic 2** (#08) — lateral, build static analyzer instead.
- **Don't buy World Anvil / LegendKeeper / Kanka / Campfire** (#08) — worldbuilding-as-product, wrong shape.
- **Don't adopt Inworld / Convai for dialogue** (#08) — runtime NPC products, not authoring.
- **Don't adopt Lokalise / Phrase / Smartling pre-launch** (#08) — Crowdin Free does the job.
- **Don't pursue Hunyuan3D-3.0 full open weights** (#03) — watch list, not adopt.
- **Don't try image-to-3D for foliage** (#03) — separate lane (SpeedTree / The Grove).
- **Don't pursue AI HUD generators** (#07) — wrong category for game UI.
- **Don't pursue diffusion VFX (Sora 2 / AnimateDiff)** (#04) — wrong tool category for alpha-matted flipbooks.
- **Don't adopt USD for VFX manifest** (#04) — overkill for flipbooks; JSON field works.
- **Don't keep AniMo on the install list** (#01) — training-only research repo, no checkpoints.
- **Don't install MocapAnything from github.com/animotionlab26** (#01 watch list, verified 2026-05-07 evening) — unofficial reimplementation of Huawei paper, anonymous 1-month-old org, no checkpoints, no license, author disclaims as "not a reproduction." Same AniMo pattern. Revisit only if Huawei publishes official weights with HF model card.
- **Don't adopt Neo4j / KuzuDB at <20K records** (#08) — architectural cosplay.
- **Don't replace vtracer/resvg/PIL atlas packer** (#07) — laterals.
- **Don't deepen MaterialAnything investment for hero terrain** (#02) — reclassified; Hunyuan3D-Paint 2.1 is the upgrade.

## Recommended next session focus

User direction 2026-05-07 evening: **do them all**, with the understanding that:
- **Option C (33-character fan-out) was reframed as content authoring** and dropped
- **Option B (faction icon LoRA) was reframed as hand-waving** — the actually-valuable use case is per-instance mesh inpainting, which became Path 2
- **Option A (free wins) is in flight** — items 1, 2, 3 ✅ done; item 4 (decimate vs meshopt) quantitative side ✅ done, visual side queued; items 5-12 pending
- **Path 2 work is in flight** — brief #09 written + dispatch-ready, design doc written, **Phase 0 PoC fully prepped** (walkthrough + 4 input artifacts ready), execution gated on user keyboard time

**Concrete next moves (in priority order):**
1. **User dispatches brief #09** (research-agent run, ~few hours, low risk) — happens off the main thread
2. **Phase 0 Path 2 PoC at the keyboard** — walkthrough at `pipelines/character_inpaint/PHASE_0_WALKTHROUGH.md`; assets pre-generated; ~1-2 hours including Blender visual-judgment step. Tells us if Architecture A (UV-space) survives the chest UV fragmentation finding.
3. **Visual A/B inspection of decimate vs meshopt LODs** — pair with Phase 0 since both need eyes-on. Comparison report at `docs/plans/LOD_COMPARISON_OBELISK_2026_05_07.md`; checklist at the bottom is the artifact.
4. **Free wins items 4-12** as time permits — item 4 is Schneider-Vos noise upgrade in `baker_volumetric_fog.py` (sub-day, codebase-local).
5. **Brief #09 returns** → refine Path 2 design → start Phase 1 batch CLI.

## Session epilogue 2026-05-07 evening (orchestrator pickup → free wins)

Picked up orchestrator duties from the prior session. **Two free-wins shipped + one prepped + one decision-ready:**

| Action | What landed |
|---|---|
| Free-win #2 (fastjsonschema additive) | `validate_records.py --validator {pydantic,fastjsonschema,both}` — backends agree on all 14 records, fastjsonschema 1.89x faster on this dataset |
| Free-win #3 (effect_from_description.py) | New LLM authoring tool at `pipelines/vfx/effect_from_description.py` — `--backend {dry-run,vllm}`, guided_json schema enforcement, validates LLM output before write; dry-run smoke test passed |
| Free-win #4 (decimate vs meshopt visual A/B) | Quantitative side complete at `docs/plans/LOD_COMPARISON_OBELISK_2026_05_07.md` — meshopt 0.7-2.0% smaller at matched tri counts; visual eyeball pass queued |
| Path 2 Phase 0 prep | Walkthrough doc + 4 input artifacts at `pipelines/character_inpaint/`; **surfaced critical Architecture A risk: chest UV fragmentation across multiple scattered islands** (memory note saved) |

**Did NOT do this session:**
- User-driven actions (dispatching brief #09, running Phase 0 inpaint, visual A/B in Blender)
- Anything cloud (per cloud-parked direction)
- Anything that would touch shared state without confirmation
- Anything that fans out the 33 characters

**Persistence-first updates landed:** NEXT_STEPS table (this doc), ROADMAP brief #03/#04/#08 sections, MEMORY.md index + new memory note `path2_uv_fragmentation_finding.md`.
