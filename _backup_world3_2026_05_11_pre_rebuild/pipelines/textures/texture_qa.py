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
from PIL import Image, ImageDraw


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
RICHNESS_PASS = 0.83              # combined content-presence score; defends
                                  # against "smooth A" failures (LESSONS L16).
                                  # Pass = 0.5 * (luminance_entropy/5 +
                                  # gradient_p99_normalized/0.4). Low = looks
                                  # like a featureless wash; the existing 3
                                  # axes pass it but the eye knows it's bad.
                                  # Calibrated A.7 / 2026-05-07 across 122
                                  # textures: SHIPPING materials all score
                                  # >=0.83 in non-uniform categories; known
                                  # smooth-A cases score 0.44-0.83.
                                  # Snow / Water / Liquid / Sand legitimately
                                  # have low spatial energy — see CATEGORY_
                                  # THRESHOLDS for relaxed values there.
                                  # **Advisory for now** (computed + reported,
                                  # NOT folded into A/B/C/D grade) so existing
                                  # texture grades don't shift under our feet.
                                  # Promote to gate when we've watched it.

# Per-category threshold overrides. Categories naturally periodic (brick,
# wood) get a relaxed periodic check; rocky/organic categories have a
# slightly looser periodic to account for real natural repetition; default
# applies otherwise.
CATEGORY_THRESHOLDS = {
    "Brick":    {"periodic": 80.0},
    "Wood":     {"periodic": 50.0},
    "Tile":     {"periodic": 80.0},
    "Cobble":   {"periodic": 80.0},
    "Rock":     {"periodic": 25.0,  "richness": 0.83},
    "Snow":     {"periodic": 18.0,  "richness": 0.45},  # legit low spatial energy
    "Sand":     {"periodic": 18.0,  "richness": 0.80},
    "Water":    {"periodic": 18.0,  "richness": 0.45},
    "Liquid":   {"periodic": 18.0,  "richness": 0.45},
    "Ground":   {"periodic": 22.0,  "richness": 0.83},
    "Foliage":  {"periodic": 25.0,  "richness": 0.83},
    "Metal":    {"periodic": 30.0,  "richness": 0.60},  # polished metal has
                                                        # narrow lum range,
                                                        # use a softer pass.
    "Concrete": {"periodic": 25.0,  "richness": 0.83},
}


def _thresholds_for(category: str | None) -> dict:
    """Return effective pass thresholds for a category. Falls back to defaults."""
    base = {
        "edge_continuity": EDGE_CONTINUITY_PASS,
        "junction_visibility": JUNCTION_RATIO_PASS,
        "periodic_artifact": PERIODIC_LOCALITY_PASS,
        "richness": RICHNESS_PASS,
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
    if "richness" in overrides:
        base["richness"] = overrides["richness"]
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


def richness(im: np.ndarray, threshold: float = RICHNESS_PASS) -> dict:
    """Content-presence check; defends against "smooth A" failures (LESSONS L16).

    The first three checks measure DEFECTS (edges don't match, seams visible,
    periodic structure). They're silent on whether the image has any content
    at all. A flat orange wash passes all three trivially. This check asks
    "does the image have either spread-out detail (high luminance entropy)
    or occasional strong gradients (high p99-normalized Laplacian)?"

    Combined score:
        score = 0.5 * (luminance_entropy / 5.0 +
                       gradient_p99_normalized / 0.4)

    where:
        luminance_entropy = Shannon entropy of the 256-bin luminance histogram
            (in bits). High = full dynamic range used (rich); low = compressed
            into a narrow band (smooth wash).
        gradient_p99_normalized = (99th percentile of |Laplacian|) / mean_lum.
            High = at least the strongest 1% of gradients are strong relative
            to the texture's average brightness (cracks, edges, features).
            Normalizing by mean luminance keeps dark moody textures with
            occasional sharp features (e.g. wgv3_rock_dark) on the rich side.

    Calibrated A.7 / 2026-05-07 across 122 textures. Per-category thresholds
    in CATEGORY_THRESHOLDS — Snow/Water/Liquid get 0.45 (legit low spatial
    energy), Sand gets 0.80, others 0.83.

    **Advisory for now.** Returned in the seam_score output but `grade_from_
    checks()` does NOT count this in the A/B/C/D grade. We'll watch the metric
    for a few sessions before promoting it to a hard gate.
    """
    h, w = im.shape[:2]
    gray = im.mean(axis=-1) if im.ndim == 3 else im
    # Luminance entropy
    hist, _ = np.histogram(gray, bins=256, range=(0.0, 1.0), density=False)
    p = hist.astype(np.float64) / max(hist.sum(), 1)
    p = p[p > 0]
    entropy_bits = float(-(p * np.log2(p)).sum()) if p.size else 0.0
    # Gradient p99 normalized by mean luminance
    lap = _laplacian_energy(gray)
    p99 = float(np.percentile(lap, 99))
    mean_lum = float(gray.mean())
    p99_norm = p99 / max(mean_lum, 1e-3)
    # Combined score
    score = 0.5 * (entropy_bits / 5.0 + p99_norm / 0.4)
    return {
        "luminance_entropy": entropy_bits,
        "gradient_p99": p99,
        "mean_luminance": mean_lum,
        "gradient_p99_normalized": p99_norm,
        "score": score,
        "passed": score >= threshold,
        "threshold": threshold,
    }


def grade_from_checks(checks: dict) -> str:
    """Grade A/B/C/D from the THREE original defect axes.

    `richness` is computed and reported in `checks` but NOT counted here —
    it's advisory until we've watched it for a few sessions. See RICHNESS_PASS
    docstring.
    """
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
        "richness": richness(im, threshold=th["richness"]),
    }
    overall_grade = grade_from_checks(checks)
    return {
        "version": 3,  # bumped when richness was added (advisory; A.7 / 2026-05-07)
        "category": category,
        "thresholds_applied": th,
        "checks": checks,
        "grade": overall_grade,
        "richness_passed": checks["richness"]["passed"],  # advisory; not in grade
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
          f"period={cs['periodic_artifact']['peak_locality_ratio']:.1f}({'P' if cs['periodic_artifact']['passed'] else 'F'})  "
          f"rich={cs['richness']['score']:.2f}({'P' if cs['richness']['passed'] else 'F'},advisory)")

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


TIER_SIZES_PX = {"4k": 4096, "2k": 2048, "1k": 1024, "512": 512, "256": 256}


def _tier_px(tier_name: str) -> int:
    """Return pixel size for a tier label like '2k' or '512'."""
    s = tier_name.strip().lower()
    if s in TIER_SIZES_PX:
        return TIER_SIZES_PX[s]
    try:
        return int(s)
    except ValueError:
        return 0


def _make_cross_tier_sheet(tier_results: list[dict], out_path: Path) -> None:
    """Write a cross-tier contact sheet: one row per tier showing tile_2x2 + metrics."""
    THUMB = 512
    TEXT_W = 480
    ROW_H = THUMB + 16
    PAD = 8
    sheet_w = PAD + THUMB + PAD + TEXT_W + PAD
    sheet_h = PAD + ROW_H * len(tier_results) + PAD * (len(tier_results) - 1)
    sheet = Image.new("RGB", (sheet_w, max(sheet_h, 64)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)

    for i, tr in enumerate(tier_results):
        y = PAD + i * (ROW_H + PAD)
        # Thumbnail
        tile_path = tr.get("tile_2x2_path")
        if tile_path and Path(tile_path).exists():
            thumb = Image.open(tile_path).convert("RGB")
            cx, cy = thumb.width // 2, thumb.height // 2
            half = THUMB // 2
            thumb = thumb.crop((cx - half, cy - half, cx + half, cy + half))
        else:
            thumb = Image.new("RGB", (THUMB, THUMB), (60, 60, 60))
        sheet.paste(thumb, (PAD, y + 8))

        # Text panel
        tx = PAD + THUMB + PAD
        ty = y + 12
        tier = tr["tier"]
        grade = tr["grade"]
        grade_color = {"A": (80, 220, 80), "B": (220, 220, 80),
                       "C": (220, 140, 60), "D": (220, 60, 60)}.get(grade, (200, 200, 200))
        draw.text((tx, ty), f"{tier}  grade={grade}", fill=grade_color)
        ty += 22
        cs = tr.get("checks", {})
        if cs:
            ec = cs.get("edge_continuity", {})
            jv = cs.get("junction_visibility", {})
            pa = cs.get("periodic_artifact", {})
            ri = cs.get("richness", {})
            draw.text((tx, ty),
                      f"edge={ec.get('overall_mse', 0):.4f}({'P' if ec.get('passed') else 'F'})  "
                      f"junc={jv.get('ratio', 0):.2f}({'P' if jv.get('passed') else 'F'})",
                      fill=(200, 200, 200))
            ty += 18
            draw.text((tx, ty),
                      f"period={pa.get('peak_locality_ratio', 0):.1f}({'P' if pa.get('passed') else 'F'})  "
                      f"rich={ri.get('score', 0):.2f}({'P' if ri.get('passed') else 'F'},adv)",
                      fill=(200, 200, 200))
            ty += 18
        richness_ok = tr.get("richness_passed", True)
        if not richness_ok:
            draw.text((tx, ty), "  richness advisory: low spatial energy",
                      fill=(180, 140, 60))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    print(f"  cross-tier sheet -> {out_path}")


def run_ladder_qa(ladder_dir: Path, category: str | None = None) -> list[dict]:
    """Run QA on every tier subdir in ladder_dir and write a cross-tier sheet.

    Each subdir must contain <id>_albedo.png (standard mip_ladder.py output).
    Writes per-tier qa/ dirs and ladder_dir/cross_tier_sheet.png.
    Returns list of per-tier result dicts sorted by resolution descending.
    """
    tier_dirs = [d for d in ladder_dir.iterdir() if d.is_dir() and d.name != "qa"]
    if not tier_dirs:
        print(f"  no tier subdirs found in {ladder_dir}")
        return []

    tier_dirs.sort(key=lambda d: _tier_px(d.name), reverse=True)
    print(f"[QA-ladder] {ladder_dir}  tiers={[d.name for d in tier_dirs]}")

    tier_results = []
    for tier_dir in tier_dirs:
        run_qa(tier_dir, category=category)
        ss_path = tier_dir / "qa" / "seam_score.json"
        tile_path = tier_dir / "qa" / "tile_2x2.png"
        if ss_path.exists():
            ss = json.loads(ss_path.read_text(encoding="utf-8"))
            tier_results.append({
                "tier": tier_dir.name,
                "grade": ss.get("grade", "?"),
                "checks": ss.get("checks", {}),
                "richness_passed": ss.get("richness_passed", True),
                "tile_2x2_path": str(tile_path) if tile_path.exists() else None,
            })
        else:
            tier_results.append({"tier": tier_dir.name, "grade": "?", "checks": {}})

    sheet_path = ladder_dir / "cross_tier_sheet.png"
    _make_cross_tier_sheet(tier_results, sheet_path)
    return tier_results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--material", type=Path)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ladder", type=Path, metavar="MAT_DIR",
                    help="run QA on every tier in <MAT_DIR>/ladder/")
    ap.add_argument("--ladder-dir", type=Path, metavar="LADDER_DIR",
                    help="run QA on every tier in this bare ladder dir (no /ladder suffix)")
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
    elif args.ladder:
        ladder_dir = args.ladder / "ladder"
        if not ladder_dir.is_dir():
            raise SystemExit(f"no ladder/ subdir found under {args.ladder}")
        run_ladder_qa(ladder_dir, category=args.category)
    elif args.ladder_dir:
        if not args.ladder_dir.is_dir():
            raise SystemExit(f"--ladder-dir not found: {args.ladder_dir}")
        run_ladder_qa(args.ladder_dir, category=args.category)
    else:
        ap.error("provide --material, --all, --ladder <mat_dir>, or --ladder-dir <dir>")


if __name__ == "__main__":
    main()
