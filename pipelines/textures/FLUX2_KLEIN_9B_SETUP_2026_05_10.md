# FLUX.2-klein 9B Setup — 2026-05-10

Status: **setup only, no comparison run yet**. The user wanted the install
ready so the side-by-side can be run later under one ComfyUI instance.

Current local state:

- `flux-2-klein-9b-Q8_0.gguf` is present in
  `D:/assets/animators/ComfyUI/models/diffusion_models`.
- `qwen_3_8b_fp8mixed.safetensors` is present in
  `D:/assets/animators/ComfyUI/models/text_encoders`.
- No official BFL NVFP4/FP8 9B transformer file was present at last local
  inspection.

Important correction: the incoming BFL NVFP4/FP8 files should be treated as a
separate lane, not as a replacement for the Q8 GGUF lane. Keep
`flux2_klein_9b` as the unsloth Q8 GGUF test, then add a new registry entry
such as `flux2_klein_9b_nvfp4` or `flux2_klein_9b_fp8` once the exact filename
and ComfyUI loader path are confirmed.

## What we picked and why

| Component | File | Size | Source | Why |
|-----------|------|------|--------|-----|
| Transformer | `flux-2-klein-9b-Q8_0.gguf` | 9.98 GB | [unsloth/FLUX.2-klein-9B-GGUF](https://huggingface.co/unsloth/FLUX.2-klein-9B-GGUF) | Highest quality GGUF; matches our Q8 convention for AuraFlow / SD3.5 / Chroma. Not gated. |
| Text encoder | `qwen_3_8b_fp8mixed.safetensors` | 8.66 GB | [Comfy-Org/vae-text-encorder-for-flux-klein-9b](https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-9b) | Official Comfy-Org fp8 quant. klein-9B requires Qwen3-8B, not the qwen_3_4b klein-4B uses. Not gated. |
| VAE | `flux2-vae.safetensors` | 0.32 GB | already on disk | Shared with klein-4B; identical file. |

Total new disk: **~18.6 GB**. Disk after: 74 GB → ~55 GB free.

## Variants we considered and rejected

### Official BFL `FLUX.2-klein-9b-fp8` (9.4 GB, single file)
- **Gated** (`gated=auto`, needs user-clicked license accept on HF).
- Quality slightly higher than community Q8 (BFL-calibrated FP8).
- **Defer until later**: user can accept terms in browser, then we re-pull and swap. Same workflow, just `unet_name` flips to `flux-2-klein-9b-fp8.safetensors` with a non-GGUF UNETLoader.

### Official BFL `FLUX.2-klein-9b-nvfp4`
- Also gated behind the BFL license flow.
- This is the likely "nvpf4" download the user mentioned; correct name is
  **NVFP4**.
- Keep as a separate comparison lane. Do not reuse the GGUF workflow until we
  confirm whether ComfyUI loads it through the standard diffusion-model loader,
  a single-file Diffusers path, or a newer FLUX 2 node path.
- Hardware notes on the BFL model card still cite roughly RTX 4090-class VRAM,
  so first local test should be a single 1024 sample before running a batch.

### Official BFL `FLUX.2-klein-9b-kv-fp8`
- Optimized for repeated multi-reference editing through KV caching.
- Probably not the first target for our texture sweep because M14 texture
  generation is mostly text-to-image plus seamless heal, not repeated
  reference-image editing.

### Nunchaku / SVDQuant INT4
- Repo `tonera/FLUX.2-klein-9B-Nunchaku` exists (3-4 GB, 3× faster than BF16).
- **ComfyUI-Nunchaku does not yet support FLUX 2** (PR #926 pending merge).
- Revisit when that PR lands.

### Unsloth Q6_K instead of Q8
- Saves 2 GB disk, ~2 GB VRAM, but measurably worse on texture detail per
  unsloth's own dynamic-quant docs (Q8_0 is their "near-lossless" tier).
- 24 GB card has headroom; the right call is Q8.

### Keep using klein-4B
- The whole point of the test. We'll know after the bakeoff whether 9B
  beats 4B on ground-texture work to a degree that justifies 2× cost.

## Settings vs klein-4B

Identical sampling shape. Both are 4-step distilled. Only differences:
- `unet_name`: `flux-2-klein-9b-Q8_0.gguf` (was `flux-2-klein-4b.safetensors`)
- Loader: `UnetLoaderGGUF` (was `UNETLoader`)
- `clip_name`: `qwen_3_8b_fp8mixed.safetensors` (was `qwen_3_4b.safetensors`)
- VAE / scheduler / sampler / CFG / steps / latent class: unchanged.

Code: `wf_flux2_klein_9b_q8()` in
[`pipelines/textures/diversity_compare.py`](diversity_compare.py).

## ComfyUI-GGUF compatibility note

The unsloth Q8 GGUF tags `general.architecture: flux` (not `flux2`) in its
metadata. This is intentional — FLUX 2 reuses the FLUX 1 DiT skeleton with
different conditioning + size. ComfyUI-GGUF's `UnetLoaderGGUF` picks the
arch from this key, then the **workflow** specifies the FLUX 2-specific
CLIPLoader type, scheduler, and latent class. Confirmed by unsloth README:
"Uses tooling from ComfyUI-GGUF by city96."

If the first ComfyUI load errors with "unsupported architecture," the fix
is to update `ComfyUI-GGUF` (`git pull` in `custom_nodes/ComfyUI-GGUF`) —
current head as of audit: `6ea2651`, last commit Oct 2025 era. No klein-9B
work flagged in their commit log but the FLUX architecture handling has
been stable.

## How to run the bakeoff (later)

```
cd d:/assets/pipelines/textures
.venv/Scripts/python.exe diversity_compare.py \
    --prompt "weathered alpine granite, lichen patches, gravel detail" \
    --id alpine_granite_9b_bakeoff \
    --seed 42 \
    --models flux2_klein,flux2_klein_9b
```

This runs the same prompt + seed through both 4B and 9B sequentially.
Output lands at `D:/tmp/diversity_compare_2026_05_09/alpine_granite_9b_bakeoff/`
with `grid_pass1.png` (raw t2i) and `grid_final.png` (offset+heal seamless).

Suggested prompt set for first comparison:

1. Alpine granite + lichen — close-play hard surface
2. Temperate forest leaf litter — close-play soft organic
3. Desert dry wash — mid-tone gravel
4. Tundra moss — high-frequency green organic (the M14 blocker class)

Seed=42 across all four for direct comparability.

## VRAM budget at runtime

- 24 GB card.
- Q8 GGUF transformer loaded: ~10.5 GB.
- fp8 text encoder loaded: ~9 GB (encoded once, then unloaded by ComfyUI).
- VAE: ~0.5 GB.
- Latent + activations at 1024² with 4 steps: ~2-3 GB peak.
- **Expected peak**: ~14 GB during sampling. ~10 GB headroom for OS/Comfy
  overhead and concurrent apps.

If we hit OOM (we shouldn't), drop to Q6_K (-2 GB) before any other change.

## Next steps

1. Wait for the text encoder download to finish (~5 min on a typical line).
2. Run the bakeoff under one ComfyUI instance, sequential model loads.
3. Score by eye + seam metric for the 4 prompts above.
4. Write a findings doc at `pipelines/textures/M14_KLEIN_9B_BAKEOFF_<date>.md`.
5. If 9B wins materially → swap to the FP8 official path (accept gate,
   re-pull). If 9B doesn't move the needle → delete the 9B files, keep the
   bakeoff doc as negative evidence.

## Disk-cleanup checklist if we end up rejecting 9B

```
del d:/assets/animators/ComfyUI/models/diffusion_models/flux-2-klein-9b-Q8_0.gguf
del d:/assets/animators/ComfyUI/models/text_encoders/qwen_3_8b_fp8mixed.safetensors
```

Reclaims ~18.6 GB.
