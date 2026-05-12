# M8 Organic Regeneration Queue Status

Date: 2026-05-10

This is the current execution board for the M8 ComfyUI/`aaa_texture.py`
organic source-material cleanup lane. It turns the queue JSON into an
explicit status report so we do not treat strict texture QA as visual
promotion.

## Summary

- Total blockers: `5`
- Sidecar candidates needing runtime trials: `0`
- M14 safe but close-conditional: `1`
- Methodology rework / layered substrate: `1`
- Visual rejected: `0`
- Queued untested: `3`

## Gate

- aaa_texture.py gate passes at the requested quality preset
- 2x2 tile sheet has no object-like repetition or visible seam
- Blender plane and sphere previews read as material, not objects
- M6 source-material noise audit improves against the current blocker
- source-stack runtime review passes close, mid, and topdown/iso context

Organic-specific hard rule:

- A candidate may pass seam/PBR QA and still fail if it contains
  object-like plants, landmark blotches, boxy sod panels, bright patch
  islands, or visible repeated leaf/grass clumps.

## Queue

| Material | Status | Latest | Next Action |
|----------|--------|--------|-------------|
| `grassland_grass` | `m14_trial_safe_close_conditional` | `m8_grassland_grass_calm_v3` | Keep as sidecar-only; M14 runtime trial was safe but not enough for production promotion. |
| `grass` | `methodology_rework_layered_substrate` | `4 rejected attempts through m8_grass_calm_v4_anchor_v1` | Treat as a layered substrate/detail target; actual blades and clumps belong to M15 scatter/features. |
| `temperate_forest_grass` | `queued_untested` | `-` | Generate the first candidate, then run seam/PBR QA, visual veto, noise audit, and terrain-context review. |
| `tundra_moss` | `queued_untested` | `-` | Generate the first candidate, then run seam/PBR QA, visual veto, noise audit, and terrain-context review. |
| `tundra_lichen` | `queued_untested` | `-` | Generate the first candidate, then run seam/PBR QA, visual veto, noise audit, and terrain-context review. |

## Next Execution Order

1. Keep `m8_grassland_grass_calm_v3` sidecar-only after its M14
   runtime trial; use it as a safe reference, not a promotion target.
2. Retry `grass` only as a layered organic substrate/detail target;
   actual blades and clumps belong to M15 scatter/features.
3. Generate the untested blockers in queue order:
   `temperate_forest_grass`, `tundra_moss`, then `tundra_lichen`.
4. Rebuild this report after every candidate attempt.

## Command

```powershell
python world3/pipeline/build_m8_regen_queue_status.py
```
