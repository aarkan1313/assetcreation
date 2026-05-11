# world3 M1-M18 Honest Audit - 2026-05-10

## Executive Verdict

world3 is now strong as a **terrain workflow and pipeline system**. It is not
yet strong as a finished AAA terrain content set.

The important achievement is that the project now has a traceable pipeline from
real source data and generated candidates into runtime review scenes, visual
captures, promotion gates, and documented blockers. The weak point is still
content richness at close gameplay distance, especially procedural terrain and
placeholder scatter assets.

## Audit Chain

- M1-M7 visual audit:
  `world3/docs/M1_M7_VISUAL_AUDIT_2026_05_08.md`.
- M7-M12 closure audit:
  `world3/docs/M7_M12_CLOSURE_AUDIT_2026_05_10.md`.
- M13-M18 roadmap and gate:
  `world3/docs/M13_M18_POST_PARITY_ROADMAP_2026_05_10.md`.
- Current production gate:
  `world3/docs/PRODUCTION_PROMOTION_AUDIT_2026_05_10.md`.
- Current M18 closure audit:
  `world3/docs/M18_CLOSURE_AUDIT_2026_05_10.md`.

## What Is Working

- Source-stack contract is the backbone: height, macro albedo, valid masks,
  splat weights, feature masks, scene, captures, and docs are now connected.
- M10/M11/M12 transitions, junctions, and view-mode parity are real workflow
  evidence, not isolated screenshots.
- M13 promotion tracking prevents accidental production claims.
- M14 texture work has a sane model-bakeoff/sidecar workflow.
- M15 scatter now consumes masks instead of hand placement.
- M16 has a gallery/review runner and a first cached iso sidecar.
- M17 extracts procedural targets from accepted source-stack proofs.
- M18 proves the M17 procedural neighbor can re-enter the runtime path and feed
  derived M15-style masks.

## Visual Strengths

- Real OpenTopo/photo/topo source areas can look compelling.
- Hard missing-data edge artifacts are no longer treated as acceptable terrain.
- Like-to-like and source-stack transitions are much better than the early debug
  screenshots.
- Topdown/iso/medium/close review parity is now a repeatable habit.
- The best workflow captures are good enough to guide future production work.

## Visual Weaknesses

- Procedural terrain fields are still the biggest visual gap. The M18 tan/sand
  side is too smooth, too broad, and too low in material identity.
- Generated texture tiles can be useful substrates, but they are not enough to
  carry biome identity by themselves.
- Scatter and decals are workflow placeholders, not authored AAA assets.
- Some accepted workflow scenes still rely on proof-quality heightfields,
  simplified material lanes, or fantasy stress inputs.
- The current closure harness reviews multiple accepted proofs side by side; it
  does not yet compose all of them into one physically streamed playable region.

## Production Gate State

The current M13 audit tracks eight candidates:

- Three are `workflow_ready_not_production`.
- Five are `conditional`.
- None are production-promoted.

That is correct. The project should not promote any terrain content yet.

## What M18 Actually Closed

Closed:

- M17 procedural output can be made into a runtime source-stack terrain.
- M15-style feature masks can be derived from the M18 runtime data.
- Close, medium, iso, and topdown captures exist for the M18 runtime slice.
- M11 junction ownership is represented in the M18 closure harness.
- A first performance smoke exists and is clean enough for workflow review.

Not closed:

- AAA procedural terrain visual quality.
- Authored scatter/decal/foliage asset quality.
- Physical streamed composition of all accepted proof types in one playable
  world area.
- Production promotion.

## Next Honest Move

Move into the post-M18 hybrid procedural roadmap, but keep the production gate
strict. The next terrain-facing work should target the procedural side directly:
richer drainage, rock exposure, erosion/roughness fields, material variation,
and authored scatter assets. The M18 sand is the visible proof that the workflow
is ready for better procedural content, not proof that the content is done.
