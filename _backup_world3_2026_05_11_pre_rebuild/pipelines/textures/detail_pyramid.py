"""Detail texture pyramid — generate a macro + detail-layer pair.

AAA terrain/wall materials use a two-layer approach:

  Macro:  the material itself (cobblestone, grass, rock) — what you see at
          1-30m. Lower frequency information dominates.
  Detail: high-frequency surface noise, sampled at ~10x macro scale, modulates
          albedo + normal at close range. What you see when the camera is 0-2m
          from the surface. Without this, AAA materials look flat up close.

How it's used in Godot:
  - Macro texture sampled at a coarse UV scale (e.g. 4m repeat).
  - Detail texture sampled at a fine UV scale (e.g. 0.3m repeat).
  - Mix detail's normal into the macro normal via Reoriented Normal Mapping (RNM).
  - Mix detail's albedo via overlay or soft-light blend.

This script:
  1. Takes an existing macro material directory
  2. Generates a complementary detail material at the same prompt with
     "fine detail surface noise variation" appended
  3. Saves it as `<id>_detail/` next to the macro
  4. Writes a `detail_pair.json` linking them

Usage:
  python detail_pyramid.py --macro world/textures/library/cobblestone_aaa --detail-strength 0.6
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LIBRARY = Path(r"D:\assets\world\textures\library")
PIPELINE_DIR = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--macro", type=Path, required=True,
                    help="existing macro material directory")
    ap.add_argument("--detail-prompt-suffix", default=", fine surface detail noise, micro-grain, weathering specks, close-up macro photography",
                    help="appended to the macro prompt to generate the detail layer")
    ap.add_argument("--detail-id", default=None,
                    help="output id; defaults to <macro_id>_detail")
    ap.add_argument("--detail-size", type=int, default=1024)
    ap.add_argument("--detail-quality", default="default",
                    help="quality preset for detail layer")
    ap.add_argument("--detail-variants", type=int, default=2,
                    help="fewer variants for the detail; quality bar lower since it's blended")
    ap.add_argument("--detail-strength", type=float, default=0.6,
                    help="hint for the runtime mix; saved in detail_pair.json")
    ap.add_argument("--detail-uv-repeat", type=float, default=10.0,
                    help="recommended repeat ratio of detail vs macro (detail samples at this many times macro frequency)")
    ap.add_argument("--detail-seed-offset", type=int, default=10000)
    args = ap.parse_args()

    macro_dir = args.macro
    if not macro_dir.exists():
        raise SystemExit(f"macro material not found: {macro_dir}")
    macro_id = macro_dir.name

    # Read macro AAA log to recover the original prompt
    macro_log_path = macro_dir / "aaa_pipeline.json"
    if macro_log_path.exists():
        macro_log = json.loads(macro_log_path.read_text(encoding="utf-8"))
        macro_prompt = macro_log.get("prompt", "")
        macro_seed = macro_log.get("seed_base", 42)
        category = macro_log.get("category", "Rock")
    else:
        # Fallback: just use the id as a hint
        macro_prompt = macro_id.replace("_", " ")
        macro_seed = 42
        category = "Rock"

    detail_id = args.detail_id or f"{macro_id}_detail"
    detail_prompt = macro_prompt + args.detail_prompt_suffix
    detail_seed = macro_seed + args.detail_seed_offset

    print(f"[detail-pyramid]")
    print(f"  macro: {macro_id} (prompt={macro_prompt!r})")
    print(f"  detail: {detail_id}")
    print(f"  detail prompt: {detail_prompt!r}")
    print(f"  detail seed: {detail_seed}")

    # Run the AAA pipeline for the detail layer
    cmd = [
        sys.executable, str(PIPELINE_DIR / "aaa_texture.py"),
        "--prompt", detail_prompt,
        "--id", detail_id,
        "--category", category,
        "--quality", args.detail_quality,
        "--variants", str(args.detail_variants),
        "--size", str(args.detail_size),
        "--seed-base", str(detail_seed),
        "--no-gate",  # detail layers can be lower quality; macro is the hero
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"  detail generation failed (rc={result.returncode})")
        sys.exit(1)

    # Write the pair manifest
    pair = {
        "macro_id": macro_id,
        "detail_id": detail_id,
        "macro_prompt": macro_prompt,
        "detail_prompt": detail_prompt,
        "detail_strength": args.detail_strength,
        "detail_uv_repeat": args.detail_uv_repeat,
        "category": category,
        "created": datetime.now(timezone.utc).isoformat(),
        "godot_hint": {
            "macro_uv_scale_m": 4.0,
            "detail_uv_scale_m": 4.0 / args.detail_uv_repeat,
            "blend_mode_albedo": "soft_light",
            "blend_mode_normal": "RNM (Reoriented Normal Mapping)",
            "detail_albedo_strength": args.detail_strength,
            "detail_normal_strength": args.detail_strength * 0.7,
            "shader_template_name": "macro_detail_v1",
        },
    }
    pair_path = macro_dir / "detail_pair.json"
    pair_path.write_text(json.dumps(pair, indent=2), encoding="utf-8")

    # Also drop a copy in the detail dir for findability
    detail_dir = LIBRARY / detail_id
    if detail_dir.exists():
        shutil.copy2(pair_path, detail_dir / "detail_pair.json")

    print(f"\ndone. macro={macro_dir} detail={detail_dir}")
    print(f"  pair manifest: {pair_path}")
    print(f"  use in Godot: macro UV @ 4m, detail UV @ {4.0/args.detail_uv_repeat:.2f}m, "
          f"blend strength {args.detail_strength}")


if __name__ == "__main__":
    main()
