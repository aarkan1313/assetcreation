"""Re-palette-lock existing texture albedos against a new anchor without
regenerating them. Useful when you re-roll the anchor of a kit and want
the rest of the kit to follow without spending compute on regeneration.

Usage:
    python relock_palette.py --anchor desert_sand --members desert_dry_brush desert_canyon_rock desert_dark_rock desert_salt_pan --strength 0.55
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

LIBRARY = Path(r"D:\assets\world\textures\library")
PIPELINE_DIR = Path(__file__).parent

sys.path.insert(0, str(PIPELINE_DIR))
from palette_lock import hist_match_lab, update_catalog_entry_from_qa  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", required=True)
    ap.add_argument("--members", nargs="+", required=True)
    ap.add_argument("--strength", type=float, default=0.55)
    args = ap.parse_args()

    anchor_albedo_path = LIBRARY / args.anchor / f"{args.anchor}_albedo.png"
    if not anchor_albedo_path.exists():
        raise SystemExit(f"anchor albedo not found: {anchor_albedo_path}")
    anchor_rgb = np.asarray(Image.open(anchor_albedo_path).convert("RGB"))

    for member in args.members:
        member_albedo_path = LIBRARY / member / f"{member}_albedo.png"
        if not member_albedo_path.exists():
            print(f"  skip {member}: albedo not found")
            continue

        # Restore from .pre_palette.png if it exists, so we hist-match
        # the un-locked version (avoids stacking palette pulls).
        pre_palette = member_albedo_path.with_suffix(".pre_palette.png")
        if pre_palette.exists():
            shutil.copy2(pre_palette, member_albedo_path)
            print(f"  restored {member} from .pre_palette before re-lock")

        member_rgb = np.asarray(Image.open(member_albedo_path).convert("RGB"))
        if anchor_rgb.shape != member_rgb.shape:
            anchor_for_match = np.asarray(
                Image.fromarray(anchor_rgb).resize(
                    (member_rgb.shape[1], member_rgb.shape[0]), Image.LANCZOS
                )
            )
        else:
            anchor_for_match = anchor_rgb

        # Backup if not already backed up.
        if not pre_palette.exists():
            shutil.copy2(member_albedo_path, pre_palette)

        matched = hist_match_lab(member_rgb, anchor_for_match,
                                 strength=args.strength)
        Image.fromarray(matched).save(member_albedo_path)
        print(f"  re-locked {member} (strength={args.strength})")

        # Re-run QA + refresh catalog entry.
        # Read category from the member's manifest to keep thresholds correct.
        manifest_path = LIBRARY / member / "aaa_pipeline.json"
        category = None
        if manifest_path.exists():
            try:
                m = json.loads(manifest_path.read_text(encoding="utf-8"))
                category = m.get("category")
            except json.JSONDecodeError:
                pass

        qa_cmd = [sys.executable, str(PIPELINE_DIR / "texture_qa.py"),
                  "--material", str(LIBRARY / member)]
        if category:
            qa_cmd += ["--category", category]
        subprocess.run(qa_cmd)
        update_catalog_entry_from_qa(member, args.strength)


if __name__ == "__main__":
    main()
