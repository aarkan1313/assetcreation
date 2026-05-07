# Prop Kit Plan: mossy_highland_ruins

Created: 2026-05-06T13:48:26.003758+00:00
Kit: `art_lab/props/kits/mossy_highland_ruins.props.json`
Library: `world/props/library`

## Summary

- Families: 13
- Variants: 76
- Ready: 26
- Partial: 0
- Missing: 50
- Blender tasks: 50
- Local AI tasks: 0
- Decal tasks: 0

## Validation Issues

- None

## Family Plan

- `rock_cluster_small`: 8 variants, `blender_rock_cluster_v1`, `scatter_multimesh`, collision `none`
- `rock_cluster_medium`: 6 variants, `blender_rock_cluster_v1`, `scatter_multimesh`, collision `simple`
- `fern_clump`: 6 variants, `blender_foliage_cards_v1`, `scatter_multimesh`, collision `none`
- `moss_tuft`: 8 variants, `blender_foliage_cards_v1`, `scatter_multimesh`, collision `none`
- `mushroom_cluster`: 5 variants, `blender_mushroom_cluster_v1`, `scatter_multimesh`, collision `none`
- `fallen_log`: 4 variants, `blender_log_v1`, `scene_prop`, collision `simple`
- `ruin_block`: 8 variants, `blender_ruins_v1`, `scatter_multimesh`, collision `simple`
- `ruin_pillar`: 5 variants, `blender_ruins_v1`, `scene_prop`, collision `simple`
- `moss_patch_01`: 6 variants, `texture_decal_v1`, `decal`, collision `none`
- `mud_splash_02`: 6 variants, `texture_decal_v1`, `decal`, collision `none`
- `cracked_stone_03`: 6 variants, `texture_decal_v1`, `decal`, collision `none`
- `rune_stain_01`: 4 variants, `texture_decal_v1`, `decal`, collision `none`
- `scorch_01`: 4 variants, `texture_decal_v1`, `decal`, collision `none`

## First Commands To Run Later

### blender
- `blender -b --python art_lab/props/tools/prop_make_blender.py -- --recipe art_lab/props/recipes/rock_cluster_small.recipe.json --variant-id rock_cluster_small_01 --out world/props/library/rock_cluster_small_01`
- `blender -b --python art_lab/props/tools/prop_make_blender.py -- --recipe art_lab/props/recipes/rock_cluster_small.recipe.json --variant-id rock_cluster_small_02 --out world/props/library/rock_cluster_small_02`
- `blender -b --python art_lab/props/tools/prop_make_blender.py -- --recipe art_lab/props/recipes/rock_cluster_small.recipe.json --variant-id rock_cluster_small_03 --out world/props/library/rock_cluster_small_03`
- `blender -b --python art_lab/props/tools/prop_make_blender.py -- --recipe art_lab/props/recipes/rock_cluster_small.recipe.json --variant-id rock_cluster_small_04 --out world/props/library/rock_cluster_small_04`
- `blender -b --python art_lab/props/tools/prop_make_blender.py -- --recipe art_lab/props/recipes/rock_cluster_small.recipe.json --variant-id rock_cluster_small_05 --out world/props/library/rock_cluster_small_05`
- `blender -b --python art_lab/props/tools/prop_make_blender.py -- --recipe art_lab/props/recipes/rock_cluster_small.recipe.json --variant-id rock_cluster_small_06 --out world/props/library/rock_cluster_small_06`
- `blender -b --python art_lab/props/tools/prop_make_blender.py -- --recipe art_lab/props/recipes/rock_cluster_small.recipe.json --variant-id rock_cluster_small_07 --out world/props/library/rock_cluster_small_07`
- `blender -b --python art_lab/props/tools/prop_make_blender.py -- --recipe art_lab/props/recipes/rock_cluster_small.recipe.json --variant-id rock_cluster_small_08 --out world/props/library/rock_cluster_small_08`
- ... 42 more tasks in `blender_queue.json`
