"""Phase F.4 — catalog-time transition pair audit.

Given a validated world plan, for every allowed adjacency pair, audit
whether the two biomes' primary catalog materials blend cleanly at a
standard seam band.

Computes four diagnostic metrics per pair:
  1. palette_delta_lab     - Lab-space distance between median colors
  2. luminance_range_delta - abs diff of p95-p5 luminance ranges
  3. high_freq_energy_ratio - ratio of high-freq band energy
  4. seam_band_delta_rgb01 - max RGB delta in the blended seam band

Verdict per pair: pass / warn / fail with a recommended_action:
  - palette_lock     - palette mismatch dominates; cross-material palette work
  - regenerate       - value-range or frequency badly off; rebuild the material
  - shader_blend_band - runtime-mitigatable wider seam
  - none             - pass

Output: world3/jobs/transition_audits/<plan_id>.json

Usage:
    python world3/pipeline/audit_transition_pairs.py world3/jobs/examples/world_plan_starter_5biome_procedural.json
    python world3/pipeline/audit_transition_pairs.py <plan> --strict   # exit 1 if any pair fails
    python world3/pipeline/audit_transition_pairs.py <plan> --json     # machine-readable to stdout

Exit codes:
    0  all pairs pass (or audit ran cleanly without --strict)
    1  --strict + at least one pair fails
    2  internal error (plan invalid, material missing, etc.)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
WORLD3 = Path(__file__).resolve().parents[1]
WGV3_DIR = WORLD3 / "textures" / "wgv3"
AUDITS_DIR = WORLD3 / "jobs" / "transition_audits"

# Standard audit parameters. Chosen to match the seam solver's defaults
# at the band size, so the audit reflects what runtime blending will do.
AUDIT_TILE_SIZE_PX = (512, 1024)   # match procedural bundle conventions
AUDIT_OVERLAP_PX = 128
AUDIT_COLOR_FEATHER_PX = 384

# Verdict thresholds — start permissive, tune as catalog grows.
THRESHOLD_PALETTE_LAB_WARN = 30.0    # Lab delta
THRESHOLD_PALETTE_LAB_FAIL = 60.0
THRESHOLD_LUM_RANGE_WARN = 0.30      # 0..1
THRESHOLD_LUM_RANGE_FAIL = 0.55
THRESHOLD_HF_RATIO_WARN = 2.5        # max(a, b) / min(a, b)
THRESHOLD_HF_RATIO_FAIL = 5.0
THRESHOLD_SEAM_BAND_WARN = 0.15      # 0..1
THRESHOLD_SEAM_BAND_FAIL = 0.30


def load_albedo(material_id: str) -> np.ndarray:
    """Load a material's albedo.png as float32 RGB in 0..1."""
    path = WGV3_DIR / material_id / "albedo.png"
    if not path.exists():
        raise FileNotFoundError(f"albedo not found for material '{material_id}' at {path}")
    img = Image.open(path).convert("RGB")
    return np.asarray(img, dtype=np.float32) / 255.0


def tile_to(arr: np.ndarray, target_hw: tuple[int, int]) -> np.ndarray:
    """Tile arr to the target (height, width). Uses np.tile + crop."""
    th, tw = target_hw
    h, w = arr.shape[:2]
    if h >= th and w >= tw:
        # already big enough — just crop
        return arr[:th, :tw]
    rep_h = (th + h - 1) // h
    rep_w = (tw + w - 1) // w
    tiled = np.tile(arr, (rep_h, rep_w, 1))
    return tiled[:th, :tw]


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Quick approximate sRGB → CIE Lab. Linearize, then matrix to XYZ,
    then to Lab. Vectorized; no per-pixel scipy/colormath dependency.
    Input/output shapes preserved (...,3)."""
    a = rgb.astype(np.float32)
    # sRGB → linear
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    # linear → XYZ (D65)
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]], dtype=np.float32)
    xyz = lin @ M.T
    # XYZ → Lab (D65 white)
    white = np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    xyz_n = xyz / white
    eps = (6.0 / 29.0) ** 3
    f = np.where(xyz_n > eps,
                 np.cbrt(xyz_n),
                 (xyz_n / (3 * (6.0/29.0) ** 2)) + (4.0 / 29.0))
    L = 116.0 * f[..., 1] - 16.0
    a_ = 500.0 * (f[..., 0] - f[..., 1])
    b_ = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a_, b_], axis=-1)


def median_color_rgb(arr: np.ndarray) -> np.ndarray:
    """Per-channel median across the flattened image."""
    flat = arr.reshape(-1, 3)
    return np.median(flat, axis=0)


def luminance_p5_p95(arr: np.ndarray) -> tuple[float, float]:
    lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    return float(np.percentile(lum, 5)), float(np.percentile(lum, 95))


def high_freq_energy(arr: np.ndarray) -> float:
    """Mean magnitude of (image - 3x3 box blur). Cheap high-freq proxy."""
    # Convert to luminance for the metric
    lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    # 3x3 box blur via np
    pad = np.pad(lum, 1, mode="edge")
    blurred = (
        pad[:-2, :-2] + pad[:-2, 1:-1] + pad[:-2, 2:] +
        pad[1:-1, :-2] + pad[1:-1, 1:-1] + pad[1:-1, 2:] +
        pad[2:, :-2] + pad[2:, 1:-1] + pad[2:, 2:]
    ) / 9.0
    return float(np.mean(np.abs(lum - blurred)))


def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def simulate_seam_band(left_rgb: np.ndarray, right_rgb: np.ndarray,
                        overlap_px: int, color_feather_px: int) -> dict:
    """Run the seam-solver blend math on the overlap band; report max
    RGB delta within the band as a proxy for runtime visible seam."""
    # Take the overlap window from each side
    a = left_rgb[:, -overlap_px:, :]      # right edge of left tile
    b_raw = right_rgb[:, :overlap_px, :]  # left edge of right tile
    diff = a - b_raw
    # global color bias (median of overlap diff)
    bias = np.median(diff.reshape(-1, 3), axis=0).astype(np.float32)
    right_matched = right_rgb + bias[None, None, :]
    # smoothstep blend across the overlap
    t = smoothstep(
        (np.arange(overlap_px, dtype=np.float32) + 0.5) / float(overlap_px)
    )[None, :, None]
    band = a * (1.0 - t) + right_matched[:, :overlap_px, :] * t
    # Max RGB delta within the band (proxy for visible discontinuity)
    band_internal_delta = np.abs(np.diff(band, axis=1))
    return {
        "global_bias_rgb": [float(x) for x in bias],
        "band_internal_max_delta_rgb01": float(np.max(band_internal_delta)),
        "band_internal_mean_delta_rgb01": float(np.mean(band_internal_delta)),
        "overlap_px": overlap_px,
    }


def classify(metrics: dict) -> tuple[str, str, list[str]]:
    """Return (verdict, recommended_action, notes)."""
    notes: list[str] = []
    palette = metrics["palette_delta_lab"]
    lum = metrics["luminance_range_delta"]
    hf = metrics["high_freq_energy_ratio"]
    seam = metrics["seam_band_internal_max_delta_rgb01"]

    fail_reasons: list[tuple[str, str]] = []
    warn_reasons: list[tuple[str, str]] = []

    if palette >= THRESHOLD_PALETTE_LAB_FAIL:
        fail_reasons.append(("palette_lock", f"palette_delta_lab={palette:.1f} >= {THRESHOLD_PALETTE_LAB_FAIL}"))
    elif palette >= THRESHOLD_PALETTE_LAB_WARN:
        warn_reasons.append(("palette_lock", f"palette_delta_lab={palette:.1f}"))

    if lum >= THRESHOLD_LUM_RANGE_FAIL:
        fail_reasons.append(("regenerate", f"luminance_range_delta={lum:.2f} >= {THRESHOLD_LUM_RANGE_FAIL}"))
    elif lum >= THRESHOLD_LUM_RANGE_WARN:
        warn_reasons.append(("regenerate", f"luminance_range_delta={lum:.2f}"))

    if hf >= THRESHOLD_HF_RATIO_FAIL:
        fail_reasons.append(("regenerate", f"high_freq_energy_ratio={hf:.2f} >= {THRESHOLD_HF_RATIO_FAIL}"))
    elif hf >= THRESHOLD_HF_RATIO_WARN:
        warn_reasons.append(("regenerate", f"high_freq_energy_ratio={hf:.2f}"))

    if seam >= THRESHOLD_SEAM_BAND_FAIL:
        fail_reasons.append(("shader_blend_band", f"seam_band_internal_max_delta_rgb01={seam:.2f} >= {THRESHOLD_SEAM_BAND_FAIL}"))
    elif seam >= THRESHOLD_SEAM_BAND_WARN:
        warn_reasons.append(("shader_blend_band", f"seam_band_internal_max_delta_rgb01={seam:.2f}"))

    if fail_reasons:
        # Pick the most-severe action; palette_lock > regenerate > shader_blend_band
        priority = {"palette_lock": 0, "regenerate": 1, "shader_blend_band": 2}
        fail_reasons.sort(key=lambda x: priority[x[0]])
        action = fail_reasons[0][0]
        notes = [r[1] for r in fail_reasons]
        return ("fail", action, notes)
    if warn_reasons:
        priority = {"palette_lock": 0, "regenerate": 1, "shader_blend_band": 2}
        warn_reasons.sort(key=lambda x: priority[x[0]])
        action = warn_reasons[0][0]
        notes = [r[1] for r in warn_reasons]
        return ("warn", action, notes)
    return ("pass", "none", [])


def audit_pair(biome_a: dict, biome_b: dict) -> dict:
    """Audit one biome pair. biome_a/b are full plan biome entries."""
    mat_a = biome_a["primary_material_id"]
    mat_b = biome_b["primary_material_id"]

    try:
        albedo_a = load_albedo(mat_a)
        albedo_b = load_albedo(mat_b)
    except FileNotFoundError as e:
        return {
            "biome_a": biome_a["id"], "biome_b": biome_b["id"],
            "material_a": mat_a, "material_b": mat_b,
            "verdict": "error", "recommended_action": "fix_catalog",
            "error": str(e),
        }

    target = (AUDIT_TILE_SIZE_PX[1], AUDIT_TILE_SIZE_PX[0])  # (H, W)
    a = tile_to(albedo_a, target)
    b = tile_to(albedo_b, target)

    # Palette delta in Lab
    lab_a = rgb_to_lab(median_color_rgb(a).reshape(1, 1, 3))[0, 0]
    lab_b = rgb_to_lab(median_color_rgb(b).reshape(1, 1, 3))[0, 0]
    palette_delta_lab = float(np.linalg.norm(lab_a - lab_b))

    # Luminance range delta
    pa = luminance_p5_p95(a); pb = luminance_p5_p95(b)
    range_a = pa[1] - pa[0]; range_b = pb[1] - pb[0]
    lum_range_delta = abs(range_a - range_b)

    # High-freq energy ratio
    hf_a = high_freq_energy(a)
    hf_b = high_freq_energy(b)
    eps = 1e-6
    hf_ratio = max(hf_a, hf_b) / max(min(hf_a, hf_b), eps)

    # Seam band simulation
    seam = simulate_seam_band(a, b, AUDIT_OVERLAP_PX, AUDIT_COLOR_FEATHER_PX)

    metrics = {
        "palette_delta_lab": palette_delta_lab,
        "luminance_range_delta": lum_range_delta,
        "high_freq_energy_ratio": hf_ratio,
        "seam_band_internal_max_delta_rgb01": seam["band_internal_max_delta_rgb01"],
        "seam_band_internal_mean_delta_rgb01": seam["band_internal_mean_delta_rgb01"],
        "median_lab_a": [float(x) for x in lab_a],
        "median_lab_b": [float(x) for x in lab_b],
        "luminance_p5_p95_a": list(pa),
        "luminance_p5_p95_b": list(pb),
        "high_freq_energy_a": hf_a,
        "high_freq_energy_b": hf_b,
        "global_bias_rgb": seam["global_bias_rgb"],
    }
    verdict, action, notes = classify(metrics)
    return {
        "biome_a": biome_a["id"], "biome_b": biome_b["id"],
        "material_a": mat_a, "material_b": mat_b,
        "verdict": verdict,
        "recommended_action": action,
        "notes": notes,
        "metrics": metrics,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("plan", type=Path, help="world plan JSON")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 if any pair fails (default: 0 regardless).")
    ap.add_argument("--json", action="store_true",
                    help="Emit the audit JSON to stdout in addition to writing it.")
    args = ap.parse_args()

    if not args.plan.exists():
        print(f"ERROR: plan not found at {args.plan}", file=sys.stderr)
        return 2
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    plan_id = plan.get("id", "unknown")
    biomes_by_id = {b["id"]: b for b in plan["biomes"]}
    pairs = plan["adjacency_rules"]["allowed_pairs"]

    print(f"=== audit_transition_pairs ===")
    print(f"Plan: {plan_id}  ({len(pairs)} allowed pairs)")
    print()

    results = []
    for pair in pairs:
        a_id, b_id = pair
        if a_id not in biomes_by_id or b_id not in biomes_by_id:
            results.append({
                "biome_a": a_id, "biome_b": b_id,
                "verdict": "error",
                "recommended_action": "fix_plan",
                "error": "adjacency references undeclared biome",
            })
            continue
        result = audit_pair(biomes_by_id[a_id], biomes_by_id[b_id])
        results.append(result)
        sym = {"pass": "OK  ", "warn": "WARN", "fail": "FAIL", "error": "ERR "}[result["verdict"]]
        action = result["recommended_action"]
        mats = f"{result['material_a']} <-> {result['material_b']}"
        print(f"  [{sym}] {result['biome_a']:<18} <-> {result['biome_b']:<18}  action={action}  ({mats})")
        if result["verdict"] in ("warn", "fail"):
            for note in result.get("notes", []):
                print(f"           - {note}")

    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = AUDITS_DIR / f"{plan_id}.json"
    audit_doc = {
        "schema_version": 1,
        "plan_id": plan_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "audit_params": {
            "tile_size_px": list(AUDIT_TILE_SIZE_PX),
            "overlap_px": AUDIT_OVERLAP_PX,
            "color_feather_px": AUDIT_COLOR_FEATHER_PX,
            "thresholds": {
                "palette_lab_warn": THRESHOLD_PALETTE_LAB_WARN,
                "palette_lab_fail": THRESHOLD_PALETTE_LAB_FAIL,
                "luminance_range_warn": THRESHOLD_LUM_RANGE_WARN,
                "luminance_range_fail": THRESHOLD_LUM_RANGE_FAIL,
                "hf_ratio_warn": THRESHOLD_HF_RATIO_WARN,
                "hf_ratio_fail": THRESHOLD_HF_RATIO_FAIL,
                "seam_band_warn": THRESHOLD_SEAM_BAND_WARN,
                "seam_band_fail": THRESHOLD_SEAM_BAND_FAIL,
            },
        },
        "pair_count": len(results),
        "pass_count": sum(1 for r in results if r["verdict"] == "pass"),
        "warn_count": sum(1 for r in results if r["verdict"] == "warn"),
        "fail_count": sum(1 for r in results if r["verdict"] == "fail"),
        "error_count": sum(1 for r in results if r["verdict"] == "error"),
        "pairs": results,
    }
    audit_path.write_text(json.dumps(audit_doc, indent=2), encoding="utf-8")

    print()
    print(f"--- Summary ---")
    print(f"  pass={audit_doc['pass_count']} warn={audit_doc['warn_count']} fail={audit_doc['fail_count']} error={audit_doc['error_count']}")
    print(f"  written: {audit_path.relative_to(ROOT)}")

    if args.json:
        print()
        print(json.dumps(audit_doc, indent=2))

    print()
    print("=== audit_transition_pairs DONE ===")

    if args.strict and (audit_doc["fail_count"] > 0 or audit_doc["error_count"] > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
