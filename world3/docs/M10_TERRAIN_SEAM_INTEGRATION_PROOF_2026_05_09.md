# M10 Terrain Seam Integration Proof

Date: 2026-05-09

## Purpose

This is the first production-facing seam proof after the same-source repeat
correction. It does not wrap a finite crop. It takes two overlapping
real-source Gloss Mountain terrain bundles and emits one runtime bundle with a
solved integration band.

## Rung 1: Overlap Inputs

- Source macro: `world3/textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png`
- Source macro valid mask: `world3/textures/source_stack/gloss_scrub_source_stack/source_macro_valid_mask.png`
- Source height: `world3/toporeview/gloss_mountain_textured_master/heightmap.png`
- Source meta: `world3/toporeview/gloss_mountain_textured_master/meta.json`
- Left crop: `240,520,416,1024` in source-macro pixels.
- Right crop: `592,520,416,1024` in source-macro pixels.
- Overlap/integration band: `64 px`, about `33.6 m`.

The two crops overlap in the original source. That is intentional for the first
rung: the proof validates the integration-band artifact, runtime sampling,
mesh clipping, and visual review path before moving to unlike or non-overlap
sources.

## Rung 1 Outputs

- Generator: `world3/pipeline/build_terrain_seam_integration_proof.py`
- Runtime macro: `world3/textures/source_stack/gloss_scrub_seam_integration_proof/source_macro_albedo.png`
- Runtime valid mask: `world3/textures/source_stack/gloss_scrub_seam_integration_proof/source_macro_valid_mask.png`
- Seam mask: `world3/textures/source_stack/gloss_scrub_seam_integration_proof/seam_integration_mask.png`
- Manifest: `world3/textures/source_stack/gloss_scrub_seam_integration_proof/manifest.json`
- Runtime height: `world3/toporeview/gloss_mountain_seam_integration_proof/heightmap.png`
- Runtime meta: `world3/toporeview/gloss_mountain_seam_integration_proof/meta.json`
- Metrics: `world3/docs/captures/review/terrain_seam_integration_gloss_metrics.json`

Review scene:

- `world3/scenes/review/source_stack_seam_integration_tour.tscn`

Smoke captures:

- `world3/docs/captures/review/source_stack_seam_integration_tour_smoke.png`
- `world3/docs/captures/review/source_stack_seam_integration_tour_iso_smoke.png`
- `world3/docs/captures/review/source_stack_seam_integration_tour_3d_smoke.png`

Capture wrappers:

- `world3/scenes/review/capture_source_stack_seam_integration_topdown.tscn`
- `world3/scenes/review/capture_source_stack_seam_integration_iso.tscn`
- `world3/scenes/review/capture_source_stack_seam_integration_3d.tscn`

## Metrics

Height overlap before solve:

- mean: `0.011 m`
- p95: `0.029 m`
- max: `0.283 m`

Height overlap after solve:

- mean: `0.007 m`
- p95: `0.024 m`
- max: `0.277 m`

Macro overlap delta:

- mean: `0.000`
- p95: `0.000`
- max: `0.000`

Valid coverage:

- left: `1.000`
- right: `0.9999`
- band: `1.000`
- output: `0.9999`

## Runtime Fix Found

The 3D verification exposed a `ChunkLoader.gd` edge case: source-footprint
clipping can legitimately produce empty chunks outside the valid terrain
footprint. `ChunkLoader.gd` now returns an empty mesh for zero-triangle chunks
and skips collision creation for empty meshes instead of submitting an invalid
surface to Godot.

## Visual Read

Pass for first-rung seam integration:

- no height wall;
- no ghost strip;
- no orthophoto box;
- no fake fallback plateau inside the valid footprint;
- topdown, iso, and close 3D all render the integrated band as continuous
  terrain.

Remaining caveats:

- finite-source footprint edges remain visible by design when clipping exposes
  missing data;
- the source macro still contains baked shadows, shrub/tree blobs, and
  orthophoto lighting variation;
- this is overlap-based same-source proof, not unlike-biome or non-overlap
  synthesis yet.

## Rung 2: Nearby Non-Overlap Proof

The second proof uses nearby Gloss Mountain crops with a source gap between
them. It is still same-source, but it does not rely on shared pixels.

Inputs:

- Left crop: `560,980,256,768`
- Right crop: `832,980,256,768`
- Source gap: `16 px`
- Integration band: `96 px`

Outputs:

- Runtime macro: `world3/textures/source_stack/gloss_scrub_seam_nonoverlap_proof/source_macro_albedo.png`
- Runtime valid mask: `world3/textures/source_stack/gloss_scrub_seam_nonoverlap_proof/source_macro_valid_mask.png`
- Seam mask: `world3/textures/source_stack/gloss_scrub_seam_nonoverlap_proof/seam_integration_mask.png`
- Manifest: `world3/textures/source_stack/gloss_scrub_seam_nonoverlap_proof/manifest.json`
- Runtime height: `world3/toporeview/gloss_mountain_seam_nonoverlap_proof/heightmap.png`
- Runtime meta: `world3/toporeview/gloss_mountain_seam_nonoverlap_proof/meta.json`
- Metrics: `world3/docs/captures/review/terrain_seam_nonoverlap_gloss_metrics.json`
- Review scene: `world3/scenes/review/source_stack_seam_nonoverlap_tour.tscn`
- Captures:
  - `world3/docs/captures/review/source_stack_seam_nonoverlap_tour_smoke.png`
  - `world3/docs/captures/review/source_stack_seam_nonoverlap_tour_iso_smoke.png`
  - `world3/docs/captures/review/source_stack_seam_nonoverlap_tour_3d_smoke.png`

Metrics:

- Raw height edge mismatch: `6.71 m` mean, `16.30 m` p95.
- Post-solve band mismatch: `2.80 m` mean, `8.20 m` p95.
- Join steps after solve: `0.24 m` mean / `0.80 m` p95 on the left join,
  `0.22 m` mean / `0.66 m` p95 on the right join.
- Valid mask coverage is repaired to full valid because the generated artifact
  had `0.9999` coverage before tiny-hole fill.

Visual read:

- no hard height wall;
- no missing terrain voids after valid-mask hole fill;
- topdown/iso/3D read as one terrain strip;
- baked orthophoto lighting and shrub/tree marks remain visible, so this is a
  workflow proof, not a production beauty pass.

Capture wrappers:

- `world3/scenes/review/capture_source_stack_seam_nonoverlap_topdown.tscn`
- `world3/scenes/review/capture_source_stack_seam_nonoverlap_iso.tscn`
- `world3/scenes/review/capture_source_stack_seam_nonoverlap_3d.tscn`

Method lesson:

- A harsher first non-overlap crop pair required a `26 m` vertical bias and
  produced either a ghosted alpha-blend strip or a muddy lowpass bridge. That
  was rejected. Crop compatibility needs to be a real gate before solving.

## Rung 3: Different-Source Real Terrain Candidate

The third proof moves from same-source Gloss Mountain crops to a different real
source pair. This is the first rung that is production-relevant for neighboring
catalog data, because the left and right sides do not share source pixels,
lighting, capture scale, or elevation datum.

Compatibility scanner:

- `world3/pipeline/scan_terrain_seam_compatibility.py`

Current selected pair:

- Left source: `world3/textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png`
- Left valid mask: `world3/textures/source_stack/gloss_scrub_source_stack/source_macro_valid_mask.png`
- Left height: `world3/toporeview/gloss_mountain_textured_master/heightmap.png`
- Right source: `world3/toporeview/phase2_fusion_max/layers/render_albedo.png`
- Right valid mask: `world3/toporeview/phase2_fusion_max/layers/source_valid_mask.png`
- Right height: `world3/toporeview/phase2_fusion_max/heightmap.png`
- Left crop: `199,699,229,457`
- Right crop: `6642,3001,614,1229`
- Normalized solve size: `512,1024`
- Integration band: `128 px`

Scanner evidence:

- Candidate list: `world3/docs/captures/review/terrain_seam_cross_source_gloss_guadalupe_clean_candidates.json`
- Candidate preview: `world3/docs/captures/review/terrain_seam_cross_source_gloss_guadalupe_clean_candidates_preview.png`
- Extended preview used for human/vision veto:
  `world3/docs/captures/review/terrain_seam_cross_source_gloss_guadalupe_clean_candidates_7_18_preview.png`

The best numeric candidates were rejected because they contained a visible
human-made landmark in the Gloss crop. The current candidate is lower-ranked
numerically but cleaner as terrain. This establishes a required method rule:
compatibility scoring is a filter, not an autopromote decision. Visual veto for
landmarks, source-edge fill, and obvious capture artifacts is mandatory.

Outputs:

- Runtime macro: `world3/textures/source_stack/gloss_guadalupe_cross_source_proof/source_macro_albedo.png`
- Runtime valid mask: `world3/textures/source_stack/gloss_guadalupe_cross_source_proof/source_macro_valid_mask.png`
- Seam mask: `world3/textures/source_stack/gloss_guadalupe_cross_source_proof/seam_integration_mask.png`
- Manifest: `world3/textures/source_stack/gloss_guadalupe_cross_source_proof/manifest.json`
- Runtime height: `world3/toporeview/gloss_guadalupe_cross_source_proof/heightmap.png`
- Runtime meta: `world3/toporeview/gloss_guadalupe_cross_source_proof/meta.json`
- Metrics: `world3/docs/captures/review/terrain_seam_cross_source_gloss_guadalupe_metrics.json`
- Review scene: `world3/scenes/review/source_stack_cross_source_tour.tscn`
- Captures:
  - `world3/docs/captures/review/source_stack_cross_source_tour_smoke.png`
  - `world3/docs/captures/review/source_stack_cross_source_tour_iso_smoke.png`
  - `world3/docs/captures/review/source_stack_cross_source_tour_3d_smoke.png`

Metrics:

- Raw height datum mismatch: `719.25 m` median, `723.36 m` p95.
- Post-solve overlap mismatch: `0.86 m` median, `3.75 m` p95.
- Join steps after solve: `0.25 m` p95 on the left join, `0.07 m` p95 on
  the right join.
- Raw macro RGB delta p95: `0.431`.
- Post macro RGB delta p95: `0.362`.
- Macro join step p95: `0.052` on the left join, `0.035` on the right join.
- Valid mask coverage is full valid.

Implementation fix found:

- The RGB solve previously faded the color-bias correction inside the feather
  zone but accidentally reapplied the full global bias across the rest of the
  right source. That could create a tinted rectangular source block. The RGB
  feather now leaves the far side of the right source unchanged unless the
  feather is explicitly disabled.

Current read:

- Geometry/runtime integration is credible for a first different-source proof:
  the vertical datum mismatch is solved into a smooth terrain band, not a wall.
- Macro/source-style integration is improved but not final closure. It still
  needs live human validation and likely a stronger material/source-style pass
  before M10 is marked closed.

## Review Lighting Correction

The first M10 review window read too bright because of the review scene setup,
not because the seam artifacts were white. The terrain shader now exposes
review-only `roughness_floor`, `specular_strength`, and `albedo_gain` controls.
The seam scenes use a matte validation preset:

- dark neutral background: `Color(0.08, 0.095, 0.1, 1)`;
- source macro strength: `0.96`;
- albedo gain: `0.92`;
- roughness floor: `0.86`;
- specular: `0.0`;
- tonemap exposure: `0.58`;
- sun energy: `0.55`;
- ambient energy: `0.2`;
- glow explicitly disabled.

This keeps tan/white source-photo rocks visible but removes false white/blue
review glare. Remaining bright patches are source orthophoto content and should
be handled by source-material/feature extraction, not by hiding them with post
processing.

Validated capture command pattern:

```powershell
$args = @(
  "--path", "D:/assets/world3",
  "--single-window",
  "--disable-crash-handler",
  "--scene", "res://scenes/review/capture_source_stack_seam_nonoverlap_topdown.tscn"
)
$p = Start-Process -FilePath "C:/Godot/Godot_v4.5-stable_win64.exe" -ArgumentList $args -Wait -PassThru
"EXIT=$($p.ExitCode)"
```

Avoid the older waited `--script res://scripts/_codex_render_runner.gd` path for
these review captures on this machine; it can trigger a Windows access
violation before scene code runs.

## Next Step

M10 should not be marked closed yet. The next M10 gate is:

1. live-review the Gloss-Guadalupe proof in topdown, iso, and close 3D;
2. add explicit scanner veto/score support for landmarks, source-edge fill,
   and capture artifacts;
3. improve the macro/source-style bridge if the live scene still shows a
   rectangular source-style break;
4. only after different-source real terrain passes those gates, promote to
   real-to-procedural and unlike-biome cross-source blending.
