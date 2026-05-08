# Pipeline Reviews — Manual Calibration Pass (2026-05-07)

A per-pipeline review series, conducted 2026-05-07, where each lane's actual on-disk output was inspected and calibrated against user judgment.

## The headline finding (canonical reframe)

User, on review #5 (Props):

> "Honestly nothing was hand-authored, all just kind of made without review. We proved it works, we will want to make sure it works well on our next pass. **Honestly this is most likely the direction every pipeline and workflow will go.** That's fine lol we just started yesterday on this entire project. We are making crazy leaps honestly."

**This applies to every pipeline reviewed.** The pattern is identical across UI / VFX / Audio / Game Data / Props:

| Layer | State |
|---|---|
| **Pipeline plumbing** | Real, mature, deserves keeping — schemas, validators, exporters, QA, provenance, Godot integration |
| **Pipeline-driven content (the first procedural pass)** | Throwaway — generated without authoring intent, without curated prompts, without reference content. Quality varies from "good placeholder" (UI) to "noise/static" (Audio). |

**The pipelines were never tested with focused intent yet.** That test comes later, asset-by-asset, when there's real game-design intent driving each push. Phase 11's obelisk is the model: pick one asset, hand-tune the inputs, push through the pipeline with real care, get a real artifact out. We have one obelisk; we don't have hand-authored everything else.

## Per-pipeline reviews

| # | Lane | Doc | Headline |
|---|---|---|---|
| 01 | UI / Icons | [01_ui_icons.md](01_ui_icons.md) | 135 icons, mostly imported CC-licensed; faction system is "just a color swap"; LoRA + cloud routes never run. **Research-calibrated 2026-05-07** ([brief #07](../research_briefs/2026_05_07_sota_survey/07_ui_icons.response.md)): two version bumps unblock the cloud lane (Recraft V3→V4 Pro Vector, FLUX-schnell→FLUX.2 Klein 4B Apache 2.0); LoRA training via AI-Toolkit (Blackwell-supported) is the single biggest unlock; **no 2026 AI HUD generator exists** — keep PIL composites with AI-generated faction textures layered on top. **+ Tabler/Iconoir/OGA RPG = ~8000 free-license glyphs** to ingest. |
| 02 | VFX (3D bake) | [02_vfx_3d_bake.md](02_vfx_3d_bake.md) | "46 effects" but 18 are palette swaps with minor speed deltas; ~15 unique-by-physics; blood/dust/spark cluster shows real tuning. **Research-calibrated 2026-05-07** ([brief #04](../research_briefs/2026_05_07_sota_survey/04_vfx_3d_bake.response.md)): GPU plan reduced from 4 backends to Warp-primary / PhiFlow-optional (Taichi maintenance, LiquidFun dead). **Skip diffusion VFX.** Real bottleneck is content authoring — build `effect_from_description.py` LLM tool *before* GPU port. |
| 03 | Audio | [03_audio.md](03_audio.md) | "Sounds like noise/static for the most part" — output archived to `_archive/audio_phase12_bake_2026_05_07/`, pipeline retained. **Research-calibrated 2026-05-07** ([brief #06](../research_briefs/2026_05_07_sota_survey/06_audio.response.md)): noise/static was workflow, not model. **6 additive upgrades queued:** CLAP+PyMusicLooper QA (sub-day, would have caught the noise pre-archive); CC0 reference library + PANNs auto-tag; Stable Audio Open LoRA per biome (cloud parked); AudioGen alongside `synth_sfx`; ACE-Step v1.5 alongside `local_music_yue`; Chatterbox-Multilingual alongside `local_tts_f5`. |
| 04 | Game Data | [04_game_data.md](04_game_data.md) | Infrastructure is the strongest in the project (provenance, DuckDB balance, validators); content is 14 toy records; **balance review flagged as long-term goal**. **Research-calibrated 2026-05-07** ([brief #08](../research_briefs/2026_05_07_sota_survey/08_game_data_balance.response.md)): infrastructure validated as best-in-project; "run the plumbed cascade" is biggest unlock (DeepSeek V4-Pro bulk + Claude Opus creative ≈ ~$0.50-$2 for 250+ records, **cloud parked**). 5 additive tools queued: pymoo Pareto, fastjsonschema, DSPy+GEPA, json-schema-diff CI gate, incremental linker. Yarn/Lore/Localization findings = "build small custom utilities, don't adopt enterprise tools." |
| 05 | Props | [05_props.md](05_props.md) | 1 hero (obelisk) + 14 procedural-variant families; "recolors but distinct-ish"; placeholder Godot materials waiting on texture worker. **Research-calibrated 2026-05-07** ([brief #03](../research_briefs/2026_05_07_sota_survey/03_props_image_to_3d.response.md)): Trellis2 default validated, no generator swap. **3 queued local-only items:** meshoptimizer side-by-side with DECIMATE COLLAPSE in LOD chain; multi-image conditioning on TRELLIS.2 for variants; Rodin Gen-2 cloud hero route **parked** (no cloud right now). |
| 06 | Characters | [06_characters.md](06_characters.md) | Most-built lane; mesh ingest + preprocess + sprite-bake all clean. **Animation step research-calibrated 2026-05-07** ([brief #01 response](../research_briefs/2026_05_07_sota_survey/01_characters_animation.response.md)): AnimateAnyMesh demoted to ambient-only; canonical chain is rig-first → skeletal → retarget. **Puppeteer installed + validated 2026-05-07 PM** (native Win cu128, deer/spiderman FBXs end-to-end). **AniMo skipped** — research repo, no checkpoints, training-only. **These 33 will be production content.** |
| 07 | VFX shaders (`art_lab/`) | [07_vfx_shaders.md](07_vfx_shaders.md) | Best-designed iteration framework in the project (scoring + gates + auto-hints + LLM review packets), but **all 5 batches are smoke tests at 128px**. Framework ready, never aimed at a real target. **Research-calibrated 2026-05-07** ([brief #05](../research_briefs/2026_05_07_sota_survey/05_vfx_shaders.response.md)): framework validated as 2026 SOTA-shaped (AI Co-Artist, ShadAR — same loop, weaker guardrails than ours). **3 additive wins:** DreamSim+LPIPS scoring side-by-side with edge-MSE; import 3 curated templates; first real batch on `occult_portal`. |
| 08 | Textures | [08_textures.md](08_textures.md) | **Research-calibrated 2026-05-07** ([brief #02 response](../research_briefs/2026_05_07_sota_survey/02_textures.response.md)). Worker still owns implementation. **3 decisions queued:** swap `derive_pbr_v2.py`→CHORD; add IP-Adapter to `flux_seamless.py`; add `hero_mesh/` sibling lane. MaterialAnything no longer SOTA for hero meshes; Hunyuan3D-Paint 2.1 is. |

## Implications for next moves

1. **Don't archive the Game Data records** (kilobytes, harmless) — but stop counting "14 records" as real content.
2. **Audio output already archived** (189 MB → `_archive/audio_phase12_bake_2026_05_07/`). Re-bake with focused prompts when there's specific game-design intent.
3. **Don't archive Props** (mostly tiny procedural files, real obelisk is the proof). Same: stop counting "51 props" as gameplay content.
4. **Don't archive UI atlas/icons** — they're functional placeholders, atlas works, free-license attribution is tracked. Just understand it's prototype-tier.
5. **Don't archive VFX catalog** — same reasoning. Pipeline + 11 migrated legacy effects + a few real bakes (fracture, fog, blood/dust/spark).
6. **The pattern is identical and the project framing already accounted for it** ("pipelines-first, content-thin" — see ROADMAP). This review pass is calibration evidence, not pivot evidence.

## What this calibration changes

Nothing strategic. The "pipelines-first, content-thin" framing was already in place. What this pass adds:

- **Concrete user verdict per pipeline**, recorded honestly. Future agents/sessions can read these and skip "is the audio good?" — it isn't, that's known.
- **Specific drift / cleanup items per pipeline** (e.g. props validation report stale by 3, audio output archived, decal alpha-coverage worth investigating).
- **Forward-direction items per pipeline** (which to push first when game-design intent comes — usually a focused single-asset push, not procedural fill).

## Reading guide

If you're new to the project:
1. Start with [docs/audits/AUDIT_2026_05_07_post_nuke.md](../audits/AUDIT_2026_05_07_post_nuke.md) for the snapshot of what exists.
2. Read this index + the 5 (eventually 8) per-pipeline reviews for the **honest quality calibration**.
3. Then look at [WORKFLOWS.md](../../WORKFLOWS.md) for the per-asset run-order + tool branches.

The reviews are intentionally pessimistic — they flag what's broken, what's templated, what's noise. The pipelines themselves are real, the infrastructure is good, the project moved fast. **Both things are true.**
