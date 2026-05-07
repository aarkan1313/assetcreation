"""Trellis2 quality sweep on the same Egyptian obelisk concept.

Sweeps the two main quality knobs:
  - decimation_target (final polycount cap)
  - texture_size      (UV bake resolution)

Each run lands at world/props/ai_routes/trellis2/sweep/<id>/.
"""
import os, sys, time, json, shutil
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
sys.path.insert(0, r"D:\assets\animators\Trellis2")

from pathlib import Path
import cv2, torch
from PIL import Image
from trellis2.pipelines import Trellis2ImageTo3DPipeline
from trellis2.renderers import EnvMap
import o_voxel
import trimesh

CONCEPT = Path(r"D:\assets\world\props\concepts\ruined_obelisk_a\source.png")
HDRI    = Path(r"D:\assets\animators\Trellis2\assets\hdri\forest.exr")
OUT_ROOT = Path(r"D:\assets\world\props\ai_routes\trellis2\sweep")
OUT_ROOT.mkdir(parents=True, exist_ok=True)

# id, decimation_target, texture_size
RUNS = [
    ("low",     50000, 1024),    # scatter-grade
    ("mid",    200000, 2048),    # what we already shipped
    ("hi",     500000, 2048),    # more geometry
    ("hi_tex", 200000, 4096),    # higher tex res
]

# Load EnvMap + pipeline ONCE; reuse for each sweep run
print("[trellis2] loading envmap...")
exr_bgr = cv2.imread(str(HDRI), cv2.IMREAD_UNCHANGED)
exr_rgb = cv2.cvtColor(exr_bgr, cv2.COLOR_BGR2RGB)
envmap = EnvMap(torch.tensor(exr_rgb, dtype=torch.float32, device="cuda"))

print("[trellis2] loading pipeline microsoft/TRELLIS.2-4B (cached)...")
t_load = time.time()
pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
pipeline.cuda()
print(f"[trellis2] pipeline loaded in {time.time()-t_load:.1f}s")

image = Image.open(CONCEPT)

# Generate mesh ONCE; reuse across decimation/texture sweeps
print("[trellis2] generating mesh on real concept (one time)...")
t_mesh = time.time()
mesh = pipeline.run(image)[0]
mesh.simplify(16777216)
mesh_gen_s = time.time() - t_mesh
print(f"[trellis2] mesh generated in {mesh_gen_s:.1f}s ({len(mesh.vertices)} verts)")

results = []
for run_id, dec_tgt, tex_sz in RUNS:
    print(f"\n=== sweep run: {run_id} (decimation={dec_tgt}, tex={tex_sz}²) ===")
    out_dir = OUT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_glb = out_dir / "model_lod0.glb"

    t0 = time.time()
    glb_obj = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices, faces=mesh.faces,
        attr_volume=mesh.attrs, coords=mesh.coords,
        attr_layout=mesh.layout, voxel_size=mesh.voxel_size,
        aabb=[[-0.5,-0.5,-0.5],[0.5,0.5,0.5]],
        decimation_target=dec_tgt,
        texture_size=tex_sz,
        remesh=True, remesh_band=1, remesh_project=0,
        verbose=False,
    )
    if hasattr(glb_obj, "export"):
        glb_obj.export(str(out_glb), file_type="glb")
    elapsed = time.time() - t0

    # Inspect
    m = trimesh.load(out_glb, force="mesh")
    mat = m.visual.material if hasattr(m.visual, "material") else None
    tex_actual = mat.baseColorTexture.size[0] if mat and getattr(mat, "baseColorTexture", None) else None
    glb_mb = out_glb.stat().st_size / (1024*1024)
    results.append(dict(
        run_id=run_id,
        decimation_target=dec_tgt,
        texture_size=tex_sz,
        wall_clock_s=round(elapsed, 1),
        verts=len(m.vertices),
        faces=len(m.faces),
        texture_px=tex_actual,
        glb_mb=round(glb_mb, 2),
    ))
    print(f"  DONE in {elapsed:.1f}s -> {len(m.vertices)} verts / {len(m.faces)} faces / {tex_actual}² / {glb_mb:.2f} MB")

print("\n=== SWEEP SUMMARY ===")
print(f"{'run_id':<8} {'time_s':>8} {'verts':>8} {'faces':>8} {'tex_px':>7} {'GLB MB':>7}")
for r in results:
    print(f"{r['run_id']:<8} {r['wall_clock_s']:>8.1f} {r['verts']:>8} {r['faces']:>8} {str(r['texture_px']):>7} {r['glb_mb']:>7.2f}")

(OUT_ROOT / "sweep_results.json").write_text(
    json.dumps({"mesh_gen_s": mesh_gen_s, "runs": results}, indent=2),
    encoding="utf-8",
)
print(f"\nresults -> {OUT_ROOT / 'sweep_results.json'}")
