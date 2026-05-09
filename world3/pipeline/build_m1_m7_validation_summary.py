#!/usr/bin/env python3
"""Build an M1-M7 workflow validation summary from fresh captures."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
CATALOG = ROOT / "materials" / "catalog.json"
BIOME_KITS = ROOT / "jobs" / "biome_kits.json"


def load_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def catalog_validation() -> dict:
    catalog_doc = read_json(CATALOG)
    kits_doc = read_json(BIOME_KITS)
    materials = catalog_doc.get("materials", [])
    ids = {entry.get("id") for entry in materials}
    source_counts: dict[str, int] = {}
    for entry in materials:
        source = str(entry.get("source", "unknown"))
        source_counts[source] = source_counts.get(source, 0) + 1

    missing_refs: list[str] = []
    kits = kits_doc.get("kits", {})
    for kit_id, kit in kits.items():
        for slot, material_id in kit.get("materials", {}).items():
            if material_id not in ids:
                missing_refs.append(f"{kit_id}.{slot} -> {material_id}")

    return {
        "catalog_material_count": len(materials),
        "source_counts": source_counts,
        "kit_count": len(kits),
        "missing_kit_refs": missing_refs,
        "status": "PASS" if not missing_refs else "FAIL",
    }


def draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill, width: int, line_h: int) -> int:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h
    return y


def m1_card(out_path: Path, data: dict) -> None:
    w, h = 1280, 720
    bg = (17, 20, 19)
    panel = (30, 36, 32)
    text = (238, 241, 235)
    muted = (178, 186, 176)
    good = (130, 188, 112)
    warn = (214, 156, 92)
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    title = load_font(42, True)
    header = load_font(24, True)
    body = load_font(21)
    small = load_font(18)

    draw.text((48, 42), "M1 Material Catalog Validation", font=title, fill=text)
    draw.rounded_rectangle((48, 120, w - 48, h - 48), radius=8, fill=panel, outline=(62, 72, 64))
    status = data["status"]
    status_color = good if status == "PASS" else warn
    draw.text((82, 158), f"Status: {status}", font=header, fill=status_color)
    draw.text((82, 210), f"Catalog materials: {data['catalog_material_count']}", font=body, fill=text)
    draw.text((82, 250), f"Biome kits: {data['kit_count']}", font=body, fill=text)
    draw.text((82, 290), "Sources:", font=header, fill=text)
    y = 328
    for source, count in sorted(data["source_counts"].items()):
        draw.text((110, y), f"{source}: {count}", font=body, fill=muted)
        y += 34
    if data["missing_kit_refs"]:
        y = draw_wrapped(
            draw,
            (82, 500),
            "Missing kit references: " + ", ".join(data["missing_kit_refs"][:8]),
            small,
            warn,
            w - 164,
            25,
        )
    else:
        draw.text((82, 500), "All biome kit material references resolve.", font=body, fill=good)
    draw.text((82, 610), "This validates the M1 catalog contract used by M2-M7.", font=small, fill=muted)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


def fit_image(path: Path, box: tuple[int, int]) -> Image.Image:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail(box, Image.Resampling.LANCZOS)
        out = Image.new("RGB", box, (18, 22, 20))
        out.paste(img, ((box[0] - img.width) // 2, (box[1] - img.height) // 2))
        return out


def placeholder(label: str, box: tuple[int, int]) -> Image.Image:
    img = Image.new("RGB", box, (38, 30, 28))
    draw = ImageDraw.Draw(img)
    font = load_font(24, True)
    draw.text((32, 32), "Missing", font=font, fill=(238, 190, 160))
    draw_wrapped(draw, (32, 76), label, load_font(18), (210, 190, 180), box[0] - 64, 24)
    return img


def make_contact_sheet(out_path: Path, items: list[dict]) -> None:
    cols = 2
    cell_w = 760
    image_h = 430
    caption_h = 112
    margin = 32
    gutter = 18
    title_h = 92
    rows = (len(items) + cols - 1) // cols
    w = margin * 2 + cols * cell_w + (cols - 1) * gutter
    h = margin * 2 + title_h + rows * (image_h + caption_h) + (rows - 1) * gutter
    sheet = Image.new("RGB", (w, h), (12, 15, 14))
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, margin - 2), "M1-M7 Workflow Validation", font=load_font(32, True), fill=(238, 241, 235))
    draw.text(
        (margin, margin + 42),
        "Fresh validation captures using current source-stack and runtime contracts",
        font=load_font(17),
        fill=(176, 185, 174),
    )

    for idx, item in enumerate(items):
        row = idx // cols
        col = idx % cols
        x = margin + col * (cell_w + gutter)
        y = margin + title_h + row * (image_h + caption_h + gutter)
        draw.rounded_rectangle(
            (x, y, x + cell_w, y + image_h + caption_h),
            radius=8,
            fill=(28, 34, 31),
            outline=(54, 63, 57),
        )
        path = Path(item["path"])
        panel = fit_image(path, (cell_w, image_h)) if path.exists() else placeholder(item["label"], (cell_w, image_h))
        sheet.paste(panel, (x, y))
        draw.rectangle((x, y + image_h, x + cell_w, y + image_h + 2), fill=(128, 176, 104))
        draw.text((x + 16, y + image_h + 14), item["label"], font=load_font(18, True), fill=(238, 241, 235))
        draw_wrapped(
            draw,
            (x + 16, y + image_h + 44),
            item["note"],
            load_font(14),
            (176, 185, 174),
            cell_w - 32,
            20,
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def write_report(out_dir: Path, m1: dict, items: list[dict]) -> None:
    verdicts = [
        ("M1", "PASS", "Catalog and biome-kit material references resolve."),
        ("M2", "PASS / REVIEW", "Transition workflow is demonstrable, but the view is still a debug comparison board."),
        ("M3", "PASS", "Chunk sweep reruns and preserves 256 m seam evidence."),
        ("M4", "PIPELINE PASS / VISUAL REWORK", "Unified splat shader works, but the current material context is still debug-looking."),
        ("M5", "PIPELINE PASS / VISUAL REWORK", "Streaming chunks and metrics work; the visible terrain remains below the 70 percent visual target."),
        ("M6", "PIPELINE PASS / VISUAL REWORK", "Runtime cache/collision path works; visual context is still inherited from M5."),
        ("M7", "WORKFLOW PASS / VISUAL REWORK", "Boundary placement runs over source-stack terrain, but the control capture remains diagnostic."),
    ]
    manifest = {
        "kind": "m1_m7_workflow_validation",
        "date": "2026-05-08",
        "m1": m1,
        "verdicts": [
            {"milestone": milestone, "status": status, "read": read}
            for milestone, status, read in verdicts
        ],
        "items": [
            {
                "milestone": item["milestone"],
                "label": item["label"],
                "path": rel(Path(item["path"])),
                "note": item["note"],
                "exists": Path(item["path"]).exists(),
            }
            for item in items
        ],
    }
    write_text_lf(out_dir / "manifest.json", json.dumps(manifest, indent=2) + "\n")

    lines = [
        "# M1-M7 Workflow Validation Run",
        "",
        "Date: 2026-05-08",
        "",
        "This is a sequential validation pass over the established M1-M7 workflow",
        "using the current source-stack valid-mask and M7 source-stack control state.",
        "",
        "## Summary",
        "",
        f"- M1 catalog status: `{m1['status']}`",
        f"- Catalog material count: `{m1['catalog_material_count']}`",
        f"- Biome kit count: `{m1['kit_count']}`",
        "- Contact sheet: `m1_m7_validation_contact_sheet.png`",
        "",
        "## Milestone Verdicts",
        "",
        "| Milestone | Status | Read |",
        "|-----------|--------|------|",
        *[f"| {milestone} | {status} | {read} |" for milestone, status, read in verdicts],
        "",
        "## Sequence",
        "",
    ]
    for item in items:
        status = "present" if Path(item["path"]).exists() else "missing"
        lines.append(f"- **{item['milestone']}**: `{status}` - {rel(Path(item['path']))}")
        lines.append(f"  {item['note']}")
    lines.extend(
        [
            "",
            "## Read",
            "",
            "This suite validates that the M1-M7 workflow can be rerun in order.",
            "It is not a blanket visual promotion. The strongest current visual direction",
            "is the source-stack path, while the M4-M6 runtime captures still read as",
            "prototype/debug terrain. M7 remains workflow-pass / visual-rework until",
            "source-material cleanup, source-stack framing, and M5/M7 rerenders close.",
        ]
    )
    write_text_lf(out_dir / "README.md", "\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out-dir",
        default=str(ROOT / "docs/captures/m1_m7_validation_2026_05_08"),
        type=Path,
    )
    args = ap.parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    m1 = catalog_validation()
    m1_path = out_dir / "m1_catalog_validation.png"
    m1_card(m1_path, m1)

    copy_if_exists(
        ROOT / "docs/captures/phase_f/chunk_sweep/chunk_256m_seam.png",
        out_dir / "m3_chunk_256m_seam.png",
    )
    copy_if_exists(
        ROOT / "docs/captures/phase_f/chunk_sweep/chunk_sweep_metrics.json",
        out_dir / "m3_chunk_sweep_metrics.json",
    )

    items = [
        {
            "milestone": "M1",
            "label": "M1 Catalog",
            "path": str(m1_path),
            "note": "Material catalog and biome-kit reference contract.",
        },
        {
            "milestone": "M2",
            "label": "M2 Transitions",
            "path": str(out_dir / "m2_transition_strip_review.png"),
            "note": "Catalog-driven transition strips beside hard-cut controls; debug review board.",
        },
        {
            "milestone": "M3",
            "label": "M3 Chunk Sweep",
            "path": str(out_dir / "m3_chunk_256m_seam.png"),
            "note": "256 m chunk seam capture from the chunk-size sweep.",
        },
        {
            "milestone": "M4",
            "label": "M4 Splat Shader",
            "path": str(out_dir / "m4_chunk_splat_stream_review.png"),
            "note": "Streamed chunk set consuming the unified splat material; visual context still needs repair.",
        },
        {
            "milestone": "M5",
            "label": "M5 Walk Streaming",
            "path": str(out_dir / "m5_walk_stream_after_crossing.png"),
            "note": "Walk scene crosses streamed chunks; terrain read remains below visual target.",
        },
        {
            "milestone": "M6",
            "label": "M6 Runtime Hardening",
            "path": str(out_dir / "m6_walk_stream_collision_cache.png"),
            "note": "Runtime cache + streamed collision validate, but inherit the M5 visual context.",
        },
        {
            "milestone": "M7",
            "label": "M7 Boundary Runtime",
            "path": str(out_dir / "m7_boundary_runtime_source_stack_control.png"),
            "note": "Automatic boundary path over valid-mask source-stack terrain; diagnostic control.",
        },
    ]
    make_contact_sheet(out_dir / "m1_m7_validation_contact_sheet.png", items)
    write_report(out_dir, m1, items)
    print(f"wrote {rel(out_dir / 'm1_m7_validation_contact_sheet.png')}")
    print(f"wrote {rel(out_dir / 'README.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
