"""HY3D-2.1 quality sweep on the real Egyptian obelisk concept.

Sweeps the four knobs most likely to affect output quality:
  - octree_resolution (DiT shape)
  - max_facenum       (postprocess)
  - view_size         (multi-view paint)
  - texture_size      (final UV bake)
  - paint_steps       (multi-view diffusion steps)

Each run lands at world/props/ai_routes/hunyuan3d/sweep_<id>/.
At the end, prints a wall-clock + face-count + texture-size table.
"""
import sys, json, time, shutil
from pathlib import Path
sys.path.insert(0, r"D:\assets")
from pipelines._meta.comfy_runner import ComfyRunner, load_workflow

CONCEPT = Path(r"D:\assets\world\props\concepts\ruined_obelisk_a\source.png")
WF = Path(r"D:\assets\pipelines\_meta\comfy_workflows\hunyuan3d_21_image_to_glb_pbr.json")
OUT_ROOT = Path(r"D:\assets\world\props\ai_routes\hunyuan3d\sweep")
OUT_ROOT.mkdir(parents=True, exist_ok=True)

# Sweep configs. id, octree, max_faces, view_size, texture_size, paint_steps
RUNS = [
    ("baseline",       384,  40000, 512,  1024, 10),  # what we already shipped
    ("hi_geo",         512, 100000, 512,  1024, 10),  # denser geometry
    ("hi_paint",       384,  40000, 1024, 2048, 20),  # higher-res textures + more paint steps
    ("hero_max",       512, 100000, 1024, 2048, 30),  # everything turned up
]

r = ComfyRunner("http://127.0.0.1:8189")

results = []
for run_id, octree, max_faces, view_size, tex_size, paint_steps in RUNS:
    print(f"\n=== sweep run: {run_id} ===")
    print(f"  octree={octree}  max_faces={max_faces}  view={view_size}  tex={tex_size}  paint_steps={paint_steps}")

    out_dir = OUT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    wf_full = load_workflow(WF)
    wf = {k: v for k, v in wf_full.items() if not k.startswith("_")}

    comfy_name = r.upload_image(CONCEPT, name=f"sweep_{run_id}.png", overwrite=True)
    wf["1"]["inputs"]["image"] = comfy_name
    # Apply overrides
    wf["4"]["inputs"]["octree_resolution"] = octree
    wf["5"]["inputs"]["max_facenum"]       = max_faces
    wf["7"]["inputs"]["view_size"]         = view_size
    wf["7"]["inputs"]["texture_size"]      = tex_size
    wf["7"]["inputs"]["steps"]             = paint_steps
    wf["9"]["inputs"]["output_mesh_name"]  = f"sweep_{run_id}"

    missing = r.missing_node_types(wf)
    if missing:
        print(f"  FATAL missing nodes: {missing}", file=sys.stderr)
        continue

    t0 = time.time()
    prompt_id = r.submit(wf)
    print(f"  submitted prompt_id={prompt_id}")
    history = r.wait_for_history(prompt_id, timeout_s=2400.0, poll_s=5.0)
    elapsed = time.time() - t0
    print(f"  DONE in {elapsed:.1f}s")

    # Harvest from temp/
    src_glb = Path(r"D:\assets\animators\ComfyUI_HY3D\temp") / f"sweep_{run_id}.glb"
    src_obj = Path(r"D:\assets\animators\ComfyUI_HY3D\temp") / f"sweep_{run_id}.obj"
    src_alb = Path(r"D:\assets\animators\ComfyUI_HY3D\temp") / f"sweep_{run_id}.jpg"
    src_met = Path(r"D:\assets\animators\ComfyUI_HY3D\temp") / f"sweep_{run_id}_metallic.jpg"
    src_rou = Path(r"D:\assets\animators\ComfyUI_HY3D\temp") / f"sweep_{run_id}_roughness.jpg"
    if src_glb.exists():
        shutil.copy(src_glb, out_dir / "model_lod0.glb")
    for src, name in ((src_alb, "albedo.jpg"), (src_met, "metallic.jpg"), (src_rou, "roughness.jpg"), (src_obj, "source.obj")):
        if src.exists():
            shutil.copy(src, out_dir / name)

    # Inspect the GLB
    import trimesh
    if (out_dir / "model_lod0.glb").exists():
        m = trimesh.load(out_dir / "model_lod0.glb", force="mesh")
        verts = len(m.vertices)
        faces = len(m.faces)
        mat = m.visual.material if hasattr(m.visual, "material") else None
        tex_actual = mat.baseColorTexture.size[0] if mat and getattr(mat, "baseColorTexture", None) else None
        glb_mb = (out_dir / "model_lod0.glb").stat().st_size / (1024 * 1024)
    else:
        verts = faces = 0
        tex_actual = None
        glb_mb = 0.0

    settings = dict(octree=octree, max_faces=max_faces, view_size=view_size, tex_size=tex_size, paint_steps=paint_steps)
    results.append(dict(
        run_id=run_id, settings=settings, wall_clock_s=elapsed,
        verts=verts, faces=faces, texture_px=tex_actual, glb_mb=round(glb_mb, 2)
    ))

# Summary table
print("\n=== SWEEP SUMMARY ===")
print(f"{'run_id':<12} {'time_s':>8} {'verts':>8} {'faces':>8} {'tex_px':>7} {'GLB MB':>7}")
for r in results:
    print(f"{r['run_id']:<12} {r['wall_clock_s']:>8.1f} {r['verts']:>8} {r['faces']:>8} {str(r['texture_px']):>7} {r['glb_mb']:>7.2f}")

# Save full results JSON
(OUT_ROOT / "sweep_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"\nresults -> {OUT_ROOT / 'sweep_results.json'}")
