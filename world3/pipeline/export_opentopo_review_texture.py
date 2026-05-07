"""Build a procedural color review texture from aligned OpenTopo PNG layers.

This creates a visual diagnostic texture, not real imagery. It is meant for
Godot review scenes where a gray DEM/hillshade is too abstract to judge terrain
shape, seams, and material potential.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


DEFAULT_RAMP = np.array(
    [
        [62, 43, 31],
        [100, 62, 42],
        [145, 84, 51],
        [185, 132, 78],
        [209, 171, 111],
        [224, 207, 165],
        [238, 228, 198],
    ],
    dtype=np.float32,
) / 255.0


def read_layer(path: Path) -> np.ndarray:
    if not path.exists():
        raise SystemExit(f"Missing required layer: {path}")
    img = Image.open(path).convert("L")
    return np.asarray(img, dtype=np.float32) / 255.0


def ramp_color(values: np.ndarray, ramp: np.ndarray) -> np.ndarray:
    values = np.clip(values, 0.0, 1.0)
    pos = values * (len(ramp) - 1)
    lo = np.floor(pos).astype(np.int32)
    hi = np.clip(lo + 1, 0, len(ramp) - 1)
    t = (pos - lo)[..., None]
    return ramp[lo] * (1.0 - t) + ramp[hi] * t


def build_texture(layers_dir: Path, output: Path, noise_strength: float) -> dict:
    elevation = read_layer(layers_dir / "elevation_gray.png")
    hillshade = read_layer(layers_dir / "hillshade.png")
    slope = read_layer(layers_dir / "slope_deg.png")
    roughness = read_layer(layers_dir / "roughness.png")

    base = ramp_color(elevation, DEFAULT_RAMP)

    # Slope-biased gray rock on steep faces helps the canyon read as a 3D form.
    cliff_weight = np.clip((slope - 0.38) / 0.42, 0.0, 1.0) ** 1.35
    cliff_color = np.array([0.58, 0.52, 0.43], dtype=np.float32)
    color = base * (1.0 - cliff_weight[..., None] * 0.34) + cliff_color * cliff_weight[..., None] * 0.34

    # Hillshade keeps drainage and wall orientation legible in an unshaded material.
    shade = 0.58 + hillshade[..., None] * 0.62
    color *= shade

    # Roughness adds a terrain-detail cue without inventing photoreal imagery.
    detail = (roughness - 0.5)[..., None] * 0.18
    color += detail

    if noise_strength > 0.0:
        rng = np.random.default_rng(42)
        noise = rng.normal(0.0, noise_strength, elevation.shape)[..., None]
        color += noise

    color = np.clip(color, 0.0, 1.0)
    rgb = (color * 255.0).astype(np.uint8)
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(output)

    sidecar = {
        "output": str(output),
        "mode": "procedural_review_rgb",
        "not_real_imagery": True,
        "inputs": {
            "elevation": str(layers_dir / "elevation_gray.png"),
            "hillshade": str(layers_dir / "hillshade.png"),
            "slope": str(layers_dir / "slope_deg.png"),
            "roughness": str(layers_dir / "roughness.png"),
        },
        "recipe": {
            "base": "Grand Canyon style elevation color ramp",
            "cliff_blend": "steep slopes blend toward gray rock",
            "lighting": "hillshade multiplied into color",
            "detail": "roughness adds subtle brightness variation",
            "noise_strength": noise_strength,
        },
        "size_px": [int(rgb.shape[1]), int(rgb.shape[0])],
    }
    output.with_suffix(output.suffix + ".json").write_text(json.dumps(sidecar, indent=2))
    return sidecar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layers-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--noise-strength", type=float, default=0.012)
    args = ap.parse_args()

    sidecar = build_texture(args.layers_dir, args.output, args.noise_strength)
    print(f"OK {sidecar['output']} ({sidecar['size_px'][0]}x{sidecar['size_px'][1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
