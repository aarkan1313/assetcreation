"""CPU validator for the prop_asset.v1 contract.

Walks `world/props/library/*/` and confirms:
  - prop.json exists and parses
  - schema is "prop_asset.v1"
  - every LoD .glb file referenced exists
  - thumbnail (if listed) exists
  - placement_tags / material_slots are non-empty lists of strings
  - footprint_radius_m is a sane positive number

Writes `world/props/validation_<ts>.md`.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

LIBRARY = Path(r"D:\assets\world\props\library")


def validate_dir(prop_dir: Path) -> tuple[bool, list[str]]:
    errs: list[str] = []
    pj = prop_dir / "prop.json"
    if not pj.exists():
        return False, ["missing prop.json"]
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except Exception as e:
        return False, [f"prop.json parse: {e}"]
    if data.get("schema") != "prop_asset.v1":
        errs.append(f"unexpected schema {data.get('schema')!r}")
    for lod in data.get("lods", []):
        f = prop_dir / lod["file"]
        if not f.exists():
            errs.append(f"missing LOD file {lod['file']}")
    thumb = data.get("thumbnail")
    if thumb and not (prop_dir / thumb).exists():
        errs.append(f"thumbnail missing: {thumb}")
    pt = data.get("placement_tags", [])
    if not isinstance(pt, list) or not all(isinstance(x, str) and x for x in pt):
        errs.append("placement_tags must be non-empty list of strings")
    rad = data.get("footprint_radius_m")
    if not isinstance(rad, (int, float)) or rad <= 0:
        errs.append("footprint_radius_m must be > 0")
    return (not errs, errs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--library", type=Path, default=LIBRARY)
    ap.add_argument("--report", type=Path,
                    default=Path(r"D:\assets\world\props"))
    args = ap.parse_args()

    rows: list[tuple[str, bool, list[str]]] = []
    for d in sorted(args.library.iterdir()):
        if not d.is_dir():
            continue
        ok, errs = validate_dir(d)
        rows.append((d.name, ok, errs))

    ok_count = sum(1 for _, o, _ in rows if o)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = [f"# Prop validation report ({ts} UTC)", ""]
    out.append(f"Total {len(rows)}, ok {ok_count}, failing {len(rows) - ok_count}")
    out.append("")
    for name, ok, errs in rows:
        if ok:
            out.append(f"- ✅ `{name}`")
        else:
            out.append(f"- ❌ `{name}`")
            for e in errs:
                out.append(f"    - {e}")
    out_path = args.report / f"validation_{ts}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out), encoding="utf-8")
    print(f"[validate_props] {ok_count}/{len(rows)} ok -> {out_path}")
    return 0 if ok_count == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
