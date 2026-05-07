"""Experiment harness for texture-pipeline R&D.

Runs `aaa_texture.py` N times with controlled variation (seeds,
prompts, settings) and emits:

  D:/tmp/world3_experiments/<name>/
    contact_sheet.png        - grid of tile_2x2 thumbnails with grade captions
    manifest.jsonl           - one row per run: prompt, seed, grade, metrics
    runs/<run_id>/           - copy of the relevant qa artifacts per run

Three sweep modes:

  --mode seeds      — same prompt, vary seed-base. The "is this prompt
                      reliable?" check.
  --mode prompts    — vary prompt, fixed seed. The "which phrasing
                      works best?" check.
  --mode settings   — same prompt + seed, vary --variants/--heal-strength
                      pipeline settings.

Common usage:

  # Same prompt × 5 seeds:
  python experiment.py --name sand_seeds --mode seeds \\
    --prompt "close-up photograph of natural desert sand dunes..." \\
    --category Sand --seeds 100 200 300 400 500

  # Multiple prompts × 4 seeds each:
  python experiment.py --name sand_prompts --mode prompts \\
    --prompts-file prompts_sand.json --seeds 100 200 300 400 \\
    --category Sand

  # Settings sweep (variants/heal/delight grid):
  python experiment.py --name dirt_settings --mode settings \\
    --prompt "rich brown dirt..." --category Ground \\
    --variants-list 4 8 --heal-list 0.25 0.45

The experiments are NOT cleaned up between runs — each gets its own
output folder under D:/tmp/world3_experiments/<name>/. Feel free to
inspect intermediate files in world/textures/library/<run_id>/ for
each run; the harness uses unique IDs like <name>__<seed> so they
don't collide.
"""
from __future__ import annotations

import argparse
import itertools
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


PIPELINE_DIR = Path(__file__).parent
LIBRARY = Path(r"D:\assets\world\textures\library")
EXPERIMENTS_ROOT = Path(r"D:/tmp/world3_experiments")


def run_aaa(asset_id: str, prompt: str, category: str,
             seed_base: int, quality: str = "default",
             variants: int | None = None,
             heal_strength: float | None = None,
             extra: list[str] | None = None) -> dict:
    """Run aaa_texture.py once. Returns a result dict (success/grade/etc)."""
    cmd = [
        sys.executable, str(PIPELINE_DIR / "aaa_texture.py"),
        "--id", asset_id,
        "--prompt", prompt,
        "--category", category,
        "--quality", quality,
        "--seed-base", str(seed_base),
        "--no-gate",  # always ship — we want to see real grades
    ]
    if variants is not None:
        cmd += ["--variants", str(variants)]
    if heal_strength is not None:
        cmd += ["--heal-strength", str(heal_strength)]
    if extra:
        cmd += extra

    print(f"  [run] {asset_id} (seed={seed_base})")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        return {"id": asset_id, "ok": False, "rc": result.returncode}

    # Read back the manifest for the run.
    manifest_path = LIBRARY / asset_id / "aaa_pipeline.json"
    if not manifest_path.exists():
        return {"id": asset_id, "ok": False, "error": "no manifest"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    qa_path = LIBRARY / asset_id / "qa" / "summary.json"
    qa = {}
    if qa_path.exists():
        qa = json.loads(qa_path.read_text(encoding="utf-8"))

    return {
        "id": asset_id,
        "ok": True,
        "prompt": prompt,
        "seed": seed_base,
        "category": category,
        "variants": variants,
        "heal_strength": heal_strength,
        "grade": manifest.get("grade", "?"),
        "passed_gate": manifest.get("passed_gate", False),
        "edge_mse": (qa.get("seam") or {}).get("checks", {}).get("edge_continuity", {}).get("overall_mse"),
        "junction_ratio": (qa.get("seam") or {}).get("checks", {}).get("junction_visibility", {}).get("ratio"),
        "periodic_locality": (qa.get("seam") or {}).get("checks", {}).get("periodic_artifact", {}).get("peak_locality_ratio"),
        "tile_2x2": str(LIBRARY / asset_id / "qa" / "tile_2x2.png"),
        "albedo": str(LIBRARY / asset_id / f"{asset_id}_albedo.png"),
    }


def make_contact_sheet(results: list[dict], out_path: Path,
                        cell_size: int = 320, cols: int = 4,
                        caption_height: int = 60) -> None:
    """Compose a grid of tile_2x2 thumbnails with grade captions."""
    if not results:
        return
    n = len(results)
    rows = (n + cols - 1) // cols
    W = cell_size * cols
    H = (cell_size + caption_height) * rows
    canvas = Image.new("RGB", (W, H), (32, 32, 36))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        small_font = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
        small_font = font

    for i, r in enumerate(results):
        col = i % cols
        row = i // cols
        x = col * cell_size
        y = row * (cell_size + caption_height)

        # Image
        tile_path = Path(r.get("tile_2x2", ""))
        if tile_path.exists():
            try:
                im = Image.open(tile_path).convert("RGB")
                im.thumbnail((cell_size, cell_size), Image.LANCZOS)
                ix = x + (cell_size - im.size[0]) // 2
                iy = y + (cell_size - im.size[1]) // 2
                canvas.paste(im, (ix, iy))
            except Exception as e:  # noqa: BLE001
                draw.text((x + 4, y + 4), f"err: {e}", fill="red", font=small_font)
        else:
            draw.text((x + 4, y + 4), "(no tile)", fill="grey", font=small_font)

        # Caption
        cy = y + cell_size
        # Color code grade: A green, B yellow, C orange, D red, ? grey
        grade = r.get("grade", "?")
        grade_color = {"A": (90, 220, 100), "B": (220, 200, 70),
                       "C": (220, 130, 50), "D": (220, 70, 70)}.get(grade, (160, 160, 160))
        draw.rectangle((x, cy, x + cell_size, cy + caption_height),
                       fill=(20, 20, 22))
        draw.text((x + 6, cy + 4),
                  f"id={r.get('id', '?')}  seed={r.get('seed', '?')}",
                  fill=(220, 220, 220), font=small_font)
        draw.text((x + 6, cy + 22), f"grade={grade}",
                  fill=grade_color, font=font)
        em = r.get("edge_mse")
        jr = r.get("junction_ratio")
        pl = r.get("periodic_locality")
        if em is not None:
            metrics = (f"e={em:.4f}  j={jr:.2f}  p={pl:.1f}"
                       if jr is not None and pl is not None else f"e={em:.4f}")
            draw.text((x + 6, cy + 42), metrics,
                      fill=(180, 180, 180), font=small_font)

    canvas.save(out_path)
    print(f"  contact sheet -> {out_path}")


def cmd_seeds(args, exp_dir: Path) -> list[dict]:
    if not args.seeds:
        raise SystemExit("--seeds required for --mode seeds")
    if not args.prompt:
        raise SystemExit("--prompt required for --mode seeds")
    results = []
    for seed in args.seeds:
        asset_id = f"{args.name}__seed{seed}"
        r = run_aaa(asset_id, args.prompt, args.category, seed,
                    quality=args.quality, variants=args.variants,
                    heal_strength=args.heal_strength)
        results.append(r)
    return results


def cmd_prompts(args, exp_dir: Path) -> list[dict]:
    if not args.prompts_file:
        raise SystemExit("--prompts-file required for --mode prompts")
    if not args.seeds:
        raise SystemExit("--seeds required for --mode prompts")
    prompts = json.loads(Path(args.prompts_file).read_text(encoding="utf-8"))
    if not isinstance(prompts, list):
        raise SystemExit("prompts file must be a JSON list of strings or {label, prompt}")
    results = []
    for i, p in enumerate(prompts):
        if isinstance(p, dict):
            label, prompt = p.get("label", f"p{i}"), p["prompt"]
        else:
            label, prompt = f"p{i}", p
        for seed in args.seeds:
            asset_id = f"{args.name}__{label}__seed{seed}"
            r = run_aaa(asset_id, prompt, args.category, seed,
                        quality=args.quality, variants=args.variants,
                        heal_strength=args.heal_strength)
            r["prompt_label"] = label
            results.append(r)
    return results


def cmd_settings(args, exp_dir: Path) -> list[dict]:
    if not args.prompt:
        raise SystemExit("--prompt required for --mode settings")
    seed = args.seeds[0] if args.seeds else 42
    variants_list = args.variants_list or [4]
    heal_list = args.heal_list or [0.35]
    results = []
    for v, h in itertools.product(variants_list, heal_list):
        asset_id = f"{args.name}__v{v}_h{int(h*100)}"
        r = run_aaa(asset_id, args.prompt, args.category, seed,
                    quality=args.quality, variants=v, heal_strength=h)
        results.append(r)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True,
                    help="experiment id (becomes folder under D:/tmp/world3_experiments/)")
    ap.add_argument("--mode", required=True, choices=("seeds", "prompts", "settings"))
    ap.add_argument("--prompt", help="prompt (modes: seeds, settings)")
    ap.add_argument("--prompts-file", help="JSON list of prompts (mode: prompts)")
    ap.add_argument("--category", default="Ground")
    ap.add_argument("--quality", default="default")
    ap.add_argument("--seeds", type=int, nargs="+",
                    help="seed-base values to run")
    ap.add_argument("--variants", type=int, default=None,
                    help="override aaa_texture --variants")
    ap.add_argument("--heal-strength", type=float, default=None)
    ap.add_argument("--variants-list", type=int, nargs="+",
                    help="(mode: settings) variants values to sweep")
    ap.add_argument("--heal-list", type=float, nargs="+",
                    help="(mode: settings) heal_strength values to sweep")
    ap.add_argument("--cols", type=int, default=4,
                    help="contact sheet column count")
    args = ap.parse_args()

    exp_dir = EXPERIMENTS_ROOT / args.name
    exp_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "seeds":
        results = cmd_seeds(args, exp_dir)
    elif args.mode == "prompts":
        results = cmd_prompts(args, exp_dir)
    elif args.mode == "settings":
        results = cmd_settings(args, exp_dir)
    else:
        raise SystemExit(f"unknown mode {args.mode!r}")

    # Write manifest.jsonl
    with (exp_dir / "manifest.jsonl").open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    # Contact sheet
    make_contact_sheet(results, exp_dir / "contact_sheet.png", cols=args.cols)

    # Brief summary
    grades = [r.get("grade", "?") for r in results if r.get("ok")]
    grade_counts: dict[str, int] = {}
    for g in grades:
        grade_counts[g] = grade_counts.get(g, 0) + 1
    print(f"\n[experiment] {args.name}: {len(results)} runs")
    for g in sorted(grade_counts.keys()):
        print(f"  grade {g}: {grade_counts[g]}")
    print(f"  output: {exp_dir}")


if __name__ == "__main__":
    main()
