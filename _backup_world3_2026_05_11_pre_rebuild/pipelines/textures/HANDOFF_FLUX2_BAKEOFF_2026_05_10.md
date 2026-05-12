# Handoff: FLUX 2 klein-9B + dev Bakeoff (2026-05-10)

**To**: the other chat session that will run the bakeoff under one
ComfyUI instance.

**From**: this chat (texture model setup + research). All weights
downloaded, all docs written, harness wired. You just need to run it.

---

## TL;DR

1. **Open ComfyUI** (it's already running at `http://127.0.0.1:8188`).
2. **Hit "Unload Models"** in the UI (or restart it) so new models get
   picked up.
3. **Run** the bakeoff command in [step 7 below](#7-run-the-bakeoff).
4. **Review** the output grids in `D:/tmp/diversity_compare_2026_05_09/`.
5. **Write findings** to
   `pipelines/textures/M14_FLUX2_BAKEOFF_FINDINGS_<date>.md`.
6. **Decide** which klein-9B quant wins; delete the losers; update the
   M14 board.

That's it. Everything else in this doc is context if you need it.

---

## 1. Context (what we're doing and why)

We're running the world3 M14 close-play terrain-quality lane. The
existing texture workflow uses `flux2_klein` (FLUX 2 klein-4B) as the
production-reference lane plus `auraflow_03` and `sd35_large` as
diversity lanes. The user asked: **does FLUX 2 klein-9B beat klein-4B
for ground-texture work, and how does FLUX 2 dev (32B) compare?**

To answer that, we pulled three klein-9B quants + the dev NVFP4. The
bakeoff will A/B them on the same prompts/seeds so we pick a winner.

See [`WORKFLOW_GUIDE_FLUX2_2026_05_10.md`](WORKFLOW_GUIDE_FLUX2_2026_05_10.md)
for the full operational reference covering settings, prompting, license,
and architecture. That's the doc you'd read if you needed to understand
the *why* of every setting. **You probably don't need to read it to run
the bakeoff** — this handoff has everything you need.

## 2. What's on disk

All weights staged at `D:/assets/animators/ComfyUI/models/`:

| Lane | Path | Size |
|---|---|---|
| klein-4B (baseline) | `diffusion_models/flux-2-klein-4b.safetensors` | 7.75 GB |
| klein-9B Q8 GGUF (community) | `diffusion_models/flux-2-klein-9b-Q8_0.gguf` | 9.98 GB |
| **klein-9B NVFP4 (official)** | `diffusion_models/flux-2-klein-9b-nvfp4.safetensors` | 5.76 GB |
| klein-9B FP8 (official) | `diffusion_models/flux-2-klein-9b-fp8.safetensors` | 9.43 GB |
| **dev NVFP4 32B (official)** | `diffusion_models/flux2-dev-nvfp4.safetensors` | 21.04 GB |
| Text encoder (4B) | `text_encoders/qwen_3_4b.safetensors` | 8.04 GB |
| Text encoder (9B + dev) | `text_encoders/qwen_3_8b_fp8mixed.safetensors` | 8.66 GB |
| VAE (shared all FLUX 2) | `vae/flux2-vae.safetensors` | 0.34 GB |

Plus the existing AuraFlow + SD 3.5 lanes (untouched in this session).

## 3. Hardware + software verified

- **GPU**: NVIDIA RTX 5090 Laptop (Blackwell, sm_120, 24 GB VRAM)
- **PyTorch**: 2.11.0+**cu130** ← *required for NVFP4 native acceleration*
- **ComfyUI**: 0.20.1 (has NVFP4 + Async Offload + Pinned Memory support)
- **ComfyUI-GGUF**: city96's, latest as of Oct 2025

If NVFP4 is silently slow (slower than FP8), PyTorch isn't cu130. Check
`http://127.0.0.1:8188/system_stats`.

## 4. License (one-pager)

Generated images are **commercially usable** — they can ship in a
paid game. Only the model weights themselves are non-commercial.
You don't need to worry about license when running this bakeoff.

Verbatim from BFL: *"You may use Output for any purpose (including for
commercial purposes), except as expressly prohibited herein."*

## 5. Settings cheat sheet

The diversity-compare harness handles this for you. For reference:

| Model | Steps | CFG | Sampler | Scheduler | Resolution |
|---|---|---|---|---|---|
| klein-4B distilled | 4 | 1.0 | euler | Flux2Scheduler | 1024² |
| klein-9B distilled (Q8/NVFP4/FP8) | 4 | 1.0 | euler | Flux2Scheduler | 1024² |
| **dev NVFP4** | **28** | **4.0** | euler | Flux2Scheduler | 1024² |

Key gotchas:
- **klein distilled breaks with >4 steps** ("does not work well with too
  many steps" — Diffusion Doodles)
- **FLUX 2 has no negative prompts** — don't bother passing them
- **Use Flux2Scheduler for t2i, BasicScheduler for img2img** (denoise arg)
- **`flux_seamless.py` offset+heal works on all four FLUX 2 variants**
  (they handle "tileable" correctly, unlike Chroma/SD3.5/Qwen)

## 6. Bakeoff harness

The harness is [`pipelines/textures/diversity_compare.py`](diversity_compare.py).

Registry entries (all wired and ready):

```python
"flux2_klein"           # klein-4B baseline
"flux2_klein_9b"        # klein-9B Q8 GGUF (community)
"flux2_klein_9b_nvfp4"  # klein-9B NVFP4 (BFL official, expected winner)
"flux2_klein_9b_fp8"    # klein-9B FP8 (BFL official)
"flux2_dev_nvfp4"       # dev 32B NVFP4 (hero-quality lane)
"auraflow_03"           # diversity lane (untouched)
"sd35_large"            # diversity lane (untouched)
```

Each builder uses the canonical FLUX 2 node graph:
`UNETLoader → CLIPLoader → VAELoader → CLIPTextEncode → CFGGuider →
KSamplerSelect + Flux2Scheduler + EmptyFlux2LatentImage + RandomNoise
→ SamplerCustomAdvanced → VAEDecode → SaveImage`.

ComfyUI evicts the previous model on each `UNETLoader` swap, so
sequential bakeoff fits in 24 GB regardless of how many lanes are in
the run.

## 7. Run the bakeoff

The textures lane has its own venv at `pipelines/textures/.venv` — use
that for the harness.

**Smoke test first** (one model, one prompt, no seamless heal):

```bash
cd d:/assets/pipelines/textures
.venv/Scripts/python.exe diversity_compare.py \
    --prompt "weathered alpine granite, lichen patches, gravel detail" \
    --id smoketest_klein9b_nvfp4 \
    --seed 42 \
    --models flux2_klein_9b_nvfp4 \
    --no-seamless
```

Expected: ~5-10 seconds wall time. If this fails, fix the error before
running the full bakeoff (likely cause: ComfyUI hasn't picked up the new
models — hit "Unload Models" or restart).

**Full FLUX 2 bakeoff across 4 prompts** (15-30 min total):

```bash
cd d:/assets/pipelines/textures

# Prompt 1 - alpine granite (hard surface)
.venv/Scripts/python.exe diversity_compare.py \
    --prompt "weathered alpine granite, lichen patches, gravel detail" \
    --id alpine_granite_flux2_bakeoff \
    --seed 42 \
    --models flux2_klein,flux2_klein_9b,flux2_klein_9b_nvfp4,flux2_klein_9b_fp8,flux2_dev_nvfp4

# Prompt 2 - forest floor (soft organic; this is an M14 blocker class)
.venv/Scripts/python.exe diversity_compare.py \
    --prompt "dense forest grass with patches of leaf litter, moss, twigs" \
    --id forest_floor_flux2_bakeoff \
    --seed 42 \
    --models flux2_klein,flux2_klein_9b,flux2_klein_9b_nvfp4,flux2_klein_9b_fp8,flux2_dev_nvfp4

# Prompt 3 - desert dry wash (mid-tone gravel)
.venv/Scripts/python.exe diversity_compare.py \
    --prompt "dry desert canyon sandstone, fine crack network, sun-bleached" \
    --id desert_wash_flux2_bakeoff \
    --seed 42 \
    --models flux2_klein,flux2_klein_9b,flux2_klein_9b_nvfp4,flux2_klein_9b_fp8,flux2_dev_nvfp4

# Prompt 4 - tundra moss (high-frequency green organic; M14 blocker class)
.venv/Scripts/python.exe diversity_compare.py \
    --prompt "compact tundra moss with frost-crystallized patches" \
    --id tundra_moss_flux2_bakeoff \
    --seed 42 \
    --models flux2_klein,flux2_klein_9b,flux2_klein_9b_nvfp4,flux2_klein_9b_fp8,flux2_dev_nvfp4
```

All four prompts share `seed=42` so the *only* variable across the
4-prompt × 5-model matrix is the model.

Output structure:
```
D:/tmp/diversity_compare_2026_05_09/
├── alpine_granite_flux2_bakeoff/
│   ├── flux2_klein/{pass1_raw.png, pass3_healed_shifted.png, final_albedo.png}
│   ├── flux2_klein_9b/...
│   ├── flux2_klein_9b_nvfp4/...
│   ├── flux2_klein_9b_fp8/...
│   ├── flux2_dev_nvfp4/...
│   ├── grid_pass1.png    ← raw t2i side-by-side
│   └── grid_final.png    ← offset+heal seamless side-by-side
├── forest_floor_flux2_bakeoff/...
├── desert_wash_flux2_bakeoff/...
└── tundra_moss_flux2_bakeoff/...
```

## 8. How to review the results

For each prompt, look at `grid_final.png` (the seamless-corrected
output). Score each model on:

1. **Subject fidelity** — does the image actually depict the material?
2. **Tileability** — does it look uniform (no central composition,
   no obvious focal point)?
3. **Detail density** — close-play would benefit from more grain/structure
4. **Color authenticity** — does it match what real photos of the
   material look like?
5. **Speed** — captured in JSON sidecars; check `total_seconds` field

Honest verdict template per model per prompt: "✅ ⚠️ ❌" plus one
sentence of why.

### Specific things to look for

- **klein-9B variants vs klein-4B baseline**: does 9B produce
  noticeably more detail, better tileability, or more accurate
  material color? If "no" → 9B isn't worth the disk space.
- **NVFP4 vs FP8 vs Q8 GGUF**: are they distinguishable by eye? The
  user expects NVFP4 to win on speed but lose slightly on quality
  ("some degrade in quality" per SECourses). If NVFP4 quality is
  fine, keep it; if visibly worse, FP8 is the keeper.
- **dev NVFP4 vs klein-9B winner**: dev should win on prompt
  fidelity and detail, lose on speed (~4× slower). Decide if dev
  earns a permanent slot or is sidecar-only for hero shots.

## 9. Decision matrix

After review:

| Outcome | Action |
|---|---|
| **klein-9B NVFP4 matches/beats klein-4B + FP8 ≈ NVFP4 quality** | Delete FP8 + Q8 (-19.4 GB). Promote NVFP4 as production lane. |
| **klein-9B NVFP4 visibly worse than FP8** | Delete NVFP4 + Q8 (-15.7 GB). Promote FP8 as production lane. |
| **klein-4B is "good enough" → 9B doesn't justify** | Delete all three 9B variants + the qwen_3_8b text encoder (-33.8 GB). Stay on klein-4B. |
| **dev NVFP4 is clearly the quality ceiling** | Keep it. Use as hero-only / single-best-of-N lane. |
| **dev NVFP4 doesn't move the needle vs klein-9B** | Delete it (-21 GB). |

Disk-cleanup commands documented in
[`FLUX2_KLEIN_9B_SETUP_2026_05_10.md`](FLUX2_KLEIN_9B_SETUP_2026_05_10.md)
section "Reclaim if we reject a lane after bakeoff".

## 10. Findings doc template

Write to `pipelines/textures/M14_FLUX2_BAKEOFF_FINDINGS_<YYYY_MM_DD>.md`:

```markdown
# M14 FLUX 2 Bakeoff Findings - <date>

## Setup
- Prompts run: <list>
- Seed: 42
- Resolution: 1024²
- Hardware: RTX 5090 Laptop, PyTorch 2.11.0+cu130, ComfyUI 0.20.1

## Speed table (sec/image, raw t2i, no seamless heal)
| Model | alpine | forest | desert | tundra | avg |
|---|---|---|---|---|---|
| flux2_klein (4B) | ... | ... | ... | ... | ... |
| flux2_klein_9b (Q8 GGUF) | ... | ... | ... | ... | ... |
| flux2_klein_9b_nvfp4 | ... | ... | ... | ... | ... |
| flux2_klein_9b_fp8 | ... | ... | ... | ... | ... |
| flux2_dev_nvfp4 | ... | ... | ... | ... | ... |

## Visual verdicts (per model, per prompt)
[detailed eyeball review]

## Decision
- Production lane (post-bakeoff): <model>
- Hero lane (if separate): <model>
- Removed from disk: <list> (~<N> GB reclaimed)

## Followups for the M14 board
- <updates to the bakeoff plan>
- <regenerate or sunset specific organic blockers>

## Sidecar evidence
- Grids: D:/tmp/diversity_compare_2026_05_09/{alpine,forest,desert,tundra}_flux2_bakeoff/grid_final.png
- Raw outputs preserved in same dirs under each model subfolder
```

## 11. Followup: update these docs after deciding

Once a winner is chosen and losers deleted:

1. [`pipelines/textures/DIVERSITY_COMPARE_2026_05_09.md`](DIVERSITY_COMPARE_2026_05_09.md)
   — add 2026-05-10 update banner noting the bakeoff result; update
   the "Models on disk" section
2. [`pipelines/textures/diversity_compare.py`](diversity_compare.py)
   — remove the losing klein-9B registry entries (and their builders
   if you want, or leave the builders as reference)
3. [`world3/docs/M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md`](../../world3/docs/M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md)
   and [`world3/jobs/m14_texture_bakeoff_plan.json`](../../world3/jobs/m14_texture_bakeoff_plan.json)
   — add the new active model lane(s) for klein-9B/dev
4. [`pipelines/textures/FLUX2_KLEIN_9B_SETUP_2026_05_10.md`](FLUX2_KLEIN_9B_SETUP_2026_05_10.md)
   — flip status from "setup complete, no bakeoff run yet" to
   "bakeoff complete, [winner] selected"

## 12. Common errors

| Error | Cause | Fix |
|---|---|---|
| "NVFP4 acceleration unavailable" | PyTorch not cu130 | Reinstall ComfyUI's torch with cu130 build |
| "Architecture flux not recognized" | ComfyUI-GGUF outdated | `cd custom_nodes/ComfyUI-GGUF; git pull` |
| OOM on dev NVFP4 | Async Offload disabled | Should be on by default in ComfyUI 0.20.1; hit Unload Models first |
| First few prompts slow | ComfyUI is loading models cold | Subsequent runs of same model will be 5-10× faster |
| Output is decorative tiles | You're running Chroma/SD3.5/Qwen (not FLUX 2) | Verify `--models` flag |

## 13. Don't do these things

- **Don't delete `qwen_3_8b_fp8mixed.safetensors`** until you've decided
  on a klein-9B lane. It's required by all three 9B variants AND by
  dev-nvfp4.
- **Don't delete `flux2-vae.safetensors`** ever. Shared across all
  FLUX 2 variants.
- **Don't try to use FLUX 1 VAE (`ae.safetensors`) with FLUX 2 models** —
  they're different VAEs. FLUX 1 uses `ae.safetensors`, FLUX 2 uses
  `flux2-vae.safetensors`.
- **Don't bump steps on klein-9B distilled** — it's distilled to
  *exactly* 4 steps. More degrades output.
- **Don't enable negative prompts on FLUX 2** — they're ignored.
- **Don't re-pull Qwen-Image or Chroma1-HD** — they were deleted in
  this session for cause; revival is documented if you ever want them
  back.

## 14. Files for context (read only if needed)

- [`WORKFLOW_GUIDE_FLUX2_2026_05_10.md`](WORKFLOW_GUIDE_FLUX2_2026_05_10.md) —
  complete operational manual (settings, prompting, license, node graph)
- [`FLUX2_KLEIN_9B_SETUP_2026_05_10.md`](FLUX2_KLEIN_9B_SETUP_2026_05_10.md) —
  decision rationale for which klein-9B variants got pulled
- [`DIVERSITY_COMPARE_2026_05_09.md`](DIVERSITY_COMPARE_2026_05_09.md) —
  original four-lane bakeoff findings (Qwen-Image / Chroma1-HD now sunset)
- [`diversity_compare.py`](diversity_compare.py) — the harness itself
- [`flux_seamless.py`](flux_seamless.py) — offset+heal seamless trick
  used by the harness's `do_seamless` path
- [`LESSONS.md`](LESSONS.md) — accumulated texture-pipeline gotchas
- [`TEXTURE_RND.md`](TEXTURE_RND.md) — full RND log

## 15. After the bakeoff

If a winner emerges, the next M14 work is regenerating the organic
blockers (`grass`, `tundra_moss`, `tundra_lichen`, `temperate_forest_grass`)
through the winning lane. See
[`world3/docs/M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md`](../../world3/docs/M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md)
for the blocker list and acceptance criteria.

If dev-nvfp4 earns its keep, it joins the lane as the hero-quality
sidecar — used for single-best-of-N hero textures where klein-9B's
4-step distillation can't deliver enough detail.

---

## Short prompt for the other chat

Paste this if you want to spin up the other chat fresh:

> I'm continuing work on `D:/assets`. The previous session set up four
> new FLUX 2 model lanes (klein-9B Q8/NVFP4/FP8 + dev NVFP4) for a
> bakeoff against the existing klein-4B baseline. All weights are on
> disk, the diversity_compare.py harness has the new registry entries,
> and ComfyUI 0.20.1 is running with PyTorch 2.11.0+cu130 on our RTX
> 5090 Laptop (Blackwell). Full handoff at
> `D:/assets/pipelines/textures/HANDOFF_FLUX2_BAKEOFF_2026_05_10.md` —
> read that first, then run the four-prompt bakeoff in section 7,
> review per section 8, decide per section 9, write findings per
> section 10, then clean up disk + update docs per section 11.
