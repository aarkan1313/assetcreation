"""Extended SFX catalogue (30+ entries) on top of synth_sfx.py primitives.

Per Phase 3 expansion-plan item: UI / spell-school x4 / footstep-surface x6 /
impact / ambience. Uses synth_sfx's noise/ADSR/envelope/filter primitives;
each preset is deterministic by seed.

Catalogue (33 entries authored here, plus the 6 in synth_sfx.py = 39 total):

  ui_      ui_select, ui_error, ui_open_menu, ui_close_menu, ui_pickup,
           ui_purchase, ui_quest_complete                          (7)

  spell_   spell_fire_cast, spell_fire_impact,
           spell_ice_cast, spell_ice_impact,
           spell_lightning_cast, spell_lightning_impact,
           spell_arcane_cast, spell_arcane_impact                  (8)

  step_    step_grass, step_stone, step_wood, step_metal,
           step_water, step_snow                                   (6)

  impact_  impact_flesh, impact_wood, impact_metal,
           impact_stone, impact_shield_block                       (5)

  amb_     amb_drone_lava, amb_drone_ice, amb_drone_mana,
           amb_drone_grass, amb_air_sweetener,
           amb_distant_thunder, amb_distant_boom                   (7)

The amb_* presets are stand-ins to be REPLACED by Stable Audio Open output via
biome_ambience.py once GPU is free; they let the catalogue ship today and they
let link_validator verify game_data references resolve to real sfx_ids.

CLI:
  python synth_sfx_extended.py --build           # author the full catalogue
                                                 # -> audio/sfx/<id>_v0.wav
                                                 # -> audio/sfx_manifest.json (merged)
                                                 # -> audio/godot/.../randomizer.tres

Each preset returns mono float32 samples in [-1, 1] @ 44.1 kHz.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from synth_sfx import (  # noqa: E402
    SAMPLE_RATE,
    sine, square, saw, noise, adsr, expo_env,
    lowpass_simple, highpass_simple,
    write_wav,
    PRESETS as BASE_PRESETS,
)
import process_audio  # noqa: E402
import audio_qa       # noqa: E402
import export_godot   # noqa: E402

ASSETS = Path(r"D:\assets")
SFX_DIR = ASSETS / "audio" / "sfx"


# ---------- helpers ----------


def mix(*signals_with_gain: tuple[np.ndarray, float]) -> np.ndarray:
    """Length-aware mix; longest sets the buffer length, shorter pad with zero."""
    n = max(len(s) for s, _ in signals_with_gain)
    out = np.zeros(n, dtype=np.float32)
    for s, g in signals_with_gain:
        if len(s) < n:
            s = np.concatenate([s, np.zeros(n - len(s), dtype=np.float32)])
        elif len(s) > n:
            s = s[:n]
        out += s.astype(np.float32) * float(g)
    return out


def sweep(start: float, end: float, length: float,
          sr: int = SAMPLE_RATE) -> np.ndarray:
    """Linear FM curve. Returns the deviation from `start`."""
    n = int(round(length * sr))
    return np.linspace(0, end - start, n).astype(np.float32)


# ---------- UI (7) ----------


def preset_ui_select(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.10
    f = 900 + rng.uniform(-30, 30)
    body = sine(f, length, fm=sweep(f, f * 1.6, length))
    env = expo_env(length, fall=14)
    return body * env * 0.65


def preset_ui_error(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.30
    f = 280 + rng.uniform(-15, 15)
    a = sine(f, length * 0.4) * adsr(length * 0.4, 0.005, 0.05, 0.7, 0.10)
    b = sine(f * 0.8, length * 0.6) * adsr(length * 0.6, 0.005, 0.10, 0.6, 0.20)
    out = np.concatenate([a, b]).astype(np.float32) * 0.6
    return out


def preset_ui_open_menu(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.22
    f = 700 + rng.uniform(-30, 30)
    body = sine(f, length, fm=sweep(f, f * 1.4, length))
    env = adsr(length, 0.005, 0.04, 0.7, 0.15)
    n = noise(0.012, rng) * np.linspace(1, 0, int(0.012 * SAMPLE_RATE))
    out = body * env * 0.55
    out[: len(n)] += n * 0.25
    return out


def preset_ui_close_menu(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.22
    f = 700 + rng.uniform(-30, 30)
    body = sine(f, length, fm=sweep(f, f * 0.6, length))
    env = adsr(length, 0.005, 0.04, 0.7, 0.15)
    return body * env * 0.55


def preset_ui_pickup(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.22
    f = 1200 + rng.uniform(-40, 40)
    a = sine(f, length * 0.45) * adsr(length * 0.45, 0.002, 0.05, 0.6, 0.10)
    b = sine(f * 1.5, length * 0.55) * adsr(length * 0.55, 0.002, 0.05, 0.7, 0.15)
    return np.concatenate([a, b]).astype(np.float32) * 0.55


def preset_ui_purchase(seed: int = 0) -> np.ndarray:
    """Three-tone arpeggio + brief shimmer, "ka-ching"-ish."""
    rng = np.random.default_rng(seed)
    chunk = 0.10
    f1 = 700 + rng.uniform(-20, 20)
    a = sine(f1, chunk) * adsr(chunk, 0.003, 0.04, 0.7, 0.04)
    b = sine(f1 * 1.25, chunk) * adsr(chunk, 0.003, 0.04, 0.7, 0.04)
    c = sine(f1 * 1.5, chunk * 1.5) * adsr(chunk * 1.5, 0.003, 0.06, 0.7, 0.10)
    body = np.concatenate([a, b, c]).astype(np.float32)
    shimmer_len = 0.12
    shimmer = noise(shimmer_len, rng) * 0.3
    shimmer = highpass_simple(shimmer, 4500)
    shimmer = shimmer * expo_env(shimmer_len, fall=10)
    n_total = len(body) + len(shimmer)
    out = np.zeros(n_total, dtype=np.float32)
    out[: len(body)] += body * 0.7
    out[-len(shimmer):] += shimmer * 0.5
    return out


def preset_ui_quest_complete(seed: int = 0) -> np.ndarray:
    """Triumphant 4-note flourish: I - V - I (high) - V (high) over 0.7s."""
    rng = np.random.default_rng(seed)
    chunk = 0.18
    f0 = 523  # C5
    notes = [f0, f0 * 1.5, f0 * 2.0, f0 * 1.5]
    parts = []
    for f in notes:
        f += rng.uniform(-3, 3)
        a = sine(f, chunk) * 0.5
        b = sine(f * 2.0, chunk) * 0.2  # octave overtone
        seg = (a + b) * adsr(chunk, 0.005, 0.05, 0.7, 0.08)
        parts.append(seg)
    out = np.concatenate(parts).astype(np.float32) * 0.55
    return out


# ---------- Spell schools (8) ----------


def _airy_whoosh(length: float, rng, seed_off: int = 0,
                 cut_lo: float = 800, cut_hi: float = 6500) -> np.ndarray:
    """Reusable rising-whoosh body for spell casts."""
    n = int(length * SAMPLE_RATE)
    raw = noise(length, rng)
    seg = 6
    parts = np.array_split(raw, seg)
    cut = np.linspace(cut_lo, cut_hi, seg)
    swept = np.concatenate([lowpass_simple(p, c) for p, c in zip(parts, cut)])
    return np.resize(swept, n).astype(np.float32)


def preset_spell_fire_cast(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.65
    n = int(length * SAMPLE_RATE)
    swept = _airy_whoosh(length, rng, cut_lo=900, cut_hi=5000)
    crackle = highpass_simple(noise(length, rng), 2400)
    burst_env = (rng.random(n) > 0.985).astype(np.float32)
    burst_env = lowpass_simple(burst_env, 1500)
    crackle *= burst_env
    sub = sine(80, length, fm=np.linspace(0, 80, n).astype(np.float32)) * 0.4
    env = adsr(length, 0.04, 0.10, 0.8, 0.18)
    return mix((swept, 0.7), (crackle, 0.6), (sub, 0.4))[:n] * env * 0.85


def preset_spell_fire_impact(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.45
    n = int(length * SAMPLE_RATE)
    boom = sine(60, length, fm=np.linspace(0, -30, n).astype(np.float32)) * expo_env(length, 8)
    body = lowpass_simple(noise(length, rng), 1800)
    body *= expo_env(length, fall=6)
    crackle = highpass_simple(noise(length, rng), 3200) * expo_env(length, 4)
    return mix((boom, 0.85), (body, 0.55), (crackle, 0.4)) * 0.95


def preset_spell_ice_cast(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.55
    n = int(length * SAMPLE_RATE)
    # Rising glassy shimmer
    shimmer = highpass_simple(noise(length, rng), 4000) * expo_env(length, 3)
    # Tonal "ringing" partial
    f = 700
    fm_curve = np.linspace(0, 600, n).astype(np.float32)
    ring = sine(f, length, fm=fm_curve) * 0.4
    env = adsr(length, 0.05, 0.08, 0.7, 0.15)
    return mix((shimmer, 0.8), (ring, 0.5)) * env * 0.85


def preset_spell_ice_impact(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.42
    n = int(length * SAMPLE_RATE)
    # Sharp glass-shatter transient + low thud
    crack = highpass_simple(noise(0.08, rng), 3500) * expo_env(0.08, 18)
    thud = sine(140, length, fm=np.linspace(0, -50, n).astype(np.float32)) * expo_env(length, 6) * 0.6
    shimmer_tail = highpass_simple(noise(length, rng), 5000) * expo_env(length, 3)
    out = np.zeros(n, dtype=np.float32)
    out[: len(crack)] += crack * 0.9
    out += thud
    out += shimmer_tail * 0.4
    return out * 0.9


def preset_spell_lightning_cast(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.45
    n = int(length * SAMPLE_RATE)
    # Static-y body + rising filter sweep
    raw = noise(length, rng)
    sweep_part = _airy_whoosh(length, rng, cut_lo=2000, cut_hi=8000)
    static = highpass_simple(raw, 3500) * (0.5 + 0.5 * rng.random(n).astype(np.float32))
    env = adsr(length, 0.005, 0.05, 0.85, 0.12)
    return mix((sweep_part, 0.5), (static, 0.7)) * env * 0.85


def preset_spell_lightning_impact(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.55
    n = int(length * SAMPLE_RATE)
    # zap snap + thunder body
    zap = highpass_simple(noise(0.05, rng), 5000) * expo_env(0.05, 20)
    boom = lowpass_simple(noise(length, rng), 600) * expo_env(length, 4)
    crackle = highpass_simple(noise(length, rng), 3500) * expo_env(length, 6) * 0.5
    out = np.zeros(n, dtype=np.float32)
    out[: len(zap)] += zap
    out += boom * 0.9
    out += crackle * 0.4
    return out * 0.95


def preset_spell_arcane_cast(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.7
    n = int(length * SAMPLE_RATE)
    # Two detuned sines climbing in pitch, light shimmer overlay
    f = 220
    fm_curve = np.linspace(0, 200, n).astype(np.float32)
    a = sine(f, length, fm=fm_curve)
    b = sine(f * 1.5, length, fm=fm_curve * 1.5) * 0.6
    shimmer = highpass_simple(noise(length, rng), 5000) * expo_env(length, 2) * 0.4
    env = adsr(length, 0.05, 0.10, 0.85, 0.20)
    return mix((a, 0.4), (b, 0.4), (shimmer, 0.5)) * env * 0.85


def preset_spell_arcane_impact(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.55
    n = int(length * SAMPLE_RATE)
    # Bell bloom + low pulse + tail shimmer
    f = 440
    bell = sine(f, length) * expo_env(length, 4) * 0.6
    bell2 = sine(f * 1.5, length) * expo_env(length, 5) * 0.3
    pulse = sine(80, length, fm=np.linspace(0, -40, n).astype(np.float32)) * expo_env(length, 6) * 0.5
    shimmer = highpass_simple(noise(length, rng), 6000) * expo_env(length, 3) * 0.3
    return mix((bell, 0.7), (bell2, 0.4), (pulse, 0.6), (shimmer, 0.5)) * 0.9


# ---------- Footstep surfaces (6) ----------


def _footstep_base(thump_freq: float, body_lp: float, body_hp: float,
                   high_emphasis_db: float, length: float, rng) -> np.ndarray:
    n = int(length * SAMPLE_RATE)
    thump = sine(thump_freq + rng.uniform(-8, 8), length) * expo_env(length, fall=20) * 0.8
    body = noise(length, rng)
    body = lowpass_simple(body, body_lp)
    body = highpass_simple(body, body_hp)
    body *= expo_env(length, fall=10) * 0.6
    if high_emphasis_db > 0:
        hi = highpass_simple(noise(length, rng), 4000) * expo_env(length, fall=14)
        body = body + hi * (10 ** (high_emphasis_db / 20)) * 0.3
    return (thump * 0.8 + body).astype(np.float32) * 0.7


def preset_step_grass(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return _footstep_base(75, 1800, 250, 0.0, 0.16, rng)


def preset_step_stone(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return _footstep_base(95, 3200, 220, 3.0, 0.14, rng)


def preset_step_wood(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    # add a brief tonal "creak"
    base = _footstep_base(85, 2400, 200, 0.0, 0.16, rng)
    n = len(base)
    creak = sine(180, 0.06, fm=sweep(180, 240, 0.06)) * expo_env(0.06, 8) * 0.25
    out = base.copy()
    out[: len(creak)] += creak
    return out


def preset_step_metal(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = _footstep_base(110, 4500, 600, 5.0, 0.18, rng)
    # short metal ring
    ring_len = 0.10
    ring = sine(1200, ring_len) * expo_env(ring_len, 14) * 0.25
    n = max(len(base), len(ring))
    out = np.zeros(n, dtype=np.float32)
    out[: len(base)] += base
    out[: len(ring)] += ring
    return out


def preset_step_water(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.20
    body = lowpass_simple(noise(length, rng), 1200)
    body *= expo_env(length, fall=7) * 0.7
    splash = highpass_simple(noise(length, rng), 3500) * expo_env(length, fall=18) * 0.5
    return (body + splash).astype(np.float32) * 0.65


def preset_step_snow(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.22
    body = highpass_simple(noise(length, rng), 1500)
    body = lowpass_simple(body, 6500)
    body *= expo_env(length, fall=12)
    return body.astype(np.float32) * 0.55


# ---------- Impacts (5) ----------


def preset_impact_flesh(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.30
    n = int(length * SAMPLE_RATE)
    thud = sine(70, length, fm=np.linspace(0, -30, n).astype(np.float32)) * expo_env(length, 8) * 0.9
    body = lowpass_simple(noise(length, rng), 900) * expo_env(length, 6) * 0.6
    return mix((thud, 0.9), (body, 0.5)) * 0.9


def preset_impact_wood(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.30
    n = int(length * SAMPLE_RATE)
    knock = sine(170, length, fm=np.linspace(0, 40, n).astype(np.float32)) * expo_env(length, 14) * 0.7
    body = highpass_simple(noise(length, rng), 1500) * expo_env(length, 12) * 0.5
    return mix((knock, 0.8), (body, 0.5)) * 0.9


def preset_impact_metal(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.5
    n = int(length * SAMPLE_RATE)
    clang = sine(900, length) * expo_env(length, 5) * 0.45
    overt = sine(1700, length) * expo_env(length, 6) * 0.25
    overt2 = sine(2400, length) * expo_env(length, 7) * 0.20
    transient = highpass_simple(noise(0.05, rng), 5000) * expo_env(0.05, 20)
    out = np.zeros(n, dtype=np.float32)
    out[: len(transient)] += transient * 0.7
    out += clang + overt + overt2
    return out * 0.95


def preset_impact_stone(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.30
    n = int(length * SAMPLE_RATE)
    thump = sine(110, length, fm=np.linspace(0, -50, n).astype(np.float32)) * expo_env(length, 10) * 0.7
    body = lowpass_simple(noise(length, rng), 1400) * expo_env(length, 8) * 0.5
    crack = highpass_simple(noise(0.04, rng), 4000) * expo_env(0.04, 22) * 0.6
    out = np.zeros(n, dtype=np.float32)
    out[: len(crack)] += crack
    out += thump + body
    return out * 0.9


def preset_impact_shield_block(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 0.40
    n = int(length * SAMPLE_RATE)
    clang = sine(550, length) * expo_env(length, 6) * 0.55
    overt = sine(1100, length) * expo_env(length, 8) * 0.30
    transient = highpass_simple(noise(0.06, rng), 4500) * expo_env(0.06, 17)
    out = np.zeros(n, dtype=np.float32)
    out[: len(transient)] += transient * 0.7
    out += clang + overt
    return out * 0.95


# ---------- Ambience placeholders (7) ----------
# These are short SYNTH stand-ins so the catalogue has unique sfx_ids today.
# Replace via biome_ambience.py outputs once GPU is free.


def _drone_pad(f1: float, f2: float, length: float, rng) -> np.ndarray:
    n = int(length * SAMPLE_RATE)
    a = sine(f1, length, fm=np.zeros(n))
    b = sine(f2, length, fm=np.zeros(n))
    body = (a * 0.5 + b * 0.4) * expo_env(length, fall=0.3)
    floor = lowpass_simple(noise(length, rng), 200) * 0.15
    return (body + floor).astype(np.float32) * 0.5


def preset_amb_drone_lava(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return _drone_pad(55, 82, 4.0, rng)


def preset_amb_drone_ice(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return _drone_pad(70, 105, 4.0, rng)


def preset_amb_drone_mana(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return _drone_pad(110, 165, 4.0, rng)  # perfect-fifth tonality


def preset_amb_drone_grass(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return _drone_pad(90, 132, 4.0, rng)


def preset_amb_air_sweetener(seed: int = 0) -> np.ndarray:
    """Short windy whoosh, biome-agnostic placeholder."""
    rng = np.random.default_rng(seed)
    length = 1.6
    raw = noise(length, rng)
    swept = lowpass_simple(raw, 1200)
    env = adsr(length, 0.4, 0.4, 0.6, 0.6)
    return swept * env * 0.5


def preset_amb_distant_thunder(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 2.5
    n = int(length * SAMPLE_RATE)
    rumble = lowpass_simple(noise(length, rng), 220)
    rumble *= np.linspace(0, 1, n // 4).tolist() + np.linspace(1, 0.3, n - n // 4).tolist()
    return np.array(rumble, dtype=np.float32) * 0.6


def preset_amb_distant_boom(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    length = 2.0
    n = int(length * SAMPLE_RATE)
    thump = sine(50, length, fm=np.linspace(0, -10, n).astype(np.float32)) * expo_env(length, 1.5) * 0.8
    rumble = lowpass_simple(noise(length, rng), 350) * expo_env(length, 1.0) * 0.4
    return mix((thump, 0.9), (rumble, 0.6)) * 0.7


# ---------- registry ----------


@dataclass
class CatalogueEntry:
    id: str
    preset: Callable[[int], np.ndarray]
    category: str           # ui|sfx|ambience  -> Godot bus
    target_rms_db: float
    variants: int = 3
    tags: list[str] | None = None
    notes: str = ""


CATALOGUE: list[CatalogueEntry] = [
    # UI (-22 LUFS)
    CatalogueEntry("ui_select", preset_ui_select, "ui", -22.0, 3, ["ui", "select"]),
    CatalogueEntry("ui_error", preset_ui_error, "ui", -22.0, 3, ["ui", "error", "negative"]),
    CatalogueEntry("ui_open_menu", preset_ui_open_menu, "ui", -22.0, 3, ["ui", "menu", "open"]),
    CatalogueEntry("ui_close_menu", preset_ui_close_menu, "ui", -22.0, 3, ["ui", "menu", "close"]),
    CatalogueEntry("ui_pickup", preset_ui_pickup, "ui", -22.0, 3, ["ui", "pickup", "loot"]),
    CatalogueEntry("ui_purchase", preset_ui_purchase, "ui", -22.0, 3, ["ui", "shop", "purchase"]),
    CatalogueEntry("ui_quest_complete", preset_ui_quest_complete, "ui", -22.0, 3, ["ui", "quest", "fanfare"]),
    # Spell schools (-16 LUFS)
    CatalogueEntry("spell_fire_cast", preset_spell_fire_cast, "sfx", -16.0, 3, ["spell", "fire", "cast"]),
    CatalogueEntry("spell_fire_impact", preset_spell_fire_impact, "sfx", -16.0, 3, ["spell", "fire", "impact"]),
    CatalogueEntry("spell_ice_cast", preset_spell_ice_cast, "sfx", -16.0, 3, ["spell", "ice", "cast"]),
    CatalogueEntry("spell_ice_impact", preset_spell_ice_impact, "sfx", -16.0, 3, ["spell", "ice", "impact"]),
    CatalogueEntry("spell_lightning_cast", preset_spell_lightning_cast, "sfx", -16.0, 3, ["spell", "lightning", "cast"]),
    CatalogueEntry("spell_lightning_impact", preset_spell_lightning_impact, "sfx", -16.0, 3, ["spell", "lightning", "impact"]),
    CatalogueEntry("spell_arcane_cast", preset_spell_arcane_cast, "sfx", -16.0, 3, ["spell", "arcane", "cast"]),
    CatalogueEntry("spell_arcane_impact", preset_spell_arcane_impact, "sfx", -16.0, 3, ["spell", "arcane", "impact"]),
    # Footsteps (-18 LUFS)
    CatalogueEntry("step_grass", preset_step_grass, "sfx", -18.0, 4, ["step", "grass", "outdoor"]),
    CatalogueEntry("step_stone", preset_step_stone, "sfx", -18.0, 4, ["step", "stone", "indoor"]),
    CatalogueEntry("step_wood", preset_step_wood, "sfx", -18.0, 4, ["step", "wood", "indoor"]),
    CatalogueEntry("step_metal", preset_step_metal, "sfx", -18.0, 4, ["step", "metal"]),
    CatalogueEntry("step_water", preset_step_water, "sfx", -18.0, 4, ["step", "water", "wet"]),
    CatalogueEntry("step_snow", preset_step_snow, "sfx", -18.0, 4, ["step", "snow", "outdoor"]),
    # Impacts (-16 LUFS)
    CatalogueEntry("impact_flesh", preset_impact_flesh, "sfx", -16.0, 3, ["impact", "hit", "flesh"]),
    CatalogueEntry("impact_wood", preset_impact_wood, "sfx", -16.0, 3, ["impact", "wood"]),
    CatalogueEntry("impact_metal", preset_impact_metal, "sfx", -16.0, 3, ["impact", "metal"]),
    CatalogueEntry("impact_stone", preset_impact_stone, "sfx", -16.0, 3, ["impact", "stone"]),
    CatalogueEntry("impact_shield_block", preset_impact_shield_block, "sfx", -16.0, 3, ["impact", "shield", "block"]),
    # Ambience placeholders (-26 LUFS)
    CatalogueEntry("amb_drone_lava", preset_amb_drone_lava, "sfx", -26.0, 1, ["ambience", "drone", "lava_field"], notes="placeholder; replace via biome_ambience.py"),
    CatalogueEntry("amb_drone_ice", preset_amb_drone_ice, "sfx", -26.0, 1, ["ambience", "drone", "ice_cavern"], notes="placeholder; replace via biome_ambience.py"),
    CatalogueEntry("amb_drone_mana", preset_amb_drone_mana, "sfx", -26.0, 1, ["ambience", "drone", "mana_crystal"], notes="placeholder; replace via biome_ambience.py"),
    CatalogueEntry("amb_drone_grass", preset_amb_drone_grass, "sfx", -26.0, 1, ["ambience", "drone", "grassland"], notes="placeholder; replace via biome_ambience.py"),
    CatalogueEntry("amb_air_sweetener", preset_amb_air_sweetener, "sfx", -28.0, 2, ["ambience", "air"], notes="placeholder"),
    CatalogueEntry("amb_distant_thunder", preset_amb_distant_thunder, "sfx", -22.0, 2, ["ambience", "distant", "thunder"], notes="peak target"),
    CatalogueEntry("amb_distant_boom", preset_amb_distant_boom, "sfx", -22.0, 2, ["ambience", "distant", "boom"], notes="peak target"),
]


def build(out_dir: Path = SFX_DIR, manifest_path: Path | None = None,
          godot_root: Path | None = None) -> dict:
    """Synthesize the full extended catalogue + merge with the v1 manifest.

    Output:
      audio/sfx/<id>_v0.wav .. <id>_vN-1.wav    (synthesized + processed + QA'd)
      audio/sfx_manifest.json                   (merged with whatever was there)
      audio/godot/<cat>/<id>/...                (Godot drop-in via export_godot)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_path or (ASSETS / "audio" / "sfx_manifest.json")
    godot_root = godot_root or (ASSETS / "audio" / "godot")

    # Start from existing manifest so we keep the v1 demo entries.
    sounds_by_id: dict[str, dict] = {}
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        for snd in existing.get("sounds", []):
            sounds_by_id[snd["id"]] = snd

    # Author every entry in the catalogue + auto-include base presets so the
    # full catalogue includes the original 6 too.
    full_list = list(CATALOGUE)
    base_added = []
    for base_id, base_fn in BASE_PRESETS.items():
        if base_id in {e.id for e in CATALOGUE}:
            continue
        # Base preset categories are derived: ui_* -> ui, else sfx
        cat = "ui" if base_id.startswith("ui_") else "sfx"
        target = -22.0 if cat == "ui" else -16.0
        base_added.append(CatalogueEntry(
            id=base_id,
            preset=base_fn,
            category=cat,
            target_rms_db=target,
            variants=3,
            tags=[base_id.split("_")[0]],
            notes="from synth_sfx.py base presets",
        ))
    full_list.extend(base_added)

    started = time.monotonic()
    for entry in full_list:
        sid = entry.id
        variants_paths_rel: list[str] = []
        cue_processing: list[dict] = []
        for v in range(entry.variants):
            seed = (1000 + 31 * v + abs(hash(sid)) % 9719)
            samples = entry.preset(seed)
            # Process. Trim disabled for ambience (we want full duration kept).
            trim = not entry.category == "ambience"
            proc, rep = process_audio.process(
                samples,
                target_rms_db=entry.target_rms_db,
                peak_ceiling_db=-1.0,
                fade_in_ms=5.0,
                fade_out_ms=12.0,
                trim=trim,
            )
            out_path = out_dir / f"{sid}_v{v}.wav"
            process_audio.write_wav(out_path, proc)
            cue_processing.append({
                "variant": v,
                "duration_s": rep.duration_out,
                "rms_dbfs_in": rep.rms_db_in,
                "rms_dbfs_out": rep.rms_db_out,
                "peak_dbfs_out": rep.peak_db_out,
                "trim_ms": rep.trim_ms_head + rep.trim_ms_tail,
                "fade_ms": rep.fade_ms,
            })
            qa_dir = out_dir / f"{sid}_v{v}_qa"
            info = audio_qa.qa(out_path, qa_dir)
            cue_processing[-1]["qa"] = {
                "clipped": info["clipped_samples"],
                "click_count_estimate": info["click_count_estimate"],
            }
            variants_paths_rel.append(f"audio/sfx/{sid}_v{v}.wav")
        sounds_by_id[sid] = {
            "id": sid,
            "category": entry.category,
            "variants": variants_paths_rel,
            "cue": {
                "preset": sid,  # preset name == sound id in the extended catalogue
                "target_rms_db": entry.target_rms_db,
                "tags": entry.tags or [],
                "notes": entry.notes,
                "backend": "synth_sfx_extended",
                "processing": cue_processing,
            },
        }

    # Write merged manifest
    manifest = {"sounds": sorted(sounds_by_id.values(), key=lambda s: s["id"])}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    counts = export_godot.export_bank(manifest_path, godot_root)
    elapsed = time.monotonic() - started

    return {
        "manifest": str(manifest_path),
        "godot_root": str(godot_root),
        "sound_count": len(manifest["sounds"]),
        "variant_count": sum(len(s["variants"]) for s in manifest["sounds"]),
        "godot_export": counts,
        "elapsed_s": elapsed,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true",
                    help="Synthesize the full extended catalogue.")
    ap.add_argument("--out", type=Path, default=SFX_DIR)
    ap.add_argument("--manifest", type=Path, default=None)
    args = ap.parse_args()

    if not args.build:
        ap.print_help()
        return 0

    summary = build(out_dir=args.out, manifest_path=args.manifest)
    print(f"[synth_sfx_extended] {summary['sound_count']} sounds / "
          f"{summary['variant_count']} variants  ({summary['elapsed_s']:.1f}s)")
    print(f"  manifest -> {summary['manifest']}")
    print(f"  godot    -> {summary['godot_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
