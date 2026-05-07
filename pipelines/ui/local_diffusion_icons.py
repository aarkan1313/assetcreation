"""Local FLUX.1 [schnell] icon generator (Apache-2.0, commercially shippable).

Per research D §1: FLUX.1 [schnell] is the **only** FLUX variant with a
commercial-OK license (Apache-2.0). FLUX.1 [dev] and [Krea-dev] are
non-commercial. This adapter HARD-FORBIDS [dev] checkpoints unless the user
passes --i-know-its-non-commercial (intended for prototype-only runs).

GPU-deferred: the actual model load is heavy (~24 GB VRAM in bf16) and the
5090 is reserved. Default mode (`--plan`) writes a "diffusion plan" JSON
listing the prompts, seeds, params, and the LoRA selection without touching
the GPU. When the GPU is free, run with `--run` to actually invoke
diffusers.

Slot-compatible with the rest of the pipeline: writes the same manifest
schema as openai_icons.py / synth_icons.py / freelib_ingest.py, so the
exporter consumes its output unchanged.

CLI:
  # Plan-only (no GPU). Always safe to run.
  python local_diffusion_icons.py --prompts ui/prompts.json --plan

  # Real run (requires diffusers + cu128 + a free GPU)
  python local_diffusion_icons.py --prompts ui/prompts.json --run

  # With LoRA
  python local_diffusion_icons.py --prompts ui/prompts.json --run \
      --lora <path/to/icon-lora.safetensors> --lora-weight 0.85
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

ASSETS = Path(r"D:\assets")
sys.path.insert(0, str(ASSETS))
ICONS_DIR = ASSETS / "ui" / "icons"
PLAN_DIR = ASSETS / "ui" / "diffusion_plans"
DEFAULT_COMFY_WORKFLOW = ASSETS / "pipelines" / "_meta" / "comfy_workflows" / "flux_schnell_ipadapter_iconset.json"

from pipelines._meta.comfy_runner import ComfyError, ComfyRunner  # noqa: E402


# -- License gate ----------------------------------------------------------

SCHNELL_MODEL_ID = "black-forest-labs/FLUX.1-schnell"
KREA_DEV_ID = "black-forest-labs/FLUX.1-Krea-dev"
DEV_MODEL_ID = "black-forest-labs/FLUX.1-dev"

NON_COMMERCIAL_IDS = {DEV_MODEL_ID, KREA_DEV_ID}

LICENSE_NOTE = (
    "FLUX.1 [schnell] is Apache-2.0 (commercial use OK). "
    "FLUX.1 [dev] and FLUX.1 [Krea-dev] are non-commercial; do NOT ship outputs."
)


# -- Style brief (matches openai_icons.py phrasing) -----------------------

STYLE_BRIEF = (
    "centered single subject, flat-shaded fantasy game icon, dark thin "
    "outline, muted earthy palette with one accent color, transparent "
    "background or single-color flat background, no text, no watermark, "
    "the icon should read clearly at 64x64 px"
)


# -- Plan-only path (CPU; always available) -------------------------------

def build_plan(specs: list[dict], *,
               model_id: str = SCHNELL_MODEL_ID,
               size: int = 1024,
               steps: int = 4,
               guidance: float = 0.0,
               seed_base: int = 1000,
               lora: str | None = None,
               lora_weight: float = 1.0,
               style_brief: str = STYLE_BRIEF) -> dict:
    """Materialize a diffusion plan: every parameter the GPU run would use,
    in JSON form, ready to feed --run later. Pure CPU, no diffusers import.
    """
    if model_id in NON_COMMERCIAL_IDS:
        raise ValueError(
            f"local_diffusion_icons: refusing to plan with {model_id!r}; "
            "non-commercial license. Use FLUX.1 [schnell] or pass "
            "--i-know-its-non-commercial.")
    return {
        "model_id": model_id,
        "license": "Apache-2.0" if model_id == SCHNELL_MODEL_ID
                    else "FLUX.1 license; verify before shipping",
        "size_px": size,
        "steps": steps,
        "guidance_scale": guidance,
        "lora": lora,
        "lora_weight": lora_weight,
        "style_brief": style_brief,
        "seed_base": seed_base,
        "icons": [
            {
                "id": s["id"],
                "prompt": f"{s['prompt']}. {style_brief}",
                "seed": seed_base + i,
                "negative_prompt": s.get("negative_prompt"),
                "size_px": size,
                "steps": steps,
                "guidance_scale": guidance,
            }
            for i, s in enumerate(specs)
        ],
    }


def write_plan(plan: dict, plan_path: Path) -> None:
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def build_comfy_plan(specs: list[dict], *,
                     workflow: Path = DEFAULT_COMFY_WORKFLOW,
                     host: str = "http://127.0.0.1:8188",
                     output_node: str = "9",
                     model_id: str = SCHNELL_MODEL_ID,
                     size: int = 1024,
                     steps: int = 4,
                     guidance: float = 1.0,
                     seed_base: int = 1000,
                     style_image: str | None = None,
                     style_weight: float = 0.65,
                     style_brief: str = STYLE_BRIEF) -> dict:
    if model_id in NON_COMMERCIAL_IDS:
        raise ValueError(
            f"local_diffusion_icons: refusing comfy plan with {model_id!r}; "
            f"use {SCHNELL_MODEL_ID!r} for shippable icon output."
        )
    icons = []
    for i, spec in enumerate(specs):
        seed = seed_base + i
        prompt = f"{spec['prompt']}. {style_brief}"
        icons.append({
            "id": spec["id"],
            "prompt": prompt,
            "negative_prompt": spec.get("negative_prompt", "text, watermark, blurry, cropped, low contrast"),
            "seed": seed,
            "overrides": {
                "2.inputs.image": Path(style_image).name if style_image else "style_reference.png",
                "3.inputs.weight": style_weight,
                "4.inputs.text": prompt,
                "5.inputs.text": spec.get("negative_prompt", "text, watermark, blurry, cropped, low contrast"),
                "6.inputs.width": size,
                "6.inputs.height": size,
                "7.inputs.seed": seed,
                "7.inputs.steps": steps,
                "7.inputs.cfg": guidance,
                "9.inputs.filename_prefix": f"phase9_icon_{spec['id']}",
            },
        })
    return {
        "backend": "comfy_flux_schnell_ipadapter",
        "model_id": model_id,
        "license": "Apache-2.0",
        "workflow": str(workflow),
        "host": host,
        "output_node": output_node,
        "style_image": style_image,
        "style_weight": style_weight,
        "size_px": size,
        "steps": steps,
        "guidance_scale": guidance,
        "seed_base": seed_base,
        "required_custom_nodes": [
            "ComfyUI_IPAdapter_plus or compatible IP-Adapter/InstantStyle nodes"
        ],
        "icons": icons,
    }


# -- Run path (GPU; lazy import of diffusers) -----------------------------

def run_plan(plan: dict, out_dir: Path, *,
             allow_non_commercial: bool = False) -> list[dict]:
    """Execute a plan against a real GPU diffuser. Lazy-imports diffusers so
    plan-only mode never pulls heavy deps."""
    if plan["model_id"] in NON_COMMERCIAL_IDS and not allow_non_commercial:
        raise RuntimeError(
            f"refusing to run {plan['model_id']!r} without "
            "--i-know-its-non-commercial; outputs are NOT commercially shippable.")

    try:
        import torch  # type: ignore
        from diffusers import FluxPipeline  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "local_diffusion_icons --run requires diffusers + torch (cu128 wheel). "
            "Install: pip install diffusers transformers accelerate sentencepiece "
            "torch --index-url https://download.pytorch.org/whl/cu128") from e

    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    pipe = FluxPipeline.from_pretrained(plan["model_id"], torch_dtype=dtype)
    if torch.cuda.is_available():
        pipe = pipe.to("cuda")
    else:
        # Schnell can run on CPU but it's slow (~2-5 min/icon); print a warning.
        print("[local_diffusion_icons] WARNING: no CUDA detected, running on CPU. "
              "This is ~50x slower; consider --plan instead.")
    if plan.get("lora"):
        pipe.load_lora_weights(
            plan["lora"], weight_name=None,
            adapter_name="icon_lora",
        )
        # cross-attention scale via diffusers cross_attention_kwargs
        pipe.set_adapters(["icon_lora"], adapter_weights=[plan.get("lora_weight", 1.0)])

    out_dir.mkdir(parents=True, exist_ok=True)
    icons: list[dict] = []
    for spec in plan["icons"]:
        gen = torch.Generator(device="cuda" if torch.cuda.is_available() else "cpu")
        gen.manual_seed(int(spec["seed"]))
        result = pipe(
            spec["prompt"],
            negative_prompt=spec.get("negative_prompt"),
            num_inference_steps=spec["steps"],
            guidance_scale=spec["guidance_scale"],
            height=spec["size_px"], width=spec["size_px"],
            generator=gen,
        )
        img = result.images[0]
        png_path = out_dir / f"{spec['id']}.png"
        img.save(png_path)
        icons.append({
            "id": spec["id"],
            "path": str(png_path.relative_to(ASSETS).as_posix()),
            "size_px": spec["size_px"],
            "backend": "flux_schnell_local",
            "model": plan["model_id"],
            "prompt": spec["prompt"],
            "seed": spec["seed"],
            "lora": plan.get("lora"),
            "lora_weight": plan.get("lora_weight"),
            "license": plan["license"],
        })
        print(f"[local_diffusion_icons] {spec['id']:24s} seed={spec['seed']} "
              f"-> {png_path.name}")
    return icons


def run_comfy_plan(plan: dict, out_dir: Path) -> list[dict]:
    runner = ComfyRunner(plan.get("host", "http://127.0.0.1:8188"))
    workflow = Path(plan["workflow"])
    style_image = Path(plan["style_image"]) if plan.get("style_image") else None
    uploaded_style_name: str | None = None
    if style_image:
        uploaded_style_name = runner.upload_image(style_image, name=f"phase9_style_{style_image.name}")
    elif any("IPAdapter" in item for item in plan.get("required_custom_nodes", [])):
        raise RuntimeError("--backend comfy run needs --style-image for the IP-Adapter iconset workflow")

    icons: list[dict] = []
    for spec in plan["icons"]:
        overrides = dict(spec["overrides"])
        if uploaded_style_name:
            overrides["2.inputs.image"] = uploaded_style_name
        icon_raw_dir = out_dir / "_comfy_raw" / spec["id"]
        result = runner.run(
            workflow_path=workflow,
            overrides=overrides,
            output_node_ids=[str(plan["output_node"])],
            out_dir=icon_raw_dir,
            dry_run=False,
            validate_nodes=True,
            timeout_s=600.0,
            poll_s=1.5,
        )
        if not result.downloaded:
            raise RuntimeError(f"ComfyUI completed without downloaded outputs for icon {spec['id']}")
        src = Path(result.downloaded[0].local_path)
        png_path = out_dir / f"{spec['id']}{src.suffix or '.png'}"
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, png_path)
        icons.append({
            "id": spec["id"],
            "path": str(png_path.relative_to(ASSETS).as_posix()),
            "size_px": plan["size_px"],
            "backend": "comfy_flux_schnell_ipadapter",
            "model": plan["model_id"],
            "prompt": spec["prompt"],
            "seed": spec["seed"],
            "style_image": plan.get("style_image"),
            "style_weight": plan.get("style_weight"),
            "license": plan["license"],
            "comfy_result": asdict(result),
        })
        print(f"[local_diffusion_icons] comfy {spec['id']:24s} seed={spec['seed']} -> {png_path.name}")
    return icons


# -- Manifest --------------------------------------------------------------

def merge_into_manifest(manifest_path: Path, new_icons: list[dict],
                        size: int) -> None:
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        m = {"set": "flux_schnell", "size": size, "icons": []}
    by_id = {e["id"]: e for e in m.get("icons", [])}
    for e in new_icons:
        by_id[e["id"]] = e
    m["icons"] = sorted(by_id.values(), key=lambda x: x["id"])
    m["size"] = size
    manifest_path.write_text(json.dumps(m, indent=2), encoding="utf-8")


# -- CLI -------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", type=Path, required=True,
                    help="JSON list of {id, prompt[, negative_prompt]}.")
    ap.add_argument("--backend", choices=("diffusers", "comfy"), default="diffusers",
                    help="diffusers keeps the original direct FLUX path; comfy uses comfy_runner + IP-Adapter workflow.")
    ap.add_argument("--model-id", default=SCHNELL_MODEL_ID,
                    help=f"HF model id. Default: {SCHNELL_MODEL_ID} (Apache-2.0).")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=4,
                    help="schnell is 1-4 step distilled; default 4.")
    ap.add_argument("--guidance", type=float, default=0.0,
                    help="schnell uses guidance=0 by design.")
    ap.add_argument("--seed-base", type=int, default=1000,
                    help="seed of first prompt; subsequent prompts increment.")
    ap.add_argument("--lora", default=None,
                    help="Path to a LoRA .safetensors (icon-style).")
    ap.add_argument("--lora-weight", type=float, default=1.0)
    ap.add_argument("--out", type=Path, default=ICONS_DIR)
    ap.add_argument("--plan", action="store_true",
                    help="Write a diffusion plan JSON only; do not invoke GPU.")
    ap.add_argument("--run", action="store_true",
                    help="Actually run diffusers (requires GPU + diffusers).")
    ap.add_argument("--plan-out", type=Path, default=None,
                    help="Path for the plan JSON (default: ui/diffusion_plans/<stem>.plan.json).")
    ap.add_argument("--comfy-host", default="http://127.0.0.1:8188")
    ap.add_argument("--workflow", type=Path, default=DEFAULT_COMFY_WORKFLOW)
    ap.add_argument("--output-node", default="9")
    ap.add_argument("--style-image", type=Path, default=None,
                    help="Style/reference image for the Comfy IP-Adapter lane.")
    ap.add_argument("--style-weight", type=float, default=0.65)
    ap.add_argument("--i-know-its-non-commercial", action="store_true",
                    help="Acknowledge that outputs from FLUX.1 [dev] / [Krea-dev] "
                         "cannot be shipped commercially.")
    args = ap.parse_args()

    print(f"[local_diffusion_icons] {LICENSE_NOTE}")

    if args.model_id in NON_COMMERCIAL_IDS and not args.i_know_its_non_commercial:
        print(f"[local_diffusion_icons] ERROR: {args.model_id!r} is non-commercial; "
              f"use {SCHNELL_MODEL_ID!r} (Apache-2.0) or pass "
              "--i-know-its-non-commercial.", file=sys.stderr)
        return 2

    specs = json.loads(args.prompts.read_text(encoding="utf-8"))
    if not isinstance(specs, list):
        raise SystemExit("--prompts must be a JSON array of {id, prompt}")

    if args.backend == "comfy":
        plan = build_comfy_plan(
            specs,
            workflow=args.workflow,
            host=args.comfy_host,
            output_node=args.output_node,
            model_id=args.model_id,
            size=args.size,
            steps=args.steps,
            guidance=args.guidance if args.guidance != 0.0 else 1.0,
            seed_base=args.seed_base,
            style_image=str(args.style_image) if args.style_image else None,
            style_weight=args.style_weight,
        )
    else:
        plan = build_plan(specs,
                          model_id=args.model_id, size=args.size,
                          steps=args.steps, guidance=args.guidance,
                          seed_base=args.seed_base,
                          lora=args.lora, lora_weight=args.lora_weight)

    if not args.run:
        # default to plan-only
        plan_path = args.plan_out or (PLAN_DIR / f"{args.prompts.stem}.plan.json")
        write_plan(plan, plan_path)
        print(f"[local_diffusion_icons] PLAN written -> {plan_path}")
        print(f"[local_diffusion_icons] {len(plan['icons'])} icons planned. "
              "Pass --run when GPU is free.")
        return 0

    try:
        if args.backend == "comfy":
            icons = run_comfy_plan(plan, args.out)
        else:
            icons = run_plan(plan, args.out,
                             allow_non_commercial=args.i_know_its_non_commercial)
    except (ComfyError, RuntimeError, OSError) as exc:
        print(f"[local_diffusion_icons] FAILED: {exc}", file=sys.stderr)
        return 1
    manifest = args.out / "manifest.json"
    merge_into_manifest(manifest, icons, size=args.size)
    print(f"[local_diffusion_icons] {len(icons)} icons -> {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
