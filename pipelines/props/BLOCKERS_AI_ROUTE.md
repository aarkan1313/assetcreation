# AI Prop Routes - Enable Steps

The AI routes are now adapters, not vapor:

- `pipelines/props/trellis2_route.py` - local image-to-3D route, dry-run safe, CUDA model load gated.
- `pipelines/props/meshy_route.py` - Meshy hero-prop route, dry-run safe, paid cloud call gated by explicit env authorization.

No GPU model and no paid API call was run during the audit/expand pass.

## Remaining Blockers

### 1. Concept/reference images

The routes need a PNG/JPG input per hero prop. Put those under:

```text
world/props/input_images/
```

The dry-run probes used `world/props/library/rock_small_a01/thumbnail.png` only to verify manifest shape.

### 2. Trellis2 runtime command

`trellis2_route.py` owns the output contract, but the exact local Trellis2 invocation varies by checkout. Set:

```powershell
$env:TRELLIS2_PROP_CMD = '<local Trellis2 command with {image} {out_glb} {seed} {target_tris}>'
```

Then run, once the GPU is free:

```powershell
python pipelines\props\trellis2_route.py world\props\input_images\altar.png --id altar_trellis2 --device cuda --run-model --publish
```

Expected first success: `world/props/library/altar_trellis2/model_lod0.glb` plus `prop.json`.

### 3. Meshy spend authorization

Meshy calls spend credits. The adapter refuses to call the API unless this is set for the current batch:

```powershell
$env:MESHY_AUTH_FOR_THIS_BATCH = 'YES'
```

Then:

```powershell
python pipelines\props\meshy_route.py world\props\input_images\altar.png --id altar_meshy --publish --texture-prompt "weathered basalt altar, moss, engraved runes"
```

Expected first success: `world/props/library/altar_meshy/model_lod0.glb` plus `prop.json`. If the underlying Meshy wrapper ever gains an interactive prompt, stop and add the non-interactive flag there before spending a batch.

## Shared Postprocess

Both routes intentionally produce the same `prop_asset.v1` shape as the procedural route. After a real model lands:

```powershell
python pipelines\props\lod_chain.py <prop_id>
python pipelines\props\collision_decompose.py <prop_id>
python pipelines\props\billboard_bake.py <prop_id> --single
python pipelines\props\pbr_material_bind.py <prop_id>
python pipelines\props\export_godot.py --id <prop_id>
python pipelines\props\validate_props.py
```

## Verified Dry Runs

```powershell
python pipelines\props\trellis2_route.py world\props\library\rock_small_a01\thumbnail.png --id trellis2_rock_small_probe --device cpu --dry-run
python pipelines\props\meshy_route.py world\props\library\rock_small_a01\thumbnail.png --id meshy_rock_small_probe --dry-run
```

Both wrote `prop_asset.v1`-shaped manifests under `world/props/ai_routes/` without GPU or cloud calls.

