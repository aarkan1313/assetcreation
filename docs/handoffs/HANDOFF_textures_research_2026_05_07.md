# Texture Worker — Research Findings (2026-05-07)

Brief #02 returned. **Read this before your next planning pass — three decisions you should weigh in on.**

Full response: [02_textures.response.md](../research_briefs/2026_05_07_sota_survey/02_textures.response.md). This doc condenses what's relevant to your in-flight work.

## TL;DR — three decisions waiting on you

1. **Skip the MaterialAnything-on-flat-terrain experiment.** Use **Hunyuan3D-Paint 2.1** instead. Architecture fit is better; install effort comparable.
2. **Replace `derive_pbr_v2.py` with CHORD** as the PBR estimation stage. CHORD = Ubisoft La Forge, SIGGRAPH Asia '25, opened Dec 2025, **CUDA 12.8 native**, ComfyUI nodes shipped. Single highest-leverage swap.
3. **Add a separate `pipelines/textures/hero_mesh/` lane** alongside the existing biome-tileable lane. Different architecture, different VRAM budget — don't fold.

## Why each, in 2-3 lines

**Decision 1 (skip MA experiment):** MaterialAnything's hemisphere-camera + ControlNet-Depth pipeline collapses on flat horizontal meshes — depth signal is nearly constant from grazing angles, only top-down views inform, multi-view consensus produces "smudgy ground toward UV edges" (reported pattern in Hunyuan3D-Paint and TexFusion communities). Hunyuan3D-Paint 2.1 has illumination-invariant albedo + multi-channel PBR designed for this exact failure. Brief explicitly says don't run MA-on-flat-terrain as the first attempt.

**Decision 2 (CHORD swap):** Our `derive_pbr_v2.py` is heuristic estimation that produces flat normals and biased roughness on materials with strong specular variance. CHORD is a learned 5-channel estimator (basecolor + normal + height + roughness + metalness) trained on MatSynth, ships native ComfyUI nodes, and `requirements.txt` is already pinned to CUDA 12.8 — Blackwell-ready out of the box. FLUX-friendly so `flux_seamless.py` stays. Research-only copyleft license (fine for our research stage; flag for commercial).

**Decision 3 (separate hero_mesh lane):** Tileable-biome and mesh-driven hero terrain have genuinely different architectures (UV-tiled-shared vs UV-baked-bespoke), different tools (CHORD+FLUX vs Hunyuan3D-Paint 2.1 / TEXGen+CHORD), different VRAM budgets, different failure modes. The hero use case is rare (~10% by area) but high-impact (boss arenas, lore set-pieces). Folding produces brittle code paths.

## New tools surfaced (just so you can plan)

| Tool | Role | Install effort | License |
|---|---|---|---|
| **CHORD** | Replace `derive_pbr_v2.py` PBR estimator | Low — CUDA 12.8 native, prebuilt | Ubisoft research-only copyleft |
| **Hunyuan3D-Paint 2.1** | Replace MA for hero-mesh terrain | Medium — pinned torch 2.5.1+cu124, expect 1-2 days Blackwell port (same shape as the Puppeteer port we just did) | Tencent non-commercial under 1M MAU |
| **MaterialMVP (ICCV '25)** | Reference-image conditioning, illumination-invariant | Research-stage code | Academic |
| **TEXGen (SIGGRAPH Asia '24)** | UV-space diffusion fallback if Hunyuan3D-Paint smudges; albedo only | Linux-leaning, WSL2 path | Academic |
| **IP-Adapter / FLUX Redux** | Reference-photo conditioning on `flux_seamless.py` FLUX stage | Drop-in to existing FLUX pipeline | Open |

## What this means for things you currently own

**`pipelines/textures/`:** brief recommends two specific edits — wire CHORD into `aaa_texture.py` (replacing `derive_pbr_v2.py`), and add IP-Adapter hook to `flux_seamless.py`'s FLUX stage. **Your call on timing.** I haven't touched those files.

**`world/textures/library/`:** no implications until CHORD lands and you re-bake.

**`WORKFLOWS.md §3`:** brief recommends splitting §3 into §3a biome-tileable (CHORD path) + §3b hero-mesh (Hunyuan3D-Paint path). Same — your call.

## What I've already updated (research-only)

- [docs/pipeline_reviews/08_textures.md](../pipeline_reviews/08_textures.md) — created (was `_deferred_`); research-calibrated only, no implementation state
- [docs/pipeline_reviews/README.md](../pipeline_reviews/README.md) — #08 status flipped from `_deferred_` to "research-calibrated, worker owns implementation"
- [docs/plans/ROADMAP.md](../plans/ROADMAP.md) — brief #02 added under "Research-calibrated findings"
- [PIPELINE_DIRECTORY.md](../../PIPELINE_DIRECTORY.md) — Textures section flagged research-calibrated; `hero_mesh/` noted as planned-not-built

## Watch list (won't unblock anything but keep an eye on)

- **DualMat (ACM MM '25)** — claims fast/tileable PBR; project page up, code release status unclear
- **MatE (Dec 2025)** — single-image to tileable PBR with geometric prior; no public code yet
- **Tiled Diffusion (CVPR '25)** — explicit "tile any latent" wrapper; could pair with CHORD as upstream generator
- **No tileable + mesh-aware hybrid exists in 2026** — genuine open research gap, would be the right architecture if anyone publishes it

## One claim worth challenging

Brief says "MaterialAnything is no longer SOTA for mesh-PBR as of mid-2026." We just validated MA on 2026-05-07 (56 MB PBR output on goblin). That validation stands — MA works, just not best-in-class for the terrain failure mode. Don't rip it out; just don't deepen investment before benchmarking against Hunyuan3D-Paint 2.1.
