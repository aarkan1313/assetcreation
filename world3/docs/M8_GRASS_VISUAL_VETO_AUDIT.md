# ComfyUI Visual Veto Audit

Date: 2026-05-08

This advisory audit catches obvious organic-material visual failures
before sidecar staging. `needs_visual_review` is not a pass; it only
means the heuristic did not catch a hard veto.

| Material | Status | Flags | Green patches | Outliers | Axis line |
|----------|--------|-------|---------------|----------|-----------|
| `m8_grassland_grass_calm_v3` | needs_visual_review | - | 0.0 | 0.008472 | 1.401285 |
| `m8_grass_calm_v1` | needs_visual_review | - | 0.0 | 0.001987 | 1.641931 |
| `m8_grass_calm_v2` | veto | axis_aligned_panel_or_row_structure | 0.0 | 0.002342 | 1.862756 |
| `m8_grass_calm_v3` | veto | bright_green_patch_islands, axis_aligned_panel_or_row_structure | 0.101013 | 0.004444 | 2.539591 |
| `m8_grass_calm_v4_anchor_v1` | veto | colored_landmark_outliers, dark_landmark_blotches | 4e-06 | 0.041611 | 1.410671 |
