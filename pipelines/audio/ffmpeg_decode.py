"""Optional ffmpeg-backed audio decode.

Pure-stdlib helper around `ffmpeg` for decoding compressed audio formats
(MP3, OGG, FLAC, M4A, WebM, Opus) to a numpy float32 mono buffer at a target
sample rate. The whole pipeline still runs WAV-only by default; this module
just unblocks two specific cases:

  1. Freesound MP3 previews  — `cc0_ingest.py` falls back to `soundfile` for
     OGG, but `soundfile` cannot decode MP3 unless built with libsndfile +
     libmpg123. ffmpeg is the universal escape hatch.
  2. Stable Audio 1.0 max output is 47 s — when an ambience bed wants more,
     concatenating SAO output then encoding to OGG (smaller, smaller file
     size on disk for ~no quality hit) requires ffmpeg.

Discovery rules:

  - `which`/`where` lookup of `ffmpeg` (PATH-resolved). No env-var override
    on first cut; if needed later, expose `AUDIO_FFMPEG_BIN`.
  - `is_available()` returns False without raising if ffmpeg is missing.
  - All decode entry points raise `FfmpegNotFound` if ffmpeg is missing AND
    `strict=True`; otherwise they return None.

CLI:
  python ffmpeg_decode.py path/to/preview.mp3 --out preview.wav
  python ffmpeg_decode.py --probe                           # is ffmpeg there?

Module API:
  ffmpeg_decode.is_available() -> bool
  ffmpeg_decode.decode(path, sr=44100) -> (samples, sr)     # raises if missing
  ffmpeg_decode.decode_or_none(path, sr=44100)              # never raises

This file imports nothing heavy (subprocess + numpy). Safe to import even
when ffmpeg is absent.
"""
from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

DEFAULT_SR = 44_100


class FfmpegNotFound(RuntimeError):
    pass


def _ffmpeg_bin() -> str | None:
    """Resolve the `ffmpeg` executable. Honors AUDIO_FFMPEG_BIN if set."""
    override = os.environ.get("AUDIO_FFMPEG_BIN")
    if override and Path(override).exists():
        return override
    return shutil.which("ffmpeg")


def is_available() -> bool:
    return _ffmpeg_bin() is not None


def probe() -> dict:
    """Return {'available': bool, 'binary': path-or-None, 'version': str-or-None}."""
    binary = _ffmpeg_bin()
    if not binary:
        return {"available": False, "binary": None, "version": None}
    try:
        out = subprocess.run(
            [binary, "-version"], capture_output=True, text=True, timeout=10,
        )
        first = (out.stdout or out.stderr or "").splitlines()[0] if (out.stdout or out.stderr) else ""
        return {"available": True, "binary": binary, "version": first.strip()}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"available": False, "binary": binary, "version": f"ERROR: {e!r}"}


def decode(src: Path, *, sr: int = DEFAULT_SR,
           timeout_s: float = 60.0) -> tuple[np.ndarray, int]:
    """Decode any ffmpeg-supported audio file to mono float32 [-1, 1] at `sr`.

    Returns (samples, sr). Raises FfmpegNotFound if ffmpeg is missing.
    Raises RuntimeError on decode error.
    """
    binary = _ffmpeg_bin()
    if not binary:
        raise FfmpegNotFound(
            "ffmpeg not found in PATH. Install ffmpeg or set AUDIO_FFMPEG_BIN. "
            "On Windows: `winget install --id=Gyan.FFmpeg -e`. "
            "On WSL/Ubuntu: `sudo apt install ffmpeg`."
        )
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(src)

    # Decode to raw 16-bit signed little-endian PCM mono on stdout. We avoid
    # an intermediate file so we don't litter /tmp.
    cmd = [
        binary, "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ac", "1",
        "-ar", str(int(sr)),
        "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"ffmpeg decode timed out after {timeout_s}s: {src}") from e
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg decode failed for {src}: {err[:400]}")
    raw = proc.stdout
    if not raw:
        raise RuntimeError(f"ffmpeg decode produced no audio: {src}")
    arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return arr, int(sr)


def decode_or_none(src: Path, *, sr: int = DEFAULT_SR,
                   timeout_s: float = 60.0) -> tuple[np.ndarray, int] | None:
    """Same as `decode` but returns None instead of raising on missing ffmpeg.

    Other errors (corrupt file, unsupported codec) still raise.
    """
    if not is_available():
        return None
    return decode(src, sr=sr, timeout_s=timeout_s)


def encode_wav_from(src: Path, dst: Path, *, sr: int = DEFAULT_SR,
                    timeout_s: float = 60.0) -> Path:
    """Convenience: decode `src` then write a 16-bit PCM mono WAV at `dst`."""
    samples, sr_out = decode(src, sr=sr, timeout_s=timeout_s)
    dst.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr_out)
        w.writeframes(pcm.tobytes())
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, nargs="?")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--sr", type=int, default=DEFAULT_SR)
    ap.add_argument("--probe", action="store_true",
                    help="Only check whether ffmpeg is available and exit.")
    args = ap.parse_args()

    if args.probe:
        info = probe()
        print(f"available={info['available']} binary={info['binary']} "
              f"version={info['version']}")
        return 0 if info["available"] else 1

    if not args.input:
        print("usage: ffmpeg_decode.py INPUT --out OUT.wav  (or --probe)",
              file=sys.stderr)
        return 2
    if not is_available():
        print("[ffmpeg_decode] ffmpeg not found in PATH; install it first "
              "(winget install Gyan.FFmpeg / apt install ffmpeg).",
              file=sys.stderr)
        return 2

    out = args.out or args.input.with_suffix(".wav")
    encode_wav_from(args.input, out, sr=args.sr)
    print(f"[ffmpeg_decode] {args.input} -> {out} ({args.sr} Hz mono)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
