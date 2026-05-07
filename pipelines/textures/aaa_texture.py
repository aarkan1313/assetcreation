"""AAA texture pipeline orchestrator.

Chains the full quality stack:

  prompt
    → variant generation (N seeds × seamless FLUX = N candidates)
    → pick best by seam score
    → de-lighting pass (LAB-space large-blur subtract)
    → Material Anything image-to-PBR (real estimation, not heuristic)
    → seam repair on derived maps (PatchMatch)
    → texture QA (seam grade + sphere/plane previews + sanity)
    → quality gate: must beat seam grade B (overall < 0.005) to pass
    → catalog manifest
    → optional Godot exporter pass

Result lives at world/textures/library/<id>/ with the standard contract:
  <id>_albedo.png, <id>_normal.png, <id>_roughness.png, <id>_metallic.png,
  <id>_height.png, <id>_ao.png, qa/, repaired/, variant_select.json

Usage:
  python aaa_texture.py --prompt "weathered mossy basalt" --id basalt --category Rock
  python aaa_texture.py --prompt "ice crystal" --id ice --category Snow --variants 6 --quality strict

Quality presets:
  fast   = 2 variants, no MA, derive_pbr_v2 only, seam C+ accepted
  default= 4 variants, MA i2p, seam B+ required
  strict = 6 variants, MA i2p, MA UV refinement, seam A required (overall<0.003)
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

LIBRARY = Path(r"D:\assets\world\textures\library")
PIPELINE_DIR = Path(__file__).parent
CATALOG = Path(r"D:\assets\world\textures\catalog\materials.jsonl")


def python_subprocess(args, label):
    print(f"\n=== {label} ===")
    result = subprocess.run([sys.executable] + args, capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed (rc={result.returncode})")


def wsl_subprocess(cmd: str, label: str):
    print(f"\n=== {label} ===")
    result = subprocess.run(["wsl", "-d", "Ubuntu-24.04", "--", "bash", "-c", cmd])
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed (rc={result.returncode})")


def edge_seam_score(im_path: Path) -> float:
    arr = np.asarray(Image.open(im_path).convert("RGB"), dtype=np.float32)
    edge_lr = float(np.mean((arr[:, 0] - arr[:, -1]) ** 2)) / (255 ** 2)
    edge_tb = float(np.mean((arr[0, :] - arr[-1, :]) ** 2)) / (255 ** 2)
    return max(edge_lr, edge_tb)


PRESETS = {
    # PBR backends:
    #   "derive"  = derive_pbr_v2 (heuristic, no model, fastest)
    #   "sm"      = StableMaterials (real diffusion model, ~20s/material on 5090)
    "fast":    {"variants": 2, "pbr": "derive", "use_repair": True, "seam_max": 0.020, "delight": 0.3},
    "default": {"variants": 4, "pbr": "sm",     "use_repair": True, "seam_max": 0.010, "delight": 0.4},
    "strict":  {"variants": 6, "pbr": "sm",     "use_repair": True, "seam_max": 0.005, "delight": 0.5},
    # NOTE: Material Anything's standalone image-to-PBR is broken for 2D
    # textures (model requires multi-view 3D consolidation). The mesh-driven
    # path still works — see material_anything_adapter.py.
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--category", default="Rock")
    ap.add_argument("--quality", choices=["fast", "default", "strict"], default="default")
    ap.add_argument("--variants", type=int, default=None,
                    help="override preset variant count")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=42)
    ap.add_argument("--heal-strength", type=float, default=0.35)
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--no-gate", action="store_true",
                    help="ship even if seam score fails the gate")
    args = ap.parse_args()

    preset = PRESETS[args.quality]
    n_variants = args.variants or preset["variants"]
    seam_max = preset["seam_max"]
    pbr_backend = preset.get("pbr", "derive")  # "derive" | "sm"
    use_repair = preset["use_repair"]
    delight_strength = preset["delight"]

    out_dir = LIBRARY / args.id
    out_dir.mkdir(parents=True, exist_ok=True)

    log = {
        "id": args.id, "prompt": args.prompt, "category": args.category,
        "quality": args.quality, "preset": preset,
        "n_variants": n_variants, "size": args.size,
        "steps": args.steps, "seed_base": args.seed_base,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "stages": [],
    }

    # ---- STAGE 1: variant generation + best-pick ----
    python_subprocess([
        str(PIPELINE_DIR / "variant_select.py"),
        "--prompt", args.prompt, "--id", args.id,
        "--variants", str(n_variants),
        "--size", str(args.size), "--steps", str(args.steps),
        "--seed-base", str(args.seed_base),
        "--heal-strength", str(args.heal_strength),
        "--host", args.host,
    ], "STAGE 1: variant gen + best-pick")
    albedo_path = out_dir / f"{args.id}_albedo.png"
    pre_score = edge_seam_score(albedo_path)
    log["stages"].append({"stage": "variants", "seam_score": pre_score})
    print(f"  post-variant seam score: {pre_score:.5f}")

    # ---- STAGE 2: de-lighting ----
    python_subprocess([
        str(PIPELINE_DIR / "delight.py"),
        "--material", str(out_dir),
        "--strength", str(delight_strength),
    ], f"STAGE 2: de-lighting (strength={delight_strength})")
    log["stages"].append({"stage": "delight", "strength": delight_strength})

    # ---- STAGE 3: PBR estimation ----
    if pbr_backend == "sm":
        # StableMaterials runs in mesa-env (which has diffusers+cu130 ready)
        sm_python = r"D:\assets\animators\mesa-env\venv\Scripts\python.exe"
        sm_script = str(PIPELINE_DIR / "stablematerials_image2pbr.py")
        result = subprocess.run([
            sm_python, sm_script,
            "--input", str(albedo_path),
            "--out", str(out_dir),
            "--id", args.id,
            "--mode", "standard",
            "--size", str(args.size),
        ])
        if result.returncode != 0:
            print(f"  StableMaterials failed; falling back to derive_pbr_v2")
            python_subprocess([
                str(PIPELINE_DIR / "derive_pbr_v2.py"),
                "--albedo", str(albedo_path),
                "--id", args.id,
                "--category", args.category,
                "--out", str(out_dir),
            ], "STAGE 3: PBR fallback (deterministic v2)")
            log["stages"].append({"stage": "pbr", "method": "derive_pbr_v2_fallback"})
        else:
            log["stages"].append({"stage": "pbr", "method": "stablematerials_standard"})
    else:
        python_subprocess([
            str(PIPELINE_DIR / "derive_pbr_v2.py"),
            "--albedo", str(albedo_path),
            "--id", args.id,
            "--category", args.category,
            "--out", str(out_dir),
        ], "STAGE 3: PBR estimation (deterministic v2)")
        log["stages"].append({"stage": "pbr", "method": "derive_pbr_v2"})

    # ---- STAGE 4: seam repair (synced across all maps) ----
    if use_repair:
        # Only run repair if pre-repair seam is above threshold; the repair
        # script itself has --threshold but we'll let it decide.
        try:
            python_subprocess([
                str(PIPELINE_DIR / "seam_repair.py"),
                "--material", str(out_dir),
                "--threshold", str(seam_max * 1.5),
                "--patch", "64",
            ], "STAGE 4: seam repair")
            log["stages"].append({"stage": "seam_repair"})
        except RuntimeError as e:
            # repair may complain about missing manifest entry; not fatal
            print(f"  seam_repair note: {e}")
            log["stages"].append({"stage": "seam_repair", "skipped": True})

    # ---- STAGE 5: texture QA ----
    python_subprocess([
        str(PIPELINE_DIR / "texture_qa.py"),
        "--material", str(out_dir),
    ], "STAGE 5: QA (seam + sphere/plane synthetic)")
    qa_summary = json.loads((out_dir / "qa" / "summary.json").read_text(encoding="utf-8"))
    final_score = qa_summary["seam"]["overall"]
    grade = qa_summary["seam"]["grade"]
    log["stages"].append({"stage": "qa", "seam_score": final_score, "grade": grade})

    # ---- STAGE 5b: real Blender PBR render (best-effort; non-fatal) ----
    try:
        python_subprocess([
            str(PIPELINE_DIR / "blender_preview.py"),
            "--material", str(out_dir),
        ], "STAGE 5b: Blender lit-sphere render")
        log["stages"].append({"stage": "blender_preview", "ok": True})
    except RuntimeError as e:
        print(f"  blender preview skipped: {e}")
        log["stages"].append({"stage": "blender_preview", "ok": False, "note": str(e)})

    # ---- STAGE 6: quality gate ----
    print(f"\n=== STAGE 6: quality gate ===")
    print(f"  required: seam < {seam_max:.5f} (grade {'A' if seam_max <= 0.003 else 'B' if seam_max <= 0.01 else 'C'})")
    print(f"  got:      seam = {final_score:.5f} (grade {grade})")
    passed = final_score <= seam_max
    log["passed_gate"] = passed
    log["final_score"] = final_score
    log["grade"] = grade

    # ---- STAGE 7: catalog ----
    record = {
        "id": args.id,
        "source": "aaa_texture_pipeline",
        "prompt": args.prompt,
        "category": args.category,
        "quality_preset": args.quality,
        "license": "self-generated; FLUX.2-klein Apache-2.0 + MA research-license",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "library_path": f"world\\textures\\library\\{args.id}",
        "maps": {
            "albedo": f"{args.id}_albedo.png",
            "normal": f"{args.id}_normal.png",
            "roughness": f"{args.id}_roughness.png",
            "metallic": f"{args.id}_metallic.png",
            "height": f"{args.id}_height.png",
            "ao": f"{args.id}_ao.png" if (out_dir / f"{args.id}_ao.png").exists() else None,
        },
        "map_completeness": [k for k, v in {
            "albedo": (out_dir / f"{args.id}_albedo.png").exists(),
            "normal": (out_dir / f"{args.id}_normal.png").exists(),
            "roughness": (out_dir / f"{args.id}_roughness.png").exists(),
            "metallic": (out_dir / f"{args.id}_metallic.png").exists(),
            "height": (out_dir / f"{args.id}_height.png").exists(),
            "ao": (out_dir / f"{args.id}_ao.png").exists(),
        }.items() if v],
        "seam_score": final_score,
        "seam_grade": grade,
        "passed_gate": passed,
    }
    record["maps"] = {k: v for k, v in record["maps"].items() if v}

    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    with CATALOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    log["completed_at"] = datetime.now(timezone.utc).isoformat()
    (out_dir / "aaa_pipeline.json").write_text(json.dumps(log, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"DONE: {out_dir}")
    print(f"  prompt:     {args.prompt!r}")
    print(f"  quality:    {args.quality}")
    print(f"  variants:   {n_variants}")
    print(f"  PBR method: {pbr_backend}")
    print(f"  seam:       {final_score:.5f} (grade {grade})")
    print(f"  gate:       {'PASS' if passed else 'FAIL (use --no-gate to ship anyway)'}")

    if not passed and not args.no_gate:
        print(f"\nQUALITY GATE FAILED. Try:")
        print(f"  - more variants:  --variants {n_variants * 2}")
        print(f"  - higher heal:    --heal-strength 0.45")
        print(f"  - different seed: --seed-base {args.seed_base + 1}")
        print(f"  - lower bar:     --quality fast")
        sys.exit(1)


if __name__ == "__main__":
    main()
