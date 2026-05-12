# M6 Source Material Noise Audit

Date: 2026-05-08

This audit targets green/organic terrain materials after user review flagged
grass/leaves as too noisy for production. It is a source-material QA pass,
not a transition or chunk-streaming failure.

| Material | Status | HF energy | Grad p95 | Green dom | Flags |
|----------|--------|-----------|----------|-----------|-------|
| `grassland_dirt` | flagged | 0.080442 | 0.214291 | 1e-06 | high_frequency_noise, sharp_micro_contrast |
| `grassland_grass` | flagged | 0.061187 | 0.178127 | 0.0 | high_frequency_noise, sharp_micro_contrast |
| `grass` | flagged | 0.034363 | 0.127072 | 0.287614 | green_organic_speckle |
| `temperate_forest_dirt` | flagged | 0.054547 | 0.145082 | 7.2e-05 | sharp_micro_contrast |
| `grassland_rock_light` | flagged | 0.049959 | 0.13811 | 0.0 | sharp_micro_contrast |
| `tundra_moss` | flagged | 0.043535 | 0.136708 | 0.037008 | sharp_micro_contrast |
| `tundra_lichen` | flagged | 0.042001 | 0.142026 | 0.044482 | sharp_micro_contrast |
| `temperate_forest_rock_light` | flagged | 0.047766 | 0.133915 | 0.002858 | sharp_micro_contrast |
| `temperate_forest_snow` | flagged | 0.042819 | 0.145952 | 0.014487 | sharp_micro_contrast |
| `temperate_forest_grass` | flagged | 0.040315 | 0.131602 | 0.000515 | sharp_micro_contrast |
| `temperate_forest_rock_dark` | ok | 0.034619 | 0.091884 | 0.000204 | - |
| `grassland_rock_dark` | ok | 0.030075 | 0.087942 | 2.5e-05 | - |
| `grassland_snow` | ok | 0.027039 | 0.064721 | 0.0 | - |
| `rock_light` | ok | 0.019886 | 0.060259 | 1e-06 | - |
| `desert_dry_brush` | ok | 0.01657 | 0.046493 | 0.0 | - |
| `scrub_dense` | ok | 0.003214 | 0.008394 | 0.000146 | - |
| `scrub_sparse` | ok | 0.001999 | 0.005609 | 7e-06 | - |

## Verdict

Flagged 10 of 17 audited green/organic materials.
Production promotion should prioritize flagged materials before adding more
runtime visual complexity.
