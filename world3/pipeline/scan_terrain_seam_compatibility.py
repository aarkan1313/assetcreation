#!/usr/bin/env python3
"""Scan two real terrain sources for plausible seam-integration crop pairs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from build_terrain_seam_integration_proof import (
    crop_height_from_macro_space,
    load_height_m,
    parse_size,
    stats,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEFT_MACRO = ROOT / "toporeview/gloss_mountain_textured_master/layers/render_albedo.png"
DEFAULT_LEFT_MASK = ROOT / "toporeview/gloss_mountain_textured_master/layers/source_valid_mask.png"
DEFAULT_LEFT_HEIGHT = ROOT / "toporeview/gloss_mountain_textured_master/heightmap.png"
DEFAULT_LEFT_META = ROOT / "toporeview/gloss_mountain_textured_master/meta.json"
DEFAULT_RIGHT_MACRO = ROOT / "toporeview/chuculay_textured_master/layers/render_albedo.png"
DEFAULT_RIGHT_MASK = ROOT / "toporeview/chuculay_textured_master/layers/source_valid_mask.png"
DEFAULT_RIGHT_HEIGHT = ROOT / "toporeview/chuculay_textured_master/heightmap.png"
DEFAULT_RIGHT_META = ROOT / "toporeview/chuculay_textured_master/meta.json"
DEFAULT_OUT = ROOT / "docs/captures/review/terrain_seam_cross_source_candidates.json"
DEFAULT_PREVIEW = ROOT / "docs/captures/review/terrain_seam_cross_source_candidates_preview.png"


def parse_world_size(value: str) -> tuple[float, float]:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 2:
        raise ValueError("world size must be width_m,height_m")
    w, h = parts
    if w <= 0.0 or h <= 0.0:
        raise ValueError("world size values must be positive")
    return w, h


def load_source(prefix: str, macro_path: Path, mask_path: Path, height_path: Path, meta_path: Path) -> dict[str, Any]:
    macro = Image.open(macro_path).convert("RGB")
    mask = Image.open(mask_path).convert("L")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    height_m = load_height_m(height_path, meta)
    macro_w, macro_h = macro.size
    world_x = float(meta.get("world_size_x_m", meta.get("world_size_m", 1.0)))
    world_z = float(meta.get("world_size_z_m", meta.get("world_size_m", 1.0)))
    return {
        "id": prefix,
        "macro_path": macro_path,
        "mask_path": mask_path,
        "height_path": height_path,
        "meta_path": meta_path,
        "macro": macro,
        "mask": mask,
        "meta": meta,
        "height_m": height_m,
        "macro_size": (macro_w, macro_h),
        "mpp": (world_x / float(macro_w), world_z / float(macro_h)),
    }


def crop_px_from_world(source: dict[str, Any], crop_world_m: tuple[float, float]) -> tuple[int, int]:
    mpp_x, mpp_z = source["mpp"]
    w = max(8, int(round(crop_world_m[0] / mpp_x)))
    h = max(8, int(round(crop_world_m[1] / mpp_z)))
    macro_w, macro_h = source["macro_size"]
    return min(w, macro_w), min(h, macro_h)


def grid_positions(
    source: dict[str, Any],
    crop_px: tuple[int, int],
    samples_x: int,
    samples_y: int,
    margin_px: int,
) -> list[tuple[int, int, int, int]]:
    macro_w, macro_h = source["macro_size"]
    crop_w, crop_h = crop_px
    min_x = min(max(0, margin_px), max(0, macro_w - crop_w))
    min_y = min(max(0, margin_px), max(0, macro_h - crop_h))
    max_x = max(min_x, macro_w - crop_w - max(0, margin_px))
    max_y = max(min_y, macro_h - crop_h - max(0, margin_px))
    xs = np.linspace(min_x, max_x, max(1, samples_x), dtype=np.int32)
    ys = np.linspace(min_y, max_y, max(1, samples_y), dtype=np.int32)
    crops: list[tuple[int, int, int, int]] = []
    for y in ys:
        for x in xs:
            crops.append((int(x), int(y), int(crop_w), int(crop_h)))
    return crops


def sample_crop(source: dict[str, Any], crop: tuple[int, int, int, int], out_size: tuple[int, int]) -> dict[str, Any]:
    x, y, w, h = crop
    box = (x, y, x + w, y + h)
    rgb_img = source["macro"].crop(box).resize(out_size, Image.Resampling.BILINEAR)
    mask_img = source["mask"].crop(box).resize(out_size, Image.Resampling.BILINEAR)
    rgb = np.asarray(rgb_img, dtype=np.float32) / 255.0
    mask = np.asarray(mask_img, dtype=np.float32) / 255.0
    height = crop_height_from_macro_space(source["height_m"], source["macro_size"], crop, out_size)
    return {"rgb": rgb, "mask": mask, "height": height}


def descriptor(sample: dict[str, Any], edge: str, edge_px: int) -> dict[str, Any]:
    rgb = sample["rgb"]
    height = sample["height"]
    mask = sample["mask"]
    edge_slice = slice(-edge_px, None) if edge == "right" else slice(0, edge_px)
    rgb_edge = rgb[:, edge_slice, :]
    height_edge = height[:, edge_slice]
    mask_edge = mask[:, edge_slice]
    profile = height_edge.mean(axis=1)
    slope_profile = np.gradient(profile).astype(np.float32)
    return {
        "rgb_edge": rgb_edge,
        "height_profile": profile.astype(np.float32),
        "slope_profile": slope_profile,
        "valid_coverage": float(mask_edge.mean()),
        "height_range_m": float(height.max() - height.min()),
        "height_std_m": float(height.std()),
        "rgb_mean": [float(v) for v in rgb_edge.reshape(-1, 3).mean(axis=0)],
    }


def pair_cost(left_desc: dict[str, Any], right_desc: dict[str, Any]) -> dict[str, Any]:
    h_delta = left_desc["height_profile"] - right_desc["height_profile"]
    h_bias = float(np.median(h_delta))
    h_post = h_delta - h_bias
    slope_delta = left_desc["slope_profile"] - right_desc["slope_profile"]

    rgb_delta = left_desc["rgb_edge"] - right_desc["rgb_edge"]
    rgb_bias = np.median(rgb_delta.reshape(-1, 3), axis=0)
    rgb_post = rgb_delta - rgb_bias[None, None, :]

    h_stats = stats(h_post)
    slope_stats = stats(slope_delta)
    rgb_stats = stats(rgb_post)
    valid_penalty = max(0.0, 0.98 - min(left_desc["valid_coverage"], right_desc["valid_coverage"])) * 12.0
    relief_penalty = abs(left_desc["height_std_m"] - right_desc["height_std_m"]) / 30.0
    cost = (
        h_stats["p95"] / 10.0
        + slope_stats["p95"] / 2.0
        + rgb_stats["p95"] * 4.0
        + valid_penalty
        + relief_penalty
    )
    return {
        "cost": float(cost),
        "height_bias_m": h_bias,
        "height_delta_after_bias_m": h_stats,
        "slope_delta_m_per_output_row": slope_stats,
        "rgb_bias": [float(v) for v in rgb_bias],
        "rgb_delta_after_bias_01": rgb_stats,
        "valid_coverage_min": min(left_desc["valid_coverage"], right_desc["valid_coverage"]),
        "left_height_range_m": left_desc["height_range_m"],
        "right_height_range_m": right_desc["height_range_m"],
        "left_height_std_m": left_desc["height_std_m"],
        "right_height_std_m": right_desc["height_std_m"],
    }


def make_preview(
    left_source: dict[str, Any],
    right_source: dict[str, Any],
    candidates: list[dict[str, Any]],
    out_path: Path,
    preview_crop_size: tuple[int, int],
) -> None:
    if not candidates:
        return
    rows = min(6, len(candidates))
    cell_w, cell_h = preview_crop_size
    label_h = 28
    canvas = Image.new("RGB", (cell_w * 2, rows * (cell_h + label_h)), (14, 16, 16))
    draw = ImageDraw.Draw(canvas)
    for row, cand in enumerate(candidates[:rows]):
        y0 = row * (cell_h + label_h)
        left = left_source["macro"].crop(tuple_crop_box(cand["left_crop_px"])).resize(preview_crop_size, Image.Resampling.BILINEAR)
        right = right_source["macro"].crop(tuple_crop_box(cand["right_crop_px"])).resize(preview_crop_size, Image.Resampling.BILINEAR)
        canvas.paste(left, (0, y0 + label_h))
        canvas.paste(right, (cell_w, y0 + label_h))
        draw.text(
            (8, y0 + 7),
            f"#{row + 1} cost {cand['metrics']['cost']:.3f} h95 {cand['metrics']['height_delta_after_bias_m']['p95']:.2f}m rgb95 {cand['metrics']['rgb_delta_after_bias_01']['p95']:.3f}",
            fill=(235, 235, 235),
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def tuple_crop_box(crop: list[int] | tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, w, h = crop
    return int(x), int(y), int(x + w), int(y + h)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-id", default="gloss_mountain")
    parser.add_argument("--right-id", default="chuculay_chile")
    parser.add_argument("--left-macro", type=Path, default=DEFAULT_LEFT_MACRO)
    parser.add_argument("--left-valid-mask", type=Path, default=DEFAULT_LEFT_MASK)
    parser.add_argument("--left-heightmap", type=Path, default=DEFAULT_LEFT_HEIGHT)
    parser.add_argument("--left-meta", type=Path, default=DEFAULT_LEFT_META)
    parser.add_argument("--right-macro", type=Path, default=DEFAULT_RIGHT_MACRO)
    parser.add_argument("--right-valid-mask", type=Path, default=DEFAULT_RIGHT_MASK)
    parser.add_argument("--right-heightmap", type=Path, default=DEFAULT_RIGHT_HEIGHT)
    parser.add_argument("--right-meta", type=Path, default=DEFAULT_RIGHT_META)
    parser.add_argument("--crop-world-size-m", default="120,240")
    parser.add_argument("--scan-output-size", default="256,512")
    parser.add_argument("--samples-x", type=int, default=8)
    parser.add_argument("--samples-y", type=int, default=8)
    parser.add_argument("--source-margin-px", type=int, default=0)
    parser.add_argument("--edge-px", type=int, default=32)
    parser.add_argument("--min-valid-coverage", type=float, default=0.98)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--preview-out", type=Path, default=DEFAULT_PREVIEW)
    args = parser.parse_args()

    crop_world = parse_world_size(args.crop_world_size_m)
    out_size = parse_size(args.scan_output_size)
    left_source = load_source(args.left_id, args.left_macro, args.left_valid_mask, args.left_heightmap, args.left_meta)
    right_source = load_source(args.right_id, args.right_macro, args.right_valid_mask, args.right_heightmap, args.right_meta)

    left_crop_px = crop_px_from_world(left_source, crop_world)
    right_crop_px = crop_px_from_world(right_source, crop_world)
    left_crops = grid_positions(left_source, left_crop_px, args.samples_x, args.samples_y, args.source_margin_px)
    right_crops = grid_positions(right_source, right_crop_px, args.samples_x, args.samples_y, args.source_margin_px)

    edge_px = min(args.edge_px, out_size[0] // 3)
    left_descs = []
    for crop in left_crops:
        sample = sample_crop(left_source, crop, out_size)
        desc = descriptor(sample, "right", edge_px)
        if desc["valid_coverage"] >= args.min_valid_coverage:
            left_descs.append({"crop": crop, "descriptor": desc})

    right_descs = []
    for crop in right_crops:
        sample = sample_crop(right_source, crop, out_size)
        desc = descriptor(sample, "left", edge_px)
        if desc["valid_coverage"] >= args.min_valid_coverage:
            right_descs.append({"crop": crop, "descriptor": desc})

    candidates: list[dict[str, Any]] = []
    for left in left_descs:
        for right in right_descs:
            metrics = pair_cost(left["descriptor"], right["descriptor"])
            candidates.append(
                {
                    "left_crop_px": list(left["crop"]),
                    "right_crop_px": list(right["crop"]),
                    "metrics": metrics,
                }
            )
    candidates.sort(key=lambda item: item["metrics"]["cost"])
    candidates = candidates[: args.top_k]

    result = {
        "version": 1,
        "left_id": args.left_id,
        "right_id": args.right_id,
        "left_macro": str(args.left_macro),
        "right_macro": str(args.right_macro),
        "crop_world_size_m": list(crop_world),
        "left_crop_size_px": list(left_crop_px),
        "right_crop_size_px": list(right_crop_px),
        "scan_output_size_px": list(out_size),
        "edge_px": edge_px,
        "source_margin_px": args.source_margin_px,
        "left_candidates_scanned": len(left_descs),
        "right_candidates_scanned": len(right_descs),
        "top_candidates": candidates,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    make_preview(left_source, right_source, candidates, args.preview_out, (256, 256))
    print(json.dumps({"out": str(args.out), "preview": str(args.preview_out), "top": candidates[:3]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
