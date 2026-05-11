"""Build the M16 source-stack gallery bridge board.

The legacy region gallery is still useful, but it is not parity evidence until
it can bind the source-stack contract. This script indexes representative
source-stack captures and produces a visual board plus machine-readable status.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "world3/jobs/m16_source_stack_gallery_manifest.json"
OUT_JSON = ROOT / "world3/docs/M16_SOURCE_STACK_GALLERY_BOARD.json"
OUT_MD = ROOT / "world3/docs/M16_SOURCE_STACK_GALLERY_BOARD_2026_05_10.md"
OUT_PNG = ROOT / "world3/docs/captures/review/source_stack_m16_gallery_board.png"


def repo_path(path: str) -> Path:
    return ROOT / path


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        p = Path(candidate)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def load_manifest() -> dict[str, Any]:
    with MANIFEST.open("r", encoding="utf-8") as f:
        return json.load(f)


def collect(manifest: dict[str, Any]) -> dict[str, Any]:
    required = list(manifest.get("required_bands", []))
    cards = []
    for raw in manifest.get("cards", []):
        captures = dict(raw.get("captures", {}))
        capture_status = {}
        for band in required:
            raw_path = captures.get(band)
            capture_status[band] = {
                "path": raw_path,
                "exists": bool(raw_path and repo_path(raw_path).exists()),
            }
        full_parity = all(capture_status[band]["exists"] for band in required)
        representative_band = str(raw.get("representative_band", "iso"))
        representative_path = captures.get(representative_band) or next(iter(captures.values()), "")
        cards.append(
            {
                "id": raw.get("id", ""),
                "title": raw.get("title", ""),
                "scene": raw.get("scene", ""),
                "source_stack": raw.get("source_stack", ""),
                "status": raw.get("status", ""),
                "representative_band": representative_band,
                "representative_path": representative_path,
                "representative_exists": bool(representative_path and repo_path(representative_path).exists()),
                "capture_status": capture_status,
                "full_parity_capture_set": full_parity,
                "contract_inputs": raw.get("contract_inputs", []),
                "next": raw.get("next", ""),
            }
        )
    full_cards = [card for card in cards if card["full_parity_capture_set"]]
    return {
        "version": manifest.get("version", 1),
        "id": manifest.get("id", "m16_source_stack_gallery_manifest"),
        "status": manifest.get("status", ""),
        "purpose": manifest.get("purpose", ""),
        "legacy_gallery_status": manifest.get("legacy_gallery_status", {}),
        "required_bands": required,
        "cards": cards,
        "summary": {
            "cards_total": len(cards),
            "full_parity_capture_sets": len(full_cards),
            "representative_images_present": sum(1 for card in cards if card["representative_exists"]),
            "sidecar_only_cards": sum(1 for card in cards if not card["full_parity_capture_set"]),
        },
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M16 Source-Stack Gallery Board - 2026-05-10",
        "",
        "This is the first M16 bridge board from the legacy regional gallery to",
        "source-stack parity evidence. It does not replace the live review scenes;",
        "it indexes which source-stack captures are ready to become gallery cards.",
        "",
        "## Summary",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- {key}: `{value}`")

    legacy = report.get("legacy_gallery_status", {})
    lines.extend(
        [
            "",
            "## Legacy Gallery Status",
            "",
            f"- Scene: `{legacy.get('scene', '')}`",
            f"- Script: `{legacy.get('script', '')}`",
            f"- Status: `{legacy.get('status', '')}`",
            f"- Reason: {legacy.get('reason', '')}",
            "",
            "## Cards",
            "",
            "| Card | Status | Full bands | Representative | Next |",
            "|------|--------|------------|----------------|------|",
        ]
    )
    for card in report["cards"]:
        full = "yes" if card["full_parity_capture_set"] else "no"
        rep = card["representative_path"] if card["representative_exists"] else "missing"
        lines.append(
            f"| `{card['id']}` | `{card['status']}` | {full} | `{rep}` | {card['next']} |"
        )

    lines.extend(
        [
            "",
            "## Visual Board",
            "",
            "`world3/docs/captures/review/source_stack_m16_gallery_board.png`",
            "",
            "## Next",
            "",
            "1. Keep the legacy `RegionGalleryCapture.gd` path available for old regional screenshots.",
            "2. Add a source-stack gallery runner that consumes this manifest shape instead of whole-kit material swaps.",
            "3. Promote only cards with topdown/iso/medium/close captures as parity evidence.",
            "4. Keep cached iso impostors as M16 sidecar renderer evidence until chunked impostors exist.",
            "",
            "Regenerate:",
            "",
            "```powershell",
            "python world3/pipeline/build_m16_source_stack_gallery_board.py",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def fit_image(path: Path, box: tuple[int, int]) -> Image.Image:
    Image.MAX_IMAGE_PIXELS = None
    if not path.exists():
        out = Image.new("RGB", box, (42, 22, 22))
        draw = ImageDraw.Draw(out)
        font = load_font(24, bold=True)
        draw.text((24, box[1] // 2 - 18), "missing capture", font=font, fill=(255, 210, 190))
        return out
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail(box, Image.Resampling.LANCZOS)
        out = Image.new("RGB", box, (16, 19, 18))
        out.paste(img, ((box[0] - img.width) // 2, (box[1] - img.height) // 2))
        return out


def build_sheet(report: dict[str, Any]) -> None:
    cols = 3
    cell_w = 600
    image_h = 338
    caption_h = 138
    margin = 30
    gutter = 18
    title_h = 100
    rows = (len(report["cards"]) + cols - 1) // cols
    width = margin * 2 + cols * cell_w + (cols - 1) * gutter
    height = margin * 2 + title_h + rows * (image_h + caption_h) + (rows - 1) * gutter
    sheet = Image.new("RGB", (width, height), (11, 14, 13))
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(30, bold=True)
    sub_font = load_font(17)
    label_font = load_font(18, bold=True)
    note_font = load_font(14)
    small_font = load_font(12)
    text = (235, 239, 232)
    muted = (175, 184, 174)
    accent = (122, 172, 104)
    warn = (214, 154, 86)

    draw.text((margin, margin - 2), "M16 Source-Stack Gallery Bridge", font=title_font, fill=text)
    draw.text(
        (margin, margin + 40),
        "Representative source-stack cards indexed for topdown/iso/medium/close gallery parity",
        font=sub_font,
        fill=muted,
    )
    summary = report["summary"]
    draw.text(
        (margin, margin + 66),
        f"{summary['full_parity_capture_sets']}/{summary['cards_total']} full parity capture sets; cached iso remains sidecar evidence",
        font=small_font,
        fill=muted,
    )

    y0 = margin + title_h
    for idx, card in enumerate(report["cards"]):
        row = idx // cols
        col = idx % cols
        x = margin + col * (cell_w + gutter)
        y = y0 + row * (image_h + caption_h + gutter)
        panel = (25, 31, 28)
        outline = (58, 70, 62)
        draw.rounded_rectangle((x, y, x + cell_w, y + image_h + caption_h), radius=8, fill=panel, outline=outline)
        rep_path = repo_path(card["representative_path"]) if card["representative_path"] else Path()
        sheet.paste(fit_image(rep_path, (cell_w, image_h)), (x, y))
        bar_color = accent if card["full_parity_capture_set"] else warn
        draw.rectangle((x, y + image_h, x + cell_w, y + image_h + 3), fill=bar_color)
        tx = x + 14
        ty = y + image_h + 13
        draw.text((tx, ty), str(card["title"]), font=label_font, fill=text)
        status = "full topdown/iso/medium/close" if card["full_parity_capture_set"] else "sidecar / partial bands"
        draw.text((tx, ty + 27), f"{card['id']} | {status}", font=small_font, fill=bar_color)
        note = f"{card['status']}. {card['next']}"
        ny = ty + 50
        for line in wrap(draw, note, note_font, cell_w - 28)[:4]:
            draw.text((tx, ny), line, font=note_font, fill=muted)
            ny += 20

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT_PNG)


def write_lf(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    manifest = load_manifest()
    report = collect(manifest)
    write_lf(OUT_JSON, json.dumps(report, indent=2) + "\n")
    write_lf(OUT_MD, markdown(report))
    build_sheet(report)
    print(f"OK {OUT_JSON.relative_to(ROOT)}")
    print(f"OK {OUT_MD.relative_to(ROOT)}")
    print(f"OK {OUT_PNG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
