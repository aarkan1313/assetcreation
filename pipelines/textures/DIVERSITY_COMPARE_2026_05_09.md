# Texture Generator Diversity Comparison — 2026-05-09

Goal: validate four candidate alternatives to the existing FLUX.2-klein pipeline as **diversity lanes** for ground-texture generation, on the same prompt + seed + offset+heal post-process.

Comparison rig: [diversity_compare.py](diversity_compare.py). Outputs: `D:/tmp/diversity_compare_2026_05_09/{sandstone,grass}_compare/`.

## Setup

- **Hardware**: RTX 5090 Laptop, 24 GB VRAM, torch 2.11.0+cu130, ComfyUI 0.20.1
- **Custom node**: ComfyUI-GGUF (city96), commit installed 2026-05-09
- **Resolution**: 1024×1024
- **Seed**: 42 (pass1), 141 (heal pass)
- **Heal denoise**: 0.35
- **Tile suffix**: same `TILE_PROMPT_SUFFIX` as `flux_seamless.py`

| Model | Quant | Disk | Encoder | VAE |
|---|---|---|---|---|
| FLUX.2-klein 4B (baseline) | full | 8.0 GB | qwen_3_4b | flux2-vae |
| Chroma1-HD | Q8_0 | 9.7 GB | t5xxl_fp8 | ae (FLUX) |
| SD 3.5 Large | Q8_0 | 8.8 GB | clip_g+clip_l+t5xxl_fp8 | sd3.5_vae |
| AuraFlow v0.3 | Q8_0 | 7.3 GB | pile_t5_xl_fp16 | auraflow_vae |
| Qwen-Image | Q6_K | 16.8 GB | qwen2.5_vl_fp8 | qwen_image_vae |

Total weight footprint: **~62 GB on D:\\** (incl. shared encoders).

## Prompt 1 — sandstone ground

Prompt: `weathered grey sandstone ground, fine grit detail` + tile suffix.

| Model | pass1 seam | final seam | total | Result |
|---|---|---|---|---|
| FLUX.2-klein | 0.0115 | **0.0085** | 10.2s | Authentic weathered sandstone with cracks ✅ |
| Chroma1-HD | 0.0008 | **0.0000** | 140.4s | Tiled wall panels — misread "tileable" as noun ❌ |
| SD 3.5 Large | 0.0778 | 0.0554 | 140.3s | Cobblestone slab, single composition, central bias persists ❌ |
| AuraFlow v0.3 | 0.0133 | **0.0052** | 172.3s | Smooth concrete (wrong material) but tiles cleanly ⚠️ |
| Qwen-Image Q6_K | 0.0533 | 0.0441 | 460.6s | Decorative pyramid tiles — also misread as noun ❌ |

## Prompt 2 — forest floor / grass

Prompt: `dense forest grass with patches of leaf litter, moss, twigs` + tile suffix.

| Model | pass1 seam | final seam | total | Result |
|---|---|---|---|---|
| FLUX.2-klein | 0.0385 | 0.0184 | 28.2s | Detailed top-down forest floor, ferns + moss + leaves ✅ |
| Chroma1-HD | 0.8177 | **0.8928** | 240.4s | Catastrophic failure — flat green grid pattern ❌ |
| SD 3.5 Large | 0.0909 | 0.0430 | 140.3s | Realistic ground but visible center seam (offset trick fighting central composition) ⚠️ |
| AuraFlow v0.3 | 0.0206 | **0.0075** | 174.3s | Dense uniform moss with twigs — different aesthetic ✅ |
| Qwen-Image Q6_K | 0.0201 | **0.0059** | 466.6s | Photographic with cinematic DOF — hero shot, not a tile ⚠️ |

## Visual verdicts

### FLUX.2-klein (baseline)
Reliable, fast (10–30s end-to-end), correct subject in both tests. **Reference quality**.

### Chroma1-HD
**Worst behavior in this test.** Both prompts failed:
- Sandstone → wall tile pattern
- Grass → degenerate flat green grid (seam=0.89)

Chroma's lower numerical seam scores on sandstone (0.0000) are misleading — they reflect the model collapsing into uniform repeated motifs, not high tile quality. **Prompt sensitivity is fundamentally different from FLUX**; the existing prompt + tile suffix is a poison pill for Chroma. User review rejects Chroma for the current texture workflow phase.

### SD 3.5 Large
Generates plausible material content but **fights tileability** — the central composition bias predicted by my pre-research played out exactly as warned. The offset+heal trick partially helps but cannot remove the central focal point baked into pass1.

For ground textures, SD 3.5 needs either:
- Stronger anti-composition prompt wording ("uniform overhead, edge-to-edge, no central focal point")
- Generation at 2048+ then crop to a non-central region
- Pairing with `spinagon/ComfyUI-seamless-tiling` for circular VAE decode

### AuraFlow v0.3
**Surprise winner among diversity candidates.** Tiles best after FLUX (final seam 0.005–0.008). Style is distinctive — flatter, more uniform, slightly painterly. Got the wrong material on sandstone (concrete instead of sandstone) but produced an excellent dense-moss texture on grass. Ideal for **stylized / painterly ground variants**.

Caveats:
- Slow (~3min total for offset+heal)
- Needs Pile-T5-XL fp16 encoder (canonical file: `fal/AuraFlow-v0.3/text_encoder/model.fp16.safetensors`, 2.95 GB)
- ComfyUI's CLIPLoader has no `'auraflow'` type — use `'stable_diffusion'`, encoder is auto-detected as T5_XL

### Qwen-Image Q6_K
Beautiful photographic output with cinematic depth-of-field — but that's exactly the problem for ground textures. Qwen-Image clearly trained on hero shots, not material samples. The grass output looks like a stock photo, not a tileable ground.

Also: **3–8× slower than competitors** (461s sandstone, 467s grass total). Q6_K runs but compute cost is prohibitive for batch texture work on the laptop GPU.

## Important finding: prompt-engineering trap

Three of four diversity models (Chroma, SD 3.5, Qwen) misread the existing `TILE_PROMPT_SUFFIX` token "**tileable**" as the noun "**tile**", producing decorative tile patterns instead of natural ground. **Only FLUX.2-klein and AuraFlow** correctly parsed it as a tiling instruction.

This means the existing suffix is calibrated to FLUX-family models. Switching diversity lanes likely requires a per-model prompt template:

- **FLUX-family** (current): "fully tileable seamless texture, ..."
- **SD 3.5 / Qwen / Chroma**: Try "macro photograph, top-down, edge-to-edge repeating pattern" or similar — avoid the word "tile".

This is a concrete actionable fix, not a model defect.

## Compatibility status

All four models slot into the existing `comfy_generate.py` pattern (HTTP API → ComfyUI workflow JSON). Architecture-specific differences:

| Model | EmptyLatent type | CFG | Steps | Sampler | Scheduler |
|---|---|---|---|---|---|
| FLUX.2-klein | `EmptyFlux2LatentImage` | 1.0 | 4 | euler | Flux2Scheduler |
| Chroma1-HD | `EmptyLatentImage` | 4.0 | 26 | euler | simple |
| SD 3.5 Large | `EmptySD3LatentImage` | 4.5 | 28 | euler | sgm_uniform |
| AuraFlow v0.3 | `EmptyLatentImage` | 3.5 | 25 | euler | simple |
| Qwen-Image | `EmptyLatentImage` | 4.0 | 30 | euler | simple |

The offset+heal trick generalizes cleanly across all five (lifted verbatim from `flux_seamless.py`). PBR derivation via CHORD/StableMaterials is model-agnostic — they consume the 1024 albedo PNG.

## User validation and lane decision

User visual review accepted this direction:

- **Sandstone**: FLUX and AuraFlow are both useful; FLUX wins.
- **Forest / organic ground**: FLUX, AuraFlow, and SD 3.5 all produced useful candidates.
- **Qwen-Image**: visually interesting, but not what this workflow needs for ground textures in this pass. It may need a very different prompt family before reconsideration.
- **Chroma1-HD**: rejected for the current phase.

Decision: M8 texture regeneration should use an active bakeoff set, not a
single-model promotion path. Generate model-specific batches from FLUX.2-klein,
AuraFlow v0.3, and SD 3.5 Large; compare them visually in terrain context; then
promote the best candidate while keeping alternates as sidecars.

## Recommendation

**Active bakeoff lanes**:

1. **FLUX.2-klein** — canonical production-reference lane. Fastest, most reliable, and still the winner for sandstone.
2. **AuraFlow v0.3** — active diversity lane. Best alternate tileability and useful for calmer/painterly/uniform surfaces.
3. **SD 3.5 Large** — active experimental photoreal lane, especially for forest/organic ground. It needs stronger anti-composition prompting and may need 2048-generate/crop or circular decode if center bias persists.

**Park**:

- **Qwen-Image Q6_K** — too slow and too hero-shot/DOF biased for the current ground-texture lane. Revisit only with a dedicated orthographic material-scan prompt family.

**Reject for this phase**:

- **Chroma1-HD** — current outputs failed the material target badly enough that it should not consume M8 regeneration time.

## Future batch workflow

For each M8 material blocker:

1. Run 4-8 candidates each from FLUX.2-klein, AuraFlow v0.3, and SD 3.5 Large.
2. Use model-specific prompt templates/settings. Do not blindly reuse the FLUX `tileable` suffix on every model.
3. Score seam/tile metrics, but treat them as a filter, not the decision.
4. Visually veto central compositions, decorative tile motifs, hero-shot depth of field, object landmarks, boxy patches, and noisy clutter.
5. Review survivors in Godot terrain context at close, mid, far, iso, and topdown distances.
6. Promote only the best terrain-context pass; retain useful alternates as sidecar candidates for future biome/style variants.

## Files

- Comparison harness: [diversity_compare.py](diversity_compare.py)
- Sandstone outputs: `D:/tmp/diversity_compare_2026_05_09/sandstone_compare/`
- Grass outputs: `D:/tmp/diversity_compare_2026_05_09/grass_compare/`
- Side-by-side grids: `grid_pass1.png` and `grid_final.png` in each compare dir

## Models on disk

```
D:/assets/animators/ComfyUI/models/
├── diffusion_models/
│   ├── chroma1-hd-Q8_0.gguf            9.7 GB
│   ├── sd3.5_large-Q8_0.gguf           8.8 GB
│   ├── aura_flow_0.3-Q8_0.gguf         7.3 GB
│   └── qwen-image-Q6_K.gguf           16.8 GB
├── text_encoders/
│   ├── t5xxl_fp8_e4m3fn.safetensors    4.9 GB  (Chroma, SD3.5)
│   ├── clip_g.safetensors              1.4 GB  (SD3.5)
│   ├── clip_l.safetensors              246 MB  (SD3.5)
│   ├── auraflow_pile_t5_xl_fp16.safetensors  2.8 GB  (AuraFlow)
│   └── qwen_2.5_vl_7b_fp8_scaled.safetensors  9.4 GB  (Qwen-Image)
└── vae/
    ├── sd3.5_vae.safetensors           167 MB
    ├── auraflow_vae.safetensors        167 MB
    └── qwen_image_vae.safetensors      254 MB
```

Total new disk footprint: **~62 GB**. Chroma reuses existing FLUX `ae.safetensors`.
