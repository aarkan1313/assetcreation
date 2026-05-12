# M16 Iso Impostor Research Plan - 2026-05-10

## Purpose

Iso/tactical view parity is mandatory, but it does not have to mean rendering
full live 3D terrain every frame. M16 now includes a sidecar renderer strategy:
keep the source-stack data contract, but test cheaper iso presentation paths.

## Constraint

Every iso alternative must consume or reference the same workflow contract:

- heightmap + `meta.json`
- source macro albedo
- valid/source mask
- runtime splat/material weights
- feature masks where relevant
- same close/medium/iso/topdown promotion status

If an iso renderer becomes a separate art path, it fails the M12 parity lesson.

## Renderer Rungs

### Rung 1 - Cached Iso Card

Use an existing source-stack iso bake as a 2D runtime card. This is the
simplest proof that a runtime view can avoid live terrain meshes while staying
anchored to a source-stack bake.

Current proof:

- Scene: `world3/scenes/review/source_stack_m16_iso_impostor_card.tscn`
- Script: `world3/scripts/M16IsoImpostorCardReview.gd`
- Source bake: `world3/docs/captures/review/source_stack_m12_runtime_fourway_iso_clean.png`
- Capture: `world3/docs/captures/review/source_stack_m16_iso_impostor_card.png`
- Gate tracking: `m16_cached_iso_impostor_seed` in
  `world3/jobs/production_promotion_candidates.json`.

This is not chunked and not final. It is a seed proof.

The source bake must be UI-free. The normal M12 live-review capture includes
overlay text and is unsuitable as an impostor source.

### Rung 2 - Cached Iso Chunk Impostors

Bake each terrain chunk from the accepted iso camera into cached textures:

- color/albedo card
- optional depth or height card
- optional normal/light card
- footprint metadata for draw order and picking

Runtime draws those cards as 2D tiles/quads. Terrain is cheap; dynamic objects
can render separately as sprites or lightweight 3D overlays.

### Rung 3 - 2D Heightfield Shader

Draw terrain in a 2D/Canvas shader that samples height, source macro, splat
weights, and normals directly. This avoids baked screenshots and could respond
to palette/lighting changes, but requires more custom shader work.

### Rung 4 - Hybrid Tactical Renderer

Use cached or shader terrain for the ground and render characters, props, VFX,
fog, outlines, and selection feedback in a separate overlay layer.

## First Acceptance Test

Rung 1 passes if:

- it displays the M12 source-stack iso bake without instantiating
  `ChunkLoader`, terrain meshes, or 3D lights;
- the source bake is traceable back to the M12 runtime parity proof;
- docs explicitly label it as cached/2D sidecar, not a replacement for 3D
  validation.

Rung 2 starts only after Rung 1 is committed.

Status: Rung 1 is accepted as conditional sidecar evidence only. Mainline work
returns to M13 promotion-gate hygiene before M14/M15 content upgrades.

## Roadmap Placement

This belongs under M16 because it scales gallery/iso parity beyond a single
representative scene. It also informs M18 performance choices for the playable
representative slice.
