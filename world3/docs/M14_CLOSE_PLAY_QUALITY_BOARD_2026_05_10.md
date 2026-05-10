# M14 Close-Play Quality Board - 2026-05-10

## Purpose

M14 is the production-facing terrain-quality lane after M13. It does not
promote assets by itself; it feeds candidates into the M13 gate after
close, medium, iso, and topdown review.

## Summary

- Materials tracked: `5`.
- `m14_flux50_shortlist_for_live_review`: `1`.
- `m14_sidecar_runtime_pass_conditional`: `1`.
- `m14_trial_safe_close_conditional`: `1`.
- `methodology_rework_layered_substrate`: `1`.
- `queued_for_bakeoff`: `1`.

## Active Model Lanes

| Lane | Status | Role | Variants | Prompt Policy |
|------|--------|------|----------|---------------|
| `flux2_klein` | `active_reference` | Fast canonical material-generation lane. | `8` | FLUX-family prompts may use 'tileable seamless texture' wording. |
| `auraflow_v03` | `active_diversity` | Calmer or more uniform alternate lane, useful for organic ground. | `8` | Prefer 'edge-to-edge overhead material sample' wording; keep tileability explicit but avoid decorative-tile cues. |
| `sd35_large` | `active_experimental` | Photoreal alternate lane for forest/organic ground, center-bias watchlist. | `8` | Avoid the word 'tileable'; use 'uniform overhead edge-to-edge material scan, no central focal point'. |

## Material Board

| Material | Status | Latest | Next Action | Failure Mode |
|----------|--------|--------|-------------|--------------|
| `grassland_grass` | `m14_trial_safe_close_conditional` | `m8_grassland_grass_calm_v3` | Keep sidecar-only; use M14 bakeoff lanes for stronger close-play candidates. | object-like dry grass blades and noisy yellow clumps dominate close views |
| `grass` | `methodology_rework_layered_substrate` | `3 M14 attempts through m14_grass_substrate_v3` | Keep M14 grass work limited to substrate/detail candidates; let M15 scatter/features carry actual blades, clumps, dry stems, and vegetation identity. | green organic speckle and small clover/object repetition reads too busy at walk scale |
| `temperate_forest_grass` | `m14_sidecar_runtime_pass_conditional` | `3 M14 attempts through m14_temperate_forest_humus_v3` | Keep as accepted M14 sidecar evidence; do not M13-promote until true forest-source review plus M15 scatter/features exist. Continue to tundra_moss and tundra_lichen bakeoffs. | leaf-litter objects and high contrast fragments create visual noise in close terrain |
| `tundra_moss` | `m14_flux50_shortlist_for_live_review` | `5 M14 attempts through m14_tundra_moss_flux50` | Live-review the FLUX 50 shortlist sheet, then stage the chosen B-family tundra substrate sidecar in a close/medium/iso/topdown terrain scene before any M13 promotion. | moss detail is too high-frequency and can turn into colored speckle in runtime |
| `tundra_lichen` | `queued_for_bakeoff` | `-` | Run FLUX/Aura/SD batches, then visual-veto before terrain staging. | lichen spots and pale contrast can repeat as visible object clusters |

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
| `qwen_image` | `parked` | Hero-shot/DOF bias and slow runtime; needs a dedicated material-scan prompt family before reconsideration. |
| `chroma1_hd` | `rejected_for_m14` | Failed current ground-texture prompt family with decorative-tile/grid artifacts. |

## Next Move

1. Live-review the `tundra_moss` FLUX 50 shortlist and choose whether
   the B-family pale substrate direction is acceptable.
2. Stage the accepted `tundra_moss` sidecar in a close/medium/iso/topdown
   terrain-context scene before any M13 promotion.
3. Start `tundra_lichen` with the same method: small multi-model bakeoff,
   then 10-50 same-model prompt-family samples if one lane is clearly
   better.
4. Feed survivors back into `production_promotion_candidates.json` only
   after the M14 board and gameplay-band captures support them.

Regenerate:

```powershell
python world3/pipeline/build_m14_close_play_quality_board.py
```
