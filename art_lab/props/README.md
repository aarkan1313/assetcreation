# Prop Kit Lab

Local-first prop and decoration pipeline for `D:\assets`.

The goal is to turn biome decoration rules into real prop families that can be
generated, normalized, reviewed, and exported to Godot. This layer does not
require Meshy or any cloud generator. Cloud tools can be tested later as
baselines, but the core path is:

```text
prop kit JSON
  -> recipe JSON per family
  -> CPU validation / planning
  -> Blender procedural generation when GPU/Blender is free
  -> normalization, LOD, collision, thumbnail, billboard
  -> gallery + human shortlist
  -> Godot prop scenes + scatter export
```

## Layout

```text
art_lab/props/
  kits/                         kit-level family list
  recipes/                      one generator recipe per prop/decal family
  tools/
    prop_common.py              shared contract helpers
    prop_validate.py            CPU-only schema/contract check
    prop_plan_kit.py            CPU-only dry-run plan + queues
    prop_gallery.py             CPU-only HTML review shell
  output/                       generated plans/galleries

world/props/library/
  <prop_id>/
    prop.json
    model_lod0.glb
    model_lod1.glb
    model_lod2.glb
    collision.glb
    thumbnail.png
    billboard.png
    qa.json
```

## CPU-Only Prep Commands

Validate the kit and recipes:

```powershell
python art_lab\props\tools\prop_validate.py --kit art_lab\props\kits\mossy_highland_ruins.props.json
```

Create a dry-run plan and future generation queues:

```powershell
python art_lab\props\tools\prop_plan_kit.py `
  --kit art_lab\props\kits\mossy_highland_ruins.props.json `
  --out-id mossy_highland_prep_001
```

Build an HTML gallery shell from the plan:

```powershell
python art_lab\props\tools\prop_gallery.py `
  --plan art_lab\props\output\mossy_highland_prep_001\plan.json
```

Generate safe CPU decals from the queue:

```powershell
python art_lab\props\tools\prop_run_queue.py `
  --queue art_lab\props\output\mossy_highland_prep_001\decal_queue.json
```

## GPU-Free Boundary

Validation, planning, gallery generation, and decal generation do not call
Blender, CUDA, Hunyuan3D, TRELLIS, Stable Fast 3D, or Godot. They prepare the
exact tasks to run later.

When the GPU is free, the next implementation slice is:

1. Smoke-test `prop_make_blender.py` for `blender_rock_cluster_v1`,
   `blender_foliage_cards_v1`, `blender_mushroom_cluster_v1`,
   `blender_log_v1`, and `blender_ruins_v1`.
2. Use the generated `blender_queue.json` as the work list.
3. Emit library folders under `world/props/library/<prop_id>/`.
4. Re-run `prop_validate.py --strict-assets`.
5. Rebuild the gallery and review only the best variants.

See `GPU_TEST_RUNBOOK.md` for the exact sequence.
