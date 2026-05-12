# M7 Transition Mask Metrics

Date: 2026-05-08

## Purpose

This adds a quantitative gate for the M7 runtime transition-mask path. The
source-stack boundary capture proves the mask can render in context; this audit
checks that the generated mask itself has sane coverage and chunk-edge
continuity.

Tool:

- `world3/pipeline/audit_transition_mask_metrics.py`

Inputs:

- scene: `world3/scenes/capture_phase_m7/boundary_runtime_source_stack_context.tscn`
- rules: `world3/jobs/biome_transition_rules.json`
- rule: `opentopo_scrub_sparse__dry_wash_neighbor`

Outputs:

- `world3/docs/captures/m7/transition_mask_metrics_source_stack_context.json`
- `world3/docs/captures/m7/transition_mask_metrics_source_stack_context.png`

## Result

Status: `PASS`

Key metrics:

- Loaded chunks: `25`
- Intersecting boundary chunks: `5`
- Band coverage mean: `0.280469`
- Band coverage range: `0.279297` to `0.282043`
- Band peak minimum: `1.0`
- Edge checks: `4`
- Worst mean band edge delta: `0.047768`
- Worst mean U edge delta: `0.022314`
- Worst circular mean V edge delta: `0.015625`

## Read

The same-source source-stack M7 control now has a measurable mask-quality pass:

- the expected five chunks in the 5x5 neighborhood receive transition masks;
- coverage is consistent across all boundary chunks;
- the boundary band reaches full strength;
- chunk-to-chunk mean edge deltas stay inside the current acceptance thresholds.

This does not make M7 visually final. It closes the same-source mask QA gap for
this control scene. Cross-material stress captures should rerun this audit with
their own rule/scene settings before visual closure.

## Command

```powershell
python world3/pipeline/audit_transition_mask_metrics.py
```
