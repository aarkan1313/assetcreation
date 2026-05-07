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
