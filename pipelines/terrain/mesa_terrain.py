"""MESA AI terrain generator (working version).

MESA = Stable Diffusion 2.1 fine-tuned to produce paired (optical, DEM) images
from text prompts. Uses the official MESA repo (PaulBorneP/MESA) for the
custom UNet + pipeline classes.

  Model:   https://huggingface.co/NewtNewt/MESA  (~5 GB)
  Code:    https://github.com/PaulBorneP/MESA  (cloned to animators/mesa-repo)
  Paper:   https://huggingface.co/papers/2504.07210

License: Adobe model license (research / non-commercial). Don't ship MESA
output in a commercial product without checking terms.

Outputs both:
  - The generated optical image (Sentinel-2 style)
  - A real DEM heightmap (the killer feature — actual elevation, not derived)

Usage:
  python mesa_terrain.py --prompt "Sentinel-2 image of montane forests and mountains in Mexico in August" --id mesa_a
  python mesa_terrain.py --prompt "alpine valley with snow" --id mesa_alpine --steps 50
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

# Make the cloned MESA repo importable
MESA_REPO = Path(r"D:\assets\animators\mesa-repo")
if str(MESA_REPO.parent) not in sys.path:
    sys.path.insert(0, str(MESA_REPO.parent))

# Make terrain_bundle importable
sys.path.insert(0, str(Path(__file__).parent))

MODEL_ID = "NewtNewt/MESA"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--guidance", type=float, default=7.5)
    ap.add_argument("--upscale", type=int, default=1024, help="resample to this for the bundle (DEM is 256x256 native)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--erosion-mode", choices=["thermal", "hydraulic", "none"], default="none")
    ap.add_argument("--erosion", type=int, default=0)
    args = ap.parse_args()

    try:
        import torch
    except ImportError:
        raise SystemExit("torch not installed in this env; use animators/mesa-env/venv/Scripts/python.exe")

    # Import from cloned mesa-repo. Renamed dir 'mesa-repo' isn't a valid module
    # name (hyphen) so we add the parent dir to sys.path and rename for import.
    repo_dir = MESA_REPO
    # The notebook imports `MESA.pipeline_terrain` and `MESA.models`. Our clone is
    # in `mesa-repo`, so we make a tiny shim: copy the two .py files alongside.
    pipeline_path = Path(__file__).parent / "_mesa_pipeline.py"
    models_path = Path(__file__).parent / "_mesa_models.py"
    if not pipeline_path.exists():
        pipeline_path.write_bytes((repo_dir / "pipeline_terrain.py").read_bytes())
    if not models_path.exists():
        models_path.write_bytes((repo_dir / "models.py").read_bytes())

    # The pipeline imports `from .models import ...` style. We rewrote to flat
    # imports by reading the file. Easier: just exec the contents in our context
    # — but that's brittle. Better: use the original repo as a top-level package.
    # Hack: create an `__init__.py` so `mesa-repo` becomes a package, but the dash
    # makes it a problem. Alternative: directly add the repo dir as a sys.path
    # entry and import the submodules flat.
    sys.path.insert(0, str(repo_dir))
    import importlib
    # Force re-import in case anything was cached
    for mod in ["pipeline_terrain", "models"]:
        if mod in sys.modules:
            del sys.modules[mod]
    # The pipeline uses `from MESA.models import ...` — not flat. We need to
    # provide a module alias. Easiest: register modules manually.
    import importlib.util

    spec_models = importlib.util.spec_from_file_location("models", repo_dir / "models.py")
    mod_models = importlib.util.module_from_spec(spec_models)
    sys.modules["models"] = mod_models
    spec_models.loader.exec_module(mod_models)
    # Also alias as MESA.models in case the pipeline uses that path
    import types
    mesa_pkg = types.ModuleType("MESA")
    mesa_pkg.models = mod_models
    sys.modules["MESA"] = mesa_pkg
    sys.modules["MESA.models"] = mod_models

    spec_pipe = importlib.util.spec_from_file_location("pipeline_terrain", repo_dir / "pipeline_terrain.py")
    mod_pipe = importlib.util.module_from_spec(spec_pipe)
    sys.modules["pipeline_terrain"] = mod_pipe
    sys.modules["MESA.pipeline_terrain"] = mod_pipe
    spec_pipe.loader.exec_module(mod_pipe)

    TerrainDiffusionPipeline = mod_pipe.TerrainDiffusionPipeline

    # The diffusers loader resolves `models.UNetDEMConditionModel` by first
    # looking inside the repo for a `models.py`, and only then in sys.modules.
    # Easiest fix: download the weights to a local dir FIRST, then drop a
    # symlink/copy of models.py inside the unet subdir, then load from there.
    weights_dir = Path(r"D:\assets\animators\mesa-repo\weights")
    weights_dir.mkdir(parents=True, exist_ok=True)
    if not (weights_dir / "model_index.json").exists():
        print(f"[mesa] downloading weights to {weights_dir}...")
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=MODEL_ID, local_dir=str(weights_dir))
    # Place models.py next to the model_index so diffusers can find UNetDEMConditionModel
    repo_models = repo_dir / "models.py"
    weights_models = weights_dir / "models.py"
    if not weights_models.exists():
        import shutil
        shutil.copy2(repo_models, weights_models)
    # Also place inside unet/ since model_index says "unet": ["models", "UNetDEMConditionModel"]
    unet_models = weights_dir / "unet" / "models.py"
    if not unet_models.exists():
        import shutil
        unet_models.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo_models, unet_models)

    print(f"[mesa] loading from {weights_dir}...")
    pipe = TerrainDiffusionPipeline.from_pretrained(
        str(weights_dir),
        torch_dtype=torch.float16,
        trust_remote_code=True,
    )
    pipe = pipe.to(args.device)

    g = torch.Generator(device=args.device).manual_seed(args.seed)
    print(f"[mesa] sampling: prompt={args.prompt!r} steps={args.steps}")
    image, dem = pipe(
        args.prompt,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        generator=g,
    )

    out_dir = Path(__file__).parent / "output" / args.id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "godot").mkdir(parents=True, exist_ok=True)

    # Save optical preview (image is typically a numpy array or list of arrays)
    img_to_save = image[0] if isinstance(image, list) else image
    if hasattr(img_to_save, "save"):
        img_to_save.save(out_dir / "mesa_optical.png")
    else:
        arr = np.asarray(img_to_save)
        # Strip batch dim if present
        while arr.ndim > 3 and arr.shape[0] == 1:
            arr = arr[0]
        if arr.dtype != np.uint8:
            arr = (arr * 255).clip(0, 255).astype(np.uint8)
        if arr.ndim == 3 and arr.shape[0] in (3, 4):  # CHW -> HWC
            arr = arr.transpose(1, 2, 0)
        Image.fromarray(arr).save(out_dir / "mesa_optical.png")
    print(f"  saved optical -> mesa_optical.png")

    # DEM is the actual heightmap from the model
    if isinstance(dem, list):
        dem = dem[0]
    dem_arr = np.asarray(dem)
    # Strip batch dim if present
    while dem_arr.ndim > 2 and dem_arr.shape[0] == 1:
        dem_arr = dem_arr[0]
    # If 3-channel (RGB), squeeze to first channel — MESA returns the same value
    # in all 3 since DEM is single-channel
    if dem_arr.ndim == 3 and dem_arr.shape[-1] in (3, 4):
        dem_arr = dem_arr[..., 0]
    elif dem_arr.ndim == 3 and dem_arr.shape[0] in (3, 4):
        dem_arr = dem_arr[0]
    dem_arr = dem_arr.astype(np.float32)
    # Normalize to 0..1
    dem_arr = (dem_arr - dem_arr.min()) / (dem_arr.max() - dem_arr.min() + 1e-9)

    # Save raw DEM at native res
    Image.fromarray((dem_arr * 65535).astype(np.uint16), mode="I;16").save(out_dir / "mesa_dem_raw.png")
    print(f"  saved raw DEM -> mesa_dem_raw.png ({dem_arr.shape})")

    # Upscale to bundle target
    if args.upscale and dem_arr.shape[0] != args.upscale:
        h_im = Image.fromarray((dem_arr * 65535).astype(np.uint16), mode="I;16")
        h_im = h_im.resize((args.upscale, args.upscale), Image.LANCZOS)
        h = np.asarray(h_im, dtype=np.float32) / 65535.0
    else:
        h = dem_arr

    from terrain_bundle import (
        slope_from_height, flow_accumulation_d8, derive_biome, splat_rgba,
        vegetation_density, water_mask, hillshade, hypsometric_preview,
        normal_from_height, to_png_16bit, GODOT_TERRAIN3D_HINT,
        heightmapshape3d_tres, hydraulic_erode_landlab, thermal_erode,
    )

    if args.erosion_mode == "hydraulic":
        h = hydraulic_erode_landlab(h, n_steps=args.erosion or 80)
    elif args.erosion_mode == "thermal":
        h = thermal_erode(h, iterations=args.erosion or 30)

    slope = slope_from_height(h)
    flow = flow_accumulation_d8(h, iterations=20)
    biome_rgb, labels = derive_biome(h, slope)
    splat = splat_rgba(labels)
    veg = vegetation_density(labels, slope, h)
    water = water_mask(h)

    to_png_16bit(h, out_dir / "height_16.png")
    normal_from_height(h).save(out_dir / "normal.png")
    Image.fromarray(splat, mode="RGBA").save(out_dir / "splat_rgba.png")
    Image.fromarray(biome_rgb, mode="RGB").save(out_dir / "biome.png")
    Image.fromarray(veg, mode="L").save(out_dir / "vegetation_density.png")
    Image.fromarray(water, mode="L").save(out_dir / "water_mask.png")
    Image.fromarray((flow * 255).astype(np.uint8), mode="L").save(out_dir / "flow.png")
    hypsometric_preview(h).save(out_dir / "preview_hypsometric.png")
    Image.fromarray(hillshade(h), mode="L").save(out_dir / "preview_hillshade.png")
    (out_dir / "godot" / "terrain3d_import.json").write_text(GODOT_TERRAIN3D_HINT, encoding="utf-8")
    (out_dir / "godot" / "heightmapshape3d.tres").write_text(
        heightmapshape3d_tres("../height_16.png"), encoding="utf-8"
    )
    (out_dir / "terrain.json").write_text(json.dumps({
        "id": args.id, "created": datetime.now(timezone.utc).isoformat(),
        "source": "mesa", "prompt": args.prompt,
        "model": MODEL_ID, "license": "Adobe research; non-commercial",
        "size": args.upscale or dem_arr.shape[0], "seed": args.seed,
        "steps": args.steps, "guidance": args.guidance,
        "erosion_mode": args.erosion_mode, "erosion": args.erosion,
        "raw_optical": "mesa_optical.png",
        "raw_dem": "mesa_dem_raw.png",
        "notes": "DEM is the actual model output (5th channel UNet head), not derived.",
    }, indent=2), encoding="utf-8")
    print(f"done: {out_dir}")


if __name__ == "__main__":
    main()
