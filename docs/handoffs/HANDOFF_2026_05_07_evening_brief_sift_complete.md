# Handoff — All 8 SOTA Briefs Integrated (2026-05-07 evening → next session)

You are picking up a multi-day asset-pipeline project. **All 8 SOTA research briefs have been returned, sifted into pipeline reviews, integrated into ROADMAP, and the additive tooling installs that don't require cloud or manual curation are done.**

This handoff supersedes [HANDOFF_2026_05_07_pm_characters_animation_install.md](HANDOFF_2026_05_07_pm_characters_animation_install.md) (which predates the brief sift and has stale claims about AniMo + Puppeteer).

## What was done this session (2026-05-07 PM → evening)

### Briefs returned and integrated (all 8)
| Brief | Pipeline | Net change |
|---|---|---|
| #01 | Characters / Animation | Puppeteer ✅ installed (native Win cu128, NOT WSL2). AniMo ❌ skipped (training-only repo, no checkpoints). Canonical animation chain validated against 2026 SOTA. |
| #02 | Textures | CHORD (Ubisoft Dec 2025) is highest-leverage swap. **Texture worker handoff written** at [HANDOFF_textures_research_2026_05_07.md](HANDOFF_textures_research_2026_05_07.md). Hero_mesh sibling lane planned. MaterialAnything reclassified. |
| #03 | Props | Trellis2 default validated. **meshoptimizer wired side-by-side with DECIMATE COLLAPSE** in `lod_chain.py --method`. Rodin parked (cloud). Foliage = separate lane. |
| #04 | VFX 3D bake | GPU plan reduced from 4 backends to **Warp-primary + PhiFlow-watch**. LLM `effect_from_description.py` comes BEFORE GPU port. `pipelines/vfx/GPU_BACKENDS_PLAN.md` carries superseded banner. |
| #05 | VFX shaders | Framework already 2026 SOTA-shaped. **dreamsim + lpips wired side-by-side with edge-MSE** via `--scorer` flag. Dedicated `art_lab/.venv` stood up. |
| #06 | Audio | Noise/static was workflow not model. **CLAP + PyMusicLooper wired into `audio_qa.py`** via `--clap-prompt` and `--loop-check`. Dedicated `pipelines/audio/.venv` stood up. 5 model installs queued. |
| #07 | UI / Icons | LoRA training (AI-Toolkit by Ostris) is biggest unlock. **FLUX.2 Klein 4B + Recraft V4 + Iconoir plumbed**. No 2026 AI HUD generator exists. |
| #08 | Game Data | Infrastructure validated as best-in-project. **`pymoo` + `fastjsonschema` + `duckdb` installed in dedicated `pipelines/game_data/.venv`**. "Run the plumbed cascade" is biggest unlock (cloud parked). |

### Code wirings done (all additive, A/B-comparable, default behavior preserved)

8 files modified across 4 lanes. Every change is **opt-in via flag**; existing callers see zero behavior change. Verified by smoke test.

| File | Flag added | Status |
|---|---|---|
| `pipelines/props/lod_chain.py` | `--method {decimate,meshopt}` + `--suffix _meshopt` | ✅ verified on obelisk_egyptian_a04 |
| `pipelines/props/blender_scripts/proc_lod.py` | `--suffix` plumbing | ✅ |
| `art_lab/tools/shader_reference_score.py` | `--scorer {edge_mse,dreamsim,lpips,all}` | ✅ verified on smoke batch |
| `pipelines/audio/audio_qa.py` | `--clap-prompt <text>` + `--loop-check` | ✅ verified +0.407 / -0.117 on archived bed_air.wav |
| `pipelines/ui/freelib_ingest.py` | Iconoir as 4th `mit-iso-libs` library | ✅ syntax check |
| `pipelines/ui/local_diffusion_icons.py` | `FLUX2_KLEIN_4B_ID` (Apache 2.0) + FLUX2_DEV_ID added | ✅ syntax check |
| `pipelines/ui/recraft_icons.py` | `--model {recraftv3,recraftv4,recraftv4-pro-vector}` | ✅ syntax check |
| `pipelines/vfx/GPU_BACKENDS_PLAN.md` | Superseded banner (Warp-primary, PhiFlow-watch) | ✅ |

### Venvs installed (one isolated per pipeline lane — see memory note)

| Venv | Tools | Brief |
|---|---|---|
| `animators/Puppeteer/.venv` | torch 2.7+cu128 + xformers 0.0.30 + flash-attn 2.7.4 + pytorch3d 0.7.9 + torch-scatter 2.1.2 + bpy 4.4.0 + triton-windows + vtk + pyvista | #01 — full recipe in [animators/INSTALL_MATRIX.md](../../animators/INSTALL_MATRIX.md) |
| `art_lab/.venv` | torch 2.7+cu128 + dreamsim + lpips | #05 |
| `pipelines/audio/.venv` | torch 2.7+cu128 + laion-clap + pymusiclooper + librosa | #06 |
| `pipelines/game_data/.venv` | pymoo + fastjsonschema + duckdb | #08 |
| `tools/meshoptimizer/gltfpack.exe` v1.1 | Standalone Windows binary, no venv | #03 |

**Pattern:** one venv per pipeline lane, isolated from each other. Discovered the hard way when modern peft (a dreamsim transitive) needed `accelerate>=1.0` while Puppeteer is pinned to `accelerate==0.28.0`. Standing up `art_lab/.venv` separately preserved the validated Puppeteer rig pipeline. Same pattern repeated for audio + game_data. **Don't pollute existing venvs with new lane deps.**

### Docs updated this session

- 8 pipeline reviews ([docs/pipeline_reviews/01-08](../pipeline_reviews/)) — each carries a "Research-calibrated update (2026-05-07)" section
- [docs/pipeline_reviews/README.md](../pipeline_reviews/README.md) — all 8 rows reflect calibration outcomes
- [docs/plans/ROADMAP.md](../plans/ROADMAP.md) — 8 brief sections under "Research-calibrated findings"
- [PIPELINE_DIRECTORY.md](../../PIPELINE_DIRECTORY.md) — relevant rows linked to research
- [docs/handoffs/HANDOFF_textures_research_2026_05_07.md](HANDOFF_textures_research_2026_05_07.md) — texture worker handoff (3 decisions, condensed)
- [docs/plans/NEXT_STEPS_2026_05_07.md](../plans/NEXT_STEPS_2026_05_07.md) — **cross-cutting state doc; read this for the at-a-glance picture**
- Brief #01 response patched with postscript: AniMo skipped, Puppeteer went native-Win-cu128
- [animators/INSTALL_MATRIX.md](../../animators/INSTALL_MATRIX.md) — Puppeteer recipe + 9 documented gotchas

### Memory notes saved (`C:\Users\josep\.claude\projects\d--assets\memory\`)

- `torch26_weights_only_trap.md` — `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` env var fix for Bytedance/older ML repo checkpoints
- `research_repo_no_inference.md` — 30-second sanity check before installing a paper repo (does it ship inference.py + checkpoints + Releases?)
- `isolated_venv_per_lane.md` — one venv per pipeline lane; don't pollute existing venvs
- `faction_inpaint_workflow_gap.md` — Path 2 = real pipeline gap (per-instance mesh albedo inpainting); LoRA on icons is hand-waving

## What's NEXT — three decisions made, one open

### Decided this session

1. **Don't fan out to all 33 characters.** Original handoff goal of "validate canonical chain on 3 characters" was reframed by user as **content authoring, not pipeline work.** Puppeteer's `deer.obj` + `spiderman.obj` smoke test already validates skeleton + skin + FBX export end-to-end. **Running the chain on goblin/hellhound/sandworm = QA on those specific meshes, not pipeline improvement.** Skipped.
2. **Faction LoRA on icons is hand-waving.** Brief #07's "LoRA training is biggest unlock" frames it as a motif/material/lighting differentiator. **User correctly identified the actual high-value use case is per-instance insignia inpainting on enemies (Path 2),** which the brief didn't surface as a workflow.
3. **Cloud is parked.** Rodin Gen-2, Stable Audio 2.5, Recraft V4 Pro Vector run, DeepSeek V4-Pro, Claude Opus passes — all queued, none done.

### Open: Path 2 inpainting workflow

The per-instance mesh albedo inpaint workflow (faction insignia / damage states / variants / tier markings) is **a real pipeline gap not covered by any of the 8 briefs**. Two options:
- **(a) Dispatch brief #09** for "per-instance mesh albedo inpainting on rigged characters" — research-agent run, ~few hours, low risk
- **(b) Design from existing knowledge** — pattern-match Hunyuan3D-Paint 2.1 + ControlNet-Mask + IP-Adapter; risk reinventing what brief would tell us

User direction at session end: **Path 2 confirmed as the priority direction**, but no decision yet on (a) vs (b). The free-wins backlog runs in parallel either way.

### Free-wins backlog (sub-day to 2-day each, owned by us, no cloud, no curation)

In the order I'd recommend tackling:

| # | Action | Brief | Effort |
|---|---|---|---|
| 1 | `pareto_dominated_records.py` (pymoo NSGA-II sibling to `duckdb_reports.py`) | #08 | 1 day |
| 2 | `fastjsonschema` additive in `validate_records.py` | #08 | sub-day |
| 3 | `effect_from_description.py` LLM authoring tool for VFX | #04 | sub-day |
| 4 | Visual A/B inspection: decimate vs meshopt on obelisk LODs (already baked) | #03 | 30 min |
| 5 | CLAP-batch tool: score every existing biome WAV against its prompt | #06 | sub-day |
| 6 | Schneider-Vos cloud noise upgrade in `baker_volumetric_fog.py` | #04 | sub-day |
| 7 | Hash-based incremental linker for `pipelines/game_data/` | #08 | sub-day |
| 8 | `getsentry/json-schema-diff` CI gate for migrations | #08 | sub-day |
| 9 | 100-line Yarn static analyzer | #08 | 1 day |
| 10 | Import 3 curated shader templates (hit_flash_2d, projectile_trail_2d, ground_glow_2d) with license sidecars | #05 | sub-day |
| 11 | `art_lab/library/<category>/<name>/manifest.json` convention + promote-from-review-queue helper | #05 | sub-day |
| 12 | `audio_clip` field on VFX `manifest.json` schema | #04 | sub-day |

## Things to actively NOT do (decided by 2026 SOTA, not us)

These are "the brief said no" — putting here so future agents don't re-investigate:

- **Don't fine-tune game-content LoRAs** (#08) — niche doesn't exist usably.
- **Don't set up RL on combat balance before combat is built** (#08).
- **Don't migrate Yarn → Ink / Dialogic 2** (#08) — lateral, build static analyzer instead.
- **Don't buy World Anvil / LegendKeeper / Kanka / Campfire** (#08) — wrong shape.
- **Don't adopt Inworld / Convai for dialogue** (#08) — runtime NPC, not authoring.
- **Don't adopt Lokalise / Phrase / Smartling pre-launch** (#08) — Crowdin Free works.
- **Don't pursue Hunyuan3D-3.0 full open weights** (#03) — watch list, not adopt.
- **Don't try image-to-3D for foliage** (#03) — separate lane (SpeedTree / The Grove).
- **Don't pursue AI HUD generators** (#07) — wrong category for game UI.
- **Don't pursue diffusion VFX (Sora 2 / AnimateDiff)** (#04) — wrong tool category.
- **Don't adopt USD for VFX manifest** (#04) — overkill for flipbooks.
- **Don't keep AniMo on the install list** (#01) — training-only research repo.
- **Don't install MocapAnything from github.com/animotionlab26** — unofficial reimpl of a Huawei paper, anonymous org, no checkpoints/license, author's own disclaimer says "not a reproduction." See [memory note](file://C:/Users/josep/.claude/projects/d--assets/memory/mocapanything_unofficial_skip.md). Revisit only if Huawei ships official weights.
- **Don't deepen MaterialAnything investment for hero terrain** (#02).
- **Don't replace vtracer/resvg/PIL atlas packer** (#07) — laterals.
- **Don't adopt Neo4j / KuzuDB at <20K records** (#08) — architectural cosplay.

## Hardware target (unchanged)

- **GPU:** RTX 5090 Laptop, 24 GB VRAM, Blackwell sm_120 — needs CUDA 12.8+ / torch ≥ 2.7
- **OS:** Windows 11; default to native Windows venvs at Python 3.11
- **WSL2:** acceptable when forced; not needed for any current install
- **Disk:** D:\ free space — check `df -h /d` before bulk pulls (D: filled to 100% on 2026-05-06; memory note exists)

## Background workers (don't disturb)

- **Worldgen worker** in `world3/` — rebuilding scene-composition pipeline.
- **Texture worker** in `pipelines/textures/` + `world/textures/library/` — improving tileable textures. Brief #02 handoff written for them at [HANDOFF_textures_research_2026_05_07.md](HANDOFF_textures_research_2026_05_07.md); 3 decisions waiting on them.

If broken markdown links surface in `world3/docs/*` or `pipelines/textures/*.md`, **leave them** — worker-managed.

## First action when you start

1. Read **this handoff** + [docs/plans/NEXT_STEPS_2026_05_07.md](../plans/NEXT_STEPS_2026_05_07.md)
2. Confirm direction with user: Path 2 inpainting brief #09 dispatch, or design-from-existing? Free-wins start with #1 (pymoo Pareto) regardless.
3. Don't restart anything. Don't redo what's already validated. Don't fan out the 33 characters — that's content authoring.

## What success looks like at the end of the next session

- Free-wins items 1-4 cleared (pymoo Pareto, fastjsonschema, effect_from_description.py, decimate-vs-meshopt visual A/B)
- Decision on Path 2 inpainting (brief #09 or design)
- If Path 2 chose "design": initial workflow design doc with the architectural shape (UV-space vs camera-projection inpaint), tool choices, and skeleton implementation plan
- Docs + ROADMAP + memory notes updated as we go. **The risk we're managing for is "do all this work then lose it" — every install/fix should land in docs the same session.**
