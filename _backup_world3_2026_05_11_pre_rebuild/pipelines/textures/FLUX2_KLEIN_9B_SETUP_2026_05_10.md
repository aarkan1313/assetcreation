# FLUX.2 9B + dev Stack Setup — 2026-05-10

Status: **setup complete; no bakeoff run yet**. All transformer files staged
in `D:/assets/animators/ComfyUI/models/diffusion_models/`. Shared encoder +
VAE staged. Diversity-compare harness registry has builders for every lane.
Ready to run the side-by-side under one ComfyUI instance.

## What's on disk

Three klein-9B variants + the dev model, all sharing one encoder + VAE.

| Lane | File | Size | Source | Status |
|---|---|---|---|---|
| Q8 GGUF (community) | `flux-2-klein-9b-Q8_0.gguf` | 9.98 GB | [unsloth/FLUX.2-klein-9B-GGUF](https://huggingface.co/unsloth/FLUX.2-klein-9B-GGUF) | ✅ on disk |
| **NVFP4 (official)** | `flux-2-klein-9b-nvfp4.safetensors` | 5.76 GB | [black-forest-labs/FLUX.2-klein-9b-nvfp4](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-nvfp4) | ✅ on disk |
| FP8 (official) | `flux-2-klein-9b-fp8.safetensors` | 9.43 GB | [black-forest-labs/FLUX.2-klein-9b-fp8](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8) | ✅ on disk |
| **dev NVFP4 32B** | `flux2-dev-nvfp4.safetensors` | 21.0 GB | [black-forest-labs/FLUX.2-dev-nvfp4](https://huggingface.co/black-forest-labs/FLUX.2-dev-nvfp4) | 🔄 downloading (HF) |

| Shared | File | Size | Source | Status |
|---|---|---|---|---|
| Text encoder | `qwen_3_8b_fp8mixed.safetensors` | 8.66 GB | [Comfy-Org/vae-text-encorder-for-flux-klein-9b](https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-9b) | ✅ on disk |
| VAE | `flux2-vae.safetensors` | 0.32 GB | shared with klein-4B | ✅ on disk |

Total disk: ~55 GB across the four model lanes + shared encoder. dev-nvfp4 is the heaviest single item.

## Why we have three klein-9B variants

The user (correctly) asked to keep them all so we can A/B the
quantization-quality tradeoff head-to-head on real prompts, not by
trusting NVIDIA/SECourses benchmarks. After the bakeoff:

- If NVFP4 quality is indistinguishable from FP8 → keep NVFP4 only,
  delete FP8 (9.43 GB) and Q8 GGUF (9.98 GB). 19.4 GB reclaim.
- If NVFP4 has visible quality loss but FP8 is fine → keep FP8, delete
  NVFP4 + Q8. 15.7 GB reclaim.
- If Q8 GGUF beats both BFL quants (unlikely but possible) → keep Q8,
  delete NVFP4 + FP8. 15.2 GB reclaim.

Whichever wins becomes the canonical `flux2_klein_9b` lane in the M14 board.

## Why FLUX.2-dev too

`FLUX.2-dev` is 32B params — 3.5× klein-9B — and undistilled. It's the
absolute open-weight quality ceiling BFL ships. At NVFP4 it fits ~14 GB
VRAM and runs ~4 sec/image at 1024² (vs <1 sec for klein-9B-nvfp4).

**Role split**:
- `klein-9b` variants → iteration / fan-out at <1 sec/img (4-step distilled)
- `dev-nvfp4` → hero passes / single best variants at ~4 sec/img (28 steps)

They're complementary, not alternatives.

## Speed/quality numbers (verified)

Per [NVIDIA blog](https://developer.nvidia.com/blog/scaling-nvfp4-inference-for-flux-2-on-nvidia-blackwell-data-center-gpus/)
and [SECourses RTX 5090 head-to-head](https://github.com/FurkanGozukara/Stable-Diffusion/wiki/BF16-vs-GGUF-FP8-Scaled-NVFP4-Speed-and-Quality-Compared-ComfyUI-CUDA-13-Gains-FLUX-2-Klein-9B):

**klein-9B 1024² 4-step on RTX 5090 (cu130)**:
- BF16: baseline (1×, ~26 GB VRAM — won't fit our 24 GB card)
- FP8 scaled: 1.7× faster, ~40% less VRAM, "almost same quality" vs BF16
- **NVFP4: 2.5× faster, ~60% less VRAM, "some degrade in quality" vs BF16**
- Q8 GGUF (community): slower than FP8 on Blackwell due to runtime quant overhead

**dev 1024² 28-step on RTX 5090 (cu130)**:
- BF16: way over VRAM, not viable
- NVFP4: ~14 GB VRAM, ~4 sec/img
- Q8 GGUF: ~7.97 sec/img (2× slower than NVFP4)
- Q4_K_S GGUF: 19.3 GB on disk, similar speed to NVFP4 but lower quality

**Our prerequisites for NVFP4**:
- PyTorch 2.11.0+cu130 ✅ (anything other than cu130 makes NVFP4 *slower* than FP8)
- ComfyUI 0.20.1 ✅ (shipped NVFP4 support)
- Blackwell GPU (sm_120) ✅ (RTX 5090 Laptop)

## Why we skipped Nunchaku / SVDQuant

[`tonera/FLUX.2-klein-9B-Nunchaku`](https://huggingface.co/tonera/FLUX.2-klein-9B-Nunchaku)
exists (3-4 GB INT4 SVDQuant) and would be ~3× faster than BF16. But
**ComfyUI-Nunchaku does not yet support FLUX 2** (PR #926 pending merge).
Revisit when that lands — could outperform NVFP4 if it does.

## Workflow nodes

All five new lanes (klein-9b Q8/NVFP4/FP8 + dev-nvfp4) share:
- `CLIPLoader` with `clip_name=qwen_3_8b_fp8mixed.safetensors`, `type=flux2`
- `VAELoader` with `vae_name=flux2-vae.safetensors`
- `EmptyFlux2LatentImage` for t2i, `VAEEncode` for img2img

Loader differs per lane:
- Q8 GGUF: `UnetLoaderGGUF` (ComfyUI-GGUF custom node)
- NVFP4: `UNETLoader` (native ComfyUI, requires 0.20.1+ for NVFP4 support)
- FP8: `UNETLoader` (native ComfyUI)
- dev-nvfp4: `UNETLoader` (native ComfyUI)

Sampler differs by distillation status:
- klein-9b (4-step distilled): CFG=1.0, 4 steps, `Flux2Scheduler`, euler
- dev (undistilled): CFG=4.0, 28 steps, `BasicScheduler` `simple`, euler

Code: `wf_flux2_klein_9b_q8`, `wf_flux2_klein_9b_nvfp4`, `wf_flux2_klein_9b_fp8`,
and `wf_flux2_dev_nvfp4` in [`diversity_compare.py`](diversity_compare.py).

## ComfyUI-GGUF compatibility note (Q8 lane only)

The unsloth Q8 GGUF tags `general.architecture: flux` (not `flux2`) in its
metadata. This is intentional — FLUX 2 reuses the FLUX 1 DiT skeleton.
ComfyUI-GGUF's `UnetLoaderGGUF` picks the arch from this key, then the
**workflow** specifies the FLUX 2-specific CLIPLoader type, scheduler, and
latent class. Confirmed by unsloth README: "Uses tooling from ComfyUI-GGUF
by city96."

If first load errors with "unsupported architecture," update ComfyUI-GGUF
(`git pull` in `custom_nodes/ComfyUI-GGUF`).

## How to run the bakeoff

```
cd d:/assets/pipelines/textures
.venv/Scripts/python.exe diversity_compare.py \
    --prompt "weathered alpine granite, lichen patches, gravel detail" \
    --id alpine_granite_klein9b_quant_bakeoff \
    --seed 42 \
    --models flux2_klein,flux2_klein_9b,flux2_klein_9b_nvfp4,flux2_klein_9b_fp8,flux2_dev_nvfp4
```

This runs the same prompt + seed through all five sequentially. ComfyUI
will evict each model on the next swap so 24 GB VRAM is sufficient.

Suggested prompt set:

1. Alpine granite + lichen — close-play hard surface
2. Temperate forest leaf litter — close-play soft organic
3. Desert dry wash — mid-tone gravel
4. Tundra moss — high-frequency green organic (the M14 blocker class)

Seed=42 across all four for direct comparability. Output lands at
`D:/tmp/diversity_compare_2026_05_09/<id>/` with `grid_pass1.png` (raw t2i)
and `grid_final.png` (offset+heal seamless).

## VRAM budget per lane

| Lane | Transformer | Text encoder (loaded then unloaded) | Latents+activations | Peak |
|---|---|---|---|---|
| klein-9b Q8 GGUF | ~10.5 GB | ~9 GB transient | ~2 GB | ~14 GB |
| klein-9b NVFP4 | ~6 GB | ~9 GB transient | ~2 GB | ~10 GB |
| klein-9b FP8 | ~10 GB | ~9 GB transient | ~2 GB | ~14 GB |
| dev NVFP4 | ~14 GB | ~9 GB transient | ~3 GB | ~17 GB |

All comfortably under 24 GB on our card.

## Next steps

1. Wait for dev-nvfp4 download to finish (~4 more min as of writing).
2. Restart ComfyUI to pick up the new model files (or hit the refresh node
   in the UI).
3. Run the bakeoff for at least 2 prompts.
4. Eyeball + seam-score the results.
5. Write findings to `pipelines/textures/M14_KLEIN9B_DEV_BAKEOFF_2026_05_10.md`.
6. Based on results: keep one klein-9b variant, decide whether dev-nvfp4
   stays in rotation or gets parked for hero-only use.

## Reclaim if we reject a lane after bakeoff

```bash
# If NVFP4 is the winner:
rm d:/assets/animators/ComfyUI/models/diffusion_models/flux-2-klein-9b-fp8.safetensors
rm d:/assets/animators/ComfyUI/models/diffusion_models/flux-2-klein-9b-Q8_0.gguf
# 19.4 GB reclaimed

# If we reject 9B entirely (4B remains the winner):
rm d:/assets/animators/ComfyUI/models/diffusion_models/flux-2-klein-9b-*.safetensors
rm d:/assets/animators/ComfyUI/models/diffusion_models/flux-2-klein-9b-Q8_0.gguf
rm d:/assets/animators/ComfyUI/models/text_encoders/qwen_3_8b_fp8mixed.safetensors
# 33.8 GB reclaimed

# If we reject dev:
rm d:/assets/animators/ComfyUI/models/diffusion_models/flux2-dev-nvfp4.safetensors
# 21 GB reclaimed
```
