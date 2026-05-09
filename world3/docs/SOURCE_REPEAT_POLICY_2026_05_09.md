# Source Repeat Policy

Date: 2026-05-09

## Finding

- Source: `Gloss Mountain Textured Master Stack`
- Wrap-safety audit: **FAIL**
- Recommended `ChunkLoader.source_repeat_mode`: `mirror`

The wall/box artifact in the source-stack auto review scene came from wrapping a finite OpenTopo height source as if its opposite edges were toroidal. They are not. When the runtime connected unrelated opposite edges, it produced a large height discontinuity.

## Edge Delta Audit

| Edge pair | mean m | median m | p95 m | max m |
| --- | ---: | ---: | ---: | ---: |
| left/right | 3.090 | 0.000 | 11.832 | 19.489 |
| top/bottom | 2.846 | 0.000 | 25.471 | 26.726 |

Thresholds for wrap-safe terrain are mean <= 1 m, p95 <= 3 m, and max <= 8 m on both edge pairs.

## Runtime Policy

- `mirror`: default for finite real-source terrain. Prevents hard source-edge height jumps while preserving local landform continuity.
- `wrap`: only for sources explicitly audited as toroidal/seam-safe.
- `clamp`: diagnostics only, for exposing finite-footprint boundaries.

For review scenes with a source macro valid mask, invalid mask areas should be clipped or hidden, not rendered as fallback terrain. A flat material fill reads as a fake plateau and obscures the actual data boundary.

## Methodology Correction

Same-source repeat is no longer considered a path to visual closure. It remains
useful for finding sample-space bugs, chunk-boundary bugs, and shader binding
errors, but a finite OpenTopo crop should not be treated as a tileable world
piece unless it has passed a wrap-safety audit.

The production-facing path is terrain seam integration: a generated
world-space integration band where height, normals, material weights, source
macro color, valid masks, and feature layers are solved together. The active
methodology note is `TERRAIN_SEAM_INTEGRATION_RESEARCH_2026_05_09.md`.

## Repeated-Source Blend Mode

A 2x2 or 3x3 repeated-source review is still valid as a workflow tool if it has an explicit boundary blend band. The blend has to operate on both geometry and appearance:

- height samples from tile A and tile B blend over the same world-space band;
- source macro albedo/orthophoto samples blend over that band;
- source valid masks blend or clip consistently;
- tileable detail material continues over the band so the join is not a flat blur.

This is similar in spirit to material transitions, but stricter: if the height blend and texture blend disagree, the seam becomes visible as either a cliff, a smear, or a photo/geometry mismatch.

## Quality Direction

Mirroring is a mitigation, not the final world-generation answer. Repeated-source blend mode is useful for review and stress testing, but the production-quality path is to extract landform/material rules from OpenTopo, stream or mosaic compatible neighboring sources, and use generated procedural terrain for extension instead of repeating one identifiable real crop forever.
