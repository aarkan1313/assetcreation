"""End-to-end demo: synth -> process -> qa -> godot export.

Builds three demo sounds (`ui_click`, `sword_swing`, `fireball_cast`),
each with 3 variants, then runs them through process_audio + audio_qa and
finally export_godot.

Output:
  audio/sfx/<id>_v{0,1,2}.wav            processed WAVs
  audio/sfx/<id>_v{0,1,2}_qa/...         waveform + spectrogram + qa.json
  audio/sfx_manifest.json                 manifest for the exporter
  audio/godot/<cat>/<id>/...              Godot drop-in
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from synth_sfx import synthesize, write_wav  # noqa: E402
from process_audio import process, read_wav   # noqa: E402
from audio_qa import qa                        # noqa: E402
from export_godot import export_bank           # noqa: E402

ASSETS = Path(r"D:\assets")
SFX_DIR = ASSETS / "audio" / "sfx"


DEMO = [
    {
        "id": "ui_click",
        "preset": "ui_click",
        "category": "ui",
        "target_rms_db": -22.0,
        "variants": 3,
    },
    {
        "id": "sword_swing",
        "preset": "sword_swing",
        "category": "sfx",
        "target_rms_db": -16.0,
        "variants": 3,
    },
    {
        "id": "fireball_cast",
        "preset": "fireball_cast",
        "category": "sfx",
        "target_rms_db": -16.0,
        "variants": 3,
    },
]


def main() -> int:
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    manifest_sounds = []
    for snd in DEMO:
        sid = snd["id"]
        preset = snd["preset"]
        cat = snd["category"]
        target = snd["target_rms_db"]
        variants_paths_rel: list[str] = []
        cue_processing: list[dict] = []
        for v in range(snd["variants"]):
            seed = 1000 + 31 * v + hash(preset) % 97
            samples = synthesize(preset, seed=seed)
            raw_path = SFX_DIR / f"{sid}_v{v}_raw.wav"
            write_wav(raw_path, samples)
            # process
            proc, rep = process(samples, target_rms_db=target)
            out_path = SFX_DIR / f"{sid}_v{v}.wav"
            write_wav(out_path, proc)
            rep.in_path = str(raw_path)
            rep.out_path = str(out_path)
            cue_processing.append({
                "variant": v,
                "duration_s": rep.duration_out,
                "rms_dbfs_in": rep.rms_db_in,
                "rms_dbfs_out": rep.rms_db_out,
                "peak_dbfs_out": rep.peak_db_out,
                "trim_ms": rep.trim_ms_head + rep.trim_ms_tail,
                "fade_ms": rep.fade_ms,
            })
            # qa
            qa_dir = SFX_DIR / f"{sid}_v{v}_qa"
            info = qa(out_path, qa_dir)
            cue_processing[-1]["qa"] = {
                "clipped": info["clipped_samples"],
                "click_count_estimate": info["click_count_estimate"],
            }
            rel = f"audio/sfx/{sid}_v{v}.wav"
            variants_paths_rel.append(rel)
            # remove raw
            raw_path.unlink(missing_ok=True)
        manifest_sounds.append({
            "id": sid,
            "category": cat,
            "variants": variants_paths_rel,
            "cue": {
                "preset": preset,
                "target_rms_db": target,
                "processing": cue_processing,
                "backend": "synth_sfx",
            },
        })
        print(f"[build_demo] {sid}: {snd['variants']} variants synthesized + processed + QA")

    manifest_path = ASSETS / "audio" / "sfx_manifest.json"
    manifest_path.write_text(json.dumps({"sounds": manifest_sounds}, indent=2))
    counts = export_bank(manifest_path, ASSETS / "audio" / "godot")
    print(f"[build_demo] manifest -> {manifest_path}")
    print(f"[build_demo] godot export: {sum(counts.values())} variants for {len(counts)} sounds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
