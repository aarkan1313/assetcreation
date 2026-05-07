"""Real-ESRGAN single-map super-resolution for tileable textures.

Drop-in 4x upscaler using ComfyUI's UpscaleModelLoader +
ImageUpscaleWithModel nodes. Tile preservation via offset+heal trick
(see flux_seamless.py / flux_upscale.py for the established pattern).

Usage:
  python sr_upscale.py --in albedo.png --out albedo_4k.png

  # Disable the offset trick (faster, may break tile seams):
  python sr_upscale.py --in albedo.png --out albedo_4k.png --no-offset-trick

  # Use a different upscale model:
  python sr_upscale.py --in albedo.png --out out.png \\
      --model realesr-general-x4v3.pth

Phase B.1 deliverable. See:
  docs/superpowers/specs/2026-05-07-phase-b-multi-resolution-pipeline-design.md
  pipelines/textures/EXTERNAL_SR_TECHNIQUES.md
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
from PIL import Image

from flux_seamless import (
    queue_prompt, wait_for, download_output, upload_image,
    offset_image, edge_seam_score,
    COMFY_HOST,
)


def workflow_upscale_with_model(input_image_name: str, model_name: str,
                                 prefix: str = "sr_upscale") -> dict:
    """ComfyUI workflow: load image → load upscale model → upscale → save.

    Mirrors the structure of workflow_img2img_klein in flux_seamless.py
    but with no diffusion — just deterministic SR via the upscale model.

    Returns a workflow dict suitable for queue_prompt().
    """
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": input_image_name},
        },
        "2": {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": model_name},
        },
        "3": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {
                "upscale_model": ["2", 0],
                "image": ["1", 0],
            },
        },
        "70": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["3", 0],
                "filename_prefix": prefix,
            },
        },
    }


def upscale_one(input_path: Path, output_path: Path, model_name: str,
                 use_offset_trick: bool = True,
                 host: str = COMFY_HOST) -> dict:
    """SR a single tileable image. Returns a metrics dict.

    use_offset_trick=True: shift→SR→reverse-shift to keep outer edges
    tileable. Adds one round-trip but is the safe default.

    use_offset_trick=False: SR raw. Faster, may break tile seams at
    the outer edge. Use only if you don't care about tileability.
    """
    src = Image.open(input_path).convert("RGB")
    src_arr = np.asarray(src)
    pre_score = edge_seam_score(src_arr)
    print(f"  input  {src.size[0]}x{src.size[1]}  edge_seam_score={pre_score:.5f}")

    # Stage the (optionally offset) image into ComfyUI's input dir
    if use_offset_trick:
        staged_arr = offset_image(src_arr)
        print(f"  offset trick on (shift to interior)")
    else:
        staged_arr = src_arr
        print(f"  offset trick OFF (raw SR)")

    tmp = Path("__sr_staged.png")
    Image.fromarray(staged_arr).save(tmp)

    server_name = upload_image(tmp, host=host)
    wf = workflow_upscale_with_model(server_name, model_name,
                                      prefix=f"sr_{input_path.stem}")
    print(f"  queued upscale: model={model_name}")
    t0 = time.time()
    pid = queue_prompt(wf, host=host)
    res = wait_for(pid, host=host, timeout=600)
    elapsed = time.time() - t0
    print(f"  upscale done in {elapsed:.1f}s")

    images = res["outputs"].get("70", {}).get("images", [])
    if not images:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("no images returned from SR workflow")

    sr_tmp = Path("__sr_result.png")
    download_output(host, images[0]["filename"], images[0]["subfolder"],
                    images[0]["type"], sr_tmp)
    sr_arr = np.asarray(Image.open(sr_tmp).convert("RGB"))

    if use_offset_trick:
        # Reverse the offset to put the original outer edges back on the outside
        final_arr = offset_image(sr_arr)
    else:
        final_arr = sr_arr

    post_score = edge_seam_score(final_arr)
    final_im = Image.fromarray(final_arr)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_im.save(output_path)
    print(f"  output {final_im.size[0]}x{final_im.size[1]}  edge_seam_score={post_score:.5f}")

    # Clean up temp files (best-effort; Windows may hold file handles briefly)
    for p in (tmp, sr_tmp):
        try:
            p.unlink(missing_ok=True)
        except PermissionError:
            pass

    return {
        "input": str(input_path),
        "output": str(output_path),
        "model": model_name,
        "use_offset_trick": use_offset_trick,
        "input_size": list(src.size),
        "output_size": list(final_im.size),
        "scale": final_im.size[0] / src.size[0],
        "edge_seam_score_pre": float(pre_score),
        "edge_seam_score_post": float(post_score),
        "elapsed_sec": round(elapsed, 2),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="input", type=Path, required=True,
                    help="input PNG (any single-map texture)")
    ap.add_argument("--out", dest="output", type=Path, required=True,
                    help="output PNG path")
    ap.add_argument("--model", default="RealESRGAN_x4plus.pth",
                    help="upscale model file in ComfyUI/models/upscale_models/")
    ap.add_argument("--no-offset-trick", action="store_true",
                    help="disable the offset+heal trick (faster, may break tile seams)")
    ap.add_argument("--host", default=COMFY_HOST,
                    help="ComfyUI host URL")
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")

    info = upscale_one(args.input, args.output, args.model,
                       use_offset_trick=not args.no_offset_trick,
                       host=args.host)
    print(f"\ndone -> {args.output}")
    print(f"  scale: {info['scale']:.2f}x")
    print(f"  seam: {info['edge_seam_score_pre']:.5f} -> {info['edge_seam_score_post']:.5f}")


if __name__ == "__main__":
    main()
