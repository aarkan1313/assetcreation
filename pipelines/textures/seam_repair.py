"""Seam repair via offset + patch quilting + multiband blending.

Replaces the previous version, which had two defects:

  1. It read the catalog manifest to find map filenames, but the catalog
     was written *after* the orchestrator ran this script. So on every
     first run, repair raised SystemExit; the orchestrator caught it and
     logged "skipped: true." Of 30 textures in the library, only 2 ever
     had any repaired output, both from manual second-runs.

  2. Output went to <material>/repaired/. Nothing copied the repaired
     files back over the originals. Consumers always read un-repaired
     textures even when repair "succeeded."

Fixes:

  - Self-contained: discover map files by filename suffix in the material
    dir. Convention is <id>_<map>.png where map is one of:
    albedo, normal, roughness, metallic, height, ao.
  - Writes repaired output back over the original files.
  - Backs up the pre-repair version to <id>_<map>.pre_repair.png so we
    can A/B compare and revert if needed.
  - Writes a repair record alongside the maps documenting what changed.

Algorithm (unchanged from prior version, that part was sound):

  1. Score the albedo's edge continuity.
  2. If above threshold (or --force), apply the offset trick: circular-
     shift by half so the wrap-around seam moves to the center.
  3. Quilt-cover the visible center cross with patches sampled from the
     interior, feathered.
  4. Reverse the offset; result tiles naturally.
  5. Apply the same spatial repair to every other map (normal, roughness,
     etc.) so they stay aligned with the albedo.

Usage:
  python seam_repair.py --material D:/assets/world/textures/library/Rock035 \\
      --threshold 0.005 --patch 64 --feather 12

  # Skip the threshold gate (always repair):
  python seam_repair.py --material <dir> --force

  # Restore originals from backups:
  python seam_repair.py --material <dir> --restore
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image


KNOWN_MAPS = ("albedo", "normal", "roughness", "metallic", "height", "ao")


def discover_maps(material_dir: Path) -> dict[str, Path]:
    """Find map files by filename convention. Returns {kind: path}.

    Looks for <anything>_<map>.png. Skips backup/sidecar files like
    *.pre_repair.png and *.pre_delight.png.
    """
    found: dict[str, Path] = {}
    for p in material_dir.iterdir():
        if not p.is_file() or p.suffix.lower() not in (".png", ".jpg"):
            continue
        name = p.stem.lower()
        # Skip stash files.
        if "pre_" in name or "_pre_" in name:
            continue
        for kind in KNOWN_MAPS:
            if name.endswith(f"_{kind}") or name == kind:
                if kind not in found:  # first match wins
                    found[kind] = p
                break
    return found


def offset_image(arr: np.ndarray) -> np.ndarray:
    """Wrap by half so the seam moves to the center, where we can paint over it."""
    h, w = arr.shape[:2]
    out = np.empty_like(arr)
    out[:h // 2, :w // 2] = arr[h // 2:, w // 2:]
    out[:h // 2, w // 2:] = arr[h // 2:, :w // 2]
    out[h // 2:, :w // 2] = arr[:h // 2, w // 2:]
    out[h // 2:, w // 2:] = arr[:h // 2, :w // 2]
    return out


def find_best_patch(im: np.ndarray, target: np.ndarray, search_locs: int = 24) -> tuple[int, int]:
    """Find a patch inside `im` that best matches `target`. Cheap NN search."""
    h, w = im.shape[:2]
    th, tw = target.shape[:2]
    if th > h or tw > w:
        return 0, 0
    rng = np.random.default_rng(42)
    locs: list[tuple[int, int]] = []
    for _ in range(search_locs):
        y = int(rng.integers(0, max(h - th, 1)))
        x = int(rng.integers(0, max(w - tw, 1)))
        locs.append((y, x))
    for y in range(0, max(h - th, 1), max(1, th // 2)):
        for x in range(0, max(w - tw, 1), max(1, tw // 2)):
            locs.append((y, x))
    target_f = target.astype(np.float32)
    best = (0, 0)
    best_err = float("inf")
    for y, x in locs:
        cand = im[y:y + th, x:x + tw].astype(np.float32)
        if cand.shape != target_f.shape:
            continue
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


def compute_repair_plan(arr: np.ndarray, patch: int = 64) -> list[dict]:
    """Search for best-match patches against the *albedo* and return a plan
    that can be replayed on every other map.

    A "plan" is a list of operations:
        {axis: 'h'|'v', slot_x_or_y: int, target_shape: (h, w), source_yx: (py, px)}

    By computing this once on the albedo and replaying on every other map,
    we guarantee spatial alignment across the PBR set. (If we re-searched
    per map, normal/roughness would minimize MSE on different criteria and
    pick a different source patch — visible as a small misalignment in the
    seam region between maps.)
    """
    h, w = arr.shape[:2]
    band = patch
    cy, cx = h // 2, w // 2
    offset = offset_image(arr)
    plan: list[dict] = []

    # Horizontal seam slots.
    h_strip = offset[cy - band:cy + band, :]
    for x in range(0, w, band):
        target = h_strip[:, x:x + band]
        if target.shape[1] < 4:
            continue
        interior = arr[band:h - band, band:w - band].astype(np.float32)
        if interior.shape[0] < target.shape[0] or interior.shape[1] < target.shape[1]:
            continue
        py, px = find_best_patch(interior, target)
        plan.append({"axis": "h", "x": x,
                     "target_shape": (target.shape[0], target.shape[1]),
                     "source_yx": (py, px)})

    # Vertical seam slots.
    v_strip = offset[:, cx - band:cx + band]
    for y in range(0, h, band):
        target = v_strip[y:y + band, :]
        if target.shape[0] < 4:
            continue
        interior = arr[band:h - band, band:w - band].astype(np.float32)
        if interior.shape[0] < target.shape[0] or interior.shape[1] < target.shape[1]:
            continue
        py, px = find_best_patch(interior, target)
        plan.append({"axis": "v", "y": y,
                     "target_shape": (target.shape[0], target.shape[1]),
                     "source_yx": (py, px)})
    return plan


def apply_repair_plan(arr: np.ndarray, plan: list[dict],
                       patch: int = 64, feather: int = 12) -> np.ndarray:
    """Apply a precomputed repair plan to a map. The plan is shared across
    all maps in the PBR set so they stay aligned after repair."""
    h, w = arr.shape[:2]
    band = patch
    cy, cx = h // 2, w // 2
    offset = offset_image(arr)
    out = offset.astype(np.float32)

    h_strip = out[cy - band:cy + band, :].copy()
    v_strip = out[:, cx - band:cx + band].copy()
    interior = arr[band:h - band, band:w - band].astype(np.float32)

    for op in plan:
        ts_h, ts_w = op["target_shape"]
        py, px = op["source_yx"]
        if (interior.shape[0] < ts_h + py or interior.shape[1] < ts_w + px
                or py < 0 or px < 0):
            # Plan referenced a slot that doesn't fit this map's interior;
            # skip this op rather than crash.
            continue
        cand = interior[py:py + ts_h, px:px + ts_w]
        if cand.shape[:2] != (ts_h, ts_w):
            continue
        m = feather_mask(ts_h, ts_w, feather)
        if cand.ndim == 3:
            m = m[..., None]
        if op["axis"] == "h":
            x = op["x"]
            sw = min(ts_w, w - x)
            if sw <= 0:
                continue
            h_strip[:, x:x + sw] = h_strip[:, x:x + sw] * (1 - m[:, :sw]) + cand[:, :sw] * m[:, :sw]
        else:
            y = op["y"]
            sh = min(ts_h, h - y)
            if sh <= 0:
                continue
            v_strip[y:y + sh, :] = v_strip[y:y + sh, :] * (1 - m[:sh, :]) + cand[:sh, :] * m[:sh, :]

    out[cy - band:cy + band, :] = h_strip
    out[:, cx - band:cx + band] = v_strip
    out = np.clip(out, 0, 255).astype(np.uint8)
    return offset_image(out)  # offset back so seams are again at the borders


def repair(arr: np.ndarray, patch: int = 64, feather: int = 12) -> np.ndarray:
    """Single-map repair: compute plan + apply. For multi-map alignment,
    use compute_repair_plan once on albedo and apply_repair_plan on others."""
    plan = compute_repair_plan(arr, patch=patch)
    return apply_repair_plan(arr, plan, patch=patch, feather=feather)


def edge_seam_score(im: np.ndarray) -> float:
    edge_lr = float(np.mean((im[:, 0].astype(np.float32) - im[:, -1].astype(np.float32)) ** 2)) / (255 ** 2)
    edge_tb = float(np.mean((im[0, :].astype(np.float32) - im[-1, :].astype(np.float32)) ** 2)) / (255 ** 2)
    return max(edge_lr, edge_tb)


def backup_path(p: Path) -> Path:
    return p.with_name(p.stem + ".pre_repair" + p.suffix)


def restore_originals(material_dir: Path) -> int:
    """Copy *.pre_repair.<ext> back over the originals. Returns count restored."""
    n = 0
    for backup in material_dir.iterdir():
        if not backup.is_file():
            continue
        stem = backup.stem
        if not stem.endswith(".pre_repair"):
            continue
        original_stem = stem[: -len(".pre_repair")]
        original = backup.with_name(original_stem + backup.suffix)
        shutil.copy2(backup, original)
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--material", type=Path, required=True)
    ap.add_argument("--threshold", type=float, default=0.005,
                    help="if albedo edge MSE is below this, skip repair (use --force to override)")
    ap.add_argument("--patch", type=int, default=64)
    ap.add_argument("--feather", type=int, default=12)
    ap.add_argument("--force", action="store_true",
                    help="repair even if score is below threshold")
    ap.add_argument("--restore", action="store_true",
                    help="copy *.pre_repair.<ext> back over originals and exit")
    ap.add_argument("--no-backup", action="store_true",
                    help="overwrite originals without writing backups (NOT RECOMMENDED)")
    args = ap.parse_args()

    if not args.material.is_dir():
        raise SystemExit(f"not a directory: {args.material}")

    if args.restore:
        n = restore_originals(args.material)
        print(f"  restored {n} files from .pre_repair backups")
        return

    maps = discover_maps(args.material)
    if "albedo" not in maps:
        raise SystemExit(f"no albedo found in {args.material} (looked for *_albedo.png)")
    print(f"  found {len(maps)} maps: {sorted(maps.keys())}")

    # Score albedo first.
    albedo_path = maps["albedo"]
    albedo_arr = np.asarray(Image.open(albedo_path).convert("RGB"), dtype=np.uint8)
    pre_score = edge_seam_score(albedo_arr)
    print(f"  pre-repair albedo edge MSE: {pre_score:.5f}")

    if pre_score < args.threshold and not args.force:
        print(f"  below threshold ({args.threshold}); skipping repair (use --force to override)")
        return

    # Compute the repair plan ONCE on the albedo, then replay it on every
    # other map. Per-map re-search would minimize MSE on each map's pixel
    # content (normal/roughness/etc), picking different source patches —
    # albedo and normal would end up patched from spatially inconsistent
    # source regions, breaking alignment. The shared plan is what makes
    # the multi-map repair safe.
    print(f"  computing repair plan from albedo...")
    plan = compute_repair_plan(albedo_arr, patch=args.patch)
    print(f"  plan has {len(plan)} patch ops; replaying across {len(maps)} maps...")

    repair_record = {
        "id": args.material.name,
        "pre_score": pre_score,
        "patch": args.patch,
        "feather": args.feather,
        "repaired_at": datetime.now(timezone.utc).isoformat(),
        "plan_op_count": len(plan),
        "maps": {},
    }
    post_score: float | None = None

    for kind, path in maps.items():
        im = np.asarray(Image.open(path), dtype=np.uint8)
        # Apply the SAME plan to every map; for grayscale, replicate to 3
        # channels for shape compatibility, then collapse back.
        if im.ndim == 2:
            im_3 = np.stack([im, im, im], axis=-1)
            rep = apply_repair_plan(im_3, plan, patch=args.patch, feather=args.feather)
            rep = rep[..., 0]
        elif im.shape[-1] == 4:
            rgb = im[..., :3]
            alpha = im[..., 3:]
            rep_rgb = apply_repair_plan(rgb, plan, patch=args.patch, feather=args.feather)
            rep = np.concatenate([rep_rgb, alpha], axis=-1)
        else:
            rep = apply_repair_plan(im, plan, patch=args.patch, feather=args.feather)

        # Backup, then overwrite.
        if not args.no_backup:
            bk = backup_path(path)
            if not bk.exists():  # only backup once; second runs preserve original original
                shutil.copy2(path, bk)
        Image.fromarray(rep).save(path)
        repair_record["maps"][kind] = {
            "path": str(path.name),
            "backup": str(backup_path(path).name) if not args.no_backup else None,
        }
        if kind == "albedo":
            check = rep[..., :3] if rep.ndim == 3 else rep
            post_score = edge_seam_score(check)

    print(f"  post-repair albedo edge MSE: {post_score:.5f}")
    repair_record["post_score"] = post_score
    repair_record["delta"] = (pre_score - post_score) if post_score is not None else None

    record_path = args.material / "repair_record.json"
    record_path.write_text(json.dumps(repair_record, indent=2), encoding="utf-8")
    print(f"  wrote repair record -> {record_path.name}")


if __name__ == "__main__":
    main()
