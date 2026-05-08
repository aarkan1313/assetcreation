# Textures — Research-Calibrated Review (2026-05-07)

**Different review pattern than #01-#07.** The texture worker is actively in `pipelines/textures/` and `world/textures/library/`. This review is **research-only** — captures findings from brief #02 without inspecting current implementation state. The worker owns the lane; this doc hands them the calibrated read on what 2026 SOTA looks like for our use case.

Full research response: [research_briefs/2026_05_07_sota_survey/02_textures.response.md](../research_briefs/2026_05_07_sota_survey/02_textures.response.md). Worker handoff with action implications: [docs/handoffs/HANDOFF_textures_research_2026_05_07.md](../handoffs/HANDOFF_textures_research_2026_05_07.md).

## What we asked

Brief #02 covered three workflows:
- **Workflow A** — biome-tileable PBR generation (current spine: `flux_seamless.py` → `derive_pbr_v2.py` → optional `aaa_texture.py`/StableMaterials)
- **Workflow B (hypothetical)** — mesh-driven hero terrain via MaterialAnything top-down on subdivided plane
- **Workflow C** — closing the B/C-grade quality gap so all biome sets reach A-grade

Plus 10 sub-questions on tileable-PBR SOTA, reference conditioning, ground-specialized models, terrain-mesh viewpoints, AAA pipeline patterns.

## Headline findings

### 1. CHORD is the consequential 2026 drop we missed

**[CHORD](https://github.com/ubisoft/ubisoft-laforge-chord)** (Ubisoft La Forge, SIGGRAPH Asia '25, weights opened **December 2025**). Production-pedigree, open-weights, ComfyUI-native, FLUX/SDXL-driven, native-tileable, **5-channel PBR** (basecolor + normal + height + roughness + metalness). `requirements.txt` pinned to **CUDA 12.8** — Blackwell-ready out of the box.

This is the single highest-leverage swap available right now. Replaces `derive_pbr_v2.py` (heuristic) with a learned model trained on MatSynth. The FLUX side of `flux_seamless.py` stays — CHORD's stage-1 generator is FLUX/SDXL-friendly.

**License:** Ubisoft Machine Learning License — research-only copyleft. Fine for our research stage; flag for any commercial release.

### 2. Hunyuan3D-Paint 2.1 beats MaterialAnything for hero meshes

**[Hunyuan3D-Paint 2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)** (Tencent, Jun 2025). Multi-view PBR diffusion with **3D-aware RoPE for cross-view consistency**, **illumination-invariant training** for light-free albedo, **spatial-aligned multi-attention** for albedo/MR register. 21 GB VRAM — fits 24 GB Blackwell with margin.

The architectural concerns about MaterialAnything-on-flat-terrain in the brief (hemisphere camera + ControlNet-Depth collapses on horizontal meshes, only top-down views inform, edge-smudging from low-confidence multi-view consensus) are real and unvalidated by any public experiment. Hunyuan3D-Paint 2.1's design specifically targets these failure modes.

**MaterialAnything reclassification:** brief says it's no longer SOTA for mesh-PBR as of mid-2026 (Hunyuan3D-Paint 2.1/2.5 + MaterialMVP have surpassed it). Our 2026-05-07 MA validation still stands — it works on goblin-style meshes — but don't deepen investment before benchmarking against Hunyuan3D-Paint.

**License:** Tencent Hunyuan Community License — non-commercial under 1M MAU. Fine for research.

### 3. AAA in 2026 is not going end-to-end ML

The dominant production pattern (Frostbite, Horizon Forbidden West, InstaMAT 2025) is still **tileable PBR atlas + splatmap blend + procedural placement + virtual texturing**. ML is being grafted onto the *front* of these pipelines (replacing manual Substance graphs for individual tile authoring), not replacing the runtime stack. We're already aligned with this — don't be tempted to replace the runtime.

The Horizon Forbidden West "deferred texturing for foliage" pattern explains why AAA accepts ~50-100 tileable PBR sets per game — runtime decoupling lets each tile cover hundreds of m² with shader-driven variation. **We don't need 1000 tiles; ~30 great ones with good macro+detail blending and biome variation suffice.**

## The three concrete decisions

### Decision A — Workflow B experiment

**Skip the MaterialAnything-on-flat-terrain experiment. Use Hunyuan3D-Paint 2.1 instead.** If it also smudges, fall back to TEXGen (UV-space diffusion, architecturally correct for terrain) + CHORD as PBR estimator.

### Decision B — Workflow A quality gap (B/C → A)

Two specific swaps:
1. **(Primary)** Replace `derive_pbr_v2.py` with **CHORD** in `aaa_texture.py`.
2. **(Secondary)** Add **IP-Adapter / FLUX Redux** reference-conditioning to `flux_seamless.py`'s FLUX stage.

Optional 3rd lever (follow-up): **FLUX LoRA** fine-tuned on Poliigon/FreePBR ground textures for biome-specific generation. ~24h LoRA training per biome family.

### Decision C — Hero terrain lane

**Add a separate `pipelines/textures/hero_mesh/` lane.** Different architecture, different VRAM budget, different failure modes than biome-tileable. Folding produces brittle code paths. Hero use case is rare (~10% by area) but high-impact (boss arenas, lore set-pieces).

## Watch list (no usable code yet, but worth tracking)

| Tool | Status | Why we'd care |
|---|---|---|
| **DualMat (ACM MM '25)** | Project page up, code TBD | Dual-path diffusion, claims 28% albedo / 39% MR error reduction vs prior SOTA, "fast and tileable" |
| **MatE (Dec 2025)** | No public code yet | Single-image to tileable PBR with geometric prior |
| **MaterialMVP (ICCV '25)** | Open code, mesh-conditioned | Strongest reference-image conditioning |
| **Tiled Diffusion (CVPR '25)** | Open | Explicit "tile any latent" wrapper; could pair with CHORD as upstream generator |
| **TEXGen (SIGGRAPH Asia '24)** | Open, albedo-only | UV-space diffusion — architecturally right for terrain; pair with CHORD for PBR |
| **Tileable + mesh-aware hybrid** | Doesn't exist | Open research gap; UV-space diffusion + circular-padding loss is the obvious next paper |

## Q&A summary (ten sub-questions, condensed)

| Q | Answer |
|---|---|
| Q1 — 2026 SOTA tileable PBR | **CHORD** (top), DualMat (watch), MatE (watch). StableMaterials surpassed. |
| Q2 — Native-tileable + materially-correct one-pass | CHORD's two-stage cascade is closest. **No single 2026 model unifies all 5 channels in one pass.** |
| Q3 — Reference-style conditioning | MaterialMVP (mesh-conditioned), CHORD + IP-Adapter on FLUX (low-friction). **Real gap; addressable.** |
| Q4 — Specialized ground generators | **No open ML beats StableMaterials for ground specifically.** Productive direction = FLUX LoRA on Poliigon/FreePBR + CHORD. |
| Q5 — Macro+detail PBR pairs | **No clear 2026 answer.** Stay with manual two-pass shader; don't block. |
| Q6 — MaterialAnything for terrain meshes | **Probably no.** No public experiment of this exact config. Hemisphere camera + ControlNet-Depth wrong fit for flat horizontal mesh. |
| Q7 — Viewpoint config for ground meshes | No clear public recipe. **Hemisphere with elevation clamp 60-90°** is most defensible default. |
| Q8 — MaterialAnything alternatives | **Hunyuan3D-Paint 2.1** (top), MaterialMVP, TEXGen (UV-space). |
| Q9 — Tileable + mesh-aware hybrid | **Doesn't exist publicly.** Closest = CHORD-tile + Hunyuan3D-Paint-mesh cascade. Re-evaluate quarterly. |
| Q10 — 2026 AAA terrain pipeline | **Tile-atlas + splatmap + virtual texture.** ML authors tiles, runtime stays tile-based. We're aligned. |

## What this changes

**Strategic:** nothing. The "pipelines-first, content-thin" framing holds. Workflow A still produces good biome sets (10 A-grade currently); Workflow B was always speculative.

**Tactical:**
- **Don't run Workflow B with MaterialAnything.** Pivot to Hunyuan3D-Paint 2.1.
- **Two named swaps queued for the worker:** CHORD replaces `derive_pbr_v2.py`; IP-Adapter on `flux_seamless.py`.
- **A new sibling lane is justified** — `pipelines/textures/hero_mesh/`, planned not built.

**Honest:** the worker may already be partway down some of these paths (they've been in `pipelines/textures/` for ~24h). This review is offered as calibration data they can sift, not as direction.
