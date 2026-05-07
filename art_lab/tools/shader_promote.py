"""Promote top shader batch candidates into a human review queue.

The batch explorer is allowed to generate lots of mediocre output. This tool
keeps the review surface small: it copies only high-scoring, optionally diverse
candidates into art_lab/shaders/review_queues/<queue_id>/ and writes a compact
gallery plus mutation commands.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

LAB_ROOT = Path(r"D:\assets\art_lab")
BATCHES_DIR = LAB_ROOT / "shaders" / "batches"
REVIEW_DIR = LAB_ROOT / "shaders" / "review_queues"


def image_feature(path: Path) -> np.ndarray:
    img = Image.open(path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
    arr = np.asarray(img).astype(np.float32) / 255.0
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    bins = []
    for channel in range(3):
        hist, _ = np.histogram(rgb[..., channel], bins=8, range=(0.0, 1.0), weights=np.maximum(alpha, 0.05))
        hist = hist.astype(np.float32)
        hist /= max(float(hist.sum()), 1e-6)
        bins.extend(hist.tolist())
    gx = np.abs(np.diff(luma, axis=1, prepend=luma[:, :1]))
    gy = np.abs(np.diff(luma, axis=0, prepend=luma[:1, :]))
    extra = [
        float(np.mean(alpha > 0.04)),
        float(np.mean(luma)),
        float(np.std(luma)),
        float(np.mean(np.sqrt(gx * gx + gy * gy))),
    ]
    return np.array(bins + extra, dtype=np.float32)


def candidate_image(candidate_dir: Path) -> Path | None:
    for name in ("flipbook_godot.png", "flipbook.png", "preview_godot.png", "preview.png"):
        path = candidate_dir / name
        if path.exists():
            return path
    return None


def load_batch(batch_dir: Path) -> list[dict[str, Any]]:
    summary_path = batch_dir / "batch_summary.json"
    if not summary_path.exists():
        raise SystemExit(f"missing batch_summary.json: {batch_dir}")
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = data.get("rows", [])
    for row in rows:
        row["source_batch"] = batch_dir.name
        row["source_batch_dir"] = str(batch_dir)
        row["candidate_dir"] = str(batch_dir / row["id"])
    return rows


def newest_batches(count: int) -> list[Path]:
    if not BATCHES_DIR.exists():
        return []
    batches = [p for p in BATCHES_DIR.iterdir() if (p / "batch_summary.json").exists()]
    return sorted(batches, key=lambda p: p.stat().st_mtime, reverse=True)[:count]


def grade_allowed(row: dict[str, Any], grades: set[str], min_score: float) -> bool:
    review = row.get("review", {})
    return review.get("grade") in grades and float(review.get("score", 0.0)) >= min_score


def diverse_select(rows: list[dict[str, Any]], max_count: int, distance: float) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_features: list[np.ndarray] = []
    for row in rows:
        cand_dir = Path(row["candidate_dir"])
        image_path = candidate_image(cand_dir)
        if not image_path:
            continue
        feature = image_feature(image_path)
        if selected_features:
            min_dist = min(float(np.linalg.norm(feature - other)) for other in selected_features)
        else:
            min_dist = math.inf
        if min_dist >= distance or len(selected) < max(2, max_count // 4):
            row["diversity_distance"] = None if math.isinf(min_dist) else round(min_dist, 4)
            selected.append(row)
            selected_features.append(feature)
        if len(selected) >= max_count:
            break
    return selected


def copy_candidate(row: dict[str, Any], queue_dir: Path) -> dict[str, Any]:
    source = Path(row["candidate_dir"])
    dest = queue_dir / row["id"]
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)
    image_path = candidate_image(dest)
    request_path = dest / "request.json"
    mutation_command = (
        f'python "D:\\assets\\art_lab\\tools\\shader_batch_review.py" '
        f'--batch-id mutate_{row["id"]} --count 24 --frames 8 --size 256 '
        f'--parent-request "{request_path}" --mutation-strength 0.12'
    )
    return {
        "id": row["id"],
        "source_batch": row["source_batch"],
        "score": row["review"]["score"],
        "grade": row["review"]["grade"],
        "template": row["template"],
        "role": row["role"],
        "relative_dir": row["id"],
        "preview": str(image_path.relative_to(queue_dir)) if image_path else "",
        "request": str(request_path.relative_to(queue_dir)),
        "mutation_command": mutation_command,
        "metrics": row["review"].get("metrics", {}),
        "hints": row["review"].get("hints", []),
        "diversity_distance": row.get("diversity_distance"),
    }


def write_gallery(queue_dir: Path, manifest: dict[str, Any]) -> None:
    cards = []
    for item in manifest["selected"]:
        hints = "".join(f"<li>{html.escape(h)}</li>" for h in item.get("hints", []))
        command = html.escape(item["mutation_command"])
        metrics = item.get("metrics", {})
        cards.append(f"""
        <article class="card {html.escape(item['grade'])}">
          <a class="thumb" href="{html.escape(item['preview'])}"><img src="{html.escape(item['preview'])}" loading="lazy"></a>
          <div class="body">
            <h2>{html.escape(item['id'])}</h2>
            <div class="meta">
              <span>{html.escape(item['template'])}</span>
              <span>{html.escape(item['role'])}</span>
              <strong>{float(item['score']):.2f}</strong>
              <span>{html.escape(item['grade'])}</span>
            </div>
            <div class="metrics">
              cov {float(metrics.get('coverage', 0.0)):.3f} |
              motion {float(metrics.get('motion', 0.0)):.3f} |
              contrast {float(metrics.get('contrast', 0.0)):.3f} |
              edge {float(metrics.get('edge_energy', 0.0)):.3f}
            </div>
            <ul>{hints}</ul>
            <details><summary>mutate</summary><pre>{command}</pre></details>
          </div>
        </article>
        """)
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shader Review Queue</title>
  <style>
    :root {{ color-scheme: dark; font-family: Segoe UI, system-ui, sans-serif; background:#0b0d12; color:#e6edf7; }}
    body {{ margin:0; padding:24px; }}
    header {{ margin-bottom:18px; }}
    h1 {{ margin:0 0 4px; font-size:24px; }}
    .sub {{ color:#94a3b8; font-size:13px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(360px, 1fr)); gap:14px; }}
    .card {{ background:#111722; border:1px solid #263246; border-radius:8px; overflow:hidden; }}
    .card.keep {{ border-color:#63e6be; }}
    .card.review {{ border-color:#ffd166; }}
    .thumb {{ display:block; background:#05070a; min-height:180px; }}
    img {{ max-width:100%; display:block; margin:auto; }}
    .body {{ padding:12px; }}
    h2 {{ font-size:15px; margin:0 0 8px; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:6px; }}
    .meta span, .meta strong {{ background:#1c2635; border-radius:999px; padding:3px 8px; font-size:12px; }}
    .meta strong {{ color:#111722; background:#e6edf7; }}
    .metrics, li {{ color:#cbd5e1; font-size:12px; line-height:1.45; }}
    pre {{ white-space:pre-wrap; overflow:auto; background:#080b10; color:#d8dee9; padding:8px; border-radius:6px; }}
    summary {{ color:#9ab7ff; cursor:pointer; }}
  </style>
</head>
<body>
  <header>
    <h1>Shader Review Queue</h1>
    <div class="sub">{html.escape(manifest['queue_id'])} | {len(manifest['selected'])} candidates | generated {html.escape(manifest['created'])}</div>
  </header>
  <section class="grid">{''.join(cards)}</section>
</body>
</html>
"""
    (queue_dir / "index.html").write_text(html_text, encoding="utf-8")


def write_review_md(queue_dir: Path, manifest: dict[str, Any]) -> None:
    lines = [
        f"# Shader Review Queue - {manifest['queue_id']}",
        "",
        "This queue is intentionally small. It should contain only candidates worth human inspection or local mutation.",
        "",
    ]
    for item in manifest["selected"]:
        lines.extend([
            f"## {item['id']} - {float(item['score']):.2f} ({item['grade']})",
            "",
            f"- Source batch: `{item['source_batch']}`",
            f"- Template: `{item['template']}`",
            f"- Role: `{item['role']}`",
            f"- Preview: `{item['preview']}`",
            f"- Request: `{item['request']}`",
            f"- Mutate: `{item['mutation_command']}`",
            "",
        ])
    (queue_dir / "review.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch_dirs", nargs="*", type=Path, help="Batch directories. Omit with --latest.")
    ap.add_argument("--latest", type=int, default=0, help="Use N newest batches")
    ap.add_argument("--queue-id", help="Output queue id")
    ap.add_argument("--min-score", type=float, default=80.0)
    ap.add_argument("--grades", default="keep,review", help="Comma-separated grades")
    ap.add_argument("--max-count", type=int, default=24)
    ap.add_argument("--diversity-distance", type=float, default=0.22,
                    help="Minimum feature distance between selected previews; 0 disables diversity filtering")
    args = ap.parse_args()

    batch_dirs = list(args.batch_dirs)
    if args.latest:
        batch_dirs.extend(newest_batches(args.latest))
    if not batch_dirs:
        raise SystemExit("provide batch_dirs or --latest N")

    rows: list[dict[str, Any]] = []
    for batch_dir in batch_dirs:
        rows.extend(load_batch(batch_dir))
    grades = {g.strip() for g in args.grades.split(",") if g.strip()}
    rows = [r for r in rows if grade_allowed(r, grades, args.min_score)]
    rows.sort(key=lambda r: float(r["review"].get("score", 0.0)), reverse=True)

    if args.diversity_distance > 0:
        selected_rows = diverse_select(rows, args.max_count, args.diversity_distance)
    else:
        selected_rows = rows[:args.max_count]

    queue_id = args.queue_id or datetime.now().strftime("review_%Y%m%d_%H%M%S")
    queue_dir = REVIEW_DIR / queue_id
    queue_dir.mkdir(parents=True, exist_ok=True)

    selected = [copy_candidate(row, queue_dir) for row in selected_rows]
    manifest = {
        "queue_id": queue_id,
        "created": datetime.now(timezone.utc).isoformat(),
        "source_batches": [str(p) for p in batch_dirs],
        "min_score": args.min_score,
        "grades": sorted(grades),
        "diversity_distance": args.diversity_distance,
        "selected": selected,
        "omitted_after_filter": max(0, len(rows) - len(selected_rows)),
    }
    (queue_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_gallery(queue_dir, manifest)
    write_review_md(queue_dir, manifest)
    print(f"wrote {queue_dir}")
    print(f"gallery: {queue_dir / 'index.html'}")


if __name__ == "__main__":
    main()
