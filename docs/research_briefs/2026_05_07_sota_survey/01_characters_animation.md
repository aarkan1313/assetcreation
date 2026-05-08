# Research Brief — Characters / Animation Pipeline (2026 SOTA)

## Goal

Identify 2026-current SOTA tools for **rigging arbitrary 3D meshes** (humanoid + non-humanoid creatures) and **animating them** (text-prompt-driven, library retargeting, or skeletal sim). The current pipeline produces meshes well but animation outputs are weak.

## Hardware target

- RTX 5090 Laptop (24 GB VRAM, Blackwell sm_120, requires CUDA 12.8+ / torch >=2.7)
- Windows 11; Python 3.11/3.12 venvs preferred. WSL2 acceptable but documented as fallback.
- Native Windows install path strongly preferred.

## Context

We have a working asset pipeline that produces 350-740k tri 3D meshes from concept images via Meshy. We preprocess them down to ~30k tris with UVs preserved. We have **33 character meshes** (mix of humanoids, monsters, undead, beasts, insects, dragons, sandworms, tentacles, etc.) ready as input.

We've installed and validated the following animator tools as of 2026-05-07:

- **Mesh-deformation animation:** AnimateAnyMesh (text-prompt → shape-key animated FBX). Outputs were judged as weak ("trash, most do nothing or barely move the head") on multiple characters. Run config wasn't documented; unclear if input mesh was rigged first.
- **Skeletal autorigging:** RigAnything (template-free autoregressive), MagicArticulate (skeleton-only), SkinTokens (skeleton + skin weights, ~30s on giraffe, claimed SOTA at 2026 launch).
- **Skeletal motion synthesis:** Anytop (skeleton-conditioned diffusion, 5 specialized models for bipeds/quadropeds/flying/millipeds_snakes/all). Tested on Bat — produces BVH motion files.
- **Text → motion → retarget:** hy-motion-fbx-exporter (Hunyuan-Motion, retargets to Mixamo skeleton).
- **Manual rigging UI:** Mesh2Motion app (humanoid + fox + bird + dragon skeleton library).
- **Mixamo (web):** humanoid-only, manual upload.

## Specific questions

1. **What is 2026 SOTA for animating diverse non-humanoid creatures?** Specifically: text-prompt or motion-library-driven animation that handles centipedes, sandworms, tentacle horrors, six-legged beasts, snake-bodies, flying creatures with wings. Does AnimateAnyMesh have a successor? Are there better alternatives in the diffusion-motion-on-arbitrary-skeletons space than Anytop?

2. **Which 2026 autoriggers handle the broadest topology range?** RigAnything claims template-free; MagicArticulate is CVPR '25; SkinTokens claims 17-22% improvement over UniRig. Is there something newer (post-Q3 2025) that's measurably better, especially on non-humanoid topology (legs ≠ 2, no clear bilateral symmetry, segmented bodies)?

3. **What's the current best workflow for end-to-end "mesh + text prompt → rigged + animated FBX"?** The user wants one canonical recipe for the 33-character roster. Specifically: should the chain be (a) rig first then animate skeletal, (b) shape-key without rigging, (c) hybrid? What does production game-asset work look like in 2026?

4. **Are there any tools we're missing entirely?** E.g., motion-capture-from-video → retarget pipelines (Move.ai successors, deepmotion alternatives, anything open-weights with a Windows path?), specialized-creature animators (something specifically for snakes/spiders/dragons), or "AI animator" wrappers that decide rigging-vs-shape-key automatically?

5. **What about animation review tooling?** We have 5 baked animations and they're hard to evaluate without opening each FBX in Blender. Is there a 2026 standard for "animation quality scoring" (e.g., looking for static frames, foot-skating, intersection artifacts) that could automate the validation?

6. **Sprite-sheet baking** — we use Blender to bake 8-angle × 16-frame sprite sheets at 6816×3344. Is there a faster / better-quality 2026 sprite-baking tool, especially one that could batch-process 33+ characters efficiently?

## Format of response

Per question:
1. Top 2-3 tool/approach recommendations with one-paragraph why
2. Hardware/install fit assessment (RTX 5090 Blackwell sm_120 / Windows native)
3. License + cost notes (we prefer open-weights or self-hosted; cloud OK if cost-effective per asset)
4. Maturity check: is the project actively maintained 2025/2026, or abandoned?
5. **Honest comparison** to what we have — does the new tool actually beat AnimateAnyMesh / RigAnything / SkinTokens / Anytop, or is it lateral?

Skip generic SaaS animation tools (Cascadeur, Kinetix, Animate-It pro, etc.) unless they have an API. We need programmatic batch processing.

## Out of scope

- 2D animation (we already do sprite-sheet baking from 3D)
- Mocap hardware/recording
- Standalone modeling tools (we use Meshy for image→3D)

## After response returns

The pipeline review at `docs/pipeline_reviews/06_characters.md` and the install matrix at `animators/INSTALL_MATRIX.md` will be updated. Specifically the user wants to:
- Recover the run config that produced the bad animations
- Decide a canonical rigging path (humanoid vs non-humanoid)
- Decide a canonical animation path (skeletal vs shape-key vs hybrid)
- Validate the chosen path on 1 humanoid + 1 non-humanoid before fanning out to all 33
