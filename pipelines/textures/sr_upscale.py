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


def main():
    raise SystemExit("not implemented yet — see Task 4")


if __name__ == "__main__":
    main()
