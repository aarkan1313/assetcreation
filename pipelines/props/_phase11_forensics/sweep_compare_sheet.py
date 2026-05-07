"""Build a single-image comparison sheet of the HY3D sweep + Trellis2 reference."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"D:\tmp\glb_compare")
LABELS = [
    # row 0 — HY3D
    ("sweep_baseline", "HY3D baseline\n40k f / 1024² tex\n90s / 1.6 MB"),
    ("sweep_hi_geo",   "HY3D hi_geo\n100k f / 1024² tex\n74s / 3.0 MB"),
    ("sweep_hi_paint", "HY3D hi_paint\n40k f / 2048² tex\n387s / 3.1 MB"),
    ("sweep_hero_max", "HY3D hero_max\n100k f / 2048² tex\n677s / 5.4 MB"),
    # row 1 — Trellis2 (mesh gen 23s + postprocess time below)
    ("t2_low",         "Trellis2 low\n49k f / 1024² tex\n23+4s / 4.0 MB"),
    ("t2_mid",         "Trellis2 mid (default)\n194k f / 2048² tex\n23+8s / 13.8 MB"),
    ("t2_hi",          "Trellis2 hi\n485k f / 2048² tex\n23+18s / 23.1 MB"),
    ("t2_hi_tex",      "Trellis2 hi_tex\n194k f / 4096² tex\n23+20s / 32.1 MB"),
]
VIEW = "iso"

CELL_W, CELL_H = 384, 384
LABEL_H = 96
PAD = 8
COLS = 4
ROWS = 2

W = CELL_W * COLS + PAD * (COLS + 1)
H = (CELL_H + LABEL_H) * ROWS + PAD * (ROWS + 1)

sheet = Image.new("RGB", (W, H), (32, 32, 32))
draw = ImageDraw.Draw(sheet)

try:
    font = ImageFont.truetype("arial.ttf", 14)
except Exception:
    font = ImageFont.load_default()

for i, (folder, label) in enumerate(LABELS):
    path = ROOT / folder / f"{VIEW}.png"
    if not path.exists():
        print(f"[skip] {path}")
        continue
    img = Image.open(path).resize((CELL_W, CELL_H), Image.LANCZOS)
    col = i % COLS
    row = i // COLS
    x = PAD + col * (CELL_W + PAD)
    y = PAD + row * (CELL_H + LABEL_H + PAD)
    sheet.paste(img, (x, y))
    ly = y + CELL_H + 4
    draw.rectangle([x, ly, x + CELL_W, ly + LABEL_H - 4], fill=(48, 48, 48))
    draw.multiline_text((x + 8, ly + 6), label, fill=(220, 220, 220), font=font, spacing=2)

OUT = Path(r"D:\tmp\sweep_compare_sheet.png")
sheet.save(OUT)
print(f"saved {OUT} ({W}x{H})")
