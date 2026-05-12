# FLUX 2 Workflow & Settings Guide — 2026-05-10

Comprehensive reference for using the FLUX 2 family (klein-4B, klein-9B,
dev) in our texture-generation pipeline. Synthesizes BFL official docs,
the ComfyUI native FLUX 2 nodes, the HuggingFace Diffusers pipeline
defaults, and community findings.

**Scope**: covers prompting, samplers, CFG, steps, resolution, the
ComfyUI node graph, license terms, and texture-specific guidance. Not a
research log — this is the operational manual.

---

## TL;DR — Settings cheat sheet

| Model | Steps | CFG | Sampler | Scheduler | EmptyLatent | Resolution | Speed (1024², 5090 Laptop) |
|---|---|---|---|---|---|---|---|
| klein-4B distilled | **4** | **1.0** | euler | `Flux2Scheduler` | `EmptyFlux2LatentImage` | 1024² | ~1.2 s |
| klein-9B distilled (Q8 / NVFP4 / FP8) | **4** | **1.0** | euler | `Flux2Scheduler` | `EmptyFlux2LatentImage` | 1024² | NVFP4 ~0.8 s, FP8 ~1.5 s, Q8 ~2.0 s |
| klein-9B base (undistilled) | 20-24 | 3.5-5.0 | euler | `Flux2Scheduler` | `EmptyFlux2LatentImage` | 1024² | ~17 s |
| **dev NVFP4 32B** | **28** | **4.0** | euler | `Flux2Scheduler` | `EmptyFlux2LatentImage` | 1024² | ~4 s |
| dev base (bf16) | 50 | 4.0 | euler | `Flux2Scheduler` | `EmptyFlux2LatentImage` | 1024² | OOM on 24 GB |

**Universal**: `CLIPLoader(type="flux2")` + `qwen_3_*` text encoder +
`flux2-vae.safetensors`. All four use the **same node graph shape**; only
the loader/scheduler/CFG/steps differ.

---

## What's on disk (active lanes)

| Lane key (in `diversity_compare.py`) | File | Loader | Text encoder | Role |
|---|---|---|---|---|
| `flux2_klein` | `flux-2-klein-4b.safetensors` | UNETLoader | `qwen_3_4b.safetensors` | Baseline / 4B reference |
| `flux2_klein_9b` | `flux-2-klein-9b-Q8_0.gguf` | UnetLoaderGGUF | `qwen_3_8b_fp8mixed.safetensors` | Community Q8 reference for quant A/B |
| `flux2_klein_9b_nvfp4` | `flux-2-klein-9b-nvfp4.safetensors` | UNETLoader | `qwen_3_8b_fp8mixed.safetensors` | **Production lane on Blackwell** |
| `flux2_klein_9b_fp8` | `flux-2-klein-9b-fp8.safetensors` | UNETLoader | `qwen_3_8b_fp8mixed.safetensors` | Quality-anchor for the 9B quant A/B |
| `flux2_dev_nvfp4` | `flux2-dev-nvfp4.safetensors` | UNETLoader | `qwen_3_8b_fp8mixed.safetensors` | Hero/final-quality pass |
| `auraflow_03` | `aura_flow_0.3-Q8_0.gguf` | UnetLoaderGGUF | `auraflow_pile_t5_xl_fp16.safetensors` | Diversity lane (calmer/painterly) |
| `sd35_large` | `sd3.5_large-Q8_0.gguf` | UnetLoaderGGUF | clip_g + clip_l + t5xxl_fp8 | Experimental photoreal lane |

VAEs by lane: FLUX 2 uses `flux2-vae.safetensors`; AuraFlow uses
`auraflow_vae.safetensors`; SD 3.5 uses `sd3.5_vae.safetensors`.

---

## When to use each lane

| Use case | Recommended lane | Why |
|---|---|---|
| Fast iteration / fan-out (8-variant batches) | **klein-9b NVFP4** | <1 s/img on Blackwell; matches BF16 quality very closely |
| Production texture promotion | klein-9b NVFP4 (winner of bakeoff TBD) | Best speed/quality on our hardware |
| Hero textures / faction crests / single-best-image | **dev NVFP4** | 32B undistilled is the open quality ceiling |
| Image-to-image / heal / seam repair | klein-9b NVFP4 (denoise 0.3-0.8) | Same model + scheduler swap to BasicScheduler |
| Multi-reference editing (rare for textures) | klein-9b-kv variant (not pulled) | KV cache speeds up reference workflows by 2.5× |
| Calm / painterly / uniform organic | auraflow_03 | Diversity lane per M14 board |
| Photoreal / forest organic | sd35_large | Diversity lane (needs anti-composition prompting) |

**Don't use**: klein-4B for production once 9B variants are validated;
klein-9B Q8 GGUF after the NVFP4-vs-FP8 bakeoff settles on a winner.

---

## Prompting guide

### Core rules from BFL official docs (`docs.bfl.ml/guides/prompting_guide_flux2`)

1. **Structure**: Subject + Action + Style + Context. In that order.
2. **Word order matters** — FLUX 2 pays more attention to what comes first.
3. **Length**: 30-80 words is ideal for most prompts. 10-30 for quick
   tests, 80+ only for complex compositions.
4. **No negative prompts**. FLUX 2 ignores them. Rephrase positively:
   "no blur" → "sharp focus throughout".
5. **Natural language, not tag lists**. "A young woman with red hair
   reading a book" not "1girl, red hair, book, reading".
6. **Photorealism specifiers work**: camera models ("Shot on Fujifilm
   X-T5, 35mm f/1.4"), film stocks ("Kodak Portra 400"), eras ("80s
   vintage photo"), lighting ("harsh cinematic flash").
7. **Style names work**: "vintage Japanese woodblock print style",
   "professional studio shot".
8. **Native-language prompts** produce more culturally authentic results.

### Differences klein vs dev

- **klein responds best to short-to-medium prompts (30-50 words).**
  Distilled at 4 steps, it can't iterate through long multi-clause
  descriptions cleanly. The Diffusion Doodles author flags this:
  "F2K took several attempts to even get close ... prompt adherence
  and composition goes awry" on complex prompts.
- **dev handles longer prompts and follows them more faithfully.**
  Undistilled with CFG=4, you can push 80-150 word prompts that klein
  would ignore.
- **dev supports caption upsampling** (`caption_upsample_temperature=0.15`)
  via its Mistral text encoder. This automatically rewrites short
  prompts into more detailed versions before encoding. Not used in our
  ComfyUI workflow but available via the Diffusers Flux2Pipeline.

### Texture-specific prompting (our case)

From [`flux_seamless.py`](flux_seamless.py) and the
[DIVERSITY_COMPARE](DIVERSITY_COMPARE_2026_05_09.md) findings:

**FLUX 2 family handles tileable wording correctly** — they read
"tileable seamless texture" as the verb/adjective, not the noun. Use:

```
<material description, 5-15 words>, fully tileable seamless texture,
all four edges loop perfectly, top-down orthographic view, even neutral
diffuse lighting, no shadows, no highlights, no vignette, no border,
no frame, uniform composition, repeating pattern, 1:1 square aspect,
high detail, photorealistic PBR-ready
```

**Good material descriptions** (front-load the noun):

- "weathered alpine granite, lichen patches, gravel detail"
- "dense forest grass with patches of leaf litter, moss, twigs"
- "dry desert canyon sandstone, fine crack network, sun-bleached"
- "compact tundra moss with frost-crystallized patches"

**Anti-patterns** that misfire even in FLUX 2 (per
`pipelines/textures/LESSONS.md`):

- "aerial photograph of field" — generates camera-tilted geometry
- Rare botanical jargon — names model has weak prior on
- "stylized" / "isometric" — confuses orthographic top-down request
- Directional cues ("wind from west", "north-facing") — bake unintended
  shadow direction

---

## ComfyUI node graph (canonical)

This is the structure for **every FLUX 2 t2i workflow** (klein and dev).
The same shape is in [`diversity_compare.py`](diversity_compare.py).

```
┌─────────────────┐                    ┌─────────────────┐
│   UNETLoader    │                    │   CLIPLoader    │
│   or            │                    │   type="flux2"  │
│   UnetLoaderGGUF│                    │   qwen_3_*.sft  │
└────────┬────────┘                    └────────┬────────┘
         │ model                                │ clip
         │                                      │
         │              ┌──────────────────────┘
         │              │
         │              ▼
         │       ┌──────────────┐
         │       │CLIPTextEncode│  (positive prompt)
         │       └──────┬───────┘
         │              │
         │              ▼
         │       ┌──────────────────────┐
         │       │ConditioningZeroOut   │ ← klein only (CFG=1)
         │       │  -- or --            │
         │       │CLIPTextEncode("")    │ ← dev (CFG=4 needs negative)
         │       └──────┬───────────────┘
         │              │
         │              ▼
         │       ┌─────────────────┐
         └─────► │   CFGGuider     │
                 │   cfg=1.0 klein │
                 │   cfg=4.0 dev   │
                 └────────┬────────┘
                          │ guider
                          │
┌─────────────────────────┴───────────────────────────┐
│                                                     │
▼                                                     ▼
┌─────────────────┐      ┌─────────────────┐    ┌──────────────────┐
│ KSamplerSelect  │      │ Flux2Scheduler  │    │ EmptyFlux2Latent │
│ sampler_name=   │      │ steps=4 (klein) │    │ width=1024       │
│   "euler"       │      │ steps=28 (dev)  │    │ height=1024      │
│                 │      │ width/height    │    │                  │
└────────┬────────┘      └────────┬────────┘    └────────┬─────────┘
         │                        │                      │
         │ sampler                │ sigmas               │ latent_image
         │                        │                      │
         │   ┌────────────────────┘                      │
         │   │   ┌──────────────────────────────────────┘
         │   │   │
         │   │   │   ┌──────────────────┐
         │   │   │   │  RandomNoise     │
         │   │   │   │  noise_seed=42   │
         │   │   │   └────────┬─────────┘
         │   │   │            │ noise
         ▼   ▼   ▼            ▼
       ┌────────────────────────────┐
       │   SamplerCustomAdvanced    │
       └────────────┬───────────────┘
                    │ samples
                    ▼
              ┌─────────────┐    ┌──────────────┐
              │  VAEDecode  │◄───│  VAELoader   │
              │             │    │ flux2-vae.sft│
              └──────┬──────┘    └──────────────┘
                     │ images
                     ▼
              ┌─────────────┐
              │  SaveImage  │
              └─────────────┘
```

### Image-to-image variant

Replace `EmptyFlux2LatentImage` with:

```
┌──────────────┐    ┌──────────────┐
│  LoadImage   │───►│  VAEEncode   │  (produces latent_image)
└──────────────┘    └──────────────┘
```

Replace `Flux2Scheduler` with **`BasicScheduler`** (so you can pass
`denoise=0.3-0.8`):

```
┌──────────────────┐
│ BasicScheduler   │
│  scheduler=simple│
│  steps=8 (klein) │
│  denoise=0.5     │
└──────────────────┘
```

**Why the scheduler switch**: `Flux2Scheduler` doesn't accept a
`denoise` arg — it builds a full sigma schedule from steps × resolution.
For img2img you need partial denoising, which only `BasicScheduler`
exposes.

---

## NVFP4 prerequisites (critical)

**NVFP4 is hardware-native on Blackwell.** Our RTX 5090 Laptop has FP4
tensor cores. Without the right PyTorch CUDA build, NVFP4 silently
falls back to a slow path **slower than FP8**.

Required:

- PyTorch 2.11.0+**cu130** (we have it: `pytorch_version: 2.11.0+cu130`)
- ComfyUI 0.20.1+ (we have 0.20.1)
- Blackwell GPU (sm_120 — RTX 5090, RTX 5080, RTX 5070 Ti, RTX 5070, RTX 5090 Laptop)

Verify in ComfyUI logs at startup. If you see "NVFP4 acceleration
unavailable" or "falling back to fp8 path," PyTorch is wrong.

Per [ComfyUI's NVFP4 blog post](https://blog.comfy.org/p/new-comfyui-optimizations-for-nvidia):
> "ComfyUI only supports NVFP4 acceleration if you are running PyTorch
> built with CUDA 13.0 (cu130). Otherwise, while the model will still
> function, your sampling may actually be up to 2x slower than fp8."

NVFP4 + Async Offload + Pinned Memory work together — they're enabled
by default in ComfyUI 0.20.1. Only matters when the model doesn't fit
fully in VRAM (klein-9b-nvfp4 at 5.76 GB fits, dev-nvfp4 at 21 GB also
fits — so async offload is mostly a non-issue for us).

---

## Quality / speed tradeoff per quant

Per [SECourses RTX 5090 head-to-head](https://github.com/FurkanGozukara/Stable-Diffusion/wiki/BF16-vs-GGUF-FP8-Scaled-NVFP4-Speed-and-Quality-Compared-ComfyUI-CUDA-13-Gains-FLUX-2-Klein-9B)
on klein-9B 1024² 4-step:

| Quant | Speed vs BF16 | VRAM | Quality vs BF16 |
|---|---|---|---|
| BF16 (reference) | 1.0× | ~26 GB | reference |
| FP8 scaled | 1.7× | ~15 GB | "almost same quality" |
| **NVFP4** | **2.5×** | **~10 GB** | "some degrade in quality" |
| Q8 GGUF (community, w/ cu130) | ~slower than FP8 | ~14 GB | high (community quant) |

For dev (32B undistilled, 28-step):

| Quant | Speed (RTX 5090) | VRAM | Status |
|---|---|---|---|
| BF16 | OOM on 24 GB | ~26 GB transformer alone | not viable |
| NVFP4 | ~4 s/img | ~14 GB | **viable, what we have** |
| Q8 GGUF | ~7.97 s/img | ~28 GB w/ offload | slower, needs offload |
| Q4_K_S GGUF | ~7 s/img | ~22 GB tight | viable but lower quality |

**Practical decision**: NVFP4 for both klein-9B and dev unless the
bakeoff shows visible "some degrade" affects our texture work.

---

## Image-to-image / heal pass settings

Used by our `offset+heal` seamless trick in
[`flux_seamless.py`](flux_seamless.py) and the `do_seamless` path in
[`diversity_compare.py`](diversity_compare.py).

For klein-9B (any quant) heal pass:
- `denoise=0.30-0.45` works for material-class textures (texture-grade
  retained, seams smoothed)
- `denoise=0.50-0.70` for stronger anchor-reference influence
- `denoise=0.85-0.95` for "use reference as loose composition guide only"
- Steps=8 (BasicScheduler + denoise<1 doesn't need 4 — 8 gives more
  effective denoising steps)
- CFG=1.0 still (klein is distilled regardless of mode)

For dev heal pass:
- `denoise=0.40-0.60` for hero-image refinement
- Steps=28, CFG=4.0 unchanged
- Use `BasicScheduler` not `Flux2Scheduler` (needs denoise arg)

---

## License (read this once, don't worry about it again)

The FLUX Non-Commercial License covers the **model weights only**, not
the **generated outputs**.

From the official BFL license text:

> "We claim no ownership rights in and to the Outputs. You are solely
> responsible for the Outputs you generate and their subsequent uses in
> accordance with this License. **You may use Output for any purpose
> (including for commercial purposes), except as expressly prohibited
> herein.**"

What this means for us:

- ✅ **Generated images can ship in a commercial game** (or any commercial product)
- ✅ Generated images can be displayed publicly (subject to AI disclosure laws in your jurisdiction)
- ✅ Personal/research/hobby use of the model weights themselves is allowed
- ⚠️ Cannot use the model weights in a revenue-generating service (running
  a paid image-gen API)
- ❌ Cannot use outputs to train a competitive image generation model
- N/A No attribution required on outputs (only on redistributing weights)

Reference: [FLUX.2-dev LICENSE.md](https://huggingface.co/black-forest-labs/FLUX.2-dev/blob/main/LICENSE.md)
section 2(d).

---

## How to run the bakeoff

Sequential through all FLUX 2 lanes (ComfyUI evicts on swap, so 24 GB
fits all):

```bash
cd d:/assets/pipelines/textures
.venv/Scripts/python.exe diversity_compare.py \
    --prompt "weathered alpine granite, lichen patches, gravel detail" \
    --id alpine_granite_flux2_full_bakeoff \
    --seed 42 \
    --models flux2_klein,flux2_klein_9b,flux2_klein_9b_nvfp4,flux2_klein_9b_fp8,flux2_dev_nvfp4
```

Expected wall time per prompt at 1024² (no seamless): ~12-25 s total
across all five. With seamless heal added: ~30-60 s total.

Recommended prompt suite for material lane (matches the M14 blockers):

1. `weathered alpine granite, lichen patches, gravel detail` — hard surface
2. `dense forest grass with patches of leaf litter, moss, twigs` — soft organic
3. `dry desert canyon sandstone, fine crack network, sun-bleached` — mid-tone
4. `compact tundra moss with frost-crystallized patches` — high-frequency green

All on `seed=42` for comparability. Output lands at
`D:/tmp/diversity_compare_2026_05_09/<id>/` with `grid_pass1.png` (raw)
and `grid_final.png` (offset+heal).

---

## Common errors and fixes

**"NVFP4 acceleration unavailable"**:
- PyTorch is not cu130. Reinstall ComfyUI's torch with cu130 build.

**"Architecture flux not recognized"** (Q8 GGUF only):
- ComfyUI-GGUF is outdated. `cd custom_nodes/ComfyUI-GGUF; git pull`.

**Output is uniform decorative tiles**:
- Wrong model. FLUX 2 family handles "tileable" correctly; this is the
  Chroma/SD3.5/Qwen "tile as noun" trap. Stay on FLUX 2 or AuraFlow.

**Output has central composition / DOF / hero-shot framing**:
- Prompt suffix has wrong wording for the model. SD 3.5 needs
  "no central focal point" added; klein/AuraFlow don't.

**OOM on 24 GB card running dev-nvfp4**:
- Should fit at ~14 GB. Verify ComfyUI is on 0.20.1+ with Async Offload
  enabled. Check that no other big models are still resident
  (use `Unload Models` button).

**klein-9B output is blurrier than klein-4B**:
- You used too many steps. klein is distilled to **exactly 4 steps**.
  Using 8+ steps degrades distilled output. From Diffusion Doodles:
  "distilled Klein models do not work well if you use too many steps."

**Long-form prompts get partially ignored**:
- klein is bad at this; switch to dev for the same prompt to see if
  it follows correctly. dev at CFG=4 handles 80-150 word prompts cleanly.

---

## Settings flow chart (decision tree)

```
Need a texture/material from text?
├── Iteration / batch / 8 variants?  → klein-9b NVFP4, 4 steps, CFG=1, Flux2Scheduler
├── One hero image / best-of-1?      → dev NVFP4, 28 steps, CFG=4, Flux2Scheduler
├── Calmer painterly variant?        → auraflow_03, 25 steps, CFG=3.5
└── Photoreal forest organic?        → sd35_large, 28 steps, CFG=4.5

Need to refine/heal an existing image?
├── Strong reference, light cleanup  → klein-9b NVFP4 img2img, denoise=0.3-0.4
├── Reference as loose guide         → klein-9b NVFP4 img2img, denoise=0.7-0.85
└── Hero-quality refinement          → dev NVFP4 img2img, denoise=0.4-0.6
```

---

## Sources

- [BFL FLUX.2 Prompting Guide (official)](https://docs.bfl.ml/guides/prompting_guide_flux2)
- [BFL FLUX.2-klein-9B model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B)
- [BFL FLUX.2-dev model card](https://huggingface.co/black-forest-labs/FLUX.2-dev)
- [BFL FLUX.2-dev LICENSE](https://huggingface.co/black-forest-labs/FLUX.2-dev/blob/main/LICENSE.md)
- [BFL flux2 inference repo](https://github.com/black-forest-labs/flux2)
- [HF Diffusers Flux2 pipeline docs](https://huggingface.co/docs/diffusers/api/pipelines/flux2)
- [ComfyUI native FLUX 2 tutorial](https://docs.comfy.org/tutorials/flux/flux-2-klein)
- [ComfyUI NVFP4 + async offload blog](https://blog.comfy.org/p/new-comfyui-optimizations-for-nvidia)
- [NVIDIA NVFP4 inference on Blackwell](https://developer.nvidia.com/blog/scaling-nvfp4-inference-for-flux-2-on-nvidia-blackwell-data-center-gpus/)
- [SECourses BF16/GGUF/FP8/NVFP4 head-to-head on RTX 5090](https://github.com/FurkanGozukara/Stable-Diffusion/wiki/BF16-vs-GGUF-FP8-Scaled-NVFP4-Speed-and-Quality-Compared-ComfyUI-CUDA-13-Gains-FLUX-2-Klein-9B)
- [Apatero FLUX 2 klein ComfyUI guide](https://www.apatero.com/blog/flux-2-klein-comfyui-workflow-guide)
- [Diffusion Doodles: Flux.2 Klein shrinking Flux.2 Dev](https://medium.com/diffusion-doodles/flux-2-klein-shrinking-flux-2-dev-2258b1078e75)
- [fal.ai FLUX 2 klein prompt guide](https://fal.ai/learn/devs/flux-2-klein-prompt-guide)
- Internal: [`pipelines/textures/DIVERSITY_COMPARE_2026_05_09.md`](DIVERSITY_COMPARE_2026_05_09.md)
- Internal: [`pipelines/textures/LESSONS.md`](LESSONS.md)
- Internal: [`pipelines/textures/TEXTURE_RND.md`](TEXTURE_RND.md)
