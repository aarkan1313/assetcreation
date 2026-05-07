"""Standalone image-to-PBR via Material Anything's MVDiffusionAlbedoPipeline.

Real PBR estimation (replaces heuristic derive_pbr_v2 for high-quality work).
Takes a flat albedo image and produces:
  - albedo (delit)
  - rm (roughness in R, metallic in G channel)
  - bump (height/normal source)

Uses Material Anything's `material_estimator` checkpoint (already downloaded
to D:/assets/animators/MaterialAnything/pretrained_models/material_estimator).

Must be invoked from the materialanything WSL conda env:
  wsl -d Ubuntu-24.04 -- bash -c "source /opt/miniconda3/etc/profile.d/conda.sh && \
      conda activate materialanything && python /mnt/d/assets/pipelines/textures/ma_image2pbr.py \
      --input <albedo.png> --out <dir>"

Or use the wrapper script ma_image2pbr_wrapper.ps1 from PowerShell which
handles the WSL bridge.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Make MA libs importable
MA_REPO = "/mnt/d/assets/animators/MaterialAnything"
if MA_REPO not in sys.path:
    sys.path.insert(0, MA_REPO)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="albedo image (RGB)")
    ap.add_argument("--out", required=True, help="output directory for PBR maps")
    ap.add_argument("--id", required=True)
    ap.add_argument("--size", type=int, default=768,
                    help="MA's training res; outputs will be resized to match input")
    ap.add_argument("--prompt", default="",
                    help="optional context for material estimation")
    ap.add_argument("--model", default="/mnt/d/assets/animators/MaterialAnything/pretrained_models/material_estimator")
    args = ap.parse_args()

    import torch
    from PIL import Image
    import numpy as np

    os.chdir(MA_REPO)  # MA does relative imports from its repo root

    # Now we can import from MA's lib
    from lib.diffusion_helper import get_image2materials, apply_material_estimation

    device = torch.device("cuda:0")
    torch.cuda.set_device(device)

    print(f"[MA-i2p] loading material_estimator from {args.model}")
    model = get_image2materials(args.model, device)

    # Load the input albedo
    in_path = Path(args.input)
    src = Image.open(in_path).convert("RGB")
    src_size = src.size
    print(f"[MA-i2p] input {in_path.name} ({src_size[0]}x{src_size[1]})")

    # MA's pipeline wants a square image at its training res
    img_for_ma = src.resize((args.size, args.size), Image.LANCZOS)

    # Build neutral "normal" (light blue) and zero init_materials/masks for flat texture
    # The pipeline iterates `for img in mask` and `for img in init_materials` and
    # expects each entry to be a 2D HxW numpy array (mask) or PIL Image (materials).
    neutral_normal = Image.new("RGB", (args.size, args.size), (128, 128, 255))
    # init_materials: dict with keys 'albedo', 'roughness_metallic', 'bump',
    # each a (B, H, W, 3) tensor of values in 0..1. Use neutral grey as the
    # init guess so the model has free reign to estimate.
    neutral = torch.full((1, args.size, args.size, 3), 0.5,
                          device=device, dtype=torch.float16)
    init_materials = {
        "albedo": neutral.clone(),
        "roughness_metallic": neutral.clone(),
        "bump": neutral.clone(),
    }
    # masks: list of torch tensors (HxW). Use 1.0 (fully visible = "estimate
    # everything; nothing is pre-known"). The pipeline calls .cpu().numpy()
    # on each entry, so they must be tensors not numpy arrays.
    masks = [torch.ones((args.size, args.size), device=device, dtype=torch.float16)]

    print(f"[MA-i2p] running 50-step estimation...")
    albedo, rm, bump = apply_material_estimation(
        model, args.prompt, img_for_ma, neutral_normal,
        init_materials, masks,
        args.size, args.size, device,
    )

    # Resize back to source resolution
    albedo = albedo.resize(src_size, Image.LANCZOS)
    rm = rm.resize(src_size, Image.LANCZOS)
    bump = bump.resize(src_size, Image.LANCZOS)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    albedo_path = out_dir / f"{args.id}_albedo.png"
    rm_path = out_dir / f"{args.id}_rm.png"
    bump_path = out_dir / f"{args.id}_bump.png"
    albedo.save(albedo_path)
    rm.save(rm_path)
    bump.save(bump_path)

    # Decompose RM into separate roughness and metallic
    rm_arr = np.asarray(rm)
    Image.fromarray(rm_arr[..., 0], mode="L").save(out_dir / f"{args.id}_roughness.png")
    Image.fromarray(rm_arr[..., 1], mode="L").save(out_dir / f"{args.id}_metallic.png")

    # Convert bump map -> normal map (Sobel from bump grayscale)
    bump_l = np.asarray(bump.convert("L"), dtype=np.float32)
    pad = np.pad(bump_l, 1, mode="edge")
    gx = (pad[1:-1, 2:] - pad[1:-1, :-2]) * 0.02
    gy = (pad[2:, 1:-1] - pad[:-2, 1:-1]) * 0.02
    nx = -gx; ny = -gy; nz = np.ones_like(gx)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx /= n; ny /= n; nz /= n
    rgb = np.stack([
        ((nx * 0.5 + 0.5) * 255).clip(0, 255),
        ((ny * 0.5 + 0.5) * 255).clip(0, 255),
        ((nz * 0.5 + 0.5) * 255).clip(0, 255),
    ], axis=-1).astype(np.uint8)
    Image.fromarray(rgb, mode="RGB").save(out_dir / f"{args.id}_normal.png")

    # Save bump as height too (high-frequency component)
    Image.fromarray(bump_l.astype(np.uint8), mode="L").save(out_dir / f"{args.id}_height.png")

    print(f"[MA-i2p] done -> {out_dir}")
    print(f"  6 maps: albedo, rm (combined), roughness, metallic, normal, height, bump")


if __name__ == "__main__":
    main()
