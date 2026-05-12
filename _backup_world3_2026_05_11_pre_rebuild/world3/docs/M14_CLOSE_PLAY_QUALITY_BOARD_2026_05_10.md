# M14 Close-Play Quality Board - 2026-05-10

## Purpose

M14 is the production-facing terrain-quality lane after M13. It does not
promote assets by itself; it feeds candidates into the M13 gate after
close, medium, iso, and topdown review.

## Summary

- Materials tracked: `5`.
- `m14_sidecar_runtime_pass_conditional`: `1`.
- `m14_sidecar_runtime_smoke_pass_conditional`: `2`.
- `m14_trial_safe_close_conditional`: `1`.
- `methodology_rework_layered_substrate`: `1`.

## Active Model Lanes

| Lane | Status | Role | Variants | Prompt Policy |
|------|--------|------|----------|---------------|
| `flux2_klein` | `active_reference` | Fast canonical material-generation lane. | `8` | FLUX-family prompts may use 'tileable seamless texture' wording. |
| `auraflow_v03` | `active_diversity` | Calmer or more uniform alternate lane, useful for organic ground. | `8` | Prefer 'edge-to-edge overhead material sample' wording; keep tileability explicit but avoid decorative-tile cues. |
| `sd35_large` | `active_experimental` | Photoreal alternate lane for forest/organic ground, center-bias watchlist. | `8` | Avoid the word 'tileable'; use 'uniform overhead edge-to-edge material scan, no central focal point'. |
| `flux2_klein_9b_nvfp4` | `candidate_pending_bakeoff_2026_05_10` | Bigger FLUX 2 (9B distilled) Blackwell-native 4-bit lane. Pending head-to-head against klein-4B + FP8/Q8 quants. Expected production lane on RTX 5090 Laptop if quality A/B holds. | `8` | Same as flux2_klein. FLUX 2 family parses 'tileable seamless texture' correctly. |
| `flux2_klein_9b_fp8` | `candidate_pending_bakeoff_2026_05_10` | BFL-official FP8 quant of klein-9B. Quality-anchor for the NVFP4-vs-FP8-vs-Q8 A/B; expected to win on quality but lose to NVFP4 on speed. | `8` | Same as flux2_klein. |
| `flux2_klein_9b` | `candidate_pending_bakeoff_2026_05_10` | Community Q8 GGUF reference for the quant A/B. Will likely be deleted post-bakeoff (BFL-official quants preferred). | `8` | Same as flux2_klein. |
| `flux2_dev_nvfp4` | `candidate_hero_pending_bakeoff_2026_05_10` | FLUX 2 dev (32B undistilled) NVFP4 hero-quality lane. ~4 sec/img vs <1 sec for klein-9B; expected role is single-best-of-N hero textures, not fan-out. | `4` | Dev supports longer prompts (80-150 words) more faithfully than klein. CFG=4, 28 steps. Otherwise same FLUX-family wording. |

## Material Board

| Material | Status | Latest | Next Action | Failure Mode |
|----------|--------|--------|-------------|--------------|
| `grassland_grass` | `m14_trial_safe_close_conditional` | `m8_grassland_grass_calm_v3` | Keep sidecar-only; use M14 bakeoff lanes for stronger close-play candidates. | object-like dry grass blades and noisy yellow clumps dominate close views |
| `grass` | `methodology_rework_layered_substrate` | `3 M14 attempts through m14_grass_substrate_v3` | Keep M14 grass work limited to substrate/detail candidates; let M15 scatter/features carry actual blades, clumps, dry stems, and vegetation identity. | green organic speckle and small clover/object repetition reads too busy at walk scale |
| `temperate_forest_grass` | `m14_sidecar_runtime_pass_conditional` | `3 M14 attempts through m14_temperate_forest_humus_v3` | Keep as accepted M14 sidecar evidence; do not M13-promote until true forest-source review plus M15 scatter/features exist. Move visible organic identity to M15 scatter/decal/features. | leaf-litter objects and high contrast fragments create visual noise in close terrain |
| `tundra_moss` | `m14_sidecar_runtime_smoke_pass_conditional` | `5 M14 attempts through m14_tundra_moss_flux50` | Keep as accepted M14 sidecar evidence; do not M13-promote until true tundra/alpine source-context review plus M15 scatter/features exist. Move visible tundra identity to M15 scatter/decal/features. | moss detail is too high-frequency and can turn into colored speckle in runtime |
| `tundra_lichen` | `m14_sidecar_runtime_smoke_pass_conditional` | `2 M14 attempts through m14_tundra_lichen_biocrust_flux10` | Keep as accepted M14 sidecar workflow evidence; do not M13-promote until true tundra/alpine source-context review plus M15 scatter/decal features exist. | lichen spots and pale contrast can repeat as visible object clusters |

## Candidate Gate

- Seam/PBR QA filters candidates but does not promote them.
- Visual veto rejects object landmarks, box panels, bright islands, central compositions, decorative tile motifs, and hero-shot depth of field.
- Organic blockers should use broad curation: identify the viable model lane, run 10-50 same-model prompt-family samples when fast enough, then shortlist by 2x2 visual review.
- Survivors require Godot terrain-context review in close, medium, iso, and topdown bands.
- Close-play promotion requires source macro to stay low-frequency and generated PBR detail to carry near-field grain.
- Promotion requires an explicit M13 manifest state change; M14 does not bypass M13.

## Parked Or Rejected Lanes

| Lane | Status | Reason |
|------|--------|--------|
| `qwen_image` | `parked_files_deleted_2026_05_10` | Hero-shot/DOF bias and slow runtime; weights deleted from disk 2026-05-10 (~26 GB reclaimed). Re-download qwen-image-Q6_K.gguf + qwen_2.5_vl_7b_fp8_scaled.safetensors + qwen_image_vae.safetensors to revive. |
| `chroma1_hd` | `rejected_files_deleted_2026_05_10` | Failed current ground-texture prompt family with decorative-tile/grid artifacts. chroma1-hd-Q8_0.gguf deleted 2026-05-10 (~9.7 GB reclaimed). Re-download from city96/Chroma1-HD-gguf to revive. |

## Next Move

1. Treat current M14 organic results as workflow evidence and sidecar
   candidates, not production-promoted terrain content.
2. Do not spend more M14 time trying to make flat ground textures carry
   all grass, moss, lichen, leaf, or debris identity.
3. Move the next visual-quality push to M15 scatter/decal/features, using
   the accepted sidecars and source-stack masks as inputs.
4. Current sidecar/material evidence covers: `grassland_grass, temperate_forest_grass, tundra_moss, tundra_lichen`.

Regenerate:

```powershell
python world3/pipeline/build_m14_close_play_quality_board.py
```
