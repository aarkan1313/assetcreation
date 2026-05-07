"""Find the best loop point inside an audio buffer.

Two metrics are supported:

  v1 (legacy SSD): compare a small window at the START of the file to
  candidate windows through the file, pick the position whose squared-distance
  to the start window is minimal. Adequate for percussive / broadband content,
  ambiguous on monotonic tonal beds (every period of a sine wave looks
  identical → a click can still appear at the seam after crossfade).

  v2 (phase-aware, default since 2026-05-06): a *composite* fitness combining
  three measurements at each candidate seam.

      fit = w_xc * (1 - |xcorr|) + w_phase * phase_inc + w_env * env_diff

  where:
    - xcorr      : Pearson cross-correlation between the head window
                   (start of file) and the candidate window. 1.0 = same
                   waveform shape; -1.0 = inverted; 0 = unrelated. Robust to
                   amplitude differences (we normalize both windows first),
                   so it doesn't punish a slowly fading bed.
    - phase_inc  : Instantaneous-phase incoherence at the dominant FFT bin
                   measured in [0, 1]. We FFT both windows, find the largest
                   shared spectral peak, take `arg(X_head) - arg(X_cand)` mod
                   2π, fold to [0, π], and divide by π. 0 = phase-locked;
                   1 = anti-phase. This is the term that closes the
                   "monotonic-tonal-drone click" failure mode E2 §6 flagged.
    - env_diff   : Absolute difference in RMS amplitude between head and
                   candidate windows, in dB, divided by 20 dB so it sits in
                   roughly [0, 1]. Catches "shape matches but the bed faded
                   out at this candidate" cases.

  Default weights (1.0, 0.6, 0.2) emphasize waveform shape but force phase
  coherence to break ties. Tunable via env vars LOOPDET_W_XC / W_PHASE /
  W_ENV for A/B comparison.

  v2 also reports the *seam-RMS* of the looped output (raw waveform delta at
  the wrap-around point) and a *long-loop seam RMS* (3 loops back-to-back,
  measured at the boundary samples) so callers can audit how well the new
  metric did vs. the old SSD result. The CLI's `--metric ssd` flag forces
  the legacy behavior for A/B regression tests.

CLI:
  python loop_detect.py audio/music/forest.wav --out audio/music/forest_loop.wav
  python loop_detect.py audio/music/forest.wav --out forest_loop.wav --metric ssd
  python loop_detect.py audio/music/forest.wav --out forest_loop.wav \
        --w-xc 1.0 --w-phase 1.0 --w-env 0.0
"""
from __future__ import annotations

import argparse
import json
import os
import wave
from pathlib import Path

import numpy as np


SAMPLE_RATE = 44_100

# ----- v2 metric weights (override with env vars for tuning) -----
_W_XC = float(os.environ.get("LOOPDET_W_XC", "1.0"))
_W_PHASE = float(os.environ.get("LOOPDET_W_PHASE", "0.6"))
_W_ENV = float(os.environ.get("LOOPDET_W_ENV", "0.2"))


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        n = w.getnframes()
        raw = w.readframes(n)
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
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


def _ssd_score(head_norm: np.ndarray, head_energy: float,
               seg_norm: np.ndarray) -> float:
    return float(np.sum((head_norm - seg_norm) ** 2)) / head_energy


def _phase_score(head: np.ndarray, seg: np.ndarray) -> tuple[float, float, float]:
    """Phase-aware composite at one candidate seam.

    Returns (xcorr_term, phase_term, env_term) all in roughly [0, 1].

      xcorr_term = 1 - max(0, normalized_pearson_xcorr)
                   ranges from 0 (identical shape) to 2 (anti-phase) but is
                   clamped to [0, 1] in practice for sensible loops.
      phase_term = phase incoherence at the dominant shared FFT bin / pi
                   ranges from 0 (locked) to 1 (anti-phase).
      env_term   = abs RMS-dB delta / 20, soft-clipped to [0, 1].
    """
    h = head - head.mean()
    s = seg - seg.mean()
    h_n = float(np.linalg.norm(h)) + 1e-12
    s_n = float(np.linalg.norm(s)) + 1e-12
    pearson = float(np.dot(h, s) / (h_n * s_n))
    # Map pearson [-1, 1] -> xcorr_term [0, 1]: 1 = perfect, -1 = inverted.
    xcorr_term = max(0.0, min(1.0, 1.0 - pearson))

    # FFT both windows; find dominant bin shared between them; phase delta there.
    n = len(h)
    # Apply a mild Hann window so the bin search isn't biased by edge effects.
    w = np.hanning(n).astype(np.float32)
    H = np.fft.rfft(h * w)
    S = np.fft.rfft(s * w)
    mag_h = np.abs(H)
    mag_s = np.abs(S)
    # Drop DC + the lowest few bins (those are window-leakage); pick the bin
    # that has the largest sum-of-magnitudes across head + seg, weighted.
    if len(mag_h) > 4:
        weights = (mag_h + mag_s)
        weights[:2] = 0.0
        bin_idx = int(np.argmax(weights))
    else:
        bin_idx = 1 if len(mag_h) > 1 else 0
    if bin_idx == 0 or mag_h[bin_idx] < 1e-6 or mag_s[bin_idx] < 1e-6:
        # No clear tonal content -> phase is meaningless; report 0 (don't punish).
        phase_term = 0.0
    else:
        ph = float(np.angle(H[bin_idx]) - np.angle(S[bin_idx]))
        # Fold to [0, pi]
        ph = abs((ph + np.pi) % (2 * np.pi) - np.pi)
        phase_term = float(min(1.0, ph / np.pi))

    # RMS envelope delta in dB
    rms_h = float(np.sqrt(np.mean(h.astype(np.float64) ** 2))) + 1e-9
    rms_s = float(np.sqrt(np.mean(s.astype(np.float64) ** 2))) + 1e-9
    db_delta = abs(20.0 * np.log10(rms_h / rms_s))
    env_term = float(min(1.0, db_delta / 20.0))

    return xcorr_term, phase_term, env_term


def find_loop_end(samples: np.ndarray, sr: int,
                  win_ms: float = 50.0,
                  search_start_pct: float = 0.5,
                  search_end_pct: float = 0.99,
                  step_ms: float = 5.0,
                  metric: str = "phase",
                  weights: tuple[float, float, float] | None = None,
                  ) -> tuple[int, float]:
    """Return (loop_end_sample_index, fitness). 0 fitness = perfect match.

    metric:
      "phase"  : v2 composite = w_xc*(1-pearson) + w_phase*phase_term + w_env*env_term
                 (default; closes the monotonic-tonal-drone click hole)
      "ssd"    : v1 sum-of-squared-differences (legacy; kept for A/B tests)
    """
    win = max(int(win_ms * sr / 1000), 16)
    step = max(int(step_ms * sr / 1000), 1)
    if len(samples) < 2 * win:
        return len(samples), float("inf")
    head = samples[:win]
    n = len(samples)
    s_lo = int(n * search_start_pct)
    s_hi = int(n * search_end_pct) - win
    if s_hi <= s_lo:
        return len(samples), float("inf")

    head_norm = head - head.mean()
    head_energy = float(np.sum(head_norm ** 2)) + 1e-9

    w_xc, w_phase, w_env = weights if weights is not None else (_W_XC, _W_PHASE, _W_ENV)

    best_idx = s_lo
    best_fit = float("inf")
    for i in range(s_lo, s_hi, step):
        seg = samples[i:i + win]
        if metric == "ssd":
            seg_norm = seg - seg.mean()
            fit = _ssd_score(head_norm, head_energy, seg_norm)
        else:
            xc, ph, en = _phase_score(head, seg)
            fit = w_xc * xc + w_phase * ph + w_env * en
        if fit < best_fit:
            best_fit = fit
            best_idx = i
    return best_idx, best_fit


def make_seamless_loop(samples: np.ndarray, loop_end: int,
                       crossfade_ms: float = 30.0,
                       sr: int = SAMPLE_RATE) -> np.ndarray:
    """Trim to [0, loop_end], crossfade the last `crossfade_ms` with the start."""
    cf = max(int(crossfade_ms * sr / 1000), 16)
    cf = min(cf, loop_end // 2)
    body = samples[:loop_end].copy()
    if cf <= 0:
        return body
    fade_out = np.linspace(1, 0, cf, dtype=np.float32)
    fade_in = np.linspace(0, 1, cf, dtype=np.float32)
    body[-cf:] = body[-cf:] * fade_out + samples[:cf] * fade_in
    return body


def loop_seam_rms(samples: np.ndarray, win: int = 256) -> float:
    """RMS difference between the very-end and the very-start (after looping).
    Lower = more seamless. Used as a quality metric for the report."""
    if len(samples) < 2 * win:
        return 0.0
    head = samples[:win]
    tail = samples[-win:]
    return float(np.sqrt(np.mean((head - tail) ** 2)))


def long_loop_seam_rms(samples: np.ndarray, repeats: int = 3,
                       win: int = 256) -> float:
    """Concatenate `repeats` copies of the loop and measure the worst RMS
    transient at the wrap-around seams.

    A successful seam should not produce a periodic click as the loop replays.
    This is the "did the v2 metric actually pay off" audit number — measure
    a window centered on each seam and take the maximum local energy spike
    relative to the loop's median local energy.
    """
    if len(samples) < 2 * win or repeats < 2:
        return loop_seam_rms(samples, win=win)
    long = np.tile(samples, repeats)
    n = len(samples)
    half = win // 2
    seam_energies = []
    for k in range(1, repeats):
        center = k * n
        a = max(0, center - half)
        b = min(len(long), center + half)
        seg = long[a:b]
        seam_energies.append(float(np.sqrt(np.mean(seg.astype(np.float64) ** 2))))
    # Compare each seam's local RMS to the global median in equivalent windows
    # picked away from the seams. Higher ratio = seam stands out = bad.
    samples_f64 = samples.astype(np.float64)
    sq = samples_f64 ** 2
    if len(sq) < win:
        return float(np.max(seam_energies))
    csum = np.concatenate(([0.0], np.cumsum(sq)))
    rms_track = np.sqrt(np.maximum((csum[win:] - csum[:-win]) / win, 0.0))
    median_rms = float(np.median(rms_track)) + 1e-9
    return float(max(0.0, max(seam_energies) - median_rms))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--win-ms", type=float, default=50.0)
    ap.add_argument("--crossfade-ms", type=float, default=30.0)
    ap.add_argument("--search-start-pct", type=float, default=0.5)
    ap.add_argument("--search-end-pct", type=float, default=0.99)
    ap.add_argument("--metric", choices=("phase", "ssd"), default="phase",
                    help="phase = v2 composite (xcorr + phase + env). ssd = v1 legacy.")
    ap.add_argument("--w-xc", type=float, default=_W_XC)
    ap.add_argument("--w-phase", type=float, default=_W_PHASE)
    ap.add_argument("--w-env", type=float, default=_W_ENV)
    ap.add_argument("--report", type=Path, default=None)
    args = ap.parse_args()

    samples, sr = read_wav(args.input)
    idx, fitness = find_loop_end(
        samples, sr, args.win_ms,
        args.search_start_pct, args.search_end_pct,
        metric=args.metric,
        weights=(args.w_xc, args.w_phase, args.w_env),
    )
    looped = make_seamless_loop(samples, idx, args.crossfade_ms, sr)
    seam = loop_seam_rms(looped)
    long_seam = long_loop_seam_rms(looped)
    write_wav(args.out, looped, sr)
    print(f"[loop_detect] metric={args.metric} loop_end={idx}/{len(samples)} "
          f"({idx*1000//sr} ms) fitness={fitness:.4f} seam_rms={seam:.4f} "
          f"long_seam_rms={long_seam:.4f} -> {args.out}")
    if args.report:
        args.report.write_text(json.dumps({
            "input": str(args.input),
            "output": str(args.out),
            "metric": args.metric,
            "weights": {"xc": args.w_xc, "phase": args.w_phase, "env": args.w_env},
            "loop_end_samples": idx,
            "loop_end_ms": int(idx * 1000 / sr),
            "fitness": fitness,
            "seam_rms": seam,
            "long_seam_rms": long_seam,
            "samplerate": sr,
            "duration_in_s": len(samples) / sr,
            "duration_loop_s": len(looped) / sr,
        }, indent=2))


if __name__ == "__main__":
    main()
