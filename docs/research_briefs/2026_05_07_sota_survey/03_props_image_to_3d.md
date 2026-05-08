# Research Brief — Props / Image-to-3D Pipeline (2026 SOTA)

## Goal

Identify 2026-current SOTA tools for **image-to-3D mesh generation** suitable for game props (rocks, weapons, furniture, ruins, environment objects). Current default is microsoft/TRELLIS.2-4B. We want to know if anything has surpassed it.

## Hardware target

- RTX 5090 Laptop (24 GB VRAM, Blackwell sm_120, requires CUDA 12.8+ / torch >=2.7)
- Windows 11; Python 3.11/3.12 venvs preferred
- Native Windows install path strongly preferred; ComfyUI integration a plus

## Context

Our props pipeline produces game-ready 3D meshes from concept image PNGs. Phase 11 (2026-05-06) compared two AI routes head-to-head on the same Egyptian-obelisk concept:

- **Trellis2 4B (microsoft/TRELLIS.2-4B)** — picked as default. Wins visually at every config tested. Even Trellis2 `low` ≈ HY3D `hero_max` for 200× less wall-clock. Local install on RTX 5090.
- **Hunyuan3D-2.1** — kept as fallback (ComfyUI integration via kijai+visualbruno custom nodes). Useful for biome scatter authoring.
- **Meshy** (cloud) — used for character pipeline; ~30 credits remaining as of yesterday.

After image-to-3D, we run a 7-stage postprocess orchestrator: stage_into_library → preprocess (Blender) → 4-tier LOD chain (DECIMATE COLLAPSE) → CoACD convex collision → billboard bake → PBR material bind → validate → Godot export. Output: `world/props/library/<id>/{model_lod0-3.glb, collision.json, prop.json, postprocess_log.json}` ready for Godot.

The pipeline has only been pushed end-to-end on **1 hero prop** (the obelisk). 50 other entries in the library are mostly procedural variants (rock_small × 4 seeds, ruin_block × 4, etc.) or decals.

## Specific questions

1. **Has anything surpassed Trellis2 4B in 2026?** Specifically asking about quality of generated mesh + PBR texture, not just speed. What about Hunyuan3D-2.5 or a 2026 successor? Trellis 3.x?

2. **What about higher-quality but slower options for hero props?** Trellis2 hi_tex preset gives 200k tris @ 4096² textures in ~30s. Is there a 2026 model that produces *visibly better* hero-quality output even if it takes 5-10 minutes per prop?

3. **Specialized prop generators for specific categories?** E.g., is there a "weapon-specific" image-to-3D model, an "architecture/ruin-specific" model, a "vegetation/foliage" specialist that beats general-purpose Trellis2 on those categories?

4. **What's the 2026 SOTA for procedural prop variation?** We currently parameterize seeded displacement (rock_small_a01..a04 differ by displacement_magnitude + z_squash + subdivisions). Is there a better way to get N variants of the same prop concept? E.g., latent-space interpolation in Trellis2, ControlNet-style reference-conditioning, etc.

5. **What about the 7-stage postprocess?** We use CoACD for collision decomposition, DECIMATE COLLAPSE for LOD chain, and a custom billboard baker. Is anything in this chain 2026-stale? E.g., is there a better automatic LOD generator than COLLAPSE for tris-budgets in the 50k → 1k range?

6. **Multi-prop batch generation tooling?** We have `trellis2_batch.py` (model-load-once batch runner). Is there a 2026 tool that does production-scale prop generation from a sketch list — e.g., "give me 30 medieval weapons" — with style consistency across the set?

7. **Cloud vs local economics for props.** Meshy cloud worked for characters. For props, is Meshy still competitive in 2026, or has the local Trellis2/HY3D path made cloud generation obsolete? Is there a hybrid pattern (e.g., Meshy for hero, local for scatter)?

## Format of response

Per question:
1. Top 2-3 tool/approach recommendations with one-paragraph why
2. Hardware/install fit (RTX 5090 Blackwell sm_120 / Windows native)
3. License + cost notes (open-weights preferred; ComfyUI integration plus)
4. Maturity check: actively maintained 2025/2026?
5. **Honest comparison** — does the new tool actually beat Trellis2 4B, or is it lateral?

## Out of scope

- 2D-only generators (we need real 3D mesh + UV + PBR)
- Photogrammetry (no real-world scanning workflow)
- Manual modeling tools (we won't ZBrush)

## After response returns

Update `docs/pipeline_reviews/05_props.md` and `pipelines/props/README.md` with new options identified. The user's interest is **multi-prop generalization** (Phase 11 was 1 example) and **higher hero-quality** for important assets.
