"""Debug helper: generate a clipmap ring mesh as an OBJ for visual
inspection in Blender / any 3D viewer. NOT used at runtime — that's
GDScript's job — but useful to verify the donut + skirt math before
porting.

Usage:
    python build_clipmap_mesh_debug.py \\
        --grid-n 256 --grid-step-m 2.0 \\
        --inner-grid-n 0 \\
        --skirt-depth-m 10.0 \\
        --outermost \\
        --out clipmap_ring0.obj
"""
from __future__ import annotations
import argparse
import math
from pathlib import Path


def build_donut_mesh(grid_n: int, grid_step_m: float,
                     inner_grid_n: int,
                     skirt_depth_m: float = 10.0,
                     outermost: bool = False) -> tuple[list, list]:
    """Build a square donut mesh with skirts.

    grid_n: outer grid resolution (vertices per side).
    grid_step_m: meters between adjacent grid vertices.
    inner_grid_n: if > 0, vertices inside a grid_n × grid_n inner
                  square are skipped (this is where the next finer
                  ring renders). Must be even and less than grid_n.
                  Centered.
    skirt_depth_m: how far the inner-edge skirt drops below the
                  surface (meters, positive). The runtime shader
                  applies displacement to everything; skirt verts
                  are offset by -skirt_depth_m in mesh-local Y so
                  they end up below the displaced surface.
    outermost: if True, also adds an outer-edge skirt (used on the
              outermost ring to hide the world rim).

    Returns (vertices, triangles).
    """
    if inner_grid_n > 0 and inner_grid_n % 2 != 0:
        raise ValueError("inner_grid_n must be even (centered)")
    if inner_grid_n >= grid_n:
        raise ValueError("inner_grid_n must be < grid_n")

    half_extent_m = (grid_n - 1) * grid_step_m * 0.5
    inner_half = inner_grid_n * grid_step_m * 0.5

    indices = [[-1] * grid_n for _ in range(grid_n)]
    verts = []
    for i in range(grid_n):
        for j in range(grid_n):
            x = -half_extent_m + j * grid_step_m
            z = -half_extent_m + i * grid_step_m
            if inner_grid_n > 0:
                if abs(x) < inner_half - 1e-3 and abs(z) < inner_half - 1e-3:
                    continue
            indices[i][j] = len(verts)
            verts.append((x, 0.0, z))

    triangles = []
    for i in range(grid_n - 1):
        for j in range(grid_n - 1):
            v00 = indices[i][j]
            v10 = indices[i][j + 1]
            v01 = indices[i + 1][j]
            v11 = indices[i + 1][j + 1]
            if -1 in (v00, v10, v01, v11):
                continue
            triangles.append((v00, v10, v11))
            triangles.append((v00, v11, v01))

    if inner_grid_n > 0:
        inner_perimeter_pairs: list[tuple[int, int]] = []
        for i in range(grid_n):
            for j in range(grid_n):
                if indices[i][j] == -1:
                    continue
                is_boundary = False
                for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    ni, nj = i + di, j + dj
                    if 0 <= ni < grid_n and 0 <= nj < grid_n:
                        if indices[ni][nj] == -1:
                            is_boundary = True
                            break
                if not is_boundary:
                    continue
                surf_vert = verts[indices[i][j]]
                skirt_idx = len(verts)
                verts.append((surf_vert[0], -skirt_depth_m, surf_vert[2]))
                inner_perimeter_pairs.append((indices[i][j], skirt_idx))
        inner_perimeter_pairs.sort(
            key=lambda p: math.atan2(verts[p[0]][2], verts[p[0]][0])
        )
        for k in range(len(inner_perimeter_pairs)):
            sa, da = inner_perimeter_pairs[k]
            sb, db = inner_perimeter_pairs[(k + 1) % len(inner_perimeter_pairs)]
            triangles.append((sa, sb, db))
            triangles.append((sa, db, da))

    if outermost:
        outer_perimeter_pairs: list[tuple[int, int]] = []
        for i in range(grid_n):
            for j in range(grid_n):
                if indices[i][j] == -1:
                    continue
                if not (i == 0 or i == grid_n - 1 or j == 0 or j == grid_n - 1):
                    continue
                surf_vert = verts[indices[i][j]]
                skirt_idx = len(verts)
                verts.append((surf_vert[0], -skirt_depth_m, surf_vert[2]))
                outer_perimeter_pairs.append((indices[i][j], skirt_idx))
        outer_perimeter_pairs.sort(
            key=lambda p: math.atan2(verts[p[0]][2], verts[p[0]][0])
        )
        for k in range(len(outer_perimeter_pairs)):
            sa, da = outer_perimeter_pairs[k]
            sb, db = outer_perimeter_pairs[(k + 1) % len(outer_perimeter_pairs)]
            # Outer skirts wind opposite direction (faces point outward).
            triangles.append((sa, db, sb))
            triangles.append((sa, da, db))

    return verts, triangles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ring", type=int, default=0)
    ap.add_argument("--grid-n", type=int, default=64)
    ap.add_argument("--grid-step-m", type=float, default=8.0)
    ap.add_argument("--inner-grid-n", type=int, default=0)
    ap.add_argument("--skirt-depth-m", type=float, default=10.0)
    ap.add_argument("--outermost", action="store_true",
                    help="Also add an outer-edge skirt.")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    verts, tris = build_donut_mesh(args.grid_n, args.grid_step_m,
                                   args.inner_grid_n,
                                   skirt_depth_m=args.skirt_depth_m,
                                   outermost=args.outermost)
    p = Path(args.out)
    with p.open("w", encoding="utf-8") as f:
        for v in verts:
            f.write(f"v {v[0]} {v[1]} {v[2]}\n")
        for t in tris:
            f.write(f"f {t[0]+1} {t[1]+1} {t[2]+1}\n")
    print(f"wrote {len(verts)} verts, {len(tris)} tris to {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
