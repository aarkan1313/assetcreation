# Research Brief — Textures Pipeline (2026 SOTA)

## Goal

Identify 2026-current SOTA tools for **PBR texture generation**, with focus on three concrete decisions:

1. **Tileable biome ground textures** (the worker is currently fixing seam quality here)
2. **Mesh-driven hero terrain** (apply MaterialAnything-style mesh-PBR to terrain pieces)
3. **Whether a "tileable + mesh-aware" hybrid exists** in 2026 that subsumes both

## Hardware target

- RTX 5090 Laptop (24 GB VRAM, Blackwell sm_120, CUDA 12.8+ / torch >=2.7)
- Windows 11; Python 3.11/3.12 venvs preferred
- WSL2 acceptable for Linux-only deps

## Context

We have **two distinct PBR-texturing workflows** in the project today, neither fully solved:

### Workflow A — Tileable PBR set (`pipelines/textures/`)

Text prompt → seamless 1024² PBR set, UV-tiled via shader across any surface. Use for biome ground, walls, anything repeated.

- **Default backend:** `aaa_texture.py` uses StableMaterials (`gvecchio/StableMaterials`) for image-to-PBR
- **Seamless albedo:** `flux_seamless.py` runs FLUX 2 with offset+heal trick (4-pass: text2img → circular shift → img2img heal → reverse shift)
- **Heuristic albedo→PBR:** `derive_pbr_v2.py` deterministically estimates height/normal/AO/roughness from albedo
- **Seam QA:** `texture_qa.py` computes edge-MSE seam grade A/B/C
- **Library state:** 31 sets in `world/textures/library/`. Worker active 2026-05-07 improving quality. As of yesterday, 10 A / 11 B / 3 C + 7 ungraded; current state TBD.
- **Worldgen v2 used `flux_seamless.py` but bypassed AAA full pipeline** → produced B/C-grade albedo-only outputs. That's part of why worldgen v1+v2 got nuked.

### Workflow B — Mesh-driven PBR (`animators/MaterialAnything/`, validated 2026-05-07)

Mesh GLB/OBJ + text prompt → per-mesh UV-baked PBR. Use for hero rocks, unique cliff faces, props.

- **Tool:** `MaterialAnything/scripts/generate_texture_pbr_3d.py` (Microsoft, CVPR '24)
- **Architecture:** ControlNet-Depth inpaint + iterative multi-view consensus + UV-space refinement
- **Validated:** end-to-end on goblin GLB (3-view smoke test, 56 MB output, ~10 min wall-clock)
- **Architectural constraint:** does NOT work on flat 2D textures (the multi-view consensus needs real 3D geometry to disambiguate). For 2D albedo→PBR, use `derive_pbr_v2.py`.
- **Per-mesh output is NOT tileable** — bespoke to that mesh. Right for hero pieces, wrong for repeated ground.

### What we want a research agent to figure out

The two workflows split cleanly for props (use B for hero, A for nothing — props don't tile). But for **terrain**:

- 90% of biome ground needs **tileable** (kilometers of forest floor, desert sand, etc.)
- 10% needs **bespoke per-mesh** (boss-arena floor, unique cliff face, volcano caldera, hero canyon)

Today we have **no solid answer for either** — Workflow A is mid-quality, Workflow B has never been run on a terrain mesh.

## Specific questions

### Tileable ground textures (Workflow A successors)

1. **2026 SOTA for tileable PBR generation.** StableMaterials shipped late 2024. What's surpassed it for tileable PBR map generation? Specifically asking about full PBR sets (albedo + normal + roughness + height + metallic) generated *natively tileable*, not retrofitted with offset+heal. Examples: TexFusion+, PBR-FLUX, Substance-3D-AI, GameTexture.AI, etc.

2. **Is there a 2026 model that natively does tileable + materially-correct?** The offset+heal trick (`flux_seamless.py`) gets us tileable albedo but the *PBR channels* are derived heuristically. A 2026 model that produces all 5 PBR channels seamlessly tileable in one pass would solve this end-to-end.

3. **Reference-based seamless texture iteration.** We score textures with edge-MSE seam grades. Is there a 2026 tool for "give me seamless mossy basalt that *matches this reference photo*" beyond CLIP-similarity scoring? Style-conditioned PBR generation?

4. **Specialized ground-texture generators.** Substance Designer has procedural-ground graphs. Are there 2026 ML alternatives specialized for *ground textures* (cracked earth, gravel, snow, sand, forest floor) that beat general-purpose StableMaterials?

5. **Macro+detail PBR pairs.** We have a macro_detail_v1.gdshader that blends a coarse + fine texture for AAA close-up + far look. Is there a 2026 tool that *generates the macro+detail pair together*, designed to blend correctly?

### Mesh-driven hero terrain (Workflow B retrofit)

6. **Can MaterialAnything be used as-is for terrain meshes?** Specifically: convert a DEM heightmap → subdivided plane mesh → UV-unwrap top-down → run MaterialAnything with prompt "cracked desert ground with scattered pebbles, satellite view". Does the iterative multi-view diffusion produce useful output on a flat horizontal mesh, or does it produce smudgy garbage because cameras are object-centered? Has anyone published this experiment?

7. **What viewpoint configuration works for ground meshes?** MaterialAnything's `predefined` mode has cameras facing the object from sides + top. For flat terrain we'd want top-down + slight oblique angles. Is there a recipe for adapting it, or is `hemisphere` mode the right answer?

8. **MaterialAnything alternatives for terrain.** What 2026 mesh-PBR tools work better than MaterialAnything specifically for terrain meshes? Examples: DreamMat, Paint3D, TEXTure variants, Hunyuan3D-2.1's texture stage. Which handle (a) flat geometry, (b) tiling-aware output, (c) detailed PBR (not just albedo)?

### Hybrid / unified approaches

9. **Is there a 2026 "tileable + mesh-aware" hybrid?** I.e., a tool that takes a mesh + text prompt and produces a PBR set that's *both* UV-baked correctly to that mesh AND tileable when unwrapped to a tile-able section. This would unify both workflows. Examples in research literature?

10. **What's the 2026 production game pipeline for terrain texturing?** AAA studios — what's their mix of tileable-procedural + mesh-baked-hero + photogrammetry? Is there a tooling pattern we should adopt that we've missed?

## Format of response

Per question:
1. Top 2-3 tool/approach recommendations with one-paragraph why
2. Hardware/install fit (RTX 5090 Blackwell sm_120 / Windows native; CUDA 12.8+)
3. License + cost notes (open-weights preferred; ComfyUI integration plus)
4. Maturity check: actively maintained 2025/2026?
5. **Honest comparison:**
   - For Workflow A questions: does the new tool actually beat StableMaterials + flux_seamless + derive_pbr_v2?
   - For Workflow B questions: is the experiment worth running, or is there a better tool to use instead?

## Out of scope

- Photogrammetry hardware/scanning (no ground-truth capture)
- Manual Substance Designer authoring (we want programmatic batch)
- Generic 2D image generators (we already have FLUX integration; question is PBR-specific)

## After response returns

Update:
- `docs/pipeline_reviews/02_textures.md` (currently un-written; create it after response lands and worker has handed off)
- `pipelines/textures/PIPELINE.md` and `LESSONS.md`
- `WORKFLOWS.md §3a/3b/3c` with actionable recommendations
- `docs/audits/AUDIT_2026_05_07_post_nuke.md` if priority moves change

Specifically the user wants to:
- Decide whether to run the Workflow B "mesh-driven hero terrain" experiment or use a 2026 alternative
- Identify the 1-2 tool changes that would close the tileable-PBR quality gap (current B/C grades, want all A)
- Decide whether to add a "hero terrain" lane separate from the biome-tileable lane

## Background context: why this brief is now active

This brief was originally **deferred until the texture worker handed off** their improvements. It became active because (a) the user asked specifically about retrofitting MaterialAnything-style approaches for ground textures, and (b) the question goes beyond what the worker is doing (they're improving tileable seam quality; this brief asks what *replaces* the tooling). The worker should still hand off their findings — those will inform which of these 10 questions are most pressing.
