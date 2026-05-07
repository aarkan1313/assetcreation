"""Texture QA: seam score, 2x2 tile preview, sphere/plane preview, sanity checks.

Per the SOTA report: every accepted texture should have an automated QA artifact
the LLM can inspect later. This script takes a material directory and emits:

  qa/
    tile_2x2.png            -- albedo tiled 2x2 to expose seams
    seam_score.json         -- numeric seam metrics
    sphere_preview.png      -- albedo on a fake sphere (lambert lighting)
    plane_preview.png       -- albedo on a tilted plane (rough lighting)
    sanity.json             -- map presence + value ranges

Usage:
  python texture_qa.py --material D:/assets/world/textures/library/Rock035
  python texture_qa.py --all       # run on every catalog entry
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


CATALOG = Path("D:/assets/world/textures/catalog/materials.jsonl")
LIBRARY = Path("D:/assets/world/textures/library")


def load_manifest_for(material_dir: Path) -> dict | None:
    if not CATALOG.exists():
        return None
    target = material_dir.name
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("id") == target:
            return rec
    return None


def find_albedo(material_dir: Path, manifest: dict | None) -> Path | None:
    if manifest and "albedo" in manifest.get("maps", {}):
        return material_dir / manifest["maps"]["albedo"]
    # fallback: filename match
    for p in material_dir.iterdir():
        if p.suffix.lower() in (".png", ".jpg") and ("color" in p.name.lower() or "albedo" in p.name.lower()):
            return p
    return None


def seam_score(albedo_path: Path) -> dict:
    """Compute the seam difference: edge-band MSE for left|right and top|bottom.

    Returns scores in 0..1 (higher = more seam visible). Below ~0.005 is great.
    """
    im = np.asarray(Image.open(albedo_path).convert("RGB"), dtype=np.float32) / 255.0
    h, w, _ = im.shape
    band = max(8, min(h, w) // 64)

    left = im[:, :band]
    right = im[:, w - band:]
    top = im[:band, :]
    bottom = im[h - band:, :]

    # Compare opposite edges as if they wrap (left vs right, top vs bottom)
    lr_diff = float(np.mean((left - np.flip(right, axis=1)) ** 2))
    tb_diff = float(np.mean((top - np.flip(bottom, axis=0)) ** 2))

    # Compare actual wrap: left edge (column 0) vs right edge (column -1)
    edge_lr = float(np.mean((im[:, 0] - im[:, -1]) ** 2))
    edge_tb = float(np.mean((im[0, :] - im[-1, :]) ** 2))

    overall = max(edge_lr, edge_tb)
    grade = "A" if overall < 0.003 else "B" if overall < 0.01 else "C" if overall < 0.03 else "D"
    return {
        "edge_lr_mse": edge_lr,
        "edge_tb_mse": edge_tb,
        "band_lr_mse": lr_diff,
        "band_tb_mse": tb_diff,
        "overall": overall,
        "grade": grade,
        "band_pixels": band,
    }


def tile_2x2(albedo_path: Path) -> Image.Image:
    im = Image.open(albedo_path).convert("RGB")
    w, h = im.size
    canvas = Image.new("RGB", (w * 2, h * 2))
    for ox in (0, w):
        for oy in (0, h):
            canvas.paste(im, (ox, oy))
    return canvas


def sphere_preview(albedo_path: Path, size: int = 256) -> Image.Image:
    """Render a fake sphere with lambert shading and the albedo as 2D texture."""
    im = np.asarray(Image.open(albedo_path).convert("RGB").resize((size, size)), dtype=np.float32) / 255.0
    cy, cx = size / 2, size / 2
    ys, xs = np.indices((size, size))
    nx = (xs - cx) / (size / 2)
    ny = (ys - cy) / (size / 2)
    nz_sq = 1.0 - nx * nx - ny * ny
    mask = nz_sq > 0
    nz = np.where(mask, np.sqrt(np.clip(nz_sq, 0, 1)), 0)
    light = np.array([0.5, -0.5, 0.7])
    light /= np.linalg.norm(light)
    lambert = np.clip(nx * light[0] + ny * light[1] + nz * light[2], 0, 1)
    shaded = im * lambert[..., None]
    shaded[~mask] = 0.06  # background
    return Image.fromarray((shaded * 255).clip(0, 255).astype(np.uint8), mode="RGB")


def plane_preview(albedo_path: Path, size: int = 320) -> Image.Image:
    """Render a tilted plane with the texture, lambert shading."""
    im = np.asarray(Image.open(albedo_path).convert("RGB").resize((size, size)), dtype=np.float32) / 255.0
    out = np.zeros((size, size, 3), dtype=np.float32)
    for y in range(size):
        # perspective compression toward top
        scale = 0.5 + 0.5 * (y / size)
        src_y = int((y / size) * size)
        for x in range(size):
            cx = (x - size / 2) / scale + size / 2
            sx = int(np.clip(cx, 0, size - 1))
            out[y, x] = im[src_y, sx]
    # add lambert: light from upper-left
    grad = np.linspace(0.4, 1.0, size).reshape(1, -1, 1)
    out = out * (0.6 + 0.4 * grad)
    return Image.fromarray((out * 255).clip(0, 255).astype(np.uint8), mode="RGB")


def sanity_check(material_dir: Path, manifest: dict | None) -> dict:
    """Map presence and value-range checks."""
    maps = manifest.get("maps", {}) if manifest else {}
    notes: list[str] = []
    stats: dict = {}
    for kind, fname in maps.items():
        p = material_dir / fname
        if not p.exists():
            notes.append(f"{kind}: missing file {fname}")
            continue
        im = np.asarray(Image.open(p), dtype=np.float32) / 255.0
        if im.ndim == 3:
            im = im[..., :3]
        s = {"min": float(im.min()), "max": float(im.max()), "mean": float(im.mean()), "std": float(im.std())}
        stats[kind] = s
        if kind == "roughness" and s["std"] < 0.02:
            notes.append("roughness has near-zero variance (suspicious flat map)")
        if kind == "metallic" and s["mean"] > 0.5 and "metal" not in (manifest.get("tags") or []):
            notes.append("metallic map looks high but tags say non-metal")
        if kind == "albedo" and s["max"] < 0.2:
            notes.append("albedo unusually dark (likely encoding issue)")
    return {
        "expected_maps": ["albedo", "normal", "roughness"],
        "found_maps": sorted(maps.keys()),
        "missing_maps": [m for m in ("albedo", "normal", "roughness") if m not in maps],
        "stats": stats,
        "notes": notes,
        "ok": not notes and "albedo" in maps and "normal" in maps,
    }


def run_qa(material_dir: Path):
    print(f"[QA] {material_dir.name}")
    manifest = load_manifest_for(material_dir)
    albedo = find_albedo(material_dir, manifest)
    if not albedo:
        print("  no albedo found")
        return

    qa_dir = material_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    seam = seam_score(albedo)
    (qa_dir / "seam_score.json").write_text(json.dumps(seam, indent=2), encoding="utf-8")
    print(f"  seam grade={seam['grade']} overall={seam['overall']:.4f}")

    tile_2x2(albedo).save(qa_dir / "tile_2x2.png")
    sphere_preview(albedo).save(qa_dir / "sphere_preview.png")
    plane_preview(albedo).save(qa_dir / "plane_preview.png")

    sanity = sanity_check(material_dir, manifest)
    (qa_dir / "sanity.json").write_text(json.dumps(sanity, indent=2), encoding="utf-8")
    print(f"  sanity ok={sanity['ok']} notes={len(sanity['notes'])}")

    summary = {
        "id": material_dir.name,
        "seam": seam,
        "sanity_ok": sanity["ok"],
        "notes": sanity["notes"],
        "previews": ["qa/tile_2x2.png", "qa/sphere_preview.png", "qa/plane_preview.png"],
    }
    (qa_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--material", type=Path)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.material:
        run_qa(args.material)
    elif args.all:
        for p in LIBRARY.iterdir():
            if p.is_dir():
                run_qa(p)
    else:
        ap.error("provide --material or --all")


if __name__ == "__main__":
    main()
