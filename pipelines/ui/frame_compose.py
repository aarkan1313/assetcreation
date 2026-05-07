"""Faction-themed 9-slice frame composer.

Per research D §7: highest visual-variety leverage. Composes:

  base 9-slice  +  ornament overlays  +  palette JSON  ->  N visual variants

Slot-compatible with the existing `nine_slice.py` contract: each output writes
`<id>.png` plus `<id>.json` (patch_margin_*), so `pack_atlas.py` and
`export_godot.py` consume them unchanged.

Bases:
  panel, button, frame, healthbar      (re-used from nine_slice.py shapes,
                                        but redrawn here against a faction palette)

Ornaments (procedural PIL):
  corners:  none, filigree, brackets, gem, scrollwork
  edges:    none, beads, ridge

Palette JSON shape:
  {
    "id": "verdant_court",
    "metal":   "#a89060",
    "metal_dark": "#5a4a30",
    "ink":     "#1a160c",
    "accent":  "#7cb342",
    "wood":    "#5b3a1c",
    "bg":      "#1c2418ee",
    "highlight": "#ffffff44"
  }

Manifest: writes `ui/9slice/frames_manifest.json` listing every variant
{id, base, faction, palette_id, ornament_corner, ornament_edge}.

CLI:
  # Single variant from a palette file
  python frame_compose.py --base panel --palette palettes/verdant_court.json \
      --corner filigree --edge ridge --id panel_verdant_court \
      --out D:/assets/ui/9slice/panel_verdant_court.png

  # Sweep: all bases x all palettes (default ornament pairings) — best path
  python frame_compose.py --sweep --palettes palettes/ --out-dir D:/assets/ui/9slice
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(r"D:\assets")
SLICE_DIR = ASSETS / "ui" / "9slice"
PALETTE_DIR = ASSETS / "ui" / "palettes"
MANIFEST_PATH = SLICE_DIR / "frames_manifest.json"


# ---------- Palette --------------------------------------------------------

DEFAULT_PALETTE = {
    "id": "default",
    "metal":      "#a89060",
    "metal_dark": "#5a4a30",
    "ink":        "#1a160c",
    "accent":     "#7cb342",
    "wood":       "#5b3a1c",
    "bg":         "#1c2418ee",
    "highlight":  "#ffffff44",
}


def _hex_to_rgba(c: str) -> tuple[int, int, int, int]:
    c = c.lstrip("#")
    if len(c) == 6:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return (r, g, b, 255)
    if len(c) == 8:
        r, g, b, a = (int(c[0:2], 16), int(c[2:4], 16),
                      int(c[4:6], 16), int(c[6:8], 16))
        return (r, g, b, a)
    raise ValueError(f"bad hex color {c!r}; want #RRGGBB or #RRGGBBAA")


def palette_rgba(p: dict) -> dict:
    return {k: _hex_to_rgba(v) for k, v in p.items() if k != "id"}


# ---------- Bases (faction-palette aware) ---------------------------------

def base_panel(size: tuple[int, int], margin: int, p: dict) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = max(margin // 2, 4)
    # outer fill + metal border
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                        fill=p["bg"], outline=p["metal"], width=4)
    # inner ink-tone double border
    inset = max(margin // 3, 6)
    d.rounded_rectangle([inset, inset, w - 1 - inset, h - 1 - inset],
                        radius=max(radius - inset, 2),
                        outline=p["metal_dark"], width=2)
    return img


def base_button(size: tuple[int, int], margin: int, p: dict) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = max(margin // 2, 4)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                        fill=p["wood"], outline=p["metal"], width=3)
    h_top = max((h - 2) // 3, 1)
    overlay = Image.new("RGBA", (w, h_top), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([2, 2, w - 3, h_top - 1],
                         radius=max(radius - 2, 2), fill=p["highlight"])
    img.alpha_composite(overlay, (0, 1))
    d.line([(2, h - 3), (w - 3, h - 3)], fill=p["metal_dark"], width=1)
    return img


def base_frame(size: tuple[int, int], margin: int, p: dict) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = max(margin // 4, 2)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                        fill=p["wood"], outline=p["metal_dark"], width=5)
    inset = margin
    d.rounded_rectangle([inset, inset, w - 1 - inset, h - 1 - inset],
                        radius=max(radius - 2, 1),
                        fill=(0, 0, 0, 0), outline=p["metal"], width=3)
    return img


def base_healthbar(size: tuple[int, int], margin: int, p: dict) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = max(h // 4, 3)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                        fill=p["ink"], outline=p["metal"], width=3)
    d.rounded_rectangle([3, 3, w - 4, h - 4], radius=max(radius - 2, 2),
                        outline=p["metal_dark"], width=1)
    return img


BASES = {
    "panel":     {"fn": base_panel,     "default_size": (256, 256), "default_margin": 24},
    "button":    {"fn": base_button,    "default_size": (256, 80),  "default_margin": 18},
    "frame":     {"fn": base_frame,     "default_size": (192, 192), "default_margin": 24},
    "healthbar": {"fn": base_healthbar, "default_size": (256, 32),  "default_margin": 8},
}


# ---------- Ornaments ------------------------------------------------------

def _draw_filigree_corner(draw: ImageDraw.ImageDraw, x: int, y: int,
                          size: int, color: tuple, mirror_x: bool = False,
                          mirror_y: bool = False) -> None:
    # A simple scrollwork: arc + two leafy curves. Drawn into a `size`x`size`
    # patch anchored at (x, y).
    sgn_x = -1 if mirror_x else 1
    sgn_y = -1 if mirror_y else 1
    cx = x + (size if mirror_x else 0)
    cy = y + (size if mirror_y else 0)

    def P(dx, dy):
        return (cx + sgn_x * dx, cy + sgn_y * dy)

    # primary arc - PIL.ImageDraw.arc requires ascending bbox coords.
    p1 = P(2, 2)
    p2 = P(size, size)
    bbox = [min(p1[0], p2[0]), min(p1[1], p2[1]),
            max(p1[0], p2[0]), max(p1[1], p2[1])]
    # Pick a 90° arc quadrant facing inward depending on which corner this is.
    if not mirror_x and not mirror_y:
        arc_start, arc_end = 0, 90       # top-left -> arc opens into ↘
    elif mirror_x and not mirror_y:
        arc_start, arc_end = 90, 180     # top-right -> ↙
    elif not mirror_x and mirror_y:
        arc_start, arc_end = 270, 360    # bottom-left -> ↗
    else:
        arc_start, arc_end = 180, 270    # bottom-right -> ↖
    draw.arc(bbox, start=arc_start, end=arc_end, fill=color, width=3)
    # inner leaf curves
    for r in (size * 0.55, size * 0.75):
        n = 8
        prev = None
        for i in range(n + 1):
            a = math.radians(180 + (90 * i / n))
            px = cx + sgn_x * (r + 4 * math.sin(3 * a)) * abs(math.cos(a))
            py = cy + sgn_y * (r + 4 * math.sin(3 * a)) * abs(math.sin(a))
            if prev is not None:
                draw.line([prev, (px, py)], fill=color, width=2)
            prev = (px, py)


def _draw_brackets_corner(draw: ImageDraw.ImageDraw, x: int, y: int,
                          size: int, color: tuple, mirror_x: bool = False,
                          mirror_y: bool = False) -> None:
    sgn_x = -1 if mirror_x else 1
    sgn_y = -1 if mirror_y else 1
    cx = x + (size if mirror_x else 0)
    cy = y + (size if mirror_y else 0)
    # L-shape with two stubs
    draw.line([(cx, cy), (cx + sgn_x * size, cy)], fill=color, width=4)
    draw.line([(cx, cy), (cx, cy + sgn_y * size)], fill=color, width=4)
    draw.line([(cx + sgn_x * size, cy), (cx + sgn_x * size, cy + sgn_y * (size // 4))],
              fill=color, width=4)
    draw.line([(cx, cy + sgn_y * size), (cx + sgn_x * (size // 4), cy + sgn_y * size)],
              fill=color, width=4)


def _draw_gem_corner(draw: ImageDraw.ImageDraw, x: int, y: int,
                     size: int, color: tuple, accent: tuple,
                     mirror_x: bool = False, mirror_y: bool = False) -> None:
    sgn_x = -1 if mirror_x else 1
    sgn_y = -1 if mirror_y else 1
    cx = x + (size // 2 if not mirror_x else size // 2)
    cy = y + (size // 2 if not mirror_y else size // 2)
    if mirror_x:
        cx = x + size - size // 2
    if mirror_y:
        cy = y + size - size // 2
    r = max(size // 5, 4)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent, outline=color, width=2)
    # tiny radial spokes
    for ang in (0, 90, 180, 270):
        rad = math.radians(ang)
        x2 = cx + int(math.cos(rad) * r * 1.4)
        y2 = cy + int(math.sin(rad) * r * 1.4)
        draw.line([(cx, cy), (x2, y2)], fill=color, width=2)


def _draw_scrollwork_corner(draw: ImageDraw.ImageDraw, x: int, y: int,
                            size: int, color: tuple, mirror_x: bool = False,
                            mirror_y: bool = False) -> None:
    sgn_x = -1 if mirror_x else 1
    sgn_y = -1 if mirror_y else 1
    cx = x + (size if mirror_x else 0)
    cy = y + (size if mirror_y else 0)
    # spiral
    n = 24
    prev = None
    for i in range(n + 1):
        t = i / n
        ang = math.radians(180 + 270 * t)
        r = (size * 0.6) * (1.0 - t * 0.7)
        px = cx + sgn_x * (size * 0.1 + r * (math.cos(ang) + 1) * 0.5)
        py = cy + sgn_y * (size * 0.1 + r * (math.sin(ang) + 1) * 0.5)
        if prev is not None:
            draw.line([prev, (px, py)], fill=color, width=2)
        prev = (px, py)


def _draw_chains_corner(draw: ImageDraw.ImageDraw, x: int, y: int,
                        size: int, color: tuple, mirror_x: bool = False,
                        mirror_y: bool = False) -> None:
    """Two diagonal chains of small ovals running into the corner."""
    sgn_x = -1 if mirror_x else 1
    sgn_y = -1 if mirror_y else 1
    cx = x + (size if mirror_x else 0)
    cy = y + (size if mirror_y else 0)
    # Two parallel rows of links along the diagonal
    n_links = 5
    link_w = max(size // 8, 4)
    link_h = max(size // 14, 3)
    for k in range(n_links):
        t = k / max(n_links - 1, 1)
        # walk along the diagonal from corner inward
        dx = sgn_x * size * 0.15 * (k + 1)
        dy = sgn_y * size * 0.15 * (k + 1)
        ox = cx + dx
        oy = cy + dy
        # alternate orientation per link so it reads as chain not dotted line
        if k % 2 == 0:
            bbox = [ox - link_w / 2, oy - link_h / 2,
                    ox + link_w / 2, oy + link_h / 2]
        else:
            bbox = [ox - link_h / 2, oy - link_w / 2,
                    ox + link_h / 2, oy + link_w / 2]
        draw.ellipse(bbox, outline=color, width=2)


def _draw_runes_corner(draw: ImageDraw.ImageDraw, x: int, y: int,
                       size: int, color: tuple, mirror_x: bool = False,
                       mirror_y: bool = False) -> None:
    """Three small angular runes along the inside of the corner.

    Runes are pseudo-Futhark-shaped: a vertical with two diagonal strokes.
    Deterministic per-corner so faction palettes stay consistent across reruns.
    """
    sgn_x = -1 if mirror_x else 1
    sgn_y = -1 if mirror_y else 1
    cx = x + (size if mirror_x else 0)
    cy = y + (size if mirror_y else 0)
    rune_h = max(size // 5, 6)
    pad = max(size // 8, 3)
    for k in range(3):
        # Stagger 3 runes along the corner's inner diagonal
        ox = cx + sgn_x * (pad + size * 0.18 * (k + 1))
        oy = cy + sgn_y * (pad + size * 0.18 * (k + 1))
        # Vertical stroke
        draw.line([(ox, oy), (ox, oy + sgn_y * rune_h)], fill=color, width=2)
        # Top-left diagonal hash (the rune-defining bar)
        bar_len = rune_h * 0.55
        draw.line([
            (ox, oy + sgn_y * rune_h * 0.20),
            (ox + sgn_x * bar_len, oy + sgn_y * (rune_h * 0.20 + bar_len * 0.5)),
        ], fill=color, width=2)
        # Mid hash for the third rune (variation)
        if k == 2:
            draw.line([
                (ox, oy + sgn_y * rune_h * 0.55),
                (ox + sgn_x * bar_len * 0.7,
                 oy + sgn_y * (rune_h * 0.55 + bar_len * 0.35)),
            ], fill=color, width=2)


def _draw_vines_corner(draw: ImageDraw.ImageDraw, x: int, y: int,
                       size: int, color: tuple, mirror_x: bool = False,
                       mirror_y: bool = False) -> None:
    """A creeping vine: sinusoidal stem along the corner, with leaf-blobs."""
    sgn_x = -1 if mirror_x else 1
    sgn_y = -1 if mirror_y else 1
    cx = x + (size if mirror_x else 0)
    cy = y + (size if mirror_y else 0)
    n = 30
    prev = None
    leaf_at = (n // 4, n // 2, 3 * n // 4)
    for i in range(n + 1):
        t = i / n
        # Sinusoidal stem walking diagonally with side-to-side waver
        wave = 0.10 * size * math.sin(4.5 * math.pi * t)
        u = sgn_x * (size * 0.20 + size * 0.6 * t + wave * 0.5)
        v = sgn_y * (size * 0.20 + size * 0.6 * t - wave * 0.5)
        px = cx + u
        py = cy + v
        if prev is not None:
            draw.line([prev, (px, py)], fill=color, width=2)
        if i in leaf_at:
            r = max(size // 16, 3)
            draw.ellipse([px - r, py - r, px + r, py + r],
                         fill=color, outline=color)
        prev = (px, py)


def _draw_fangs_corner(draw: ImageDraw.ImageDraw, x: int, y: int,
                       size: int, color: tuple, mirror_x: bool = False,
                       mirror_y: bool = False) -> None:
    """A row of small triangular fangs pointing inward from the corner.

    Aggressive ornament for faction frames that need visual edge (e.g. ashen_pact).
    """
    sgn_x = -1 if mirror_x else 1
    sgn_y = -1 if mirror_y else 1
    cx = x + (size if mirror_x else 0)
    cy = y + (size if mirror_y else 0)
    # Fangs along the top + left interior edges of the corner patch
    n_fangs = 4
    fang_w = max(size // 10, 4)
    fang_h = max(size // 6, 6)
    # Top edge fangs (pointing down/inward)
    for k in range(n_fangs):
        ox = cx + sgn_x * (size * 0.15 + k * fang_w * 1.2)
        oy = cy
        draw.polygon([
            (ox, oy),
            (ox + sgn_x * fang_w, oy),
            (ox + sgn_x * fang_w * 0.5, oy + sgn_y * fang_h),
        ], fill=color, outline=color)
    # Left edge fangs (pointing right/inward)
    for k in range(n_fangs):
        ox = cx
        oy = cy + sgn_y * (size * 0.15 + k * fang_w * 1.2)
        draw.polygon([
            (ox, oy),
            (ox, oy + sgn_y * fang_w),
            (ox + sgn_x * fang_h, oy + sgn_y * fang_w * 0.5),
        ], fill=color, outline=color)


def _draw_edge_beads(draw: ImageDraw.ImageDraw, length: int, x: int, y: int,
                     horiz: bool, color: tuple, accent: tuple) -> None:
    n = max(length // 18, 2)
    for i in range(n):
        if horiz:
            cx_, cy_ = x + (i + 0.5) * length / n, y
        else:
            cx_, cy_ = x, y + (i + 0.5) * length / n
        r = 3
        draw.ellipse([cx_ - r, cy_ - r, cx_ + r, cy_ + r],
                     fill=accent, outline=color, width=1)


def _draw_edge_ridge(draw: ImageDraw.ImageDraw, length: int, x: int, y: int,
                     horiz: bool, color: tuple) -> None:
    if horiz:
        draw.line([(x + 6, y), (x + length - 6, y)], fill=color, width=2)
    else:
        draw.line([(x, y + 6), (x, y + length - 6)], fill=color, width=2)


CORNER_DRAWERS = {
    "filigree":   _draw_filigree_corner,
    "brackets":   _draw_brackets_corner,
    "gem":        _draw_gem_corner,        # needs accent argument
    "scrollwork": _draw_scrollwork_corner,
    "chains":     _draw_chains_corner,
    "runes":      _draw_runes_corner,
    "vines":      _draw_vines_corner,
    "fangs":      _draw_fangs_corner,
    "none":       None,
}


# Recraft-replacement hints (informational; consumed by future ornament-as-SVG
# work). Each ornament name maps to a Recraft V3 prompt that produces a vector
# alternative when set-style consistency matters more than determinism. These
# are NOT used at frame-compose time; they're a docstring slot the
# ui_plan_recraft_set could consume later.
RECRAFT_REPLACEMENT_HINTS = {
    "filigree":  "ornate baroque corner filigree, swirling acanthus leaves, "
                 "engraved silver thin line, transparent background, vector",
    "brackets":  "minimalist L-shaped corner bracket, two thin parallel lines, "
                 "vector silhouette, transparent background",
    "gem":       "single faceted gemstone in metal setting at corner, four "
                 "radial spokes, vector silhouette, transparent background",
    "scrollwork":"ornate scrollwork spiral corner ornament, baroque, "
                 "single line vector, transparent background",
    "chains":    "two diagonal rows of small chain links running into corner, "
                 "thin black line vector, transparent background",
    "runes":     "three angular Futhark runes carved along corner, two diagonal "
                 "strokes per rune, thin black line vector, transparent background",
    "vines":     "creeping vine with three small leaf blobs running into "
                 "corner, organic sinuous stem, thin black line vector, "
                 "transparent background",
    "fangs":     "row of small triangular fangs along corner edges pointing "
                 "inward, aggressive sawtooth pattern, vector silhouette, "
                 "transparent background",
}


def apply_ornaments(img: Image.Image, p: dict, margin: int,
                    corner: str = "filigree", edge: str = "none") -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    drw = ImageDraw.Draw(overlay)
    w, h = img.size
    # Corners — sized to match the 9-slice outer margin so they live entirely
    # in the corner patches, leaving the stretchable edges/center untouched.
    cs = max(margin, 8)
    draw = CORNER_DRAWERS.get(corner)
    if draw is not None:
        if corner == "gem":
            for x, y, mx, my in (
                (2, 2, False, False),
                (w - cs - 2, 2, True, False),
                (2, h - cs - 2, False, True),
                (w - cs - 2, h - cs - 2, True, True),
            ):
                draw(drw, x, y, cs, p["metal"], p["accent"], mx, my)
        else:
            for x, y, mx, my in (
                (2, 2, False, False),
                (w - cs - 2, 2, True, False),
                (2, h - cs - 2, False, True),
                (w - cs - 2, h - cs - 2, True, True),
            ):
                draw(drw, x, y, cs, p["metal"], mx, my)

    # Edges — tile within the stretchable bands. Keep clear of corner zones.
    if edge in ("beads", "ridge"):
        edge_color = p["metal"]
        accent_color = p["accent"]
        # top
        if edge == "beads":
            _draw_edge_beads(drw, w - 2 * cs - 4, cs + 2, cs // 2, True,
                             edge_color, accent_color)
            _draw_edge_beads(drw, w - 2 * cs - 4, cs + 2, h - cs // 2, True,
                             edge_color, accent_color)
            _draw_edge_beads(drw, h - 2 * cs - 4, cs // 2, cs + 2, False,
                             edge_color, accent_color)
            _draw_edge_beads(drw, h - 2 * cs - 4, w - cs // 2, cs + 2, False,
                             edge_color, accent_color)
        else:
            _draw_edge_ridge(drw, w - 2 * cs - 4, cs + 2, cs // 2, True, edge_color)
            _draw_edge_ridge(drw, w - 2 * cs - 4, cs + 2, h - cs // 2, True, edge_color)
            _draw_edge_ridge(drw, h - 2 * cs - 4, cs // 2, cs + 2, False, edge_color)
            _draw_edge_ridge(drw, h - 2 * cs - 4, w - cs // 2, cs + 2, False, edge_color)

    # Subtle inner shadow on the bg fill so ornaments read crisper
    return Image.alpha_composite(img, overlay)


# ---------- Compose --------------------------------------------------------

def compose(base: str, palette: dict, corner: str, edge: str,
            size: tuple[int, int] | None = None,
            margin: int | None = None) -> tuple[Image.Image, int]:
    if base not in BASES:
        raise ValueError(f"unknown base {base!r}; valid: {sorted(BASES)}")
    spec = BASES[base]
    sz = size or spec["default_size"]
    mg = margin if margin is not None else spec["default_margin"]
    p = palette_rgba(palette)
    img = spec["fn"](sz, mg, p)
    img = apply_ornaments(img, p, mg, corner=corner, edge=edge)
    return img, mg


def write_outputs(img: Image.Image, margin: int, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    meta = {
        "image": out_path.name,
        "patch_margin_left":   margin,
        "patch_margin_top":    margin,
        "patch_margin_right":  margin,
        "patch_margin_bottom": margin,
    }
    out_path.with_suffix(".json").write_text(json.dumps(meta, indent=2),
                                             encoding="utf-8")


# ---------- Default palettes (4 factions) ---------------------------------

DEFAULT_FACTION_PALETTES = [
    {
        "id": "verdant_court",
        "metal":      "#9caf6a", "metal_dark": "#4d5a2c",
        "ink":        "#10180a",
        "accent":     "#d2b85a",
        "wood":       "#3b2c18",
        "bg":         "#16241aee",
        "highlight":  "#ffffff44",
    },
    {
        "id": "ember_legion",
        "metal":      "#c46a3a", "metal_dark": "#5a2810",
        "ink":        "#180c08",
        "accent":     "#f7d04a",
        "wood":       "#3a1c10",
        "bg":         "#241612ee",
        "highlight":  "#ffffff44",
    },
    {
        "id": "tide_bound",
        "metal":      "#7ac1d6", "metal_dark": "#234a5e",
        "ink":        "#0a1822",
        "accent":     "#cdebff",
        "wood":       "#1d2c3a",
        "bg":         "#101e2cee",
        "highlight":  "#ffffff55",
    },
    {
        "id": "ashen_pact",
        "metal":      "#a59ea6", "metal_dark": "#3a3236",
        "ink":        "#100c10",
        "accent":     "#a25cff",
        "wood":       "#241820",
        "bg":         "#171318ee",
        "highlight":  "#ffffff44",
    },
]


# Default ornament pairings per element. Keeps the sweep deterministic and
# gives panels heavier ornament than buttons.
DEFAULT_PAIRINGS = {
    "panel":     {"corner": "filigree",   "edge": "ridge"},
    "button":    {"corner": "brackets",   "edge": "none"},
    "frame":     {"corner": "scrollwork", "edge": "beads"},
    "healthbar": {"corner": "none",       "edge": "ridge"},
}


# Faction-signature ornament style — each faction's "hero" panel uses this
# ornament instead of the default. Drives a second sweep that produces one
# `panel_<faction>_signature.png` per faction so v3 reviewers can spot-check
# how the new ornaments (chains/runes/vines/fangs) read against each palette.
FACTION_SIGNATURE_ORNAMENT = {
    "verdant_court": {"corner": "vines",  "edge": "beads"},
    "ember_legion":  {"corner": "fangs",  "edge": "ridge"},
    "tide_bound":    {"corner": "runes",  "edge": "beads"},
    "ashen_pact":    {"corner": "chains", "edge": "none"},
}


def write_default_palettes(palette_dir: Path) -> list[dict]:
    palette_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for p in DEFAULT_FACTION_PALETTES:
        out = palette_dir / f"{p['id']}.json"
        out.write_text(json.dumps(p, indent=2), encoding="utf-8")
        written.append(p)
    return written


def load_palettes(palette_dir: Path) -> list[dict]:
    return [
        json.loads(f.read_text(encoding="utf-8"))
        for f in sorted(palette_dir.glob("*.json"))
    ]


# ---------- Sweep ---------------------------------------------------------

def sweep(palettes: list[dict], out_dir: Path,
          bases: list[str] | None = None,
          pairings: dict | None = None) -> list[dict]:
    bases = bases or list(BASES)
    pairings = pairings or DEFAULT_PAIRINGS
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    for p in palettes:
        for b in bases:
            pair = pairings.get(b, {"corner": "none", "edge": "none"})
            img, mg = compose(b, p, pair["corner"], pair["edge"])
            stem = f"{b}_{p['id']}"
            out_path = out_dir / f"{stem}.png"
            write_outputs(img, mg, out_path)
            entries.append({
                "id": stem,
                "base": b,
                "faction": p["id"],
                "palette_id": p["id"],
                "ornament_corner": pair["corner"],
                "ornament_edge": pair["edge"],
                "size_px": list(img.size),
                "margin": mg,
                "path": f"ui/9slice/{out_path.name}",
            })
            print(f"[frame_compose] {stem:36s} {pair['corner']}/{pair['edge']}")
    return entries


def write_manifest(entries: list[dict], path: Path = MANIFEST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"frames": entries}, indent=2), encoding="utf-8")


# ---------- CLI ------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", choices=list(BASES) + ["sweep"], default=None)
    ap.add_argument("--palette", type=Path, default=None,
                    help="JSON palette file (single-variant mode)")
    ap.add_argument("--corner", choices=list(CORNER_DRAWERS), default="filigree")
    ap.add_argument("--edge",   choices=["none", "beads", "ridge"], default="none")
    ap.add_argument("--id", type=str, default=None,
                    help="Asset id; default <base>_<palette.id>")
    ap.add_argument("--size", type=str, default=None,
                    help="WxH override (e.g. 256x80)")
    ap.add_argument("--margin", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None,
                    help="Single-variant output PNG path")
    ap.add_argument("--sweep", action="store_true",
                    help="Write all bases x all palettes; ignores --base/--palette")
    ap.add_argument("--palettes", type=Path, default=PALETTE_DIR,
                    help="Directory of palette JSON files for --sweep")
    ap.add_argument("--out-dir", type=Path, default=SLICE_DIR,
                    help="Output directory for --sweep")
    ap.add_argument("--write-default-palettes", action="store_true",
                    help="Write the 4 default faction palettes to --palettes "
                         "and exit")
    ap.add_argument("--signatures", action="store_true",
                    help="Write one 'signature' panel per faction using the "
                         "FACTION_SIGNATURE_ORNAMENT mapping (chains/runes/"
                         "vines/fangs). Output: panel_<faction>_signature.png "
                         "per faction; merges into frames_manifest.json.")
    args = ap.parse_args()

    if args.write_default_palettes:
        wrote = write_default_palettes(args.palettes)
        print(f"[frame_compose] wrote {len(wrote)} default palettes -> {args.palettes}")
        return 0

    if args.signatures:
        if not args.palettes.exists() or not list(args.palettes.glob("*.json")):
            write_default_palettes(args.palettes)
        palettes = load_palettes(args.palettes)
        entries: list[dict] = []
        for p in palettes:
            sig = FACTION_SIGNATURE_ORNAMENT.get(p["id"])
            if not sig:
                continue
            img, mg = compose("panel", p, sig["corner"], sig["edge"])
            stem = f"panel_{p['id']}_signature"
            out_path = args.out_dir / f"{stem}.png"
            write_outputs(img, mg, out_path)
            entries.append({
                "id": stem,
                "base": "panel",
                "faction": p["id"],
                "palette_id": p["id"],
                "ornament_corner": sig["corner"],
                "ornament_edge": sig["edge"],
                "size_px": list(img.size),
                "margin": mg,
                "path": f"ui/9slice/{out_path.name}",
                "signature": True,
            })
            print(f"[frame_compose] {stem:42s} {sig['corner']}/{sig['edge']}")
        # Merge into manifest (don't clobber other sweep entries).
        existing = []
        if MANIFEST_PATH.exists():
            existing = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("frames", [])
        by_id = {e["id"]: e for e in existing}
        for e in entries:
            by_id[e["id"]] = e
        write_manifest(sorted(by_id.values(), key=lambda x: x["id"]))
        print(f"[frame_compose] signatures wrote {len(entries)} variants -> {args.out_dir}")
        return 0

    if args.sweep:
        if not args.palettes.exists() or not list(args.palettes.glob("*.json")):
            print(f"[frame_compose] no palettes in {args.palettes}; "
                  "writing defaults first.")
            write_default_palettes(args.palettes)
        palettes = load_palettes(args.palettes)
        entries = sweep(palettes, args.out_dir)
        # Merge into existing manifest if present (don't clobber prior single-variant entries).
        existing = []
        if MANIFEST_PATH.exists():
            existing = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("frames", [])
        by_id = {e["id"]: e for e in existing}
        for e in entries:
            by_id[e["id"]] = e
        write_manifest(sorted(by_id.values(), key=lambda x: x["id"]))
        print(f"[frame_compose] sweep wrote {len(entries)} variants -> {args.out_dir}")
        print(f"[frame_compose] manifest -> {MANIFEST_PATH}")
        return 0

    # Single variant
    if args.base is None or args.base == "sweep":
        print("[frame_compose] need --base <panel|button|frame|healthbar> "
              "or --sweep", file=__import__("sys").stderr)
        return 2
    palette = (json.loads(args.palette.read_text(encoding="utf-8"))
               if args.palette and args.palette.exists() else DEFAULT_PALETTE)
    size = None
    if args.size:
        if "x" in args.size:
            w, h = args.size.split("x", 1)
            size = (int(w), int(h))
        else:
            n = int(args.size); size = (n, n)
    img, mg = compose(args.base, palette, args.corner, args.edge,
                      size=size, margin=args.margin)
    iid = args.id or f"{args.base}_{palette.get('id', 'default')}"
    out_path = args.out or (SLICE_DIR / f"{iid}.png")
    write_outputs(img, mg, out_path)
    print(f"[frame_compose] {iid} {args.corner}/{args.edge} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
