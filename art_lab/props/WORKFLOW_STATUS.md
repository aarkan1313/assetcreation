# Prop Workflow Status

Updated: 2026-05-06

## Current State

The prop/decor pipeline is prepared for later GPU/Blender tests without needing
Meshy or cloud generation.

Completed CPU-only work:

- Added local-first prop contract docs.
- Added `mossy_highland_ruins` prop kit covering every asset/decal referenced
  by `art_lab/biomes/kits/mossy_highland_ruins.json`.
- Added 13 recipe JSONs:
  - 8 mesh families: rocks, ferns, moss, mushrooms, logs, ruin blocks, pillars.
  - 5 decal families: moss, mud, cracked stone, rune stains, scorch marks.
- Added validation, planning, gallery, queue-runner, CPU decal generation, and
  Blender generator entrypoint scripts.
- Generated 26 CPU decal variants into `world/props/library`.
- Generated the current dry-run plan and gallery at
  `art_lab/props/output/mossy_highland_prep_001`.

Current validation result:

```text
recipes loaded: 13
variants planned: 76
ready/partial/missing: 26/0/50
validation issues: 0
```

The 50 missing variants are the Blender mesh props. They were intentionally not
generated while the GPU was saturated.

## Key Files

```text
art_lab/props/kits/mossy_highland_ruins.props.json
art_lab/props/output/mossy_highland_prep_001/plan.json
art_lab/props/output/mossy_highland_prep_001/gallery.html
art_lab/props/output/mossy_highland_prep_001/blender_queue.json
art_lab/props/GPU_TEST_RUNBOOK.md
```

## Next Action When GPU Is Free

Run one Blender smoke test:

```powershell
blender -b --python art_lab\props\tools\prop_make_blender.py -- `
  --recipe art_lab\props\recipes\rock_cluster_small.recipe.json `
  --variant-id rock_cluster_small_01 `
  --out world\props\library\rock_cluster_small_01
```

Then rebuild the plan/gallery and inspect the thumbnail before generating the
remaining rock variants.

