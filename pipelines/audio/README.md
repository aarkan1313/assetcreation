# Audio Pipeline

**Status:** ✅ Working end-to-end (offline-first via procedural synth; cloud SFX via ElevenLabs activated by `ELEVENLABS_API_KEY`).

Per `research/E_audio.md`'s recommended chain:

```
generate (synth_sfx | eleven_sfx) ─→ process (trim/fade/normalize/limit)
                                       ↓
                              audio_qa (waveform + spectrogram + sanity)
                                       ↓
                                   sfx_manifest.json
                                       ↓
                       export_godot (AudioStreamWAV + AudioStreamRandomizer)
                                       ↓
                                res://audio/<cat>/<id>/
```

## Files

| File | Role |
|---|---|
| [synth_sfx.py](synth_sfx.py) | Pure-Python procedural SFX. 6 presets: `ui_click`, `ui_confirm`, `ui_back`, `sword_swing`, `fireball_cast`, `footstep`. No keys, no GPU, fully deterministic by seed. |
| [eleven_sfx.py](eleven_sfx.py) | ElevenLabs Sound Effects API adapter. Gated on `ELEVENLABS_API_KEY`. Pulls PCM 44100 directly so we never need ffmpeg/pydub. |
| [process_audio.py](process_audio.py) | Trim + fade + RMS-target normalize + true-peak limiter. Pure numpy. |
| [audio_qa.py](audio_qa.py) | Waveform PNG + spectrogram PNG (numpy STFT) + clipped/click sanity. |
| [loop_detect.py](loop_detect.py) | Cross-correlation seamless-loop finder + crossfade synthesizer. For ambience/music. |
| [export_godot.py](export_godot.py) | Reads `sfx_manifest.json`, copies WAVs into `audio/godot/<cat>/<id>/`, emits per-WAV `.import` files, `randomizer.tres` (AudioStreamRandomizer wrapping all variants), `cue.json`, and a `bus_layout.tres` skeleton. |
| [build_demo.py](build_demo.py) | End-to-end demo: synth 3 sounds × 3 variants → process → QA → manifest → export. |

## Quickstart

```powershell
# Build the 3-sound, 9-variant demo set:
python pipelines\audio\build_demo.py

# Or step-by-step:
python pipelines\audio\synth_sfx.py fireball_cast --out audio\sfx\fb_v0.wav --variants 3 --seed 7
python pipelines\audio\process_audio.py audio\sfx\fb_v0.wav --out audio\sfx\fb_v0_p.wav --target-rms-db -16
python pipelines\audio\audio_qa.py audio\sfx\fb_v0_p.wav

# Cloud route (only when ELEVENLABS_API_KEY is set):
python pipelines\audio\eleven_sfx.py --prompt "short fireball cast, dry ignition, airy whoosh, no explosion tail" --duration 0.8 --out audio\sfx\fireball_eleven.wav
```

Drop `audio/godot/` into a Godot 4.5 project at `res://audio/`:

```gdscript
var s := load("res://audio/sfx/fireball_cast/randomizer.tres")
$AudioStreamPlayer.stream = s
$AudioStreamPlayer.play()
```

## What we did NOT add (and why)

- **`ffmpeg`** — not installed locally. Every existing piece works without it: PCM-44100 from ElevenLabs avoids mp3 decode; WAV is the only on-disk format for SFX; OGG/MP3 conversion is reserved for music/ambience and is a future install. When ffmpeg is added, swap `eleven_sfx`'s mp3 branch and add `convert_format.py`.
- **`pyloudnorm` / true LUFS** — heavy install. Our RMS-dBFS proxy is within ~2 dB of true short-term LUFS for SFX; that's enough for game-asset normalization. Real LUFS goes in when shipping.
- **`librosa`** — only needed if we want pitch/tempo/onset detection beyond loop seam search. Not required for the demo.
- **AI music** — Suno/Lyria/Udio are recommended in the research, but their licenses + headless automation paths are unclear. Music stays a manual workflow.
- **Voice / TTS** — placeholder. Adding OpenAI TTS or ElevenLabs TTS is the same shape as `eleven_sfx.py`; gated on a key.

## Loudness targets (E_audio defaults)

| Category | RMS target (dBFS proxy) | True-peak ceiling |
|---|---:|---:|
| UI         | -22 | -1 |
| Combat/spell | -16 | -1 |
| Voice      | -18 | -1 |
| Ambience   | -26 | -2 |
| Music      | -20 | -1 |

`process_audio.py --target-rms-db ...` controls this per call. The build demo passes per-category targets through its `DEMO` table.

## Output contract

```
audio/sfx/<id>_v<N>.wav                 final processed WAVs
audio/sfx/<id>_v<N>_qa/                 waveform.png + spectrogram.png + qa.json
audio/sfx_manifest.json                 inventory for the exporter
audio/godot/                            Godot drop-in
  bus_layout.tres                       Master/SFX/UI/Voice/Ambience/Music
  README.txt
  ui/<id>/<id>_v<N>.wav (+.import)      per category
  ui/<id>/randomizer.tres
  ui/<id>/cue.json                      provenance + processing report
  sfx/<id>/...
```

## Demo measurements

```
ui_click_v0:       dur 0.064s  rms -22.0 dBFS  peak -3.2 dBFS  clipped 0
sword_swing_v0:    dur 0.369s  rms -16.0 dBFS  peak -1.1 dBFS  clipped 0
fireball_cast_v0:  dur 0.690s  rms -16.0 dBFS  peak -1.0 dBFS  clipped 0
```

## Cloud-key contract

| Env var | Activates | Notes |
|---|---|---|
| `ELEVENLABS_API_KEY` | `eleven_sfx.py` | endpoint forced to `pcm_44100` (no mp3 decode) |
| `FREESOUND_API_KEY`  | `cc0_ingest.py --freesound QUERY` | filters to license:"Creative Commons 0" |
| `OPENAI_API_KEY`     | `openai_tts.py --run` | also requires `--max-cost-usd <cap>`; default mode is plan-only |
| (gated) `MESHY_AUTH_FOR_THIS_BATCH=YES` | n/a here (props only) | listed for cross-pipeline awareness |

---

## v3 push (2026-05-06 PM, Build chat A2) — decision tree

The pipeline now has 5 generation backends + 4 dogfood/integration tools +
3 GPU-bound scaffolds + a documented adaptive music lane. Here's how to
pick what to use for a given asset.

### Decision tree — which backend should I reach for?

```
Need a new sound. What kind?
├── UI click / footstep / impact / spell-cast / pickup
│       → synth_sfx_extended.py (39 presets ready; deterministic by seed)
│         Use when: instant, free, license-clean, "good enough to ship".
│         Skip when: need recognizable real-world foley (then library / cloud).
│
├── A specific real-world recording (bird / wind / stream / thunder)
│       → cc0_ingest.py --sonniss DIR  (one-time bulk ingest from a Sonniss bundle)
│         + cc0_ingest.py --freesound QUERY (per-clip web grab, needs FREESOUND_API_KEY)
│         Use when: you have or can obtain royalty-free real audio.
│         Don't use when: no library entry exists and you can't acquire one.
│
├── A polished one-shot (sword swing variant, custom UI confirm chime)
│       → eleven_sfx.py  (cloud, ElevenLabs SFX API; needs ELEVENLABS_API_KEY)
│         Use when: synth result is too uniform / synthetic-sounding for a hero asset.
│         ~$0.10-0.30 per 8-sec clip; expect 1-5 sec wall time.
│
├── A long ambience bed / atmospheric drone
│       → biome_ambience.py + local_audio_open.py
│         Recipe: pipelines/audio/recipes/biome_ambience.json (10 biomes wired).
│         Backend: Stable Audio Open 1.0 on the 5090 (real beds).
│         Today: --dry-run silent placeholders; flip when GPU is free.
│
├── Voice line / NPC bark / placeholder dialogue
│       → openai_tts.py  (plan-only by default; --run requires OPENAI_API_KEY +
│                          --max-cost-usd cap)
│         9 voices (alloy / ash / ballad / coral / echo / fable / nova / sage /
│         shimmer); gpt-4o-mini-tts ~ $0.001/line, tts-1 ~ $0.025/line.
│         Don't use when: shipping voice acting needed (commission instead).
│
├── Adaptive music track (combat / exploration / boss / town)
│       → adaptive_music.py --intent recipes/music_intents/<id>.json
│         Scaffolds the AudioStreamSynchronized + Godot controller.
│         REPLACE the placeholder stems with real audio (manual).
│         No license-clean OPEN-WEIGHTS music model is wired today
│         (see: research/K_open_weights_2026.md item 11 — YuE pilot, parked).
│
└── HRTF / 3D-positioned ambience emitter
        → see audio/godot/spatial/SpatialEmitter.gd (auto-falls-back to
          AudioStreamPlayer3D if the godot-resonance-audio addon isn't installed)
          Install steps: pipelines/audio/recipes/hrtf_resonance.json
          Verify: `godot --headless --quit-after 1 --script res://audio/godot/spatial/HRTFVerify.gd`
```

### "When to gate vs build" — backend status table

| Backend | Status | Unblock action |
|---|---|---|
| `synth_sfx` / `synth_sfx_extended` | ✅ ships today | (none — always available) |
| `eleven_sfx` | ✅ adapter built | set `ELEVENLABS_API_KEY` |
| `openai_tts` | ✅ plan-only mode ships; `--run` gated | set `OPENAI_API_KEY` + pass `--max-cost-usd` cap |
| `local_audio_open` (Stable Audio Open) | ✅ adapter + dry-run plumbing | free 5090 + accept HF gated license; no code changes |
| `cc0_ingest --sonniss` | ✅ ingester built | manual download Sonniss GDC bundle, run with `--sonniss DIR` |
| `cc0_ingest --freesound` | ✅ ingester built | set `FREESOUND_API_KEY` (free) |
| `biome_ambience` | ✅ runner built; 10 biomes wired | flip from `--dry-run` once SAO unblocked |
| `ambience_pack` | ✅ Godot exporter ships | (none — runs CPU-only) |
| `loop_detect` (v2 phase-aware) | ✅ default | (none) |
| `process_audio` (true LUFS) | ✅ pyloudnorm-backed | (`pip install pyloudnorm` already in place) |
| `gallery.py` | ✅ static HTML | (none — open `audio/gallery.html`) |
| `lint_audio.py` | ✅ strict gating | runs after every catalogue change |
| `suggest_sfx_for_record.py` | ✅ suggestion tool | runs alongside game_data regen |
| `adaptive_music.py` | ✅ scaffold | **stems are placeholder silent WAVs**; replace with real audio |
| `ffmpeg_decode.py` (optional) | ✅ helper | install ffmpeg on host (winget Gyan.FFmpeg / apt install ffmpeg) |
| `godot-resonance-audio` HRTF | ⏸️ recipe + scaffold ship | unzip release into `res://addons/`; restart Godot |
| MusicGen / AudioCraft / YuE music | ⏸️ no adapter | research K-rec #11 YuE pilot when budget allows |

### Authoring + integration helpers (v3-new)

| Tool | What it produces | When to run |
|---|---|---|
| `gallery.py` | `audio/gallery.html` browser (autoplay + waveform thumbs + LUFS column) | After any catalogue change (synth / ambience / library) |
| `lint_audio.py` | `audio/lint_audio_report.json` + stdout summary | Before merging game_data updates that reference sfx |
| `suggest_sfx_for_record.py` | `audio/suggestions.{json,md}` + `sfx_id_patch.jsonl` | Before regenerating game_data records |
| `loop_detect.py --metric phase` (default) | Better seams on tonal drone beds | Auto-applied by `biome_ambience.py` |
| `ffmpeg_decode.py --probe` | One-shot check whether ffmpeg is installed | Before running cc0_ingest on MP3-only Freesound sources |
| `adaptive_music.py --emit-stub <id>` | Starter intent JSON | Before authoring a new music track |

### Loudness targets (LUFS / dBTP) — quick reference

The full authoring guide is in
[`pipelines/audio/LUFS_AUTHORING_GUIDE.md`](LUFS_AUTHORING_GUIDE.md). Quick
table for normalization targets:

| Category | Integrated LUFS | True-peak ceiling | Notes |
|---|---:|---:|---|
| UI click / confirm    | -22 | -1 dBTP | Short; usually fall back to RMS dBFS |
| Footstep              | -20 | -1 dBTP | Per-surface tuning lives in `synth_sfx_extended.py` |
| Combat / spell impact | -16 | -1 dBTP | High transient; expect 5-8 dB peak headroom |
| Spell cast            | -18 | -1 dBTP | Slightly quieter than impact for asymmetry |
| Voice line            | -18 | -1 dBTP | TTS or live-recorded |
| Music                 | -20 | -1 dBTP | Per-stem on the synchronized stream |
| Ambience bed (drone)  | -28 | -1 dBTP | Mixed continuously; needs lowest target |
| Ambience bed (air)    | -30 | -1 dBTP | Even lower so sweeteners can poke through |
| Ambience sweetener (wildlife) | -22 (peak) | -1 dBTP | Triggered one-shots; peak-target not RMS |
| Ambience sweetener (distant)  | -20 (peak) | -1 dBTP | Rare events; -20 reads as "far but real" |

