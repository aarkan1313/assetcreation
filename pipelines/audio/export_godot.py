"""Audio Godot exporter.

For each sound in a sound-bank manifest we emit:
  godot/audio/sfx/<id>/<id>_v0.wav  (the WAV itself, copied)
  godot/audio/sfx/<id>/<id>_v0.wav.import  (Godot WAV import metadata)
  godot/audio/sfx/<id>/randomizer.tres  (AudioStreamRandomizer wrapping all variants)
  godot/audio/sfx/<id>/cue.json         (provenance + processing report)

Drop `godot/audio/` into a Godot 4.5 project at `res://audio/` and use:

    var s = load("res://audio/sfx/ui_click/randomizer.tres")
    $AudioStreamPlayer.stream = s
    $AudioStreamPlayer.play()

The randomizer will pick a uniform-random variant on each play().

We also write a `bus_layout.tres` skeleton with:
  Master, SFX, UI, Voice, Ambience, Music

CLI:
  python export_godot.py audio/sfx_manifest.json --out game_data/godot/audio/
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def make_wav_import(wav_relpath_godot: str) -> str:
    """Godot 4.5 .wav.import metadata so the engine treats the WAV as
    AudioStreamWAV (uncompressed, perfect for short SFX per E_audio)."""
    return (
        '[remap]\n\n'
        'importer="wav"\n'
        'type="AudioStreamWAV"\n'
        f'uid="uid://{_simple_uid(wav_relpath_godot)}"\n'
        f'path="res://.godot/imported/{Path(wav_relpath_godot).stem}-import.sample"\n\n'
        '[deps]\n\n'
        f'source_file="res://{wav_relpath_godot}"\n'
        f'dest_files=["res://.godot/imported/{Path(wav_relpath_godot).stem}-import.sample"]\n\n'
        '[params]\n\n'
        'force/8_bit=false\n'
        'force/mono=false\n'
        'force/max_rate=false\n'
        'force/max_rate_hz=44100\n'
        'edit/trim=false\n'
        'edit/normalize=false\n'
        'edit/loop_mode=0\n'
        'edit/loop_begin=0\n'
        'edit/loop_end=-1\n'
        'compress/mode=0\n'
    )


def _simple_uid(s: str) -> str:
    h = abs(hash(s)) & 0xFFFFFFFFFF
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    out = []
    for _ in range(8):
        out.append(chars[h % 36])
        h //= 36
    return "".join(out)


def make_randomizer_tres(sound_id: str, variant_paths_godot: list[str],
                         random_pitch: float = 1.05,
                         random_volume_db: float = 1.5) -> str:
    """AudioStreamRandomizer with all variants weighted equally."""
    n = len(variant_paths_godot)
    # load_steps = number of unique [ext_resource] entries + 1 (for the [resource])
    load_steps = n + 1
    lines = [
        f'[gd_resource type="AudioStreamRandomizer" load_steps={load_steps} format=3]',
        '',
    ]
    for i, p in enumerate(variant_paths_godot, start=1):
        lines.append(
            f'[ext_resource type="AudioStream" path="res://{p}" id="{i}_{sound_id}_v{i-1}"]'
        )
    lines.append('')
    lines.append('[resource]')
    lines.append(f'random_pitch = {random_pitch}')
    lines.append(f'random_volume_offset_db = {random_volume_db}')
    lines.append(f'streams_count = {n}')
    for i in range(n):
        lines.append(f'stream_{i}/stream = ExtResource("{i+1}_{sound_id}_v{i}")')
        lines.append(f'stream_{i}/weight = 1.0')
    return "\n".join(lines) + "\n"


BUS_LAYOUT_TRES = '''[gd_resource type="AudioBusLayout" load_steps=1 format=3]

[resource]
bus/0/name = &"Master"
bus/0/solo = false
bus/0/mute = false
bus/0/bypass_fx = false
bus/0/volume_db = 0.0
bus/0/send = &""
bus/1/name = &"SFX"
bus/1/solo = false
bus/1/mute = false
bus/1/bypass_fx = false
bus/1/volume_db = 0.0
bus/1/send = &"Master"
bus/2/name = &"UI"
bus/2/solo = false
bus/2/mute = false
bus/2/bypass_fx = false
bus/2/volume_db = 0.0
bus/2/send = &"Master"
bus/3/name = &"Voice"
bus/3/solo = false
bus/3/mute = false
bus/3/bypass_fx = false
bus/3/volume_db = 0.0
bus/3/send = &"Master"
bus/4/name = &"Ambience"
bus/4/solo = false
bus/4/mute = false
bus/4/bypass_fx = false
bus/4/volume_db = 0.0
bus/4/send = &"Master"
bus/5/name = &"Music"
bus/5/solo = false
bus/5/mute = false
bus/5/bypass_fx = false
bus/5/volume_db = -3.0
bus/5/send = &"Master"
'''


def export_bank(manifest_path: Path, out_root: Path) -> dict:
    """Walk a sound-bank manifest and emit Godot resources.

    Manifest format (JSON):
      {
        "sounds": [
          {
            "id": "ui_click",
            "category": "ui",     // ui|sfx|voice|ambience|music
            "variants": [
              "audio/sfx/ui_click_v0.wav",  // path relative to D:/assets
              "audio/sfx/ui_click_v1.wav"
            ],
            "cue": { ... freeform metadata ... }
          },
          ...
        ]
      }
    """
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    for snd in data["sounds"]:
        sid = snd["id"]
        cat = snd.get("category", "sfx")
        bank_dir = out_root / cat / sid
        bank_dir.mkdir(parents=True, exist_ok=True)
        variant_godot_paths: list[str] = []
        for i, src in enumerate(snd["variants"]):
            src_path = (Path(r"D:\assets") / src).resolve()
            dst_name = f"{sid}_v{i}.wav"
            dst_path = bank_dir / dst_name
            shutil.copyfile(src_path, dst_path)
            # Godot res:// path. We assume the Godot project will mount this
            # under res://audio/<cat>/<id>/<file>.wav
            godot_rel = f"audio/{cat}/{sid}/{dst_name}"
            (bank_dir / f"{dst_name}.import").write_text(
                make_wav_import(godot_rel), encoding="utf-8"
            )
            variant_godot_paths.append(godot_rel)
        # randomizer
        randomizer = make_randomizer_tres(sid, variant_godot_paths)
        (bank_dir / "randomizer.tres").write_text(randomizer, encoding="utf-8")
        # cue
        cue = {
            "id": sid,
            "category": cat,
            "variants": variant_godot_paths,
            **snd.get("cue", {}),
        }
        (bank_dir / "cue.json").write_text(json.dumps(cue, indent=2))
        counts[sid] = len(variant_godot_paths)

    # bus layout
    (out_root / "bus_layout.tres").write_text(BUS_LAYOUT_TRES, encoding="utf-8")
    # README
    (out_root / "README.txt").write_text(
        "# audio drop-in for Godot 4.5\n"
        "Copy this folder to res://audio/. Each sound has a randomizer.tres\n"
        "that picks one of N WAV variants per .play().\n\n"
        "    var s := load('res://audio/sfx/ui_click/randomizer.tres')\n"
        "    $AudioStreamPlayer.stream = s\n"
        "    $AudioStreamPlayer.play()\n\n"
        "Optional: import bus_layout.tres via Project > Project Settings >\n"
        "Audio > Buses > Load to apply the recommended bus structure\n"
        "(Master / SFX / UI / Voice / Ambience / Music).\n",
        encoding="utf-8",
    )
    return counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--out", type=Path,
                    default=Path(r"D:\assets\audio\godot"))
    args = ap.parse_args()
    counts = export_bank(args.manifest, args.out)
    print(f"[export_godot] wrote {sum(counts.values())} variants across "
          f"{len(counts)} sounds:")
    for sid, n in counts.items():
        print(f"  {sid:24s} {n} variants")
    print(f"  -> {args.out}")


if __name__ == "__main__":
    main()
