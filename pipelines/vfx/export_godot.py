"""VFX Godot 4.5 2D exporter.

For each baked effect, write `<effect_dir>/godot/sprite_frames.tres` and
`<effect_dir>/godot/<id>.tscn` REFERENCING frames at their existing catalog
paths via `res://vfx/<kind>/<id>/frames/...`. NO file copies.

The user copies `vfx/catalog/` contents into their Godot project as
`res://vfx/` once, and every effect's `.tscn`/`.tres` resolves cleanly via
the `res://` path.

Why no copies:
  Earlier versions of this exporter `shutil.copytree`d every per-frame PNG
  into a parallel `vfx/godot/<kind>/<id>/frames/` dir. With 46 effects x
  ~20 frames the duplication overflowed disk and produced 580k+ files
  inside `vfx/godot/`. Rewritten 2026-05-06 to reference catalog paths
  directly. See HANDOFF_vfx_v2_*.md for the bug post-mortem.

CLI:
  python export_godot.py vfx/catalog/spells/fireball_projectile
  python export_godot.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _ext_resource_block(godot_frames_path: str, n_frames: int,
                        frame_ids_start: int = 1) -> tuple[list[str], list[str]]:
    """Return (ext_resource lines, ExtResource id strings per frame).

    `godot_frames_path` is the res://-relative path of the frames dir
    (e.g. "vfx/spell/fireball_projectile/frames"). NO copying happens here -
    the .tres just references PNGs that already live in the catalog dir."""
    lines: list[str] = []
    ids: list[str] = []
    for i in range(n_frames):
        eid = f"{frame_ids_start + i}_f{i}"
        path = f"res://{godot_frames_path}/frame_{i:04d}.png"
        lines.append(f'[ext_resource type="Texture2D" path="{path}" id="{eid}"]')
        ids.append(eid)
    return lines, ids


def make_sprite_frames_tres(effect_id: str, fps: int,
                            godot_frames_path: str, n_frames: int) -> str:
    ext_lines, eids = _ext_resource_block(godot_frames_path, n_frames)
    load_steps = n_frames + 1
    out = [f'[gd_resource type="SpriteFrames" load_steps={load_steps} format=3]', ""]
    out.extend(ext_lines)
    out.append("")
    out.append("[resource]")
    out.append("animations = [{")
    out.append(f'"frames": [')
    for eid in eids:
        out.append(f'{{ "duration": 1.0, "texture": ExtResource("{eid}") }},')
    out.append("],")
    out.append('"loop": false,')
    out.append(f'"name": &"{effect_id}",')
    out.append(f'"speed": {float(fps)}')
    out.append("}]")
    return "\n".join(out) + "\n"


def make_scene_tscn(effect_id: str, sprite_frames_godot: str) -> str:
    return (
        '[gd_scene load_steps=2 format=3]\n\n'
        f'[ext_resource type="SpriteFrames" path="res://{sprite_frames_godot}" id="1_sf"]\n\n'
        f'[node name="{effect_id}" type="AnimatedSprite2D"]\n'
        'sprite_frames = ExtResource("1_sf")\n'
        f'animation = &"{effect_id}"\n'
        'autoplay = "default"\n'
    )


def export_effect(effect_dir: Path) -> dict | None:
    """Read effect.json + manifest.json from `effect_dir`, write Godot files
    into `effect_dir/godot/`. References frames via res:// catalog paths;
    no file copies."""
    eff_path = effect_dir / "effect.json"
    man_path = effect_dir / "manifest.json"
    if not eff_path.exists() or not man_path.exists():
        return None
    eff = json.loads(eff_path.read_text(encoding="utf-8"))
    man = json.loads(man_path.read_text(encoding="utf-8"))
    eid = eff["id"]
    kind = eff.get("kind", "spell")
    n_frames = man["n_frames"]
    fps = man["fps"]
    if n_frames < 1:
        # No-frame backend (volumetric_fog, runtime_trail). Skip 2D export.
        return None

    out_dir = effect_dir / "godot"
    out_dir.mkdir(exist_ok=True)

    # res://-relative frames path. Assumes the user copies vfx/catalog/
    # contents into res://vfx/ (so res://vfx/<kind>/<id>/ == effect_dir).
    godot_frames_path = f"vfx/{kind}/{eid}/frames"

    sprite_frames_text = make_sprite_frames_tres(eid, fps, godot_frames_path, n_frames)
    sprite_path = out_dir / "sprite_frames.tres"
    sprite_path.write_text(sprite_frames_text, encoding="utf-8")

    scene_godot = f"vfx/{kind}/{eid}/godot/sprite_frames.tres"
    tscn = make_scene_tscn(eid, scene_godot)
    scene_path = out_dir / f"{eid}.tscn"
    scene_path.write_text(tscn, encoding="utf-8")

    return {
        "id": eid, "kind": kind,
        "sprite_frames": str(sprite_path),
        "scene": str(scene_path),
        "frames": n_frames,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("effect_dir", type=Path, nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--catalog", type=Path,
                    default=Path(r"D:\assets\vfx\catalog"))
    args = ap.parse_args()

    if args.all:
        ok = 0
        skipped = 0
        for d in sorted(args.catalog.rglob("effect.json")):
            try:
                info = export_effect(d.parent)
                if info is None:
                    skipped += 1
                    continue
                print(f"[export_godot] {info['id']:32s} ({info['kind']}) "
                      f"{info['frames']} frames -> {info['scene']}")
                ok += 1
            except Exception as e:
                print(f"[export_godot] FAILED {d.parent}: {e}")
        # README at catalog root: tells the user how to drop into Godot.
        readme_path = args.catalog / "README_GODOT_DROPIN.txt"
        readme_path.write_text(
            "# vfx/ drop-in for Godot 4.5\n"
            "Copy the *contents* of this folder (vfx/catalog/) into res://vfx/.\n"
            "\n"
            "Each effect lives at:\n"
            "  res://vfx/<kind>/<id>/effect.json     (authored)\n"
            "  res://vfx/<kind>/<id>/manifest.json   (baked metadata)\n"
            "  res://vfx/<kind>/<id>/frames/*.png    (baked frames)\n"
            "  res://vfx/<kind>/<id>/flipbook.png    (baked atlas)\n"
            "  res://vfx/<kind>/<id>/godot/<id>.tscn (Godot scene; what you instance)\n"
            "  res://vfx/<kind>/<id>/godot/sprite_frames.tres  (the SpriteFrames resource)\n"
            "  res://vfx/<kind>/<id>/godot/<id>_billboard.tscn (3D billboard variant, if export_target=3d_billboard)\n"
            "  res://vfx/<kind>/<id>/godot/<id>_decal.tscn     (decal variant)\n"
            "  res://vfx/<kind>/<id>/godot/<id>_trail.tscn     (mesh trail variant)\n"
            "  res://vfx/<kind>/<id>/godot/<id>_fog.tscn       (fog volume variant)\n"
            "\n"
            "Runtime helpers (autoload one):\n"
            "  res://vfx/runtime/AudioCueBus.gd  - register as autoload AudioCueBus\n"
            "  res://vfx/runtime/MeshTrail3D.gd  - class for mesh-trail nodes\n"
            "\n"
            "Usage:\n"
            "  var effect = preload('res://vfx/spell/fireball_projectile/godot/fireball_projectile.tscn').instantiate()\n"
            "  add_child(effect)\n",
            encoding="utf-8",
        )
        print(f"[export_godot] exported {ok} 2D scenes ({skipped} skipped: no-frame backends)")
        return 0
    if not args.effect_dir:
        ap.error("provide effect_dir or --all")
    info = export_effect(args.effect_dir)
    if info:
        print(f"[export_godot] {info['id']} -> {info['scene']}")
    else:
        print(f"[export_godot] {args.effect_dir} skipped (no frames or missing manifest)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
