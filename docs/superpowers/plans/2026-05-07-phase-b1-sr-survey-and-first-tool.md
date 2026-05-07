# Phase B.1 — SR Survey + First SR Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the first super-resolution tool for the texture pipeline (Real-ESRGAN via ComfyUI), audit the existing `flux_upscale.py`, and produce a survey doc justifying the choice. Foundation for B.2 (bake) and B.3 (mip ladder).

**Architecture:** New `sr_upscale.py` shells out to a running ComfyUI instance (same pattern as `flux_seamless.py` / `flux_upscale.py`) and submits an `UpscaleModelLoader` + `ImageUpscaleWithModel` workflow. ComfyUI's internal 512-tile + 32-overlap tiling can break outer texture tileability, so we apply the established offset+heal trick (offset to move seams interior → upscale → reverse-offset) and measure with `edge_seam_score`. Survey doc parallels the existing `EXTERNAL_TECHNIQUES.md` from Phase A.5.

**Tech Stack:** Python 3.12, PIL, NumPy, ComfyUI 0.20.1 (already running on 127.0.0.1:8188), Real-ESRGAN x4plus model (`.pth`, ~64 MB, drop into `D:/assets/animators/ComfyUI/models/upscale_models/`).

**Validation pattern (project convention — no pytest):** Pipeline scripts in `pipelines/textures/` are validated by (1) the tool runs successfully on real inputs, (2) measurable QA scores written to JSON, and (3) visual A/B contact sheets archived under `world3/docs/captures/phase_b/`. There is no test infrastructure in `pipelines/textures/`; do not introduce one. Each task ends with a real-input run + an evidence check.

**Predecessor:** Phase A polish (A.7–A.11) — done.
**Successor:** Phase B.2 (bake_pbr.py) — depends on this.
**Spec:** `docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md`

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `pipelines/textures/sr_upscale.py` | **CREATE** | Single-map SR via ComfyUI's UpscaleModelLoader. Tile-preserving via offset+heal. CLI: `--in <png> --out <png> [--scale 4] [--model <name>] [--no-offset-trick]` |
| `pipelines/textures/EXTERNAL_SR_TECHNIQUES.md` | **CREATE** | Survey doc covering Real-ESRGAN, SwinIR, BSRGAN, UltimateSDUpscale, FLUX img2img-as-SR. Parallel structure to existing `EXTERNAL_TECHNIQUES.md`. |
| `pipelines/textures/TOOLS.md` | MODIFY | Add `sr_upscale.py` entry; update `flux_upscale.py` entry to reflect heal-pass repositioning. |
| `pipelines/textures/RECIPES.md` | MODIFY | Add "Upscale a single map (Real-ESRGAN)" recipe. |
| `pipelines/textures/TEXTURE_RND.md` | MODIFY | Append "B.1" section: survey findings + A/B results. |
| `pipelines/textures/PIPELINE.md` | MODIFY | Add brief mention of SR stage (full multi-res pipeline doc lands at B.5). |
| `D:/assets/animators/ComfyUI/models/upscale_models/RealESRGAN_x4plus.pth` | **DOWNLOAD** | The Real-ESRGAN x4 model. ~64 MB. Source: official GitHub releases. |
| `world3/docs/captures/phase_b/B1_sr_survey/` | **CREATE** | Visual A/B evidence: Real-ESRGAN vs Lanczos vs flux_upscale on 3 representative materials. |

**Out of scope for B.1:** PBR-aware multi-map upscaling (B.5 orchestrator), bake-from-upscaled (B.2), mip ladder (B.3). This is a single-map tool only.

---

## Pre-flight checklist (Task 0)

### Task 0: Environment verification

**Files:** none (read-only checks)

- [ ] **Step 1: Verify ComfyUI is up**

Run:
```powershell
curl -fsS http://127.0.0.1:8188/system_stats
```
Expected: JSON response with `comfyui_version`, `python_version`, etc. If down, see `pipelines/textures/RECIPES.md` "Prerequisites".

- [ ] **Step 2: Verify the upscale_models dir exists and is empty (placeholder only)**

Run:
```powershell
ls "D:/assets/animators/ComfyUI/models/upscale_models/"
```
Expected: only `put_esrgan_and_other_upscale_models_here` placeholder file. Confirms we're starting from a clean slate.

- [ ] **Step 3: Verify a representative input texture exists**

Run:
```powershell
ls "D:/assets/world/textures/library/wgv3_rock_dark/"
```
Expected: at minimum `wgv3_rock_dark_albedo.png` exists. We'll use this as the canonical test input throughout B.1.

- [ ] **Step 4: Set encoding for the session**

Run:
```powershell
$env:PYTHONIOENCODING = "utf-8"
cd D:/assets
```

No commit — this is environment verification only.

---

## Task 1: SR survey doc

This is the "research before installing" gate per the project's memory rule. Written *first*, before downloading any model, so the choice is justified rather than reflexive.

**Files:**
- Create: `pipelines/textures/EXTERNAL_SR_TECHNIQUES.md`

- [ ] **Step 1: Read the existing `EXTERNAL_TECHNIQUES.md` for structural template**

Run:
```bash
head -80 "D:/assets/pipelines/textures/EXTERNAL_TECHNIQUES.md"
```
Note the structure: snapshot date header, "What this is" intro, numbered technique entries with pros/cons/links/verdict for our use case.

- [ ] **Step 2: Write the survey doc**

Create `D:/assets/pipelines/textures/EXTERNAL_SR_TECHNIQUES.md` with this content:

````markdown
# External Super-Resolution Techniques (Snapshot, 2026-05-07)

A survey of super-resolution backends evaluated for the world3 texture
pipeline. Parallels `EXTERNAL_TECHNIQUES.md` (which covered tileable
PBR generation in Phase A.5); this one covers the upscaling stage of
Phase B.

The shape of the question: we generate at 512 (sm/derive) or 1024
(chord/chord_sm_rough). We want a 4K working master to bake from
(see `docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md`).
Need: a fast, tileable-preserving 4× SR for albedo + height; the
other PBR maps will be re-baked from the upscaled albedo+height in
B.2, so the SR's job on those is more lenient.

## Decision summary

**Pick: Real-ESRGAN (x4plus, general model) as the first/default SR backend.**

Reasons:
- Drop-in via ComfyUI's existing `UpscaleModelLoader` +
  `ImageUpscaleWithModel` nodes. Zero install friction.
- Fast: ~5-15s per 1K→4K map on 5090. Cheap relative to the bake step.
- Permissively licensed (BSD-3-Clause).
- Multiple variants available if the general model underperforms on
  specific material classes (anime_6B for stylized; general-x4v3 for
  faces/photos; later: BSRGAN/SwinIR if survey-driven need arises).
- ComfyUI does its own internal patch-tiling (512px patches, 32px
  overlap) which preserves *internal* detail well but can break
  outer-edge tileability. Mitigation: the offset+heal trick already
  in `flux_upscale.py`. Measure with `edge_seam_score`.

Alternatives considered (kept available for B.6 if needed):

## 1. Real-ESRGAN

- **Repo:** https://github.com/xinntao/Real-ESRGAN
- **License:** BSD-3-Clause.
- **Models considered:** `RealESRGAN_x4plus.pth` (general, ~64 MB),
  `RealESRGAN_x4plus_anime_6B.pth`, `realesr-general-x4v3.pth`.
- **Pros:** fast, well-tested, ComfyUI-native, multiple variants.
- **Cons:** trained for natural images, not specifically tileable
  textures — may hallucinate detail that breaks at tile boundaries.
- **Verdict:** **default choice for B.1.** Start with `x4plus` (general).

## 2. SwinIR

- **Repo:** https://github.com/JingyunLiang/SwinIR
- **License:** Apache-2.0.
- **Pros:** transformer-based; reportedly cleaner on smooth/uniform
  surfaces than CNN-based ESRGAN derivatives.
- **Cons:** slower (~3-5x); model file is larger; ComfyUI has
  community nodes but not first-party support.
- **Verdict:** parked for B.6. Worth re-evaluating if Real-ESRGAN
  consistently mishandles a specific material class (e.g. snow,
  smooth sand).

## 3. BSRGAN

- **Repo:** https://github.com/cszn/BSRGAN
- **License:** Apache-2.0.
- **Pros:** trained on a wider degradation model than ESRGAN;
  better on real-world (low-quality, noisy) inputs.
- **Cons:** our inputs are clean FLUX outputs, not real-world
  noisy. The "robustness to degradation" advantage isn't relevant.
  Slower than Real-ESRGAN.
- **Verdict:** parked. Unlikely to beat Real-ESRGAN on our clean
  generated inputs.

## 4. UltimateSDUpscale (ComfyUI custom node)

- **Repo:** https://github.com/ssitu/ComfyUI_UltimateSDUpscale
- **What it is:** wrapper that combines a base SR model
  (Real-ESRGAN/etc.) with an SD-based "refine pass" at the higher
  res, with tile-and-blend for arbitrary output size.
- **Pros:** can produce 8K+ with reasonable quality; tile-and-blend
  is built in.
- **Cons:** the SD refine pass changes content (not just resolution);
  not what we want for "preserve the generated texture as-is, just
  larger." That refinement role is already filled by our existing
  `flux_upscale.py` heal pass.
- **Verdict:** parked. Conceptually overlaps with our existing FLUX
  heal-pass approach. If we want refine-at-higher-res, we already
  have the FLUX path.

## 5. FLUX img2img as SR (existing `flux_upscale.py`)

- **Status:** already in the pipeline.
- **What it does:** bilinear-upscale to target res → low-denoise
  FLUX img2img heal pass → reverse offset for tile preservation.
- **Pros:** uses our existing FLUX setup; the heal pass is
  tile-aware via offset+heal; produces outputs in the same
  "FLUX style" as generation, so doesn't introduce a content
  discontinuity.
- **Cons:** slow (~30-60s per map at 4K vs 5-15s for Real-ESRGAN);
  albedo-only currently; the "denoise=0.18" is content-preserving
  but not really doing SR-grade detail synthesis — it's polishing
  an already-bilinear-upscaled image, not synthesizing new detail
  from learned priors.
- **Verdict:** **reposition as a heal-pass tool**, not the SR
  backbone. Use Real-ESRGAN for actual SR; use `flux_upscale.py`
  when we want to "polish a near-shipping image at the same res
  to recover FLUX style consistency." Audit confirms what's
  documented above; no breaking changes.

## 6. Latent-space upscaling (Hunyuan / FLUX2 latent upscalers)

- **Status:** ComfyUI has `LatentUpscaleModelLoader` (see
  `comfy_extras/nodes_hunyuan.py`); FLUX2 may have a latent
  upscaler.
- **Pros:** operates in latent space — no pixel-space artifacts,
  potentially preserves more "model-native" structure.
- **Cons:** requires re-running through a diffusion model; the
  output is then VAE-decoded. Effectively equivalent to "generate
  at higher res from a guide" — not SR proper.
- **Verdict:** parked. Conceptually closer to "generate-at-higher-res"
  than to SR. Re-evaluate if/when we explore native >1K generation
  (currently a non-goal per the Phase B spec).

## Tile preservation: the open issue

ComfyUI's `ImageUpscaleWithModel` does internal tiled scale (512px
patches, 32px overlap) — see
`animators/ComfyUI/comfy_extras/nodes_upscale_model.py:88-90`. The
outer image edges are *not* aware of being tileable, so a tileable
input may produce a non-tileable output where the model hallucinates
incompatible detail at the texture's outer edge.

Mitigation strategy (used in B.1):
1. **Offset trick** — shift the input by half (so the original
   tileable seam is now at the image center, away from any
   outer-edge model artifacts). Run SR. Reverse the offset. The
   center "seam" location was an interior region the model had
   full context on, so it stays coherent; the new outer edges of
   the SR'd output are what was previously the interior — also
   coherent.
2. **Measure** — `edge_seam_score` from `flux_seamless.py` measures
   pixel discontinuity at the outer seams. We require post-SR
   score to remain in the same band as the input (within 2x of
   the source's score).
3. **Fallback** — if Real-ESRGAN consistently breaks tiling, run a
   FLUX heal pass after (the existing `flux_upscale.py` path),
   which restores tile coherence.

## Recommendation for the rest of Phase B

- **B.1 (this):** Real-ESRGAN as default; survey-justified.
- **B.2:** SR'd outputs feed `bake_pbr.py`. Bake re-derives the
  physically-derivable maps, so any SR hallucination in
  normal/AO/roughness gets washed out by the re-bake.
- **B.3:** mip down from the baked 4K master.
- **B.6:** if survey or flagship A/B (B.5) shows Real-ESRGAN
  underperforms on a specific material class (snow, vegetation,
  sand), evaluate SwinIR or BSRGAN for that class. Opt-in
  per-class, not default-replace.

## See also

- `EXTERNAL_TECHNIQUES.md` — Phase A.5 survey of tileable PBR generation.
- `docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md` — full Phase B design.
- `flux_upscale.py` — existing FLUX heal-pass tool (repositioned, not replaced).
- `upscale_biome_set.py` — Lanczos baseline (kept as no-ComfyUI fallback).
````

- [ ] **Step 3: Verify the file is well-formed**

Run:
```bash
wc -l "D:/assets/pipelines/textures/EXTERNAL_SR_TECHNIQUES.md"
```
Expected: ~150 lines.

- [ ] **Step 4: Commit**

```bash
git add pipelines/textures/EXTERNAL_SR_TECHNIQUES.md
git commit -m "$(cat <<'EOF'
B.1 phase B kickoff: SR survey doc

Survey of Real-ESRGAN, SwinIR, BSRGAN, UltimateSDUpscale,
FLUX img2img, latent upscalers. Decision: Real-ESRGAN x4plus
as B.1 default; alternatives parked for B.6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Install Real-ESRGAN x4plus model

**Files:**
- Download: `D:/assets/animators/ComfyUI/models/upscale_models/RealESRGAN_x4plus.pth`

- [ ] **Step 1: Confirm the canonical download URL is current**

The official Real-ESRGAN release model is at:
```
https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth
```
This URL has been stable since 2021. If the GitHub repo has moved or the URL no longer resolves, search for "RealESRGAN_x4plus.pth official release" before proceeding.

- [ ] **Step 2: Download the model**

Run:
```powershell
$dest = "D:/assets/animators/ComfyUI/models/upscale_models/RealESRGAN_x4plus.pth"
curl -L -o $dest "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
```
Expected: 67040989 bytes (~64 MB).

- [ ] **Step 3: Verify the file size and that it loads**

Run:
```powershell
Get-Item "D:/assets/animators/ComfyUI/models/upscale_models/RealESRGAN_x4plus.pth" | Select-Object Length
```
Expected: `Length: 67040989`. If significantly different, the download was truncated or wrong file.

- [ ] **Step 4: Confirm ComfyUI sees the model**

Run:
```powershell
curl -fsS "http://127.0.0.1:8188/object_info/UpscaleModelLoader" 2>&1 | python -c "import sys,json; d=json.load(sys.stdin); print(d['UpscaleModelLoader']['input']['required']['model_name'][0])"
```
Expected: a list including `RealESRGAN_x4plus.pth`. If not present, restart ComfyUI to pick up the new file (ComfyUI rescans `upscale_models/` at startup).

- [ ] **Step 5: No commit**

`.pth` files should not be committed to git. Verify it's already gitignored:
```bash
git check-ignore "animators/ComfyUI/models/upscale_models/RealESRGAN_x4plus.pth" || echo "NOT IGNORED — investigate"
```
If "NOT IGNORED", add `animators/ComfyUI/models/upscale_models/*.pth` to `.gitignore` before continuing.

---

## Task 3: Build the bare SR workflow function

This is the ComfyUI-side workflow definition — the JSON dict passed via `queue_prompt`. Pattern: same as `workflow_text2img_klein` and `workflow_img2img_klein` in `flux_seamless.py`.

**Files:**
- Create: `pipelines/textures/sr_upscale.py` (initial skeleton)

- [ ] **Step 1: Create the file with the workflow function only**

Create `D:/assets/pipelines/textures/sr_upscale.py`:

```python
"""Real-ESRGAN single-map super-resolution for tileable textures.

Drop-in 4x upscaler using ComfyUI's UpscaleModelLoader +
ImageUpscaleWithModel nodes. Tile preservation via offset+heal trick
(see flux_seamless.py / flux_upscale.py for the established pattern).

Usage:
  python sr_upscale.py --in albedo.png --out albedo_4k.png

  # Disable the offset trick (faster, may break tile seams):
  python sr_upscale.py --in albedo.png --out albedo_4k.png --no-offset-trick

  # Use a different upscale model:
  python sr_upscale.py --in albedo.png --out out.png \\
      --model realesr-general-x4v3.pth

Phase B.1 deliverable. See:
  docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md
  pipelines/textures/EXTERNAL_SR_TECHNIQUES.md
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
from PIL import Image

from flux_seamless import (
    queue_prompt, wait_for, download_output, upload_image,
    offset_image, edge_seam_score,
    COMFY_HOST,
)


def workflow_upscale_with_model(input_image_name: str, model_name: str,
                                 prefix: str = "sr_upscale") -> dict:
    """ComfyUI workflow: load image → load upscale model → upscale → save.

    Mirrors the structure of workflow_img2img_klein in flux_seamless.py
    but with no diffusion — just deterministic SR via the upscale model.

    Returns a workflow dict suitable for queue_prompt().
    """
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": input_image_name},
        },
        "2": {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": model_name},
        },
        "3": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {
                "upscale_model": ["2", 0],
                "image": ["1", 0],
            },
        },
        "70": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["3", 0],
                "filename_prefix": prefix,
            },
        },
    }


def main():
    raise SystemExit("not implemented yet — see Task 4")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it imports without error**

Run:
```powershell
cd D:/assets
python -c "import sys; sys.path.insert(0, 'pipelines/textures'); from sr_upscale import workflow_upscale_with_model; wf = workflow_upscale_with_model('test.png', 'RealESRGAN_x4plus.pth'); print('OK,', len(wf), 'nodes')"
```
Expected: `OK, 4 nodes`.

- [ ] **Step 3: Submit a smoke-test workflow to ComfyUI (pre-implementation sanity)**

This confirms the workflow JSON shape is valid before writing the upload/download glue. We'll use an arbitrary image already in ComfyUI's input dir.

Run:
```powershell
cd D:/assets
python -c @'
import sys; sys.path.insert(0, "pipelines/textures")
from pathlib import Path
from flux_seamless import upload_image, queue_prompt, wait_for, download_output
from sr_upscale import workflow_upscale_with_model

src = Path("D:/assets/world/textures/library/wgv3_rock_dark/wgv3_rock_dark_albedo.png")
print(f"uploading {src}")
name = upload_image(src)
print(f"uploaded as {name}")

wf = workflow_upscale_with_model(name, "RealESRGAN_x4plus.pth", prefix="b1_smoketest")
pid = queue_prompt(wf)
print(f"queued: {pid}")

res = wait_for(pid, timeout=300)
images = res["outputs"].get("70", {}).get("images", [])
print(f"got {len(images)} image(s)")
if images:
    out = Path("__b1_smoketest.png")
    download_output("http://127.0.0.1:8188", images[0]["filename"], images[0]["subfolder"], images[0]["type"], out)
    from PIL import Image
    im = Image.open(out)
    print(f"output size: {im.size}")
    out.unlink()
'@
```
Expected output:
```
uploading D:\assets\world\textures\library\wgv3_rock_dark\wgv3_rock_dark_albedo.png
uploaded as <something>.png
queued: <uuid>
got 1 image(s)
output size: (2048, 2048)
```
(Output is 2048 because rock_dark albedo is 512 native; 512 × 4 = 2048.)

If `output size: (2048, 2048)`, the workflow shape is right. If ComfyUI returns an error, debug before continuing — common failures:
- Model not found → restart ComfyUI to rescan `upscale_models/`
- LoadImage node can't find input → upload failed; check `flux_seamless.upload_image` return value
- Workflow validation error → inspect the prompt body in ComfyUI's terminal log

- [ ] **Step 4: Commit**

```bash
git add pipelines/textures/sr_upscale.py
git commit -m "$(cat <<'EOF'
B.1: sr_upscale.py workflow skeleton

ComfyUI workflow function for Real-ESRGAN SR via UpscaleModelLoader
+ ImageUpscaleWithModel. Mirrors workflow_img2img_klein structure
from flux_seamless.py. No CLI yet — that lands in Task 4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Build the upscale-with-tile-preservation function and CLI

**Files:**
- Modify: `pipelines/textures/sr_upscale.py` (replace the `main()` stub with the real implementation)

- [ ] **Step 1: Replace the `main()` stub with the full upscale function + CLI**

Edit `D:/assets/pipelines/textures/sr_upscale.py`. Replace the entire `def main():` block (the `raise SystemExit(...)` placeholder) with this:

```python
def upscale_one(input_path: Path, output_path: Path, model_name: str,
                 use_offset_trick: bool = True,
                 host: str = COMFY_HOST) -> dict:
    """SR a single tileable image. Returns a metrics dict.

    use_offset_trick=True: shift→SR→reverse-shift to keep outer edges
    tileable. Adds one round-trip but is the safe default.

    use_offset_trick=False: SR raw. Faster, may break tile seams at
    the outer edge. Use only if you don't care about tileability.
    """
    src = Image.open(input_path).convert("RGB")
    src_arr = np.asarray(src)
    pre_score = edge_seam_score(src_arr)
    print(f"  input  {src.size[0]}x{src.size[1]}  edge_seam_score={pre_score:.5f}")

    # Stage the (optionally offset) image into ComfyUI's input dir
    if use_offset_trick:
        staged_arr = offset_image(src_arr)
        print(f"  offset trick on (shift to interior)")
    else:
        staged_arr = src_arr
        print(f"  offset trick OFF (raw SR)")

    tmp = Path("__sr_staged.png")
    Image.fromarray(staged_arr).save(tmp)

    server_name = upload_image(tmp, host=host)
    wf = workflow_upscale_with_model(server_name, model_name,
                                      prefix=f"sr_{input_path.stem}")
    print(f"  queued upscale: model={model_name}")
    t0 = time.time()
    pid = queue_prompt(wf, host=host)
    res = wait_for(pid, host=host, timeout=600)
    elapsed = time.time() - t0
    print(f"  upscale done in {elapsed:.1f}s")

    images = res["outputs"].get("70", {}).get("images", [])
    if not images:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("no images returned from SR workflow")

    sr_tmp = Path("__sr_result.png")
    download_output(host, images[0]["filename"], images[0]["subfolder"],
                    images[0]["type"], sr_tmp)
    sr_arr = np.asarray(Image.open(sr_tmp).convert("RGB"))

    if use_offset_trick:
        # Reverse the offset to put the original outer edges back on the outside
        final_arr = offset_image(sr_arr)
    else:
        final_arr = sr_arr

    post_score = edge_seam_score(final_arr)
    final_im = Image.fromarray(final_arr)
    final_im.save(output_path)
    print(f"  output {final_im.size[0]}x{final_im.size[1]}  edge_seam_score={post_score:.5f}")

    tmp.unlink(missing_ok=True)
    sr_tmp.unlink(missing_ok=True)

    return {
        "input": str(input_path),
        "output": str(output_path),
        "model": model_name,
        "use_offset_trick": use_offset_trick,
        "input_size": list(src.size),
        "output_size": list(final_im.size),
        "scale": final_im.size[0] / src.size[0],
        "edge_seam_score_pre": float(pre_score),
        "edge_seam_score_post": float(post_score),
        "elapsed_sec": round(elapsed, 2),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="input", type=Path, required=True,
                    help="input PNG (any single-map texture)")
    ap.add_argument("--out", dest="output", type=Path, required=True,
                    help="output PNG path")
    ap.add_argument("--model", default="RealESRGAN_x4plus.pth",
                    help="upscale model file in ComfyUI/models/upscale_models/")
    ap.add_argument("--no-offset-trick", action="store_true",
                    help="disable the offset+heal trick (faster, may break tile seams)")
    ap.add_argument("--host", default=COMFY_HOST,
                    help="ComfyUI host URL")
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    info = upscale_one(args.input, args.output, args.model,
                       use_offset_trick=not args.no_offset_trick,
                       host=args.host)
    print(f"\ndone -> {args.output}")
    print(f"  scale: {info['scale']:.2f}x")
    print(f"  seam: {info['edge_seam_score_pre']:.5f} -> {info['edge_seam_score_post']:.5f}")
```

- [ ] **Step 2: Verify the CLI shows help**

Run:
```powershell
cd D:/assets
python pipelines/textures/sr_upscale.py --help
```
Expected: argparse help text including `--in`, `--out`, `--model`, `--no-offset-trick`, `--host`.

- [ ] **Step 3: Run on the canonical test input (rock_dark albedo)**

Run:
```powershell
cd D:/assets
python pipelines/textures/sr_upscale.py `
  --in "world/textures/library/wgv3_rock_dark/wgv3_rock_dark_albedo.png" `
  --out "D:/tmp/b1_rock_dark_albedo_4x.png"
```
Expected output:
```
  input  512x512  edge_seam_score=0.00XXX
  offset trick on (shift to interior)
  queued upscale: model=RealESRGAN_x4plus.pth
  upscale done in ~10s
  output 2048x2048  edge_seam_score=0.00XXX

done -> D:/tmp/b1_rock_dark_albedo_4x.png
  scale: 4.00x
  seam: 0.00XXX -> 0.00XXX
```

Critical check: **the `edge_seam_score_post` must be in the same order of magnitude as `edge_seam_score_pre`**. If post is >2x pre, the offset trick isn't preserving tiles correctly — investigate before continuing.

- [ ] **Step 4: Quick visual sanity check**

Open `D:/tmp/b1_rock_dark_albedo_4x.png` and the source `wgv3_rock_dark_albedo.png` in any image viewer side-by-side. The SR'd version should:
- Be 4× larger (2048 vs 512)
- Show micro-detail that wasn't visible in the source (this is expected — Real-ESRGAN hallucinates plausible detail)
- Not have visible artifacts at the outer edges (no obvious bands, no color shifts, no resolution discontinuities at edges)

If visual check fails (visible edge artifacts, blurry/blocky output, color cast), the install or workflow has a problem. Common causes: wrong model file, ComfyUI not picking up the model, wrong workflow node IDs.

- [ ] **Step 5: Commit**

```bash
git add pipelines/textures/sr_upscale.py
git commit -m "$(cat <<'EOF'
B.1: sr_upscale.py CLI + tile-preserving upscale

upscale_one() function does offset → SR → reverse-offset to preserve
outer-edge tileability. Measures edge_seam_score pre/post for
verification. CLI: --in, --out, --model, --no-offset-trick, --host.

Verified on wgv3_rock_dark_albedo.png: 512 -> 2048 in ~10s,
seam score preserved within tolerance.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Validate offset-trick effectiveness (A/B)

The whole point of the offset trick is to keep tiles tileable. Verify
empirically by running with and without it on the same input.

**Files:** none (read-only validation)

- [ ] **Step 1: Run without the offset trick for comparison**

Run:
```powershell
cd D:/assets
python pipelines/textures/sr_upscale.py `
  --in "world/textures/library/wgv3_rock_dark/wgv3_rock_dark_albedo.png" `
  --out "D:/tmp/b1_rock_dark_albedo_4x_NO_OFFSET.png" `
  --no-offset-trick
```
Note the `edge_seam_score_post` value.

- [ ] **Step 2: Compare scores**

Compare the post-scores from Task 4 (with offset trick) and Task 5 Step 1 (without). Expected: with-offset-trick score is materially better (lower) than without. If they're equal, the offset trick isn't earning its keep — note in TEXTURE_RND, but it's likely the trick still helps on harder cases (test on snow / leaf_litter in Task 6).

- [ ] **Step 3: Visual A/B (optional but informative)**

Tile both outputs 2x2 and look for visible seams at the boundaries. The simplest way:

```powershell
python -c @'
from PIL import Image
for tag in ["with_offset", "no_offset"]:
    src = "D:/tmp/b1_rock_dark_albedo_4x.png" if tag == "with_offset" else "D:/tmp/b1_rock_dark_albedo_4x_NO_OFFSET.png"
    im = Image.open(src)
    grid = Image.new("RGB", (im.width * 2, im.height * 2))
    for x in (0, im.width):
        for y in (0, im.height):
            grid.paste(im, (x, y))
    out = f"D:/tmp/b1_rock_dark_tile2x2_{tag}.png"
    grid.save(out)
    print(f"wrote {out}")
'@
```

Open both `_tile2x2_*.png` files. Look for visible seam lines at the midpoints (horizontal and vertical). The `with_offset` version should be cleaner.

- [ ] **Step 4: No commit (validation only)**

Note the findings; they get written into the TEXTURE_RND.md entry in Task 8.

---

## Task 6: Run on three representative materials (the A/B set)

The Phase A.2 "representative materials" set is: volcanic, snow, sand, grass, leaf_litter (× 3 seeds). For B.1's purposes, **3 materials covering different difficulty profiles** are enough:

- **wgv3_rock_dark** — hard-edge geometry, strong micro-detail, the flagship for Phase B
- **wgv3_snow** — smooth/uniform surface, the failure mode where SR is most likely to hallucinate wrong micro-detail
- **wgv3_forest_floor** — heterogeneous (leaves + dirt), the "tile-prone-to-lattice" case from A.2

**Files:**
- Create: `world3/docs/captures/phase_b/B1_sr_survey/` (and contents)

- [ ] **Step 1: Confirm the inputs exist**

Run:
```powershell
$ids = @("wgv3_rock_dark", "wgv3_snow", "wgv3_forest_floor")
foreach ($id in $ids) {
    $src = "D:/assets/world/textures/library/$id/${id}_albedo.png"
    if (Test-Path $src) {
        $size = (Get-Item $src).Length
        Write-Host "OK  $id  ($size bytes)"
    } else {
        Write-Host "MISSING  $src"
    }
}
```
Expected: all three present.

If any are missing, generate them via `aaa_texture.py` per the existing cookbook prompts in `pipelines/textures/TEXTURE_RND.md` Part 2, or substitute another material that exists and serves the same role. Document the substitution in the TEXTURE_RND entry.

- [ ] **Step 2: Create the captures dir**

Run:
```powershell
$dir = "D:/assets/world3/docs/captures/phase_b/B1_sr_survey"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Write-Host "created $dir"
```

- [ ] **Step 3: Run Real-ESRGAN SR on each albedo**

Run:
```powershell
cd D:/assets
$ids = @("wgv3_rock_dark", "wgv3_snow", "wgv3_forest_floor")
foreach ($id in $ids) {
    python pipelines/textures/sr_upscale.py `
      --in "world/textures/library/$id/${id}_albedo.png" `
      --out "world3/docs/captures/phase_b/B1_sr_survey/${id}_realesrgan_4x.png"
}
```
Expected: each runs in ~10-15s; outputs are 2048x2048 (since wgv3 albedos are 512 native).

Capture the per-material `edge_seam_score_pre` and `edge_seam_score_post` printed by each run — write them down or re-derive in Step 6.

- [ ] **Step 4: Run Lanczos baseline on each**

For comparison, also produce a Lanczos 4x upscale (the no-install baseline that `upscale_biome_set.py` uses):

```powershell
cd D:/assets
python -c @'
from pathlib import Path
from PIL import Image
ids = ["wgv3_rock_dark", "wgv3_snow", "wgv3_forest_floor"]
for id in ids:
    src = f"D:/assets/world/textures/library/{id}/{id}_albedo.png"
    dst = f"D:/assets/world3/docs/captures/phase_b/B1_sr_survey/{id}_lanczos_4x.png"
    im = Image.open(src)
    out = im.resize((im.width * 4, im.height * 4), Image.LANCZOS)
    out.save(dst)
    print(f"  {id}: {im.size} -> {out.size}  ->  {dst}")
'@
```

- [ ] **Step 5: Run flux_upscale heal-pass on each (for completeness)**

Compares against the existing FLUX path. Note this only goes to 2K (not 4K) because flux_upscale was designed for 2K hero output.

```powershell
cd D:/assets
$ids = @("wgv3_rock_dark", "wgv3_snow", "wgv3_forest_floor")
foreach ($id in $ids) {
    $src = "world/textures/library/$id/${id}_albedo.png"
    $dst = "world3/docs/captures/phase_b/B1_sr_survey/${id}_flux_2k.png"
    python pipelines/textures/flux_upscale.py `
      --input $src --output $dst --target 2048 `
      --prompt "tileable photorealistic surface texture"
}
```

Note: this is slow (~60-90s per map). If it errors, log the error in the TEXTURE_RND entry (it may be that flux_upscale needs an update, which becomes a B.6-or-later note). Don't block on this; we're documenting the comparison, and "flux_upscale errored on these inputs" is itself useful information.

- [ ] **Step 6: Build a per-material contact sheet (3 cols × 3 rows)**

Three columns (Lanczos / Real-ESRGAN / FLUX), three rows (one per material), each cell shows a center 512×512 crop of the upscaled output for fair visual comparison (since they're at different output resolutions: 4K, 4K, 2K).

```powershell
cd D:/assets
python -c @'
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

base = Path("D:/assets/world3/docs/captures/phase_b/B1_sr_survey")
ids = ["wgv3_rock_dark", "wgv3_snow", "wgv3_forest_floor"]
methods = [("Lanczos 4x",  "lanczos_4x.png"),
           ("Real-ESRGAN 4x", "realesrgan_4x.png"),
           ("FLUX heal 2K", "flux_2k.png")]

CROP = 512
PAD = 16
LABEL_H = 28

cell_w, cell_h = CROP, CROP + LABEL_H
sheet_w = cell_w * len(methods) + PAD * (len(methods) + 1)
sheet_h = cell_h * len(ids) + PAD * (len(ids) + 1)

sheet = Image.new("RGB", (sheet_w, sheet_h), (32, 32, 32))
draw = ImageDraw.Draw(sheet)

for r, id in enumerate(ids):
    for c, (label, suffix) in enumerate(methods):
        path = base / f"{id}_{suffix}"
        x = PAD + c * (cell_w + PAD)
        y = PAD + r * (cell_h + PAD)
        if not path.exists():
            draw.text((x, y + 8), f"{label}\n{id}\nMISSING", fill=(200, 100, 100))
            continue
        im = Image.open(path).convert("RGB")
        # Center crop CROP x CROP
        cx, cy = im.width // 2, im.height // 2
        crop = im.crop((cx - CROP // 2, cy - CROP // 2, cx + CROP // 2, cy + CROP // 2))
        sheet.paste(crop, (x, y + LABEL_H))
        draw.text((x + 4, y + 4), f"{id}  -  {label}", fill=(220, 220, 220))

out = base / "_contact_sheet.png"
sheet.save(out)
print(f"wrote {out}")
'@
```

Expected: a 3-column-by-3-row grid PNG at `world3/docs/captures/phase_b/B1_sr_survey/_contact_sheet.png` showing center crops of each material × method.

- [ ] **Step 7: Visual review**

Open the contact sheet. Look for:

- **Real-ESRGAN vs Lanczos**: Real-ESRGAN should show *more* micro-detail than Lanczos (which is just a smoother stretch). On `rock_dark`, Real-ESRGAN should make crystal/grain edges sharper. On `snow`, *check carefully* — Real-ESRGAN may hallucinate non-snow micro-detail (this is the predicted failure mode and is fine to surface here).
- **Real-ESRGAN vs FLUX heal**: FLUX heal at 2K should look more "FLUX-style" coherent; Real-ESRGAN at 4K should look more pixel-accurate-but-less-stylistically-coherent. They're solving different problems.
- **Tile coherence**: not visible in this contact sheet (it crops the center), but the per-material `edge_seam_score_post` numbers from Step 3 cover this quantitatively.

Take notes for the TEXTURE_RND.md entry in Task 8.

- [ ] **Step 8: Commit the captures**

```bash
git add world3/docs/captures/phase_b/
git commit -m "$(cat <<'EOF'
B.1: SR comparison captures (Real-ESRGAN vs Lanczos vs FLUX heal)

3 materials x 3 methods contact sheet at
world3/docs/captures/phase_b/B1_sr_survey/_contact_sheet.png
plus per-method per-material full-resolution outputs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Audit `flux_upscale.py` and document its repositioning

**Files:**
- Read: `pipelines/textures/flux_upscale.py` (read-only audit)
- Modify: `pipelines/textures/flux_upscale.py` (docstring update only — no behavior change)

- [ ] **Step 1: Re-read `flux_upscale.py` with the new framing in mind**

Open `D:/assets/pipelines/textures/flux_upscale.py`. Confirm what the spec already documented:
- Albedo only (lines 92-94, 107-128 — `--material` mode only touches albedo)
- Bilinear upscale (LANCZOS in PIL terms, line 53) followed by FLUX img2img heal at low denoise (default 0.18, line 102)
- Tile-preserving via offset+heal (lines 57-58, 78)
- Default target 2048; supports up to 4096 (line 94)
- Slower than Real-ESRGAN (FLUX img2img is ~30-60s per pass)

- [ ] **Step 2: Update the module docstring to reflect repositioning**

Edit `D:/assets/pipelines/textures/flux_upscale.py`. Replace the current module docstring (lines 1-16) with:

```python
"""FLUX img2img heal-pass tool for tileable textures.

REPOSITIONED IN PHASE B.1 (2026-05-07): no longer the primary
super-resolution tool. Real-ESRGAN via sr_upscale.py is now the
default SR backend; this tool is the "heal pass" that polishes a
near-shipping image at the same (or higher) resolution to recover
FLUX-style coherence after generation or after Real-ESRGAN SR.

Two-stage approach (preserves tiling):
  1. Bilinear upscale to 2x (1024 -> 2048)
  2. FLUX img2img low-denoise refinement (recovers detail without altering structure)
  3. Repeat for 4K

We use the same offset trick to keep tiling intact through the upscale: shift
the 2x'd image, denoise, shift back.

Albedo-only. Other PBR maps are handled by the bake step in B.2
(re-derived from upscaled height + albedo).

For most game uses 2K is plenty. 4K is for hero materials.

Usage:
  python flux_upscale.py --material world/textures/library/cobblestone_aaa --target 2048
  python flux_upscale.py --input some_albedo.png --output upscaled.png --target 4096

See also:
  pipelines/textures/sr_upscale.py — primary SR (Real-ESRGAN)
  pipelines/textures/EXTERNAL_SR_TECHNIQUES.md — survey + decision rationale
"""
```

- [ ] **Step 3: Verify the file still imports**

Run:
```powershell
cd D:/assets
python -c "import sys; sys.path.insert(0, 'pipelines/textures'); import flux_upscale; print('OK')"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add pipelines/textures/flux_upscale.py
git commit -m "$(cat <<'EOF'
B.1: reposition flux_upscale.py as heal-pass tool

Docstring update only. Real-ESRGAN via sr_upscale.py is now the
primary SR backend (Phase B.1 decision). flux_upscale.py keeps its
existing role as the FLUX img2img heal pass for FLUX-style coherence
recovery. No behavior change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Document in TEXTURE_RND.md

**Files:**
- Modify: `pipelines/textures/TEXTURE_RND.md`

- [ ] **Step 1: Find the current end of Part 1 (sweeps log)**

Run:
```bash
grep -n "^## A\.\|^## B\.\|^# Part 2\|^## Part 2" "D:/assets/pipelines/textures/TEXTURE_RND.md" | head -30
```
Find the heading immediately before "Part 2" (the cookbook). The B.1 entry goes right after the last "## A.X" entry and before Part 2.

- [ ] **Step 2: Append the B.1 entry**

Insert this section at the appropriate location (after the last A.X entry, before Part 2):

```markdown
## B.1 — SR survey + Real-ESRGAN as default backend (2026-05-07)

**What:** First Phase B sub-step. Surveyed SR backends, chose Real-ESRGAN
x4plus as default, wrote `sr_upscale.py` with offset+heal tile preservation,
A/B'd against Lanczos and FLUX heal on 3 representative materials.

**Survey doc:** `pipelines/textures/EXTERNAL_SR_TECHNIQUES.md`
**A/B captures:** `world3/docs/captures/phase_b/B1_sr_survey/`

**Decision: Real-ESRGAN x4plus as B.1 default.**
- Drop-in via ComfyUI's `UpscaleModelLoader` + `ImageUpscaleWithModel`.
- Fast (~10-15s per 512→2048 map on 5090).
- BSD-3-Clause license.
- Alternatives parked for B.6 if survey or B.5 flagship A/B surfaces a need.

**Reposition: `flux_upscale.py` is now the heal-pass tool**, not the
SR backbone. Docstring updated; behavior unchanged.

**A/B findings (3 materials × 3 methods):**

| Material | Lanczos | Real-ESRGAN | FLUX heal (2K) | Notes |
|----------|---------|-------------|----------------|-------|
| rock_dark | smooth/blurred | sharp grain | FLUX-coherent | Real-ESRGAN visibly recovered crystal edges; expected win on hard-edge geometry. |
| snow | smooth | <see contact sheet, fill in> | <fill in> | Watch for hallucinated non-snow micro-detail in Real-ESRGAN — predicted failure mode. |
| forest_floor | smooth heterogeneous | <fill in> | <fill in> | Heterogeneous case — does Real-ESRGAN preserve leaf-vs-dirt boundaries? |

(Fill in the per-material observations after running Task 6.)

**Tile coherence (offset+heal trick effectiveness):**

| Material | edge_seam_score (input) | post-SR (with offset) | post-SR (no offset) |
|----------|-------------------------|------------------------|----------------------|
| rock_dark | <fill in> | <fill in> | <fill in> |
| snow | <fill in> | <fill in> | <fill in> |
| forest_floor | <fill in> | <fill in> | <fill in> |

(Fill in from Tasks 4-5 output. Expected: with-offset stays within ~2x of input score; no-offset is materially worse.)

**Open / surfaced for later steps:**
- (record any surprises or "we should look into X" items here)

**Time spent:** ~half session.
**Next:** B.2 — `bake_pbr.py` (high-res re-derive of normal/AO/roughness from upscaled albedo+height).
```

- [ ] **Step 3: Verify the file is well-formed**

Run:
```bash
grep -c "^## " "D:/assets/pipelines/textures/TEXTURE_RND.md"
```
Note the count is one higher than before. Then visually confirm the section reads correctly:
```bash
grep -A 2 "^## B\.1" "D:/assets/pipelines/textures/TEXTURE_RND.md"
```

- [ ] **Step 4: Commit**

```bash
git add pipelines/textures/TEXTURE_RND.md
git commit -m "$(cat <<'EOF'
B.1: TEXTURE_RND entry — SR survey + Real-ESRGAN default

A/B findings table, tile coherence measurements, decision rationale.
Cross-references EXTERNAL_SR_TECHNIQUES.md and the captures dir.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Update TOOLS.md and RECIPES.md

**Files:**
- Modify: `pipelines/textures/TOOLS.md`
- Modify: `pipelines/textures/RECIPES.md`

- [ ] **Step 1: Add `sr_upscale.py` to TOOLS.md**

Open `D:/assets/pipelines/textures/TOOLS.md`. Find the existing `flux_upscale.py` entry (search for "flux_upscale"). Add a new entry for `sr_upscale.py` immediately before it (so the SR tools are grouped):

```markdown
### `sr_upscale.py` — Real-ESRGAN single-map super-resolution

**What:** Drop-in 4× SR for any single tileable PNG (albedo, height,
normal, roughness, etc.) via ComfyUI's `UpscaleModelLoader` +
`ImageUpscaleWithModel` nodes with the Real-ESRGAN x4plus model.
Tile preservation via offset+heal trick.

**Reach for it when:** You need to upscale one map by 4×. Default SR
tool for the multi-resolution pipeline (Phase B.1+). For multi-map
PBR sets, use the orchestrator (`aaa_texture.py --ladder`, lands in B.5)
which composes this with `bake_pbr.py` and `mip_ladder.py`.

**Don't reach for it when:**
- You want FLUX-style coherence recovery — use `flux_upscale.py`
  instead (it's the heal-pass tool, not SR proper).
- You don't have ComfyUI running — use `upscale_biome_set.py` (Lanczos
  baseline, no-install fallback).

**Output:** Single PNG at the upscaled resolution.

**See also:** `EXTERNAL_SR_TECHNIQUES.md` for the survey that justifies
the choice; B.2's `bake_pbr.py` for what to do with the SR'd output.
```

- [ ] **Step 2: Update the existing `flux_upscale.py` entry to reflect repositioning**

In the same file, find the existing `flux_upscale.py` entry. Update its "What" / "Reach for it when" sections to reflect heal-pass repositioning. If the existing entry says it's for SR, change it to say it's a heal-pass tool now (mirror the docstring update from Task 7). Leave any other content (output paths, etc.) intact.

If the existing entry doesn't have explicit "Reach for it when" sub-sections, add a short note:

```markdown
**Phase B.1 update (2026-05-07):** Repositioned as a heal-pass tool.
For SR proper, use `sr_upscale.py`. This tool is now used to recover
FLUX-style coherence after generation or after Real-ESRGAN SR.
```

- [ ] **Step 3: Add the SR recipe to RECIPES.md**

Open `D:/assets/pipelines/textures/RECIPES.md`. Find the "Quality gating + QA" section heading. Add a new top-level section *immediately before* "Quality gating + QA":

```markdown
## Upscaling

### Upscale a single map (Real-ESRGAN, default)

```powershell
python pipelines/textures/sr_upscale.py `
  --in <path/to/map.png> `
  --out <path/to/map_4x.png>
```

4× super-resolution via ComfyUI's UpscaleModelLoader + Real-ESRGAN
x4plus. ~10-15s per 512→2048 map on 5090. Tile-preserving via
offset+heal trick.

**Use when:** you need any single tileable PNG (albedo, height, etc.)
upscaled to 4× its native resolution. This is the default SR tool
for the Phase B multi-resolution pipeline.

### Upscale + heal pass (FLUX, for FLUX-style coherence)

```powershell
python pipelines/textures/flux_upscale.py `
  --input <path/to/albedo.png> `
  --output <path/to/albedo_2k.png> `
  --target 2048
```

Bilinear upscale + FLUX img2img low-denoise heal pass. Slower
(~60-90s) than Real-ESRGAN; produces "more FLUX-coherent" output
that matches generation style. Albedo only.

**Use when:** you need a near-shipping image polished to recover
FLUX style after some other transformation (or as a 2K-tier hero
albedo without going through the full SR ladder). For multi-map SR,
use `sr_upscale.py` instead.

### Lanczos baseline (no-ComfyUI fallback)

```powershell
python pipelines/textures/upscale_biome_set.py `
  --set <set_id> --factor 4
```

Pure PIL Lanczos upscale of every PBR map in a biome set. No model
required, no ComfyUI required. Quality is meaningfully worse than
Real-ESRGAN but it's the no-install baseline.

**Use when:** ComfyUI isn't available or you want a deterministic
quick-and-dirty upscale. Backs up originals to `_original_<map>.png`.
```

- [ ] **Step 4: Commit both doc updates together**

```bash
git add pipelines/textures/TOOLS.md pipelines/textures/RECIPES.md
git commit -m "$(cat <<'EOF'
B.1: TOOLS + RECIPES updates for sr_upscale.py

New tool entry, repositioned flux_upscale.py entry, new "Upscaling"
recipes section covering Real-ESRGAN / FLUX heal / Lanczos with
clear "use when" guidance per tool.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Brief PIPELINE.md mention

The full multi-resolution pipeline doc lands at B.5 when the orchestrator integrates everything. For now, just add a brief forward-looking mention so PIPELINE.md doesn't pretend the SR stage doesn't exist.

**Files:**
- Modify: `pipelines/textures/PIPELINE.md`

- [ ] **Step 1: Find an appropriate location**

Run:
```bash
grep -n "^## " "D:/assets/pipelines/textures/PIPELINE.md" | head -30
```
Look for a section about pipeline stages or a "future" / "roadmap" section. If neither exists, add at the end of the file before any "See also" footer.

- [ ] **Step 2: Add the brief section**

Append (or insert at the appropriate location):

```markdown
## Super-resolution stage (Phase B.1+)

As of Phase B.1 (2026-05-07), the pipeline has a standalone SR tool:
`sr_upscale.py` (Real-ESRGAN via ComfyUI). It's not yet wired into
`aaa_texture.py` — that integration lands in B.5 along with
`bake_pbr.py` (B.2) and `mip_ladder.py` (B.3) to form the full
multi-resolution ladder.

For now, SR is invoked manually per the recipes in
[RECIPES.md](RECIPES.md) "Upscaling" section. The
[Phase B design doc](../../docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md)
describes the full target pipeline.
```

- [ ] **Step 3: Commit**

```bash
git add pipelines/textures/PIPELINE.md
git commit -m "$(cat <<'EOF'
B.1: PIPELINE.md note about SR stage

Brief forward-looking section documenting that sr_upscale.py exists
standalone and full integration arrives at B.5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Backfill TEXTURE_RND placeholders + final pass

The TEXTURE_RND.md entry (Task 8) had `<fill in>` placeholders for the
per-material A/B observations and the seam-score table. Backfill them
now that all the runs have been done.

**Files:**
- Modify: `pipelines/textures/TEXTURE_RND.md`

- [ ] **Step 1: Backfill the A/B findings table**

Re-open `D:/tmp/b1_rock_dark_albedo_4x.png` and the contact sheet at
`world3/docs/captures/phase_b/B1_sr_survey/_contact_sheet.png`. For
each material, write a one-line observation:

- For `rock_dark`: did Real-ESRGAN sharpen the grain meaningfully vs Lanczos? Yes/no, magnitude.
- For `snow`: did Real-ESRGAN hallucinate non-snow micro-detail? Yes/no, severity.
- For `forest_floor`: did Real-ESRGAN preserve heterogeneous structure (leaves vs dirt boundaries)? Yes/no.

If the FLUX heal column ran successfully, also note its character vs Real-ESRGAN ("more coherent" / "softer" / "FLUX-style" etc.).

Edit the TEXTURE_RND.md A/B findings table to replace `<fill in>` with the actual observations.

- [ ] **Step 2: Backfill the seam-score table**

From the per-material outputs in Task 6 (Real-ESRGAN with offset trick) and Task 5 (rock_dark no-offset comparison), populate the tile coherence table.

For materials where you didn't run a "no offset" comparison, you can either:
- Run the no-offset comparison now for completeness, OR
- Note "not measured" and document the rock_dark result as the canonical demonstration.

Either is acceptable — the rock_dark with-vs-without comparison is the load-bearing one.

- [ ] **Step 3: Backfill the "Open / surfaced for later steps" section**

Write down anything surprising or worth following up on in B.2-B.6. Examples that might come up:
- "Real-ESRGAN consistently softens the height map's high-frequency detail — B.2 may want to use FLUX heal for height instead of Real-ESRGAN."
- "FLUX heal errored on snow input — investigate before B.5 flagship if FLUX heal is in the recipe."
- "Offset trick made no measurable difference on rock_dark; revisit on harder lattice-prone material in B.5."

If nothing's surprising, write "None — Real-ESRGAN behaved as expected; ready for B.2."

- [ ] **Step 4: Commit**

```bash
git add pipelines/textures/TEXTURE_RND.md
git commit -m "$(cat <<'EOF'
B.1: backfill TEXTURE_RND with measured A/B findings

Replace <fill in> placeholders with observations from the SR survey
captures. Per-material A/B observations + tile coherence table +
open items for B.2-B.6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: B.1 sign-off

**Files:** none (verification only)

- [ ] **Step 1: Run the full sequence once more end-to-end**

Sanity check that everything works after all the doc/repositioning changes. Pick one fresh material (any wgv3_* you haven't already run) and run:

```powershell
cd D:/assets
$id = "wgv3_dirt"  # or any other wgv3_* with an albedo
python pipelines/textures/sr_upscale.py `
  --in "world/textures/library/$id/${id}_albedo.png" `
  --out "D:/tmp/b1_signoff_${id}_4x.png"
```
Expected: succeeds, post-SR seam score within tolerance of input.

- [ ] **Step 2: Verify the captures dir contains everything expected**

Run:
```powershell
Get-ChildItem "D:/assets/world3/docs/captures/phase_b/B1_sr_survey/"
```
Expected: 3 materials × 2-3 methods = 6-9 PNGs + `_contact_sheet.png`.

- [ ] **Step 3: Verify all docs cross-reference correctly**

Run:
```bash
grep -l "B.1\|sr_upscale\|EXTERNAL_SR_TECHNIQUES" \
  "D:/assets/pipelines/textures/PIPELINE.md" \
  "D:/assets/pipelines/textures/TOOLS.md" \
  "D:/assets/pipelines/textures/RECIPES.md" \
  "D:/assets/pipelines/textures/TEXTURE_RND.md" \
  "D:/assets/pipelines/textures/EXTERNAL_SR_TECHNIQUES.md"
```
Expected: all 5 files listed.

- [ ] **Step 4: Verify the recent git log**

Run:
```bash
git log --oneline -15
```
Expected (in order, oldest first within the B.1 sequence):
1. `B.1 phase B kickoff: SR survey doc`
2. `B.1: sr_upscale.py workflow skeleton`
3. `B.1: sr_upscale.py CLI + tile-preserving upscale`
4. `B.1: SR comparison captures (Real-ESRGAN vs Lanczos vs FLUX heal)`
5. `B.1: reposition flux_upscale.py as heal-pass tool`
6. `B.1: TEXTURE_RND entry — SR survey + Real-ESRGAN default`
7. `B.1: TOOLS + RECIPES updates for sr_upscale.py`
8. `B.1: PIPELINE.md note about SR stage`
9. `B.1: backfill TEXTURE_RND with measured A/B findings`

- [ ] **Step 5: Mark B.1 done — no commit, just declare completion**

Print/announce: "B.1 complete. SR survey + sr_upscale.py shipped. Ready for B.2 (bake_pbr.py)."

The next session writes the B.2 plan (`docs/superpowers/plans/<date>-phase-b2-bake-pbr.md`) using this same plan as the reference template.

---

## Self-review (executed by plan author 2026-05-07)

**1. Spec coverage**
- [x] B.1 deliverable: `EXTERNAL_SR_TECHNIQUES.md` — Task 1 ✓
- [x] B.1 deliverable: `sr_upscale.py` — Tasks 3-4 ✓
- [x] B.1 deliverable: A/B contact sheet — Task 6 ✓
- [x] B.1 deliverable: TOOLS.md + RECIPES.md + TEXTURE_RND.md entries — Tasks 8, 9 ✓
- [x] B.1 deliverable: flux_upscale.py audit + repositioning — Task 7 ✓
- [x] B.1 exit criterion: `sr_upscale.py --in --out --scale 4` works on tileable input, output stays tileable (measured) — Task 4 step 3 + Task 5 ✓

**2. Placeholder scan**
- The TEXTURE_RND entry in Task 8 deliberately contains `<fill in>` placeholders that get backfilled in Task 11 — this is intentional staging, not a plan failure (each is a measurable observation from a step that runs after Task 8). ✓
- No "TODO", "later", "etc." in plan steps. ✓
- Task 7 step 2 says "Replace the current module docstring (lines 1-16)" — line numbers are based on the current state of the file (verified during plan-writing); engineer should verify lines before edit if file has changed. Acceptable specificity. ✓

**3. Type / signature consistency**
- `upscale_one()` signature in Task 4 matches the one called by `main()` in same task ✓
- `workflow_upscale_with_model()` signature in Task 3 matches the call site in Task 4 ✓
- `edge_seam_score()`, `offset_image()`, `upload_image()`, `queue_prompt()`, `wait_for()`, `download_output()`, `COMFY_HOST` are all real symbols in `flux_seamless.py` (verified via grep during plan-writing) ✓
- ComfyUI node IDs (`UpscaleModelLoader`, `ImageUpscaleWithModel`, `LoadImage`, `SaveImage`) verified against `comfy_extras/nodes_upscale_model.py` ✓
- Save node ID `"70"` in workflow matches the one used in `flux_seamless.workflow_img2img_klein` (so `res["outputs"]["70"]` extraction works) — verified ✓

**4. Validation pattern**
- No pytest infrastructure in `pipelines/textures/` (verified: zero `test_*.py` or `*_test.py` files in the dir). Plan uses real-input runs + measured QA scores + visual contact sheets per project convention. ✓
- Each task ends with a real validation step + a commit, matching the bite-sized pattern. ✓
