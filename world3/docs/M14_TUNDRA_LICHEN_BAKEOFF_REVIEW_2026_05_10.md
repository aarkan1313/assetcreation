# M14 Tundra Lichen Bakeoff Review

Date: 2026-05-10

Purpose: validate the generated-texture sidecar workflow for `tundra_lichen`.
This is pipeline evidence, not a production content promotion.

## Candidate

- selected material id: `m14_tundra_lichen_flux10_09_202605259`
- source slot: `tundra_lichen`
- model lane: `flux2_klein`
- seed: `202605259`
- heal strength: `0.28`
- final seam score: `0.014873`
- selected by user review from the FLUX10 sheet

User-facing acceptance criteria for this pass:

- tileable enough for workflow validation
- visually usable as lichen-on-gritty-ground
- no obvious square boxes, hard lines, bad seams, or blur

## Bakeoff Notes

Initial active-model bakeoff:

- grid: `world3/docs/captures/m14/m14_tundra_lichen_substrate_v1_grid_final.png`
- summary: `world3/docs/captures/m14/m14_tundra_lichen_substrate_v1_summary.json`
- result: useful diagnosis, but no direct winner. FLUX read as obvious lichen
  colonies, AuraFlow became gray substrate, and SD produced patterned green
  blotches.

FLUX-only workflow sweep:

- contact sheet: `world3/docs/captures/m14/m14_tundra_lichen_biocrust_flux10_contact_sheet.png`
- shortlist 2x2: `world3/docs/captures/m14/m14_tundra_lichen_flux10_shortlist3_2x2.png`
- shortlist summary: `world3/docs/captures/m14/m14_tundra_lichen_flux10_shortlist3_summary.json`
- selected: candidate `09`, because it had the cleanest workflow read and the
  lowest seam score among the visually acceptable shortlist.

## Runtime Staging

Generated PBR maps with `derive_pbr_v2`, then staged into the quarantined
Comfy sidecar catalog:

- sidecar texture dir: `world3/textures/wgv3_comfy_candidates/m14_tundra_lichen_flux10_09_202605259/`
- sidecar catalog: `world3/materials/catalog_comfy_candidates.json`
- source-stack material: `world3/textures/wgv3/terrain_source_stack_gloss_tundra_lichen_flux10_09_source_stack.tres`
- source-stack manifest: `world3/textures/source_stack/gloss_tundra_lichen_flux10_09_source_stack/manifest.json`
- review scene: `world3/scenes/review/source_stack_gloss_tundra_lichen_flux10_09_tour.tscn`

## Captures

| View | Capture |
|------|---------|
| topdown | `world3/docs/captures/m14/m14_tundra_lichen_flux10_09_gloss_topdown.png` |
| iso | `world3/docs/captures/m14/m14_tundra_lichen_flux10_09_gloss_iso.png` |
| 3D medium | `world3/docs/captures/m14/m14_tundra_lichen_flux10_09_gloss_3d.png` |
| close | `world3/docs/captures/m14/m14_tundra_lichen_flux10_09_gloss_close.png` |
| contact sheet | `world3/docs/captures/m14/m14_tundra_lichen_flux10_09_gloss_contact_sheet.png` |

## Verdict

Conditional M14 sidecar workflow pass.

The selected texture is acceptable for validating the generated texture lane:
ComfyUI candidate selection, derived PBR, catalog staging, Godot import, and
source-stack terrain review all work end to end.

Limits:

- Gloss Mountain is clean real-source runtime context, not true tundra.
- The lichen layer is intentionally a detail/sidecar layer, not the whole biome.
- Larger lichen colonies, stones, moss cushions, and tundra identity should be
  handled later by M15 scatter/decal/features.
- Do not M13-promote this until true tundra/alpine source-context review passes.

## Workflow Lesson

For pipeline work, do not overfit the content semantics too early. The correct
gate for M14 generated sidecars is: tileability, artifact safety, runtime
staging, and view-band behavior. Final content quality belongs to later
source-context and feature/scatter passes.
