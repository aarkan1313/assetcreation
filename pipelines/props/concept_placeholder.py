"""Procedural concept placeholder — exercises Hunyuan3D / Trellis2 plumbing
when no real concept PNG (and no OPENAI_API_KEY) is available.

This is INTENTIONALLY low-quality: a flat-shaded silhouette of a tapered
obelisk on white. It gets the input shape right (1024x1024, white bg, single
centered subject, hero angle), so the image-to-3D model has something to bite
on, but it WILL produce ugly geometry. That's fine — the goal of Phase 11 is
to verify the chain runs end-to-end. Real concept art (via concept_gen.py or
hand-authored) replaces this on the second pass.

Output: D:/assets/world/props/concepts/<id>/source.png + concept.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

DEFAULT_OUT = Path(r"D:\assets\world\props\concepts")


def draw_obelisk_placeholder(size: int = 1024) -> Image.Image:
    """Tapered four-sided stone obelisk on white. Two visible faces."""
    img = Image.new("RGB", (size, size), (255, 255, 255))
    d = ImageDraw.Draw(img)

    # Vertical extents — leave 10% padding on top/bottom
    top_y = int(size * 0.10)
    bot_y = int(size * 0.90)
    cx = size // 2

    # Tapered silhouette: top is 12% of width, base is 28% of width
    top_half = int(size * 0.060)
    bot_half = int(size * 0.140)

    # Three-quarter view: shift the right face so we see TWO faces
    # Front face (the wider, lighter one)
    front_left  = (cx - bot_half, bot_y)
    front_right = (cx + int(bot_half * 0.55), bot_y)
    front_top_l = (cx - top_half, top_y)
    front_top_r = (cx + int(top_half * 0.55), top_y)

    # Right face (narrower, darker) — projects to the right and back
    side_skew = int(size * 0.08)
    side_top_r = (front_top_r[0] + side_skew, top_y - int(size * 0.005))
    side_bot_r = (front_right[0] + side_skew, bot_y - int(size * 0.005))

    # Front face polygon
    front = [front_left, front_right, front_top_r, front_top_l]
    d.polygon(front, fill=(140, 132, 122))  # warm stone

    # Right side polygon (darker)
    side = [front_right, side_bot_r, side_top_r, front_top_r]
    d.polygon(side, fill=(96, 90, 82))  # shadowed stone

    # Broken/chipped tip — clip the top with a jagged line
    chip_y = top_y + int(size * 0.015)
    chip_left = (front_top_l[0], chip_y)
    chip_mid = (cx, top_y - int(size * 0.005))
    chip_right = (side_top_r[0], chip_y - int(size * 0.005))
    d.polygon([front_top_l, chip_left, chip_mid, chip_right, side_top_r,
               front_top_r], fill=(255, 255, 255))

    # A few horizontal "carved relief" bands on the front face
    for frac in (0.30, 0.45, 0.60, 0.75):
        ry = int(top_y + (bot_y - top_y) * frac)
        # band thickness scaled to local width
        local_half = int(top_half + (bot_half - top_half) * frac)
        bx0 = cx - int(local_half * 0.85)
        bx1 = cx + int(int(local_half * 0.55) * 0.85)
        bh = max(2, int(size * 0.005))
        d.rectangle([bx0, ry - bh, bx1, ry + bh], fill=(110, 102, 92))

    # Vertical mossy crack
    crack_x = cx - int(bot_half * 0.30)
    crack_pts = []
    rng = np.random.default_rng(7)
    for f in np.linspace(0.0, 1.0, 8):
        y = int(top_y + (bot_y - top_y) * f)
        x_jitter = int(rng.integers(-6, 6))
        crack_pts.append((crack_x + x_jitter, y))
    d.line(crack_pts, fill=(70, 86, 60), width=4)

    return img


def write_concept(prop_id: str, prompt: str, png: bytes, out_root: Path,
                  *, size: int) -> Path:
    out_dir = out_root / prop_id
    out_dir.mkdir(parents=True, exist_ok=True)
    img_path = out_dir / "source.png"
    img_path.write_bytes(png)
    sha = hashlib.sha256(png).hexdigest()[:16]
    meta = {
        "schema": "prop_concept.v1",
        "id": prop_id,
        "prompt": prompt,
        "backend": "procedural_placeholder",
        "model": "concept_placeholder.py:draw_obelisk_placeholder",
        "size_px": size,
        "image": "source.png",
        "image_sha256_16": sha,
        "generated_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "_warning": "Procedural placeholder — geometry-quality lower bound. Replace with concept_gen.py output or hand-authored PNG before scoring AI-route quality.",
    }
    (out_dir / "concept.json").write_text(json.dumps(meta, indent=2),
                                          encoding="utf-8")
    return img_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default="ruined_obelisk_a_placeholder")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--size", type=int, default=1024)
    args = ap.parse_args()

    img = draw_obelisk_placeholder(args.size)
    import io as _io
    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()

    prompt = ("weathered tapered four-sided stone obelisk with carved relief "
              "bands, chipped tip, mossy vertical crack, three-quarter view")
    path = write_concept(args.id, prompt, png, args.out, size=args.size)
    print(f"[concept_placeholder] wrote {path} ({len(png)//1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
