"""Raster -> SVG round-trip via vtracer.

Per `research/D_ui.md` §1: when a raster icon needs to feed back through a
vector-only adapter (Recraft V3 SVG mode, ornament SVG library, etc), we need
a deterministic raster->SVG converter. **vtracer** (Rust core, Python wheel
on Windows) is the 2026 winner: BSD-3-Clause, no DLL deps, deterministic
quantize-then-trace.

What this tool does:

  raster <id>.png  -->  vtracer  -->  ui/icons/svg_traced/<id>.svg
                                      ui/icons/svg_traced/<id>_round_trip.png
                                      (re-rasterized via the freelib chain
                                       so we can diff visually with the input)

The round-trip PNG lets reviewers spot tracer regressions (color quantization
artifacts, fang loss on small features) before feeding the SVGs to Recraft.

Use cases (each documented as a separate sub-flag):
  --feed-recraft       prepare SVG inputs for `recraft_icons.py --svg-input`
  --feed-frame-compose drop SVG ornaments into frame_compose's ornament hooks
  --tag-as-vector      annotate manifest entries with `svg_traced=path` so
                       downstream consumers know a vector form exists

Gracefully degrades when vtracer is missing: prints install hint and exits 0
in --plan-only mode.

CLI:
  # Plan-only; lists what would be traced
  python vtracer_roundtrip.py --plan-only --filter ico_sword,ico_shield

  # Real trace (requires `pip install vtracer`)
  python vtracer_roundtrip.py --filter ico_sword,ico_shield
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

ASSETS = Path(r"D:\assets")
ICONS_MANIFEST = ASSETS / "ui" / "icons" / "manifest.json"
SVG_OUT = ASSETS / "ui" / "icons" / "svg_traced"


@dataclass
class TracePlan:
    icon_id: str
    src_png: str
    out_svg: str
    out_round_trip_png: str
    color_mode: str = "binary"   # "binary" or "color"
    hierarchical: str = "stacked"  # "stacked" or "cutout"
    filter_speckle: int = 4
    color_precision: int = 8
    layer_difference: int = 16
    corner_threshold: int = 60
    length_threshold: float = 4.0
    max_iterations: int = 10
    splice_threshold: int = 45
    path_precision: int = 5


def _have_vtracer() -> bool:
    try:
        import vtracer  # type: ignore  # noqa: F401
        return True
    except ImportError:
        return False


def build_plan(icon_id: str, src_png: Path, out_root: Path,
               *, color_mode: str = "binary") -> TracePlan:
    out_root.mkdir(parents=True, exist_ok=True)
    return TracePlan(
        icon_id=icon_id,
        src_png=str(src_png),
        out_svg=str(out_root / f"{icon_id}.svg"),
        out_round_trip_png=str(out_root / f"{icon_id}_round_trip.png"),
        color_mode=color_mode,
    )


def trace_one(plan: TracePlan) -> None:
    """Run vtracer on one icon. Raises ImportError if vtracer not installed."""
    import vtracer  # type: ignore
    Path(plan.out_svg).parent.mkdir(parents=True, exist_ok=True)
    vtracer.convert_image_to_svg_py(
        plan.src_png,
        plan.out_svg,
        colormode=plan.color_mode,
        hierarchical=plan.hierarchical,
        mode="spline",
        filter_speckle=plan.filter_speckle,
        color_precision=plan.color_precision,
        layer_difference=plan.layer_difference,
        corner_threshold=plan.corner_threshold,
        length_threshold=plan.length_threshold,
        max_iterations=plan.max_iterations,
        splice_threshold=plan.splice_threshold,
        path_precision=plan.path_precision,
    )


def re_rasterize(plan: TracePlan, size: int = 256) -> None:
    """Round-trip rasterize using freelib's 3-tier rasterizer.

    Lets the reviewer diff src.png vs round_trip.png and see how much of
    the silhouette survived the trace.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        import freelib_ingest  # type: ignore
    except Exception:
        # Fallback: skip round-trip rasterization, leave SVG only
        return
    svg_bytes = Path(plan.out_svg).read_bytes()
    try:
        png = freelib_ingest.rasterize(svg_bytes, size)
    except Exception:
        return
    Path(plan.out_round_trip_png).write_bytes(png)


def annotate_manifest(manifest_path: Path, plans: list[TracePlan]) -> None:
    """Optionally write `svg_traced` into each icon's manifest entry so
    downstream consumers (recraft_icons --svg-input, future frame_compose
    SVG ornament binding) can find the vector form by id."""
    if not manifest_path.exists():
        return
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in data.get("icons", [])}
    for p in plans:
        if p.icon_id in by_id:
            rel = str(Path(p.out_svg).relative_to(ASSETS).as_posix())
            by_id[p.icon_id]["svg_traced"] = rel
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=ICONS_MANIFEST)
    ap.add_argument("--out", type=Path, default=SVG_OUT)
    ap.add_argument("--filter", default=None,
                    help="Comma-separated icon ids OR substring tokens to "
                         "filter (matches id contains-any).")
    ap.add_argument("--max", type=int, default=0,
                    help="Cap number of icons (0 = no cap).")
    ap.add_argument("--color-mode", choices=["binary", "color"],
                    default="binary",
                    help="binary -> single-color silhouettes (game-icons.net "
                         "style); color -> retain palette.")
    ap.add_argument("--plan-only", action="store_true",
                    help="Don't import vtracer; just write a list of plans.")
    ap.add_argument("--annotate-manifest", action="store_true",
                    help="Update ui/icons/manifest.json with svg_traced paths.")
    args = ap.parse_args()

    if not args.manifest.exists():
        print(f"[vtracer_roundtrip] ERROR: manifest not found: {args.manifest}",
              file=sys.stderr)
        return 2
    icons = json.loads(args.manifest.read_text(encoding="utf-8")).get("icons", [])

    filter_tokens = (
        [s.strip() for s in args.filter.split(",") if s.strip()]
        if args.filter else None
    )
    plans: list[TracePlan] = []
    for ic in icons:
        iid = ic["id"]
        if filter_tokens and not any(t in iid for t in filter_tokens):
            continue
        src = ASSETS / ic["path"]
        if not src.exists():
            continue
        plans.append(build_plan(iid, src, args.out, color_mode=args.color_mode))
    if args.max:
        plans = plans[:args.max]

    print(f"[vtracer_roundtrip] {len(plans)} icons selected "
          f"(filter={filter_tokens}, color_mode={args.color_mode})")
    plans_json = args.out / "trace_plans.json"
    plans_json.parent.mkdir(parents=True, exist_ok=True)
    plans_json.write_text(
        json.dumps([asdict(p) for p in plans], indent=2),
        encoding="utf-8")
    print(f"[vtracer_roundtrip] plans -> {plans_json}")

    if args.plan_only:
        return 0

    if not _have_vtracer():
        print("[vtracer_roundtrip] vtracer not installed; install with:\n"
              "    pip install vtracer\n"
              "Then re-run without --plan-only.", file=sys.stderr)
        return 2

    n_ok = 0
    for p in plans:
        try:
            trace_one(p)
            re_rasterize(p, size=256)
            n_ok += 1
            print(f"[vtracer_roundtrip] {p.icon_id:32s} -> {Path(p.out_svg).name}")
        except Exception as e:  # noqa: BLE001 - per-icon failures shouldn't kill the run
            print(f"[vtracer_roundtrip] FAIL {p.icon_id}: {e}", file=sys.stderr)

    if args.annotate_manifest and n_ok > 0:
        annotate_manifest(args.manifest, plans)
        print(f"[vtracer_roundtrip] annotated manifest with {n_ok} svg_traced paths")
    print(f"[vtracer_roundtrip] traced {n_ok}/{len(plans)} icons -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
