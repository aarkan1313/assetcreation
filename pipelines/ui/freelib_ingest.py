"""Free icon library ingester.

Pulls icons from public CC-BY / MIT / ISC / CC0 libraries into our `ui/icons/`
manifest schema. Single biggest variety unlock for the UI pipeline -
game-icons.net alone is ~5000 monochrome RPG-style silhouettes under CC-BY.

Sources supported:

  game-icons-net   ~5000 CC-BY 3.0/4.0 silhouettes, fantasy/RPG-leaning
                   Two intake modes:
                     --zip <path>   bulk archive (preferred, license-correct)
                     --slugs a,b,c  per-icon URL fetch from game-icons.net
                   Either way, attribution per-icon is preserved.
                   See https://game-icons.net/about.html

  url-list         Generic. --url-list <path>  -- one of:
                     {"id": "...", "url": "https://...svg",
                      "license": "MIT", "attribution": null,
                      "semantic_tags": ["..."], "rtl_mirror": false}
                   Use this for Lucide / Phosphor / Tabler raw GitHub URLs.

  mit-iso-libs     UI-chrome libraries via jsDelivr (auto URL templates).
                   --library {lucide,phosphor,tabler,iconoir} --picks <txt>
                   Iconoir added 2026-05-07 per brief #07 (~1600 hand-drawn
                   line icons, MIT). Tabler is the largest free-license set
                   we ingest (~6128, MIT) — the biggest *quantity* win for
                   generic inventory glyphs per the brief.

  oga-rpg700       OpenGameArt 700+ RPG Icons pack (CC0). User-supplied zip
                   only — OGA doesn't expose a stable HTTP API. Fetch
                   manually from https://opengameart.org/content/700-rpg-icons
                   then --zip <path>. Per brief #07 worth-considering ingest.

License hygiene:
  * --accept-license is required for any network fetch. CC-BY libraries also
    require attribution; this tool always writes ATTRIBUTION.md aggregating
    every fetched/ingested icon.
  * The manifest schema includes `license`, `attribution`, `source_url`,
    and the v2 fields `rtl_mirror`, `min_display_px`, `semantic_tags`.

SVG-to-PNG rasterizer:
  resvg-py (preferred, pure-Rust no-DLL wheel) -> cairosvg -> PIL silhouette
  fallback for the single-monochrome-path subset that game-icons.net uses.

CLI:
  python freelib_ingest.py --source game-icons-net --zip game-icons.zip --pick 30
  python freelib_ingest.py --source game-icons-net --slugs sword-wound,fire \
      --accept-license
  python freelib_ingest.py --source url-list --url-list lucide_picks.json \
      --accept-license
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from typing import Iterable

from PIL import Image

ASSETS = Path(r"D:\assets")
ICONS_DIR = ASSETS / "ui" / "icons"
SVG_CACHE = ASSETS / "ui" / "freelib_svg_cache"
ATTRIBUTION_MD = ASSETS / "ui" / "ATTRIBUTION.md"

GAME_ICONS_NET_URL_TMPL = "https://game-icons.net/icons/ffffff/000000/1x1/{author}/{slug}.svg"

# UI-chrome libraries via jsDelivr (stable, CDN-cacheable, no auth).
LUCIDE_URL_TMPL   = "https://cdn.jsdelivr.net/npm/lucide-static@latest/icons/{name}.svg"
PHOSPHOR_URL_TMPL = "https://cdn.jsdelivr.net/npm/@phosphor-icons/core@latest/assets/{weight}/{name}{weight_suffix}.svg"
TABLER_URL_TMPL   = "https://cdn.jsdelivr.net/npm/@tabler/icons@latest/icons/outline/{name}.svg"
# Iconoir added 2026-05-07 per brief #07 — ~1600 hand-drawn line icons, MIT.
# Pairs well with fantasy UI chrome where Tabler/Phosphor read too geometric.
ICONOIR_URL_TMPL  = "https://cdn.jsdelivr.net/npm/iconoir/icons/regular/{name}.svg"

UI_LIB_LICENSES = {
    "lucide":   "ISC",
    "phosphor": "MIT",
    "tabler":   "MIT",
    "iconoir":  "MIT",
}

# OpenGameArt 700+ RPG Icons pack (CC0) — fantasy/RPG specific, raster originally
# but community SVG conversions exist. Per brief #07 worth-considering ingest.
# Unlike CDN libs, this is a single zip download; users must fetch it manually
# via --zip <path> --source oga-rpg700 since OGA doesn't expose a stable HTTP API.
# Original pack: https://opengameart.org/content/700-rpg-icons
OGA_RPG700_LICENSE = "CC0"
OGA_RPG700_ATTRIBUTION_TEXT = (
    "OpenGameArt 700+ RPG Icons (CC0). Original at "
    "https://opengameart.org/content/700-rpg-icons. CC0 = no attribution "
    "required, but recording the source here for asset provenance."
)
# game-icons.net's primary mirror also exposes per-icon raw SVGs by slug.
# The raw silhouette URL pattern is /<author>/<slug>.svg under their CDN.
# We try a couple of patterns because the public site organizes by author.
USER_AGENT = "D-assets-ui-pipeline/1.0 (UI ingester; respect-robots; CC-BY-aware)"


# ---------- Rasterizers ----------------------------------------------------

def _try_resvg(svg_bytes: bytes, size: int) -> bytes | None:
    try:
        import resvg_py  # type: ignore
    except ImportError:
        return None
    try:
        return resvg_py.svg_to_bytes(svg_string=svg_bytes.decode("utf-8"),
                                     width=size, height=size)
    except Exception:  # noqa: BLE001 - fallback through chain
        return None


def _try_cairosvg(svg_bytes: bytes, size: int) -> bytes | None:
    try:
        import cairosvg  # type: ignore
    except (ImportError, OSError):
        # Windows often has cairosvg installed but no libcairo DLL.
        return None
    try:
        return cairosvg.svg2png(bytestring=svg_bytes,
                                output_width=size, output_height=size)
    except Exception:  # noqa: BLE001 - libcairo missing on Windows often
        return None


def _try_pil_silhouette(svg_bytes: bytes, size: int) -> bytes | None:
    """Last-resort rasterizer for game-icons.net's single-path SVGs.

    Parses one `<path d="..."/>` element and walks the path commands using
    PIL.ImageDraw, treating it as a filled silhouette. This is intentionally
    a small subset of SVG (Move, Line, Cubic-Bezier, Quadratic-Bezier, Arc,
    Close) — enough for game-icons.net but not a general renderer.

    Returns None if the SVG is not parseable as a single fill-path silhouette.
    """
    try:
        text = svg_bytes.decode("utf-8", errors="replace")
        m_view = re.search(r'viewBox\s*=\s*"([^"]+)"', text)
        vw = vh = 512.0
        vx = vy = 0.0
        if m_view:
            parts = m_view.group(1).split()
            if len(parts) == 4:
                vx, vy, vw, vh = (float(p) for p in parts)
        m_path = re.search(r'<path[^>]*\sd="([^"]+)"', text)
        if not m_path:
            return None
        d = m_path.group(1)
        from PIL import ImageDraw
        # Scale to target size
        sx = size / vw
        sy = size / vh
        polys = _flatten_path(d, sx, sy, vx, vy)
        if not polys:
            return None
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        drw = ImageDraw.Draw(img)
        for poly in polys:
            if len(poly) >= 3:
                drw.polygon(poly, fill=(0, 0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
    except Exception:  # noqa: BLE001 - silhouette is best-effort
        return None


def _flatten_path(d: str, sx: float, sy: float,
                  vx: float, vy: float) -> list[list[tuple[float, float]]]:
    """Walk SVG path-data and return a list of sub-polygons (linear approx).

    Cubic/quadratic Beziers are flattened to N=12 line segments. Elliptical
    arcs are approximated with the chord (not perfect, but adequate for
    silhouette rendering of stylized icons).
    """
    cmds = re.findall(r'([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)', d)
    polys: list[list[tuple[float, float]]] = []
    poly: list[tuple[float, float]] = []
    cx = cy = 0.0
    sx0 = sy0 = 0.0  # last subpath start
    last_ctrl = None  # for S/T smooth continuation

    def add(x, y):
        polys[-1].append((((x - vx) * sx), ((y - vy) * sy))) \
            if polys else polys.append([(((x - vx) * sx), ((y - vy) * sy))])

    def _start_subpath():
        polys.append([])

    for cmd, body in cmds:
        nums = [float(n) for n in re.findall(
            r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', body)]
        i = 0
        rel = cmd.islower()
        c = cmd.upper()
        if c == 'M':
            # Move => start new subpath
            _start_subpath()
            x, y = nums[i], nums[i + 1]
            if rel:
                x += cx; y += cy
            cx, cy = x, y
            sx0, sy0 = cx, cy
            polys[-1].append(((cx - vx) * sx, (cy - vy) * sy))
            i += 2
            # Subsequent pairs after M are implicit L
            while i + 1 < len(nums):
                x, y = nums[i], nums[i + 1]
                if rel:
                    x += cx; y += cy
                cx, cy = x, y
                polys[-1].append(((cx - vx) * sx, (cy - vy) * sy))
                i += 2
            last_ctrl = None
        elif c == 'L':
            while i + 1 < len(nums):
                x, y = nums[i], nums[i + 1]
                if rel:
                    x += cx; y += cy
                cx, cy = x, y
                if not polys:
                    _start_subpath()
                polys[-1].append(((cx - vx) * sx, (cy - vy) * sy))
                i += 2
            last_ctrl = None
        elif c == 'H':
            while i < len(nums):
                x = nums[i]
                if rel:
                    x += cx
                cx = x
                if not polys:
                    _start_subpath()
                polys[-1].append(((cx - vx) * sx, (cy - vy) * sy))
                i += 1
            last_ctrl = None
        elif c == 'V':
            while i < len(nums):
                y = nums[i]
                if rel:
                    y += cy
                cy = y
                if not polys:
                    _start_subpath()
                polys[-1].append(((cx - vx) * sx, (cy - vy) * sy))
                i += 1
            last_ctrl = None
        elif c == 'C':
            while i + 5 < len(nums):
                x1, y1, x2, y2, x, y = nums[i:i + 6]
                if rel:
                    x1 += cx; y1 += cy
                    x2 += cx; y2 += cy
                    x += cx; y += cy
                _flatten_cubic(polys, sx, sy, vx, vy, cx, cy, x1, y1, x2, y2, x, y)
                cx, cy = x, y
                last_ctrl = (x2, y2)
                i += 6
        elif c == 'S':
            while i + 3 < len(nums):
                x2, y2, x, y = nums[i:i + 4]
                if rel:
                    x2 += cx; y2 += cy
                    x += cx; y += cy
                if last_ctrl is not None:
                    x1 = 2 * cx - last_ctrl[0]
                    y1 = 2 * cy - last_ctrl[1]
                else:
                    x1, y1 = cx, cy
                _flatten_cubic(polys, sx, sy, vx, vy, cx, cy, x1, y1, x2, y2, x, y)
                cx, cy = x, y
                last_ctrl = (x2, y2)
                i += 4
        elif c == 'Q':
            while i + 3 < len(nums):
                x1, y1, x, y = nums[i:i + 4]
                if rel:
                    x1 += cx; y1 += cy
                    x += cx; y += cy
                _flatten_quad(polys, sx, sy, vx, vy, cx, cy, x1, y1, x, y)
                cx, cy = x, y
                last_ctrl = (x1, y1)
                i += 4
        elif c == 'T':
            while i + 1 < len(nums):
                x, y = nums[i], nums[i + 1]
                if rel:
                    x += cx; y += cy
                if last_ctrl is not None:
                    x1 = 2 * cx - last_ctrl[0]
                    y1 = 2 * cy - last_ctrl[1]
                else:
                    x1, y1 = cx, cy
                _flatten_quad(polys, sx, sy, vx, vy, cx, cy, x1, y1, x, y)
                cx, cy = x, y
                last_ctrl = (x1, y1)
                i += 2
        elif c == 'A':
            # rx, ry, x-axis-rotation, large-arc, sweep, x, y -- approximate
            # by drawing the chord. game-icons.net uses arcs sparingly.
            while i + 6 < len(nums):
                _, _, _, _, _, x, y = nums[i:i + 7]
                if rel:
                    x += cx; y += cy
                if not polys:
                    _start_subpath()
                polys[-1].append(((x - vx) * sx, (y - vy) * sy))
                cx, cy = x, y
                i += 7
            last_ctrl = None
        elif c == 'Z':
            if polys and polys[-1] and (polys[-1][0] != polys[-1][-1]):
                polys[-1].append(polys[-1][0])
            cx, cy = sx0, sy0
            last_ctrl = None
    # Drop empty sub-polys
    return [p for p in polys if len(p) >= 2]


def _flatten_cubic(polys, sx, sy, vx, vy,
                   x0, y0, x1, y1, x2, y2, x3, y3, n: int = 12) -> None:
    if not polys:
        polys.append([])
    for k in range(1, n + 1):
        t = k / n
        u = 1 - t
        bx = u**3 * x0 + 3 * u**2 * t * x1 + 3 * u * t**2 * x2 + t**3 * x3
        by = u**3 * y0 + 3 * u**2 * t * y1 + 3 * u * t**2 * y2 + t**3 * y3
        polys[-1].append(((bx - vx) * sx, (by - vy) * sy))


def _flatten_quad(polys, sx, sy, vx, vy,
                  x0, y0, x1, y1, x2, y2, n: int = 10) -> None:
    if not polys:
        polys.append([])
    for k in range(1, n + 1):
        t = k / n
        u = 1 - t
        bx = u**2 * x0 + 2 * u * t * x1 + t**2 * x2
        by = u**2 * y0 + 2 * u * t * y1 + t**2 * y2
        polys[-1].append(((bx - vx) * sx, (by - vy) * sy))


def rasterize(svg_bytes: bytes, size: int) -> bytes:
    """Returns PNG bytes. Tries resvg-py -> cairosvg -> PIL silhouette."""
    for fn in (_try_resvg, _try_cairosvg, _try_pil_silhouette):
        out = fn(svg_bytes, size)
        if out:
            return out
    raise RuntimeError(
        "No SVG rasterizer available. Install resvg-py "
        "(pip install resvg-py) or ensure libcairo is on PATH for cairosvg."
    )


# ---------- Network --------------------------------------------------------

def _fetch_url(url: str, timeout_s: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        return r.read()


# ---------- Source: game-icons-net -----------------------------------------

GAME_ICONS_LICENSE_NOTE = (
    "game-icons.net icons are CC-BY 3.0 unless author opts into CC-BY 4.0 "
    "(see https://game-icons.net/about.html). Attribution is required - this "
    "tool writes ATTRIBUTION.md aggregating every ingested icon's author + "
    "URL. The aggregate-credits-page approach is explicitly allowed."
)


def _record_path(p: Path) -> str:
    """Record a path relative to D:\\assets when possible; else absolute posix."""
    try:
        return str(p.relative_to(ASSETS).as_posix())
    except ValueError:
        return str(p.as_posix())


def _slug_to_id(slug: str, prefix: str = "ico_") -> str:
    s = slug.replace("-", "_").replace("/", "_").lower()
    s = re.sub(r"[^a-z0-9_]", "", s)
    if not s:
        s = "icon"
    return f"{prefix}{s}"


def _load_slug_list(path: Path) -> set[str]:
    """Load a newline-delimited slug list. '#' starts a comment, blank lines ignored."""
    slugs: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Allow `author/slug` or just `slug`; we match by slug only here.
        if "/" in line:
            line = line.split("/", 1)[1]
        slugs.add(line)
    return slugs


def ingest_game_icons_zip(zip_path: Path, out_dir: Path,
                          size: int = 256,
                          pick: int | None = None,
                          name_filter: str | None = None,
                          slug_allowlist: set[str] | None = None,
                          existing_ids: set[str] | None = None,
                          dry_run: bool = False) -> list[dict]:
    """Walk a game-icons.net bulk archive (any zip containing .svg files).

    The archive layout used by game-icons.net is `<author>/<slug>.svg`. We
    accept any zip that follows that pattern, plus optionally an `icons.csv`
    metadata sidecar with columns `slug,name,author,license,tags`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    SVG_CACHE.mkdir(parents=True, exist_ok=True)
    existing_ids = set(existing_ids or set())

    csv_meta: dict[str, dict] = {}
    icons: list[dict] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Optional csv sidecar
        for name in zf.namelist():
            if name.lower().endswith("icons.csv"):
                with zf.open(name) as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                    for row in reader:
                        slug = (row.get("slug") or row.get("name") or "").strip()
                        if slug:
                            csv_meta[slug] = row
                break

        svg_names = sorted(n for n in zf.namelist()
                           if n.lower().endswith(".svg"))
        if name_filter:
            pat = re.compile(name_filter)
            svg_names = [n for n in svg_names if pat.search(n)]
        if slug_allowlist:
            svg_names = [n for n in svg_names if Path(n).stem in slug_allowlist]
        if pick:
            svg_names = svg_names[:pick]

        for name in svg_names:
            parts = name.split("/")
            slug = Path(name).stem
            author = parts[-2] if len(parts) >= 2 else "unknown"
            icon_id = _slug_to_id(slug)
            if icon_id in existing_ids:
                continue
            existing_ids.add(icon_id)
            meta = csv_meta.get(slug, {})
            license_id = meta.get("license") or "CC-BY 3.0"
            display_name = meta.get("name") or slug.replace("-", " ").title()
            tags_raw = meta.get("tags", "") or ""
            tags = [t.strip() for t in tags_raw.split("|") if t.strip()]
            svg_bytes = zf.read(name)
            cache_svg = SVG_CACHE / f"{icon_id}.svg"
            cache_svg.write_bytes(svg_bytes)
            png_path = out_dir / f"{icon_id}.png"
            if dry_run:
                print(f"[freelib_ingest] DRY {icon_id} ({author}/{slug})")
                continue
            png = rasterize(svg_bytes, size)
            png_path.write_bytes(png)
            icons.append({
                "id": icon_id,
                "path": _record_path(png_path),
                "size_px": size,
                "backend": "freelib",
                "source": "game-icons.net",
                "source_slug": slug,
                "source_author": author,
                "source_url": f"https://game-icons.net/1x1/{author}/{slug}.html",
                "license": license_id,
                "attribution": f"{author} / game-icons.net / {license_id}",
                "display_name": display_name,
                "semantic_tags": tags,
                "rtl_mirror": False,
                "min_display_px": 32,
            })
            print(f"[freelib_ingest] {icon_id:30s} ({author}/{slug})")
    return icons


def ingest_game_icons_slugs(slugs_with_authors: list[tuple[str, str]],
                            out_dir: Path,
                            size: int = 256,
                            existing_ids: set[str] | None = None) -> list[dict]:
    """Per-icon URL fetch from game-icons.net.

    Each entry is (author, slug). We try the public raw silhouette URL and
    fall back if the author guess is wrong. License is assumed CC-BY 3.0
    unless the caller provides metadata.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    SVG_CACHE.mkdir(parents=True, exist_ok=True)
    existing_ids = set(existing_ids or set())
    icons: list[dict] = []
    for author, slug in slugs_with_authors:
        icon_id = _slug_to_id(slug)
        if icon_id in existing_ids:
            print(f"[freelib_ingest] SKIP {icon_id} (already in manifest)")
            continue
        url = GAME_ICONS_NET_URL_TMPL.format(author=author, slug=slug)
        try:
            svg_bytes = _fetch_url(url)
        except urllib.error.HTTPError as e:
            print(f"[freelib_ingest] WARN {icon_id} HTTP {e.code} {url}")
            continue
        except Exception as e:  # noqa: BLE001
            print(f"[freelib_ingest] WARN {icon_id} {type(e).__name__}: {e}")
            continue
        cache_svg = SVG_CACHE / f"{icon_id}.svg"
        cache_svg.write_bytes(svg_bytes)
        png_path = out_dir / f"{icon_id}.png"
        png = rasterize(svg_bytes, size)
        png_path.write_bytes(png)
        existing_ids.add(icon_id)
        icons.append({
            "id": icon_id,
            "path": _record_path(png_path),
            "size_px": size,
            "backend": "freelib",
            "source": "game-icons.net",
            "source_slug": slug,
            "source_author": author,
            "source_url": f"https://game-icons.net/1x1/{author}/{slug}.html",
            "license": "CC-BY 3.0",
            "attribution": f"{author} / game-icons.net / CC-BY 3.0",
            "display_name": slug.replace("-", " ").title(),
            "semantic_tags": [],
            "rtl_mirror": False,
            "min_display_px": 32,
        })
        print(f"[freelib_ingest] {icon_id:30s} ({author}/{slug})")
        # be a polite client
        time.sleep(0.25)
    return icons


# ---------- Source: game-icons-net via curated picklist --------------------

def ingest_game_icons_picklist(items: list[dict], out_dir: Path,
                               size: int = 256,
                               existing_ids: set[str] | None = None,
                               throttle_s: float = 0.25) -> list[dict]:
    """Per-icon URL fetch with explicit per-entry id + semantic_tags.

    Picklist entry shape (extends the simple slugs path):
      {
        "author": "lorc",
        "slug":   "fire",
        "id":     "ico_gi_fire",                 # overrides auto-generated
        "semantic_tags": ["spell","fire","element"],
        "rtl_mirror": false,                      # optional
        "min_display_px": 32,                     # optional
        "display_name": "Fire",                   # optional
        "license":  "CC-BY 3.0"                   # optional override
      }

    Used by curated picklists (`pipelines/ui/picklists/*.json`) so the
    generated manifest has rich `semantic_tags` (consumed by
    `suggest_icon_for_record.py`) without manual post-processing.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    SVG_CACHE.mkdir(parents=True, exist_ok=True)
    existing_ids = set(existing_ids or set())
    icons: list[dict] = []
    for entry in items:
        author = entry["author"]
        slug = entry["slug"]
        icon_id = entry.get("id") or _slug_to_id(slug)
        if icon_id in existing_ids:
            print(f"[freelib_ingest] SKIP {icon_id} (already in manifest)")
            continue
        url = GAME_ICONS_NET_URL_TMPL.format(author=author, slug=slug)
        try:
            svg_bytes = _fetch_url(url)
        except urllib.error.HTTPError as e:
            print(f"[freelib_ingest] WARN {icon_id} HTTP {e.code} {url}")
            continue
        except Exception as e:  # noqa: BLE001
            print(f"[freelib_ingest] WARN {icon_id} {type(e).__name__}: {e}")
            continue
        cache_svg = SVG_CACHE / f"{icon_id}.svg"
        cache_svg.write_bytes(svg_bytes)
        png_path = out_dir / f"{icon_id}.png"
        png = rasterize(svg_bytes, size)
        png_path.write_bytes(png)
        existing_ids.add(icon_id)
        license_id = entry.get("license") or "CC-BY 3.0"
        icons.append({
            "id": icon_id,
            "path": _record_path(png_path),
            "size_px": size,
            "backend": "freelib",
            "source": "game-icons.net",
            "source_slug": slug,
            "source_author": author,
            "source_url": f"https://game-icons.net/1x1/{author}/{slug}.html",
            "license": license_id,
            "attribution": f"{author} / game-icons.net / {license_id}",
            "display_name": entry.get(
                "display_name", slug.replace("-", " ").title()),
            "semantic_tags": entry.get("semantic_tags", []),
            "rtl_mirror": entry.get("rtl_mirror", False),
            "min_display_px": entry.get("min_display_px", 32),
        })
        print(f"[freelib_ingest] {icon_id:32s} ({author}/{slug}) "
              f"tags={','.join(entry.get('semantic_tags', []))[:40]}")
        if throttle_s > 0:
            time.sleep(throttle_s)
    return icons


# ---------- Source: UI chrome (Lucide / Phosphor / Tabler) -----------------

def _ui_lib_url(entry: dict) -> str:
    lib = entry["lib"]
    name = entry["name"]
    if lib == "lucide":
        return LUCIDE_URL_TMPL.format(name=name)
    if lib == "phosphor":
        weight = entry.get("weight", "regular")
        # Phosphor file names are <name>.svg for "regular"; <name>-<weight>.svg
        # for thin/light/bold/fill/duotone.
        suffix = "" if weight == "regular" else f"-{weight}"
        return PHOSPHOR_URL_TMPL.format(name=name, weight=weight,
                                        weight_suffix=suffix)
    if lib == "tabler":
        return TABLER_URL_TMPL.format(name=name)
    if lib == "iconoir":
        # Added 2026-05-07 per brief #07. Hand-drawn line icons, MIT, ~1600 entries.
        return ICONOIR_URL_TMPL.format(name=name)
    raise ValueError(f"unknown ui lib {lib!r}; valid: lucide / phosphor / tabler / iconoir")


def ingest_ui_lib_picklist(items: list[dict], out_dir: Path,
                           size: int = 256,
                           existing_ids: set[str] | None = None,
                           throttle_s: float = 0.10) -> list[dict]:
    """Ingester for Lucide / Phosphor / Tabler.

    Picklist entry shape:
      {
        "lib":  "lucide" | "phosphor" | "tabler",
        "name": "settings",                     # icon name in the library
        "id":   "ico_lc_settings",              # required (no attribution
                                                # nudge from us)
        "semantic_tags": ["chrome","settings"],
        "weight": "regular",                    # phosphor only; default "regular"
        "rtl_mirror": false,
        "min_display_px": 16,
        "display_name": "Settings"
      }

    All three libraries are MIT or ISC: **no attribution required**.
    The license field is still recorded in the manifest for audit.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    SVG_CACHE.mkdir(parents=True, exist_ok=True)
    existing_ids = set(existing_ids or set())
    icons: list[dict] = []
    for entry in items:
        lib = entry["lib"]
        name = entry["name"]
        icon_id = entry.get("id") or f"ico_{lib[:2]}_{name.replace('-', '_')}"
        if icon_id in existing_ids:
            print(f"[freelib_ingest] SKIP {icon_id} (already in manifest)")
            continue
        try:
            url = _ui_lib_url(entry)
        except ValueError as e:
            print(f"[freelib_ingest] WARN {icon_id} {e}")
            continue
        try:
            svg_bytes = _fetch_url(url)
        except urllib.error.HTTPError as e:
            print(f"[freelib_ingest] WARN {icon_id} HTTP {e.code} {url}")
            continue
        except Exception as e:  # noqa: BLE001
            print(f"[freelib_ingest] WARN {icon_id} {type(e).__name__}: {e}")
            continue
        cache_svg = SVG_CACHE / f"{icon_id}.svg"
        cache_svg.write_bytes(svg_bytes)
        png_path = out_dir / f"{icon_id}.png"
        # Lucide / Tabler / Phosphor outline ship as STROKE icons (no fill).
        # Our PIL silhouette fallback fills polygons, so prefer resvg-py here.
        png = rasterize(svg_bytes, size)
        png_path.write_bytes(png)
        existing_ids.add(icon_id)
        license_id = entry.get("license") or UI_LIB_LICENSES.get(lib, "unknown")
        icons.append({
            "id": icon_id,
            "path": _record_path(png_path),
            "size_px": size,
            "backend": "freelib",
            "source": lib,
            "source_name": name,
            "source_url": url,
            "license": license_id,
            "attribution": None,  # MIT/ISC do not require per-icon credit
            "display_name": entry.get("display_name", name.replace("-", " ").title()),
            "semantic_tags": entry.get("semantic_tags", []),
            "rtl_mirror": entry.get("rtl_mirror", False),
            "min_display_px": entry.get("min_display_px", 16),
        })
        if entry.get("weight"):
            icons[-1]["weight"] = entry["weight"]
        print(f"[freelib_ingest] {icon_id:32s} ({lib}/{name}) "
              f"tags={','.join(entry.get('semantic_tags', []))[:40]}")
        if throttle_s > 0:
            time.sleep(throttle_s)
    return icons


# ---------- Source: url-list -----------------------------------------------

def ingest_url_list(specs: list[dict], out_dir: Path,
                    size: int = 256,
                    existing_ids: set[str] | None = None) -> list[dict]:
    """Generic URL-list ingester. Each spec needs:
        id, url
    Optional:
        license, attribution, source, semantic_tags, rtl_mirror,
        min_display_px, display_name
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    SVG_CACHE.mkdir(parents=True, exist_ok=True)
    existing_ids = set(existing_ids or set())
    icons: list[dict] = []
    for spec in specs:
        icon_id = spec["id"]
        if icon_id in existing_ids:
            print(f"[freelib_ingest] SKIP {icon_id} (already in manifest)")
            continue
        url = spec["url"]
        try:
            data = _fetch_url(url)
        except Exception as e:  # noqa: BLE001
            print(f"[freelib_ingest] WARN {icon_id} {type(e).__name__}: {e}")
            continue
        is_svg = url.lower().endswith(".svg") or data[:200].lstrip().startswith(b"<")
        png_path = out_dir / f"{icon_id}.png"
        if is_svg:
            cache = SVG_CACHE / f"{icon_id}.svg"
            cache.write_bytes(data)
            png = rasterize(data, size)
            png_path.write_bytes(png)
        else:
            # raw raster passthrough; resize to size
            with Image.open(io.BytesIO(data)) as im:
                im = im.convert("RGBA").resize((size, size), Image.LANCZOS)
                im.save(png_path)
        existing_ids.add(icon_id)
        icons.append({
            "id": icon_id,
            "path": _record_path(png_path),
            "size_px": size,
            "backend": "freelib",
            "source": spec.get("source", "url-list"),
            "source_url": url,
            "license": spec.get("license", "unknown"),
            "attribution": spec.get("attribution"),
            "display_name": spec.get(
                "display_name", icon_id.replace("ico_", "").replace("_", " ").title()),
            "semantic_tags": spec.get("semantic_tags", []),
            "rtl_mirror": spec.get("rtl_mirror", False),
            "min_display_px": spec.get("min_display_px", 32),
        })
        print(f"[freelib_ingest] {icon_id:30s} ({spec.get('source','url-list')})")
        time.sleep(0.1)
    return icons


# ---------- Source: MIT/ISC monochrome icon libraries ---------------------

# Lucide / Phosphor / Tabler — UI primitives game-icons.net doesn't cover well.
# All three serve raw SVGs from versioned GitHub paths under permissive licenses.
# The URL templates below pin to release tags so output is reproducible. Bump
# the tags here when the upstream library has a meaningful update.
MIT_ISO_LIB_REGISTRY: dict[str, dict] = {
    "lucide": {
        "license": "ISC",
        # `main` is stable enough for our UI-chrome needs and avoids version
        # churn in pinned tags. Pin a specific commit later if reproducibility
        # of the EXACT bytes matters; we cache the SVG anyway.
        "url_template": "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{slug}.svg",
        "source_html": "https://lucide.dev/icons/{slug}",
        "attribution": "Lucide contributors / ISC (no attribution required)",
    },
    "phosphor": {
        "license": "MIT",
        # Phosphor ships per-weight subdirs; use 'regular' as default.
        "url_template": "https://raw.githubusercontent.com/phosphor-icons/core/main/raw/regular/{slug}.svg",
        "source_html": "https://phosphoricons.com/?q={slug}",
        "attribution": "Phosphor Icons / MIT (no attribution required)",
    },
    "tabler": {
        "license": "MIT",
        # Tabler also has 'filled/' and 'outline/'. Outline is the default.
        "url_template": "https://raw.githubusercontent.com/tabler/tabler-icons/main/icons/outline/{slug}.svg",
        "source_html": "https://tabler.io/icons/icon/{slug}",
        "attribution": "Tabler Icons / MIT (no attribution required)",
    },
    # Iconoir added 2026-05-07 per brief #07. ~1600 hand-drawn line icons,
    # MIT. Pairs better with fantasy UI chrome than the more geometric
    # Lucide/Phosphor/Tabler — line weight is friendlier to ornate frames.
    "iconoir": {
        "license": "MIT",
        # Iconoir's regular weight is the default. solid/ also exists.
        "url_template": "https://raw.githubusercontent.com/iconoir-icons/iconoir/main/icons/regular/{slug}.svg",
        "source_html": "https://iconoir.com/?search={slug}",
        "attribution": "Iconoir / MIT (no attribution required)",
    },
}


# Curated UI-primitive picks per library. These cover the chrome game-icons.net
# is weakest at: chevrons, arrows, gear, x, plus, search, settings, menu, and
# similar 2-pixel-line monochromatic UI marks. Lines may have a leading
# 'lucide:' / 'phosphor:' / 'tabler:' prefix to override the source for one
# slug; otherwise they apply to whichever library is selected via --library.
MIT_ISO_DEFAULT_PICKS: dict[str, list[str]] = {
    "lucide": [
        "chevron-left", "chevron-right", "chevron-up", "chevron-down",
        "arrow-left", "arrow-right", "arrow-up", "arrow-down",
        "settings", "menu", "x", "plus", "minus", "search",
        "info", "alert-triangle", "check", "circle",
        "filter", "list", "trash-2", "save", "user", "users",
    ],
    "phosphor": [
        "caret-left", "caret-right", "caret-up", "caret-down",
        "arrow-left", "arrow-right", "arrow-up", "arrow-down",
        "gear", "list", "x", "plus", "minus", "magnifying-glass",
        "info", "warning", "check", "circle",
    ],
    "tabler": [
        "chevron-left", "chevron-right", "chevron-up", "chevron-down",
        "arrow-left", "arrow-right", "arrow-up", "arrow-down",
        "settings", "menu-2", "x", "plus", "minus", "search",
        "info-circle", "alert-triangle", "check", "circle",
        "filter", "list", "trash", "device-floppy",
    ],
    "iconoir": [
        # Default UI-chrome subset; Iconoir's strength is ornate-line aesthetic
        # so picks bias toward icons that game frames actually need.
        "nav-arrow-left", "nav-arrow-right", "nav-arrow-up", "nav-arrow-down",
        "settings", "menu", "xmark", "plus", "minus", "search",
        "info-circle", "warning-triangle", "check", "circle",
        "filter-list", "list", "trash", "save",
    ],
}


# Library-specific semantic_tags — these are derived deterministically from
# the slug rather than authored per-icon, but the schema slot is preserved
# so suggest_icon_for_record.py and link_validator can reason over them.
MIT_ISO_TAG_HINTS = {
    # mark-class hints inferred from common UI-primitive names
    "chevron":  ["nav", "arrow", "compact"],
    "arrow":    ["nav", "direction"],
    "settings": ["ui", "menu", "config"],
    "gear":     ["ui", "menu", "config"],
    "menu":     ["ui", "open"],
    "x":        ["ui", "close", "cancel"],
    "plus":     ["ui", "add", "create"],
    "minus":    ["ui", "remove", "subtract"],
    "search":   ["ui", "find"],
    "magnifying-glass": ["ui", "find"],
    "info":     ["ui", "status", "info"],
    "alert":    ["ui", "status", "warning"],
    "warning":  ["ui", "status", "warning"],
    "check":    ["ui", "status", "ok"],
    "circle":   ["ui", "neutral"],
    "filter":   ["ui", "list"],
    "list":     ["ui", "view"],
    "trash":    ["ui", "destructive"],
    "save":     ["ui", "persist"],
    "device-floppy": ["ui", "persist"],
    "user":     ["ui", "identity"],
    "caret":    ["nav", "arrow", "compact"],
}


def _mit_iso_id_prefix(library: str) -> str:
    return f"ico_{library}_"  # ico_lucide_chevron_left, ico_phosphor_x, ...


def _mit_iso_tags(slug: str) -> list[str]:
    out: list[str] = []
    for stem, tags in MIT_ISO_TAG_HINTS.items():
        if stem in slug:
            for t in tags:
                if t not in out:
                    out.append(t)
    return out


def ingest_mit_iso_lib(library: str, slugs: list[str], out_dir: Path,
                       *, size: int = 256,
                       existing_ids: set[str] | None = None,
                       throttle_s: float = 0.10) -> list[dict]:
    """Fetch curated UI-primitive icons from Lucide / Phosphor / Tabler.

    All three libraries are MIT or ISC, so attribution is informational rather
    than required, but the tool still records `license` + `attribution` for
    audit hygiene. Throttle is short because these are GitHub raw fetches and
    the libraries explicitly publish CDN-friendly tags.
    """
    if library not in MIT_ISO_LIB_REGISTRY:
        raise ValueError(
            f"unknown library {library!r}; expected one of "
            f"{sorted(MIT_ISO_LIB_REGISTRY)}")
    spec = MIT_ISO_LIB_REGISTRY[library]
    out_dir.mkdir(parents=True, exist_ok=True)
    SVG_CACHE.mkdir(parents=True, exist_ok=True)
    existing_ids = set(existing_ids or set())
    icons: list[dict] = []
    prefix = _mit_iso_id_prefix(library)
    for slug in slugs:
        # Allow per-line library override: 'phosphor:gear' etc.
        if ":" in slug:
            lib2, slug = slug.split(":", 1)
            if lib2 not in MIT_ISO_LIB_REGISTRY:
                print(f"[freelib_ingest] WARN unknown library prefix {lib2!r}; "
                      f"using {library!r}")
                lib2 = library
            local_spec = MIT_ISO_LIB_REGISTRY[lib2]
            local_prefix = _mit_iso_id_prefix(lib2)
        else:
            lib2 = library
            local_spec = spec
            local_prefix = prefix
        icon_id = f"{local_prefix}{_slug_to_id(slug, prefix='').strip('_')}"
        if icon_id in existing_ids:
            print(f"[freelib_ingest] SKIP {icon_id} (already in manifest)")
            continue
        url = local_spec["url_template"].format(slug=slug)
        try:
            svg_bytes = _fetch_url(url)
        except urllib.error.HTTPError as e:
            print(f"[freelib_ingest] WARN {icon_id} HTTP {e.code} {url}")
            continue
        except Exception as e:  # noqa: BLE001
            print(f"[freelib_ingest] WARN {icon_id} {type(e).__name__}: {e}")
            continue
        cache_svg = SVG_CACHE / f"{icon_id}.svg"
        cache_svg.write_bytes(svg_bytes)
        png_path = out_dir / f"{icon_id}.png"
        png = rasterize(svg_bytes, size)
        png_path.write_bytes(png)
        existing_ids.add(icon_id)
        source_html = local_spec["source_html"].format(slug=slug)
        icons.append({
            "id": icon_id,
            "path": _record_path(png_path),
            "size_px": size,
            "backend": "freelib",
            "source": lib2,
            "source_slug": slug,
            "source_url": source_html,
            "license": local_spec["license"],
            "attribution": local_spec["attribution"],
            "display_name": slug.replace("-", " ").title(),
            "semantic_tags": _mit_iso_tags(slug),
            "rtl_mirror": slug.startswith(("chevron-", "caret-", "arrow-"))
                          and slug.endswith(("-left", "-right")),
            "min_display_px": 16,
        })
        print(f"[freelib_ingest] {icon_id:36s} ({lib2} / {local_spec['license']})")
        if throttle_s > 0:
            time.sleep(throttle_s)
    return icons


def write_mit_iso_default_picks_file(library: str, out_path: Path) -> int:
    """Materialize a default newline-list of curated picks for `library`."""
    if library not in MIT_ISO_DEFAULT_PICKS:
        raise ValueError(library)
    picks = MIT_ISO_DEFAULT_PICKS[library]
    lines = [
        f"# {library} curated UI-primitive picks (auto-generated)",
        f"# license: {MIT_ISO_LIB_REGISTRY[library]['license']}",
        "# Used by: freelib_ingest.py --source mit-iso-libs --library "
        f"{library} --slugs-file <this>",
        "",
    ] + picks
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(picks)


# ---------- Manifest I/O ---------------------------------------------------

def load_existing_manifest(path: Path) -> dict:
    if not path.exists():
        return {"set": "freelib", "size": 256, "icons": []}
    return json.loads(path.read_text(encoding="utf-8"))


def merge_manifest(manifest: dict, new_icons: list[dict]) -> dict:
    by_id = {e["id"]: e for e in manifest.get("icons", [])}
    for entry in new_icons:
        by_id[entry["id"]] = entry
    manifest["icons"] = sorted(by_id.values(), key=lambda e: e["id"])
    return manifest


def write_attribution_md(out_path: Path, icons: list[dict]) -> None:
    lines = [
        "# UI Icon Attribution",
        "",
        "Auto-generated by `pipelines/ui/freelib_ingest.py`.",
        "Lists every ingested icon and its required attribution. Attribution is",
        "required for CC-BY licensed assets; informational for MIT/ISC/CC0.",
        "",
    ]
    by_source: dict[str, list[dict]] = {}
    for e in icons:
        src = e.get("source") or "first-party"
        by_source.setdefault(src, []).append(e)
    for src in sorted(by_source):
        lines.append(f"## {src}")
        lines.append("")
        for e in sorted(by_source[src], key=lambda x: x["id"]):
            lic = e.get("license") or "first-party"
            attr = e.get("attribution")
            url = e.get("source_url") or ""
            if attr:
                lines.append(f"- `{e['id']}` — {attr}" + (f" — {url}" if url else ""))
            else:
                lines.append(f"- `{e['id']}` — {lic}" + (f" — {url}" if url else ""))
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------- CLI ------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True,
                    choices=["game-icons-net", "url-list", "mit-iso-libs"])
    ap.add_argument("--library", choices=sorted(MIT_ISO_LIB_REGISTRY),
                    default="lucide",
                    help="mit-iso-libs: which library to fetch from "
                         "(lucide=ISC, phosphor=MIT, tabler=MIT). Default lucide. "
                         "Per-slug override possible via 'phosphor:gear' lines.")
    ap.add_argument("--slugs-file", type=Path, default=None,
                    help="mit-iso-libs: newline-delimited slugs file. Defaults "
                         "to the built-in curated UI-primitive list for the "
                         "selected --library when omitted.")
    ap.add_argument("--write-default-picks", action="store_true",
                    help="mit-iso-libs: write the default curated picks for "
                         "--library to pipelines/ui/mit_iso_picks_<library>.txt "
                         "and exit. Useful as a starting point for editing.")
    ap.add_argument("--zip", type=Path, default=None,
                    help="game-icons-net: path to bulk archive zip")
    ap.add_argument("--slugs", type=str, default=None,
                    help="game-icons-net: comma-separated 'author/slug,author/slug' pairs")
    ap.add_argument("--picklist", type=Path, default=None,
                    help="game-icons-net: curated JSON picklist (per-entry id + semantic_tags). "
                         "See pipelines/ui/picklists/game_icons_core.json.")
    ap.add_argument("--limit", type=int, default=None,
                    help="picklist: take first N entries (test/curation runs)")
    ap.add_argument("--url-list", dest="url_list", type=Path, default=None,
                    help="url-list: JSON file with [{id, url, license, ...}]")
    ap.add_argument("--out", type=Path, default=ICONS_DIR)
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--pick", type=int, default=None,
                    help="game-icons-net zip: take first N icons")
    ap.add_argument("--filter", type=str, default=None,
                    help="game-icons-net zip: regex applied to entry path")
    ap.add_argument("--filter-by-list", type=Path, default=None,
                    help="game-icons-net zip: take only slugs in this newline-"
                         "delimited file (one slug per line; '#' starts a comment; "
                         "'author/slug' lines accepted, only the slug part is matched). "
                         "Combine with --filter to AND both. Useful with the curated "
                         "list at pipelines/ui/freelib_curated_slugs.txt.")
    ap.add_argument("--accept-license", action="store_true",
                    help="Required for any network fetch; acknowledges per-source license terms.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.source == "game-icons-net":
        print(GAME_ICONS_LICENSE_NOTE)

    manifest_path = args.out / "manifest.json"
    manifest = load_existing_manifest(manifest_path)
    existing_ids = {e["id"] for e in manifest.get("icons", [])}
    new_icons: list[dict] = []

    if args.source == "game-icons-net":
        if args.zip:
            allowlist = None
            if args.filter_by_list:
                if not args.filter_by_list.exists():
                    print(f"[freelib_ingest] ERROR: --filter-by-list "
                          f"{args.filter_by_list} not found", file=sys.stderr)
                    return 2
                allowlist = _load_slug_list(args.filter_by_list)
                print(f"[freelib_ingest] curated allowlist: "
                      f"{len(allowlist)} slugs from {args.filter_by_list}")
            new_icons = ingest_game_icons_zip(
                args.zip, args.out, size=args.size, pick=args.pick,
                name_filter=args.filter, slug_allowlist=allowlist,
                existing_ids=existing_ids,
                dry_run=args.dry_run)
        elif args.picklist:
            if not args.picklist.exists():
                print(f"[freelib_ingest] ERROR: picklist not found: {args.picklist}",
                      file=sys.stderr)
                return 2
            if not args.accept_license and not args.dry_run:
                print("[freelib_ingest] ERROR: --accept-license required for "
                      "network fetch (CC-BY attribution is mandatory).",
                      file=sys.stderr)
                return 2
            data = json.loads(args.picklist.read_text(encoding="utf-8"))
            items = data.get("items", data) if isinstance(data, dict) else data
            if not isinstance(items, list):
                print("[freelib_ingest] ERROR: picklist must be an array of "
                      "{author, slug, id, ...} or an object with key 'items'.",
                      file=sys.stderr)
                return 2
            if args.limit:
                items = items[:args.limit]
            if args.dry_run:
                for it in items:
                    iid = it.get("id") or _slug_to_id(it["slug"])
                    print(f"[freelib_ingest] DRY {iid:32s} ({it['author']}/{it['slug']})")
                new_icons = []
            else:
                new_icons = ingest_game_icons_picklist(
                    items, args.out, size=args.size,
                    existing_ids=existing_ids)
        elif args.slugs:
            if not args.accept_license and not args.dry_run:
                print("[freelib_ingest] ERROR: --accept-license required for "
                      "network fetch (CC-BY attribution is mandatory).",
                      file=sys.stderr)
                return 2
            pairs = []
            for token in args.slugs.split(","):
                token = token.strip()
                if not token:
                    continue
                if "/" in token:
                    a, s = token.split("/", 1)
                else:
                    print(f"[freelib_ingest] ERROR: slug '{token}' must be 'author/slug'",
                          file=sys.stderr)
                    return 2
                pairs.append((a, s))
            new_icons = ingest_game_icons_slugs(
                pairs, args.out, size=args.size, existing_ids=existing_ids)
        else:
            print("[freelib_ingest] ERROR: provide --zip <path>, --picklist <json>, "
                  "or --slugs author/slug,...", file=sys.stderr)
            return 2
    elif args.source == "url-list":
        if not args.url_list or not args.url_list.exists():
            print("[freelib_ingest] ERROR: --url-list <path> required",
                  file=sys.stderr)
            return 2
        if not args.accept_license and not args.dry_run:
            print("[freelib_ingest] ERROR: --accept-license required for "
                  "network fetch (verify per-asset license).",
                  file=sys.stderr)
            return 2
        specs = json.loads(args.url_list.read_text(encoding="utf-8"))
        if not isinstance(specs, list):
            print("[freelib_ingest] ERROR: url-list JSON must be an array of {id, url, ...}",
                  file=sys.stderr)
            return 2
        new_icons = ingest_url_list(
            specs, args.out, size=args.size, existing_ids=existing_ids)
    elif args.source == "mit-iso-libs":
        if args.write_default_picks:
            picks_path = (Path(__file__).parent /
                          f"mit_iso_picks_{args.library}.txt")
            n = write_mit_iso_default_picks_file(args.library, picks_path)
            print(f"[freelib_ingest] wrote {n} default picks for "
                  f"{args.library} -> {picks_path}")
            return 0
        if not args.accept_license and not args.dry_run:
            print(f"[freelib_ingest] ERROR: --accept-license required for "
                  f"network fetch ({args.library} = "
                  f"{MIT_ISO_LIB_REGISTRY[args.library]['license']}; "
                  "attribution is informational, license acknowledgement still required).",
                  file=sys.stderr)
            return 2
        if args.slugs_file:
            if not args.slugs_file.exists():
                print(f"[freelib_ingest] ERROR: --slugs-file {args.slugs_file} "
                      f"not found", file=sys.stderr)
                return 2
            slugs = []
            for raw in args.slugs_file.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                slugs.append(line)
        else:
            slugs = list(MIT_ISO_DEFAULT_PICKS[args.library])
            print(f"[freelib_ingest] using built-in {len(slugs)} curated "
                  f"{args.library} picks (override with --slugs-file)")
        if args.dry_run:
            for slug in slugs:
                if ":" in slug:
                    lib2, s = slug.split(":", 1)
                else:
                    lib2, s = args.library, slug
                iid = f"{_mit_iso_id_prefix(lib2)}{_slug_to_id(s, prefix='').strip('_')}"
                print(f"[freelib_ingest] DRY {iid:36s} ({lib2}/{s})")
            new_icons = []
        else:
            new_icons = ingest_mit_iso_lib(
                args.library, slugs, args.out, size=args.size,
                existing_ids=existing_ids)

    if args.dry_run:
        print(f"[freelib_ingest] dry run: {len(new_icons)} icons would be ingested")
        return 0

    manifest = merge_manifest(manifest, new_icons)
    manifest["set"] = manifest.get("set") or "freelib"
    manifest["size"] = args.size
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_attribution_md(ATTRIBUTION_MD, manifest["icons"])
    print(f"[freelib_ingest] +{len(new_icons)} new -> {manifest_path} "
          f"(total {len(manifest['icons'])})")
    print(f"[freelib_ingest] attribution -> {ATTRIBUTION_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
