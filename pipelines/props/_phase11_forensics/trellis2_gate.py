"""Trellis2 image-to-3D smoke run on the same concept used for HY3D-2.1.

Mirrors the pattern in animators/Trellis2/example.py but with our concept image.
Outputs to D:/assets/world/props/ai_routes/trellis2/ruined_obelisk_a/.

CRITICAL: must be run from D:/assets/animators/Trellis2/ working dir
(or PYTHONPATH set) so 'import trellis2' resolves.
"""
import os
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import sys
sys.path.insert(0, r"D:\assets\animators\Trellis2")

import time
from pathlib import Path

import cv2
import torch
from PIL import Image

from trellis2.pipelines import Trellis2ImageTo3DPipeline
from trellis2.renderers import EnvMap
import o_voxel

CONCEPT = Path(r"D:\assets\world\props\concepts\ruined_obelisk_a\source.png")
OUT_DIR = Path(r"D:\assets\world\props\ai_routes\trellis2\ruined_obelisk_a_gate")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_GLB = OUT_DIR / "model_lod0.glb"

# Need an HDRI for the renderer; use the bundled forest.exr from Trellis2 repo
HDRI = Path(r"D:\assets\animators\Trellis2\assets\hdri\forest.exr")
if not HDRI.exists():
    print(f"[trellis2] WARNING: HDRI missing at {HDRI}; renderer setup may fail")

print(f"[trellis2] torch {torch.__version__} cuda={torch.cuda.is_available()}")
print(f"[trellis2] free GPU mem before: {torch.cuda.mem_get_info()[0]/1e9:.1f} GB")

t0 = time.time()
print(f"[trellis2] loading EnvMap from {HDRI} ...")
exr_bgr = cv2.imread(str(HDRI), cv2.IMREAD_UNCHANGED)
exr_rgb = cv2.cvtColor(exr_bgr, cv2.COLOR_BGR2RGB)
envmap = EnvMap(torch.tensor(exr_rgb, dtype=torch.float32, device="cuda"))
print(f"[trellis2] envmap loaded in {time.time()-t0:.1f}s")

t1 = time.time()
print(f"[trellis2] loading pipeline microsoft/TRELLIS.2-4B ... (large download on first run)")
pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
pipeline.cuda()
print(f"[trellis2] pipeline loaded in {time.time()-t1:.1f}s")
print(f"[trellis2] free GPU mem after pipeline load: {torch.cuda.mem_get_info()[0]/1e9:.1f} GB")

t2 = time.time()
print(f"[trellis2] running on {CONCEPT} ...")
image = Image.open(CONCEPT)
mesh = pipeline.run(image)[0]
mesh.simplify(16777216)
print(f"[trellis2] mesh generated in {time.time()-t2:.1f}s")
print(f"[trellis2] vertices={len(mesh.vertices)} faces={len(mesh.faces)}")

t3 = time.time()
print(f"[trellis2] postprocess to GLB at {OUT_GLB} ...")
glb_bytes = o_voxel.postprocess.to_glb(
    vertices=mesh.vertices,
    faces=mesh.faces,
    attr_volume=mesh.attrs,
    coords=mesh.coords,
    attr_layout=mesh.layout,
    voxel_size=mesh.voxel_size,
    aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
    decimation_target=200000,  # cap for our prop pipeline (HY3D was 40k)
    texture_size=2048,
    remesh=True,
    remesh_band=1,
    remesh_project=0,
    verbose=True,
)
# o_voxel.postprocess.to_glb returns a trimesh.Trimesh (not bytes/path).
import trimesh as _tm
if isinstance(glb_bytes, (bytes, bytearray)):
    OUT_GLB.write_bytes(glb_bytes)
elif isinstance(glb_bytes, str):
    import shutil
    shutil.copyfile(glb_bytes, OUT_GLB)
elif isinstance(glb_bytes, _tm.base.Trimesh) or hasattr(glb_bytes, "export"):
    glb_bytes.export(str(OUT_GLB), file_type="glb")
else:
    print(f"[trellis2] WARNING: unexpected to_glb return type {type(glb_bytes)}")
print(f"[trellis2] GLB written in {time.time()-t3:.1f}s")

total = time.time() - t0
print(f"[trellis2] DONE in {total:.1f}s -> {OUT_GLB}")
