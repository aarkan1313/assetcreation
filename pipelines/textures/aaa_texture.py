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
    #
    # Sizes:
    #   `flux_size`  — what FLUX generates the source albedo at (1024 = standard).
    #   `pbr_size`   — what we deliver. 512 matches StableMaterials' native
    #                  training resolution. We deliberately don't upscale beyond
    #                  the model's native res; doing so just LANCZOS-stretches
    #                  the signal without adding detail.
    # All maps generated at 512 — matches StableMaterials' native training res
    # and avoids the size-mismatch bug. FLUX 2 klein at 512 still produces
    # good tileable albedos and runs ~4x faster than 1024. For terrain via
    # world_triplanar (one tile every 5-20m), 512 supplies plenty of pixel
    # density at any of our camera ranges.
    "fast":    {"variants": 2, "pbr": "derive", "flux_size": 512, "pbr_size": 512, "use_repair": True, "seam_max": 0.020, "delight": 0.3, "min_grade": "C"},
    "default": {"variants": 4, "pbr": "sm",     "flux_size": 512, "pbr_size": 512, "use_repair": True, "seam_max": 0.010, "delight": 0.4, "min_grade": "B"},
    "strict":  {"variants": 6, "pbr": "sm",     "flux_size": 512, "pbr_size": 512, "use_repair": True, "seam_max": 0.005, "delight": 0.5, "min_grade": "A"},
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
    ap.add_argument("--size", type=int, default=None,
                    help="override preset flux_size + pbr_size (uniform). "
                         "Default: preset-defined (512 for default/strict)")
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=42)
    ap.add_argument("--heal-strength", type=float, default=0.35)
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--no-gate", action="store_true",
                    help="ship even if seam score fails the gate")
    ap.add_argument("--pbr-backend",
                    choices=["derive", "sm", "chord", "chord_sm_rough"],
                    default=None,
                    help="override preset PBR backend. 'derive' = "
                         "derive_pbr_v2 (heuristic, no model), 'sm' = "
                         "StableMaterials (default for default/strict "
                         "presets), 'chord' = CHORD (Ubisoft, opt-in; "
                         "requires ComfyUI-Chord nodes + chord_v1.safetensors), "
                         "'chord_sm_rough' = HYBRID (A.11): CHORD for "
                         "albedo/normal/height/metallic/ao + SM for "
                         "roughness only. Best of both for hard-edge "
                         "rock-class materials where CHORD's roughness "
                         "is too flat. ~25s extra per material.")
    args = ap.parse_args()

    preset = PRESETS[args.quality]
    n_variants = args.variants or preset["variants"]
    seam_max = preset["seam_max"]
    # Backend resolution order: explicit --pbr-backend flag > preset default
    pbr_backend = args.pbr_backend or preset.get("pbr", "derive")  # "derive" | "sm" | "chord"
    use_repair = preset["use_repair"]
    delight_strength = preset["delight"]
    flux_size = args.size if args.size is not None else preset["flux_size"]
    pbr_size = args.size if args.size is not None else preset["pbr_size"]
    min_grade = preset.get("min_grade", "B")

    out_dir = LIBRARY / args.id
    out_dir.mkdir(parents=True, exist_ok=True)

    log = {
        "id": args.id, "prompt": args.prompt, "category": args.category,
        "quality": args.quality, "preset": preset,
        "n_variants": n_variants,
        "flux_size": flux_size, "pbr_size": pbr_size,
        "steps": args.steps, "seed_base": args.seed_base,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "stages": [],
    }

    # ---- STAGE 1: variant generation + best-pick ----
    python_subprocess([
        str(PIPELINE_DIR / "variant_select.py"),
        "--prompt", args.prompt, "--id", args.id,
        "--variants", str(n_variants),
        "--size", str(flux_size), "--steps", str(args.steps),
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
    if pbr_backend == "chord":
        # CHORD (Ubisoft La Forge) — talks to ComfyUI HTTP API, runs the
        # ChordMaterialEstimation node graph there. Requires ComfyUI-Chord
        # custom nodes + chord_v1.safetensors checkpoint installed (see
        # PIPELINE.md "PBR backends" section).
        chord_script = str(PIPELINE_DIR / "chord_image2pbr.py")
        result = subprocess.run([
            sys.executable, chord_script,
            "--input", str(albedo_path),
            "--out", str(out_dir),
            "--id", args.id,
            "--host", args.host,
        ])
        if result.returncode != 0:
            print(f"  CHORD failed; falling back to derive_pbr_v2")
            python_subprocess([
                str(PIPELINE_DIR / "derive_pbr_v2.py"),
                "--albedo", str(albedo_path),
                "--id", args.id,
                "--category", args.category,
                "--out", str(out_dir),
            ], "STAGE 3: PBR fallback (deterministic v2)")
            log["stages"].append({"stage": "pbr", "method": "derive_pbr_v2_fallback"})
        else:
            log["stages"].append({"stage": "pbr", "method": "chord_v1"})
    elif pbr_backend == "chord_sm_rough":
        # HYBRID (A.11): CHORD for albedo/normal/height/metallic/ao;
        # SM for roughness only. CHORD's roughness on rock-class
        # materials is near-flat and fails our existing sanity check;
        # SM produces visibly varied roughness on the same input. This
        # backend gets the best of both.
        chord_script = str(PIPELINE_DIR / "chord_image2pbr.py")
        chord_result = subprocess.run([
            sys.executable, chord_script,
            "--input", str(albedo_path),
            "--out", str(out_dir),
            "--id", args.id,
            "--host", args.host,
        ])
        if chord_result.returncode != 0:
            print(f"  CHORD failed; falling back to derive_pbr_v2")
            python_subprocess([
                str(PIPELINE_DIR / "derive_pbr_v2.py"),
                "--albedo", str(albedo_path),
                "--id", args.id,
                "--category", args.category,
                "--out", str(out_dir),
            ], "STAGE 3: PBR fallback (deterministic v2)")
            log["stages"].append({"stage": "pbr", "method": "derive_pbr_v2_fallback"})
        else:
            # Now run SM into a temp dir and copy ONLY its roughness over
            # CHORD's. We don't use --no-overwrite because we want SM's
            # roughness to win.
            import tempfile
            sm_python = r"D:\assets\animators\mesa-env\venv\Scripts\python.exe"
            sm_script = str(PIPELINE_DIR / "stablematerials_image2pbr.py")
            sm_tmp = Path(tempfile.mkdtemp(prefix="a11_sm_rough_"))
            try:
                sm_result = subprocess.run([
                    sm_python, sm_script,
                    "--input", str(albedo_path),
                    "--out", str(sm_tmp),
                    "--id", args.id,
                    "--mode", "standard",
                    "--size", str(pbr_size),
                ])
                if sm_result.returncode != 0:
                    print(f"  SM (for roughness) failed; keeping CHORD's roughness")
                    log["stages"].append({"stage": "pbr",
                                          "method": "chord_v1+sm_roughness_failed"})
                else:
                    sm_rough_src = sm_tmp / f"{args.id}_roughness.png"
                    chord_rough_dst = out_dir / f"{args.id}_roughness.png"
                    if sm_rough_src.exists():
                        # Backup CHORD's roughness so we can compare/restore
                        chord_rough_backup = (
                            out_dir / f"{args.id}_roughness.pre_sm_swap.png")
                        if chord_rough_dst.exists():
                            chord_rough_dst.replace(chord_rough_backup)
                        shutil.copy2(sm_rough_src, chord_rough_dst)
                        print(f"  hybrid: replaced CHORD roughness with SM "
                              f"({chord_rough_dst.name}); "
                              f"CHORD's saved as .pre_sm_swap.png")
                        log["stages"].append({"stage": "pbr",
                                              "method": "chord_v1+sm_roughness"})
                    else:
                        print(f"  SM produced no roughness; keeping CHORD's")
                        log["stages"].append({"stage": "pbr",
                                              "method": "chord_v1+sm_roughness_missing"})
            finally:
                # Clean up the SM temp dir (we copied what we need)
                shutil.rmtree(sm_tmp, ignore_errors=True)
    elif pbr_backend == "sm":
        # StableMaterials runs in mesa-env (which has diffusers+cu130 ready).
        # We pass --size matching the model's native resolution (512). Larger
        # values just LANCZOS-stretch the output; not worth the lie.
        sm_python = r"D:\assets\animators\mesa-env\venv\Scripts\python.exe"
        sm_script = str(PIPELINE_DIR / "stablematerials_image2pbr.py")
        result = subprocess.run([
            sm_python, sm_script,
            "--input", str(albedo_path),
            "--out", str(out_dir),
            "--id", args.id,
            "--mode", "standard",
            "--size", str(pbr_size),
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

    # ---- STAGE 5: texture QA (3-check seam metric + sanity) ----
    python_subprocess([
        str(PIPELINE_DIR / "texture_qa.py"),
        "--material", str(out_dir),
        "--category", args.category,
    ], "STAGE 5: QA (3-check seam metric + sphere/plane preview + sanity)")
    qa_summary = json.loads((out_dir / "qa" / "summary.json").read_text(encoding="utf-8"))
    seam = qa_summary["seam"]
    grade = seam["grade"]
    checks = seam["checks"]
    log["stages"].append({
        "stage": "qa",
        "grade": grade,
        "edge_mse": checks["edge_continuity"]["overall_mse"],
        "junction_ratio": checks["junction_visibility"]["ratio"],
        "periodic_locality": checks["periodic_artifact"]["peak_locality_ratio"],
        "sanity_ok": qa_summary["sanity_ok"],
    })

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
    # Multi-check verdict. Pass requires:
    #   1. seam grade meets preset's min_grade (A=all 3 checks pass, B=>=2,
    #      C=>=1, D=none)
    #   2. sanity_ok (map ranges look sensible; all expected maps present)
    #   3. at least 4 of {albedo, normal, roughness, height} maps exist
    print(f"\n=== STAGE 6: quality gate ===")
    grade_rank = {"A": 3, "B": 2, "C": 1, "D": 0}
    if grade not in grade_rank:
        # Defensive: don't silently treat an unexpected grade as D and
        # potentially pass it through with min_grade='D'. Surface the
        # corruption.
        raise RuntimeError(
            f"texture_qa returned unexpected grade {grade!r}; "
            f"expected one of {sorted(grade_rank)}"
        )
    if min_grade not in grade_rank:
        raise RuntimeError(
            f"preset min_grade {min_grade!r} not in {sorted(grade_rank)}"
        )
    grade_pass = grade_rank[grade] >= grade_rank[min_grade]
    sanity_pass = bool(qa_summary.get("sanity_ok"))
    core_maps_present = sum(1 for m in ("albedo", "normal", "roughness", "height")
                            if (out_dir / f"{args.id}_{m}.png").exists())
    maps_pass = core_maps_present >= 4

    failures: list[str] = []
    if not grade_pass:
        per_check = [
            ("edge_continuity", checks["edge_continuity"]["passed"]),
            ("junction_visibility", checks["junction_visibility"]["passed"]),
            ("periodic_artifact", checks["periodic_artifact"]["passed"]),
        ]
        failed_checks = [n for n, ok in per_check if not ok]
        failures.append(f"grade={grade} below min={min_grade} "
                        f"(failed: {','.join(failed_checks) or 'none'})")
    if not sanity_pass:
        notes = qa_summary.get("notes") or []
        failures.append(f"sanity: {'; '.join(notes) or 'unspecified'}")
    if not maps_pass:
        failures.append(f"only {core_maps_present}/4 core maps present")

    passed = grade_pass and sanity_pass and maps_pass
    print(f"  required:    grade>={min_grade}, sanity_ok=True, core_maps>=4")
    print(f"  got:         grade={grade}, sanity_ok={sanity_pass}, core_maps={core_maps_present}/4")
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
    else:
        print(f"  PASS")

    log["passed_gate"] = passed
    log["grade"] = grade
    log["gate"] = {
        "min_grade": min_grade,
        "grade_pass": grade_pass,
        "sanity_pass": sanity_pass,
        "maps_pass": maps_pass,
        "core_maps_present": core_maps_present,
        "failures": failures,
    }

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
        "seam_grade": grade,
        "seam_checks": {
            "edge_continuity_mse": checks["edge_continuity"]["overall_mse"],
            "junction_ratio": checks["junction_visibility"]["ratio"],
            "periodic_locality": checks["periodic_artifact"]["peak_locality_ratio"],
        },
        "passed_gate": passed,
        "gate_failures": failures,
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
    print(f"  size:       {pbr_size}x{pbr_size} (flux at {flux_size})")
    print(f"  grade:      {grade}  edge={checks['edge_continuity']['overall_mse']:.4f} "
          f"junc={checks['junction_visibility']['ratio']:.2f} "
          f"period={checks['periodic_artifact']['peak_locality_ratio']:.1f}")
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
