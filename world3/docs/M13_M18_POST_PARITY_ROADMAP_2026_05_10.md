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
- Iso/tactical optimization is allowed, but alternate renderers must preserve
  the M12 source-stack contract. Cached impostors and 2D heightfield shaders are
  renderer choices, not separate art pipelines.
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
- `world3/jobs/m14_texture_bakeoff_plan.json`.
- `world3/docs/M14_CLOSE_PLAY_QUALITY_BOARD_2026_05_10.md`.

Deliverables:

- Batch generation harness for FLUX/Aura/SD variants with model-specific
  prompts/settings.
- Visual veto plus terrain-context capture sheet for each survivor.
- M4/M7 runtime rerender trials for promoted sidecar materials.
- M14 quality board generated from the M8 queue and model-lane policy.

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

**Goal**: scale view-mode parity beyond one representative scene and explore
cheaper iso/tactical rendering without breaking the source-stack contract.

Inputs:

- `RegionGalleryCapture.gd` legacy path.
- M12 runtime parity contract.
- `docs/MASTER_DATA_CATALOG.md` and `world3/data_catalog.json`.
- `M16_ISO_IMPOSTOR_RESEARCH_PLAN_2026_05_10.md`.

Deliverables:

- Gallery/region review path that can bind source macro, valid masks, splat
  weights, and shared materials.
- Candidate selector using master catalog state and coverage gaps.
- Representative capture set across at least three regions.
- Iso renderer sidecar ladder:
  - cached iso card from an accepted source-stack bake
  - cached iso chunk impostors
  - optional 2D heightfield shader
  - hybrid terrain-card plus object-overlay tactical renderer
- Proof that any non-3D iso view is traceable to the same height/macro/mask/
  splat contract as the 3D source-stack scene.

Exit:

- Region review is no longer limited to old per-kit material swaps.
- The first iso-impostor experiment proves whether cached 2D playback can carry
  the M12 source-stack contract without running live terrain meshes.

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

M13 gate hygiene is active for every new artifact. The candidate manifest and
audit are clean after M12 workflow acceptance and the M16 iso sidecar entry.
M14 close-play terrain quality is now active. Start with the M14 board's first
move after the `m8_grassland_grass_calm_v3` runtime trial: rework `grass` from
the darker v1 direction as a layered substrate/detail target, then run active
FLUX/Aura/SD bakeoffs for the remaining organic blockers. Do not require a flat
`grass` tile to contain visible grass plants; M15 scatter/features should carry
actual blades and clumps. The same rule now applies to `temperate_forest_grass`:
AuraFlow v3 has the first staged sidecar-worthy dark humus substrate, while
whole leaves/twigs should move to M15 scatter/features. Next action is live
terrain-context review of `source_stack_gloss_temperate_forest_humus_v3_tour`,
then `tundra_moss` and `tundra_lichen` bakeoffs.
