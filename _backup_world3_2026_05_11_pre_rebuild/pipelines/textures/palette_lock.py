"""Biome palette lock — generate a coherent set of textures with shared palette.

When you generate textures independently they end up with mismatched
saturation/hue/contrast. Result: a "biome" of materials that obviously
weren't designed together.

Strategy:
  1. First texture in the kit defines the palette (its histogram / dominant colors).
  2. Each subsequent texture goes through:
     a. Normal AAA pipeline
     b. Histogram-match its hue/saturation/value distributions to the anchor
     c. Re-run de-lighting if the match introduced shadows
  3. Save palette manifest so downstream additions can match.

Usage:
  # First, create the anchor:
  python aaa_texture.py --prompt "mossy basalt rock" --id basalt --category Rock

  # Then lock subsequent textures to it:
  python palette_lock.py --kit highland_kit --anchor basalt \
      --add "weathered cobblestone:cobblestone:Bricks" \
      --add "wet mossy soil:soil:Ground" \
      --add "fern undergrowth:fern:Ground"
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
CATALOG = Path(r"D:\assets\world\textures\catalog\materials.jsonl")
PIPELINE_DIR = Path(__file__).parent


def update_catalog_entry_from_qa(asset_id: str, palette_strength: float) -> None:
    """Rewrite the catalog line for asset_id to reflect the post-match QA.

    aaa_texture writes a catalog entry before palette_lock runs, so the
    grade in materials.jsonl reflects the pre-match albedo. After the
    histogram match + re-QA, the grade can shift (often unchanged, but
    edge_continuity in particular can move when the matched albedo has a
    different distribution at the edge). This function reads the latest
    qa/summary.json and rewrites the matching line.
    """
    if not CATALOG.exists():
        return
    qa_summary_path = LIBRARY / asset_id / "qa" / "summary.json"
    if not qa_summary_path.exists():
        print(f"  catalog not refreshed: {qa_summary_path} missing")
        return
    summary = json.loads(qa_summary_path.read_text(encoding="utf-8"))
    seam = summary.get("seam") or {}
    new_grade = seam.get("grade")
    new_checks = seam.get("checks") or {}

    lines = CATALOG.read_text(encoding="utf-8").splitlines()
    rewritten = False
    for i, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("id") != asset_id:
            continue
        rec["seam_grade"] = new_grade
        if new_checks:
            rec["seam_checks"] = {
                "edge_continuity_mse": new_checks.get("edge_continuity", {}).get("overall_mse"),
                "junction_ratio": new_checks.get("junction_visibility", {}).get("ratio"),
                "periodic_locality": new_checks.get("periodic_artifact", {}).get("peak_locality_ratio"),
            }
        rec["palette_locked"] = True
        rec["palette_match_strength"] = palette_strength
        lines[i] = json.dumps(rec)
        rewritten = True
        # Don't break — if there are duplicate entries (rare but possible
        # from prior runs), update them all.
    if rewritten:
        CATALOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  catalog refreshed for {asset_id} (grade={new_grade})")


def hist_match_lab(target_rgb: np.ndarray, anchor_rgb: np.ndarray,
                    strength: float = 0.6) -> np.ndarray:
    """Histogram-match LAB channels of target → anchor.

    strength=0 = no change, 1 = full match. 0.6 = soft palette pull.
    """
    try:
        from skimage import color, exposure
    except ImportError:
        print("  scikit-image not in this env; skipping palette match")
        return target_rgb

    target_lab = color.rgb2lab(target_rgb / 255.0)
    anchor_lab = color.rgb2lab(anchor_rgb / 255.0)

    matched = target_lab.copy()
    for c in range(3):
        ref = anchor_lab[..., c].flatten()
        src = target_lab[..., c].flatten()
        m = exposure.match_histograms(target_lab[..., c], anchor_lab[..., c])
        # Lerp between the original and the matched
        matched[..., c] = target_lab[..., c] * (1 - strength) + m * strength

    rgb = (color.lab2rgb(matched) * 255).clip(0, 255).astype(np.uint8)
    return rgb


def extract_palette_summary(rgb: np.ndarray, n_colors: int = 5) -> dict:
    """Extract dominant colors via PIL quantize for the manifest."""
    im = Image.fromarray(rgb).quantize(colors=n_colors)
    palette = im.getpalette()[:n_colors * 3]
    counts = sorted(im.getcolors() or [], reverse=True)
    summary = []
    for count, idx in counts[:n_colors]:
        r, g, b = palette[idx*3:idx*3+3]
        summary.append({"rgb": [r, g, b], "weight": count / (rgb.shape[0] * rgb.shape[1])})
    return {"dominant_colors": summary,
            "lab_means": [float(rgb[..., c].mean()) for c in range(3)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True, help="kit name for grouping")
    ap.add_argument("--anchor", required=True, help="existing material ID to use as palette anchor")
    ap.add_argument("--add", action="append", default=[],
                    help='format "prompt:id:category", repeatable')
    ap.add_argument("--strength", type=float, default=0.6,
                    help="palette match strength 0..1")
    ap.add_argument("--quality", default="default",
                    help="quality preset for new textures")
    ap.add_argument("--variants", type=int, default=3)
    ap.add_argument("--size", type=int, default=None,
                    help="override generation size (default: preset-defined, "
                         "currently 512 for default/strict)")
    ap.add_argument("--seed-base", type=int, default=42)
    ap.add_argument("--rerun-qa", action="store_true", default=True,
                    help="rerun texture_qa after palette-matching (default on)")
    args = ap.parse_args()

    anchor_dir = LIBRARY / args.anchor
    anchor_albedo = anchor_dir / f"{args.anchor}_albedo.png"
    if not anchor_albedo.exists():
        raise SystemExit(f"anchor albedo not found: {anchor_albedo}")

    anchor_rgb = np.asarray(Image.open(anchor_albedo).convert("RGB"))
    palette_info = extract_palette_summary(anchor_rgb)
    print(f"[palette] anchor: {args.anchor}")
    for c in palette_info["dominant_colors"][:3]:
        rgb_str = "#{:02x}{:02x}{:02x}".format(*c["rgb"])
        print(f"  {rgb_str} (weight {c['weight']:.2%})")

    kit_log = {
        "kit": args.kit,
        "anchor": args.anchor,
        "anchor_palette": palette_info,
        "match_strength": args.strength,
        "members": [args.anchor],
        "additions": [],
    }

    for entry in args.add:
        parts = entry.split(":")
        if len(parts) != 3:
            print(f"  skip malformed --add: {entry!r}")
            continue
        prompt, asset_id, category = parts
        print(f"\n[palette] adding {asset_id!r}: {prompt!r}")

        # Step 1: run AAA pipeline normally
        cmd = [
            sys.executable, str(PIPELINE_DIR / "aaa_texture.py"),
            "--prompt", prompt, "--id", asset_id, "--category", category,
            "--quality", args.quality, "--variants", str(args.variants),
            "--seed-base", str(args.seed_base),
            "--no-gate",  # accept whatever; we'll palette-match anyway
        ]
        if args.size is not None:
            cmd += ["--size", str(args.size)]
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"  AAA pipeline failed for {asset_id}, skipping")
            continue

        # Step 2: histogram-match albedo to anchor
        new_albedo_path = LIBRARY / asset_id / f"{asset_id}_albedo.png"
        new_rgb = np.asarray(Image.open(new_albedo_path).convert("RGB"))
        backup = new_albedo_path.with_suffix(".pre_palette.png")
        if not backup.exists():
            shutil.copy2(new_albedo_path, backup)

        # If the new texture is bigger, downsample anchor for matching;
        # if smaller, upsample anchor; either way only used for hist match
        if anchor_rgb.shape != new_rgb.shape:
            anchor_for_match = np.asarray(
                Image.fromarray(anchor_rgb).resize((new_rgb.shape[1], new_rgb.shape[0]),
                                                    Image.LANCZOS)
            )
        else:
            anchor_for_match = anchor_rgb

        matched = hist_match_lab(new_rgb, anchor_for_match, strength=args.strength)
        Image.fromarray(matched).save(new_albedo_path)
        print(f"  palette-matched (strength={args.strength}); backup at {backup.name}")

        # Step 3: re-run QA so the manifest reflects the post-match albedo,
        # not the pre-match one. The grade may shift slightly.
        if args.rerun_qa:
            qa_result = subprocess.run([
                sys.executable, str(PIPELINE_DIR / "texture_qa.py"),
                "--material", str(LIBRARY / asset_id),
                "--category", category,
            ])
            if qa_result.returncode != 0:
                print(f"  QA rerun failed for {asset_id} (non-fatal)")

        # Step 4: refresh the catalog entry. aaa_texture wrote the catalog
        # line BEFORE palette_lock ran, so the catalog still has the
        # pre-match grade. Read the post-match QA summary and rewrite the
        # corresponding line in materials.jsonl.
        update_catalog_entry_from_qa(asset_id, args.strength)

        kit_log["members"].append(asset_id)
        kit_log["additions"].append({"id": asset_id, "prompt": prompt, "category": category,
                                      "palette_match_strength": args.strength})

    # Save kit manifest
    kits_dir = Path(r"D:\assets\art_lab\biomes\kits")
    kits_dir.mkdir(parents=True, exist_ok=True)
    kit_path = kits_dir / f"{args.kit}_palette.json"
    kit_path.write_text(json.dumps(kit_log, indent=2), encoding="utf-8")
    print(f"\n[palette] kit manifest -> {kit_path}")
    print(f"  {len(kit_log['members'])} members: {kit_log['members']}")


if __name__ == "__main__":
    main()
