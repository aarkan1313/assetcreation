# Future Model Watchlist

Tracker for models / tools we've evaluated but **not installed**.
Each entry has the verdict, the install cost, the gating condition for
revisit, and where in the pipeline it would slot.

Updated when a model is evaluated. Promoted to install (and removed
from this list) when its gating condition is met.

---

## HiDream-O1-Image (released 2026-05-08)

- **Source**: https://huggingface.co/HiDream-ai/HiDream-O1-Image
- **License**: MIT
- **What it is**: 8B-param unified image generative foundation model.
  Pixel-level Unified Transformer (UiT) architecture — encodes raw
  pixels + text + task conditions in one shared token space, no
  external VAE, no separate text encoder. New architecture (not a
  diffusion model in the FLUX/SD sense).
- **What it does**: text-to-image up to 2048×2048, instruction-based
  image editing, subject-driven personalization with multi-reference
  images, long-text rendering (multilingual), complex layout control.
- **Benchmark**: #8 on Artificial Analysis Text-to-Image Arena
  (2026-05-05).

### Install cost (if we did it)

- **Disk**: 35.2 GB (8 safetensors shards, FP16). No quantized
  variant available yet.
- **VRAM**: 8B parameter model implies ~16 GB+ at inference, more
  with flash-attn.
- **Deps**: HF Transformers + safetensors + flash-attn (recommended).
  Disable flash-attn requires editing `models/pipeline.py:291`.

### Verdict — DO NOT INSTALL YET (2026-05-09)

Reasons:

1. **No ComfyUI integration**. Released 2 days ago. Community has
   wrapped HiDream-**I1** (April 2025) for ComfyUI but **not O1**
   (different architecture, can't reuse the I1 nodes). Installing
   the model means we can't actually call it from our existing
   pipeline.
2. **35 GB disk cost is steep.** D: drive was at 80%+ usage when
   evaluated; we just added 30+ GB of DEMs in the megastack pull.
3. **Marginal benefit over current stack.** For PBR tile generation
   we have FLUX.1-dev + StableMaterials + CHORD + variant_blend +
   reference-anchor (Phase A polish). For tiles specifically, the
   FLUX offset+heal trick + StableMaterials downstream is dialed.
   O1 is a generalist image model ranked #8 — not a specialist
   material generator.
4. **Quantized variant likely incoming.** HiDream-I1 had GGUF/NF4
   quantizations land within ~2 weeks of release. O1 will probably
   follow the same pattern; pulling raw FP16 now means
   re-downloading the smaller quant later.

### Revisit when

Any one of:
- ComfyUI native or community node lands for O1 (search:
  `comfyui_HiDream-O1` or `HiDream-O1` ComfyUI integration)
- GGUF / NF4 / FP8 quantized variant drops on HF (likely 10-15 GB
  vs 35 GB)
- We hit a specific failure case our current FLUX/SM/CHORD stack
  can't solve and O1's reference-image / long-text / layout-control
  features would address it

### Where it would slot in our pipeline

- **Texture lane**: NOT a primary candidate. FLUX is better suited
  to tileable PBR generation; O1's strength is composition + text
  rendering + identity-preservation across scenes — none of which
  we need for tiles.
- **UI / icon lane** (`pipelines/ui/`): potentially useful for HUD
  mockups, fantasy map icons, in-game text/scroll generation. The
  long-text rendering + layout control could matter here.
- **Concept art / hero image lane**: best fit. Fantasy region maps,
  faction emblems, character concept art, world-building reference
  imagery.
- **Fantasy biome source** (post-M5 Track A in `world3/docs/FUTURE_WORLD_SOURCES_2026_05_08.md`):
  long-text + layout could help "draw a sketch map → generate
  fantasy heightmap" workflow if we want to revisit the
  sketch-to-heightmap option.

### Notes

- Two variants in the repo: `HiDream-O1-Image` (50 steps) and
  `HiDream-O1-Image-Dev` (28 steps).
- Review ComfyUI ecosystem state when revisiting:
  - `comfyanonymous.github.io/ComfyUI_examples/hidream/`
  - `lum3on/comfyui_HiDream-Sampler` (for I1 today; may extend)

---

## How to extend this doc

Append new entries above this section. Keep the format:

- **Source**: URL
- **License**:
- **What it is**: 1-2 sentences
- **What it does**: bullets
- **Install cost**: disk / VRAM / deps
- **Verdict**: install / hold / reject + reasons
- **Revisit when**: gating conditions
- **Where it would slot**: which pipeline lane

When a model graduates to install, remove the entry and add a one-line
note here: "**INSTALLED** YYYY-MM-DD: HiDream-O1 → see
`pipelines/<lane>/...` for integration."

When a model is rejected outright, replace its entry with:
"**REJECTED** YYYY-MM-DD: <one-line reason>. Original eval at
git-blame of this file before that commit."

---

## Change log

- **2026-05-09**: Initial doc. HiDream-O1-Image entry added with hold
  verdict.
