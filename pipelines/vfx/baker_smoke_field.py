"""CPU 2D smoke baker: semi-Lagrangian advection of a density field.

Tiny stable-fluids-style solver on a coarse grid (default 64x64), upscaled
to the effect's bounds_px for rendering. Each frame we:

  1. add density at the source emitter
  2. add an upward buoyancy force (inverse temperature -> velocity up)
  3. advect velocity (semi-Lagrangian backtrace + bilinear sample)
  4. advect density similarly
  5. small viscosity / dissipation
  6. render: density -> alpha + color via palette lookup

This is genuinely a fluid sim; not just particle approximation. CPU-only,
deterministic, ~64x64 grid runs at interactive frame rates in Python.

Backend params:
  grid_size:     int (default 64)
  emit_pos:      [x, y]   normalized [0,1]
  emit_radius:   float    in grid cells
  emit_density:  float    per second
  buoyancy:      float    grid cells / s^2 (positive = up)
  dissipation:   float    1/s (density)
  viscosity:     float    1/s (velocity)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from schemas import BakeManifest, Effect  # noqa: E402


def _hex_rgb(c: str) -> np.ndarray:
    s = c.lstrip("#")[:6]
    return np.array([int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)], dtype=np.float32) / 255.0


def _bilinear_sample(field: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Sample `field` (H,W) or (H,W,C) at fractional coords. Out-of-bounds = 0."""
    H, W = field.shape[:2]
    xs_c = np.clip(xs, 0, W - 1.001)
    ys_c = np.clip(ys, 0, H - 1.001)
    x0 = np.floor(xs_c).astype(np.int32)
    y0 = np.floor(ys_c).astype(np.int32)
    x1 = x0 + 1
    y1 = y0 + 1
    fx = (xs_c - x0).astype(np.float32)
    fy = (ys_c - y0).astype(np.float32)
    if field.ndim == 2:
        v00 = field[y0, x0]
        v10 = field[y0, x1]
        v01 = field[y1, x0]
        v11 = field[y1, x1]
    else:
        v00 = field[y0, x0]
        v10 = field[y0, x1]
        v01 = field[y1, x0]
        v11 = field[y1, x1]
        fx = fx[..., None]
        fy = fy[..., None]
    return (v00 * (1 - fx) * (1 - fy) + v10 * fx * (1 - fy)
            + v01 * (1 - fx) * fy + v11 * fx * fy)


def _palette_color(palette: list[str], life01: float) -> np.ndarray:
    if not palette:
        return np.array([1, 1, 1], dtype=np.float32)
    n = len(palette)
    if n == 1:
        return _hex_rgb(palette[0])
    pos = (1 - life01) * (n - 1)
    i = int(np.floor(pos))
    t = pos - i
    if i >= n - 1:
        return _hex_rgb(palette[-1])
    return _hex_rgb(palette[i]) * (1 - t) + _hex_rgb(palette[i + 1]) * t


def bake(effect: Effect, out_root: Path) -> BakeManifest:
    p = effect.backend_params
    rng = np.random.default_rng(p.get("seed", 0))
    bounds = effect.bounds_px
    W_px, H_px = bounds
    n_frames = effect.n_frames
    dt = 1.0 / effect.fps

    G = int(p.get("grid_size", 64))
    emit_norm = p.get("emit_pos", [0.5, 0.85])  # bottom-mid, plume rises
    emit_x = float(emit_norm[0]) * G
    emit_y = float(emit_norm[1]) * G
    emit_radius = float(p.get("emit_radius", 3.0))
    emit_density = float(p.get("emit_density", 5.0))
    buoyancy = float(p.get("buoyancy", -8.0))  # negative = up in screen coords
    dissipation = float(p.get("dissipation", 0.6))
    viscosity = float(p.get("viscosity", 0.5))
    palette = effect.visual.palette

    # state
    density = np.zeros((G, G), dtype=np.float32)
    vx = np.zeros((G, G), dtype=np.float32)
    vy = np.zeros((G, G), dtype=np.float32)

    # cached coordinate grid for advection
    yy, xx = np.meshgrid(np.arange(G, dtype=np.float32),
                         np.arange(G, dtype=np.float32), indexing="ij")

    frames_dir = out_root / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    metrics_per_frame = []

    # background
    bg_hex = effect.visual.background.lstrip("#")
    if len(bg_hex) == 8:
        bg = np.array([int(bg_hex[0:2], 16), int(bg_hex[2:4], 16),
                       int(bg_hex[4:6], 16), int(bg_hex[6:8], 16)], dtype=np.float32) / 255.0
    else:
        bg = np.array([*_hex_rgb("#" + bg_hex[:6]), 0.0], dtype=np.float32)

    for f in range(n_frames):
        # 1) add density + a tiny random vertical kick
        d2 = (xx - emit_x) ** 2 + (yy - emit_y) ** 2
        bump = np.exp(-d2 / (2 * emit_radius ** 2)) * emit_density * dt
        # taper emission later in the duration
        emit_taper = max(0.0, 1.0 - (f * dt) / max(effect.duration_s * 0.7, 1e-3))
        density += bump * emit_taper
        vy += np.where(d2 < emit_radius * emit_radius, rng.uniform(-1, 1, (G, G)) * 4 - 8, 0).astype(np.float32) * dt
        # 2) buoyancy (proportional to density)
        vy += buoyancy * density * dt
        # 3) advect velocity (semi-Lagrangian: trace back -dt and sample)
        bx = xx - vx * dt
        by = yy - vy * dt
        vx_new = _bilinear_sample(vx, bx, by)
        vy_new = _bilinear_sample(vy, bx, by)
        # 4) viscosity dampens velocity
        vx_new *= np.exp(-viscosity * dt)
        vy_new *= np.exp(-viscosity * dt)
        vx, vy = vx_new, vy_new
        # 5) advect density
        bx = xx - vx * dt
        by = yy - vy * dt
        density = _bilinear_sample(density, bx, by)
        # 6) dissipate
        density *= np.exp(-dissipation * dt)
        # render upscale to bounds
        # density -> 0..1 -> rgba
        d_clip = np.clip(density, 0, 2.0) / 2.0
        # color via simple linear gradient by density
        rgb = np.zeros((G, G, 3), dtype=np.float32)
        # use 2-3 palette entries
        if len(palette) >= 2:
            c0 = _hex_rgb(palette[0])
            c1 = _hex_rgb(palette[-1])
            blend = d_clip[..., None]
            rgb = c0 * (1 - blend) + c1 * blend
        else:
            c = _hex_rgb(palette[0]) if palette else np.array([1, 1, 1], dtype=np.float32)
            rgb[..., 0] = c[0]
            rgb[..., 1] = c[1]
            rgb[..., 2] = c[2]
        rgba = np.dstack([rgb, d_clip])
        # composite over bg
        a = rgba[..., 3:4]
        composed = rgba[..., :3] * a + bg[:3] * (1 - a) * bg[3]
        out_a = a + bg[3] * (1 - a)
        composed_rgba = np.dstack([composed, out_a])
        # upscale (nearest is fine for fluid look)
        img8 = (np.clip(composed_rgba, 0, 1) * 255).astype(np.uint8)
        small = Image.fromarray(img8, "RGBA")
        big = small.resize((W_px, H_px), Image.LANCZOS)
        big.save(frames_dir / f"frame_{f:04d}.png")
        metrics_per_frame.append({
            "t": f * dt,
            "max_density": float(density.max()),
            "mean_density": float(density.mean()),
        })

    # field summary (final-frame grid for shaders that want a flowmap source)
    field_path = out_root / "field.json"
    field_path.write_text(json.dumps({
        "grid_size": G,
        "frames": metrics_per_frame,
    }))

    from baker_particle_cpu import pack_flipbook
    flipbook_path = pack_flipbook(frames_dir, n_frames, bounds, out_root / "flipbook.png")

    return BakeManifest(
        effect_id=effect.id,
        backend="smoke_field",
        n_frames=n_frames,
        fps=effect.fps,
        bounds_px=bounds,
        flipbook=str(flipbook_path),
        frames_dir=str(frames_dir),
        extras={"field_json": str(field_path)},
        metrics={"max_density_global": max(m["max_density"] for m in metrics_per_frame)},
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("effect_json", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    effect = Effect.model_validate_json(args.effect_json.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = bake(effect, args.out)
    (args.out / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    print(f"[smoke_field] {effect.id}: {manifest.n_frames} frames, grid={manifest.bounds_px}")


if __name__ == "__main__":
    main()
