# M12 View-Mode Parity Audit - 2026-05-10

## Status

Initial M12 audit. This is an inventory, not closure.

M12 starts from the accepted M10/M11 workflow scenes and asks whether the
same terrain/material/source decision can be reviewed in close, medium, iso,
and topdown bands without switching pipelines.

## Summary

- Source-stack tour scenes: `13`.
- Scenes with complete close/medium/iso/topdown captures: `5`.
- Scenes with source-stack macro contract: `11`.
- Scenes with runtime splat weights: `4`.

## Workflow Inventory

| Workflow | Profile | Bands | Missing | Runtime splat | Notes |
|----------|---------|-------|---------|---------------|-------|
| `auto` | `standard` | - | close, medium, iso, topdown | no | missing source-stack macro override; tour only |
| `cross_source` | `seam_integration` | iso, medium, topdown | close | no | - |
| `cross_source_chuculay_guadalupe` | `seam_integration` | iso, medium, topdown | close | no | - |
| `cross_source_second` | `seam_integration` | iso, medium, topdown | close | no | - |
| `ecotone_layer` | `ecotone_layer` | close, iso, medium, topdown | none | yes | current workflow evidence |
| `full_map_fast` | `full_map_fast` | - | close, medium, iso, topdown | no | missing source-stack macro override; tour only |
| `m11_fourway_corner` | `junction_fourway` | close, iso, medium, topdown | none | yes | current workflow evidence |
| `m11_junction` | `junction_layer` | close, iso, medium, topdown | none | yes | current workflow evidence |
| `m12_parity_fourway` | `m12_parity` | close, iso, medium, topdown | none | yes | - |
| `real_procedural` | `seam_integration` | close, iso, medium, topdown | none | no | current workflow evidence |
| `same_source_blend` | `same_source_blend` | - | close, medium, iso, topdown | no | tour only |
| `seam_integration` | `seam_integration` | iso, medium, topdown | close | no | - |
| `seam_nonoverlap` | `seam_integration` | iso, medium, topdown | close | no | - |

## Findings

- The newest M10/M11 proof scenes already have the capture shape M12 wants:
  close, medium, iso, and topdown review bands.
- Older cross-source and seam-integration proofs often have only one 3D
  capture, which is acceptable as historical evidence but not parity closure.
- `RegionGalleryCapture.gd` still uses per-mode whole-kit material swaps; that
  is the main remaining divergence from the source-stack review contract.
- Walk-mode parity is not solved by capture wrappers alone. The next real M12
  implementation step is to bind the same material/source stack into a walk
  scene and capture close/medium bands from that path.

## M12 Parity Template

`source_stack_m12_parity_fourway_tour.tscn` now exposes the accepted
four-way M11 proof through named camera bands: close play, medium play,
iso/tactical, and topdown/map. It uses the same source/material/height/splat
contract for every band.

## Next M12 Step

Use the parity template as the control scene, then bring one true walk-mode
scene and one gallery/region view onto the same source-stack/splat contract.
That is the remaining path divergence M12 needs to resolve.

Regenerate:

```powershell
python world3/pipeline/audit_m12_view_mode_parity.py
```
