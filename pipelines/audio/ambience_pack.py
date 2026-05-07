"""Godot exporter for biome ambience packs.

Reads `audio/ambience/<biome>/biome_ambience.json` (output of `biome_ambience.py`)
and emits a Godot 4.5 drop-in:

  audio/godot/ambience/
    BiomeAmbienceController.tscn
    BiomeAmbienceController.gd
    biome_ambience_registry.tres        (lookup biome_id -> BiomeAmbiencePreset)
    bus_layout_ambience_overlay.tres    (additive Ambience + AmbienceReverb buses)
    <biome_id>/
      bed_drone.wav (+ .import w/ loop=1)
      bed_air.wav   (+ .import w/ loop=1)
      wildlife/<id>_v<N>.wav (+ .import)
      wildlife/randomizer.tres   (AudioStreamRandomizer over all wildlife variants)
      distant/<id>_v<N>.wav (+ .import)
      distant/randomizer.tres
      preset.tres                (Resource: BiomeAmbiencePreset)

The runtime side (BiomeAmbienceController.gd, .tscn) lives in a sibling step
(see this same module's `write_runtime_files`).

Per E2 5.3:
  - Beds -> AudioStreamPlayer (non-positional, looped, on the Ambience bus)
  - Sweeteners -> AudioStreamPlayer3D + AudioStreamRandomizer (positional)
  - Reverb tweak per biome via Godot 4.5 audio bus effects (AudioEffectReverb)
  - 4-second crossfade between biomes via Tween on volume_db
  - Poisson timer fires sweeteners; each stem has its own lambda

CLI:
  python ambience_pack.py --in audio/ambience --out audio/godot/ambience
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ASSETS = Path(r"D:\assets")


# ---------- .import + .tres helpers ----------


def _simple_uid(s: str) -> str:
    h = abs(hash(s)) & 0xFFFFFFFFFF
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    out = []
    for _ in range(8):
        out.append(chars[h % 36])
        h //= 36
    return "".join(out)


def make_wav_import(godot_relpath: str, *, loop: bool = False,
                    loop_mode: int = 1) -> str:
    """Godot 4.5 .wav.import metadata.

    loop_mode: 0=disabled, 1=forward, 2=ping-pong, 3=backward.
    For ambience beds we want loop=1 (forward) and loop_begin=0 / loop_end=-1.
    """
    return (
        '[remap]\n\n'
        'importer="wav"\n'
        'type="AudioStreamWAV"\n'
        f'uid="uid://{_simple_uid(godot_relpath)}"\n'
        f'path="res://.godot/imported/{Path(godot_relpath).stem}-import.sample"\n\n'
        '[deps]\n\n'
        f'source_file="res://{godot_relpath}"\n'
        f'dest_files=["res://.godot/imported/{Path(godot_relpath).stem}-import.sample"]\n\n'
        '[params]\n\n'
        'force/8_bit=false\n'
        'force/mono=false\n'
        'force/max_rate=false\n'
        'force/max_rate_hz=44100\n'
        'edit/trim=false\n'
        'edit/normalize=false\n'
        f'edit/loop_mode={loop_mode if loop else 0}\n'
        'edit/loop_begin=0\n'
        'edit/loop_end=-1\n'
        'compress/mode=0\n'
    )


def make_randomizer_tres(group_id: str, variant_godot_paths: list[str], *,
                         random_pitch: float = 1.05,
                         random_volume_db: float = 1.5) -> str:
    """AudioStreamRandomizer wrapping N variants with equal weights."""
    n = len(variant_godot_paths)
    load_steps = n + 1
    lines = [
        f'[gd_resource type="AudioStreamRandomizer" load_steps={load_steps} format=3]',
        '',
    ]
    for i, p in enumerate(variant_godot_paths, start=1):
        lines.append(
            f'[ext_resource type="AudioStream" path="res://{p}" id="{i}_{group_id}_v{i-1}"]'
        )
    lines.append('')
    lines.append('[resource]')
    lines.append(f'random_pitch = {random_pitch}')
    lines.append(f'random_volume_offset_db = {random_volume_db}')
    lines.append(f'streams_count = {n}')
    for i in range(n):
        lines.append(f'stream_{i}/stream = ExtResource("{i+1}_{group_id}_v{i}")')
        lines.append(f'stream_{i}/weight = 1.0')
    return "\n".join(lines) + "\n"


def make_preset_resource_tres(biome_id: str, manifest: dict, *,
                              godot_root: str = "audio/ambience") -> str:
    """A custom Resource we save as preset.tres. Each entry is a string path
    plus the float reverb/poisson params. The matching `class_name
    BiomeAmbiencePreset` is declared in BiomeAmbienceController.gd, so the
    runtime can `load(...)` this file directly.
    """
    bed_drone_path = f"{godot_root}/{biome_id}/bed_drone.wav"
    bed_air_path = f"{godot_root}/{biome_id}/bed_air.wav"
    wildlife_rand = f"{godot_root}/{biome_id}/wildlife/randomizer.tres"
    distant_rand = f"{godot_root}/{biome_id}/distant/randomizer.tres"

    reverb = manifest.get("reverb", {})
    poisson = manifest.get("poisson_lambda_per_sec", {})

    # External resource refs (4 ext_resource entries -> load_steps=5)
    lines = [
        '[gd_resource type="Resource" script_class="BiomeAmbiencePreset" load_steps=5 format=3]',
        '',
        f'[ext_resource type="AudioStream" path="res://{bed_drone_path}" id="1_bed_drone"]',
        f'[ext_resource type="AudioStream" path="res://{bed_air_path}" id="2_bed_air"]',
        f'[ext_resource type="AudioStream" path="res://{wildlife_rand}" id="3_wildlife"]',
        f'[ext_resource type="AudioStream" path="res://{distant_rand}" id="4_distant"]',
        '',
        '[resource]',
        f'biome_id = "{biome_id}"',
        'bed_drone = ExtResource("1_bed_drone")',
        'bed_air = ExtResource("2_bed_air")',
        'wildlife_randomizer = ExtResource("3_wildlife")',
        'distant_randomizer = ExtResource("4_distant")',
        f'reverb_room_size = {float(reverb.get("room_size", 0.5))}',
        f'reverb_damp = {float(reverb.get("damp", 0.5))}',
        f'reverb_wet = {float(reverb.get("wet", 0.1))}',
        f'reverb_predelay_ms = {float(reverb.get("predelay_ms", 30.0))}',
        f'wildlife_lambda = {float(poisson.get("wildlife_sparse", 0.05))}',
        f'distant_lambda = {float(poisson.get("distant_event", 0.01))}',
    ]
    return "\n".join(lines) + "\n"


def make_registry_tres(biome_ids: list[str], *,
                       godot_root: str = "audio/ambience") -> str:
    """A Resource holding a Dictionary {biome_id: preset_resource}."""
    n = len(biome_ids)
    load_steps = n + 1
    lines = [
        f'[gd_resource type="Resource" script_class="BiomeAmbienceRegistry" '
        f'load_steps={load_steps} format=3]',
        '',
    ]
    for i, bid in enumerate(biome_ids, start=1):
        lines.append(
            f'[ext_resource type="Resource" path="res://{godot_root}/{bid}/preset.tres" '
            f'id="{i}_{bid}_preset"]'
        )
    lines.append('')
    lines.append('[resource]')
    # presets: Dictionary[biome_id -> preset]
    items = ",\n".join([f'"{bid}": ExtResource("{i}_{bid}_preset")'
                        for i, bid in enumerate(biome_ids, start=1)])
    lines.append('presets = {')
    lines.append(items)
    lines.append('}')
    return "\n".join(lines) + "\n"


# ---------- bus layout overlay ----------


BUS_LAYOUT_AMBIENCE_OVERLAY = '''[gd_resource type="AudioBusLayout" load_steps=1 format=3]

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
bus/4/volume_db = -3.0
bus/4/send = &"AmbienceReverb"
bus/5/name = &"Music"
bus/5/solo = false
bus/5/mute = false
bus/5/bypass_fx = false
bus/5/volume_db = -3.0
bus/5/send = &"Master"
bus/6/name = &"AmbienceReverb"
bus/6/solo = false
bus/6/mute = false
bus/6/bypass_fx = false
bus/6/volume_db = 0.0
bus/6/send = &"Master"
bus/6/effect/0/effect = SubResource("AudioEffectReverb_default")
bus/6/effect/0/enabled = true

[sub_resource type="AudioEffectReverb" id="AudioEffectReverb_default"]
room_size = 0.5
damping = 0.5
wet = 0.2
dry = 1.0
predelay_msec = 30.0
'''


# ---------- main exporter ----------


def export_one_biome(biome_dir: Path, out_root: Path, *,
                     godot_root: str) -> dict:
    """Walk a single biome's outputs and emit Godot files.

    Returns a summary dict for the top-level manifest.
    """
    manifest = json.loads((biome_dir / "biome_ambience.json").read_text(encoding="utf-8"))
    biome_id = manifest["biome"]
    biome_out = out_root / biome_id
    biome_out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    # --- beds ---
    for bed_stem in ("bed_drone", "bed_air"):
        src = biome_dir / f"{bed_stem}.wav"
        if not src.exists():
            continue
        dst = biome_out / f"{bed_stem}.wav"
        shutil.copyfile(src, dst)
        godot_rel = f"{godot_root}/{biome_id}/{bed_stem}.wav"
        (biome_out / f"{bed_stem}.wav.import").write_text(
            make_wav_import(godot_rel, loop=True, loop_mode=1),
            encoding="utf-8",
        )
        written.append(godot_rel)

    # --- sweeteners (wildlife + distant) ---
    for stem, sub_name in (("wildlife_sparse", "wildlife"), ("distant_event", "distant")):
        src_dir = biome_dir / stem
        dst_dir = biome_out / sub_name
        if not src_dir.exists():
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        variant_godot_paths: list[str] = []
        for wav in sorted(src_dir.glob("*.wav")):
            dst = dst_dir / wav.name
            shutil.copyfile(wav, dst)
            godot_rel = f"{godot_root}/{biome_id}/{sub_name}/{wav.name}"
            (dst_dir / f"{wav.name}.import").write_text(
                make_wav_import(godot_rel, loop=False),
                encoding="utf-8",
            )
            variant_godot_paths.append(godot_rel)
            written.append(godot_rel)
        if variant_godot_paths:
            randomizer = make_randomizer_tres(
                f"{biome_id}_{sub_name}", variant_godot_paths,
                random_pitch=1.08, random_volume_db=2.0,
            )
            (dst_dir / "randomizer.tres").write_text(randomizer, encoding="utf-8")

    # --- preset.tres ---
    (biome_out / "preset.tres").write_text(
        make_preset_resource_tres(biome_id, manifest, godot_root=godot_root),
        encoding="utf-8",
    )

    return {
        "biome": biome_id,
        "files": written,
        "preset": f"{godot_root}/{biome_id}/preset.tres",
        "reverb": manifest.get("reverb", {}),
        "poisson_lambda_per_sec": manifest.get("poisson_lambda_per_sec", {}),
    }


def export_all(in_root: Path, out_root: Path, *,
               godot_root: str = "audio/ambience") -> dict:
    out_root.mkdir(parents=True, exist_ok=True)
    biome_dirs = sorted(d for d in in_root.iterdir()
                        if d.is_dir() and (d / "biome_ambience.json").exists())
    summary: list[dict] = []
    biome_ids: list[str] = []
    for bd in biome_dirs:
        info = export_one_biome(bd, out_root, godot_root=godot_root)
        summary.append(info)
        biome_ids.append(info["biome"])

    # Top-level resources
    (out_root / "biome_ambience_registry.tres").write_text(
        make_registry_tres(biome_ids, godot_root=godot_root),
        encoding="utf-8",
    )
    (out_root / "bus_layout_ambience_overlay.tres").write_text(
        BUS_LAYOUT_AMBIENCE_OVERLAY, encoding="utf-8",
    )
    (out_root / "ambience_pack.json").write_text(
        json.dumps({
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "biomes": summary,
            "godot_root": godot_root,
        }, indent=2),
        encoding="utf-8",
    )
    (out_root / "README.txt").write_text(
        "# Biome ambience drop-in for Godot 4.5\n"
        "Copy this folder to res://audio/ambience/. Then in your scene:\n\n"
        "    var c := preload('res://audio/ambience/BiomeAmbienceController.tscn').instantiate()\n"
        "    add_child(c)\n"
        "    c.set_biome('ice_cavern')\n\n"
        "The controller cross-fades beds, fires Poisson sweeteners, and\n"
        "tunes the AmbienceReverb bus per biome preset.\n\n"
        "Optional: import bus_layout_ambience_overlay.tres via\n"
        "Project > Project Settings > Audio > Buses > Load to add the\n"
        "Ambience + AmbienceReverb buses (idempotent: same Master/SFX/UI/\n"
        "Voice/Music order as the SFX exporter, plus 2 ambience buses).\n",
        encoding="utf-8",
    )
    return {
        "biomes": biome_ids,
        "biome_count": len(biome_ids),
        "out_root": str(out_root),
    }


# ---------- runtime files ----------


def write_runtime_files(out_root: Path) -> None:
    """Emit BiomeAmbienceController.tscn + .gd + the supporting custom Resource
    classes. Kept inside the exporter so the entire pack ships together.
    """
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "BiomeAmbiencePreset.gd").write_text(
        BIOME_AMBIENCE_PRESET_GD, encoding="utf-8")
    (out_root / "BiomeAmbienceRegistry.gd").write_text(
        BIOME_AMBIENCE_REGISTRY_GD, encoding="utf-8")
    (out_root / "BiomeAmbienceController.gd").write_text(
        BIOME_AMBIENCE_CONTROLLER_GD, encoding="utf-8")
    (out_root / "BiomeAmbienceController.tscn").write_text(
        BIOME_AMBIENCE_CONTROLLER_TSCN, encoding="utf-8")


BIOME_AMBIENCE_PRESET_GD = '''@tool
class_name BiomeAmbiencePreset
extends Resource

# Per-biome ambience preset. Loaded by BiomeAmbienceController.
# Authored by pipelines/audio/ambience_pack.py — do not hand-edit.

@export var biome_id: String = ""
@export var bed_drone: AudioStream
@export var bed_air: AudioStream
@export var wildlife_randomizer: AudioStream  # AudioStreamRandomizer
@export var distant_randomizer: AudioStream   # AudioStreamRandomizer

# Reverb (applied to AmbienceReverb bus on biome enter)
@export_range(0.0, 1.0, 0.01) var reverb_room_size: float = 0.5
@export_range(0.0, 1.0, 0.01) var reverb_damp: float = 0.5
@export_range(0.0, 1.0, 0.01) var reverb_wet: float = 0.2
@export_range(0.0, 500.0, 1.0) var reverb_predelay_ms: float = 30.0

# Poisson scheduling (mean events/second for sweetener layers)
@export_range(0.0, 1.0, 0.001) var wildlife_lambda: float = 0.05
@export_range(0.0, 1.0, 0.001) var distant_lambda: float = 0.01
'''


BIOME_AMBIENCE_REGISTRY_GD = '''@tool
class_name BiomeAmbienceRegistry
extends Resource

# Lookup table biome_id -> BiomeAmbiencePreset. Used by
# BiomeAmbienceController.set_biome(biome_id).

@export var presets: Dictionary = {}
'''


BIOME_AMBIENCE_CONTROLLER_GD = '''class_name BiomeAmbienceController
extends Node

# Runtime controller for biome-aware ambience.
#
# Usage:
#   var c := preload("res://audio/ambience/BiomeAmbienceController.tscn").instantiate()
#   add_child(c)
#   c.set_biome("ice_cavern")
#
# What it does:
#   - Two AudioStreamPlayer for bed_drone + bed_air (always-on loops, Ambience bus)
#   - Two Timer-driven Poisson schedulers for wildlife + distant sweeteners
#   - 4-second crossfade between current and target biome on set_biome()
#   - Per-biome reverb tuning on the AmbienceReverb bus (room_size/damp/wet/predelay)
#
# Per-zone density override:
#   c.density_multiplier = 2.0    # double the wildlife/distant rate
#
# Requirements:
#   res://audio/ambience/biome_ambience_registry.tres   (output of ambience_pack.py)
#   Bus "Ambience" + "AmbienceReverb" loaded (or import bus_layout_ambience_overlay.tres)

const REGISTRY_PATH := "res://audio/ambience/biome_ambience_registry.tres"
const CROSSFADE_S := 4.0
const AMBIENCE_BUS := "Ambience"
const AMBIENCE_REVERB_BUS := "AmbienceReverb"
const SWEETENER_RADIUS_M := 12.0     # Poisson emitters spawned within this radius

@export var density_multiplier: float = 1.0

var registry: BiomeAmbienceRegistry
var current_biome: String = ""
var current_preset: BiomeAmbiencePreset = null

@onready var bed_drone_player: AudioStreamPlayer = $BedDrone
@onready var bed_air_player: AudioStreamPlayer = $BedAir
@onready var wildlife_timer: Timer = $WildlifeTimer
@onready var distant_timer: Timer = $DistantTimer

func _ready() -> void:
    if ResourceLoader.exists(REGISTRY_PATH):
        registry = load(REGISTRY_PATH) as BiomeAmbienceRegistry
    bed_drone_player.bus = AMBIENCE_BUS
    bed_air_player.bus = AMBIENCE_BUS
    wildlife_timer.timeout.connect(_on_wildlife_tick)
    distant_timer.timeout.connect(_on_distant_tick)
    _schedule_wildlife()
    _schedule_distant()

func set_biome(biome_id: String) -> void:
    if biome_id == current_biome:
        return
    if registry == null or not registry.presets.has(biome_id):
        push_warning("BiomeAmbienceController: unknown biome %s" % biome_id)
        return
    var target: BiomeAmbiencePreset = registry.presets[biome_id]
    _crossfade_to(target)
    current_biome = biome_id
    current_preset = target
    _apply_reverb(target)
    _schedule_wildlife()
    _schedule_distant()

func _crossfade_to(target: BiomeAmbiencePreset) -> void:
    var tween := create_tween().set_parallel(true)
    # fade out current beds
    if bed_drone_player.playing:
        tween.tween_property(bed_drone_player, "volume_db", -80.0, CROSSFADE_S)
    if bed_air_player.playing:
        tween.tween_property(bed_air_player, "volume_db", -80.0, CROSSFADE_S)
    await tween.finished
    # swap streams + restart at -80 dB then fade in
    bed_drone_player.stream = target.bed_drone
    bed_air_player.stream = target.bed_air
    bed_drone_player.volume_db = -80.0
    bed_air_player.volume_db = -80.0
    bed_drone_player.play()
    bed_air_player.play()
    var fade_in := create_tween().set_parallel(true)
    fade_in.tween_property(bed_drone_player, "volume_db", 0.0, CROSSFADE_S)
    fade_in.tween_property(bed_air_player, "volume_db", 0.0, CROSSFADE_S)

func _apply_reverb(p: BiomeAmbiencePreset) -> void:
    var idx := AudioServer.get_bus_index(AMBIENCE_REVERB_BUS)
    if idx == -1:
        push_warning("BiomeAmbienceController: AmbienceReverb bus not found.")
        return
    var fx := AudioServer.get_bus_effect(idx, 0)
    if fx is AudioEffectReverb:
        fx.room_size = p.reverb_room_size
        fx.damping = p.reverb_damp
        fx.wet = p.reverb_wet
        fx.predelay_msec = p.reverb_predelay_ms

func _schedule_wildlife() -> void:
    if current_preset == null:
        wildlife_timer.stop()
        return
    var lam := current_preset.wildlife_lambda * max(density_multiplier, 0.0)
    if lam <= 0.0:
        wildlife_timer.stop()
        return
    # Poisson inter-arrival = -ln(U)/lambda
    var u := randf()
    if u <= 0.0:
        u = 0.0001
    wildlife_timer.start(-log(u) / lam)

func _schedule_distant() -> void:
    if current_preset == null:
        distant_timer.stop()
        return
    var lam := current_preset.distant_lambda * max(density_multiplier, 0.0)
    if lam <= 0.0:
        distant_timer.stop()
        return
    var u := randf()
    if u <= 0.0:
        u = 0.0001
    distant_timer.start(-log(u) / lam)

func _on_wildlife_tick() -> void:
    _spawn_one_shot(current_preset.wildlife_randomizer)
    _schedule_wildlife()

func _on_distant_tick() -> void:
    _spawn_one_shot(current_preset.distant_randomizer)
    _schedule_distant()

func _spawn_one_shot(stream: AudioStream) -> void:
    if stream == null:
        return
    var p := AudioStreamPlayer3D.new()
    p.stream = stream
    p.bus = AMBIENCE_BUS
    p.unit_size = 4.0
    p.max_distance = 80.0
    p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
    add_child(p)
    var ang := randf() * TAU
    var r := randf_range(SWEETENER_RADIUS_M * 0.3, SWEETENER_RADIUS_M)
    p.position = Vector3(r * cos(ang), 0.0, r * sin(ang))
    p.finished.connect(p.queue_free)
    p.play()
'''


BIOME_AMBIENCE_CONTROLLER_TSCN = '''[gd_scene load_steps=2 format=3 uid="uid://biomeambctrl1"]

[ext_resource type="Script" path="res://audio/ambience/BiomeAmbienceController.gd" id="1_ctrl"]

[node name="BiomeAmbienceController" type="Node"]
script = ExtResource("1_ctrl")

[node name="BedDrone" type="AudioStreamPlayer" parent="."]
bus = &"Ambience"
autoplay = false

[node name="BedAir" type="AudioStreamPlayer" parent="."]
bus = &"Ambience"
autoplay = false

[node name="WildlifeTimer" type="Timer" parent="."]
one_shot = true
autostart = false

[node name="DistantTimer" type="Timer" parent="."]
one_shot = true
autostart = false
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_root", type=Path,
                    default=ASSETS / "audio" / "ambience")
    ap.add_argument("--out", dest="out_root", type=Path,
                    default=ASSETS / "audio" / "godot" / "ambience")
    ap.add_argument("--godot-root", default="audio/ambience",
                    help="Path inside the Godot project (under res://) where this "
                         "directory will be mounted.")
    args = ap.parse_args()

    summary = export_all(args.in_root, args.out_root, godot_root=args.godot_root)
    write_runtime_files(args.out_root)
    print(f"[ambience_pack] exported {summary['biome_count']} biomes "
          f"({', '.join(summary['biomes'])}) -> {args.out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
