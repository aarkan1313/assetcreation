# M1-M7 Visual Remediation Plan

Date: 2026-05-08

## Purpose

This plan converts the M1-M7 visual audit into repair work. The current goal is
not to expand the terrain system. The goal is to rebuild trust in the visual
gate before normal M8/M9/M10 progress.

Use `M1_M7_VISION_GAP_REVIEW_2026_05_08.md` as the visual severity read. The
target is roughly 70 percent of the best stacked photo/topo OpenTopo reference
quality, not "better than the current debug captures."

## Current Verdict

M7 is a workflow pass and a visual rework item. The automatic boundary-mask path
should stay, but current M7 captures are diagnostics only.

## Remediation Sequence

| Step | Scope | Status | Exit |
|------|-------|--------|------|
| R1 | M1 catalog validation sync | Done | Every M6-flagged material has `validated_views.close = needs_review`. |
| R2 | M2 control-pair selection | Done | `scrub_sparse -> dry_wash` is the baseline control pair. |
| R3 | Source-stack pivot | Done for review bridge | Source macro albedo drives runtime terrain through a valid-mask contract; parity captures exist for mid/close/topdown. |
| R4 | Source-material repair | Active | Organic repair candidates exist, but remain quarantined; ComfyUI inventory and regeneration queue now define the first M8 repair lane. |
| R5 | M4 splat context repair | Pending | Replace prototype/debug-looking splat context with a visually credible material assignment for rerenders. |
| R6 | M5/M7 rerender | Pending | Rerender walk and automatic-boundary captures against repaired sources/context. |
| R7 | Visual closure decision | Pending | Decide whether M7 can close visually or needs a second boundary-placement pass. |

## R2 Baseline Pair

Use `scrub_sparse -> dry_wash` as the first control pair. It is same-source,
low-style-delta, and calm in the current M2/M7 evidence. It is not a final hero
asset, but it is the best available control because it isolates transition
placement from the bad grass/organic source issue.

Do not use `desert_sand -> grassland_grass` as a success baseline until
grassland source materials are repaired. Keep it as a stress test.

## R3 Source-Stack Pivot

Do not try to tune the current debug-looking procedural runtime captures into
production shape. They are too far below target. The remediation should move the
runtime material path toward a source-stack model. OpenTopo is the first visual
control lane, but the model is not OpenTopo-only:

- Real or source-derived macro color anchors the terrain.
- Slope/height/material masks select broad terrain classes.
- Tileable generated materials from ComfyUI/`aaa_texture.py` provide scalable
  close detail only where they are clean.
- OpenTopo finished materials are used as the first control materials.
- Procedural grass/leaf/straw materials stay quarantined until they stop
  reading as repeated objects.

## R4 Priority Source Materials

Repair or quarantine these first:

1. `grassland_grass`
2. `grass`
3. `temperate_forest_grass`
4. `tundra_moss`
5. `tundra_lichen`
6. `grassland_dirt`
7. `grassland_rock_light`
8. `temperate_forest_dirt`
9. `temperate_forest_rock_light`
10. `temperate_forest_snow`

The first five are highest priority because they directly affect organic-heavy
transition and walk-view reads. The later five remain close-view blockers but
can wait if the control pair and first rerender need a narrower pass.

Use `COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md` and
`world3/jobs/comfy_texture_regen_candidates.json` for the first regeneration
queue. Deterministic filtering is useful for quarantine experiments, but the
main repair path for these organic blockers is prompt/variant/PBR regeneration
through the ComfyUI texture workflow.

## Quality Bar

For a repaired material to leave `close = needs_review`, it needs:

- A non-noisy 2x2 tile read at close range.
- Lower high-frequency or micro-contrast flags than the M6 audit threshold.
- A Godot terrain-context capture, not only a flat texture sheet.
- No obvious repeated leaf/grass clumps at walk-view scale.
- A ComfyUI inventory entry with source library maps, staged runtime maps, QA
  summaries, and explicit promotion state.

## Next Action

Continue R3/R4 into R5/R6:

1. Use the source-stack control captures as the visual baseline.
2. Regenerate the five priority organic blockers through the ComfyUI queue,
   then re-run source-material noise and terrain-context review.
3. Keep organic repair candidates albedo-only/low-strength until they pass
   terrain-context close/mid/far review.
4. Repair M4 splat context against source-stack policy.
5. Rerender M5/M7 captures only after the source/detail policy is stable.

## Progress 2026-05-08

Implemented the first source-stack runtime bridge and deterministic organic
repair loop. See `SOURCE_STACK_RUNTIME_REMEDIATION_2026_05_08.md` and
`M1_M7_ORGANIC_TEXTURE_REPAIR_2026_05_08.md`.

Added ComfyUI/`aaa_texture.py` parity inventory and the first M8 regeneration
queue. See `COMFYUI_TEXTURE_WORKFLOW_INVENTORY_2026_05_08.md` and
`world3/jobs/comfy_texture_regen_candidates.json`.

Ran the first ComfyUI regeneration on `grassland_grass`. The first two
grass-worded attempts failed or stayed too tufted; `m8_grassland_grass_calm_v3`
passed strict QA with the hardpan/straw-fragment prompt and passed the first
terrain-context candidate gate. It remains a sidecar candidate, not a canonical
promotion. See `M8_COMFYUI_TEXTURE_REGEN_PASS_2026_05_08.md` and
`M8_COMFYUI_TERRAIN_CONTEXT_REVIEW_2026_05_08.md`.

Implemented source-stack valid-area policy and rerendered current/Comfy
grassland terrain-context captures. Source macro albedo is now gated by
`source_macro_valid_mask`; invalid macro pixels are edge-bleed repaired before
save. See `SOURCE_STACK_VALID_AREA_POLICY_2026_05_08.md`.

Started R6 with a source-stack M7 control rerender:
`docs/captures/m7/boundary_runtime_source_stack_control.png`. The capture proves
the boundary path can run over valid-mask source macro terrain, but remains
diagnostic because it is a one-chunk finite-footprint view with visible source
photo shadow content. See `M7_BOUNDARY_RUNTIME_INTEGRATION.md`.

Ran a fresh sequential M1-M7 workflow validation suite at
`docs/captures/m1_m7_validation_2026_05_08/`. Result: M1-M3 pass as workflow
evidence; M4-M6 remain pipeline-pass/visual-rework; M7 remains workflow-pass/
visual-rework. See `M1_M7_WORKFLOW_VALIDATION_RUN_2026_05_08.md`.
