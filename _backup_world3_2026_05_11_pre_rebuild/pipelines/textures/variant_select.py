"""Variant generation: produce N candidates, pick the best by seam score.

For tileable textures the cheapest reliable quality lever is N×generation +
selection by deterministic metric. Same prompt, different seeds, run through
flux_seamless, then keep the best.

Usage:
  python variant_select.py --prompt "weathered cobblestone" --id cobblestone \
      --variants 4 --size 1024 --steps 4 --heal-strength 0.35
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from flux_seamless import run_seamless, edge_seam_score


LIBRARY = Path("D:/assets/world/textures/library")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--variants", type=int, default=4)
    ap.add_argument("--unet", default="flux-2-klein-4b.safetensors")
    ap.add_argument("--clip", default="qwen_3_4b.safetensors")
    ap.add_argument("--vae", default="flux2-vae.safetensors")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--seed-base", type=int, default=42)
    ap.add_argument("--heal-strength", type=float, default=0.35)
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--keep-all", action="store_true",
                    help="keep all variants in <id>_v0 .. <id>_vN; default keeps best as <id>")
    args = ap.parse_args()

    print(f"[variants] generating {args.variants} candidates for {args.id!r}")
    results = []
    for i in range(args.variants):
        seed = args.seed_base + i * 1000
        variant_id = f"{args.id}_v{i}"
        try:
            path = run_seamless(args.prompt, variant_id,
                                args.unet, args.clip, args.vae,
                                args.size, seed, args.steps,
                                args.heal_strength, args.host)
            arr = np.asarray(Image.open(path).convert("RGB"))
            score = edge_seam_score(arr)
            print(f"  variant {i} seed={seed} score={score:.5f}")
            results.append((variant_id, path, score, seed))
        except Exception as e:
            print(f"  variant {i} FAILED: {e}")

    if not results:
        raise SystemExit("all variants failed")

    # Pick best (lowest seam score)
    results.sort(key=lambda r: r[2])
    best_id, best_path, best_score, best_seed = results[0]
    print(f"\n[variants] best: {best_id} score={best_score:.5f} seed={best_seed}")

    # Copy best to canonical id
    final_dir = LIBRARY / args.id
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / f"{args.id}_albedo.png"
    shutil.copy2(best_path, final_path)

    summary = {
        "id": args.id,
        "prompt": args.prompt,
        "n_variants": args.variants,
        "best_seed": best_seed,
        "best_score": best_score,
        "all_scores": [{"id": r[0], "seed": r[3], "score": r[2]} for r in results],
    }
    (final_dir / "variant_select.json").write_text(json.dumps(summary, indent=2),
                                                     encoding="utf-8")
    print(f"  saved best -> {final_path}")
    print(f"  summary -> {final_dir/'variant_select.json'}")

    if not args.keep_all:
        for v_id, _, _, _ in results:
            v_dir = LIBRARY / v_id
            if v_dir != final_dir and v_dir.exists():
                shutil.rmtree(v_dir)
        print(f"  removed {args.variants} variant dirs (use --keep-all to retain)")


if __name__ == "__main__":
    main()
