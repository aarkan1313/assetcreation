# Phase 11 Props Deep-Dive — forensics scripts

Scratch scripts captured at the end of Phase 11 (2026-05-06). Kept for reproducibility — these are the actual one-shots that produced the A/B and sweep outputs in `world/props/ai_routes/`. They were originally at `D:\tmp\` and are preserved here so future runs can re-use the same gate / sweep / render orchestration without rebuilding from scratch.

For the active, production-grade adapters use:
- `pipelines/props/ai_route_dispatch.py`
- `pipelines/props/trellis2_batch.py`
- `pipelines/props/trellis2_route.py`
- `pipelines/props/hunyuan3d_route.py`

For the patches required to make these venvs work see `pipelines/props/TRELLIS2_PATCHES.md` and the `../../../docs/audits/REVIEW.md` Phase 11 section.

## Files

| File | Purpose |
|---|---|
| `hy3d_gate1.py` | First HY3D-2.1 smoke run — geometry-only, no PBR. Path-hardcoded for `ruined_obelisk_a` concept. |
| `hy3d_gate2.py` | HY3D-2.1 PBR-textured run (geometry + multi-view paint + bake + inpaint). |
| `hy3d_post_driver_update.py` | Recovery sequence script after the NVIDIA driver upgrade 592 -> 596 to fix the cu130 PTX issue. Reinstalls the prebuilt rasterizer wheel and smoke-tests imports. |
| `hy3d_resume_after_restart.md` | State-snapshot notes from the mid-Phase-11 PC restart. Documents what was running, what was deferred, and the resume sequence. |
| `hy3d_sweep.py` | HY3D-2.1 quality sweep (4 configs: baseline / hi_geo / hi_paint / hero_max). Produces `world/props/ai_routes/hunyuan3d/sweep/<run_id>/`. |
| `trellis2_gate.py` | First Trellis2 4B smoke run on `ruined_obelisk_a` concept. Loads pipeline + envmap + runs once. |
| `trellis2_sweep.py` | Trellis2 quality sweep (4 configs: low / mid / hi / hi_tex). Smart: loads model once, generates mesh once, runs 4 different `o_voxel.postprocess.to_glb()` configs against the cached mesh. |
| `render_glb_compare.py` | Blender 5.1 headless multi-GLB renderer. Renders 5 views (front/back/left/right/iso) per GLB. Runs as `blender --background --python this`. |
| `sweep_compare_sheet.py` | Builds the 4x2 grid PNG from the rendered iso views. Output: `D:\tmp\sweep_compare_sheet.png`. |

## Reuse pattern

If we ever want to re-run the sweep on a new concept:

1. Stage the concept as `world/props/concepts/<id>/source.png`.
2. Boot ComfyUI HY3D server: `python D:/assets/animators/ComfyUI_HY3D/main.py --listen 127.0.0.1 --port 8189 --disable-auto-launch`.
3. Edit `hy3d_sweep.py` CONCEPT path and run with `D:/assets/animators/ComfyUI_HY3D/.venv/Scripts/python.exe hy3d_sweep.py`.
4. Edit `trellis2_sweep.py` CONCEPT path and run with `D:/assets/animators/Trellis2/venv/Scripts/python.exe trellis2_sweep.py`.
5. Edit `render_glb_compare.py` GLBS list and run via Blender 5.1 headless.
6. Edit `sweep_compare_sheet.py` LABELS list and run with any python that has PIL.
