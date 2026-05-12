# M14 Grassland Grass Runtime Trial - 2026-05-10

## Purpose

Test `m8_grassland_grass_calm_v3` as the first M14 close-play material
candidate across the gameplay bands that matter: close, medium, iso, and
topdown. This is a runtime material-context trial, not a flat texture QA pass.

## Inputs

- Candidate: `m8_grassland_grass_calm_v3`
- Baseline material: current `grassland_grass`
- Candidate material:
  `world3/textures/wgv3/terrain_source_stack_gloss_grassland_comfy_v3_source_stack.tres`
- Baseline material:
  `world3/textures/wgv3/terrain_source_stack_gloss_grassland_current_source_stack.tres`
- Review script: `world3/scripts/SourceStackRuntimeReview.gd`
- Capture sheet:
  `world3/docs/captures/m14/m14_grassland_comfy_v3_runtime_trial_contact_sheet.png`

## Captures

| Band | Current | Candidate |
|------|---------|-----------|
| Close | `world3/docs/captures/m14/m14_grassland_current_close.png` | `world3/docs/captures/m14/m14_grassland_comfy_v3_close.png` |
| Medium | `world3/docs/captures/m14/m14_grassland_current_medium.png` | `world3/docs/captures/m14/m14_grassland_comfy_v3_medium.png` |
| Iso | `world3/docs/captures/m14/m14_grassland_current_iso.png` | `world3/docs/captures/m14/m14_grassland_comfy_v3_iso.png` |
| Topdown | `world3/docs/captures/m14/m14_grassland_current_topdown.png` | `world3/docs/captures/m14/m14_grassland_comfy_v3_topdown.png` |

## Visual Read

- Normal source-stack bands are almost unchanged between baseline and
  candidate because the OpenTopo macro layer dominates.
- That is a useful safety result: the candidate does not visibly damage close,
  medium, iso, or topdown terrain context.
- It is not enough for production promotion. The candidate's improvement is
  subtle in the runtime stack, and the earlier detail-stress review still shows
  slight pale/hazy behavior when pushed.
- The candidate should remain a low-strength sidecar material while M14
  generates stronger FLUX/Aura/SD organic candidates.

## Band Status

| Band | Status | Reason |
|------|--------|--------|
| Close | `conditional` | Safe/no obvious regression, but not a clear close-play production upgrade. |
| Medium | `pass` | Candidate preserves source-stack read. |
| Iso | `pass` | Candidate preserves source-stack read. |
| Topdown | `pass` | Candidate preserves source-stack read. |

## Decision

`m8_grassland_grass_calm_v3` passes M14 as conditional sidecar evidence only.
Do not promote it into the canonical material catalog. Keep it available for
low-strength use and use the M14 bakeoff lanes to generate better close-play
organic candidates.
