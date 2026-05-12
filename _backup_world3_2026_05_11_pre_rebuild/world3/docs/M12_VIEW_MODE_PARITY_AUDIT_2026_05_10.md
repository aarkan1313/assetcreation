# M12 View-Mode Parity Audit - 2026-05-10

## Status

M12 runtime parity checkpoint. The audit now includes a representative
runtime proof that uses one source/material/height/splat contract across
true walk close/medium bands and gallery-style iso/topdown bands.

This is stronger than the initial camera-template audit, but it does not
retrofit every historical gallery script. `RegionGalleryCapture.gd` remains
a legacy bulk-region tool until we decide it needs source-stack promotion.

## Summary

- Source-stack tour scenes: `21`.
- Scenes with complete close/medium/iso/topdown captures: `8`.
- Scenes with source-stack macro contract: `14`.
- Scenes with runtime splat weights: `6`.

## Workflow Inventory

| Workflow | Profile | Bands | Missing | Runtime splat | Notes |
|----------|---------|-------|---------|---------------|-------|
| `auto` | `standard` | - | close, medium, iso, topdown | no | missing source-stack macro override; tour only |
| `cross_source` | `seam_integration` | iso, medium, topdown | close | no | - |
| `cross_source_chuculay_guadalupe` | `seam_integration` | iso, medium, topdown | close | no | - |
| `cross_source_second` | `seam_integration` | iso, medium, topdown | close | no | - |
| `ecotone_layer` | `ecotone_layer` | close, iso, medium, topdown | none | yes | current workflow evidence |
| `full_map_fast` | `full_map_fast` | - | close, medium, iso, topdown | no | missing source-stack macro override; tour only |
| `gloss_temperate_forest_humus_v3` | `full_map_fast` | - | close, medium, iso, topdown | no | missing source-stack macro override; tour only |
| `gloss_tundra_lichen_compare_source_only` | `full_map_fast` | - | close, medium, iso, topdown | no | missing source-stack macro override; tour only |
| `gloss_tundra_lichen_compare_stress` | `full_map_fast` | - | close, medium, iso, topdown | no | missing source-stack macro override; tour only |
| `gloss_tundra_lichen_flux10_09` | `full_map_fast` | - | close, medium, iso, topdown | no | missing source-stack macro override; tour only |
| `gloss_tundra_moss_flux50_b8` | `full_map_fast` | - | close, medium, iso, topdown | no | missing source-stack macro override; tour only |
| `m11_fourway_corner` | `junction_fourway` | close, iso, medium, topdown | none | yes | current workflow evidence |
| `m11_junction` | `junction_layer` | close, iso, medium, topdown | none | yes | current workflow evidence |
| `m12_parity_fourway` | `m12_parity` | close, iso, medium, topdown | none | yes | - |
| `m12_runtime_fourway` | `standard` | close, iso, medium, topdown | none | yes | - |
| `m15_feature_scatter` | `ecotone_layer` | close, iso, medium, topdown | none | yes | - |
| `m18_guided_neighbor` | `seam_integration` | close, iso, medium, topdown | none | no | - |
| `real_procedural` | `seam_integration` | close, iso, medium, topdown | none | no | current workflow evidence |
| `same_source_blend` | `same_source_blend` | - | close, medium, iso, topdown | no | tour only |
| `seam_integration` | `seam_integration` | iso, medium, topdown | close | no | - |
| `seam_nonoverlap` | `seam_integration` | iso, medium, topdown | close | no | - |

## Findings

- The newest M10/M11 proof scenes already have the capture shape M12 wants:
  close, medium, iso, and topdown review bands.
- Older cross-source and seam-integration proofs often have only one 3D
  capture, which is acceptable as historical evidence but not parity closure.
- `RegionGalleryCapture.gd` still uses per-mode whole-kit material swaps, so
  the old bulk gallery remains a legacy path rather than parity evidence.

## M12 Parity Template

`source_stack_m12_parity_fourway_tour.tscn` now exposes the accepted
four-way M11 proof through named camera bands: close play, medium play,
iso/tactical, and topdown/map. It uses the same source/material/height/splat
contract for every band.

## M12 Runtime Parity Proof

`source_stack_m12_runtime_fourway_tour.tscn` instantiates the accepted
four-way proof through the runtime path: a `CharacterBody3D` with
`Walker.gd`, streamed `ChunkLoader` chunks, collision chunks, the accepted
four-way material, source macro/mask overrides, and runtime splat weights.

Its close and medium captures are true walk-runtime bands. Its iso and
topdown captures are gallery-style review bands over the same loaded
runtime contract, not per-mode kit material swaps.

## Next M12 Step

Use the runtime parity proof for live review. If it passes, M12 can close
as representative parity and the full `RegionGalleryCapture.gd` retrofit
can become follow-up bulk-gallery work instead of a milestone blocker.

Regenerate:

```powershell
python world3/pipeline/audit_m12_view_mode_parity.py
```
