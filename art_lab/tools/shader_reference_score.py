"""Score shader candidates against curated visual references.

This is not a magic aesthetic judge. It is a cheap, deterministic layer for
answering "does this candidate live near the visual style we want?" Use it
after the normal batch scorer has removed broken or boring candidates.
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-dir", type=Path, required=True)
    ap.add_argument("--reference-set", required=True,
                    help="Reference set name under shaders/reference_sets or an explicit directory")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--update-summary", action="store_true")
    args = ap.parse_args()

    ref_dir = resolve_reference_dir(args.reference_set)
    refs = image_paths(ref_dir)
    if not refs:
        raise SystemExit(f"no reference images found in {ref_dir}")
    ref_features = [(p, feature(p)) for p in refs]

    summary, rows = load_rows(args.batch_dir)
    scored = []
    for row in rows:
        candidate_dir = args.batch_dir / row["id"]
        preview = candidate_preview(candidate_dir)
        if not preview:
            continue
        ref_score, nearest, distance = similarity(feature(preview), ref_features)
        payload = {
            "reference_set": str(ref_dir),
            "reference_score": ref_score,
            "nearest_reference": str(nearest),
            "reference_distance": distance,
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
        })

    scored.sort(key=lambda r: (r["reference_score"], r["base_score"]), reverse=True)
    result = {
        "batch": args.batch_dir.name,
        "reference_set": str(ref_dir),
        "reference_count": len(refs),
        "created": datetime.now(timezone.utc).isoformat(),
        "rows": scored[:args.top],
    }
    (args.batch_dir / "reference_scores.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_markdown(args.batch_dir, result)

    if args.update_summary:
        summary["reference_review"] = {
            "reference_set": str(ref_dir),
            "created": result["created"],
            "top": result["rows"],
        }
        (args.batch_dir / "batch_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"wrote {args.batch_dir / 'reference_scores.json'}")
    print(f"wrote {args.batch_dir / 'reference_review.md'}")


if __name__ == "__main__":
    main()
