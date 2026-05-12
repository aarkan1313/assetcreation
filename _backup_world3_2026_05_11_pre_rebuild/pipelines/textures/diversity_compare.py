"""Run identical prompt+seed across multiple ComfyUI t2i models, with the
same offset+heal seamless trick, then save outputs side-by-side.

Models compared:
  - flux2_klein     (baseline, the existing pipeline)
  - chroma1_hd      (FLUX-schnell de-distilled, Apache-2.0)
  - sd35_large      (Stable Diffusion 3.5 Large, Stability Community License)
  - auraflow_03     (AuraFlow v0.3, Apache-2.0)
  - qwen_image      (Qwen-Image 20B, Apache-2.0)

Active M8 bakeoff lanes after 2026-05-09 review:
  - flux2_klein
  - auraflow_03
  - sd35_large

All four diversity models loaded as GGUF (Q8_0 except Qwen Q6_K) via
ComfyUI-GGUF. ComfyUI auto-evicts the previous model when a new
UNetLoaderGGUF is invoked, so 24GB VRAM is sufficient sequentially.

Usage:
    python diversity_compare.py --prompt "mossy basalt rock" \
        --id basalt_diversity --seed 42 --models active
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
OUTDIR = Path("D:/tmp/diversity_compare_2026_05_09")

FLUX_TILE_PROMPT_SUFFIX = (
    ", fully tileable seamless texture, all four edges loop perfectly, "
    "top-down orthographic view, even neutral diffuse lighting, "
    "no shadows, no highlights, no vignette, no border, no frame, "
    "uniform composition, repeating pattern, 1:1 square aspect, "
    "high detail, photorealistic PBR-ready"
)

SD35_TILE_PROMPT_SUFFIX = (
    ", top-down orthographic material scan, edge-to-edge natural ground sample, "
    "continuous surface pattern, even diffuse lighting, no shadows, no highlights, "
    "no vignette, no border, no frame, no central focal point, no single subject, "
    "no decorative floor tiles, no masonry, no pavers, no wall panels, "
    "uniform macro and micro detail, 1:1 square aspect, photorealistic PBR-ready"
)

DEFAULT_TILE_PROMPT_SUFFIX = (
    ", top-down orthographic material sample, edge-to-edge continuous ground, "
    "even neutral diffuse lighting, no shadows, no highlights, no vignette, "
    "no border, no frame, no central focal point, no decorative tiles, "
    "uniform composition, 1:1 square aspect, high detail"
)


# ---------- ComfyUI HTTP helpers ----------

def queue_prompt(workflow: dict, host: str = COMFY_HOST) -> str:
    payload = json.dumps({"prompt": workflow, "client_id": str(uuid.uuid4())}).encode()
    req = urllib.request.Request(f"{host}/prompt", data=payload,
                                  headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read().decode())["prompt_id"]


def wait_for(prompt_id: str, host: str = COMFY_HOST, timeout: int = 1800) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        with urllib.request.urlopen(f"{host}/history/{prompt_id}") as r:
            hist = json.loads(r.read().decode())
        if prompt_id in hist:
            entry = hist[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                msgs = status.get("messages", [])
                raise RuntimeError(f"ComfyUI error: {msgs[-3:] if msgs else status}")
            return entry
        time.sleep(2)
    raise TimeoutError(f"prompt {prompt_id} did not complete within {timeout}s")


def download_output(host: str, filename: str, subfolder: str, type_: str, dest: Path):
    qs = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": type_})
    with urllib.request.urlopen(f"{host}/view?{qs}") as r, dest.open("wb") as f:
        f.write(r.read())


def upload_image(image_path: Path, host: str = COMFY_HOST) -> str:
    import http.client
    boundary = uuid.uuid4().hex
    body_lines = [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"'.encode(),
        b"Content-Type: image/png",
        b"",
        image_path.read_bytes(),
        f"--{boundary}--".encode(),
        b"",
    ]
    body = b"\r\n".join(body_lines)
    parsed = urllib.parse.urlparse(host)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
    conn.request("POST", "/upload/image", body=body,
                  headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    r = conn.getresponse()
    res = json.loads(r.read().decode())
    conn.close()
    return res["name"]


# ---------- Workflow builders, one per model ----------

def wf_flux2_klein(prompt: str, size: int, seed: int, prefix: str,
                    init_image: str | None = None, denoise: float = 1.0) -> dict:
    """FLUX.2-klein 4B distilled, 4-step euler. Matches existing pipeline."""
    base = {
        "10": {"class_type": "UNETLoader",
               "inputs": {"unet_name": "flux-2-klein-4b.safetensors", "weight_dtype": "default"}},
        "11": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "flux2", "device": "default"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "21": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["20", 0]}},
        "30": {"class_type": "CFGGuider",
               "inputs": {"model": ["10", 0], "positive": ["20", 0],
                          "negative": ["21", 0], "cfg": 1.0}},
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "60": {"class_type": "VAEDecode", "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        "70": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["60", 0]}},
    }
    if init_image:
        base["15"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        base["16"] = {"class_type": "VAEEncode",
                      "inputs": {"pixels": ["15", 0], "vae": ["12", 0]}}
        base["41"] = {"class_type": "BasicScheduler",
                      "inputs": {"model": ["10", 0], "scheduler": "simple",
                                 "steps": 8, "denoise": denoise}}
        latent_src = ["16", 0]
    else:
        base["43"] = {"class_type": "EmptyFlux2LatentImage",
                      "inputs": {"width": size, "height": size, "batch_size": 1}}
        base["41"] = {"class_type": "Flux2Scheduler",
                      "inputs": {"steps": 4, "width": size, "height": size}}
        latent_src = ["43", 0]
    base["50"] = {"class_type": "SamplerCustomAdvanced",
                  "inputs": {"noise": ["42", 0], "guider": ["30", 0],
                             "sampler": ["40", 0], "sigmas": ["41", 0],
                             "latent_image": latent_src}}
    return base


def wf_flux2_klein_9b_q8(prompt: str, size: int, seed: int, prefix: str,
                          init_image: str | None = None, denoise: float = 1.0) -> dict:
    """FLUX.2-klein 9B GGUF Q8_0 (unsloth). FLUX 2 arch, but 9B uses the
    BIGGER 8B Qwen3 text encoder (qwen_3_8b_fp8mixed.safetensors, 8.66 GB)
    -- NOT the qwen_3_4b that klein-4B uses. flux2-vae and Flux2Scheduler
    are shared with klein-4B. 4-step euler, CFG=1.0 (distilled).
    Total disk: 10 GB Q8 transformer + 8.66 GB fp8 text encoder = ~18.7 GB.
    Peak VRAM ~12-14 GB (transformer + text encoder eviction-swapped)."""
    base = {
        "10": {"class_type": "UnetLoaderGGUF",
               "inputs": {"unet_name": "flux-2-klein-9b-Q8_0.gguf"}},
        "11": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": "qwen_3_8b_fp8mixed.safetensors", "type": "flux2", "device": "default"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "21": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["20", 0]}},
        "30": {"class_type": "CFGGuider",
               "inputs": {"model": ["10", 0], "positive": ["20", 0],
                          "negative": ["21", 0], "cfg": 1.0}},
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "60": {"class_type": "VAEDecode", "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        "70": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["60", 0]}},
    }
    if init_image:
        base["15"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        base["16"] = {"class_type": "VAEEncode",
                      "inputs": {"pixels": ["15", 0], "vae": ["12", 0]}}
        base["41"] = {"class_type": "BasicScheduler",
                      "inputs": {"model": ["10", 0], "scheduler": "simple",
                                 "steps": 8, "denoise": denoise}}
        latent_src = ["16", 0]
    else:
        base["43"] = {"class_type": "EmptyFlux2LatentImage",
                      "inputs": {"width": size, "height": size, "batch_size": 1}}
        base["41"] = {"class_type": "Flux2Scheduler",
                      "inputs": {"steps": 4, "width": size, "height": size}}
        latent_src = ["43", 0]
    base["50"] = {"class_type": "SamplerCustomAdvanced",
                  "inputs": {"noise": ["42", 0], "guider": ["30", 0],
                             "sampler": ["40", 0], "sigmas": ["41", 0],
                             "latent_image": latent_src}}
    return base


def wf_flux2_klein_9b_nvfp4(prompt: str, size: int, seed: int, prefix: str,
                             init_image: str | None = None, denoise: float = 1.0) -> dict:
    """FLUX.2-klein 9B NVFP4 (BFL official, single safetensors, 5.76 GB).
    Native 4-bit FP format for Blackwell tensor cores. On RTX 5090 / RTX 5090
    Laptop with PyTorch cu130 this is 2.5x faster than BF16, 60% less VRAM.
    Pairs with the Qwen3-8B text encoder + flux2-vae like the other 9B paths.
    Same 4-step distilled sampling shape as klein-4B."""
    base = {
        "10": {"class_type": "UNETLoader",
               "inputs": {"unet_name": "flux-2-klein-9b-nvfp4.safetensors", "weight_dtype": "default"}},
        "11": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": "qwen_3_8b_fp8mixed.safetensors", "type": "flux2", "device": "default"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "21": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["20", 0]}},
        "30": {"class_type": "CFGGuider",
               "inputs": {"model": ["10", 0], "positive": ["20", 0],
                          "negative": ["21", 0], "cfg": 1.0}},
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "60": {"class_type": "VAEDecode", "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        "70": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["60", 0]}},
    }
    if init_image:
        base["15"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        base["16"] = {"class_type": "VAEEncode",
                      "inputs": {"pixels": ["15", 0], "vae": ["12", 0]}}
        base["41"] = {"class_type": "BasicScheduler",
                      "inputs": {"model": ["10", 0], "scheduler": "simple",
                                 "steps": 8, "denoise": denoise}}
        latent_src = ["16", 0]
    else:
        base["43"] = {"class_type": "EmptyFlux2LatentImage",
                      "inputs": {"width": size, "height": size, "batch_size": 1}}
        base["41"] = {"class_type": "Flux2Scheduler",
                      "inputs": {"steps": 4, "width": size, "height": size}}
        latent_src = ["43", 0]
    base["50"] = {"class_type": "SamplerCustomAdvanced",
                  "inputs": {"noise": ["42", 0], "guider": ["30", 0],
                             "sampler": ["40", 0], "sigmas": ["41", 0],
                             "latent_image": latent_src}}
    return base


def wf_flux2_klein_9b_fp8(prompt: str, size: int, seed: int, prefix: str,
                           init_image: str | None = None, denoise: float = 1.0) -> dict:
    """FLUX.2-klein 9B FP8 (BFL official, single safetensors, 9.43 GB).
    Per SECourses + ComfyUI: 1.7x faster than BF16, ~40% less VRAM. Higher
    quality than NVFP4 (FP8 keeps more dynamic range), at the cost of being
    slower and larger. Same Qwen3-8B encoder + flux2-vae as NVFP4."""
    base = {
        "10": {"class_type": "UNETLoader",
               "inputs": {"unet_name": "flux-2-klein-9b-fp8.safetensors", "weight_dtype": "default"}},
        "11": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": "qwen_3_8b_fp8mixed.safetensors", "type": "flux2", "device": "default"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "21": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["20", 0]}},
        "30": {"class_type": "CFGGuider",
               "inputs": {"model": ["10", 0], "positive": ["20", 0],
                          "negative": ["21", 0], "cfg": 1.0}},
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "60": {"class_type": "VAEDecode", "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        "70": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["60", 0]}},
    }
    if init_image:
        base["15"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        base["16"] = {"class_type": "VAEEncode",
                      "inputs": {"pixels": ["15", 0], "vae": ["12", 0]}}
        base["41"] = {"class_type": "BasicScheduler",
                      "inputs": {"model": ["10", 0], "scheduler": "simple",
                                 "steps": 8, "denoise": denoise}}
        latent_src = ["16", 0]
    else:
        base["43"] = {"class_type": "EmptyFlux2LatentImage",
                      "inputs": {"width": size, "height": size, "batch_size": 1}}
        base["41"] = {"class_type": "Flux2Scheduler",
                      "inputs": {"steps": 4, "width": size, "height": size}}
        latent_src = ["43", 0]
    base["50"] = {"class_type": "SamplerCustomAdvanced",
                  "inputs": {"noise": ["42", 0], "guider": ["30", 0],
                             "sampler": ["40", 0], "sigmas": ["41", 0],
                             "latent_image": latent_src}}
    return base


def wf_flux2_dev_nvfp4(prompt: str, size: int, seed: int, prefix: str,
                        init_image: str | None = None, denoise: float = 1.0,
                        steps: int = 28, cfg: float = 4.0) -> dict:
    """FLUX.2-dev NVFP4 (BFL official, 21 GB single safetensors).
    32B parameter undistilled model -- the quality ceiling for open
    text-to-image. Not 4-step distilled like klein; uses 28 steps + CFG=4
    per the BFL diffusers Flux2Pipeline defaults and the official ComfyUI
    workflow. Uses Flux2Scheduler (resolution-aware sigma schedule), not
    BasicScheduler. On RTX 5090 Laptop + cu130 expect ~4 sec/image
    (vs <1 sec for klein-9B-nvfp4) with ~14 GB VRAM peak.
    Same Qwen3-8B encoder + flux2-vae as klein-9B paths."""
    base = {
        "10": {"class_type": "UNETLoader",
               "inputs": {"unet_name": "flux2-dev-nvfp4.safetensors", "weight_dtype": "default"}},
        "11": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": "qwen_3_8b_fp8mixed.safetensors", "type": "flux2", "device": "default"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "21": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["11", 0]}},
        "30": {"class_type": "CFGGuider",
               "inputs": {"model": ["10", 0], "positive": ["20", 0],
                          "negative": ["21", 0], "cfg": cfg}},
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "60": {"class_type": "VAEDecode", "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        "70": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["60", 0]}},
    }
    if init_image:
        base["15"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        base["16"] = {"class_type": "VAEEncode",
                      "inputs": {"pixels": ["15", 0], "vae": ["12", 0]}}
        # img2img uses BasicScheduler so we can control denoise; t2i uses
        # Flux2Scheduler for the resolution-aware sigma schedule.
        base["41"] = {"class_type": "BasicScheduler",
                      "inputs": {"model": ["10", 0], "scheduler": "simple",
                                 "steps": steps, "denoise": denoise}}
        latent_src = ["16", 0]
    else:
        base["43"] = {"class_type": "EmptyFlux2LatentImage",
                      "inputs": {"width": size, "height": size, "batch_size": 1}}
        base["41"] = {"class_type": "Flux2Scheduler",
                      "inputs": {"steps": steps, "width": size, "height": size}}
        latent_src = ["43", 0]
    base["50"] = {"class_type": "SamplerCustomAdvanced",
                  "inputs": {"noise": ["42", 0], "guider": ["30", 0],
                             "sampler": ["40", 0], "sigmas": ["41", 0],
                             "latent_image": latent_src}}
    return base


def wf_chroma(prompt: str, size: int, seed: int, prefix: str,
               init_image: str | None = None, denoise: float = 1.0,
               steps: int = 26, cfg: float = 4.0) -> dict:
    """Chroma1-HD GGUF. T5xxl + FLUX VAE. Needs CFG ~4 (de-distilled)."""
    base = {
        "10": {"class_type": "UnetLoaderGGUF",
               "inputs": {"unet_name": "chroma1-hd-Q8_0.gguf"}},
        "11": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors",
                          "type": "chroma", "device": "default"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "21": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["11", 0]}},
        "30": {"class_type": "CFGGuider",
               "inputs": {"model": ["10", 0], "positive": ["20", 0],
                          "negative": ["21", 0], "cfg": cfg}},
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "41": {"class_type": "BasicScheduler",
               "inputs": {"model": ["10", 0], "scheduler": "simple",
                          "steps": steps, "denoise": denoise}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "60": {"class_type": "VAEDecode", "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        "70": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["60", 0]}},
    }
    if init_image:
        base["15"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        base["16"] = {"class_type": "VAEEncode",
                      "inputs": {"pixels": ["15", 0], "vae": ["12", 0]}}
        latent_src = ["16", 0]
    else:
        base["43"] = {"class_type": "EmptyLatentImage",
                      "inputs": {"width": size, "height": size, "batch_size": 1}}
        latent_src = ["43", 0]
    base["50"] = {"class_type": "SamplerCustomAdvanced",
                  "inputs": {"noise": ["42", 0], "guider": ["30", 0],
                             "sampler": ["40", 0], "sigmas": ["41", 0],
                             "latent_image": latent_src}}
    return base


def wf_sd35(prompt: str, size: int, seed: int, prefix: str,
             init_image: str | None = None, denoise: float = 1.0,
             steps: int = 28, cfg: float = 4.5) -> dict:
    """SD 3.5 Large GGUF + clip_l + clip_g + t5xxl + sd3.5_vae."""
    base = {
        "10": {"class_type": "UnetLoaderGGUF",
               "inputs": {"unet_name": "sd3.5_large-Q8_0.gguf"}},
        "11": {"class_type": "TripleCLIPLoader",
               "inputs": {"clip_name1": "clip_g.safetensors",
                          "clip_name2": "clip_l.safetensors",
                          "clip_name3": "t5xxl_fp8_e4m3fn.safetensors"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "sd3.5_vae.safetensors"}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "21": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["11", 0]}},
        "30": {"class_type": "CFGGuider",
               "inputs": {"model": ["10", 0], "positive": ["20", 0],
                          "negative": ["21", 0], "cfg": cfg}},
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "41": {"class_type": "BasicScheduler",
               "inputs": {"model": ["10", 0], "scheduler": "sgm_uniform",
                          "steps": steps, "denoise": denoise}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "60": {"class_type": "VAEDecode", "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        "70": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["60", 0]}},
    }
    if init_image:
        base["15"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        base["16"] = {"class_type": "VAEEncode",
                      "inputs": {"pixels": ["15", 0], "vae": ["12", 0]}}
        latent_src = ["16", 0]
    else:
        base["43"] = {"class_type": "EmptySD3LatentImage",
                      "inputs": {"width": size, "height": size, "batch_size": 1}}
        latent_src = ["43", 0]
    base["50"] = {"class_type": "SamplerCustomAdvanced",
                  "inputs": {"noise": ["42", 0], "guider": ["30", 0],
                             "sampler": ["40", 0], "sigmas": ["41", 0],
                             "latent_image": latent_src}}
    return base


def wf_auraflow(prompt: str, size: int, seed: int, prefix: str,
                 init_image: str | None = None, denoise: float = 1.0,
                 steps: int = 25, cfg: float = 3.5) -> dict:
    """AuraFlow v0.3 GGUF + UMT5-XXL + auraflow VAE."""
    base = {
        "10": {"class_type": "UnetLoaderGGUF",
               "inputs": {"unet_name": "aura_flow_0.3-Q8_0.gguf"}},
        "11": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": "auraflow_pile_t5_xl_fp16.safetensors",
                          "type": "stable_diffusion", "device": "default"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "auraflow_vae.safetensors"}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "21": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["11", 0]}},
        "30": {"class_type": "CFGGuider",
               "inputs": {"model": ["10", 0], "positive": ["20", 0],
                          "negative": ["21", 0], "cfg": cfg}},
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "41": {"class_type": "BasicScheduler",
               "inputs": {"model": ["10", 0], "scheduler": "simple",
                          "steps": steps, "denoise": denoise}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "60": {"class_type": "VAEDecode", "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        "70": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["60", 0]}},
    }
    if init_image:
        base["15"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        base["16"] = {"class_type": "VAEEncode",
                      "inputs": {"pixels": ["15", 0], "vae": ["12", 0]}}
        latent_src = ["16", 0]
    else:
        base["43"] = {"class_type": "EmptyLatentImage",
                      "inputs": {"width": size, "height": size, "batch_size": 1}}
        latent_src = ["43", 0]
    base["50"] = {"class_type": "SamplerCustomAdvanced",
                  "inputs": {"noise": ["42", 0], "guider": ["30", 0],
                             "sampler": ["40", 0], "sigmas": ["41", 0],
                             "latent_image": latent_src}}
    return base


def wf_qwen_image(prompt: str, size: int, seed: int, prefix: str,
                   init_image: str | None = None, denoise: float = 1.0,
                   steps: int = 30, cfg: float = 4.0) -> dict:
    """Qwen-Image GGUF Q6_K + qwen2.5-vl encoder + qwen_image VAE."""
    base = {
        "10": {"class_type": "UnetLoaderGGUF",
               "inputs": {"unet_name": "qwen-image-Q6_K.gguf"}},
        "11": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                          "type": "qwen_image", "device": "default"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "21": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["11", 0]}},
        "30": {"class_type": "CFGGuider",
               "inputs": {"model": ["10", 0], "positive": ["20", 0],
                          "negative": ["21", 0], "cfg": cfg}},
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "41": {"class_type": "BasicScheduler",
               "inputs": {"model": ["10", 0], "scheduler": "simple",
                          "steps": steps, "denoise": denoise}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "60": {"class_type": "VAEDecode", "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        "70": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["60", 0]}},
    }
    if init_image:
        base["15"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        base["16"] = {"class_type": "VAEEncode",
                      "inputs": {"pixels": ["15", 0], "vae": ["12", 0]}}
        latent_src = ["16", 0]
    else:
        base["43"] = {"class_type": "EmptyLatentImage",
                      "inputs": {"width": size, "height": size, "batch_size": 1}}
        latent_src = ["43", 0]
    base["50"] = {"class_type": "SamplerCustomAdvanced",
                  "inputs": {"noise": ["42", 0], "guider": ["30", 0],
                             "sampler": ["40", 0], "sigmas": ["41", 0],
                             "latent_image": latent_src}}
    return base


# ---------- offset+heal (lifted from flux_seamless.py) ----------

def offset_image(arr: np.ndarray) -> np.ndarray:
    h, w = arr.shape[:2]
    out = np.empty_like(arr)
    out[:h // 2, :w // 2] = arr[h // 2:, w // 2:]
    out[:h // 2, w // 2:] = arr[h // 2:, :w // 2]
    out[h // 2:, :w // 2] = arr[:h // 2, w // 2:]
    out[h // 2:, w // 2:] = arr[:h // 2, :w // 2]
    return out


def edge_seam_score(im: np.ndarray) -> float:
    edge_lr = float(np.mean((im[:, 0].astype(np.float32) - im[:, -1].astype(np.float32)) ** 2)) / (255 ** 2)
    edge_tb = float(np.mean((im[0, :].astype(np.float32) - im[-1, :].astype(np.float32)) ** 2)) / (255 ** 2)
    return max(edge_lr, edge_tb)


# ---------- model registry ----------

MODELS = {
    "flux2_klein":           {"builder": wf_flux2_klein,           "label": "FLUX.2-klein 4B (baseline)",
                               "suffix": FLUX_TILE_PROMPT_SUFFIX},
    "flux2_klein_9b":        {"builder": wf_flux2_klein_9b_q8,     "label": "FLUX.2-klein 9B Q8_0 (unsloth)",
                               "suffix": FLUX_TILE_PROMPT_SUFFIX},
    "flux2_klein_9b_nvfp4":  {"builder": wf_flux2_klein_9b_nvfp4,  "label": "FLUX.2-klein 9B NVFP4 (BFL)",
                               "suffix": FLUX_TILE_PROMPT_SUFFIX},
    "flux2_klein_9b_fp8":    {"builder": wf_flux2_klein_9b_fp8,    "label": "FLUX.2-klein 9B FP8 (BFL)",
                               "suffix": FLUX_TILE_PROMPT_SUFFIX},
    "flux2_dev_nvfp4":       {"builder": wf_flux2_dev_nvfp4,       "label": "FLUX.2-dev NVFP4 32B (BFL)",
                               "suffix": FLUX_TILE_PROMPT_SUFFIX},
    "sd35_large":            {"builder": wf_sd35,                  "label": "SD 3.5 Large Q8_0",
                               "suffix": SD35_TILE_PROMPT_SUFFIX},
    "auraflow_03":           {"builder": wf_auraflow,              "label": "AuraFlow v0.3 Q8_0",
                               "suffix": FLUX_TILE_PROMPT_SUFFIX},
    # Sunset 2026-05-10 (files deleted from disk to reclaim ~36 GB):
    #   "chroma1_hd"  - rejected for this phase (tileable -> "tile" noun, decorative motifs)
    #   "qwen_image"  - parked (slow + hero-shot/DOF bias for ground textures)
    # Builders wf_chroma and wf_qwen_image stay in code as reference; re-download
    # chroma1-hd-Q8_0.gguf / qwen-image-Q6_K.gguf (+ encoders/VAE) to revive.
}

ACTIVE_MODELS = ["flux2_klein", "auraflow_03", "sd35_large"]


def run_one(model_key: str, prompt: str, asset_id: str, size: int, seed: int,
             host: str, heal_strength: float, do_seamless: bool) -> dict:
    """Returns a dict with paths + seam scores."""
    builder = MODELS[model_key]["builder"]
    out_dir = OUTDIR / asset_id / model_key
    out_dir.mkdir(parents=True, exist_ok=True)

    full_prompt = prompt + MODELS[model_key]["suffix"]

    # Pass 1: text2img
    print(f"\n=== {model_key}: text2img ===")
    t0 = time.time()
    wf = builder(full_prompt, size, seed, prefix=f"{asset_id}_{model_key}_pass1")
    pid = queue_prompt(wf, host=host)
    res = wait_for(pid, host=host)
    images = res["outputs"].get("70", {}).get("images", [])
    if not images:
        raise RuntimeError(f"no images from {model_key} pass 1")
    p1_path = out_dir / "pass1_raw.png"
    download_output(host, images[0]["filename"], images[0]["subfolder"],
                     images[0]["type"], p1_path)
    p1 = np.asarray(Image.open(p1_path).convert("RGB"))
    p1_score = edge_seam_score(p1)
    p1_t = time.time() - t0
    print(f"  pass1 done in {p1_t:.1f}s, seam={p1_score:.5f}")

    result = {
        "model": model_key,
        "label": MODELS[model_key]["label"],
        "pass1": str(p1_path),
        "pass1_seam": p1_score,
        "pass1_seconds": round(p1_t, 1),
    }

    if not do_seamless:
        return result

    # Pass 2: circular shift
    shifted = offset_image(p1)
    shifted_path = out_dir / "pass2_shifted.png"
    Image.fromarray(shifted).save(shifted_path)
    server_name = upload_image(shifted_path, host=host)

    # Pass 3: img2img heal
    print(f"=== {model_key}: heal pass denoise={heal_strength} ===")
    t1 = time.time()
    wf = builder(full_prompt, size, seed + 99, prefix=f"{asset_id}_{model_key}_pass3",
                  init_image=server_name, denoise=heal_strength)
    pid = queue_prompt(wf, host=host)
    res = wait_for(pid, host=host)
    images = res["outputs"].get("70", {}).get("images", [])
    if not images:
        raise RuntimeError(f"no images from {model_key} pass 3")
    p3_path = out_dir / "pass3_healed_shifted.png"
    download_output(host, images[0]["filename"], images[0]["subfolder"],
                     images[0]["type"], p3_path)
    p3 = np.asarray(Image.open(p3_path).convert("RGB"))
    p3_t = time.time() - t1
    print(f"  pass3 done in {p3_t:.1f}s")

    # Pass 4: reverse shift
    final = offset_image(p3)
    final_path = out_dir / "final_albedo.png"
    Image.fromarray(final).save(final_path)
    final_score = edge_seam_score(final)
    print(f"  final seam={final_score:.5f}")

    result.update({
        "pass3": str(p3_path),
        "final": str(final_path),
        "final_seam": final_score,
        "pass3_seconds": round(p3_t, 1),
        "total_seconds": round(p1_t + p3_t, 1),
    })
    return result


def make_grid(results: list[dict], asset_id: str, mode: str) -> Path:
    """5-up grid (one column per model). mode='pass1' or 'final'."""
    n = len(results)
    label_h = 40
    cell = 512  # downscale for grid
    grid = Image.new("RGB", (cell * n, cell + label_h), "white")
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(grid)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()

    for i, r in enumerate(results):
        path = r.get(mode) or r["pass1"]
        if not Path(path).exists():
            continue
        im = Image.open(path).convert("RGB").resize((cell, cell), Image.LANCZOS)
        grid.paste(im, (i * cell, label_h))
        seam_key = "final_seam" if mode == "final" else "pass1_seam"
        seam = r.get(seam_key, r.get("pass1_seam", 0))
        secs = r.get("total_seconds", r.get("pass1_seconds", 0))
        label = f"{r['label']} | seam={seam:.4f} | {secs}s"
        draw.text((i * cell + 8, 10), label, fill="black", font=font)

    grid_path = OUTDIR / asset_id / f"grid_{mode}.png"
    grid_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(grid_path)
    return grid_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--heal-strength", type=float, default=0.35)
    ap.add_argument("--host", default=COMFY_HOST)
    ap.add_argument("--models", default="active",
                    help="comma list, 'active', or 'all'. options: " + ",".join(MODELS))
    ap.add_argument("--no-seamless", action="store_true",
                    help="skip offset+heal; just run pass1 (smoke test)")
    args = ap.parse_args()

    if args.models == "all":
        keys = list(MODELS)
    elif args.models == "active":
        keys = ACTIVE_MODELS
    else:
        keys = [k.strip() for k in args.models.split(",") if k.strip()]
    print(f"Running {len(keys)} models on prompt: {args.prompt!r}")
    print(f"  seed={args.seed} size={args.size} heal={args.heal_strength}")

    results = []
    for k in keys:
        if k not in MODELS:
            print(f"  ! unknown model: {k}, skipping")
            continue
        try:
            r = run_one(k, args.prompt, args.id, args.size, args.seed,
                         args.host, args.heal_strength,
                         do_seamless=not args.no_seamless)
            results.append(r)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  !! {k} failed: {e}")
            results.append({"model": k, "label": MODELS[k]["label"],
                            "error": str(e), "pass1_seam": 0,
                            "pass1": "", "pass1_seconds": 0})

    summary = OUTDIR / args.id / "summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(results, indent=2))
    print(f"\nsummary -> {summary}")

    if not args.no_seamless:
        grid = make_grid(results, args.id, "final")
        print(f"final grid -> {grid}")
    pass1_grid = make_grid(results, args.id, "pass1")
    print(f"pass1 grid -> {pass1_grid}")


if __name__ == "__main__":
    main()
