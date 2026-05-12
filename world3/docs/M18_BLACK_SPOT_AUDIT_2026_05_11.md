# M18 Black Spot Audit - 2026-05-11

## Verdict

The black spots in the M18 guided-neighbor slice were not a Godot render bug
and were not introduced by the procedural neighbor. They came from the left
real-source macro crop:

`world3/textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png`

The specific M18 crop `229,734,229,457`, resized to `512x1024`, contained
valid-pixel dark islands. Because the valid mask for that crop is full
coverage, the seam solver correctly preserved those pixels and enlarged them
into visible dark blobs in the runtime macro.

## Root Cause

- Left real-source crop: dark islands present.
- Right procedural source: clean for the same near-black threshold.
- M18 seam solver: faithfully copied/blended the left crop.
- Valid mask: did not mark these islands invalid, so the previous valid-area
  repair path never touched them.

Measured before repair:

| Asset | dark_lt18 | spot components | spot area |
|---|---:|---:|---:|
| left source crop resized to `512x1024` | `3.5320%` | `147` | `16364 px` |
| M18 runtime macro | `1.8215%` | `133` | `15514 px` |
| right procedural render albedo | `0.0000%` | `0` | `0 px` |

## Fix Applied

Added an opt-in dark-island repair pass to
`world3/pipeline/build_terrain_seam_integration_proof.py`.

The repair runs after crop/resize and before seam integration. It selects
valid interior islands by luma and connected-component area, then fills those
pixels from nearest non-selected neighbors. This keeps the global source stack
unchanged and only repairs the M18 runtime slice where the crop is known bad.

M18 was rebuilt with:

```powershell
python world3/pipeline/build_terrain_seam_integration_proof.py `
  --left-macro world3/textures/source_stack/gloss_scrub_source_stack/source_macro_albedo.png `
  --left-valid-mask world3/textures/source_stack/gloss_scrub_source_stack/source_macro_valid_mask.png `
  --left-heightmap world3/toporeview/gloss_mountain_textured_master/heightmap.png `
  --left-meta world3/toporeview/gloss_mountain_textured_master/meta.json `
  --right-macro world3/toporeview/m17_guided_desert_canyon_neighbor/layers/render_albedo.png `
  --right-valid-mask world3/toporeview/m17_guided_desert_canyon_neighbor/layers/source_valid_mask.png `
  --right-heightmap world3/toporeview/m17_guided_desert_canyon_neighbor/heightmap.png `
  --right-meta world3/toporeview/m17_guided_desert_canyon_neighbor/meta.json `
  --left-crop 229,734,229,457 `
  --right-crop 0,0,512,1024 `
  --output-size 512,1024 `
  --overlap-px 128 `
  --height-feather-px 224 `
  --color-feather-px 384 `
  --profile-blur-px 12 `
  --macro-band-mode blend `
  --macro-bridge-blur-px 26 `
  --macro-bridge-detail-strength 0.12 `
  --dark-spot-repair-side left `
  --dark-spot-threshold 0.07058823529411765 `
  --dark-spot-min-area-px 4 `
  --dark-spot-max-area-px 5000 `
  --artifact-name "M18 guided neighbor slice proof" `
  --integration-kind m17_extracted_rules_rebaked_through_m10_seam_solver_for_m18_runtime_review `
  --policy adjacent_overlap_sources_solved_into_single_runtime_bundle `
  --texture-out world3/textures/source_stack/m18_guided_neighbor_slice_proof `
  --topo-out world3/toporeview/m18_guided_neighbor_slice_proof `
  --metrics-out world3/docs/captures/review/terrain_seam_m18_guided_neighbor_metrics.json
```

## Result

Manifest repair metrics:

- selected left-crop components: `147`
- selected left-crop pixels: `16377`
- largest selected component: `1372 px`
- left-crop dark fraction: `3.5320% -> 0.4084%`

Runtime macro audit after repair:

| Asset | dark_lt18 | spot components | spot area |
|---|---:|---:|---:|
| M18 runtime macro | `0.1278%` | `4` | `382 px` |

The remaining screenshot-level dark-pixel counts are not a clean black-spot
signal because the captures include the fixed black UI overlay, terrain
shadows, and scatter silhouettes. The canonical check for this issue is the
runtime macro plus the `dark_spot_repair` block in:

`world3/textures/source_stack/m18_guided_neighbor_slice_proof/manifest.json`

## Regenerated Evidence

- `world3/textures/source_stack/m18_guided_neighbor_slice_proof/source_macro_albedo.png`
- `world3/textures/source_stack/m18_guided_neighbor_slice_proof/manifest.json`
- `world3/docs/captures/review/terrain_seam_m18_guided_neighbor_metrics.json`
- `world3/textures/source_stack/m18_guided_neighbor_slice_proof/layers/feature_mask_metrics.json`
- `world3/docs/captures/review/source_stack_m18_guided_neighbor_topdown.png`
- `world3/docs/captures/review/source_stack_m18_guided_neighbor_iso.png`
- `world3/docs/captures/review/source_stack_m18_guided_neighbor_medium.png`
- `world3/docs/captures/review/source_stack_m18_guided_neighbor_close.png`
