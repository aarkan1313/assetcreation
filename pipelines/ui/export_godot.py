"""Godot 4.5 UI exporter.

Two outputs:

  1. **AtlasTexture .tres per icon** — references the packed atlas + the rect
     for that icon. Drop atlas.png into the project, load any
     `<id>_atlas.tres` as a Texture2D.

  2. **Theme .tres** — a starter Theme that wires the 9-slice panel/button/
     frame into the Godot StyleBoxTexture system, plus icon constants for
     each atlas region. This is the path Godot 4.5 docs recommend for
     consistent UI styling (`Theme` → `StyleBoxTexture` → NinePatchRect-aware
     stretch).

Output goes to `ui/godot/` and is meant to be copied into a Godot 4.5 project
under `res://ui/`.

CLI:
  python export_godot.py
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ASSETS = Path(r"D:\assets")
ATLAS_DIR = ASSETS / "ui" / "atlas"
SLICE_DIR = ASSETS / "ui" / "9slice"
GODOT_OUT = ASSETS / "ui" / "godot"


def make_atlas_texture_tres(atlas_godot_path: str, region: dict) -> str:
    return (
        '[gd_resource type="AtlasTexture" load_steps=2 format=3]\n\n'
        f'[ext_resource type="Texture2D" path="res://{atlas_godot_path}" id="1"]\n\n'
        '[resource]\n'
        'atlas = ExtResource("1")\n'
        f'region = Rect2({region["x"]}, {region["y"]}, '
        f'{region["w"]}, {region["h"]})\n'
    )


def make_stylebox_texture_tres(tex_godot_path: str, margin: dict) -> str:
    return (
        '[gd_resource type="StyleBoxTexture" load_steps=2 format=3]\n\n'
        f'[ext_resource type="Texture2D" path="res://{tex_godot_path}" id="1"]\n\n'
        '[resource]\n'
        'texture = ExtResource("1")\n'
        f'texture_margin_left = {margin["patch_margin_left"]}\n'
        f'texture_margin_top = {margin["patch_margin_top"]}\n'
        f'texture_margin_right = {margin["patch_margin_right"]}\n'
        f'texture_margin_bottom = {margin["patch_margin_bottom"]}\n'
        'axis_stretch_horizontal = 0\n'
        'axis_stretch_vertical = 0\n'
    )


def make_theme_tres(stylebox_paths: dict[str, str], icon_paths: dict[str, str]) -> str:
    """Build a Theme resource. Wires:
      - Button.normal/hover/pressed -> stylebox button
      - Panel.panel                 -> stylebox panel
      - HSlider/HScrollBar grabber  -> stylebox button (looks fine for prototypes)
      - icon constants on a synthetic 'icons' theme type for direct lookup.
    """
    # Build ext_resource list
    ext_paths = list(set(stylebox_paths.values()) | set(icon_paths.values()))
    ext_paths.sort()
    ext_id = {p: i + 1 for i, p in enumerate(ext_paths)}
    load_steps = len(ext_paths) + 1

    lines = [f'[gd_resource type="Theme" load_steps={load_steps} format=3]', ""]
    for path, eid in ext_id.items():
        # We register textures + styleboxes as plain Resource refs.
        # Godot will type them by their .tres header.
        lines.append(f'[ext_resource type="Resource" path="res://{path}" id="{eid}"]')
    lines.append("")
    lines.append("[resource]")

    # Button styleboxes
    if "button" in stylebox_paths:
        eid = ext_id[stylebox_paths["button"]]
        lines.append(f'Button/styles/normal = ExtResource("{eid}")')
        lines.append(f'Button/styles/hover = ExtResource("{eid}")')
        lines.append(f'Button/styles/pressed = ExtResource("{eid}")')
    if "panel" in stylebox_paths:
        eid = ext_id[stylebox_paths["panel"]]
        lines.append(f'Panel/styles/panel = ExtResource("{eid}")')
        lines.append(f'PanelContainer/styles/panel = ExtResource("{eid}")')

    # Icon constants (loaded as Texture2D-typed resources via AtlasTexture .tres)
    for icon_id, path in sorted(icon_paths.items()):
        eid = ext_id[path]
        # Theme expects icons under a type. Use 'IconSet' as a synthetic type.
        lines.append(f'IconSet/icons/{icon_id} = ExtResource("{eid}")')
    lines.append("")
    return "\n".join(lines)


def export(atlas_dir: Path = ATLAS_DIR, slice_dir: Path = SLICE_DIR,
           out_dir: Path = GODOT_OUT) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {"icons": 0, "9slice": 0, "stylebox": 0}

    # 1. copy atlas + emit AtlasTexture tres per icon
    atlas_meta_path = atlas_dir / "atlas.json"
    icon_godot_paths: dict[str, str] = {}
    if atlas_meta_path.exists():
        meta = json.loads(atlas_meta_path.read_text(encoding="utf-8"))
        atlas_src = atlas_dir / meta["atlas"]
        atlas_dst = out_dir / "atlas.png"
        shutil.copyfile(atlas_src, atlas_dst)
        atlas_godot_path = "ui/atlas.png"
        for sid, region in meta["regions"].items():
            tres = make_atlas_texture_tres(atlas_godot_path, region)
            tres_path = out_dir / f"{sid}_atlas.tres"
            tres_path.write_text(tres, encoding="utf-8")
            icon_godot_paths[sid] = f"ui/{sid}_atlas.tres"
            counts["icons"] += 1

    # 2. copy 9-slice PNGs + emit StyleBoxTexture tres
    stylebox_godot_paths: dict[str, str] = {}
    for png in sorted(slice_dir.glob("*.png")):
        meta_path = png.with_suffix(".json")
        if not meta_path.exists():
            continue
        margin = json.loads(meta_path.read_text(encoding="utf-8"))
        # Copy the PNG into out_dir/9slice/
        nine_dir = out_dir / "9slice"
        nine_dir.mkdir(exist_ok=True)
        shutil.copyfile(png, nine_dir / png.name)
        sb_path = out_dir / f"{png.stem}_stylebox.tres"
        tex_godot_path = f"ui/9slice/{png.name}"
        sb_path.write_text(
            make_stylebox_texture_tres(tex_godot_path, margin), encoding="utf-8")
        stylebox_godot_paths[png.stem] = f"ui/{png.stem}_stylebox.tres"
        counts["9slice"] += 1
        counts["stylebox"] += 1

    # 3. write the Theme.tres
    theme_text = make_theme_tres(stylebox_godot_paths, icon_godot_paths)
    (out_dir / "theme.tres").write_text(theme_text, encoding="utf-8")

    # 4. README
    (out_dir / "README.txt").write_text(
        "# UI drop-in for Godot 4.5\n"
        "Copy this folder to res://ui/. Apply theme.tres to a Control's\n"
        "'theme' property (or set as the default theme in Project Settings).\n\n"
        "Icons are AtlasTexture references into atlas.png. Load any one with:\n"
        "    var t: Texture2D = load('res://ui/ico_sword_atlas.tres')\n\n"
        "9-slice elements (panel/button/frame/healthbar) are StyleBoxTexture\n"
        "resources auto-wired into Button.styles and Panel.styles by theme.tres.\n",
        encoding="utf-8",
    )

    return counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas-dir", type=Path, default=ATLAS_DIR)
    ap.add_argument("--slice-dir", type=Path, default=SLICE_DIR)
    ap.add_argument("--out", type=Path, default=GODOT_OUT)
    args = ap.parse_args()

    counts = export(args.atlas_dir, args.slice_dir, args.out)
    print(f"[export_godot] icons={counts['icons']} 9slice={counts['9slice']} "
          f"styleboxes={counts['stylebox']} -> {args.out}")


if __name__ == "__main__":
    main()
