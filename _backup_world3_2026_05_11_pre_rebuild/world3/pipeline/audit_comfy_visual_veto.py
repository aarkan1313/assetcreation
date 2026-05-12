#!/usr/bin/env python3
"""Advisory visual-veto audit for ComfyUI organic texture candidates.

This is intentionally a veto helper, not a promotion gate. It catches obvious
bright patch islands, colored/dark landmarks, and axis-aligned panel/row
structure, then leaves the remaining cases for human/vision review.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
LIBRARY = REPO / "world" / "textures" / "library"
LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def find_albedo(library_id: str) -> Path:
    mat_dir = LIBRARY / library_id
    preferred = mat_dir / f"{library_id}_albedo.png"
    if preferred.exists():
        return preferred
    matches = sorted(mat_dir.glob("*_albedo.png"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"no albedo found for {library_id}")


def load_rgb(path: Path) -> np.ndarray:
    img = Image.open(path).convert("RGB").resize((512, 512), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def axis_line_score(rgb: np.ndarray) -> float:
    img = Image.fromarray((rgb * 255).astype(np.uint8), mode="RGB")
    img = img.resize((256, 256), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=4))
    low = np.asarray(img, dtype=np.float32) / 255.0
    lum = low @ LUMA
    dx = np.abs(lum[:, 1:] - lum[:, :-1])
    dy = np.abs(lum[1:, :] - lum[:-1, :])
    col = dx.mean(axis=0)
    row = dy.mean(axis=1)
    col_score = float(np.percentile(col, 99) / (np.median(col) + 1e-6))
    row_score = float(np.percentile(row, 99) / (np.median(row) + 1e-6))
    return max(col_score, row_score)


def audit_image(library_id: str, path: Path, args: argparse.Namespace) -> dict[str, Any]:
    rgb = load_rgb(path)
    lum = rgb @ LUMA
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    sat = (mx - mn) / np.maximum(mx, 1e-6)
    median_rgb = np.median(rgb.reshape(-1, 3), axis=0)
    color_dist = np.linalg.norm(rgb - median_rgb, axis=2)
    green_excess = np.maximum(rgb[:, :, 1] - np.maximum(rgb[:, :, 0], rgb[:, :, 2]), 0.0)
    median_lum = float(np.median(lum))

    outlier_ratio = float(np.mean(color_dist > args.color_outlier_threshold))
    bright_green_ratio = float(np.mean((green_excess > args.green_excess_threshold) & (sat > 0.25)))
    dark_landmark_ratio = float(np.mean(lum < median_lum - args.dark_delta_threshold))
    bright_landmark_ratio = float(np.mean(lum > median_lum + args.bright_delta_threshold))
    line_score = axis_line_score(rgb)

    flags: list[str] = []
    if bright_green_ratio >= args.bright_green_ratio:
        flags.append("bright_green_patch_islands")
    if outlier_ratio >= args.color_outlier_ratio:
        flags.append("colored_landmark_outliers")
    if dark_landmark_ratio >= args.dark_landmark_ratio:
        flags.append("dark_landmark_blotches")
    if bright_landmark_ratio >= args.bright_landmark_ratio:
        flags.append("bright_landmark_flecks")
    if line_score >= args.axis_line_score:
        flags.append("axis_aligned_panel_or_row_structure")

    return {
        "id": library_id,
        "albedo": path.resolve().relative_to(REPO.resolve()).as_posix(),
        "status": "veto" if flags else "needs_visual_review",
        "flags": flags,
        "metrics": {
            "luma_mean": round(float(lum.mean()), 6),
            "saturation_mean": round(float(sat.mean()), 6),
            "color_outlier_ratio": round(outlier_ratio, 6),
            "bright_green_ratio": round(bright_green_ratio, 6),
            "dark_landmark_ratio": round(dark_landmark_ratio, 6),
            "bright_landmark_ratio": round(bright_landmark_ratio, 6),
            "axis_line_score": round(line_score, 6),
        },
    }


def write_markdown(results: list[dict[str, Any]], out_path: Path) -> None:
    lines = [
        "# ComfyUI Visual Veto Audit",
        "",
        f"Date: {date.today().isoformat()}",
        "",
        "This advisory audit catches obvious organic-material visual failures",
        "before sidecar staging. `needs_visual_review` is not a pass; it only",
        "means the heuristic did not catch a hard veto.",
        "",
        "| Material | Status | Flags | Green patches | Outliers | Axis line |",
        "|----------|--------|-------|---------------|----------|-----------|",
    ]
    for result in results:
        metrics = result["metrics"]
        lines.append(
            f"| `{result['id']}` | {result['status']} | "
            f"{', '.join(result['flags']) or '-'} | "
            f"{metrics['bright_green_ratio']} | "
            f"{metrics['color_outlier_ratio']} | "
            f"{metrics['axis_line_score']} |"
        )
    write_lf(out_path, "\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--library-id", action="append", required=True)
    ap.add_argument("--out-json", default=str(ROOT / "docs/M8_COMFY_VISUAL_VETO_AUDIT.json"))
    ap.add_argument("--out-md", default=str(ROOT / "docs/M8_COMFY_VISUAL_VETO_AUDIT.md"))
    ap.add_argument("--color-outlier-threshold", type=float, default=0.28)
    ap.add_argument("--green-excess-threshold", type=float, default=0.12)
    ap.add_argument("--bright-green-ratio", type=float, default=0.04)
    ap.add_argument("--color-outlier-ratio", type=float, default=0.03)
    ap.add_argument("--dark-delta-threshold", type=float, default=0.20)
    ap.add_argument("--bright-delta-threshold", type=float, default=0.20)
    ap.add_argument("--dark-landmark-ratio", type=float, default=0.01)
    ap.add_argument("--bright-landmark-ratio", type=float, default=0.01)
    ap.add_argument("--axis-line-score", type=float, default=1.75)
    args = ap.parse_args()

    results = [audit_image(library_id, find_albedo(library_id), args) for library_id in args.library_id]
    out = {
        "version": 1,
        "updated": date.today().isoformat(),
        "policy": "advisory_veto_helper_not_promotion_gate",
        "results": results,
    }
    out_json = Path(args.out_json)
    write_lf(out_json, json.dumps(out, indent=2) + "\n")
    write_markdown(results, Path(args.out_md))
    print(f"audited {len(results)} materials; wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
