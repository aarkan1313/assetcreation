"""ComfyUI prompt-to-texture wrapper for FLUX.2-klein-4B.

Calls a running ComfyUI server (default http://127.0.0.1:8188) with the
canonical FLUX.2-klein 4B distilled text-to-image workflow, then optionally
pipes the result through derive_pbr_v2 for a full PBR set.

Usage:
  Start ComfyUI separately:
    cd D:\assets\animators\ComfyUI && .\start.ps1
  Then:
    python comfy_generate.py --prompt "mossy basalt cliff seamless tileable" --id basalt_a --category Rock

Models expected (run download_flux2_klein.ps1 first):
  models/diffusion_models/flux-2-klein-4b.safetensors
  models/text_encoders/qwen_3_4b.safetensors
  models/vae/flux2-vae.safetensors
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import numpy as np
from PIL import Image


COMFY_HOST = "http://127.0.0.1:8188"
LIBRARY = Path("D:/assets/world/textures/library")


def build_workflow_flux2_klein(prompt: str, unet: str, clip: str, vae: str,
                                size: int, seed: int, steps: int = 4) -> dict:
    """FLUX.2-klein 4B distilled text-to-image workflow.

    Adapted from ComfyUI's canonical template
    `image_flux2_klein_text_to_image.json` (4B distilled subgraph), flattened
    for the API-prompt endpoint.

    Distilled klein uses: cfg=1, euler sampler, Flux2Scheduler with ~4 steps,
    ConditioningZeroOut for negative prompt.
    """
    return {
        # ---- model loaders ----
        "10": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet, "weight_dtype": "default"},
        },
        "11": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip, "type": "flux2", "device": "default"},
        },
        "12": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae},
        },
        # ---- prompt encoding ----
        "20": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["11", 0]},
        },
        "21": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": ["20", 0]},
        },
        # ---- guider ----
        "30": {
            "class_type": "CFGGuider",
            "inputs": {"model": ["10", 0], "positive": ["20", 0],
                        "negative": ["21", 0], "cfg": 1.0},
        },
        # ---- sampling pipeline ----
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "41": {
            "class_type": "Flux2Scheduler",
            "inputs": {"steps": steps, "width": size, "height": size},
        },
        "42": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": seed},
        },
        "43": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": size, "height": size, "batch_size": 1},
        },
        "50": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["42", 0],
                "guider": ["30", 0],
                "sampler": ["40", 0],
                "sigmas": ["41", 0],
                "latent_image": ["43", 0],
            },
        },
        # ---- decode + save ----
        "60": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["50", 0], "vae": ["12", 0]},
        },
        "70": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "asset_factory_flux2", "images": ["60", 0]},
        },
    }


def queue_prompt(workflow: dict, host: str = COMFY_HOST) -> str:
    payload = json.dumps({"prompt": workflow, "client_id": str(uuid.uuid4())}).encode()
    req = urllib.request.Request(f"{host}/prompt", data=payload,
                                  headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read().decode())["prompt_id"]


def wait_for(prompt_id: str, host: str = COMFY_HOST, timeout: int = 1200) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        with urllib.request.urlopen(f"{host}/history/{prompt_id}") as r:
            hist = json.loads(r.read().decode())
        if prompt_id in hist:
            return hist[prompt_id]
        time.sleep(2)
    raise TimeoutError(f"prompt {prompt_id} did not complete within {timeout}s")


def download_output(host: str, filename: str, subfolder: str, type_: str, dest: Path):
    qs = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": type_})
    with urllib.request.urlopen(f"{host}/view?{qs}") as r, dest.open("wb") as f:
        f.write(r.read())


def run_comfy(prompt: str, unet: str, clip: str, vae: str, size: int, seed: int,
              steps: int, host: str) -> Path:
    print(f"[comfy] FLUX.2-klein prompt: {prompt!r}")
    print(f"  unet={unet} clip={clip} vae={vae}")
    print(f"  size={size}x{size} steps={steps} seed={seed}")
    wf = build_workflow_flux2_klein(prompt, unet, clip, vae, size, seed, steps)
    pid = queue_prompt(wf, host=host)
    print(f"  prompt_id={pid}, sampling...")
    result = wait_for(pid, host=host)
    images = result["outputs"].get("70", {}).get("images", [])
    if not images:
        raise RuntimeError(f"no images in result; full output: {json.dumps(result)[:500]}")
    img = images[0]
    out = Path("__comfy_temp.png")
    download_output(host, img["filename"], img["subfolder"], img["type"], out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--category", default="Rock")
    ap.add_argument("--unet", default="flux-2-klein-4b.safetensors")
    ap.add_argument("--clip", default="qwen_3_4b.safetensors")
    ap.add_argument("--vae", default="flux2-vae.safetensors")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=4,
                    help="distilled klein needs ~4; base klein wants ~20")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--host", default=COMFY_HOST)
    ap.add_argument("--no-pbr", action="store_true",
                    help="skip the deterministic PBR derivation pass")
    args = ap.parse_args()

    out_dir = LIBRARY / args.id
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = run_comfy(args.prompt, args.unet, args.clip, args.vae,
                     args.size, args.seed, args.steps, args.host)
    albedo_path = out_dir / f"{args.id}_albedo.png"
    Image.open(raw).save(albedo_path)
    raw.unlink(missing_ok=True)
    print(f"  saved albedo -> {albedo_path}")

    if not args.no_pbr:
        import subprocess
        import sys
        result = subprocess.run([
            sys.executable, str(Path(__file__).parent / "derive_pbr_v2.py"),
            "--albedo", str(albedo_path),
            "--id", args.id,
            "--category", args.category,
            "--out", str(out_dir),
        ])
        if result.returncode != 0:
            print("  warning: derive_pbr_v2 failed; albedo still saved")

    print(f"done: {out_dir}")


if __name__ == "__main__":
    main()
