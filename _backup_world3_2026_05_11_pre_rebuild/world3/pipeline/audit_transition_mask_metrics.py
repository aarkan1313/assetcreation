#!/usr/bin/env python3
"""Audit runtime transition-mask geometry for M7 boundary scenes."""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent

DEFAULT_SCENE = ROOT / "scenes/capture_phase_m7/boundary_runtime_source_stack_context.tscn"
DEFAULT_RULES = ROOT / "jobs/biome_transition_rules.json"
DEFAULT_JSON = ROOT / "docs/captures/m7/transition_mask_metrics_source_stack_context.json"
DEFAULT_SHEET = ROOT / "docs/captures/m7/transition_mask_metrics_source_stack_context.png"


SCENE_DEFAULTS: dict[str, Any] = {
    "transition_rule_id": "biome_desert__grassland_base",
    "anchor_x_m": 128.0,
    "boundary_z_m": 1792.0,
    "chunk_size_m": 256.0,
    "view_radius_chunks": 1,
    "transition_width_m": 192.0,
    "transition_repeat_m": 128.0,
    "transition_strength": 0.92,
    "transition_mask_resolution": 128,
}


def write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO.resolve()).as_posix()


def parse_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def parse_scene(path: Path) -> dict[str, Any]:
    config = dict(SCENE_DEFAULTS)
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("["):
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if key in config:
            config[key] = parse_scalar(raw_value)
    config["transition_boundary_axis"] = "z"
    config["transition_boundary_world_m"] = float(config["boundary_z_m"])
    config["anchor_z_m"] = float(config["boundary_z_m"])
    return config


def load_rule(rules_path: Path, rule_id: str) -> dict[str, Any]:
    rules_doc = json.loads(rules_path.read_text(encoding="utf-8"))
    for rule in rules_doc.get("rules", []):
        if rule.get("id") == rule_id and rule.get("enabled", False):
            return rule
    raise ValueError(f"enabled transition rule not found: {rule_id}")


def fposmod(value: np.ndarray | float, modulus: float) -> np.ndarray | float:
    return np.mod(value, modulus)


def hash2(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return fposmod(np.sin(x * 12.9898 + y * 78.233) * 43758.5453, 1.0)


def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / max(edge1 - edge0, 0.000001), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def chunk_intersects(cx: int, cz: int, config: dict[str, Any]) -> bool:
    axis = str(config["transition_boundary_axis"])
    coord = cx if axis == "x" else cz
    chunk_size = float(config["chunk_size_m"])
    boundary = float(config["transition_boundary_world_m"])
    half_width = float(config["transition_width_m"]) * 0.5
    min_v = float(coord) * chunk_size
    max_v = min_v + chunk_size
    return boundary >= min_v - half_width and boundary <= max_v + half_width


def wanted_chunks(config: dict[str, Any]) -> list[tuple[int, int]]:
    chunk_size = float(config["chunk_size_m"])
    radius = int(config["view_radius_chunks"])
    center_x = math.floor(float(config["anchor_x_m"]) / chunk_size)
    center_z = math.floor(float(config["anchor_z_m"]) / chunk_size)
    return [
        (cx, cz)
        for cz in range(center_z - radius, center_z + radius + 1)
        for cx in range(center_x - radius, center_x + radius + 1)
    ]


def build_mask(cx: int, cz: int, config: dict[str, Any], rule: dict[str, Any]) -> np.ndarray:
    n = int(np.clip(int(config["transition_mask_resolution"]), 16, 1024))
    chunk_size = float(config["chunk_size_m"])
    min_x = float(cx) * chunk_size
    min_z = float(cz) * chunk_size
    width_m = max(float(config["transition_width_m"]), 0.001)
    repeat_m = max(float(config["transition_repeat_m"]), 0.001)
    noise_strength = float(rule.get("tuning", {}).get("noise_strength", 0.0))

    coords = (np.arange(n, dtype=np.float32) + 0.5) / float(n)
    fx, fz = np.meshgrid(coords, coords)
    global_x = min_x + fx * chunk_size
    global_z = min_z + fz * chunk_size

    if config["transition_boundary_axis"] == "x":
        across = global_x
        along = global_z
    else:
        across = global_z
        along = global_x

    noisy_offset = (hash2(global_x * 0.035, global_z * 0.035) - 0.5) * width_m * noise_strength
    raw_local = ((across - float(config["transition_boundary_world_m"])) + noisy_offset) / width_m + 0.5
    inside = ((raw_local >= 0.0) & (raw_local <= 1.0)).astype(np.float32)
    band = inside * smoothstep(0.0, 0.12, raw_local) * (1.0 - smoothstep(0.88, 1.0, raw_local))
    transition_u = np.clip(raw_local, 0.0, 1.0)
    transition_v = fposmod(along / repeat_m, 1.0)
    return np.dstack([band, transition_u, transition_v]).astype(np.float32)


def circular_abs_delta(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    delta = np.abs(a - b)
    return np.minimum(delta, 1.0 - delta)


def summarize_chunk(cx: int, cz: int, mask: np.ndarray) -> dict[str, Any]:
    band = mask[:, :, 0]
    u = mask[:, :, 1]
    v = mask[:, :, 2]
    return {
        "coord": [cx, cz],
        "band_coverage_ratio": round(float(np.mean(band > 0.001)), 6),
        "band_mean": round(float(np.mean(band)), 6),
        "band_max": round(float(np.max(band)), 6),
        "u_min": round(float(np.min(u)), 6),
        "u_max": round(float(np.max(u)), 6),
        "v_min": round(float(np.min(v)), 6),
        "v_max": round(float(np.max(v)), 6),
    }


def edge_checks(masks: dict[tuple[int, int], np.ndarray]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for (cx, cz), mask in sorted(masks.items()):
        right_key = (cx + 1, cz)
        down_key = (cx, cz + 1)
        if right_key in masks:
            left_edge = mask[:, -1, :]
            right_edge = masks[right_key][:, 0, :]
            checks.append(edge_summary([cx, cz], right_key, "x", left_edge, right_edge))
        if down_key in masks:
            top_edge = mask[-1, :, :]
            bottom_edge = masks[down_key][0, :, :]
            checks.append(edge_summary([cx, cz], down_key, "z", top_edge, bottom_edge))
    return checks


def edge_summary(
    a: list[int],
    b: tuple[int, int],
    axis: str,
    edge_a: np.ndarray,
    edge_b: np.ndarray,
) -> dict[str, Any]:
    band = np.abs(edge_a[:, 0] - edge_b[:, 0])
    u = np.abs(edge_a[:, 1] - edge_b[:, 1])
    v = circular_abs_delta(edge_a[:, 2], edge_b[:, 2])
    return {
        "from": a,
        "to": [b[0], b[1]],
        "axis": axis,
        "band_mean_abs": round(float(np.mean(band)), 6),
        "band_max_abs": round(float(np.max(band)), 6),
        "u_mean_abs": round(float(np.mean(u)), 6),
        "u_max_abs": round(float(np.max(u)), 6),
        "v_circular_mean_abs": round(float(np.mean(v)), 6),
        "v_circular_max_abs": round(float(np.max(v)), 6),
    }


def acceptance(summary: dict[str, Any]) -> dict[str, Any]:
    thresholds = {
        "band_coverage_min": 0.18,
        "band_coverage_max": 0.36,
        "band_peak_min": 0.95,
        "edge_band_mean_abs_max": 0.08,
        "edge_u_mean_abs_max": 0.08,
        "edge_v_circular_mean_abs_max": 0.03,
    }
    failures: list[str] = []
    if summary["intersecting_chunks"] < 1:
        failures.append("no_intersecting_chunks")
    if not (thresholds["band_coverage_min"] <= summary["band_coverage_mean"] <= thresholds["band_coverage_max"]):
        failures.append("band_coverage_outside_expected_range")
    if summary["band_peak_min"] < thresholds["band_peak_min"]:
        failures.append("band_peak_too_low")
    if summary["edge_band_mean_abs_max"] > thresholds["edge_band_mean_abs_max"]:
        failures.append("edge_band_discontinuity")
    if summary["edge_u_mean_abs_max"] > thresholds["edge_u_mean_abs_max"]:
        failures.append("edge_u_discontinuity")
    if summary["edge_v_circular_mean_abs_max"] > thresholds["edge_v_circular_mean_abs_max"]:
        failures.append("edge_v_discontinuity")
    return {
        "status": "PASS" if not failures else "REVIEW",
        "failures": failures,
        "thresholds": thresholds,
    }


def load_font(size: int) -> ImageFont.ImageFont:
    for name in ["DejaVuSans.ttf", "Arial.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_sheet(out_path: Path, chunk_summaries: list[dict[str, Any]], masks: dict[tuple[int, int], np.ndarray], summary: dict[str, Any]) -> None:
    tile = 160
    pad = 14
    header_h = 88
    footer_h = 48
    cols = max(1, len(chunk_summaries))
    width = cols * tile + (cols + 1) * pad
    height = header_h + tile + footer_h + pad * 2
    img = Image.new("RGB", (width, height), (28, 34, 30))
    draw = ImageDraw.Draw(img)
    font = load_font(14)
    small = load_font(11)
    title = (
        f"M7 transition mask QA | {summary['transition_rule_id']} | "
        f"{summary['acceptance']['status']}"
    )
    draw.text((pad, 14), title, fill=(238, 242, 232), font=font)
    draw.text(
        (pad, 40),
        (
            f"chunks {summary['intersecting_chunks']}/{summary['loaded_chunks']} | "
            f"coverage mean {summary['band_coverage_mean']:.3f} | "
            f"edge band mean max {summary['edge_band_mean_abs_max']:.3f}"
        ),
        fill=(190, 200, 184),
        font=small,
    )
    draw.text((pad, 62), "grayscale = boundary band weight stored in mask R", fill=(168, 176, 164), font=small)

    y0 = header_h
    for i, chunk in enumerate(chunk_summaries):
        cx, cz = chunk["coord"]
        band = masks[(cx, cz)][:, :, 0]
        thumb = Image.fromarray(np.clip(band * 255.0, 0, 255).astype(np.uint8), mode="L")
        thumb = thumb.resize((tile, tile), Image.Resampling.NEAREST).convert("RGB")
        x0 = pad + i * (tile + pad)
        img.paste(thumb, (x0, y0))
        draw.rectangle((x0, y0, x0 + tile - 1, y0 + tile - 1), outline=(118, 132, 112), width=1)
        label = f"chunk {cx},{cz}  cov {chunk['band_coverage_ratio']:.3f}"
        draw.text((x0 + 5, y0 + tile + 8), label, fill=(222, 226, 216), font=small)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def run(args: argparse.Namespace) -> dict[str, Any]:
    scene_path = Path(args.scene)
    rules_path = Path(args.rules)
    config = parse_scene(scene_path)
    rule = load_rule(rules_path, str(config["transition_rule_id"]))

    loaded = wanted_chunks(config)
    intersecting = [(cx, cz) for cx, cz in loaded if chunk_intersects(cx, cz, config)]
    masks = {(cx, cz): build_mask(cx, cz, config, rule) for cx, cz in intersecting}
    chunks = [summarize_chunk(cx, cz, masks[(cx, cz)]) for cx, cz in intersecting]
    edges = edge_checks(masks)

    coverage = [chunk["band_coverage_ratio"] for chunk in chunks]
    peaks = [chunk["band_max"] for chunk in chunks]
    edge_band = [edge["band_mean_abs"] for edge in edges] or [0.0]
    edge_u = [edge["u_mean_abs"] for edge in edges] or [0.0]
    edge_v = [edge["v_circular_mean_abs"] for edge in edges] or [0.0]
    summary = {
        "transition_rule_id": str(config["transition_rule_id"]),
        "loaded_chunks": len(loaded),
        "intersecting_chunks": len(intersecting),
        "band_coverage_mean": round(float(np.mean(coverage)) if coverage else 0.0, 6),
        "band_coverage_min": round(float(np.min(coverage)) if coverage else 0.0, 6),
        "band_coverage_max": round(float(np.max(coverage)) if coverage else 0.0, 6),
        "band_peak_min": round(float(np.min(peaks)) if peaks else 0.0, 6),
        "edge_checks": len(edges),
        "edge_band_mean_abs_max": round(float(np.max(edge_band)), 6),
        "edge_u_mean_abs_max": round(float(np.max(edge_u)), 6),
        "edge_v_circular_mean_abs_max": round(float(np.max(edge_v)), 6),
    }
    summary["acceptance"] = acceptance(summary)

    out = {
        "version": 1,
        "updated": date.today().isoformat(),
        "kind": "m7_transition_mask_metrics",
        "scene": repo_rel(scene_path),
        "rules": repo_rel(rules_path),
        "config": {
            "transition_rule_id": config["transition_rule_id"],
            "transition_boundary_axis": config["transition_boundary_axis"],
            "transition_boundary_world_m": config["transition_boundary_world_m"],
            "chunk_size_m": config["chunk_size_m"],
            "view_radius_chunks": config["view_radius_chunks"],
            "transition_width_m": config["transition_width_m"],
            "transition_repeat_m": config["transition_repeat_m"],
            "transition_mask_resolution": config["transition_mask_resolution"],
            "rule_noise_strength": float(rule.get("tuning", {}).get("noise_strength", 0.0)),
        },
        "summary": summary,
        "chunks": chunks,
        "edge_checks": edges,
    }

    out_json = Path(args.out_json)
    out_sheet = Path(args.out_sheet)
    write_lf(out_json, json.dumps(out, indent=2) + "\n")
    draw_sheet(out_sheet, chunks, masks, summary)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default=str(DEFAULT_SCENE))
    ap.add_argument("--rules", default=str(DEFAULT_RULES))
    ap.add_argument("--out-json", default=str(DEFAULT_JSON))
    ap.add_argument("--out-sheet", default=str(DEFAULT_SHEET))
    args = ap.parse_args()

    result = run(args)
    status = result["summary"]["acceptance"]["status"]
    print(f"{status}: wrote {repo_rel(Path(args.out_json))}")
    print(f"{status}: wrote {repo_rel(Path(args.out_sheet))}")
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
