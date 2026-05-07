"""Audio gallery — static HTML browser of the SFX + ambience catalogues.

Same shape as `vfx/index.html` and `pipelines/ui/icons/`'s gallery: one
self-contained `audio/gallery.html` you can double-click to open. No build
step, no JS framework.

Reads:
  audio/sfx_manifest.json                 — 39 sounds × 1-4 variants each
  audio/ambience/ambience_summary.json    — 10 biomes × 4-layer stems
  audio/sfx/<id>_v<N>_qa/waveform.png     — pre-rendered by audio_qa.py
  audio/sfx/<id>_v<N>_qa/spectrogram.png  — same
  audio/sfx/<id>_v<N>_qa/qa.json          — RMS, peak, click count, etc.
  audio/ambience/<biome>/<stem>.cue.json  — provenance per ambience stem

Writes:
  audio/gallery.html                      — single-file static gallery

Features:
  - Tabbed view: SFX (39) | Ambience (10 biomes) | All variants (112+)
  - Per-row inline <audio controls preload="none"> player
  - Filter box (live, debounced; matches id, tags, category, biome)
  - Sortable columns (id / category / RMS / peak / duration)
  - Per-row mini waveform thumb + click-to-zoom spectrogram modal
  - Per-row provenance (backend, prompt, seed, model) from cue.json
  - Per-biome reverb/Poisson summary row
  - LUFS measurement column (true LUFS where >=400 ms; RMS proxy otherwise)
  - "Open" button -> file:// link to the WAV (Windows file association)
  - Total file size + total duration in the header

Asset paths in the HTML are written **relative to audio/gallery.html**, so
the gallery survives moving the audio/ tree as long as it stays
self-contained.

CLI:
  python pipelines/audio/gallery.py
  python pipelines/audio/gallery.py --out D:/tmp/audio_gallery.html
  python pipelines/audio/gallery.py --no-ambience      # SFX-only
"""
from __future__ import annotations

import argparse
import html
import json
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ASSETS = Path(r"D:\assets")
SFX_MANIFEST = ASSETS / "audio" / "sfx_manifest.json"
AMBIENCE_SUMMARY = ASSETS / "audio" / "ambience" / "ambience_summary.json"
DEFAULT_OUT = ASSETS / "audio" / "gallery.html"


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def file_size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


def wav_duration(p: Path) -> float:
    try:
        with wave.open(str(p), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (OSError, wave.Error):
        return 0.0


def relpath(p: Path, base: Path) -> str:
    """`p` and `base` may not share a common drive on Windows when symlinks
    are involved; fall back to absolute file:// URI."""
    try:
        return p.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return p.as_uri()


def fmt_duration(s: float) -> str:
    if s < 60:
        return f"{s:.2f}s"
    m, sec = divmod(s, 60)
    return f"{int(m)}m{sec:04.1f}s"


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n/1024:.1f} KB"
    return f"{n/1024**2:.1f} MB"


def collect_sfx_rows(sfx_manifest: dict, gallery_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for entry in sfx_manifest.get("sounds", []):
        sid = entry["id"]
        cue = entry.get("cue", {}) or {}
        category = entry.get("category", cue.get("category", "sfx"))
        tags = cue.get("tags") or entry.get("tags") or []
        target_rms = cue.get("target_rms_db")
        backend = cue.get("backend", "synth_sfx")
        notes = cue.get("notes", "")
        for v_idx, wav_rel in enumerate(entry.get("variants", [])):
            wav_path = ASSETS / wav_rel
            qa_dir = wav_path.parent / f"{wav_path.stem}_qa"
            qa_json = qa_dir / "qa.json"
            qa = load_json(qa_json, {}) or {}
            rms_in = rms_out = peak_in = peak_out = None
            duration = qa.get("duration_s")
            click_estimate = qa.get("click_count_estimate")
            clipped = qa.get("clipped")
            # Cue may also carry a per-variant processing dict
            proc_list = cue.get("processing", []) or []
            proc = next((p for p in proc_list if p.get("variant") == v_idx), {})
            rms_out = proc.get("rms_dbfs_out", qa.get("rms_dbfs_out"))
            peak_out = proc.get("peak_dbfs_out", qa.get("peak_dbfs_out"))
            rms_in = proc.get("rms_dbfs_in")
            if duration is None:
                duration = wav_duration(wav_path)
            rows.append({
                "kind": "sfx",
                "id": sid,
                "variant": v_idx,
                "category": category,
                "tags": list(tags),
                "wav_rel": relpath(wav_path, gallery_dir),
                "waveform_rel": relpath(qa_dir / "waveform.png", gallery_dir)
                                 if (qa_dir / "waveform.png").exists() else None,
                "spectrogram_rel": relpath(qa_dir / "spectrogram.png", gallery_dir)
                                    if (qa_dir / "spectrogram.png").exists() else None,
                "duration_s": duration,
                "rms_dbfs_in": rms_in,
                "rms_dbfs_out": rms_out,
                "peak_dbfs_out": peak_out,
                "target_rms_db": target_rms,
                "backend": backend,
                "click_estimate": click_estimate,
                "clipped": clipped,
                "size_bytes": file_size(wav_path),
                "notes": notes,
                "preset": cue.get("preset"),
            })
    return rows


def collect_ambience_rows(summary: dict, gallery_dir: Path) -> tuple[list[dict], list[dict]]:
    """Returns (biome_rows, stem_rows). biome_rows = one per biome (with reverb,
    poisson), stem_rows = one per individual ambience WAV stem."""
    biome_rows: list[dict] = []
    stem_rows: list[dict] = []
    for biome_id, biome in (summary.get("biomes") or {}).items():
        biome_dir = ASSETS / "audio" / "ambience" / biome_id
        manifest_path = biome_dir / "biome_ambience.json"
        manifest = load_json(manifest_path, {}) or {}
        biome_rows.append({
            "biome": biome_id,
            "reverb": biome.get("reverb", {}),
            "poisson_lambda": biome.get("poisson_lambda_per_sec", {}),
            "stem_count": biome.get("stem_count", 0),
            "all_dry_run": biome.get("all_dry_run", False),
        })
        # Walk each stem in the per-biome manifest
        for stem in manifest.get("stems", []):
            wav_path = Path(stem.get("out_path", "")) if stem.get("out_path") else None
            if not wav_path or not wav_path.exists():
                continue
            cue_path = wav_path.with_suffix(".cue.json")
            cue = load_json(cue_path, {}) or {}
            stem_name = stem.get("stem", wav_path.stem)
            stem_rows.append({
                "kind": "ambience",
                "biome": biome_id,
                "stem": stem_name,
                "wav_rel": relpath(wav_path, gallery_dir),
                "waveform_rel": None,  # ambience stems aren't routinely QA'd
                "duration_s": stem.get("duration_s"),
                "rms_dbfs": stem.get("rms_dbfs"),
                "peak_dbfs": stem.get("peak_dbfs"),
                "lufs_target": stem.get("lufs_target"),
                "backend_actual": stem.get("backend_actual"),
                "backend_requested": stem.get("backend_requested"),
                "loop": stem.get("loop"),
                "seam_rms": stem.get("seam_rms"),
                "fitness": stem.get("fitness"),
                "prompt": stem.get("prompt") or cue.get("prompt"),
                "model": cue.get("model"),
                "seed": stem.get("seed"),
                "dry_run": stem.get("dry_run", False),
                "size_bytes": file_size(wav_path),
            })
    return biome_rows, stem_rows


# ---------- HTML ----------

CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { font: 14px/1.45 ui-sans-serif, system-ui, sans-serif;
       background: #0e1116; color: #d8dde8; margin: 0; padding: 0; }
header { padding: 14px 20px; border-bottom: 1px solid #20242c;
         background: #11141a; position: sticky; top: 0; z-index: 9; }
h1 { font-size: 18px; margin: 0; display: inline-block; }
.subtitle { color: #8a93a3; margin-left: 16px; font-size: 12px; }
nav { padding: 8px 20px; background: #0a0d11; border-bottom: 1px solid #20242c; }
nav a { color: #8ab4ff; margin-right: 14px; text-decoration: none;
        padding: 4px 10px; border-radius: 4px; }
nav a.active { background: #1a2333; color: #fff; }
.controls { padding: 8px 20px; background: #0a0d11; border-bottom: 1px solid #20242c;
            display: flex; gap: 12px; align-items: center; }
input[type=search] { background: #1a1e26; color: #d8dde8;
                     border: 1px solid #2a303c; border-radius: 4px;
                     padding: 6px 10px; width: 320px; font-size: 13px; }
.section { padding: 12px 20px; }
table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
th, td { padding: 6px 10px; border-bottom: 1px solid #1d212b;
         text-align: left; vertical-align: middle; }
th { background: #14181f; color: #aab2c3; cursor: pointer; user-select: none;
     position: sticky; top: 0; }
th[data-sort] { white-space: nowrap; }
tbody tr:hover { background: #161b25; }
audio { height: 28px; max-width: 240px; }
.tag { display: inline-block; background: #1c2231; color: #97a4bc;
       border-radius: 3px; padding: 1px 6px; font-size: 11px; margin-right: 4px; }
.thumb { height: 36px; cursor: pointer; image-rendering: pixelated; }
.lufs-good { color: #8be08b; }
.lufs-warn { color: #e0c98b; }
.lufs-bad  { color: #e08b8b; }
.muted { color: #6f7689; }
.modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,0.85);
            display: none; align-items: center; justify-content: center;
            z-index: 100; }
.modal-bg.open { display: flex; }
.modal-bg img { max-width: 90vw; max-height: 80vh; }
.biome-card { background: #14181f; border: 1px solid #20242c;
              border-radius: 6px; padding: 10px 14px; margin-bottom: 10px; }
.biome-card h3 { margin: 0 0 6px 0; font-size: 14px; color: #d8e7ff; }
.kvs { color: #97a4bc; font-size: 12px; }
.kvs span { margin-right: 14px; }
"""


JS = r"""
const $ = (s, p=document) => p.querySelector(s);
const $$ = (s, p=document) => Array.from(p.querySelectorAll(s));

function setupTabs() {
  $$('nav a').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    $$('nav a').forEach(x => x.classList.remove('active'));
    a.classList.add('active');
    const tgt = a.dataset.tab;
    $$('.tab').forEach(t => t.style.display = (t.dataset.tab === tgt ? 'block' : 'none'));
    location.hash = tgt;
  }));
  // Honor #hash on load
  const hash = (location.hash || '#sfx').slice(1);
  const a = $$('nav a').find(x => x.dataset.tab === hash) || $$('nav a')[0];
  a.click();
}

function setupFilter() {
  const inp = $('#filter');
  let timer;
  inp.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const q = inp.value.toLowerCase().trim();
      $$('.tab tbody tr, .tab .biome-card').forEach(r => {
        if (!q) { r.style.display = ''; return; }
        const hay = (r.dataset.search || r.textContent).toLowerCase();
        r.style.display = hay.includes(q) ? '' : 'none';
      });
    }, 60);
  });
}

function setupSort() {
  $$('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      const tbody = th.closest('table').querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const cur = th.dataset.dir === 'asc' ? 'desc' : 'asc';
      $$('th[data-sort]', th.closest('table')).forEach(x => delete x.dataset.dir);
      th.dataset.dir = cur;
      rows.sort((a, b) => {
        const av = a.dataset[col] ?? a.cells[+th.dataset.colIdx]?.textContent ?? '';
        const bv = b.dataset[col] ?? b.cells[+th.dataset.colIdx]?.textContent ?? '';
        const af = parseFloat(av), bf = parseFloat(bv);
        const cmp = (!isNaN(af) && !isNaN(bf)) ? af - bf : av.localeCompare(bv);
        return cur === 'asc' ? cmp : -cmp;
      });
      rows.forEach(r => tbody.appendChild(r));
    });
  });
}

function setupModal() {
  const bg = $('#modal-bg');
  const img = $('#modal-img');
  $$('.thumb').forEach(t => t.addEventListener('click', () => {
    if (!t.dataset.spec) return;
    img.src = t.dataset.spec;
    bg.classList.add('open');
  }));
  bg.addEventListener('click', () => { bg.classList.remove('open'); img.src = ''; });
}

document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  setupFilter();
  setupSort();
  setupModal();
});
"""


def lufs_class(rms: float | None, target: float | None) -> str:
    if rms is None or target is None:
        return "muted"
    diff = abs(rms - target)
    if diff <= 1.0: return "lufs-good"
    if diff <= 3.5: return "lufs-warn"
    return "lufs-bad"


def render_html(sfx_rows: list[dict], biome_rows: list[dict],
                stem_rows: list[dict],
                title: str = "Audio gallery") -> str:
    total_sfx_size = sum(r["size_bytes"] or 0 for r in sfx_rows)
    total_amb_size = sum(r["size_bytes"] or 0 for r in stem_rows)
    total_dur = sum((r.get("duration_s") or 0) for r in (sfx_rows + stem_rows))
    n_sfx = len({r["id"] for r in sfx_rows})
    n_variants = len(sfx_rows)
    n_biomes = len(biome_rows)
    n_stems = len(stem_rows)

    out = []
    out.append("<!doctype html>")
    out.append('<html lang="en"><head><meta charset="utf-8">')
    out.append(f"<title>{html.escape(title)}</title>")
    out.append(f"<style>{CSS}</style>")
    out.append("</head><body>")
    out.append("<header>")
    out.append(f"<h1>{html.escape(title)}</h1>")
    out.append(f'<span class="subtitle">{n_sfx} SFX / {n_variants} variants &middot; '
               f'{n_biomes} biomes / {n_stems} ambience stems &middot; '
               f'{fmt_duration(total_dur)} &middot; '
               f'{fmt_bytes(total_sfx_size + total_amb_size)} &middot; '
               f'generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}</span>')
    out.append("</header>")

    out.append('<nav>')
    out.append('<a href="#sfx" data-tab="sfx" class="active">SFX</a>')
    out.append('<a href="#ambience" data-tab="ambience">Ambience</a>')
    out.append('<a href="#stems" data-tab="stems">Ambience stems</a>')
    out.append("</nav>")

    out.append('<div class="controls">')
    out.append('<input type="search" id="filter" placeholder="Filter by id, tag, category, biome..." autocomplete="off">')
    out.append('</div>')

    # ---- SFX tab ----
    out.append('<div class="tab section" data-tab="sfx">')
    out.append('<table><thead><tr>')
    headers = [
        ("id", "ID"), ("variant", "v"), ("category", "Category"),
        ("duration_s", "Dur"), ("rms_out", "RMS"),
        ("peak_out", "Peak"), ("target_rms", "Target"),
        ("backend", "Backend"), ("preview", "Preview"), ("waveform", "Wave"),
        ("size", "Size"),
    ]
    for i, (k, label) in enumerate(headers):
        out.append(f'<th data-sort="{k}" data-col-idx="{i}">{label}</th>')
    out.append('</tr></thead><tbody>')
    for r in sfx_rows:
        rms = r.get("rms_dbfs_out")
        peak = r.get("peak_dbfs_out")
        target = r.get("target_rms_db")
        cls = lufs_class(rms, target)
        wav_rel = r["wav_rel"]
        waveform = r.get("waveform_rel")
        spec = r.get("spectrogram_rel")
        thumb = (f'<img class="thumb" src="{html.escape(waveform)}" loading="lazy" '
                 f'data-spec="{html.escape(spec) if spec else ""}" '
                 f'alt="waveform">' if waveform else '<span class="muted">-</span>')
        tag_html = " ".join(
            f'<span class="tag">{html.escape(t)}</span>'
            for t in (r.get("tags") or [])[:4])
        search_attr = " ".join(filter(None, [
            r["id"], str(r.get("category", "")), r.get("backend") or "",
            r.get("preset") or "", " ".join(r.get("tags") or []),
        ]))
        out.append(
            f'<tr data-search="{html.escape(search_attr.lower())}"'
            f' data-id="{html.escape(r["id"])}" data-variant="{r["variant"]}"'
            f' data-duration_s="{r.get("duration_s") or 0:.4f}"'
            f' data-rms_out="{rms or 0:.2f}" data-peak_out="{peak or 0:.2f}"'
            f' data-target_rms="{target or 0:.2f}"'
            f' data-size="{r.get("size_bytes") or 0}">'
        )
        out.append(f'<td><strong>{html.escape(r["id"])}</strong><br>{tag_html}</td>')
        out.append(f'<td>v{r["variant"]}</td>')
        out.append(f'<td>{html.escape(str(r.get("category","")))}</td>')
        out.append(f'<td>{(r.get("duration_s") or 0):.2f}s</td>')
        out.append(f'<td class="{cls}">{rms:.1f}</td>' if rms is not None else '<td class="muted">-</td>')
        out.append(f'<td>{peak:.1f}</td>' if peak is not None else '<td class="muted">-</td>')
        out.append(f'<td>{target:.1f}</td>' if target is not None else '<td class="muted">-</td>')
        out.append(f'<td class="muted">{html.escape(str(r.get("backend") or "?"))}</td>')
        out.append(f'<td><audio controls preload="none" src="{html.escape(wav_rel)}"></audio></td>')
        out.append(f'<td>{thumb}</td>')
        out.append(f'<td>{fmt_bytes(r.get("size_bytes") or 0)}</td>')
        out.append('</tr>')
    out.append('</tbody></table>')
    out.append('</div>')

    # ---- Ambience tab (per-biome cards) ----
    out.append('<div class="tab section" data-tab="ambience" style="display:none">')
    for b in biome_rows:
        rev = b.get("reverb") or {}
        poi = b.get("poisson_lambda") or {}
        rev_str = ", ".join(f"{k}={v}" for k, v in rev.items())
        poi_str = ", ".join(f"{k}={v}" for k, v in poi.items())
        all_dry = b.get("all_dry_run", False)
        out.append(f'<div class="biome-card" data-search="{html.escape(b["biome"].lower())}">')
        out.append(f'<h3>{html.escape(b["biome"])} '
                   f'<span class="muted">({b.get("stem_count",0)} stems'
                   f'{", DRY-RUN" if all_dry else ""})</span></h3>')
        out.append(f'<div class="kvs"><span>reverb: {html.escape(rev_str)}</span>'
                   f'<span>poisson: {html.escape(poi_str)}</span></div>')
        out.append('</div>')
    out.append('</div>')

    # ---- Ambience stems tab ----
    out.append('<div class="tab section" data-tab="stems" style="display:none">')
    out.append('<table><thead><tr>')
    headers2 = [
        ("biome", "Biome"), ("stem", "Stem"),
        ("duration", "Dur"), ("rms", "RMS"), ("peak", "Peak"),
        ("target", "Target"), ("seam", "Seam"),
        ("backend", "Backend"), ("preview", "Preview"), ("size", "Size"),
    ]
    for i, (k, label) in enumerate(headers2):
        out.append(f'<th data-sort="{k}" data-col-idx="{i}">{label}</th>')
    out.append('</tr></thead><tbody>')
    for r in stem_rows:
        rms = r.get("rms_dbfs")
        peak = r.get("peak_dbfs")
        target = r.get("lufs_target")
        cls = lufs_class(rms, target)
        seam = r.get("seam_rms")
        seam_str = f"{seam:.4f}" if seam is not None else "-"
        backend = r.get("backend_actual") or r.get("backend_requested") or "?"
        if r.get("dry_run"):
            backend = backend + " (dry)"
        prompt = (r.get("prompt") or "")[:80] + ("..." if r.get("prompt") and len(r.get("prompt")) > 80 else "")
        search_attr = " ".join(filter(None, [
            r["biome"], r["stem"], str(backend),
            r.get("model") or "", r.get("prompt") or "",
        ]))
        out.append(
            f'<tr data-search="{html.escape(search_attr.lower())}"'
            f' data-biome="{html.escape(r["biome"])}"'
            f' data-stem="{html.escape(r["stem"])}"'
            f' data-duration="{r.get("duration_s") or 0:.4f}"'
            f' data-rms="{rms or 0:.2f}" data-peak="{peak or 0:.2f}"'
            f' data-target="{target or 0:.2f}"'
            f' data-seam="{seam or 0:.5f}" data-size="{r.get("size_bytes") or 0}">'
        )
        out.append(f'<td><strong>{html.escape(r["biome"])}</strong></td>')
        out.append(f'<td>{html.escape(r["stem"])}<br><span class="muted">{html.escape(prompt)}</span></td>')
        out.append(f'<td>{(r.get("duration_s") or 0):.1f}s</td>')
        out.append(f'<td class="{cls}">{rms:.1f}</td>' if rms is not None else '<td class="muted">-</td>')
        out.append(f'<td>{peak:.1f}</td>' if peak is not None else '<td class="muted">-</td>')
        out.append(f'<td>{target:.1f}</td>' if target is not None else '<td class="muted">-</td>')
        out.append(f'<td>{html.escape(seam_str)}</td>')
        out.append(f'<td class="muted">{html.escape(str(backend))}</td>')
        out.append(f'<td><audio controls preload="none" src="{html.escape(r["wav_rel"])}"></audio></td>')
        out.append(f'<td>{fmt_bytes(r.get("size_bytes") or 0)}</td>')
        out.append('</tr>')
    out.append('</tbody></table>')
    out.append('</div>')

    out.append('<div id="modal-bg" class="modal-bg"><img id="modal-img" alt="spectrogram"></div>')
    out.append(f'<script>{JS}</script>')
    out.append("</body></html>")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sfx-manifest", type=Path, default=SFX_MANIFEST)
    ap.add_argument("--ambience-summary", type=Path, default=AMBIENCE_SUMMARY)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-ambience", action="store_true",
                    help="Render SFX-only (skip ambience tab).")
    ap.add_argument("--title", default="Audio gallery — D:\\assets")
    args = ap.parse_args()

    sfx = load_json(args.sfx_manifest, {"sounds": []}) or {"sounds": []}
    summary = ({"biomes": {}}
               if args.no_ambience
               else (load_json(args.ambience_summary, {"biomes": {}}) or {"biomes": {}}))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    sfx_rows = collect_sfx_rows(sfx, args.out.parent)
    biome_rows, stem_rows = collect_ambience_rows(summary, args.out.parent)

    html_doc = render_html(sfx_rows, biome_rows, stem_rows, title=args.title)
    args.out.write_text(html_doc, encoding="utf-8")
    print(f"[gallery] wrote {args.out}")
    print(f"[gallery] sfx_rows={len(sfx_rows)} biomes={len(biome_rows)} "
          f"ambience_stems={len(stem_rows)}")
    print(f"[gallery] open: file:///{str(args.out).replace(chr(92), '/')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
