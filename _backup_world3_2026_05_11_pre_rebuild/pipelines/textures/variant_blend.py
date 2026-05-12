"""variant_blend — combine N tileable albedos into one tileable tile.

Companion / alternative to `variant_select.py`. Where variant_select
*picks* the best of N candidate variants (by edge-MSE seam score),
variant_blend *combines* them. Different rescue strategy.

When to reach for which:
- variant_select: when one of the N candidates is good and the others
  are bad. Default mode for `aaa_texture.py`.
- variant_blend: when all N candidates have a similar lattice/periodic
  artifact at a similar phase, AND combining them shifts the dominant
  frequency enough to break the periodicity. Useful on lattice-prone
  categories (grass, leaf_litter on bad seeds) where prompt rewrites
  alone don't reach grade A.

Approach
--------
Each candidate is *itself* tileable (FLUX 2 klein + offset+heal). To
preserve tileability of the OUTPUT, we blend them through tileable
masks — periodic 2D noise patterns that wrap perfectly at the edges.

For N inputs, we generate N tileable noise fields, each peaked at a
different spatial offset. Per pixel we take a softmax-weighted blend
across the N fields. Strongest field at that pixel wins, with smooth
transitions (no hard seams).

Because the noise fields wrap, opposite output edges sample the same
weights. Because each input also wraps, the blended output wraps.
Output is tileable.

Practical detail: the noise fields are generated as low-frequency
sinusoidal sums (~1-3 cycles per tile). Low frequency means each
input dominates large contiguous regions; high frequency would
salt-and-pepper the inputs and look noisy. The mix factor is tuned
toward "regions of input A, regions of input B, soft-feathered
transitions" rather than "every pixel is a new mix."

Usage
-----
    python variant_blend.py --inputs A.png B.png C.png D.png \\
        --out blended.png

  # Or driven by an asset id (auto-finds variant dirs in the library):
    python variant_blend.py --id wgv3_grass_test --variants 4 \\
        --out world/textures/library/wgv3_grass_blend
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


LIBRARY = Path("D:/assets/world/textures/library")


def _tileable_lowfreq_field(h: int, w: int, n_components: int = 3,
                             seed: int = 0) -> np.ndarray:
    """A smooth field that wraps tileably. Sum of sinusoids at integer
    spatial frequencies — each component has period h/k for integer k,
    so it wraps cleanly at the boundary.

    Returns a float32 array in [0, 1].
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.indices((h, w))
    # Normalize to [0, 1) over the tile
    u = xx / w
    v = yy / h
    field = np.zeros((h, w), dtype=np.float32)
    # Sum n_components sinusoids at random integer frequencies + phases
    for _ in range(n_components):
        kx = int(rng.integers(1, 4))   # 1..3 cycles per tile
        ky = int(rng.integers(1, 4))
        phase = rng.uniform(0, 2 * np.pi)
        amp = rng.uniform(0.5, 1.0)
        field += amp * np.cos(2 * np.pi * (kx * u + ky * v) + phase)
    # Normalize to [0, 1]
    field -= field.min()
    rng_max = field.max()
    if rng_max > 1e-9:
        field /= rng_max
    return field


def softmax_weights(fields: np.ndarray, sharpness: float = 4.0) -> np.ndarray:
    """Convert N tileable fields (shape N x H x W) to N tileable
    weight maps that sum to 1 per pixel. Higher sharpness = harder
    transitions between regions; lower = smoother feathering.

    sharpness=4 is the default — gives "regions of dominance with
    soft transitions" rather than salt-and-pepper.
    """
    scaled = fields * sharpness
    # Stabilize before exp
    scaled -= scaled.max(axis=0, keepdims=True)
    e = np.exp(scaled)
    return e / e.sum(axis=0, keepdims=True)


def blend_variants(images: list[np.ndarray], sharpness: float = 4.0,
                    seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Combine N tileable images into one tileable image.

    images: list of HxWx3 float32 arrays in [0, 1]
    Returns: (blended HxWx3 float32, weight map NxHxW float32)
    """
    n = len(images)
    if n < 2:
        raise ValueError("need at least 2 input images to blend")
    h, w = images[0].shape[:2]
    # Generate N tileable fields with different seeds
    fields = np.stack(
        [_tileable_lowfreq_field(h, w, n_components=3, seed=seed + i)
         for i in range(n)],
        axis=0,
    )
    weights = softmax_weights(fields, sharpness=sharpness)
    # Per-channel weighted sum
    out = np.zeros_like(images[0])
    for i in range(n):
        out += weights[i, :, :, None] * images[i]
    return out, weights


def find_variants(asset_id: str, n_variants: int) -> list[Path]:
    """Find the variant albedos for an asset id under LIBRARY/<id>_v0
    .. _v(N-1). variant_select.py writes those before picking the best.

    Note: variant_select.py deletes them by default unless --keep-all
    was passed; you'll need to re-run with --keep-all to use this.
    """
    paths = []
    for i in range(n_variants):
        v_dir = LIBRARY / f"{asset_id}_v{i}"
        cand = v_dir / f"{asset_id}_v{i}_albedo.png"
        if not cand.exists():
            # variant_select uses flux_seamless which writes
            # `<id>_v{i}_albedo.png` directly in the variant dir
            for p in v_dir.glob("*_albedo.png"):
                if "pre_" not in p.name:
                    cand = p
                    break
        if not cand.exists():
            raise SystemExit(
                f"variant {i} not found for {asset_id} at {v_dir}. "
                "Did you re-run with --keep-all?"
            )
        paths.append(cand)
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, nargs="+",
                    help="input albedo PNGs (2 or more)")
    ap.add_argument("--id", help="asset id; finds variant dirs at "
                                  "LIBRARY/<id>_v0..<id>_v(N-1)")
    ap.add_argument("--variants", type=int, default=4,
                    help="number of variants to find (mode: --id)")
    ap.add_argument("--out", type=Path, required=True,
                    help="output albedo path (or directory if --id "
                         "given; output written as <out>/<id>_albedo.png)")
    ap.add_argument("--out-id", default=None,
                    help="custom asset id for the output filename "
                         "(default: <id>_blend or 'blended')")
    ap.add_argument("--sharpness", type=float, default=4.0,
                    help="softmax sharpness (default 4.0). Higher = "
                         "harder region transitions, lower = smoother "
                         "feathered blends")
    ap.add_argument("--seed", type=int, default=0,
                    help="seed for the tileable field generation; "
                         "different seeds give different region maps")
    ap.add_argument("--save-weights", action="store_true",
                    help="also write a weights_NxHxW.npy file for debug")
    args = ap.parse_args()

    # Resolve inputs
    if args.inputs:
        input_paths = args.inputs
    elif args.id:
        input_paths = find_variants(args.id, args.variants)
    else:
        ap.error("provide --inputs OR --id")

    print(f"[blend] {len(input_paths)} input variants:")
    for p in input_paths:
        print(f"  {p}")

    images = []
    for p in input_paths:
        im = np.asarray(Image.open(p).convert("RGB"),
                        dtype=np.float32) / 255.0
        images.append(im)

    # Verify same shape
    h0, w0 = images[0].shape[:2]
    for i, im in enumerate(images[1:], start=1):
        if im.shape[:2] != (h0, w0):
            raise SystemExit(f"variant {i} size {im.shape[:2]} != "
                              f"variant 0 size {(h0, w0)}")

    blended, weights = blend_variants(
        images, sharpness=args.sharpness, seed=args.seed)

    # Resolve output path
    if args.out.is_dir() or (args.id and not args.out.suffix):
        args.out.mkdir(parents=True, exist_ok=True)
        out_id = args.out_id or (f"{args.id}_blend" if args.id else "blended")
        out_path = args.out / f"{out_id}_albedo.png"
    else:
        out_path = args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)

    Image.fromarray((blended * 255).clip(0, 255).astype(np.uint8),
                    mode="RGB").save(out_path)
    print(f"\nblended -> {out_path}")

    # Save metadata
    meta = {
        "n_inputs": len(input_paths),
        "inputs": [str(p) for p in input_paths],
        "sharpness": args.sharpness,
        "seed": args.seed,
        "output": str(out_path),
    }
    meta_path = out_path.with_suffix(".blend.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"meta    -> {meta_path}")

    if args.save_weights:
        wp = out_path.with_suffix(".weights.npy")
        np.save(wp, weights)
        print(f"weights -> {wp}")


if __name__ == "__main__":
    main()
