"""Phase F.6 — in-context material re-audit.

For each biome in a world plan, render one of its tiles through the
E.4 orchestrator capture driver in iso mode, then re-compute the F.4
diagnostic metrics on the rendered PNG and compare them to the
catalog-time metrics. Flags drift between "what the material looks
like as a tiled albedo" and "what it looks like rendered through
the actual shader + lighting + tour profile."

Closes the audit loop: catalog (F.4 static metrics) -> runtime
(F.6 rendered metrics) -> drift verdict per biome.

Output: world3/jobs/in_context_audits/<plan_id>.json

Usage:
    python world3/pipeline/audit_materials_in_context.py world3/jobs/examples/world_plan_starter_5biome_procedural.json
    python world3/pipeline/audit_materials_in_context.py <plan> --skip-render  # use existing captures
    python world3/pipeline/audit_materials_in_context.py <plan> --json

Exit codes: 0 ok / 1 any biome failed render / 2 internal
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
WORLD3 = Path(__file__).resolve().parents[1]
WORLDS_DIR = WORLD3 / "worlds"
WGV3_DIR = WORLD3 / "textures" / "wgv3"
AUDITS_OUT_DIR = WORLD3 / "jobs" / "in_context_audits"
CAPTURES_DIR = WORLD3 / "docs" / "captures" / "review"

# Match F.4's metric helpers — duplicated minimally rather than imported
# to avoid coupling F.6 to F.4's internals.
def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    a = rgb.astype(np.float32)
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]], dtype=np.float32)
    xyz = lin @ M.T
    white = np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    xyz_n = xyz / white
    eps = (6.0 / 29.0) ** 3
    f = np.where(xyz_n > eps,
                 np.cbrt(xyz_n),
                 (xyz_n / (3 * (6.0/29.0) ** 2)) + (4.0 / 29.0))
    L = 116.0 * f[..., 1] - 16.0
    a_ = 500.0 * (f[..., 0] - f[..., 1])
    b_ = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a_, b_], axis=-1)


def material_metrics(rgb: np.ndarray) -> dict:
    """Same metric definitions F.4 uses on tiled albedos."""
    # Median Lab
    flat = rgb.reshape(-1, 3)
    med_rgb = np.median(flat, axis=0)
    med_lab = rgb_to_lab(med_rgb.reshape(1, 1, 3))[0, 0]

    # Luminance p5..p95
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    p5, p95 = float(np.percentile(lum, 5)), float(np.percentile(lum, 95))

    # High-frequency energy (3x3 box residual)
    pad = np.pad(lum, 1, mode="edge")
    blurred = (
        pad[:-2, :-2] + pad[:-2, 1:-1] + pad[:-2, 2:] +
        pad[1:-1, :-2] + pad[1:-1, 1:-1] + pad[1:-1, 2:] +
        pad[2:, :-2] + pad[2:, 1:-1] + pad[2:, 2:]
    ) / 9.0
    hf = float(np.mean(np.abs(lum - blurred)))

    return {
        "median_lab": [float(x) for x in med_lab],
        "luminance_p5_p95": [p5, p95],
        "luminance_range": p95 - p5,
        "high_freq_energy": hf,
    }


def load_png_center_patch(path: Path, patch_size: int = 512) -> np.ndarray:
    """Load a capture PNG and return a center patch as float32 RGB 0..1.
    Center patch avoids the HUD overlay in the top-left and the screen
    edges where the tour camera frames terrain edges."""
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]
    cy, cx = h // 2, w // 2
    half = patch_size // 2
    y0 = max(0, cy - half)
    x0 = max(0, cx - half)
    y1 = min(h, cy + half)
    x1 = min(w, cx + half)
    return arr[y0:y1, x0:x1]


def load_catalog_albedo_metrics(material_id: str) -> dict | None:
    path = WGV3_DIR / material_id / "albedo.png"
    if not path.exists():
        return None
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return material_metrics(arr)


def find_first_tile_for_biome(world_map: dict, biome_id: str) -> dict | None:
    for tile in world_map["tiles"]:
        if tile["biome"] == biome_id:
            return tile
    return None


def render_iso_capture(tile: dict, biome_kit: str, style_pack: str,
                        output_path: Path) -> tuple[bool, str]:
    """Drive run_orchestrator_capture.py on this tile in iso mode."""
    import subprocess
    bundle_dir_res = "res://" + tile["bundle_dir"].replace("world3/", "", 1).replace("\\", "/")
    material_res = f"res://textures/wgv3/terrain_blend_{biome_kit}.tres"
    output_res = "res://" + str(output_path.relative_to(WORLD3)).replace("\\", "/")
    macro_res = bundle_dir_res + "/layers/render_albedo.png"
    mask_res = bundle_dir_res + "/layers/source_valid_mask.png"

    # Compute reasonable framing from bundle meta if present
    start_x = 60
    start_z = 120
    chunk_size = 120
    chunk_res = 4
    meta_disk = ROOT / tile["bundle_dir"] / "meta.json"
    if meta_disk.exists():
        try:
            meta = json.loads(meta_disk.read_text(encoding="utf-8"))
            wx = meta.get("world_size_x_m", 240.0)
            wz = meta.get("world_size_z_m", 240.0)
            start_x = wx / 2
            start_z = wz / 2
            chunk_size = max(min(wx, wz), 32)
        except Exception:
            pass

    cmd = [
        sys.executable, str(WORLD3 / "pipeline" / "run_orchestrator_capture.py"),
        "--bundle-dir", bundle_dir_res,
        "--material", material_res,
        "--mode", "iso",
        "--output", output_res,
        "--style-pack", style_pack,
        "--macro-albedo", macro_res,
        "--macro-mask", mask_res,
        "--start-x", str(start_x),
        "--start-z", str(start_z),
        "--chunk-size", str(chunk_size),
        "--chunk-resolution", str(chunk_res),
        "--warmup-frames", "60",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return False, f"exit={result.returncode}: {result.stderr[-300:]}"
        return True, "ok"
    except subprocess.TimeoutExpired:
        return False, "timeout (120s)"


def lab_distance(a: list[float], b: list[float]) -> float:
    return float(np.linalg.norm(np.array(a) - np.array(b)))


def classify_drift(catalog: dict, rendered: dict) -> tuple[str, list[str]]:
    """Return (verdict, notes) comparing catalog vs rendered metrics."""
    notes: list[str] = []
    palette_drift = lab_distance(catalog["median_lab"], rendered["median_lab"])
    lum_range_drift = abs(catalog["luminance_range"] - rendered["luminance_range"])
    eps = 1e-6
    hf_ratio = max(catalog["high_freq_energy"], rendered["high_freq_energy"]) / max(
        min(catalog["high_freq_energy"], rendered["high_freq_energy"]), eps
    )

    verdict = "pass"
    if palette_drift >= 40.0:
        notes.append(f"palette drift Lab={palette_drift:.1f} (catalog vs rendered)")
        verdict = "fail"
    elif palette_drift >= 20.0:
        notes.append(f"palette drift Lab={palette_drift:.1f}")
        verdict = "warn" if verdict == "pass" else verdict

    if lum_range_drift >= 0.4:
        notes.append(f"luminance range drift={lum_range_drift:.2f}")
        verdict = "fail"
    elif lum_range_drift >= 0.2:
        notes.append(f"luminance range drift={lum_range_drift:.2f}")
        verdict = "warn" if verdict == "pass" else verdict

    if hf_ratio >= 4.0:
        notes.append(f"high-freq energy ratio={hf_ratio:.2f}")
        verdict = "fail"
    elif hf_ratio >= 2.0:
        notes.append(f"high-freq energy ratio={hf_ratio:.2f}")
        verdict = "warn" if verdict == "pass" else verdict

    return verdict, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("plan", type=Path)
    ap.add_argument("--skip-render", action="store_true",
                    help="Skip the orchestrator capture step (re-use existing captures)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.plan.exists():
        print(f"ERROR: plan not found at {args.plan}", file=sys.stderr)
        return 2
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    plan_id = plan["id"]

    world_map_path = WORLDS_DIR / plan_id / "world_map.json"
    if not world_map_path.exists():
        print(f"ERROR: world map not found at {world_map_path}", file=sys.stderr)
        print(f"       Run world_plan_to_bundles.py --run first", file=sys.stderr)
        return 2
    world_map = json.loads(world_map_path.read_text(encoding="utf-8"))

    style_pack = plan.get("style_pack", "photoreal")

    print(f"=== audit_materials_in_context ===")
    print(f"Plan: {plan_id}")
    print(f"Biomes: {len(plan['biomes'])}")
    print()

    results = []
    render_failures = 0
    for biome in plan["biomes"]:
        bid = biome["id"]
        material_id = biome.get("primary_material_id") or biome.get("source", {}).get("material_id")
        tile = find_first_tile_for_biome(world_map, bid)
        if tile is None:
            print(f"  [ERR ] {bid}: no tile found in world map")
            results.append({"biome": bid, "verdict": "error", "reason": "no tile in world map"})
            continue

        capture_path = CAPTURES_DIR / f"in_context_{plan_id}_{bid}_iso.png"
        capture_path.parent.mkdir(parents=True, exist_ok=True)

        if not args.skip_render or not capture_path.exists():
            ok, msg = render_iso_capture(tile, biome["biome_kit"], style_pack, capture_path)
            if not ok:
                print(f"  [FAIL] {bid}: render failed: {msg}")
                results.append({"biome": bid, "verdict": "error", "reason": f"render failed: {msg}"})
                render_failures += 1
                continue

        if not capture_path.exists():
            print(f"  [FAIL] {bid}: capture missing at {capture_path}")
            results.append({"biome": bid, "verdict": "error", "reason": "capture missing after render"})
            render_failures += 1
            continue

        patch = load_png_center_patch(capture_path)
        rendered = material_metrics(patch)
        catalog = load_catalog_albedo_metrics(material_id)
        if catalog is None:
            print(f"  [WARN] {bid}: no catalog albedo for {material_id}")
            results.append({"biome": bid, "verdict": "error", "reason": f"no catalog albedo for {material_id}"})
            continue

        verdict, notes = classify_drift(catalog, rendered)
        sym = {"pass": "OK  ", "warn": "WARN", "fail": "FAIL"}[verdict]
        print(f"  [{sym}] {bid:<18} ({material_id})  tile={tile['tile_xy']}")
        for note in notes:
            print(f"           - {note}")
        results.append({
            "biome": bid,
            "material_id": material_id,
            "tile_xy": tile["tile_xy"],
            "capture_path": str(capture_path.relative_to(WORLD3)).replace("\\", "/"),
            "catalog_metrics": catalog,
            "rendered_metrics": rendered,
            "verdict": verdict,
            "notes": notes,
        })

    AUDITS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUDITS_OUT_DIR / f"{plan_id}.json"
    doc = {
        "schema_version": 1,
        "plan_id": plan_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "biome_count": len(plan["biomes"]),
        "results": results,
        "pass_count": sum(1 for r in results if r["verdict"] == "pass"),
        "warn_count": sum(1 for r in results if r["verdict"] == "warn"),
        "fail_count": sum(1 for r in results if r["verdict"] == "fail"),
        "error_count": sum(1 for r in results if r["verdict"] == "error"),
    }
    out_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    print()
    print(f"--- Summary ---")
    print(f"  pass={doc['pass_count']} warn={doc['warn_count']} fail={doc['fail_count']} error={doc['error_count']}")
    print(f"  written: {out_path.relative_to(ROOT)}")
    print()
    print(f"=== audit_materials_in_context DONE ===")

    if args.json:
        print()
        print(json.dumps(doc, indent=2))

    return 1 if render_failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
