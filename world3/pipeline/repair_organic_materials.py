#!/usr/bin/env python3
"""Build calmer organic material candidates for visual remediation.

This is not a magic production-texture generator. It is a deterministic repair
stage for M1-M7 remediation:

- suppress object-scale grass/leaf silhouettes;
- lower high-frequency and neon-green noise;
- emit neutral detail maps that can be used lightly in runtime shaders;
- keep outputs quarantined in a candidate catalog until terrain-context review.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
CATALOG = ROOT / "materials" / "catalog.json"
OUT_ROOT = ROOT / "textures" / "wgv3_repair"
CANDIDATE_CATALOG = ROOT / "materials" / "catalog_repair_candidates.json"
DOC_PATH = ROOT / "docs" / "M1_M7_ORGANIC_TEXTURE_REPAIR_2026_05_08.md"
CAPTURE_DIR = ROOT / "docs" / "captures" / "visual_remediation"


@dataclass(frozen=True)
class RepairProfile:
    target_mean: tuple[float, float, float]
    saturation: float
    detail_keep: float
    green_cap: float
    macro_radius: float
    mid_radius: float
    detail_radius: float
    normal_strength: float


PROFILES: dict[str, RepairProfile] = {
    "grassland_grass": RepairProfile((0.53, 0.48, 0.30), 0.48, 0.025, 0.09, 28.0, 9.0, 16.0, 0.85),
    "grass": RepairProfile((0.28, 0.38, 0.22), 0.36, 0.018, 0.06, 32.0, 10.0, 18.0, 0.75),
    "temperate_forest_grass": RepairProfile((0.34, 0.29, 0.23), 0.46, 0.020, 0.06, 28.0, 9.0, 16.0, 0.75),
    "tundra_moss": RepairProfile((0.30, 0.34, 0.29), 0.42, 0.030, 0.06, 28.0, 9.0, 18.0, 0.72),
    "tundra_lichen": RepairProfile((0.42, 0.44, 0.41), 0.35, 0.022, 0.05, 30.0, 10.0, 20.0, 0.70),
}


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO.resolve()).as_posix()


def load_catalog() -> dict[str, dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data.get("materials", [])}


def load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def save_rgb(arr: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="RGB").save(path)


def save_gray(arr: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="L").save(path)


def wrap_blur(arr: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0:
        return arr.copy()
    if arr.ndim == 3 and arr.shape[2] == 1:
        return wrap_blur(arr[..., 0], radius)[..., None]
    h, w = arr.shape[:2]
    tiled = np.tile(arr, (3, 3, 1)) if arr.ndim == 3 else np.tile(arr, (3, 3))
    mode = "RGB" if arr.ndim == 3 else "L"
    src = Image.fromarray(np.clip(tiled * 255.0 + 0.5, 0, 255).astype(np.uint8), mode=mode)
    # Pillow exposes filters through ImageFilter; keep the import local so the
    # filter dependency is obvious at the callsite.
    from PIL import ImageFilter

    blurred = src.filter(ImageFilter.GaussianBlur(radius))
    out = np.asarray(blurred, dtype=np.float32) / 255.0
    return out[h : h * 2, w : w * 2].copy()


def luminance(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def high_frequency_energy(rgb: np.ndarray) -> float:
    dx = np.abs(rgb[:, 1:, :] - rgb[:, :-1, :]).mean(axis=2)
    dy = np.abs(rgb[1:, :, :] - rgb[:-1, :, :]).mean(axis=2)
    return float((dx.mean() + dy.mean()) * 0.5)


def p95_gradient(rgb: np.ndarray) -> float:
    lum = luminance(rgb)
    dx = np.abs(lum[:, 1:] - lum[:, :-1]).ravel()
    dy = np.abs(lum[1:, :] - lum[:-1, :]).ravel()
    return float(np.percentile(np.concatenate([dx, dy]), 95))


def green_dominance(rgb: np.ndarray) -> float:
    rb = np.maximum(rgb[..., 0], rgb[..., 2])
    return float(np.mean(np.maximum(rgb[..., 1] - rb, 0.0)))


def saturation_mean(rgb: np.ndarray) -> float:
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    return float(np.mean((mx - mn) / np.maximum(mx, 1e-6)))


def metrics(rgb: np.ndarray) -> dict[str, float]:
    hf = high_frequency_energy(rgb)
    grad = p95_gradient(rgb)
    green = green_dominance(rgb)
    sat = saturation_mean(rgb)
    return {
        "high_frequency_energy": round(hf, 6),
        "gradient_p95": round(grad, 6),
        "green_dominance": round(green, 6),
        "saturation_mean": round(sat, 6),
        "noise_score": round(hf * (1.0 + sat) * (1.0 + green * 2.0), 6),
    }


def reduce_green(rgb: np.ndarray, cap: float) -> np.ndarray:
    out = rgb.copy()
    rb = np.maximum(out[..., 0], out[..., 2])
    max_green = rb + cap
    out[..., 1] = np.minimum(out[..., 1], max_green)
    return out


def target_color_mean(rgb: np.ndarray, target: tuple[float, float, float], strength: float = 0.62) -> np.ndarray:
    current = rgb.mean(axis=(0, 1))
    scale = np.asarray(target, dtype=np.float32) / np.maximum(current, 1e-4)
    corrected = np.clip(rgb * scale[None, None, :], 0.0, 1.0)
    return np.clip(rgb * (1.0 - strength) + corrected * strength, 0.0, 1.0)


def calm_albedo(rgb: np.ndarray, profile: RepairProfile) -> np.ndarray:
    macro = wrap_blur(rgb, profile.macro_radius)
    mid = wrap_blur(rgb, profile.mid_radius)
    detail = rgb - mid
    out = mid * 0.82 + macro * 0.18 + detail * profile.detail_keep
    gray = luminance(out)[..., None]
    out = gray * (1.0 - profile.saturation) + out * profile.saturation
    out = reduce_green(out, profile.green_cap)
    out = target_color_mean(out, profile.target_mean)
    return np.clip(out, 0.0, 1.0)


def neutral_detail(albedo: np.ndarray, profile: RepairProfile) -> np.ndarray:
    lum = luminance(albedo)
    base = wrap_blur(lum[..., None], profile.detail_radius)[..., 0]
    high = np.clip((lum - base) * 1.65 + 0.5, 0.0, 1.0)
    high = wrap_blur(high[..., None], 1.0)[..., 0]
    return np.repeat(high[..., None], 3, axis=2)


def height_from_albedo(albedo: np.ndarray) -> np.ndarray:
    lum = luminance(albedo)
    smooth = wrap_blur(lum[..., None], 2.0)[..., 0]
    lo, hi = np.percentile(smooth, [2.0, 98.0])
    return np.clip((smooth - lo) / max(hi - lo, 1e-6), 0.0, 1.0)


def normal_from_height(height: np.ndarray, strength: float) -> np.ndarray:
    dx = np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)
    dy = np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)
    nx = -dx * strength
    ny = -dy * strength
    nz = np.ones_like(height)
    inv = 1.0 / np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1e-6)
    normal = np.stack([nx * inv, ny * inv, nz * inv], axis=2)
    return normal * 0.5 + 0.5


def roughness_from_albedo(albedo: np.ndarray) -> np.ndarray:
    lum = luminance(albedo)
    detail = np.abs(lum - wrap_blur(lum[..., None], 8.0)[..., 0])
    return np.clip(0.70 + detail * 0.42, 0.58, 0.92)


def tile_2x2(img: Image.Image) -> Image.Image:
    out = Image.new(img.mode, (img.width * 2, img.height * 2))
    for y in range(2):
        for x in range(2):
            out.paste(img, (x * img.width, y * img.height))
    return out


def make_sheet(material_id: str, before: np.ndarray, after: np.ndarray, out_path: Path) -> None:
    tile = tile_2x2(Image.fromarray(np.clip(after * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="RGB"))
    before_img = Image.fromarray(np.clip(before * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="RGB")
    after_img = Image.fromarray(np.clip(after * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="RGB")
    panel_w = max(before_img.width, after_img.width, tile.width)
    panel_h = before_img.height + 34
    sheet = Image.new("RGB", (panel_w * 3, panel_h), (34, 36, 36))
    draw = ImageDraw.Draw(sheet)
    panels = [("source", before_img), ("repair", after_img), ("repair 2x2", tile.resize((before_img.width, before_img.height)))]
    for i, (label, img) in enumerate(panels):
        x = i * panel_w
        sheet.paste(img, (x, 34))
        draw.text((x + 10, 10), f"{material_id} {label}", fill=(240, 240, 235))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def candidate_entry(source: dict, candidate_id: str, out_dir: Path, report: dict) -> dict:
    return {
        "id": candidate_id,
        "source": source.get("source", "procedural"),
        "asset_status": "repair_candidate",
        "provenance": {
            "type": "deterministic_organic_repair_candidate",
            "source_material_id": source["id"],
            "tool": "world3/pipeline/repair_organic_materials.py",
            "policy": "object_silhouette_suppression_neutral_detail_quarantine",
            "metrics_before": report["metrics_before"],
            "metrics_after": report["metrics_after"],
            "operations": [
                "periodic_low_frequency_blur",
                "saturation_and_green_dominance_reduction",
                "target_mean_palette_fit",
                "neutral_detail_albedo_from_repaired_luminance",
                "normal_from_low_contrast_repaired_height",
            ],
            "settings": {
                "world_uv_scale": 0.015625,
                "hex_strength": 1.0,
                "blend_sharpness": 8.0,
                "roughness_strength": 1.0,
                "normal_strength": 0.0,
                "detail_uv_scale_mult": 12.0,
                "detail_albedo_strength": 0.015,
                "detail_normal_strength": 0.0,
                "detail_rough_strength": 0.0,
                "detail_fade_start_m": 4.0,
                "detail_fade_end_m": 30.0,
            },
        },
        "scale_m_per_repeat": source.get("scale_m_per_repeat", 10.0),
        "color_family": str(source.get("color_family", "")) + "-repair-calm",
        "runtime_texture_dir": rel(out_dir),
        "pbr_maps": {
            "albedo": rel(out_dir / "albedo_balanced.png"),
            "normal": rel(out_dir / "normal.png"),
            "roughness": rel(out_dir / "roughness.png"),
            "height": rel(out_dir / "height.png"),
            "ao": rel(out_dir / "ao_white.png"),
            "detail_albedo": rel(out_dir / "detail_albedo_neutral.png"),
            "detail_height": rel(out_dir / "detail_height.png"),
            "detail_normal": rel(out_dir / "detail_normal.png"),
            "detail_roughness": rel(out_dir / "detail_roughness.png"),
            "tile_2x2": rel(out_dir / "tile_2x2.png"),
        },
        "shader_binding": "terrain_hex_detail",
        "validated_views": {
            "close": "needs_review",
            "mid": "needs_review",
            "far": "needs_review",
        },
    }


def repair_one(material_id: str, entry: dict) -> tuple[dict, dict]:
    profile = PROFILES[material_id]
    source_path = REPO / entry["pbr_maps"]["albedo"]
    before = load_rgb(source_path)
    after = calm_albedo(before, profile)
    detail = neutral_detail(after, profile)
    height = height_from_albedo(after)
    normal = normal_from_height(height, profile.normal_strength)
    rough = roughness_from_albedo(after)
    ao = np.ones_like(height)
    candidate_id = f"{material_id}_repair_calm"
    out_dir = OUT_ROOT / candidate_id
    save_rgb(after, out_dir / "albedo_balanced.png")
    save_rgb(detail, out_dir / "detail_albedo_neutral.png")
    save_gray(height, out_dir / "height.png")
    save_gray(height, out_dir / "detail_height.png")
    save_rgb(normal, out_dir / "normal.png")
    save_rgb(normal, out_dir / "detail_normal.png")
    save_gray(rough, out_dir / "roughness.png")
    save_gray(rough, out_dir / "detail_roughness.png")
    save_gray(ao, out_dir / "ao_white.png")
    tile_2x2(Image.fromarray(np.clip(after * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="RGB")).save(out_dir / "tile_2x2.png")
    make_sheet(material_id, before, after, CAPTURE_DIR / f"{candidate_id}_before_after.png")

    report = {
        "source_material_id": material_id,
        "candidate_id": candidate_id,
        "source_albedo": rel(source_path),
        "candidate_dir": rel(out_dir),
        "sheet": rel(CAPTURE_DIR / f"{candidate_id}_before_after.png"),
        "metrics_before": metrics(before),
        "metrics_after": metrics(after),
    }
    manifest = {
        "version": 1,
        "kind": "organic_repair_candidate",
        **report,
        "target": "reduce_object_silhouette_noise_before_terrain_context_review",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return report, candidate_entry(entry, candidate_id, out_dir, report)


def write_candidate_catalog(entries: list[dict]) -> None:
    data = {
        "version": 1,
        "updated": "2026-05-08",
        "role": "quarantined_repair_candidates_not_canonical_catalog",
        "materials": entries,
    }
    CANDIDATE_CATALOG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_contact_sheet(reports: list[dict]) -> None:
    sheets = [Image.open(REPO / report["sheet"]).convert("RGB") for report in reports]
    if not sheets:
        return
    width = max(img.width for img in sheets)
    height = sum(img.height for img in sheets)
    out = Image.new("RGB", (width, height), (28, 30, 30))
    y = 0
    for img in sheets:
        out.paste(img, (0, y))
        y += img.height
    out.save(CAPTURE_DIR / "organic_repair_contact_sheet.png")


def write_doc(reports: list[dict]) -> None:
    lines = [
        "# M1-M7 Organic Texture Repair",
        "",
        "Date: 2026-05-08",
        "",
        "This is the first deterministic texture repair pass after the M1-M7",
        "vision audit. The outputs are candidates, not promotions. They are kept",
        "outside the canonical material catalog until terrain-context captures pass.",
        "",
        "Policy: reduce object-scale silhouettes and neon/high-frequency organic",
        "noise, then feed only calm albedo plus neutral detail into runtime review.",
        "",
        "Contact sheet:",
        "",
        "- `docs/captures/visual_remediation/organic_repair_contact_sheet.png`",
        "",
        "| Source | Candidate | HF before | HF after | Grad before | Grad after | Green before | Green after | Sheet |",
        "|--------|-----------|-----------|----------|-------------|------------|--------------|-------------|-------|",
    ]
    for r in reports:
        before = r["metrics_before"]
        after = r["metrics_after"]
        lines.append(
            f"| `{r['source_material_id']}` | `{r['candidate_id']}` | "
            f"{before['high_frequency_energy']} | {after['high_frequency_energy']} | "
            f"{before['gradient_p95']} | {after['gradient_p95']} | "
            f"{before['green_dominance']} | {after['green_dominance']} | "
            f"`{r['sheet']}` |"
        )
    lines += [
        "",
        "## Verdict",
        "",
        "This pass fixes the worst workflow problem: procedural organic images are",
        "no longer allowed to enter M2/M5/M7 as raw object-photo tiles. The repair",
        "candidates are calmer, but still need Godot close/mid/far terrain-context",
        "review before any `close = ok` promotion.",
        "",
        "Runtime use rule:",
        "",
        "1. Keep these candidates in `materials/catalog_repair_candidates.json`.",
        "2. Bind them as albedo-only/low-strength detail in source-stack review.",
        "3. Do not promote normal/detail influence until terrain-context captures",
        "   reach the 70 percent target.",
    ]
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materials", nargs="*", default=list(PROFILES.keys()))
    args = ap.parse_args()
    catalog = load_catalog()
    reports: list[dict] = []
    candidates: list[dict] = []
    for material_id in args.materials:
        if material_id not in PROFILES:
            raise KeyError(f"No repair profile for {material_id}")
        if material_id not in catalog:
            raise KeyError(f"Material not in catalog: {material_id}")
        report, entry = repair_one(material_id, catalog[material_id])
        reports.append(report)
        candidates.append(entry)
        before = report["metrics_before"]["noise_score"]
        after = report["metrics_after"]["noise_score"]
        print(f"{material_id}: noise_score {before} -> {after}")
    write_candidate_catalog(candidates)
    write_contact_sheet(reports)
    write_doc(reports)
    print(f"wrote {rel(CANDIDATE_CATALOG)}")
    print(f"wrote {rel(DOC_PATH)}")
    print(f"wrote {rel(CAPTURE_DIR / 'organic_repair_contact_sheet.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
