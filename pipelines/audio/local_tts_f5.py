"""Local open-weights TTS lane: F5-TTS voice clone + Kokoro placeholder barks.

Build-time default writes a deterministic placeholder WAV and cue JSON so the
voice pipeline can be verified without loading models or touching the GPU.

Real F5-TTS generation is routed through ComfyUI and gated by:

  --device cuda --run-model

Kokoro-82M is exposed as a cheap-TTS sibling via --engine kokoro. Its real
runtime path is command-template based so the installed local wrapper can vary
without changing this pipeline contract.

License discipline:
  - F5-TTS: MIT.
  - Kokoro-82M: commercial-friendly open weights per Research K; verify model
    card before shipping a specific voice pack.
  - XTTS-v2 and Spark-TTS are intentionally not supported here.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import wave
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ASSETS = Path(r"D:\assets")
sys.path.insert(0, str(ASSETS))

from pipelines._meta.comfy_runner import ComfyError, ComfyRunner  # noqa: E402


SAMPLE_RATE = 24_000
DEFAULT_WORKFLOW = ASSETS / "pipelines" / "_meta" / "comfy_workflows" / "f5tts_voice_clone.json"
VOICE_OUT = ASSETS / "audio" / "voice"

MODEL_IDS = {
    "f5": "SWivid/F5-TTS",
    "kokoro": "hexgrad/Kokoro-82M",
}


@dataclass
class TTSReport:
    schema: str
    engine: str
    model_id: str
    text: str
    reference_audio: str | None
    reference_text: str | None
    voice: str | None
    seed: int
    speed: float
    samplerate: int
    samples: int
    backend: str
    dry_run: bool
    out_path: str
    timestamp: str


def estimate_duration_s(text: str, speed: float) -> float:
    words = max(1, len(text.split()))
    return max(0.8, min(18.0, words * 0.34 / max(0.25, speed) + 0.35))


def placeholder_voice(text: str, *, seed: int, speed: float) -> list[int]:
    duration = estimate_duration_s(text, speed)
    samples = int(duration * SAMPLE_RATE)
    base = 150.0 + (seed % 35)
    out: list[int] = []
    for i in range(samples):
        t = i / SAMPLE_RATE
        word_gate = 0.55 + 0.45 * math.sin(2.0 * math.pi * 4.0 * t)
        syllable = math.sin(2.0 * math.pi * (base + 18.0 * math.sin(2.0 * math.pi * 2.1 * t)) * t)
        breath = math.sin(2.0 * math.pi * 820.0 * t) * 0.025
        envelope = min(1.0, i / (0.05 * SAMPLE_RATE), (samples - i) / (0.08 * SAMPLE_RATE))
        value = 0.18 * envelope * word_gate * (syllable + breath)
        out.append(int(max(-1.0, min(1.0, value)) * 32767))
    return out


def write_wav(path: Path, pcm16: list[int], sample_rate: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(struct.pack("<h", sample) for sample in pcm16))


def write_report(path: Path, report: TTSReport, *, extra: dict | None = None) -> Path:
    cue_path = path.with_suffix(".cue.json")
    payload = asdict(report)
    if extra:
        payload.update(extra)
    cue_path.parent.mkdir(parents=True, exist_ok=True)
    cue_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return cue_path


def dry_run(args: argparse.Namespace) -> int:
    pcm = placeholder_voice(args.text, seed=args.seed, speed=args.speed)
    write_wav(args.out, pcm)
    report = TTSReport(
        schema="local_tts_open.report.v1",
        engine=args.engine,
        model_id=MODEL_IDS[args.engine],
        text=args.text,
        reference_audio=str(args.ref_audio) if args.ref_audio else None,
        reference_text=args.ref_text,
        voice=args.voice,
        seed=args.seed,
        speed=args.speed,
        samplerate=SAMPLE_RATE,
        samples=len(pcm),
        backend="dry_run_placeholder_voice",
        dry_run=True,
        out_path=str(args.out),
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    cue = write_report(args.out, report)
    print(f"[local_tts_f5] dry-run {args.engine}: {len(pcm) / SAMPLE_RATE:.2f}s -> {args.out}")
    print(f"[local_tts_f5] cue -> {cue}; no model import/load performed")
    return 0


def run_f5_comfy(args: argparse.Namespace) -> int:
    if not args.ref_audio:
        print("[local_tts_f5] F5 Comfy run requires --ref-audio", file=sys.stderr)
        return 2
    if not args.ref_audio.exists():
        print(f"[local_tts_f5] missing --ref-audio: {args.ref_audio}", file=sys.stderr)
        return 1
    runner = ComfyRunner(args.host)
    try:
        ref_name = runner.upload_input_file(args.ref_audio, name=f"phase9_f5_ref_{args.ref_audio.name}")
        result = runner.run(
            workflow_path=args.workflow,
            overrides={
                "1.inputs.audio": ref_name,
                "2.inputs.reference_text": args.ref_text or "",
                "2.inputs.text": args.text,
                "2.inputs.seed": args.seed,
                "2.inputs.speed": args.speed,
                "3.inputs.filename_prefix": args.out.stem,
            },
            output_node_ids=[args.output_node],
            out_dir=args.out.parent / "_comfy_raw" / args.out.stem,
            dry_run=False,
            validate_nodes=True,
            timeout_s=600.0,
            poll_s=1.5,
        )
    except (ComfyError, OSError) as exc:
        print(f"[local_tts_f5] failed: {exc}", file=sys.stderr)
        return 1
    if not result.downloaded:
        print("[local_tts_f5] ComfyUI completed without downloaded audio", file=sys.stderr)
        return 1
    src = Path(result.downloaded[0].local_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, args.out)
    report = TTSReport(
        schema="local_tts_open.report.v1",
        engine="f5",
        model_id=MODEL_IDS["f5"],
        text=args.text,
        reference_audio=str(args.ref_audio),
        reference_text=args.ref_text,
        voice=args.voice,
        seed=args.seed,
        speed=args.speed,
        samplerate=SAMPLE_RATE,
        samples=0,
        backend="comfy_f5tts",
        dry_run=False,
        out_path=str(args.out),
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    write_report(args.out, report, extra={"comfy_result": asdict(result)})
    print(f"[local_tts_f5] f5 comfy -> {args.out}")
    return 0


def run_kokoro_command(args: argparse.Namespace) -> int:
    cmd_template = os.environ.get("KOKORO_TTS_CMD")
    if not cmd_template:
        print("[local_tts_f5] KOKORO_TTS_CMD is not set; use --dry-run or set a local command template", file=sys.stderr)
        return 2
    cmd = cmd_template.format(
        text=args.text,
        out=str(args.out),
        voice=args.voice or "",
        seed=args.seed,
        speed=args.speed,
    )
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"[local_tts_f5] Kokoro command failed with exit {result.returncode}", file=sys.stderr)
        return result.returncode
    print(f"[local_tts_f5] kokoro command -> {args.out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", type=Path, default=VOICE_OUT / "tts_open.wav")
    ap.add_argument("--engine", choices=("f5", "kokoro"), default="f5")
    ap.add_argument("--ref-audio", type=Path, default=None)
    ap.add_argument("--ref-text", default=None)
    ap.add_argument("--voice", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    ap.add_argument("--run-model", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backend", choices=("comfy", "command"), default="comfy")
    ap.add_argument("--host", default="http://127.0.0.1:8188")
    ap.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    ap.add_argument("--output-node", default="3")
    args = ap.parse_args()

    if args.dry_run or args.device == "cpu" or not args.run_model:
        return dry_run(args)
    if args.device != "cuda":
        print("[local_tts_f5] --run-model requires --device cuda", file=sys.stderr)
        return 2
    if args.engine == "f5":
        return run_f5_comfy(args)
    return run_kokoro_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
