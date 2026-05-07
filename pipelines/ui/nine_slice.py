"""9-slice / NinePatch generator.

Two modes:

  1. **synth** - draws procedural panels, buttons, frames, bars from primitives.
     Output: a base PNG plus `<id>.json` margin metadata for Godot's NinePatchRect.

  2. **derive** - takes an input PNG and writes the matching `<id>.json` metadata
     (margins detected from the alpha channel + a configurable inset). Used to
     turn an AI-generated panel into a real 9-slice asset.

Per Godot 4.5 NinePatchRect: corners stay fixed, edges tile/stretch, center
tiles/stretches. The `.tres` form is `NinePatchRect` with `texture` +
`patch_margin_left/top/right/bottom`. We don't write the .tres here - that's
the exporter's job; we just write a JSON sidecar with the margins.

CLI:
  python nine_slice.py button     --out ui/9slice/button.png --size 256 --margin 24
  python nine_slice.py panel      --out ui/9slice/panel.png  --size 512 --margin 32
  python nine_slice.py healthbar  --out ui/9slice/healthbar.png --size 256x32 --margin 8
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


PALETTE = {
    "panel_bg": (40, 38, 50, 235),
    "panel_border": (180, 165, 130, 255),
    "panel_inner_border": (60, 55, 75, 255),
    "button_bg": (90, 80, 70, 255),
    "button_highlight": (180, 165, 130, 255),
    "button_shadow": (40, 35, 30, 255),
    "frame_bg": (220, 200, 165, 255),
    "frame_border": (90, 60, 30, 255),
    "bar_bg": (40, 30, 30, 255),
    "bar_border": (90, 70, 50, 255),
}


def _parse_size(s: str) -> tuple[int, int]:
    if "x" in s:
        w, h = s.split("x", 1)
        return int(w), int(h)
    n = int(s)
    return n, n


def panel(size: tuple[int, int], margin: int) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # outer rounded rect
    radius = max(margin // 2, 4)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                        fill=PALETTE["panel_bg"],
                        outline=PALETTE["panel_border"], width=4)
    # inner double border
    inset = max(margin // 3, 6)
    d.rounded_rectangle([inset, inset, w - 1 - inset, h - 1 - inset],
                        radius=max(radius - inset, 2),
                        outline=PALETTE["panel_inner_border"], width=2)
    return img


def button(size: tuple[int, int], margin: int) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = max(margin // 2, 4)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                        fill=PALETTE["button_bg"],
                        outline=PALETTE["button_highlight"], width=3)
    # top highlight (1/3 of height)
    h_top = max((h - 2) // 3, 1)
    overlay = Image.new("RGBA", (w, h_top), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([2, 2, w - 3, h_top - 1], radius=max(radius - 2, 2),
                         fill=(255, 255, 255, 30))
    img.alpha_composite(overlay, (0, 1))
    # bottom shadow line
    d.line([(2, h - 3), (w - 3, h - 3)], fill=PALETTE["button_shadow"], width=1)
    return img


def frame(size: tuple[int, int], margin: int) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = max(margin // 4, 2)
    # outer wood
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                        fill=PALETTE["frame_bg"],
                        outline=PALETTE["frame_border"], width=5)
    # inner cut-out (transparent center for icon)
    inset = margin
    d.rounded_rectangle([inset, inset, w - 1 - inset, h - 1 - inset],
                        radius=max(radius - 2, 1),
                        fill=(0, 0, 0, 0),
                        outline=PALETTE["frame_border"], width=3)
    return img


def healthbar(size: tuple[int, int], margin: int) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = max(h // 4, 3)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                        fill=PALETTE["bar_bg"],
                        outline=PALETTE["bar_border"], width=3)
    # inner notch
    d.rounded_rectangle([3, 3, w - 4, h - 4], radius=max(radius - 2, 2),
                        outline=(0, 0, 0, 130), width=1)
    return img


KINDS = {
    "panel": panel,
    "button": button,
    "frame": frame,
    "healthbar": healthbar,
}


def detect_margins(img: Image.Image, alpha_threshold: int = 32) -> dict:
    """Find the smallest opaque bbox of `img`. Margins are pixels from each
    edge to the bbox - useful to seed `patch_margin_*` defaults."""
    a = img.split()[-1]
    bbox = a.point(lambda p: 255 if p > alpha_threshold else 0).getbbox()
    if not bbox:
        return {"left": 0, "top": 0, "right": 0, "bottom": 0}
    L, T, R, B = bbox
    w, h = img.size
    return {"left": L, "top": T, "right": w - R, "bottom": h - B}


def write_meta(img_path: Path, margin: int) -> None:
    """Write `<id>.json` next to the PNG. Used by the Godot exporter to
    construct NinePatchRect.tres."""
    meta = {
        "image": img_path.name,
        "patch_margin_left": margin,
        "patch_margin_top": margin,
        "patch_margin_right": margin,
        "patch_margin_bottom": margin,
    }
    img_path.with_suffix(".json").write_text(json.dumps(meta, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=list(KINDS) + ["derive"])
    ap.add_argument("--size", default="256",
                    help="WxH or single int (square). Defaults: panel 256x256, "
                         "button 256x80, healthbar 256x32, frame 128x128.")
    ap.add_argument("--margin", type=int, default=24)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--from", dest="src", type=Path, default=None,
                    help="(derive mode) input PNG.")
    ap.add_argument("--alpha-threshold", type=int, default=32)
    args = ap.parse_args()

    if args.kind == "derive":
        if args.src is None:
            raise SystemExit("derive mode requires --from <png>")
        img = Image.open(args.src).convert("RGBA")
        # Margins from alpha bbox + the user-supplied inset
        det = detect_margins(img, args.alpha_threshold)
        margin = max(args.margin, max(det.values()))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        img.save(args.out)
        write_meta(args.out, margin)
        print(f"[nine_slice] derive -> {args.out} margin={margin} (auto-detect={det})")
        return

    fn = KINDS[args.kind]
    size = _parse_size(args.size)
    img = fn(size, args.margin)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    img.save(args.out)
    write_meta(args.out, args.margin)
    print(f"[nine_slice] {args.kind} {size[0]}x{size[1]} margin={args.margin} -> {args.out}")


if __name__ == "__main__":
    main()
