"""Build a contact sheet for slot-level candidate review.

For a given biome × slot, builds a grid of all candidates' albedo
thumbnails (+ tag + grade overlay) so you can review the entire slot
pool as one image. Saves to:

    candidates/<biome>/<slot>/_contact_sheet.png

Usage:
    python build_contact_sheet.py --biome alpine
    python build_contact_sheet.py --biome alpine --slots ground
    python build_contact_sheet.py --biome alpine --thumb 384
    python build_contact_sheet.py --biome alpine --grade-filter B C D
        (only show below-A candidates — useful for spot-check review)
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANDIDATES_ROOT = Path(r"D:\assets\world 4\the world 4\candidates")
DEFAULT_THUMB = 256
LABEL_HEIGHT = 36
PADDING = 8
GRADE_COLORS = {
    "A": (40, 200, 80),
    "B": (220, 180, 30),
    "C": (240, 130, 30),
    "D": (220, 60, 60),
    None: (140, 140, 140),
}


def _load_font(size: int = 16) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _slot_dirs(biome: str, slots: list[str] | None) -> list[Path]:
    biome_dir = CANDIDATES_ROOT / biome
    if not biome_dir.exists():
        raise SystemExit(f"biome dir not found: {biome_dir}")
    out = []
    for d in sorted(biome_dir.iterdir()):
        if d.is_dir() and not d.name.startswith("_"):
            if slots and d.name not in slots:
                continue
            out.append(d)
    return out


def _candidate_cells(slot_dir: Path, grade_filter: set[str] | None
                     ) -> list[tuple[Path, dict]]:
    index_path = slot_dir / "_index.json"
    if not index_path.exists():
        return []
    index = json.loads(index_path.read_text(encoding="utf-8"))
    cells = []
    for cid, entry in sorted(index.get("candidates", {}).items()):
        if grade_filter is not None and entry.get("grade") not in grade_filter:
            continue
        cand_dir = slot_dir / cid
        albedo = cand_dir / "albedo.png"
        if not albedo.exists():
            continue
        cells.append((albedo, entry))
    return cells


def _draw_cell(albedo: Path, entry: dict, thumb: int) -> Image.Image:
    cell = Image.new("RGB", (thumb, thumb + LABEL_HEIGHT), (16, 16, 16))
    img = Image.open(albedo).convert("RGB").resize((thumb, thumb), Image.LANCZOS)
    cell.paste(img, (0, 0))
    draw = ImageDraw.Draw(cell)
    font = _load_font(14)
    grade = entry.get("grade")
    color = GRADE_COLORS.get(grade, GRADE_COLORS[None])
    # grade badge
    draw.rectangle([0, thumb, 28, thumb + LABEL_HEIGHT], fill=color)
    draw.text((6, thumb + 7), grade or "-", font=_load_font(20),
              fill=(0, 0, 0))
    # tag + metric
    tag = entry["id"]
    metrics = entry.get("metrics") or {}
    period = metrics.get("periodic")
    period_s = f" p={period:.1f}" if period is not None else ""
    draw.text((34, thumb + 4), tag[:30], font=font, fill=(230, 230, 230))
    draw.text((34, thumb + 20), period_s, font=_load_font(12),
              fill=(180, 180, 180))
    reason = entry.get("below_A_reason")
    if reason:
        # red overlay strip on the right edge of the thumb area
        draw.rectangle([thumb - 6, 0, thumb, thumb], fill=(220, 60, 60))
    return cell


def build_sheet(biome: str, slot_dir: Path, thumb: int,
                grade_filter: set[str] | None) -> Path | None:
    cells = _candidate_cells(slot_dir, grade_filter)
    if not cells:
        print(f"  [skip] {biome}/{slot_dir.name}: no matching candidates")
        return None
    n = len(cells)
    cols = max(1, min(6, int(math.ceil(math.sqrt(n)))))
    rows = int(math.ceil(n / cols))
    cell_w = thumb + PADDING
    cell_h = thumb + LABEL_HEIGHT + PADDING
    title_h = 40
    sheet_w = cols * cell_w + PADDING
    sheet_h = rows * cell_h + PADDING + title_h
    sheet = Image.new("RGB", (sheet_w, sheet_h), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    suffix = f" (filter={','.join(sorted(grade_filter))})" if grade_filter else ""
    draw.text((12, 8), f"{biome} / {slot_dir.name} — {n} candidates{suffix}",
              font=_load_font(20), fill=(230, 230, 230))
    for i, (albedo, entry) in enumerate(cells):
        r, c = divmod(i, cols)
        x = PADDING + c * cell_w
        y = title_h + PADDING + r * cell_h
        sheet.paste(_draw_cell(albedo, entry, thumb), (x, y))
    out_name = "_contact_sheet.png" if grade_filter is None else \
        f"_contact_sheet_{'_'.join(sorted(grade_filter)).lower()}.png"
    out = slot_dir / out_name
    sheet.save(out)
    print(f"  wrote {out} ({n} cells, {cols}x{rows})")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--biome", required=True)
    ap.add_argument("--slots", nargs="*",
                    help="restrict to specific slots (default: all)")
    ap.add_argument("--thumb", type=int, default=DEFAULT_THUMB,
                    help=f"thumb edge in px (default: {DEFAULT_THUMB})")
    ap.add_argument("--grade-filter", nargs="*",
                    help="only include candidates with one of these grades "
                         "(e.g. B C D). Default: all grades.")
    args = ap.parse_args()
    grade_filter = set(args.grade_filter) if args.grade_filter else None
    for slot_dir in _slot_dirs(args.biome, args.slots):
        build_sheet(args.biome, slot_dir, args.thumb, grade_filter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
