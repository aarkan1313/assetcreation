"""Score shader candidates against curated visual references.

This is not a magic aesthetic judge. It is a cheap, deterministic layer for
answering "does this candidate live near the visual style we want?" Use it
after the normal batch scorer has removed broken or boring candidates.

Three scoring backends, additive, A/B-comparable (per brief #05):

  - ``edge_mse`` (DEFAULT): the original heuristic — colour histograms,
    luma/chroma stats, edge density. Pure numpy/PIL, runs anywhere.
  - ``dreamsim``: DreamSim perceptual distance. Requires `pip install dreamsim`
    and torch. Recommended for "does this look like the reference style"
    questions where pixel-level alignment matters less than semantic shape.
  - ``lpips``: classic learned-perceptual-image-patch-similarity. Requires
    `pip install lpips` and torch. Lower-level than DreamSim; complementary.
  - ``all``: compute every scorer and emit per-candidate metrics for each.
    Use this to compare grading orderings before promoting a scorer to
    default. **Edge-MSE remains the default until a manual A/B prefers swap.**

Heavy scorers (dreamsim, lpips, all) need torch + dreamsim + lpips +
modern accelerate/peft. Run from the dedicated **art_lab venv** (NOT the
Puppeteer venv — Puppeteer is pinned to accelerate==0.28.0 which is
incompatible with modern peft/dreamsim):

    D:\\assets\\art_lab\\.venv\\Scripts\\python.exe art_lab\\tools\\shader_reference_score.py \\
        --batch-dir <batch> --reference-set <ref> --scorer all

The art_lab venv was built 2026-05-07 with:
    py -3.11 -m venv D:/assets/art_lab/.venv
    .venv\\Scripts\\python -m pip install "numpy<2" pillow torch==2.7.0 \\
        torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cu128
    .venv\\Scripts\\python -m pip install dreamsim lpips
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

LAB_ROOT = Path(r"D:\assets\art_lab")
REFERENCE_ROOT = LAB_ROOT / "shaders" / "reference_sets"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def image_paths(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXTS)


def feature(path: Path) -> np.ndarray:
    img = Image.open(path).convert("RGBA").resize((96, 96), Image.Resampling.LANCZOS)
    arr = np.asarray(img).astype(np.float32) / 255.0
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    mask_weight = np.maximum(alpha, 0.05)
    luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    chroma = np.std(rgb, axis=2)
    gx = np.abs(np.diff(luma, axis=1, prepend=luma[:, :1]))
    gy = np.abs(np.diff(luma, axis=0, prepend=luma[:1, :]))
    edge = np.sqrt(gx * gx + gy * gy)

    values: list[float] = [
        float(np.mean(alpha > 0.04)),
        float(np.average(luma, weights=mask_weight)),
        float(np.sqrt(np.average((luma - np.average(luma, weights=mask_weight)) ** 2, weights=mask_weight))),
        float(np.average(chroma, weights=mask_weight)),
        float(np.average(edge, weights=mask_weight)),
        float(np.percentile(luma, 95) - np.percentile(luma, 5)),
    ]
    for channel in range(3):
        hist, _ = np.histogram(rgb[..., channel], bins=10, range=(0.0, 1.0), weights=mask_weight)
        hist = hist.astype(np.float32)
        hist /= max(float(hist.sum()), 1e-6)
        values.extend(hist.tolist())
    return np.array(values, dtype=np.float32)


def candidate_preview(candidate_dir: Path) -> Path | None:
    for name in ("preview_godot.png", "preview.png", "flipbook_godot.png", "flipbook.png"):
        path = candidate_dir / name
        if path.exists():
            return path
    return None


def resolve_reference_dir(value: str) -> Path:
    path = Path(value)
    if path.exists():
        return path
    return REFERENCE_ROOT / value


# ---------------------------------------------------------------------------
# Optional perceptual scorer backends (lazy-imported so edge_mse keeps working
# without torch installed). Per brief #05 — additive, A/B-comparable.
# ---------------------------------------------------------------------------

_DREAMSIM_MODEL = None
_LPIPS_MODEL = None
_TORCH = None


def _lazy_torch():
    global _TORCH
    if _TORCH is None:
        import torch  # type: ignore
        _TORCH = torch
    return _TORCH


def _lazy_dreamsim():
    global _DREAMSIM_MODEL
    if _DREAMSIM_MODEL is None:
        torch = _lazy_torch()
        from dreamsim import dreamsim  # type: ignore
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model, preprocess = dreamsim(pretrained=True, device=device)
        _DREAMSIM_MODEL = (model, preprocess, device)
    return _DREAMSIM_MODEL


def _lazy_lpips():
    global _LPIPS_MODEL
    if _LPIPS_MODEL is None:
        torch = _lazy_torch()
        import lpips  # type: ignore
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # 'alex' is the standard LPIPS backbone; faster than 'vgg', similar quality
        model = lpips.LPIPS(net="alex").to(device)
        _LPIPS_MODEL = (model, device)
    return _LPIPS_MODEL


def _load_pil_rgb(path: Path):
    """Load a PNG as PIL RGB (drops alpha — perceptual scorers don't take it)."""
    return Image.open(path).convert("RGB")


def dreamsim_distance(candidate_path: Path, reference_paths: list[Path]) -> tuple[float, Path, float]:
    """DreamSim distance to nearest reference. Returns (score, nearest, distance).

    Score is 1 - mean_distance, clamped to [0, 1] so larger == more similar
    (matches edge_mse's polarity). Distance is the raw nearest-reference
    DreamSim metric for diagnostics.
    """
    torch = _lazy_torch()
    model, preprocess, device = _lazy_dreamsim()
    cand = preprocess(_load_pil_rgb(candidate_path)).to(device)
    best_dist = float("inf")
    best_path: Path | None = None
    with torch.no_grad():
        for ref_path in reference_paths:
            ref = preprocess(_load_pil_rgb(ref_path)).to(device)
            dist = float(model(cand, ref).item())
            if dist < best_dist:
                best_dist = dist
                best_path = ref_path
    score = max(0.0, 1.0 - best_dist)
    return score, best_path or reference_paths[0], best_dist


def lpips_distance(candidate_path: Path, reference_paths: list[Path]) -> tuple[float, Path, float]:
    """LPIPS distance to nearest reference. Returns (score, nearest, distance).

    Score is 1 - mean_distance, clamped to [0, 1]. LPIPS values typically
    sit in [0, 1] but can exceed 1 for very-different images, hence clamp.
    """
    torch = _lazy_torch()
    model, device = _lazy_lpips()
    # LPIPS expects [-1, 1] tensor at 64x64 minimum; we resize to 256 for stability.
    def _to_tensor(p: Path):
        img = _load_pil_rgb(p).resize((256, 256), Image.Resampling.LANCZOS)
        arr = np.asarray(img).astype(np.float32) / 127.5 - 1.0
        t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)
        return t
    cand_t = _to_tensor(candidate_path)
    best_dist = float("inf")
    best_path: Path | None = None
    with torch.no_grad():
        for ref_path in reference_paths:
            d = float(model(cand_t, _to_tensor(ref_path)).item())
            if d < best_dist:
                best_dist = d
                best_path = ref_path
    score = max(0.0, min(1.0, 1.0 - best_dist))
    return score, best_path or reference_paths[0], best_dist


def similarity(candidate: np.ndarray, references: list[tuple[Path, np.ndarray]]) -> tuple[float, Path, float]:
    best_path = references[0][0]
    best_distance = math.inf
    for path, ref in references:
        dist = float(np.linalg.norm(candidate - ref))
        if dist < best_distance:
            best_distance = dist
            best_path = path
    score = 100.0 * math.exp(-best_distance * 2.2)
    return round(score, 2), best_path, round(best_distance, 5)


def load_rows(batch_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = batch_dir / "batch_summary.json"
    if not path.exists():
        raise SystemExit(f"missing batch_summary.json: {batch_dir}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, data.get("rows", [])


def update_request(candidate_dir: Path, payload: dict[str, Any]) -> None:
    path = candidate_dir / "request.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("reference_review", {}).update(payload)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_markdown(batch_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        f"# Reference Score - {result['batch']}",
        "",
        f"Reference set: `{result['reference_set']}`",
        "",
        "| Rank | Candidate | Base | Ref | Nearest reference |",
        "| ---: | --- | ---: | ---: | --- |",
    ]
    for i, row in enumerate(result["rows"], 1):
        lines.append(
            f"| {i} | `{row['id']}` | {row['base_score']:.2f} | {row['reference_score']:.2f} | `{row['nearest_reference']}` |"
        )
    (batch_dir / "reference_review.md").write_text("\n".join(lines), encoding="utf-8")


SCORERS = ("edge_mse", "dreamsim", "lpips", "all")


def _score_candidate(scorer: str, preview: Path, ref_paths: list[Path],
                     ref_features: list[tuple[Path, np.ndarray]] | None
                     ) -> dict[str, tuple[float, Path, float]]:
    """Return {scorer_name: (score, nearest, distance)}. For ``all`` runs every
    available backend; ``edge_mse`` always present."""
    out: dict[str, tuple[float, Path, float]] = {}
    if scorer in ("edge_mse", "all"):
        assert ref_features is not None
        out["edge_mse"] = similarity(feature(preview), ref_features)
    if scorer in ("dreamsim", "all"):
        out["dreamsim"] = dreamsim_distance(preview, ref_paths)
    if scorer in ("lpips", "all"):
        out["lpips"] = lpips_distance(preview, ref_paths)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-dir", type=Path, required=True)
    ap.add_argument("--reference-set", required=True,
                    help="Reference set name under shaders/reference_sets or an explicit directory")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--update-summary", action="store_true")
    ap.add_argument("--scorer", choices=SCORERS, default="edge_mse",
                    help="Scoring backend (default edge_mse — original behavior). "
                         "dreamsim/lpips need torch + the matching pip package; run from "
                         "the Puppeteer venv if you haven't built one for art_lab. "
                         "Use 'all' to compute every metric on the same batch for A/B "
                         "comparison without changing the default ranking key.")
    ap.add_argument("--rank-by", default="",
                    help="Which scorer's score to sort by when --scorer all. "
                         "Defaults to the first scorer that ran. Has no effect "
                         "for non-'all' runs.")
    args = ap.parse_args()

    ref_dir = resolve_reference_dir(args.reference_set)
    refs = image_paths(ref_dir)
    if not refs:
        raise SystemExit(f"no reference images found in {ref_dir}")
    # Edge-MSE features are precomputed once per reference set; perceptual
    # scorers re-encode references each candidate (small N, OK).
    ref_features = [(p, feature(p)) for p in refs] if args.scorer in ("edge_mse", "all") else None

    summary, rows = load_rows(args.batch_dir)
    scored = []
    for row in rows:
        candidate_dir = args.batch_dir / row["id"]
        preview = candidate_preview(candidate_dir)
        if not preview:
            continue
        per_scorer = _score_candidate(args.scorer, preview, refs, ref_features)

        # The "primary" ranking key: edge_mse for default runs; for 'all' runs
        # the user picks via --rank-by, falling back to first scorer in SCORERS
        # that was computed.
        if args.scorer == "all":
            rank_key = args.rank_by or next(s for s in SCORERS if s != "all" and s in per_scorer)
        else:
            rank_key = args.scorer
        ref_score, nearest, distance = per_scorer[rank_key]

        payload = {
            "reference_set": str(ref_dir),
            "scorer": args.scorer,
            "rank_by": rank_key,
            "reference_score": ref_score,
            "nearest_reference": str(nearest),
            "reference_distance": distance,
            "all_scorers": {k: {"score": v[0], "nearest": str(v[1]), "distance": v[2]}
                            for k, v in per_scorer.items()},
            "created": datetime.now(timezone.utc).isoformat(),
        }
        row["reference_review"] = payload
        update_request(candidate_dir, payload)
        scored.append({
            "id": row["id"],
            "template": row.get("template", ""),
            "role": row.get("role", ""),
            "base_score": float(row.get("review", {}).get("score", 0.0)),
            "reference_score": ref_score,
            "nearest_reference": str(nearest.relative_to(ref_dir) if nearest.is_relative_to(ref_dir) else nearest),
            "reference_distance": distance,
            "preview": str(preview.relative_to(args.batch_dir)),
            "all_scorers": payload["all_scorers"],
        })

    scored.sort(key=lambda r: (r["reference_score"], r["base_score"]), reverse=True)
    # Resolve the actual rank_by used (mirrors the per-row branch above so the
    # summary record matches what was used to sort `scored`).
    if args.scorer == "all":
        resolved_rank_by = args.rank_by or next(s for s in SCORERS if s != "all")
    else:
        resolved_rank_by = args.scorer
    result = {
        "batch": args.batch_dir.name,
        "reference_set": str(ref_dir),
        "reference_count": len(refs),
        "scorer": args.scorer,
        "rank_by": resolved_rank_by,
        "created": datetime.now(timezone.utc).isoformat(),
        "rows": scored[:args.top],
    }
    (args.batch_dir / "reference_scores.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_markdown(args.batch_dir, result)

    if args.update_summary:
        summary["reference_review"] = {
            "reference_set": str(ref_dir),
            "scorer": args.scorer,
            "created": result["created"],
            "top": result["rows"],
        }
        (args.batch_dir / "batch_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"wrote {args.batch_dir / 'reference_scores.json'}  scorer={args.scorer}")
    print(f"wrote {args.batch_dir / 'reference_review.md'}")


if __name__ == "__main__":
    main()
