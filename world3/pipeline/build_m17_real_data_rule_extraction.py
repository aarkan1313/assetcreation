"""Extract first procedural-neighbor rules from accepted source-stack proofs."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
WORLD3 = ROOT / "world3"
SOURCES = WORLD3 / "jobs/m17_rule_extraction_sources.json"
OUT_JSON = WORLD3 / "docs/M17_REAL_DATA_RULE_EXTRACTION.json"
OUT_MD = WORLD3 / "docs/M17_REAL_DATA_RULE_EXTRACTION_2026_05_10.md"
OUT_BOARD = WORLD3 / "docs/captures/review/source_stack_m17_rule_extraction_board.png"
OUT_RECIPE = WORLD3 / "jobs/m17_procedural_neighbor_recipe.json"


def repo_path(path: str) -> Path:
    if path.startswith("res://"):
        return WORLD3 / path.removeprefix("res://")
    p = Path(path)
    if p.is_absolute():
        return p
    return ROOT / p


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_image01(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        arr = np.asarray(img)
    if np.issubdtype(arr.dtype, np.integer) and int(np.max(arr)) > 255:
        return arr.astype(np.float32) / 65535.0
    return arr.astype(np.float32) / 255.0


def height_meters(height_path: Path, meta: dict[str, Any]) -> np.ndarray:
    norm = load_image01(height_path)
    if norm.ndim == 3:
        norm = norm[:, :, 0]
    elev_min = float(meta.get("elevation_min_m", 0.0))
    elev_range = float(meta.get("elevation_range_m", 1.0))
    return elev_min + norm * elev_range


def blur_height(arr: np.ndarray, radius: float) -> np.ndarray:
    values = np.asarray(arr, dtype=np.float32)
    lo = float(np.min(values))
    hi = float(np.max(values))
    if hi <= lo:
        return values.copy()
    norm = np.clip((values - lo) / (hi - lo), 0.0, 1.0)
    img = Image.fromarray((norm * 255.0).astype(np.uint8), mode="L")
    blurred = np.asarray(img.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32) / 255.0
    return lo + blurred * (hi - lo)


# PIL exposes ImageFilter at module import time in some environments; keep this
# import separate to avoid lint noise in the main import block.
from PIL import ImageFilter  # noqa: E402


def landform_metrics(height: np.ndarray, meta: dict[str, Any]) -> dict[str, float]:
    h, w = height.shape
    world_x = float(meta.get("world_size_x_m", meta.get("world_size_m", w)))
    world_z = float(meta.get("world_size_z_m", meta.get("world_size_m", h)))
    px_x = world_x / max(w - 1, 1)
    px_z = world_z / max(h - 1, 1)
    dz, dx = np.gradient(height, px_z, px_x)
    slope = np.sqrt(dx * dx + dz * dz)
    low = blur_height(height, max(min(w, h) / 96.0, 2.0))
    rough = height - low
    return {
        "world_size_x_m": world_x,
        "world_size_z_m": world_z,
        "elevation_min_m": float(np.min(height)),
        "elevation_max_m": float(np.max(height)),
        "elevation_range_m": float(np.max(height) - np.min(height)),
        "slope_mean": float(np.mean(slope)),
        "slope_p50": float(np.percentile(slope, 50)),
        "slope_p95": float(np.percentile(slope, 95)),
        "roughness_std_m": float(np.std(rough)),
        "roughness_p95_abs_m": float(np.percentile(np.abs(rough), 95)),
    }


def mask_metrics(layers: dict[str, str]) -> dict[str, dict[str, float]]:
    wanted = [
        "wash_line_mask",
        "shrub_carryover_mask",
        "dry_grass_density_mask",
        "soil_exposure_mask",
        "rock_cluster_mask",
        "no_scatter_mask",
        "ecotone_weight",
        "splat_weights_rgba",
    ]
    out: dict[str, dict[str, float]] = {}
    for key in wanted:
        raw = layers.get(key)
        if not raw:
            continue
        path = repo_path(raw)
        if not path.exists():
            continue
        arr = load_image01(path)
        if arr.ndim == 3 and key != "splat_weights_rgba":
            arr = arr[:, :, 0]
        if key == "splat_weights_rgba":
            weights = arr[:, :, :4]
            total = np.sum(weights, axis=2, keepdims=True)
            norm = weights / np.maximum(total, 1e-6)
            entropy = -np.sum(norm * np.log2(np.maximum(norm, 1e-6)), axis=2) / 2.0
            dominance = np.max(norm, axis=2)
            out[key] = {
                "entropy_mean": float(np.mean(entropy)),
                "transition_coverage": float(np.mean(dominance < 0.78)),
                "dominance_p50": float(np.percentile(dominance, 50)),
                "dominance_p05": float(np.percentile(dominance, 5)),
            }
        else:
            out[key] = {
                "mean": float(np.mean(arr)),
                "coverage_gt_0_25": float(np.mean(arr > 0.25)),
                "coverage_gt_0_50": float(np.mean(arr > 0.50)),
                "p95": float(np.percentile(arr, 95)),
            }
    return out


def analyze_source(entry: dict[str, Any]) -> dict[str, Any]:
    manifest_path = repo_path(entry["manifest"])
    manifest = load_json(manifest_path)
    meta_path = repo_path(manifest.get("runtime_meta", ""))
    height_path = repo_path(manifest.get("runtime_heightmap", ""))
    meta = load_json(meta_path) if meta_path.exists() else {}
    height = height_meters(height_path, meta) if height_path.exists() else np.zeros((2, 2), dtype=np.float32)
    layers = manifest.get("layers", {})
    return {
        "id": entry["id"],
        "role": entry.get("role", ""),
        "manifest": entry["manifest"],
        "runtime_heightmap": manifest.get("runtime_heightmap", ""),
        "runtime_macro": manifest.get("runtime_macro", ""),
        "landform": landform_metrics(height, meta),
        "masks": mask_metrics(layers),
        "manifest_metrics": manifest.get("metrics", {}),
        "policy": manifest.get("policy", ""),
    }


def aggregate(samples: list[dict[str, Any]]) -> dict[str, Any]:
    landforms = [s["landform"] for s in samples if s["landform"]["elevation_range_m"] > 0.0]
    source_ranges = [lf["elevation_range_m"] for lf in landforms]
    slope_p95 = [lf["slope_p95"] for lf in landforms]
    rough = [lf["roughness_p95_abs_m"] for lf in landforms]
    mask_means: dict[str, list[float]] = {}
    transition_coverages: list[float] = []
    for sample in samples:
        for key, metrics in sample["masks"].items():
            if "mean" in metrics:
                mask_means.setdefault(key, []).append(float(metrics["mean"]))
            if key == "splat_weights_rgba":
                transition_coverages.append(float(metrics["transition_coverage"]))
    def avg(values: list[float], fallback: float = 0.0) -> float:
        return float(np.mean(values)) if values else fallback
    return {
        "height": {
            "target_elevation_range_m": avg(source_ranges, 18.0),
            "target_slope_p95": avg(slope_p95, 0.35),
            "target_roughness_p95_abs_m": avg(rough, 1.0),
        },
        "drainage_wash": {
            "target_wash_mean": avg(mask_means.get("wash_line_mask", []), 0.015),
            "target_wash_coverage_gt_0_25": avg(
                [s["masks"].get("wash_line_mask", {}).get("coverage_gt_0_25", 0.0) for s in samples],
                0.02,
            ),
        },
        "vegetation_scatter": {
            "target_shrub_mean": avg(mask_means.get("shrub_carryover_mask", []), 0.12),
            "target_dry_grass_mean": avg(mask_means.get("dry_grass_density_mask", []), 0.28),
            "target_no_scatter_mean": avg(mask_means.get("no_scatter_mask", []), 0.08),
        },
        "material_transition": {
            "target_transition_coverage": avg(transition_coverages, 0.18),
            "target_ecotone_mean": avg(mask_means.get("ecotone_weight", []), 0.12),
        },
    }


def build_neighbor(recipe: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    target = recipe["neighbor_target"]
    out = repo_path(target["out"])
    elev_range = rules["height"]["target_elevation_range_m"]
    cmd = [
        sys.executable,
        str(WORLD3 / "pipeline/build_procedural_neighbor_bundle.py"),
        "--material-id",
        target["material_id"],
        "--out",
        str(out),
        "--size",
        target["size"],
        "--world-size-m",
        target["world_size_m"],
        "--elev-min-m",
        "416.0",
        "--elev-range-m",
        f"{elev_range:.3f}",
        "--seed",
        str(target["seed"]),
        "--name",
        "M17 guided desert canyon procedural neighbor",
    ]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=True)
    return {
        "command": " ".join(cmd),
        "stdout": result.stdout,
        "out": target["out"],
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M17 Real-Data Rule Extraction - 2026-05-10",
        "",
        "M17 starts converting accepted source-stack proofs into procedural-neighbor",
        "rules. This is intentionally modest: first metrics, then one guided",
        "procedural neighbor bundle with the same height/macro/valid-mask contract.",
        "",
        "## Rule Targets",
        "",
        f"- Height range target: `{report['rules']['height']['target_elevation_range_m']:.2f} m`",
        f"- Slope p95 target: `{report['rules']['height']['target_slope_p95']:.3f}`",
        f"- Roughness p95 target: `{report['rules']['height']['target_roughness_p95_abs_m']:.2f} m`",
        f"- Wash mean target: `{report['rules']['drainage_wash']['target_wash_mean']:.4f}`",
        f"- Shrub mean target: `{report['rules']['vegetation_scatter']['target_shrub_mean']:.4f}`",
        f"- Dry grass mean target: `{report['rules']['vegetation_scatter']['target_dry_grass_mean']:.4f}`",
        f"- Transition coverage target: `{report['rules']['material_transition']['target_transition_coverage']:.4f}`",
        "",
        "## Samples",
        "",
        "| Source | Elev range | Slope p95 | Rough p95 | Masks |",
        "|--------|------------|-----------|-----------|-------|",
    ]
    for sample in report["samples"]:
        lf = sample["landform"]
        mask_keys = ", ".join(sample["masks"].keys()) or "-"
        lines.append(
            f"| `{sample['id']}` | `{lf['elevation_range_m']:.2f}m` | "
            f"`{lf['slope_p95']:.3f}` | `{lf['roughness_p95_abs_m']:.2f}m` | {mask_keys} |"
        )
    lines.extend(
        [
            "",
            "## Guided Neighbor",
            "",
            f"- Output: `{report['neighbor']['out']}`",
            f"- Recipe: `world3/jobs/m17_procedural_neighbor_recipe.json`",
            "",
            "The generated neighbor is not production terrain. It is a procedural bundle",
            "that can enter the same source-stack review path as earlier proofs.",
            "",
            "## Visual Board",
            "",
            "`world3/docs/captures/review/source_stack_m17_rule_extraction_board.png`",
            "",
            "## Next",
            "",
            "1. Feed the M17 guided neighbor into a real-to-procedural source-stack review scene.",
            "2. Compare against the M10 procedural canyon proof and M12 gameplay bands.",
            "3. Expand extraction to multiple real DEM families before M19 corpus-scale spectral fitting.",
            "",
            "Regenerate:",
            "",
            "```powershell",
            "python world3/pipeline/build_m17_real_data_rule_extraction.py",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


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


def fit_image(path: Path, box: tuple[int, int]) -> Image.Image:
    if not path.exists():
        return Image.new("RGB", box, (46, 24, 24))
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail(box, Image.Resampling.LANCZOS)
        out = Image.new("RGB", box, (17, 20, 18))
        out.paste(img, ((box[0] - img.width) // 2, (box[1] - img.height) // 2))
        return out


def build_board(report: dict[str, Any]) -> None:
    cards: list[dict[str, Any]] = []
    for sample in report["samples"]:
        lf = sample["landform"]
        cards.append(
            {
                "title": sample["id"],
                "image": repo_path(sample.get("runtime_macro", "")),
                "accent": (122, 172, 104),
                "lines": [
                    "range %.1fm | slope p95 %.3f | rough p95 %.1fm"
                    % (lf["elevation_range_m"], lf["slope_p95"], lf["roughness_p95_abs_m"]),
                    "masks: " + (", ".join(sample["masks"].keys()) or "-"),
                    sample.get("role", ""),
                ],
            }
        )
    neighbor_dir = repo_path(report["neighbor"]["out"])
    neighbor_meta = {}
    meta_path = neighbor_dir / "meta.json"
    if meta_path.exists():
        neighbor_meta = load_json(meta_path)
    cards.append(
        {
            "title": "m17_guided_neighbor",
            "image": neighbor_dir / "layers/render_albedo.png",
            "accent": (189, 145, 91),
            "lines": [
                "generated from extracted targets | seed 1701",
                "range %.1fm | contract: heightmap + macro + valid mask"
                % float(neighbor_meta.get("elevation_range_m", report["rules"]["height"]["target_elevation_range_m"])),
                "first bake for M18 review, not production terrain",
            ],
        }
    )
    cols = 3
    cell_w = 570
    image_h = 300
    caption_h = 126
    margin = 28
    gutter = 18
    title_h = 96
    rows = math.ceil(len(cards) / cols)
    width = margin * 2 + cols * cell_w + (cols - 1) * gutter
    height = margin * 2 + title_h + rows * (image_h + caption_h) + (rows - 1) * gutter
    sheet = Image.new("RGB", (width, height), (11, 14, 13))
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(30, True)
    sub_font = load_font(16)
    label_font = load_font(18, True)
    note_font = load_font(14)
    text = (236, 239, 232)
    muted = (176, 185, 174)
    accent = (122, 172, 104)
    draw.text((margin, margin - 2), "M17 Real-Data Rule Extraction", font=title_font, fill=text)
    draw.text(
        (margin, margin + 40),
        "Accepted source-stack proofs converted into first procedural-neighbor metrics",
        font=sub_font,
        fill=muted,
    )
    rules = report["rules"]
    draw.text(
        (margin, margin + 64),
        "targets: height %.1fm | wash %.3f | shrub %.3f | transition %.3f"
        % (
            rules["height"]["target_elevation_range_m"],
            rules["drainage_wash"]["target_wash_mean"],
            rules["vegetation_scatter"]["target_shrub_mean"],
            rules["material_transition"]["target_transition_coverage"],
        ),
        font=note_font,
        fill=muted,
    )
    y0 = margin + title_h
    for idx, card in enumerate(cards):
        row = idx // cols
        col = idx % cols
        x = margin + col * (cell_w + gutter)
        y = y0 + row * (image_h + caption_h + gutter)
        draw.rounded_rectangle((x, y, x + cell_w, y + image_h + caption_h), radius=8, fill=(26, 32, 29), outline=(58, 70, 62))
        sheet.paste(fit_image(card["image"], (cell_w, image_h)), (x, y))
        draw.rectangle((x, y + image_h, x + cell_w, y + image_h + 3), fill=card["accent"])
        tx = x + 14
        ty = y + image_h + 13
        draw.text((tx, ty), card["title"], font=label_font, fill=text)
        ny = ty + 30
        for line in card["lines"]:
            for wrapped in textwrap.wrap(line, width=72)[:2]:
                draw.text((tx, ny), wrapped, font=note_font, fill=muted)
                ny += 18
            if ny > y + image_h + caption_h - 20:
                break
    OUT_BOARD.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT_BOARD)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    config = load_json(SOURCES)
    samples = [analyze_source(entry) for entry in config["sources"]]
    rules = aggregate(samples)
    neighbor = build_neighbor(config, rules)
    report = {
        "version": 1,
        "id": "m17_real_data_rule_extraction",
        "sources_manifest": repo_rel(SOURCES),
        "samples": samples,
        "rules": rules,
        "neighbor": neighbor,
    }
    write(OUT_JSON, json.dumps(report, indent=2) + "\n")
    write(OUT_RECIPE, json.dumps({"version": 1, "rules": rules, "neighbor": config["neighbor_target"], "build": neighbor}, indent=2) + "\n")
    write(OUT_MD, markdown(report))
    build_board(report)
    print(f"OK {repo_rel(OUT_JSON)}")
    print(f"OK {repo_rel(OUT_RECIPE)}")
    print(f"OK {repo_rel(OUT_MD)}")
    print(f"OK {repo_rel(OUT_BOARD)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
