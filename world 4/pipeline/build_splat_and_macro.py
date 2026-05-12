"""Anchor demo — Phase 3: build splat + macro from the heightmap.

Reads heightmap.png + meta.json from worlds/anchor/, computes:
  - D8 drainage accumulation (richdem)
  - Slope from height gradient
  - 5-channel splat (RGBA + implicit remainder) mapping to material slots:
      R = grass         (low elev, low slope, low drainage)
      G = dirt          (mid-low, transitional + drainage paths)
      B = rock_light    (mid-high, exposed)
      A = rock_dark     (high slope, steep faces)
      remainder = snow  (ridges / very high elev, the leftover)

Writes:
  - layers/splat_weights_rgba.png  (256x256 RGBA, 4 explicit channels)
  - layers/source_valid_mask.png   (256x256 L, all white for anchor)
  - layers/drainage.png            (debug: drainage accumulation)
  - layers/slope.png               (debug: slope magnitude)
  - layers/render_albedo.png       (composited per-pixel macro from 5 slot albedos)

The macro composite mirrors what the shader will compute at runtime —
baked here so the rendered terrain has M11-quality per-pixel character
even before the shader does anything fancy.

Run with the terrain venv (has richdem + PIL + numpy):
    D:/assets/pipelines/terrain/.venv/Scripts/python.exe build_splat_and_macro.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import richdem as rd
from PIL import Image, ImageFilter

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

ROOT = Path("D:/assets")
ANCHOR_DIR = ROOT / "world 4" / "the world 4" / "worlds" / "anchor"
MATERIALS_DIR = ROOT / "world 4" / "the world 4" / "materials" / "anchor"

# Slot mapping (matches what the .tres will bind)
SLOT_MATERIALS = {
    "grass":      "temperate_forest_grass",
    "dirt":       "temperate_forest_dirt",
    "rock_light": "temperate_forest_rock_light",
    "rock_dark":  "temperate_forest_rock_dark",
    "snow":       "temperate_forest_snow",
}

# ----------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------

def load_heightmap(path: Path, meta: dict) -> np.ndarray:
    """Load 16-bit heightmap PNG, return float meters."""
    img = Image.open(str(path))
    # 16-bit PNGs come in as I;16 mode; convert via numpy
    arr = np.asarray(img, dtype=np.uint16).astype(np.float32) / 65535.0
    return arr * meta["elevation_range_m"] + meta["elevation_min_m"]


# ----------------------------------------------------------------------
# Drainage + slope
# ----------------------------------------------------------------------

def compute_drainage(height_m: np.ndarray) -> np.ndarray:
    """D8 flow accumulation. Returns float array, 1.0 = single cell,
    larger = more flow. We log-normalize for use in splat math."""
    dem = rd.rdarray(height_m.astype(np.float64), no_data=-9999.0)
    # Fill depressions so flow doesn't get trapped
    filled = rd.FillDepressions(dem, in_place=False)
    accum = rd.FlowAccumulation(filled, method="D8")
    accum_np = np.asarray(accum, dtype=np.float32)
    # Log-normalize: drainage span is huge (1 to thousands), log makes it
    # human-perceivable. Then 0..1.
    log_accum = np.log1p(accum_np)
    norm = (log_accum - log_accum.min()) / max(log_accum.max() - log_accum.min(), 1e-6)
    return norm.astype(np.float32)


def compute_slope(height_m: np.ndarray) -> np.ndarray:
    """Slope magnitude as 0..1, percentile-normalized so a small tile's
    actual slope doesn't dominate the math."""
    gy, gx = np.gradient(height_m)
    mag = np.sqrt(gx * gx + gy * gy)
    p_lo = np.percentile(mag, 2)
    p_hi = np.percentile(mag, 98)
    return np.clip((mag - p_lo) / max(p_hi - p_lo, 1e-6), 0.0, 1.0).astype(np.float32)


# ----------------------------------------------------------------------
# Splat rule
# ----------------------------------------------------------------------

def build_splat(height_m: np.ndarray, slope: np.ndarray, drainage: np.ndarray) -> dict:
    """5-zone splat:
      grass     = low-flat (low elev, low slope, low drainage)
      dirt      = transitional + drainage paths
      rock_light = mid-high + slope
      rock_dark = steep
      snow      = high + flat (the implicit remainder)

    Each channel is float 0..1. We then normalize so they sum to ~1 per pixel.
    """
    elev_min = float(height_m.min())
    elev_range = max(float(height_m.max() - height_m.min()), 1e-6)
    h_norm = (height_m - elev_min) / elev_range  # 0..1

    # Channel formulas — each is a soft membership function
    # grass: low elevation, low slope, away from drainage
    w_grass = np.clip(
        (1.0 - h_norm * 0.8)
        * (1.0 - slope * 0.7)
        * (1.0 - drainage * 0.5),
        0.0, 1.0,
    )

    # dirt: low-to-mid elevation + drainage paths boost
    w_dirt = np.clip(
        (1.0 - np.abs(h_norm - 0.3) * 1.6)
        * (1.0 - slope * 0.4)
        + drainage * 0.5,
        0.0, 1.0,
    )

    # rock_light: mid-high elevation, moderate slope
    w_rock_light = np.clip(
        (1.0 - np.abs(h_norm - 0.55) * 1.4)
        * (0.3 + slope * 0.7),
        0.0, 1.0,
    )

    # rock_dark: steep slopes (dominant signal is slope)
    w_rock_dark = np.clip(
        slope * 1.2
        + np.maximum(h_norm - 0.6, 0.0) * 0.4,
        0.0, 1.0,
    )

    # snow: high elevation + flat (ridge tops)
    w_snow = np.clip(
        np.maximum(h_norm - 0.7, 0.0) * 2.0
        * (1.0 - slope * 0.5),
        0.0, 1.0,
    )

    # Smooth each channel slightly (avoid pixel-stairs)
    def smooth(arr: np.ndarray, radius: float = 1.2) -> np.ndarray:
        img = Image.fromarray((arr * 255).clip(0, 255).astype(np.uint8), mode="L")
        img = img.filter(ImageFilter.GaussianBlur(radius=radius))
        return np.asarray(img, dtype=np.float32) / 255.0

    w_grass = smooth(w_grass)
    w_dirt = smooth(w_dirt)
    w_rock_light = smooth(w_rock_light)
    w_rock_dark = smooth(w_rock_dark)
    w_snow = smooth(w_snow)

    # Power-shape so the dominant slot wins more cleanly per pixel
    stack = np.stack([w_grass, w_dirt, w_rock_light, w_rock_dark, w_snow], axis=2)
    stack = np.power(np.maximum(stack, 1e-5), 1.15)
    # Normalize so all 5 sum to 1 per pixel
    stack /= np.maximum(stack.sum(axis=2, keepdims=True), 1e-6)

    return {
        "grass": stack[..., 0],
        "dirt": stack[..., 1],
        "rock_light": stack[..., 2],
        "rock_dark": stack[..., 3],
        "snow": stack[..., 4],
    }


# ----------------------------------------------------------------------
# Macro composite
# ----------------------------------------------------------------------

def load_albedo(material_id: str, width: int, height: int) -> np.ndarray:
    path = MATERIALS_DIR / material_id / "albedo.png"
    img = Image.open(str(path)).convert("RGB")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    # Tile to (height, width)
    h, w = arr.shape[:2]
    rep_h = (height + h - 1) // h
    rep_w = (width + w - 1) // w
    return np.tile(arr, (rep_h, rep_w, 1))[:height, :width]


def compute_light(height_m: np.ndarray) -> np.ndarray:
    """M11-style lambertian light from height gradient.
    Normalize 1..99 percentile so the light values use the full 0..1 range."""
    gy, gx = np.gradient(height_m)
    raw = -(gx * 0.48 + gy * 0.82)
    p_lo = np.percentile(raw, 1)
    p_hi = np.percentile(raw, 99)
    return np.clip((raw - p_lo) / max(p_hi - p_lo, 1e-6), 0.0, 1.0).astype(np.float32)


def smooth_noise(width: int, height: int, grid: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    sw = max(2, int(np.ceil(width / grid)))
    sh = max(2, int(np.ceil(height / grid)))
    raw = rng.random((sh, sw), dtype=np.float32)
    img = Image.fromarray((raw * 255.0).astype(np.uint8), mode="L")
    img = img.resize((width, height), Image.Resampling.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def compose_macro(splat: dict, height_m: np.ndarray, slot_albedos: dict) -> np.ndarray:
    """Per-pixel macro = sum of (slot albedo × slot splat weight) + M11-style
    brightness modulation. This is what the shader will compute at runtime;
    we bake it so the saved PNG already reads as the terrain (helps debugging
    and the shader can mix bake vs runtime per the source_macro_strength)."""
    h, w = height_m.shape
    light = compute_light(height_m)
    low_noise = smooth_noise(w, h, 72, 4117)
    fine_noise = smooth_noise(w, h, 24, 4119)

    preview = np.zeros((h, w, 3), dtype=np.float32)
    for slot_name, slot_alb in slot_albedos.items():
        tinted = np.clip(
            slot_alb * (0.86 + light[:, :, None] * 0.18 + fine_noise[:, :, None] * 0.04),
            0.0, 1.0,
        )
        preview += tinted * splat[slot_name][:, :, None]

    # Subtle low-frequency wash for natural variation
    wash = (low_noise * 0.7 + fine_noise * 0.3 - 0.5)[:, :, None] * 0.04
    return np.clip(preview + wash, 0.0, 1.0)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main() -> int:
    layers_dir = ANCHOR_DIR / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)

    meta = json.loads((ANCHOR_DIR / "meta.json").read_text(encoding="utf-8"))
    print(f"[anchor/splat] loaded meta: elev {meta['elevation_min_m']:.1f}..{meta['elevation_max_m']:.1f}m world {meta['world_size_m']}m")

    height_m = load_heightmap(ANCHOR_DIR / "heightmap.png", meta)
    h, w = height_m.shape
    print(f"[anchor/splat] heightmap {h}x{w}px")

    print(f"[anchor/splat] computing D8 drainage...")
    drainage = compute_drainage(height_m)
    print(f"  drainage: {drainage.min():.3f}..{drainage.max():.3f} mean={drainage.mean():.3f}")

    print(f"[anchor/splat] computing slope...")
    slope = compute_slope(height_m)
    print(f"  slope: {slope.min():.3f}..{slope.max():.3f} mean={slope.mean():.3f}")

    print(f"[anchor/splat] building 5-channel splat...")
    splat = build_splat(height_m, slope, drainage)
    for name, ch in splat.items():
        print(f"  {name}: mean={ch.mean():.3f} max={ch.max():.3f}")

    # Save splat as RGBA (4 explicit channels; snow = implicit remainder)
    splat_rgba = np.stack(
        [splat["grass"], splat["dirt"], splat["rock_light"], splat["rock_dark"]],
        axis=2,
    )
    splat_path = layers_dir / "splat_weights_rgba.png"
    Image.fromarray((splat_rgba * 255).clip(0, 255).astype(np.uint8), mode="RGBA").save(splat_path)
    print(f"  wrote {splat_path}")

    # Valid mask (all white)
    valid_mask_path = layers_dir / "source_valid_mask.png"
    Image.fromarray(np.full((h, w), 255, dtype=np.uint8), mode="L").save(valid_mask_path)

    # Debug layers
    Image.fromarray((drainage * 255).clip(0, 255).astype(np.uint8), mode="L").save(layers_dir / "drainage.png")
    Image.fromarray((slope * 255).clip(0, 255).astype(np.uint8), mode="L").save(layers_dir / "slope.png")
    Image.fromarray((splat["snow"] * 255).clip(0, 255).astype(np.uint8), mode="L").save(layers_dir / "splat_snow.png")

    # Macro composite
    print(f"[anchor/splat] composing macro from 5 slot albedos...")
    slot_albedos = {
        name: load_albedo(mat_id, w, h)
        for name, mat_id in SLOT_MATERIALS.items()
    }
    macro = compose_macro(splat, height_m, slot_albedos)
    macro_path = layers_dir / "render_albedo.png"
    Image.fromarray((macro * 255).clip(0, 255).astype(np.uint8), mode="RGB").save(macro_path)
    print(f"  wrote {macro_path}  mean={macro.mean():.3f} std={macro.std():.3f}")

    print()
    print(f"[anchor/splat] DONE")
    print(f"  splat:       {splat_path}")
    print(f"  valid_mask:  {valid_mask_path}")
    print(f"  macro:       {macro_path}")
    print(f"  debug:       {layers_dir / 'drainage.png'}, slope.png, splat_snow.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
