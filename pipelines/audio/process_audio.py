"""Audio processing spine - pure-Python (no ffmpeg, no pyloudnorm).

What we do per E_audio's recommended chain:
  1. trim leading/trailing silence (RMS-window threshold)
  2. fade in/out (5-30 ms, configurable)
  3. RMS target normalization (proxy for LUFS - close enough for SFX)
  4. true-peak limiter (sample-domain peak under -1 dBTP)
  5. write WAV (mono 16-bit PCM, optional samplerate convert)

We DO NOT pull in librosa or pyloudnorm because they are heavyweight installs.
For full EBU R128 compliance we recommend `pip install pyloudnorm` later and
swap the `rms_lufs_proxy` for the real BS.1770 weighting.

Loudness targets (from research/E_audio.md):
  ui            : -22 LUFS, true-peak <= -1 dBTP
  combat/spell  : -16 LUFS, true-peak <= -1 dBTP
  voice         : -18 LUFS
  ambience      : -26 LUFS
  music         : -20 LUFS

CLI:
  python process_audio.py audio/sfx/raw.wav --out audio/sfx/processed.wav --target-rms-db -16
"""
from __future__ import annotations

import argparse
import json
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


SAMPLE_RATE = 44_100


@dataclass
class ProcessReport:
    in_path: str
    out_path: str
    samples_in: int
    samples_out: int
    duration_in: float
    duration_out: float
    rms_db_in: float
    rms_db_out: float
    peak_db_in: float
    peak_db_out: float
    target_rms_db: float
    fade_ms: int
    trim_ms_head: int
    trim_ms_tail: int


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read mono float32 [-1,1]. Stereo files are downmixed."""
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        n = w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        # could be PCM32 or float32 - assume PCM32
        arr = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sw == 1:
        arr = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    else:
        raise ValueError(f"unsupported sample width {sw}")
    if ch == 2:
        arr = arr.reshape(-1, 2).mean(axis=1)
    return arr.astype(np.float32), sr


def write_wav(path: Path, samples: np.ndarray, sr: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = np.clip(samples, -1.0, 1.0)
    pcm16 = (samples * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16.tobytes())


def db_to_amp(db: float) -> float:
    return 10 ** (db / 20)


def amp_to_db(amp: float) -> float:
    return 20 * np.log10(max(amp, 1e-10))


def _rms_dbfs(samples: np.ndarray) -> float:
    rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
    return amp_to_db(rms)


def rms_lufs_proxy(samples: np.ndarray, sr: int = SAMPLE_RATE) -> float:
    """Loudness in LUFS (BS.1770) when pyloudnorm is available, RMS-dBFS proxy
    otherwise.

    pyloudnorm's `Meter.integrated_loudness()` requires >=400 ms of audio and
    is the EBU R128 / BS.1770-4 weighted gated measurement. For shorter
    one-shots (UI clicks, footsteps) we fall back to the RMS proxy because
    the true integrated LUFS gate would silence them.

    The function name is preserved for backwards-compat with build_demo.py
    and the audio_qa report keys; the meaning is now "true LUFS where
    possible, RMS-dBFS otherwise" and the report records which was used via
    the audio_qa.sanity() output.
    """
    if len(samples) < int(0.4 * sr):
        return _rms_dbfs(samples)
    try:
        import pyloudnorm  # type: ignore
    except ImportError:
        return _rms_dbfs(samples)
    try:
        meter = pyloudnorm.Meter(sr)
        # pyloudnorm wants float64 in [-1,1]; mono is shape (N,)
        loudness = float(meter.integrated_loudness(samples.astype(np.float64)))
        # `integrated_loudness` returns -inf if the signal is below the gate;
        # in that case fall back to RMS-dBFS for a sensible normalization
        # target (e.g. silent tails would otherwise be amplified to clipping).
        if not np.isfinite(loudness):
            return _rms_dbfs(samples)
        return loudness
    except Exception:
        return _rms_dbfs(samples)


def peak_db(samples: np.ndarray) -> float:
    return amp_to_db(np.max(np.abs(samples)) if len(samples) > 0 else 0.0)


def trim_silence(samples: np.ndarray, sr: int = SAMPLE_RATE,
                 threshold_db: float = -50.0,
                 win_ms: float = 5.0) -> tuple[np.ndarray, int, int]:
    """RMS-window-based silence trim. Returns (trimmed, head_samples, tail_samples)."""
    if len(samples) == 0:
        return samples, 0, 0
    win = max(int(win_ms * sr / 1000), 1)
    threshold = db_to_amp(threshold_db)
    # rolling RMS via square + cumsum
    sq = samples.astype(np.float64) ** 2
    csum = np.concatenate(([0.0], np.cumsum(sq)))
    rms = np.sqrt((csum[win:] - csum[:-win]) / win)
    above = rms > threshold
    if not above.any():
        return samples.copy(), 0, 0
    first = np.argmax(above)
    last = len(above) - 1 - np.argmax(above[::-1])
    head = first
    tail = (len(samples) - (last + win))
    out = samples[head: last + win]
    return out, head, max(tail, 0)


def fade(samples: np.ndarray, sr: int = SAMPLE_RATE,
         in_ms: float = 5.0, out_ms: float = 10.0) -> np.ndarray:
    n = len(samples)
    a = max(int(in_ms * sr / 1000), 1)
    b = max(int(out_ms * sr / 1000), 1)
    a = min(a, n // 2)
    b = min(b, n // 2)
    out = samples.copy()
    out[:a] *= np.linspace(0, 1, a, dtype=np.float32)
    out[-b:] *= np.linspace(1, 0, b, dtype=np.float32)
    return out


def normalize_rms(samples: np.ndarray, target_db: float = -16.0,
                  peak_ceiling_db: float = -1.0,
                  sr: int = SAMPLE_RATE) -> np.ndarray:
    cur = rms_lufs_proxy(samples, sr)
    if not np.isfinite(cur):
        return samples
    gain_db = target_db - cur
    out = samples * db_to_amp(gain_db)
    # apply a hard true-peak ceiling to avoid clipping
    p = np.max(np.abs(out)) if len(out) else 0.0
    ceil = db_to_amp(peak_ceiling_db)
    if p > ceil:
        out = out * (ceil / p)
    return out.astype(np.float32)


def process(samples: np.ndarray, sr: int = SAMPLE_RATE,
            target_rms_db: float = -16.0,
            peak_ceiling_db: float = -1.0,
            fade_in_ms: float = 5.0, fade_out_ms: float = 12.0,
            silence_threshold_db: float = -50.0,
            trim: bool = True) -> tuple[np.ndarray, ProcessReport]:
    rms_in = rms_lufs_proxy(samples, sr)
    peak_in = peak_db(samples)

    trimmed, head, tail = (samples, 0, 0)
    if trim:
        trimmed, head, tail = trim_silence(samples, sr, silence_threshold_db)
    if len(trimmed) == 0:
        # all-silence input - bail with original
        trimmed = samples
        head = tail = 0
    faded = fade(trimmed, sr, fade_in_ms, fade_out_ms)
    out = normalize_rms(faded, target_rms_db, peak_ceiling_db, sr=sr)

    report = ProcessReport(
        in_path="",  # caller fills these
        out_path="",
        samples_in=len(samples),
        samples_out=len(out),
        duration_in=len(samples) / sr,
        duration_out=len(out) / sr,
        rms_db_in=float(rms_in),
        rms_db_out=float(rms_lufs_proxy(out, sr)),
        peak_db_in=float(peak_in),
        peak_db_out=float(peak_db(out)),
        target_rms_db=target_rms_db,
        fade_ms=int(fade_in_ms + fade_out_ms),
        trim_ms_head=int(head * 1000 / sr),
        trim_ms_tail=int(tail * 1000 / sr),
    )
    return out, report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--target-rms-db", type=float, default=-16.0,
                    help="Target loudness in dBFS (RMS proxy for LUFS). "
                         "Defaults: ui=-22, combat=-16, voice=-18, ambience=-26.")
    ap.add_argument("--peak-ceiling-db", type=float, default=-1.0)
    ap.add_argument("--fade-in-ms", type=float, default=5.0)
    ap.add_argument("--fade-out-ms", type=float, default=12.0)
    ap.add_argument("--no-trim", action="store_true")
    ap.add_argument("--report", type=Path, default=None,
                    help="Optional path to write a process report JSON.")
    args = ap.parse_args()

    samples, sr = read_wav(args.input)
    out, rep = process(
        samples, sr,
        target_rms_db=args.target_rms_db,
        peak_ceiling_db=args.peak_ceiling_db,
        fade_in_ms=args.fade_in_ms,
        fade_out_ms=args.fade_out_ms,
        trim=not args.no_trim,
    )
    rep.in_path = str(args.input)
    rep.out_path = str(args.out)
    write_wav(args.out, out, sr)
    print(f"[process_audio] {args.input.name} -> {args.out.name}: "
          f"RMS {rep.rms_db_in:.1f} -> {rep.rms_db_out:.1f} dBFS, "
          f"peak {rep.peak_db_in:.1f} -> {rep.peak_db_out:.1f} dBFS, "
          f"trim {rep.trim_ms_head}+{rep.trim_ms_tail} ms")
    if args.report:
        args.report.write_text(json.dumps({
            **rep.__dict__,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2))


if __name__ == "__main__":
    main()
