"""Texture QA — three-check tile/seam metric.

Replaces the previous 1-pixel-wide vanity metric. The old seam grade only
measured wrap-around continuity at the outermost columns/rows; visible
defects 8+ pixels in (lattice patterns, healed-but-still-visible center
seams, periodic structure) all scored grade A. This file replaces it
with three orthogonal checks. A texture grades A only if all three pass.

Checks:

  1. edge_continuity
     Mean-squared-error between the leftmost and rightmost columns and
     between top and bottom rows. Catches gross border discontinuities.
     Same idea as the old metric, kept for backward compat.

  2. junction_visibility
     Tile the texture 2x2 and look at the cross-shaped seam region.
     Compute Laplacian-of-Gaussian energy in the seam region vs. the
     interior. If the seam region has measurably more high-frequency
     content, the seam is visible.

  3. periodic_artifact
     FFT power spectrum of the (centered, hann-windowed) image. Look for
     spurious peaks at frequencies that correspond to integer fractions
     of the texture width (1/2, 1/3, 1/4) — signatures of FLUX center
     bias and lattice artifacts. Compares peak power to the surrounding
     spectrum's median.

Outputs are deliberately verbose: raw numbers + per-check pass/fail +
overall grade. Consumers can re-grade against tighter thresholds without
re-running the metric.

  qa/
    seam_score.json       -- numeric metrics + per-check pass/fail
    summary.json          -- compact summary (id, grade, notes, previews)
    tile_2x2.png          -- albedo tiled 2x2 (visual seam preview)
    sphere_preview.png    -- albedo on a fake sphere (lambert)
    plane_preview.png     -- albedo on a tilted plane
    sanity.json           -- map presence + value ranges + notes

Usage:
  python texture_qa.py --material D:/assets/world/textures/library/Rock035
  python texture_qa.py --all
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


CATALOG = Path("D:/assets/world/textures/catalog/materials.jsonl")
LIBRARY = Path("D:/assets/world/textures/library")


# Pass thresholds. Empirically calibrated; see docs/TEXTURE_PIPELINE_FIX_PLAN.md.
EDGE_CONTINUITY_PASS = 0.005      # MSE in [0, 1]; <0.005 = edges wrap cleanly
JUNCTION_RATIO_PASS = 1.35        # seam-region energy / interior energy < 1.35x
PERIODIC_LOCALITY_PASS = 18.0     # peak / local-neighborhood median < 18x
                                  # calibrated 2026-05-07 against the library:
                                  # real-photo PolyHaven sets sit at 8-17; AI
                                  # noise-like at 6-20; structured patterns
                                  # (cobble) and lattice artifacts at 25-600.

# Per-category threshold overrides. Categories naturally periodic (brick,
# wood) get a relaxed periodic check; rocky/organic categories have a
# slightly looser periodic to account for real natural repetition; default
# applies otherwise.
CATEGORY_THRESHOLDS = {
    "Brick":    {"periodic": 80.0},
    "Wood":     {"periodic": 50.0},
    "Tile":     {"periodic": 80.0},
    "Cobble":   {"periodic": 80.0},
    "Rock":     {"periodic": 25.0},
    "Snow":     {"periodic": 18.0},  # uniform roughness handled separately
    "Sand":     {"periodic": 18.0},
    "Water":    {"periodic": 18.0},
    "Liquid":   {"periodic": 18.0},
    "Ground":   {"periodic": 22.0},
    "Foliage":  {"periodic": 25.0},
    "Metal":    {"periodic": 30.0},
    "Concrete": {"periodic": 25.0},
}


def _thresholds_for(category: str | None) -> dict:
    """Return effective pass thresholds for a category. Falls back to defaults."""
    base = {
        "edge_continuity": EDGE_CONTINUITY_PASS,
        "junction_visibility": JUNCTION_RATIO_PASS,
        "periodic_artifact": PERIODIC_LOCALITY_PASS,
    }
    if not category:
        return base
    overrides = CATEGORY_THRESHOLDS.get(category.strip(), {})
    if "edge" in overrides:
        base["edge_continuity"] = overrides["edge"]
    if "junction" in overrides:
        base["junction_visibility"] = overrides["junction"]
    if "periodic" in overrides:
        base["periodic_artifact"] = overrides["periodic"]
    return base


def _load_manifest_for(material_dir: Path) -> dict | None:
    if not CATALOG.exists():
        return None
    target = material_dir.name
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("id") == target:
            return rec
    return None


def _find_albedo(material_dir: Path, manifest: dict | None) -> Path | None:
    """Locate the albedo file. Manifest takes precedence; falls back to filename."""
    if manifest and "albedo" in manifest.get("maps", {}):
        cand = material_dir / manifest["maps"]["albedo"]
        if cand.exists():
            return cand
    for p in material_dir.iterdir():
        if p.suffix.lower() not in (".png", ".jpg"):
            continue
        name = p.name.lower()
        # Skip stash files like _albedo.pre_delight.png, _albedo.pre_repair.png
        if "pre_" in name:
            continue
        if "color" in name or "albedo" in name:
            return p
    return None


def _laplacian_energy(arr: np.ndarray) -> np.ndarray:
    """Per-pixel |Laplacian| on a grayscale float32 array. No external deps."""
    # 5-tap discrete Laplacian
    pad = np.pad(arr, 1, mode="reflect")
    lap = (
        pad[1:-1, 2:] + pad[1:-1, :-2] + pad[2:, 1:-1] + pad[:-2, 1:-1]
        - 4.0 * pad[1:-1, 1:-1]
    )
    return np.abs(lap)


def edge_continuity(im: np.ndarray, threshold: float = EDGE_CONTINUITY_PASS) -> dict:
    """1-pixel border MSE between opposite edges. Catches outright discontinuity."""
    edge_lr = float(np.mean((im[:, 0] - im[:, -1]) ** 2))
    edge_tb = float(np.mean((im[0, :] - im[-1, :]) ** 2))
    overall = max(edge_lr, edge_tb)
    return {
        "edge_lr_mse": edge_lr,
        "edge_tb_mse": edge_tb,
        "overall_mse": overall,
        "passed": overall < threshold,
        "threshold": threshold,
    }


def junction_visibility(im: np.ndarray, band_frac: float = 0.04,
                         threshold: float = JUNCTION_RATIO_PASS) -> dict:
    """Tile 2x2, compare LoG energy in the seam-cross region vs. the interior.

    A seam that's been healed but still visible shows up as a high-frequency
    band along the centerline of the tiled image. We compare that band's
    energy to a reference taken from a non-seam region.

    `band_frac` controls the seam band width as a fraction of the texture's
    own size. 0.04 of 1024 = 40 pixels — wide enough to catch FLUX healing
    artifacts but not so wide that legitimate detail dilutes the signal.
    """
    h, w = im.shape[:2]
    gray = im.mean(axis=-1) if im.ndim == 3 else im
    tiled = np.tile(gray, (2, 2))
    th, tw = tiled.shape

    band_h = max(8, int(h * band_frac))
    band_w = max(8, int(w * band_frac))

    # The 2x2 seam cross sits at row=h and col=w (where adjacent copies meet).
    cy, cx = h, w

    lap = _laplacian_energy(tiled)

    # Horizontal seam band: rows cy-band_h .. cy+band_h, full width
    h_band = lap[cy - band_h:cy + band_h, :]
    # Vertical seam band: full height, cols cx-band_w .. cx+band_w
    v_band = lap[:, cx - band_w:cx + band_w]
    seam_energy = float((h_band.sum() + v_band.sum())
                        / (h_band.size + v_band.size))

    # Reference interior: a quarter-tile-sized window inside one copy,
    # offset from any seam.
    ry0, ry1 = h // 4, 3 * h // 4
    rx0, rx1 = w // 4, 3 * w // 4
    interior = lap[ry0:ry1, rx0:rx1]
    interior_energy = float(interior.mean())
    eps = 1e-9
    ratio = seam_energy / max(interior_energy, eps)

    return {
        "seam_energy": seam_energy,
        "interior_energy": interior_energy,
        "ratio": ratio,
        "band_pixels": [band_h, band_w],
        "passed": ratio < threshold,
        "threshold": threshold,
    }


def periodic_artifact(im: np.ndarray,
                       threshold: float = PERIODIC_LOCALITY_PASS) -> dict:
    """FFT-based check for lattice / center-bias artifacts.

    Real natural textures have a smooth power spectrum where any peaks
    blend into their neighborhoods. A repeating structure (lattice, FLUX
    healing seam, regular grid) produces a sharp, *localized* peak at
    some non-DC frequency.

    Algorithm: find the brightest pixel in the AC region (anywhere outside
    a small DC mask) and compare its tight-window max to its surrounding-
    window median. High ratio = sharp delta-like peak = lattice signature.
    Low ratio = smooth lump = natural texture.

    This catches lattices at any frequency, not just 1/2, 1/3, 1/4.
    """
    h, w = im.shape[:2]
    gray = im.mean(axis=-1) if im.ndim == 3 else im
    gray = gray - gray.mean()
    hann_y = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(h) / max(h - 1, 1))
    hann_x = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(w) / max(w - 1, 1))
    windowed = gray * np.outer(hann_y, hann_x)
    F = np.fft.fft2(windowed)
    P = np.abs(F) ** 2
    P_shift = np.fft.fftshift(P)

    cy, cx = h // 2, w // 2
    rmask = max(8, min(h, w) // 64)

    # Mask out the DC region; we don't care about the bias.
    yy, xx = np.indices(P_shift.shape)
    in_dc = (np.abs(yy - cy) <= rmask) & (np.abs(xx - cx) <= rmask)
    P_search = P_shift.copy()
    P_search[in_dc] = 0.0

    # Find the brightest AC bin.
    py, px = np.unravel_index(int(np.argmax(P_search)), P_search.shape)

    inner = 3
    outer = 12
    py0i = max(0, py - inner); py1i = min(h, py + inner + 1)
    px0i = max(0, px - inner); px1i = min(w, px + inner + 1)
    py0o = max(0, py - outer); py1o = min(h, py + outer + 1)
    px0o = max(0, px - outer); px1o = min(w, px + outer + 1)
    inner_max = float(P_shift[py0i:py1i, px0i:px1i].max())
    outer_med = float(np.median(P_shift[py0o:py1o, px0o:px1o]))
    eps = 1e-9
    locality_ratio = inner_max / max(outer_med, eps)

    # Frequency in cycles-per-image of the dominant peak (informational).
    freq_y = py - cy
    freq_x = px - cx
    period_y = (h / abs(freq_y)) if freq_y != 0 else 0.0
    period_x = (w / abs(freq_x)) if freq_x != 0 else 0.0

    return {
        "peak_locality_ratio": locality_ratio,
        "peak_pos": [int(py - cy), int(px - cx)],
        "peak_period_px": [period_y, period_x],
        "passed": locality_ratio < threshold,
        "threshold": threshold,
    }


def grade_from_checks(checks: dict) -> str:
    n_pass = sum(1 for k in ("edge_continuity", "junction_visibility",
                              "periodic_artifact") if checks[k]["passed"])
    return {3: "A", 2: "B", 1: "C", 0: "D"}[n_pass]


def seam_score(albedo_path: Path, category: str | None = None) -> dict:
    """Run all three checks. Returns the grade record. Per-category
    threshold overrides apply (see CATEGORY_THRESHOLDS)."""
    im = np.asarray(Image.open(albedo_path).convert("RGB"),
                    dtype=np.float32) / 255.0
    th = _thresholds_for(category)
    checks = {
        "edge_continuity": edge_continuity(im, threshold=th["edge_continuity"]),
        "junction_visibility": junction_visibility(im, threshold=th["junction_visibility"]),
        "periodic_artifact": periodic_artifact(im, threshold=th["periodic_artifact"]),
    }
    overall_grade = grade_from_checks(checks)
    return {
        "version": 2,
        "category": category,
        "thresholds_applied": th,
        "checks": checks,
        "grade": overall_grade,
        "passed": overall_grade == "A",
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
    im = np.asarray(
        Image.open(albedo_path).convert("RGB").resize((size, size)),
        dtype=np.float32,
    ) / 255.0
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
    shaded[~mask] = 0.06
    return Image.fromarray((shaded * 255).clip(0, 255).astype(np.uint8),
                           mode="RGB")


def plane_preview(albedo_path: Path, size: int = 320) -> Image.Image:
    """Render a tilted plane with the texture, lambert shading."""
    im = np.asarray(
        Image.open(albedo_path).convert("RGB").resize((size, size)),
        dtype=np.float32,
    ) / 255.0
    out = np.zeros((size, size, 3), dtype=np.float32)
    for y in range(size):
        scale = 0.5 + 0.5 * (y / size)
        src_y = int((y / size) * size)
        for x in range(size):
            cx_v = (x - size / 2) / scale + size / 2
            sx = int(np.clip(cx_v, 0, size - 1))
            out[y, x] = im[src_y, sx]
    grad = np.linspace(0.4, 1.0, size).reshape(1, -1, 1)
    out = out * (0.6 + 0.4 * grad)
    return Image.fromarray((out * 255).clip(0, 255).astype(np.uint8),
                           mode="RGB")


def _discover_maps(material_dir: Path) -> dict[str, str]:
    """Find <id>_<map>.png files when no manifest is available.

    Same convention as seam_repair.py: filename ends in _<map> where
    map is one of albedo/normal/roughness/metallic/height/ao. Skips
    .pre_repair / .pre_delight backup files.
    """
    found: dict[str, str] = {}
    known = ("albedo", "normal", "roughness", "metallic", "height", "ao")
    for p in material_dir.iterdir():
        if not p.is_file() or p.suffix.lower() not in (".png", ".jpg"):
            continue
        name = p.stem.lower()
        if "pre_" in name:
            continue
        for kind in known:
            if name.endswith(f"_{kind}") or name == kind:
                if kind not in found:
                    found[kind] = p.name
                break
    return found


# Categories where naturally-uniform roughness is expected (don't flag flat
# roughness as suspicious for these). "Snow" was the original false-positive
# case; same logic applies to fresh sand, undisturbed water, polished metal.
UNIFORM_ROUGHNESS_OK_CATEGORIES = {"Snow", "Water", "Sand", "Liquid"}


def sanity_check(material_dir: Path, manifest: dict | None,
                 category: str | None = None) -> dict:
    """Map presence and value-range checks. Falls back to filename discovery
    when there's no manifest yet (orchestrator writes the catalog after QA).

    `category` (one of the aaa_texture --category values) relaxes a few
    checks that would otherwise flag legitimate but unusual materials —
    e.g. snow's roughness is genuinely flat across the whole tile.
    """
    if manifest and manifest.get("maps"):
        maps = manifest["maps"]
    else:
        maps = _discover_maps(material_dir)
    if category is None and manifest is not None:
        category = manifest.get("category")
    notes: list[str] = []
    stats: dict = {}
    uniform_rough_ok = (category or "").strip() in UNIFORM_ROUGHNESS_OK_CATEGORIES
    for kind, fname in maps.items():
        p = material_dir / fname
        if not p.exists():
            notes.append(f"{kind}: missing file {fname}")
            continue
        im = np.asarray(Image.open(p), dtype=np.float32) / 255.0
        if im.ndim == 3:
            im = im[..., :3]
        s = {"min": float(im.min()), "max": float(im.max()),
             "mean": float(im.mean()), "std": float(im.std())}
        stats[kind] = s
        if kind == "roughness" and s["std"] < 0.02 and not uniform_rough_ok:
            notes.append("roughness has near-zero variance (suspicious flat map)")
        if kind == "metallic" and s["mean"] > 0.5 and "metal" not in (manifest.get("tags") or [] if manifest else []):
            notes.append("metallic map looks high but tags say non-metal")
        if kind == "albedo" and s["max"] < 0.2:
            notes.append("albedo unusually dark (likely encoding issue)")
    return {
        "expected_maps": ["albedo", "normal", "roughness"],
        "found_maps": sorted(maps.keys()),
        "missing_maps": [m for m in ("albedo", "normal", "roughness")
                         if m not in maps],
        "category": category,
        "uniform_roughness_ok": uniform_rough_ok,
        "stats": stats,
        "notes": notes,
        "ok": not notes and "albedo" in maps and "normal" in maps,
    }


def run_qa(material_dir: Path, category: str | None = None):
    print(f"[QA] {material_dir.name}")
    manifest = _load_manifest_for(material_dir)
    albedo = _find_albedo(material_dir, manifest)
    if not albedo:
        print("  no albedo found")
        return

    qa_dir = material_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    # Resolve category: explicit arg overrides manifest's record.
    effective_cat = category or (manifest or {}).get("category")
    seam = seam_score(albedo, category=effective_cat)
    (qa_dir / "seam_score.json").write_text(json.dumps(seam, indent=2),
                                            encoding="utf-8")
    cs = seam["checks"]
    print(f"  grade={seam['grade']}  "
          f"edge={cs['edge_continuity']['overall_mse']:.4f}({'P' if cs['edge_continuity']['passed'] else 'F'})  "
          f"junc={cs['junction_visibility']['ratio']:.2f}({'P' if cs['junction_visibility']['passed'] else 'F'})  "
          f"period={cs['periodic_artifact']['peak_locality_ratio']:.1f}({'P' if cs['periodic_artifact']['passed'] else 'F'})")

    tile_2x2(albedo).save(qa_dir / "tile_2x2.png")
    sphere_preview(albedo).save(qa_dir / "sphere_preview.png")
    plane_preview(albedo).save(qa_dir / "plane_preview.png")

    sanity = sanity_check(material_dir, manifest, category=category)
    (qa_dir / "sanity.json").write_text(json.dumps(sanity, indent=2),
                                        encoding="utf-8")
    print(f"  sanity ok={sanity['ok']} notes={len(sanity['notes'])}")

    summary = {
        "id": material_dir.name,
        "seam": seam,
        "sanity_ok": sanity["ok"],
        "notes": sanity["notes"],
        "previews": [
            "qa/tile_2x2.png",
            "qa/sphere_preview.png",
            "qa/plane_preview.png",
        ],
    }
    (qa_dir / "summary.json").write_text(json.dumps(summary, indent=2),
                                         encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--material", type=Path)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--category", default=None,
                    help="material category (Snow/Water/Sand/Liquid relax "
                         "the uniform-roughness sanity check). Falls back to "
                         "manifest-stored category if omitted.")
    args = ap.parse_args()
    if args.material:
        run_qa(args.material, category=args.category)
    elif args.all:
        for p in LIBRARY.iterdir():
            if p.is_dir():
                run_qa(p, category=args.category)
    else:
        ap.error("provide --material or --all")


if __name__ == "__main__":
    main()
