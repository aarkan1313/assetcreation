#!/usr/bin/env python3
"""Build first-pass M15-style feature masks for the M18 runtime slice."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


WORLD3 = Path(__file__).resolve().parents[1]
STACK = WORLD3 / "textures/source_stack/m18_guided_neighbor_slice_proof"
TOPO = WORLD3 / "toporeview/m18_guided_neighbor_slice_proof"


def res_path(path: Path) -> str:
    return "res://" + path.resolve().relative_to(WORLD3.resolve()).as_posix()


def load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def load_gray01(path: Path) -> np.ndarray:
    img = Image.open(path)
    arr = np.asarray(img)
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    if np.issubdtype(arr.dtype, np.integer) and int(arr.max()) > 255:
        return arr.astype(np.float32) / 65535.0
    return arr.astype(np.float32) / 255.0


def load_height_m(path: Path, meta: dict[str, Any]) -> np.ndarray:
    norm = load_gray01(path)
    elev_min = float(meta.get("elevation_min_m", 0.0))
    elev_range = float(meta.get("elevation_range_m", 1.0))
    return elev_min + norm * elev_range


def blur01(arr: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.0:
        return np.asarray(arr, dtype=np.float32)
    img = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), mode="L")
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32) / 255.0


def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def normalized(values: np.ndarray, p_lo: float = 5.0, p_hi: float = 95.0) -> np.ndarray:
    lo = float(np.percentile(values, p_lo))
    hi = float(np.percentile(values, p_hi))
    if hi <= lo:
        return np.zeros_like(values, dtype=np.float32)
    return np.clip((values - lo) / (hi - lo), 0.0, 1.0)


def save_gray(path: Path, arr: np.ndarray) -> dict[str, float]:
    values = np.clip(arr, 0.0, 1.0).astype(np.float32)
    Image.fromarray((values * 255.0).astype(np.uint8), mode="L").save(path)
    return {
        "mean": float(values.mean()),
        "coverage_gt_0_25": float(np.mean(values > 0.25)),
        "coverage_gt_0_50": float(np.mean(values > 0.50)),
        "p95": float(np.percentile(values, 95)),
    }


def main() -> int:
    macro = load_rgb(STACK / "source_macro_albedo.png")
    seam = load_gray01(STACK / "seam_integration_mask.png")
    meta = json.loads((TOPO / "meta.json").read_text(encoding="utf-8"))
    height = load_height_m(TOPO / "heightmap.png", meta)

    h, w = seam.shape
    luma = macro[:, :, 0] * 0.299 + macro[:, :, 1] * 0.587 + macro[:, :, 2] * 0.114
    r = macro[:, :, 0]
    g = macro[:, :, 1]
    b = macro[:, :, 2]

    world_x = float(meta.get("world_size_x_m", w))
    world_z = float(meta.get("world_size_z_m", h))
    dz, dx = np.gradient(height, world_z / max(h - 1, 1), world_x / max(w - 1, 1))
    slope = np.sqrt(dx * dx + dz * dz)
    slope_n = normalized(slope, 20.0, 98.0)
    low = blur01(normalized(height), 18.0)
    valley = normalized(low - normalized(height), 58.0, 98.0)

    x_norm = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    right_domain = smoothstep((x_norm - 0.49) / 0.16)
    seam_no_scatter = blur01(seam, 7.0)

    vegetation = np.clip((g * 1.22 - r * 0.58 - b * 0.32 - luma * 0.18 + 0.08) * 3.4, 0.0, 1.0)
    dark_organic = np.clip((0.64 - luma) * 2.6, 0.0, 1.0)
    warm_soil = np.clip((r * 0.78 + g * 0.36 - b * 0.55 - 0.18) * 2.0, 0.0, 1.0)
    pale_dust = np.clip((luma - 0.34) * 1.8, 0.0, 1.0)

    shrub = blur01(vegetation * dark_organic * (1.0 - slope_n * 0.45), 3.0)
    shrub *= 1.0 - right_domain * 0.88
    shrub *= 1.0 - seam_no_scatter * 0.45

    dry_grass = blur01((warm_soil * 0.55 + vegetation * 0.35 + pale_dust * 0.10) * (1.0 - slope_n * 0.55), 5.0)
    dry_grass = np.maximum(dry_grass, right_domain * 0.10 * (1.0 - slope_n))
    dry_grass *= 1.0 - seam_no_scatter * 0.35

    rock = blur01((slope_n ** 1.35) * (0.55 + dark_organic * 0.25 + right_domain * 0.35), 2.0)
    rock *= 1.0 - seam_no_scatter * 0.28

    soil = blur01((warm_soil * 0.65 + pale_dust * 0.35) * (1.0 - shrub * 0.85), 4.0)
    wash = blur01((valley * 0.78 + right_domain * valley * 0.32) * (1.0 - slope_n * 0.30), 3.0)
    no_scatter = np.clip(seam_no_scatter * 0.70 + slope_n * 0.42 + wash * 0.18, 0.0, 1.0)

    layers_dir = STACK / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "shrub_carryover_mask": shrub,
        "dry_grass_density_mask": dry_grass,
        "rock_cluster_mask": rock,
        "soil_exposure_mask": soil,
        "wash_line_mask": wash,
        "no_scatter_mask": no_scatter,
    }

    metrics: dict[str, Any] = {}
    layer_paths: dict[str, str] = {}
    for name, arr in outputs.items():
        out_path = layers_dir / f"{name}.png"
        metrics[name] = save_gray(out_path, arr)
        layer_paths[name] = res_path(out_path)

    summary_path = layers_dir / "feature_mask_metrics.json"
    summary_path.write_text(json.dumps({"version": 1, "metrics": metrics}, indent=2) + "\n", encoding="utf-8")

    manifest_path = STACK / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    layers = dict(manifest.get("layers", {}))
    layers.update(layer_paths)
    layers["feature_mask_metrics"] = res_path(summary_path)
    manifest["layers"] = layers
    manifest["m18_feature_masks"] = {
        "version": 1,
        "builder": "build_m18_slice_feature_masks.py",
        "policy": "derived_from_m18_runtime_macro_height_seam_mask_for_m15_overlay",
        "metrics": metrics,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"OK {summary_path.relative_to(WORLD3)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
