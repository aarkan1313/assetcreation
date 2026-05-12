"""CHORD image-to-PBR adapter.

CHORD (Chain of Rendering Decomposition for PBR Material Estimation from
Generated Texture Images) is Ubisoft La Forge's diffusion-based PBR
estimator from a single texture image. Outputs aligned 5-channel maps:
basecolor / normal / roughness / metalness, plus height derived via
Poisson integration of the predicted normal.

Why we have it: alternative to stablematerials_image2pbr.py for the
texture -> PBR estimation stage. Per the 2026-05-07 research handoff,
CHORD uses native circular padding for tile-aware inference and
operates at 1024x1024 internally; should produce sharper, more
material-accurate maps than StableMaterials on rich-content albedos.

Architecture: this is a *wrapper* around the ComfyUI custom nodes
(github.com/ubisoft/ComfyUI-Chord). It talks to ComfyUI over HTTP
the same way flux_seamless.py does — uploads the input albedo,
queues a CHORD workflow, downloads the 5 maps. The CHORD nodes
themselves load the model on the GPU; we don't import diffusers or
torch in this process.

Repo:    https://github.com/ubisoft/ComfyUI-Chord
Paper:   https://arxiv.org/abs/2509.09952 (SIGGRAPH Asia 2025)
License: Ubisoft Machine Learning License (Research-Only Copyleft)

Usage:
  python pipelines/textures/chord_image2pbr.py \\
    --input world/textures/library/wgv3_dirt/wgv3_dirt_albedo.pre_delight.png \\
    --out world/textures/library/wgv3_dirt --id wgv3_dirt
"""
from __future__ import annotations

import argparse
import http.client
import json
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

COMFY_HOST = "http://127.0.0.1:8188"
CHORD_CKPT = "chord_v1.safetensors"   # placed in ComfyUI/models/checkpoints/


def queue_prompt(workflow: dict, host: str = COMFY_HOST) -> str:
    payload = json.dumps({"prompt": workflow,
                          "client_id": str(uuid.uuid4())}).encode()
    req = urllib.request.Request(f"{host}/prompt", data=payload,
                                  headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read().decode())["prompt_id"]


def wait_for(prompt_id: str, host: str = COMFY_HOST,
             timeout: int = 1200) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        with urllib.request.urlopen(f"{host}/history/{prompt_id}") as r:
            hist = json.loads(r.read().decode())
        if prompt_id in hist:
            return hist[prompt_id]
        time.sleep(2)
    raise TimeoutError(f"prompt {prompt_id} did not complete within {timeout}s")


def download_output(host: str, filename: str, subfolder: str,
                    type_: str, dest: Path):
    qs = urllib.parse.urlencode(
        {"filename": filename, "subfolder": subfolder, "type": type_})
    with urllib.request.urlopen(f"{host}/view?{qs}") as r, dest.open("wb") as f:
        f.write(r.read())


def upload_image(image_path: Path, host: str = COMFY_HOST) -> str:
    """POST an image to /upload/image; returns the server-side filename."""
    boundary = uuid.uuid4().hex
    body_lines = []
    body_lines.append(f"--{boundary}".encode())
    body_lines.append(
        f'Content-Disposition: form-data; name="image"; '
        f'filename="{image_path.name}"'.encode())
    body_lines.append(b"Content-Type: image/png")
    body_lines.append(b"")
    body_lines.append(image_path.read_bytes())
    body_lines.append(f"--{boundary}--".encode())
    body_lines.append(b"")
    body = b"\r\n".join(body_lines)
    parsed = urllib.parse.urlparse(host)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
    conn.request("POST", "/upload/image", body=body,
                  headers={"Content-Type":
                           f"multipart/form-data; boundary={boundary}"})
    r = conn.getresponse()
    res = json.loads(r.read().decode())
    conn.close()
    return res["name"]


def chord_workflow(input_image_name: str, ckpt: str = CHORD_CKPT,
                   prefix: str = "chord_pbr") -> dict:
    """Build the CHORD ComfyUI workflow.

    Mirrors example_workflows/chord_image_to_material.json: load image,
    load CHORD model, run material estimation (-> basecolor/normal/
    roughness/metalness), derive height from normal, save all 5.
    """
    return {
        # Load input texture
        "1": {"class_type": "LoadImage",
              "inputs": {"image": input_image_name}},
        # Load CHORD model
        "2": {"class_type": "ChordLoadModel",
              "inputs": {"ckpt_name": ckpt}},
        # Estimate 4 PBR maps from the image
        "3": {"class_type": "ChordMaterialEstimation",
              "inputs": {"chord_model": ["2", 0], "image": ["1", 0]}},
        # Derive height from predicted normal (Poisson solver)
        "4": {"class_type": "ChordNormalToHeight",
              "inputs": {"normal": ["3", 1]}},
        # Save outputs — each save node writes a uniquely-prefixed file
        # so we can match them in the history.
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["3", 0],
                          "filename_prefix": f"{prefix}_basecolor"}},
        "11": {"class_type": "SaveImage",
               "inputs": {"images": ["3", 1],
                          "filename_prefix": f"{prefix}_normal"}},
        "12": {"class_type": "SaveImage",
               "inputs": {"images": ["3", 2],
                          "filename_prefix": f"{prefix}_roughness"}},
        "13": {"class_type": "SaveImage",
               "inputs": {"images": ["3", 3],
                          "filename_prefix": f"{prefix}_metalness"}},
        "14": {"class_type": "SaveImage",
               "inputs": {"images": ["4", 0],
                          "filename_prefix": f"{prefix}_height"}},
    }


# Map ComfyUI's prefix-based filename back to which PBR channel it is.
# Order matches the SaveImage nodes above (10..14).
PREFIX_TO_KIND = {
    "basecolor": "albedo",   # we name outputs `<id>_albedo.png` in the library
    "normal":    "normal",
    "roughness": "roughness",
    "metalness": "metallic",  # match library convention (`metallic` not `metalness`)
    "height":    "height",
}


def run_chord(input_path: Path, out_dir: Path, asset_id: str,
              ckpt: str = CHORD_CKPT, host: str = COMFY_HOST) -> dict:
    """Upload input, run CHORD workflow, download 5 maps. Returns
    a dict {kind: saved_path}."""
    print(f"[chord] input: {input_path.name}")
    server_name = upload_image(input_path, host=host)
    print(f"[chord] uploaded as {server_name!r}")

    prefix = f"chord_{asset_id}"
    wf = chord_workflow(server_name, ckpt=ckpt, prefix=prefix)
    pid = queue_prompt(wf, host=host)
    print(f"[chord] queued prompt {pid}; waiting...")
    hist = wait_for(pid, host=host)

    # Walk the history outputs to find each SaveImage's file
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Path] = {}
    outputs = hist.get("outputs", {})
    # outputs is keyed by node id; SaveImage nodes are 10..14
    for node_id, node_out in outputs.items():
        for img in node_out.get("images", []):
            fn = img["filename"]
            sub = img.get("subfolder", "")
            type_ = img.get("type", "output")
            # Identify which channel this is from the filename prefix
            kind = None
            for prefix_token, channel in PREFIX_TO_KIND.items():
                if f"_{prefix_token}_" in fn or fn.startswith(
                        f"{prefix}_{prefix_token}"):
                    kind = channel
                    break
            if kind is None:
                print(f"  [chord] unrecognized output: {fn}")
                continue
            dest = out_dir / f"{asset_id}_{kind}.png"
            download_output(host, fn, sub, type_, dest)
            saved[kind] = dest
            print(f"  saved {kind:12s} -> {dest.name}")
    return saved


def derive_ao(out_dir: Path, asset_id: str) -> Path | None:
    """CHORD doesn't emit AO. Derive a cheap one from the height map
    (same approach as stablematerials_image2pbr.py)."""
    height_path = out_dir / f"{asset_id}_height.png"
    if not height_path.exists():
        return None
    try:
        import numpy as np
        from PIL import Image, ImageFilter
        h = Image.open(height_path).convert("L")
        arr = np.asarray(h, dtype=np.float32)
        blurred = np.asarray(
            h.filter(ImageFilter.GaussianBlur(radius=8)), dtype=np.float32)
        ao = np.clip(1.0 + (arr - blurred) / 128.0, 0, 1)
        ao_img = Image.fromarray((ao * 255).astype(np.uint8), mode="L")
        ao_path = out_dir / f"{asset_id}_ao.png"
        ao_img.save(ao_path)
        print(f"  saved {'ao':12s} -> {ao_path.name} (derived from height)")
        return ao_path
    except Exception as e:
        print(f"  ao derivation failed: {e}")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True,
                    help="input albedo image (will be passed unchanged to "
                         "CHORD; CHORD resizes internally to 1024)")
    ap.add_argument("--out", type=Path, required=True,
                    help="output directory; PBR maps written as "
                         "<out>/<id>_<kind>.png")
    ap.add_argument("--id", required=True,
                    help="asset id; output filenames use this as prefix")
    ap.add_argument("--ckpt", default=CHORD_CKPT,
                    help="CHORD checkpoint filename (placed in "
                         "ComfyUI/models/checkpoints/)")
    ap.add_argument("--host", default=COMFY_HOST)
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")

    saved = run_chord(args.input, args.out, args.id,
                      ckpt=args.ckpt, host=args.host)
    if "height" in saved:
        derive_ao(args.out, args.id)

    expected = ("albedo", "normal", "roughness", "metallic", "height", "ao")
    missing = [k for k in expected if not (args.out / f"{args.id}_{k}.png").exists()]
    if missing:
        print(f"\nWARNING missing maps: {missing}")
    else:
        print(f"\ndone -> {args.out}")


if __name__ == "__main__":
    main()
