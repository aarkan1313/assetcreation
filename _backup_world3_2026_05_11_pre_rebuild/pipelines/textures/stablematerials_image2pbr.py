"""StableMaterials image-to-PBR adapter (replaces ma_image2pbr).

StableMaterials (gvecchio/StableMaterials) is a diffusion model that takes a
*single* image (or text prompt) and outputs tileable PBR maps:
  - basecolor, normal, height, roughness, metallic

Unlike Material Anything (which requires multi-view 3D mesh consolidation),
StableMaterials is single-image-native. Designed for tileable textures.

License: OpenRAIL (commercial OK).
Repo:    https://huggingface.co/gvecchio/StableMaterials
Paper:   StableMaterials (Vecchio, semi-supervised LDM distilled from SDXL).

Two pipelines:
  - Standard: 50 steps, slower, higher quality
  - LCM:       4 steps, ~10x faster, slight quality loss

Designed to run in `animators/mesa-env/venv` (already has diffusers 0.38 +
cu130 torch).

Usage:
  D:/assets/animators/mesa-env/venv/Scripts/python.exe `
    pipelines/textures/stablematerials_image2pbr.py `
    --input world/textures/library/cobblestone_seamless/cobblestone_seamless_albedo.pre_delight.png `
    --out world/textures/library/cobblestone_aaa --id cobblestone_aaa --mode lcm
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ID = "gvecchio/StableMaterials"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path,
                    help="(required for image mode) input image path")
    ap.add_argument("--prompt", type=str,
                    help="(text mode) prompt")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--mode", choices=["standard", "lcm"], default="lcm",
                    help="standard = 50 steps high quality; lcm = 4 steps fast")
    ap.add_argument("--guidance", type=float, default=10.0)
    ap.add_argument("--steps", type=int, default=None,
                    help="override default step count")
    ap.add_argument("--tileable", action="store_true", default=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--size", type=int, default=512,
                    help="output resolution (StableMaterials trains at 512)")
    args = ap.parse_args()

    if not args.input and not args.prompt:
        ap.error("provide --input (image mode) or --prompt (text mode)")

    import torch
    from diffusers import DiffusionPipeline, LCMScheduler, UNet2DConditionModel
    from diffusers.utils import load_image
    from PIL import Image

    print(f"[stablematerials] mode={args.mode} loading pipeline...")
    if args.mode == "lcm":
        unet = UNet2DConditionModel.from_pretrained(
            REPO_ID, subfolder="unet_lcm", torch_dtype=torch.float16
        )
        pipe = DiffusionPipeline.from_pretrained(
            REPO_ID, trust_remote_code=True, unet=unet, torch_dtype=torch.float16
        )
        pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
        steps = args.steps or 4
    else:
        pipe = DiffusionPipeline.from_pretrained(
            REPO_ID, trust_remote_code=True, torch_dtype=torch.float16
        )
        steps = args.steps or 50

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipe = pipe.to(device)

    g = torch.Generator(device=device).manual_seed(args.seed)

    if args.input:
        print(f"[stablematerials] image mode: {args.input}")
        prompt_in = load_image(str(args.input))
    else:
        print(f"[stablematerials] text mode: {args.prompt!r}")
        prompt_in = args.prompt

    print(f"[stablematerials] generating PBR set ({steps} steps, "
          f"guidance={args.guidance}, tileable={args.tileable})...")
    material = pipe(
        prompt=prompt_in,
        guidance_scale=args.guidance,
        tileable=args.tileable,
        num_images_per_prompt=1,
        num_inference_steps=steps,
        generator=g,
    ).images[0]

    # Output is a MaterialResult with basecolor/normal/height/roughness/metallic
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    # Each map is a PIL image
    saves = {
        "albedo":    material.basecolor,
        "normal":    material.normal,
        "roughness": material.roughness,
        "metallic":  material.metallic,
        "height":    material.height,
    }

    for kind, img in saves.items():
        if img is None:
            continue
        # Resize to target if needed (StableMaterials base = 512)
        if args.size != img.size[0]:
            img = img.resize((args.size, args.size), Image.LANCZOS)
        path = out_dir / f"{args.id}_{kind}.png"
        img.save(path)
        print(f"  saved {kind:12s} -> {path.name}")

    # Also save an AO placeholder (StableMaterials doesn't emit AO; derive from height)
    if material.height is not None:
        try:
            import numpy as np
            from PIL import ImageFilter
            h = saves.get("height")
            if h:
                arr = np.asarray(h.convert("L"), dtype=np.float32)
                # Cheap AO: 1 - normalized concavity from gaussian-blur diff
                blurred = np.asarray(
                    h.convert("L").filter(ImageFilter.GaussianBlur(radius=8)),
                    dtype=np.float32
                )
                ao = np.clip(1.0 + (arr - blurred) / 128.0, 0, 1)
                ao_img = Image.fromarray((ao * 255).astype(np.uint8), mode="L")
                ao_img.save(out_dir / f"{args.id}_ao.png")
                print(f"  saved {'ao':12s} -> {args.id}_ao.png (derived from height)")
        except Exception as e:
            print(f"  ao derivation failed: {e}")

    print(f"\ndone -> {out_dir}")


if __name__ == "__main__":
    main()
