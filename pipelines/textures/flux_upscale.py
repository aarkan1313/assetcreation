"""FLUX img2img heal-pass tool for tileable textures.

REPOSITIONED IN PHASE B.1 (2026-05-07): no longer the primary
super-resolution tool. Real-ESRGAN via sr_upscale.py is now the
default SR backend; this tool is the "heal pass" that polishes a
near-shipping image at the same (or higher) resolution to recover
FLUX-style coherence after generation or after Real-ESRGAN SR.

Two-stage approach (preserves tiling):
  1. Bilinear upscale to 2x (1024 -> 2048)
  2. FLUX img2img low-denoise refinement (recovers detail without altering structure)
  3. Repeat for 4K

We use the same offset trick to keep tiling intact through the upscale: shift
the 2x'd image, denoise, shift back.

Albedo-only. Other PBR maps are handled by the bake step in B.2
(re-derived from upscaled height + albedo).

For most game uses 2K is plenty. 4K is for hero materials.

Usage:
  python flux_upscale.py --material world/textures/library/cobblestone_aaa --target 2048
  python flux_upscale.py --input some_albedo.png --output upscaled.png --target 4096

See also:
  pipelines/textures/sr_upscale.py — primary SR (Real-ESRGAN)
  pipelines/textures/EXTERNAL_SR_TECHNIQUES.md — survey + decision rationale
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

from flux_seamless import (
    queue_prompt, wait_for, download_output, upload_image,
    workflow_img2img_klein, offset_image, edge_seam_score, TILE_PROMPT_SUFFIX,
    COMFY_HOST,
)


def upscale_with_heal(input_path: Path, target_size: int, prompt: str,
                       unet: str, clip: str, vae: str, seed: int,
                       denoise: float = 0.18, steps: int = 8,
                       host: str = COMFY_HOST) -> Path:
    """Single 2x upscale step: bilinear → upload → low-denoise FLUX → return.

    For seamless preservation we offset → heal → reverse-offset.
    """
    src = Image.open(input_path).convert("RGB")
    src_size = src.size[0]
    if src_size >= target_size:
        print(f"  source already {src_size} >= target {target_size}, copying")
        return input_path

    print(f"  upscale {src_size} -> {target_size}")
    upscaled = src.resize((target_size, target_size), Image.LANCZOS)

    # Offset so seams move to center; heal pass denoises whole image lightly
    arr = np.asarray(upscaled)
    shifted = offset_image(arr)
    shifted_im = Image.fromarray(shifted)
    tmp = Path("__upscale_shifted.png")
    shifted_im.save(tmp)

    full_prompt = prompt + TILE_PROMPT_SUFFIX
    server_name = upload_image(tmp, host=host)

    print(f"  img2img heal at {target_size}x{target_size} denoise={denoise}")
    wf = workflow_img2img_klein(full_prompt, server_name, unet, clip, vae,
                                  target_size, seed, denoise=denoise,
                                  steps=steps, prefix=f"upscale_{target_size}")
    pid = queue_prompt(wf, host=host)
    res = wait_for(pid, host=host)
    images = res["outputs"].get("70", {}).get("images", [])
    if not images:
        raise RuntimeError("no images from upscale heal")
    healed = Path("__upscale_healed.png")
    download_output(host, images[0]["filename"], images[0]["subfolder"], images[0]["type"], healed)

    healed_arr = np.asarray(Image.open(healed).convert("RGB"))
    final = offset_image(healed_arr)
    final_score = edge_seam_score(final)
    print(f"  post-upscale seam score: {final_score:.5f}")

    out = input_path.parent / f"{input_path.stem}_{target_size}.png"
    Image.fromarray(final).save(out)
    tmp.unlink(missing_ok=True)
    healed.unlink(missing_ok=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, help="single albedo file")
    ap.add_argument("--output", type=Path, help="output for --input mode")
    ap.add_argument("--material", type=Path, help="material dir; will upscale ONLY albedo (other maps stay derived)")
    ap.add_argument("--target", type=int, default=2048,
                    help="target resolution; valid: 2048 or 4096")
    ap.add_argument("--prompt", default="seamless tileable photorealistic texture",
                    help="prompt for the heal pass (low denoise, just steers detail)")
    ap.add_argument("--unet", default="flux-2-klein-4b.safetensors")
    ap.add_argument("--clip", default="qwen_3_4b.safetensors")
    ap.add_argument("--vae", default="flux2-vae.safetensors")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--denoise", type=float, default=0.18)
    ap.add_argument("--host", default=COMFY_HOST)
    args = ap.parse_args()

    if args.material:
        # Upscale the albedo and keep it in place (back up first)
        manifest_albedo = list(args.material.glob("*_albedo.png"))
        if not manifest_albedo:
            raise SystemExit(f"no albedo in {args.material}")
        # Skip pre_delight backups
        manifest_albedo = [p for p in manifest_albedo if "pre_" not in p.name]
        albedo = manifest_albedo[0]
        backup = albedo.with_suffix(".pre_upscale.png")
        if not backup.exists():
            shutil.copy2(albedo, backup)

        # Step to 2K first
        cur = albedo
        for target in [2048, 4096]:
            if target > args.target:
                break
            cur = upscale_with_heal(cur, target, args.prompt, args.unet, args.clip,
                                     args.vae, args.seed, args.denoise, host=args.host)

        # Replace canonical albedo with the highest-res result
        shutil.copy2(cur, albedo)
        print(f"\ndone. Upscaled albedo at {albedo}, backup at {backup.name}")
    else:
        if not args.input or not args.output:
            ap.error("provide --material OR (--input AND --output)")
        cur = args.input
        for target in [2048, 4096]:
            if target > args.target:
                break
            cur = upscale_with_heal(cur, target, args.prompt, args.unet, args.clip,
                                     args.vae, args.seed, args.denoise, host=args.host)
        shutil.copy2(cur, args.output)
        print(f"\ndone -> {args.output}")


if __name__ == "__main__":
    main()
