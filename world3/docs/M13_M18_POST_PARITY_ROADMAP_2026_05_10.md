# M13-M18 Post-Parity Roadmap

Date: 2026-05-10

This roadmap opens after the M7-M12 foundation lane produced representative
chunk, source, biome, junction, and view-mode parity evidence.

The project framing remains: world3 is a pipeline/workflow creation set aimed
at AAA-quality terrain workflows. Current assets are not production-promoted
unless the promotion gate says so.

## Sequencing Rules

- Production promotion is a separate state from workflow acceptance.
- Close, medium, iso, and topdown bands must be recorded for visual promotion.
- New scatter/props/procedural work must consume the source-stack contract
  rather than bypassing it.
- The master data catalog remains the authority for real-world source coverage.
- Procedural generation should learn from many sources; do not stretch one
  finite OpenTopo crop into a world.

## M13 - Production Promotion Gate

**Goal**: make acceptance states auditable before more content is added.

Initial implementation:

- `world3/jobs/production_promotion_candidates.json`
- `world3/pipeline/audit_production_promotion_candidates.py`
- `world3/docs/PRODUCTION_PROMOTION_AUDIT_2026_05_10.md`

Exit:

- Every candidate artifact has a status: workflow evidence, sidecar candidate,
  negative evidence, production candidate, or production promoted.
- Promotion requires all required gameplay bands, no missing evidence, and an
  explicit state change.

## M14 - Close-Play Terrain Quality

**Goal**: make near-field ground hold up at gameplay scale.

Inputs:

- M8 organic texture queue.
- FLUX/Aura/SD multi-model bakeoff lane.
- Source-stack terrain-context captures.
- Gameplay view quality matrix.

Deliverables:

- Batch generation harness for FLUX/Aura/SD variants with model-specific
  prompts/settings.
- Visual veto plus terrain-context capture sheet for each survivor.
- M4/M7 runtime rerender trials for promoted sidecar materials.

Exit:

- At least one organic/grass blocker moves from sidecar to production candidate
  or is explicitly rejected with evidence.

## M15 - Production Scatter And Feature Layers

**Goal**: replace placeholder scatter meshes with authored, source-driven
feature layers.

Inputs:

- M10/M11 feature masks: shrub, grass, rock, soil, wash, no-scatter.
- Accepted ecotone and junction proofs.

Deliverables:

- Small production-style asset library for shrubs, grasses, stones, and dry
  debris.
- LOD and visibility policy by gameplay band.
- Runtime scatter review using existing masks, not hand placement.

Exit:

- A representative ecotone/junction scene improves close/medium quality without
  damaging iso/topdown readability.

## M16 - Bulk Region/Gallery Source-Stack Retrofit

**Goal**: scale view-mode parity beyond one representative scene.

Inputs:

- `RegionGalleryCapture.gd` legacy path.
- M12 runtime parity contract.
- `docs/MASTER_DATA_CATALOG.md` and `world3/data_catalog.json`.

Deliverables:

- Gallery/region review path that can bind source macro, valid masks, splat
  weights, and shared materials.
- Candidate selector using master catalog state and coverage gaps.
- Representative capture set across at least three regions.

Exit:

- Region review is no longer limited to old per-kit material swaps.

## M17 - Real-Data-Guided Procedural Extraction

**Goal**: begin converting real-source data into procedural rules.

Inputs:

- Master catalog.
- Seam integration metrics.
- Accepted source-stack proofs.
- Feature masks and material weights.

Deliverables:

- Rule-extraction notes for landform, drainage/wash, vegetation density, and
  material transition fields.
- Prototype procedural neighbor generator that emits the same height/macro/mask
  contract as source-stack proofs.

Exit:

- Procedural output can be reviewed through the same M12 bands and M13 gate.

## M18 - Playable Representative Slice

**Goal**: assemble a small playable terrain slice that exercises the complete
workflow.

Inputs:

- M13 promotion gate.
- M14 close-play materials.
- M15 scatter/features.
- M16 region/gallery parity.
- M17 procedural neighbor generation.

Deliverables:

- One streamed runtime scene with source terrain, procedural neighbor, ecotone,
  junction, scatter/features, and gameplay-band review.
- Performance pass for runtime interaction/hitches.

Exit:

- A user can inspect the slice at close, medium, iso, and topdown bands with
  documented pass/conditional/fail status.

## Current First Move

M13 is active now. Do not promote or expand visuals until the candidate manifest
and audit stay clean.
