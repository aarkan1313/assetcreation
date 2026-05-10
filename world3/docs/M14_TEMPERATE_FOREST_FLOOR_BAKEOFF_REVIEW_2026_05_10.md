# M14 Temperate Forest Floor Bakeoff Review - 2026-05-10

## Purpose

Review the first M14 bakeoff attempts for `temperate_forest_grass`, whose
current blocker is noisy leaf-litter/object detail at close gameplay scale.

The corrected target is not a complete forest-floor photograph. M14 should
produce a calm duff/humus substrate that can sit under source macro color.
Readable leaves, sticks, moss clumps, roots, and debris belong in M15
scatter/features.

## Evidence

| Attempt | Grid | Summary |
|---------|------|---------|
| v1 | `world3/docs/captures/m14/m14_temperate_forest_floor_v1_grid_final.png` | `world3/docs/captures/m14/m14_temperate_forest_floor_v1_summary.json` |
| v2 | `world3/docs/captures/m14/m14_temperate_forest_duff_v2_grid_final.png` | `world3/docs/captures/m14/m14_temperate_forest_duff_v2_summary.json` |
| v3 | `world3/docs/captures/m14/m14_temperate_forest_humus_v3_grid_final.png` | `world3/docs/captures/m14/m14_temperate_forest_humus_v3_summary.json` |

## Attempt v1

Prompt direction: damp temperate forest floor with decomposed brown leaf mulch
and dark loam.

Visual result:

- FLUX produced a decorative repeated leaf pattern. Reject for terrain use.
- AuraFlow gave the best seam score and the most plausible forest-floor read,
  but it is too dark and still contains identifiable debris.
- SD 3.5 produced flat brown fine material with loose leaf objects. Reject.

## Attempt v2

Prompt direction: decomposed forest duff and humus, with stronger negatives
against whole leaves and visible objects.

Visual result:

- FLUX still repeated small leaf-like objects across the tile. Reject.
- AuraFlow improved seam quality but retained visible leaf/object landmarks and
  remains very dark.
- SD 3.5 went to cracked dry mud plus large leaves. Reject.

## Attempt v3

Prompt direction: fine decomposed temperate forest humus soil, dark loam,
granular organic substrate, no readable leaf shapes.

Visual result:

- AuraFlow is the strongest candidate: a dark continuous humus substrate with
  excellent seam score. It is sidecar-worthy for terrain-context testing, but
  may need brightness/color lift under runtime lighting.
- FLUX is usable as a drier straw-flecked loam direction but still has visible
  fiber/object marks. Keep as reference, not first staging choice.
- SD 3.5 again becomes cracked dry mud/rocks and is rejected for this target.

## Decision

Use `m14_temperate_forest_humus_v3` AuraFlow as the first
`temperate_forest_grass` sidecar candidate for close/medium/iso/topdown
terrain-context testing. Do not treat it as complete forest-floor dressing.
It is a substrate/detail layer. M15 should add leaf scatter, sticks, moss
breakup, and readable forest identity.

## Next Action

Stage only the AuraFlow v3 albedo as an M14 sidecar detail material, with
normal/detail strength conservative at first. Runtime validation must check:

- close view: does the dark humus add usable grain without black crush?
- medium/iso/topdown: does it disappear into source macro instead of tiling?
- transition/junction scenes: does it help forest edges without becoming a
  repeated dark strip?
