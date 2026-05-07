"""Stable Audio Open local backend (Small for SFX, 1.0 for ambience).

Per `research/E2_audio_local_ambience.md`. Mirrors `eleven_sfx.py`'s shape:
`generate(prompt, duration, ...) -> (samples_float32_mono, samplerate)` plus a
CLI. The model is loaded lazily on first call and cached module-global so
batch runs in `biome_ambience.py` only pay the load cost once.

Two checkpoints:
  - `--model small` -> stabilityai/stable-audio-open-small (341M, <=11s, ~2 GB VRAM)
  - `--model large` -> stabilityai/stable-audio-open-1.0 (1.21B, <=47s, ~5 GB VRAM)

Both run on cu128 / sm_120 (Blackwell) under bf16 via the diffusers
`StableAudioPipeline`. The `stable-audio-tools` reference repo pins
`torch<2.4` — we explicitly DO NOT use it. Diffusers is the cu128-clean path.

CPU is unsupported. Stable Audio Open on CPU is ~50x real-time slower; the
adapter raises `RuntimeError` before attempting it. To run end-to-end
plumbing without a GPU (build mode, dry-run plumbing), pass `--dry-run`: the
adapter then writes a 1-second silent placeholder WAV so downstream stages
(process_audio, audio_qa, exporter) can be exercised. The placeholder cue
records `dry_run=true` for provenance and the wrap-up handoff.

License: Stability AI Community License (free <$1M ARR, attribution
recommended). The model HF repos are gated; accept the license on the model
page once before first run.

CLI:
  # Dry run (no GPU, writes 1s silence + cue with dry_run=true)
  python local_audio_open.py --prompt "deep magma rumble" --duration 30 \
        --model large --out audio/ambience/lava/bed_drone.wav --dry-run

  # Real run (requires CUDA, gated HF login, accepted license)
  python local_audio_open.py --prompt "deep magma rumble, no music" \
        --negative-prompt "music, melody, vocals, rhythm" \
        --duration 30 --steps 100 --seed 42 \
        --model large --out audio/ambience/lava/bed_drone.wav

Env vars:
  HF_HUB_OFFLINE=1            -> only use cached models (fail otherwise)
  STABLE_AUDIO_OPEN_CACHE     -> override default ~/.cache/huggingface

Module API mirrors eleven_sfx.py:
  generate(prompt, duration, *, model="small"|"large", steps=100,
           seed=None, negative_prompt=None) -> (np.ndarray, int)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import numpy as np


SAMPLE_RATE = 44_100  # Stable Audio Open native output rate

MODEL_IDS = {
    "small": "stabilityai/stable-audio-open-small",
    "large": "stabilityai/stable-audio-open-1.0",
}

# diffusers pipeline cache. Keys are model names ("small"/"large").
_PIPE_CACHE: dict[str, object] = {}


@dataclass
class GenerateReport:
    prompt: str
    negative_prompt: Optional[str]
    model: str
    model_id: str
    duration_s: float
    steps: int
    seed: Optional[int]
    samplerate: int
    samples: int
    backend: str
    wall_seconds: float
    dry_run: bool


def _load_pipe(model: str):
    """Lazy-load the diffusers StableAudioPipeline. Caches per model.

    Raises RuntimeError if torch/diffusers/CUDA aren't available, with a
    message pointing at the install steps.
    """
    if model in _PIPE_CACHE:
        return _PIPE_CACHE[model]

    try:
        import torch  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            f"local_audio_open: torch not installed. "
            f"Install per E2: pip install --index-url "
            f"https://download.pytorch.org/whl/cu128 torch==2.7.0 torchaudio==2.7.0  "
            f"({e})"
        )

    if not torch.cuda.is_available():
        raise RuntimeError(
            "local_audio_open: CUDA not available. Stable Audio Open on CPU "
            "is too slow to be useful (~50x slower than GPU). Use --dry-run "
            "for build-time plumbing or run on a CUDA host."
        )

    try:
        from diffusers import StableAudioPipeline  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            f"local_audio_open: diffusers not installed. "
            f"pip install diffusers==0.32.0 transformers==4.46.0 accelerate==1.1.0 "
            f"safetensors soundfile einops  ({e})"
        )

    if model not in MODEL_IDS:
        raise ValueError(f"unknown model {model!r}; expected one of {list(MODEL_IDS)}")

    model_id = MODEL_IDS[model]

    # Prefer a fully-downloaded local copy over the gated HF API path.
    # Per STABLE_AUDIO_SETUP.md, the download lands at
    # ComfyUI_HY3D/models/diffusers/<repo_name>/. If that tree exists, pass it
    # to from_pretrained so we don't re-auth against the gated repo at runtime.
    # Falls back to the HF repo id (which then requires HF_TOKEN + accepted
    # license) if the local copy is missing.
    local_dir_name = model_id.split("/", 1)[-1]  # "stable-audio-open-1.0"
    local_path = Path(r"D:\assets\animators\ComfyUI_HY3D\models\diffusers") / local_dir_name
    load_target = str(local_path) if (local_path / "model_index.json").exists() else model_id
    print(f"[local_audio_open] loading {load_target} (bf16, cuda)")

    # bf16 is critical on sm_120: fp32 would consume ~17 GB VRAM for the 1.21B
    # checkpoint. Blackwell has native bf16 matmul.
    pipe = StableAudioPipeline.from_pretrained(load_target, torch_dtype=torch.bfloat16)
    pipe = pipe.to("cuda")
    _PIPE_CACHE[model] = pipe
    return pipe


def generate(prompt: str,
             duration: float,
             *,
             model: str = "small",
             steps: int = 100,
             seed: Optional[int] = None,
             negative_prompt: Optional[str] = None,
             num_waveforms: int = 1) -> tuple[np.ndarray, int]:
    """Generate audio from text. Returns (samples_float32_mono, samplerate).

    The diffusers StableAudioPipeline returns shape (channels, samples)
    in fp32 within [-1, 1] at 44.1 kHz. Stereo is downmixed to mono here
    so the rest of the pipeline (process_audio, loop_detect, exporter)
    keeps its uniform-mono assumption.
    """
    if duration <= 0:
        raise ValueError(f"duration must be > 0, got {duration}")
    if model == "small" and duration > 11.5:
        raise ValueError(
            f"small model maxes at ~11s, requested {duration}. Use model='large'."
        )
    if model == "large" and duration > 47.5:
        raise ValueError(
            f"large model maxes at ~47s, requested {duration}."
        )

    pipe = _load_pipe(model)

    import torch  # type: ignore
    gen = None
    if seed is not None:
        gen = torch.Generator(device="cuda").manual_seed(int(seed))

    out = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=int(steps),
        audio_end_in_s=float(duration),
        num_waveforms_per_prompt=int(num_waveforms),
        generator=gen,
    )
    audio = out.audios[0]  # tensor shape (channels, samples)

    # Downmix to mono float32 in [-1, 1]
    arr = audio.float().cpu().numpy()
    if arr.ndim == 2:
        arr = arr.mean(axis=0)
    arr = np.clip(arr.astype(np.float32), -1.0, 1.0)
    return arr, SAMPLE_RATE


def silent_placeholder(duration: float) -> np.ndarray:
    """Return a duration-correct silent buffer for dry-run plumbing.

    Adds a -60 dBFS pink-noise floor so downstream tools (waveform PNG, RMS
    measurement) don't divide-by-zero or render an empty image. The floor is
    deterministic per duration so QA tests are reproducible.
    """
    n = int(round(duration * SAMPLE_RATE))
    rng = np.random.default_rng(seed=int(duration * 10000) & 0xFFFFFFFF)
    floor = rng.normal(0, 1e-3, n).astype(np.float32)  # -60 dBFS-ish
    return floor


def write_wav(path: Path, samples: np.ndarray, sr: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = np.clip(samples, -1.0, 1.0)
    pcm16 = (samples * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16.tobytes())


def _write_cue(out_path: Path, report: GenerateReport) -> Path:
    """Write a `<stem>.cue.json` next to the WAV with full provenance."""
    cue_path = out_path.with_suffix(".cue.json")
    cue_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(report)
    payload["out_path"] = str(out_path)
    cue_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return cue_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--duration", type=float, required=True,
                    help="Seconds. small <=11, large <=47.")
    ap.add_argument("--model", choices=list(MODEL_IDS), default="small")
    ap.add_argument("--steps", type=int, default=100,
                    help="Inference steps; 50 fast / 100 default / 150 quality.")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--negative-prompt", default=None,
                    help="Critical for ambience: 'music, melody, vocals, rhythm'.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Skip GPU; write a duration-correct silent placeholder. "
                         "Used to exercise downstream pipeline plumbing without a GPU.")
    args = ap.parse_args()

    started = time.monotonic()

    if args.dry_run:
        samples = silent_placeholder(args.duration)
        backend = "dry_run_silent"
        write_wav(args.out, samples)
        wall = time.monotonic() - started
        report = GenerateReport(
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            model=args.model,
            model_id=MODEL_IDS[args.model],
            duration_s=float(args.duration),
            steps=int(args.steps),
            seed=args.seed,
            samplerate=SAMPLE_RATE,
            samples=int(len(samples)),
            backend=backend,
            wall_seconds=wall,
            dry_run=True,
        )
        _write_cue(args.out, report)
        print(f"[local_audio_open] DRY RUN ({args.model}): "
              f"{args.duration:.1f}s placeholder -> {args.out} "
              f"(wall {wall:.2f}s)")
        return 0

    try:
        samples, sr = generate(
            args.prompt,
            args.duration,
            model=args.model,
            steps=args.steps,
            seed=args.seed,
            negative_prompt=args.negative_prompt,
        )
    except RuntimeError as e:
        print(f"[local_audio_open] FAILED: {e}", file=sys.stderr)
        print("[local_audio_open] Use --dry-run to exercise plumbing without GPU.",
              file=sys.stderr)
        return 1

    write_wav(args.out, samples, sr)
    wall = time.monotonic() - started
    report = GenerateReport(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        model=args.model,
        model_id=MODEL_IDS[args.model],
        duration_s=float(args.duration),
        steps=int(args.steps),
        seed=args.seed,
        samplerate=int(sr),
        samples=int(len(samples)),
        backend="stable_audio_open",
        wall_seconds=wall,
        dry_run=False,
    )
    _write_cue(args.out, report)
    print(f"[local_audio_open] {args.model} {args.duration:.1f}s -> {args.out} "
          f"({len(samples) / sr:.2f}s @ {sr} Hz, wall {wall:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
