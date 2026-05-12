# M8 ComfyUI Terrain Context Review

Date: 2026-05-08

## Purpose

This review tests the first M8 ComfyUI regeneration candidate in terrain
context instead of treating flat texture QA as enough. The candidate is
`m8_grassland_grass_calm_v3`, staged as a quarantined sidecar replacement
candidate for the canonical `grassland_grass` material.

The goal is not canonical promotion. The goal is to prove whether the ComfyUI
lane can produce source material that is safer in the source-stack runtime path
and worth feeding into the M4/M7 visual rerender loop.

## Inputs

Candidate:

- Library output: `world/textures/library/m8_grassland_grass_calm_v3/`
- Staged sidecar material:
  `world3/textures/wgv3_comfy_candidates/m8_grassland_grass_calm_v3/`
- Sidecar catalog: `world3/materials/catalog_comfy_candidates.json`
- Regeneration log: `M8_COMFYUI_TEXTURE_REGEN_PASS_2026_05_08.md`
- Source-material noise audit: `M8_COMFYUI_CANDIDATE_NOISE_AUDIT.md`

Terrain-context captures:

- `captures/visual_remediation/grassland_comfy_v3_terrain_context_contact_sheet.png`
- `captures/visual_remediation/grassland_comfy_v3_detail_stress_contact_sheet.png`
- `captures/visual_remediation/source_stack_runtime_grassland_current_close.png`
- `captures/visual_remediation/source_stack_runtime_grassland_current_mid.png`
- `captures/visual_remediation/source_stack_runtime_grassland_current_topdown.png`
- `captures/visual_remediation/source_stack_runtime_grassland_comfy_v3_close.png`
- `captures/visual_remediation/source_stack_runtime_grassland_comfy_v3_mid.png`
- `captures/visual_remediation/source_stack_runtime_grassland_comfy_v3_topdown.png`
- `captures/visual_remediation/source_stack_runtime_grassland_current_detail_stress_close.png`
- `captures/visual_remediation/source_stack_runtime_grassland_comfy_v3_detail_stress_close.png`

2026-05-08 rerender note: these captures were regenerated after
`SOURCE_STACK_VALID_AREA_POLICY_2026_05_08.md`. The source-stack material now
uses `source_macro_valid_mask` and falls back to procedural/tileable terrain
where the OpenTopo source stack marks macro coverage invalid.

## Source-Material Noise Delta

| Material | HF energy | Grad p95 | Green dom | Saturation | Noise score | Flags |
|----------|-----------|----------|-----------|------------|-------------|-------|
| `grassland_grass` current | 0.061187 | 0.178127 | 0.000000 | 0.528222 | 0.093508 | `high_frequency_noise`, `sharp_micro_contrast` |
| `m8_grassland_grass_calm_v3` | 0.037443 | 0.096886 | 0.000248 | 0.327361 | 0.049726 | none |

The candidate clears the thresholds that flagged the current material. The
noise score is roughly half the current material's score, and the high-gradient
micro-contrast issue is gone.

## Terrain Read

Normal source-stack review:

- Close, mid, and topdown views are nearly identical between current and
  candidate because source macro color dominates and tileable detail strength
  is intentionally low.
- After the valid-mask rerender, the normal views read as real source terrain
  rather than debug texture assignment. The remaining blue/background footprint
  in mid/topdown captures is review framing, not invalid source macro fill.
- That is a useful safety result: the candidate does not visibly regress the
  OpenTopo source-stack terrain when used conservatively.
- It is not enough by itself to promote the candidate, because the review path
  deliberately suppresses detail impact.

Detail-stress review:

- Current `grassland_grass` produces the known failure: yellow/green wavy grass
  strands and tuft-like texture content overpower the source terrain.
- `m8_grassland_grass_calm_v3` is materially better under the same stress. It
  is calmer, less tufted, less saturated, and less object-like.
- The candidate is still slightly pale and hazy when the detail layer is pushed.
  That means it is a good sidecar candidate, not a canonical replacement yet.

## Verdict

`m8_grassland_grass_calm_v3` passes the first terrain-context candidate gate.
It should stay quarantined in `catalog_comfy_candidates.json`, but it is now
eligible for M4/M7 rerender trials as a low-strength detail replacement for the
current `grassland_grass`.

Do not promote it into `world3/materials/catalog.json` yet.

Promotion still requires:

1. M7 boundary stress rerender using the candidate.
2. M4/M5 source-stack rerender trials using the now-fixed valid-area/clamp
   policy.
3. Close/mid/topdown or walk/iso/topdown review where the candidate remains
   calmer without washing out the OpenTopo macro read.
4. Optional palette tuning if the pale/hazy read persists.

## Next

Keep using the ComfyUI lane for the remaining M8 organic blockers. The prompt
lesson is clear: avoid object words such as "grass cover" for close terrain
materials; ask for continuous substrate plus flattened fragments.
