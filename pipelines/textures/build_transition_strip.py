"""Build catalog-driven transition strips between two terrain materials.

This is the M2 prototype path: it does not try to solve biome transitions
permanently. It gives us deterministic transition assets and hard-cut
comparisons so M4 has concrete material pairs to design against.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "world3/materials/catalog.json"
DEFAULT_OUT_ROOT = ROOT / "world3/textures/transitions"
DEFAULT_CAPTURE_ROOT = ROOT / "world3/docs/captures/transitions"

MAPS = ("albedo", "normal", "roughness", "height", "ao")


def load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    materials = {}
    for item in data.get("materials", []):
        materials[item["id"]] = item
    return materials


def resolve_asset(path_text: str | None) -> Path:
    if not path_text:
        return ROOT / "__missing_asset__"
    p = Path(path_text.replace("\\", "/"))
    if p.is_absolute():
        return p
    return ROOT / p


def load_rgb(path: Path, size: int) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    if img.size != (size, size):
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def load_gray(path: Path, size: int, default: float) -> np.ndarray:
    if not path.exists():
        return np.full((size, size), default, dtype=np.float32)
    img = Image.open(path).convert("L")
    if img.size != (size, size):
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def tile_to_strip(tile: np.ndarray, width: int, height: int) -> np.ndarray:
    reps_y = int(np.ceil(height / tile.shape[0]))
    reps_x = int(np.ceil(width / tile.shape[1]))
    if tile.ndim == 2:
        tiled = np.tile(tile, (reps_y, reps_x))
        return tiled[:height, :width]
    tiled = np.tile(tile, (reps_y, reps_x, 1))
    return tiled[:height, :width, :]


def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def make_noise(width: int, height: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coarse_w = max(8, width // 96)
    coarse_h = max(8, height // 96)
    coarse = rng.random((coarse_h, coarse_w), dtype=np.float32)
    img = Image.fromarray((coarse * 255.0).astype(np.uint8), mode="L")
    img = img.resize((width, height), Image.Resampling.BICUBIC)
    noise = np.asarray(img, dtype=np.float32) / 255.0
    noise = (noise - float(noise.min())) / max(float(noise.max() - noise.min()), 1e-6)
    return noise


def make_mask(width: int, height: int, seed: int, noise_strength: float) -> np.ndarray:
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    x = np.repeat(x, height, axis=0)
    noise = make_noise(width, height, seed)
    warped = x + (noise - 0.5) * noise_strength
    return smoothstep(0.18, 0.82, warped)


def save_rgb(arr: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray((np.clip(arr, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), mode="RGB")
    img.save(path)


def save_gray(arr: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray((np.clip(arr, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), mode="L")
    img.save(path)


def blend_normals(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> np.ndarray:
    na = a * 2.0 - 1.0
    nb = b * 2.0 - 1.0
    m = mask[:, :, None]
    n = na * (1.0 - m) + nb * m
    length = np.linalg.norm(n, axis=2, keepdims=True)
    n = n / np.maximum(length, 1e-6)
    return n * 0.5 + 0.5


def hard_cut(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    out = a.copy()
    mid = out.shape[1] // 2
    out[:, mid:] = b[:, mid:]
    return out


def luminance(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
    maxc = np.max(rgb, axis=-1)
    minc = np.min(rgb, axis=-1)
    delta = maxc - minc

    h = np.zeros_like(maxc)
    valid = delta > 1e-6

    r_is_max = valid & (maxc == r)
    g_is_max = valid & (maxc == g)
    b_is_max = valid & (maxc == b)

    h[r_is_max] = np.mod((g[r_is_max] - b[r_is_max]) / delta[r_is_max], 6.0)
    h[g_is_max] = ((b[g_is_max] - r[g_is_max]) / delta[g_is_max]) + 2.0
    h[b_is_max] = ((r[b_is_max] - g[b_is_max]) / delta[b_is_max]) + 4.0
    h = np.mod(h / 6.0, 1.0)

    s = np.zeros_like(maxc)
    bright = maxc > 1e-6
    s[bright] = delta[bright] / maxc[bright]
    return np.stack([h, s, maxc], axis=-1)


def circular_hue_mean(hue: np.ndarray, saturation: np.ndarray) -> float:
    weights = np.clip(saturation, 0.0, 1.0)
    total_weight = float(np.sum(weights))
    if total_weight <= 1e-6:
        return 0.0
    angles = hue * math.tau
    x = float(np.sum(np.cos(angles) * weights)) / total_weight
    y = float(np.sum(np.sin(angles) * weights)) / total_weight
    angle = math.atan2(y, x)
    if angle < 0.0:
        angle += math.tau
    return angle / math.tau


def high_frequency_energy(rgb: np.ndarray) -> float:
    lum = luminance(rgb)
    dx = float(np.mean(np.abs(np.diff(lum, axis=1)))) if lum.shape[1] > 1 else 0.0
    dy = float(np.mean(np.abs(np.diff(lum, axis=0)))) if lum.shape[0] > 1 else 0.0
    return dx + dy


def normal_energy(normal: np.ndarray) -> float:
    n = normal * 2.0 - 1.0
    xy = np.sqrt(n[..., 0] * n[..., 0] + n[..., 1] * n[..., 1])
    return float(np.mean(xy))


def transition_scores(
    a_maps: dict[str, np.ndarray],
    b_maps: dict[str, np.ndarray],
    transition_albedo: np.ndarray,
    hard_edge_delta: float,
) -> dict[str, float]:
    a_hsv = rgb_to_hsv(a_maps["albedo"])
    b_hsv = rgb_to_hsv(b_maps["albedo"])
    a_hue = circular_hue_mean(a_hsv[..., 0], a_hsv[..., 1])
    b_hue = circular_hue_mean(b_hsv[..., 0], b_hsv[..., 1])
    hue_delta = abs(a_hue - b_hue)
    hue_delta = min(hue_delta, 1.0 - hue_delta)

    a_freq = high_frequency_energy(a_maps["albedo"])
    b_freq = high_frequency_energy(b_maps["albedo"])
    a_normal_energy = normal_energy(a_maps["normal"])
    b_normal_energy = normal_energy(b_maps["normal"])

    mid = transition_albedo.shape[1] // 2
    transition_center_delta = float(
        np.mean(np.abs(transition_albedo[:, mid - 1] - transition_albedo[:, mid]))
    )
    edge_improvement = 1.0 - transition_center_delta / max(hard_edge_delta, 1e-6)

    lum = luminance(transition_albedo)
    transition_gradient_p95 = float(np.percentile(np.abs(np.diff(lum, axis=1)), 95.0))

    return {
        "source_hue_delta": round(float(hue_delta), 6),
        "source_value_delta": round(float(abs(np.mean(a_hsv[..., 2]) - np.mean(b_hsv[..., 2]))), 6),
        "source_saturation_delta": round(float(abs(np.mean(a_hsv[..., 1]) - np.mean(b_hsv[..., 1]))), 6),
        "roughness_mean_abs_delta": round(float(np.mean(np.abs(a_maps["roughness"] - b_maps["roughness"]))), 6),
        "normal_energy_delta": round(float(abs(a_normal_energy - b_normal_energy)), 6),
        "normal_mean_abs_delta": round(float(np.mean(np.abs(a_maps["normal"] - b_maps["normal"]))), 6),
        "visible_frequency_delta": round(float(abs(a_freq - b_freq)), 6),
        "hard_edge_mean_abs_albedo_delta": round(float(hard_edge_delta), 6),
        "transition_center_albedo_delta": round(float(transition_center_delta), 6),
        "edge_delta_improvement_ratio": round(float(edge_improvement), 6),
        "transition_gradient_p95": round(float(transition_gradient_p95), 6),
    }


def review_hints(scores: dict[str, float]) -> list[str]:
    hints: list[str] = []
    if scores["source_value_delta"] >= 0.18:
        hints.append("value_grade_before_runtime")
    if scores["source_hue_delta"] >= 0.16:
        hints.append("palette_grade_before_runtime")
    if scores["roughness_mean_abs_delta"] >= 0.18:
        hints.append("roughness_grade_before_runtime")
    if scores["normal_energy_delta"] >= 0.08:
        hints.append("normal_energy_mismatch")
    if scores["visible_frequency_delta"] >= 0.035:
        hints.append("visible_frequency_mismatch")
    if scores["edge_delta_improvement_ratio"] < 0.55:
        hints.append("transition_band_needs_wider_or_stronger_mask")
    return hints


def material_maps(material: dict[str, Any], size: int, width: int, height: int) -> dict[str, np.ndarray]:
    pbr = material.get("pbr_maps", {})
    albedo = tile_to_strip(load_rgb(resolve_asset(pbr["albedo"]), size), width, height)
    normal_path = resolve_asset(pbr.get("normal", ""))
    normal = tile_to_strip(load_rgb(normal_path, size), width, height) if normal_path.exists() else np.dstack([
        np.full((height, width), 0.5, dtype=np.float32),
        np.full((height, width), 0.5, dtype=np.float32),
        np.full((height, width), 1.0, dtype=np.float32),
    ])
    roughness = tile_to_strip(load_gray(resolve_asset(pbr.get("roughness", "")), size, 0.85), width, height)
    height_map = tile_to_strip(load_gray(resolve_asset(pbr.get("height", "")), size, 0.5), width, height)
    ao = tile_to_strip(load_gray(resolve_asset(pbr.get("ao", "")), size, 1.0), width, height)
    return {
        "albedo": albedo,
        "normal": normal,
        "roughness": roughness,
        "height": height_map,
        "ao": ao,
    }


def pair_seed(a_id: str, b_id: str) -> int:
    digest = hashlib.sha256(f"{a_id}->{b_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little", signed=False)


def build_pair(
    a_id: str,
    b_id: str,
    catalog: dict[str, dict[str, Any]],
    out_root: Path,
    capture_root: Path,
    tile_px: int,
    tiles_wide: int,
    noise_strength: float,
) -> dict[str, Any]:
    if a_id not in catalog:
        raise SystemExit(f"unknown material id: {a_id}")
    if b_id not in catalog:
        raise SystemExit(f"unknown material id: {b_id}")

    width = tile_px * tiles_wide
    height = tile_px
    seed = pair_seed(a_id, b_id)
    mask = make_mask(width, height, seed, noise_strength)

    a_maps = material_maps(catalog[a_id], tile_px, width, height)
    b_maps = material_maps(catalog[b_id], tile_px, width, height)

    out_dir = out_root / f"{a_id}__{b_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    transition = {
        "albedo": a_maps["albedo"] * (1.0 - mask[:, :, None]) + b_maps["albedo"] * mask[:, :, None],
        "normal": blend_normals(a_maps["normal"], b_maps["normal"], mask),
        "roughness": a_maps["roughness"] * (1.0 - mask) + b_maps["roughness"] * mask,
        "height": a_maps["height"] * (1.0 - mask) + b_maps["height"] * mask,
        "ao": a_maps["ao"] * (1.0 - mask) + b_maps["ao"] * mask,
    }

    save_rgb(transition["albedo"], out_dir / "albedo.png")
    save_rgb(transition["normal"], out_dir / "normal.png")
    save_gray(transition["roughness"], out_dir / "roughness.png")
    save_gray(transition["height"], out_dir / "height.png")
    save_gray(transition["ao"], out_dir / "ao.png")
    save_gray(mask, out_dir / "mask.png")

    hard = hard_cut(a_maps["albedo"], b_maps["albedo"])
    transition_albedo = transition["albedo"]
    preview_path = capture_root / f"{a_id}__{b_id}_hard_vs_transition.png"
    make_preview(hard, transition_albedo, a_id, b_id, preview_path)

    edge_delta = float(np.mean(np.abs(a_maps["albedo"][:, width // 2 - 1] - b_maps["albedo"][:, width // 2])))
    scores = transition_scores(a_maps, b_maps, transition_albedo, edge_delta)
    manifest = {
        "pair": [a_id, b_id],
        "seed": seed,
        "tile_px": tile_px,
        "tiles_wide": tiles_wide,
        "noise_strength": noise_strength,
        "outputs": {name: str((out_dir / f"{name}.png").relative_to(ROOT)).replace("\\", "/") for name in MAPS},
        "mask": str((out_dir / "mask.png").relative_to(ROOT)).replace("\\", "/"),
        "preview": str(preview_path.relative_to(ROOT)).replace("\\", "/"),
        "hard_edge_mean_abs_albedo_delta": round(edge_delta, 6),
        "scores": scores,
        "review_hints": review_hints(scores),
        "status": "prototype_transition_strip",
    }
    (out_dir / "manifest.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return manifest


def make_preview(hard: np.ndarray, transition: np.ndarray, a_id: str, b_id: str, path: Path) -> None:
    gap = 18
    label_h = 58
    hard_img = Image.fromarray((np.clip(hard, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), mode="RGB")
    trans_img = Image.fromarray((np.clip(transition, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), mode="RGB")
    sheet = Image.new("RGB", (hard_img.width, hard_img.height * 2 + label_h * 2 + gap), (18, 20, 20))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 18), f"{a_id} -> {b_id}: hard cut", fill=(245, 245, 245), font=font)
    sheet.paste(hard_img, (0, label_h))
    y2 = label_h + hard_img.height + gap
    draw.text((18, y2 + 18), f"{a_id} -> {b_id}: noisy transition strip", fill=(245, 245, 245), font=font)
    sheet.paste(trans_img, (0, y2 + label_h))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def parse_pair(text: str) -> tuple[str, str]:
    if ":" in text:
        a, b = text.split(":", 1)
    elif "," in text:
        a, b = text.split(",", 1)
    else:
        raise argparse.ArgumentTypeError("pair must be A:B or A,B")
    return a.strip(), b.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    ap.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    ap.add_argument("--tile-px", type=int, default=512)
    ap.add_argument("--tiles-wide", type=int, default=6)
    ap.add_argument("--noise-strength", type=float, default=0.22)
    ap.add_argument(
        "--pair",
        action="append",
        type=parse_pair,
        required=True,
        help="Material pair as A:B. Repeat for multiple pairs.",
    )
    args = ap.parse_args()

    catalog = load_catalog(args.catalog)
    manifests = []
    for a_id, b_id in args.pair:
        manifest = build_pair(
            a_id,
            b_id,
            catalog,
            args.out_root,
            args.capture_root,
            args.tile_px,
            args.tiles_wide,
            args.noise_strength,
        )
        manifests.append(manifest)
        print(f"OK {a_id}->{b_id} preview={manifest['preview']}")

    index = {
        "catalog": str(args.catalog.relative_to(ROOT)).replace("\\", "/"),
        "pairs": manifests,
    }
    args.out_root.mkdir(parents=True, exist_ok=True)
    (args.out_root / "index.json").write_bytes((json.dumps(index, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
