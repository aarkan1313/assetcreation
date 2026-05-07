"""Godot exporter: turn pipeline outputs into ready-to-import Godot resources.

Supports four asset types:

  sprite_sheet   -- character pipeline atlas + frames JSON → SpriteFrames .tres
  pbr_material   -- ambientCG/derived material folder → StandardMaterial3D + ORMMaterial3D .tres
  terrain        -- terrain bundle folder → HeightMapShape3D .tres + Terrain3D import hint
  rigged_glb     -- already a Godot-importable GLB; copy with .gdimport sidecar

Usage:
  python export_godot.py --type pbr_material --src D:/assets/world/textures/library/Rock035 --out D:/assets/godot_pack/materials/rock035
  python export_godot.py --type sprite_sheet --src D:/assets/meshy/output/goblin --out D:/assets/godot_pack/sprites/goblin
  python export_godot.py --type terrain --src D:/assets/pipelines/terrain/output/smoketest_a --out D:/assets/godot_pack/terrain/smoketest_a
  python export_godot.py --type rigged_glb --src D:/assets/meshy/output/goblin/model.glb --out D:/assets/godot_pack/characters/goblin

Output is a folder that can be dropped into a Godot 4.5 project.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


# ---------------------------------------------------------------------------
# Material exporter
# ---------------------------------------------------------------------------
STANDARD_MAT_TEMPLATE = """[gd_resource type=\"StandardMaterial3D\" load_steps={n_steps} format=3]

{ext_resources}

[resource]
albedo_texture = ExtResource(\"albedo\")
roughness_texture = ExtResource(\"roughness\")
{normal_block}
{ao_block}
{height_block}
{metallic_block}
"""

ORM_MAT_TEMPLATE = """[gd_resource type=\"ORMMaterial3D\" load_steps={n_steps} format=3]

{ext_resources}

[resource]
albedo_texture = ExtResource(\"albedo\")
orm_texture = ExtResource(\"orm\")
{normal_block}
{height_block}
"""


def _ext(idx: int, name: str, path: str) -> str:
    return f'[ext_resource type="Texture2D" path="{path}" id="{name}"]'


def _load_manifest(material_dir: Path) -> dict:
    catalog = Path("D:/assets/world/textures/catalog/materials.jsonl")
    if not catalog.exists():
        return {}
    target = material_dir.name
    for line in catalog.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("id") == target:
            return rec
    return {}


def export_material(src: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(src)
    maps = manifest.get("maps", {})
    if "albedo" not in maps:
        # try direct file inspection fallback
        for p in src.iterdir():
            n = p.name.lower()
            if "color" in n or "albedo" in n:
                maps["albedo"] = p.name
            elif "normalgl" in n or "_normal." in n:
                maps["normal"] = p.name
            elif "roughness" in n:
                maps["roughness"] = p.name
            elif "ambientocclusion" in n or "_ao." in n:
                maps["ao"] = p.name
            elif "displacement" in n or "_height." in n:
                maps["height"] = p.name
            elif "metallic" in n or "metalness" in n:
                maps["metallic"] = p.name
    if "albedo" not in maps:
        raise SystemExit(f"no albedo found in {src}")

    # Copy maps to output folder
    copied = {}
    for kind, fname in maps.items():
        s = src / fname
        if not s.exists():
            continue
        d = out / s.name
        shutil.copy2(s, d)
        copied[kind] = s.name

    # StandardMaterial3D
    ext_lines = [_ext(0, "albedo", copied["albedo"])]
    if "roughness" in copied:
        ext_lines.append(_ext(1, "roughness", copied["roughness"]))
    n_steps = len(ext_lines)
    blocks = {"normal_block": "", "ao_block": "", "height_block": "", "metallic_block": ""}
    for i, key in enumerate(["normal", "ao", "height", "metallic"]):
        if key in copied:
            ext_lines.append(_ext(n_steps, key, copied[key]))
            n_steps += 1
            if key == "normal":
                blocks["normal_block"] = 'normal_enabled = true\nnormal_texture = ExtResource("normal")'
            elif key == "ao":
                blocks["ao_block"] = 'ao_enabled = true\nao_texture = ExtResource("ao")'
            elif key == "height":
                blocks["height_block"] = 'heightmap_enabled = true\nheightmap_texture = ExtResource("height")'
            elif key == "metallic":
                blocks["metallic_block"] = 'metallic_texture = ExtResource("metallic")\nmetallic = 1.0'

    standard_tres = STANDARD_MAT_TEMPLATE.format(
        n_steps=len(ext_lines) + 1,
        ext_resources="\n".join(ext_lines),
        **blocks,
    )
    (out / f"{src.name}_standard.tres").write_text(standard_tres, encoding="utf-8")

    info = {
        "type": "pbr_material",
        "id": src.name,
        "source": manifest.get("source"),
        "license": manifest.get("license"),
        "files": copied,
        "godot_resources": [f"{src.name}_standard.tres"],
        "notes": "Drop this folder into your Godot 4.5 project under res://materials/",
    }
    (out / "godot_export.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"  pbr_material -> {out}")


# ---------------------------------------------------------------------------
# Terrain exporter
# ---------------------------------------------------------------------------
def export_terrain(src: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    metadata_path = src / "terrain.json"
    if not metadata_path.exists():
        raise SystemExit(f"no terrain.json in {src}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    # Copy the bundle
    for fname in ["height_16.png", "normal.png", "splat_rgba.png", "biome.png",
                  "vegetation_density.png", "water_mask.png"]:
        s = src / fname
        if s.exists():
            shutil.copy2(s, out / fname)

    # HeightMapShape3D resource
    tres = """[gd_resource type=\"HeightMapShape3D\" load_steps=2 format=3]

[ext_resource type=\"Texture2D\" path=\"height_16.png\" id=\"1\"]

[resource]
map_data = ExtResource(\"1\")
"""
    (out / "heightmapshape3d.tres").write_text(tres, encoding="utf-8")

    info = {
        "type": "terrain",
        "id": metadata.get("id"),
        "source_terrain_json": "terrain.json",
        "godot_resources": ["heightmapshape3d.tres"],
        "terrain3d_hint": "drop height_16.png into a Terrain3D node as the height map; splat_rgba.png as the control map; vegetation_density.png as the foliage mask.",
    }
    (out / "godot_export.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    shutil.copy2(metadata_path, out / "terrain.json")
    print(f"  terrain -> {out}")


# ---------------------------------------------------------------------------
# Sprite sheet exporter
# ---------------------------------------------------------------------------
def export_sprite_sheet(src: Path, out: Path):
    """Look for an atlas + frames.json next to it. Copy + write SpriteFrames .tres."""
    out.mkdir(parents=True, exist_ok=True)
    atlas = None
    frames = None
    for p in src.rglob("*atlas*.png"):
        atlas = p
        break
    for p in src.rglob("*atlas*.json"):
        frames = p
        break
    if not atlas:
        # any png+json pair
        for p in src.glob("*.png"):
            atlas = p
            break
        for p in src.glob("*.json"):
            frames = p
            break
    if not atlas:
        raise SystemExit(f"no atlas .png found in {src}")
    shutil.copy2(atlas, out / atlas.name)
    if frames and frames.exists():
        shutil.copy2(frames, out / frames.name)
    # Minimal SpriteFrames stub. The user will need to add animations in editor;
    # producing a fully wired SpriteFrames .tres requires per-frame UV rects which
    # we leave to the editor / a future exporter pass.
    tres = f"""[gd_resource type=\"SpriteFrames\" load_steps=2 format=3]

[ext_resource type=\"Texture2D\" path=\"{atlas.name}\" id=\"atlas\"]

[resource]
animations = [{{
\"name\": &\"default\",
\"speed\": 12.0,
\"loop\": true,
\"frames\": []
}}]
"""
    (out / f"{src.name}_spriteframes.tres").write_text(tres, encoding="utf-8")
    info = {
        "type": "sprite_sheet",
        "id": src.name,
        "atlas": atlas.name,
        "frames_json": frames.name if frames else None,
        "godot_resources": [f"{src.name}_spriteframes.tres"],
        "notes": "SpriteFrames stub created. Open in Godot 4.5 and use 'Add Frames from Sprite Sheet' to slice using frames_json grid metadata.",
    }
    (out / "godot_export.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"  sprite_sheet -> {out}")


# ---------------------------------------------------------------------------
# Rigged GLB exporter
# ---------------------------------------------------------------------------
def export_rigged_glb(src: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        shutil.copy2(src, out / src.name)
        glb_name = src.name
    else:
        # find one
        glbs = list(src.glob("*.glb"))
        if not glbs:
            raise SystemExit(f"no .glb found in {src}")
        shutil.copy2(glbs[0], out / glbs[0].name)
        glb_name = glbs[0].name
    info = {
        "type": "rigged_glb",
        "id": Path(glb_name).stem,
        "files": [glb_name],
        "notes": "Godot 4.5 imports GLB natively. On first import, Godot will create a .glb.import sidecar.",
    }
    (out / "godot_export.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"  rigged_glb -> {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
EXPORTERS = {
    "pbr_material": export_material,
    "terrain": export_terrain,
    "sprite_sheet": export_sprite_sheet,
    "rigged_glb": export_rigged_glb,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", required=True, choices=list(EXPORTERS.keys()))
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if not args.src.exists():
        raise SystemExit(f"source not found: {args.src}")
    EXPORTERS[args.type](args.src, args.out)


if __name__ == "__main__":
    main()
