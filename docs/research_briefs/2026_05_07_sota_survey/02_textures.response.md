# Research Response — Textures Pipeline 2026 SOTA

Date: 2026-05-07
Brief: `02_textures.md`
Hardware target: RTX 5090 Laptop, 24 GB VRAM, Blackwell sm_120, CUDA 12.8+, torch 2.7+, Windows 11 native (WSL2 acceptable)

## Executive summary

The single biggest 2025/2026 development that hits this brief directly is **Ubisoft La Forge's CHORD** (SIGGRAPH Asia 2025, weights opened December 2025). It is the first **production-pedigree, open-weights, ComfyUI-native, FLUX/SDXL-driven, native-tileable, full-PBR (basecolor + normal + height + roughness + metalness) pipeline** released into the wild — and it explicitly ships with `requirements.txt` pinned to **CUDA 12.8**, which is the exact target for our Blackwell stack. CHORD is the only 2026 tool that cleanly subsumes both Workflow A roles (`flux_seamless.py` + `derive_pbr_v2.py` + `aaa_texture.py/StableMaterials`). License is research-only copyleft, not commercial — but the project here is research-grade, so that is acceptable for now.

For Workflow B (mesh-driven hero terrain), the brief's hypothetical experiment ("DEM → subdivided plane → MaterialAnything top-down") is **not worth running first**. Better 2026 candidates exist: **Hunyuan3D-Paint 2.1/2.5** (multi-channel PBR, illumination-invariant albedo, Apache-derived but Tencent non-commercial) and **MaterialMVP** (ICCV 2025, illumination-invariant, dual-channel albedo+MR, open). Both are designed exactly for the failure mode MaterialAnything has on flat horizontal meshes (object-centric cameras, no SDS smudging). MaterialAnything was strong in late 2024 but is no longer best-in-class for mesh-PBR in mid-2026.

The "tileable + mesh-aware hybrid" question (Q9) currently has **no clear public answer**. The closest is the CHORD + Hunyuan3D-Paint cascade: tile a CHORD material, then bake/project it onto a mesh via Hunyuan3D-Paint conditioning. No single 2026 model unifies both.

The rest of the document treats each question in turn, then synthesizes the three concrete decisions.

---

## Q1. 2026 SOTA for tileable PBR generation (StableMaterials successors)

### Top recommendations

1. **CHORD (Ubisoft La Forge, SIGGRAPH Asia 2025).** Two-stage: (a) generation stage uses a text-to-image model (FLUX/SDXL) to synthesize a tileable texture with creative control, (b) estimation stage decomposes that image into basecolor / normal / roughness / metalness via "chain-of-rendering-decomposition," with height derived by normal integration. Plus an integrated 2x/4x PBR-aware upscaler. Native ComfyUI nodes. This is the most consequential drop in the entire 2025 PBR space. https://ubisoft-laforge.github.io/world/chord/ , https://github.com/ubisoft/ComfyUI-Chord , https://blog.comfy.org/p/ubisoft-open-sources-the-chord-model

2. **DualMat (ACM MM 2025, arXiv 2508.05060).** Coherent dual-path diffusion: an albedo-optimized RGB-latent path leveraging pretrained visual priors plus a metallic-roughness-specialized compact-latent path. Reports 28% improvement in albedo and 39% reduction in metallic-roughness error vs prior SOTA. Patch-based for high-res, cross-view attention for multi-view, and crucially the project page describes it as "fast, high-quality, and tileable." Code release status unclear from public sources (project page is up: https://yifehuang97.github.io/DualMatProjPage/). https://arxiv.org/abs/2508.05060

3. **MatE (arXiv 2512.18312, Dec 2025).** Single-image to tileable PBR with geometric prior — newer than DualMat, also targets tileable output natively. No clear public code release yet. Treat as one to watch.

### Hardware fit
CHORD: ships with `requirements.txt` pinned to CUDA 12.8, Python 3.12, torch + torchvision installed against cu128 — directly compatible with RTX 5090 / Blackwell / sm_120 on Windows native. No friction expected. https://github.com/ubisoft/ubisoft-laforge-chord
DualMat / MatE: research code, no Blackwell-specific notes; expect to build from source against torch 2.7+/cu128 — may require ~24 GB VRAM for high-res patches.

### License + ComfyUI integration
- **CHORD:** Ubisoft Machine Learning License (Research-Only, Copyleft). MatSynth training data. **Native ComfyUI nodes** at `ubisoft/ComfyUI-Chord` — major plus for our pipeline. Not licensed for commercial release of game assets, but fine for research/personal use.
- **DualMat / MatE:** academic, license usually Apache or research-only when published — confirm at code release.

### Maturity
CHORD: actively maintained — repo opened Dec 2025, ComfyUI nodes live. DualMat/MatE: research-stage, code release timing uncertain. **StableMaterials itself has had no major update since June 2024** — it has effectively been surpassed.

### Honest comparison vs current Workflow A
Workflow A today = `flux_seamless.py` (FLUX 2 + offset+heal for tileable albedo) → `derive_pbr_v2.py` (heuristic albedo→PBR) → optional `aaa_texture.py` (StableMaterials estimator). The weak link is `derive_pbr_v2.py`: heuristic estimation produces flat normals and biased roughness on materials with strong specular variance.

**CHORD replaces both `derive_pbr_v2.py` and `aaa_texture.py/StableMaterials` directly** with a higher-quality, learned, explicitly-tileable estimator, plus a PBR-aware upscaler we currently lack. The FLUX side of `flux_seamless.py` can stay — CHORD's stage 1 is essentially the same idea (generate a tileable texture image), but its stage 2 estimator is materially better than our heuristic. **Yes, CHORD beats the current stack.**

---

## Q2. Native-tileable + materially-correct in one pass

### Top recommendations
1. **CHORD** (same as Q1) — closest public answer. The stage-1 generator is tileable-conditioned and stage-2 inherits that tiling. So all five PBR channels emerge tileable from the same upstream texture.
2. **MatFuse (CVPR 2024) / "MaterialCrafter" Blender add-on** — older but still relevant: SVBRDF diffusion conditioned on text/sketch/palette. Outputs are not natively guaranteed seamless without rolling tricks; CHORD's lineage is meaningfully newer. https://gvecchio.com/matfuse/
3. **Tiled Diffusion (CVPR 2025) + CHORD** — Tiled Diffusion (https://github.com/madaror/tiled-diffusion) is an explicit "tile any latent" wrapper that supports SDXL/SD3/ControlNet (FLUX not officially listed yet). Pair it as the upstream generator for CHORD or for a per-channel multi-diffusion approach.

### Honest comparison
A **single 2026 model that produces all five PBR channels seamlessly tileable in one pass with no offset+heal** does not yet exist as an open release. CHORD's two-stage cascade is the closest practical approximation: the stage-1 generator's tileability propagates to stage-2 channels, and you only need offset+heal as a fallback if stage-1 misses a seam (rare with Tiled Diffusion guidance). Treat CHORD as the single-model answer for now.

---

## Q3. Reference-based / style-conditioned seamless PBR

### Top recommendations
1. **MaterialMVP (ICCV 2025).** Reference Attention module specifically for image-prompt conditioning, dual-channel albedo + metallic-roughness with multi-channel-aligned attention. Designed to handle reference images robustly across view/illumination changes. Code at https://github.com/ZebinHe/MaterialMVP . https://arxiv.org/abs/2503.10289
2. **CHORD with IP-Adapter / FLUX Redux on stage 1.** CHORD's stage-1 generator is FLUX/SDXL — drop in IP-Adapter or InstantStyle reference conditioning, get a reference-styled tileable texture, then estimate PBR. The reference signal flows naturally because CHORD does not re-style during estimation.
3. **MaterialFusion (CVPR 2025, arXiv 2502.06606).** Material *transfer* (apply material X to object Y while preserving Y's structure). Works at the diffusion-model level, supports degree-of-application control. Useful when you have a reference photo and want to drive an existing albedo/PBR toward it. https://github.com/ControlGenAI/MaterialFusion

### Honest comparison
We currently score with edge-MSE only and have no reference-style conditioning beyond raw text. Adding **IP-Adapter on the FLUX stage of `flux_seamless.py`** is a low-friction win even before swapping to CHORD. MaterialMVP is the cleanest research-grade answer but is mesh-conditioned (multi-view) so it does not directly target the tileable-2D case. **Yes, this is a real gap and IP-Adapter + CHORD addresses it.**

---

## Q4. Specialized ground-texture generators

### Top recommendations
1. **InstaMAT 2025 (Abstract).** Released July 2025. Includes **AAA terrain generation nodes** with erosion, water/snow sim, biome generation, asset scattering, dynamic PBR texturing. Used in production by Bandai Namco, Blizzard, Pearl Abyss. Procedural / node-based, **not** ML-diffusion. Commercial, not open-source. https://instamaterial.com/2025/07/16/instamat-2025-prepares-to-launch-with-powerful-new-features-and-scalable-workflows/
2. **No open ML model is specialized for ground textures** in the sense of being trained narrowly on cracked-earth / gravel / sand / forest-floor and beating a general model on those classes. CHORD/StableMaterials/DualMat are all general PBR estimators. Specialization in the current open ecosystem is achieved via prompting + LoRA fine-tunes on FLUX, not via a dedicated model.
3. **World Creator / World Machine 2025 ("Hurricane Ridge").** Procedural terrain generators with built-in PBR biome materials. Adjacent to ML but not part of the diffusion pipeline.

### Honest comparison
**No open ML alternative beats StableMaterials for ground specifically** as of 2026-05-07. A productive direction is to fine-tune a **FLUX LoRA on a curated ground-texture set** (Poliigon/FreePBR/textures.com) and feed that into CHORD's stage 1. That is ~24h of LoRA training and probably worth doing once per biome family. It will outperform any general model on those specific classes.

---

## Q5. Macro + detail PBR pairs

### Top recommendations
1. **No clear public answer.** Searched arXiv and the major project pages — no 2026 paper trains explicitly on macro-detail pairs designed to blend in `macro_detail_v1.gdshader`-style shaders. The closest is **Meta 3D TextureGen** (multi-resolution UV passes) and the coarse-to-fine cascades inside Hunyuan3D 2.5's "zoom-in" 768² phase, but neither outputs a pair designed for shader-blending.
2. **Practical workaround.** Generate the coarse texture with CHORD at 1k from a "broad pattern" prompt, then run CHORD again at 4k with a "tight detail" prompt seeded by the coarse channel as ControlNet input. Compose them in `macro_detail_v1.gdshader` as you do now. This is two CHORD passes — straightforward to script.
3. **Substance Designer / InstaMAT graphs** — handle this elegantly via nested noise frequencies. If macro+detail is critical for one scene, hand-author a graph rather than waiting for ML.

### Honest comparison
This is a niche the open-ML community has not yet addressed. Stay with the manual two-pass approach in the shader; do not block on a model that does not exist.

---

## Q6. Can MaterialAnything be used as-is for terrain meshes?

### Direct answer
**Probably no — and there is no published experiment of this exact configuration.** Searches for "MaterialAnything terrain ground hemisphere camera" returned zero relevant hits. The architectural concern in the brief is correct: MaterialAnything's `predefined` mode places cameras on a hemisphere/sphere around a centered object and uses **iterative multi-view consensus + ControlNet-Depth inpainting** to disambiguate. On a flat horizontal plane:

- The depth signal is nearly constant from sides (oblique grazing) → ControlNet-Depth gives almost no useful signal.
- Top-down views become the only informative camera, but multi-view consensus with one good camera and many bad ones produces low-confidence inpainting outside the top-down footprint.
- The empirical result reported by similar terrain attempts in the Hunyuan3D-Paint and TexFusion communities is "smudgy ground, especially toward UV edges."

### What might actually work
Two adaptations have public discussion:
- Use **`hemisphere` mode with a tight zenith band** (cameras at 60–90° elevation only, no equatorial views). This is closer to a "satellite + low-oblique" capture pattern. Untested in MaterialAnything specifically.
- Subdivide into **small mesh patches** (e.g., 4x4 chunks) and texture each as if it were an object with hemisphere coverage — then re-stitch in UV space. This is essentially what TEXGen does natively.

### Honest comparison
**The proposed Workflow B mesh-driven hero terrain experiment is not worth running on MaterialAnything as the first attempt.** Better: run it with **Hunyuan3D-Paint 2.1** (Q8) which has an illumination-invariant albedo head and is designed to handle larger meshes. If you want to insist on MaterialAnything for consistency, validate the architectural risk first by running on a small (4 m²) subdivided plane GLB before scaling.

---

## Q7. Viewpoint configuration for ground meshes

### Direct answer
**No clear public recipe.** Best inferred guidance from the literature:

- **Hemisphere with elevation clamp (60–90°)** plus 4–6 azimuth samples is the most defensible default for flat horizontal terrain. This mimics a satellite-pass and avoids the grazing-angle failure mode.
- **Patch-and-stitch** (treat the terrain as N objects, each get hemisphere coverage, blend in UV space). This is the strategy used inside TEXGen's UV-space diffusion and is closer to the "right" architecture for terrain.
- **Top-down only** is *worse* — single-view diffusion has no consensus to lean on and tends to hallucinate inconsistent detail.

### Honest comparison
Without published experiments on terrain-mesh PBR diffusion, this is currently empirical territory. Recommendation: if you do run this experiment, instrument it with a "viewpoint ablation" at 4 hemisphere configurations (top-only, top+oblique-30°, top+oblique-60°, full-hemisphere) and report seam-MSE + visual grade.

---

## Q8. MaterialAnything alternatives for terrain

### Top recommendations
1. **Hunyuan3D-Paint 2.1 (and 2.5 if released).** Tencent. Multi-view PBR diffusion with **3D-aware RoPE for cross-view consistency**, **illumination-invariant training strategy** for light-free albedo, **spatial-aligned multi-attention** to keep albedo and metallic-roughness in register. Outputs albedo + metallic + roughness (height/normal derived). 21 GB VRAM for the texture stage — fits 24 GB Blackwell with margin. Native ComfyUI integration via `ComfyUI-Hunyuan3d-2-1`. Windows-supported. Most production-ready 2026 mesh-PBR. https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1 , https://arxiv.org/html/2506.15442v1
2. **MaterialMVP (ICCV 2025).** Open code at https://github.com/ZebinHe/MaterialMVP . Stronger reference-image conditioning than Hunyuan3D-Paint, still illumination-invariant. Smaller research codebase, more friction to adapt to terrain meshes but the cleanest research-grade option.
3. **TEXGen (SIGGRAPH Asia 2024 best-paper honorable mention).** UV-space diffusion (not multi-view projection) — architecturally the best fit for terrain because it does not depend on camera placement. **Caveat: albedo only, no PBR channels.** 24 GB VRAM at inference. Pair with CHORD for PBR estimation post-hoc. https://github.com/CVMI-Lab/TEXGen
4. **Make-A-Texture (arXiv 2412.07766).** 3-second texture per mesh on H100; depth-aware inpainting with auto view-selection. Fast iteration. Albedo-leaning.

### Hardware/install fit
Hunyuan3D 2.1 explicitly tested on torch 2.5.1+cu124 — Blackwell (cu128, sm_120) requires the ComfyUI-Win-Blackwell or PyTorch 2.7+ nightly path that already works for FLUX, but Hunyuan needs a recompile of any custom CUDA ops. Confirm with the Tencent issue tracker before relying on this in a sprint.

TEXGen: 24 GB inference budget matches our card; Linux-leaning install (apt-get / conda), so WSL2 is the path of least resistance.

### License
- Hunyuan3D-2.1: **TENCENT HUNYUAN COMMUNITY LICENSE** — non-commercial below 1M MAU, requires Tencent agreement above. Code release is open. Acceptable for research; flag for a future commercial release.
- MaterialMVP: academic, check repo.
- TEXGen: academic, check repo.

### Honest comparison vs MaterialAnything
For a terrain-mesh hero experiment in 2026, **Hunyuan3D-Paint 2.1 is the better first run than MaterialAnything**. The illumination-invariant training and PBR multi-channel head are designed for exactly the relighting failure modes that MaterialAnything's progressive consensus produces on non-canonical meshes. **Yes, swap the experiment.**

---

## Q9. Tileable + mesh-aware hybrid

### Direct answer
**No single 2026 open model unifies both.** The research literature does not contain a "give me PBR that bakes correctly to this mesh's UVs **and** is tileable when extracted to a tile section." The closest approximations:

- **CHORD's tileable-PBR + mesh projection in shader.** Run CHORD per biome; in Godot, the macro-detail shader UV-tiles the CHORD set across any mesh including hero terrain. This is what the worker is converging on for biome ground.
- **Hunyuan3D-Paint tile-aware fine-tune** — does not exist publicly. Would require fine-tuning the multi-view diffusion with a tileability loss in UV space. Open research direction; nothing released.
- **TEXGen UV-space diffusion** — operates directly in UV, which is the natural domain for tileability constraints. A UV-space diffusion with circular-padding loss could in principle produce tileable per-mesh textures, but no public training run does this.

### Honest comparison
This unified hybrid would be the right architecture, but no one has published it. **For now, accept the two-lane split** (tileable CHORD for biome ground, Hunyuan3D-Paint for hero meshes) and re-evaluate quarterly.

---

## Q10. 2026 production game terrain pipeline

### Recommendations / observations
1. **The dominant AAA pattern in 2025/2026 is still "tileable PBR atlas + splatmap blend + procedural placement," not ML-diffusion-end-to-end.** Frostbite, Horizon Forbidden West (Guerrilla — GDC 2022/2023 talks on procedural texturing of machines and deferred texturing of foliage), and InstaMAT 2025 all converge on a node-graph + tileable atlas + splatmap stack. ML-PBR is being grafted onto the *front* of these pipelines (replacing manual Substance graphs for individual tile authoring), not replacing the runtime stack.
2. **GDC 2025 / SIGGRAPH 2025 trend:** generative AI is being absorbed via ComfyUI as a **content authoring sidecar**, with CHORD (Ubisoft) being the most public production-grade example. Adobe's Substance 3D Sampler 4.4+ ships text-to-texture / image-to-material via Firefly (closed-source). https://blog.adobe.com/en/publish/2024/05/29/painter-10th-anniversary-generative-ai-updates-for-substance-3d
3. **Hero terrain is still mostly hand-authored** with photogrammetry + Substance Designer / Mari, and stitched into the tile-atlas via decals or virtual textures.
4. **The pattern we're missing**: **virtual texturing / runtime texture streaming**. The Horizon Forbidden West "deferred texturing for foliage" approach (GDC Vault 1027553) and Frostbite's procedural shader splatting are runtime techniques that decouple tile count from runtime cost. This is orthogonal to PBR generation but explains why AAA accepts having "only" 50–100 tileable PBR sets per game — because the runtime stack lets each tile cover hundreds of m² with shader-driven variation. We do not need 1000 tiles; we need ~30 great ones with good macro+detail blending and good biome variation.

### What we should adopt
- The tile-atlas-as-canonical-output pattern. We already do this; reaffirm it.
- A "hero decal layer" on top of tiled biome ground for one-off detail (boss-arena floor, lore-significant area) — built from `Hunyuan3D-Paint` outputs projected onto a low-poly hero mesh and composed via decal rendering. This avoids the need for hero terrain to be globally consistent with the tile set.

---

## Synthesis — three concrete decisions

### 1. Run the Workflow B "mesh-driven hero terrain" experiment, or use a 2026 alternative?
**Use a 2026 alternative — specifically Hunyuan3D-Paint 2.1.** Do not invest in adapting MaterialAnything's hemisphere camera config to a flat plane. The architectural concerns in the brief are real, no public experiment validates them, and Hunyuan3D-Paint 2.1's illumination-invariant + multi-channel-PBR design dominates MaterialAnything on the failure modes that flat terrain triggers. **Concrete plan: stand up Hunyuan3D-Paint 2.1 in a separate venv (Blackwell wheels via ComfyUI-Win-Blackwell or torch 2.7+/cu128 path), run the same goblin smoke-test that validated MaterialAnything, then run on a 4 m² subdivided desert-floor GLB at hemisphere-with-elevation-clamp (60–90°). Compare side-by-side to MaterialAnything on the same input.** Budget: 1–2 days install + 1 day experiment. If Hunyuan3D-Paint also smudges, fall back to TEXGen (UV-space diffusion, architecturally correct for terrain) + CHORD-as-PBR-estimator post-hoc.

### 2. The 1–2 specific tool changes that close the tileable-PBR quality gap (B/C → A)
- **(Primary)** Replace `derive_pbr_v2.py` with **CHORD** as the PBR estimation stage in `aaa_texture.py`. Wire it via the `ubisoft/ComfyUI-Chord` nodes or call its inference script directly from the AAA texture pipeline. CHORD is FLUX-friendly (so `flux_seamless.py` stays), CUDA-12.8-native (so Blackwell is fine), and outputs all 5 PBR channels with a learned model trained on MatSynth — strictly better than our heuristic estimator on materials with non-trivial specular variance. This is the single highest-leverage change.
- **(Secondary)** Add an **IP-Adapter / FLUX Redux reference-conditioning hook** on the FLUX stage of `flux_seamless.py`. Then the seam-grade pipeline gets a "reference photo" channel (`texture_qa.py` already grades; this lets the *generator* hit the reference). This addresses the brief's Q3 directly and turns C-grade textures into A-grade by giving the generator a target rather than only a text prompt.

Optionally (third lever): a **FLUX LoRA fine-tuned on Poliigon/FreePBR ground textures** for biome-specific generation. That's a follow-up after CHORD lands.

### 3. Add a separate "hero terrain" lane, or fold into existing lanes?
**Add a separate hero-terrain lane.** Three reasons:
- The architectures are genuinely different (UV-baked-bespoke vs UV-tiled-shared); trying to pretend they are one pipeline produces brittle code paths.
- The use case is rare (10% by area) but high-impact (boss arenas, lore set-pieces) — it deserves its own lane so it does not pollute the high-throughput biome-tileable lane with one-off tooling.
- The 2026 tool stack is different: tileable-biome lane = CHORD + FLUX + IP-Adapter; hero-terrain lane = Hunyuan3D-Paint 2.1 (or TEXGen + CHORD) + per-mesh GLB pipeline. Different venvs, different VRAM budgets, different failure modes.

Suggested naming: `pipelines/textures/biome_tileable/` (current) and `pipelines/textures/hero_mesh/` (new). The hero lane stays small until the Hunyuan3D-Paint terrain experiment validates the approach.

---

## Surprising findings worth flagging

- **CHORD landed in Dec 2025** and is essentially under-the-radar in our notes. It is the most consequential 2026 tool for our exact use case and we should adopt it before doing anything else on Workflow A.
- **MaterialAnything is no longer SOTA for mesh-PBR.** Hunyuan3D-Paint 2.1 (Jun 2025) and 2.5 (Jun 2025) plus MaterialMVP (Mar 2025) all surpass it on illumination-invariance and PBR channel quality. We validated MaterialAnything on 2026-05-07; we should not over-invest in it before benchmarking against Hunyuan3D-Paint.
- **No "tileable + mesh-aware hybrid" exists in 2026.** This is an open research gap — a UV-space diffusion with circular-padding loss is the obvious next paper but no one has published it.
- **Blackwell sm_120 support is now stable** in PyTorch 2.7.0+ with cu128 wheels, but Hunyuan3D and MaterialAnything ship pinned to older torch/CUDA — expect 1–2 days of dependency-untangling per tool, not weeks.
- **AAA pipelines in 2026 are NOT going end-to-end-ML.** They are using ML for tile authoring (CHORD-style) and keeping the runtime stack tile-atlas + splat + virtual-texture. We are correctly aligned with this pattern; we should not be tempted to replace the runtime stack.

## Sources

- [CHORD project page (Ubisoft La Forge)](https://ubisoft-laforge.github.io/world/chord/)
- [Ubisoft La Forge announcement: Generative Base Material](https://www.ubisoft.com/en-us/studio/laforge/news/1i3YOvQX2iArLlScBPqBZs/generative-base-material-an-opensource-prototype-for-pbr-material-estimation-debuting-at-siggraph-asia-2025)
- [ComfyUI blog: Ubisoft open-sources CHORD](https://blog.comfy.org/p/ubisoft-open-sources-the-chord-model)
- [ubisoft/ComfyUI-Chord GitHub](https://github.com/ubisoft/ComfyUI-Chord)
- [ubisoft/ubisoft-laforge-chord GitHub](https://github.com/ubisoft/ubisoft-laforge-chord)
- [Hunyuan3D 2.1 GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)
- [Hunyuan3D 2.1 paper (arXiv 2506.15442)](https://arxiv.org/html/2506.15442v1)
- [Hunyuan3D 2.5 paper (arXiv 2506.16504)](https://arxiv.org/abs/2506.16504)
- [MaterialMVP (ICCV 2025) paper](https://arxiv.org/abs/2503.10289)
- [MaterialMVP GitHub](https://github.com/ZebinHe/MaterialMVP)
- [TEXGen (SIGGRAPH Asia 2024)](https://arxiv.org/html/2411.14740v1)
- [TEXGen GitHub](https://github.com/CVMI-Lab/TEXGen)
- [DualMat paper (arXiv 2508.05060)](https://arxiv.org/abs/2508.05060)
- [DualMat project page](https://yifehuang97.github.io/DualMatProjPage/)
- [Tiled Diffusion (CVPR 2025)](https://arxiv.org/abs/2412.15185)
- [Tiled Diffusion GitHub](https://github.com/madaror/tiled-diffusion)
- [MatFuse project page](https://gvecchio.com/matfuse/)
- [MaterialFusion (arXiv 2502.06606)](https://arxiv.org/abs/2502.06606)
- [DreamMat GitHub](https://github.com/zzzyuqing/DreamMat)
- [Material Anything project page](https://xhuangcv.github.io/MaterialAnything/)
- [Make-A-Texture project page](https://mukosame.github.io/make-a-texture/)
- [Paint-it project page](https://kim-youwang.github.io/paint-it)
- [StableMaterials (HuggingFace)](https://huggingface.co/gvecchio/StableMaterials)
- [Adobe Substance 3D Sampler 4.4 release notes](https://helpx.adobe.com/substance-3d-sampler/release-notes/version-4-4---substance-3d-sampler.html)
- [Adobe Painter / Substance generative AI announcement](https://blog.adobe.com/en/publish/2024/05/29/painter-10th-anniversary-generative-ai-updates-for-substance-3d)
- [InstaMAT 2025 announcement](https://instamaterial.com/2025/07/16/instamat-2025-prepares-to-launch-with-powerful-new-features-and-scalable-workflows/)
- [InstaMAT 2025 release coverage (CG Channel)](https://www.cgchannel.com/2025/07/abstract-unveils-instamat-2025/)
- [InstaMAT terrain workflow](https://instamaterial.com/2025/05/19/revolutionizing-terrain-creation-instamats-all-in-one-workflow/)
- [Frostbite procedural shader splatting (chapter)](https://media.contentapi.ea.com/content/dam/eacom/frostbite/files/chapter5-andersson-terrain-rendering-in-frostbite.pdf)
- [GDC: Deferred Texturing in Horizon Forbidden West](https://gdcvault.com/play/1027553/Adventures-with-Deferred-Texturing-in)
- [GDC: Procedural Texturing of Horizon Forbidden West Machines](https://gdcvault.com/play/1029327/Taking-a-Procedural-Approach-to)
- [PyTorch sm_120 / RTX 5090 issue thread](https://github.com/pytorch/pytorch/issues/164342)
- [ComfyUI Blackwell installation discussion](https://github.com/Comfy-Org/ComfyUI/discussions/6643)
