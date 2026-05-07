"""Billboard atlas baker — orchestrator wrapping proc_billboard.py.

For each prop, renders an N-angle horizontal strip atlas of the LOD0 model
on a transparent background. Default: 8 angles × 256px = 2048×256 PNG.
Updates prop.json with a `billboard` field.

The Godot side: the multi-LOD scene exporter already wires Sprite3D ->
billboard.png as the final tier. For 8-angle parallax-correct sampling we'd
need a small custom shader to slice by camera yaw — left for later. The
single-strip atlas works as input for that future shader, AND a single
front-facing slice already works as an okay impostor for grass/rocks etc.

CLI:
  python billboard_bake.py rock_small_demo
  python billboard_bake.py barrel_a01 --angles 8 --tile-px 256
  python billboard_bake.py --all
  python billboard_bake.py --all --single  # cheap front-only
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = Path(r"D:\assets")
CONFIG = json.loads((ASSETS / "meshy" / "config.json").read_text())
BLENDER = Path(CONFIG["blender_exe"])
LIBRARY = ASSETS / "world" / "props" / "library"
SCRIPT = ROOT / "blender_scripts" / "proc_billboard.py"


def bake_one(prop_dir: Path, *, angles: int, tile_px: int,
             single: bool, elevation: float) -> dict:
    src = prop_dir / "model_lod0.glb"
    if not src.exists():
        return {"id": prop_dir.name, "ok": False, "err": "no model_lod0.glb"}
    out = prop_dir / "billboard.png"
    cmd = [
        str(BLENDER),
        "--background",
        "--factory-startup",
        "--python", str(SCRIPT),
        "--",
        "--in", str(src),
        "--out", str(out),
        "--angles", str(angles),
        "--tile-px", str(tile_px),
        "--elevation-deg", str(elevation),
    ]
    if single:
        cmd.append("--single")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return {"id": prop_dir.name, "ok": False,
                "err": (r.stdout[-500:] + "\n" + r.stderr[-500:])[-800:]}
    if not out.exists():
        return {"id": prop_dir.name, "ok": False, "err": "billboard.png not produced"}

    # Update prop.json
    pj = prop_dir / "prop.json"
    if pj.exists():
        data = json.loads(pj.read_text(encoding="utf-8"))
        data["billboard"] = {
            "file": "billboard.png",
            "angles": 1 if single else angles,
            "tile_px": tile_px,
            "atlas_layout": "h_strip" if not single else "single",
        }
        pj.write_text(json.dumps(data, indent=2))

    return {"id": prop_dir.name, "ok": True,
            "angles": 1 if single else angles, "tile_px": tile_px}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--library", type=Path, default=LIBRARY)
    ap.add_argument("--angles", type=int, default=8)
    ap.add_argument("--tile-px", type=int, default=256)
    ap.add_argument("--single", action="store_true")
    ap.add_argument("--elevation", type=float, default=20.0)
    args = ap.parse_args()

    if not args.all and not args.ids:
        print("usage: billboard_bake.py <id>... | --all", file=sys.stderr)
        return 1

    candidates: list[Path] = []
    if args.all:
        for d in sorted(args.library.iterdir()):
            if d.is_dir() and (d / "model_lod0.glb").exists():
                candidates.append(d)
    candidates.extend(args.library / pid for pid in args.ids)

    rows = []
    for prop_dir in candidates:
        result = bake_one(prop_dir, angles=args.angles, tile_px=args.tile_px,
                          single=args.single, elevation=args.elevation)
        rows.append(result)
        if result["ok"]:
            print(f"[billboard_bake] {result['id']}  angles={result['angles']}  tile={result['tile_px']}px")
        else:
            print(f"[billboard_bake] {result['id']}  FAIL {result['err'][-300:]}",
                  file=sys.stderr)

    n_ok = sum(1 for r in rows if r["ok"])
    print(f"[billboard_bake] {n_ok}/{len(rows)} ok")
    return 0 if n_ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
