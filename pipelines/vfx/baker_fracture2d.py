"""First-party 2D fracture baker. Deterministic. No physics solver.

Approach (per `D:/spell lab` first-party fracture concept):
  1. Start from a regular polygon (n-gon) representing the source shape.
  2. Pick K Voronoi seed points inside the polygon.
  3. Clip the polygon by each seed's Voronoi cell -> K convex shards.
  4. Each shard gets an analytical motion: outward radial velocity from the
     impact center + gravity + spin + linear drag.
  5. Render each frame with shards as solid polygons + thin outline.

Output:
  frames/frame_NNNN.png      RGBA per-frame
  flipbook.png               atlas
  fragments.json             per-shard polygon vertex list (initial)
  bodies.json                per-frame transform per shard

Backend params (effect.backend_params):
  source_shape:     "circle" | "rect" | "ngon"
  source_n_sides:   int (used for ngon)
  source_radius_px: float
  shard_count:      int
  impact_center:    [x, y]
  gravity:          [gx, gy]   px/s^2
  drag:             float      1/s
  burst_speed:      float      px/s
  burst_jitter:     float
  spin_max:         float      rad/s
  base_color:       hex string
  outline_color:    hex string
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from schemas import BakeManifest, Effect  # noqa: E402


def _hex(c: str) -> tuple[int, int, int, int]:
    s = c.lstrip("#")
    if len(s) == 6:
        s = s + "ff"
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))


def _ngon(center: np.ndarray, radius: float, n: int,
          rng: np.random.Generator) -> np.ndarray:
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False) + rng.uniform(0, np.pi / n)
    return np.column_stack([
        center[0] + radius * np.cos(angles),
        center[1] + radius * np.sin(angles),
    ]).astype(np.float32)


def _clip_to_cell(poly: np.ndarray, seed_idx: int, seeds: np.ndarray) -> np.ndarray:
    """Sutherland-Hodgman clip the polygon by each half-plane that defines
    the Voronoi cell of seeds[seed_idx]. Stops if the polygon becomes empty."""
    me = seeds[seed_idx]
    out = poly.copy()
    for j, other in enumerate(seeds):
        if j == seed_idx:
            continue
        # Half-plane: closer to `me` than to `other`.
        # Bisector: midpoint normal to (other - me).
        mid = (me + other) / 2.0
        n = (me - other)
        # In >0 means inside (closer to me).
        def inside(p):
            return float(np.dot(p - mid, n)) >= 0.0
        if len(out) == 0:
            return out
        new_out = []
        prev = out[-1]
        prev_in = inside(prev)
        for cur in out:
            cur_in = inside(cur)
            if prev_in:
                if cur_in:
                    new_out.append(cur)
                else:
                    # exiting -> add intersection
                    new_out.append(_intersect(prev, cur, mid, n))
            else:
                if cur_in:
                    new_out.append(_intersect(prev, cur, mid, n))
                    new_out.append(cur)
            prev = cur
            prev_in = cur_in
        out = np.array(new_out, dtype=np.float32) if new_out else np.zeros((0, 2), dtype=np.float32)
    return out


def _intersect(a: np.ndarray, b: np.ndarray, mid: np.ndarray, n: np.ndarray) -> np.ndarray:
    # Find t such that ((a + t(b-a)) - mid) . n = 0.
    denom = float(np.dot(b - a, n))
    if abs(denom) < 1e-9:
        return a
    t = float(np.dot(mid - a, n)) / denom
    return (a + t * (b - a)).astype(np.float32)


def _polygon_centroid(poly: np.ndarray) -> np.ndarray:
    if len(poly) < 3:
        return poly.mean(axis=0) if len(poly) else np.zeros(2, dtype=np.float32)
    x = poly[:, 0]
    y = poly[:, 1]
    a = x * np.roll(y, -1) - np.roll(x, -1) * y
    A = 0.5 * a.sum()
    if abs(A) < 1e-9:
        return poly.mean(axis=0)
    cx = (1 / (6 * A)) * ((x + np.roll(x, -1)) * a).sum()
    cy = (1 / (6 * A)) * ((y + np.roll(y, -1)) * a).sum()
    return np.array([cx, cy], dtype=np.float32)


def bake(effect: Effect, out_root: Path) -> BakeManifest:
    p = effect.backend_params
    rng = np.random.default_rng(p.get("seed", 0))
    bounds = effect.bounds_px
    w, h = bounds
    n_frames = effect.n_frames
    dt = 1.0 / effect.fps

    src_radius = float(p.get("source_radius_px", min(w, h) * 0.30))
    src_n_sides = int(p.get("source_n_sides", 12))
    shard_count = int(p.get("shard_count", 9))
    impact_center = np.array(p.get("impact_center", [w / 2, h / 2]), dtype=np.float32)
    gravity = np.array(p.get("gravity", [0.0, 60.0]), dtype=np.float32)
    drag = float(p.get("drag", 0.4))
    burst_speed = float(p.get("burst_speed", 60.0))
    burst_jitter = float(p.get("burst_jitter", 20.0))
    spin_max = float(p.get("spin_max", 6.0))
    base_color = _hex(p.get("base_color", effect.visual.palette[0] if effect.visual.palette else "#cccccc"))
    outline_color = _hex(p.get("outline_color", "#1a1a1a"))

    # 1) source polygon
    poly = _ngon(impact_center, src_radius, src_n_sides, rng)
    # 2) Voronoi seeds inside the polygon (rejection sample)
    seeds: list[np.ndarray] = []
    while len(seeds) < shard_count:
        x = rng.uniform(impact_center[0] - src_radius, impact_center[0] + src_radius)
        y = rng.uniform(impact_center[1] - src_radius, impact_center[1] + src_radius)
        # quick acceptance: inside the polygon's bounding circle
        if (x - impact_center[0]) ** 2 + (y - impact_center[1]) ** 2 <= src_radius ** 2:
            seeds.append(np.array([x, y], dtype=np.float32))
    seeds_arr = np.array(seeds, dtype=np.float32)
    # 3) clip the source polygon by each Voronoi cell
    shards: list[dict] = []
    for i in range(shard_count):
        cell = _clip_to_cell(poly, i, seeds_arr)
        if len(cell) < 3:
            continue
        c = _polygon_centroid(cell)
        # local-space verts (relative to centroid)
        local = (cell - c).astype(np.float32)
        # outward velocity from impact center
        d = c - impact_center
        d_len = float(np.linalg.norm(d) + 1e-6)
        v0 = (d / d_len) * (burst_speed + rng.uniform(-burst_jitter, burst_jitter))
        omega = rng.uniform(-spin_max, spin_max)
        shards.append({
            "id": f"s{i}",
            "centroid": c.tolist(),
            "local_verts": local.tolist(),
            "v0": v0.tolist(),
            "omega": float(omega),
            "color": list(base_color),
        })

    # bake frames + bodies trajectory
    frames_dir = out_root / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    bodies_per_frame = []  # list of [{id,x,y,theta}, ...]
    pos = np.array([s["centroid"] for s in shards], dtype=np.float32)
    vel = np.array([s["v0"] for s in shards], dtype=np.float32)
    theta = np.zeros(len(shards), dtype=np.float32)
    omega = np.array([s["omega"] for s in shards], dtype=np.float32)

    for f in range(n_frames):
        # update
        if f > 0:
            vel = vel + gravity * dt
            vel *= np.exp(-drag * dt)
            pos = pos + vel * dt
            theta = theta + omega * dt
        # render
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for i, sh in enumerate(shards):
            local = np.array(sh["local_verts"], dtype=np.float32)
            ct, st = float(np.cos(theta[i])), float(np.sin(theta[i]))
            R = np.array([[ct, -st], [st, ct]], dtype=np.float32)
            world = local @ R.T + pos[i]
            poly_xy = [(float(x), float(y)) for x, y in world]
            d.polygon(poly_xy, fill=tuple(sh["color"]),
                      outline=outline_color, width=2)
        img.save(frames_dir / f"frame_{f:04d}.png")
        bodies_per_frame.append([
            {"id": shards[i]["id"], "x": float(pos[i][0]),
             "y": float(pos[i][1]), "theta": float(theta[i])}
            for i in range(len(shards))
        ])

    # extras
    fragments_path = out_root / "fragments.json"
    fragments_path.write_text(json.dumps({
        "shards": [{
            "id": s["id"],
            "local_verts": s["local_verts"],
            "color": s["color"],
        } for s in shards],
    }, indent=2))
    bodies_path = out_root / "bodies.json"
    bodies_path.write_text(json.dumps({
        "fps": effect.fps,
        "frames": bodies_per_frame,
    }, indent=2))

    # flipbook
    from baker_particle_cpu import pack_flipbook  # reuse
    flipbook_path = pack_flipbook(frames_dir, n_frames, bounds, out_root / "flipbook.png")

    return BakeManifest(
        effect_id=effect.id,
        backend="fracture2d",
        n_frames=n_frames,
        fps=effect.fps,
        bounds_px=bounds,
        flipbook=str(flipbook_path),
        frames_dir=str(frames_dir),
        extras={"fragments_json": str(fragments_path),
                "bodies_json": str(bodies_path)},
        metrics={"shard_count": len(shards)},
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
    print(f"[fracture2d] {effect.id}: {manifest.n_frames} frames, "
          f"shards={manifest.metrics['shard_count']} -> {args.out}")


if __name__ == "__main__":
    main()
