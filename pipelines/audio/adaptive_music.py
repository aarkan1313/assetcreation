"""Adaptive music orchestrator scaffold.

Per `research/E2_audio_local_ambience.md` §3.4 and the v3 brief: build a
**scaffold** for adaptive music using Godot 4.5's `AudioStreamSynchronized`
node. **No generation backend is wired** because every shipping-clean
open-weights music model is currently parked:

  - MusicGen / AudioGen / AudioCraft : CC-BY-NC weights → not shippable
  - Suno / Lyria 3 / Udio            : cloud-only; license unclear / TBD
  - YuE                               : Apache-2.0 first commercial-ok
                                        open-weights model (Research K
                                        rec #11) but pilot-stage; reserved
                                        for hero tracks
  - DiffRhythm                        : research-only as of 2026-05

So this tool reads a music *intent* JSON describing target tracks + stems
and emits two artifacts:

  1. `audio/music/<id>/intent.json`   — copy-with-provenance (the input)
  2. `audio/music/<id>/manifest.json` — list of expected stem files
                                        (placeholders today; real audio
                                        slots in later)
  3. `audio/godot/music/<id>/track.tscn` — Godot 4.5
                                           AudioStreamSynchronized scaffold
                                           with N stem slots + per-stem
                                           bus + Music bus routing.
  4. `audio/godot/music/<id>/AdaptiveMusicTrack.gd` — runtime controller:
        - `set_intensity(level: float)`   0..1
        - `set_state(name: String)`       state -> stem-mix mapping
        - `play()` / `stop()` / `crossfade_to(track_id, seconds)`

Intent schema:

```json
{
  "id": "combat_a",
  "display_name": "Combat track A",
  "bpm": 120,
  "bars": 16,
  "loop": true,
  "stems": [
    {"id": "drums",    "intensity_min": 0.0, "intensity_max": 1.0},
    {"id": "bass",     "intensity_min": 0.0, "intensity_max": 1.0},
    {"id": "lead",     "intensity_min": 0.4, "intensity_max": 1.0},
    {"id": "perc_hi",  "intensity_min": 0.7, "intensity_max": 1.0}
  ],
  "states": {
    "calm":      {"intensity": 0.2},
    "tense":     {"intensity": 0.6},
    "combat":    {"intensity": 0.9},
    "victory":   {"intensity": 1.0, "next_track": "victory_a"}
  }
}
```

This shape mirrors how Wwise / FMOD model "music states" — each state maps
to an intensity level which the runtime translates into per-stem volume.
The orchestrator is intentionally **mixer-style**, not procedural-composition.

CLI:
  python adaptive_music.py --intent recipes/music_intents/combat_a.json
  python adaptive_music.py --all       # walk every intent in recipes/music_intents/
  python adaptive_music.py --emit-stub combat_a   # write a starter intent JSON
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ASSETS = Path(r"D:\assets")
DEFAULT_INTENTS_DIR = ASSETS / "pipelines" / "audio" / "recipes" / "music_intents"
DEFAULT_OUT = ASSETS / "audio" / "music"
DEFAULT_GODOT = ASSETS / "audio" / "godot" / "music"

EXAMPLE_INTENTS = {
    "combat_a": {
        "id": "combat_a",
        "display_name": "Combat — Track A",
        "bpm": 120, "bars": 16, "loop": True,
        "stems": [
            {"id": "drums", "intensity_min": 0.0, "intensity_max": 1.0},
            {"id": "bass", "intensity_min": 0.0, "intensity_max": 1.0},
            {"id": "lead", "intensity_min": 0.4, "intensity_max": 1.0},
            {"id": "perc_hi", "intensity_min": 0.7, "intensity_max": 1.0},
        ],
        "states": {
            "calm":     {"intensity": 0.2},
            "tense":    {"intensity": 0.6},
            "combat":   {"intensity": 0.9},
            "victory":  {"intensity": 1.0, "next_track": "victory_a"},
        },
    },
    "exploration_a": {
        "id": "exploration_a",
        "display_name": "Exploration — Track A",
        "bpm": 90, "bars": 32, "loop": True,
        "stems": [
            {"id": "pad", "intensity_min": 0.0, "intensity_max": 1.0},
            {"id": "harp", "intensity_min": 0.2, "intensity_max": 1.0},
            {"id": "low_strings", "intensity_min": 0.5, "intensity_max": 1.0},
        ],
        "states": {
            "open":      {"intensity": 0.4},
            "discovery": {"intensity": 0.8},
        },
    },
    "bossfight_a": {
        "id": "bossfight_a",
        "display_name": "Boss Fight — Track A",
        "bpm": 140, "bars": 16, "loop": True,
        "stems": [
            {"id": "drums", "intensity_min": 0.0, "intensity_max": 1.0},
            {"id": "low_brass", "intensity_min": 0.0, "intensity_max": 1.0},
            {"id": "choir", "intensity_min": 0.3, "intensity_max": 1.0},
            {"id": "lead_strings", "intensity_min": 0.5, "intensity_max": 1.0},
            {"id": "perc_taiko", "intensity_min": 0.8, "intensity_max": 1.0},
        ],
        "states": {
            "intro":   {"intensity": 0.5},
            "phase_1": {"intensity": 0.7},
            "phase_2": {"intensity": 0.9},
            "phase_3": {"intensity": 1.0},
            "defeated":{"intensity": 0.4, "next_track": "victory_a"},
        },
    },
    "town_a": {
        "id": "town_a",
        "display_name": "Town — Track A",
        "bpm": 100, "bars": 24, "loop": True,
        "stems": [
            {"id": "guitar", "intensity_min": 0.0, "intensity_max": 1.0},
            {"id": "flute", "intensity_min": 0.3, "intensity_max": 1.0},
            {"id": "tambourine", "intensity_min": 0.6, "intensity_max": 1.0},
        ],
        "states": {
            "morning":{"intensity": 0.5},
            "evening":{"intensity": 0.8},
            "festival":{"intensity": 1.0},
        },
    },
}


@dataclass
class TrackArtifacts:
    intent: dict
    out_dir: Path
    godot_dir: Path
    intent_json: Path
    manifest_json: Path
    track_tscn: Path
    controller_gd: Path
    placeholder_stems: list[Path] = field(default_factory=list)


def _validate(intent: dict) -> list[str]:
    errors = []
    for k in ("id", "display_name", "bpm", "stems", "states"):
        if k not in intent:
            errors.append(f"missing {k!r}")
    for st in intent.get("stems", []):
        if "id" not in st:
            errors.append(f"stem missing id: {st!r}")
    return errors


def _bus_layout_amendment(intent: dict) -> dict:
    """Music bus configuration the Godot side should add.

    A future bus_layout exporter (in export_godot.py) would consume this and
    write a Music + per-stem bus tree. For now we just emit it as JSON so the
    Godot side documents what's expected.
    """
    return {
        "Master": {"children": ["Music"]},
        "Music": {"send": "Master", "default_db": 0.0,
                  "children": [f"Music_{s['id']}" for s in intent.get("stems", [])]},
    }


def _make_placeholder_wav(path: Path, *, duration_s: float = 30.0,
                          samplerate: int = 44100) -> None:
    """Write a duration-correct silent WAV. Real stems slot in later by
    overwriting these files."""
    import wave, struct
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(duration_s * samplerate)
    pcm = b"\x00\x00" * n
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(samplerate)
        w.writeframes(pcm)


# ---------- Godot scaffold writers ----------

GD_CONTROLLER = '''# AdaptiveMusicTrack — runtime controller for an adaptive music track.
#
# Generated by pipelines/audio/adaptive_music.py. Do not hand-edit; re-run
# the Python tool to regenerate.
#
# How it works:
#  - One AudioStreamSynchronized resource holds N synchronized stems.
#  - Each stem has its own bus (Music_<stem_id>) so volume can be mixed live.
#  - set_intensity(level) maps 0..1 to per-stem volume_db using each stem's
#    intensity_min/intensity_max envelope.
#  - set_state(name) looks up the state in `STATES` and applies its intensity.
#  - crossfade_to() tweens volume_db down then loads + starts the next track.

extends Node
class_name {ClassName}

const STEMS: Array = {STEMS_LITERAL}
const STATES: Dictionary = {STATES_LITERAL}
const BPM: float = {BPM}
const BARS: int = {BARS}
const LOOP: bool = {LOOP}

var _intensity: float = 1.0
var _stream_sync: AudioStreamSynchronized
var _player: AudioStreamPlayer

func _ready() -> void:
	_player = AudioStreamPlayer.new()
	_player.bus = "Music"
	add_child(_player)
	_player.stream = _build_synchronized_stream()
	apply_intensity(_intensity)

func _build_synchronized_stream() -> AudioStreamSynchronized:
	var sync := AudioStreamSynchronized.new()
	sync.stream_count = STEMS.size()
	for i in range(STEMS.size()):
		var info: Dictionary = STEMS[i]
		var stem_path := "res://audio/music/{TrackId}/{stem}.wav".format({{"stem": info.id}})
		var stream: AudioStream = load(stem_path)
		sync.set_sync_stream(i, stream)
		sync.set_sync_stream_volume(i, 0.0)
	return sync

func play() -> void:
	if _player and not _player.playing:
		_player.play()

func stop() -> void:
	if _player and _player.playing:
		_player.stop()

func set_intensity(level: float) -> void:
	_intensity = clamp(level, 0.0, 1.0)
	apply_intensity(_intensity)

func apply_intensity(level: float) -> void:
	for i in range(STEMS.size()):
		var info: Dictionary = STEMS[i]
		var lo: float = info.get("intensity_min", 0.0)
		var hi: float = info.get("intensity_max", 1.0)
		var v: float = 0.0
		if level <= lo:
			v = -80.0
		elif level >= hi:
			v = 0.0
		else:
			# Linear ramp -80 dB -> 0 dB across [lo, hi]
			v = lerp(-80.0, 0.0, (level - lo) / max(hi - lo, 0.001))
		_stream_sync = _player.stream as AudioStreamSynchronized
		if _stream_sync:
			_stream_sync.set_sync_stream_volume(i, v)

func set_state(name: String) -> void:
	if not STATES.has(name):
		push_warning("[AdaptiveMusicTrack] unknown state: %s" % name)
		return
	var st: Dictionary = STATES[name]
	if st.has("intensity"):
		set_intensity(float(st["intensity"]))
	if st.has("next_track"):
		# Caller is expected to load the next track and crossfade.
		emit_signal("state_requests_track_change", st["next_track"])

signal state_requests_track_change(track_id: String)

func crossfade_to(other: AdaptiveMusicTrack, seconds: float = 4.0) -> void:
	if other == null:
		return
	var tween := create_tween().set_parallel(true)
	tween.tween_property(_player, "volume_db", -80.0, seconds)
	other.play()
	tween.tween_property(other._player, "volume_db", 0.0, seconds).from(-80.0)
	tween.finished.connect(stop)
'''


def write_track(intent: dict, out_root: Path, godot_root: Path) -> TrackArtifacts:
    track_id = intent["id"]
    out_dir = out_root / track_id
    godot_dir = godot_root / track_id
    out_dir.mkdir(parents=True, exist_ok=True)
    godot_dir.mkdir(parents=True, exist_ok=True)

    # 1) intent.json (copy-with-provenance)
    annotated = dict(intent)
    annotated["_generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    annotated["_generator"] = "pipelines/audio/adaptive_music.py"
    annotated["_bus_layout_amendment"] = _bus_layout_amendment(intent)
    intent_json = out_dir / "intent.json"
    intent_json.write_text(json.dumps(annotated, indent=2), encoding="utf-8")

    # 2) manifest.json — placeholder stems
    samplerate = 44100
    bpm = float(intent.get("bpm", 120))
    bars = int(intent.get("bars", 16))
    beats_per_bar = 4
    duration_s = (bars * beats_per_bar) * (60.0 / bpm)
    placeholders: list[Path] = []
    for stem in intent.get("stems", []):
        wav_path = out_dir / f"{stem['id']}.wav"
        if not wav_path.exists():
            _make_placeholder_wav(wav_path, duration_s=duration_s, samplerate=samplerate)
        placeholders.append(wav_path)
    manifest = {
        "track_id": track_id,
        "bpm": bpm, "bars": bars, "duration_s": duration_s,
        "loop": bool(intent.get("loop", True)),
        "stems": [
            {
                "id": s["id"],
                "wav": str((out_dir / f"{s['id']}.wav").relative_to(ASSETS)).replace("\\", "/"),
                "intensity_min": s.get("intensity_min", 0.0),
                "intensity_max": s.get("intensity_max", 1.0),
                "is_placeholder": True,
            }
            for s in intent.get("stems", [])
        ],
        "states": intent.get("states", {}),
    }
    manifest_json = out_dir / "manifest.json"
    manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # 3) track.tscn — wraps the AudioStreamSynchronized
    tscn_text = _build_tscn(intent, manifest)
    track_tscn = godot_dir / "track.tscn"
    track_tscn.write_text(tscn_text, encoding="utf-8")

    # 4) AdaptiveMusicTrack.gd
    class_name = f"AdaptiveMusicTrack_{track_id.replace('-', '_').replace(' ', '_')}"
    gd_text = (GD_CONTROLLER
               .replace("{ClassName}", class_name)
               .replace("{TrackId}", track_id)
               .replace("{STEMS_LITERAL}", _gd_literal(intent.get("stems", [])))
               .replace("{STATES_LITERAL}", _gd_literal(intent.get("states", {})))
               .replace("{BPM}", str(intent.get("bpm", 120)))
               .replace("{BARS}", str(intent.get("bars", 16)))
               .replace("{LOOP}", "true" if intent.get("loop", True) else "false"))
    controller_gd = godot_dir / "AdaptiveMusicTrack.gd"
    controller_gd.write_text(gd_text, encoding="utf-8")

    return TrackArtifacts(
        intent=annotated, out_dir=out_dir, godot_dir=godot_dir,
        intent_json=intent_json, manifest_json=manifest_json,
        track_tscn=track_tscn, controller_gd=controller_gd,
        placeholder_stems=placeholders,
    )


def _gd_literal(value: Any) -> str:
    """Render a Python value as a Godot 4 GDScript literal. Supports
    primitives, lists, and dicts; safe for the small JSON shapes used
    here. We re-use `json.dumps` because GDScript 4 accepts JSON-compatible
    Array / Dictionary literals (and `true`/`false` too)."""
    return json.dumps(value)


def _build_tscn(intent: dict, manifest: dict) -> str:
    """Hand-write a small Godot 4.5 .tscn referring to the controller GD and
    each stem WAV. Same ext_resource shape Godot writes itself."""
    track_id = intent["id"]
    lines = []
    lines.append('[gd_scene load_steps=2 format=3 uid="uid://amus_' + track_id[:14] + '"]')
    lines.append('')
    lines.append(f'[ext_resource type="Script" path="res://audio/godot/music/{track_id}/AdaptiveMusicTrack.gd" id="1_ctrl"]')
    lines.append('')
    lines.append('[node name="AdaptiveMusicTrack" type="Node"]')
    lines.append('script = ExtResource("1_ctrl")')
    lines.append('')
    return "\n".join(lines)


# ---------- top level ----------

def emit_stub(track_id: str, intents_dir: Path) -> Path:
    intents_dir.mkdir(parents=True, exist_ok=True)
    template = EXAMPLE_INTENTS.get(track_id)
    if template is None:
        # Generic stub — combat shape with the requested id
        template = dict(EXAMPLE_INTENTS["combat_a"])
        template["id"] = track_id
        template["display_name"] = track_id.replace("_", " ").title()
    path = intents_dir / f"{track_id}.json"
    path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intent", type=Path, default=None,
                    help="Single music intent JSON to compile.")
    ap.add_argument("--all", action="store_true",
                    help="Compile every JSON in the intents dir.")
    ap.add_argument("--intents-dir", type=Path, default=DEFAULT_INTENTS_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="Where placeholder stems + intent/manifest land.")
    ap.add_argument("--godot-out", type=Path, default=DEFAULT_GODOT,
                    help="Where Godot scaffold .tscn / .gd land.")
    ap.add_argument("--emit-stub", default=None,
                    help="Write a starter intent JSON for this id and exit.")
    args = ap.parse_args()

    if args.emit_stub:
        path = emit_stub(args.emit_stub, args.intents_dir)
        print(f"[adaptive_music] wrote stub: {path}")
        return 0

    intents: list[dict] = []
    if args.intent:
        intents.append(json.loads(args.intent.read_text(encoding="utf-8")))
    elif args.all:
        if not args.intents_dir.exists():
            args.intents_dir.mkdir(parents=True, exist_ok=True)
            for stub_id in EXAMPLE_INTENTS:
                emit_stub(stub_id, args.intents_dir)
            print(f"[adaptive_music] seeded {args.intents_dir} with {len(EXAMPLE_INTENTS)} examples")
        for p in sorted(args.intents_dir.glob("*.json")):
            intents.append(json.loads(p.read_text(encoding="utf-8")))
    else:
        print("[adaptive_music] need --intent <file> or --all (or --emit-stub <id>).")
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    args.godot_out.mkdir(parents=True, exist_ok=True)

    arts: list[TrackArtifacts] = []
    for intent in intents:
        errors = _validate(intent)
        if errors:
            print(f"[adaptive_music] {intent.get('id','?')}: invalid: "
                  f"{'; '.join(errors)}")
            continue
        a = write_track(intent, args.out, args.godot_out)
        arts.append(a)
        print(f"[adaptive_music] {intent['id']}: "
              f"{len(a.placeholder_stems)} placeholder stems, "
              f"out={a.out_dir}, godot={a.godot_dir}")

    # Top-level music_pack.json
    pack = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tracks": [
            {
                "id": a.intent["id"],
                "manifest": str(a.manifest_json.relative_to(ASSETS)).replace("\\","/"),
                "tscn": str(a.track_tscn.relative_to(ASSETS)).replace("\\","/"),
                "controller": str(a.controller_gd.relative_to(ASSETS)).replace("\\","/"),
                "stem_count": len(a.placeholder_stems),
            }
            for a in arts
        ],
    }
    pack_path = args.godot_out / "music_pack.json"
    pack_path.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    print(f"[adaptive_music] pack -> {pack_path} ({len(arts)} tracks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
