"""Phase E: emit per-game-mode terrain_blend material variants for each kit.

For each kit + mode in (walk, iso, topdown), reads the kit's existing
`terrain_blend_<kit>.tres`, replaces the tunable shader params with
mode-specific values, and writes `terrain_blend_<kit>_<mode>.tres`. The
ext_resource lines (texture paths, shader path) are passed through
unchanged so each variant uses the same texture set.

Per-mode tuning rationale (per ROADMAP Phase E):
- walk:    1-3m repeat (close-up dominates), sharp normals, low macro_value
- iso:     10-20m repeat (mid-detail), moderate normals, moderate macro
- topdown: 50-100m repeat (color-blocking dominates), muted normals, high macro

`world_uv_scale` is multiplied by world position to drive texture sampling,
so HIGHER scale = more repeats per meter = closer-feeling detail. So:
- walk:    world_uv_scale ~0.4   (~2.5m repeat)
- iso:     world_uv_scale ~0.1   (~10m repeat) — current default
- topdown: world_uv_scale ~0.02  (~50m repeat)

Usage:
    python pipelines/textures/emit_per_mode_materials.py
    python pipelines/textures/emit_per_mode_materials.py --kit alpine
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WGV3 = REPO / "world3" / "textures" / "wgv3"

KITS = ["alpine", "desert", "tundra", "temperate_forest", "grassland"]

# Mode → shader-param overrides. Values that aren't listed are inherited
# from the base .tres unchanged (slope_threshold, height bands, elev params,
# texture references, etc.).
MODES: dict[str, dict[str, float]] = {
    "walk": {
        "world_uv_scale": 0.4,        # ~2.5m repeat — close-up detail
        "normal_strength": 1.2,        # sharper normals up close
        "macro_value_strength": 0.05,  # macro tint nearly off
        "blend_sharpness": 12.0,       # tighter blends visible up close
        "h_band_softness": 0.06,       # crisper material transitions
    },
    "iso": {
        "world_uv_scale": 0.1,         # ~10m repeat — current default
        "normal_strength": 1.0,
        "macro_value_strength": 0.15,
        "blend_sharpness": 8.0,
        "h_band_softness": 0.08,
    },
    "topdown": {
        "world_uv_scale": 0.02,        # ~50m repeat — color-blocking
        "normal_strength": 0.4,        # muted; topdown lighting flattens normals
        "macro_value_strength": 0.35,  # macro tint dominates the read
        "blend_sharpness": 4.0,        # softer blends so transitions read at zoom-out
        "h_band_softness": 0.12,
    },
}

# Param-line pattern. Captures the param name and its value (number).
PARAM_LINE = re.compile(r'^(shader_parameter/(\w+))\s*=\s*([\d\.\-]+)\s*$')


def patch_params(text: str, overrides: dict[str, float]) -> str:
    """Rewrite numeric shader_parameter lines that have an override; leave
    everything else (including ExtResource() params) untouched."""
    out_lines: list[str] = []
    for line in text.splitlines():
        m = PARAM_LINE.match(line)
        if m and m.group(2) in overrides:
            v = overrides[m.group(2)]
            out_lines.append(f'{m.group(1)} = {v}')
        else:
            out_lines.append(line)
    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else "")


def emit_for_kit(kit: str) -> int:
    base = WGV3 / f"terrain_blend_{kit}.tres"
    if not base.exists():
        print(f"  skip {kit}: {base.name} missing", file=sys.stderr)
        return 0
    base_text = base.read_text(encoding="utf-8")
    n = 0
    for mode, overrides in MODES.items():
        out = WGV3 / f"terrain_blend_{kit}_{mode}.tres"
        out.write_text(patch_params(base_text, overrides), encoding="utf-8")
        print(f"  {kit}: {out.name}")
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", choices=KITS, default=None,
                    help="emit only this kit (default: all)")
    args = ap.parse_args()
    kits = [args.kit] if args.kit else KITS
    total = 0
    for k in kits:
        print(f"[{k}]")
        total += emit_for_kit(k)
    print(f"wrote {total} per-mode .tres files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
