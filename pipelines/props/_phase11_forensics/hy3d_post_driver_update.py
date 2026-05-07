"""Post-driver-update recovery sequence.

Run this AFTER the NVIDIA driver update completes (and reboot if asked).

Sequence:
  1. Print new driver / CUDA runtime
  2. Force-reinstall the kijai cu130 custom_rasterizer wheel (overwriting the broken bare 0.1)
  3. Smoke-test custom_rasterizer + custom_rasterizer_kernel imports
  4. Smoke-test a tiny CUDA op via custom_rasterizer

If all 4 pass, we re-launch ComfyUI + fire gate-2 PBR.
"""
import subprocess
import sys
from pathlib import Path

VENV_PY = Path(r"D:\assets\animators\ComfyUI_HY3D\.venv\Scripts\python.exe")
WHEEL = Path(r"D:\assets\animators\ComfyUI_HY3D\custom_nodes\ComfyUI-Hunyuan3DWrapper\wheels\custom_rasterizer-0.1.0+torch2100.cuda130-cp312-cp312-win_amd64.whl")


def run(cmd, **kw):
    print(f"\n$ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.stdout:
        print(r.stdout[-2000:])
    if r.stderr:
        print("STDERR:", r.stderr[-2000:], file=sys.stderr)
    return r.returncode == 0


def main():
    # 1. driver state
    print("=== Driver state ===")
    run(["nvidia-smi", "--query-gpu=driver_version,name", "--format=csv,noheader"])

    # 2. force-reinstall cu130 wheel
    print("\n=== Reinstalling kijai cu130 wheel ===")
    if not WHEEL.exists():
        print(f"FATAL wheel not found: {WHEEL}")
        return 2
    ok = run([str(VENV_PY), "-m", "pip", "install", "--force-reinstall", "--no-deps", str(WHEEL)])
    if not ok:
        print("FATAL pip install failed (server probably still holding the .pyd)")
        return 3

    # 3. import test
    print("\n=== Import test ===")
    ok = run([str(VENV_PY), "-c",
              "import custom_rasterizer, custom_rasterizer_kernel; print('rasterizer OK:', custom_rasterizer.__file__)"])
    if not ok:
        print("FATAL: rasterizer import failed")
        return 4

    # 4. tiny CUDA op
    print("\n=== Tiny CUDA op (rasterize 1 triangle) ===")
    ok = run([str(VENV_PY), "-c", """
import torch
import custom_rasterizer
import custom_rasterizer_kernel
pos = torch.tensor([[[-0.5,-0.5,0,1],[0.5,-0.5,0,1],[0.,0.5,0,1]]], dtype=torch.float32, device='cuda')
tri = torch.tensor([[0,1,2]], dtype=torch.int32, device='cuda')
findices, bary = custom_rasterizer_kernel.rasterize_image(pos[0], tri, False, 64, 64, 1, 0)
print('rasterized OK, findices shape:', findices.shape)
"""])
    if not ok:
        print("FATAL: rasterize op failed (PTX still mismatched? Driver too new for kernel?)")
        return 5

    print("\n=== ALL SMOKES PASS ===")
    print("Next steps:")
    print("  1. Relaunch ComfyUI: cd D:/assets/animators/ComfyUI_HY3D && .venv/Scripts/python main.py --listen 127.0.0.1 --port 8189 --disable-auto-launch")
    print("  2. Re-fire gate-2: python D:/tmp/hy3d_gate2.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
