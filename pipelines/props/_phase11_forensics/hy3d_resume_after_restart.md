# Resume state after PC restart — 2026-05-06 PM

## What was done before restart

Phase 11A hero-prop deep-dive on the Egyptian obelisk concept.

✅ HY3D-2.1 install fully working (cu130 / torch 2.10 / driver 596.36 / sm_120)
✅ Trellis2 install fully working (cu128 / torch 2.8)
✅ Both produced PBR-textured GLBs end-to-end
✅ A/B doc landed at `D:\assets\world\props\ai_routes\AB_hy3d_vs_trellis2_2026_05_06.md`

## What was happening when restart started

HY3D quality sweep (4 configs) hit a bug on run #2:

```
AttributeError: 'Hunyuan3DPaintPipeline' object has no attribute 'view_processor'
```

**Root cause**: `clean_memory()` at `textureGenPipeline.py:280-283` deleted `self.view_processor` after the first successful workflow run. ComfyUI cached the pipeline object across runs; second run's `Hy3DInPaint.process()` failed because the attribute was gone.

**Patch applied**: Modified `textureGenPipeline.py:280` to keep `view_processor` alive (it's a thin python orchestrator, not a GPU-heavy object). Now `clean_memory()` only releases `render` and `model`. See diff via:

```
git -C D:\assets\animators\ComfyUI_HY3D\custom_nodes\ComfyUI-Hunyuan3d-2-1 diff hy3dpaint/textureGenPipeline.py
```

## What to do after restart

1. **Boot ComfyUI HY3D server**:
   ```powershell
   cd D:\assets\animators\ComfyUI_HY3D
   .\.venv\Scripts\python.exe main.py --listen 127.0.0.1 --port 8189 --disable-auto-launch
   ```
   Wait for `To see the GUI go to: http://127.0.0.1:8189`. Should take ~30s.

2. **Re-fire the sweep** to verify the patch works:
   ```powershell
   D:\assets\animators\ComfyUI_HY3D\.venv\Scripts\python.exe D:\tmp\hy3d_sweep.py
   ```
   4 runs at ~85-180s each. Outputs land at `D:\assets\world\props\ai_routes\hunyuan3d\sweep\<run_id>\`.

3. **Render comparison** with Blender after sweep completes:
   Edit `D:\tmp\render_glb_compare.py` GLBS list to include all 4 sweep outputs, then:
   ```powershell
   "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --background --python D:\tmp\render_glb_compare.py
   ```

4. **Continue with**: build `pipelines/props/ai_route_dispatch.py` based on sweep results, then wire it into the route adapters.

## State of all GPU compute

- ComfyUI HY3D server: was running on port 8189; expected to be killed by restart
- Trellis2: was idle (last run completed at ~20:31)
- LM Studio + Epic Games Launcher + stale ComfyUI on port 8188: were killed earlier; restart-state unknown

## Files touched in patches (forensics, do not roll back)

| File | Patch |
|---|---|
| `D:\assets\animators\ComfyUI_HY3D\custom_nodes\ComfyUI-Hunyuan3d-2-1\hy3dpaint\multiview_utils.py` | Added `trust_remote_code=True` to `HunyuanPaintPipeline.from_pretrained` (line 45) |
| `D:\assets\animators\ComfyUI_HY3D\custom_nodes\ComfyUI-Hunyuan3d-2-1\hy3dpaint\convert_utils.py` | Replaced Chinese-character print at line 138 with ASCII (Windows cp1252 crash) |
| `D:\assets\animators\ComfyUI_HY3D\custom_nodes\ComfyUI-Hunyuan3d-2-1\hy3dpaint\textureGenPipeline.py` | `clean_memory()` no longer deletes `view_processor` (this restart's fix) |
| `D:\assets\animators\Trellis2\venv\Lib\site-packages\flex_gemm\kernels\__init__.py` | Added CUDA + torch DLL search dirs at import time |
| `D:\assets\animators\Trellis2\venv\Lib\site-packages\flex_gemm\kernels\triton\__init__.py` | New file — pure-torch fallback for `indice_weighed_sum_fwd/bwd` (sentinel + dtype safe) |
| `D:\tmp\trellis2_gate.py` | Defensive `Trimesh.export()` instead of `bytes` write |

## Dispatcher draft (for after sweep)

```python
# pipelines/props/ai_route_dispatch.py — DRAFT
def pick_route(render_class: str, has_fine_relief: bool = False) -> tuple[str, dict]:
    """
    render_class: 'hero_prop' | 'scene_prop' | 'scatter_multimesh'
    has_fine_relief: True if concept has carved detail / hieroglyphs / etc
    """
    if render_class == 'scatter_multimesh':
        # mid/far distance, biome scatter — HY3D is the right scale
        return ('hunyuan3d', {
            'octree': 384, 'max_facenum': 40000,
            'view_size': 512, 'texture_size': 1024, 'paint_steps': 10,
        })
    if render_class == 'hero_prop' and has_fine_relief:
        # carved relief / sharp edges win on Trellis2
        return ('trellis2', {
            'decimation_target': 200000, 'texture_size': 2048,
        })
    if render_class == 'hero_prop':
        # generic hero — push HY3D knobs first; if not satisfactory, switch to Trellis2
        return ('hunyuan3d', {
            'octree': 512, 'max_facenum': 100000,
            'view_size': 1024, 'texture_size': 2048, 'paint_steps': 30,
        })
    # scene_prop — middle ground
    return ('hunyuan3d', {
        'octree': 384, 'max_facenum': 60000,
        'view_size': 768, 'texture_size': 1024, 'paint_steps': 15,
    })
```

That's a starting point — sweep results will inform the actual setting values.
