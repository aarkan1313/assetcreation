# Review Scene Auto Tour

Date: 2026-05-08

## Purpose

This is the representative user-facing review scene for the current M1-M8
terrain workflow state. It is meant for quick remote-desktop validation, not as
a production gameplay scene.

Scene:

- `world3/scenes/review/source_stack_auto_tour.tscn`
- `world3/scenes/review/source_stack_full_map_fast_tour.tscn`
- `world3/scenes/review/source_stack_seam_integration_tour.tscn`
- `world3/scenes/review/source_stack_seam_nonoverlap_tour.tscn`

Script:

- `world3/scripts/World3AutoReviewTour.gd`

Smoke capture:

- `world3/docs/captures/review/source_stack_auto_tour_smoke.png`
- `world3/docs/captures/review/source_stack_auto_tour_topdown_smoke.png`
- `world3/docs/captures/review/source_stack_auto_tour_overview_smoke.png`
- `world3/docs/captures/review/source_stack_auto_tour_near_sweep_smoke.png`
- `world3/docs/captures/review/source_stack_full_map_fast_tour_smoke.png`
- `world3/docs/captures/review/source_stack_seam_integration_tour_smoke.png`
- `world3/docs/captures/review/source_stack_seam_integration_tour_iso_smoke.png`
- `world3/docs/captures/review/source_stack_seam_integration_tour_3d_smoke.png`
- `world3/docs/captures/review/source_stack_seam_nonoverlap_tour_smoke.png`
- `world3/docs/captures/review/source_stack_seam_nonoverlap_tour_iso_smoke.png`
- `world3/docs/captures/review/source_stack_seam_nonoverlap_tour_3d_smoke.png`

## What It Shows

- Source-stack OpenTopo macro terrain.
- M4/M5 streamed visual baseline context.
- Quarantined M8 `m8_grassland_grass_calm_v3` sidecar detail candidate.
- 7x7 streamed chunk neighborhood using `ChunkLoader.gd`.
- Mirrored finite-source height/UV sampling, so non-toroidal OpenTopo crop
  edges do not create repeated height walls during the review loop.
- Optional source-footprint clipping. The full-map fast tour clips to both the
  height source bounds and the source macro valid mask, so invalid/no-image
  areas show as dataset boundary/empty background instead of fake beige terrain.
- M10 seam integration proof scene: two overlapping source crops integrated
  into one height/macro bundle with an explicit integration band.
- M10 nearby non-overlap proof scene: two compatible non-overlap crops
  integrated into one height/macro bundle with the same review camera path.
- Automatic camera tour through:
  - close 3D ground pass;
  - medium 3D boundary read;
  - iso close material read;
  - topdown footprint;
  - controlled topdown overview;
  - final near-field sweep.

## Controls

- `Space`: pause or resume auto tour.
- `N`: next view.
- `B`: previous view.
- `R`: reset tour.
- `H`: hide/show overlay.

## Read

Use these scenes to judge whether the current best visual lane reads coherently
across close, medium, iso, topdown, and 3D views. The default tour uses the
M4/M5 source-stack visual context with the M8 sidecar candidate, because the
M7 boundary-enabled scene is already validated separately and still reads too
diagnostic as a first user-facing review.

Do not treat it as a final art pass: the current terrain is still source-stack
validation material, and M8 organic texture cleanup is still active.

2026-05-09 correction: true far/horizon views are intentionally excluded from
the default tour. They expose finite-footprint limits that are real workflow
gaps, not acceptable representative review. The `show_footprint_debug_views`
toggle can expose that diagnostic view when needed, but normal review stays
inside the valid inspection footprint.

2026-05-09 runtime correction: the visible wall/box artifact in the tour came
from wrapping a finite OpenTopo height source whose opposite edges do not
match. `ChunkLoader.gd` now defaults to `source_repeat_mode = "mirror"` and the
auto-tour scenes set that explicitly. Legacy `"wrap"` remains available for
sources that have been proven toroidal/seam-safe; `"clamp"` is available for
finite-footprint diagnostics.

2026-05-09 full-map correction: the first fast full-map tour made missing
source imagery look like terrain by clamping to fallback material. The review
scene now uses `clip_to_source_bounds = true` and
`source_macro_valid_mask.png`, so absent source data is visible as a data
boundary instead of a plateau.

2026-05-09 M10 seam proofs: `source_stack_seam_integration_tour.tscn` covers
the overlap proof. `source_stack_seam_nonoverlap_tour.tscn` covers the nearby
non-overlap proof. Both auto-cycle topdown, iso, close 3D, medium 3D, and
footprint views over integrated seam artifacts. Use them to validate the
methodology shift away from forced repeated-source tiling.

## Next Steps After Review

1. If this scene reads well enough, continue M8 by running M4/M7 runtime trials
   for `m8_grassland_grass_calm_v3`.
2. Retry `grass` only after revising prompts to avoid landmarks, panels, patch
   islands, and individual plant objects.
3. Generate and review the untested organic queue items:
   `temperate_forest_grass`, `tundra_moss`, and `tundra_lichen`.
4. After M8 cleanup, continue the near roadmap: M9 performance/interaction,
   M10 cross-source blending, M11 junction transitions, and M12 view parity.
