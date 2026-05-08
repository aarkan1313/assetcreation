# Research Brief — Audio Pipeline (2026 SOTA)

## Goal

Identify 2026-current SOTA tools for **game-audio generation** — biome ambience, SFX (combat/footsteps/UI/spells), music (adaptive), TTS. Current pipeline produced output that the user judged as "noise/static for the most part" and we archived 189 MB on 2026-05-07.

## Hardware target

- RTX 5090 Laptop (24 GB VRAM, Blackwell sm_120, CUDA 12.8+ / torch >=2.7)
- Windows 11; Python 3.11/3.12 venvs preferred
- WSL2 acceptable for Linux-only deps

## Context

We have a fully-plumbed audio pipeline: 4-layer biome ambience model (bed_drone + bed_air + wildlife_sparse Poisson + distant_event Poisson), LUFS-targeted normalization per layer, multi-stem adaptive music with intent.json driving intensity ramps, Godot bus_layout export, audio_qa.py for spectrogram + waveform + LUFS metrics per WAV, frame-synced cue metadata. **The plumbing is correct.**

Output was bad — user audition verdict: "**some are ok, but mostly they sound like noise/static.**" Two contributing problems:
1. **Ambience prompts were generic.** Stable Audio Open 1.0 (1.21B params) was used with off-the-shelf prompts. Output is 19.6s loops at -28 dBFS, technically correct but artistically weak.
2. **SFX is procedural synth only.** `synth_sfx.py` and `synth_sfx_extended.py` produce algorithmic noise, not material-grounded recordings. ElevenLabs SFX route exists (`eleven_sfx.py`) but never run with real keys. Freesound CC0 ingest exists but never run.

We archived 189 MB of output to `_archive/audio_phase12_bake_2026_05_07/`. Pipeline tools retained.

**Current tools:**
- **Ambience:** `biome_ambience.py` + `local_audio_open.py` (Stable Audio Open 1.0 GPU bake, gated repo on HF)
- **SFX:** `synth_sfx.py` (procedural baseline), `eleven_sfx.py` (ElevenLabs cloud, unused), `cc0_ingest.py` (Freesound CC0, unused)
- **Music:** `local_music_yue.py` (YuE generative, parked — 4-second smoke test only), `adaptive_music.py` (procedural multi-stem)
- **TTS:** `local_tts_f5.py` (F5-TTS, unused), `openai_tts.py` (cloud, unused)
- **QA:** `audio_qa.py` (LUFS/peak/RMS/click detection), `lint_audio.py`, `loop_detect.py`

## Specific questions

1. **2026 SOTA for game ambience.** Is Stable Audio Open 1.0 still current, or has Stable Audio 2.x / ElevenLabs Sound Effects 2 / Suno-V5 / something else become the standard for ambient game audio loops? Specifically: 30-second biome-specific seamless loops at decent quality.

2. **Reference-conditioned ambience generation.** Stable Audio Open accepts prompts but not reference audio. Is there a 2026 model that takes "this 5-second sample of forest ambience" + a longer-length request and produces a stylistically-matched seamless loop? This would let us re-bake against curated style references instead of relying on text-only.

3. **2026 SOTA for game SFX.** Specifically focused, deterministic per-asset generation: "wood crack, sharp" → 0.3s WAV that sounds like wood cracking, not generic noise. ElevenLabs SFX is the obvious cloud option — what's the open-weights / self-hosted equivalent in 2026? Sound effect-specific diffusion models?

4. **Music generation 2026 SOTA.** YuE was hot in early 2025 but we haven't tested it real yet. Suno is API-only. Is there a 2026 open-weights music model that can produce game-quality multi-stem outputs (separate drums/bass/melody/pads stems for adaptive playback) suitable for fantasy-game tone?

5. **Procedural music vs generative.** Our `adaptive_music.py` produces procedural multi-stem with proper intensity ramps but the music itself is weak. Is there a 2026 hybrid approach — generative model that produces stems compatible with adaptive playback (intent.json-style state machine)?

6. **TTS for game NPCs.** F5-TTS is what we have plumbed. Is there a 2026 TTS that's better for *game character voicing* specifically — emotional range, voice cloning from short samples, multilingual, fantasy-character voice (not real-person clone)?

7. **Audio QA tooling.** We compute LUFS / peak / RMS / click detection. Is there a 2026 standard for "game audio quality scoring" — perceptual quality, loop seam detection, distortion detection — that goes beyond raw signal metrics? CLAP embeddings for "does this sound like the prompt" verification?

8. **Freesound / curated CC0 search.** `cc0_ingest.py` is plumbed for Freesound. What's the 2026 best-practice for building a curated game-audio library from CC0 sources? Tools that auto-tag, auto-categorize, auto-lufs-normalize?

## Format of response

Per question:
1. Top 2-3 tool/approach recommendations with one-paragraph why
2. Hardware/install fit (RTX 5090 sm_120 / Windows native)
3. License + cost notes (open-weights or self-hosted preferred; commercial OK if cost-effective per asset)
4. Maturity check
5. **Honest comparison** — does the new tool actually beat Stable Audio Open / synth_sfx / YuE for game-specific use, or is it lateral?

## Out of scope

- Voice acting recording (we won't hire voice talent)
- DAW integration (we want programmatic batch)
- Real-time audio synthesis at runtime (we bake to WAVs)

## After response returns

Update `docs/pipeline_reviews/03_audio.md` and `pipelines/audio/README.md`. The user wants to:
- Identify which lane(s) need re-baking when game-design intent crystallizes
- Decide whether current tools survive or need replacement
- Build a "play this audio sample" reference for each biome before re-prompting Stable Audio
