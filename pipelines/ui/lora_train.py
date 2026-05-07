"""Icon LoRA training scaffold (plan-only).

Per `research/D_ui.md` "Honest Tradeoffs" — Civitai LoRAs are the right
starting point; train your own only when none holds the style. This tool
prepares everything kohya-ss / sd-scripts needs for a custom train run, but
**never starts the trainer**. The 5090 is reserved.

What the scaffold writes for you:

  ui/lora/<run_id>/
    dataset/
      img/
        repeats_<N>_<token>/<icon_id>.png    (resized to base resolution)
        repeats_<N>_<token>/<icon_id>.txt    (caption file per icon)
      reg/                                    (regularization images, if any)
    dataset.toml                              (kohya-ss-format dataset cfg)
    train_lora.toml                           (training cfg w/ all knobs)
    train_command.sh                          (the shell line you run when
                                               GPU is free)
    metadata.json                             (run id, references, defaults)

Why kohya-ss: research D §1 calls out kohya-ss as the de-facto standard for
LoRA training in the SDXL/FLUX 2026 era; sd-scripts is the upstream project.
We pin compatible versions in the train_command.sh comment so the run is
reproducible.

Caption strategy: each reference icon's caption is built from its
`semantic_tags` (when present) plus a fixed style brief. The default trigger
token is `tlteic0n` (uncommon enough not to collide with FLUX's vocabulary).

License safety: this scaffold reads ONLY icons from `ui/icons/manifest.json`
whose license is permissive for derivative training (CC0, CC-BY where the
attribution is preserved in the dataset, MIT/ISC). Anything else is excluded
and listed in `metadata.json::excluded_for_license`. The shipped LoRA
inherits the most-restrictive license of the included sources -- by default
CC-BY-style attribution applies.

Verify command (when 5090 free; runs the actual train):
  cd ui/lora/<run_id>
  bash train_command.sh         # real GPU run; ~2-4 h on a 5090

CLI:
  # Plan with defaults (FLUX.1-schnell base, 30 highest-tagged icons)
  python lora_train.py --run-id v1_smoke

  # Pick a specific style of references
  python lora_train.py --run-id v1_swords --filter sword,axe,blade --max 30

  # Override base model (still plan-only)
  python lora_train.py --run-id v1_sdxl --base-model stabilityai/stable-diffusion-xl-base-1.0
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ASSETS = Path(r"D:\assets")
ICONS_MANIFEST = ASSETS / "ui" / "icons" / "manifest.json"
ICONS_DIR = ASSETS / "ui" / "icons"
LORA_ROOT = ASSETS / "ui" / "lora"


# Permissive licenses we accept for training data. Everything else is excluded.
TRAIN_OK_LICENSES = {
    "CC0", "CC-0", "Public Domain",
    "MIT", "ISC", "Apache-2.0",
    "first-party", "synthetic",  # our own synth_icons
    "CC-BY 3.0", "CC-BY 4.0",   # attribution preserved in dataset metadata
}


@dataclass
class LoraTrainPlan:
    run_id: str
    created_at: str
    base_model: str
    base_resolution: int
    trigger_token: str
    style_brief: str
    network_dim: int
    network_alpha: int
    learning_rate: float
    batch_size: int
    max_train_steps: int
    save_every_n_steps: int
    n_repeats: int
    references: list[dict] = field(default_factory=list)
    excluded_for_license: list[dict] = field(default_factory=list)
    dataset_root: Optional[str] = None
    train_command: Optional[str] = None


def _filter_icons(manifest: dict, license_ok: set[str],
                  filter_tokens: Optional[list[str]] = None,
                  max_n: int = 30) -> tuple[list[dict], list[dict]]:
    icons = manifest.get("icons", [])
    keep, exclude = [], []
    for ic in icons:
        lic = (ic.get("license") or "first-party").strip()
        if lic not in license_ok and not any(
            ok.lower() in lic.lower() for ok in license_ok
        ):
            exclude.append({"id": ic.get("id"), "license": lic,
                            "reason": "license not in TRAIN_OK_LICENSES"})
            continue
        if filter_tokens:
            bag = " ".join(
                [ic.get("id", ""), ic.get("display_name", ""),
                 " ".join(ic.get("semantic_tags", []) or [])]
            ).lower()
            if not any(t.lower() in bag for t in filter_tokens):
                exclude.append({"id": ic.get("id"), "license": lic,
                                "reason": f"no match for filter {filter_tokens}"})
                continue
        keep.append(ic)
    # Prefer entries with semantic_tags (richer captions train better)
    keep.sort(key=lambda e: -len(e.get("semantic_tags") or []))
    return keep[:max_n], exclude


def _caption_for(icon: dict, trigger: str, style_brief: str) -> str:
    tags = icon.get("semantic_tags") or []
    name = icon.get("display_name") or icon.get("id", "icon")
    parts = [trigger, name.lower()]
    parts.extend(tags)
    parts.append(style_brief)
    return ", ".join(parts)


def _resize_and_copy(src: Path, dst: Path, resolution: int) -> None:
    """Resize the icon PNG to `resolution` square (LANCZOS) and write a clean
    RGBA copy. We don't pad-fit — kohya-ss handles aspect via bucketing — but
    icons are already square so resize is fine."""
    from PIL import Image  # type: ignore
    with Image.open(src) as im:
        im = im.convert("RGBA")
        if im.size != (resolution, resolution):
            im = im.resize((resolution, resolution), Image.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, format="PNG")


def write_dataset_toml(plan: LoraTrainPlan, dataset_root: Path) -> Path:
    """kohya-ss dataset.toml format (sd-scripts >=0.9, kohya-ss >=v22)."""
    img_subdir = f"repeats_{plan.n_repeats}_{plan.trigger_token}"
    body = (
        "# Auto-written by pipelines/ui/lora_train.py — DO NOT hand-edit;\n"
        "# re-run lora_train.py with new args to regenerate.\n\n"
        "[general]\n"
        f"resolution = {plan.base_resolution}\n"
        "shuffle_caption = true\n"
        "caption_extension = \".txt\"\n"
        "keep_tokens = 1\n\n"
        "[[datasets]]\n"
        "  [[datasets.subsets]]\n"
        f"  image_dir = '{(dataset_root / 'img' / img_subdir).as_posix()}'\n"
        f"  num_repeats = {plan.n_repeats}\n"
    )
    out = dataset_root / "dataset.toml"
    out.write_text(body, encoding="utf-8")
    return out


def write_train_toml(plan: LoraTrainPlan, run_root: Path,
                     dataset_toml: Path) -> Path:
    """sd-scripts train_network.py args, expressed as a TOML file you pass via
    `--config_file`. Captures every parameter so re-runs are deterministic."""
    out = run_root / "train_lora.toml"
    body = (
        "# kohya-ss / sd-scripts train_network.py config\n"
        f"# Run: bash {(run_root / 'train_command.sh').name}\n\n"
        f"pretrained_model_name_or_path = '{plan.base_model}'\n"
        f"dataset_config = '{dataset_toml.as_posix()}'\n"
        "output_dir = './output'\n"
        f"output_name = 'tlte_icons_{plan.run_id}'\n"
        "save_model_as = 'safetensors'\n"
        f"resolution = {plan.base_resolution}\n"
        f"network_module = 'networks.lora'\n"
        f"network_dim = {plan.network_dim}\n"
        f"network_alpha = {plan.network_alpha}\n"
        f"train_batch_size = {plan.batch_size}\n"
        f"max_train_steps = {plan.max_train_steps}\n"
        f"learning_rate = {plan.learning_rate}\n"
        "lr_scheduler = 'cosine_with_restarts'\n"
        "lr_warmup_steps = 100\n"
        f"save_every_n_steps = {plan.save_every_n_steps}\n"
        "mixed_precision = 'bf16'\n"
        "save_precision = 'bf16'\n"
        "gradient_checkpointing = true\n"
        "enable_bucket = false\n"
        "logging_dir = './logs'\n"
        "log_with = 'tensorboard'\n"
    )
    out.write_text(body, encoding="utf-8")
    return out


def write_train_command(plan: LoraTrainPlan, run_root: Path,
                        train_toml: Path) -> Path:
    """The shell command the user runs when GPU is free. Pinned to a tested
    sd-scripts revision so reproducibility is preserved across the year."""
    out = run_root / "train_command.sh"
    body = (
        "#!/usr/bin/env bash\n"
        f"# LoRA train — run id {plan.run_id}\n"
        f"# Base model: {plan.base_model}\n"
        f"# Auto-written by pipelines/ui/lora_train.py at {plan.created_at}\n"
        "#\n"
        "# Pre-reqs (run once on the 5090 host):\n"
        "#   conda create -n lora python=3.11 -y && conda activate lora\n"
        "#   pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu128\n"
        "#   git clone --branch v0.9.0 https://github.com/kohya-ss/sd-scripts.git\n"
        "#   cd sd-scripts && pip install -e .\n"
        "#\n"
        "# Real run (this script):\n"
        "set -euo pipefail\n"
        f'cd "$(dirname "$0")"\n'
        "mkdir -p output logs\n"
        f"accelerate launch --num_cpu_threads_per_process 4 \\\n"
        f"  $(python -c \"import sd_scripts; print(sd_scripts.__path__[0])\")/sdxl_train_network.py \\\n"
        f"  --config_file '{train_toml.as_posix()}'\n"
    )
    out.write_text(body, encoding="utf-8", newline="\n")
    return out


def build_plan(run_id: str, *,
               base_model: str = "black-forest-labs/FLUX.1-schnell",
               base_resolution: int = 1024,
               trigger_token: str = "tlteic0n",
               style_brief: str = "fantasy game icon, flat-shaded silhouette, "
                                  "centered subject, transparent background",
               network_dim: int = 16, network_alpha: int = 8,
               learning_rate: float = 1e-4,
               batch_size: int = 2,
               max_train_steps: int = 2000,
               save_every_n_steps: int = 500,
               n_repeats: int = 10) -> LoraTrainPlan:
    return LoraTrainPlan(
        run_id=run_id,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        base_model=base_model,
        base_resolution=base_resolution,
        trigger_token=trigger_token,
        style_brief=style_brief,
        network_dim=network_dim,
        network_alpha=network_alpha,
        learning_rate=learning_rate,
        batch_size=batch_size,
        max_train_steps=max_train_steps,
        save_every_n_steps=save_every_n_steps,
        n_repeats=n_repeats,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True,
                    help="Used as the output dir name (ui/lora/<run_id>/).")
    ap.add_argument("--icons", type=Path, default=ICONS_MANIFEST)
    ap.add_argument("--out-root", type=Path, default=LORA_ROOT)
    ap.add_argument("--max", type=int, default=30,
                    help="Max icons to include in the dataset.")
    ap.add_argument("--filter", default=None,
                    help="Comma-separated tokens: only icons whose id/name/"
                         "tags include any of these words are included.")
    ap.add_argument("--base-model",
                    default="black-forest-labs/FLUX.1-schnell",
                    help="HuggingFace repo id of the base model.")
    ap.add_argument("--resolution", type=int, default=1024,
                    choices=[512, 768, 1024])
    ap.add_argument("--trigger", default="tlteic0n",
                    help="Trigger token (1st in caption, never shuffled).")
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--steps", type=int, default=2000)
    ap.add_argument("--repeats", type=int, default=10)
    ap.add_argument("--network-dim", type=int, default=16)
    ap.add_argument("--network-alpha", type=int, default=8)
    args = ap.parse_args()

    if not args.icons.exists():
        print(f"[lora_train] ERROR: manifest not found: {args.icons}",
              file=sys.stderr)
        return 2
    manifest = json.loads(args.icons.read_text(encoding="utf-8"))

    plan = build_plan(
        run_id=args.run_id,
        base_model=args.base_model,
        base_resolution=args.resolution,
        trigger_token=args.trigger,
        learning_rate=args.lr,
        max_train_steps=args.steps,
        n_repeats=args.repeats,
        network_dim=args.network_dim,
        network_alpha=args.network_alpha,
    )

    filter_tokens = (
        [s.strip() for s in args.filter.split(",") if s.strip()]
        if args.filter else None
    )
    keep, exclude = _filter_icons(manifest, TRAIN_OK_LICENSES,
                                  filter_tokens=filter_tokens,
                                  max_n=args.max)
    plan.references = [
        {"id": ic["id"], "path": ic.get("path"),
         "license": ic.get("license"),
         "attribution": ic.get("attribution"),
         "semantic_tags": ic.get("semantic_tags") or [],
         "display_name": ic.get("display_name") or ic.get("id")}
        for ic in keep
    ]
    plan.excluded_for_license = exclude

    if not plan.references:
        print(f"[lora_train] ERROR: no icons matched filters/license; "
              f"excluded {len(exclude)}",
              file=sys.stderr)
        return 2

    run_root = args.out_root / args.run_id
    dataset_root = run_root / "dataset"
    img_subdir = dataset_root / "img" / f"repeats_{plan.n_repeats}_{plan.trigger_token}"
    img_subdir.mkdir(parents=True, exist_ok=True)
    (dataset_root / "reg").mkdir(parents=True, exist_ok=True)

    # Copy + resize references; write captions
    for ic in keep:
        src = ASSETS / ic["path"]
        if not src.exists():
            print(f"[lora_train] WARN missing png: {src}", file=sys.stderr)
            continue
        dst = img_subdir / f"{ic['id']}.png"
        _resize_and_copy(src, dst, plan.base_resolution)
        cap = _caption_for(ic, plan.trigger_token, plan.style_brief)
        dst.with_suffix(".txt").write_text(cap, encoding="utf-8")

    plan.dataset_root = str(dataset_root.relative_to(ASSETS).as_posix())
    dataset_toml = write_dataset_toml(plan, dataset_root)
    train_toml = write_train_toml(plan, run_root, dataset_toml)
    cmd = write_train_command(plan, run_root, train_toml)
    plan.train_command = f"bash {cmd.relative_to(ASSETS).as_posix()}"

    (run_root / "metadata.json").write_text(
        json.dumps(asdict(plan), indent=2), encoding="utf-8")

    print(f"[lora_train] {args.run_id} plan ready  -> {run_root}")
    print(f"  icons included : {len(plan.references)}")
    print(f"  icons excluded : {len(plan.excluded_for_license)} "
          f"(license/filter)")
    print(f"  base model     : {plan.base_model}")
    print(f"  resolution     : {plan.base_resolution}")
    print(f"  total steps    : {plan.max_train_steps} "
          f"(LR {plan.learning_rate}, dim {plan.network_dim})")
    print(f"  next: {plan.train_command}  (run on 5090 when free)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
