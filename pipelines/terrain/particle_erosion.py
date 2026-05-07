"""Particle / droplet hydraulic erosion (numpy implementation).

Per the SOTA report this complements Landlab's stream-power approach. Particle
erosion drops virtual rain droplets and tracks each as it flows downhill,
picking up sediment on slopes and depositing on flats. It's slower than
thermal but produces different visual results — sharper river carving.

Library option: github.com/setanarut/rainfall (Go) is what the report names,
but a portable numpy implementation is more useful here.

Usage:
  python particle_erosion.py --input height.png --out eroded.png --particles 50000
  python particle_erosion.py --bundle output/<id>  # in-place erode the bundle's height
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image


def droplet_erode(
    h: np.ndarray,
    n_particles: int = 50_000,
    max_lifetime: int = 30,
    inertia: float = 0.05,
    sediment_capacity: float = 4.0,
    min_slope: float = 0.01,
    erode_speed: float = 0.3,
    deposit_speed: float = 0.3,
    evaporate: float = 0.01,
    gravity: float = 4.0,
    seed: int = 42,
) -> np.ndarray:
    """Particle-based hydraulic erosion. Modifies a copy of h."""
    h = h.astype(np.float32).copy()
    rows, cols = h.shape
    rng = np.random.default_rng(seed)

    def gradient_at(px, py):
        # bilinear gradient via finite differences
        x0 = int(px); y0 = int(py)
        x0 = max(0, min(cols - 2, x0))
        y0 = max(0, min(rows - 2, y0))
        u = px - x0; v = py - y0
        h00 = h[y0, x0]; h10 = h[y0, x0 + 1]
        h01 = h[y0 + 1, x0]; h11 = h[y0 + 1, x0 + 1]
        gx = (h10 - h00) * (1 - v) + (h11 - h01) * v
        gy = (h01 - h00) * (1 - u) + (h11 - h10) * u
        height = h00 * (1 - u) * (1 - v) + h10 * u * (1 - v) + h01 * (1 - u) * v + h11 * u * v
        return gx, gy, height

    for i in range(n_particles):
        px = rng.uniform(0, cols - 1)
        py = rng.uniform(0, rows - 1)
        dx = 0.0; dy = 0.0
        speed = 1.0
        water = 1.0
        sediment = 0.0
        for _ in range(max_lifetime):
            x0 = int(px); y0 = int(py)
            if x0 < 1 or x0 >= cols - 2 or y0 < 1 or y0 >= rows - 2:
                break
            gx, gy, old_h = gradient_at(px, py)
            dx = dx * inertia - gx * (1 - inertia)
            dy = dy * inertia - gy * (1 - inertia)
            mag = math.sqrt(dx * dx + dy * dy)
            if mag < 1e-9:
                break
            dx /= mag; dy /= mag
            new_px = px + dx; new_py = py + dy
            if not (0 <= new_px < cols - 1 and 0 <= new_py < rows - 1):
                break
            _, _, new_h = gradient_at(new_px, new_py)
            dh = new_h - old_h

            cap = max(-dh * speed * water * sediment_capacity, min_slope)
            if sediment > cap or dh > 0:
                # deposit
                deposit = (sediment - cap) * deposit_speed if dh <= 0 else min(dh, sediment)
                sediment -= deposit
                u = px - x0; v = py - y0
                h[y0, x0] += deposit * (1 - u) * (1 - v)
                h[y0, x0 + 1] += deposit * u * (1 - v)
                h[y0 + 1, x0] += deposit * (1 - u) * v
                h[y0 + 1, x0 + 1] += deposit * u * v
            else:
                # erode
                amount = min((cap - sediment) * erode_speed, -dh)
                if amount > 0:
                    u = px - x0; v = py - y0
                    h[y0, x0] -= amount * (1 - u) * (1 - v)
                    h[y0, x0 + 1] -= amount * u * (1 - v)
                    h[y0 + 1, x0] -= amount * (1 - u) * v
                    h[y0 + 1, x0 + 1] -= amount * u * v
                    sediment += amount

            speed = math.sqrt(max(0, speed * speed + dh * gravity))
            water *= (1 - evaporate)
            px = new_px; py = new_py

    h = (h - h.min()) / (h.max() - h.min() + 1e-9)
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--bundle", type=Path, help="path to a terrain bundle dir; will erode height_16.png in place (backup .bak first)")
    ap.add_argument("--particles", type=int, default=50_000)
    ap.add_argument("--lifetime", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.bundle:
        height_path = args.bundle / "height_16.png"
        if not height_path.exists():
            raise SystemExit(f"no height_16.png in {args.bundle}")
        backup = args.bundle / "height_16.pre_particle.png"
        if not backup.exists():
            backup.write_bytes(height_path.read_bytes())
        h = np.asarray(Image.open(height_path), dtype=np.float32) / 65535.0
        print(f"[particle] eroding {h.shape} bundle with {args.particles} particles")
        h2 = droplet_erode(h, n_particles=args.particles, max_lifetime=args.lifetime, seed=args.seed)
        out = (h2 * 65535).clip(0, 65535).astype(np.uint16)
        Image.fromarray(out, mode="I;16").save(height_path)
        print(f"  done. backup at {backup.name}")
        return

    if not args.input or not args.out:
        raise SystemExit("either --bundle or both --input and --out required")
    im = Image.open(args.input)
    if im.mode == "I;16":
        h = np.asarray(im, dtype=np.float32) / 65535.0
    else:
        h = np.asarray(im.convert("L"), dtype=np.float32) / 255.0
    print(f"[particle] eroding {h.shape} with {args.particles} particles")
    h2 = droplet_erode(h, n_particles=args.particles, max_lifetime=args.lifetime, seed=args.seed)
    out_arr = (h2 * 65535).clip(0, 65535).astype(np.uint16)
    Image.fromarray(out_arr, mode="I;16").save(args.out)
    print(f"  wrote {args.out}")


if __name__ == "__main__":
    main()
