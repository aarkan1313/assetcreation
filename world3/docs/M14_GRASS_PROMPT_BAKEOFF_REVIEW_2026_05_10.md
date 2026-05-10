# M14 Grass Prompt Bakeoff Review - 2026-05-10

## Purpose

Review the first M14 prompt-rework attempts for the `grass` blocker. The target
is not tall grass. It is a close-play terrain detail material that can sit under
source macro color and future scatter without producing repeated plant objects.

## Evidence

| Attempt | Grid | Summary |
|---------|------|---------|
| v1 | `world3/docs/captures/m14/m14_grass_rework_v1_grid_final.png` | `world3/docs/captures/m14/m14_grass_rework_v1_summary.json` |
| v2 | `world3/docs/captures/m14/m14_grass_rework_v2_grid_final.png` | `world3/docs/captures/m14/m14_grass_rework_v2_summary.json` |

## Attempt v1

Prompt direction: dark green-brown vegetated loam substrate with continuous
low ground nap.

Visual result:

- FLUX is calm and coherent, but reads as sparse vegetated dirt / dry loam, not
  grass.
- AuraFlow reads as damp forest floor or mossy undergrowth. It is usable as a
  separate forest/moss sidecar direction, not generic grass.
- SD 3.5 produces useful pebbly soil content but has clear cross seams and is
  rejected for this material target.

## Attempt v2

Prompt direction: pressed olive-brown compact groundcover felt / very short
mossy grass nap.

Visual result:

- FLUX overcorrects into repeated radial grass clumps. This is the old failure
  class: object-like plants in the tile.
- AuraFlow becomes an almost black-green uniform nap. It may be useful as a
  dark moss/felt substrate, but it is too dark and not enough like generic
  grass.
- SD 3.5 gives the most lawn-like fine turf color/texture, but it is saturated
  and still fails seam quality.

## Decision

Do not pursue `grass` as a single "grass photo texture" tile. That prompt
family keeps oscillating between sparse dirt, object clumps, and saturated turf.

The correct M14 framing is layered:

- base material: calm dirt/loam/organic substrate
- detail layer: very subtle green-brown ground nap or moss-felt, low strength
- future M15 feature/scatter layer: actual grass blades, clumps, deadfall, and
  vegetation identity

`m14_grass_rework_v1` FLUX can be kept as a sparse vegetated dirt direction.
It should not replace `grass`. `m14_grass_rework_v2` FLUX is rejected for grass
because of clumped plant objects. SD 3.5 remains interesting only if seam
repair/cropping can remove its cross artifact.

## Next Prompt Target

The next `grass` material attempt should avoid the noun "grass" as the primary
subject and target:

```text
fine olive-brown organic ground substrate, compact root-mat and loam, subtle
green ground nap, continuous low terrain material, no individual plants, no
blades, no tufts, no clumps, no bright turf, no bare holes, no central object
```

Promotion rule: a candidate is allowed to look less grassy in the flat tile if
it becomes a better close-play substrate once combined with source macro color
and scatter.
