"""Biome consistency check — does this texture's color family fit the kit?

Compares a candidate albedo to an anchor's LAB distribution.
Cheap signal we can use BEFORE palette_lock to catch "FLUX missed the
prompt" cases where the candidate is the wrong material entirely (e.g.
expected sand → got cracked mud, expected moss → got rusted metal).
palette_lock can pull a slightly-off candidate into the right hue, but
it can't rescue a fundamentally-wrong material.

ADVISORY, NOT GATE-BLOCKING. Some kit slots are *designed* to contrast
with the anchor (the rock_dark slot in a sandy desert kit is supposed
to be dark; the snow slot in an alpine kit is supposed to be white).
A `way_off` verdict means "very different from anchor." That can be
correct (intentional contrast) or wrong (FLUX missed the material).
Use the verdict + your eyes; don't auto-reject on it.

The two contrast slots that legitimately read way_off:
  - "rock_dark" slot (vs warm anchor)
  - "snow" slot (vs warm or dark anchor)
  - "ice" slot in tundra (similar)
For these, a way_off verdict on the dark/light extreme is expected.
A way_off verdict on the *anchor-adjacent* slots (e.g. "dirt" in a
sandy kit, "lichen" in a moss kit) indicates real prompt failure.

Two signals:
  1. LAB mean delta — Δ in average L*a*b* between candidate and anchor.
     Captures "is the overall lightness/chroma in the right neighborhood?"
  2. Hue histogram intersection — what fraction of the candidate's color
     histogram overlaps the anchor's. Captures "do they share colors?"

Verdicts:
  in_palette   — both signals pass. palette_lock will adjust this nicely.
  drift        — one signal off. palette_lock can pull but result may
                 lose character. Worth a regenerate first.
  way_off      — both signals off. Don't palette_lock — regenerate.

Usage:
  python biome_consistency.py --anchor desert_sand --candidate desert_dark_rock
  python biome_consistency.py --anchor tundra_moss --candidates tundra_lichen tundra_ice
  python biome_consistency.py --kit desert  # check every member of the kit
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

LIBRARY = Path(r"D:\assets\world\textures\library")
PIPELINE_DIR = Path(__file__).parent
BIOME_KITS_JSON = Path(r"D:\assets\world3\jobs\biome_kits.json")
MATERIAL_CATALOG_JSON = Path(r"D:\assets\world3\materials\catalog.json")
_CATALOG: dict[str, dict] | None = None


# Thresholds calibrated against the existing alpine + desert kits.
# Tune as we generate more kits and see real distributions.
LAB_DELTA_OK = 25.0      # Δ-L*a*b* mean below this = same neighborhood
LAB_DELTA_DRIFT = 50.0   # 25-50 = drifting; >50 = way off
HIST_OVERLAP_OK = 0.45   # >0.45 = good color overlap (in_palette)
HIST_OVERLAP_DRIFT = 0.20   # 0.20-0.45 = drift; <0.20 = way off


def _catalog() -> dict[str, dict]:
    global _CATALOG
    if _CATALOG is None:
        if MATERIAL_CATALOG_JSON.exists():
            data = json.loads(MATERIAL_CATALOG_JSON.read_text(encoding="utf-8"))
            _CATALOG = {m["id"]: m for m in data.get("materials", [])}
        else:
            _CATALOG = {}
    return _CATALOG


def _source_asset_id(material_id: str) -> str:
    entry = _catalog().get(material_id, {})
    provenance = entry.get("provenance", {})
    return provenance.get("source_asset_id") or material_id


def _albedo_path(material_id: str) -> Path:
    source_id = _source_asset_id(material_id)
    p = LIBRARY / source_id / f"{source_id}_albedo.png"
    if not p.exists():
        raise FileNotFoundError(f"albedo not found: {p}")
    return p


def _to_lab(rgb: np.ndarray) -> np.ndarray:
    from skimage import color
    return color.rgb2lab(rgb / 255.0)


def lab_mean_delta(rgb_a: np.ndarray, rgb_b: np.ndarray) -> float:
    """Mean Euclidean distance in LAB between two image distributions."""
    lab_a = _to_lab(rgb_a)
    lab_b = _to_lab(rgb_b)
    mean_a = lab_a.reshape(-1, 3).mean(axis=0)
    mean_b = lab_b.reshape(-1, 3).mean(axis=0)
    return float(np.linalg.norm(mean_a - mean_b))


def hist_overlap_3d(rgb_a: np.ndarray, rgb_b: np.ndarray, bins: int = 6) -> float:
    """3D histogram intersection in RGB. Returns fraction in [0, 1].

    Bin both images into a `bins**3` cube, sum min(a, b) / sum a — the
    standard histogram intersection metric. 1.0 = identical distribution,
    0.0 = no shared colors at all.
    """
    h_a, _ = np.histogramdd(
        rgb_a.reshape(-1, 3), bins=bins, range=[[0, 256]] * 3, density=False
    )
    h_b, _ = np.histogramdd(
        rgb_b.reshape(-1, 3), bins=bins, range=[[0, 256]] * 3, density=False
    )
    h_a = h_a / max(h_a.sum(), 1.0)
    h_b = h_b / max(h_b.sum(), 1.0)
    return float(np.minimum(h_a, h_b).sum())


def verdict_for(lab_delta: float, hist_overlap: float) -> str:
    lab_ok = lab_delta < LAB_DELTA_OK
    lab_drift = lab_delta < LAB_DELTA_DRIFT
    hist_ok = hist_overlap > HIST_OVERLAP_OK
    hist_drift = hist_overlap > HIST_OVERLAP_DRIFT

    if lab_ok and hist_ok:
        return "in_palette"
    if lab_drift and hist_drift:
        return "drift"
    return "way_off"


def check(anchor_id: str, candidate_id: str) -> dict:
    a_path = _albedo_path(anchor_id)
    c_path = _albedo_path(candidate_id)
    a_rgb = np.asarray(Image.open(a_path).convert("RGB"))
    c_rgb = np.asarray(Image.open(c_path).convert("RGB"))
    if a_rgb.shape != c_rgb.shape:
        c_rgb = np.asarray(
            Image.fromarray(c_rgb).resize(
                (a_rgb.shape[1], a_rgb.shape[0]), Image.LANCZOS
            )
        )
    lab_d = lab_mean_delta(a_rgb, c_rgb)
    hist_o = hist_overlap_3d(a_rgb, c_rgb)
    v = verdict_for(lab_d, hist_o)
    return {
        "anchor": anchor_id,
        "candidate": candidate_id,
        "lab_mean_delta": lab_d,
        "hist_overlap": hist_o,
        "verdict": v,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", help="anchor texture id")
    ap.add_argument("--candidate", help="single candidate id")
    ap.add_argument("--candidates", nargs="+", help="multiple candidates")
    ap.add_argument("--kit",
                    help="kit name from biome_kits.json (checks every member "
                         "vs the kit's anchor)")
    ap.add_argument("--json", action="store_true",
                    help="print machine-readable JSON instead of human text")
    args = ap.parse_args()

    pairs: list[tuple[str, str]] = []

    if args.kit:
        if not BIOME_KITS_JSON.exists():
            raise SystemExit(f"biome_kits.json not found at {BIOME_KITS_JSON}")
        kits = json.loads(BIOME_KITS_JSON.read_text(encoding="utf-8"))["kits"]
        kit = kits.get(args.kit)
        if not kit:
            raise SystemExit(f"kit {args.kit!r} not in biome_kits.json")
        anchor = kit["anchor"]
        for slot, member in kit["slots"].items():
            if member == anchor:
                continue
            pairs.append((anchor, member))
    elif args.anchor and args.candidate:
        pairs.append((args.anchor, args.candidate))
    elif args.anchor and args.candidates:
        for c in args.candidates:
            pairs.append((args.anchor, c))
    else:
        ap.error("provide --kit or (--anchor + --candidate(s))")

    results = []
    for anchor, candidate in pairs:
        try:
            r = check(anchor, candidate)
            results.append(r)
        except FileNotFoundError as e:
            results.append({"anchor": anchor, "candidate": candidate,
                            "error": str(e)})

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print(f"{'anchor':<22s}  {'candidate':<25s}  {'ΔLAB':>6s}  {'hist∩':>6s}  verdict")
    print("-" * 80)
    for r in results:
        if "error" in r:
            print(f"{r['anchor']:<22s}  {r['candidate']:<25s}  ERROR: {r['error']}")
            continue
        print(f"{r['anchor']:<22s}  {r['candidate']:<25s}  "
              f"{r['lab_mean_delta']:>6.1f}  {r['hist_overlap']:>6.2f}  {r['verdict']}")


if __name__ == "__main__":
    main()
