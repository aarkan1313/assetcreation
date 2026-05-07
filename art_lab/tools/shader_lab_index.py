"""Build a static index for shader batches, review queues, and references."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

LAB_ROOT = Path(r"D:\assets\art_lab")
SHADER_ROOT = LAB_ROOT / "shaders"
BATCHES_DIR = SHADER_ROOT / "batches"
REVIEW_DIR = SHADER_ROOT / "review_queues"
REFERENCE_DIR = SHADER_ROOT / "reference_sets"


def rel(path: Path) -> str:
    return path.relative_to(SHADER_ROOT).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def batch_rows(limit: int) -> str:
    rows = []
    batches = [p for p in BATCHES_DIR.glob("*") if (p / "batch_summary.json").exists()]
    batches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for batch in batches[:limit]:
        summary = read_json(batch / "batch_summary.json")
        top = (summary.get("rows") or [{}])[0]
        top_score = top.get("review", {}).get("score", "")
        top_grade = top.get("review", {}).get("grade", "")
        ref = summary.get("reference_review", {}).get("reference_set", "")
        rows.append(f"""
        <tr>
          <td><a href="{html.escape(rel(batch / 'gallery.html'))}">{html.escape(batch.name)}</a></td>
          <td>{int(summary.get('count', 0))}</td>
          <td>{html.escape(str(top_score))}</td>
          <td>{html.escape(str(top_grade))}</td>
          <td>{html.escape(Path(ref).name if ref else '')}</td>
          <td><a href="{html.escape(rel(batch / 'llm_review.md'))}">llm</a></td>
        </tr>
        """)
    return "\n".join(rows)


def queue_cards(limit: int) -> str:
    cards = []
    queues = [p for p in REVIEW_DIR.glob("*") if (p / "manifest.json").exists()]
    queues.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for queue in queues[:limit]:
        manifest = read_json(queue / "manifest.json")
        selected = manifest.get("selected", [])
        preview = selected[0].get("preview", "") if selected else ""
        img = f'<img src="{html.escape(rel(queue / preview))}" loading="lazy">' if preview else ""
        cards.append(f"""
        <article class="card">
          <a class="thumb" href="{html.escape(rel(queue / 'index.html'))}">{img}</a>
          <h3>{html.escape(queue.name)}</h3>
          <p>{len(selected)} promoted candidates</p>
          <a href="{html.escape(rel(queue / 'review.md'))}">review.md</a>
        </article>
        """)
    return "\n".join(cards)


def reference_list() -> str:
    items = []
    if REFERENCE_DIR.exists():
        for ref_dir in sorted(p for p in REFERENCE_DIR.iterdir() if p.is_dir()):
            count = len([p for p in ref_dir.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}])
            items.append(f"<li><code>{html.escape(ref_dir.name)}</code> - {count} images</li>")
    return "\n".join(items)


def template_list() -> str:
    items = []
    for path in sorted((SHADER_ROOT / "templates").glob("*.gdshader")):
        items.append(f'<li><a href="{html.escape(rel(path))}">{html.escape(path.name)}</a></li>')
    return "\n".join(items)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-limit", type=int, default=20)
    ap.add_argument("--queue-limit", type=int, default=12)
    args = ap.parse_args()

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shader Lab Index</title>
  <style>
    :root {{ color-scheme: dark; font-family: Segoe UI, system-ui, sans-serif; background:#0b0d12; color:#e6edf7; }}
    body {{ margin:0; padding:24px; }}
    h1 {{ margin:0 0 18px; }}
    h2 {{ margin:28px 0 10px; font-size:18px; }}
    table {{ border-collapse:collapse; width:100%; background:#111722; border:1px solid #263246; }}
    th, td {{ padding:8px 10px; border-bottom:1px solid #263246; text-align:left; font-size:13px; }}
    th {{ color:#94a3b8; }}
    a {{ color:#9ab7ff; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:14px; }}
    .card {{ background:#111722; border:1px solid #263246; border-radius:8px; padding:12px; }}
    .thumb {{ display:block; min-height:120px; background:#05070a; margin:-12px -12px 10px; border-radius:8px 8px 0 0; overflow:hidden; }}
    img {{ width:100%; display:block; }}
    code {{ color:#ffd166; }}
    li {{ margin:4px 0; }}
  </style>
</head>
<body>
  <h1>Shader Lab Index</h1>
  <h2>Review Queues</h2>
  <section class="grid">{queue_cards(args.queue_limit)}</section>
  <h2>Batches</h2>
  <table>
    <thead><tr><th>Batch</th><th>Count</th><th>Top Score</th><th>Top Grade</th><th>Reference</th><th>Packet</th></tr></thead>
    <tbody>{batch_rows(args.batch_limit)}</tbody>
  </table>
  <h2>Reference Sets</h2>
  <ul>{reference_list()}</ul>
  <h2>Templates</h2>
  <ul>{template_list()}</ul>
  <h2>Operator Files</h2>
  <ul>
    <li><a href="prompts/llm_shader_operator.md">LLM shader operator prompt</a></li>
    <li><a href="../legacy/FOUND_OLD_SHADER_WORKFLOW.md">Recovered Shader Cauldron notes</a></li>
    <li><a href="../legacy/shader-cauldron-v6.html">Recovered Shader Cauldron HTML</a></li>
  </ul>
</body>
</html>
"""
    out = SHADER_ROOT / "index.html"
    out.write_text(html_text, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
