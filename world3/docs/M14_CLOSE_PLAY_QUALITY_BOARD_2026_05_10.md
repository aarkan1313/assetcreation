# M14 Close-Play Quality Board - 2026-05-10

## Purpose

M14 is the production-facing terrain-quality lane after M13. It does not
promote assets by itself; it feeds candidates into the M13 gate after
close, medium, iso, and topdown review.

## Summary

- Materials tracked: `5`.
- `m14_sidecar_staged_live_review_pending`: `1`.
- `m14_trial_safe_close_conditional`: `1`.
- `methodology_rework_layered_substrate`: `1`.
- `queued_for_bakeoff`: `2`.

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
| `temperate_forest_grass` | `m14_sidecar_staged_live_review_pending` | `3 M14 attempts through m14_temperate_forest_humus_v3` | Run live close, medium, iso, and topdown terrain-context review before any M13 promotion. | leaf-litter objects and high contrast fragments create visual noise in close terrain |
| `tundra_moss` | `queued_for_bakeoff` | `-` | Run FLUX/Aura/SD batches, then visual-veto before terrain staging. | moss detail is too high-frequency and can turn into colored speckle in runtime |
| `tundra_lichen` | `queued_for_bakeoff` | `-` | Run FLUX/Aura/SD batches, then visual-veto before terrain staging. | lichen spots and pale contrast can repeat as visible object clusters |

## Candidate Gate

- Seam/PBR QA filters candidates but does not promote them.
- Visual veto rejects object landmarks, box panels, bright islands, central compositions, decorative tile motifs, and hero-shot depth of field.
- Survivors require Godot terrain-context review in close, medium, iso, and topdown bands.
- Close-play promotion requires source macro to stay low-frequency and generated PBR detail to carry near-field grain.
- Promotion requires an explicit M13 manifest state change; M14 does not bypass M13.

## Parked Or Rejected Lanes

| Lane | Status | Reason |
|------|--------|--------|
| `qwen_image` | `parked` | Hero-shot/DOF bias and slow runtime; needs a dedicated material-scan prompt family before reconsideration. |
| `chroma1_hd` | `rejected_for_m14` | Failed current ground-texture prompt family with decorative-tile/grid artifacts. |

## Next Move

1. Run close/medium/iso/topdown runtime trials for
   any future sidecar candidates before M13 promotion.
2. Convert `grass` from a monolithic plant-photo tile target into a
   layered substrate/detail target, then rerun the active FLUX/Aura/SD
   lanes only against that corrected brief.
3. Generate first bakeoff batches for `temperate_forest_grass`,
   `tundra_moss`, and `tundra_lichen` in queue order.
4. Feed survivors back into `production_promotion_candidates.json` only
   after the M14 board and gameplay-band captures support them.

Regenerate:

```powershell
python world3/pipeline/build_m14_close_play_quality_board.py
```
