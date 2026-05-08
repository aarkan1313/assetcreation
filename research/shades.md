# AI/Generative Tooling for Shader Creation — Survey for Godot/three.js/WebGL VFX Pipelines

## TL;DR
- The space breaks into three usable layers: (1) **VLM/LLM program-synthesis models** that emit node graphs or Python (VLMaterial, MultiMat, MatFormer/ProcMatRL, BlenderAlchemy) — best for procedural materials but tied to Substance/Blender, not GLSL; (2) **diffusion-based PBR texture generators** (StableMaterials, MatFuse, MaterialPalette, Chord/Generative Base Material, MaterialMVP, Hunyuan3D 2.1, Polycam) that drop into any GLSL/Godot/three.js workflow as albedo/normal/roughness/metallic maps; and (3) **LLM-driven Shadertoy/GLSL generation** (AI Co-Artist, ShaderToy-MCP, AI Shader Studio, image-to-shader, AI Shader Generator for Unity, Sasso et al.'s interactive evolutionary shader tool) — the most directly relevant family for animated spell/VFX shaders, but largely experimental.
- For the user's specific spell/VFX use case on GLSL/WebGL, the highest-leverage stack today is: **Claude/GPT/Gemini + Shadertoy21k corpus (RAG) + Vipitis/shadermatch evaluation harness + iterative render-in-the-loop critique**, supplemented by diffusion PBR generators for static surfaces and Material Maker/Infinigen as a bridge for procedural noise libraries. There is currently **no production-grade, spell-VFX-specific generative model** — only general LLM coding plus Shadertoy-domain fine-tuning research.
- The most genuinely "frontier/fringe" items worth experimenting with: **VLMaterial (ICLR'25 Spotlight, weights released)**, **MultiMat (Sept 2025, Adobe)**, **AI Co-Artist (arXiv 2512.08951, Nov 2025, evolutionary GLSL with GPT-4)**, **ProcMatRL (Adobe SIGGRAPH Asia 2024 RL fine-tuning of MatFormer)**, **Vipitis/shadereval + shaders21k benchmark and dataset**, and **Chord / Ubisoft Generative Base Material (SIGGRAPH Asia 2025, open-sourced)**.

---

## Key Findings

### 1. Vision-Language Models for shader/material program synthesis
- **VLMaterial (mit-gfx, ICLR 2025 Spotlight)** — fine-tunes LLaMA-3-8B-based LLaVA-NeXT to emit Blender Python procedural-material programs from an image. Code, dataset, and weights are publicly released on GitHub (mit-gfx/VLMaterial). [arXiv](https://arxiv.org/abs/2501.18623) Output: Blender shader-node graphs as Python. Not GLSL, but graphs can be baked to texture maps for Godot/three.js. Requires ≥48 GB VRAM to retrain; [GitHub](https://github.com/mit-gfx/VLMaterial) inference is lighter. Maturity: research code, runnable.
- **MultiMat (arXiv 2509.22151, Belouadi et al., Sept 2025; v2 Feb 2026)** — multimodal program synthesis for Adobe Substance 3D node graphs. Trains on the largest curated Substance corpus to date. Adds constrained tree-search inference for static correctness. Outperforms VLMaterial-style text-only baselines. Output: Substance graphs (node-by-node, image+text conditioned). Not directly GLSL; pipeline is Substance → bake → maps. Code/data status: paper-only as of search (no public weights confirmed). Maturity: cutting-edge research.
- **MatFormer (Adobe Research, SIGGRAPH 2022)** — first transformer-based generator for Substance graphs (nodes → params → edges, three transformers). [Paulguerrero](https://paulguerrero.net/matformer/) [arXiv](https://arxiv.org/pdf/2207.01044) Foundation for all subsequent work. The conditional MatFormer (Hu et al. SIGGRAPH 2023) adds CLIP-based text/image conditioning. [arxiv](https://arxiv.org/pdf/2304.13172)
- **ProcMatRL (adobe-research/ProcMatRL, SIGGRAPH Asia 2024, Li et al.)** — RL-fine-tunes a conditional MatFormer with rendering-loss reward. [GitHub](https://github.com/adobe-research/ProcMatRL) Code released; pre-trained weights only available for a sample model trained on DiffMat-published materials (not Adobe internal data). [GitHub](https://github.com/adobe-research/ProcMatRL) Maturity: research code.
- **Conditional MatFormer / "Generating Procedural Materials from Text or Image Prompts" (Hu et al. 2023)** — image- or text-conditioned graph generation using CLIP-conditioned MatFormer.
- **BlenderAlchemy (Stanford, ECCV 2024, Huang/Yang/Guibas)** — uses GPT-4V as an iterative editor of Blender programs. [Ecva](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/12578.pdf) Edits material/lighting node graphs from text or reference images via vision-based "edit generator + state evaluator" search loop. [Dsin](https://dsin.ai/news/article/cO5YmEm/blenderalchemy_editing_3d_graphics_with_vision_language_models) Code released (ianhuang0630.github.io/BlenderAlchemyWeb). Output: Blender Python edits. Practical for an "image → tweak → rerender" loop, again not GLSL but bakeable.

### 2. Diffusion-based PBR / SVBRDF generation (drop-in PBR maps)
- **MatFuse (Vecchio et al., CVPR 2024; giuvecchio/matfuse-sd)** — multi-conditional LDM (color palette + sketch + text + image) producing diffuse/normal/roughness/specular SVBRDF maps. Code on GitHub; not weights-light (relies on multi-encoder VQ-GAN). Maturity: research code, runnable.
- **StableMaterials (gvecchio/StableMaterials on Hugging Face)** — semi-supervised LDM distilled from SDXL. Generates tileable PBR (basecolor, normal, height, roughness, metallic) at 512×512 (base) with refiner, plus a 4-step LCM variant. Weights public. Direct fit for Godot/three.js (just sample maps and plug into StandardMaterial3D/MeshStandardMaterial). Maturity: production-usable.
- **MaterialPalette (astra-vision/MaterialPalette, CVPR 2024)** — extracts PBR (albedo, normal, roughness) from a single real-world photo by per-region SD fine-tuning + decomposition net. Weights and code public. Useful for "photograph → tileable texture" pipelines.
- **ControlMat (Adobe, 2024)** — controlled SVBRDF estimation/generation with noise-rolling for tileability. Paper, not open weights.
- **Chord / Generative Base Material (Ubisoft La Forge, ETH Zürich, SIGGRAPH Asia 2025)** — two-stage: text/sketch/height-guided diffusion for tileable color image, then chained image-conditional diffusion ("Chord" with LEGO-conditioning) decomposes into basecolor → normal+height → roughness+metalness, plus a 2×/4× upscaler. Open-source prototype trained on MatSynth weights released; project page at ubisoft-laforge.github.io/world/chord/. arXiv 2509.09952. Maturity: prototype/research, but explicitly aimed at game artists.
- **MaterialMVP (Tencent Hunyuan, arXiv 2503.10289)** — multi-view PBR diffusion for textured 3D meshes. Generates albedo + metallic-roughness from mesh + reference image with consistency regularization. Pairs with Hunyuan3D 2.1. [arxiv](https://arxiv.org/pdf/2506.16504)
- **DreamMat (ACM TOG 2024, zzzyuqing.github.io/dreammat.github.io)** — text-to-PBR for meshes via geometry- and light-aware 2D diffusion, distilled into PBR materials without baked-in lighting. [arxiv](https://arxiv.org/pdf/2405.17176) Open code.
- **Hunyuan3D 2.1 / 2.5 (Tencent, June–Aug 2025)** — fully open-sourced (2.1) image→3D with PBR pipeline, including weights and training code. [GitHub](https://github.com/tencent-hunyuan/hunyuan3d-2.1) Can be repurposed to generate PBR materials in isolation. Hunyuan3D 2.5 adds 4K textures, bump, multi-view PBR [GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/issues/111) but is not yet open-sourced.
- **MatPedia (2025)** — joint RGB-PBR foundation model trained on MatHybrid-410K, native 1024×1024, supports text/image-to-material and intrinsic decomposition (paper).
- **EnvMat** — simultaneously generates PBR + environment maps from a single image (paper).
- **MatE** — generates tileable PBR from a single in-the-wild image with depth-guided rectification (paper).
- **Polycam Material Generator / withPoly** — commercial text-to-tileable PBR with seamless tiling [Easy With AI](https://easywithai.com/ai-3d-assets-textures/polycam-material-generator/) and PBR map outputs (albedo/normal/roughness/displacement). Free tier; [BlenderNation](https://www.blendernation.com/2023/05/09/poly-create-8k-pbr-textures-in-seconds-with-generative-ai/) production-ready output for any GLSL workflow.
- **MatSynth (arXiv 2401.06056, Vecchio & Deschaintre, CVPR 2024)** — 4,000+ CC0 4K PBR materials with metadata and 3M+ renderings. [arxiv](https://arxiv.org/pdf/2401.06056) The de-facto open training corpus for the diffusion-PBR family above. On Hugging Face (gvecchio/MatSynth).
- **Stable Diffusion XL DIY pipelines** (Casey Primozic; "Toolify" tutorial) — manual albedo + Materialize/DeepBump for height/normal/roughness. [Toolify](https://www.toolify.ai/ai-news/create-stunning-pbr-materials-with-ai-stable-diffusion-tutorial-2624258) Crude but very flexible.

### 3. LLM-based GLSL / Shadertoy generation (the closest fit to spell/VFX)
- **AI Co-Artist (arXiv 2512.08951, Yuksel & Sawaf, Nov 2025)** — GPT-4-driven evolutionary refinement of GLSL fragment shaders [arXiv](https://arxiv.org/abs/2512.08951) [arXiv](https://arxiv.org/html/2512.08951) with audio reactivity, crossover, and mutation. Picbreeder-style UI. [arXiv](https://arxiv.org/html/2512.08951) [arXiv](https://arxiv.org/abs/2512.08951) User study shows novices producing 4.2 vs 0.6 viable shaders (vs raw Shadertoy) and >60% time-to-first-result reduction. [arXiv](https://arxiv.org/html/2512.08951) Working HTML prototype available. [arXiv](https://arxiv.org/html/2512.08951) Highly relevant template for spell/VFX iteration.
- **ShaderToy-MCP (wilsonchenghy/ShaderToy-MCP, GitHub)** — Model Context Protocol server exposing Shadertoy.com to Claude/Cursor. Lets the LLM read existing community shaders and remix them into new ones. [LobeHub](https://lobehub.com/mcp/wilsonchenghy-shadertoy-mcp) [Glama](https://glama.ai/mcp/servers/@wilsonchenghy/ShaderToy-MCP) Output: Shadertoy-style GLSL (`mainImage(out vec4, in vec2)`). [LobeHub](https://lobehub.com/mcp/wilsonchenghy-shadertoy-mcp) Easy to drop into three.js (uniforms iTime, iResolution, iMouse [Shadertoy](https://www.shadertoy.com/view/cst3R2) trivially port).
- **llm-shader-toy (johnPertoft/llm-shader-toy)** — minimal browser app that pipes prompts to an LLM and runs the GLSL output in WebGL. [GitHub](https://github.com/johnPertoft/llm-shader-toy) Simple, hackable.
- **Interactive GLSL Shader Creator (llm-shader-art.sabrina.dev)** — natural-language→GLSL web tool [Sabrina](https://llm-shader-art.sabrina.dev/) (small/personal but live).
- **AI Shader Studio (simonkandah.com)** — Three.js + MediaPipe + Gemini API pipeline that generates GLSL fragment shaders at runtime and applies them to webcam video; [Simon Kandah](https://simonkandah.com/ai-shader-studio/) demonstrates real-time prompt-to-shader on the web stack the user is targeting.
- **AI Shader Generator (aishader.com)** — commercial text-prompt → Unity Shader Graph asset [Aishader](https://aishader.com/) (Shader Graph JSON format). Limited utility for Godot/three.js, but evidence of demand.
- **Generative AI for Node-Based Shaders (Erfani, Medium 2024-2025)** — research blog describing GPT-4/Gemini + RAG + parser to emit Unity Shader Graph JSON. Reports ~8–9 s generation, [Medium](https://medium.com/design-bootcamp/exploring-ai-integration-in-node-based-shaders-5d127fd3cbff) similarity scores ~5.2/10 on abstract prompts ("aurora borealis"), [Medium](https://medium.com/design-bootcamp/exploring-ai-integration-in-node-based-shaders-5d127fd3cbff) and especially good results on particle effects (e.g., "swarm of fireflies"). [Medium](https://medium.com/design-bootcamp/exploring-ai-integration-in-node-based-shaders-5d127fd3cbff) Not GLSL, but a usable template if porting via a Godot VisualShader JSON parser.
- **Mejba's "AI Shader Effects" Claude skill** — practitioner write-up of building a Three.js distortion/glow shader skill that handles ShaderMaterial uniforms, mouse coords, ResizeObserver, disposal — i.e., the AI-generated WebGL plumbing failures. [Engr Mejba Ahmed](https://www.mejba.me/blog/ai-shader-effects-claude-code) Best practice notes, not a model.
- **AI Co-Artist's evolutionary mutation/crossover prompts** — directly applicable for evolving spell shader variants ("more chaotic," "slow down"). [arXiv](https://arxiv.org/html/2512.08951)
- **A Tool for Procedural Generation of Shaders using Interactive Evolutionary Algorithms (Sasso, Loiacono, Lanzi, arXiv 2312.17587)** — Unity-integrated IEC over the underlying graph. [arxiv](https://arxiv.org/pdf/2312.17587) Algorithm transferable to Godot VisualShader graphs.
- **Datasets / benchmarks for fine-tuning**:
  - **shaders21k (mbaradad/shaders21k, NeurIPS 2022)** — ~21,000 Shadertoy fragment shaders with code + rendered frames. The standard corpus for shader ML.
  - **shaders20k / Vipitis/shadertoys-dataset** — Shadertoy-only subset, with API-fetched 2022-2023 additions; tree-sitter-glsl parsing scripts and license detection. [GitHub](https://github.com/Vipitis/shadertoys-dataset)
  - **Vipitis/Shadereval-inputs / shadermatch metric (HF + bigcode-evaluation-harness PR #173)** — function-completion benchmark [Hugging Face](https://huggingface.co/datasets/Vipitis/Shadereval-inputs) + perceptual `shadermatch` similarity metric for evaluating LLM shader generation. Used in IEEE LLM4Code 2025 paper "Evaluating Language Models for Computer Graphics Code Completion" (Kels et al.). Directly usable as a critic in a render-in-the-loop pipeline.
  - **WAT↔WGSL parallel corpus (ACM 2025, dl.acm.org/doi/10.1145/3759425.3763398)** — 14,547 parallel WebAssembly-WGSL pairs derived from shaders21k. Useful if targeting WebGPU.
- **LLM Ultimate Challenge: Interactive GLSL Shader Art (artificialanalysis.ai microeval)** — informal benchmark probing frontier LLMs (Claude/GPT/Gemini) on Three.js + GLSL fractal generation. [Artificial Analysis](https://artificialanalysis.ai/microevals/llm-ultimate-challenge-interactive-glsl-shader-art-1756340323607) Good evidence that frontier models can produce non-trivial animated WebGL out of the box.

### 4. SDF / raymarching / CSG generation
- **UCSG-Net (Kania et al., NeurIPS 2020)** — unsupervised CSG-tree extraction (primitives + boolean ops) from shapes via differentiable indicator functions; predicted parse trees are reproducible in CAD. [NeurIPS](https://papers.neurips.cc/paper_files/paper/2020/file/63d5fb54a858dd033fe90e6e4a74b0f0-Paper.pdf)
- **Constructive Solid Geometry on Neural SDFs (Marschner et al., SIGGRAPH Asia 2023)** — closest-point-loss regularizer that keeps neural implicits as true SDFs [ACM Digital Library](https://dl.acm.org/doi/fullHtml/10.1145/3610548.3618170) through union/intersection/subtract operations and parametric families. [Zoemarschner](https://zoemarschner.com/research/csg_on_neural_sdfs.html)
- **Diffusion-SDF (arXiv 2212.03293)** — text-to-shape via voxelized diffusion of TSDFs. [arxiv](https://arxiv.org/pdf/2212.03293) Useful upstream of SDF-based raymarchers.
- **InverseCSG (Du et al., SIGGRAPH Asia 2018)** — automatic conversion of 3D models to CSG trees [ACM Digital Library](https://dl.acm.org/doi/10.1145/3610548.3618170) (still cited in modern work).
- **DIST: Differentiable sphere tracing (Liu et al., CVPR 2020)** — differentiable rendering for neural SDFs; [arxiv](https://arxiv.org/pdf/1911.13225) lets you optimize SDF parameters via image loss — a building block for SDF "render-in-the-loop" pipelines.
- **For raymarched/SDF shader code itself**, current practice is to point Claude/GPT-4/Gemini at Inigo Quilez's `iquilezles.org/articles/raymarchingdf/` library and Shadertoy fragments and let them assemble — there is no dedicated "text→SDF GLSL" model with public weights. The ShaderToy-MCP + AI Co-Artist pattern is the de-facto approach.
- **Infinigen (Princeton VL, princeton-vl/infinigen)** — fully procedural Blender-based world/terrain/plant/creature generator. ~50 procedural-material generators. [Medium](https://xrender-farm.medium.com/infinigen-free-procedural-environment-generator-for-3d-creation-b11241290fc7) Outputs full geometry + Blender shader nodes; export via Blender to OBJ/FBX/USD for Godot/three.js. Not AI per se ("Math rules only. Zero AI") [Infinigen](https://infinigen.org/) but its procedural noise/material library is excellent training data for VLM-style code generation (and is used as such by VLMaterial).

### 5. Node graph generators for Godot / three.js / GLSL
- **Material Maker (RodZilla; godotengine.org/article/godot-showcase-material-maker)** — open-source Godot-native procedural material editor. Already exports to Godot, Unity, Unreal (translates GLSL → HLSL). [Godot Engine](https://godotengine.org/article/godot-showcase-material-maker/) The natural target for any node-graph-emitting LLM if you stay GLSL-native. ~250 nodes, [Godot Engine](https://godotengine.org/article/godot-showcase-material-maker/) active community.
- **MaterialX → GLSL importer for Godot (godotengine/godot-proposals#714)** — proposal/effort to translate Substance MaterialX exports into Godot shaders. [GitHub](https://github.com/godotengine/godot-proposals/issues/714) Useful if you want to consume MatFormer/MultiMat outputs.
- **basementstudio/shader-lab** — Three.js-native ShaderMaterial / TSL toolkit; useful as a runtime sandbox for AI-generated shaders.
- **Substance Designer's MaterialX plugin → GLSL** — discussed in three.js forum thread (discourse.threejs.org/t/22795); requires GLSL v4.0+, [Three.js](https://discourse.threejs.org/t/making-materials-using-rawshadermaterial-with-shaders-from-substance-designer/22795) plus a custom THREE.RawShaderMaterial wrapper.
- **Polycam / withPoly** also export PBR-map ZIPs that drop straight into Godot's StandardMaterial3D and three.js MeshStandardMaterial.

### 6. Frontier/fringe research worth tracking
- **MultiMat** (Sept 2025) — multimodal Substance-graph synthesis with constrained tree search; the current SOTA for procedural-material program synthesis.
- **VLMaterial successors / MIT diffmat ecosystem** — `mit-gfx/diffmat` (PyTorch differentiable Substance graphs; [GitHub](https://github.com/mit-gfx/diffmat) SIGGRAPH Asia 2020 + ongoing) is the substrate; MATch optimizer; VLMaterial dataset (`material_dataset_filtered.zip` available with the repo); pre-trained LLaVA-NeXT VLM weights provided. [GitHub](https://github.com/mit-gfx/VLMaterial)
- **Chord / LEGO-conditioning** (Ubisoft, SIGGRAPH Asia 2025) — open-source PBR estimation pipeline aimed at production game art.
- **AI Co-Artist** — only 2025 paper explicitly evolving animated GLSL fragment shaders with an LLM; small but the most directly aligned with spell-VFX use case.
- **Diffusion as Shader (DaS, IGL-HKUST/DiffusionAsShader, SIGGRAPH 2025)** — *not* a GLSL generator despite the name; it's a 3D-tracking-conditioned video diffusion model. [Hugging Face](https://huggingface.co/papers/2501.03847) Useful for *referencing* spell motion (camera/object control of a video showing the desired effect) before implementing the GLSL.
- **Procedural Image Programs for Representation Learning / shaders21k** — basis for several of the benchmarks above.
- **Learning from Shader Program Traces (arXiv 2102.04533)** — auxiliary technique: feeding the program trace (intermediate values per pixel) into a learned model. Useful as a denoising/postprocessing layer in a render-in-the-loop critic.
- **Dressi (Huawei, arXiv 2204.01386)** — Vulkan-based hardware-agnostic differentiable renderer [arxiv](https://arxiv.org/pdf/2204.01386) with reactive shader packing. Differentiable rasterization-time shader optimization, niche but interesting.
- **Sasso et al. interactive evolutionary Unity shader IEC (arXiv 2312.17587)** — small but practical interactive evolution over Shader Graph.
- **Hi-Godot/Godot-AI MCP (godotengine.org Asset Library #5050)** — MCP server with one-call presets for `ShaderMaterial`, `GPUParticles`, fire/smoke/sparks/magic/lightning/explosion/rain. [Godot Engine](https://godotengine.org/asset-library/asset/5050) Not generative in the model sense but a prompt-driven authoring layer for Godot specifically; pairs well with Claude Code/Cursor.
- **GodotPrompter (jame581/GodotPrompter)** — agentic skills framework: 44 Godot 4.3+ skills including `particles-vfx` (GPUParticles2D/3D, ParticleProcessMaterial recipes, color ramps). [GitHub](https://github.com/jame581/GodotPrompter)
- **godot-copilot (minosvasilias)** — in-editor Godot 4.x AI completion using OpenAI APIs. [GitHub](https://github.com/minosvasilias/godot-copilot)

### 7. Practical render-in-the-loop & differentiable-rendering substrates
- **Mitsuba 3** — Python-bound, JIT-compiled, differentiable physically-based renderer (Dr.Jit). Standard for inverse-rendering loss back-propagation. Compatible with PyTorch.
- **nvdiffrast (NVlabs/nvdiffrast)** — modular high-performance differentiable rasterization primitives. [arxiv](https://arxiv.org/pdf/2011.03277) The standard for fast diff-rasterization gradients to material/shader parameters.
- **Slang.D / Dr.Jit** — newer differentiable-shading layers; Slang.D is a shading-language-level autodiff system from NVIDIA.
- **DiffMat (mit-gfx/diffmat)** — PyTorch reproduction of Substance Designer compositing graphs with autodiff; [GitHub](https://github.com/Owlety/diffmat_ext) [Pythondig](https://pythondig.com/r/pytorchbased-differentiable-material-graph-library-for-procedural-material-capture) perfect critic for material-graph generators.
- **Stochastic Gradient Estimation (Vorba et al., arXiv 2404.09758)** — turns any non-differentiable rasterizer (e.g., Godot/three.js engine itself) into a finite-diff differentiable one. [arxiv](https://arxiv.org/pdf/2404.09758) Useful when you can't or won't replace the runtime renderer.
- **Standard render-loop pattern**: prompt → LLM emits GLSL → compile in headless `wgpu-shadertoy` / `puppeteer + WebGL` / Mitsuba 3 → screenshot → CLIP/LPIPS/`shadermatch` similarity to reference → critique → re-prompt. The Vipitis/shadermatch metric is the closest to a turnkey component.

### 8. Specific to spell/VFX (animated time-based shaders)
- **No dedicated AI VFX-shader model** with weights exists today. The practical recipes the user can stand up:
  1. **Curated handcrafted spell-shader corpus (RAG)** + Claude/GPT-4/Gemini, prompted for `mainImage` Shadertoy-format output. The ShaderToy-MCP server is a ready-built version.
  2. **AI Co-Artist's evolutionary loop** adapted: keep a population of spell shader variants, mutate via "more chaotic," "add bloom," "shift to ice palette" prompts; user-in-the-loop selection.
  3. **Erfani-style RAG → Shader Graph JSON** approach, ported to Godot's VisualShader JSON format. Particle/spawn effect prompts ("swarm of fireflies", "colorful tornados") were the strongest case studies in the original.
  4. **Pixelcut / Pixa / Reelmind text-to-VFX** — commercial AI image/video VFX generators (sparkles, fire, magic). Output static PNGs / short MP4s [Pixa](https://www.pixa.com/create/particle-effect-generator) — usable as flipbook textures or particle sprite atlases inside Godot's GPUParticles, not as shaders. Useful for asset generation but not for shader code.
  5. **For dissolve, hologram, force field, lightning, fire/water** — the Shadertoy corpus already contains hundreds of canonical examples; an LLM with RAG over `shaders21k` reliably remixes them. The hard part is API hygiene (uniforms, dispose, ShaderMaterial setup) — for which Mejba's "AI Shader Skill" pattern is the best documented mitigation.
- **Niagara/VFX Graph automation**: there is no public AI auto-author for Niagara. For Unity VFX Graph, only the Erfani prototype exists. For Godot, the closest is **Hi-Godot/Godot-AI MCP**'s preset library (fire, sparks, magic, lightning, explosion).

---

## Details (capability matrix, condensed)

| Tool | What it outputs | GLSL/Godot/three.js fit | Runnable today | Maturity |
|------|-----------------|------------------------|----------------|----------|
| VLMaterial | Blender Python procedural-material program | Indirect (bake → maps) | Yes; weights public | Research, ICLR'25 Spotlight |
| MultiMat | Substance graph (multimodal) | Indirect (Substance → maps) | Paper; data partially public | Research (Sept 2025) |
| MatFormer / Conditional MatFormer | Substance graph | Indirect | Code; weights limited | Research |
| ProcMatRL | RL-fine-tuned Substance graphs | Indirect | Code public; demo weights only | Research |
| BlenderAlchemy | Blender Python edits | Indirect | Code public | Research, ECCV'24 |
| MatFuse | SVBRDF maps (LDM) | Direct ✓ | Yes; CVPR'24 code | Research, runnable |
| StableMaterials | PBR maps (LDM + LCM 4-step) | Direct ✓ | HF weights | Production-ready |
| MaterialPalette | PBR maps from photo | Direct ✓ | Yes; CVPR'24 code | Runnable |
| ControlMat | SVBRDF | Direct ✓ | Closed | Adobe paper |
| Chord / Generative Base Material | PBR maps from text/sketch | Direct ✓ | Open prototype (MatSynth weights) | Research, SIGGRAPH Asia '25 |
| MaterialMVP | Multi-view PBR for meshes | Direct ✓ | Hunyuan3D ecosystem | Research |
| DreamMat | Mesh PBR (no baked light) | Direct ✓ | Code public | Research, TOG'24 |
| Hunyuan3D 2.1 | Image→3D mesh+PBR | Direct ✓ | Open-source weights | Production-grade |
| Polycam / withPoly | Tileable PBR maps from text | Direct ✓ | Free + paid | Production |
| MatSynth | 4K PBR dataset | Training data | HF dataset | CC0 |
| ShaderToy-MCP | Shadertoy GLSL via Claude | Direct ✓ (port iTime/iResolution) | Yes | Hobbyist |
| AI Co-Artist | Animated GLSL fragment shaders | Direct ✓ | Prototype HTML+OpenAI key | Research, Nov '25 |
| llm-shader-toy / sabrina.dev | GLSL in browser | Direct ✓ | Yes | Hobbyist |
| AI Shader Studio (Kandah) | Three.js+GLSL via Gemini | Direct ✓ | Demo + blog | Hobbyist |
| Erfani Generative AI for Shader Graph | Unity Shader Graph JSON via GPT-4/Gemini + RAG | Indirect (Unity-only) | Blog/research only | Research |
| AI Shader Generator (aishader.com) | Unity Shader Graph | Indirect | Commercial | Commercial |
| Sasso interactive evolutionary IEC | Unity Shader Graph variants | Indirect | Code | Research |
| Material Maker | Procedural Godot/Unity/Unreal materials | Direct ✓ (Godot native) | Open-source | Production |
| Infinigen | Procedural Blender environments + 50 mat-gens | Indirect (export) | Open-source | Production |
| DiffMat | Differentiable Substance graphs | Critic substrate | Open-source | Research |
| nvdiffrast / Mitsuba 3 / Slang.D | Differentiable rendering substrates | Loop infrastructure | Open-source | Production |
| Vipitis/shaders21k + shadermatch | Dataset + similarity metric | Eval/RAG corpus | HF datasets + harness | Public |
| Diffusion as Shader (DaS) | 3D-controlled video | Reference-only | Code + weights public | Research |

### Recommended starter stack for spell/VFX on GLSL/WebGL/Godot/three.js
1. **Procedural surface materials (rocks, runes, magical metals)**: StableMaterials (HF) → albedo/normal/roughness/metallic → drop into Godot StandardMaterial3D / three.js MeshStandardMaterial. Polycam as a UI alternative if speed matters.
2. **Photo→PBR for one-off references**: MaterialPalette.
3. **Procedural noise libraries / terrain seed**: Infinigen + Material Maker.
4. **Animated spell shaders (the core pain-point)**: Build a Claude/Gemini agent with:
   - System prompt enforcing Shadertoy `mainImage`/`fragColor` format, plus your project's Godot/three.js uniform conventions.
   - **RAG over shaders21k + your handcrafted spell library**, indexed with CLIP-image embeddings of rendered frames so prompts like "lightning chain" retrieve visually-similar exemplars.
   - **Render-in-the-loop critic**: headless `wgpu-shadertoy` (or three.js + Puppeteer) compiles each candidate, captures frames, [Medium](https://medium.com/@tiagomoraismorgado/conceptual-overview-of-recursive-and-cyclic-llm-use-for-code-iteration-65e74007257e) runs `shadermatch`/CLIP/LPIPS against a reference (image you sketch or a Veo/Sora video frame). Re-prompt on failure.
   - **Evolutionary layer**: AI Co-Artist's mutation/crossover prompts to sustain creative variety.
5. **Higher-level Godot authoring**: Hi-Godot/Godot-AI MCP for one-call particle/material presets driven by the same agent.
6. **For Substance-style procedural material graphs you want to bake but not author**: VLMaterial inference (image → Blender Python → bake to maps) or (when public) MultiMat. ProcMatRL if you want RL-tuned MatFormer with image targets.
7. **Differentiable refinement**: For surface materials only, DiffMat allows gradient-descent fitting of an authored Substance graph to a reference image. For SDF spell geometry, DIST or Mitsuba 3 sphere-tracing gradients.

---

## Caveats
- The "VLMaterial" hits in newer 2026 search returns include an unrelated camera-radar fusion paper (arXiv 2604.11671) — same name, different authors, completely different domain (mmWave material identification). Don't confuse it with the MIT graphics paper.
- "Diffusion as Shader" (DaS) is named misleadingly: it controls video diffusion via 3D tracking, [Hugging Face](https://huggingface.co/papers/2501.03847) it is not a shader-code generator. Use it to *describe* the look you want, not produce GLSL.
- Most of the procedural-material program-synthesis stack (VLMaterial, MultiMat, MatFormer, ProcMatRL, BlenderAlchemy) targets Substance/Blender. To reach Godot/three.js GLSL natively you must bake to PBR maps, or write a node-graph-to-GLSL transpiler (Material Maker already does GLSL→HLSL, and there is precedent in MaterialX→GLSL via Substance's plugin).
- **Trustworthiness of LLM-generated WebGL**: practitioners (Mejba, Erfani) consistently report that even frontier LLMs miss WebGL plumbing details — uniform binding, ResizeObserver, `dispose()` — more than they miss the GLSL math. Plan for a non-trivial harness around the model. [Engr Mejba Ahmed](https://www.mejba.me/blog/ai-shader-effects-claude-code)
- Several quoted user-study numbers (AI Co-Artist's 4.2 vs 0.6 shaders, ~60% time reduction, 4.7/5 satisfaction; [arXiv](https://arxiv.org/html/2512.08951) Erfani's 5.2/10 abstract-prompt similarity) are from small studies in research preprints, not independent replication. Treat as directional evidence.
- "Hunyuan3D 2.5" features (4K textures, multi-view PBR, bump) are real but the model is **not yet open-sourced**; only 2.1 weights are public as of mid-2025. The 2.5 issue tracker (Tencent-Hunyuan/Hunyuan3D-2.1#111) explicitly asks about open-source plans. [GitHub](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/issues/111)
- Reelmind, Pixelcut, Pixa "particle effect generators" are image/video tools, not shader-code generators. They produce PNG/MP4 assets — useful for sprite-flipbook particles, not for live GLSL.
- The Vipitis `shadermatch` metric is the most established eval signal for LLM-generated GLSL today, but it scores function-completion accuracy and perceptual similarity, not gameplay fitness. You will still want human selection in the spell-VFX loop.
- Adobe-trained datasets (MatFormer, conditional MatFormer, internal ProcMatRL weights) are not redistributable; only DiffMat-public-material variants are released. Plan around licensing if you intend to ship commercial output.
- The "frontier" is moving very fast: between Sept 2025 (MultiMat v1) and Feb 2026 (MultiMat v2) the field added new 3D PBR work (MatPedia), Hunyuan3D 2.5, and AI Co-Artist. Re-check arXiv categories cs.GR / cs.CV every 1–2 months.
- I have not exhaustively confirmed weight availability for every paper above; before committing to one, verify the GitHub repo and Hugging Face Hub directly. Specifically, MultiMat code/weights status is unclear from public-facing pages as of this search; Chord weights are described as "open-source prototype" tied to MatSynth — may require retraining.