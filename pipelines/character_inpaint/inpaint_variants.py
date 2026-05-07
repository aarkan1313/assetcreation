"""inpaint_variants.py — Top-level CLI for the character inpaint pipeline (Architecture B).

Pipeline:
    GLB -> render N orbit views (Blender headless)
         -> inpaint each view (FLUX.1-Fill or dry-run)
         -> back-project inpainted views to UV atlas
         -> repack UV atlas as new albedo into output GLB

Usage:
    python inpaint_variants.py \\
        --glb <path> \\
        --reference <faction_emblem.png> \\
        --out <variant_output.glb> \\
        [--work-dir <path>]           # default: <out_glb_dir>/<stem>_work
        [--n-views 6] \\
        [--resolution 512] \\
        [--camera-distance 2.5] \\
        [--elevation-deg 15.0] \\
        [--inpaint-backend dry-run] \\
        [--project-backend dry-run] \\
        [--comfy-url http://127.0.0.1:8188] \\
        [--positive-prompt "..."] \\
        [--blender-exe blender] \\
        [--uv-size 1024]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Module imports (same directory)
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from render_views_runner import render_views
from comfy_inpaint import inpaint_view
from back_project import back_project
from glb_repack import repack_albedo


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def run_variant(
    glb_path: Path,
    reference_img: Path,            # faction emblem / brand image
    out_glb: Path,                  # where to write the variant GLB
    *,
    work_dir: Path,                 # scratch dir for intermediates (views, masks, albedo)
    n_views: int = 6,
    resolution: int = 512,
    camera_distance: float = 2.5,
    elevation_deg: float = 15.0,
    inpaint_backend: str = "dry-run",   # "dry-run" or "flux-fill"
    project_backend: str = "dry-run",   # "dry-run" or "nvdiffrast"
    comfy_url: str = "http://127.0.0.1:8188",
    positive_prompt: str = "faction emblem branded onto leather armor, seamlessly integrated",
    blender_exe: str = "blender",
    uv_size: int = 1024,
) -> Path:
    """Run the full inpaint variant pipeline end-to-end.

    Parameters
    ----------
    glb_path:
        Source GLB character mesh.
    reference_img:
        Faction emblem / brand reference image.
    out_glb:
        Destination path for the variant GLB.
    work_dir:
        Scratch directory for intermediates (views, masks, inpainted, albedo).
    n_views:
        Number of evenly-spaced orbit views to render.
    resolution:
        Square render resolution in pixels.
    camera_distance:
        Camera distance from origin (world units, post-normalization).
    elevation_deg:
        Camera elevation above the equatorial plane in degrees.
    inpaint_backend:
        "dry-run" (PIL composite) or "flux-fill" (ComfyUI FLUX.1-Fill).
    project_backend:
        "dry-run" (copy albedo) or "nvdiffrast" (GPU rasterization).
    comfy_url:
        ComfyUI server URL (flux-fill backend only).
    positive_prompt:
        Positive text conditioning (flux-fill backend only).
    blender_exe:
        Path to Blender executable.
    uv_size:
        Output UV atlas resolution (square, pixels).

    Returns
    -------
    Path
        The written output GLB path.
    """
    # --- Validate inputs ------------------------------------------------------
    if not glb_path.exists():
        raise FileNotFoundError(f"GLB not found: {glb_path}")
    if not reference_img.exists():
        raise FileNotFoundError(f"Reference image not found: {reference_img}")

    # --- Ensure work subdirectories exist -------------------------------------
    views_dir = work_dir / "views"
    masks_dir = work_dir / "masks"
    inpainted_dir = work_dir / "inpainted"
    for d in (views_dir, masks_dir, inpainted_dir):
        d.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Step 1/5: Render views
    # =========================================================================
    print(f"[inpaint_variants] Step 1/5: Rendering {n_views} views...")
    view_paths = render_views(
        glb_path=glb_path,
        out_dir=views_dir,
        n_views=n_views,
        resolution=resolution,
        camera_distance=camera_distance,
        elevation_deg=elevation_deg,
        blender_exe=blender_exe,
    )
    print(f"[inpaint_variants]   -> {len(view_paths)} views in {views_dir}")

    # =========================================================================
    # Step 2/5: Generate masks
    # =========================================================================
    print(f"[inpaint_variants] Step 2/5: Generating {n_views} circular masks...")
    mask_paths: list[Path] = []
    cx = resolution // 2
    cy = resolution * 2 // 3
    radius = resolution // 6

    for i in range(n_views):
        mask_img = Image.new("L", (resolution, resolution), 0)
        draw = ImageDraw.Draw(mask_img)
        draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            fill=255,
        )
        mask_path = masks_dir / f"mask_{i:02d}.png"
        mask_img.save(str(mask_path))
        mask_paths.append(mask_path)

    print(f"[inpaint_variants]   -> {len(mask_paths)} masks in {masks_dir}")

    # =========================================================================
    # Step 3/5: Inpaint views
    # =========================================================================
    print(f"[inpaint_variants] Step 3/5: Inpainting {n_views} views "
          f"(backend={inpaint_backend!r})...")
    reference_pil = Image.open(str(reference_img)).convert("RGBA")
    inpainted_paths: list[Path] = []

    for i, view_path in enumerate(view_paths):
        source_pil = Image.open(str(view_path)).convert("RGBA")
        mask_pil = Image.open(str(mask_paths[i]))

        inpainted = inpaint_view(
            source=source_pil,
            mask=mask_pil,
            reference=reference_pil,
            backend=inpaint_backend,
            comfy_url=comfy_url,
            positive_prompt=positive_prompt,
        )

        out_path = inpainted_dir / f"inpainted_{i:02d}.png"
        inpainted.save(str(out_path))
        inpainted_paths.append(out_path)
        print(f"[inpaint_variants]   view {i:02d} -> {out_path.name}")

    print(f"[inpaint_variants]   -> {len(inpainted_paths)} inpainted views in {inpainted_dir}")

    # =========================================================================
    # Step 4/5: Back-project to UV atlas
    # =========================================================================
    atlas_path = work_dir / "variant_albedo.png"
    print(f"[inpaint_variants] Step 4/5: Back-projecting to UV atlas "
          f"(backend={project_backend!r})...")
    atlas_path = back_project(
        glb_path=glb_path,
        inpainted_views=inpainted_paths,
        masks=mask_paths,
        out_path=atlas_path,
        n_views=n_views,
        camera_distance=camera_distance,
        elevation_deg=elevation_deg,
        resolution=resolution,
        uv_size=uv_size,
        backend=project_backend,
    )
    print(f"[inpaint_variants]   -> atlas: {atlas_path}")

    # =========================================================================
    # Step 5/5: Repack albedo into output GLB
    # =========================================================================
    print(f"[inpaint_variants] Step 5/5: Repacking albedo into output GLB...")
    out_path = repack_albedo(
        src_glb=glb_path,
        new_albedo=atlas_path,
        out_glb=out_glb,
    )
    print(f"[inpaint_variants]   -> {out_path}")

    print(f"[inpaint_variants] Done. Output: {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Character inpaint pipeline: GLB -> render -> inpaint -> back-project -> GLB",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--glb", required=True, help="Input GLB character mesh")
    p.add_argument("--reference", required=True, metavar="IMG",
                   help="Faction emblem / brand reference image (PNG/JPEG)")
    p.add_argument("--out", required=True, metavar="OUTPUT_GLB",
                   help="Output variant GLB path")
    p.add_argument(
        "--work-dir", metavar="DIR", default=None,
        help="Scratch directory for intermediates. "
             "Default: <out_dir>/<stem>_work",
    )
    p.add_argument("--n-views", type=int, default=6,
                   help="Number of orbit views to render")
    p.add_argument("--resolution", type=int, default=512,
                   help="Square render resolution in pixels")
    p.add_argument("--camera-distance", type=float, default=2.5,
                   help="Camera distance from origin (world units)")
    p.add_argument("--elevation-deg", type=float, default=15.0,
                   help="Camera elevation above equatorial plane (degrees)")
    p.add_argument(
        "--inpaint-backend", default="dry-run",
        choices=["dry-run", "flux-fill"],
        help="Inpaint backend: dry-run (PIL composite) or flux-fill (ComfyUI)",
    )
    p.add_argument(
        "--project-backend", default="dry-run",
        choices=["dry-run", "nvdiffrast"],
        help="Back-projection backend: dry-run or nvdiffrast (GPU)",
    )
    p.add_argument("--comfy-url", default="http://127.0.0.1:8188",
                   help="ComfyUI server URL (flux-fill backend only)")
    p.add_argument(
        "--positive-prompt",
        default="faction emblem branded onto leather armor, seamlessly integrated",
        help="Positive text conditioning (flux-fill backend only)",
    )
    p.add_argument("--blender-exe", default="blender",
                   help="Path to Blender executable")
    p.add_argument("--uv-size", type=int, default=1024,
                   help="UV atlas output resolution (square, pixels)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    glb_path = Path(args.glb).resolve()
    reference_img = Path(args.reference).resolve()
    out_glb = Path(args.out).resolve()

    # Resolve work_dir: default to <out_dir>/<stem>_work
    if args.work_dir is not None:
        work_dir = Path(args.work_dir).resolve()
    else:
        work_dir = out_glb.parent / f"{out_glb.stem}_work"

    try:
        run_variant(
            glb_path=glb_path,
            reference_img=reference_img,
            out_glb=out_glb,
            work_dir=work_dir,
            n_views=args.n_views,
            resolution=args.resolution,
            camera_distance=args.camera_distance,
            elevation_deg=args.elevation_deg,
            inpaint_backend=args.inpaint_backend,
            project_backend=args.project_backend,
            comfy_url=args.comfy_url,
            positive_prompt=args.positive_prompt,
            blender_exe=args.blender_exe,
            uv_size=args.uv_size,
        )
        return 0
    except FileNotFoundError as exc:
        print(f"[inpaint_variants] ERROR: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"[inpaint_variants] ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[inpaint_variants] UNEXPECTED ERROR: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
