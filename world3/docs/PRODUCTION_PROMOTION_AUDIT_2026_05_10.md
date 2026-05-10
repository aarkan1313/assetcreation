# Production Promotion Audit - 2026-05-10

## Purpose

This audit separates workflow acceptance from production promotion. A
workflow can be accepted while still being blocked for production by close
play quality, placeholder scatter, missing bands, or incomplete live review.

## Summary

- Candidates tracked: `6`.
- `conditional`: `3`.
- `workflow_ready_not_production`: `3`.

## Candidate Table

| Candidate | Track | State | Readiness | Bands | Missing Evidence |
|-----------|-------|-------|-----------|-------|------------------|
| `m12_runtime_fourway_parity` | `view_mode_parity` | `ready_for_live_review` | `workflow_ready_not_production` | close:pass, medium:pass, iso:pass, topdown:pass | - |
| `m11_fourway_corner_workflow` | `junction_case_library` | `accepted_workflow` | `workflow_ready_not_production` | close:pass, medium:pass, iso:pass, topdown:pass | - |
| `m11_three_way_junction_workflow` | `junction_case_library` | `accepted_workflow` | `workflow_ready_not_production` | close:pass, medium:pass, iso:pass, topdown:pass | - |
| `m10_ecotone_layer_workflow` | `unlike_biome_ecotone` | `accepted_workflow` | `conditional` | close:conditional, medium:pass, iso:pass, topdown:pass | - |
| `m10_real_procedural_gloss_canyon` | `real_to_procedural_neighbor` | `accepted_workflow` | `conditional` | close:conditional, medium:pass, iso:pass, topdown:pass | - |
| `m8_grassland_grass_calm_v3` | `comfyui_texture_regen` | `sidecar_candidate` | `conditional` | close:conditional, medium:not_reviewed, iso:not_applicable, topdown:not_applicable | - |

## Blockers

### m12_runtime_fourway_parity
- Needs live user review before M12 closure.
- Bulk RegionGalleryCapture.gd remains a legacy follow-up path.

### m11_fourway_corner_workflow
- T/L/island variants are still future case-library work.
- Fantasy domain is accepted as a stress case, not production promotion.

### m11_three_way_junction_workflow
- Canyon geometry is proof heightfield quality.
- Scatter assets are placeholder review meshes.

### m10_ecotone_layer_workflow
- Scatter uses composite low-poly review meshes.
- Grassland material still needs stronger close-play candidates.

### m10_real_procedural_gloss_canyon
- Procedural side needs richer close-range PBR/detail.
- Needs production scatter/features before AAA close-play promotion.

### m8_grassland_grass_calm_v3
- Slightly pale/hazy under detail stress.
- Needs M4/M7 rerender trials before canonical promotion.

## Gate Rule

Production promotion requires all required gameplay bands to be `pass`, no
missing evidence, and an explicit promotion-state change to
`production_candidate` or `production_promoted`. Current accepted M10/M11/M12
items are workflow evidence unless separately promoted.

Regenerate:

```powershell
python world3/pipeline/audit_production_promotion_candidates.py
```
