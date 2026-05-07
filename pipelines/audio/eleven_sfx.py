"""ElevenLabs Sound Effects API adapter.

Gated on `ELEVENLABS_API_KEY` env var. Falls back with a clear message if the
key is missing (we *don't* fall back silently to synth_sfx; the caller decides).

Endpoint: POST https://api.elevenlabs.io/v1/sound-generation
Docs: https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert

Returns binary audio (mp3 by default; we also support requesting WAV via
output_format=pcm_44100). We always convert to mono float32 [-1,1] and write a
WAV so the rest of the pipeline can work on a uniform format.

CLI:
  python eleven_sfx.py --prompt "short magical fireball cast, dry ignition" \
        --duration 0.8 --out audio/sfx/fireball_eleven.wav
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
import wave
from pathlib import Path

import numpy as np

DEFAULT_ENDPOINT = "https://api.elevenlabs.io/v1/sound-generation"
DEFAULT_OUTPUT_FORMAT = "pcm_44100"  # raw 16-bit signed little-endian @ 44.1 kHz


def _has_key() -> tuple[bool, str | None]:
    if not os.environ.get("ELEVENLABS_API_KEY"):
        return False, "ELEVENLABS_API_KEY not set"
    return True, None


def _pcm16_to_float32(raw: bytes) -> np.ndarray:
    arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return arr


def generate(prompt: str, duration_seconds: float | None = None,
             prompt_influence: float = 0.3, loop: bool = False,
             output_format: str = DEFAULT_OUTPUT_FORMAT,
             endpoint: str = DEFAULT_ENDPOINT,
             timeout_s: float = 60.0) -> tuple[np.ndarray, int]:
    """Call ElevenLabs SFX. Returns (samples_float32_mono, samplerate).

    Raises RuntimeError if no key, or any other error fetching.
    """
    ok, reason = _has_key()
    if not ok:
        raise RuntimeError(f"eleven_sfx: {reason}")

    import requests  # available
    payload: dict = {
        "text": prompt,
        "prompt_influence": prompt_influence,
        "output_format": output_format,
    }
    if duration_seconds is not None:
        payload["duration_seconds"] = float(duration_seconds)
    if loop:
        payload["loop"] = True
    headers = {
        "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
        "accept": "*/*",
        "Content-Type": "application/json",
    }
    resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout_s)
    if resp.status_code != 200:
        raise RuntimeError(f"eleven_sfx: HTTP {resp.status_code}: {resp.text[:300]}")
    raw = resp.content
    if output_format.startswith("pcm_"):
        sr = int(output_format.split("_")[1])
        return _pcm16_to_float32(raw), sr
    if output_format.startswith("mp3_") or output_format == "mp3":
        # decode mp3 - we can't without ffmpeg or pydub. Suggest pcm_44100.
        raise RuntimeError(
            "eleven_sfx: mp3 decoding requires ffmpeg/pydub. "
            "Pass --output-format pcm_44100 instead."
        )
    raise RuntimeError(f"eleven_sfx: unknown output_format {output_format!r}")


def write_wav(path: Path, samples: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = np.clip(samples, -1.0, 1.0)
    pcm16 = (samples * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16.tobytes())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--duration", type=float, default=None,
                    help="seconds (1-22 per ElevenLabs API). Omit to let API pick.")
    ap.add_argument("--prompt-influence", type=float, default=0.3,
                    help="0.0 = creative, 1.0 = literal. ElevenLabs default 0.3.")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--output-format", default=DEFAULT_OUTPUT_FORMAT)
    args = ap.parse_args()

    ok, reason = _has_key()
    if not ok:
        print(f"[eleven_sfx] SKIPPED: {reason}", file=sys.stderr)
        print("[eleven_sfx] Set ELEVENLABS_API_KEY in user env to enable.",
              file=sys.stderr)
        return 2

    try:
        samples, sr = generate(
            args.prompt, args.duration, args.prompt_influence,
            args.loop, args.output_format,
        )
    except RuntimeError as e:
        print(f"[eleven_sfx] FAILED: {e}", file=sys.stderr)
        return 1
    write_wav(args.out, samples, sr)
    print(f"[eleven_sfx] {args.prompt!r} -> {args.out} "
          f"({len(samples) / sr:.2f}s @ {sr} Hz)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
