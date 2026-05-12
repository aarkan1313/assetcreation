"""Anchor v2 — write the simpler slope-blended 3-slot material.tres.

3 texture slots, each a tileable PBR set:
  - ground (low slope) : scrub_dense  -- real ortho-derived tileable
  - mid    (mid slope) : tundra_lichen -- ComfyUI generated
  - rock   (high slope): rocky_slope  -- real ortho-derived tileable

Mix of real-ortho + ComfyUI in the same render. No source_macro, no splat
weights texture, no procedurally-composited macro layer. Just three PBR
sets blended by surface slope.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path("D:/assets")
W4_ROOT = ROOT / "world 4" / "the world 4"
ANCHOR_DIR = W4_ROOT / "worlds" / "anchor"

SLOTS = ["ground", "mid", "rock"]
SLOT_MATERIALS = {
    "ground": "scrub_dense",       # real ortho-derived (W3 _soft_composite)
    "mid":    "tundra_lichen",     # ComfyUI generated (m14_tundra_lichen_flux10_09)
    "rock":   "rocky_slope",       # real ortho-derived (W3 _soft_composite)
}
MAPS = ["albedo", "normal", "rough", "ao"]
MAP_FILES = {
    "albedo":  "albedo",
    "normal":  "normal",
    "rough":   "roughness",
    "ao":      "ao",
}


def res(path: Path) -> str:
    rel = path.resolve().relative_to(W4_ROOT.resolve())
    return "res://" + rel.as_posix()


def ext(kind: str, path: str, ident: str) -> str:
    return f'[ext_resource type="{kind}" path="{path}" id="{ident}"]'


def main() -> int:
    shader_path = W4_ROOT / "shaders" / "terrain_anchor_v2.gdshader"
    if not shader_path.exists():
        print(f"ERROR: shader missing {shader_path}")
        return 1

    ext_lines = [ext("Shader", res(shader_path), "shader")]
    res_ident_for: dict[tuple[str, str], str] = {}

    for slot in SLOTS:
        mat_id = SLOT_MATERIALS[slot]
        for kind in MAPS:
            file_name = MAP_FILES[kind]
            tex_path = W4_ROOT / "materials" / "anchor_v2" / mat_id / f"{file_name}.png"
            if not tex_path.exists():
                print(f"ERROR: missing texture {tex_path}")
                return 1
            ident = f"{slot}_{kind}"
            ext_lines.append(ext("Texture2D", res(tex_path), ident))
            res_ident_for[(slot, kind)] = ident

    lines = [
        f'[gd_resource type="ShaderMaterial" load_steps={len(ext_lines) + 1} format=3]',
        "",
        *ext_lines,
        "",
        "[resource]",
        'shader = ExtResource("shader")',
        # Slope thresholds
        "shader_parameter/slope_ground_max = 0.92",   # cos(~23°) = top of flat zone
        "shader_parameter/slope_rock_max = 0.55",     # cos(~57°) = top of rock zone
        # Tile scale
        "shader_parameter/world_uv_scale = 0.04",     # 1m → 0.04 UV, ~25m per repeat
        "shader_parameter/normal_strength = 0.3",
        "shader_parameter/roughness_floor = 0.5",
    ]
    for slot in SLOTS:
        for kind in MAPS:
            uniform = f"{slot}_{kind}"
            lines.append(f'shader_parameter/{uniform} = ExtResource("{res_ident_for[(slot, kind)]}")')

    out_path = ANCHOR_DIR / "material.tres"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    print(f"[anchor v2/tres] wrote {out_path}")
    print(f"  shader: {res(shader_path)}")
    print(f"  3 slots × 4 maps = 12 textures bound")
    print(f"  slot map:")
    for slot, mat in SLOT_MATERIALS.items():
        print(f"    {slot:7s} = {mat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
