# M17 Real-Data Rule Extraction - 2026-05-10

M17 starts converting accepted source-stack proofs into procedural-neighbor
rules. This is intentionally modest: first metrics, then one guided
procedural neighbor bundle with the same height/macro/valid-mask contract.

## Rule Targets

- Height range target: `53.10 m`
- Slope p95 target: `0.835`
- Roughness p95 target: `1.16 m`
- Wash mean target: `0.0440`
- Shrub mean target: `0.1016`
- Dry grass mean target: `0.2795`
- Transition coverage target: `0.3118`

## Samples

| Source | Elev range | Slope p95 | Rough p95 | Masks |
|--------|------------|-----------|-----------|-------|
| `m10_ecotone_layer` | `74.45m` | `1.060` | `1.59m` | wash_line_mask, shrub_carryover_mask, dry_grass_density_mask, soil_exposure_mask, rock_cluster_mask, no_scatter_mask, ecotone_weight, splat_weights_rgba |
| `m11_three_way_junction` | `53.51m` | `0.814` | `1.28m` | wash_line_mask, shrub_carryover_mask, dry_grass_density_mask, soil_exposure_mask, rock_cluster_mask, no_scatter_mask, splat_weights_rgba |
| `m11_fourway_corner` | `53.82m` | `0.695` | `1.05m` | wash_line_mask, shrub_carryover_mask, dry_grass_density_mask, soil_exposure_mask, rock_cluster_mask, no_scatter_mask, splat_weights_rgba |
| `m12_runtime_parity` | `53.82m` | `0.695` | `1.05m` | wash_line_mask, shrub_carryover_mask, dry_grass_density_mask, soil_exposure_mask, rock_cluster_mask, no_scatter_mask, splat_weights_rgba |
| `m10_real_to_procedural` | `29.88m` | `0.911` | `0.82m` | - |

## Guided Neighbor

- Output: `world3/toporeview/m17_guided_desert_canyon_neighbor`
- Recipe: `world3/jobs/m17_procedural_neighbor_recipe.json`

The generated neighbor is not production terrain. It is a procedural bundle
that can enter the same source-stack review path as earlier proofs.

## Visual Board

`world3/docs/captures/review/source_stack_m17_rule_extraction_board.png`

## Next

1. Feed the M17 guided neighbor into a real-to-procedural source-stack review scene.
2. Compare against the M10 procedural canyon proof and M12 gameplay bands.
3. Expand extraction to multiple real DEM families before M19 corpus-scale spectral fitting.

Regenerate:

```powershell
python world3/pipeline/build_m17_real_data_rule_extraction.py
```
