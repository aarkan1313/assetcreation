"""Run the audit's 16-combo experiment on a representative prompt.

Tests the 4 highest-leverage axes from
docs/plans/TEXTURE_PIPELINE_AUDIT_2026_05_12.md:

  1. FLUX heal denoise   (A: 1.0 silent / B: 0.35 honored)
  2. Delight strength    (A: 0.4 / B: 0.0 skip)
  3. PBR backend         (A: sm / B: derive)
  4. Heal mode           (A: flux_heal / B: none)   <- proxy for "external repair"

NOTE on axis 1: 'A=1.0 silent' is approximated by setting heal_denoise=1.0
explicitly in tx_seamless (which now always honors it via BasicScheduler).
We can't reproduce the upstream's "Flux2Scheduler silently ignores
denoise" behavior anymore in W4 code — we just run heal at 1.0 vs 0.35.
This is actually cleaner: it proves whether 0.35 is better than 1.0 on
the same correct scheduler.

2^4 = 16 combos × 1 prompt × 1 variant = 16 generations.
Output to D:/assets/world 4/the world 4/candidates/_pipeline_review/audit/
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from tx_pipeline import PipelineSettings, run_pipeline


# The 4 axes from the audit.
AXES = {
    "heal_denoise": [1.0, 0.35],     # A: full / B: gentle
    "delight":     [0.4, 0.0],       # A: current default / B: skip
    "pbr":         ["sm", "derive"], # A: SM / B: derive heuristic
    "heal_mode":   ["flux_heal", "none"],  # A: 4-pass / B: pass1 only
}

# Single prompt that's been A-grade in old QA. Easier to detect
# *worsening* on a known-good baseline.
PROMPT = ("tileable seamless texture, wind-packed snow with sastrugi "
          "ridges, sharp wind-carved striations, bright white, overhead "
          "perspective")
ASSET_ID_BASE = "audit_windpack"
OUT_ROOT = Path(r"D:\assets\world 4\the world 4\candidates\_pipeline_review\audit")


def combo_label(combo: dict) -> str:
    """Compact label for a combo. e.g. 'h0.35_d0.0_pbrderive_modeflux'."""
    return (f"h{combo['heal_denoise']}"
            f"_d{combo['delight']}"
            f"_pbr{combo['pbr']}"
            f"_mode{combo['heal_mode'].split('_')[0]}")


def run_matrix(prompt: str, asset_id_base: str, out_root: Path,
               size: int, dry_run: bool) -> dict:
    out_root.mkdir(parents=True, exist_ok=True)
    combos = list(itertools.product(
        AXES["heal_denoise"], AXES["delight"], AXES["pbr"], AXES["heal_mode"]))
    print(f"\n[experiment] {len(combos)} combos × 1 variant each")
    print(f"  prompt: {prompt!r}")
    print(f"  out_root: {out_root}")
    print(f"  size: {size}")
    print(f"  dry_run: {dry_run}")
    results = []
    t_start = time.time()
    for i, (hd, dl, pbr, hmode) in enumerate(combos, 1):
        combo = {"heal_denoise": hd, "delight": dl, "pbr": pbr,
                 "heal_mode": hmode}
        label = combo_label(combo)
        cdir = out_root / label
        if cdir.exists() and (cdir / "manifest.json").exists():
            print(f"\n[{i:02d}/16] {label} — exists, skipping")
            results.append(json.loads(
                (cdir / "manifest.json").read_text(encoding="utf-8")))
            continue
        print(f"\n[{i:02d}/16] {label}")
        if dry_run:
            print("  (dry-run: skip)")
            continue
        settings = PipelineSettings(
            size=size, variants=1, seed_base=42,
            heal_denoise=hd, heal_mode=hmode,
            delight_strength=dl, pbr_backend=pbr,
            category="Snow",
        )
        try:
            manifest = run_pipeline(prompt, f"{asset_id_base}_{label}", cdir,
                                    settings)
        except Exception as e:
            print(f"  FAILED: {e}")
            manifest = {
                "asset_id": asset_id_base, "label": label,
                "settings": asdict(settings), "status": "failed", "error": str(e),
            }
            cdir.mkdir(parents=True, exist_ok=True)
            (cdir / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8")
        manifest["label"] = label
        manifest["combo"] = combo
        results.append(manifest)
    elapsed = time.time() - t_start
    summary = {
        "prompt": prompt,
        "n_combos": len(combos),
        "elapsed_seconds": round(elapsed, 1),
        "results": results,
    }
    (out_root / "matrix_summary.json").write_text(
        json.dumps(summary, indent=2, default=float), encoding="utf-8")
    print(f"\n[experiment] done. {elapsed:.0f}s elapsed.")
    return summary


def build_comparison_sheet(out_root: Path) -> Path:
    """Build a 4x4 grid comparison sheet of all 16 combo albedos."""
    label_h = 32
    thumb = 384
    cell_w = thumb + 8
    cell_h = thumb + label_h + 8
    cols, rows = 4, 4
    sheet_w = cols * cell_w + 16
    sheet_h = rows * cell_h + 80
    sheet = Image.new("RGB", (sheet_w, sheet_h), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
        title_font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
        title_font = font
    draw.text((16, 16), "Audit matrix — 16 combos × windpack prompt",
              font=title_font, fill=(230, 230, 230))
    draw.text((16, 44), "axes: heal_denoise, delight, pbr, heal_mode",
              font=font, fill=(180, 180, 180))

    cells = sorted(out_root.glob("h*/manifest.json"))
    for i, mf in enumerate(cells[:16]):
        manifest = json.loads(mf.read_text(encoding="utf-8"))
        label = manifest.get("label", mf.parent.name)
        grade = manifest.get("grade", "-")
        alb = mf.parent / "albedo.png"
        r, c = divmod(i, cols)
        x = 8 + c * cell_w
        y = 80 + r * cell_h
        if alb.exists():
            img = Image.open(alb).convert("RGB").resize((thumb, thumb),
                                                        Image.LANCZOS)
            sheet.paste(img, (x, y))
        # label strip
        strip_y = y + thumb
        grade_color = {"A": (40, 200, 80), "B": (220, 180, 30),
                       "C": (240, 130, 30), "D": (220, 60, 60)}.get(grade, (140, 140, 140))
        draw.rectangle([x, strip_y, x + 28, strip_y + label_h], fill=grade_color)
        draw.text((x + 6, strip_y + 5), grade, font=title_font, fill=(0, 0, 0))
        draw.text((x + 34, strip_y + 2), label[:30], font=font, fill=(230, 230, 230))
        # second line: passed checks
        passed = manifest.get("stages", [])
        qa_stage = next((s for s in passed if s.get("stage") == "qa"), {})
        failed = qa_stage.get("failed") or []
        if failed:
            draw.text((x + 34, strip_y + 18),
                      f"fails: {','.join(failed)[:35]}",
                      font=font, fill=(220, 100, 100))
    out = out_root / "_comparison_sheet.png"
    sheet.save(out)
    print(f"wrote {out}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--out-root", type=Path, default=OUT_ROOT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sheet-only", action="store_true",
                    help="skip generation; just rebuild the comparison sheet from existing outputs")
    args = ap.parse_args()
    if not args.sheet_only:
        run_matrix(PROMPT, ASSET_ID_BASE, args.out_root, args.size, args.dry_run)
    build_comparison_sheet(args.out_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
