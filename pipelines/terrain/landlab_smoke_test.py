"""
Landlab smoke test for the world3 M19-M24 hybrid procedural roadmap.

Verifies:
  - landlab + numpy + matplotlib import cleanly
  - RasterModelGrid constructs and exposes a height field
  - FastscapeEroder (fluvial) runs without errors
  - LinearDiffuser (hillslope diffusion) runs without errors
  - A FastNoise-style base field (perlin-ish via np.sin/cos sums) gets
    visibly transformed: ridges sharpen, valleys deepen, drainage
    network appears
  - A side-by-side PNG of before / after lands at
    pipelines/terrain/output/landlab_smoke/before_after.png

Run:
  d:/assets/pipelines/terrain/.venv/Scripts/python.exe \
      d:/assets/pipelines/terrain/landlab_smoke_test.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

OUT_DIR = Path(__file__).parent / "output" / "landlab_smoke"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def make_fake_noise_terrain(rows: int, cols: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:rows, 0:cols].astype(np.float64)
    z = np.zeros((rows, cols), dtype=np.float64)
    for freq, amp in [(1 / 80.0, 60.0), (1 / 30.0, 20.0), (1 / 12.0, 6.0)]:
        phase_x = rng.uniform(0, 2 * np.pi)
        phase_y = rng.uniform(0, 2 * np.pi)
        z += amp * (np.sin(2 * np.pi * freq * x + phase_x)
                    * np.cos(2 * np.pi * freq * y + phase_y))
    z += 4.0 * rng.standard_normal(z.shape)
    z -= z.min()
    return z


def field_stats(label: str, z: np.ndarray) -> dict:
    s = {
        "label": label,
        "min": float(z.min()),
        "max": float(z.max()),
        "mean": float(z.mean()),
        "std": float(z.std()),
        "p99-p1": float(np.percentile(z, 99) - np.percentile(z, 1)),
    }
    print(f"  {label:>10s}: "
          f"range=[{s['min']:7.2f}, {s['max']:7.2f}] "
          f"mean={s['mean']:6.2f} std={s['std']:6.2f} "
          f"p99-p1={s['p99-p1']:6.2f}")
    return s


def main() -> int:
    print("=" * 70)
    print("Landlab smoke test (world3 M19-M24)")
    print("=" * 70)

    t_imp = time.perf_counter()
    import landlab
    from landlab import RasterModelGrid
    from landlab.components import FastscapeEroder, LinearDiffuser
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    print(f"landlab        : {landlab.__version__}")
    print(f"numpy          : {np.__version__}")
    print(f"matplotlib     : {matplotlib.__version__}")
    print(f"import         : {time.perf_counter() - t_imp:5.2f}s")
    print()

    rows, cols = 128, 128
    spacing = 30.0
    print(f"grid           : {rows}x{cols} @ {spacing} m  "
          f"({rows*cols} nodes, {rows*spacing/1000.0:.2f} km square)")

    grid = RasterModelGrid((rows, cols), xy_spacing=spacing)
    z_field = grid.add_zeros("topographic__elevation", at="node")
    z0 = make_fake_noise_terrain(rows, cols, seed=42)
    z_field[:] = z0.ravel()

    grid.set_closed_boundaries_at_grid_edges(False, False, False, False)

    print()
    print("before erosion:")
    pre = field_stats("noise", z_field.reshape(rows, cols))

    print()
    from landlab.components import FlowAccumulator
    fa = FlowAccumulator(grid, flow_director="D8")
    fa.run_one_step()
    fs = FastscapeEroder(grid, K_sp=2.0e-4, m_sp=0.5, n_sp=1.0)
    ld = LinearDiffuser(grid, linear_diffusivity=0.01)
    print("components     : FlowAccumulator(D8), "
          "FastscapeEroder(K_sp=2e-4), LinearDiffuser(D=0.01)")

    n_steps = 60
    dt = 500.0
    t_sim = time.perf_counter()
    try:
        for _ in range(n_steps):
            fa.run_one_step()
            fs.run_one_step(dt)
            ld.run_one_step(dt)
    except Exception as e:
        print(f"!! erosion loop failed: {e}")
        raise
    t_sim = time.perf_counter() - t_sim
    print(f"sim            : {n_steps} steps x dt={dt}s = "
          f"{n_steps*dt:.0f} sim-yr in {t_sim:5.2f}s wall "
          f"({t_sim/n_steps*1000:.1f} ms/step)")

    print()
    print("after erosion:")
    post = field_stats("eroded", z_field.reshape(rows, cols))

    drainage = grid.at_node["drainage_area"].reshape(rows, cols)
    print()
    print(f"drainage area  : max={drainage.max():.0f} m^2, "
          f"finite={np.isfinite(drainage).all()}")

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    z_pre = z0
    z_post = z_field.reshape(rows, cols)
    extent = [0, cols * spacing, 0, rows * spacing]
    im0 = axes[0].imshow(z_pre, cmap="terrain", origin="lower",
                         extent=extent)
    axes[0].set_title(f"before (noise)\nrange "
                      f"{pre['min']:.0f}-{pre['max']:.0f}")
    plt.colorbar(im0, ax=axes[0], fraction=0.046)

    im1 = axes[1].imshow(z_post, cmap="terrain", origin="lower",
                         extent=extent)
    axes[1].set_title(f"after (erosion)\nrange "
                      f"{post['min']:.0f}-{post['max']:.0f}")
    plt.colorbar(im1, ax=axes[1], fraction=0.046)

    im2 = axes[2].imshow(np.log10(drainage + 1.0), cmap="Blues",
                         origin="lower", extent=extent)
    axes[2].set_title("log10(drainage_area+1)")
    plt.colorbar(im2, ax=axes[2], fraction=0.046)
    for ax in axes:
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
    fig.suptitle("Landlab smoke test - "
                 "FastNoise base -> FastscapeEroder + LinearDiffuser",
                 fontsize=12)
    fig.tight_layout()
    png = OUT_DIR / "before_after.png"
    fig.savefig(png, dpi=120)
    print()
    print(f"capture        : {png}")

    relief_delta = (post["p99-p1"] - pre["p99-p1"])
    cell_area = spacing * spacing
    drainage_concentration = drainage.max() / cell_area
    drainage_ok = drainage_concentration >= 100.0
    eroded_ok = post["mean"] < pre["mean"]
    print()
    print("checks:")
    print(f"  relief change (p99-p1)  : "
          f"{pre['p99-p1']:.1f} -> {post['p99-p1']:.1f} "
          f"(delta {relief_delta:+.1f})")
    print(f"  mean elevation drop     : "
          f"{pre['mean']:.2f} -> {post['mean']:.2f} "
          f"({'eroded' if eroded_ok else 'NOT eroded'})")
    print(f"  drainage concentration  : "
          f"max channel collects {drainage_concentration:.0f} cells "
          f"({'OK (>=100)' if drainage_ok else 'WEAK (<100)'})")

    if not np.isfinite(z_post).all():
        print("FAIL: NaN in output height field")
        return 1
    if not drainage_ok:
        print("FAIL: drainage did not concentrate")
        return 1
    if not eroded_ok:
        print("FAIL: mean elevation did not drop -- erosion solver inert")
        return 1
    print()
    print("OK: landlab smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
