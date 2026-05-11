# Production Promotion Audit - 2026-05-10

## Purpose

This audit separates workflow acceptance from production promotion. A
workflow can be accepted while still being blocked for production by close
play quality, placeholder scatter, missing bands, or incomplete live review.

## Summary

- Candidates tracked: `8`.
- `conditional`: `5`.
- `workflow_ready_not_production`: `3`.

## Candidate Table

| Candidate | Track | State | Readiness | Bands | Missing Evidence |
|-----------|-------|-------|-----------|-------|------------------|
| `m12_runtime_fourway_parity` | `view_mode_parity` | `accepted_workflow` | `workflow_ready_not_production` | close:pass, medium:pass, iso:pass, topdown:pass | - |
| `m11_fourway_corner_workflow` | `junction_case_library` | `accepted_workflow` | `workflow_ready_not_production` | close:pass, medium:pass, iso:pass, topdown:pass | - |
| `m16_cached_iso_impostor_seed` | `iso_runtime_strategy` | `sidecar_candidate` | `conditional` | close:not_applicable, medium:not_applicable, iso:conditional, topdown:not_applicable | - |
| `m11_three_way_junction_workflow` | `junction_case_library` | `accepted_workflow` | `workflow_ready_not_production` | close:pass, medium:pass, iso:pass, topdown:pass | - |
| `m10_ecotone_layer_workflow` | `unlike_biome_ecotone` | `accepted_workflow` | `conditional` | close:conditional, medium:pass, iso:pass, topdown:pass | - |
| `m10_real_procedural_gloss_canyon` | `real_to_procedural_neighbor` | `accepted_workflow` | `conditional` | close:conditional, medium:pass, iso:pass, topdown:pass | - |
| `m18_representative_slice_first_pass` | `representative_runtime_slice` | `ready_for_live_review` | `conditional` | close:conditional, medium:conditional, iso:pass, topdown:conditional | - |
| `m8_grassland_grass_calm_v3` | `comfyui_texture_regen` | `sidecar_candidate` | `conditional` | close:conditional, medium:pass, iso:pass, topdown:pass | - |

## Blockers And Notes

### m12_runtime_fourway_parity
- No production promotion requested; this remains workflow evidence.
- Bulk RegionGalleryCapture.gd is an M16 follow-up, not an M12 blocker.

### m11_fourway_corner_workflow
- T/L/island variants are still future case-library work.
- Fantasy domain is accepted as a stress case, not production promotion.

### m16_cached_iso_impostor_seed
- First proof is a single cached card, not chunked runtime impostors.
- Needs depth, picking, object-overlay, and streaming experiments before tactical use.
- Must remain tied to the M12 source-stack contract; it is not a separate art path.

### m11_three_way_junction_workflow
- Canyon geometry is proof heightfield quality.
- Scatter assets are placeholder review meshes.

### m10_ecotone_layer_workflow
- Scatter uses composite low-poly review meshes.
- Grassland material still needs stronger close-play candidates.

### m10_real_procedural_gloss_canyon
- Procedural side needs richer close-range PBR/detail.
- Needs production scatter/features before AAA close-play promotion.

### m18_representative_slice_first_pass
- Procedural tan/sand side reads too smooth and broad for AAA close-play.
- Derived M15 scatter uses procedural review primitives, not authored production assets.
- M11 junction ownership is represented in the M18 closure harness, not physically composed into the same streamed terrain.
- No production promotion requested; this remains representative workflow evidence.

### m8_grassland_grass_calm_v3
- M14 runtime trial is safe but too subtle for close-play production promotion.
- Earlier detail-stress review remains slightly pale/hazy.
- Keep as low-strength sidecar while generating stronger FLUX/Aura/SD organic candidates.

## Gate Rule

Production promotion requires all required gameplay bands to be `pass`, no
missing evidence, and an explicit promotion-state change to
`production_candidate` or `production_promoted`. Current accepted M10/M11/M12
items are workflow evidence unless separately promoted.

Regenerate:

```powershell
python world3/pipeline/audit_production_promotion_candidates.py
```
