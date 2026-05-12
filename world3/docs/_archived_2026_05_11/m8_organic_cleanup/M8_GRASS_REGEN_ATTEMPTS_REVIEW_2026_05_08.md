# M8 Grass Regeneration Attempts Review

Date: 2026-05-08

## Purpose

This is the second M8 ComfyUI regeneration target after
`grassland_grass`. The canonical source material is `grass`
(`wgv3_grass`), which the M6 audit flagged because close-range green organic
speckle and clover/object repetition read too busy at walk scale.

Outcome: no `grass` candidate is promoted or sidecar-staged yet. Several runs
passed strict seam/PBR QA, but visual review rejected them.

Evidence:

- `captures/visual_remediation/m8_grass_regen_attempts_contact_sheet.png`
- `M8_GRASS_VISUAL_VETO_AUDIT.md`
- `world/textures/library/m8_grass_calm_v1/qa/tile_2x2.png`
- `world/textures/library/m8_grass_calm_v2/qa/tile_2x2.png`
- `world/textures/library/m8_grass_calm_v3/qa/tile_2x2.png`
- `world/textures/library/m8_grass_calm_v4_anchor_v1/m8_grass_calm_v4_anchor_v1_albedo.png`

## Attempts

| Run | Gate | Visual Result | Verdict |
|-----|------|---------------|---------|
| `m8_grass_calm_v1` | strict pass, grade A, edge 0.0003, junction 1.05, periodic 10.0 | Best direction of the set: darker, dirtier, less panel-like. Still has object-like dark/bright landmarks and a few colored patches. | Reject for staging; keep as prompt direction reference. |
| `m8_grass_calm_v2` | strict pass, grade A, edge 0.0003, junction 0.94, periodic 14.0 | Overcorrected toward pale sod. Broad low-frequency bands and rectangular/boxy forms would wash out terrain. | Reject. |
| `m8_grass_calm_v3` | strict pass, grade A, edge 0.0014, junction 1.01, periodic 16.4 | Bright green patch islands, repeated vertical dark landmarks, and camouflage-like blobs. | Reject. |
| `m8_grass_calm_v4_anchor_v1` | albedo-only reference-anchor test | Reference-anchor path created individual plant objects. | Reject; do not PBR. |

## What Went Wrong

The workflow over-trusted seam/PBR QA. `aaa_texture.py` correctly proved the
tiles loop and the maps are technically valid, but it does not yet judge
semantic texture quality. Grass materials can pass grade A while still having
object-like landmarks, boxy fields, repeated green islands, or plant objects.

Prompt-specific findings:

- `v1` had the best tone and scale, but "small dark soil gaps" plus olive/brown
  variation still produced high-salience landmarks.
- `v2` banned the landmarks too aggressively and leaned on "sod" plus
  "low contrast"; the model interpreted that as pale field panels.
- `v3` tried to restore detail with "pasture ground" and "brown loam"; the model
  split the tile into bright grass islands and dark repeated patches.
- `v4` used the reference-anchor lane against v1. With the current prompt, the
  anchor mode did not smooth the material; it generated individual plants.

## Workflow Rule

For M8 organic materials, strict `aaa_texture.py` QA is necessary but not
sufficient. A generated material may not be sidecar-staged until it passes a
visual landmark/object veto:

- no rectangular/boxy panels;
- no bright patch islands;
- no repeated dark or colored landmarks;
- no individual plant objects, clover leaves, flowers, or radial tufts;
- no pale washout that would overpower the OpenTopo source macro.

## Next Direction

Start the next `grass` attempt from the darker `v1` direction, not the pale
`v2`/patchy `v3` direction. The prompt should preserve a darker, dirtier base
while avoiding "soil gaps", "sod", "pasture", "holes", and other words that
produce field-scale patches or object landmarks.

Do not spend terrain-context review time on `grass` until a flat tile passes
the visual veto above.

## Tooling Follow-Up

Added `world3/pipeline/audit_comfy_visual_veto.py` as an advisory veto helper.
It does not promote materials. It only catches obvious failures and marks
everything else as `needs_visual_review`.

Initial calibration:

- `m8_grass_calm_v2`: vetoed for axis-aligned panel/row structure.
- `m8_grass_calm_v3`: vetoed for bright green patch islands and panel/row
  structure.
- `m8_grass_calm_v4_anchor_v1`: vetoed for colored/dark landmark outliers.
- `m8_grass_calm_v1`: left as `needs_visual_review`, matching the manual read:
  not an obvious hard-metric veto, but still rejected for staging.
