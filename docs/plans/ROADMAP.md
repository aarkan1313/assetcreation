# Pipeline Roadmap

What's working, what's missing, what to build next. **Updated 2026-05-07 evening** — all 8 SOTA briefs returned + integrated. **Read [NEXT_STEPS_2026_05_07.md](NEXT_STEPS_2026_05_07.md) for cross-cutting state** + [latest handoff](../handoffs/HANDOFF_2026_05_07_evening_brief_sift_complete.md).

> **🚨 Worldgen nuked 2026-05-07.** v1 + v2 both archived to `_archive/worldgen_2026_05_07/`. The OpenTopography DEM-fetch tooling under `pipelines/terrain/` is **kept** — 222 cached TIFFs / 8.1 GB at top-level `dems/`. **All worldgen-related rows in the legacy table below are stale** until a new worldgen pipeline gets designed. Worldgen worker is rebuilding in `world3/`.
>
> **🟢 SOTA brief sift complete 2026-05-07 evening.** All 8 briefs returned, sifted into pipeline reviews, integrated below under "Research-calibrated findings." 4 dedicated venvs stood up (Puppeteer, art_lab, audio, game_data). 8 code wirings added (all additive, A/B-comparable, default behavior preserved). 2 user directions captured: **(1) cloud parked** (Rodin, Stable Audio 2.5, Recraft V4 run, DeepSeek V4-Pro all queued not done); **(2) 33-character fan-out is content authoring not pipeline work, deferred.** Real pipeline gap surfaced: per-instance mesh albedo inpaint for faction insignia / damage states (Path 2) — not covered by any brief, queued for brief #09 or design pass.

For navigation: [TOOLS_INDEX.md](../../TOOLS_INDEX.md) | [PIPELINE_GUIDE.md](../../PIPELINE_GUIDE.md) | [PIPELINE_DIRECTORY.md](../../PIPELINE_DIRECTORY.md) | [../audits/REVIEW.md](../audits/REVIEW.md) | [../pipeline_reviews/README.md](../pipeline_reviews/README.md) | [RESEARCH_HANDOFF.md](RESEARCH_HANDOFF.md) | **[NEXT_STEPS_2026_05_07.md](NEXT_STEPS_2026_05_07.md)** | **[handoff](../handoffs/HANDOFF_2026_05_07_evening_brief_sift_complete.md)**

---

## 🎯 State as of 2026-05-07 PM (the honest picture)

### Canonical reframe (from the review pass)

> "Honestly nothing was hand-authored, all just kind of made without review. We proved it works, we will want to make sure it works well on our next pass. Honestly this is most likely the direction every pipeline and workflow will go. That's fine lol we just started yesterday on this entire project. We are making crazy leaps honestly." — user, after props review

**Across all 7 reviewed pipelines, the pattern is identical:**

- **Pipeline plumbing is real** — schemas, validators, bakers, exporters, QA, provenance, Godot integration. This is the actual deliverable.
- **First-pass procedural content is throwaway** — generated without authoring intent, curated prompts, or reference content. Ranges from "good placeholders" (UI) to "noise/static" (audio).
- **Real authoring quality only emerges with focused single-asset push.** The Phase 11 obelisk is the model. Everything else awaits similar focused passes.

### Per-pipeline state snapshot

| Pipeline | Pipeline state | Content state | Reviewed |
|---|---|---|---|
| **Characters** | ✅ most-complete in project | 33 GLBs, 5 animations baked, 11 sprite sheets — **animation step uncalibrated** (bad outputs from undocumented config) | [06_characters](../pipeline_reviews/06_characters.md) |
| **Props** | ✅ Phase 11 mature | 1 hero (obelisk) + 14 procedural-variant families. AI route validated on 1 example only. | [05_props](../pipeline_reviews/05_props.md) |
| **Game Data** | ✅ best infrastructure in project | 14 toy records (synthetic). Schemas + provenance + DuckDB balance reports + Yarn validator all real. **Balance review = long-term goal.** | [04_game_data](../pipeline_reviews/04_game_data.md) |
| **VFX (3D bake)** | ✅ working | 46 effect.json claimed, **18 are palette-swap recolors**. Real unique by physics: ~15. Blood/dust/spark cluster has real tuning. | [02_vfx_3d](../pipeline_reviews/02_vfx_3d_bake.md) |
| **VFX (shaders)** | ✅ best-designed iteration framework | 5 batches, all smoke tests. Templates competent, **never aimed at real target**. | [07_vfx_shaders](../pipeline_reviews/07_vfx_shaders.md) |
| **UI / Icons** | ✅ working placeholders | 135 icons (mix of synth + game-icons.net + lucide + phosphor). 4 factions are **just color swaps**. | [01_ui_icons](../pipeline_reviews/01_ui_icons.md) |
| **Audio** | ✅ pipeline kept | **Output archived 2026-05-07** (189 MB, was noise/static). Re-bake when game-design intent specific. | [03_audio](../pipeline_reviews/03_audio.md) |
| **Textures** | 🟡 worker active | (Deferred review — worker hasn't handed off) | _pending_ |
| **DEM Fetch** | ✅ working | 220 TIFFs / 8.1 GB. The only non-throwaway terrain-adjacent thing. | (no review needed) |
| **Worldgen / Scene composition** | ❌ gone (rebuilding) | `world3/` worker in flight. v1+v2 archived. | — |

### Animator tools — 13 of 13 install-validated 2026-05-07

All animator tools have venvs, weights, and end-to-end smoke tests confirming real output:

- ComfyUI, ComfyUI_HY3D (Phase 11), Trellis2 (Phase 11), hy-motion-fbx-exporter (Phase 11), SkinTokens (giraffe rigged 33s)
- AnimateAnyMesh (flying dragon FBX), Anytop (Bat motion BVH+MP4+NPY, **Windows-ported from Linux conda**), RigAnything (rigged spyro_the_dragon GLB), MagicArticulate (6 example skeletons), MaterialAnything (56MB PBR output, **kaolin install path corrected today**), mesa-repo (text→768²+DEM in 3s)
- mesh2motion-app (browser app build verified), Anytop ✅

Full recipes per tool: [`animators/INSTALL_MATRIX.md`](../../animators/INSTALL_MATRIX.md).

### Cleanup actions taken 2026-05-07

- Worldgen v1 + v2 → archived to `_archive/worldgen_2026_05_07/`
- DEMs relocated `pipelines/terrain/source_dems/` → `dems/` (top-level)
- 6 root cruft files swept (.pytest scratch dirs, stray __init__.py, prompts file, ChatGPT image)
- Audio output (189 MB) archived after manual audition revealed noise-tier quality
- Pipeline reviews series created at `docs/pipeline_reviews/01-07_*.md`
- INSTALL_MATRIX.md created + updated covering all 13 animator tools
- Multiple stale handoff/research docs archived

---

## 🛣 What comes next

The user's stated next-direction priorities (from session 2026-05-07 PM):

### Now in flight

- **C: SOTA tooling-gap survey** — research-agent dispatch per pipeline ("what 2026 SOTA would close the gaps the review pass surfaced?")
- **Characters animation deep-dive** — recover run config from `meshy/batch_logs/`, decide canonical animation path, verify rigging quality on humanoid + non-humanoid characters

### Background workers (don't disturb)

- **Worldgen worker** in `world3/` (rebuilding scene-composition pipeline)
- **Texture worker** in `world/textures/library/` + `pipelines/textures/` (improving tileable texture quality)

### Deferred / gated

- **Multi-prop generalization test** — drop 3-5 diverse concept PNGs through `trellis2_batch.py` to confirm Phase 11 isn't a one-shot
- **Real shader-evolve batch** — pick one effect (e.g. fire impact ring), build 6-image reference set, run `shader_evolve.py` for real
- **Game data balance** — flagged as long-term goal; needs N≥100 records to be analytically meaningful
- **One real audio bake** with curated prompts + reference audio (per-biome focused push, not procedural fill)
- **TLTE seed records** — game-design intent gated
- **TTS** — game-data dialogue-authoring gated
- **Phase 13 GPU VFX bakers** — Taichi/Warp/PhiFlow per `pipelines/vfx/GPU_BACKENDS_PLAN.md`

### Permanently changed framing

- "X effects / Y icons / Z props" headlines are **proof-of-pipeline**, not content claims
- Procedural fan-out is **the wrong move** for content quality; focused single-asset pushes are the right model
- Characters lane is the only place this might *not* apply — those 33 GLBs may end up production
- Pipeline reviews surface what each pipeline still needs; SOTA-survey will surface what it's missing

### Research-calibrated findings (returns from SOTA briefs as they land)

#### Brief #01 — Characters / Animation (returned 2026-05-07)

Full response: [`docs/research_briefs/2026_05_07_sota_survey/01_characters_animation.response.md`](../research_briefs/2026_05_07_sota_survey/01_characters_animation.response.md). Headlines:

- **AnimateAnyMesh demoted.** Not broken — wrong tool for character action. Reclassified to ambient/secondary motion only. Layer additively on top of skeletal animation.
- **Canonical chain decided:** rig-first → skeletal animation by topology → Blender retarget. **Path A** (humanoid): SkinTokens → Hunyuan-Motion → retarget. **Path B** (non-humanoid): RigAnything/SkinTokens → AniMo (text-conditioned) / AnyTop (OOD) / Puppeteer (video) → retarget.
- **Puppeteer installed + validated 2026-05-07 PM** — native Windows, py3.11, torch 2.7+cu128 (override path, not the WSL2 fallback the brief recommended). End-to-end rig pipeline working: deer.fbx + spiderman.fbx produced from skeleton + skinning + bpy export. 9 install gotchas overcome and documented; full recipe in [animators/INSTALL_MATRIX.md](../../animators/INSTALL_MATRIX.md). Animation stage (video-guided) deferred — only needed if/when we actually want video-guided animation.
- **AniMo skipped 2026-05-07** — repo at github.com/WandererXX/AniMo ships **only training scripts** (`train_vq.py`, `train_t2m_transformer.py`, `train_res_transformer.py`). No `inference.py`, no released checkpoints, no Releases page, no tags. Dataset must be self-generated. Research artifact, not a usable tool. The brief's "modest VRAM, ~30 min install, native Windows plausible" estimate was wrong. Documented as ❌ skipped in INSTALL_MATRIX. Use AnyTop (already validated, unconditional) for non-humanoid motion until a SOTA text-conditioned animal-motion tool with shipped checkpoints emerges.
- **Animation review tooling**: build a 100-line Blender CI linter (static-frame detection + foot-skating + FVMD aggregate). No 2026 turnkey exists. Not started.
- **Sprite-sheet baking**: stay on Blender headless EEVEE-Next; no 2026 alternative beats it. Parallelize with `-P` for fanout.
- **Watch list (no usable code yet):** UniMoGen, X-MoGen, OmniZoo, SPRig.

Remaining action items: (1) recover bad-run config from `meshy/batch_logs/` for forensics; (2) ~~install AniMo~~ (skipped); (3) ~~install Puppeteer in WSL2~~ (done, native Win); (4) validate on goblin (Path A) + hellhound or similar (Path B quadruped) + tentacle_horror or sandworm (Path B OOD); (5) build the linter; (6) fan out.

#### Brief #02 — Textures (returned 2026-05-07)

Full response: [`docs/research_briefs/2026_05_07_sota_survey/02_textures.response.md`](../research_briefs/2026_05_07_sota_survey/02_textures.response.md). Pipeline review: [`docs/pipeline_reviews/08_textures.md`](../pipeline_reviews/08_textures.md). Worker handoff: [`docs/handoffs/HANDOFF_textures_research_2026_05_07.md`](../handoffs/HANDOFF_textures_research_2026_05_07.md). Headlines:

- **CHORD (Ubisoft La Forge, SIGGRAPH Asia '25, opened Dec 2025)** is the consequential 2026 drop we missed. Open-weights, ComfyUI-native, FLUX/SDXL-driven, **5-channel tileable PBR**, `requirements.txt` already pinned to **CUDA 12.8** — Blackwell-ready. Research-only copyleft license. Highest-leverage swap: **replaces `derive_pbr_v2.py`** as the PBR estimator in `aaa_texture.py`.
- **MaterialAnything reclassified.** No longer SOTA for mesh-PBR as of mid-2026 — **Hunyuan3D-Paint 2.1** (Tencent, illumination-invariant + multi-view PBR) and MaterialMVP (ICCV '25) have surpassed it. Our 2026-05-07 MA validation still stands but don't deepen investment before benchmarking.
- **Workflow B (mesh-driven hero terrain) experiment redirected.** Skip MaterialAnything-on-flat-terrain (architectural mismatch: hemisphere camera + ControlNet-Depth collapses on horizontal mesh). Use **Hunyuan3D-Paint 2.1** instead. Fall back to TEXGen + CHORD if Hunyuan also smudges.
- **Two specific Workflow A tool changes for the worker:** (1) replace `derive_pbr_v2.py` with CHORD; (2) add IP-Adapter / FLUX Redux reference conditioning to `flux_seamless.py`'s FLUX stage. Optional 3rd lever: per-biome FLUX LoRA on Poliigon/FreePBR ground textures (~24h training/biome).
- **New sibling lane justified:** `pipelines/textures/hero_mesh/` (planned, not built) alongside the existing biome-tileable lane. Different architecture, different VRAM budget, different failure modes.
- **AAA pattern in 2026 is NOT end-to-end ML.** Tile-atlas + splatmap + virtual texture is the runtime; ML authors tiles. We're aligned. Don't replace runtime.
- **Watch list:** DualMat (ACM MM '25, code TBD), MatE (Dec 2025, no public code), Tiled Diffusion (CVPR '25), MaterialMVP, TEXGen.
- **Open research gap:** no "tileable + mesh-aware hybrid" exists in 2026. UV-space diffusion + circular-padding loss is the obvious next paper.

Action items (worker-owned, not us): (1) install CHORD; (2) wire CHORD into `aaa_texture.py` replacing `derive_pbr_v2.py`; (3) add IP-Adapter hook to `flux_seamless.py` FLUX stage; (4) install Hunyuan3D-Paint 2.1 (Blackwell port, ~1-2 days, similar shape to the Puppeteer port we just did); (5) stand up `pipelines/textures/hero_mesh/` lane; (6) optionally fine-tune biome-specific FLUX LoRAs.

#### Brief #03 — Props / image-to-3D (returned 2026-05-07)

Full response: [`docs/research_briefs/2026_05_07_sota_survey/03_props_image_to_3d.response.md`](../research_briefs/2026_05_07_sota_survey/03_props_image_to_3d.response.md). Headlines:

- **Reassuring, not redirecting.** TRELLIS.2-4B remains the right default for May 2026 — no released open-weights model decisively beats it for our props use case. "Trellis 3" doesn't exist. **Phase 11's Trellis2-as-default decision validated against 2026 SOTA.** Useful negative result.
- **Three local-only action items:** (1) **meshoptimizer** alongside DECIMATE COLLAPSE in the LOD chain (per user direction 2026-05-07 PM: side-by-side, not replacement, for easier A/B comparison); (2) **multi-image conditioning** on TRELLIS.2 for procedural variation (closest 2026 analog to "ControlNet for 3D"); (3) **Rodin Gen-2 cloud `--hero` route PARKED** per user direction (no cloud right now). Adapter scaffold not built.
- **No texture-worker overlap.** Brief #03 is entirely props-lane internal.
- **What NOT to do:** don't pursue full Hunyuan3D-3.0 open weights, don't try image-to-3D for foliage (separate lane: SpeedTree / The Grove 3D), don't expand cloud usage.
- **Watch list:** Knodt 2026 (quadric convex decomp for collision), Hunyuan3D-3.0 full open release, HY3D-Bench (Feb 2026, 252K watertight + 240K part-decomposed — fine-tune material if we ever want it).
- **Cloud-vs-local for props is settled in favor of local.** Meshy is no longer competitive with TRELLIS.2 for props. Cloud only earns its keep on hero quads (Rodin) and the existing Meshy character pipeline.

Action items (us, sub-day each): (1) ✅ **meshoptimizer wired alongside DECIMATE COLLAPSE 2026-05-07 PM** — `gltfpack v1.1` at `tools/meshoptimizer/`, `lod_chain.py --method meshopt --suffix _meshopt`, verified A/B on obelisk_egyptian_a04 (4 LODs); **quantitative side complete 2026-05-07 evening** — meshopt is 0.7-2.0% smaller at matched tri counts for LOD1-3, LOD0 identical; tri counts within ±2 across LODs; full table at [`docs/plans/LOD_COMPARISON_OBELISK_2026_05_07.md`](LOD_COMPARISON_OBELISK_2026_05_07.md); visual eyeball pass still pending; (2) extend `trellis2_route.py` / `trellis2_batch.py` for multi-image conditioning input; (3) defer Rodin Gen-2 adapter until cloud is back in scope.

#### Brief #04 — VFX (3D bake) (returned 2026-05-07)

Full response: [`docs/research_briefs/2026_05_07_sota_survey/04_vfx_3d_bake.response.md`](../research_briefs/2026_05_07_sota_survey/04_vfx_3d_bake.response.md). Pipeline review: [`docs/pipeline_reviews/02_vfx_3d_bake.md`](../pipeline_reviews/02_vfx_3d_bake.md). Headlines:

- **Deferred GPU plan in `pipelines/vfx/GPU_BACKENDS_PLAN.md` is half-stale.** Reduces from 4 backends to **Warp-primary, PhiFlow-optional**:
  - **NVIDIA Warp** ✅ — alive, validated on RTX 5090 sm_120 (CUDA 12.9, native Windows wheels). Promote to primary GPU backend.
  - **PhiFlow** ✅ — alive (PyPI 3.4.0 Aug 2025), Apache-2.0, healthy. Strength is differentiable PDE for ML training — **overkill for baked flipbooks.** Watch list only.
  - **Taichi** 🟡 — maintenance mode mid-2024 (per taichi-dev/taichi#8506). Drop.
  - **LiquidFun** ❌ — dead. Drop.
- **Skip diffusion VFX.** Sora 2 discontinued April 2026; AnimateDiff produces RGB video, not alpha-matted tileable flipbooks. Wrong tool for the bake-to-flipbook use case.
- **Real bottleneck = content authoring, not sim throughput.** The "18 of 24 palette-swap recolors" issue from review #02 is an authoring problem. Fix order matters.
- **Reordered Phase 13 priorities** (per brief, our paraphrase):
  1. **Build LLM-driven `effect_from_description.py`** — plain-language design intent → seeded `effect.json`. Sub-day scaffold; addresses the palette-swap problem at the right layer. **This comes before any GPU port.**
  2. **Then install Warp + port `particle_cpu`** — start with vortex/swirl/attraction effects where CPU bakers strain.
  3. **Mesh fracture: use Blender Cell Fracture headless** — no new install required if Blender is around.
  4. **Volumetric fog: add Schneider-Vos cloud noise** as in-place upgrade to existing numpy `baker_volumetric_fog.py`. Keep the baker we have.
  5. **Audio cue extension: `audio_clip` field on `manifest.json`** — don't adopt USD.

Action items (us, in priority order):
1. ✅ **DONE 2026-05-07 evening** — `pipelines/vfx/effect_from_description.py` built. Mirrors `pipelines/game_data/local_llm_backend.py` shape: `--backend {dry-run,vllm}`, OpenAI-compat HTTP, `guided_json` w/ Effect-schema enforcement, validates LLM output against the canonical Pydantic `Effect` model before write. Dry-run smoke test on `giant_fire_slam_wave` produced schema-valid effect.json. Cloud backends (Claude, DeepSeek) deliberately not wired per cloud-parked direction; sibling backend = 1-file addition when cloud comes back. Real LLM run requires a local vLLM server — a server-up run is queued for the next time vLLM is hot.
2. **(LATER)** Install NVIDIA Warp (`pip install warp-lang` on a fresh `pipelines/vfx/` venv) + Warp-port `particle_cpu`. Gated on (1) being done — now unblocked.
3. **(SMALL)** Schneider-Vos noise upgrade in-place on `baker_volumetric_fog.py`. (Free-wins #4 in NEXT_STEPS table — pending.)
4. **(SMALL)** Add `audio_clip` field to `manifest.json` schema + emitter.
5. **(DOC)** Mark `pipelines/vfx/GPU_BACKENDS_PLAN.md` as superseded by this brief; the four-backend plan is reduced to Warp + PhiFlow-watch. ✅ **done 2026-05-07 PM.**

#### Brief #05 — VFX shaders (`art_lab/`) (returned 2026-05-07)

Full response: [`docs/research_briefs/2026_05_07_sota_survey/05_vfx_shaders.response.md`](../research_briefs/2026_05_07_sota_survey/05_vfx_shaders.response.md). Pipeline review: [`docs/pipeline_reviews/07_vfx_shaders.md`](../pipeline_reviews/07_vfx_shaders.md). Headlines:

- **Framework validated as 2026 SOTA-shaped.** Two 2025/2026 academic papers (AI Co-Artist Nov 2025, ShadAR Feb 2026 ISMAR) implement essentially the same LLM-mutation loop we already built, with **weaker compile-failure guardrails** than ours. Useful negative result — like brief #03's Trellis2 vindication.
- **Three operational wins, all additive (no replacements, A/B comparable):**
  1. **DreamSim + LPIPS scoring backend** alongside edge-MSE in `art_lab/tools/shader_reference_score.py`. Behind a `--scorer {edge_mse,dreamsim,lpips,all}` flag. Edge-MSE stays default. ~20 ms/candidate. Single pip install (`dreamsim` + `lpips`).
  2. **Import 3 curated template families** with license sidecars: `hit_flash_2d` (Hollow Pixel), `projectile_trail_2d` (gdquest-demos), `ground_glow_2d` (godotshaders.com). Closes 3 of the 8 missing common templates flagged in review #07.
  3. **Aim the first real (non-smoke) batch at `occult_portal`** using `portal_swirl_2d` + `ring_field_2d`. The only target with a curated reference image already in hand. This is a batch run, not a tooling change.
- **Confirmed open issues (no action):**
  - **Video-to-shader has no usable open release in 2026.** Don't pursue.
  - **Production package convention does not exist as industry standard.** Brief recommends a small custom `art_lab/library/<category>/<name>/manifest.json` tier for promoted shaders. Addresses the "promoted shaders sit in `review_queues/` indefinitely" gap from review #07.
- **No texture-worker overlap.** `art_lab/` is its own lane.

Action items (us, in priority order, additive only):
1. ✅ **DONE 2026-05-07 PM** — `--scorer` flag wired into `art_lab/tools/shader_reference_score.py` with backends `edge_mse` (default), `dreamsim`, `lpips`, `all`. Edge-MSE remains default; `--scorer all` computes every metric on the same batch and emits per-row `all_scorers` map for A/B comparison. Dedicated **`art_lab/.venv`** stood up (py3.11 + torch 2.7+cu128 + dreamsim + lpips) to avoid polluting the Puppeteer venv (which is pinned to accelerate==0.28.0 and incompatible with modern peft/dreamsim). Smoke-tested on `shader_evolve_smoke_001` — edge_mse / dreamsim / lpips all produced ranked output, top candidates broadly agree across all three metrics.
2. **(SMALL)** Import 3 curated templates with license sidecars into `art_lab/shaders/templates/`: `hit_flash_2d` (Hollow Pixel), `projectile_trail_2d` (gdquest-demos), `ground_glow_2d` (godotshaders.com).
3. **(BATCH)** Run first real `shader_evolve.py` batch on `occult_portal` (no tooling change — just point the existing framework at a real target).
4. **(DOC/SCAFFOLD)** Stand up `art_lab/library/<category>/<name>/manifest.json` convention + a "promote from review_queue → library" helper script.

#### Brief #06 — Audio (returned 2026-05-07)

Full response: [`docs/research_briefs/2026_05_07_sota_survey/06_audio.response.md`](../research_briefs/2026_05_07_sota_survey/06_audio.response.md). Pipeline review: [`docs/pipeline_reviews/03_audio.md`](../pipeline_reviews/03_audio.md). Headlines:

- **Noise/static archive was a WORKFLOW failure, not a model failure.** Stable Audio Open 1.0 stays — still leading open-weights audio diffusion in 2026 (Stability went closed on 2.x line). Fix is reference clips + CLAP QA + LoRA fine-tune, not a model swap.
- **Two real model upgrades for the OTHER lanes:**
  - **TTS:** Chatterbox-Multilingual (Resemble AI, **MIT**, ~63% A/B win vs ElevenLabs, built-in emotion + paralinguistic tags). Near-strict upgrade over F5-TTS for character voicing.
  - **Music:** ACE-Step v1.5 (Jan 2026, **Apache 2.0**, royalty-free outputs, native multi-stem export). Supersedes YuE on game-tone benchmarks. `adaptive_music.py` runtime layer unchanged.
- **6 additive upgrades, all alongside existing tools (no replacements):**
  1. **(SUB-DAY)** CLAP audio-text similarity + PyMusicLooper seam validator added to `audio_qa.py`. Would have caught the noise/static pre-archive (current LUFS/peak/RMS QA can't fail on noise).
  2. **(1-2 DAYS)** Run `cc0_ingest.py` for real + extend with PANNs auto-tag + CLAP semantic index → per-biome reference clip library.
  3. **(2 DAYS LOCAL)** LoRA fine-tune Stable Audio Open per biome on curated CC0 references. (**Cloud Stable Audio 2.5 path parked** per user direction.)
  4. **(1 DAY)** Wire AudioGen / MAGNeT alongside `synth_sfx.py` — self-hosted SFX peer to ElevenLabs cloud.
  5. **(1-2 DAYS)** Wire ACE-Step v1.5 alongside `local_music_yue.py`. YuE stays as fallback initially, archived later.
  6. **(1 DAY)** Wire Chatterbox-Multilingual alongside `local_tts_f5.py`. F5 stays as fallback.
- **License caveats:** AudioGen/MAGNeT weights = CC-BY-NC (non-commercial). MusicGen-Stem = CC-BY-NC. ACE-Step + Chatterbox + Stable Audio Open LoRA = commercial-safe.
- **No texture-worker overlap.**

Action items (us, in priority order, additive only):
1. ✅ **DONE 2026-05-07 PM** — `pipelines/audio/.venv` stood up (py3.11 + torch 2.7+cu128 + laion-clap + pymusiclooper + librosa). `audio_qa.py` extended with `--clap-prompt` and `--loop-check` flags; default sanity-only path unchanged. Verified end-to-end on archived `bed_air.wav`: matching biome prompt = +0.407 ("matches"), unrelated prompt ("happy birthday party") = -0.117 ("does_not_match"). The "noise/static" archive WAV actually scores reasonably well against its biome prompt — user's verdict was about artistic quality, not prompt-content correctness.
2. **(SOON)** Run `cc0_ingest.py` for real with PANNs auto-tagging + CLAP semantic index.
3. **(MEDIUM)** Wire AudioGen alongside `synth_sfx.py` (uses existing audio venv).
4. **(MEDIUM)** Wire ACE-Step v1.5 + Chatterbox-Multilingual (each may need separate venv if dep conflicts surface; default to existing audio venv).
5. **(LATER)** LoRA fine-tune Stable Audio Open on curated CC0 references per biome.

#### Brief #07 — UI / Icons (returned 2026-05-07)

Full response: [`docs/research_briefs/2026_05_07_sota_survey/07_ui_icons.response.md`](../research_briefs/2026_05_07_sota_survey/07_ui_icons.response.md). Pipeline review: [`docs/pipeline_reviews/01_ui_icons.md`](../pipeline_reviews/01_ui_icons.md). Headlines:

- **Brief validates our review.** The "just a color swap" verdict is correct; the unblocking step is running the cloud lane + LoRA training, both already-identified.
- **Two version bumps unblock the existing cloud lane:**
  - `recraft_icons.py` → **Recraft V4 Pro Vector** (Feb 2026 rebuild, native SVG output, $0.30/SVG, ~$9 for 30 hero icons)
  - `local_diffusion_icons.py` FLUX-schnell → **FLUX.2 Klein 4B** (Apache 2.0, ~13 GB, **commercial-safe**, day-0 ComfyUI Blackwell support). FLUX.2 [dev] is non-commercial-licensed; **always use Klein 4B for shipped assets.**
- **Faction LoRA scaffold = single biggest unlock.** **AI-Toolkit by Ostris** is the 2026 community default trainer with documented Blackwell/PyTorch 2.9.1 path. 15-25 hand-curated images per faction, ~30-60 min train per faction on the 5090. Apply at inference via **rgthree's Power LoRA Loader** (one workflow, faction selector, hot-swap).
- **NO 2026 AI HUD generator exists for games.** Galileo/Uizard/v0.dev/NightCafe all produce static screenshots that don't respect 9-slice, don't reuse atlas, don't round-trip into Godot. **Viable answer:** AI for the *materials* per faction (frame metal, banner cloth, parchment), then PIL-composite as today.
- **Style-unification across the 135 mixed-source library:** ComfyUI graph (FLUX.2 Redux multi-reference + Canny ControlNet + img2img). No dedicated "icon-set unifier" exists. Canny preserves silhouettes; Reference-only is largely deprecated for FLUX.
- **Free-license library expansion:** **Tabler Icons (6128+, MIT)** is biggest *quantity* win; plus **Iconoir (1600, MIT)** + **OGA 700+ RPG (CC0)**. **Don't ingest Flaticon Fantasy RPG** (non-CC0/MIT).
- **Watch list:** StarVector (CVPR 2025, Apache 2.0) — PNG→SVG vision-language model; 1B feasible on 5090. Side experiment for AI-generated icons that vtracer mangles, not a drop-in.
- **No texture-worker overlap.**

Action items (us, in priority order, additive only):
1. **(SUB-DAY)** Add Tabler + Iconoir + OGA 700+ RPG sources to `freelib_ingest.py` (~8000 free-license glyphs added; no run yet).
2. **(SUB-DAY)** Add **FLUX.2 Klein 4B** as model option in `local_diffusion_icons.py` (FLUX-schnell stays as fallback per additive pattern).
3. **(SUB-DAY)** Update `recraft_icons.py` to target **Recraft V4 Pro Vector API** endpoints (plumbing only; no run — cloud parked per user direction).
4. **(1 DAY)** Install **AI-Toolkit by Ostris** + scaffold one faction LoRA training pipeline (curation user-gated).
5. **(USER-GATED CLOUD)** Run cloud lane for the 6 prompted icons in `prompts.json` (~$2 in Recraft V4 Pro Vector spend). Cloud parked.
6. **(USER-GATED CURATION)** Train one faction LoRA end-to-end on `v1_smoke` scaffold (needs 20-image curation per faction).

#### Brief #08 — Game Data / Balance (returned 2026-05-07)

Full response: [`docs/research_briefs/2026_05_07_sota_survey/08_game_data_balance.response.md`](../research_briefs/2026_05_07_sota_survey/08_game_data_balance.response.md). Pipeline review: [`docs/pipeline_reviews/04_game_data.md`](../pipeline_reviews/04_game_data.md). Headlines:

- **Infrastructure validated as best-in-project.** Pydantic schemas + OpenAI/Claude/synthetic/vLLM cascade + DuckDB reports + kill-dummy sim + Yarn validator + migrations + .tres export = right architecture for May 2026. **Same shape as brief #03 (Props): the 2026 SOTA story is "run what's plumbed" + a few additive tools, not a rebuild.**
- **Single highest-leverage move: run the plumbed cascade on real keys.** DeepSeek V4-Pro for bulk records (~$0.18-$0.51 per 1K records, 30-100× cheaper than Opus, OpenAI-API-compatible — drops into existing cascade). Claude Opus 4.7 for creative weight (~10% of records). 250 records at DeepSeek bulk + 25 at Opus ≈ **~$0.50-$2 total**. **Cloud parked** per user direction.
- **Five additive tools (free, additive, owned by us):**
  1. **pymoo NSGA-II** Pareto utility (`pareto_dominated_records.py` sibling to `duckdb_reports.py`) — 1 day.
  2. **fastjsonschema** or **okjson** alongside `jsonschema` (50-100× speedup) — sub-day, additive.
  3. **DSPy + GEPA** (ICLR 2026 Oral) wired into `generate_records.py` for items/abilities — 1-2 days.
  4. **`getsentry/json-schema-diff` CI gate** for migrations (BACKWARD/FORWARD/BREAKING) — sub-day.
  5. **Hash-based incremental linker** (~50 LOC) — sub-day.
- **XGrammar-2 (2026-05-04)** — 10-80× faster constrained decoding when vLLM ships compat. Watch list.
- **Sub-pipeline findings (condensed):**
  - **Combat sim:** keep `kill_dummy_sim.py`. **No RL on combat balance before combat exists.** Scripted-heuristic Monte Carlo in PettingZoo + LLM-as-tester pass (~$5/run) when ready.
  - **Dialogue:** Yarn migration is lateral. Build ~100-line static analyzer + Claude-based authoring lint instead. **Don't adopt Inworld/Convai** (runtime NPC, not authoring).
  - **Lore:** Obsidian + Smart Connections + git. **Don't buy World Anvil / LegendKeeper / Kanka / Campfire** (worldbuilding-as-product, wrong shape).
  - **Localization:** Godot gettext (.po) + Crowdin Free + Claude Haiku/DeepL pre-translate. Pseudo-localization on day one. **Don't buy Lokalise / Phrase / Smartling pre-launch.**
  - **Cross-ref:** custom linker fine through ~20K records IF lookups use `dict[id → record]` maps. Audit this. Re-evaluate at 50K.
- **No texture-worker overlap.**

Action items (us, in priority order, additive only):
1. **(SUB-DAY)** Build dedicated `pipelines/game_data/.venv` (lightweight: pymoo + fastjsonschema + dspy + gepa).
2. **(1 DAY)** Build `pareto_dominated_records.py` on top of pymoo NSGA-II as sibling to `duckdb_reports.py`.
3. ✅ **DONE 2026-05-07 evening** — `fastjsonschema` wired as additive option in `validate_records.py`. New `--validator {pydantic,fastjsonschema,both}` flag (pydantic remains default). `both` mode reports per-backend timing + record-level verdict-disagreement diagnostics — useful for confirming the dumped JSON Schemas faithfully encode the Pydantic constraints. Smoke-tested on the 14-record validated set: backends agreed on every record; **fastjsonschema 1.89x faster** even at this tiny scale (brief #08's 5-50x framing applies at the 250-record scale). Pydantic was also installed in `pipelines/game_data/.venv` (which already had fastjsonschema + pymoo + duckdb) so all three modes run from a single interpreter without polluting system Python.
4. **(SUB-DAY)** Add `getsentry/json-schema-diff` CI gate to migrations.
5. **(1-2 DAYS)** Wire DSPy + GEPA scaffold into `generate_records.py` for items/abilities (metric: schema valid + Pareto-non-dominated + embedding distance).
6. **(USER-GATED CLOUD)** Run the LLM cascade on real DeepSeek + Claude keys. ~$0.50-$2 spend.
7. **(LATER)** XGrammar-2 upgrade in `local_llm_backend.py` when vLLM ships compat.

#### Brief #09 — Per-Instance Mesh Albedo Inpaint (RETURNED 2026-05-07 evening)

Brief: [`docs/research_briefs/2026_05_07_sota_survey/09_mesh_inpaint_per_instance.md`](../research_briefs/2026_05_07_sota_survey/09_mesh_inpaint_per_instance.md). Response: [`docs/research_briefs/2026_05_07_sota_survey/09_mesh_inpaint_per_instance.response.md`](../research_briefs/2026_05_07_sota_survey/09_mesh_inpaint_per_instance.response.md). Design doc (updated post-response): [`docs/plans/PATH_2_INPAINT_DESIGN_2026_05_07.md`](PATH_2_INPAINT_DESIGN_2026_05_07.md).

Headlines:

- **Architecture A (UV-space inpaint) ruled out for this asset class.** UV fragmentation is not a goblin-specific bug — it is the expected output of area-optimization UV packing from Trellis2/Meshy, universal across the entire character roster. Architecture A fails on all of them without a semantic re-unwrap step that no 2026 tool automates.
- **Architecture B (camera-projection inpaint) confirmed as correct.** Camera-projection is UV-layout-agnostic — render from N views, inpaint in screen-space (where "chest" is always contiguous), back-project to UV. This is the 2026 industry consensus for the exact reason: UV fragmentation is irrelevant in screen space.
- **No off-the-shelf tool.** 3-step stitched pipeline: Blender headless render → FLUX.1-Fill + IP-Adapter-FLUX inpaint (ComfyUI `/prompt` API) → nvdiffrast UV back-projection → Blender GLB repack.
- **nvdiffrast** is the lightweight back-projector: `pip install nvdiffrast`, CUDA-native, no torch-version sensitivity. Full Hunyuan3D-Paint 2.1 is a quality upgrade (deferred to Phase 2).
- **Workflow order confirmed: texture-first, then rig.** Puppeteer preserves UV + albedo through skinning. Smart pattern: generate all N variant albedos → rig base mesh once → swap texture reference per variant. Avoids N rig runs.
- **Insignia and damage-states share all infrastructure.** Build insignia once; damage states are a different reference image + lower IP-Adapter weight. Not a separate system.
- **IP-Adapter-FLUX (XLabs-AI x-flux)** is the reference-identity tool. At weight 0.8–1.0, it preserves the insignia's visual identity across instances (not pixel-perfect, but sufficient for faction marking reads at gameplay distance).
- **Phase 0 skipped.** Brief returned before the PoC ran; Architecture A is already ruled out.

Action items (us, Phase 1 build):
1. ✅ **(DONE 2026-05-07 evening)** Stand up `pipelines/character_inpaint/.venv` + build 5-module pipeline. All modules shipped: `render_views_runner.py`, `comfy_inpaint.py`, `back_project.py`, `glb_repack.py`, `inpaint_variants.py`. Dry-run smoke test passed end-to-end (goblin_p × ashen_pact_brand, 6 views, 5/5 steps clean). FLUX.1-Fill + nvdiffrast GPU backends are coded — gated on FLUX.1-Fill model download (~16 GB) and GPU validation run.
2. **(QUALITY GATE)** Download FLUX.1-Fill weights → run with `--inpaint-backend flux-fill --project-backend nvdiffrast` → compare one automated variant visually. Decide if smearing is acceptable.
3. **(LATER)** Phase 2: replace nvdiffrast back-projection with Hunyuan3D-Paint projection module if smearing is unacceptable.
4. **(LATER)** Phase 3: Grounded-SAM-2 for text-prompted view-space mask generation ("the chest area" → SAM mask on each render). Removes need for hand-authored per-view masks.

#### Cross-cutting completed work (2026-05-07 evening session)

After brief sift, the following landed in the same session:

- ✅ **`pareto_dominated_records.py`** built on pymoo NSGA-II (sibling to `duckdb_reports.py`). Run from `pipelines/game_data/.venv`. Verified end-to-end on the existing 14 records — output renders correctly even when sample size is too sparse for dominance to surface anything (honest "either everything is on frontier or cohorts have <2 records" messaging). At brief #08's recommended scale (250 records via DeepSeek bulk + 25 via Opus creative), this becomes a real designer-facing balance lens.
- ✅ **Brief #09 written + dispatched-ready** — per-instance mesh inpaint workflow, the cross-pipeline gap none of #01-#08 covered.
- ✅ **Path 2 design doc written** — initial architectural shape + open questions; will be refined when #09 returns.
- ✅ **Persistence layer secured** — fresh canonical handoff at [`docs/handoffs/HANDOFF_2026_05_07_evening_brief_sift_complete.md`](../handoffs/HANDOFF_2026_05_07_evening_brief_sift_complete.md), stale handoff postscripted, 2 new memory notes (isolated-venv-per-lane, faction-inpaint-workflow-gap).

#### Briefs 03-08 (pending)

- **03 Props** — image-to-3D 2026 SOTA beyond Trellis2
- **04 VFX 3D bake** — GPU plan refresh
- **05 VFX shaders** — better than LLM-mutation framework?
- **06 Audio** — re-bake path after archive
- **07 UI / Icons** — faction LoRA + hero icons
- **08 Game Data** — ML-driven balance tooling

(03/04/05 responses already returned per file inventory; sift those next.)

---

## 🎯 Top-level vision

A complete asset **pipeline factory** for **Godot 4.5 / JK Engine / TLTE** covering every category we'll need to ship a game.

**Reframe (2026-05-06 PM):** the assets being produced today are **mostly throwaway** — except possibly the characters. The point is not to build a content library; the point is to **figure out which pipelines and workflows actually work, find the failure modes, and document the tradeoffs**. Real production content gets authored later, against pipelines that already proved themselves.

What this means in practice:

- **No content-volume targets.** "39 sounds, 135 icons, 57 effects, 24 props" are coverage proofs of the pipeline, not deliverables. Once a pipeline can hit a clean output across 3-5 representative cases, declare it proven and move on.
- **Quality bar still high.** Throwaway content does not mean low-quality content. Each proof has to actually look/sound right — bleached albedo, broken seams, fictional asset IDs, dropped collisions all count as the pipeline failing.
- **Failure modes are deliverables.** Every "this doesn't work" is as valuable as a "this works" — character pipeline became mature because we knew SkinTokens did radial topology and Mesh2Motion didn't, not because we shipped 33 GLBs.
- **Real production content is gated on user intent.** TLTE seed records, hero-prop concept PNGs, real LUFS-measured biome ambience, faction LoRAs — all wait until there's an actual game scene asking for them. The pipelines stay ready.

**Pipeline depth standard:** every pipeline gets the same level of thought and care — not necessarily the same number of tools, but the same investigation discipline:
- Survey what's available (multiple options, not just one)
- Test what we pick (verify on real assets, find failure modes)
- Document tradeoffs honestly (what's good, what's broken, when to use what)
- Update the roadmap when reality differs from the plan

Character pipeline became mature because we did this for 5+ rigging tools, 2 image-to-3D services, 3 animators. Other pipelines should reach the same maturity *of decisions*, even if they end up using fewer tools.



| Category | Status | Depth target |
|---|---|---|
| **Characters** | ✅ Mature — full pipeline | Reference depth |
| **World / Terrain** | ✅ **Mature** — 6 input modes (synthetic, DEM, WorldEngine, MESA AI, FastNoise, particle erosion) | Reached |
| **World / Tileable Textures** | ✅ **AAA** — `aaa_texture.py` uses StableMaterials; current on-disk best seam grade A / 0.00037 | Exceeded |
| **World / Props** | ✅ **Phase 11 deep-dive complete** — v2 spine + AI-route layer (HY3D-2.1 via kijai+visualbruno + Trellis2 4B local). 4×4 quality sweep on Egyptian-obelisk concept; **Trellis2 picked as default** (beats HY3D every config; even Trellis2 `low` ≈ HY3D `hero_max` for 200× less wall-clock). Shared infra: `ai_route_dispatch.py`, `trellis2_batch.py`, `TRELLIS2_PATCHES.md`. Hero PBR-textured GLB shipped (obelisk, 30s end-to-end). | Reached AI-route depth; scene integration (11C) deferred |
| **World / Scenes (composite)** | 🟡 `stage_biome_scatter.py` v3 prop_pool path **landed Phase 10A** for `scatter_multimesh` render_class; spawn-on-terrain raycast also landed. Remaining gaps: `scene_prop` scatter path (still falls back to placeholders for `fallen_log`/`tombstone_grave`/`fence_section`), camera follow, and the one-button "biome + props + ambience + VFX + HUD" demo. **Worldgen v1 broke 2026-05-06; v2 rebuild in `../../pipelines/worldgen_v2/` is the new scene target.** | Partly proven; gated on worldgen v2 |
| **World Map (political/biome layers)** | ✅ **Working** — 12 settlements, 134 rivers, 3 factions, 5 previews | Reached |
| **Coherent multi-biome world** | ✅ **Phase A done** — 4 biomes, terrain-feature-aware transitions, 3-tier views (world/regional/local), continental heightmap | Reached |
| **Region zoom (world → playable terrain)** | ✅ **Phase B done** — bbox in any world → playable bundle with fresh detail at full feature scale | Reached |
| **Macro+detail close-up shader** | ✅ **Phase C done** — `macro_detail_v1.gdshader` + Blender preview validated. AAA close-up cobblestone visible at iso angle. | Reached |
| **Real-DEM ↔ biome engine integration** | ✅ — `world_biome_engine.py --base-heightmap` accepts any terrain-bundle DEM; verified on Utah canyons + Norwegian fjord | Reached |
| **OpenTopography preset library** | ✅ — 13 presets (canyon/alpine/appalachian/dolomites/iceland/sahara + fjord/glacier/hoodoo/highlands/spires/atlas/japanese_alps); auto-selects AW3D30 for high-latitude | Reached |
| **AAA single-image PBR estimation** | ✅ — `gvecchio/StableMaterials` (OpenRAIL, ungated) wired as default `aaa_texture.py` backend; verified seam grade B on cobblestone + basalt | Reached |
| **Biome ↔ AAA-texture binding** | ✅ — `biome_texture_registry.json` + `biome_splat.py` + `biome_texture_bind.py`; auto-generates the 4 biome PBR sets, emits `biome_pbr_pack.json` | Reached |
| **Godot 4.5 biome terrain test scene** | ✅ — `stage_biome_terrain.py` + `biome_terrain.gdshader` (4-layer blender + vertex displacement + triplanar); 3 camera modes (walkable/topdown/iso); WorldEnvironment + sky + fog; animated water plane with depth-fade shoreline; ~10k MultiMesh scatter instances | Reached |
| **One-command region pipeline** | ✅ — `region_pipeline.py` chains import_dem → fantasy_edit → biome_engine → splat → texture_bind → scatter → 3 Godot scenes. Verified end-to-end on Bryce/spired. | Reached |
| **Fantasy DEM editing** | ✅ — `dem_fantasy_edit.py` with 7 styles (realistic, exaggerated, terraced, sharpened, spired, floating, mythic). Slots between import_dem and biome engine. | Reached |
| **Bulk DEM ingestion + cache** | ✅ — `bulk_pull.py` walks `data_wishlist.json` (172 named regions), caches raw TIFFs to `../../dems/` (relocated 2026-05-07). Current: 222 TIFFs / ~8.1 GB. | Reached |
| **Worldwide mystery region sampler** | ✅ — `mystery_sampler.py` generated 300 random bboxes from interesting strips (Andes, Himalayas, Scandinavia, etc). | Reached |
| **OpenTopography deep coverage** | ✅ — Default bumped COP30 (30m global), added GEBCO bathymetry merge, `--res` for high-res pulls, AW3D30 auto-pick for high-latitude. | Reached |
| **Magic / Shaders** | 🟢 5 first-party Godot templates + batch review harness | Match characters |
| **VFX / Spells (physics bake lab)** | ✅ **v2 SOTA push complete** — v1 spine (3 CPU bakers + Effect schema + 2D Godot exporter + spell-lab importer + gallery) + `export_godot_3d.py` 4 export targets (3d_billboard / decal / mesh_trail / fog_volume) + `baker_volumetric_fog.py` numpy noise → Texture3D-via-slice-atlas + 7 biome haze presets + `MeshTrail3D.gd` runtime helper + `AudioCueBus.gd` autoload (frame_changed → cue_hit driven by `manifest.extras.audio_cues`) + 24-cell element×archetype generator + 12-effect damage/impact catalogue + gallery v2 (filters/search/autoplay) + no-copy exporters. **57 effects** (3 v1 + 11 spell-lab migrated + 24 element×archetype + 12 damage/impact + 7 biome haze); 39 2D + 43 3D Godot scenes; link_validator MISSING=none ✓. GPU bakers (Taichi/Warp/PhiFlow/LiquidFun) deferred per `GPU_BACKENDS_PLAN.md`; VAT deferred per C2 §5. | Reached v2 |
| **UI / Icons** | ✅ **v3 SOTA push complete** — v2 spine + 190-slug game-icons.net curated allowlist + `--filter-by-list` + new `mit-iso-libs` source (Lucide/Phosphor/Tabler via jsDelivr CDN, 24/19/22 curated UI primitives) + `pixellab_icons.py` PixelLab adapter (plan-only default; cost-cap gated) + `suggest_icon_for_record.py` cosine-on-token-sets matcher (record→icon top-K with reasons) + `lint_icons.py` strict gating wrapper (unused / missing-tags / record↔icon mismatch / RTL review) + `hud_mockup.py --fixtures` (4 factions × 6 scenarios = 24 spot-check fixtures) + 4 new ornament drawers (chains/runes/vines/fangs → 8 total) + `lora_train.py` plan-only kohya-ss/sd-scripts scaffold (license-correct dataset prep) + `vtracer_roundtrip.py` raster→SVG round-trip + `../../ui/palettes/PALETTE_AUTHOR_GUIDE.md` per-faction design philosophy + UI tool decision tree in pipelines/ui/README.md. Catalogue: **135 icons** + 28 HUD previews + LoRA training scaffold ready for the free 5090. PixelLab live run + LoRA train run + game_data icon_id wiring still parked. | Reached v3 |
| **Audio (SFX, ambience, music)** | ✅ **v3 SOTA push complete** — v2 spine (39 sounds / 112 variants / Stable Audio Open adapter / 4-layer biome ambience / pyloudnorm) + phase-aware `loop_detect.py` (xcorr + phase coherence + env metric, closes E2 §6 monotonic-drone hole) + `ffmpeg_decode.py` optional helper (Freesound MP3 + ambience >47 s) + `openai_tts.py` plan-only default / `--run` cost-cap-gated + 6 new biome recipes (forest/desert/tundra/swamp/charred_wasteland/underwater → all 10 registered biomes covered, 142 ambience stems built) + `gallery.py` static HTML browser (autoplay + spectrogram modal + LUFS column) + `lint_audio.py` strict-audio gating wrapper (unused/mismatch/bus-sanity/ambience-coverage) + `suggest_sfx_for_record.py` cosine-tag matcher (record→sfx top-K + sfx_id_patch.jsonl) + HRTF Godot wrapper recipe (godot-resonance-audio + `SpatialEmitter.gd` fallback + `HRTFVerify.gd`) + `adaptive_music.py` orchestrator scaffold (4 example tracks × 15 placeholder stems × .tscn × `AdaptiveMusicTrack.gd`) + `AmbienceDensityAutoload.gd` per-zone density wire + `LUFS_AUTHORING_GUIDE.md` + audio tool decision tree in `../../pipelines/audio/README.md`. **39 sounds / 112 variants / 10 biomes / 142 ambience stems / 4 music tracks scaffolded.** Real Stable Audio Open bake + real music stems still parked on GPU window + license-clean open-weights music. | Reached v3 |
| **Game Data (items, lore)** | ✅ v1.5+ working — Pydantic schemas, synth/OpenAI/Claude generation, balance-target constrained mode, kill-dummy sim, migrations, schema dumps, DuckDB reports, Yarn link validator, local-LLM dry-run adapter, Godot `.tres` export, 14/14 round-trip pass. | Reached v1.5+ tooling; real TLTE content pending |
| **Props (3D decoration)** | ✅ **Phase 11 deep-dive complete** — v2 spine (13 procedural recipes / variation_sweep / 4-tier LOD / CoACD collision / Godot HLOD / billboard + kit atlases / biome_scatter_rules v3 / AAA-PBR binding) **PLUS** AI-route layer: HY3D-2.1 (kijai+visualbruno wrappers, ComfyUI workflow JSON, ~30-90s/prop balanced) + Trellis2 4B (microsoft/TRELLIS.2-4B, ~30s/prop balanced). Both produce PBR-textured GLBs end-to-end on cu130/sm_120. Trellis2 picked as default per quality sweep. New shared infra: `../../pipelines/props/ai_route_dispatch.py` (Trellis2-default dispatcher), `trellis2_batch.py` (model-load-once batch runner), wired `trellis2_route.py` (auto-resolves preset via dispatcher), `TRELLIS2_PATCHES.md` (forensics + reapply). | Reached AI-route depth; 11C scene integration deferred |
| **Engine integration (Godot exporters)** | ✅ 4 asset types (pbr_material/terrain/sprite_sheet/rigged_glb) | Reached |

---

## ✅ End-of-day 2026-05-06 — AAA texture stack + Material Anything online

**Major milestones:**

- **AAA texture pipeline (`aaa_texture.py`)** — chains variants, de-light, StableMaterials PBR for `default`/`strict` (with `derive_pbr_v2` fallback), seam repair, QA, Blender Cycles render, and quality gate. Current on-disk best is grade A / 0.00037; `cobblestone_aaa` is grade B / 0.00329.
- **FLUX.2-klein-4B** installed (Apache 2.0, ungated, ~16 GB total). Drives texture generation via ComfyUI server.
- **Material Anything status clarified** — mesh-driven PBR (`material_anything_adapter.py`) runs end-to-end but is low-quality/bleached; standalone flat image-to-PBR (`ma_image2pbr.py`) is broken for 2D textures. StableMaterials is the production 2D PBR backend.
- **MESA AI terrain** — text → DEM heightmap, working at ~7 it/s on 5090.
- **Magic/World Art Lab built** — 5 Godot shader templates (ring/beam/dissolve/shield/portal) + batch review harness with non-OCR scoring.
- **World Map generator** — full G-deep-dive contract (rivers, roads, settlements, landmarks, labels, fog, factions) in pure Python.
- **Biome decoration compiler** — kit + terrain + map → 9818 scatter + 603 decal placements with mask-based blue-noise sampling.
- **3 research reports reviewed** (C VFX, E audio, F game data) — audio and game-data v1s have since landed; VFX remains scoped.

**New tools added (textures):** flux_seamless, variant_select, delight, stablematerials_image2pbr, render_ma_mesh, flux_upscale, palette_lock, blender_preview, biome_texture_bind, aaa_texture (orchestrator).

**New tools added (other):** mesa_terrain, fastnoise_height, particle_erosion, worldengine_to_bundle, generate_world_map, dress_biome, shader_compile_preview, shader_batch_review.

**Setup/build scripts in `D:\wsl\`:** install-pytorch3d-cuda-ma, install-kaolin, stub-pulsar-ma, download-ma-extra-models, install-material-anything, test-materialanything, probe-* (~10 reproducible build scripts).

---

## ✅ End-of-day 2026-05-05 — what got done

- Pipeline review across all 14 character scripts; 3 confirmed bugs found and fixed:
  - `pack_sheet.py` animation jitter (per-frame independent crops → union bbox per angle)
  - `pixel_art.py` color shimmer (per-frame palettes → shared palette across animation)
  - `bake_sprites.py` camera math (no-op ternary + missing radius_z)
- All 33 Meshy assets batch-preprocessed (30/30 succeeded in 6.8 min; 3 already done).
- Mesh2Motion installed as Mixamo alternative (humanoid + fox + bird + dragon skeletons).
- Asset directory tree expanded: `world/`, `vfx/`, `ui/`, `audio/`, `game_data/`, `skills/`, `pipelines/`.
- Texture pipeline v0 written and tested (procedural test_stone → albedo + normal + roughness + ao + Godot `.tres`).
- Terrain pipeline v0 written and tested (mountains + islands biomes; 16-bit heightmap + hypsometric preview + normal map; FBM noise + thermal erosion).
- Props pipeline written (chains existing Meshy + preprocess; untested).
- SpellLab inventoried: 10 GB existing physics sandbox at `D:\spell lab\`. Verdict: **complete rewrite** with content-first mindset.

---

## 🏗 Top priorities going forward (revised 2026-05-06 PM)

### Phase 11 Props deep-dive — ✅ COMPLETE (2026-05-06 PM)

**What landed:**
- HY3D-2.1 install proven on cu130/sm_120/Win11 (3 source patches: `trust_remote_code`, Chinese-print Unicode, NVIDIA driver upgrade 592→596). Real PBR-textured GLB end-to-end via visualbruno node pack.
- Trellis2 4B install proven on the same machine (3 source patches in `flex_gemm`: DLL search dirs, missing `triton` submodule pure-torch fallback, sentinel + dtype safety). Real PBR-textured GLB end-to-end via microsoft/TRELLIS.2-4B.
- 4×4 quality sweep on a real Egyptian-obelisk concept. **Trellis2 wins visually at every config** — even Trellis2 `low` (49k faces / 1024² / 4s postprocess) beats HY3D `hero_max` (100k / 2048² / 677s).
- **Trellis2 picked as default** for props going forward. HY3D kept as ComfyUI-integration fallback for biome scatter.
- Shared workflow infra: `ai_route_dispatch.py` + `trellis2_batch.py` (model-load-once) + wired `trellis2_route.py` + `TRELLIS2_PATCHES.md`.
- 6 ../audits/REVIEW.md-grade patches discovered + fixed during the deep-dive. `AB_hy3d_vs_trellis2_2026_05_06.md` documents every patch + the visual A/B + the dispatch matrix.

**What was found and is now obvious in hindsight:**
- AI-route quality is **concept-quality-bottlenecked, not model-bottlenecked**. Same HY3D model on a flat-polygon placeholder vs a real Egyptian obelisk: identical mesh stats, dramatically different output. Strong signal for what HY3D will do with photo-quality input.
- **Geometry knobs > texture knobs on HY3D**: bumping octree 384→512 + max_facenum 40k→100k actually got *faster* (74s vs 90s) while doubling polycount. Going to 2048² textures alone pushed wall-clock 90s → 387s. HY3D `hi_paint`/`hero_max` configs are not worth their wall-clock.
- **Trellis2 mesh gen is one-time per concept (~23s), postprocess is fast (4-20s)**. Batch runner amortizes the model load cost across N concepts.

**What's deferred (still on the books, NOT dropped):**
- **Phase 11C scene-integration final-mile** — postprocess orchestrator landed (✅), drop into a real Godot biome scene still pending. Gated on world-gen recovering. ~30 min of work once a working biome `.tscn` exists.
- **Multi-prop generalization test (N=1 → N≥3)** — current sample is one Egyptian obelisk. Confidence is moderate, not high. Drop 3-5 different concept types (mushroom / crate / weapon / fountain / statue) through `trellis2_batch.py` to confirm Trellis2 generalizes beyond carved-stone hero props. Gated on either user-provided concept PNGs or `OPENAI_API_KEY` for `concept_gen.py`. ~5 min of GPU per prop.
- **Hunyuan3D-Omni pilot** (per Phase 11D-bis EXPANSION_PLAN entry) — geometry-only, bbox/voxel control. Pass criteria: bbox-conditioned envelope ±10% on long axis. Run only if envelope-fit becomes an issue.

---

### Where things stand (2026-05-07)

**Closed deep-dives:**
- **Phase 11 — Props.** A grade. HY3D-2.1 + Trellis2 both proven; Trellis2 picked as default; postprocess orchestrator landed; obelisk hero-prop shipped to `../../godot_pack/props/`. See `../handoffs/HANDOFF_phase11_props_2026_05_06.md`.
- **Phase 12 — Audio.** A grade. Stable Audio Open 1.0 GPU bake on all 10 biomes; 142 real stems / 56 MB. See `../handoffs/HANDOFF_phase12_audio_2026_05_06.md`.

**Open / blocked:**
- **Worldgen v1 broke late 2026-05-06.** v2 rebuild active at `../../pipelines/worldgen_v2/` (milestone 1 = terrain-only). Outputs to `D:\assets\worldgen2\`. Live source of truth: `../../pipelines/worldgen_v2/README.md` + `docs/superpowers/specs/2026-05-06-worldgen-v2-design.md`. **This blocks Phase 11C scene-integration AND the cross-pipeline composition demo.**

### What comes next

Three viable directions; pick by user intent.

**A. Phase 13 — VFX deep-dive (parallels Phase 11/12 install-pain shape).** ~half day. 57 effects catalogued + CPU bakers running, but Taichi/Warp/PhiFlow GPU bakers deferred. Same shape: GPU adapter exists, install pain unknown until first run, visible end-product (real fluid/MPM/falling-sand effects). Doesn't block on worldgen. Closes another pipeline at A-grade.

**B. Worldgen v2 status check + push.** ~30-90 min. v2 has its own README + design spec but root canonical docs don't reflect what milestone 1 actually does today. Quick recon would surface whether v2 is close to a usable scene target (which would unblock 11C + the composition demo) or far (skip until later).

**C. Operational closeouts that don't need new development.** ~30 min total:
- **Listen-test Phase 12 ambience** (you, in any audio player) — confirm the bakes actually sound right
- **Re-export Phase 12 audio to Godot import format** via `ambience_pack.py` — `../../audio/godot/` still has stale v3 exports
- **Multi-prop generalization test (N≥3)** — drop 3-5 concept PNGs through `trellis2_batch.py`, confirm Trellis2 works beyond carved-stone hero props

### Other deep-dive candidates (lower priority)
- **Game-data** — plumbing solid; real TLTE seed content authoring is a user-intent task, not engineering
- **UI** — 135 icons solid; LoRA training scaffold exists but never run

Recommended ordering: **B (worldgen v2 recon) → A (Phase 13 VFX)** if v2 is far, or **B → cross-pipeline composition demo** if v2 is close. C items are small enough to interleave.

---

### Background priorities (parked while Phase 11 deep-dive ran)

**All five formerly-vapor categories reached v2/v3 SOTA with working tooling.** Every category now has at minimum: a Pydantic/contract schema, a real CPU-runnable generator, optional cloud adapter gated on env keys, a Godot 4.5 drop-in, and a strict-lint gate. See `HANDOFF_<name>_<v>_2026_05_06.md` per pipeline.

**The framing for what comes next** (per 2026-05-06 PM reframe): the open work is **pipelines we have not yet proved**, not more output volume from the ones we have. A pipeline counts as proven when:
1. It has at least one CPU-runnable / dry-run-safe path end-to-end
2. It produced at least one clean output across 3-5 representative cases
3. Its failure modes are documented (../audits/REVIEW.md / HANDOFF post-mortems)
4. Its outputs round-trip cleanly into Godot or pass cross-pipeline link_validator

By that bar: characters / terrain / textures / world-maps / props / UI / audio / VFX / game_data are all proven. The next priority work is **proving the pipelines that aren't proven yet**, polishing the seams between them, and unlocking the GPU-gated lanes.

### Tier 0 — Cross-pipeline integration (the seams)
The pipelines all individually work. The work that is left is making them feed each other cleanly. This is the highest leverage work right now:

- ~~**`stage_biome_scatter.py` v3 prop_pool pickup**~~ ✅ **DONE Phase 10A** for `scatter_multimesh` render_class. Reads `biome_scatter_rules.json` v3 prop_pool, samples per instance, emits per-LOD chunked MultiMesh + `metadata/prop_glb_path` for runtime mesh swap. **Remaining**: `scene_prop` render_class path (per-pick PackedScene Node3D children for low-density props like `fallen_log`/`tombstone_grave`/`fence_section`).
- ~~**Walkable player spawn-on-terrain raycast**~~ ✅ **DONE Phase 10A** in `stage_biome_terrain.py`. Player capsule now spawns ~1 m above terrain at the configured XZ instead of falling in from a fixed Y.
- **Comparison-scene camera follow** — top-down + iso scenes pan with the player when in walkable mode. Lets us validate the world from multiple angles in one session.
- **Cross-pipeline reference resolver pass** — link_validator MISSING is at 0, but UNUSED is high (131 unused icons / 55 unused vfx / 38 unused sfx). Either we wire game_data references to them in one pass, or we explicitly mark them as "library, not record-bound" so UNUSED is a real signal again.
- **One-button "prove the seams" demo** — a single command that takes one biome region, drops a player, scatters real props from the prop library, runs ambience from the audio pipeline, plays one VFX from the catalog when the player presses a key, and renders the HUD. If that works end-to-end it proves the entire factory works as one system.

### Tier 1 — Pipelines not yet proved
These are pipelines where we have either a stub, a research brief, or zero — and they belong on the same maturity bar as the rest. Pick by cost-of-proof, not by content urgency:

- **Animation/dialogue/audio sync** — mouth-sync (Wav2Lip / SadTalker), gesture sync, beat-synced VFX. None of these have a pipeline today. Brief or pilot, not a full SOTA push.
- **Cutscene / cinematics** — Godot's AnimationPlayer + camera shot composition + audio mix. We have all the inputs (characters, props, biomes, VFX, audio); the seam from "asset library" to "linear cinematic" is unbuilt.
- **Quest / scripting data** — Yarn link validator exists; the quest *graph* (preconditions, branches, rewards) does not. One Pydantic schema + one validator + one Godot codegen pass.
- **Save / load / persistence schema** — what does a TLTE save file look like? Pydantic schema + migration runner + Godot Resource codegen, mirrors the `game_data/` shape.
- **Localization** — TOML/PO bundles, key-stability checker, Yarn-aware extractor. Every pipeline that emits text needs to feed this.
- **Performance budgets / profiling pipeline** — frame-time / draw-call / VRAM checks per scene. Right now we generate scenes blind to whether they hit 60fps on a target GPU.
- **Asset gallery (cross-pipeline)** — UI v3 + VFX v2 + Audio v3 each have their own gallery.html. A factory-wide one (browse every asset across every pipeline in one page) is unbuilt and is the natural counterpart to link_validator.
- **Cross-pipeline manifest (`factory.jsonl`)** — every asset's provenance, parameters, hashes, license, license-trap status. Useful for diffing, regen, audit. Mentioned in Tier 3 today; promote to Tier 1 since several pipelines now emit half of what's needed.

### Tier 2 — Existing-pipeline polish (proven, but hands-on improvements)
Quality-of-life upgrades on pipelines that already work. Not blockers:

- **TIFF cache pruner** — `prune_dems.py --keep-recent 30` (D: drive at 100% on 2026-05-06; this is now a real constraint, not a theoretical one).
- **Procedural water level** (current sea level is hard-coded 0.32 × 64 = 20.48 m; tie to actual heightmap min/avg).
- **Ortho cel-shader** post pass on the iso scene (banded lighting + Sobel edge for "drawn 2D" feel).
- **Polyhaven / ambientCG fallback path** in `aaa_texture.py` for "I just want a pre-made decent texture, not 5 minutes of generation."
- **Mesh2Motion test on hellhound** (quadruped path) — FBX prepped at `D:\assets\meshy\mixamo_ready\hellhound.fbx`. Outstanding capability test.
- **SkinTokens on abstract topology** (eye_horror) — does SOTA neural rigger handle radial topology? Outstanding capability test.
- **Trellis2 inference smoke test** — image-to-3D backup is ready; never run. Outstanding capability test.

### Tier 1 — Worldgen swap-points (Phase 1) ✅ LANDED 2026-05-06

Refactored the world-gen pipeline to match the character-pipeline's swap-able pattern. Four new swap-points + a declarative config layer:

1. **Shader registry** at `../../godot_pack/shaders/shader_registry.json` with presets `topdown` (default), `triplanar`, `hextile` (RESERVED), `heightblend` (RESERVED). `--shader-preset NAME` picks one.
2. **Splat mode** — `biome_splat.py --splat-mode {gaussian, soft, hard, height_blend}`.
3. **Per-world terrain extents** — `--use-real-extents` reads real bbox span + elev range from upstream `terrain.json` / `tile_grid.json` via new `dem_meta` block in world.json. Default stays at legacy 512m × 64m diorama scale (multi-km worlds need scatter density / tile_meters retuning to look right at scale).
4. **Region config schema** `region.config.v1` at `../../art_lab/biomes/regions/*.region.json`. `region_pipeline_from_config.py` walks one or many configs.

Pattern matches `../../meshy/batch_pipeline.py`. Architecture audit + status table at [../../_archive/worldgen_2026_05_07/docs/worldgen_v1/WORLDGEN_ARCHITECTURE.md](../../_archive/worldgen_2026_05_07/docs/worldgen_v1/WORLDGEN_ARCHITECTURE.md) (v1-era, archived). Schema reference at [../../art_lab/biomes/regions/README.md](../../art_lab/biomes/regions/README.md). End-to-end verified on death_valley_basin.

**Phase 2 next** (research-driven quality wins): implement hex-tile shader (Mikkelsen 2022), height-blend shader, BC7/BC5 reimport, Real-ESRGAN x4plus offline upscale.

### Tier 1 — Regional-raster unlock ✅ SOLVED 2026-05-06

OpenTopography's `/globaldem` endpoint refuses LINZ1m / ArcticDEM / REMA regardless of name spelling, EPSG hint, or projected bbox. The OT `/rasterSubmit` POST flow (form action on `/arcticDem`, `/linzDem`, etc) is a UI job-queue requiring browser session auth — not a programmatic API. **Bypassed entirely** by going to the providers' open S3 buckets via STAC:

- ArcticDEM (2m / 10m / 32m) and REMA (2m / 10m / 32m): `https://stac.pgc.umn.edu/api/v1/` → `s3://pgc-opendata-dems/`
- LINZ NZ 1m (DEM/DSM): static catalog `https://nz-elevation.s3-ap-southeast-2.amazonaws.com/catalog.json` → `s3://nz-elevation/`

No API key, no quota, no auth. `../../pipelines/terrain/fetch_regional_stac.py` does STAC bbox-search → rasterio windowed-read → reproject from native EPSG (3413/3031/2193) to 4326 GeoTIFF. Wired into `import_dem.py` via new `pgc_stac` and `linz_stac` endpoint types. **Verified end-to-end**: ArcticDEM10m at Disko Bay, REMA10m at Mt Erebus, LINZ1m at Milford Sound (Godot scene built). Use no-underscore names: `ArcticDEM10m`, `REMA10m`.

See [../reference/OPENTOPO_API.md](../reference/OPENTOPO_API.md) "Regional rasters: SOLVED" section for full details + how the discovery happened.

### Tier 2 — Phase B in progress (OT+ confirmed 2026-05-06)
1. ✅ **USGS 1m unlocked + verified.** Half Dome pulled at 1712×1717 px, 8.5 MB. Pipeline + cache work.
2. ✅ **PIL decompression-bomb cap raised** (was rejecting 200M+ pixel TIFFs).
3. ✅ **NoData sentinel sanitization** (USGS uses -999999; replaced with valid min).
4. ✅ **`tile_stitch.py` built** — multi-tile composer for regions over the per-call km² limit. Verified 2×2 Yosemite USGS10m, seamless.
5. ✅ **Bulk-pull quota bumped** to 400/24h (OT+ tier).
6. ✅ **`stitched` tier added to wishlist** (10 regions: Yosemite-full-1m, Bryce-extended, Grand Canyon full, Mt St Helens flank, Rainier full, Crater Lake full, Death Valley basin, Olympic Peninsula, Aconcagua massif, fjordland-west full).

Remaining for Phase B:
- `bulk_pull.py --tier showcase` — 14/20 output dirs (6 regions had no USGS1m coverage, expected). All 13 cached regions now built into Godot scenes via `bulk_build_scenes.py`.
- `bulk_pull.py --tier premium` — 50/50 output dirs ✅
- `bulk_pull.py --tier standard` — 1/62; underway in current session.
- `bulk_pull.py --tier bathymetric` — running this session.
- Tile-stitched recipes from the `stitched` tier — **1/10 done (yosemite_full_1m, marquee scene built)**; remaining 9 runnable individually via `tile_stitch.py`.
- `bulk_pull.py --wishlist art_lab\biomes\data_wishlist_mystery.json` — 0/300; bulk runnable.
- **Catalogue auto-generator** — `bulk_build_scenes.py` covers showcase tier; extend to walk premium/stitched/regional tiers too.
- **Character-cam ortho** — `--cam character` flag added to `stage_biome_terrain.py`. All 16 existing scenes re-staged + screenshotted at character scale (D:\tmp\scene_shots\character\).

### Tier 3 — GPU-window flips (queued, no new code)
Every adapter is built and dry-run safe. When the 5090 is free, run these in order; ~1 week of GPU time drains the entire backlog:

1. ~~**Stable Audio Open** — biome ambience real bake~~ ✅ **DONE Phase 12 (2026-05-06 PM).** 142 stems / 10 biomes / 56 MB. License gate + HF auth + 2 patches documented.
2. **FLUX.1-schnell + LoRA train** — real icon set + per-faction icon LoRA (kohya-ss scaffold ready at `../../ui/lora/`).
3. ~~**Trellis2 image-to-3D smoke test**~~ ✅ **DONE Phase 11 (2026-05-06 PM).** Trellis2 4B proven end-to-end on RTX 5090 / cu130 / Win11 with PBR-textured GLB on the Egyptian-obelisk concept; picked as default AI route for props. 3 patches documented in `../../pipelines/props/TRELLIS2_PATCHES.md` + ../audits/REVIEW.md.
4. **Hunyuan3D-2.5 prop bake** — open-weights alternative to Trellis2 + Meshy.
5. **Taichi / Warp / PhiFlow VFX bakers** — replace CPU baker fallbacks for fluid/MPM-class effects.
6. **F5-TTS** — real voice for `openai_tts.py`'s plan-only NPC lines.
7. **vLLM + xgrammar** — local constrained-gen for game_data `--backend local`.
8. **Wan 2.5 + flipbook extract** — video → flipbook for cinematic VFX or hero animations.
9. **YuE music pilot** — license-clean open-weights stems for `adaptive_music.py`'s placeholder tracks.

Each lane runs independently; each finishes when its proof-cases pass.

### Tier 4 — Open-weights / ComfyUI expansion (Phase 9)
Phase 9 foundation shipped (`comfy_runner.py` + 9 workflow JSONs + 12 scripts). Remaining work is **infrastructure, not pipelines** — installing the missing custom node packs (Hunyuan3D / IP-Adapter / F5 / Wan / BiRefNet / Depth) and confirming each workflow runs through the shared headless host. Treat this as a one-time setup task, not a pipeline build.

### Cross-cutting infrastructure (pre-shipped)
- ✅ `../../pipelines/_meta/link_validator.py` — game_data ↔ ui/vfx/audio/props reference checker; **MISSING: 0** as of 2026-05-06 PM.
- ✅ `../reference/CLOUD_KEYS.md` — env-var index with 5 active + 6 stubbed.
- ✅ `EXPANSION_PLAN.md` — living checklist for all phases.
- ✅ `../../DOCS_INDEX.md` — doc ownership map.

### Round 3 research (when actually needed)
Round 1 (A-J) and Round 2 (D + C2/E2/F2/J2) and Round K (open-weights) are done. Round 3 is gated on **a concrete pipeline gap surfacing**, not on "we should research X." Examples that *may* surface:
- Cinematic / cutscene composition workflow in Godot 4.5
- Mouth-sync (Wav2Lip vs SadTalker vs newer) for NPC dialogue
- Performance-budget profiling pipeline for 1024² + scattered scenes

### Stretch / research-mode goals (no current driver)
- **Procedural-from-real terrain learning** — see [../../research/proceduralize_dem.md](../../research/proceduralize_dem.md). Four approaches surveyed. Parked until either (a) the cached catalogue is ~600 regions deep or (b) a real game scene asks for a procedural variant of a real DEM.
- **Cross-DEM blending** — pull macro shape from one preset, micro detail from another. "Norwegian fjord macro + Bryce hoodoo small-scale." `dem_fantasy_edit.py` could grow a `--source-detail <other_dem>` mode.
- **Multi-asset thumbnailer** — one command renders thumbs for everything in the factory. Folds into the Tier 1 cross-pipeline gallery.

---

## 🌄 Terrain Reality

The old terrain depth checklist is done or superseded. Current terrain/world-gen reality:

- ✅ Synthetic, FastNoise, WorldEngine, OpenTopography/Mapzen DEM, MESA AI, hydraulic/particle erosion paths all exist.
- ✅ Bundle contract emits 16-bit height, normal, splat, biome labels, vegetation density, water/flow masks, previews, metadata, and Godot collision resources.
- ✅ Region pipeline composes real DEM → fantasy edit → biome paint → splat → StableMaterials texture bind → scatter → 3 Godot scenes.
- ✅ OT+ data pipeline is active with cache/resume/quota tracking, catalog search, USGS1m support, and tile-stitch support.
- 🟡 Remaining terrain work is polish/catalogue, not core capability: player spawn-on-terrain, follow cameras, procedural water level, cache pruning, stitched recipe batch, and larger biome variety.

---

## 🪄 SpellLab v2 — proposed rewrite

The current `D:\spell lab\` is a physics research lab with 17 engines and a browser UI. The engine survey was correct work — it inventoried what's available. The gap is that **the engines were installed but never actually exercised in depth.** The wrapper/scaffolding got built; the experiments didn't happen.

**The fundamental issue:**
- **Engine-first**, not content-first
- No spell *catalog* — you can't browse the spells you've built
- No clear path from prototype → game-ready spell artifact
- Naming reflects research ("warp_blackhole_fit") not gameplay ("teleport", "vortex", "frostbolt")
- **Engines are untested at depth** — we don't know what each is actually good at because the wrapper effort consumed the time

### Proposed v2 mindset

**Important reframe: this isn't just about spells.** Physics engines generate animated visual data — that data feeds into spells, environmental VFX (waterfalls, chimney smoke, dust storms), projectile trails, destruction sequences, ambient atmosphere. Anywhere you want "this thing happens visually but the gameplay doesn't need live physics."

**Bake-once, play-many.** Most outputs are **baked offline** (run the simulation once, save the resulting frames as PNG sequences or flipbook sheets). The game plays those frames back like sprite animations — cheap at runtime, expensive once. Same model as characters: we rig + animate offline; the game plays the sprite. The physics engines are essentially **VFX bakers** for most use cases.

The exception is **runtime engines**: LiquidFun (real-time Box2D fluid) and GPU CA (falling sand) actually run in-game during play. Those are rare — most spell/VFX work is baked.

So SpellLab → "VFX Lab" might be a more honest name. It produces:
- Spell flipbooks
- Environment effect flipbooks (waterfall, fire, smoke, etc.)
- Particle data for runtime spawning
- Material rules (for the runtime engines)
- Shader stubs

**Two layers, both done with care:**

1. **Engine investigation layer** — actually use each engine's capabilities. Build one strong demo per engine that exercises what makes it unique. Document what it's good at, what it's bad at, when to reach for it. This is research that gets *finished*, not started.
2. **Content layer (baked artifacts)** — author specific VFX/spell entries. Each picks the engine that fits. Output is game-ready PNGs/JSON/shaders.

**Effects are content, not experiments.** You author an entry. The system bakes artifacts. The game plays them back.

```
D:\assets\vfx\               ← all baked visual effects (was "skills")
├── README.md
├── catalog\                 ← every effect, browsable
│   ├── spells\
│   │   ├── frostbolt\
│   │   │   ├── effect.json  ← canonical definition (name, kind, params)
│   │   │   ├── flipbook.png
│   │   │   ├── particles.json
│   │   │   ├── audio.cue.json
│   │   │   └── godot\
│   │   │       ├── frostbolt.tres
│   │   │       └── frostbolt.gdshader
│   │   ├── teleport\
│   │   └── vortex\
│   ├── environment\         ← non-spell baked VFX
│   │   ├── waterfall_small\
│   │   ├── chimney_smoke\
│   │   ├── dust_storm\
│   │   └── torch_flame\
│   ├── projectiles\         ← arrow trails, bullet streaks, etc.
│   └── destruction\         ← rubble, glass shards, explosions
├── pipelines\
│   ├── engines\             ← one demo per physics engine
│   │   ├── taichi_demo.py   ← MPM/sand/fluid (general-purpose baker)
│   │   ├── warp_demo.py     ← differentiable particles
│   │   ├── liquidfun_demo.py← Box2D fluid (runtime-friendly)
│   │   ├── splisplas_demo.py← high-quality SPH (offline ref)
│   │   ├── mantaflow_demo.py← FLIP/Eulerian
│   │   ├── ca_demo.py       ← GPU falling-sand
│   │   ├── voronoi_demo.py  ← fracture
│   │   ├── physx_demo.py    ← rigid bodies
│   │   ├── phiflow_demo.py  ← differentiable Eulerian
│   │   ├── newton_demo.py   ← Warp-based multi-physics
│   │   ├── genesis_demo.py  ← unified
│   │   ├── mujoco_demo.py   ← articulated
│   │   ├── brax_demo.py     ← batched JAX rigid
│   │   ├── jaxmd_demo.py    ← differentiable particles
│   │   ├── difftaichi_demo.py
│   │   ├── sandspiel_demo.py← falling sand
│   │   └── README.md        ← when-to-use-which guide
│   ├── bake.py              ← author tool: read effect.json → call right engine → write artifacts
│   ├── audio_synth.py       ← procedural SFX
│   └── godot_export.py      ← compose all artifacts into Godot resources
└── tools\
    ├── catalog_browser.py   ← thin web UI (browse, preview, edit effects)
    └── from_old_lab.py      ← migration: pull useful bits from D:\spell lab\
```

The current `D:\assets\skills\` and `D:\assets\vfx\` directories already exist; we'd consolidate into `vfx\` since it's the more general name.

### Spell.json schema (proposed)

```json
{
  "id": "frostbolt",
  "name": "Frostbolt",
  "school": "elemental.cold",
  "tier": 1,
  "cost": {"mana": 12, "cooldown_sec": 1.5},
  "shape": "projectile",
  "visual": {
    "engine": "taichi",
    "preset": "ice_shard",
    "color_grade": [0.6, 0.8, 1.0],
    "duration_frames": 24
  },
  "physics": {
    "speed": 18.0,
    "lifetime_sec": 2.0,
    "collision": "first_hit"
  },
  "on_hit": {
    "damage": {"cold": 24},
    "status": [{"id": "chilled", "duration_sec": 3.0}]
  },
  "audio": {
    "cast": "cast_cold_short",
    "travel": "loop_ice_whoosh",
    "impact": "impact_ice_crack"
  },
  "lore": "A shard of crystallized winter, forged in an instant.",
  "tags": ["cold", "single-target", "low-cost"]
}
```

This is the **canonical artifact** that the game consumes. Pipelines just generate the visual/audio/godot files referenced by the spell.

### What survives from SpellLab v1

**Everything stays available.** All 17 engines were correctly identified as relevant — we just didn't finish testing them. The v2 work is to:

- Keep all engines installed (they're already set up; that work is done)
- Build **one capability demo per engine** that actually uses it for something spell-relevant. Each demo is a proof point: "here's what this engine does well." A few hours per engine, ~3-5 days total to cover all 17.
- Tag each engine: "primary" (use often), "specialty" (specific use case), or "reference" (good ideas but not building on)
- Then build the content layer on top

### What gets reorganized

- The `scenarios.json` schema gets replaced by per-spell `.json` files (spells become individual content artifacts with their own folder)
- The browser UI becomes a *spell catalog browser*, not a *scenario runner*
- "warp_blackhole_fit" type names become "vortex.frostbolt.json" type names (gameplay-relevant, not engine-relevant)

### Decision needed from you

1. **Migrate or replace?** Should v2 live at `D:\assets\skills\` and treat `D:\spell lab\` as archive-only? Or rebuild in-place?
2. **Authoring UX?** Do you want a web UI (like current SpellLab), a CLI, both, or just JSON files in an editor?
3. **Game integration?** How does the game *currently* consume spells? That dictates the export format.

---

## ⏸ Pending validation tasks (deferred from earlier)

These were "Phase 1" before scope expanded. Still worth doing eventually:

- Mesh2Motion test on hellhound (quadruped path) — FBX prepped at `D:\assets\meshy\mixamo_ready\hellhound.fbx`
- Trellis2 inference smoke test (image-to-3D backup is ready)
- SkinTokens on an abstract creature (eye_horror) — does SOTA neural rigger handle radial topology?

---

## 🗺 Recommended order of operations (revised 2026-05-06 PM)

If we want the most leverage per hour, given the "pipelines-first, content-thin" reframe:

1. **Prove the seams** — scatter v3 pickup ✅ done, walkable spawn ✅ done, **scene_prop scatter path + camera follow + one-button "prove the seams" demo still owed**. Demo is the test of whether 22+ individually-proven pipelines actually compose. Gated on worldgen v2 reaching a usable scene target.
2. **Sweep the cross-pipeline UNUSED count down** — either wire game_data references to the existing icons/vfx/sfx assets, or mark them library-only so link_validator UNUSED becomes a real signal again.
3. **Build the next unproved pipelines** (Tier 1 above) — pick by cost-of-proof, not content urgency. Start with whichever is the cheapest to dry-run-prove. Quest schema or save-load schema are likely cheapest.
4. **Run the GPU-window flips** (Tier 3) when the 5090 is free — no new code, just running already-built adapters end-to-end.
5. **Cross-pipeline gallery + factory.jsonl manifest** — once the seams demo works, the natural next step is browsing the whole factory output in one place.
6. **Round 3 research** — only when a concrete pipeline gap surfaces. Don't pre-emptively research.

Real production content authoring (TLTE seed records, hero-prop concept PNGs, real ambience bake) sits underneath all of this — gated on user intent, not on pipeline readiness. The pipelines stay ready.

---

## 📊 Pipeline parity scorecard

A grading exercise: how close is each pipeline to character-pipeline depth?

| Category | Generation | QA / validation | Engine export | Authoring / orchestration | Score |
|---|---|---|---|---|---|
| Characters | A | A- | B | B- | **B+** |
| Terrain / region | A | B+ | A- | A- | **A-** |
| Textures | A- | B+ | B+ | B+ | **B+** |
| World maps / biomes | B+ | B | B | B | **B** |
| Props | A (13 proc Blender + variation sweep + LOD chain + **HY3D-2.1 + Trellis2 both running, both producing PBR GLBs end-to-end**; ai_route_dispatch picks Trellis2 by default) | A (validator + 4-tier LOD + CoACD + billboard + kit atlas + AAA-PBR binding report + AI-route A/B doc with quality sweep + 6 ../audits/REVIEW.md patches documented) | A- (Godot 4.5 HLOD + PBR binder + multimesh templates + collision; scene-integration deferred to 11C) | A- (`trellis2_batch.py` model-load-once orchestrator + dispatcher + wired `trellis2_route.py` adapter + `TRELLIS2_PATCHES.md` forensics) | **A** |
| Scenes composite | B- | C | B | C | **C+** |
| Shaders | B | B | C+ | B | **B-** |
| VFX | B+ (3 CPU bakers + volumetric_fog + 24-cell element×archetype + 12 damage/impact + 7 biome haze stubs; GPU bakers gated) | B+ (link_validator + gallery v2 filters + element/archetype/export-target tagging) | A- (4 export targets: 2d / 3d_billboard / decal / fog_volume / mesh_trail; runtime helpers MeshTrail3D + AudioCueBus; no-copy exporters → 81MB total) | B+ | **B+/A-** |
| UI/Icons | A- (37 synth + 98 freelib via curated allowlist + 3 cloud lanes (OpenAI/Recraft/PixelLab) + FLUX schnell + LoRA train scaffold + vtracer round-trip + Lucide/Phosphor/Tabler MIT/ISC chrome) | A- (135-icon catalogue + 8 ornament drawers + 24 HUD scenario fixtures + suggestions.md tag-overlap matcher) | A- (4 real HUD .tscn per faction + 24 fixture previews + Theme + AtlasTextures + 60 ext_resources) | A- (frames_manifest, hud_manifest, license-aware ingest manifest, lint_icons strict report, suggestions json+md, lora plan metadata) | **A-** |
| Audio | A (39 SFX + 142 real Stable Audio Open ambience stems / 10 biomes / 56 MB + openai_tts adapter + ffmpeg decode helper + adaptive_music orchestrator) | A (true LUFS + phase-aware loop_detect + lint_audio strict-audio + audio_qa per-variant + suggest_sfx_for_record + LUFS_AUTHORING_GUIDE + Phase 12 patches doc) | A- (Randomizer + BiomeAmbienceController + AmbienceReverb bus + 4-second crossfade + AmbienceDensityAutoload + AdaptiveMusicTrack + SpatialEmitter HRTF fallback. NOTE: `../../audio/godot/` still holds older v3 export; Phase 12 ambience needs re-export via `ambience_pack.py`) | A (gallery.html + suggestions.{json,md} + lint_audio_report + zone_overrides + music_pack + decision tree in README) | **A** |
| Game Data | B+ (synthetic/OpenAI/Claude + constrained + local-LLM adapter) | A- (Pydantic + link validation + sim + DuckDB + Yarn link) | B (.tres codegen) | B+ | **B+ tooling / B- content** |

**Aggregate:** **A-** with **Props at A** (post Phase 11 deep-dive) and **Audio at A** (post Phase 12 Stable Audio Open bake — 142 stems / 10 biomes / 56 MB real audio shipped, replacing dry-run silence). UI at A-, and the rest in the B+ band. Terrain / world-gen + characters + textures + props + audio share the A- bar (or higher); props and audio specifically pushed past it via the deep-dive treatment. The "drag categories" of three days ago (game_data / audio / UI / VFX / props) all reached v2 SOTA in 2026-05-06 PM:

- **VFX v2 SOTA shipped** — 46 effects in catalog (was 3), 4 export targets (2d/3d_billboard/decal/fog_volume/mesh_trail), volumetric_fog backend with biome wiring, runtime helpers (MeshTrail3D, AudioCueBus), gallery v2, no-copy exporters. Critical bug found and fixed mid-flight: exporters were copying frames per-effect × per-target, exploding to 580 GB / 586k files; rewrite eliminated copies (artifacts referenced at catalog paths via res://). Now 81 MB total VFX disk.
- **Audio v2 + UI v2 SOTA** landed earlier in same session.
- **Props v2 + audit-expand** landed AAA-PBR material binding + Meshy/Trellis2 adapters (gated on cloud spend / GPU window).
- **Game Data v1.5 + audit-expand** added DuckDB reports + Yarn link validator + local-LLM constrained-gen adapter (gated on GPU).

**The honest drag now** is no longer "does the pipeline exist" or "is the plumbing v2" — it's:

1. **Cross-pipeline seams unproven** — every pipeline works in isolation, but the canonical "biome scene with scattered props + ambience + on-cast VFX + HUD" composition has never been run end-to-end. Tier 0 above is what closes this.
2. **GPU-window flips queued** — Stable Audio bake (✅ Phase 12) / Trellis2 (✅ Phase 11) / Hunyuan3D-2.1 (✅ Phase 11) are done. Remaining: FLUX schnell icons + LoRA train / Taichi VFX bakers / Hunyuan3D-Omni (geometry-only, bbox/voxel control) / local-LLM constrained gen / F5-TTS / Wan video / YuE music. All have CPU-side adapters built; flip on when 5090 frees up. ~3-4 days of GPU time drains the remaining backlog.
3. **Several pipelines not yet built** — animation/dialogue audio sync, cutscene/cinematics, quest/scripting data, save/load persistence, localization, performance budgets, and a cross-pipeline gallery/manifest. Tier 1 above.

Real production content authoring (TLTE seed records for game_data; concept PNGs for props; real Stable Audio bake for biome ambience) is **gated on user intent, not pipeline readiness**. Per the 2026-05-06 PM reframe, the assets being produced today are mostly throwaway proofs of pipeline correctness — the pipelines stay ready, and real content slots in when there's a real game scene asking for it.

Each pipeline has a HANDOFF_<name>_<v>_2026_05_06.md detailing built/tested/stubbed/blocked. EXPANSION_PLAN.md tracks the post-landing quality-followup checklist + Phase 9 open-weights/ComfyUI buildout.
