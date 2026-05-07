"""CPU particle baker. Numpy SoA, no GPU, no Taichi.

Good for: projectiles (fireballs, ice shards), bursts (sparks, explosions),
trails (chaff, dust). Produces:
  frames/frame_NNNN.png    one PNG per simulated frame, RGBA
  flipbook.png             grid atlas of all frames (rows × cols)
  particles.json           per-frame summary stats (count, energy, bbox)

Backend params (effect.backend_params):
  emitter:     "burst" | "stream"          burst spawns N at t=0; stream spawns rate/sec
  count:       int                         particle count (burst) or per-second (stream)
  initial_speed:  float (px/s)
  speed_jitter:   float (px/s)
  direction_deg:  float (0=right, 90=up)
  spread_deg:     float                    cone half-angle
  gravity:        [gx, gy] (px/s^2)        positive y = down (screen)
  drag:           float (1/s)
  size_px:        float
  size_jitter:    float
  fade:           float (1=full life, lower=earlier fade-out)
  emission_pos:   [x, y]                   center of emitter
  trail:          bool                     leave a fading trail
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


def hex_to_rgb(c: str) -> tuple[int, int, int]:
    s = c.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def lerp_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def palette_at(palette: list[str], life01: float) -> tuple[int, int, int]:
    if not palette:
        return (255, 255, 255)
    if len(palette) == 1:
        return hex_to_rgb(palette[0])
    # piecewise linear interpolation through the palette as life goes 1->0
    n = len(palette)
    pos = (1 - life01) * (n - 1)
    i = int(np.floor(pos))
    t = pos - i
    if i >= n - 1:
        return hex_to_rgb(palette[-1])
    return lerp_color(hex_to_rgb(palette[i]), hex_to_rgb(palette[i + 1]), t)


def _render_frame(positions: np.ndarray, sizes: np.ndarray,
                  alphas: np.ndarray, colors: np.ndarray,
                  bounds: tuple[int, int], blend: str,
                  bg: tuple[int, int, int, int]) -> Image.Image:
    w, h = bounds
    # Render as float32 RGBA accumulator, then composite to uint8.
    acc = np.zeros((h, w, 4), dtype=np.float32)
    if blend == "additive":
        acc[..., :3] = 0.0
    else:
        acc[..., 0] = bg[0] / 255
        acc[..., 1] = bg[1] / 255
        acc[..., 2] = bg[2] / 255
    for x, y, s, a, col in zip(positions[:, 0], positions[:, 1], sizes, alphas, colors):
        if a <= 0 or s <= 0:
            continue
        r = max(int(s), 1)
        x0 = int(round(x - r))
        y0 = int(round(y - r))
        x1 = int(round(x + r + 1))
        y1 = int(round(y + r + 1))
        cx0 = max(x0, 0)
        cy0 = max(y0, 0)
        cx1 = min(x1, w)
        cy1 = min(y1, h)
        if cx0 >= cx1 or cy0 >= cy1:
            continue
        ys = np.arange(cy0, cy1, dtype=np.float32) - y
        xs = np.arange(cx0, cx1, dtype=np.float32) - x
        gx, gy = np.meshgrid(xs, ys)
        d2 = gx * gx + gy * gy
        # Gaussian falloff
        sigma = max(s * 0.5, 0.5)
        kernel = np.exp(-d2 / (2 * sigma * sigma)) * a
        if blend == "additive":
            acc[cy0:cy1, cx0:cx1, 0] += kernel * (col[0] / 255)
            acc[cy0:cy1, cx0:cx1, 1] += kernel * (col[1] / 255)
            acc[cy0:cy1, cx0:cx1, 2] += kernel * (col[2] / 255)
            acc[cy0:cy1, cx0:cx1, 3] = np.maximum(acc[cy0:cy1, cx0:cx1, 3], kernel)
        else:  # alpha blend (over)
            cur_a = acc[cy0:cy1, cx0:cx1, 3]
            src_a = kernel
            new_a = src_a + cur_a * (1 - src_a)
            for ch in range(3):
                src = (col[ch] / 255) * src_a
                dst = acc[cy0:cy1, cx0:cx1, ch] * cur_a * (1 - src_a)
                acc[cy0:cy1, cx0:cx1, ch] = np.where(
                    new_a > 1e-6, (src + dst) / np.maximum(new_a, 1e-6),
                    acc[cy0:cy1, cx0:cx1, ch],
                )
            acc[cy0:cy1, cx0:cx1, 3] = new_a

    out = (np.clip(acc, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def bake(effect: Effect, out_root: Path) -> BakeManifest:
    p = effect.backend_params
    rng = np.random.default_rng(p.get("seed", 0))
    n = int(p.get("count", 80))
    bounds = effect.bounds_px
    w, h = bounds
    n_frames = effect.n_frames
    dt = 1.0 / effect.fps
    duration = effect.duration_s

    emit_pos = np.array(p.get("emission_pos", [w / 2, h / 2]), dtype=np.float32)
    speed = float(p.get("initial_speed", 80.0))
    speed_j = float(p.get("speed_jitter", 20.0))
    angle_deg = float(p.get("direction_deg", 90.0))  # 90 = up (screen y-down)
    spread_deg = float(p.get("spread_deg", 25.0))
    gravity = np.array(p.get("gravity", [0.0, 80.0]), dtype=np.float32)
    drag = float(p.get("drag", 0.6))
    size_base = float(p.get("size_px", 6.0))
    size_j = float(p.get("size_jitter", 2.0))
    fade = float(p.get("fade", 1.0))
    palette = effect.visual.palette
    blend = effect.visual.blend
    # background: hex like #00000000 or #00000000 -> use last 2 chars as alpha
    bg_hex = effect.visual.background.lstrip("#")
    if len(bg_hex) == 8:
        bg = (int(bg_hex[0:2], 16), int(bg_hex[2:4], 16),
              int(bg_hex[4:6], 16), int(bg_hex[6:8], 16))
    else:
        bg = (*hex_to_rgb("#" + bg_hex), 0)

    emitter = p.get("emitter", "burst")
    if emitter == "burst":
        spawn_at = np.zeros(n, dtype=np.float32)
    else:
        # stream - spread over the full duration
        spawn_at = np.linspace(0, duration * 0.9, n, dtype=np.float32)

    # initial conditions per particle
    angles_rad = np.deg2rad(angle_deg + rng.uniform(-spread_deg, spread_deg, n))
    speeds = speed + rng.uniform(-speed_j, speed_j, n)
    pos = np.tile(emit_pos, (n, 1))
    # Note: screen y-down, so up is -sin
    vel = np.column_stack([np.cos(angles_rad) * speeds, -np.sin(angles_rad) * speeds]).astype(np.float32)
    sizes = (size_base + rng.uniform(-size_j, size_j, n)).clip(min=1.0).astype(np.float32)
    lifetimes = rng.uniform(0.7, 1.0, n).astype(np.float32) * duration

    spawned = np.zeros(n, dtype=bool)
    age = np.zeros(n, dtype=np.float32) - 1.0

    frames_dir = out_root / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    summary_per_frame = []

    for f in range(n_frames):
        t = f * dt
        # spawn
        new_spawns = (~spawned) & (spawn_at <= t)
        if new_spawns.any():
            age[new_spawns] = 0.0
            spawned[new_spawns] = True
        alive = spawned & (age <= lifetimes)
        # update active
        if alive.any():
            v = vel[alive]
            v += gravity * dt
            v *= np.exp(-drag * dt)
            vel[alive] = v
            pos[alive] += v * dt
            age[alive] += dt
        # build per-particle alpha + color from age fraction
        life_frac = np.clip(1 - (age / np.maximum(lifetimes, 1e-6)), 0, 1)
        alphas = life_frac * fade
        alphas = np.where(alive, alphas, 0.0).astype(np.float32)
        colors = np.zeros((n, 3), dtype=np.uint8)
        for i in np.where(alive)[0]:
            colors[i] = palette_at(palette, life_frac[i])
        img = _render_frame(pos, sizes, alphas, colors, bounds, blend, bg)
        img.save(frames_dir / f"frame_{f:04d}.png")
        # summary
        bbox = None
        live_mask = alphas > 0
        if live_mask.any():
            bbox = [
                float(pos[live_mask, 0].min()),
                float(pos[live_mask, 1].min()),
                float(pos[live_mask, 0].max()),
                float(pos[live_mask, 1].max()),
            ]
        summary_per_frame.append({
            "t": t,
            "alive": int(alive.sum()),
            "bbox": bbox,
            "energy": float(alphas.sum()),
        })

    # particles.json - lightweight per-frame stats only (full SoA dump can be huge)
    extras_path = out_root / "particles.json"
    extras_path.write_text(json.dumps({
        "frames": summary_per_frame,
        "n_total": n,
        "emitter": emitter,
    }, indent=2))

    # flipbook
    flipbook_path = pack_flipbook(frames_dir, n_frames, bounds, out_root / "flipbook.png")

    return BakeManifest(
        effect_id=effect.id,
        backend="particle_cpu",
        n_frames=n_frames,
        fps=effect.fps,
        bounds_px=bounds,
        flipbook=str(flipbook_path),
        frames_dir=str(frames_dir),
        extras={"particles_json": str(extras_path)},
        metrics={
            "max_alive": max(s["alive"] for s in summary_per_frame),
            "total_energy": sum(s["energy"] for s in summary_per_frame),
        },
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def pack_flipbook(frames_dir: Path, n_frames: int,
                  cell_bounds: tuple[int, int], out_path: Path) -> Path:
    """Concatenate frames into a row-major grid atlas."""
    w, h = cell_bounds
    cols = int(np.ceil(np.sqrt(n_frames)))
    rows = int(np.ceil(n_frames / cols))
    sheet = Image.new("RGBA", (w * cols, h * rows), (0, 0, 0, 0))
    for f in range(n_frames):
        path = frames_dir / f"frame_{f:04d}.png"
        if not path.exists():
            continue
        img = Image.open(path).convert("RGBA")
        x = (f % cols) * w
        y = (f // cols) * h
        sheet.paste(img, (x, y))
    sheet.save(out_path)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("effect_json", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    effect = Effect.model_validate_json(args.effect_json.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = bake(effect, args.out)
    (args.out / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    print(f"[particle_cpu] {effect.id}: {manifest.n_frames} frames, "
          f"max_alive={manifest.metrics['max_alive']} -> {args.out}")


if __name__ == "__main__":
    main()
