# ComfyUI Texture Workflow Inventory

Date: 2026-05-08

## Purpose

This inventory makes the ComfyUI/`aaa_texture.py` lane explicit in the
M1-M7 visual remediation work. OpenTopo source stacks and ComfyUI-generated
materials are peer inputs: OpenTopo gives real macro terrain truth; ComfyUI
gives scalable biome/material coverage, controlled variants, and fantasy or
missing-biome fill.

The current goal is workflow quality, not silent production promotion.
Generated texture candidates must pass the same terrain-context review bar
before they can drive close-detail or transition evidence.

## Inventory Summary

- Catalog materials total: 31
- ComfyUI/aaa_texture materials: 25
- Library source folders present: 25/25
- Runtime core map sets complete: 25/25
- Library core map sets complete: 25/25
- QA summaries present: 25/25
- Priority regeneration blockers: 5
- Close-view materials still marked `needs_review`: 18

## Shared Promotion Gate

A ComfyUI material can participate in M5/M7/M8 visual closure only after:

- source library maps and staged runtime maps are present;
- `aaa_texture.py` quality gate and seam QA pass;
- 2x2 tile and Blender preview do not show object-like repetition;
- Godot terrain-context captures pass close, mid, and far views;
- source-stack detail use starts albedo-only/low-strength until normal/detail review passes.

## Priority Regeneration Queue

| Material | Source asset | Catalog QA | Close view | Recommended action |
|----------|--------------|------------|------------|--------------------|
| grass | wgv3_grass | B | needs_review | regenerate_with_comfy_prompt_and_terrain_gate |
| tundra_moss | tundra_moss | A | needs_review | regenerate_with_comfy_prompt_and_terrain_gate |
| tundra_lichen | tundra_lichen | A | needs_review | regenerate_with_comfy_prompt_and_terrain_gate |
| temperate_forest_grass | wgv3_tf_leaf_litter | B | needs_review | regenerate_with_comfy_prompt_and_terrain_gate |
| grassland_grass | wgv3_gl_tall_grass | B | needs_review | regenerate_with_comfy_prompt_and_terrain_gate |

Use `world3/jobs/comfy_texture_regen_candidates.json` as the first M8
work queue. The first pass should regenerate these from prompt/variant
control, not rely only on deterministic blur/filter repair.

## Context-Review Queue

| Material | Source asset | Catalog QA | Action |
|----------|--------------|------------|--------|
| desert_dry_brush | desert_dry_brush | A | terrain_context_review_required |
| desert_sand | desert_sand | A | terrain_context_review_required |
| desert_canyon_rock | desert_canyon_rock | B | terrain_context_review_required |
| desert_dark_rock | desert_dark_rock | A | terrain_context_review_required |
| desert_salt_pan | desert_salt_pan | B | terrain_context_review_required |
| tundra_frost_rock | tundra_frost_rock | B | terrain_context_review_required |
| tundra_dark_rock | tundra_dark_rock | A | terrain_context_review_required |
| tundra_ice | tundra_ice | B | terrain_context_review_required |
| temperate_forest_rock_light | wgv3_tf_mossy_rock | A | terrain_context_review_required |
| temperate_forest_rock_dark | wgv3_tf_bark_rock | A | terrain_context_review_required |
| temperate_forest_snow | wgv3_tf_fern_ground | A | terrain_context_review_required |
| grassland_rock_dark | wgv3_gl_grass_rock | A | terrain_context_review_required |

## Runtime Staging Gaps

All ComfyUI runtime folders have the required core maps.

## Missing Or Incomplete Library Sets

All ComfyUI source library folders have the required core maps.

## Rebuild

```powershell
python world3/pipeline/build_comfy_material_candidate_catalog.py
```

Machine-readable output:
`world3/materials/comfy_texture_workflow_inventory.json`.
