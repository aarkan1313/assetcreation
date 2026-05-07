"""FLUX albedo generation helper for v2.

Wraps `pipelines/textures/flux_seamless.py` as a subprocess. That tool runs
4 ComfyUI passes (text2img -> circular shift -> img2img heal -> reverse shift)
and produces a seamless tileable albedo PNG via FLUX.2-klein-4B.

Output for `id="<job_id>__<biome>"` lands at
`D:/assets/world/textures/library/<id>/<id>_albedo.png` (the v1 library path).
We then copy it back into the worldgen v2 job output dir so the rest of v2 only
ever reads from `output/<job>/`.

Requires:
- ComfyUI running on COMFY_HOST (default http://127.0.0.1:8188)
- FLUX 2 klein + Qwen text encoder + flux2 VAE installed in
  D:/assets/animators/ComfyUI/models/
"""
from __future__ import annotations
import shutil
import subprocess
import sys
from pathlib import Path

V1_FLUX_TOOL = Path(r"D:/assets/pipelines/textures/flux_seamless.py")
V1_LIBRARY = Path(r"D:/assets/world/textures/library")


def generate(prompt: str, asset_id: str, size: int = 1024, steps: int = 4,
             seed: int = 42, heal_strength: float = 0.35,
             host: str = "http://127.0.0.1:8188") -> Path:
    """Run flux_seamless and return the path to the generated albedo PNG."""
    if not V1_FLUX_TOOL.exists():
        raise FileNotFoundError(
            f"flux_albedo: missing v1 FLUX tool at {V1_FLUX_TOOL}. "
            "Did pipelines/textures/ get deleted?"
        )
    cmd = [
        sys.executable, str(V1_FLUX_TOOL),
        "--prompt", prompt,
        "--id", asset_id,
        "--size", str(size),
        "--steps", str(steps),
        "--seed", str(seed),
        "--heal-strength", str(heal_strength),
        "--host", host,
    ]
    print(f"[flux_albedo] generating {asset_id!r} via FLUX ({size}x{size}, {steps} steps)")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(f"flux_seamless failed for {asset_id} (rc={result.returncode})")
    out = V1_LIBRARY / asset_id / f"{asset_id}_albedo.png"
    if not out.exists():
        raise FileNotFoundError(f"flux_albedo: expected output missing at {out}")
    return out


def generate_to(prompt: str, asset_id: str, dest: Path, **kwargs) -> Path:
    """Generate then copy to a final destination path."""
    src = generate(prompt, asset_id, **kwargs)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return dest
