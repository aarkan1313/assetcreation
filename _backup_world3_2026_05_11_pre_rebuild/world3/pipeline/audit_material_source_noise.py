#!/usr/bin/env python3
"""Audit close-range source material noise for green/organic terrain slots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def high_frequency_energy(rgb: np.ndarray) -> float:
    dx = np.abs(rgb[:, 1:, :] - rgb[:, :-1, :]).mean(axis=2)
    dy = np.abs(rgb[1:, :, :] - rgb[:-1, :, :]).mean(axis=2)
    return float((dx.mean() + dy.mean()) * 0.5)


def p95_gradient(rgb: np.ndarray) -> float:
    lum = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
    dx = np.abs(lum[:, 1:] - lum[:, :-1]).ravel()
    dy = np.abs(lum[1:, :] - lum[:-1, :]).ravel()
    return float(np.percentile(np.concatenate([dx, dy]), 95))


def green_dominance(rgb: np.ndarray) -> float:
    g = rgb[..., 1]
    rb = np.maximum(rgb[..., 0], rgb[..., 2])
    return float(np.mean(np.maximum(g - rb, 0.0)))


def saturation_mean(rgb: np.ndarray) -> float:
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    return float(np.mean((mx - mn) / np.maximum(mx, 1e-6)))


def should_audit(entry: dict) -> bool:
    family = str(entry.get("color_family", ""))
    mid = str(entry.get("id", ""))
    prompt = str(entry.get("provenance", {}).get("prompt", ""))
    haystack = " ".join([family, mid, prompt]).lower()
    keys = ["green", "organic", "grass", "leaf", "leaves", "moss", "scrub", "forest", "lichen", "fern"]
    return any(k in haystack for k in keys)


def audit_entry(entry: dict, hf_threshold: float, gradient_threshold: float, green_threshold: float) -> dict | None:
    albedo = entry.get("pbr_maps", {}).get("albedo")
    if not albedo:
        return None
    path = REPO / albedo
    if not path.exists():
        return {
            "id": entry.get("id"),
            "albedo": albedo,
            "status": "missing_albedo",
        }
    rgb = load_rgb(path)
    hf = high_frequency_energy(rgb)
    grad95 = p95_gradient(rgb)
    green = green_dominance(rgb)
    sat = saturation_mean(rgb)
    noise_score = hf * (1.0 + sat) * (1.0 + green * 2.0)
    flags: list[str] = []
    if hf >= hf_threshold:
        flags.append("high_frequency_noise")
    if grad95 >= gradient_threshold:
        flags.append("sharp_micro_contrast")
    if green >= green_threshold and (hf >= hf_threshold * 0.75 or grad95 >= gradient_threshold * 0.75):
        flags.append("green_organic_speckle")
    return {
        "id": entry.get("id"),
        "source": entry.get("source"),
        "color_family": entry.get("color_family"),
        "albedo": albedo,
        "high_frequency_energy": round(hf, 6),
        "gradient_p95": round(grad95, 6),
        "green_dominance": round(green, 6),
        "saturation_mean": round(sat, 6),
        "noise_score": round(noise_score, 6),
        "flags": flags,
        "status": "flagged" if flags else "ok",
    }


def write_markdown(results: list[dict], out_path: Path) -> None:
    lines = [
        "# M6 Source Material Noise Audit",
        "",
        "Date: 2026-05-08",
        "",
        "This audit targets green/organic terrain materials after user review flagged",
        "grass/leaves as too noisy for production. It is a source-material QA pass,",
        "not a transition or chunk-streaming failure.",
        "",
        "| Material | Status | HF energy | Grad p95 | Green dom | Flags |",
        "|----------|--------|-----------|----------|-----------|-------|",
    ]
    for r in sorted(results, key=lambda x: float(x.get("noise_score", 0.0)), reverse=True):
        lines.append(
            f"| `{r.get('id')}` | {r.get('status')} | {r.get('high_frequency_energy', '')} | "
            f"{r.get('gradient_p95', '')} | {r.get('green_dominance', '')} | "
            f"{', '.join(r.get('flags', [])) or '-'} |"
        )
    flagged = [r for r in results if r.get("status") == "flagged"]
    lines += [
        "",
        "## Verdict",
        "",
        f"Flagged {len(flagged)} of {len(results)} audited green/organic materials.",
        "Production promotion should prioritize flagged materials before adding more",
        "runtime visual complexity.",
    ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=str(ROOT / "materials/catalog.json"))
    ap.add_argument("--out-json", default=str(ROOT / "docs/M6_SOURCE_MATERIAL_NOISE_AUDIT.json"))
    ap.add_argument("--out-md", default=str(ROOT / "docs/M6_SOURCE_MATERIAL_NOISE_AUDIT.md"))
    ap.add_argument("--hf-threshold", type=float, default=0.055)
    ap.add_argument("--gradient-threshold", type=float, default=0.13)
    ap.add_argument("--green-threshold", type=float, default=0.045)
    args = ap.parse_args()

    catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    results = []
    for entry in catalog.get("materials", []):
        if should_audit(entry):
            result = audit_entry(entry, args.hf_threshold, args.gradient_threshold, args.green_threshold)
            if result is not None:
                results.append(result)

    out = {
        "version": 1,
        "updated": "2026-05-08",
        "thresholds": {
            "high_frequency_energy": args.hf_threshold,
            "gradient_p95": args.gradient_threshold,
            "green_dominance": args.green_threshold,
        },
        "results": sorted(results, key=lambda x: float(x.get("noise_score", 0.0)), reverse=True),
    }
    out_json = Path(args.out_json)
    out_json.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    write_markdown(results, Path(args.out_md))
    print(f"audited {len(results)} materials; wrote {out_json}")


if __name__ == "__main__":
    main()
