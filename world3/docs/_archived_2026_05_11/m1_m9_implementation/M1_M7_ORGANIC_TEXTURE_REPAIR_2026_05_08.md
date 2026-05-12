# M1-M7 Organic Texture Repair

Date: 2026-05-08

This is the first deterministic texture repair pass after the M1-M7
vision audit. The outputs are candidates, not promotions. They are kept
outside the canonical material catalog until terrain-context captures pass.

Policy: reduce object-scale silhouettes and neon/high-frequency organic
noise, then feed only calm albedo plus neutral detail into runtime review.

Contact sheet:

- `docs/captures/visual_remediation/organic_repair_contact_sheet.png`

| Source | Candidate | HF before | HF after | Grad before | Grad after | Green before | Green after | Sheet |
|--------|-----------|-----------|----------|-------------|------------|--------------|-------------|-------|
| `grassland_grass` | `grassland_grass_repair_calm` | 0.061187 | 0.002578 | 0.178127 | 0.006705 | 0.0 | 0.0 | `world3/docs/captures/visual_remediation/grassland_grass_repair_calm_before_after.png` |
| `grass` | `grass_repair_calm` | 0.034363 | 0.00231 | 0.127072 | 0.006678 | 0.287614 | 0.083854 | `world3/docs/captures/visual_remediation/grass_repair_calm_before_after.png` |
| `temperate_forest_grass` | `temperate_forest_grass_repair_calm` | 0.040315 | 0.002728 | 0.131602 | 0.007193 | 0.000515 | 0.0 | `world3/docs/captures/visual_remediation/temperate_forest_grass_repair_calm_before_after.png` |
| `tundra_moss` | `tundra_moss_repair_calm` | 0.043535 | 0.004082 | 0.136708 | 0.011124 | 0.037008 | 0.024732 | `world3/docs/captures/visual_remediation/tundra_moss_repair_calm_before_after.png` |
| `tundra_lichen` | `tundra_lichen_repair_calm` | 0.042001 | 0.002713 | 0.142026 | 0.006895 | 0.044482 | 0.018263 | `world3/docs/captures/visual_remediation/tundra_lichen_repair_calm_before_after.png` |

## Verdict

This pass fixes the worst workflow problem: procedural organic images are
no longer allowed to enter M2/M5/M7 as raw object-photo tiles. The repair
candidates are calmer, but still need Godot close/mid/far terrain-context
review before any `close = ok` promotion.

Runtime use rule:

1. Keep these candidates in `materials/catalog_repair_candidates.json`.
2. Bind them as albedo-only/low-strength detail in source-stack review.
3. Do not promote normal/detail influence until terrain-context captures
   reach the 70 percent target.
