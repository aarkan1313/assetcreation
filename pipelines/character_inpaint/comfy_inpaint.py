"""ComfyUI inpaint client for the character_inpaint pipeline.

Two backends:
  dry-run   -- PIL composite only; no ML model needed.
  flux-fill -- Calls ComfyUI HTTP API with FLUX.1-Fill + FLUX.1-Redux workflow.

Public API
----------
inpaint_view(source, mask, reference, backend="dry-run", ...) -> PIL.Image
"""
from __future__ import annotations

import io
import json
import time
import uuid
from pathlib import Path

import numpy as np
import requests
from PIL import Image

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def inpaint_view(
    source: Image.Image,
    mask: Image.Image,
    reference: Image.Image,
    backend: str = "dry-run",
    comfy_url: str = "http://127.0.0.1:8188",
    positive_prompt: str = "faction emblem branded onto leather armor, seamlessly integrated",
    redux_strength: float = 1.0,
    use_redux: bool = False,
    denoise: float = 0.95,
    steps: int = 28,
) -> Image.Image:
    """Inpaint the mask region using the reference image. Returns RGBA PIL Image.

    Parameters
    ----------
    source:
        RGBA render from Blender.
    mask:
        L-mode mask image (white=inpaint, black=keep).  Will be converted to L
        internally if passed as RGB/RGBA.
    reference:
        RGBA reference insignia to blend into the mask region.
    backend:
        "dry-run"  -- PIL-only composite (no ComfyUI required).
        "flux-fill" -- ComfyUI FLUX.1-Fill + FLUX.1-Redux reference conditioning.
    comfy_url:
        Base URL of the ComfyUI server (flux-fill backend only).
    positive_prompt:
        Positive text conditioning (flux-fill backend only).
    redux_strength:
        FLUX.1-Redux reference image influence weight 0..10 (flux-fill backend only).
        Only used when use_redux=True.
    use_redux:
        If True, include FLUX.1-Redux reference conditioning. Default False — prompt-only
        inpainting is more reliable for hard insignia stamps (Redux is a style adapter,
        not a logo compositor).
    denoise:
        KSampler denoise strength 0..1 (flux-fill backend only). Default 0.95 (high) so
        FLUX overwrites the mask region completely.
    steps:
        KSampler step count (flux-fill backend only).

    Returns
    -------
    PIL.Image (RGBA)
    """
    # Normalise inputs
    source = source.convert("RGBA")
    mask = mask.convert("L")

    if backend == "dry-run":
        return _dry_run(source, mask, reference)
    elif backend == "flux-fill":
        return _flux_fill(
            source=source,
            mask=mask,
            reference=reference,
            comfy_url=comfy_url.rstrip("/"),
            positive_prompt=positive_prompt,
            redux_strength=redux_strength,
            use_redux=use_redux,
            denoise=denoise,
            steps=steps,
        )
    else:
        raise ValueError(f"Unknown backend {backend!r}. Choose 'dry-run' or 'flux-fill'.")


# ---------------------------------------------------------------------------
# Backend: dry-run
# ---------------------------------------------------------------------------


def _dry_run(
    source: Image.Image,
    mask: Image.Image,
    reference: Image.Image,
) -> Image.Image:
    """Composite reference into the mask region of source.

    Algorithm
    ---------
    1. Find bounding box of white (>128) pixels in mask.
    2. Resize reference to fit that bounding box, preserving aspect ratio,
       centred inside the box.
    3. For each pixel where mask > 128, blend reference over source at alpha=0.85
       (so it is visible but clearly a dry-run composite, not real diffusion output).
    4. Return RGBA composited image.
    """
    mask_arr = np.array(mask)  # H x W uint8

    # --- find bounding box of inpaint region ---
    ys, xs = np.where(mask_arr > 128)
    if len(xs) == 0 or len(ys) == 0:
        # Nothing to inpaint -- return source unchanged
        return source.copy()

    x_min, x_max = int(xs.min()), int(xs.max())
    y_min, y_max = int(ys.min()), int(ys.max())
    box_w = x_max - x_min + 1
    box_h = y_max - y_min + 1

    # --- resize reference to fit bounding box, preserving aspect ratio ---
    ref_rgba = reference.convert("RGBA")
    ref_w, ref_h = ref_rgba.size
    scale = min(box_w / ref_w, box_h / ref_h)
    new_w = max(1, int(ref_w * scale))
    new_h = max(1, int(ref_h * scale))
    ref_resized = ref_rgba.resize((new_w, new_h), Image.LANCZOS)

    # Place resized reference centred within bounding box on a transparent canvas
    # the same size as source.
    src_w, src_h = source.size
    ref_canvas = Image.new("RGBA", (src_w, src_h), (0, 0, 0, 0))
    paste_x = x_min + (box_w - new_w) // 2
    paste_y = y_min + (box_h - new_h) // 2
    ref_canvas.paste(ref_resized, (paste_x, paste_y))

    # --- blend at alpha=0.85 where mask > 128 ---
    src_arr = np.array(source, dtype=np.float32)       # H x W x 4
    ref_arr = np.array(ref_canvas, dtype=np.float32)   # H x W x 4
    inpaint_region = (mask_arr > 128)                  # H x W bool

    alpha = 0.85
    blended = src_arr.copy()
    blended[inpaint_region] = (
        alpha * ref_arr[inpaint_region]
        + (1.0 - alpha) * src_arr[inpaint_region]
    )

    result_arr = np.clip(blended, 0, 255).astype(np.uint8)
    return Image.fromarray(result_arr, mode="RGBA")


# ---------------------------------------------------------------------------
# Backend: flux-fill  (ComfyUI HTTP API)
# ---------------------------------------------------------------------------

_COMFY_TIMEOUT = 300   # seconds to wait for ComfyUI to finish
_POLL_INTERVAL = 2     # seconds between history polls


def _check_comfy_reachable(comfy_url: str) -> None:
    """Raise RuntimeError if ComfyUI is not responding."""
    try:
        r = requests.get(f"{comfy_url}/system_stats", timeout=5)
        r.raise_for_status()
    except Exception as exc:
        raise RuntimeError(
            f"ComfyUI not reachable at {comfy_url}: {exc}"
        ) from exc


def _upload_image(
    comfy_url: str,
    image: Image.Image,
    filename: str,
    image_type: str = "input",
) -> str:
    """Upload a PIL Image to ComfyUI and return the server-side filename."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    resp = requests.post(
        f"{comfy_url}/upload/image",
        files={"image": (filename, buf, "image/png")},
        data={"type": image_type, "overwrite": "true"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["name"]


def _build_workflow(
    source_name: str,
    mask_name: str,
    reference_name: str | None,
    positive_prompt: str,
    redux_strength: float,
    use_redux: bool,
    denoise: float,
    steps: int,
    seed: int,
) -> dict:
    """Build the ComfyUI workflow dict for FLUX.1-Fill inpainting.

    Two modes controlled by use_redux:
      use_redux=False (default): prompt-only. Text prompt drives the inpaint.
        Best for hard insignia stamps where you describe the mark in the prompt.
        Node graph: LoadImage×2, VAELoader, DualCLIPLoader, UNETLoader,
          CLIPTextEncode×2, InpaintModelConditioning, KSampler, VAEDecode, SaveImage

      use_redux=True: adds FLUX.1-Redux reference image conditioning.
        Nodes 3,9,10,11,12 added. Redux is a style adapter — useful for texture/style
        transfer but not reliable for exact logo placement.
        Requires: sigclip_vision_patch14_384.safetensors, flux1-redux-dev.safetensors

    All class names confirmed in D:/assets/animators/ComfyUI/nodes.py.
    """
    # Positive conditioning source: node 12 (StyleModelApply) if redux, else node 7 (text)
    positive_cond = ["12", 0] if use_redux else ["7", 0]

    nodes: dict = {
        # Node 1: Load source image
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": source_name},
        },
        # Node 2: Load mask image (slot 1 output = MASK tensor)
        "2": {
            "class_type": "LoadImage",
            "inputs": {"image": mask_name},
        },
        # Node 4: Load VAE (standard FLUX AE, 16-ch; Fill packs 96ch = 6×16ch)
        "4": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"},
        },
        # Node 5: Load dual CLIP (clip_l + t5xxl for FLUX text conditioning)
        "5": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "clip_l.safetensors",
                "clip_name2": "t5xxl_fp8_e4m3fn.safetensors",
                "type": "flux",
            },
        },
        # Node 6: Load FLUX.1-Fill UNET (fp8 quant, 11.9 GB, fits 24 GB VRAM)
        "6": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "flux1-fill-dev-fp8.safetensors",
                "weight_dtype": "fp8_e4m3fn",
            },
        },
        # Node 7: Positive text prompt
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["5", 0], "text": positive_prompt},
        },
        # Node 8: Negative prompt (empty; FLUX doesn't use negatives meaningfully)
        "8": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["5", 0], "text": ""},
        },
        # Node 13: InpaintModelConditioning (noise_mask=True required in ComfyUI 0.20+)
        "13": {
            "class_type": "InpaintModelConditioning",
            "inputs": {
                "positive": positive_cond,
                "negative": ["8", 0],
                "vae": ["4", 0],
                "pixels": ["1", 0],
                "mask": ["2", 1],
                "noise_mask": True,
            },
        },
        # Node 14: KSampler (cfg=1.0 for FLUX distilled guidance)
        "14": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["6", 0],
                "positive": ["13", 0],
                "negative": ["13", 1],
                "latent_image": ["13", 2],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": denoise,
            },
        },
        # Node 15: VAEDecode
        "15": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["14", 0], "vae": ["4", 0]},
        },
        # Node 16: SaveImage
        "16": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["15", 0],
                "filename_prefix": "inpaint_out",
            },
        },
    }

    if use_redux and reference_name is not None:
        nodes.update({
            # Node 3: Load reference image for Redux style conditioning
            "3": {
                "class_type": "LoadImage",
                "inputs": {"image": reference_name},
            },
            # Node 9: Load SigLIP vision encoder (redux_dim=1152, requires SO400M-patch14-384)
            "9": {
                "class_type": "CLIPVisionLoader",
                "inputs": {"clip_name": "sigclip_vision_patch14_384.safetensors"},
            },
            # Node 10: Encode reference image (crop required in ComfyUI 0.20+)
            "10": {
                "class_type": "CLIPVisionEncode",
                "inputs": {"clip_vision": ["9", 0], "image": ["3", 0], "crop": "center"},
            },
            # Node 11: Load FLUX.1-Redux style model
            "11": {
                "class_type": "StyleModelLoader",
                "inputs": {"style_model_name": "flux1-redux-dev.safetensors"},
            },
            # Node 12: Apply Redux style conditioning (strength controls reference influence)
            "12": {
                "class_type": "StyleModelApply",
                "inputs": {
                    "conditioning": ["7", 0],
                    "style_model": ["11", 0],
                    "clip_vision_output": ["10", 0],
                    "strength": redux_strength,
                },
            },
        })

    return nodes


def _flux_fill(
    source: Image.Image,
    mask: Image.Image,
    reference: Image.Image,
    comfy_url: str,
    positive_prompt: str,
    redux_strength: float,
    use_redux: bool,
    denoise: float,
    steps: int,
) -> Image.Image:
    """Run the FLUX.1-Fill inpaint workflow via ComfyUI HTTP API."""

    # 1. Check ComfyUI is reachable
    _check_comfy_reachable(comfy_url)

    # 2. Upload images
    run_id = uuid.uuid4().hex[:8]
    source_name = _upload_image(comfy_url, source,    f"ci_source_{run_id}.png")
    mask_name   = _upload_image(comfy_url, mask,      f"ci_mask_{run_id}.png")
    ref_name    = _upload_image(comfy_url, reference, f"ci_ref_{run_id}.png") if use_redux else None

    # 3. Build and submit workflow
    seed = int(uuid.uuid4().int & 0xFFFFFFFF)
    workflow = _build_workflow(
        source_name=source_name,
        mask_name=mask_name,
        reference_name=ref_name,
        positive_prompt=positive_prompt,
        redux_strength=redux_strength,
        use_redux=use_redux,
        denoise=denoise,
        steps=steps,
        seed=seed,
    )

    client_id = str(uuid.uuid4())
    payload = {"prompt": workflow, "client_id": client_id}
    resp = requests.post(f"{comfy_url}/prompt", json=payload, timeout=30)
    resp.raise_for_status()
    prompt_id = resp.json()["prompt_id"]

    # 4. Poll history until done
    deadline = time.monotonic() + _COMFY_TIMEOUT
    output_images = None
    while time.monotonic() < deadline:
        time.sleep(_POLL_INTERVAL)
        hist_resp = requests.get(f"{comfy_url}/history/{prompt_id}", timeout=10)
        hist_resp.raise_for_status()
        history = hist_resp.json()
        if prompt_id in history:
            entry = history[prompt_id]
            # Check for error status
            if entry.get("status", {}).get("status_str") == "error":
                messages = entry.get("status", {}).get("messages", [])
                raise RuntimeError(f"ComfyUI workflow failed: {messages}")
            # Collect outputs from any node that produced images
            outputs = entry.get("outputs", {})
            if outputs:
                for node_id, node_out in outputs.items():
                    imgs = node_out.get("images", [])
                    if imgs:
                        output_images = imgs
                        break
                if output_images:
                    break
    else:
        raise RuntimeError(
            f"ComfyUI workflow timed out after {_COMFY_TIMEOUT}s "
            f"(prompt_id={prompt_id})"
        )

    # 5. Download first output image
    img_info = output_images[0]
    params = {
        "filename": img_info["filename"],
        "subfolder": img_info.get("subfolder", ""),
        "type": img_info.get("type", "output"),
    }
    dl_resp = requests.get(f"{comfy_url}/view", params=params, timeout=60)
    dl_resp.raise_for_status()

    flux_result = Image.open(io.BytesIO(dl_resp.content)).convert("RGBA")

    # 6. Composite: keep source outside mask, use FLUX result inside mask only.
    # FLUX.1-Fill returns full-image regeneration; we only want the inpainted region.
    # Resize flux result to match source in case ComfyUI resampled.
    if flux_result.size != source.size:
        flux_result = flux_result.resize(source.size, Image.LANCZOS)
    mask_resized = mask.resize(source.size, Image.NEAREST)

    # Only paste where BOTH the mask is white AND the source character has visible pixels
    # (source alpha > 0). This prevents FLUX's transparent background from bleeding in.
    src_alpha = np.array(source)[:, :, 3]          # H x W uint8
    mask_arr = np.array(mask_resized)               # H x W uint8
    composite_mask_arr = np.minimum(mask_arr, (src_alpha > 128).astype(np.uint8) * 255)
    composite_mask = Image.fromarray(composite_mask_arr, mode="L")

    # Paste only the RGB channels of FLUX result (its alpha is unreliable)
    flux_rgb = flux_result.convert("RGB").convert("RGBA")
    result = source.copy()
    result.paste(flux_rgb, mask=composite_mask)
    return result
