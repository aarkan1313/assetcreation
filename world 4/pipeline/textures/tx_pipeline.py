"""W4 tx_pipeline — texture orchestrator (replaces aaa_texture.py for W4).

Wires the W4 texture stages together with no silent defaults, no
hidden side effects, no flat library writes. Caller specifies output
dir, prompt, knobs; we generate variants, derive PBR, run QA, emit
a structured manifest.

Pipeline shape (per the 2026-05-12 audit):

  prompt
    ↓
  Stage 1: tx_seamless (4-pass FLUX, honored heal-denoise)
    ↓ run N times → tx_variant_select → ranked list (all kept)
  Stage 2: [optional] delight — DISABLED by default per audit
    ↓
  Stage 3: PBR backend (tx_pbr_derive default, tx_pbr_sm opt-in)
    ↓
  Stage 4: [optional] external seam_repair — DISABLED unless FLUX heal failed
    ↓
  Stage 5: tx_qa (3 base + mip32_stdev + advisory)
    ↓
  Stage 6: emit manifest

Output directory layout per candidate:
  <out_dir>/
    albedo.png  normal.png  roughness.png  ao.png  height.png  metallic.png
    qa.json
    manifest.json    ← prompt, settings, all stage logs, final grade
    variants/        ← all N raw FLUX outputs (the audit fix: keep all)
      v0_albedo.png  v1_albedo.png  ...
      ranking.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

# W4 modules
from tx_variant_select import generate_variants
from tx_pbr_derive import derive_pbr as derive_pbr_heuristic
from tx_qa import qa_albedo


@dataclass
class PipelineSettings:
    """All pipeline knobs, no silent defaults.

    The audit's findings drive these defaults:
      - heal_denoise=0.35 honored (vs upstream's silent 1.0)
      - delight=0.0 (skip; prompt already requests flat lighting)
      - pbr_backend='derive' (consistent with albedo, not SM-invented)
      - external_seam_repair=False (the FLUX heal is the seam repair)
    """
    # Generation
    unet: str = "flux-2-klein-9b-fp8.safetensors"
    clip: str = "qwen_3_8b_fp8mixed.safetensors"
    vae: str = "flux2-vae.safetensors"
    size: int = 1024
    steps: int = 4
    seed_base: int = 42
    variants: int = 4

    # Heal pass — the audit's biggest find
    heal_denoise: float = 0.35
    heal_mode: str = "flux_heal"  # 'flux_heal' or 'none'

    # Delight — off by default; prompt handles lighting
    delight_strength: float = 0.0

    # PBR backend
    pbr_backend: str = "derive"  # 'derive' or 'sm'

    # External seam_repair (legacy PatchMatch) — off by default
    external_seam_repair: bool = False

    # QA category — drives thresholds
    category: str = "Rock"

    # ComfyUI host
    host: str = "http://127.0.0.1:8188"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pick_best_variant(ranking: list[dict]) -> tuple[int, Path] | None:
    """Pick the highest-composite-score variant that didn't fail."""
    for r in ranking:
        if "error" not in r and "path" in r:
            return r["variant_index"], Path(r["path"])
    return None


def run_pipeline(prompt: str, asset_id: str, out_dir: Path,
                 settings: PipelineSettings) -> dict:
    """Run the W4 texture pipeline. Returns the manifest dict.

    Writes outputs into out_dir. Caller is responsible for the
    biome/slot/idx layout — this just owns one candidate folder.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    variants_dir = out_dir / "variants"
    variants_dir.mkdir(exist_ok=True)

    manifest: dict[str, Any] = {
        "version": "w4_tx_pipeline_v1",
        "asset_id": asset_id,
        "prompt": prompt,
        "settings": asdict(settings),
        "started_at": _now(),
        "stages": [],
    }

    # ----- STAGE 1: generate N variants, rank by composite -----
    print(f"\n=== STAGE 1: generate {settings.variants} variants ===")
    ranking = generate_variants(
        prompt, asset_id, settings.variants,
        unet=settings.unet, clip=settings.clip, vae=settings.vae,
        size=settings.size, steps=settings.steps,
        seed_base=settings.seed_base, heal_denoise=settings.heal_denoise,
        heal_mode=settings.heal_mode, host=settings.host,
        out_dir=variants_dir,
    )
    manifest["stages"].append({
        "stage": "variants",
        "n_variants": settings.variants,
        "ranking": ranking,
    })

    # Pick best by composite. Variants paths are relative to variants_dir.
    pick = _pick_best_variant(ranking)
    if pick is None:
        manifest["completed_at"] = _now()
        manifest["status"] = "failed"
        manifest["failure_reason"] = "all_variants_failed"
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        raise RuntimeError("all variants failed")
    best_idx, best_path_rel = pick
    best_albedo = variants_dir / best_path_rel
    print(f"\n  best variant: v{best_idx}  (composite="
          f"{ranking[0]['composite']:.3f})")

    # ----- STAGE 2: delight (default OFF per audit) -----
    if settings.delight_strength > 0.0:
        print(f"\n=== STAGE 2: delight (strength={settings.delight_strength}) ===")
        # We import the upstream module's delight function and use it
        # in-process; no subprocess shell-out.
        sys.path.insert(0, r"D:/assets/pipelines/textures")
        from delight import delight as _delight  # noqa: E402
        rgb = np.asarray(Image.open(best_albedo).convert("RGB"))
        delit = _delight(rgb, strength=settings.delight_strength)
        # Backup the pre-delight albedo
        (variants_dir / f"v{best_idx}_albedo.pre_delight.png").write_bytes(
            best_albedo.read_bytes())
        Image.fromarray(delit).save(best_albedo)
        manifest["stages"].append({
            "stage": "delight",
            "strength": settings.delight_strength,
        })
    else:
        manifest["stages"].append({
            "stage": "delight",
            "skipped": True,
            "reason": "default off per audit; prompt already handles lighting",
        })

    # Copy the chosen albedo into out_dir/albedo.png — the PBR backends
    # will read it from there and write the rest of the maps alongside.
    canonical_albedo = out_dir / "albedo.png"
    Image.open(best_albedo).save(canonical_albedo)

    # ----- STAGE 3: PBR backend -----
    print(f"\n=== STAGE 3: PBR ({settings.pbr_backend}) ===")
    if settings.pbr_backend == "derive":
        pbr_log = derive_pbr_heuristic(canonical_albedo, out_dir,
                                       category=settings.category)
    elif settings.pbr_backend == "sm":
        # Import lazily — SM needs the mesa-env subprocess
        from tx_pbr_sm import derive_pbr as derive_pbr_sm
        pbr_log = derive_pbr_sm(canonical_albedo, out_dir, size=512)
    else:
        raise ValueError(f"unknown pbr_backend: {settings.pbr_backend!r}")
    manifest["stages"].append({"stage": "pbr", **pbr_log})

    # ----- STAGE 4: external seam_repair (default OFF per audit) -----
    if settings.external_seam_repair:
        print(f"\n=== STAGE 4: external seam_repair (PatchMatch) ===")
        # Shell out to upstream seam_repair, but feed it a temp dir
        # because it writes <id>_<map>.png and we use canonical names.
        # Skipped here: implement only if a real-data run needs it.
        manifest["stages"].append({
            "stage": "external_seam_repair",
            "skipped": True,
            "reason": "implementation deferred; default OFF makes this rare",
        })
    else:
        manifest["stages"].append({
            "stage": "external_seam_repair",
            "skipped": True,
            "reason": "default off per audit; FLUX heal pass is the repair",
        })

    # ----- STAGE 5: QA -----
    print(f"\n=== STAGE 5: tx_qa (category={settings.category}) ===")
    qa_report = qa_albedo(canonical_albedo, category=settings.category)
    (out_dir / "qa.json").write_text(json.dumps(qa_report, indent=2,
                                                default=float), encoding="utf-8")
    manifest["stages"].append({
        "stage": "qa",
        "grade": qa_report["grade"],
        "passed_checks": qa_report["passed_checks"],
        "thresholds": qa_report["thresholds_applied"],
        "failed": [k for k, v in qa_report["checks"].items()
                   if isinstance(v, dict) and v.get("passed") is False
                   and k in ("edge_continuity", "junction_visibility",
                             "periodic_artifact", "mip32_stdev")],
    })
    manifest["grade"] = qa_report["grade"]
    manifest["passed"] = qa_report["passed"]
    print(f"  grade: {qa_report['grade']}  "
          f"({qa_report['passed_checks']}/4 checks passed)")
    failed = manifest["stages"][-1]["failed"]
    if failed:
        print(f"  failed checks: {', '.join(failed)}")

    # ----- DONE -----
    manifest["completed_at"] = _now()
    manifest["status"] = "completed"
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=float), encoding="utf-8")
    print(f"\nwrote {out_dir / 'manifest.json'}")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="W4 texture pipeline")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--category", default="Rock")
    # generation
    ap.add_argument("--variants", type=int, default=4)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=42)
    ap.add_argument("--unet", default="flux-2-klein-9b-fp8.safetensors")
    ap.add_argument("--clip", default="qwen_3_8b_fp8mixed.safetensors")
    ap.add_argument("--vae", default="flux2-vae.safetensors")
    # audit knobs
    ap.add_argument("--heal-denoise", type=float, default=0.35)
    ap.add_argument("--heal-mode", choices=["flux_heal", "none"],
                    default="flux_heal")
    ap.add_argument("--delight-strength", type=float, default=0.0,
                    help="default 0.0 (skip) per audit")
    ap.add_argument("--pbr-backend", choices=["derive", "sm"],
                    default="derive",
                    help="default 'derive' (heuristic, consistent with albedo)")
    ap.add_argument("--external-seam-repair", action="store_true",
                    help="opt-in PatchMatch fallback; default off")
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    args = ap.parse_args()

    settings = PipelineSettings(
        unet=args.unet, clip=args.clip, vae=args.vae,
        size=args.size, steps=args.steps, seed_base=args.seed_base,
        variants=args.variants,
        heal_denoise=args.heal_denoise, heal_mode=args.heal_mode,
        delight_strength=args.delight_strength,
        pbr_backend=args.pbr_backend,
        external_seam_repair=args.external_seam_repair,
        category=args.category,
        host=args.host,
    )
    manifest = run_pipeline(args.prompt, args.id, args.out_dir, settings)
    print(f"\n=== final ===")
    print(f"  grade:  {manifest['grade']}")
    print(f"  status: {manifest['status']}")
    return 0 if manifest.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
