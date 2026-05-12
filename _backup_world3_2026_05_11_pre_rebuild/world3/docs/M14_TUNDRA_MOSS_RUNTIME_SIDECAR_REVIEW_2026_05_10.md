# M14 Tundra Moss Runtime Sidecar Review - 2026-05-10

## Purpose

Stage the accepted `tundra_moss` FLUX 50 `b8` candidate as a runtime sidecar
and verify it in gameplay-view bands before any M13 promotion.

## Candidate

- material id: `m14_tundra_moss_flux50_b_202605207`
- source candidate: FLUX 50 family B, seed `202605207`
- role: pale sage peat-loam/tundra substrate detail
- PBR: `derive_pbr_v2` from the selected albedo
- policy: sidecar/detail only; not canonical and not M13-promoted

The candidate is intentionally not a full moss biome tile. M15 scatter/features
still own moss cushions, lichen islands, stones, and small plants.

## Runtime Staging

| Asset | Path |
|-------|------|
| sidecar texture dir | `world3/textures/wgv3_comfy_candidates/m14_tundra_moss_flux50_b_202605207/` |
| sidecar catalog | `world3/materials/catalog_comfy_candidates.json` |
| source-stack manifest | `world3/textures/source_stack/gloss_tundra_moss_flux50_b8_source_stack/manifest.json` |
| source-stack material | `world3/textures/wgv3/terrain_source_stack_gloss_tundra_moss_flux50_b8_source_stack.tres` |
| review scene | `world3/scenes/review/source_stack_gloss_tundra_moss_flux50_b8_tour.tscn` |

## Captures

| Band | Capture |
|------|---------|
| topdown | `world3/docs/captures/m14/m14_tundra_moss_flux50_b8_gloss_topdown.png` |
| iso | `world3/docs/captures/m14/m14_tundra_moss_flux50_b8_gloss_iso.png` |
| 3D medium | `world3/docs/captures/m14/m14_tundra_moss_flux50_b8_gloss_3d.png` |
| close | `world3/docs/captures/m14/m14_tundra_moss_flux50_b8_gloss_close.png` |
| contact sheet | `world3/docs/captures/m14/m14_tundra_moss_flux50_b8_gloss_contact_sheet.png` |

## Visual Read

Smoke result: conditional pass for sidecar evidence.

- No obvious black crush or overbright lighting issue.
- No obvious square tile seam or repeated moss-object islands in the smoke
  views.
- The candidate reads as low-strength substrate/detail under the real-source
  macro, which is the intended M14 role.
- Gloss Mountain is a clean real-source terrain context, not a true tundra
  biome context. This validates runtime behavior, not semantic tundra promotion.

Rejected context attempt: Rainier south was tried as an alpine/tundra-adjacent
context, but its available `terrain_texture.png` contains a large low-information
dark no-data region. The resulting captures were flat green and were discarded
as invalid review evidence.

## Decision

Keep `m14_tundra_moss_flux50_b_202605207` as an accepted M14 sidecar evidence
candidate pending live user review. Do not promote it through M13 until a true
tundra/alpine textured source context and M15 scatter/features are available.

Next move: start `tundra_lichen` with the same broad-candidate method, or run a
true tundra source-stack pass once a suitable textured terrain lands in the data
catalog.
