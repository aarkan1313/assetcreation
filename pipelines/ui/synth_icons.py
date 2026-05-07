"""Procedural SVG-to-PNG icon generator (no GPU, no AI).

Produces simple, stylistically-consistent flat icons for game data prototypes:
sword, shield, potion, gem, scroll, key, coin, skull. Uses a palette and
simple primitive shapes (polygons, circles, rounded rects) drawn through PIL.

Each icon is 256x256 px on a transparent background. They look like flat-design
icons - good enough for 32/64/128 px display in a UI before art passes.

These are placeholders, but they validate the entire downstream path: each
icon is real, transparent, atlas-packable, and Godot-loadable as Texture2D.
The cloud generator (`openai_icons.py`) drops in to replace synth.

CLI:
  python synth_icons.py --set rpg --out ui/icons --size 256
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


# Style: muted fantasy palette. All icons share these slots so they read as a
# coherent set even with very different shapes.
PALETTE = {
    "bg": (0, 0, 0, 0),           # transparent
    "ink": (24, 22, 18, 255),     # near-black outline
    "metal": (170, 175, 185, 255),
    "metal_dark": (110, 116, 130, 255),
    "wood": (110, 80, 50, 255),
    "wood_dark": (75, 55, 35, 255),
    "leather": (130, 90, 60, 255),
    "blood": (170, 40, 40, 255),
    "potion_red": (180, 50, 60, 255),
    "potion_blue": (60, 110, 200, 255),
    "potion_green": (90, 170, 90, 255),
    "gem_blue": (90, 160, 230, 255),
    "gem_red": (220, 80, 90, 255),
    "gem_green": (110, 200, 130, 255),
    "scroll_bg": (240, 220, 175, 255),
    "scroll_dark": (180, 150, 100, 255),
    "gold": (220, 175, 70, 255),
    "gold_dark": (150, 110, 40, 255),
    "highlight": (255, 255, 255, 110),
}


def _new(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (size, size), PALETTE["bg"])
    return img, ImageDraw.Draw(img)


def _outline(draw, polygon, w=4, color=PALETTE["ink"]):
    pts = list(polygon)
    pts.append(pts[0])
    draw.line(pts, fill=color, width=w, joint="curve")


def icon_sword(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    blade = [
        (cx, int(cy - size * 0.40)),
        (cx - size * 0.05, int(cy + size * 0.10)),
        (cx + size * 0.05, int(cy + size * 0.10)),
    ]
    d.polygon(blade, fill=PALETTE["metal"])
    _outline(d, blade)
    # crossguard
    d.rounded_rectangle(
        [cx - size * 0.20, cy + size * 0.08, cx + size * 0.20, cy + size * 0.14],
        radius=int(size * 0.02), fill=PALETTE["metal_dark"], outline=PALETTE["ink"], width=4,
    )
    # grip
    d.rounded_rectangle(
        [cx - size * 0.04, cy + size * 0.14, cx + size * 0.04, cy + size * 0.32],
        radius=int(size * 0.02), fill=PALETTE["leather"], outline=PALETTE["ink"], width=4,
    )
    # pommel
    d.ellipse(
        [cx - size * 0.06, cy + size * 0.30, cx + size * 0.06, cy + size * 0.40],
        fill=PALETTE["gold"], outline=PALETTE["ink"], width=4,
    )
    # blade highlight
    h = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(h)
    hd.polygon(
        [(cx - 2, int(cy - size * 0.36)),
         (cx - size * 0.025, int(cy + size * 0.05)),
         (cx + 2, int(cy + size * 0.05)),
         (cx, int(cy - size * 0.36))],
        fill=PALETTE["highlight"],
    )
    img = Image.alpha_composite(img, h)
    return img


def icon_shield(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    pts = [
        (cx - size * 0.30, cy - size * 0.30),
        (cx + size * 0.30, cy - size * 0.30),
        (cx + size * 0.30, cy),
        (cx, cy + size * 0.35),
        (cx - size * 0.30, cy),
    ]
    d.polygon(pts, fill=PALETTE["metal"])
    _outline(d, pts, w=5)
    # boss
    d.ellipse(
        [cx - size * 0.07, cy - size * 0.07, cx + size * 0.07, cy + size * 0.07],
        fill=PALETTE["gold"], outline=PALETTE["ink"], width=4,
    )
    # diagonal stripe
    d.line(
        [cx - size * 0.25, cy - size * 0.25, cx + size * 0.25, cy + size * 0.10],
        fill=PALETTE["potion_red"], width=int(size * 0.03),
    )
    return img


def icon_potion(size: int, color_key: str = "potion_red") -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # bottle body (rounded rect)
    d.ellipse(
        [cx - size * 0.20, cy - size * 0.10, cx + size * 0.20, cy + size * 0.30],
        fill=PALETTE[color_key], outline=PALETTE["ink"], width=5,
    )
    # neck
    d.rounded_rectangle(
        [cx - size * 0.07, cy - size * 0.25, cx + size * 0.07, cy - size * 0.05],
        radius=int(size * 0.02), fill=PALETTE["metal"], outline=PALETTE["ink"], width=4,
    )
    # cork
    d.rounded_rectangle(
        [cx - size * 0.09, cy - size * 0.32, cx + size * 0.09, cy - size * 0.22],
        radius=int(size * 0.02), fill=PALETTE["wood"], outline=PALETTE["ink"], width=4,
    )
    # liquid highlight
    h = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(h)
    hd.ellipse(
        [cx - size * 0.10, cy - size * 0.04, cx - size * 0.02, cy + size * 0.08],
        fill=PALETTE["highlight"],
    )
    img = Image.alpha_composite(img, h)
    return img


def icon_gem(size: int, color_key: str = "gem_blue") -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    pts = [
        (cx, cy - size * 0.30),
        (cx + size * 0.25, cy - size * 0.05),
        (cx + size * 0.15, cy + size * 0.30),
        (cx - size * 0.15, cy + size * 0.30),
        (cx - size * 0.25, cy - size * 0.05),
    ]
    d.polygon(pts, fill=PALETTE[color_key])
    _outline(d, pts, w=5)
    # facet lines
    d.line([(cx, cy - size * 0.30), (cx, cy + size * 0.30)], fill=PALETTE["ink"], width=3)
    d.line([(cx - size * 0.25, cy - size * 0.05), (cx + size * 0.25, cy - size * 0.05)],
           fill=PALETTE["ink"], width=3)
    # highlight
    h = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(h)
    hd.polygon(
        [(cx - size * 0.05, cy - size * 0.20),
         (cx + size * 0.05, cy - size * 0.20),
         (cx + size * 0.02, cy - size * 0.08),
         (cx - size * 0.10, cy - size * 0.08)],
        fill=PALETTE["highlight"],
    )
    img = Image.alpha_composite(img, h)
    return img


def icon_scroll(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # parchment
    d.rounded_rectangle(
        [cx - size * 0.27, cy - size * 0.20, cx + size * 0.27, cy + size * 0.20],
        radius=int(size * 0.04),
        fill=PALETTE["scroll_bg"], outline=PALETTE["ink"], width=4,
    )
    # rolled ends
    d.ellipse(
        [cx - size * 0.34, cy - size * 0.22, cx - size * 0.22, cy + size * 0.22],
        fill=PALETTE["scroll_dark"], outline=PALETTE["ink"], width=4,
    )
    d.ellipse(
        [cx + size * 0.22, cy - size * 0.22, cx + size * 0.34, cy + size * 0.22],
        fill=PALETTE["scroll_dark"], outline=PALETTE["ink"], width=4,
    )
    # ink lines (3 lines of "writing")
    for i in range(3):
        y = cy - size * 0.10 + i * size * 0.10
        d.line([cx - size * 0.18, y, cx + size * 0.18, y], fill=PALETTE["ink"], width=3)
    return img


def icon_key(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # bow (the round part)
    d.ellipse(
        [cx - size * 0.30, cy - size * 0.12, cx - size * 0.06, cy + size * 0.12],
        fill=PALETTE["gold"], outline=PALETTE["ink"], width=4,
    )
    # bow hole
    d.ellipse(
        [cx - size * 0.22, cy - size * 0.04, cx - size * 0.14, cy + size * 0.04],
        fill=PALETTE["bg"], outline=PALETTE["ink"], width=3,
    )
    # shaft
    d.rectangle(
        [cx - size * 0.06, cy - size * 0.04, cx + size * 0.30, cy + size * 0.04],
        fill=PALETTE["gold"], outline=PALETTE["ink"], width=4,
    )
    # teeth
    d.rectangle(
        [cx + size * 0.20, cy + size * 0.04, cx + size * 0.26, cy + size * 0.14],
        fill=PALETTE["gold"], outline=PALETTE["ink"], width=4,
    )
    d.rectangle(
        [cx + size * 0.14, cy + size * 0.04, cx + size * 0.18, cy + size * 0.10],
        fill=PALETTE["gold"], outline=PALETTE["ink"], width=4,
    )
    return img


def icon_coin(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    d.ellipse(
        [cx - size * 0.30, cy - size * 0.30, cx + size * 0.30, cy + size * 0.30],
        fill=PALETTE["gold"], outline=PALETTE["ink"], width=5,
    )
    d.ellipse(
        [cx - size * 0.22, cy - size * 0.22, cx + size * 0.22, cy + size * 0.22],
        outline=PALETTE["gold_dark"], width=3,
    )
    # central rune (a star)
    pts = []
    for i in range(10):
        angle = -np.pi / 2 + i * np.pi / 5
        r = size * (0.16 if i % 2 == 0 else 0.07)
        pts.append((cx + r * np.cos(angle), cy + r * np.sin(angle)))
    d.polygon(pts, fill=PALETTE["gold_dark"], outline=PALETTE["ink"])
    # highlight crescent
    h = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(h)
    hd.pieslice(
        [cx - size * 0.30, cy - size * 0.30, cx + size * 0.30, cy + size * 0.30],
        start=210, end=290, fill=PALETTE["highlight"],
    )
    img = Image.alpha_composite(img, h)
    return img


def icon_axe(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # haft
    d.rounded_rectangle(
        [cx - size * 0.04, cy - size * 0.32, cx + size * 0.04, cy + size * 0.36],
        radius=int(size * 0.02), fill=PALETTE["wood"],
        outline=PALETTE["ink"], width=4,
    )
    # head (asymmetric crescent)
    pts = [
        (cx, cy - size * 0.30),
        (cx + size * 0.32, cy - size * 0.18),
        (cx + size * 0.30, cy + size * 0.05),
        (cx + size * 0.05, cy - size * 0.05),
    ]
    d.polygon(pts, fill=PALETTE["metal"])
    _outline(d, pts, w=4)
    # bind
    d.rounded_rectangle(
        [cx - size * 0.07, cy + size * 0.30, cx + size * 0.07, cy + size * 0.36],
        radius=int(size * 0.02), fill=PALETTE["leather"],
        outline=PALETTE["ink"], width=3,
    )
    return img


def icon_mace(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # haft
    d.rounded_rectangle(
        [cx - size * 0.04, cy - size * 0.05, cx + size * 0.04, cy + size * 0.36],
        radius=int(size * 0.02), fill=PALETTE["wood"],
        outline=PALETTE["ink"], width=4,
    )
    # head (knobby)
    d.ellipse(
        [cx - size * 0.18, cy - size * 0.30, cx + size * 0.18, cy - size * 0.02],
        fill=PALETTE["metal"], outline=PALETTE["ink"], width=4,
    )
    # spikes
    for ang in (-90, -45, 0, 45, 90, 135, 180, 225):
        rad = np.radians(ang)
        x0 = cx + np.cos(rad) * size * 0.13
        y0 = cy - size * 0.16 + np.sin(rad) * size * 0.13
        x1 = cx + np.cos(rad) * size * 0.20
        y1 = cy - size * 0.16 + np.sin(rad) * size * 0.20
        d.line([(x0, y0), (x1, y1)], fill=PALETTE["metal_dark"], width=4)
    return img


def icon_dagger(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    blade = [
        (cx, int(cy - size * 0.34)),
        (cx - size * 0.04, int(cy + size * 0.05)),
        (cx + size * 0.04, int(cy + size * 0.05)),
    ]
    d.polygon(blade, fill=PALETTE["metal"])
    _outline(d, blade)
    d.rounded_rectangle(
        [cx - size * 0.14, cy + size * 0.02, cx + size * 0.14, cy + size * 0.10],
        radius=int(size * 0.02), fill=PALETTE["metal_dark"],
        outline=PALETTE["ink"], width=3,
    )
    d.rounded_rectangle(
        [cx - size * 0.04, cy + size * 0.10, cx + size * 0.04, cy + size * 0.28],
        radius=int(size * 0.02), fill=PALETTE["leather"],
        outline=PALETTE["ink"], width=3,
    )
    return img


def icon_bow(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # arc (just a thick C)
    d.arc([cx - size * 0.32, cy - size * 0.34, cx + size * 0.18, cy + size * 0.34],
          start=300, end=60, fill=PALETTE["wood"], width=int(size * 0.06))
    # string
    d.line([(cx + size * 0.10, cy - size * 0.30), (cx + size * 0.10, cy + size * 0.30)],
           fill=PALETTE["ink"], width=2)
    # arrow
    d.line([(cx - size * 0.20, cy), (cx + size * 0.36, cy)],
           fill=PALETTE["wood_dark"], width=4)
    pts = [(cx + size * 0.36, cy - size * 0.06),
           (cx + size * 0.42, cy),
           (cx + size * 0.36, cy + size * 0.06)]
    d.polygon(pts, fill=PALETTE["metal"], outline=PALETTE["ink"])
    return img


def icon_staff(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    d.rounded_rectangle(
        [cx - size * 0.04, cy - size * 0.20, cx + size * 0.04, cy + size * 0.40],
        radius=int(size * 0.02), fill=PALETTE["wood"],
        outline=PALETTE["ink"], width=4,
    )
    # head: gem in claw
    pts = [
        (cx, cy - size * 0.32),
        (cx + size * 0.10, cy - size * 0.20),
        (cx, cy - size * 0.12),
        (cx - size * 0.10, cy - size * 0.20),
    ]
    d.polygon(pts, fill=PALETTE["gem_blue"], outline=PALETTE["ink"], width=3)
    return img


def icon_spear(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    d.rounded_rectangle(
        [cx - size * 0.03, cy - size * 0.22, cx + size * 0.03, cy + size * 0.40],
        radius=int(size * 0.015), fill=PALETTE["wood"],
        outline=PALETTE["ink"], width=3,
    )
    pts = [
        (cx, cy - size * 0.40),
        (cx + size * 0.08, cy - size * 0.20),
        (cx, cy - size * 0.16),
        (cx - size * 0.08, cy - size * 0.20),
    ]
    d.polygon(pts, fill=PALETTE["metal"], outline=PALETTE["ink"], width=3)
    return img


def icon_hammer(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    d.rounded_rectangle(
        [cx - size * 0.04, cy - size * 0.05, cx + size * 0.04, cy + size * 0.36],
        radius=int(size * 0.02), fill=PALETTE["wood"],
        outline=PALETTE["ink"], width=4,
    )
    d.rounded_rectangle(
        [cx - size * 0.22, cy - size * 0.24, cx + size * 0.22, cy - size * 0.02],
        radius=int(size * 0.04), fill=PALETTE["metal"],
        outline=PALETTE["ink"], width=4,
    )
    return img


def icon_warhorn(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    pts = [
        (cx - size * 0.30, cy + size * 0.18),
        (cx + size * 0.30, cy - size * 0.12),
        (cx + size * 0.36, cy + size * 0.04),
        (cx - size * 0.10, cy + size * 0.30),
    ]
    d.polygon(pts, fill=PALETTE["wood"], outline=PALETTE["ink"], width=4)
    # mouthpiece
    d.ellipse(
        [cx - size * 0.34, cy + size * 0.10, cx - size * 0.22, cy + size * 0.22],
        fill=PALETTE["gold"], outline=PALETTE["ink"], width=3,
    )
    return img


def icon_elixir(size: int) -> Image.Image:
    return icon_potion(size, color_key="potion_green")


# ---- spells / schools ---------------------------------------------------

def icon_fireball(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    d.ellipse(
        [cx - size * 0.30, cy - size * 0.30, cx + size * 0.30, cy + size * 0.30],
        fill=(220, 90, 30, 255), outline=PALETTE["ink"], width=4,
    )
    d.ellipse(
        [cx - size * 0.20, cy - size * 0.20, cx + size * 0.10, cy + size * 0.10],
        fill=(245, 200, 60, 255),
    )
    # flame tongues
    for ang in (-30, 30, 110, 200):
        rad = np.radians(ang)
        x0 = cx + np.cos(rad) * size * 0.24
        y0 = cy + np.sin(rad) * size * 0.24
        x1 = cx + np.cos(rad) * size * 0.40
        y1 = cy + np.sin(rad) * size * 0.40
        d.line([(x0, y0), (x1, y1)], fill=(220, 90, 30, 255), width=int(size * 0.05))
    return img


def icon_frostbolt(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    pts = [
        (cx, cy - size * 0.36),
        (cx + size * 0.06, cy - size * 0.10),
        (cx + size * 0.16, cy + size * 0.05),
        (cx + size * 0.04, cy + size * 0.30),
        (cx - size * 0.08, cy + size * 0.18),
        (cx - size * 0.16, cy + size * 0.05),
        (cx - size * 0.06, cy - size * 0.10),
    ]
    d.polygon(pts, fill=(160, 220, 240, 255), outline=PALETTE["ink"], width=4)
    # crystalline highlight
    d.line([(cx, cy - size * 0.36), (cx, cy + size * 0.30)], fill=(220, 240, 255, 255), width=3)
    return img


def icon_lightning(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    pts = [
        (cx - size * 0.06, cy - size * 0.36),
        (cx + size * 0.16, cy - size * 0.04),
        (cx + size * 0.04, cy - size * 0.04),
        (cx + size * 0.20, cy + size * 0.36),
        (cx - size * 0.10, cy + size * 0.06),
        (cx - size * 0.02, cy + size * 0.06),
        (cx - size * 0.18, cy - size * 0.18),
    ]
    d.polygon(pts, fill=(245, 220, 80, 255), outline=PALETTE["ink"], width=4)
    return img


def icon_shadow_bolt(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    d.ellipse(
        [cx - size * 0.30, cy - size * 0.30, cx + size * 0.30, cy + size * 0.30],
        fill=(40, 20, 70, 255), outline=PALETTE["ink"], width=4,
    )
    # tendrils
    for ang in (10, 80, 160, 230, 290):
        rad = np.radians(ang)
        x0 = cx + np.cos(rad) * size * 0.20
        y0 = cy + np.sin(rad) * size * 0.20
        x1 = cx + np.cos(rad) * size * 0.42
        y1 = cy + np.sin(rad) * size * 0.42
        d.line([(x0, y0), (x1, y1)], fill=(80, 50, 130, 255), width=int(size * 0.04))
    # core glow
    d.ellipse(
        [cx - size * 0.10, cy - size * 0.10, cx + size * 0.10, cy + size * 0.10],
        fill=(180, 120, 220, 255),
    )
    return img


def icon_nature_thorn(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # leaf base
    pts = [
        (cx - size * 0.30, cy + size * 0.10),
        (cx, cy - size * 0.30),
        (cx + size * 0.30, cy + size * 0.10),
        (cx, cy + size * 0.32),
    ]
    d.polygon(pts, fill=(80, 150, 70, 255), outline=PALETTE["ink"], width=4)
    d.line([(cx, cy - size * 0.30), (cx, cy + size * 0.32)], fill=PALETTE["ink"], width=3)
    # thorns along the lower edge
    for s_x in (-0.18, 0.0, 0.18):
        d.polygon(
            [(cx + s_x * size, cy + size * 0.20),
             (cx + s_x * size + size * 0.04, cy + size * 0.30),
             (cx + s_x * size - size * 0.04, cy + size * 0.30)],
            fill=PALETTE["ink"],
        )
    return img


def icon_arcane_orb(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    d.ellipse(
        [cx - size * 0.28, cy - size * 0.28, cx + size * 0.28, cy + size * 0.28],
        fill=(70, 40, 130, 255), outline=PALETTE["ink"], width=4,
    )
    # rune ring
    for ang in range(0, 360, 30):
        rad = np.radians(ang)
        x0 = cx + np.cos(rad) * size * 0.22
        y0 = cy + np.sin(rad) * size * 0.22
        x1 = cx + np.cos(rad) * size * 0.34
        y1 = cy + np.sin(rad) * size * 0.34
        d.line([(x0, y0), (x1, y1)], fill=(180, 130, 255, 255), width=2)
    d.ellipse(
        [cx - size * 0.12, cy - size * 0.12, cx + size * 0.12, cy + size * 0.12],
        fill=(220, 200, 255, 255),
    )
    return img


def icon_holy_light(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # sun rays
    for ang in range(0, 360, 22):
        rad = np.radians(ang)
        x0 = cx + np.cos(rad) * size * 0.16
        y0 = cy + np.sin(rad) * size * 0.16
        x1 = cx + np.cos(rad) * size * 0.36
        y1 = cy + np.sin(rad) * size * 0.36
        d.line([(x0, y0), (x1, y1)], fill=(245, 220, 110, 255), width=3)
    d.ellipse(
        [cx - size * 0.16, cy - size * 0.16, cx + size * 0.16, cy + size * 0.16],
        fill=(255, 240, 160, 255), outline=PALETTE["ink"], width=4,
    )
    return img


def icon_poison_drop(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    pts = [
        (cx, cy - size * 0.34),
        (cx + size * 0.20, cy + size * 0.10),
        (cx + size * 0.12, cy + size * 0.30),
        (cx - size * 0.12, cy + size * 0.30),
        (cx - size * 0.20, cy + size * 0.10),
    ]
    d.polygon(pts, fill=(110, 180, 90, 255), outline=PALETTE["ink"], width=4)
    # bubble highlights
    d.ellipse([cx - size * 0.10, cy - size * 0.05, cx - size * 0.04, cy + size * 0.01],
              fill=PALETTE["highlight"])
    d.ellipse([cx + size * 0.04, cy + size * 0.10, cx + size * 0.10, cy + size * 0.16],
              fill=PALETTE["highlight"])
    return img


# ---- buffs / states / chrome -------------------------------------------

def icon_haste_wing(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # sandal sole
    d.rounded_rectangle(
        [cx - size * 0.30, cy + size * 0.10, cx + size * 0.30, cy + size * 0.22],
        radius=int(size * 0.04), fill=PALETTE["leather"],
        outline=PALETTE["ink"], width=3,
    )
    # wing
    pts = [
        (cx - size * 0.20, cy - size * 0.06),
        (cx + size * 0.20, cy - size * 0.30),
        (cx + size * 0.30, cy - size * 0.10),
        (cx + size * 0.10, cy + size * 0.04),
        (cx - size * 0.10, cy + size * 0.06),
    ]
    d.polygon(pts, fill=(240, 240, 240, 255), outline=PALETTE["ink"], width=3)
    # feather lines
    for f_x, f_y in [(0.05, -0.05), (0.10, -0.13), (0.15, -0.22)]:
        d.line([(cx + f_x * size, cy + f_y * size + size * 0.05),
                (cx + f_x * size, cy + f_y * size - size * 0.05)],
               fill=PALETTE["ink"], width=2)
    return img


def icon_barrier(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    d.ellipse(
        [cx - size * 0.32, cy - size * 0.32, cx + size * 0.32, cy + size * 0.32],
        outline=(120, 200, 255, 255), width=int(size * 0.04),
    )
    d.ellipse(
        [cx - size * 0.22, cy - size * 0.22, cx + size * 0.22, cy + size * 0.22],
        outline=(180, 230, 255, 255), width=2,
    )
    # central rune - simple cross
    d.line([(cx - size * 0.14, cy), (cx + size * 0.14, cy)],
           fill=(120, 200, 255, 255), width=4)
    d.line([(cx, cy - size * 0.14), (cx, cy + size * 0.14)],
           fill=(120, 200, 255, 255), width=4)
    return img


def icon_heart_full(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # symmetrical heart
    pts = []
    for t in np.linspace(0, 2 * np.pi, 36):
        x = 16 * np.sin(t) ** 3
        y = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
        pts.append((cx + x * size * 0.018, cy + y * size * 0.018))
    d.polygon(pts, fill=(200, 50, 60, 255), outline=PALETTE["ink"])
    # highlight
    d.ellipse(
        [cx - size * 0.16, cy - size * 0.18, cx - size * 0.06, cy - size * 0.10],
        fill=PALETTE["highlight"],
    )
    return img


def icon_heart_empty(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    pts = []
    for t in np.linspace(0, 2 * np.pi, 36):
        x = 16 * np.sin(t) ** 3
        y = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
        pts.append((cx + x * size * 0.018, cy + y * size * 0.018))
    d.polygon(pts, fill=(70, 30, 30, 255), outline=PALETTE["ink"], width=4)
    return img


def icon_mana_drop(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    pts = [
        (cx, cy - size * 0.30),
        (cx + size * 0.18, cy + size * 0.06),
        (cx + size * 0.10, cy + size * 0.28),
        (cx - size * 0.10, cy + size * 0.28),
        (cx - size * 0.18, cy + size * 0.06),
    ]
    d.polygon(pts, fill=(60, 120, 220, 255), outline=PALETTE["ink"], width=4)
    d.ellipse(
        [cx - size * 0.06, cy - size * 0.10, cx, cy - size * 0.04],
        fill=PALETTE["highlight"],
    )
    return img


# ---- misc ----------------------------------------------------------------

def icon_eye(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    d.ellipse(
        [cx - size * 0.32, cy - size * 0.18, cx + size * 0.32, cy + size * 0.18],
        fill=(240, 240, 230, 255), outline=PALETTE["ink"], width=4,
    )
    d.ellipse(
        [cx - size * 0.13, cy - size * 0.13, cx + size * 0.13, cy + size * 0.13],
        fill=(60, 130, 90, 255), outline=PALETTE["ink"], width=3,
    )
    d.ellipse(
        [cx - size * 0.05, cy - size * 0.05, cx + size * 0.05, cy + size * 0.05],
        fill=PALETTE["ink"],
    )
    return img


def icon_rune(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    d.rectangle(
        [cx - size * 0.28, cy - size * 0.28, cx + size * 0.28, cy + size * 0.28],
        fill=PALETTE["wood_dark"], outline=PALETTE["ink"], width=4,
    )
    # angular glyph
    d.line([(cx - size * 0.16, cy - size * 0.18), (cx + size * 0.16, cy + size * 0.18)],
           fill=PALETTE["gold"], width=4)
    d.line([(cx - size * 0.16, cy + size * 0.18), (cx, cy)],
           fill=PALETTE["gold"], width=4)
    d.line([(cx, cy), (cx + size * 0.16, cy + size * 0.18)],
           fill=PALETTE["gold"], width=4)
    return img


def icon_footprint(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # heel
    d.ellipse(
        [cx - size * 0.16, cy + size * 0.04, cx + size * 0.16, cy + size * 0.30],
        fill=PALETTE["ink"], outline=PALETTE["ink"], width=2,
    )
    # ball
    d.ellipse(
        [cx - size * 0.20, cy - size * 0.18, cx + size * 0.20, cy + size * 0.10],
        fill=PALETTE["ink"], outline=PALETTE["ink"], width=2,
    )
    # toes
    for x_off in (-0.16, -0.06, 0.04, 0.14):
        d.ellipse(
            [cx + x_off * size - size * 0.04, cy - size * 0.32,
             cx + x_off * size + size * 0.04, cy - size * 0.20],
            fill=PALETTE["ink"],
        )
    return img


def icon_skull(size: int) -> Image.Image:
    img, d = _new(size)
    cx, cy = size // 2, size // 2
    # cranium
    d.ellipse(
        [cx - size * 0.28, cy - size * 0.30, cx + size * 0.28, cy + size * 0.10],
        fill=(230, 225, 215, 255), outline=PALETTE["ink"], width=5,
    )
    # eye sockets
    d.ellipse(
        [cx - size * 0.20, cy - size * 0.15, cx - size * 0.05, cy],
        fill=PALETTE["ink"],
    )
    d.ellipse(
        [cx + size * 0.05, cy - size * 0.15, cx + size * 0.20, cy],
        fill=PALETTE["ink"],
    )
    # nose
    pts = [(cx, cy + size * 0.02), (cx - size * 0.04, cy + size * 0.10),
           (cx + size * 0.04, cy + size * 0.10)]
    d.polygon(pts, fill=PALETTE["ink"])
    # jaw
    d.rounded_rectangle(
        [cx - size * 0.18, cy + size * 0.10, cx + size * 0.18, cy + size * 0.28],
        radius=int(size * 0.04),
        fill=(230, 225, 215, 255), outline=PALETTE["ink"], width=5,
    )
    # teeth
    for i in range(5):
        x = cx - size * 0.14 + i * size * 0.07
        d.line([(x, cy + size * 0.12), (x, cy + size * 0.26)], fill=PALETTE["ink"], width=3)
    return img


# Default icon set. Original v1 kept the first 8 IDs intact (referenced by
# game_data); v2 expands to 32 entries covering weapons, consumables, currency,
# spells (one per school), buffs/states, and chrome. Same palette across all
# so the set still reads as one.
DEFAULT_SET = [
    # --- v1 originals (game_data references these IDs; do not rename) ---
    {"id": "ico_sword",        "fn": icon_sword,   "kwargs": {}},
    {"id": "ico_shield",       "fn": icon_shield,  "kwargs": {}},
    {"id": "ico_potion_red",   "fn": icon_potion,  "kwargs": {"color_key": "potion_red"}},
    {"id": "ico_potion_blue",  "fn": icon_potion,  "kwargs": {"color_key": "potion_blue"}},
    {"id": "ico_gem_blue",     "fn": icon_gem,     "kwargs": {"color_key": "gem_blue"}},
    {"id": "ico_scroll",       "fn": icon_scroll,  "kwargs": {}},
    {"id": "ico_key",          "fn": icon_key,     "kwargs": {}},
    {"id": "ico_coin",         "fn": icon_coin,    "kwargs": {}},
    # --- v2 weapons ---
    {"id": "ico_axe",          "fn": icon_axe,     "kwargs": {}},
    {"id": "ico_mace",         "fn": icon_mace,    "kwargs": {}},
    {"id": "ico_dagger",       "fn": icon_dagger,  "kwargs": {}},
    {"id": "ico_bow",          "fn": icon_bow,     "kwargs": {}},
    {"id": "ico_staff",        "fn": icon_staff,   "kwargs": {}},
    {"id": "ico_spear",        "fn": icon_spear,   "kwargs": {}},
    {"id": "ico_hammer",       "fn": icon_hammer,  "kwargs": {}},
    {"id": "ico_warhorn",      "fn": icon_warhorn, "kwargs": {}},
    # --- v2 consumables / gems ---
    {"id": "ico_potion_green", "fn": icon_potion,  "kwargs": {"color_key": "potion_green"}},
    {"id": "ico_elixir",       "fn": icon_elixir,  "kwargs": {}},
    {"id": "ico_gem_red",      "fn": icon_gem,     "kwargs": {"color_key": "gem_red"}},
    {"id": "ico_gem_green",    "fn": icon_gem,     "kwargs": {"color_key": "gem_green"}},
    # --- v2 spells (one per school in the game_data Ability schema) ---
    {"id": "ico_fireball",     "fn": icon_fireball,     "kwargs": {}},
    {"id": "ico_frostbolt",    "fn": icon_frostbolt,    "kwargs": {}},
    {"id": "ico_lightning",    "fn": icon_lightning,    "kwargs": {}},
    {"id": "ico_shadow_bolt",  "fn": icon_shadow_bolt,  "kwargs": {}},
    {"id": "ico_nature_thorn", "fn": icon_nature_thorn, "kwargs": {}},
    {"id": "ico_arcane_orb",   "fn": icon_arcane_orb,   "kwargs": {}},
    {"id": "ico_holy_light",   "fn": icon_holy_light,   "kwargs": {}},
    {"id": "ico_poison_drop",  "fn": icon_poison_drop,  "kwargs": {}},
    # --- v2 buffs / chrome ---
    {"id": "ico_haste_wing",   "fn": icon_haste_wing,   "kwargs": {}},
    {"id": "ico_barrier",      "fn": icon_barrier,      "kwargs": {}},
    {"id": "ico_heart_full",   "fn": icon_heart_full,   "kwargs": {}},
    {"id": "ico_heart_empty",  "fn": icon_heart_empty,  "kwargs": {}},
    {"id": "ico_mana_drop",    "fn": icon_mana_drop,    "kwargs": {}},
    {"id": "ico_skull",        "fn": icon_skull,        "kwargs": {}},
    {"id": "ico_eye",          "fn": icon_eye,          "kwargs": {}},
    {"id": "ico_rune",         "fn": icon_rune,         "kwargs": {}},
    {"id": "ico_footprint",    "fn": icon_footprint,    "kwargs": {}},
]


def render_set(set_name: str, size: int, out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    icons = []
    for spec in DEFAULT_SET:
        img = spec["fn"](size, **spec["kwargs"])
        path = out_dir / f"{spec['id']}.png"
        img.save(path)
        icons.append({
            "id": spec["id"],
            "path": str(path.relative_to(Path(r"D:\assets")).as_posix()),
            "size_px": size,
            "backend": "synth",
        })
    return icons


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="rpg", help="Set name (manifest tag only)")
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--out", type=Path, default=Path(r"D:\assets\ui\icons"))
    args = ap.parse_args()

    icons = render_set(args.set, args.size, args.out)
    manifest_path = args.out / "manifest.json"
    manifest_path.write_text(json.dumps({
        "set": args.set,
        "size": args.size,
        "icons": icons,
    }, indent=2))
    print(f"[synth_icons] {len(icons)} icons -> {args.out}/")
    for i in icons:
        print(f"  {i['id']:18s} {i['path']}")


if __name__ == "__main__":
    main()
