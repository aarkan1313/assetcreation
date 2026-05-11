# M18 Representative Slice First Pass - 2026-05-10

M18 starts with a constrained runtime proof: take the M17 guided procedural
neighbor, rebake it through the accepted M10 seam solver, and review it through
the same close/medium/iso/topdown bands used by M12/M13.

This is not full M18 closure. It is the first runtime slice scaffold.

## Inputs

- Real source: `world3/textures/source_stack/gloss_scrub_source_stack/`.
- Procedural source: `world3/toporeview/m17_guided_desert_canyon_neighbor/`.
- Solver: `world3/pipeline/build_terrain_seam_integration_proof.py`.
- Manifest: `world3/jobs/m18_representative_slice_manifest.json`.

## Outputs

- Runtime source stack:
  `world3/textures/source_stack/m18_guided_neighbor_slice_proof/`.
- Runtime height/meta:
  `world3/toporeview/m18_guided_neighbor_slice_proof/`.
- Metrics:
  `world3/docs/captures/review/terrain_seam_m18_guided_neighbor_metrics.json`.
- Tour scene:
  `world3/scenes/review/source_stack_m18_guided_neighbor_tour.tscn`.
- Capture sheet:
  `world3/docs/captures/review/source_stack_m18_guided_neighbor_contact_sheet.png`.

## Metrics Read

- Height join p95: `0.23 m` left-to-band, `0.31 m` band-to-right.
- Post-overlap height mismatch: `1.90 m` median, `6.95 m` p95.
- Macro join p95: `0.086` left-to-band, `0.009` band-to-right.
- Valid-mask coverage: `1.0`.

## Visual Read

Accepted as workflow evidence:

- The M17 procedural bundle can re-enter the source-stack terrain path.
- Topdown, iso, close, and medium captures all come from the same runtime
  bundle.
- There is no invalid plateau, missing-data void, or Godot capture failure.

Conditional / not accepted as final:

- The procedural side still reads too smooth and broad in close/medium views.
- This first pass does not yet combine M15 scatter/features or M11 junction
  ownership into the same runtime slice.
- The transition is mechanically solved, not final art-directed ecotone quality.

## Next

1. Add M15 feature/scatter policy to the M18 runtime slice.
2. Decide whether M11 junction ownership must be physically composed into the
   same terrain, or represented as a required adjacent runtime band in the M18
   review harness.
3. Improve the procedural neighbor generator with richer drainage, rock
   exposure, and close-detail fields before any production promotion attempt.

Regenerate the slice:

```powershell
python world3/pipeline/build_terrain_seam_integration_proof.py --left-macro world3/textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png --left-valid-mask world3/textures/source_stack/gloss_scrub_source_stack/source_macro_valid_mask.png --left-heightmap world3/toporeview/gloss_mountain_textured_master/heightmap.png --left-meta world3/toporeview/gloss_mountain_textured_master/meta.json --right-macro world3/toporeview/m17_guided_desert_canyon_neighbor/layers/render_albedo.png --right-valid-mask world3/toporeview/m17_guided_desert_canyon_neighbor/layers/source_valid_mask.png --right-heightmap world3/toporeview/m17_guided_desert_canyon_neighbor/heightmap.png --right-meta world3/toporeview/m17_guided_desert_canyon_neighbor/meta.json --left-crop 229,734,229,457 --right-crop 0,0,512,1024 --output-size 512,1024 --overlap-px 128 --height-feather-px 224 --color-feather-px 384 --profile-blur-px 20 --macro-band-mode blend --macro-bridge-blur-px 26 --macro-bridge-detail-strength 0.12 --artifact-name "M18 guided procedural neighbor representative slice" --integration-kind m18_guided_real_to_procedural_integration_band_proof --policy m17_extracted_rules_rebaked_through_m10_seam_solver_for_m18_runtime_review --texture-out world3/textures/source_stack/m18_guided_neighbor_slice_proof --topo-out world3/toporeview/m18_guided_neighbor_slice_proof --metrics-out world3/docs/captures/review/terrain_seam_m18_guided_neighbor_metrics.json
```
