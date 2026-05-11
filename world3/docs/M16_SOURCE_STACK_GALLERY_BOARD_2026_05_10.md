# M16 Source-Stack Gallery Board - 2026-05-10

This is the first M16 bridge board from the legacy regional gallery to
source-stack parity evidence. It does not replace the live review scenes;
it indexes which source-stack captures are ready to become gallery cards.

## Summary

- cards_total: `6`
- full_parity_capture_sets: `5`
- representative_images_present: `6`
- sidecar_only_cards: `1`

## Legacy Gallery Status

- Scene: `world3/scenes/region_gallery.tscn`
- Script: `world3/scripts/RegionGalleryCapture.gd`
- Status: `legacy_per_kit_material_swap`
- Reason: Useful regional screenshot tool, but not parity evidence until it can bind source macro, valid masks, splat weights, feature masks, and source-stack materials.

## Cards

| Card | Status | Full bands | Representative | Next |
|------|--------|------------|----------------|------|
| `m10_ecotone_layer` | `accepted_source_stack_evidence` | yes | `world3/docs/captures/review/source_stack_ecotone_layer_tour_iso.png` | Keep as first source-stack gallery card; retrofit gallery compiler to consume this contract. |
| `m11_three_way_junction` | `accepted_source_stack_evidence` | yes | `world3/docs/captures/review/source_stack_m11_junction_tour_iso.png` | Use as junction gallery card once bulk scene selection exists. |
| `m11_fourway_corner` | `accepted_source_stack_evidence` | yes | `world3/docs/captures/review/source_stack_m11_fourway_corner_tour_iso.png` | Use as four-way gallery card and parity stress case. |
| `m12_runtime_parity` | `accepted_runtime_parity_evidence` | yes | `world3/docs/captures/review/source_stack_m12_runtime_fourway_iso.png` | Use as the standard for any promoted region-gallery parity card. |
| `m15_feature_scatter` | `workflow_proven_assets_not_final` | yes | `world3/docs/captures/review/source_stack_m15_feature_scatter_close.png` | Keep in M16 board as scatter/features parity case; final art still M15 follow-up. |
| `m16_cached_iso_impostor` | `sidecar_rung_1_conditional` | no | `world3/docs/captures/review/source_stack_m16_iso_impostor_card.png` | Use only as iso renderer sidecar evidence; not a full gallery parity card. |

## Visual Board

`world3/docs/captures/review/source_stack_m16_gallery_board.png`

## Next

1. Keep the legacy `RegionGalleryCapture.gd` path available for old regional screenshots.
2. Add a source-stack gallery runner that consumes this manifest shape instead of whole-kit material swaps.
3. Promote only cards with topdown/iso/medium/close captures as parity evidence.
4. Keep cached iso impostors as M16 sidecar renderer evidence until chunked impostors exist.

Regenerate:

```powershell
python world3/pipeline/build_m16_source_stack_gallery_board.py
```
