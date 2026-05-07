"""Pure-Python procedural SFX generator (jsfxr/Jfxr-style, no external deps).

This is the offline default backend - the equivalent of `derive_pbr_v2.py` for
audio: deterministic, fast, no keys, no GPU. Every preset returns mono float32
samples in [-1, 1] which then go through `process_audio.py` and the Godot
exporter.

Six presets, chosen to cover the asset categories game prototypes need first:
  - ui_click        ~80 ms    fast UI feedback
  - ui_confirm      ~250 ms   menu accept
  - ui_back         ~250 ms   menu cancel
  - sword_swing     ~400 ms   short whoosh
  - fireball_cast   ~700 ms   pitched-up airy whoosh + crackle
  - footstep        ~150 ms   noise burst with a low thump

Per E_audio's recommendation: use a procedural backend for "deterministic UI/
coin/laser/jump sounds" and reserve the AI backend for spell/Foley.

CLI:
  python synth_sfx.py ui_click --out audio/sfx/ui_click_a.wav --seed 0
  python synth_sfx.py fireball_cast --out audio/sfx/fireball_cast_a.wav --variants 3
"""
from __future__ import annotations

import argparse
import math
import struct
import wave
from pathlib import Path

import numpy as np


SAMPLE_RATE = 44_100


# -------- low-level synth ops --------


def sine(freq: float, length: float, sr: int = SAMPLE_RATE,
         phase: float = 0.0, fm: np.ndarray | None = None) -> np.ndarray:
    n = int(round(length * sr))
    t = np.arange(n) / sr
    if fm is None:
        return np.sin(2 * np.pi * freq * t + phase).astype(np.float32)
    # `fm` is an instantaneous freq curve, length must match
    if len(fm) != n:
        # resample by linear interpolation
        x_old = np.linspace(0, 1, len(fm))
        x_new = np.linspace(0, 1, n)
        fm = np.interp(x_new, x_old, fm)
    inst = freq + fm
    phase_arr = np.cumsum(inst) * (2 * np.pi / sr) + phase
    return np.sin(phase_arr).astype(np.float32)


def square(freq: float, length: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    n = int(round(length * sr))
    t = np.arange(n) / sr
    return np.sign(np.sin(2 * np.pi * freq * t)).astype(np.float32)


def saw(freq: float, length: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    n = int(round(length * sr))
    t = np.arange(n) / sr
    return (2 * (t * freq - np.floor(t * freq + 0.5))).astype(np.float32)


def noise(length: float, rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    n = int(round(length * sr))
    return rng.uniform(-1.0, 1.0, n).astype(np.float32)


def adsr(length: float, attack: float, decay: float, sustain: float,
         release: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    n = int(round(length * sr))
    a = max(int(attack * sr), 1)
    d = max(int(decay * sr), 1)
    r = max(int(release * sr), 1)
    s = max(n - a - d - r, 1)
    out = np.empty(n, dtype=np.float32)
    out[:a] = np.linspace(0, 1, a, endpoint=False)
    out[a:a + d] = np.linspace(1, sustain, d, endpoint=False)
    out[a + d:a + d + s] = sustain
    out[a + d + s:n] = np.linspace(sustain, 0, n - a - d - s, endpoint=False)
    return out


def expo_env(length: float, fall: float = 6.0, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Exponential decay envelope. Higher `fall` => faster decay."""
    n = int(round(length * sr))
    t = np.linspace(0, 1, n)
    return np.exp(-fall * t).astype(np.float32)


def lowpass_simple(x: np.ndarray, cutoff_hz: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    """1-pole IIR lowpass. Adequate for SFX shaping."""
    if cutoff_hz <= 0:
        return x.copy()
    rc = 1.0 / (2 * np.pi * cutoff_hz)
    dt = 1.0 / sr
    alpha = dt / (rc + dt)
    y = np.empty_like(x)
    y[0] = x[0] * alpha
    for i in range(1, len(x)):
        y[i] = y[i - 1] + alpha * (x[i] - y[i - 1])
    return y.astype(np.float32)


def highpass_simple(x: np.ndarray, cutoff_hz: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    if cutoff_hz <= 0:
        return x.copy()
    rc = 1.0 / (2 * np.pi * cutoff_hz)
    dt = 1.0 / sr
    alpha = rc / (rc + dt)
    y = np.empty_like(x)
    y[0] = x[0]
    for i in range(1, len(x)):
        y[i] = alpha * (y[i - 1] + x[i] - x[i - 1])
    return y.astype(np.float32)


# -------- preset definitions --------


def preset_ui_click(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.080
    base = 1200 + rng.uniform(-120, 120)
    pitch_drop = -np.linspace(0, 800, int(length * SAMPLE_RATE)).astype(np.float32)
    body = sine(base, length, fm=pitch_drop)
    env = expo_env(length, fall=18)
    out = body * env * 0.7
    # subtle click transient from filtered noise
    n = noise(0.005, rng) * np.linspace(1.0, 0.0, int(0.005 * SAMPLE_RATE))
    out[: len(n)] += n * 0.3
    return out


def preset_ui_confirm(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.260
    # Two-tone arpeggio (perfect-fifth-ish ascend)
    f1 = 600 + rng.uniform(-30, 30)
    f2 = f1 * 1.5
    chunk = int(length * 0.5 * SAMPLE_RATE)
    a = sine(f1, length * 0.5) * adsr(length * 0.5, 0.005, 0.05, 0.7, 0.07)
    b = sine(f2, length * 0.5) * adsr(length * 0.5, 0.005, 0.05, 0.7, 0.10)
    out = np.concatenate([a, b]).astype(np.float32) * 0.6
    return out


def preset_ui_back(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.260
    f1 = 600 + rng.uniform(-30, 30)
    f2 = f1 / 1.5
    a = sine(f1, length * 0.5) * adsr(length * 0.5, 0.005, 0.05, 0.7, 0.07)
    b = sine(f2, length * 0.5) * adsr(length * 0.5, 0.005, 0.05, 0.7, 0.10)
    return np.concatenate([a, b]).astype(np.float32) * 0.6


def preset_sword_swing(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.380
    n = int(length * SAMPLE_RATE)
    # filtered noise with a moving lowpass to evoke whoosh
    raw = noise(length, rng)
    # window the cutoff: 6kHz -> 1kHz across the duration
    # cheap approximation: blend two lowpasses
    lp_high = lowpass_simple(raw, 5500)
    lp_low = lowpass_simple(raw, 1200)
    blend = np.linspace(0, 1, n).astype(np.float32)
    body = lp_high * (1 - blend) + lp_low * blend
    env = adsr(length, 0.040, 0.06, 0.75, 0.28) * np.linspace(1, 0.55, n)
    return body * env * 0.85


def preset_fireball_cast(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.700
    n = int(length * SAMPLE_RATE)
    # rising air whoosh (filtered noise with low->high cutoff sweep)
    raw = noise(length, rng)
    # Apply sweeping LP via per-segment blend (approximation, but cheap)
    seg = 6
    parts = np.array_split(raw, seg)
    cut = np.linspace(800, 6500, seg)
    swept = np.concatenate([lowpass_simple(p, c) for p, c in zip(parts, cut)])
    swept = np.resize(swept, n).astype(np.float32)
    # crackle layer: small high-passed noise bursts
    crackle_raw = noise(length, rng) * 0.5
    crackle_raw = highpass_simple(crackle_raw, 2500)
    crackle = np.resize(crackle_raw, n)
    burst_env = (rng.random(n) > 0.985).astype(np.float32)
    burst_env = lowpass_simple(burst_env, 1500)
    burst_env = np.resize(burst_env, n)
    crackle = crackle * burst_env
    # rising sub-pitch
    sub_curve = np.linspace(60, 220, n).astype(np.float32) - 60
    sub = sine(60, length, fm=sub_curve) * 0.4
    sub = np.resize(sub, n)
    env = adsr(length, 0.05, 0.10, 0.8, 0.20)
    env = np.resize(env, n)
    out = (swept * 0.7 + crackle * 0.6 + sub * 0.4) * env * 0.85
    return out.astype(np.float32)


def preset_footstep(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.150
    n = int(length * SAMPLE_RATE)
    # low thump (sine 80Hz)
    thump = sine(80 + rng.uniform(-10, 10), length) * expo_env(length, fall=20)
    # mid noise body
    body = noise(length, rng)
    body = lowpass_simple(body, 2200)
    body = highpass_simple(body, 200)
    body *= expo_env(length, fall=10) * 0.6
    return (thump * 0.8 + body).astype(np.float32) * 0.7


PRESETS: dict[str, callable] = {
    "ui_click": preset_ui_click,
    "ui_confirm": preset_ui_confirm,
    "ui_back": preset_ui_back,
    "sword_swing": preset_sword_swing,
    "fireball_cast": preset_fireball_cast,
    "footstep": preset_footstep,
}


# -------- WAV writer --------


def write_wav(path: Path, samples: np.ndarray, sr: int = SAMPLE_RATE) -> None:
    """Write 16-bit PCM mono WAV. samples must be float32 in [-1,1]."""
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = np.clip(samples, -1.0, 1.0)
    pcm16 = (samples * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16.tobytes())


# -------- main --------


def synthesize(preset: str, seed: int = 0) -> np.ndarray:
    if preset not in PRESETS:
        raise KeyError(f"unknown preset {preset!r}; expected one of {list(PRESETS)}")
    return PRESETS[preset](seed=seed)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("preset", choices=sorted(PRESETS))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--variants", type=int, default=1,
                    help="Generate N variants by incrementing seed; "
                         "outputs <out_stem>_v0.wav .. _vN-1.wav")
    args = ap.parse_args()

    if args.variants == 1:
        samples = synthesize(args.preset, seed=args.seed)
        write_wav(args.out, samples)
        print(f"[synth_sfx] {args.preset} -> {args.out} ({len(samples)/SAMPLE_RATE:.3f}s)")
        return

    stem = args.out.with_suffix("")
    for i in range(args.variants):
        samples = synthesize(args.preset, seed=args.seed + i)
        path = Path(f"{stem}_v{i}.wav")
        write_wav(path, samples)
        print(f"[synth_sfx] {args.preset} v{i} -> {path}")


if __name__ == "__main__":
    main()
