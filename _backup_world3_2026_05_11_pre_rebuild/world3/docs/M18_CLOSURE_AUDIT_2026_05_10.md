# M18 Closure Audit - 2026-05-10

## Verdict

M18 is **workflow-closed / visually conditional**.

It proves that the post-parity pipeline can assemble a representative runtime
review harness from:

- M13 promotion tracking.
- M14 close-play material sidecars.
- M15 feature/scatter masks and overlay policy.
- M16 source-stack gallery review.
- M17 real-data-guided procedural neighbor generation.
- M10/M11/M12 accepted terrain, transition, junction, and view-mode evidence.

It does **not** prove production terrain quality.

## What M18 Now Has

- Physical runtime slice:
  `world3/scenes/review/source_stack_m18_guided_neighbor_tour.tscn`.
- Closure review harness:
  `world3/scenes/review/source_stack_m18_closure_review.tscn`.
- Closure manifest:
  `world3/jobs/m18_closure_review_manifest.json`.
- Representative slice manifest:
  `world3/jobs/m18_representative_slice_manifest.json`.
- Derived feature masks:
  `world3/pipeline/build_m18_slice_feature_masks.py`.
- Promotion audit entry:
  `m18_representative_slice_first_pass` in
  `world3/jobs/production_promotion_candidates.json`.
- Capture sheet:
  `world3/docs/captures/review/source_stack_m18_guided_neighbor_contact_sheet.png`.
- Closure harness smoke capture:
  `world3/docs/captures/review/source_stack_m18_closure_review.png`.
- Performance smoke:
  `world3/docs/captures/review/m18_guided_neighbor_performance_smoke.json`.

## Visual Audit

Pass:

- The real-source side still reads strongly because the OpenTopo macro and
  height evidence are carrying it.
- There is no missing-data plateau or obvious invalid-source wall.
- The seam is mechanically solved well enough for workflow review.
- Close, medium, iso, and topdown captures all run from the same M18 runtime
  terrain bundle.
- M15-style feature masks are derived from the M18 runtime data instead of hand
  placement.
- The M18 closure harness now includes the accepted M11 three-way and four-way
  junction ownership evidence.
- First performance smoke is clean for a workflow scene: average `4.72 ms`,
  p95 `7.98 ms`, max `11.85 ms` at 1600x1000.

Conditional / weak:

- The procedural tan/sand side is visually poor: too smooth, too broad, and too
  texture-light for AAA close-play.
- Derived scatter is visible but still procedural review primitive quality.
- Topdown transition is functional but still reads like a broad softened band,
  not a final art-directed ecotone.
- M11 junction ownership is represented in the closure harness, not physically
  composed into the same streamed terrain.
- The M16 cached iso card remains a sidecar renderer seed, not tactical-runtime
  closure.
- The performance number is a smoke metric, not a broad optimization pass over
  many streamed areas.

Fail for production promotion:

- No M18 artifact is production-promoted.
- M18 remains blocked on procedural terrain richness, authored scatter assets,
  and a future stream/director composition pass that can place multiple
  accepted source-stack proofs in a single playable area without weakening
  provenance.

## M13-M18 Audit State

The M13 audit currently reports:

- `workflow_ready_not_production`: M11/M12 workflow items with all bands present.
- `conditional`: M10 ecotone, M10 real-to-procedural, M16 iso sidecar, M18
  representative slice, and M8/M14 sidecar material evidence.

This is the right state. The project has strong workflow machinery and honest
evidence separation, but close-play AAA content remains open.

Regenerate the gate audit:

```powershell
python world3/pipeline/audit_production_promotion_candidates.py
```

## Next After M18

0. Run the full M1-M18 audit plan:
   `world3/docs/WORLD3_M1_M18_FULL_AUDIT_PLAN_2026_05_11.md`.
1. Improve procedural terrain generation using the M17 extraction path plus
   broader catalog data. The immediate visible target is avoiding the current
   smooth tan/sand field.
2. Replace procedural feature primitives with authored scatter/decal assets
   while preserving the derived-mask workflow.
3. Promote M11 junction ownership from closure-harness evidence into a future
   streamed composition/director pass.
4. Continue into the post-M18 hybrid procedural roadmap only after keeping the
   production-promotion gate active.
