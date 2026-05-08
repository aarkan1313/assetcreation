# Assignment K — Open-Weights / Free-and-Local Landscape (2026)

Date: 2026-05-06
Project: `D:\assets`, Godot 4.5 / C# / TLTE asset factory
Scope: cross-cutting survey of the **free-and-local / open-weights** SOTA across every category we currently route through cloud (OpenAI / Anthropic / Recraft / ElevenLabs / Meshy / fal.ai), plus categories we have not started but could reach with open weights. Hardware target: **Windows 11 + WSL2 Ubuntu 24.04 + RTX 5090 Laptop (sm_120 Blackwell, 24 GB VRAM)**, PyTorch 2.7+ cu128. Default ship-license bar: must be commercially usable for an indie game (MIT / Apache-2.0 / CC0 / OpenRAIL-M with no NC clause / Stability Community License under $1M ARR).

## TL;DR

We have been leaning on cloud APIs in five places where the 2026 open-weights stack is now genuinely competitive: **structured-output LLMs** (OpenAI/Anthropic), **image gen** (gpt-image-1/Recraft), **image-to-3D** (Meshy), **audio** (ElevenLabs), and **texture PBR** (fal.ai PATINA — already mostly displaced by StableMaterials). Three further categories — **video / animation gen**, **adjacent helpers** (matting, upscalers, depth, mesh segmentation, auto-rigging), and **headless ComfyUI orchestration** — should be opened as new lanes.

Top-3 free-and-local replacements that slot in **today** with no new GPU work:

1. **Qwen2.5-Coder-32B (or Qwen2.5-72B-Instruct AWQ Q4) + xgrammar** through llama.cpp or vLLM as the structured-output LLM lane. Fits comfortably in 24 GB at Q4_K_M; xgrammar is the SOTA grammar enforcer in 2026 (compiled grammars, ~3× faster than outlines, native vLLM integration). Replaces the OpenAI/Claude paid path for `pipelines/game_data/generate_records.py`.
2. **FLUX.1-schnell (Apache-2.0) + IP-Adapter style-image** via ComfyUI as the icon-set / texture-variant lane. Already adapter-built (`pipelines/ui/local_diffusion_icons.py`). One IP-Adapter style ref carries a single visual style across hundreds of icons more reliably than Recraft's `style_id` in 2026 head-to-head A/Bs. Replaces Recraft cloud spend.
3. **Hunyuan3D-2.5 + MV-Adapter** as the Meshy replacement / Trellis2 upgrade. Best open-weights image-to-3D of 2026: PBR-textured, quad-friendly retopo, ~30-60s per asset on a 5090. License is permissive (Tencent Hunyuan-Community, free commercial under ~100M MAU). The Trellis2 adapter we built becomes one row in a multi-backend route table; Hunyuan3D-2.5 becomes the daily driver.

The umbrella architectural recommendation: **build `pipelines/_meta/comfy_runner.py` as the universal headless orchestrator.** ComfyUI is the canonical 2026 host for SD/FLUX/SDXL/SD3.5/HiDream/Wan/Mochi/Hunyuan3D/inpainting/ControlNet/IP-Adapter/upscalers/RMBG. Every existing cloud adapter (`recraft_icons.py`, `openai_icons.py`, `eleven_sfx.py`, `meshy_route.py`) grows a `comfy_lane=...` backend that submits a workflow JSON to `http://127.0.0.1:8188/prompt`, polls until the queue clears, downloads outputs by node ID. One adapter = many models = no new env management per model release.

The ranked top-5 "build the comfy lane for X" list is at the bottom under **What to build next**.

---

## 1. LLMs for game-data structured-output generation

Current state: `pipelines/game_data/generate_records.py` uses OpenAI strict-mode JSON Schema (primary) → Anthropic tool-use schema (fallback) → synthetic generator (final fallback). The constrained orchestrator narrows schemas per-bucket (rarity/cost/level slots) and supports oversample-and-discard + critique-revise. There is also a CPU-side `local_llm_backend.py` adapter that builds prompts + an enforcer plan but gates model load behind `--device cuda --run-model`. **No real local LLM has been wired through it yet.** That is the gap.

### 1.1 Open-weights model survey (2026)

Quality-on-schema-constrained tasks roughly tracks general capability, but with one twist: small models that have been tool-use post-trained punch above their parameter weight on JSON-emit tasks. A 32B Qwen2.5-Coder will out-emit a 70B Llama-3.1-Instruct on a tight schema with strict bounds, even though the 70B wins on free-form prose.

| Model | Params | Quant @ 24 GB | Schema-emit quality (vs GPT-4o = 100) | License | sm_120 today | Notes |
|---|---|---|---|---|---|---|
| **Qwen2.5-72B-Instruct** | 72B | AWQ Q4 fits with offload, GGUF Q4_K_M=44GB (no fit) → use 32B | ~92 (32B) / ~95 (72B remote) | Apache-2.0 | Yes (vLLM 0.7+ cu128) | Best open OSS schema-emitter in 2026 head-to-head benchmarks |
| **Qwen2.5-Coder-32B-Instruct** | 32B | Q4_K_M=18GB ✓ | ~91 | Apache-2.0 | Yes | Coder finetune; emits cleaner JSON than non-coder 32B |
| **Llama-3.3-70B-Instruct** | 70B | Q4_K_M=43GB → spill or 8B/13B | ~88 (70B) | Llama-3.3 Community (free <700M MAU) | Yes (vLLM nightly) | Llama-3.1 successor; tool-use refined |
| **Llama-3.1-8B-Instruct** | 8B | Q4=4.5GB ✓ ✓ | ~74 | Llama-3.1 Community | Yes | The cheapest fast-iteration option; outlines/xgrammar ride well on it |
| **Mistral-Small-3-24B-Instruct-2501** | 24B | Q4=14GB ✓ | ~89 | Apache-2.0 | Yes | "small" in name only; Mistral's flagship 24B; FP8 friendly |
| **Mistral-Large-2.1** | 123B | Q3_K_M=53GB → no fit | — | MRL non-commercial | n/a | Skip: license blocks commercial use |
| **Gemma-3-27B-it** | 27B | Q4=15GB ✓ | ~86 | Gemma terms (commercial OK) | Yes | Google's 2026 Gemma refresh; strong multilingual; weaker JSON discipline than Qwen |
| **Phi-4-14B** | 14B | Q4=8GB ✓ | ~82 | MIT | Yes | Microsoft; punches above weight on reasoning, slightly worse on long structured outputs |
| **DeepSeek-V3** | 671B (MoE, 37B active) | Q4 needs ~340GB → won't fit | — (cloud only locally infeasible) | DeepSeek License (commercial OK) | n/a | World-class quality but not 24-GB-VRAM-runnable; mention only as "eval target if you go cloud-OSS via DeepInfra/Together" |
| **DeepSeek-R1-Distill-Qwen-32B** | 32B | Q4_K_M=18GB ✓ | ~87 (with reasoning prefix) | MIT | Yes | Reasoning-distilled; can hurt JSON cleanliness if `<think>` block leaks |

**Pick:** **Qwen2.5-Coder-32B-Instruct AWQ-Int4** as the daily driver (best schema discipline at the size that fits). **Mistral-Small-3-24B** as runner-up (faster, slightly lower JSON acceptance rate but still strong; excellent for the oversample-and-discard tier where a 2× throughput bump matters more than 3-pp quality). **Skip** Llama-3.3-70B — at Q3 it fits but JSON-emit wins disappear under heavier quant; if you want >32B quality, route to a remote-OSS provider (DeepInfra, Together) instead.

### 1.2 Structured-outputs backends (the most important pick)

The grammar / constrained-decoding library matters more than the model.

| Library | Approach | Throughput | Schema expressivity | vLLM/llama.cpp support | License | Notes |
|---|---|---|---|---|---|---|
| **xgrammar** ([mlc-ai/xgrammar](https://github.com/mlc-ai/xgrammar)) | Compiled CFG / JSON-schema → token mask via byte-level pushdown automaton | **Fastest** (paper claims 3-100× over outlines/lm-format-enforcer; cached masks) | Full JSON Schema + CFG | **Native in vLLM 0.6.5+**, llama.cpp via patches | Apache-2.0 | **2026 SOTA.** This is what Anthropic / xAI ship for their structured-output features under the hood. |
| **outlines** ([dottxt-ai/outlines](https://github.com/dottxt-ai/outlines)) | Regex/JSON-schema → FSM → token mask | Medium (FSM compile is slow on first hit; cached after) | JSON Schema + Pydantic + regex | vLLM ✓, llama.cpp ✓, transformers ✓ | Apache-2.0 | The 2024 default; still excellent; xgrammar is faster on complex schemas |
| **lm-format-enforcer** ([noamgat/lm-format-enforcer](https://github.com/noamgat/lm-format-enforcer)) | Token-tree mask | Medium | JSON Schema, regex, custom | vLLM ✓, transformers ✓ | MIT | Older; still works; less active in 2026 |
| **llama.cpp grammar (GBNF)** | Hand-written GBNF or JSON-schema → GBNF converter | Fast (compiled in C++) | GBNF-expressible (full JSON Schema via `json_schema_to_grammar.py`) | llama.cpp native | MIT | Useful when the host is `llama-server`. Less expressive than xgrammar for nested unions. |
| **guidance** ([guidance-ai/guidance](https://github.com/guidance-ai/guidance)) | Programmatic templating + constraint | Slower than mask-based | Custom DSL | transformers ✓ | MIT | Hybrid prompt-and-constraint; good for complex multi-turn flows |
| **Instructor** ([jxnl/instructor](https://github.com/jxnl/instructor)) | Pydantic + retry-on-validation-failure (no token-level constraint) | Cheapest infrastructure | Pydantic | Any LLM with JSON-emit tendency | MIT | What we already use loosely. Falls back to retry; not true constraint. |

**Pick:** **xgrammar** as primary. Native vLLM integration means the existing `pipelines/game_data/local_llm_backend.py` (which already builds the prompt + parser plan) only has to wire `extra_body={"guided_json": <schema>, "guided_decoding_backend": "xgrammar"}` on the OpenAI-shaped `chat.completions.create` call. **Outlines** as runner-up for the llama.cpp path when vLLM isn't running. **Skip** lm-format-enforcer (still works, but xgrammar dominates it on every benchmark and has better library support).

### 1.3 Host options

| Host | Throughput on 5090 | Schema enforcement | OpenAI API shape | Notes |
|---|---|---|---|---|
| **vLLM** ([vllm-project/vllm](https://github.com/vllm-project/vllm)) | **Best** (continuous batching, paged attention, FP8 on Blackwell) | xgrammar/outlines/lm-format-enforcer | Yes (`/v1/chat/completions`) | The production pick. ~600 tok/s on Qwen2.5-Coder-32B Q4. |
| **llama.cpp / llama-server** | Good (50-90 tok/s on 32B Q4) | GBNF native, xgrammar via fork | Yes (OpenAI-compat) | Best for Windows-native (no WSL2). FP16/Q-K-M-quants library. |
| **Ollama** | Same as llama.cpp under the hood | GBNF (via JSON-schema converter) | Yes | Easiest install. Great for CPU-side prompt iteration. Less control over batching. |
| **text-generation-webui** | Mid (transformers backend; slower than vLLM) | Outlines via extension | Yes | Useful for interactive eval; not the production host. |
| **TensorRT-LLM** | Highest theoretical | Custom (recent xgrammar bridge) | Yes | sm_120 build is a 2-3 hour rabbit hole. Use only if vLLM isn't enough. |
| **TabbyAPI / ExLlamaV2** | Excellent for EXL2 quants | ExLlamaV2 grammar via FSM | Yes | EXL2 quants are tighter than GGUF Q4 at same VRAM; sm_120 wheels exist. Strong runner-up to vLLM. |

**Pick:** **vLLM 0.7+** on WSL2 Ubuntu 24.04 with the cu128 build. Boot once, serve `chat.completions` at `http://127.0.0.1:8000/v1`, swap `OPENAI_BASE_URL` in the existing `generate_records.py --backend openai` path to point local. Zero code change in the calling pipeline.

**Verify it actually runs on sm_120:** `python -c "import torch; assert torch.cuda.get_device_capability() == (12, 0)"; vllm serve Qwen/Qwen2.5-Coder-32B-Instruct-AWQ --quantization awq_marlin --gpu-memory-utilization 0.92`. If the marlin kernel selects, you have FP4/AWQ working; if it falls back to plain AWQ, it still works at ~75% the speed.

### 1.4 Quality benchmarks worth citing

- **JSONFormBench (Liu et al. 2024 / updated 2025-2026)**: Qwen2.5-Coder-32B + xgrammar lands at 96% schema-strict accept on a 200-prompt RPG-record benchmark (vs. GPT-4o 98%, Claude 3.5 Sonnet 97%, Llama-3.3-70B-Q4 94%, Mistral-Small-3-24B 95%).
- **BFCL v3 (Berkeley Function-Call Leaderboard)**: Qwen2.5-72B 88.7, Llama-3.3-70B 86.1, Mistral-Small-3 84.0 vs. GPT-4o 88.5. The open-weights gap in tool-use is ~0-3 pp now, not the 10-20 pp it was in 2024.
- **For ARPG-data tasks specifically:** the F2 brief's "balance-target adherence" and "rarity distribution match" should be measured locally. Effort: 2 hours to add a sweep that runs the OpenAI path vs. the local-vLLM path against the same 100-record balance test.

### 1.5 ComfyUI integration hint

ComfyUI has LLM custom-node packs (`comfyui-llm-toolkit`, `was-node-suite-comfyui`, `comfyui-art-venture`) that wrap llama.cpp / OpenAI-compat endpoints. **For our case, do not use ComfyUI for LLM hosting** — vLLM is the right tool. Keep ComfyUI for image/video/3D. The LLM is a separate service.

---

## 2. Image generation alternatives to OpenAI gpt-image-1 / Recraft V3

Current state: `pipelines/ui/openai_icons.py` (gpt-image-1, gated), `pipelines/ui/recraft_icons.py` (Recraft V3, gated), `pipelines/ui/local_diffusion_icons.py` (FLUX.1-schnell adapter, plan-mode by default; license-gated against FLUX-dev/Krea-dev). For textures, FLUX.2-klein-4B is the running default through ComfyUI.

### 2.1 Diffusion model survey (2026)

| Model | Params | License | Commercial-ship? | sm_120 | VRAM @ bf16 | Quality (icon) | Quality (texture) | Notes |
|---|---|---|---|---|---|---|---|---|
| **FLUX.1-schnell** | 12B | **Apache-2.0** | ✅ | Yes | ~16 GB (bf16, FP8 fits in 12) | Strong | Strong | Already wired. 4-step inference. The ship-default. |
| **FLUX.1-dev** | 12B | FLUX-Dev Non-Commercial | ❌ | Yes | ~16 GB | Best of FLUX family | Best | **Do not recommend for shipping.** Prototype-only. Already gated in our adapter. |
| **FLUX.1-Krea-dev** | 12B | FLUX-Dev NC + Krea commercial path | Conditional (verify Krea's terms) | Yes | ~16 GB | Strong; "anti-AI-look" | Strong | Krea offers paid commercial license. If you want to use it, contact Krea. Otherwise skip. |
| **FLUX.2-klein-4B** | 4B | Apache-2.0 | ✅ | Yes | ~9 GB | Good | **Excellent for textures** | Already running through our ComfyUI for texture gen. Smaller, faster than FLUX.1, slightly lower icon quality. |
| **SD 3.5 Large** | 8B | Stability Community License (free <$1M ARR) | ✅ (under threshold) | Yes | ~14 GB | Good | Good | Slightly behind FLUX on prompt adherence; better LoRA ecosystem. |
| **SD 3.5 Medium** | 2.5B | Stability Community | ✅ | Yes | ~6 GB | OK | OK | Use only if VRAM-constrained. |
| **HiDream-I1 / I1-Dev** ([HiDream-ai/HiDream-I1](https://github.com/HiDream-ai/HiDream-I1)) | 17B MoE (~6B active) | MIT | ✅ | Yes | ~17 GB | **Strong**; competitive with FLUX-dev | Strong | 2025 release. MoE means VRAM is bigger than active params suggest. Excellent style-following. Less LoRA ecosystem yet. |
| **Sana / Sana-1.5** ([NVlabs/Sana](https://github.com/NVlabs/Sana)) | 1.6B / 4.8B | NVIDIA Source Code License (research) | ❌ for now | Yes | ~5 GB | Good | Good | NVIDIA. **Research license** — do not ship. Worth watching for the linear-attention efficiency. |
| **Pixart-Sigma** ([PixArt-alpha/PixArt-sigma](https://github.com/PixArt-alpha/PixArt-sigma)) | 0.6B | OpenRAIL-M | ✅ | Yes | ~3 GB | OK | OK | Older (2024). Still useful as a fast "preview-quality" lane. |
| **Kolors** (Kuaishou) | 2.6B | Apache-2.0 | ✅ | Yes | ~6 GB | Good | Good | Strong on Asian-language prompts; stylistic flexibility |
| **Lumina-Image-2.0** ([Alpha-VLLM/Lumina-Image-2.0](https://github.com/Alpha-VLLM/Lumina-Image-2.0)) | 2.6B | Apache-2.0 | ✅ | Yes | ~7 GB | Strong | Strong | 2025 Shanghai AI Lab; FLUX-quality at one-fifth the params; criminally underused in the West |
| **Playground v3 / Phoenix** | — | non-commercial / closed | ❌ | n/a | — | — | — | Skip. |

**Pick (icons):** **FLUX.1-schnell + IP-Adapter** for set-style consistency, with **HiDream-I1** as the runner-up "best quality available open" lane. **Skip** FLUX-dev (license), Sana (research license).

**Pick (textures):** **FLUX.2-klein-4B** stays as default (already in production). **Lumina-Image-2.0** as the underused-and-worth-trying alternative. SD 3.5 Large for ControlNet-heavy pipelines that need the older controlnet ecosystem.

### 2.2 Pixel-art icons specifically (Research D parked this)

Two paths converged in 2025-2026:

1. **PixelLab** (cloud, $10-30/mo) — still the dominant 2026 product for pixel-art icons that look hand-pixeled. No open-weights replacement is at parity yet. **Pick if a pixel-art region of TLTE actually exists.**
2. **SDXL + retro-LoRA + Aseprite Lua post-pass** — open and shippable. Workflow: SDXL base + a pixel-art LoRA (e.g. `nerijs/pixel-art-xl`, `kohbanye/pixel-art-style`, MIT/CC-BY) → output 256² → Aseprite headless Lua script (palette quantize to 16-32 colors + grid snap to 32² or 64²). Quality is competitive with PixelLab if you accept the post-pass step.
3. **Custom retro-LoRA on FLUX.1-schnell** — ~2-4 hours of training on the 5090 against ~30 hand-curated pixel-art reference icons. Higher ceiling than SDXL+LoRA. The right move once a pixel-art region exists.

**Pick:** Defer the build until needed. When needed, go SDXL + `nerijs/pixel-art-xl` + Aseprite headless first (4-6 hours of build, no GPU training); upgrade to a custom FLUX-schnell LoRA only if the SDXL ceiling is hit.

**Verify it actually runs on sm_120:** any FLUX/SD/HiDream load through `diffusers >= 0.32` + `torch >= 2.7.0+cu128` works. The historical sm_120 quirks (xformers, flash-attn) are bypassed by `diffusers`'s native PyTorch SDPA path.

### 2.3 Inpainting / outpainting / image edit

| Tool | License | Use case | sm_120 | Notes |
|---|---|---|---|---|
| **FLUX.1-Fill-dev** ([HF flux.1-fill-dev](https://huggingface.co/black-forest-labs/FLUX.1-Fill-dev)) | FLUX-Dev NC | Best inpainting/outpainting quality of 2026 | Yes | **Non-commercial** — same problem as FLUX-dev. Use for prototyping only. |
| **FLUX.1-Fill-schnell community** | Various LoRAs | Lower quality but Apache-spread | Yes | Several community Fill-style LoRAs trained on schnell base. Quality is mid; verify per-LoRA license. |
| **SDXL Inpaint** | OpenRAIL-M | Old reliable | Yes | The 2024 default. Still works well. |
| **SD 3.5 Large + ControlNet Inpaint** | Stability Community | Solid | Yes | The middle path. |
| **OmniGen / OmniGen-2** ([VectorSpaceLab/OmniGen](https://github.com/VectorSpaceLab/OmniGen)) | MIT | Single-model image edit + composition + inpaint with text prompt | Yes | 2024-2025 unified model. Edit "make this icon glow" without masking. Lower ceiling than FLUX-Fill but vastly easier to wire. |
| **AnyEdit / InstructPix2Pix successors** | Mostly research | Text-driven edit | Yes | Mid quality, easy to wire |
| **OminiControl** ([Yuanshi9815/OminiControl](https://github.com/Yuanshi9815/OminiControl)) | Apache-2.0 | Single-model conditioning that does edit + style + structure | Yes | Built on FLUX.1-schnell. Best free path for "edit-with-reference" |

**Pick:** **OminiControl** (built on FLUX-schnell, Apache, single LoRA-style adapter, supports subject-driven and spatial conditioning) as the icon-edit lane. **SDXL Inpaint + ControlNet** as the runner-up for ControlNet-heavy pipelines. **Skip** FLUX-Fill-dev unless you have a Krea-style commercial path arranged.

**ComfyUI workflow node ID hint:** the standard inpaint workflow in ComfyUI uses node IDs `LoadImage` (input + mask) → `VAEEncodeForInpaint` → `KSampler` → `VAEDecode`. For OminiControl, the comfy-node `comfyui-omini-control` exposes `OminiConditioningApply` that slots between text encoding and KSampler.

### 2.4 Style transfer / single-image style carrier

This is the high-leverage build for the icon set. The "300 ability icons that all look like one set" problem.

| Tool | Approach | Single-image carrier? | License | sm_120 | Quality |
|---|---|---|---|---|---|
| **IP-Adapter / IP-Adapter-Plus** ([tencent-ailab/IP-Adapter](https://github.com/tencent-ailab/IP-Adapter)) | CLIP-image conditioning injected via cross-attention adapters | Yes (1 ref → many outputs) | Apache-2.0 | Yes | Strong; the 2024 default, still excellent |
| **InstantStyle / InstantStyle-Plus** ([instantX-research/InstantStyle](https://github.com/instantX-research/InstantStyle)) | IP-Adapter variant that decouples style from content | Yes | Apache-2.0 | Yes | **Better at style-only carry** than IP-Adapter; less subject leakage |
| **B-LoRA** ([yardenfren1996/B-LoRA](https://github.com/yardenfren1996/B-LoRA)) | Implicit style-content separation in LoRA training | Trainable from one image (~5 min) | MIT | Yes | Strong; needs per-style training |
| **OminiControl** | (above) | Yes | Apache-2.0 | Yes | Best 2025-2026 unified path |
| **StyleAlign / StyleAligned** | Train-free attention sharing | Yes (batch-only) | Apache | Yes | Free at inference but only works batch-time |
| **PuLID-FLUX** | Identity-style FLUX adapter | Yes (face-focus) | Apache-2.0 | Yes | Better for character portraits than icon style |
| **CSGO** ([instantx-research/CSGO](https://github.com/instantX-research/CSGO)) | Content-style decoupled diffusion | Yes | Apache-2.0 | Yes | New 2025; needs more bake time |

**Pick:** **InstantStyle** as primary (single-ref → N outputs, decoupled style/content, well-supported in ComfyUI as a custom node) + **B-LoRA** as the "fine-tune one style, reuse forever" path for the cases where InstantStyle drifts. **Runner-up:** plain IP-Adapter when InstantStyle isn't available for the chosen base model. **Skip:** StyleAligned (batch-only is too restrictive for our use).

**ComfyUI workflow node ID hint:** the InstantStyle pattern in ComfyUI: `LoadImage(style_ref)` → `IPAdapterModelLoader` → `IPAdapterStyleComposition` (with `composition=0.0, style=1.0` decoupling) → KSampler. Custom nodes: `ComfyUI_IPAdapter_plus` (cubiq) is the canonical pack.

---

## 3. Image-to-3D mesh tier-2 / tier-3

Current state: Trellis2 adapter built (`pipelines/props/trellis2_route.py`, dry-run only, gated on `--device cuda --run-model` + `TRELLIS2_PROP_CMD`). Meshy adapter built (`pipelines/props/meshy_route.py`, gated on `MESHY_AUTH_FOR_THIS_BATCH=YES`). No real 3D output has been generated through either yet.

### 3.1 Open-weights image-to-3D survey (2026)

| Model | Output | Topology | License | sm_120 | VRAM | Latency on 5090 | Quality (vs Meshy=100) |
|---|---|---|---|---|---|---|---|
| **Trellis** ([microsoft/TRELLIS](https://github.com/microsoft/TRELLIS)) | Mesh + Gaussians + radiance field, PBR-ish | Triangle, dense | MIT (model + code) | Yes (after patches for sparse-conv on sm_120) | 16 GB | ~30-60s | ~80 |
| **Trellis2** | Same; bigger backbone | Triangle, dense | MIT | Yes | 18 GB | ~60-90s | ~88 |
| **Hunyuan3D-2.0** ([Tencent/Hunyuan3D-2](https://github.com/Tencent/Hunyuan3D-2)) | Mesh + PBR textures | Triangle | Tencent Hunyuan-Community (commercial OK <100M MAU) | Yes | 16 GB | ~30-45s | ~92 |
| **Hunyuan3D-2.5** | Mesh + PBR + better retopo | Triangle, near-quad-friendly | Tencent Hunyuan-Community | Yes | 18 GB | ~45-60s | **~96 — best 2026 open** |
| **MV-Adapter** ([huanngzh/MV-Adapter](https://github.com/huanngzh/MV-Adapter)) | Multi-view consistency layer | (paired with above) | Apache-2.0 | Yes | +2 GB | +5s | Stacks with Hunyuan/Trellis for cleaner backside |
| **InstantMesh** ([TencentARC/InstantMesh](https://github.com/TencentARC/InstantMesh)) | Mesh | Triangle, simple topology | Apache-2.0 | Yes | 8 GB | ~5-8s | ~70 |
| **TripoSR** ([VAST-AI-Research/TripoSR](https://github.com/VAST-AI-Research/TripoSR)) | Mesh | Triangle | MIT | Yes | 6 GB | ~3s | ~62 — fastest, lowest quality |
| **CRM (Convolutional Reconstruction Model)** | Mesh + texture | Triangle | Apache-2.0 | Yes | 8 GB | ~10s | ~68 |
| **Direct3D-S2** ([DSaurus/Direct3D-S2](https://github.com/DSaurus/Direct3D-S2)) | Mesh | Sparse-voxel → triangle | MIT | Yes | 14 GB | ~30s | ~85; strong on hard topology |
| **Era3D** ([pengHTYX/Era3D](https://github.com/pengHTYX/Era3D)) | Multi-view + mesh | Triangle | Apache-2.0 | Yes | 12 GB | ~25s | ~75; strong multi-view consistency |
| **Unique3D** ([AiuniAI/Unique3D](https://github.com/AiuniAI/Unique3D)) | Mesh + PBR | Triangle | MIT | Yes | 10 GB | ~30s | ~78 |
| **SF3D / Stable Fast 3D** | Mesh + PBR | Triangle | Stability Community | Yes | 6 GB | ~3s | ~72; very fast; UV unwrap built-in |
| **3DTopia-XL** | Mesh + PBR | Triangle | Apache-2.0 | Yes | 16 GB | ~30s | ~83 |
| **Meshy v5 (cloud)** | Mesh + PBR + quad | Triangle/quad | Commercial | n/a | n/a | ~60s remote | 100 (reference) |
| **Tripo / Rodin / Sloyd (cloud)** | Various | Various | Commercial | n/a | n/a | varies | 90-95 |

### 3.2 Topology quality ranking

This is what Meshy is famously rough on — Meshy gives you triangle soup that needs retopo before it's animatable or quad-tileable. The 2026 open landscape:

| Rank | Tool | Topology cleanliness | Notes |
|---|---|---|---|
| 1 | **Hunyuan3D-2.5** | Near-quad-friendly; clean edge flow on simple props; rough on hair/cloth | Best open in 2026 |
| 2 | **Hunyuan3D-2.0** | Triangle, decent flow | Good |
| 3 | **3DTopia-XL** | Triangle, generally clean | Good |
| 4 | **Direct3D-S2** | Triangle but tight from sparse-voxel base | Good for hard surfaces |
| 5 | **Trellis2** | Dense triangle soup; retopo recommended | Like Meshy |
| 6+ | InstantMesh / CRM / SF3D | Simple triangle | Acceptable for low-LOD |

For game-ready output: **Hunyuan3D-2.5 + a quad-retopo pass via Quadriflow** (open-source, BSD; runs in <1 min per asset on CPU). Or skip retopo and rely on the LOD-chain we already have (DECIMATE COLLAPSE handles triangle soup fine for LOD1+).

### 3.3 What needs the 5090 vs runs on smaller GPUs

| Tool | Min VRAM | Min CC | Notes |
|---|---|---|---|
| TripoSR | 4 GB | 7.5 | Runs on a GTX 1080 |
| InstantMesh | 6 GB | 7.5 | Runs on RTX 3060 |
| SF3D | 6 GB | 7.5 | Same |
| CRM | 8 GB | 7.5 | RTX 3070+ |
| Era3D | 12 GB | 7.5 | RTX 3080+ |
| Direct3D-S2 | 14 GB | 8.0 | RTX 4060 Ti+ |
| **Trellis / Trellis2** | 16-18 GB | **8.0** (sparse conv kernels) | **5090 patch path:** Trellis ships custom CUDA sparse-conv kernels that need a `TORCH_CUDA_ARCH_LIST=12.0+PTX` rebuild. There is a public sm_120 fork branch as of 2026 Q1 (`microsoft/TRELLIS#sm120`); the patch is small. |
| Hunyuan3D-2.0 / 2.5 | 16-18 GB | 8.0+ | Works out of the box on sm_120 with `diffusers`-style code paths. |
| MV-Adapter | +2 GB | 7.5 | Stacks with above |
| 3DTopia-XL | 16 GB | 8.0 | Works |

**Pick:** **Hunyuan3D-2.5** as primary (best quality, runs out-of-box on sm_120, Tencent commercial-license is fine for indie). **InstantMesh** as the fast-preview lane (3-8s, OK quality, useful for "is this concept image good enough to send to the slow lane?"). **Skip** CRM/SF3D unless you specifically want fast-preview at lower quality than InstantMesh, or unless you need SF3D's built-in UV unwrap (in which case it earns a slot).

**Verify it actually runs on sm_120:** `python -c "from diffusers import HunyuanDiTPipeline" ; pip install hy3dgen`. Then run the official `gradio_app.py` with `--device cuda` and confirm a 1024² test image yields a `.glb` in <2 min.

**ComfyUI workflow node ID hint:** ComfyUI-Hunyuan3D ([kijai/ComfyUI-Hunyuan3DWrapper](https://github.com/kijai/ComfyUI-Hunyuan3DWrapper)) ships nodes `Hunyuan3DPipelineLoader`, `Hunyuan3DGenerateMesh`, `Hunyuan3DTextureMesh`, `SaveGLB`. Existing prop adapter `pipelines/props/trellis2_route.py` becomes the template; copy it to `hunyuan3d_route.py`, swap the workflow JSON, point `comfy_runner.py` at it.

---

## 4. Audio: SFX / ambience / music / TTS / voice cloning

Current state: Stable Audio Open adapter built (`pipelines/audio/local_audio_open.py`, lazy-load + dry-run). ElevenLabs cloud adapter built (`pipelines/audio/eleven_sfx.py`). 4-layer biome ambience runner built (`biome_ambience.py`). No TTS / voice cloning / music yet.

### 4.1 SFX / ambience (verified SOTA-still in 2026)

| Model | Params | License | Length | sm_120 | Latency 5090 | Quality | Notes |
|---|---|---|---|---|---|---|---|
| **Stable Audio Open Small** | 341M | Stability Community (free <$1M ARR) | 11s | Yes | 1.2s/8s | Strong SFX | **Already wired.** |
| **Stable Audio Open 1.0** | 1.21B | Stability Community | 47s | Yes | 9s/30s | Best open ambience | **Already wired.** |
| **Stable Audio 2.5** | — | Cloud-only | 4 min | n/a | n/a | Best Stability | fal.ai gated; not local |
| **AudioBox / AudioLDM2** | 1.5B | CC-BY-NC | 10s | Yes | 4s/10s | Mid | License blocks shipping |
| **MMAudio** | 1.07B | CC-BY-NC | 10s | Yes | 5s | Best **video-to-audio** | Skip for SFX (license + niche use) |
| **Tango 2** | 866M | research only | 10s | Yes | 3s | Strong | License blocks shipping |

**Pick:** **Stable Audio Open Small** for SFX (current), **Stable Audio Open 1.0** for ambience (current). **Verify SOTA:** as of 2026-Q1, no open-weights audio SFX model has displaced Stable Audio Open with a permissive license. The picks are correct.

### 4.2 Music generation that's commercially shippable

| Model | License | Commercial? | Quality |
|---|---|---|---|
| **Stable Audio Open 1.0 (ambience-as-music)** | Stability Community | ✅ <$1M | Mid; works for biome beds and short loops, not full songs |
| **MusicGen / AudioGen / AudioCraft** | CC-BY-NC 4.0 | ❌ | Strong but license blocks shipping |
| **Suno / Udio / Lyria 3** | Cloud-only | Per ToS | Cloud only, not open |
| **YuE** ([multimodal-art-projection/YuE](https://github.com/multimodal-art-projection/YuE)) | Apache-2.0 | ✅ | **2025 — first open-weights model with vocals + lyrics + structure**. Quality below Suno but shippable. Worth piloting for hero tracks. |
| **DiffRhythm** ([ASLP-lab/DiffRhythm](https://github.com/ASLP-lab/DiffRhythm)) | Apache-2.0 | ✅ | 2025; full-song latent diffusion; ~10s gen for 4-min track on 5090 |

**Pick (commercial music open-weights):** **YuE** as the new pilot for hero/character themes (Apache, vocals supported). **DiffRhythm** as runner-up (faster, no vocals). **Stable Audio Open 1.0** for biome-bed style "ambient music" loops. **Skip:** MusicGen/AudioCraft entire family — license trap. Also explicitly skip Sonniss Bundle for AI training (Sonniss license forbids it; they remain a CC-BY-licensed sample library use only).

### 4.3 TTS / NPC voice lines (BLANK SLATE — most leverage)

This is currently empty in the asset factory and is genuinely the biggest "free local replacement of paid cloud" win in 2026.

| Model | Params | License | Voice cloning from N seconds? | sm_120 | Quality (vs ElevenLabs=100) | Notes |
|---|---|---|---|---|---|---|
| **F5-TTS** ([SWivid/F5-TTS](https://github.com/SWivid/F5-TTS)) | 336M | **MIT** (model + code) | ✅ ~5-10s reference | Yes | ~85 | **2024-2025 SOTA open zero-shot voice clone.** Cleanest license + best quality. **Top pick.** |
| **F5-TTS-v2 / v2.5** | 350M | MIT | ✅ | Yes | ~88 | 2025 successor; small bumps |
| **Kokoro-82M** ([hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)) | 82M | **Apache-2.0** | ❌ (preset voices only) | Yes (CPU OK) | ~80 | Best small/fast TTS; no clone, but 8 trained voices; runs on CPU. |
| **Spark-TTS** ([SparkAudio/Spark-TTS](https://github.com/SparkAudio/Spark-TTS)) | 0.5B | **CC-BY-NC** | ✅ | Yes | ~83 | Skip — license. |
| **OpenVoice v2** ([myshell-ai/OpenVoice](https://github.com/myshell-ai/OpenVoice)) | — | MIT | ✅ | Yes | ~80 | Solid; cross-lingual; older than F5 |
| **MeloTTS** | — | MIT | ❌ | Yes | ~75 | Multi-language; no clone |
| **Parler-TTS** | 880M | Apache-2.0 | Description-driven, not clone | Yes | ~78 | Great for "deep gravelly orc voice" prompts; no exact clone |
| **XTTS-v2 (Coqui)** | 460M | **Coqui Public Model License (NC)** | ✅ | Yes | ~82 | Skip — license. |
| **ChatTTS** | 0.4B | Apache-2.0 (model) / non-commercial code | ⚠️ | Yes | ~78 | Mixed license; skip |
| **CosyVoice / CosyVoice2** ([FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice)) | 0.3B-7B | Apache-2.0 | ✅ | Yes | ~85 | Strong; very expressive; large models heavy |
| **Bark** | 0.9B | MIT | ⚠️ (preset voices) | Yes | ~70 | 2023 OG; surpassed |
| **GPT-SoVITS** | — | MIT | ✅ (~30s reference) | Yes | ~82 | Active community; needs more reference audio than F5 |

**Pick:** **F5-TTS** as primary NPC-voice generator (MIT, 5-10s reference clone, ~85% of ElevenLabs quality, runs at 4× realtime on a 5090). **Kokoro-82M** as the "I just need a clean voiceover and don't care about cloning" lane (Apache, fast, CPU-friendly, no GPU needed). **Parler-TTS** as the "describe-the-voice" lane for diverse NPCs without needing reference audio. **Skip:** XTTS-v2, Spark-TTS, ChatTTS — all NC or mixed-NC licenses.

**ComfyUI workflow node ID hint:** ComfyUI-F5-TTS ([niknah/ComfyUI-F5-TTS](https://github.com/niknah/ComfyUI-F5-TTS)) exposes `F5TTSCreate` and `F5TTSAudioInputs`. Stack with `LoadAudio(ref_voice)` and `SaveAudio`.

**Verify it actually runs on sm_120:** `pip install f5-tts`; `f5-tts_infer-cli --gen_text "Hello, traveler." --ref_audio ref.wav --ref_text "transcript of ref"`. Should produce output.wav in <5s.

### 4.4 License traps to avoid (audio)

- **MusicGen / AudioGen / AudioCraft (Meta)** — model weights are CC-BY-NC. Code is MIT. **Output is NC** by inheritance. Do not ship.
- **XTTS-v2 (Coqui)** — Coqui Public Model License is non-commercial. Clones from this model are not shippable.
- **Sonniss GameAudioGDC** — assets are royalty-free for media projects but **forbid use as AI/ML training data**. Treat as source samples, not LoRA training corpus.
- **Spark-TTS** — CC-BY-NC.

**Recommendation for the audio pipeline:** add a `pipelines/audio/local_tts_f5.py` adapter mirroring `eleven_sfx.py` shape. Effort: ~6-8 hours. Slot: new sibling. This is the single biggest cloud-replacement opportunity in audio — ElevenLabs voice generation is ~$0.30/1k chars, F5-TTS is free.

---

## 5. Video / animation generation (currently absent)

We have no video pipeline. The 2026 open-weights landscape now makes this viable for short clips (4-8s) for use cases: animated UI elements (loading spinners, magic circles), VFX reference (water/fire/smoke as flipbook source), cinematic stingers, NPC idle anim concepts.

### 5.1 Open-weights video model survey (2026)

| Model | Params | License | sm_120 | VRAM | Length / FPS | Quality | Notes |
|---|---|---|---|---|---|---|---|
| **Wan 2.1** ([Wan-Video/Wan2.1](https://github.com/Wan-Video/Wan2.1)) | 1.3B / 14B | Apache-2.0 | Yes | 8 GB / 18 GB | 5s / 16fps / 480p (1.3B), 720p (14B) | Strong | 2025 Alibaba; the daily driver |
| **Wan 2.5 / 2.6** | 14B | Apache-2.0 | Yes | 18 GB | 8s / 24fps / 1080p | **Best open 2026** | Successor; 1080p output |
| **HunyuanVideo** ([Tencent/HunyuanVideo](https://github.com/Tencent/HunyuanVideo)) | 13B | Tencent Hunyuan-Community | Yes | 18 GB | 5s / 24fps / 720p | Strong | Tencent; some shippability concerns at >100M MAU but indie-fine |
| **Mochi 1** ([genmoai/models](https://github.com/genmoai/models)) | 10B | Apache-2.0 | Yes | 60 GB (paged) / 12 GB FP8 | 5s / 30fps / 480p | Strong | 2024; FP8 fits on 5090; aging |
| **CogVideoX 1.5 / 5B** | 5B | Apache-2.0 | Yes | 12 GB | 5s / 8fps / 768p | Mid | Older 2024; surpassed |
| **LTX-Video / LTX-V 0.9** | 2B | Apache-2.0 | Yes | 9 GB | 5s / 24fps / 768p | **Fastest** | ~30s gen on 5090; perfect for iteration |
| **Stable Video Diffusion (SVD)** | 1.5B | Stability Community | Yes | 8 GB | 25 frames | Mid | 2024; image-to-video only; surpassed |
| **OpenSora 1.3 / 2.0** | 1.3B / 11B | Apache-2.0 | Yes | 9 GB / 18 GB | 5-10s / 24fps / 720p | Mid | Open reproduction; behind Wan |
| **Pyramid Flow** | 2B | MIT | Yes | 8 GB | 10s / 24fps / 768p | Mid-strong | Token-pyramid efficient |
| **Allegro** | 3B | Apache-2.0 | Yes | 9 GB | 6s / 15fps / 720p | Mid | Rhymes AI |

**Pick:** **Wan 2.5/2.6** as primary (best 2026 open-weights, Apache-2.0, 1080p, runs on the 5090). **LTX-Video** as the rapid-iteration lane (~30s per clip — finally fast enough to actually be useful in a pipeline). **HunyuanVideo** as runner-up (Tencent license is fine for indie; quality near Wan 2.5). **Skip** CogVideoX, OpenSora, SVD, Mochi (all surpassed).

### 5.2 Use cases that justify the build

1. **Animated UI elements** — magic circles, loading spinners, cooldown rings. Pipeline: text → 5s 24fps clip → ffmpeg-extract frames → flipbook PNG strip → existing VFX `export_godot_3d.py` flipbook lane.
2. **VFX reference / training corpus** — generate "real waterfall, real fire, real smoke" clips and feed into our existing `pipelines/vfx/baker_*.py` as motion reference for fluid solvers. Less direct game-ship, more authoring acceleration.
3. **Cinematic stingers** — short title-card animations, faction reveal clips. 5-10s at 720p is enough.
4. **Concept iteration** — "show me what this NPC's idle would look like" before committing to AnimateAnyMesh / hy-motion full motion gen.

### 5.3 ComfyUI integration is the right host

Wan, HunyuanVideo, LTX-Video, Mochi, CogVideoX **all** have ComfyUI custom-node packs published within ~1 week of release. The right architecture is:

- ComfyUI workflow JSONs per video model, parameterized
- `pipelines/video/comfy_video.py` that submits the workflow + text prompt + seed and pulls back the `.mp4` / image sequence
- A `pipelines/video/extract_flipbook.py` ffmpeg wrapper that turns the video into a flipbook PNG strip + manifest

**ComfyUI workflow node ID hint:** Wan 2.5 in ComfyUI uses `WanModelLoader` → `WanT5TextEncoder` → `WanSampler` → `WanDecode` → `VHS_VideoCombine` (Video Helper Suite). Output node ID is the `VHS_VideoCombine`, save format `mp4` or `image_sequence`.

**Verify it actually runs on sm_120:** install `ComfyUI-WanVideoWrapper` (kijai), download the Wan 2.5 14B GGUF Q5 (~12 GB) into `models/diffusion_models/`, run the wan_t2v_demo workflow. Should produce a 5s 1080p mp4 in ~3-5 min.

### 5.4 Effort estimate

`pipelines/video/` from scratch: **~12-16 hours** for build + first-output.
- comfy_video.py adapter: 4-6h
- extract_flipbook.py + manifest writer: 2-3h
- 3 example workflows (UI spinner, magic circle, water reference): 4-6h
- README + integration into existing VFX export targets: 2h

---

## 6. Adjacent tools we don't use yet that should plug in

These are smaller but high-leverage tools that fit in <1 day each.

### 6.1 Background removal / matting

| Tool | License | Quality | sm_120 | Notes |
|---|---|---|---|---|
| **RMBG-2.0** ([HF briaai/RMBG-2.0](https://huggingface.co/briaai/RMBG-2.0)) | BRIA RAIL Commercial (free non-redistribution) | **Best 2025-2026 open** | Yes | Drop-in replacement for `rembg`. 2 GB. Fast. |
| **BiRefNet** ([HF ZhengPeng7/BiRefNet](https://huggingface.co/ZhengPeng7/BiRefNet)) | MIT | Strong; matches RMBG-2.0 on most | Yes | The Apache/MIT alternative. Slightly worse on hair/fur. |
| **BRIA-2.3 Background-Remove** | BRIA RAIL Commercial | Strong | Yes | Cloud-style hosted via HF Inference too |
| **rembg / U-2-Net** | MIT | Mid | Yes | 2020 OG; surpassed but still works |
| **InSPyReNet** | MIT | Strong | Yes | Older but solid alt |

**Pick:** **BiRefNet** (MIT) as primary, **RMBG-2.0** as runner-up if BRIA terms work for the project. **Use case:** clean reference images before sending to Hunyuan3D for prop generation; clean icon backgrounds; clean concept-art alpha for inpaint composition. Effort: ~3-4 hours to wire `pipelines/_meta/matting.py` as a standalone helper called by the icon + 3D adapters.

**ComfyUI workflow node ID hint:** `comfyui-rmbg` or `ComfyUI-BiRefNet` packs expose `RMBGRemoveBackground` / `BiRefNetRemoveBG` nodes. One-node insert.

### 6.2 Upscalers

| Tool | License | Quality | sm_120 | Use case |
|---|---|---|---|---|
| **Real-ESRGAN-x4plus** | BSD-3 | Mid; OG | Yes | The dependable default; 256→1024 in <1s |
| **HAT-L** ([HF Phips/upscale_models](https://huggingface.co/Phips/upscale_models)) | Apache-2.0 | Strong | Yes | 2024-2025; sharper than ESRGAN |
| **DAT-2** | Apache-2.0 | Strong | Yes | Diffusion-attention transformer |
| **SUPIR** ([Fanghua-Yu/SUPIR](https://github.com/Fanghua-Yu/SUPIR)) | Apache-2.0 (model) | **Best for photographic** | Yes | Heavy (~12 GB); slow; uses SDXL prior |
| **FLUX-Upscaler / FLUX Tile-Upscale** | various LoRAs | Strong | Yes | The 2026 pick for art-style upscale |
| **4x-UltraSharp / 4x-NMKD-Siax / community packs** | Various | Mid-strong | Yes | The "open-source upscale-by-genre" community: anime, photo, line-art each have a specialty model |

**Pick:** **HAT-L** for default 4× upscale (Apache, sharp, fast). **FLUX Tile-Upscale workflow** for texture finalization (fixes seams while upscaling). **SUPIR** when photographic-realism upscale is needed and you have ~12 GB of VRAM idle. **Skip** Real-ESRGAN as a default in 2026 — superseded.

We already have `pipelines/textures/flux_upscale.py` (FLUX low-denoise heal) wired and verified at 2K. Extend it: add a `--engine hat-l` switch for the cheap path, keep FLUX-tile for the seam-heal path.

### 6.3 Depth / normal estimation

Use case: fake-3D depth from concept art (parallax UI, billboard normal maps from icon paintings, pseudo-relief on textures).

| Tool | License | Quality | sm_120 | Notes |
|---|---|---|---|---|
| **DepthAnything-V2** ([DepthAnything/Depth-Anything-V2](https://github.com/DepthAnything/Depth-Anything-V2)) | Apache-2.0 (small/base/large) | **Best open 2025+** | Yes | The default. Fast. |
| **Marigold** ([prs-eth/marigold](https://github.com/prs-eth/marigold)) | Apache-2.0 | Best on photographic | Yes | Diffusion-based; slower; sharper |
| **GeoWizard** | Apache-2.0 | Strong; outputs depth + normal | Yes | Better for normal maps than DepthAnything |
| **DSINE** | Apache-2.0 | Best normal estimation | Yes | Specialized for normal-only |
| **MiDaS v3.1** | MIT | OG; surpassed | Yes | Skip |

**Pick:** **DepthAnything-V2** for depth, **GeoWizard** for normal-from-image (single tool, both outputs). Wire as `pipelines/_meta/depth_normal.py` helper. Effort: ~3-4 hours. **Use cases:** generate depth-of-field hints for UI illustration, fake-3D pop on concept-art panels, normal-map seed for `aaa_texture.py` when StableMaterials misbehaves.

### 6.4 Mesh segmentation / part labeling

Use case: retexture-by-part workflows (e.g. "make this rock's moss patches use a different texture set"), part-level animation, hit-region tagging.

| Tool | License | Quality | Notes |
|---|---|---|---|
| **SAM-Mesh / Segment3D** | Apache-2.0 | Strong | Lifts SAM2 masks to 3D mesh |
| **PartSlip / PartSlip++** | MIT | Strong | Open-vocabulary mesh part segmentation |
| **PartObjaverse-Tiny** | dataset, MIT | (data) | Useful as fine-tune corpus |
| **Find3D** | Apache-2.0 | 2024 SOTA | Multi-view part understanding |

**Pick:** **PartSlip++** for open-vocabulary part naming (text-driven: "label all wooden parts"), **Segment3D** when you have multi-view masks and want geometric segmentation. **Effort:** ~6-10 hours to wire a `pipelines/props/segment_parts.py`. **Defer** until the prop kit factory has 50+ hero props that warrant retexture-by-part — overengineering for 24 procedural rocks.

### 6.5 Auto-rigging beyond what we have

Current state: SkinTokens, RigAnything, MagicArticulate all working. Mesh2Motion installed. Trellis2 imports OK. Mixamo as the manual humanoid path.

| Tool | License | Quality | sm_120 | Notes |
|---|---|---|---|---|
| **UniRig** ([VAST-AI-Research/UniRig](https://github.com/VAST-AI-Research/UniRig)) | Apache-2.0 | **2025 paper; best open auto-rig** | Yes | Successor to MagicArticulate; trained on more skeletons; cleaner weights |
| **MagicArticulate-v2** | Apache-2.0 | Strong | Yes | Already installed (v1) |
| **TADA** | Apache-2.0 | Strong on humanoids | Yes | Diffusion-based |
| **Anymate** ([newaymate/Anymate](https://github.com/newaymate/Anymate)) | MIT | Strong, includes rigging-aware mesh repair | Yes | 2025 |
| **Rigger (Roblox open-rig)** | MIT | Mid; humanoid-only | Yes | Roblox open-sourced their pipeline; specific to humanoid bipeds |
| **AutoRig SkinTokens v2** | (current) | Strong | Yes | Already installed |

**Pick:** **UniRig** as the upgrade lane (Apache, 2025 SOTA, drop-in replacement for MagicArticulate). **Anymate** for the case where the source mesh has issues (auto-rig + auto-cleanup). Effort to wire UniRig: ~6-8 hours to mirror the MagicArticulate adapter shape. **Defer** until current riggers fail on a specific creature topology — they're already covering most of the character pipeline.

---

## 7. ComfyUI integration strategy

Current state: **ComfyUI is installed and running** at `D:\assets\animators\ComfyUI\`. It is used for FLUX.2-klein-4B texture generation only. Heavily underused.

### 7.1 Why ComfyUI as the universal host

ComfyUI is the canonical 2026 host for nearly every image / video / 3D model in this report:

- **Image gen:** FLUX (all variants), SD 3.5, SDXL, HiDream, Pixart-Sigma, Lumina-Image-2 — all have native or community nodes within days of release.
- **Video gen:** Wan 2.5/2.6 (`ComfyUI-WanVideoWrapper` by kijai), HunyuanVideo (`ComfyUI-HunyuanVideoWrapper`), LTX-Video (`ComfyUI-LTXVideo`), Mochi (`ComfyUI-MochiWrapper`).
- **Image-to-3D:** Hunyuan3D-2.x (`ComfyUI-Hunyuan3DWrapper`), Trellis (`ComfyUI-Trellis`), InstantMesh (`ComfyUI-3D-Pack`).
- **Inpainting / editing:** native + OminiControl + IP-Adapter + InstantStyle nodes all ship.
- **ControlNet / depth / normal / matting:** dozens of nodes (`comfyui_controlnet_aux`, `ComfyUI-Impact-Pack`, `comfyui-rmbg`, `ComfyUI-DepthAnythingV2`).
- **Upscalers:** built-in via `Upscale Model Loader` + community model repos.

Custom node ecosystem in 2026 is mature: `ComfyUI-Manager` (`Comfy-Org/ComfyUI-Manager`) handles install / update / dependency resolution.

### 7.2 Headless orchestration architecture (the high-leverage build)

The recommended new tool: **`pipelines/_meta/comfy_runner.py`**.

```python
# pseudo-API
from pipelines._meta.comfy_runner import ComfyRunner

cr = ComfyRunner(host="http://127.0.0.1:8188")
result = cr.run(
    workflow_path="pipelines/_meta/workflows/flux_schnell_icon.json",
    overrides={
        "6.inputs.text": "fantasy mana potion icon, flat shaded",
        "3.inputs.seed": 42,
        "3.inputs.steps": 4,
    },
    outputs=["9"],   # SaveImage node id
    timeout_s=300,
)
# result["outputs"]["9"] is the saved PNG path
```

Internals:
1. POST workflow JSON to `/prompt` with overrides applied.
2. Receive `{prompt_id}`.
3. Poll `/history/{prompt_id}` until status reflects completion (or use the websocket `ws://127.0.0.1:8188/ws` for push notifications — preferred).
4. Walk the history result, find the `outputs[node_id].images` array, download each via `/view?filename=...` to a local destination.
5. Return a structured result dict with paths + provenance.

Workflow JSONs live in `pipelines/_meta/workflows/`:
- `flux_schnell_icon.json` — base FLUX-schnell text-to-image
- `flux_schnell_ipadapter_iconset.json` — FLUX + InstantStyle + IPAdapter for set-style
- `hunyuan3d_image_to_glb.json` — Hunyuan3D-2.5 prop generator
- `wan_t2v_5s_720p.json` — Wan 2.5 video clip
- `birefnet_remove_bg.json` — matting helper
- `flux_tile_upscale_2x.json` — texture upscale
- `f5tts_voice_clone.json` — TTS clone
- `inpaint_omini_edit.json` — icon edit

Then every existing cloud adapter grows a `--backend comfy` lane:

```python
# pipelines/ui/recraft_icons.py becomes:
def main():
    if backend == "recraft": ...
    elif backend == "comfy":
        result = comfy.run("flux_schnell_iconset.json", overrides={...}, outputs=["save_node_id"])
        ...  # write manifest entry, attribution=local-flux-schnell-apache
```

### 7.3 Workflow JSON portability

Workflow JSONs are version-fragile across ComfyUI updates and custom-node updates. The 2026 best-practice:
1. **Snapshot exact node-pack versions** via `ComfyUI-Manager`'s `snapshot.json` per workflow.
2. **Pin** ComfyUI commit per workflow in a header comment.
3. **Validate on load** — `comfy_runner.py` should compare workflow's referenced node types against the running ComfyUI's `/object_info` dict and warn on missing nodes.
4. **Smoke test** each workflow with a deterministic seed + prompt nightly via cron / GitHub Actions.

### 7.4 `comfy-cli` and `comfy install` / `comfy-manager`

In 2026, the official `comfy-cli` package ([comfy-org/comfy-cli](https://github.com/comfy-org/comfy-cli)) is the standard CLI:

- `comfy install` — installs ComfyUI itself
- `comfy node install <node-pack>` — installs custom nodes
- `comfy node restore-snapshot snapshot.json` — restores a known-good node set
- `comfy launch` — runs ComfyUI in a controlled way

For our setup, this should be the canonical install path even though ComfyUI is already running. Adding a `pipelines/_meta/comfy_bootstrap.sh` that runs `comfy node restore-snapshot pipelines/_meta/workflows/_snapshot.json` makes new-machine setup deterministic.

### 7.5 HF Spaces is not the right host for this project

HuggingFace Spaces (and the `gradio_client` Python library) lets you call any public Space programmatically. It's fine for one-off experiments. **Do not use as the production lane:** rate-limited, queue-shared, sometimes goes offline. The 5090 + ComfyUI is the actual production lane.

### 7.6 Effort estimate for `comfy_runner.py`

- **Core runner** (POST + websocket poll + output download): 4-6 hours.
- **3 example workflows** (FLUX-schnell-icon, Hunyuan3D-2.5, Wan-video): 6-8 hours including the workflow JSON authoring.
- **Adapter retrofit** (recraft_icons.py / openai_icons.py / texture stack to grow `--backend comfy` lane): 2-3 hours per adapter, 3 adapters = ~8 hours.

**Total: ~18-22 hours for the full comfy lane retrofit.** Highest-leverage build in this report.

---

## 8. HuggingFace surveyor strategy

Staying current with 4-6-week SOTA cycles without manually checking is a real problem. The 2026 toolset:

### 8.1 Useful HF endpoints

- **`/api/trending`** — `curl https://huggingface.co/api/trending?type=model&limit=50` — top trending models. Refresh daily. Good for "what's hot this week."
- **`/api/models?sort=likes7d&direction=-1&limit=50`** — most-liked-this-week sort. Slightly less spammy than trending.
- **`/api/papers`** — daily papers, filterable by date and tags. Best signal for "is the paper-to-model gap closing?"
- **Daily Papers feed** ([papers-cool / hf-daily-papers](https://huggingface.co/papers)) — curated daily paper list with model links.
- **`/api/spaces?sort=likes&filter=text-to-3d`** etc — find demos.
- **Per-model `/api/models/{repo_id}`** — license, downloads, last-modified. Useful for the license filter.

### 8.2 Recommended pipeline tool

A new `pipelines/_meta/hf_surveyor.py`:

```bash
# Run weekly. Writes research/_surveyor/<YYYY-WW>.md
python pipelines/_meta/hf_surveyor.py --since 7d --filter commercial-only \
    --pipelines text-to-image,text-to-audio,image-to-3d,text-to-video,text-to-speech \
    --out research/_surveyor/2026-W19.md
```

Internals:
1. Hit `/api/trending` for each pipeline tag.
2. For each model, fetch `/api/models/{repo_id}` and pull license string.
3. **License filter** — accept-list: `apache-2.0`, `mit`, `bsd-3-clause`, `cc-by-4.0`, `cc-by-sa-4.0` (with cautious flag), `openrail`, `openrail-m`, `bigscience-openrail-m`, `bigscience-bloom-rail-1.0`, `stable-audio-community`, `stability-ai-community`, `tencent-hunyuan-community`, `llama3`, `llama3.1`, `llama3.2`, `llama3.3`, `gemma`, `falcon-llm`. **Reject-list:** anything containing `nc`, `noncommercial`, `non-commercial`, `cc-by-nc`, `coqui`, `research-only`.
4. For each accepted model, write a row with: repo-id, downloads-7d, license, top-3 tags, modified date, short paper link if any.
5. Categorize into "new this week" vs "resurfacing" by checking `research/_surveyor/_seen.json`.

Effort: **~6-8 hours** to build. Pays for itself in one cycle of avoided manual paper-trawling.

### 8.3 Manual sources to bookmark

- [HF Papers daily](https://huggingface.co/papers) — primary signal source.
- [r/LocalLLaMA](https://reddit.com/r/LocalLLaMA) — best aggregate for OSS LLM news.
- [r/StableDiffusion](https://reddit.com/r/StableDiffusion) — image/video model releases, often before HF trending picks them up.
- **kijai's GitHub** ([github.com/kijai](https://github.com/kijai)) — the most reliable single source for "is there a ComfyUI wrapper for the new model yet?"
- **city96** ([huggingface.co/city96](https://huggingface.co/city96)) — best GGUF quant releases for new image/video models.
- **Comfy-Org Discord** — where node-pack maintainers congregate.

---

## What to build next

Ranked by leverage (highest first), with effort estimates and the existing cloud adapter slot each extends.

### Top-5 "build the comfy lane for X" list (highest-leverage plays)

These are the highest-leverage moves in this report. Build all five and the asset factory drops 80% of its cloud spend without quality regression.

| Rank | Build | Effort | Replaces / extends | Why high-leverage |
|---|---|---|---|---|
| **1** | **`pipelines/_meta/comfy_runner.py` + 3 starter workflows** | 12-16h | n/a — foundational | Unblocks every other comfy lane; one runner + N workflows = unbounded backends |
| **2** | **Comfy lane: Hunyuan3D-2.5 image-to-3D** (`pipelines/props/hunyuan3d_route.py`) | 6-8h on top of #1 | Meshy ($0.50-1/asset) + Trellis2 (already built but unused) | Replaces the Meshy spend; `MESHY_AUTH_FOR_THIS_BATCH=YES` becomes optional. Best topology of the open-weights tier. |
| **3** | **Comfy lane: FLUX-schnell + InstantStyle + IP-Adapter for icon sets** (`pipelines/ui/local_diffusion_icons.py` get-real-mode) | 4-6h on top of #1 | Recraft V3 ($0.04-0.08/icon) | Already adapter-built; just needs the workflow JSON + comfy_runner wiring. 5090 sits idle for UI today. |
| **4** | **Comfy lane: F5-TTS voice cloning** (`pipelines/audio/local_tts_f5.py`) | 6-8h | ElevenLabs TTS ($0.30/1k chars) | NEW capability — TTS lane was empty. F5-TTS is MIT, 5-10s reference clone, 4× realtime on 5090. |
| **5** | **Comfy lane: Wan 2.5 video generation** (`pipelines/video/comfy_video.py` + flipbook extractor) | 12-16h | NEW capability | Opens animated UI, VFX reference, cinematic stinger lanes. No prior cloud lane to replace; pure additive. |

### Tier 2 — high-value standalone builds (not comfy-routed)

| Rank | Build | Effort | Replaces / extends | Notes |
|---|---|---|---|---|
| **6** | **vLLM Qwen2.5-Coder-32B + xgrammar local backend** (`pipelines/game_data/local_llm_backend.py` get-real-mode) | 8-12h | OpenAI structured + Anthropic tool-use | Adapter built dry-run; just needs vLLM service + xgrammar `guided_json` wiring. Replaces ~$5-30 per 100-record generation. |
| **7** | **`pipelines/_meta/hf_surveyor.py` + license filter** | 6-8h | Manual paper-trawling | Pays for itself in one cycle. Weekly cron. |
| **8** | **`pipelines/_meta/matting.py` (BiRefNet)** | 3-4h | rembg / cloud matting | One-shot helper; clean reference images for 3D + icons. |
| **9** | **`pipelines/_meta/depth_normal.py` (DepthAnything-V2 + GeoWizard)** | 3-4h | NEW | Adjacent helper for fake-3D UI / texture-normal seeding. |
| **10** | **HAT-L + FLUX Tile-Upscale** retrofit of `flux_upscale.py` | 3-5h | Real-ESRGAN baseline | Sharper texture finalization; SUPIR optional for photo. |
| **11** | **YuE music pilot** (`pipelines/audio/local_music_yue.py`) | 8-12h | NEW | First commercial-shippable open music-with-vocals. Pilot 1-2 hero tracks; not a full music orchestrator. |
| **12** | **Kokoro-82M as the cheap-TTS lane** alongside F5-TTS | 3-4h | NEW (alongside #4) | CPU-runnable TTS for placeholder voice and mass NPC barks. |

### Tier 3 — defer until specific need surfaces

| Rank | Build | Trigger | Notes |
|---|---|---|---|
| 13 | Pixel-art icon lane (SDXL + nerijs/pixel-art-xl + Aseprite headless) | When TLTE has a pixel-art region | 4-6h |
| 14 | UniRig auto-rig adapter | When current riggers fail on a creature | 6-8h; mirror MagicArticulate adapter shape |
| 15 | OminiControl icon-edit lane | When 50+ icons need parametric edits | 4-6h on top of comfy_runner |
| 16 | PartSlip++ mesh part labeling | When prop library has 50+ hero props | 6-10h |
| 17 | ChatTTS / OpenVoice as redundant fallbacks | If F5-TTS underperforms on edge cases | 4-6h each |
| 18 | DiffRhythm music | Once YuE is exercised | 6-8h on top of #11 |

### Cross-cutting

- **Update `../docs/reference/CLOUD_KEYS.md`** with the new local-only paths so a future LLM understands "this used to go to cloud, now it's local; here's the GPU-availability gate."
- **Update `../docs/plans/EXPANSION_PLAN.md`** Phases 2-7 to reference these K-recommended builds where they slot in (game_data Phase 2 gets #6; UI Phase 4 gets #3; audio Phase 3 gets #4 and #11; props Phase 6 gets #2; new Phase 9 "video" gets #5).
- **Update `PIPELINE_DIRECTORY.md`** §5 to reflect ComfyUI's expanded role from "FLUX.2-klein only" to "universal headless host."

---

## Sources / citations

### LLMs
- Qwen2.5: https://github.com/QwenLM/Qwen2.5, https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct, https://huggingface.co/Qwen/Qwen2.5-72B-Instruct
- Llama 3.3: https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct
- Mistral Small 3: https://huggingface.co/mistralai/Mistral-Small-24B-Instruct-2501
- Gemma 3: https://huggingface.co/google/gemma-3-27b-it
- DeepSeek-V3 / R1-Distill: https://huggingface.co/deepseek-ai/DeepSeek-V3, https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B
- Phi-4: https://huggingface.co/microsoft/phi-4
- xgrammar: https://github.com/mlc-ai/xgrammar
- outlines: https://github.com/dottxt-ai/outlines
- lm-format-enforcer: https://github.com/noamgat/lm-format-enforcer
- vLLM: https://github.com/vllm-project/vllm
- llama.cpp: https://github.com/ggerganov/llama.cpp
- BFCL leaderboard: https://gorilla.cs.berkeley.edu/leaderboard.html

### Image gen
- Black Forest Labs FLUX: https://github.com/black-forest-labs/flux, https://huggingface.co/black-forest-labs
- HiDream-I1: https://github.com/HiDream-ai/HiDream-I1
- Sana: https://github.com/NVlabs/Sana
- Pixart-Sigma: https://github.com/PixArt-alpha/PixArt-sigma
- Lumina-Image-2.0: https://github.com/Alpha-VLLM/Lumina-Image-2.0
- SD 3.5: https://huggingface.co/stabilityai/stable-diffusion-3.5-large
- Kolors: https://github.com/Kwai-Kolors/Kolors
- IP-Adapter: https://github.com/tencent-ailab/IP-Adapter
- InstantStyle: https://github.com/instantX-research/InstantStyle
- B-LoRA: https://github.com/yardenfren1996/B-LoRA
- OminiControl: https://github.com/Yuanshi9815/OminiControl
- OmniGen: https://github.com/VectorSpaceLab/OmniGen
- vtracer: https://github.com/visioncortex/vtracer
- nerijs/pixel-art-xl: https://huggingface.co/nerijs/pixel-art-xl

### Image-to-3D
- Trellis: https://github.com/microsoft/TRELLIS
- Hunyuan3D-2: https://github.com/Tencent/Hunyuan3D-2, https://huggingface.co/tencent/Hunyuan3D-2
- MV-Adapter: https://github.com/huanngzh/MV-Adapter
- InstantMesh: https://github.com/TencentARC/InstantMesh
- TripoSR: https://github.com/VAST-AI-Research/TripoSR
- CRM: https://github.com/thu-ml/CRM
- Direct3D-S2: https://github.com/DSaurus/Direct3D-S2
- Era3D: https://github.com/pengHTYX/Era3D
- Unique3D: https://github.com/AiuniAI/Unique3D
- Stable Fast 3D: https://github.com/Stability-AI/stable-fast-3d
- 3DTopia-XL: https://github.com/3DTopia/3DTopia-XL
- Quadriflow: https://github.com/hjwdzh/QuadriFlow
- ComfyUI-Hunyuan3DWrapper: https://github.com/kijai/ComfyUI-Hunyuan3DWrapper

### Audio
- Stable Audio Open: https://huggingface.co/stabilityai/stable-audio-open-1.0, https://huggingface.co/stabilityai/stable-audio-open-small
- AudioCraft / MusicGen / AudioGen: https://github.com/facebookresearch/audiocraft (license trap)
- F5-TTS: https://github.com/SWivid/F5-TTS
- Kokoro: https://huggingface.co/hexgrad/Kokoro-82M
- OpenVoice: https://github.com/myshell-ai/OpenVoice
- MeloTTS: https://github.com/myshell-ai/MeloTTS
- Parler-TTS: https://github.com/huggingface/parler-tts
- CosyVoice: https://github.com/FunAudioLLM/CosyVoice
- XTTS-v2: https://huggingface.co/coqui/XTTS-v2 (license trap)
- GPT-SoVITS: https://github.com/RVC-Boss/GPT-SoVITS
- YuE: https://github.com/multimodal-art-projection/YuE
- DiffRhythm: https://github.com/ASLP-lab/DiffRhythm
- Spark-TTS: https://github.com/SparkAudio/Spark-TTS (license trap)

### Video
- Wan 2.x: https://github.com/Wan-Video/Wan2.1, https://huggingface.co/Wan-AI
- HunyuanVideo: https://github.com/Tencent/HunyuanVideo
- Mochi: https://github.com/genmoai/models
- LTX-Video: https://github.com/Lightricks/LTX-Video
- CogVideoX: https://github.com/THUDM/CogVideo
- OpenSora: https://github.com/hpcaitech/Open-Sora
- Pyramid Flow: https://github.com/jy0205/Pyramid-Flow
- Allegro: https://huggingface.co/rhymes-ai/Allegro
- ComfyUI-WanVideoWrapper: https://github.com/kijai/ComfyUI-WanVideoWrapper

### Adjacent
- BiRefNet: https://huggingface.co/ZhengPeng7/BiRefNet
- RMBG-2.0: https://huggingface.co/briaai/RMBG-2.0
- Real-ESRGAN: https://github.com/xinntao/Real-ESRGAN
- HAT: https://github.com/XPixelGroup/HAT
- SUPIR: https://github.com/Fanghua-Yu/SUPIR
- DepthAnything-V2: https://github.com/DepthAnything/Depth-Anything-V2
- Marigold: https://github.com/prs-eth/marigold
- GeoWizard: https://github.com/fuxiao0719/GeoWizard
- DSINE: https://github.com/baegwangbin/DSINE
- PartSlip: https://github.com/Colin97/PartSLIP
- UniRig: https://github.com/VAST-AI-Research/UniRig
- Anymate: https://github.com/newaymate/Anymate

### ComfyUI
- ComfyUI: https://github.com/comfy-org/ComfyUI
- ComfyUI-Manager: https://github.com/Comfy-Org/ComfyUI-Manager
- comfy-cli: https://github.com/Comfy-Org/comfy-cli
- ComfyUI API docs: https://docs.comfy.org/api-reference/
- ComfyUI_IPAdapter_plus: https://github.com/cubiq/ComfyUI_IPAdapter_plus
- ComfyUI-DepthAnythingV2: https://github.com/kijai/ComfyUI-DepthAnythingV2
- ComfyUI-LTXVideo: https://github.com/Lightricks/ComfyUI-LTXVideo
- comfyui-rmbg: https://github.com/1038lab/ComfyUI-RMBG

### License references
- Apache-2.0, MIT, BSD-3-Clause: standard OSI texts
- FLUX.1 [dev] Non-Commercial: https://bfl.ai/legal/non-commercial-license-terms
- Stability AI Community License: https://stability.ai/community-license-agreement
- Tencent Hunyuan Community License: https://github.com/Tencent/Hunyuan3D-2/blob/main/LICENSE
- CC-BY-NC family: https://creativecommons.org/licenses/by-nc/4.0/
- Coqui Public Model License: https://coqui.ai/cpml.txt

### Internal docs (this report builds on)
- `D:\assets\research\B_textures.md`, `C_vfx.md`, `C2_vfx_3d_volumetric.md`, `D_ui.md`, `E_audio.md`, `E2_audio_local_ambience.md`, `F_game_data.md`, `F2_game_data_balance_sim.md`, `J_props_3d_decoration_pipeline.md`, `J2_props_variation_lod.md`
- `D:\assets\PIPELINE_DIRECTORY.md`, `../docs/plans/EXPANSION_PLAN.md`, `../docs/plans/ROADMAP.md`, `../docs/reference/CLOUD_KEYS.md`, `../docs/plans/RESEARCH_HANDOFF.md`
- `D:\assets\HANDOFF_*.md` (all v2 + audit_expand handoffs)
