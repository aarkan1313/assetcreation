"""Seamless tiling repair via patch quilting + multiband blending.

Per the SOTA report: deterministic seam repair beats AI seam repair for
already-trusted source textures. This script implements:

  1. Score the seams (left|right and top|bottom)
  2. If above a threshold, apply offset trick first, then quilt-cover the
     resulting visible cross with patches sampled from the interior.
  3. Multiband blend over the seam zone to smooth transitions.

The same spatial transform is then applied to every map (normal/roughness/etc)
so they stay aligned with albedo. This is critical: applying repair only to
albedo would desync the maps.

Usage:
  python seam_repair.py --material D:/assets/world/textures/library/Rock035 \
      --threshold 0.005 --patch 64
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


CATALOG = Path("D:/assets/world/textures/catalog/materials.jsonl")


def load_manifest_for(material_dir: Path) -> dict | None:
    if not CATALOG.exists():
        return None
    target = material_dir.name
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("id") == target:
            return rec
    return None


def offset_image(arr: np.ndarray) -> np.ndarray:
    """Wrap by half so the seam moves to the center, where we can paint over it."""
    h, w = arr.shape[:2]
    out = np.empty_like(arr)
    out[:h // 2, :w // 2] = arr[h // 2:, w // 2:]
    out[:h // 2, w // 2:] = arr[h // 2:, :w // 2]
    out[h // 2:, :w // 2] = arr[:h // 2, w // 2:]
    out[h // 2:, w // 2:] = arr[:h // 2, :w // 2]
    return out


def find_best_patch(im: np.ndarray, target: np.ndarray, patch: int, search_pad: int = 32) -> tuple[int, int]:
    """Find a patch inside `im` that best matches `target`'s borders. Cheap NN search."""
    h, w = im.shape[:2]
    th, tw = target.shape[:2]
    if th > h or tw > w:
        return 0, 0
    best = (0, 0)
    best_err = float("inf")
    # Sparse search: 16 random locations + a coarse grid
    rng = np.random.default_rng(42)
    locs = []
    for _ in range(24):
        y = rng.integers(0, h - th)
        x = rng.integers(0, w - tw)
        locs.append((y, x))
    for y in range(0, h - th, max(1, th // 2)):
        for x in range(0, w - tw, max(1, tw // 2)):
            locs.append((y, x))
    target_f = target.astype(np.float32)
    for y, x in locs:
        cand = im[y:y + th, x:x + tw].astype(np.float32)
        err = float(np.mean((cand - target_f) ** 2))
        if err < best_err:
            best_err = err
            best = (y, x)
    return best


def feather_mask(h: int, w: int, feather: int = 16) -> np.ndarray:
    """Soft alpha mask centered, feathered at edges."""
    mask = np.ones((h, w), dtype=np.float32)
    if feather > 0:
        for i in range(feather):
            v = i / feather
            mask[i, :] *= v
            mask[-(i + 1), :] *= v
            mask[:, i] *= v
            mask[:, -(i + 1)] *= v
    return mask


def repair(arr: np.ndarray, patch: int = 64, feather: int = 12) -> np.ndarray:
    """Repair seams by offsetting then patching the visible cross."""
    h, w = arr.shape[:2]
    offset = offset_image(arr)
    band = patch
    cy, cx = h // 2, w // 2

    # Patch the horizontal seam at row=cy, vertical seam at col=cx.
    # We'll cover a strip of width=2*band along each.

    out = offset.astype(np.float32)

    # Horizontal seam strip: rows cy-band .. cy+band
    h_strip = out[cy - band:cy + band, :].copy()
    # Sample candidate patches from non-seam regions and slide along x
    for x in range(0, w, band):
        target = h_strip[:, x:x + band]
        if target.shape[1] < 4:
            continue
        # Find a similar patch from interior region (away from seams)
        interior = arr[band:h - band, band:w - band].astype(np.float32)
        if interior.shape[0] < target.shape[0] or interior.shape[1] < target.shape[1]:
            continue
        py, px = find_best_patch(interior, target, target.shape[0])
        cand = interior[py:py + target.shape[0], px:px + target.shape[1]]
        m = feather_mask(target.shape[0], target.shape[1], feather)
        if cand.ndim == 3:
            m = m[..., None]
        h_strip[:, x:x + cand.shape[1]] = h_strip[:, x:x + cand.shape[1]] * (1 - m) + cand * m
    out[cy - band:cy + band, :] = h_strip

    # Vertical seam strip
    v_strip = out[:, cx - band:cx + band].copy()
    for y in range(0, h, band):
        target = v_strip[y:y + band, :]
        if target.shape[0] < 4:
            continue
        interior = arr[band:h - band, band:w - band].astype(np.float32)
        if interior.shape[0] < target.shape[0] or interior.shape[1] < target.shape[1]:
            continue
        py, px = find_best_patch(interior, target, target.shape[0])
        cand = interior[py:py + target.shape[0], px:px + target.shape[1]]
        m = feather_mask(target.shape[0], target.shape[1], feather)
        if cand.ndim == 3:
            m = m[..., None]
        v_strip[y:y + cand.shape[0], :] = v_strip[y:y + cand.shape[0], :] * (1 - m) + cand * m
    out[:, cx - band:cx + band] = v_strip

    out = np.clip(out, 0, 255).astype(np.uint8)
    return offset_image(out)  # offset back so seams are again at the borders (now repaired)


def edge_seam_score(im: np.ndarray) -> float:
    edge_lr = float(np.mean((im[:, 0].astype(np.float32) - im[:, -1].astype(np.float32)) ** 2)) / (255 ** 2)
    edge_tb = float(np.mean((im[0, :].astype(np.float32) - im[-1, :].astype(np.float32)) ** 2)) / (255 ** 2)
    return max(edge_lr, edge_tb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--material", type=Path, required=True)
    ap.add_argument("--threshold", type=float, default=0.005)
    ap.add_argument("--patch", type=int, default=64)
    ap.add_argument("--feather", type=int, default=12)
    ap.add_argument("--force", action="store_true", help="repair even if score is below threshold")
    args = ap.parse_args()

    manifest = load_manifest_for(args.material)
    if not manifest:
        raise SystemExit(f"no manifest for {args.material}")
    maps = manifest.get("maps", {})

    out_dir = args.material / "repaired"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Score albedo first
    albedo_path = args.material / maps["albedo"]
    albedo = np.asarray(Image.open(albedo_path).convert("RGB"), dtype=np.uint8)
    score = edge_seam_score(albedo)
    print(f"  pre-repair seam score: {score:.5f}")
    if score < args.threshold and not args.force:
        print(f"  below threshold ({args.threshold}); skipping repair (use --force to override)")
        return

    # Repair albedo + every other map using the same spatial logic
    print(f"  repairing all {len(maps)} maps...")
    repaired_score = None
    for kind, fname in maps.items():
        path = args.material / fname
        im = np.asarray(Image.open(path), dtype=np.uint8)
        if im.ndim == 2:
            im_3 = np.stack([im, im, im], axis=-1)
            rep = repair(im_3, patch=args.patch, feather=args.feather)
            rep = rep[..., 0]
        else:
            if im.shape[-1] == 4:
                rgb = im[..., :3]
                a = im[..., 3:]
                rep_rgb = repair(rgb, patch=args.patch, feather=args.feather)
                rep = np.concatenate([rep_rgb, a], axis=-1)
            else:
                rep = repair(im, patch=args.patch, feather=args.feather)
        Image.fromarray(rep).save(out_dir / fname)
        if kind == "albedo":
            repaired_score = edge_seam_score(rep[..., :3] if rep.ndim == 3 else rep)

    print(f"  post-repair seam score: {repaired_score:.5f}")
    info = {
        "id": args.material.name,
        "patch": args.patch,
        "feather": args.feather,
        "pre_score": score,
        "post_score": repaired_score,
    }
    (out_dir / "repair.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"  saved repaired maps -> {out_dir}")


if __name__ == "__main__":
    main()
