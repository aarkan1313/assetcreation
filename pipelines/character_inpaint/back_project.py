"""back_project.py -- UV back-projection module for the character inpaint pipeline.

Architecture B (camera-projection inpaint): takes N inpainted view PNGs and their
masks, back-projects the inpainted pixels to UV space, and fuses them into a single
variant_albedo.png atlas.

Public API:
    back_project(glb_path, inpainted_views, masks, out_path, n_views, ...) -> Path
    extract_albedo_from_glb(glb_path) -> PIL.Image | None

CLI:
    python back_project.py --glb <path> --views <...> --masks <...> --out <path>
                           --n-views <N> --backend dry-run|nvdiffrast
"""
from __future__ import annotations

import argparse
import io
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# pygltflib: required for GLB geometry / texture extraction.  Install if missing.
# ---------------------------------------------------------------------------
try:
    import pygltflib
except ModuleNotFoundError:
    import subprocess as _sp
    _venv_pip = Path(__file__).parent / ".venv" / "Scripts" / "pip"
    print("[back_project] pygltflib not found -- installing...")
    _sp.check_call([str(_venv_pip), "install", "pygltflib"])
    import pygltflib  # noqa: F811


# ---------------------------------------------------------------------------
# Helpers: GLB geometry / texture extraction
# ---------------------------------------------------------------------------

def _get_buffer_view_bytes(glb: "pygltflib.GLTF2", bv_idx: int) -> bytes:
    """Return the raw bytes of a bufferView from the GLB binary blob.

    pygltflib 1.16.x does not expose get_data_from_buffer_view; we read
    directly from glb._glb_data which holds the GLB binary payload.
    """
    bv = glb.bufferViews[bv_idx]
    offset = bv.byteOffset or 0
    return glb._glb_data[offset: offset + bv.byteLength]


def _accessor_to_numpy(glb: "pygltflib.GLTF2", accessor_idx: int) -> np.ndarray:
    """Read a GLTF accessor and return a numpy array."""
    acc = glb.accessors[accessor_idx]

    # GLTF componentType codes -> numpy dtype
    _COMP = {
        5120: np.int8,
        5121: np.uint8,
        5122: np.int16,
        5123: np.uint16,
        5125: np.uint32,
        5126: np.float32,
    }
    dtype = _COMP[acc.componentType]
    # GLTF type codes -> element dimensions
    _DIMS = {
        "SCALAR": 1,
        "VEC2": 2,
        "VEC3": 3,
        "VEC4": 4,
        "MAT2": 4,
        "MAT3": 9,
        "MAT4": 16,
    }
    dim = _DIMS[acc.type]

    bv = glb.bufferViews[acc.bufferView]
    data = _get_buffer_view_bytes(glb, acc.bufferView)
    byte_offset = acc.byteOffset or 0
    stride = bv.byteStride  # None means tightly packed
    element_bytes = int(np.dtype(dtype).itemsize) * dim
    if stride is None or stride == 0 or stride == element_bytes:
        arr = np.frombuffer(data, dtype=dtype, count=acc.count * dim, offset=byte_offset)
    else:
        # Interleaved buffer: step through data using byteStride
        arr = np.stack([
            np.frombuffer(data, dtype=dtype, count=dim,
                          offset=byte_offset + i * stride)
            for i in range(acc.count)
        ])
    if dim > 1:
        arr = arr.reshape(acc.count, dim)
    return arr


def extract_albedo_from_glb(glb_path: Path) -> Optional[Image.Image]:
    """Extract the base-color texture from the first mesh primitive.

    Returns None if any step fails (no material, no texture, no bufferView, etc.).
    """
    try:
        glb = pygltflib.GLTF2().load(str(glb_path))
        prim = glb.meshes[0].primitives[0]
        if prim.material is None:
            return None
        mat = glb.materials[prim.material]
        pbr = mat.pbrMetallicRoughness
        if pbr is None or pbr.baseColorTexture is None:
            return None
        tex_idx = pbr.baseColorTexture.index
        tex = glb.textures[tex_idx]
        if tex.source is None:
            return None
        img_info = glb.images[tex.source]
        if img_info.bufferView is None:
            return None
        raw = _get_buffer_view_bytes(glb, img_info.bufferView)
        return Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Camera / MVP math (numpy only)
# ---------------------------------------------------------------------------

def _lookat(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    """Build a 4x4 view matrix (camera looks from eye toward target)."""
    f = target - eye
    f = f / np.linalg.norm(f)
    r = np.cross(f, up)
    r = r / np.linalg.norm(r)
    u = np.cross(r, f)

    M = np.eye(4, dtype=np.float32)
    M[0, :3] = r
    M[1, :3] = u
    M[2, :3] = -f
    M[0, 3] = -np.dot(r, eye)
    M[1, 3] = -np.dot(u, eye)
    M[2, 3] = np.dot(f, eye)
    return M


def _perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    """Build a 4x4 OpenGL-style perspective projection matrix."""
    f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
    P = np.zeros((4, 4), dtype=np.float32)
    P[0, 0] = f / aspect
    P[1, 1] = f
    P[2, 2] = (far + near) / (near - far)
    P[2, 3] = (2 * far * near) / (near - far)
    P[3, 2] = -1.0
    return P


def _camera_position(azimuth_deg: float, elevation_deg: float, distance: float) -> np.ndarray:
    """Spherical -> cartesian, matching render_views.py convention."""
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    x = distance * math.cos(el) * math.cos(az)
    y = distance * math.cos(el) * math.sin(az)
    z = distance * math.sin(el)
    return np.array([x, y, z], dtype=np.float32)


def _build_mvp(
    azimuth_deg: float,
    elevation_deg: float,
    distance: float,
    fov_deg: float = 45.0,
    near: float = 0.1,
    far: float = 10.0,
) -> np.ndarray:
    """Build the 4x4 MVP matrix for one orbit view."""
    eye = _camera_position(azimuth_deg, elevation_deg, distance)
    target = np.zeros(3, dtype=np.float32)
    # Up vector: Z-up (matching Blender / render_views.py convention)
    up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    V = _lookat(eye, target, up)
    P = _perspective(fov_deg, aspect=1.0, near=near, far=far)
    # Model is identity (mesh already normalized)
    return (P @ V).astype(np.float32)


# ---------------------------------------------------------------------------
# Geometry loading + normalization
# ---------------------------------------------------------------------------

def _load_geometry(glb_path: Path):
    """Load vertex positions, UV coords, and triangle faces from the first primitive.

    Returns (positions, uv_coords, faces) as float32/int32 numpy arrays:
      positions  (V, 3)
      uv_coords  (V, 2)
      faces      (F, 3) int32
    """
    glb = pygltflib.GLTF2().load(str(glb_path))
    prim = glb.meshes[0].primitives[0]

    for attr_name, accessor_idx in [
        ("POSITION", prim.attributes.POSITION),
        ("TEXCOORD_0", prim.attributes.TEXCOORD_0),
        ("indices", prim.indices),
    ]:
        if accessor_idx is None:
            raise ValueError(
                f"GLB mesh primitive is missing required attribute '{attr_name}': {glb_path}"
            )

    positions = _accessor_to_numpy(glb, prim.attributes.POSITION).astype(np.float32)
    uv_coords = _accessor_to_numpy(glb, prim.attributes.TEXCOORD_0).astype(np.float32)

    raw_faces = _accessor_to_numpy(glb, prim.indices)
    faces = raw_faces.reshape(-1, 3).astype(np.int32)

    return positions, uv_coords, faces


def _normalize_geometry(positions: np.ndarray) -> np.ndarray:
    """Center at origin; scale so bounding-box half-diagonal == 1.0.

    Mirrors render_views.py normalize_mesh() logic exactly.
    """
    mn = positions.min(axis=0)
    mx = positions.max(axis=0)
    center = (mn + mx) / 2.0
    positions = positions - center
    half_diag = float(np.linalg.norm((mx - mn) / 2.0))
    half_diag = max(half_diag, 1e-6)
    positions = positions / half_diag
    return positions


# ---------------------------------------------------------------------------
# Back-projection backends
# ---------------------------------------------------------------------------

def _dry_run(glb_path: Path, out_path: Path) -> Path:
    """Dry-run backend: copy existing albedo (or gray fallback) to out_path."""
    albedo = extract_albedo_from_glb(glb_path)
    if albedo is None:
        albedo = Image.new("RGBA", (512, 512), (128, 128, 128, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    albedo.save(str(out_path))
    print(f"[back_project] dry-run: copied existing albedo to {out_path}")
    return out_path


def _nvdiffrast_backend(
    glb_path: Path,
    inpainted_views: list[Path],
    masks: list[Path],
    out_path: Path,
    n_views: int,
    camera_distance: float,
    elevation_deg: float,
    resolution: int,
    uv_size: int,
    front_azimuth_deg: float = 270.0,
) -> Path:
    """nvdiffrast GPU rasterization back-projection backend."""
    try:
        import nvdiffrast.torch as dr
        import torch
    except ImportError as e:
        raise RuntimeError("nvdiffrast not available — use backend='dry-run'") from e

    # --- Load original albedo for compositing base ---
    orig_albedo = extract_albedo_from_glb(glb_path)
    if orig_albedo is None:
        orig_albedo = Image.new("RGBA", (uv_size, uv_size), (128, 128, 128, 255))
    else:
        orig_albedo = orig_albedo.resize((uv_size, uv_size), Image.LANCZOS)
    orig_arr = np.array(orig_albedo).astype(np.float32) / 255.0  # (H, W, 4)

    # --- Load geometry and normalize ---
    positions, uv_coords, faces = _load_geometry(glb_path)
    positions = _normalize_geometry(positions)

    # Convert to torch tensors on CUDA — nvdiffrast requires contiguous memory
    device = torch.device("cuda")
    uv_t_batch = torch.from_numpy(np.ascontiguousarray(uv_coords)).unsqueeze(0).to(device)  # (1, V, 2)
    faces_t = torch.from_numpy(np.ascontiguousarray(faces)).to(device)                       # (F, 3) int32

    # Build nvdiffrast rasterize context once
    glctx = dr.RasterizeCudaContext()

    # Accumulation buffers in UV atlas space
    atlas_color = np.zeros((uv_size, uv_size, 4), dtype=np.float64)
    atlas_count = np.zeros((uv_size, uv_size), dtype=np.float64)

    # Must match render_views.py orbit order: start at front_azimuth_deg, step 360/n_views
    azimuths = [(front_azimuth_deg + 360.0 * i / n_views) % 360.0 for i in range(n_views)]

    for i, az in enumerate(azimuths):
        print(f"[back_project] Processing view {i:02d} (az={az:.1f}deg)")

        # --- Load inpainted view ---
        view_img = Image.open(str(inpainted_views[i])).convert("RGBA")
        if view_img.size != (resolution, resolution):
            view_img = view_img.resize((resolution, resolution), Image.LANCZOS)
        view_arr = np.array(view_img).astype(np.float32) / 255.0  # (H, W, 4)

        # --- Load mask ---
        mask_img = Image.open(str(masks[i])).convert("L")
        if mask_img.size != (resolution, resolution):
            mask_img = mask_img.resize((resolution, resolution), Image.NEAREST)
        mask_arr = np.array(mask_img).astype(np.float32) / 255.0  # (H, W)
        mask_bin = mask_arr > 0.5  # bool (H, W)

        # --- Build MVP and transform vertices to clip space ---
        MVP = _build_mvp(az, elevation_deg, camera_distance)  # (4, 4) float32
        ones = np.ones((positions.shape[0], 1), dtype=np.float32)
        verts_h = np.concatenate([positions, ones], axis=1)   # (V, 4)
        verts_clip = (MVP @ verts_h.T).T.astype(np.float32)   # (V, 4)

        # nvdiffrast expects verts [1, V, 4], faces [F, 3] int32 — all must be contiguous
        verts_clip_c = np.ascontiguousarray(verts_clip)
        verts_clip_t = torch.from_numpy(verts_clip_c).unsqueeze(0).to(device)  # (1, V, 4)

        # --- Rasterize ---
        rast, _ = dr.rasterize(
            glctx, verts_clip_t, faces_t, resolution=[resolution, resolution]
        )
        # rast: (1, H, W, 4)

        # --- Interpolate UVs ---
        uv_interp, _ = dr.interpolate(uv_t_batch, rast, faces_t)
        # uv_interp: (1, H, W, 2)

        rast_np = rast[0].cpu().numpy()    # (H, W, 4)
        uv_np = uv_interp[0].cpu().numpy() # (H, W, 2)

        # Coverage: rast channel 3 is triangle ID (0 = background)
        inside = rast_np[..., 3] > 0  # (H, W) bool

        # Valid pixels: inside a triangle AND in the inpainted mask region
        valid = inside & mask_bin

        if not np.any(valid):
            print(f"[back_project]   view {i:02d}: no valid pixels to project")
            continue

        # Gather pixel colors and UV coords for valid pixels
        rows, cols = np.where(valid)
        pix_colors = view_arr[rows, cols, :]  # (N, 4)
        u_vals = uv_np[rows, cols, 0]         # (N,) in [0,1]
        v_vals = uv_np[rows, cols, 1]         # (N,) in [0,1]

        # Map UV -> atlas pixel coords. GLTF UV origin is upper-left (V=0=top row),
        # matching PIL's row-0=top convention — no V-flip needed.
        atlas_x = np.clip((u_vals * uv_size).astype(np.int32), 0, uv_size - 1)
        atlas_y = np.clip((v_vals * uv_size).astype(np.int32), 0, uv_size - 1)

        # Accumulate contributions
        np.add.at(atlas_color, (atlas_y, atlas_x), pix_colors)
        np.add.at(atlas_count, (atlas_y, atlas_x), 1.0)

        n_valid = int(np.sum(valid))
        print(f"[back_project]   view {i:02d}: {n_valid} valid pixels accumulated")

    # --- Fuse: composite over original albedo ---
    result = orig_arr.copy()
    covered = atlas_count > 0
    if np.any(covered):
        fused = atlas_color[covered] / atlas_count[covered, np.newaxis]
        result[covered] = fused.astype(np.float32)

    result_uint8 = (result * 255.0).clip(0, 255).astype(np.uint8)
    out_img = Image.fromarray(result_uint8, mode="RGBA")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(str(out_path))
    print(f"[back_project] Written variant_albedo to {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def back_project(
    glb_path: "Path | str",
    inpainted_views: "list[Path | str]",
    masks: "list[Path | str]",
    out_path: "Path | str",
    n_views: int,
    camera_distance: float = 2.5,
    elevation_deg: float = 15.0,
    resolution: int = 512,
    uv_size: int = 1024,
    backend: str = "nvdiffrast",
    front_azimuth_deg: float = 270.0,
) -> Path:
    """Back-project inpainted view pixels to UV space and write variant_albedo.png.

    Parameters
    ----------
    glb_path:
        Source GLB character mesh.
    inpainted_views:
        N inpainted view PNGs (RGBA), one per orbit view.
    masks:
        N mask PNGs (L or RGBA, white=inpainted region), one per orbit view.
    out_path:
        Destination path for the output UV atlas PNG.
    n_views:
        Number of orbit views (must match len(inpainted_views) and len(masks)).
    camera_distance:
        Camera distance from origin (post-normalization world units).
    elevation_deg:
        Camera elevation above the equatorial plane in degrees.
    resolution:
        Square render/view resolution in pixels (must match inpainted view size).
    uv_size:
        Output UV atlas resolution (square).
    backend:
        "nvdiffrast" for GPU rasterization, "dry-run" for pipeline smoke test.

    Returns
    -------
    Path
        The written output path.
    """
    glb_path = Path(glb_path)
    out_path = Path(out_path)
    inpainted_views = [Path(p) for p in inpainted_views]
    masks = [Path(p) for p in masks]

    # --- Validation ---
    if not glb_path.exists():
        raise FileNotFoundError(f"GLB not found: {glb_path}")
    if len(inpainted_views) != n_views:
        raise ValueError(
            f"len(inpainted_views)={len(inpainted_views)} != n_views={n_views}"
        )
    if len(masks) != n_views:
        raise ValueError(f"len(masks)={len(masks)} != n_views={n_views}")

    if backend == "dry-run":
        return _dry_run(glb_path, out_path)
    elif backend == "nvdiffrast":
        try:
            import nvdiffrast.torch  # noqa: F401
        except ImportError as e:
            raise RuntimeError("nvdiffrast not available — use backend='dry-run'") from e
        return _nvdiffrast_backend(
            glb_path=glb_path,
            inpainted_views=inpainted_views,
            masks=masks,
            out_path=out_path,
            n_views=n_views,
            camera_distance=camera_distance,
            elevation_deg=elevation_deg,
            resolution=resolution,
            uv_size=uv_size,
            front_azimuth_deg=front_azimuth_deg,
        )
    else:
        raise ValueError(f"Unknown backend: {backend!r}. Use 'nvdiffrast' or 'dry-run'.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Back-project inpainted views to UV atlas (variant_albedo.png)"
    )
    ap.add_argument("--glb", required=True, help="Input GLB character mesh")
    ap.add_argument(
        "--views", nargs="+", required=True, metavar="VIEW_PNG",
        help="Inpainted view PNGs (one per orbit view, RGBA)",
    )
    ap.add_argument(
        "--masks", nargs="+", required=True, metavar="MASK_PNG",
        help="Mask PNGs matching each view (L or RGBA, white=inpainted region)",
    )
    ap.add_argument("--out", required=True, help="Output path for variant_albedo.png")
    ap.add_argument(
        "--n-views", type=int, default=None,
        help="Number of views (defaults to len(--views))",
    )
    ap.add_argument(
        "--backend", choices=["nvdiffrast", "dry-run"], default="nvdiffrast",
        help="Projection backend (default: nvdiffrast)",
    )
    ap.add_argument("--uv-size", type=int, default=1024,
                    help="UV atlas resolution (default: 1024)")
    ap.add_argument("--camera-distance", type=float, default=2.5)
    ap.add_argument("--elevation-deg", type=float, default=15.0)
    ap.add_argument(
        "--resolution", type=int, default=512,
        help="View render resolution in pixels (must match inpainted views, default: 512)",
    )
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    n_views = args.n_views if args.n_views is not None else len(args.views)

    try:
        out = back_project(
            glb_path=args.glb,
            inpainted_views=args.views,
            masks=args.masks,
            out_path=args.out,
            n_views=n_views,
            camera_distance=args.camera_distance,
            elevation_deg=args.elevation_deg,
            resolution=args.resolution,
            uv_size=args.uv_size,
            backend=args.backend,
        )
        print(f"[back_project] Done. Output: {out}")
        return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"[back_project] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
