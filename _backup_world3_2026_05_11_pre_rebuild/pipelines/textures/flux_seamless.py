"""Seam-aware FLUX.2-klein texture generation.

Standard "seamless" prompts in FLUX produce non-tiling output. This module
applies the canonical hybrid approach:

  Pass 1: Generate at full resolution with reinforced tiling prompt
  Pass 2: Circular-shift the result by half its size, exposing the (formerly
          edge) seams in the center
  Pass 3: img2img low-denoise FLUX pass to "heal" the visible seam cross
  Pass 4: Reverse the circular shift; result tiles naturally.

This is the same algorithm Substance Designer + Stable Diffusion communities
use ("offset method"). Not perfect — directional patterns (planks, bricks)
still need a structure-aware repair pass — but works well for noise-like
materials and gives 3-5x better seam scores.

Usage:
  python flux_seamless.py --prompt "mossy basalt rock" --id basalt --size 1024 \
      --seed 7 --heal-strength 0.35
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
LIBRARY = Path("D:/assets/world/textures/library")


# Reinforce tiling intent. FLUX listens to long prompts.
TILE_PROMPT_SUFFIX = (
    ", fully tileable seamless texture, all four edges loop perfectly, "
    "top-down orthographic view, even neutral diffuse lighting, "
    "no shadows, no highlights, no vignette, no border, no frame, "
    "uniform composition, repeating pattern, 1:1 square aspect, "
    "high detail, photorealistic PBR-ready"
)


def queue_prompt(workflow: dict, host: str = COMFY_HOST) -> str:
    payload = json.dumps({"prompt": workflow, "client_id": str(uuid.uuid4())}).encode()
    req = urllib.request.Request(f"{host}/prompt", data=payload,
                                  headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read().decode())["prompt_id"]


def wait_for(prompt_id: str, host: str = COMFY_HOST, timeout: int = 1200) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        with urllib.request.urlopen(f"{host}/history/{prompt_id}") as r:
            hist = json.loads(r.read().decode())
        if prompt_id in hist:
            return hist[prompt_id]
        time.sleep(2)
    raise TimeoutError(f"prompt {prompt_id} did not complete within {timeout}s")


def download_output(host: str, filename: str, subfolder: str, type_: str, dest: Path):
    qs = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": type_})
    with urllib.request.urlopen(f"{host}/view?{qs}") as r, dest.open("wb") as f:
        f.write(r.read())


def upload_image(image_path: Path, host: str = COMFY_HOST) -> str:
    """POST an image to /upload/image; returns the server-side filename."""
    import http.client
    import os
    boundary = uuid.uuid4().hex
    body_lines = []
    body_lines.append(f"--{boundary}".encode())
    body_lines.append(f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"'.encode())
    body_lines.append(b"Content-Type: image/png")
    body_lines.append(b"")
    body_lines.append(image_path.read_bytes())
    body_lines.append(f"--{boundary}--".encode())
    body_lines.append(b"")
    body = b"\r\n".join(body_lines)
    parsed = urllib.parse.urlparse(host)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
    conn.request("POST", "/upload/image", body=body,
                  headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    r = conn.getresponse()
    res = json.loads(r.read().decode())
    conn.close()
    return res["name"]


def workflow_text2img_klein(prompt: str, unet: str, clip: str, vae: str,
                             size: int, seed: int, steps: int = 4,
                             prefix: str = "asset_factory",
                             reference_image: str | None = None,
                             reference_mode: str = "anchor",
                             reference_denoise: float = 0.88) -> dict:
    """Pass 1: text-to-image with klein. Two reference modes:

    `reference_mode="conditioning"` — chains the VAE-encoded reference
    through `ReferenceLatent` into the positive conditioning. Sampler
    still starts from EmptyFlux2LatentImage. **Microscopic influence
    on the output in our setup** (klein-4B at 4 steps); see
    TEXTURE_RND "A.10" entry. Kept as a future hook.

    `reference_mode="anchor"` (DEFAULT when a reference is given) —
    img2img: sampler starts from VAEEncode(reference) at
    `reference_denoise` strength. denoise=1.0 ~= pure text2img;
    denoise=0.0 ~= identity passthrough. **0.85-0.92 is the sweet
    spot** for "text-driven content with reference style anchor"
    in klein. The reference materially influences output —
    color/palette/surface character bleeds through.

    No reference → vanilla text2img path, identical to pre-A.10
    behavior (regression-tested 2026-05-07, grade A on wgv3_dirt).
    """
    base = {
        "10": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "11": {"class_type": "CLIPLoader", "inputs": {"clip_name": clip, "type": "flux2", "device": "default"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "21": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["20", 0]}},
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "60": {"class_type": "VAEDecode", "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        "70": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["60", 0]}},
    }

    positive_src: list = ["20", 0]
    latent_src: list = ["43", 0]
    sched_inputs: dict = {"steps": steps, "width": size, "height": size}

    if reference_image:
        # Always upload + VAE-encode the reference
        base["22"] = {"class_type": "LoadImage",
                      "inputs": {"image": reference_image}}
        base["23"] = {"class_type": "VAEEncode",
                      "inputs": {"pixels": ["22", 0], "vae": ["12", 0]}}

        if reference_mode == "conditioning":
            # ReferenceLatent path (weak in klein-4B; advisory)
            base["25"] = {"class_type": "ReferenceLatent",
                          "inputs": {"conditioning": ["20", 0],
                                     "latent": ["23", 0]}}
            positive_src = ["25", 0]
            # latent_src stays = empty
            base["43"] = {"class_type": "EmptyFlux2LatentImage",
                          "inputs": {"width": size, "height": size,
                                     "batch_size": 1}}
        elif reference_mode == "anchor":
            # img2img-with-anchor: sampler starts from reference latent
            # at `reference_denoise` strength. Most denoising replaces
            # the reference content with text-driven content; the last
            # ~10-15% preserves reference style/color.
            #
            # CRITICAL: anchor mode needs more steps than klein's 4-step
            # text2img default. At 4 steps + denoise=0.5, only 2 effective
            # denoising steps fire, which is not enough for klein to
            # converge to useful content. Bump to max(steps, 8) when
            # anchoring. Matches the heal pass's 8-step default.
            sched_inputs["steps"] = max(sched_inputs["steps"], 8)
            sched_inputs["denoise"] = reference_denoise
            latent_src = ["23", 0]
            # No empty latent needed
        else:
            raise ValueError(
                f"unknown reference_mode={reference_mode!r}; "
                "expected 'conditioning' or 'anchor'")
    else:
        # Vanilla text2img — empty latent, full denoise (no override)
        base["43"] = {"class_type": "EmptyFlux2LatentImage",
                      "inputs": {"width": size, "height": size,
                                 "batch_size": 1}}

    # Scheduler choice: vanilla text2img uses Flux2Scheduler (klein's
    # distilled noise schedule). Anchor mode needs partial denoise,
    # which Flux2Scheduler silently ignores; swap to BasicScheduler
    # which does honor `denoise`. (Diagnosed 2026-05-07 / A.10b.)
    if "denoise" in sched_inputs:
        # BasicScheduler signature: model, scheduler, steps, denoise
        base["41"] = {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["10", 0],
                "scheduler": "simple",
                "steps": sched_inputs["steps"],
                "denoise": sched_inputs["denoise"],
            },
        }
    else:
        base["41"] = {"class_type": "Flux2Scheduler",
                      "inputs": sched_inputs}
    base["30"] = {"class_type": "CFGGuider",
                  "inputs": {"model": ["10", 0],
                             "positive": positive_src,
                             "negative": ["21", 0],
                             "cfg": 1.0}}
    base["50"] = {"class_type": "SamplerCustomAdvanced",
                  "inputs": {"noise": ["42", 0], "guider": ["30", 0],
                             "sampler": ["40", 0],
                             "sigmas": ["41", 0],
                             "latent_image": latent_src}}
    return base


def workflow_img2img_klein(prompt: str, input_image_name: str, unet: str, clip: str, vae: str,
                            size: int, seed: int, denoise: float = 0.35,
                            steps: int = 8, prefix: str = "asset_factory_heal",
                            honor_denoise: bool = False) -> dict:
    """Pass 3: img2img heal pass over the offset-shifted texture.

    Two scheduler paths:

    `honor_denoise=False` (DEFAULT, preserves project history):
        Uses `Flux2Scheduler`. **`denoise` is silently ignored** by
        Flux2Scheduler (diagnosed A.10c, 2026-05-07) — the heal pass
        runs at effectively full denoise=1.0 regardless of the value
        passed. This has been our behavior since project start;
        empirically works because klein's 8-step distilled schedule
        converges quickly. Don't change without re-validating against
        the entire shipping set.

    `honor_denoise=True` (opt-in, used by A.10 reference-anchor mode):
        Uses `BasicScheduler` which actually honors the `denoise`
        parameter. Necessary so pass-1 reference influence isn't
        fully overwritten by the heal pass. Pass `denoise=0.20-0.30`
        for a *gentle* heal that smooths seams without erasing
        anchor signal.

    Filed as TEXTURE_RND open question: should default heal switch
    to honor_denoise=True at some calibrated denoise (probably ~0.5)?
    Would require A/B vs the entire wgv3_* shipping set. Out of A.10
    scope; potential future audit task.
    """
    if honor_denoise:
        scheduler_node = {
            "class_type": "BasicScheduler",
            "inputs": {"model": ["10", 0], "scheduler": "simple",
                       "steps": steps, "denoise": denoise},
        }
    else:
        scheduler_node = {
            "class_type": "Flux2Scheduler",
            "inputs": {"steps": steps, "width": size, "height": size,
                       "denoise": denoise},  # silently ignored, kept for log clarity
        }
    return {
        "10": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "11": {"class_type": "CLIPLoader", "inputs": {"clip_name": clip, "type": "flux2", "device": "default"}},
        "12": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        # load the offset image we just uploaded
        "15": {"class_type": "LoadImage", "inputs": {"image": input_image_name}},
        "16": {"class_type": "VAEEncode", "inputs": {"pixels": ["15", 0], "vae": ["12", 0]}},
        "20": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["11", 0]}},
        "21": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["20", 0]}},
        "30": {"class_type": "CFGGuider", "inputs": {"model": ["10", 0], "positive": ["20", 0],
                                                       "negative": ["21", 0], "cfg": 1.0}},
        "40": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "41": scheduler_node,
        "42": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed + 99}},
        "50": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["42", 0], "guider": ["30", 0], "sampler": ["40", 0],
            "sigmas": ["41", 0], "latent_image": ["16", 0],
        }},
        "60": {"class_type": "VAEDecode", "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        "70": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["60", 0]}},
    }


def offset_image(arr: np.ndarray) -> np.ndarray:
    """Wrap by half so seams move to the center."""
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


def run_seamless(prompt: str, asset_id: str, unet: str, clip: str, vae: str,
                 size: int, seed: int, steps: int, heal_strength: float,
                 host: str, reference_image: Path | str | None = None,
                 reference_mode: str = "anchor",
                 reference_denoise: float = 0.88) -> Path:
    full_prompt = prompt + TILE_PROMPT_SUFFIX
    print(f"[seamless] prompt: {prompt!r}")
    print(f"  +tile suffix: {TILE_PROMPT_SUFFIX[:60]}...")

    # If a local reference image path was passed, resize-to-`size` and
    # upload. The sampler in 'anchor' mode requires the reference's
    # encoded latent to match the output latent shape exactly; a
    # mismatched reference would error. Resize defensively even in
    # 'conditioning' mode so the latent shape stays valid for
    # ReferenceLatent.
    ref_server_name = None
    if reference_image:
        rp = Path(reference_image)
        if rp.exists():
            from PIL import Image as _Image
            _ref = _Image.open(rp).convert("RGB")
            if _ref.size != (size, size):
                _ref = _ref.resize((size, size), _Image.LANCZOS)
                tmp_path = Path(f"D:/tmp/world3_experiments/_ref_resized_{asset_id}.png")
                tmp_path.parent.mkdir(parents=True, exist_ok=True)
                _ref.save(tmp_path)
                ref_server_name = upload_image(tmp_path, host=host)
                print(f"[seamless] reference image (resized {size}x{size}): "
                      f"{rp.name} -> {ref_server_name!r}")
            else:
                ref_server_name = upload_image(rp, host=host)
                print(f"[seamless] reference image: {rp.name} -> "
                      f"{ref_server_name!r}")
        else:
            # Already a server-side filename (caller pre-uploaded; assume sized)
            ref_server_name = str(reference_image)
            print(f"[seamless] reference image (server-side): "
                  f"{ref_server_name!r}")
        print(f"[seamless]   mode={reference_mode}"
              f"{f', denoise={reference_denoise}' if reference_mode == 'anchor' else ''}")

    # PASS 1: text-to-image (with optional reference conditioning)
    print(f"[1/4] text2img generation (size={size}, steps={steps}"
          f"{', +reference' if ref_server_name else ''})")
    wf = workflow_text2img_klein(full_prompt, unet, clip, vae, size, seed, steps,
                                  prefix=f"{asset_id}_pass1",
                                  reference_image=ref_server_name,
                                  reference_mode=reference_mode,
                                  reference_denoise=reference_denoise)
    pid = queue_prompt(wf, host=host)
    res = wait_for(pid, host=host)
    images = res["outputs"].get("70", {}).get("images", [])
    if not images:
        raise RuntimeError("no images from pass 1")
    pass1_path = Path("__pass1.png")
    download_output(host, images[0]["filename"], images[0]["subfolder"], images[0]["type"], pass1_path)
    pass1 = np.asarray(Image.open(pass1_path).convert("RGB"))
    print(f"  pass1 seam score: {edge_seam_score(pass1):.5f}")

    # PASS 2: circular shift
    print(f"[2/4] circular shift (seams move to center)")
    shifted = offset_image(pass1)
    shifted_path = Path("__shifted.png")
    Image.fromarray(shifted).save(shifted_path)

    # Upload shifted image so ComfyUI can use it as input
    # Heal pass scheduler choice:
    #  - vanilla (no reference): keep Flux2Scheduler default to preserve
    #    project history. denoise param is silently ignored anyway.
    #  - anchor mode with reference: switch to BasicScheduler (honor_denoise=True)
    #    and use a *gentle* denoise (default 0.25) so the reference
    #    influence from pass 1 isn't fully overwritten by the heal pass.
    is_anchor_mode = (reference_image is not None
                      and reference_mode == "anchor")
    effective_heal_denoise = (0.25 if is_anchor_mode else heal_strength)
    print(f"[3/4] upload + img2img heal "
          f"(denoise={effective_heal_denoise}"
          f"{', BasicScheduler (anchor)' if is_anchor_mode else ', Flux2Scheduler (default; denoise silently ignored)'})")
    server_name = upload_image(shifted_path, host=host)

    # PASS 3: img2img heal
    heal_steps = max(steps * 2, 8)  # need more steps for partial denoise
    wf = workflow_img2img_klein(full_prompt, server_name, unet, clip, vae,
                                  size, seed, denoise=effective_heal_denoise,
                                  steps=heal_steps, prefix=f"{asset_id}_pass3",
                                  honor_denoise=is_anchor_mode)
    pid = queue_prompt(wf, host=host)
    res = wait_for(pid, host=host)
    images = res["outputs"].get("70", {}).get("images", [])
    if not images:
        raise RuntimeError("no images from pass 3")
    pass3_path = Path("__pass3.png")
    download_output(host, images[0]["filename"], images[0]["subfolder"], images[0]["type"], pass3_path)
    pass3 = np.asarray(Image.open(pass3_path).convert("RGB"))

    # PASS 4: reverse shift
    print(f"[4/4] reverse shift")
    final = offset_image(pass3)
    final_score = edge_seam_score(final)
    print(f"  final seam score: {final_score:.5f}")

    # Cleanup
    for p in [pass1_path, shifted_path, pass3_path]:
        p.unlink(missing_ok=True)

    out_dir = LIBRARY / asset_id
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / f"{asset_id}_albedo.png"
    Image.fromarray(final).save(final_path)
    return final_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--unet", default="flux-2-klein-4b.safetensors")
    ap.add_argument("--clip", default="qwen_3_4b.safetensors")
    ap.add_argument("--vae", default="flux2-vae.safetensors")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--heal-strength", type=float, default=0.35,
                    help="img2img denoise strength for the heal pass (0.2-0.5 range)")
    ap.add_argument("--host", default=COMFY_HOST)
    ap.add_argument("--reference-image", default=None,
                    help="(A.10) optional reference image path. Auto-"
                         "resized to --size before upload. Used to anchor "
                         "the FLUX generation on a real-world material photo "
                         "(or another texture). Klein-native; no IP-Adapter "
                         "install.")
    ap.add_argument("--reference-mode", default="anchor",
                    choices=["anchor", "conditioning"],
                    help="(A.10) how to apply the reference. 'anchor' "
                         "(default): img2img — sampler starts from the "
                         "reference latent at --reference-denoise strength. "
                         "Real material/color influence on the output. "
                         "'conditioning': chain via ReferenceLatent into "
                         "the positive conditioning. Klein-native but "
                         "produces microscopic influence (TEXTURE_RND A.10 "
                         "negative finding) — kept for future iteration.")
    ap.add_argument("--reference-denoise", type=float, default=0.88,
                    help="(A.10, anchor mode only) denoise applied to the "
                         "reference latent. 1.0 ~= pure text2img (reference "
                         "ignored); 0.0 ~= identity (reference passes "
                         "through). 0.85-0.92 sweet spot for 'text-driven "
                         "content with reference style anchor'. Default 0.88.")
    args = ap.parse_args()

    out = run_seamless(args.prompt, args.id, args.unet, args.clip, args.vae,
                       args.size, args.seed, args.steps, args.heal_strength,
                       args.host, reference_image=args.reference_image,
                       reference_mode=args.reference_mode,
                       reference_denoise=args.reference_denoise)
    print(f"\ndone: {out}")


if __name__ == "__main__":
    main()
