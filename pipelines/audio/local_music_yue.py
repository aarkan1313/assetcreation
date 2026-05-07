"""YuE local music pilot.

Phase 9 K-rec #11: first commercial-shippable open music pilot lane. This is
not a full adaptive music orchestrator; it writes a plan/cue for 1-2 hero
tracks and can call a local YuE command template when the GPU is free.

The adapter intentionally does not support MusicGen, AudioCraft, or AudioGen
because those are non-commercial traps for this project.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import struct
import subprocess
import sys
import wave
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ASSETS = Path(r"D:\assets")
MUSIC_OUT = ASSETS / "audio" / "music"
SAMPLE_RATE = 44_100
MODEL_ID = "multimodal-art-projection/YuE"


@dataclass
class MusicReport:
    schema: str
    backend: str
    model_id: str
    title: str
    prompt: str
    lyrics: str | None
    duration_s: float
    seed: int
    dry_run: bool
    out_path: str
    license_note: str
    timestamp: str


def write_placeholder(path: Path, duration: float, seed: int) -> int:
    samples = int(max(1.0, min(duration, 20.0)) * SAMPLE_RATE)
    path.parent.mkdir(parents=True, exist_ok=True)
    root = 110.0 + (seed % 12) * 2.5
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        frames = []
        for i in range(samples):
            t = i / SAMPLE_RATE
            env = min(1.0, i / (0.25 * SAMPLE_RATE), (samples - i) / (0.5 * SAMPLE_RATE))
            pad = 0.08 * env * (
                math.sin(2 * math.pi * root * t)
                + 0.5 * math.sin(2 * math.pi * root * 1.5 * t)
                + 0.35 * math.sin(2 * math.pi * root * 2.0 * t)
            )
            pulse = 0.02 * env * math.sin(2 * math.pi * 2.0 * t)
            left = int(max(-1.0, min(1.0, pad + pulse)) * 32767)
            right = int(max(-1.0, min(1.0, pad - pulse)) * 32767)
            frames.append(struct.pack("<hh", left, right))
        wav.writeframes(b"".join(frames))
    return samples


def write_report(path: Path, report: MusicReport, extra: dict | None = None) -> Path:
    cue = path.with_suffix(".music.json")
    payload = asdict(report)
    if extra:
        payload.update(extra)
    cue.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return cue


def dry_run(args: argparse.Namespace) -> int:
    samples = write_placeholder(args.out, args.duration, args.seed)
    report = MusicReport(
        schema="local_music_yue.report.v1",
        backend="dry_run_placeholder_music",
        model_id=MODEL_ID,
        title=args.title,
        prompt=args.prompt,
        lyrics=args.lyrics,
        duration_s=args.duration,
        seed=args.seed,
        dry_run=True,
        out_path=str(args.out),
        license_note="YuE selected by Research K as commercial-shippable candidate; verify exact checkpoint/model-card terms before ship.",
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    cue = write_report(args.out, report, extra={"samples": samples, "sample_rate": SAMPLE_RATE})
    print(f"[local_music_yue] dry-run {samples / SAMPLE_RATE:.2f}s placeholder -> {args.out}")
    print(f"[local_music_yue] cue -> {cue}; no model import/load performed")
    return 0


def run_yue_command(args: argparse.Namespace) -> int:
    cmd_template = os.environ.get("YUE_MUSIC_CMD")
    if not cmd_template:
        print("[local_music_yue] YUE_MUSIC_CMD is not set; use --dry-run or set a local command template", file=sys.stderr)
        return 2
    lyrics_path = ""
    if args.lyrics:
        lyrics_file = args.out.with_suffix(".lyrics.txt")
        lyrics_file.write_text(args.lyrics, encoding="utf-8")
        lyrics_path = str(lyrics_file)
    cmd = cmd_template.format(
        prompt=args.prompt,
        lyrics=lyrics_path,
        out=str(args.out),
        seed=args.seed,
        duration=args.duration,
        title=args.title,
    )
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"[local_music_yue] YuE command failed with exit {result.returncode}", file=sys.stderr)
        return result.returncode
    report = MusicReport(
        schema="local_music_yue.report.v1",
        backend="yue_command",
        model_id=MODEL_ID,
        title=args.title,
        prompt=args.prompt,
        lyrics=args.lyrics,
        duration_s=args.duration,
        seed=args.seed,
        dry_run=False,
        out_path=str(args.out),
        license_note="Verify exact YuE checkpoint/model-card terms before ship.",
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    write_report(args.out, report)
    print(f"[local_music_yue] YuE command -> {args.out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="phase9_yue_pilot")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--lyrics", default=None)
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=MUSIC_OUT / "phase9_yue_pilot.wav")
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    ap.add_argument("--run-model", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run or args.device == "cpu" or not args.run_model:
        return dry_run(args)
    if args.device != "cuda":
        print("[local_music_yue] --run-model requires --device cuda", file=sys.stderr)
        return 2
    return run_yue_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
