# Visual Remediation Captures

Date: 2026-05-08

These captures are M1-M7 visual remediation evidence, not milestone promotion
by themselves.

## Source-Stack Control

- `source_stack_runtime_review_mid.png`
- `source_stack_runtime_review_close.png`
- `source_stack_runtime_review_topdown.png`

Verdict: strongest current runtime direction. Source macro albedo carries the
terrain much better than the procedural/debug M4-M7 captures. Valid-area/clamp
policy is now implemented for the source-stack review materials; remaining work
is highlight cleanup, finite-footprint framing, and better close detail.

## M8 Grassland Terrain Context Rerender

- `grassland_comfy_v3_terrain_context_contact_sheet.png`
- `grassland_comfy_v3_detail_stress_contact_sheet.png`
- `source_stack_runtime_grassland_current_*.png`
- `source_stack_runtime_grassland_comfy_v3_*.png`

Verdict: after the valid-mask rerender, normal close/mid/topdown views read as
source terrain. Current `grassland_grass` still fails detail stress with
straw/tuft noise; `m8_grassland_grass_calm_v3` is calmer but still sidecar-only.

## Organic Repair Candidates

- `organic_repair_contact_sheet.png`
- `*_repair_calm_before_after.png`
- `source_stack_runtime_grass_repair_close.png`
- `source_stack_runtime_grassland_repair_close.png`

Verdict: numeric noise is much lower, but these are not canonical material
promotions. Runtime review showed repaired procedural organic detail should stay
albedo-only and very low strength until close/mid/far terrain-context captures
pass.
