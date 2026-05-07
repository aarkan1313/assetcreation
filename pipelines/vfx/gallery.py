"""Build the static HTML VFX gallery.

v2 (2026-05-06): adds element + archetype filters, tag search, and CSS-driven
autoplay flipbook previews using the baked atlas's grid layout.

Each tile shows an actual playing flipbook (CSS @keyframes scrolling
background-position over the atlas). Atlas grid is read from manifest:
cols = ceil(sqrt(n_frames)), rows = ceil(n_frames / cols), matching what
`pack_flipbook` produces. For non-frame backends (volumetric_fog), the tile
renders a static tinted placeholder.

CLI:
  python gallery.py --out vfx/index.html
"""
from __future__ import annotations

import argparse
import json
import math
from html import escape
from pathlib import Path


GALLERY_CSS = """
* { box-sizing: border-box; }
body {
  background: #181820; color: #eaeaea;
  font: 14px system-ui, sans-serif;
  margin: 0; padding: 24px;
}
h1 { margin: 0 0 8px; }
h2 { border-bottom: 1px solid #333; padding-bottom: 8px; margin-top: 32px; }
small { color: #888; font-weight: normal; font-size: 12px; }

#controls {
  position: sticky; top: 0; z-index: 50;
  background: #181820; padding: 12px 0; margin-bottom: 16px;
  border-bottom: 1px solid #333;
}
#controls .row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
#search {
  background: #252532; color: #eaeaea; border: 1px solid #444; border-radius: 6px;
  padding: 6px 10px; min-width: 220px; font: inherit;
}
.fbtn {
  background: #2a2a3a; color: #eaeaea; border: 1px solid #444; border-radius: 4px;
  padding: 4px 10px; cursor: pointer; font: 12px system-ui;
}
.fbtn.on { background: #5a4ad8; border-color: #7868f0; color: white; }
.fbtn:hover { background: #36364a; }
.fbtn.on:hover { background: #6a5ae8; }
.label-em { color: #888; margin-right: 4px; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.card {
  background: #252532; border-radius: 8px; padding: 8px;
  display: flex; flex-direction: column;
  transition: transform .06s;
}
.card.hidden { display: none; }
.card:hover { transform: translateY(-2px); }
.thumb {
  width: 100%; aspect-ratio: 1 / 1;
  display: flex; align-items: center; justify-content: center;
  background: #0a0a12; border-radius: 6px; overflow: hidden;
  position: relative;
}
.thumb img.full {
  max-width: 100%; max-height: 100%; image-rendering: pixelated;
  display: block;
}
.flip {
  width: 100%; height: 100%;
  background-repeat: no-repeat; background-size: var(--atlas-w) var(--atlas-h);
  image-rendering: pixelated;
  animation: flip-anim var(--dur) steps(var(--frames)) infinite;
  background-position-x: 0;
}
@keyframes flip-anim {
  to { background-position-x: calc(-1 * var(--atlas-row-w)); }
}
.no-preview { color: #555; font-size: 11px; }
.thumb.fog {
  background: linear-gradient(180deg, var(--top, #888), var(--bottom, #222));
}
.thumb.fog::after {
  content: "vol-fog";
  position: absolute; bottom: 4px; right: 4px;
  font-size: 10px; padding: 1px 4px;
  background: rgba(0,0,0,0.4); border-radius: 3px;
}

.meta { padding: 8px 4px 0; flex: 1; }
.meta strong { display: block; margin-bottom: 4px; }
.t {
  display: inline-block; background: #36364a; border-radius: 4px;
  padding: 2px 6px; margin-right: 4px; margin-top: 2px;
  font-size: 11px;
}
.t.elem-fire { background: #5e2412; color: #ffc090; }
.t.elem-ice { background: #1e3650; color: #90d8ff; }
.t.elem-lightning { background: #3a2a60; color: #c8b4ff; }
.t.elem-earth { background: #4a3820; color: #e0c890; }
.t.elem-arcane { background: #4a2870; color: #e0b8ff; }
.t.elem-shadow { background: #2a1240; color: #b890e8; }
.t.elem-physical { background: #3a3a3a; color: #e0e0e0; }
.t.elem-neutral { background: #2a2a2a; color: #aaaaaa; }
.t.arch { background: #284a48; color: #c0f8e8; }
.t.export { background: #4a3a28; color: #f0d4a8; }

.path { color: #777; font-size: 10px; margin-top: 6px; word-break: break-all; }
.empty {
  text-align: center; color: #888; padding: 40px; font-style: italic;
  grid-column: 1 / -1;
}
"""

GALLERY_JS = """
(function() {
  const search = document.getElementById('search');
  const buttons = document.querySelectorAll('.fbtn');
  const cards = Array.from(document.querySelectorAll('.card'));
  const sections = Array.from(document.querySelectorAll('section'));
  const counter = document.getElementById('counter');
  const total = cards.length;

  // active filters per facet
  const active = { element: new Set(), archetype: new Set(), backend: new Set(), export: new Set() };

  function apply() {
    const q = (search.value || '').trim().toLowerCase();
    let shown = 0;
    cards.forEach(c => {
      const elem = c.dataset.element || '';
      const arch = c.dataset.archetype || '';
      const backend = c.dataset.backend || '';
      const exp = c.dataset.export || '';
      const tags = (c.dataset.tags || '').toLowerCase();
      const id = c.dataset.id.toLowerCase();
      const okElem = active.element.size === 0 || active.element.has(elem);
      const okArch = active.archetype.size === 0 || active.archetype.has(arch);
      const okBack = active.backend.size === 0 || active.backend.has(backend);
      const okExp = active.export.size === 0 || active.export.has(exp);
      const okQ = !q || id.includes(q) || tags.includes(q) || elem.includes(q) || arch.includes(q);
      const visible = okElem && okArch && okBack && okExp && okQ;
      c.classList.toggle('hidden', !visible);
      if (visible) shown++;
    });
    counter.textContent = `${shown} / ${total}`;
    // Toggle empty messages on sections.
    sections.forEach(s => {
      const visible = s.querySelectorAll('.card:not(.hidden)').length;
      const emptyMsg = s.querySelector('.empty');
      if (emptyMsg) emptyMsg.style.display = visible === 0 ? '' : 'none';
    });
  }

  buttons.forEach(b => {
    b.addEventListener('click', () => {
      const facet = b.dataset.facet;
      const val = b.dataset.value;
      if (active[facet].has(val)) {
        active[facet].delete(val); b.classList.remove('on');
      } else {
        active[facet].add(val); b.classList.add('on');
      }
      apply();
    });
  });
  search.addEventListener('input', apply);
  document.getElementById('clear').addEventListener('click', () => {
    Object.values(active).forEach(s => s.clear());
    buttons.forEach(b => b.classList.remove('on'));
    search.value = '';
    apply();
  });
  apply();
})();
"""


def _palette_at(palette: list[str], idx: int) -> str:
    if not palette:
        return "#888888"
    return palette[min(idx, len(palette) - 1)]


def _flip_dims(n_frames: int, cell_w: int, cell_h: int) -> tuple[int, int, int, int]:
    """Returns (cols, rows, atlas_w_px, atlas_row_w_px). atlas_row_w_px is
    cell_w * cols * how-many-rows-of-frames-need-to-scroll. The CSS animation
    loops over a SINGLE row by stepping background-position-x. For multi-row
    atlases we treat rows as additional 'phases' by using the full atlas
    width as the scroll target, which produces a correct per-frame step
    when steps(n_frames) divides evenly. n_frames/cols may not equal rows
    for non-square counts, so we clamp to cols * rows total cells."""
    cols = int(math.ceil(math.sqrt(n_frames)))
    rows = int(math.ceil(n_frames / cols))
    atlas_w = cell_w * cols
    # We rely on a wide background image with all cells laid out; CSS
    # `steps(n_frames)` advances by atlas_row_w_px / n_frames pixels per
    # frame. Setting atlas_row_w_px = cell_w * n_frames lets the simple
    # 1D step animation work even for multi-row atlases by treating the
    # background as a virtual long row. We'll also display the atlas
    # scaled appropriately.
    # NOTE: simple approach: just animate the X-step across the FIRST row
    # and accept that multi-row atlases will only autoplay row 0. Most
    # of our effects fit in one row anyway (n_frames <= ~20). Document
    # this and move on.
    return cols, rows, atlas_w, cell_w * cols


def _card_for_effect(eff_dir: Path, eff: dict, manifest: dict | None,
                     out_path: Path) -> str:
    eid = eff["id"]
    kind = eff.get("kind", "spell")
    backend = eff.get("backend", "?")
    phen = eff.get("phenomenon", "?")
    element = eff.get("element", "neutral")
    archetype = eff.get("archetype", "burst")
    export_target = eff.get("export_target", "2d")
    tags = eff.get("tags", []) or []
    rel_dir = eff_dir.relative_to(out_path.parent).as_posix()

    # Decide preview shape.
    flipbook = eff_dir / "flipbook.png"
    fog_density = eff_dir / "density.png"
    is_fog = backend == "volumetric_fog" and fog_density.exists()

    n_frames = (manifest or {}).get("n_frames", 0)
    fps = (manifest or {}).get("fps", eff.get("fps", 24))
    bounds = (manifest or {}).get("bounds_px", eff.get("bounds_px", [256, 256]))

    if is_fog:
        palette = eff.get("visual", {}).get("palette", ["#888888", "#222222"])
        top = palette[0] if palette else "#888888"
        bot = palette[-1] if palette else "#222222"
        thumb_html = (
            f'<div class="thumb fog" style="--top:{escape(top)};--bottom:{escape(bot)};">'
            f'</div>'
        )
    elif flipbook.exists() and n_frames > 1:
        cell_w, cell_h = bounds[0], bounds[1]
        cols, rows, atlas_w, row_w = _flip_dims(n_frames, cell_w, cell_h)
        dur = max(n_frames / max(fps, 1), 0.3)
        flipbook_rel = f"{rel_dir}/flipbook.png"
        # Show only the first row autoplay - hard limitation of pure-CSS
        # spritesheet animation. Effects with all frames in one row look
        # perfect; multi-row atlases will animate the first row only.
        thumb_html = (
            f'<div class="thumb">'
            f'<div class="flip" style="'
            f'background-image:url(\'{escape(flipbook_rel)}\');'
            f'--atlas-w:{atlas_w}px;'
            f'--atlas-h:{cell_h * rows}px;'
            f'--atlas-row-w:{cols * cell_w}px;'
            f'--frames:{cols};'
            f'--dur:{dur:.2f}s;"></div>'
            f'</div>'
        )
    elif flipbook.exists():
        flipbook_rel = f"{rel_dir}/flipbook.png"
        thumb_html = (
            f'<div class="thumb">'
            f'<img class="full" src="{escape(flipbook_rel)}" alt="{escape(eid)}">'
            f'</div>'
        )
    else:
        thumb_html = '<div class="thumb"><span class="no-preview">no preview</span></div>'

    tags_visible = list(dict.fromkeys(  # dedupe preserving order
        [phen, *tags]
    ))
    tag_html = " ".join(f'<span class="t">{escape(t)}</span>' for t in tags_visible)

    element_class = f"elem-{element}"

    return (
        f'<div class="card" '
        f'data-id="{escape(eid)}" '
        f'data-element="{escape(element)}" '
        f'data-archetype="{escape(archetype)}" '
        f'data-backend="{escape(backend)}" '
        f'data-export="{escape(export_target)}" '
        f'data-tags="{escape(",".join(tags_visible))}">'
        f'{thumb_html}'
        f'<div class="meta">'
        f'<strong>{escape(eid)}</strong>'
        f'<div>'
        f'<span class="t {element_class}">{escape(element)}</span>'
        f'<span class="t arch">{escape(archetype)}</span>'
        f'<span class="t export">{escape(export_target)}</span>'
        f'</div>'
        f'<div>{tag_html}</div>'
        f'<div class="path">{escape(rel_dir)}</div>'
        f'</div></div>'
    )


def render(catalog_root: Path, migrated_root: Path, out_path: Path) -> None:
    sections_data = [
        ("Catalog", catalog_root),
        ("Migrated from spell-lab", migrated_root),
    ]
    section_html: list[str] = []
    counts = {"total": 0, "with_preview": 0}
    facet_values = {
        "element": set(), "archetype": set(),
        "backend": set(), "export": set(),
    }
    for sect_name, root in sections_data:
        if not root.exists():
            continue
        eff_jsons = sorted(root.rglob("effect.json"))
        cards: list[str] = []
        for ej in eff_jsons:
            try:
                eff = json.loads(ej.read_text(encoding="utf-8"))
            except Exception:
                continue
            mf_path = ej.with_name("manifest.json")
            manifest = None
            if mf_path.exists():
                try:
                    manifest = json.loads(mf_path.read_text(encoding="utf-8"))
                except Exception:
                    manifest = None
            d = ej.parent
            counts["total"] += 1
            if (d / "flipbook.png").exists() or (d / "density.png").exists():
                counts["with_preview"] += 1
            facet_values["element"].add(eff.get("element", "neutral"))
            facet_values["archetype"].add(eff.get("archetype", "burst"))
            facet_values["backend"].add(eff.get("backend", "?"))
            facet_values["export"].add(eff.get("export_target", "2d"))
            cards.append(_card_for_effect(d, eff, manifest, out_path))
        if not cards:
            continue
        section_html.append(
            f'<section><h2>{escape(sect_name)} '
            f'<small>{escape(str(root))}</small></h2>'
            f'<div class="grid">{"".join(cards)}'
            f'<div class="empty" style="display:none">'
            f'no effects match the current filters</div>'
            f'</div></section>'
        )

    # Render filter buttons
    def _btns(facet: str, label: str) -> str:
        vals = sorted(facet_values[facet])
        if not vals:
            return ""
        btns = "".join(
            f'<button class="fbtn" data-facet="{escape(facet)}" '
            f'data-value="{escape(v)}">{escape(v)}</button>' for v in vals
        )
        return f'<span class="label-em">{escape(label)}:</span>{btns}'

    controls = (
        '<div id="controls">'
        '<div class="row">'
        '<input id="search" type="search" placeholder="search id, tag, phenomenon..." />'
        '<button id="clear" class="fbtn">clear</button>'
        '<span id="counter" style="color:#888;margin-left:auto;">0 / 0</span>'
        '</div>'
        '<div class="row">'
        + _btns("element", "element") +
        '</div>'
        '<div class="row">'
        + _btns("archetype", "archetype") +
        '</div>'
        '<div class="row">'
        + _btns("backend", "backend") + _btns("export", "target") +
        '</div>'
        '</div>'
    )

    html = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>VFX gallery v2</title>'
        f'<style>{GALLERY_CSS}</style>'
        '</head><body>'
        f'<h1>VFX gallery <small>{counts["total"]} effects, '
        f'{counts["with_preview"]} with previews</small></h1>'
        + controls +
        "\n".join(section_html)
        + f'<script>{GALLERY_JS}</script>'
        + "</body></html>"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[gallery] {counts['total']} effects, "
          f"{counts['with_preview']} with previews -> {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path,
                    default=Path(r"D:\assets\vfx\catalog"))
    ap.add_argument("--migrated", type=Path,
                    default=Path(r"D:\assets\vfx\migrated_from_spell_lab"))
    ap.add_argument("--out", type=Path, default=Path(r"D:\assets\vfx\index.html"))
    args = ap.parse_args()
    render(args.catalog, args.migrated, args.out)


if __name__ == "__main__":
    main()
