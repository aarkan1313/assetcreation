# Research Response — UI / Icons Pipeline (2026 SOTA)

**Date:** 2026-05-07
**Hardware target:** RTX 5090 Laptop, 24 GB VRAM, Blackwell sm_120, CUDA 12.8+, torch >=2.7
**Source brief:** `07_ui_icons.md`

---

## TL;DR — what to actually do

1. **Two version bumps unblock the entire cloud lane.** `recraft_icons.py` should target **Recraft V4 / V4 Pro Vector** (Feb 2026 rebuild with explicit icon-grid logic + native SVG output), and `local_diffusion_icons.py` should swap **FLUX-schnell → FLUX.2 Klein 4B** (Apache 2.0, ~13 GB, commercial-safe on the 5090). Both are direct successors, not laterals.
2. **The faction-LoRA scaffold (`ui/lora/v1_smoke/`) is the single biggest unlock.** Use **AI-Toolkit by Ostris** as the trainer (community default in 2026, has documented Blackwell/PyTorch 2.9.1 install path). 15–25 hand-curated images per faction, ~30–60 min train per faction on the 5090. Apply at inference via **rgthree's Power LoRA Loader** in ComfyUI — one workflow, faction selector, hot-swap. This converts the "color swap" criticism into actual motif/material/lighting differentiation.
3. **There is NO 2026 AI tool that generates production game HUDs end-to-end.** Galileo AI / Uizard / v0.dev / NightCafe all produce static screenshots that don't respect 9-slice geometry, don't reuse your atlas, and don't round-trip into Godot. The viable answer is **AI for the *materials* (frame metal, banner cloth, parchment plate) per faction, then PIL-composite as you do today.** This keeps your 16-19 KB HUD outputs but makes them feel genuinely different.
4. **For the hero-icon pass (~30 icons):** Recraft V4 Pro Vector at $0.30/SVG (~$9 total) for vector-clean icons, or gpt-image-1.5 high-quality at $0.133/image (~$4 total) for painterly hero icons where vector isn't required. The 2026 indie consensus is **AI generation + human polish in Affinity/Illustrator**, not commission and not pure-AI.
5. **Style-unification pass for the 135 mixed-source library: a ComfyUI graph (FLUX.2 Redux multi-reference + Canny ControlNet + img2img).** No dedicated "icon-set unifier" exists in 2026 — this is the canonical workflow. Use **Canny** (silhouette-preserving), not Reference-only (largely deprecated for FLUX).
6. **Smaller tooling stays put.** vtracer + resvg is still the right SVG roundtrip; custom PIL atlas packing is fine; no AI 9-slice auto-detection tool worth ingesting; biggest new free-license library to add is **Tabler Icons (6128 icons, MIT)** — biggest *quantity* win for generic inventory glyphs. No new fantasy-specific CC0/MIT library at game-icons.net's scale has launched since 2024.

The biggest behavioural shift this brief should drive: **stop calling the cloud lane "plumbed" and start running it.** The whole plumbing chain is ~$15 of cloud spend + one weekend of LoRA training to demonstrate that the faction system *can* produce visually-distinct output.

---

## Q1 — 2026 SOTA for Game Icon Generation

### Recommendations

1. **Recraft V4 / V4 Pro Vector (cloud, raster + native SVG).** V4 shipped February 2026 as a "ground-up rebuild" with explicit icon-set affordances: 24/16-px grid logic, consistent stroke widths, and a documented prompt-structure recipe for keeping a set coherent. **It is still the only flagship that emits real editable SVG paths from a prompt** — neither FLUX.2, gpt-image-1.5, nor Nano Banana Pro produce vector output. ([Recraft pricing](https://www.recraft.ai/docs/api-reference/pricing), [MindStudio V4 walk-through](https://www.mindstudio.ai/blog/what-is-recraft-v4-vector-generate-svg-logos-icons-ai), [Z.Tools V4 review](https://z.tools/blog/recraft-v4-vector-image))

2. **FLUX.2 [klein] 4B (open-weights raster, ComfyUI).** Released 2025-11-25, klein family on 2026-01-15. Klein 4B is **Apache 2.0** and fits ~13 GB — the right answer for any pipeline that wants commercial-safe local generation on a 5090 Laptop. FLUX.2's multi-reference editing is the actual "set-style consistency" mechanism for raster icons. FLUX.2 [dev] is non-commercial-license only, so use Klein 4B for shipped assets. ([BFL FLUX.2 Klein 4B card](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B), [NVIDIA RTX FLUX.2 announcement](https://blogs.nvidia.com/blog/rtx-ai-garage-flux-2-comfyui/), [Apatero Klein license guide](https://www.apatero.com/blog/flux-2-klein-apache-license-commercial-use))

3. **gpt-image-1.5 / Nano Banana Pro as character/illustration backstops.** Independent rankings put gpt-image-1.5 first for game character art and Nano Banana Pro first for "object detail" ([VibeDex 2026 ranking](https://vibedex.ai/blog/best-ai-image-generator-concept-art-2026)), but neither is icon-grid-aware and neither outputs SVG — they're better as a hero-icon painter than a set generator.

### Hardware fit

- Recraft V4 / gpt-image-1.5 / Nano Banana Pro: cloud, no local concerns.
- FLUX.2 Klein 4B: native ComfyUI on RTX 5090 with [day-0 ComfyUI support](https://blog.comfy.org/p/flux2-state-of-the-art-visual-intelligence). Watch the Blackwell sm_120 trap: PyTorch nightly cu128/cu130 is required, no xformers ([Comfy Blackwell discussion #6643](https://github.com/comfyanonymous/ComfyUI/discussions/6643), [discussion #6980](https://github.com/Comfy-Org/ComfyUI/discussions/6980)).

### License + cost

- Recraft V4 raster: $0.04/image, V4 Vector $0.08, V4 Pro Vector $0.30. Commercial rights included on paid plans/API.
- FLUX.2 Klein 4B: Apache 2.0 (commercial OK).
- FLUX.2 [dev]: BFL non-commercial license.
- gpt-image-1.5: $0.133/image at 1024² high-quality ([AI Free API pricing breakdown](https://www.aifreeapi.com/en/posts/gpt-image-1-5-pricing)).

### Maturity

- Recraft V4: GA since Feb 2026, well-documented API, used in production by design tools.
- FLUX.2 Klein 4B: shipped Jan 2026, ComfyUI native day-0; LoRA ecosystem still younger than FLUX.1.
- Civitai's RPG-icon LoRA scene is alive but mostly SDXL/Illustrious base — closest 2026 entry is the long-running ["Handpainted RPG Icons Style LoRA"](https://civitai.com/models/6876/handpainted-rpg-icons-style-lora) plus newer fantasy-RPG LoRAs like [Fantasy RPG v1 (Jan 2026)](https://civitai.com/models/2345652/fantasy-rpg). No purpose-built "FLUX.2 game-icon" LoRA has emerged as canonical yet.

### Honest comparison

**Recraft V3 → V4 is a real upgrade for icons** (better grid behaviour, V4 Pro Vector for finer paths), not lateral. **FLUX-schnell → FLUX.2 Klein 4B is a clear upgrade** and fixes the commercial-license problem your existing schnell setup already had. FLUX.2 does **not** dethrone Recraft for inventory/spell icons specifically because of the SVG gap and weaker grid conventions — treat them as complements (Recraft for the icon, FLUX.2 for hero-painted variants).

---

## Q2 — Faction-Style LoRA Training in 2026

### Recommendations

1. **AI-Toolkit by Ostris (primary).** The community has converged on this as the default FLUX LoRA trainer in 2026. Ships with a web UI for job management, sane defaults tuned for style/character LoRAs, YAML configs, ~20–30% faster than SimpleTuner on equivalent settings. Critically, has a documented Blackwell/RTX 5090 install path using PyTorch 2.9.1 + CUDA 12.8 — matches your environment exactly. ([github.com/ostris/ai-toolkit](https://github.com/ostris/ai-toolkit), [apatero flux-2 guide](https://apatero.com/blog/flux-2-lora-training-complete-guide-2025), [neurocanvas ai-toolkit guide](https://neurocanvas.net/blog/ai-toolkit-guide/))

2. **FluxGym (cocktailpeanut).** Gradio wrapper around Kohya sd-scripts, dead-simple, low-VRAM defaults. Fallback if AI-Toolkit's Blackwell install fights you. ([github.com/cocktailpeanut/fluxgym](https://github.com/cocktailpeanut/fluxgym))

3. **Kohya sd-scripts (v0.9.1+).** Still "gold standard" for deep configurability, more friction than AI-Toolkit, less sensible defaults for small style sets. Only if you outgrow AI-Toolkit's presets. ([sanj.dev LoRA 2025 guide](https://sanj.dev/post/lora-training-2025-ultimate-guide))

### Dataset size for style LoRAs

Your 10-30 hand-curated images per faction is squarely in the recommended range. Multiple 2025-2026 sources converge: **20-30 images is sufficient for a focused FLUX style LoRA**, and "ten sharp varied images beat fifty similar ones." Character LoRAs run smaller (15-20); broad conceptual styles want 100-200. For a "faction look = palette + motif" target, **15-25 per faction with diverse subject matter rendered in that style is the sweet spot.** ([Civitai dataset prep](https://civitai.com/articles/7777/detailed-flux-training-guide-dataset-preparation), [fal.ai style LoRA blog](https://blog.fal.ai/training-flux-style-lora-on-fal-ai/), [segmind guide](https://blog.segmind.com/easy-flux-lora-training-guide/))

### Training time on RTX 5090 Laptop (24 GB)

Direct LoRA-training benchmarks on Blackwell are still thin, but inference benchmarks set the floor: 5090 generates 1024² FLUX.1-dev FP16 in ~7-9s vs ~10s on 4090, FP4 native cuts to ~6s. By rough proportionality with published 4090 LoRA times, **expect ~30-60 minutes per faction** for a 20-image dataset at 512-1024 res, rank 16-32, ~2000 steps. 24 GB is comfortable for FLUX.1-dev LoRA at 1024; FLUX.2 (9B Klein) tighter and likely needs FP8/FP4 quant or 768 res. ([runpod 5090 review](https://www.runpod.io/articles/guides/nvidia-rtx-5090), [tensorrigs FLUX VRAM guide](https://tensorrigs.com/blog/flux-vram-guide/))

### Multi-LoRA inference / runtime

The de facto pattern is **rgthree's Power LoRA Loader** in ComfyUI: single node holds N LoRAs each with its own strength slider and on/off toggle, hot-swappable without rewiring. For your 4-faction setup, **one workflow + Power LoRA Loader + faction selector beats four parallel workflows.** ([rgthree-comfy](https://github.com/rgthree/rgthree-comfy), [Power LoRA Loader docs](https://www.runcomfy.com/comfyui-nodes/rgthree-comfy/Power-Lora-Loader--rgthree-))

### Base model choice

- **FLUX.1-dev/schnell**: still the default May 2026. Largest LoRA ecosystem, most ControlNets, deepest documentation. Schnell is fast; LoRAs trained against dev have mostly-acceptable cross-compatibility with schnell.
- **FLUX.2 [dev] / [klein 4B/9B]**: Q1 2026, first-class LoRA support, klein 4B can stack 3 LoRAs at inference, higher quality ceiling than FLUX.1. Younger ecosystem; 9B strains 24 GB. ([fal FLUX.2 dev LoRA](https://fal.ai/models/fal-ai/flux-2/lora), [Kevin Gabeci FLUX.2 guide](https://kgabeci.medium.com/flux-2-lora-training-the-complete-2026-guide-from-someone-who-built-the-training-platform-14d0bcb396eb))
- **SDXL**: still relevant for icon-scale work specifically because it's small, fast, deepest LoRA back-catalog. For 256-512 px icons it's arguably overkill to go FLUX.
- **HiDream-I1 / Lumina2 / OmniGen2**: all support LoRA via SimpleTuner/AI-Toolkit but far smaller LoRA communities than FLUX. Not worth the migration tax.

### License + cost

- AI-Toolkit / FluxGym / rgthree-comfy: free (MIT / open).
- FLUX.1-schnell: Apache-2.0 (commercial OK).
- FLUX.1-dev: BFL non-commercial.
- FLUX.2 Klein 4B: Apache-2.0 (commercial OK) — best base for shipped LoRAs.

### Honest comparison

Current state is "color swap on procedurally-composed PNG." A trained style LoRA gets you **generated motifs, lighting, weathering, and material treatment** that no PIL palette swap can produce. **This is not overhyped — it's the single largest quality jump available for the icon pipeline.** Caveat: LoRA quality is dataset-bound; a rushed 20-image set produces a rushed LoRA. The faction differentiation problem becomes a *curation* problem, which is the correct place for it to land.

**Recommended sequence:** train one faction (`v1_smoke` already has scaffold) → confirm end-to-end loop → train remaining three → swap `local_diffusion_icons.py` to FLUX.2 Klein 4B base → wire Power LoRA Loader workflow.

---

## Q3 — HUD Composition / Mockup Tools

### Honest top-line answer

**There is no general-purpose AI tool in May 2026 that generates production-quality game HUDs from a faction palette + icon set + 9-slice frames.** The marketing pages — NightCafe "Game UI Mockup Generator", Visualizee, Filmora's Nano Banana writeups — produce pretty static screenshots that are not editable layouts, do not respect 9-slice geometry, do not reuse your icons, and don't round-trip into Godot/Unity. ([visualizee game UI](https://visualizee.ai/blog/game-ui-design-ai-generator), [NightCafe game UI mockup](https://creator.nightcafe.studio/tools/game-ui-mockup-generator), [Filmora Nano Banana 30 examples](https://filmora.wondershare.com/ai-prompt/game-ui-ai.html))

The web-UI tools are wrong tool entirely: **Galileo AI** (now Google Stitch) outputs Figma files; **Uizard** targets wireframes; **v0.dev** outputs React. None understand game HUD conventions (radial menus, ammo counters, minimaps, 9-slice frames, ability cooldowns). ([banani.co Galileo review](https://www.banani.co/blog/galileo-ai-features-and-alternatives), [Figma AI UI generator](https://www.figma.com/solutions/ai-ui-generator/))

### Two practical 2026 routes

1. **Route A — ComfyUI img2img with IPAdapter + ControlNet.** Build a wireframe layout in PIL (you already do this), then run through a FLUX/SDXL workflow conditioned on: (1) Canny/MLSD ControlNet from your wireframe to lock geometry, (2) IPAdapter pointing at a faction reference plate for theme/material, (3) the faction LoRA from Q2 for motifs. This is the closest 2026 equivalent to a "hero HUD generator." Shakker-Labs FLUX.1-dev-ControlNet-Union-Pro-2.0 supports canny + soft-edge + depth + pose + gray in one model. ([Shakker-Labs Union Pro 2.0](https://huggingface.co/Shakker-Labs/FLUX.1-dev-ControlNet-Union-Pro-2.0), [comfy.org style-transfer handbook](https://blog.comfy.org/p/the-complete-style-transfer-handbook), [comflowy IPAdapter guide](https://comflowy.com/blog/IPAdapter-Plus))

2. **Route B — Keep procedural PIL, layer AI-generated *parts* on top.** Use AI to generate the **texture plates** (frame metal, banner cloth, scroll parchment) per faction once, then PIL-composite as you do today. This preserves pixel-exact 9-slice geometry, keeps file sizes tiny (your 16-19 KB HUDs stay 16-19 KB), and the "feels different per faction" comes from the textures, not the layout. **This is probably the right answer for your pipeline.**

### ComfyUI game-specific node packs

Only one notable package exists: **mattwilliamson/comfyui-ai-gamedev**, but it focuses on Hunyuan 3D 2.1 asset generation and Ollama prompt extension — not HUDs. **No ComfyUI node pack for game HUD composition exists as of May 2026.** ([mattwilliamson/comfyui-ai-gamedev](https://github.com/mattwilliamson/comfyui-ai-gamedev))

### Hardware fit

Route A: native to your stack — ComfyUI on Windows, RTX 5090, FLUX.1-dev + Union Pro ControlNet (~6 GB) + IPAdapter (~1 GB) + faction LoRA (~150 MB) all fit comfortably in 24 GB. Route B: pure CPU/PIL — already in your pipeline.

### License + cost

- ComfyUI / rgthree / AI-Toolkit: free.
- FLUX.1-dev: non-commercial; schnell Apache-2.0.
- Shakker-Labs ControlNet: FLUX-derived, non-commercial.
- All routes are zero-cloud-cost; only license risk is FLUX.1-dev for commercial release.

### Maturity

- rgthree Power LoRA Loader: production-mature.
- AI-Toolkit: actively developed, weekly commits, has Blackwell support.
- FLUX ControlNet Union Pro 2.0: 2025, stable.
- "AI HUD generator" category: **immature / non-existent for games specifically.**

### Honest comparison

For **per-faction texture plates fed back into PIL composites**: clear win, ~1 day of setup beats hand-painting four faction skins. For **end-to-end "AI generates the HUD"**: overhyped. The output won't be production-usable, won't be 16-19 KB, won't reuse your atlas, and won't round-trip into Godot. **The shipping-pipeline answer is genuinely still "designer + procedural compositor", with AI generating the *materials* not the *layout*.**

---

## Q4 — 9-slice + Atlas Tooling in 2026

### Recommendations

1. **Godot's built-in "Texture Atlas" import (4.x, including 4.4)** — Godot has had a Texture Atlas import type since 3.2 and persists in 4.4 with `AtlasTexture`. It's a *consumer* of atlases (region-of-larger-texture) plus a basic packer at import time, not a sophisticated rect packer. For a 103-icon CC-BY/MIT pipeline where you want deterministic JSON output for non-Godot consumers, **custom PIL packing is still the right call.** ([Godot docs](https://docs.godotengine.org/en/4.4/classes/class_atlastexture.html), [Godot atlas article](https://godotengine.org/article/atlas-support-returns-godot-3-2/))

2. **free-tex-packer** — open-source, MIT, exports Godot/Phaser/Pixi/Cocos2d JSON, runs as Electron app or CLI on Windows. Solid lateral if you want to drop the maintenance of `pack_atlas.py`. ([free-tex-packer.com](https://free-tex-packer.com/), [GitHub odrick/free-tex-packer](https://github.com/odrick/free-tex-packer))

3. **TexturePacker (CodeAndWeb)** — commercial (~$40 one-time), best polygon packing + Godot importer plugin. Overkill for 103 icons. ([CodeAndWeb plugin](https://github.com/CodeAndWeb/texturepacker-godot-plugin))

4. **msdf-atlas-gen** — only relevant if you start shipping **MSDF font/icon atlases** (sharp at any scale). Not a replacement for sprite-icon atlasing. ([atlasify reference](https://github.com/soimy/atlasify))

### 9-slice auto-detection

**No mature 2025-2026 ML tool exists.** Searches surface 9-slice *rendering* support requests (e.g. [grida #430](https://github.com/gridaco/grida/issues/430)) and unrelated SAHI "slicing-aided inference" for object detection ([Ultralytics](https://docs.ultralytics.com/guides/sahi-tiled-inference/)). **Verdict: keep a heuristic** (longest constant-color run on each axis of alpha+RGB delta) — no tool to ingest.

### Honest comparison

**Lateral.** Custom PIL packer is fine; replace only if you want the JSON-format zoo free-tex-packer gives you for free.

---

## Q5 — SVG ↔ PNG / Vector Tracing in 2026

### PNG → SVG

1. **vtracer (visioncortex)** — last release **v0.6.4 on 2024-04-20**; effectively in maintenance mode but stable, fast, Rust-native, deterministic. Still excellent for flat icons. ([GitHub](https://github.com/visioncortex/vtracer))

2. **StarVector (CVPR 2025)** — vision-language foundation model that emits SVG **code** from a raster. 1B and 8B checkpoints on HF, **Apache 2.0**, explicitly tuned for **icons and logotypes**. On a 5090 Laptop the 1B is feasible; 8B is tight. **This is the one genuine SOTA leap since vtracer.** ([starvector.github.io](https://starvector.github.io/starvector/), [GitHub joanrod/star-vector](https://github.com/joanrod/star-vector), [HF 1B](https://huggingface.co/starvector/starvector-1b-im2svg), [HF 8B](https://huggingface.co/starvector/starvector-8b-im2svg))

3. **Recraft Vectorize API / Vectorizer.AI** — closed-source, paid per-call. Cleaner paths than vtracer on noisy inputs, but for 256² flat fantasy icons the quality delta is small and you give up offline determinism. ([Recraft Vectorize on Replicate](https://replicate.com/recraft-ai/recraft-vectorize))

### SVG → PNG

**resvg is still SOTA** and very actively maintained: now under the **linebender** org (alongside tiny-skia/usvg), latest release **v0.47.0 on 2026-02-10**. ~13× faster than librsvg with better spec coverage. cairosvg is fine for trivial cases but lags on filters/gradients. ([GitHub linebender/resvg](https://github.com/linebender/resvg))

### Honest comparison

**For your 256×256 flat fantasy icons: vtracer + resvg is still the right roundtrip** — fast, offline, deterministic, no GPU needed. **StarVector-1B is worth a side experiment** if you ever need to vectorize *AI-generated* icons that vtracer mangles, but it's not a drop-in replacement for a 103-asset pipeline.

---

## Q6 — Hero-Icon Pass Workflow (~30 icons)

### Recommendations

1. **Recraft V4 Pro Vector + manual touch-up in Affinity/Illustrator.** $0.30 × 30 hero icons = ~$9 of API spend; the SVG path output makes manual cleanup tractable instead of repaint-from-scratch. Dominant 2026 design-tool round-up recommendation: "for logos, icons, and SVG vectors, Recraft is the only serious option" ([flux-ai.io Recraft review](https://flux-ai.io/blog/detail/Recraft-AI-Review-Best-for-Brand-Graphics-Vectors-and-Design-Ready-Images-e2438154341c/), [Ropewalk 2026 designer-tools guide](https://ropewalk.ai/blog/best-ai-tools-graphic-designers-2026)).

2. **gpt-image-1.5 high-quality tier** for painterly hero icons where vector isn't required. $0.133/image at 1024² → ~$4 for 30 icons ([AI Free API pricing breakdown](https://www.aifreeapi.com/en/posts/gpt-image-1-5-pricing)). Currently leads LM Arena at Elo 1264 ([llm-stats](https://llm-stats.com/models/gpt-image-1.5)); best-in-class instruction-following for "polish this exact icon to AAA quality" prompts.

3. **Local FLUX.2 [dev] (32B FP8) + LoRA** when you need 100+ hero passes, deterministic seeds, or commercially-safe but hand-tuned style. FP8 fits a 24 GB 5090 Laptop ([WillItRunAI VRAM guide](https://willitrunai.com/blog/image-generation-vram-guide-2026)). FLUX.2 [dev] license is non-commercial — use Klein 4B base for fine-tuning if you ship commercially.

### Cost vs commission reality check

Freelance icon commission runs $50–200/hr. AI exploration is "$5–20 for 100–500 generations" ([Apatero AI-art-for-game-devs](https://apatero.com/blog/ai-art-game-developers-complete-guide-2025), [aloa.co game-dev tools](https://aloa.co/ai/comparisons/ai-image-comparison/top-ai-art-tools-game-developers)). **2026 indie consensus is AI generation + human polish, not commission and not pure-AI.** The 5%-hero / 95%-bulk split is explicit.

### Hardware fit

Recraft and gpt-image-1.5 are cloud — zero local risk. FLUX.2 Klein 4B in ComfyUI is the easiest local path on a 5090 Laptop with day-0 ComfyUI support ([Comfy blog](https://blog.comfy.org/p/flux2-state-of-the-art-visual-intelligence)). Watch the sm_120 trap.

### Maturity

Recraft V4 GA Feb 2026; gpt-image-1.5 GA early 2026; FLUX.2 GA Q1 2026 — all production-grade.

### Honest comparison

**Cloud diffusion (Recraft V4 Pro Vector for vector, gpt-image-1.5 for painterly) beats commission for indie-scope hero passes by 100×+ in cost and 10×+ in iteration speed.** It does *not* beat a senior icon artist for top-of-the-line polish. For your project state ("good placeholders, would need much better work to ship"), the right move is **run the 6 prompted cloud icons in `prompts.json` first** — ~$2 spend — and judge the output against the procedural baseline before scaling to 30.

---

## Q7 — Style-Unification Across Mixed-Source Library

### Recommendations

1. **FLUX.2 [dev] + Redux multi-reference + Canny ControlNet img2img**, in a ComfyUI graph. **Canonical 2026 stack for "stylise a batch to match one reference":** Redux supplies up to 3 reference images for style at low strength, Canny preserves silhouette/composition, low-strength img2img blends. Workflows by odam_ai and others on OpenArt are de-facto templates ([OpenArt: 100% Flux Native ControlNet + IPAdapter Style Transfer](https://openart.ai/workflows/odam_ai/100-flux-native-controlnet-ipadapter-style-transfer/u55OSJqYClitcKGAqQ8B), [Flux Tools Redux + ControlNet beginner workflow](https://openart.ai/workflows/odam_ai/flux---style-transfer-controlnet-flux-tools-redux---beginner-friendly/LWMhfWmaku6tdDWjkM8D), [MyAIForce Flux Tools](https://myaiforce.com/flux-tools-workflow/)).

2. **InstantX / Shakker-Labs FLUX IP-Adapter** when Redux isn't precise enough. The InstantX FLUX.1-dev IP-Adapter (open-sourced 2024-11-22) plus Shakker's ComfyUI nodes is the closest analogue to the SDXL IP-Adapter people remember. For mixed-source icons (lucide line + procedural + CC-BY painted), use **Style-only weight type** plus Canny ControlNet at ~0.6–0.8 strength to keep the lucide silhouettes intact ([InstantX release notes](https://comfyui-wiki.com/en/news/2024-11-22-instantx-flux-ipadapter-release), [Shakker-Labs/ComfyUI-IPAdapter-Flux](https://github.com/Shakker-Labs/ComfyUI-IPAdapter-Flux), [comfyui.org IPAdapter style-transfer guide](https://comfyui.org/en/image-style-transfer-controlnet-ipadapter-workflow)).

3. **Recraft V4 "image-to-image with style reference"** for the lazy-but-cheap path. $0.04/raster × 135 icons = ~$5.40 to push the whole library through a single style. No vector preservation, but **lowest-effort batch unifier and respects icon conventions.**

### Hardware fit

All three viable on a 5090 Laptop / Windows / ComfyUI native; Recraft is cloud.

### Honest comparison

**There is no dedicated 2026 "icon-set unifier" tool — it remains a hand-crafted ComfyUI graph (Redux + Canny + img2img) or a cloud img2img loop.** Reference-only ControlNet is largely deprecated for FLUX; **Canny is the right ControlNet for icons** because silhouette preservation matters more than depth/pose. IP-Adapter still beats fine-tuned Img2Img alone for cross-style transfer because it factorises style from content. **A LoRA trained on your own 55 game-icons.net set + applied at low weight is the upgrade path** once you have a "house style" — feeds back into Q2.

---

## Q8 — 2026 Free-License Fantasy-Icon Libraries

### Already ingested

- **game-icons.net** — ~4180 SVGs, CC-BY 3.0, weekly additions (~180 added since 2024) ([game-icons.net](https://game-icons.net/))
- **lucide** (UI utility), **phosphor** (UI utility) — both MIT.

### Best new/expanded fantasy-leaning ingests

1. **Tabler Icons** — **6128+ icons, MIT**, large enough that the "object" subset (sword, shield, flask, scroll, dice, crown) covers many inventory placeholders. Steady 2025-2026 growth. **Biggest *quantity* win** for generic inventory glyphs. ([GitHub tabler/tabler-icons](https://github.com/tabler/tabler-icons), [tabler.io/icons](https://tabler.io/icons))

2. **Iconoir** — **~1600 icons, MIT**, hand-drawn line aesthetic that pairs well with fantasy UI chrome. Active through 2026. ([iconoir.com](https://iconoir.com/), [LICENSE](https://github.com/iconoir-icons/iconoir/blob/main/LICENSE))

3. **OpenGameArt "700+ RPG Icons" pack** — **CC0**, explicitly fantasy/RPG (potions, swords, runes, monsters). Raster originally; community SVG conversions exist. ([OGA pack](https://opengameart.org/content/700-rpg-icons), [OGA CC0 hub](https://opengameart.org/content/cc0-resources))

### Worth considering, narrower fit

- **RPG-Awesome** — CC-BY-SA 3.0 + SIL OFL, ~495 fantasy-themed glyphs (curated from game-icons.net). License compatible with your CC-BY 3.0 set. ([RPG-Awesome](https://nagoshiashumari.github.io/Rpg-Awesome/))
- **Heroicons** (MIT, ~300, Tailwind team) and **Remix Icon** (Apache 2.0, ~3000+) — UI utility only, no fantasy bias.
- **Solar Icons / Streamline Free** — Streamline's free tier is small, full library is paid (~180k commercial). Skip for an open pipeline. ([streamlinehq.com](https://www.streamlinehq.com/))
- **Flaticon "Fantasy RPG" packs** — *not* CC0/MIT; free tier requires attribution and forbids redistribution. **Do not ingest.** ([Flaticon pack](https://www.flaticon.com/packs/fantasy-rpg))

### Honest comparison

**Only genuinely new fantasy-specific addition since 2024 is incremental game-icons.net growth and the OpenGameArt CC0 RPG packs.** Tabler's 6k MIT corpus is the biggest *quantity* win for generic inventory glyphs. **No 2025-2026 fantasy-icon CC0/MIT library has launched at the scale of game-icons.net.** Recommendation: extend `freelib_ingest.py` to add Tabler + Iconoir + OGA 700+ RPG; that's the entire 2026 ingest delta.

---

## Cross-question synthesis — what I'd actually do this week

Ranked by ROI on the user's "just a color swap" / "good placeholders" verdict:

1. **Run the 6 cloud-route prompts in `prompts.json`.** ~$2 in Recraft V4 Pro Vector spend (`recraft_icons.py` against the 6 dragon-head/spell-fireball/amulet-lunar entries). One afternoon. Validates the cloud lane works end-to-end and produces 6 hero-quality references to compare against the procedural baseline. **This is the cheapest demonstration that the pipeline can ship hero-quality output.**

2. **Train one faction LoRA** (`v1_smoke` scaffold). Install AI-Toolkit, hand-curate 20 reference images for ashen_pact (concept art, faction-themed paintings, mood boards), train ~45 min on RTX 5090. Confirms the LoRA loop works end-to-end. **Even one trained LoRA invalidates the "just a color swap" verdict** if it produces visibly faction-styled output.

3. **Build the Redux+Canny ComfyUI graph for style-unification.** One workflow file. Run all 135 icons through it pointing at one reference style. This addresses the "1.3 KB ico_dagger.png next to 15 KB ico_gi_battered_axe.png" inconsistency without manual repaint.

4. **Texture-plate per faction (Q3 Route B).** Generate 4 faction-specific frame metals + banner cloths in FLUX.2, drop into existing PIL HUD compositor. Tiny code change, biggest visual delta.

5. **Ingest Tabler + Iconoir + OGA 700+ RPG into `freelib_ingest.py`.** Extend coverage by ~8000 free-license glyphs.

6. **Defer:** atlas/9-slice/vtracer changes (lateral). FLUX.2 base swap (lateral until LoRA loop works). StarVector experiments (cool but tangential). Bumping Recraft V3→V4 in code is trivial and worth doing, but the ROI is in *running* the cloud lane, not refactoring it.

The user verdict "LoRA training is the unblocking step we haven't taken" is correct — and the 2026 toolchain (AI-Toolkit on Blackwell, rgthree Power LoRA Loader, FLUX.2 Klein 4B for commercial-safe inference) makes it a weekend project, not a multi-week one.
