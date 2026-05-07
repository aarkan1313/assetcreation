# Prop Kit GPU Test Runbook

Use this when the GPU is free enough to run Blender or local 3D models.

## 0. Check GPU Headroom

```powershell
nvidia-smi
```

Wait if VRAM is near full or GPU utilization is pinned. The last check during
prep showed about 23.6 GB of 24.5 GB used and 100 percent utilization, so only
CPU tasks were run.

## 1. Validate The Contract

```powershell
python art_lab\props\tools\prop_validate.py `
  --kit art_lab\props\kits\mossy_highland_ruins.props.json
```

Expected current state after prep:

- 13 recipes loaded
- 76 variants planned
- 26 ready decal variants
- 50 missing Blender mesh variants
- 0 validation issues

## 2. Rebuild The Plan/Gallery

```powershell
python art_lab\props\tools\prop_plan_kit.py `
  --kit art_lab\props\kits\mossy_highland_ruins.props.json `
  --out-id mossy_highland_prep_001

python art_lab\props\tools\prop_gallery.py `
  --plan art_lab\props\output\mossy_highland_prep_001\plan.json
```

Open:

```text
art_lab/props/output/mossy_highland_prep_001/gallery.html
```

## 3. Blender Smoke Test

Run one cheap rock first:

```powershell
blender -b --python art_lab\props\tools\prop_make_blender.py -- `
  --recipe art_lab\props\recipes\rock_cluster_small.recipe.json `
  --variant-id rock_cluster_small_01 `
  --out world\props\library\rock_cluster_small_01
```

Expected files:

```text
world/props/library/rock_cluster_small_01/
  model_lod0.glb
  thumbnail.png
  prop.json
  qa.json
```

Then rebuild the plan and gallery. The ready count should increase by 1.

## 4. First Full Family Test

Generate the remaining `rock_cluster_small` variants from `blender_queue.json`.
The commands are already written in:

```text
art_lab/props/output/mossy_highland_prep_001/blender_queue.json
art_lab/props/output/mossy_highland_prep_001/review.md
```

Do not run all 50 mesh tasks first. Run one family, inspect thumbnails, then
iterate on `prop_make_blender.py` before generating the rest.

## 5. Strict Validation

After all mesh variants are generated:

```powershell
python art_lab\props\tools\prop_validate.py `
  --kit art_lab\props\kits\mossy_highland_ruins.props.json `
  --strict-assets
```

This should pass only when every expected prop folder has:

- `prop.json`
- `qa.json`
- `thumbnail.png`
- `model_lod0.glb` for mesh props or `decal.png` for decal props

## 6. Next Integration Test

Once the library has mesh props:

1. Re-run biome dressing:

```powershell
python art_lab\biomes\tools\dress_biome.py `
  --kit mossy_highland_ruins `
  --terrain smoketest_a `
  --map mythos_a `
  --id mossy_x_mythos_props
```

2. Build a Godot prop/scatter exporter that resolves each `asset` in
   `scatter.csv` to variants in `world/props/library`.
3. Export one Godot scene with chunked `MultiMeshInstance3D` groups.

