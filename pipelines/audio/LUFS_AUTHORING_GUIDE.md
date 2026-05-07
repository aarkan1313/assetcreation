# LUFS / dBTP authoring guide

Single source of truth for audio loudness targets across the v3 catalogue.
Aligns to **EBU R128 / BS.1770-4** for measurements ≥ 400 ms (true LUFS via
`pyloudnorm`) and falls back to RMS-dBFS for shorter one-shots (UI clicks,
footsteps) where the integrated-LUFS gate would silence them.

## What "loudness" means here

Three numbers matter:

| Term | Symbol | What it measures | When you care |
|---|---|---|---|
| **Integrated LUFS** | LUFS-I | EBU R128 weighted, gated, full-clip mean | Any sound ≥ 400 ms |
| **Short-term LUFS** | LUFS-S | EBU R128 weighted over a 3-sec sliding window | Music / ambience that varies |
| **True-peak (dBTP)** | dBTP | Peak after inter-sample peak modeling | Always — the limiter ceiling |
| **RMS dBFS** | dBFS-rms | Simple root-mean-square; no weighting / gating | Sounds < 400 ms (gate would silence them) |

`pipelines/audio/process_audio.py::rms_lufs_proxy()` returns LUFS-I when
the input is long enough and pyloudnorm is installed; otherwise it returns
RMS-dBFS. The function name is preserved across both behaviors so callers
don't have to branch.

## The single canonical table

```
┌────────────────────────────┬───────────┬──────────────────┬────────────────┐
│ Category                   │ LUFS-I    │ True-peak (dBTP) │ Headroom rule  │
├────────────────────────────┼───────────┼──────────────────┼────────────────┤
│ UI click / confirm         │ −22       │ −1               │ RMS-dBFS proxy │
│ UI menu open / close       │ −22       │ −1               │ RMS-dBFS proxy │
│ UI pickup / purchase       │ −20       │ −1               │ RMS-dBFS proxy │
│ UI quest-complete / level  │ −16       │ −1               │ Hero stinger   │
│ Footstep                   │ −20       │ −1               │ Per-surface    │
│ Spell cast (single-target) │ −18       │ −1               │ 4 dB headroom  │
│ Spell cast (AoE / hero)    │ −16       │ −1               │ 6 dB headroom  │
│ Spell impact / blast       │ −16       │ −1               │ 8 dB headroom  │
│ Weapon swing               │ −18       │ −1               │ 4 dB headroom  │
│ Weapon impact (flesh)      │ −16       │ −1               │ 6 dB headroom  │
│ Weapon impact (metal)      │ −16       │ −1               │ 6 dB headroom  │
│ Voice — narration / lore   │ −18       │ −1               │ 4 dB headroom  │
│ Voice — combat barks       │ −16       │ −1               │ 6 dB headroom  │
│ Music — exploration        │ −20       │ −1               │ 4 dB headroom  │
│ Music — combat / boss      │ −18       │ −1               │ 4 dB headroom  │
│ Music — town / menu        │ −22       │ −1               │ 6 dB headroom  │
│ Ambience bed_drone         │ −28       │ −1               │ Continuous     │
│ Ambience bed_air           │ −30       │ −1               │ Continuous     │
│ Ambience wildlife (peak)   │ −22       │ −1               │ Peak target    │
│ Ambience distant (peak)    │ −20       │ −1               │ Peak target    │
└────────────────────────────┴───────────┴──────────────────┴────────────────┘
```

These targets are **per-stem**, not per-mix. The runtime mix lives in the
Godot bus tree (Master → SFX / UI / Voice / Ambience / Music + AmbienceReverb
send) and is mixed live by gameplay code. Authoring is responsible for the
*intrinsic* loudness of each clip; the bus mix adjusts the *contextual*
loudness.

## How the targets were derived

* **UI ≤ -22 LUFS** — UI sits under voice and combat in the mix. Targeting
  -22 keeps it audible without drawing attention away from gameplay.
* **Combat/spell -16 LUFS** — The "loud" tier. -16 + -1 dBTP is a 15 dB
  dynamic envelope that survives true-peak limiting on transient impacts.
* **Voice -18 LUFS** — Sits 2 dB above music to ensure intelligibility,
  6 dB below combat impacts so impacts duck voice naturally.
* **Music -20 LUFS** — Streaming-platform loudness reference (Spotify
  -14 LUFS broadcast target gives ~4 dB programmer headroom). Game music
  needs to sit *under* SFX, hence -20.
* **Ambience bed_drone -28 LUFS / bed_air -30 LUFS** — Borrowed from
  Skyrim & Elden Ring postmortems (research E2 §2). The wide gap between
  the bed and sweeteners (-22/-20 peak) gives sweeteners the perceptual
  "punch" without making the bed too quiet to feel present.

## Per-tool defaults

The following tools use these targets by default — no flag needed unless
you want to override:

| Tool | Default target | Override flag |
|---|---|---|
| `synth_sfx_extended.py --build` | per-preset (table above) | `--target-rms-db` per preset |
| `process_audio.py` | `--target-rms-db -16` (combat) | `--target-rms-db <db>` |
| `biome_ambience.py` | per-stem from recipe (`lufs_target`) | edit `recipes/biome_ambience.json` |
| `cc0_ingest.py` | -23 LUFS (permissive) | `--target-rms-db <db>` (planned) |
| `ambience_pack.py` | inherits from `biome_ambience` | not configurable |

## How to verify a clip post-authoring

```bash
# Single-clip LUFS measurement
python -c "
import sys; sys.path.insert(0,'pipelines/audio')
import wave, numpy as np, process_audio
samples, sr = process_audio.read_wav(sys.argv[1])
print(f'  duration: {len(samples)/sr:.2f}s')
print(f'  RMS dBFS: {process_audio.rms_lufs_proxy(samples, sr):.2f}')
print(f'  peak dBTP: {process_audio.peak_db(samples):.2f}')
" audio/sfx/spell_fire_cast_v0.wav

# Bulk audit (every variant in the manifest)
python pipelines/audio/audio_qa.py audio/sfx/*.wav
```

The bulk audit writes a `qa.json` next to each `.wav` with
`rms_dbfs_out`, `peak_dbfs_out`, and a click-count estimate.

## Diagnosing LUFS misses

| Symptom | Likely cause | Fix |
|---|---|---|
| Clip measures right but sounds quiet vs others | Real LUFS used on a transient where peak limiter ate the body | Lower target by 2 dB or add soft-knee compressor before limiter |
| Clip measures wrong (off by >3 dB) | Clip < 400 ms; pyloudnorm gate dropped to RMS-dBFS proxy | Expected; the proxy is within ~2 dB of true LUFS for short SFX |
| Clip clipped (peak > -0.9 dBTP) | Limiter ceiling too permissive OR true-peak calc rounded | Re-run with `--peak-ceiling-db -1.5` |
| Bed_drone louder than bed_air | They share a bus & sum at runtime; bed_air is intentionally quieter | Working as designed; raise `bed_air.lufs_target` in recipe to taste |
| Sweetener feels too sparse | Poisson lambda * density_multiplier too low | Edit recipe `poisson_lambda_per_sec` or zone `density` |

## Marginal cases known today (2026-05-06 v3)

From the v2 audit (carried forward — not regressed):

```
impact_metal_v0..v2          rms ~-18.7  target -16   (peak ceiling won)
spell_arcane_impact_v0..v2   rms ~-20.4  target -16   (bell-bloom transient)
spell_fire_impact_v0..v1     rms ~-19.3  target -16
```

These are correct behavior under a true-peak limiter at -1 dBTP. The clip
authoring is fine; the report number "looks low" because the limiter is
catching the transient before the body of the sound averages up. A future
tweak — either a 2 dB target relaxation for impact-class presets or a
soft-knee compressor before the limiter — would close the gap on paper.

## Targets per audience platform

These are **content** targets (what the asset measures on disk), not
**delivery** targets (what the game outputs after the bus mix):

| Audience platform | Recommended overall mix LUFS-I | How to achieve |
|---|---:|---|
| PC speakers / loud headphones | -16 LUFS | Default bus mix, no master adjust |
| Console TV speakers | -23 LUFS | -7 dB on Master via accessibility menu |
| Mobile / quiet listening | -18 LUFS | -2 dB on Master |
| EBU R128 broadcast | -23 LUFS | Master normalized post-mix in Audacity / ffmpeg-loudnorm |

The audio pipeline does not author for any specific audience. Authoring
targets above are **content-loudness intrinsic to the clip**; the runtime
bus mix and accessibility menu provide the delivery normalization.

## Cross-references

* Per-tool details: `pipelines/audio/README.md`
* Process spine: `pipelines/audio/process_audio.py` (LUFS measurement function)
* Loudness research: `research/E_audio.md` §6, `research/E2_audio_local_ambience.md` §2.3
* Live measurements: `audio/sfx/<id>_v<N>_qa/qa.json`
