"""Build an HTML review shell for a prop kit plan."""
from __future__ import annotations

import argparse
import html
import os
from pathlib import Path

from prop_common import ASSET_ROOT, load_json


def file_url(path_text: str, base_dir: Path) -> str | None:
    path = ASSET_ROOT / path_text
    if not path.exists():
        return None
    return os.path.relpath(path, base_dir).replace("\\", "/")


def card(variant: dict, base_dir: Path) -> str:
    thumb = file_url(f"{variant['library_dir']}/thumbnail.png", base_dir)
    if thumb:
        media = f'<img src="{html.escape(thumb)}" alt="{html.escape(variant["id"])}">'
    else:
        media = f'<div class="placeholder">{html.escape(variant["status"].upper())}</div>'
    tags = " ".join(f"<span>{html.escape(str(t))}</span>" for t in variant.get("placement_tags", [])[:5])
    missing = ", ".join(variant.get("missing_files", []))
    return f"""
    <article class="card {html.escape(variant['status'])}">
      <div class="media">{media}</div>
      <h3>{html.escape(variant['id'])}</h3>
      <p><b>family</b> {html.escape(variant['family'])}</p>
      <p><b>generator</b> {html.escape(str(variant['generator']))}</p>
      <p><b>class</b> {html.escape(variant['render_class'])} / {html.escape(variant['collision'])}</p>
      <p><b>next</b> {html.escape(variant.get('next_action', ''))}</p>
      <p class="missing"><b>missing</b> {html.escape(missing or 'none')}</p>
      <div class="tags">{tags}</div>
    </article>
    """


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    plan = load_json(args.plan)
    out = args.out or (args.plan.parent / "gallery.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    base_dir = out.parent

    cards = "\n".join(card(v, base_dir) for v in plan["variants"])
    issues = plan.get("validation_issues", [])
    issue_html = "<li>None</li>" if not issues else "\n".join(f"<li>{html.escape(i)}</li>" for i in issues)

    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prop Kit Plan - {html.escape(plan['kit'])}</title>
  <style>
    body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; background: #111614; color: #e6eee8; }}
    header {{ padding: 24px 28px; background: #1c2722; border-bottom: 1px solid #33443c; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 28px 28px 12px; font-size: 20px; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }}
    .pill {{ padding: 7px 10px; border: 1px solid #52685f; border-radius: 6px; background: #18201d; }}
    .issues {{ margin: 0 28px; padding: 16px 20px; background: #1b211f; border: 1px solid #38443f; border-radius: 6px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 14px; padding: 0 28px 32px; }}
    .card {{ border: 1px solid #33443c; border-radius: 6px; overflow: hidden; background: #171d1a; }}
    .card.ready {{ border-color: #5da56f; }}
    .card.partial {{ border-color: #b79a57; }}
    .card.missing {{ border-color: #5f6b65; }}
    .media {{ aspect-ratio: 1 / 1; background: #0b0f0d; display: grid; place-items: center; }}
    .media img {{ width: 100%; height: 100%; object-fit: cover; }}
    .placeholder {{ color: #81918a; letter-spacing: 0; font-weight: 700; }}
    h3 {{ margin: 12px 12px 8px; font-size: 15px; }}
    p {{ margin: 6px 12px; color: #bdc9c1; font-size: 13px; line-height: 1.35; }}
    .missing {{ color: #d2c5a3; }}
    .tags {{ display: flex; flex-wrap: wrap; gap: 5px; padding: 10px 12px 14px; }}
    .tags span {{ font-size: 12px; padding: 3px 6px; border-radius: 5px; background: #24332d; color: #cdd8d1; }}
    code {{ color: #bce0c4; }}
  </style>
</head>
<body>
  <header>
    <h1>Prop Kit Plan: {html.escape(plan['kit'])}</h1>
    <div><code>{html.escape(str(args.plan))}</code></div>
    <div class="summary">
      <div class="pill">families: {plan['summary']['families']}</div>
      <div class="pill">variants: {plan['summary']['variants']}</div>
      <div class="pill">ready: {plan['summary']['ready']}</div>
      <div class="pill">partial: {plan['summary']['partial']}</div>
      <div class="pill">missing: {plan['summary']['missing']}</div>
      <div class="pill">blender: {plan['summary']['blender_tasks']}</div>
      <div class="pill">decals: {plan['summary']['decal_tasks']}</div>
    </div>
  </header>
  <h2>Validation</h2>
  <ul class="issues">{issue_html}</ul>
  <h2>Variants</h2>
  <main class="grid">
    {cards}
  </main>
</body>
</html>
"""
    out.write_text(doc, encoding="utf-8")
    print(f"gallery: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

